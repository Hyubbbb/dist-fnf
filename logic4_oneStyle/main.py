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
                    sku_file='발주수량.csv', store_file='매장데이터.csv'):
    """
    SKU 분배 최적화 실행
    
    Args:
        target_style: 대상 스타일 코드
        scenario: 실험 시나리오 이름
        show_detailed_output: 상세 출력 여부
        create_visualizations: 시각화 생성 여부
        sku_file: SKU 데이터 파일명 (기본값: '발주수량.csv')
        store_file: 매장 데이터 파일명 (기본값: '매장데이터.csv')
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
        
        # 4. 3-Step 최적화 (Step1: 커버리지 + Step2: 1개씩 배분 + Step3: 잔여 배분)
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
        allocation_summary = optimization_result  # 결과 요약을 그대로 사용
        
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
            data_loader.df_sku_filtered, tier_system, {}  # b_hat 대신 빈 딕셔너리
        )
        
        # 7. 실험 결과 저장
        print("\n💾 7단계: 실험 결과 저장")
        experiment_manager = ExperimentManager()
        
        # 시나리오 파라미터 준비
        scenario_params = EXPERIMENT_SCENARIOS[scenario].copy()
        scenario_params['target_style'] = target_style
        
        # 출력 경로 생성 (시나리오명만 사용)
        experiment_path, file_paths = experiment_manager.create_experiment_output_path(scenario, target_style)
        
        # 결과 저장
        scenario_name = f"{target_style}_{scenario}"  # 저장용 시나리오명 (스타일 포함)
        experiment_manager.save_experiment_results(
            file_paths, df_results, analysis_results, scenario_params,
            scenario_name, allocation_summary
        )
        
        # 8. 시각화 (옵션)
        if create_visualizations:
            print("\n📈 8단계: 시각화 생성")
            visualizer = ResultVisualizer()
            
            try:
                # PNG 저장 경로 생성
                import os
                visualization_dir = experiment_path

                # Step별 allocation matrix 경로 (Step1/Step2/Step3)
                matrix_step1_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step1_allocation_matrix.png")
                matrix_step2_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step2_allocation_matrix.png")
                matrix_step3_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step3_allocation_matrix.png")

                # 배분 매트릭스 히트맵 (Step1, Step2, Step3) - 모든 매장과 모든 SKU 표시

                # Step1
                if hasattr(three_step_optimizer, 'step1_allocation') and three_step_optimizer.step1_allocation:
                    visualizer.create_allocation_matrix_heatmap(
                        three_step_optimizer.step1_allocation,
                        target_stores, data['SKUs'], data['QSUM'],
                        data_loader.df_sku_filtered, data['A'], tier_system,
                        save_path=matrix_step1_path, max_stores=None, max_skus=None,
                        fixed_max=3, SHOP_NAMES=data.get('SHOP_NAMES')
                    )

                # Step2
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
                
                # 📊 엑셀 배분 매트릭스 생성 (Step별)
                print("\n📊 엑셀 배분 매트릭스 생성 중...")
                
                # Step별 엑셀 파일 경로
                excel_step1_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step1_allocation_matrix.xlsx")
                excel_step2_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step2_allocation_matrix.xlsx")
                excel_step3_path = os.path.join(visualization_dir, f"{target_style}_{scenario}_step3_allocation_matrix.xlsx")
                
                # Step1 엑셀 - 디버깅 정보 추가
                print(f"🔍 Step1 엑셀 생성 확인:")
                print(f"   hasattr(three_step_optimizer, 'step1_allocation'): {hasattr(three_step_optimizer, 'step1_allocation')}")
                if hasattr(three_step_optimizer, 'step1_allocation'):
                    print(f"   step1_allocation 타입: {type(three_step_optimizer.step1_allocation)}")
                    print(f"   step1_allocation 길이: {len(three_step_optimizer.step1_allocation)}")
                    print(f"   step1_allocation 샘플: {list(three_step_optimizer.step1_allocation.items())[:3]}")
                
                # 최적화 시간 정보 추출
                step_analysis = optimization_result.get('step_analysis', {})
                total_optimization_time = (
                    step_analysis.get('step1', {}).get('time', 0) +
                    step_analysis.get('step2', {}).get('time', 0) +
                    step_analysis.get('step3', {}).get('time', 0)
                )
                
                if hasattr(three_step_optimizer, 'step1_allocation') and len(three_step_optimizer.step1_allocation) > 0:
                    print(f"   ✅ Step1 엑셀 생성 중: {excel_step1_path}")
                    visualizer.create_allocation_matrix_excel(
                        three_step_optimizer.step1_allocation,
                        target_stores, data['SKUs'], data['QSUM'],
                        data_loader.df_sku_filtered, data['A'], tier_system,
                        save_path=excel_step1_path, SHOP_NAMES=data.get('SHOP_NAMES'),
                        optimization_time=step_analysis.get('step1', {}).get('time', 0)
                    )
                else:
                    print(f"   ❌ Step1 엑셀 생성 건너뜀 - step1_allocation이 비어있거나 존재하지 않음")
                
                # Step2 엑셀 - 디버깅 정보 추가
                print(f"🔍 Step2 엑셀 생성 확인:")
                print(f"   hasattr(three_step_optimizer, 'allocation_after_step2'): {hasattr(three_step_optimizer, 'allocation_after_step2')}")
                if hasattr(three_step_optimizer, 'allocation_after_step2'):
                    print(f"   allocation_after_step2 길이: {len(three_step_optimizer.allocation_after_step2)}")
                
                if hasattr(three_step_optimizer, 'allocation_after_step2') and len(three_step_optimizer.allocation_after_step2) > 0:
                    print(f"   ✅ Step2 엑셀 생성 중: {excel_step2_path}")
                    visualizer.create_allocation_matrix_excel(
                        three_step_optimizer.allocation_after_step2,
                        target_stores, data['SKUs'], data['QSUM'],
                        data_loader.df_sku_filtered, data['A'], tier_system,
                        save_path=excel_step2_path, SHOP_NAMES=data.get('SHOP_NAMES'),
                        optimization_time=step_analysis.get('step1', {}).get('time', 0) + step_analysis.get('step2', {}).get('time', 0)
                    )
                else:
                    print(f"   ❌ Step2 엑셀 생성 건너뜀 - allocation_after_step2가 비어있거나 존재하지 않음")
                
                # Step3 (최종) 엑셀
                print(f"🔍 Step3 엑셀 생성 확인:")
                print(f"   final_allocation 길이: {len(final_allocation)}")
                if len(final_allocation) > 0:
                    print(f"   ✅ Step3 엑셀 생성 중: {excel_step3_path}")
                    visualizer.create_allocation_matrix_excel(
                        final_allocation, target_stores, data['SKUs'],
                        data['QSUM'], data_loader.df_sku_filtered, data['A'], tier_system,
                        save_path=excel_step3_path, SHOP_NAMES=data.get('SHOP_NAMES'),
                        optimization_time=total_optimization_time
                    )
                else:
                    print(f"   ❌ Step3 엑셀 생성 건너뜀 - final_allocation이 비어있음")
                
            except Exception as e:
                print(f"⚠️ 시각화 생성 중 오류: {str(e)}")
                print("   (시각화 오류는 전체 프로세스에 영향을 주지 않습니다)")
        
        # ✅ 3-Step 분해 분석 추가
        if optimization_result['status'] == 'success':
            try:
                # 3-Step 분해 정보 추출
                step_analysis = three_step_optimizer.get_step_analysis()
                
                print(f"📊 3-Step 분해 결과:")
                print(f"   🎯 Step1 - 커버리지 최적화:")
                print(f"       커버리지 점수: {step_analysis['step1']['objective']:.1f}")
                print(f"       선택된 SKU-매장 조합: {step_analysis['step1']['combinations']}개")
                print(f"       소요 시간: {step_analysis['step1']['time']:.2f}초")
                print(f"   📦 Step2 - 1개씩 추가 배분:")
                print(f"       추가 배분량: {step_analysis['step2']['additional_allocation']}개")
                print(f"       소요 시간: {step_analysis['step2']['time']:.2f}초")
                print(f"   📦 Step3 - 잔여 수량 추가 배분:")
                print(f"       추가 배분량: {step_analysis['step3']['additional_allocation']}개")
                print(f"       소요 시간: {step_analysis['step3']['time']:.2f}초")
                
                # 배분 우선순위 설명
                if 'priority_temperature' in scenario_params:
                    print(f"   🌀 Priority Temperature: {scenario_params['priority_temperature']}")
                
                # 3-Step 분해 정보를 결과에 추가
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
                         sku_file='발주수량.csv', store_file='매장데이터.csv'):
    """
    배치 실험 실행
    
    Args:
        target_styles: 실험할 스타일 리스트 (None이면 기본 스타일만)
        scenarios: 실험할 시나리오 리스트 (None이면 모든 시나리오)
        create_visualizations: 시각화 생성 여부 (기본값: False, 시간 절약)
        sku_file: SKU 데이터 파일명 (기본값: '발주수량.csv')
        store_file: 매장 데이터 파일명 (기본값: '매장데이터.csv')
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
                create_visualizations=create_visualizations,  # 파라미터로 제어
                sku_file=sku_file,
                store_file=store_file
            )
            
            if result:
                results.append(result)
                print(f"✅ 완료: {target_style} - {scenario}")
                
                # 실험 완료 요약 출력
                step_analysis = result.get('step_analysis', {})
                if step_analysis:
                    print(f"   ✅ 실험 완료 - Step1 커버리지: {step_analysis['step1']['objective']:.1f}, Step2 추가배분: {step_analysis['step2']['additional_allocation']}개")
            else:
                print(f"❌ 실패: {target_style} - {scenario}")
    
    print(f"\n🎉 배치 실험 완료!")
    print(f"   성공한 실험: {len(results)}개")
    print(f"   실패한 실험: {len(target_styles) * len(scenarios) - len(results)}개")
    

    
    return results


def list_saved_experiments():
    """저장된 실험 목록 출력"""
    experiment_manager = ExperimentManager()
    experiments = experiment_manager.list_experiments()
    
    if not experiments:
        print("저장된 실험이 없습니다.")
        return
    
    print(f"💾 저장된 실험 목록 ({len(experiments)}개):")
    print("-" * 80)
    
    for i, exp in enumerate(experiments[:10], 1):  # 최신 10개만 표시
        print(f"{i:2d}. {exp['folder_name']}")
        print(f"     스타일: {exp.get('target_style', 'Unknown')}")
        print(f"     시나리오: {exp.get('scenario_name', 'Unknown')}")
        print(f"     생성시간: {exp['created_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    if len(experiments) > 10:
        print(f"... 외 {len(experiments) - 10}개 실험")


if __name__ == "__main__":
    """메인 실행부"""
    
    print("🔧 SKU 분배 최적화 시스템")
    print("="*50)
    
    # 기본 설정으로 단일 실험 실행
    """
    시나리오 종류
    deterministic: 결정론적 배분

    temperature_50: temperature 0.5

    random: 랜덤 배분

    original_coverage: 기존 커버리지 방식 테스트 (색상 + 사이즈 커버리지 단순 합산)

    normalized_coverage: 정규화 커버리지 방식 테스트 (스타일별 색상/사이즈 개수 반영)
    """

    """
    스타일 종류

    1. 대물량
    DWDJ68046

    2. 아더컬러 어려운거
    DMDJ85046
    DWDJ8P046
    DXDJ8C046
    DXMT33044

    3. 소물량
    DWLG42044
    """

    # (1) 단일 실험
    # result = run_optimization(target_style='DWLG42044', 
    #                           scenario='deterministic',
    #                           sku_file='ord_real.csv',
    #                           store_file='shop_real_control.csv')
    
    # print("   단일 실험: run_optimization(target_style='DWLG42044', scenario='deterministic')")
    # print("   단일 실험: run_optimization(target_style='DWLG42044', scenario='temperature_50')")
    # print("   단일 실험: run_optimization(target_style='DWLG42044', scenario='random')")

    # (2) 배치 실험
    # run_batch_experiments(['DWLG42044'],
    #                       ['deterministic', 'temperature_50', 'random'])
    # print("   배치 실험: run_batch_experiments(['DWLG42044'], ['deterministic', 'temperature_50', 'random'])")
    
    # run_batch_experiments(['DWDJ68046', 'DMDJ85046', 'DWDJ8P046', 'DXDJ8C046', 'DXMT33044', 'DWLG42044'],
    #                       ['deterministic', 'temperature_50', 'random'])
    # print("   배치 실험: run_batch_experiments(['DWDJ68046', 'DMDJ85046', 'DWDJ8P046', 'DXDJ8C046', 'DXMT33044', 'DWLG42044'], ['deterministic', 'temperature_50', 'random', 'original_coverage', 'normalized_coverage'])")
    

    # (3) 실험 목록
    # print("   실험 목록: list_saved_experiments()")
    # print("   다른 스타일: config.py에서 설정 변경 가능")
    # print("   사용 가능한 시나리오:\n      deterministic,\n      temperature_50,\n      random,\n      original_coverage,\n      normalized_coverage")
    # print("   커버리지 비교 시나리오:\n      original_coverage,\n      normalized_coverage")
    
    # (4) 다른 데이터 파일 사용 예시
    # print("\n📁 다른 데이터 파일 사용 예시:")
    # print("   단일 실험 - 다른 데이터:")
    # result = run_optimization(target_style='DWLG42044', 
    #                         scenario='deterministic',
    #                         sku_file='ord_real.csv',
    #                         store_file='shop_real_control.csv')
    
    print("   배치 실험 - 다른 데이터:")
    # run_batch_experiments(['DWLG42044'],
    # run_batch_experiments(['DMDJ85046'], # 존재 X
    # run_batch_experiments(['DWDJ68046', 'DWDJ8P046', 'DXDJ8C046', 'DXMT33044'],
    run_batch_experiments(['DWWJ7D053'],
                          ['deterministic', 'temperature_50', 'random'],
                          sku_file='ord_real_25s2.csv',
                          store_file='shop_real_control_25s.csv')