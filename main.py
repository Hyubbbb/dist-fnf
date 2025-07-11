"""
SKU 분배 최적화 메인 실행 파일
"""

import sys
import os
import time

# 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules import (
    DataLoader, StoreTierSystem, SKUClassifier, 
    ResultAnalyzer, ResultVisualizer, ExperimentManager
)
from modules.three_step_optimizer import ThreeStepOptimizer
from config import EXPERIMENT_SCENARIOS, DEFAULT_TARGET_STYLE, DEFAULT_SCENARIO


def run_optimization(target_style=DEFAULT_TARGET_STYLE, scenario=DEFAULT_SCENARIO, 
                    show_detailed_output=False, create_visualizations=True,
                    sku_file='ord/ord.json', store_file='shop/shop.json',
                    save_allocation_results=True, save_experiment_summary=True,
                    save_png_matrices=True, save_excel_matrices=True):
    """
    SKU 분배 최적화 실행
    
    Args:
        target_style: 대상 스타일 코드
        scenario: 실험 시나리오 이름
        show_detailed_output: 상세 출력 여부
        create_visualizations: 시각화 생성 여부
        sku_file: SKU 데이터 파일명
        store_file: 매장 데이터 파일명
        save_allocation_results: allocation_results.csv 저장 여부
        save_experiment_summary: experiment_summary.txt 저장 여부
        save_png_matrices: step별 PNG 매트릭스 저장 여부
        save_excel_matrices: step별 Excel 매트릭스 저장 여부
    """
    
    start_time = time.time()
    
    print("🚀 SKU 분배 최적화 시작")
    print(f"   대상 스타일: {target_style}")
    print(f"   시나리오: {scenario}")
    print(f"   SKU 파일: {sku_file}")
    print(f"   매장 파일: {store_file}")
    print("="*50)
    
    try:
        # 1. 데이터 로드 및 전처리
        print("\n📊 1단계: 데이터 로드 및 전처리")
        data_loader = DataLoader(sku_file=sku_file, store_file=store_file)
        data_loader.load_data()
        data_loader.filter_by_style(target_style)
        data = data_loader.get_basic_data_structures()
        
        # 2. 매장 Tier 시스템 설정
        print("\n🏆 2단계: 매장 Tier 시스템 설정")
        tier_system = StoreTierSystem()
        target_stores = tier_system.get_target_stores(data['stores'], target_style)
        store_allocation_limits = tier_system.create_store_allocation_limits(target_stores)
        
        # 3. SKU 분류
        print("\n🔍 3단계: SKU 분류 (희소/충분)")
        sku_classifier = SKUClassifier(data_loader.df_sku_filtered)
        scarce_skus, abundant_skus = sku_classifier.classify_skus(data['A'], target_stores)
        
        if show_detailed_output:
            sku_classifier.print_detailed_summary(data['A'], show_details=True)
        
        # 4. 3-Step 최적화
        print("\n🎯 4단계: 3-Step 최적화")
        three_step_optimizer = ThreeStepOptimizer(target_style)
        
        # 시나리오 파라미터 가져오기
        scenario_params = EXPERIMENT_SCENARIOS[scenario].copy()
        
        optimization_result = three_step_optimizer.optimize_three_step(
            data, scarce_skus, abundant_skus, target_stores,
            store_allocation_limits, data_loader.df_sku_filtered,
            tier_system, scenario_params
        )
        
        if optimization_result['status'] != 'success':
            print("❌ 3-Step 최적화 실패")
            return None
        
        final_allocation = optimization_result['final_allocation']
        allocation_summary = optimization_result
        
        # 5. 결과 분석
        print("\n📊 5단계: 결과 분석")
        analyzer = ResultAnalyzer(target_style)
        analysis_results = analyzer.analyze_results(
            final_allocation, data, scarce_skus, abundant_skus,
            target_stores, data_loader.df_sku_filtered, data['QSUM'], tier_system
        )
        
        # 6. 결과 DataFrame 생성
        df_results = analyzer.create_result_dataframes(
            final_allocation, data, scarce_skus, target_stores,
            data_loader.df_sku_filtered, tier_system, {}
        )
        
        # 7. 실험 결과 저장
        print("\n💾 7단계: 실험 결과 저장")
        experiment_manager = ExperimentManager()
        
        # 시나리오 파라미터 준비
        scenario_params = EXPERIMENT_SCENARIOS[scenario].copy()
        scenario_params['target_style'] = target_style
        
        # 출력 경로 생성
        experiment_path, file_paths = experiment_manager.create_experiment_output_path(scenario, target_style)
        
        # 결과 저장 (파라미터에 따라 선택적 저장)
        if save_allocation_results or save_experiment_summary:
            scenario_name = f"{target_style}_{scenario}"
            experiment_manager.save_experiment_results(
                file_paths, df_results if save_allocation_results else pd.DataFrame(), 
                analysis_results, scenario_params, scenario_name, allocation_summary,
                save_allocation_results=save_allocation_results,
                save_experiment_summary=save_experiment_summary
            )
        
        # 8. 시각화 (옵션)
        if create_visualizations:
            print("\n📈 8단계: 시각화 생성")
            visualizer = ResultVisualizer()
            
            try:
                # PNG 저장 경로 생성
                import os
                visualization_dir = experiment_path

                # Step별 allocation matrix 경로
                if save_png_matrices:
                    matrix_step1_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step1_allocation_matrix.png")
                    matrix_step2_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step2_allocation_matrix.png")
                    matrix_step3_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step3_allocation_matrix.png")

                    # 배분 매트릭스 히트맵 (Step1, Step2, Step3)
                    if hasattr(three_step_optimizer, 'step1_allocation') and three_step_optimizer.step1_allocation:
                        visualizer.create_allocation_matrix_heatmap(
                            three_step_optimizer.step1_allocation,
                            target_stores, data['SKUs'], data['QSUM'],
                            data_loader.df_sku_filtered, data['A'], tier_system,
                            save_path=matrix_step1_path, max_stores=None, max_skus=None,
                            fixed_max=3, SHOP_NAMES=data.get('SHOP_NAMES')
                        )

                    if hasattr(three_step_optimizer, 'allocation_after_step2') and three_step_optimizer.allocation_after_step2:
                        visualizer.create_allocation_matrix_heatmap(
                            three_step_optimizer.allocation_after_step2,
                            target_stores, data['SKUs'], data['QSUM'],
                            data_loader.df_sku_filtered, data['A'], tier_system,
                            save_path=matrix_step2_path, max_stores=None, max_skus=None,
                            fixed_max=3, SHOP_NAMES=data.get('SHOP_NAMES')
                        )

                    # Step3 (최종)
                    visualizer.create_allocation_matrix_heatmap(
                        final_allocation, target_stores, data['SKUs'],
                        data['QSUM'], data_loader.df_sku_filtered, data['A'], tier_system,
                        save_path=matrix_step3_path, max_stores=None, max_skus=None,
                        fixed_max=3, SHOP_NAMES=data.get('SHOP_NAMES')
                    )
                
                # 엑셀 배분 매트릭스 생성 (Step별)
                if save_excel_matrices:
                    print("\n📊 엑셀 배분 매트릭스 생성 중...")
                    
                    # Step별 엑셀 파일 경로
                    excel_step1_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step1_allocation_matrix.xlsx")
                    excel_step2_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step2_allocation_matrix.xlsx")
                    excel_step3_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step3_allocation_matrix.xlsx")
                    
                    # 최적화 시간 정보 추출
                    step_analysis = optimization_result.get('step_analysis', {})
                    total_optimization_time = (
                        step_analysis.get('step1', {}).get('time', 0) +
                        step_analysis.get('step2', {}).get('time', 0) +
                        step_analysis.get('step3', {}).get('time', 0)
                    )
                    
                    if hasattr(three_step_optimizer, 'step1_allocation') and len(three_step_optimizer.step1_allocation) > 0:
                        visualizer.create_allocation_matrix_excel(
                            three_step_optimizer.step1_allocation,
                            target_stores, data['SKUs'], data['QSUM'],
                            data_loader.df_sku_filtered, data['A'], tier_system,
                            save_path=excel_step1_path, SHOP_NAMES=data.get('SHOP_NAMES'),
                            optimization_time=step_analysis.get('step1', {}).get('time', 0)
                        )
                    
                    if hasattr(three_step_optimizer, 'allocation_after_step2') and len(three_step_optimizer.allocation_after_step2) > 0:
                        visualizer.create_allocation_matrix_excel(
                            three_step_optimizer.allocation_after_step2,
                            target_stores, data['SKUs'], data['QSUM'],
                            data_loader.df_sku_filtered, data['A'], tier_system,
                            save_path=excel_step2_path, SHOP_NAMES=data.get('SHOP_NAMES'),
                            optimization_time=step_analysis.get('step1', {}).get('time', 0) + step_analysis.get('step2', {}).get('time', 0)
                        )
                    
                    if len(final_allocation) > 0:
                        visualizer.create_allocation_matrix_excel(
                            final_allocation, target_stores, data['SKUs'],
                            data['QSUM'], data_loader.df_sku_filtered, data['A'], tier_system,
                            save_path=excel_step3_path, SHOP_NAMES=data.get('SHOP_NAMES'),
                            optimization_time=total_optimization_time
                        )
                
            except Exception as e:
                print(f"⚠️ 시각화 생성 중 오류: {str(e)}")
                print("   (시각화 오류는 전체 프로세스에 영향을 주지 않습니다)")
        
        # 3-Step 분해 분석 추가
        if optimization_result['status'] == 'success':
            try:
                step_analysis = three_step_optimizer.get_step_analysis()
                
                print(f"📊 3-Step 분해 결과:")
                print(f"   🎯 Step1 - 간접 다양성 최적화:")
                print(f"       간접 다양성 점수: {step_analysis['step1']['objective']:.1f}")
                print(f"       선택된 SKU-매장 조합: {step_analysis['step1']['combinations']}개")
                print(f"       소요 시간: {step_analysis['step1']['time']:.2f}초")
                print(f"   📦 Step2 - 1개씩 추가 배분:")
                print(f"       추가 배분량: {step_analysis['step2']['additional_allocation']}개")
                print(f"       소요 시간: {step_analysis['step2']['time']:.2f}초")
                print(f"   📦 Step3 - 잔여 수량 추가 배분:")
                print(f"       추가 배분량: {step_analysis['step3']['additional_allocation']}개")
                print(f"       소요 시간: {step_analysis['step3']['time']:.2f}초")
                
                if 'priority_temperature' in scenario_params:
                    print(f"   🌀 Priority Temperature: {scenario_params['priority_temperature']}")
                
                optimization_result['step_analysis'] = step_analysis
                
            except Exception as e:
                print(f"⚠️ 3-Step 분해 분석 실패: {e}")
                optimization_result['step_analysis'] = {}
        
        # 9. 최종 요약 출력
        print("\n" + "="*50)
        print("         🎉 3-Step 최적화 완료!")
        print("="*50)
        
        print(f"✅ 총 소요시간: {time.time() - start_time:.2f}초")
        return {
            'status': 'success',
            'target_style': target_style,
            'scenario': scenario,
            'analysis_results': analysis_results,
            'df_results': df_results,
            'experiment_path': experiment_path,
            'file_paths': file_paths,
            'step_analysis': optimization_result.get('step_analysis', {})
        }
        
    except Exception as e:
        print(f"\n❌ 최적화 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def run_batch_experiments(target_styles=None, scenarios=None, create_visualizations=True,
                         sku_file='ord/ord.json', store_file='shop/shop.json',
                         save_allocation_results=True, save_experiment_summary=True,
                         save_png_matrices=True, save_excel_matrices=True):
    """
    배치 실험 실행
    
    Args:
        target_styles: 실험할 스타일 리스트 (None이면 기본 스타일만)
        scenarios: 실험할 시나리오 리스트 (None이면 모든 시나리오)
        create_visualizations: 시각화 생성 여부
        sku_file: SKU 데이터 파일명
        store_file: 매장 데이터 파일명
        save_allocation_results: allocation_results.csv 저장 여부
        save_experiment_summary: experiment_summary.txt 저장 여부
        save_png_matrices: step별 PNG 매트릭스 저장 여부
        save_excel_matrices: step별 Excel 매트릭스 저장 여부
    """
    
    if target_styles is None:
        target_styles = [DEFAULT_TARGET_STYLE]
    
    if scenarios is None:
        scenarios = list(EXPERIMENT_SCENARIOS.keys())
    
    print(f"🔬 배치 실험 시작:")
    print(f"   대상 스타일: {target_styles}")
    print(f"   시나리오: {scenarios}")
    print(f"   SKU 파일: {sku_file}")
    print(f"   매장 파일: {store_file}")
    print(f"   총 실험 수: {len(target_styles) * len(scenarios)}개")
    
    results = []
    
    for target_style in target_styles:
        for scenario in scenarios:
            print(f"\n{'='*60}")
            print(f"실험: {target_style} - {scenario}")
            print(f"{'='*60}")
            
            result = run_optimization(
                target_style=target_style,
                scenario=scenario,
                show_detailed_output=False,
                create_visualizations=create_visualizations,
                sku_file=sku_file,
                store_file=store_file,
                save_allocation_results=save_allocation_results,
                save_experiment_summary=save_experiment_summary,
                save_png_matrices=save_png_matrices,
                save_excel_matrices=save_excel_matrices
            )
            
            if result:
                results.append(result)
                print(f"✅ 완료: {target_style} - {scenario}")
                
                step_analysis = result.get('step_analysis', {})
                if step_analysis:
                    print(f"   ✅ 실험 완료 - Step1 간접 다양성: {step_analysis['step1']['objective']:.1f}, Step2 추가배분: {step_analysis['step2']['additional_allocation']}개")
            else:
                print(f"❌ 실패: {target_style} - {scenario}")
    
    print(f"\n🎉 배치 실험 완료!")
    print(f"   성공한 실험: {len(results)}개")
    print(f"   실패한 실험: {len(target_styles) * len(scenarios) - len(results)}개")
    
    return results


if __name__ == "__main__":
    """메인 실행부"""
    
    print("🔧 SKU 분배 최적화 시스템")
    print("="*50)
    
    # 기본 설정으로 단일 실험 실행
    """
    시나리오 종류
    1. deterministic: 결정론적 배분 (매출 상위 매장 우선)
    2. random: 랜덤 배분 (매출을 고려하지 않은 랜덤 배분)
    3. temperature_50: temperature 0.5 (절충안)
    """
    
    """
    스타일 종류
    1. 대물량
        - DWDJ68046
        
    2. 아더컬러 어려운거
        - DMDJ85046
        - DWDJ8P046
        - DXDJ8C046
        - DXMT33044

    3. 소물량
        - DWLG42044
    """

    
    print("   배치 실험:")
    # run_batch_experiments(['DWDJ68046', 'DWDJ8P046', 'DXDJ8C046', 'DXMT33044'],
    run_batch_experiments(['DWWJ7D053'],
                          ['deterministic', 'temperature_50', 'random'],
                          sku_file='ord/ord_real_25s_DWWJ7D053.json',
                          store_file='shop/shop_real_control_25s.json',
                          save_allocation_results=True,      # allocation_results.csv 저장
                          save_experiment_summary=True,      # experiment_summary.txt 저장  
                          save_png_matrices=False,            # step별 PNG 매트릭스 저장
                          save_excel_matrices=True)          # step별 Excel 매트릭스 저장