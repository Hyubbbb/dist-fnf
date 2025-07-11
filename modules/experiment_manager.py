"""
실험 관리 모듈
"""

import os
import json
import pandas as pd
from datetime import datetime
from config import OUTPUT_PATH


class ExperimentManager:
    """실험 관리 및 결과 저장을 담당하는 클래스"""
    
    def __init__(self):
        self.output_path = OUTPUT_PATH
        
    def create_experiment_output_path(self, scenario_name, style_name):
        """실험별 고유한 출력 폴더 및 파일명 생성"""
        
        # 현재 시간 (MMDD_HHMM 형식)
        timestamp = datetime.now().strftime("%m%d_%H%M")
        
        # 계층적 폴더 구조: 스타일명/시나리오명/일시
        style_folder = os.path.join(self.output_path, style_name)
        scenario_folder = os.path.join(style_folder, scenario_name)
        experiment_folder = os.path.join(scenario_folder, timestamp)
        
        # 폴더 생성 (존재하지 않으면)
        os.makedirs(experiment_folder, exist_ok=True)
        
        # 파일명 패턴 생성 (스타일명_시나리오명_일시)
        file_prefix = f"{style_name}_{scenario_name}_{timestamp}"
        
        file_paths = {
            'allocation_results': os.path.join(experiment_folder, f"{file_prefix}_allocation_results.csv"),
            'experiment_params': os.path.join(experiment_folder, f"{file_prefix}_experiment_params.json"),
            'experiment_summary': os.path.join(experiment_folder, f"{file_prefix}_experiment_summary.txt")
        }
        
        return experiment_folder, file_paths
    
    def save_experiment_results(self, file_paths, df_results, analysis_results, params, 
                              scenario_name, optimization_summary, save_allocation_results=True, 
                              save_experiment_summary=True):
        """실험 결과 저장"""
        
        print(f"\n💾 실험 결과 저장 중...")
        
        try:
            # 1. 할당 결과 CSV 저장 (옵션)
            if save_allocation_results and len(df_results) > 0:
                df_results.to_csv(file_paths['allocation_results'], index=False, encoding='utf-8-sig')
                print(f"   ✅ 할당 결과: {os.path.basename(file_paths['allocation_results'])}")
            
            # 2. 실험 메타데이터 저장 (옵션)
            if save_experiment_summary:
                self._save_experiment_metadata(file_paths, scenario_name, params, optimization_summary, analysis_results)
            
            print(f"📁 실험 '{scenario_name}' 결과 저장 완료!")
            
        except Exception as e:
            print(f"❌ 실험 결과 저장 실패: {str(e)}")
            raise
    
    def _save_experiment_metadata(self, file_paths, scenario_name, params, optimization_summary, analysis_results):
        """실험 메타데이터 저장"""
        
        # JSON 직렬화 가능하도록 데이터 정리
        def make_json_serializable(obj):
            """JSON 직렬화 가능한 형태로 변환"""
            if isinstance(obj, dict):
                # tuple 키를 문자열로 변환
                return {str(k): make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            elif isinstance(obj, (int, float, str, bool)) or obj is None:
                return obj
            else:
                return str(obj)  # 기타 객체들은 문자열로 변환
        
        # 1. 실험 파라미터 JSON 저장
        experiment_info = {
            'scenario_name': scenario_name,
            'timestamp': datetime.now().isoformat(),
            'parameters': make_json_serializable(params),
            'optimization_summary': make_json_serializable(optimization_summary)
        }
        
        with open(file_paths['experiment_params'], 'w', encoding='utf-8') as f:
            json.dump(experiment_info, f, indent=2, ensure_ascii=False)
        
        # 2. 실험 요약 텍스트 저장
        summary_text = self._create_summary_text(scenario_name, params, optimization_summary, analysis_results)
        
        with open(file_paths['experiment_summary'], 'w', encoding='utf-8') as f:
            f.write(summary_text)
        
        print(f"   ✅ 메타데이터: {os.path.basename(file_paths['experiment_params'])}")
        print(f"   ✅ 요약: {os.path.basename(file_paths['experiment_summary'])}")
    
    def _create_summary_text(self, scenario_name, params, optimization_summary, analysis_results):
        """실험 요약 텍스트 생성"""
        
        # 색상/사이즈 다양성 정보 추출
        coverage_info = ""
        if 'style_coverage' in analysis_results:
            style_coverage = analysis_results['style_coverage']
            color_coverage = style_coverage.get('color_coverage', {})
            size_coverage = style_coverage.get('size_coverage', {})
            
            coverage_info = f"""
📊 다양성 분석:
- 색상 다양성:
  * 평균: {color_coverage.get('avg_ratio', 0):.3f}
  * 최대: {color_coverage.get('max_ratio', 0):.3f}
  * 최소: {color_coverage.get('min_ratio', 0):.3f}
  * 총 색상 수: {color_coverage.get('total_colors', 0)}개
- 사이즈 다양성:
  * 평균: {size_coverage.get('avg_ratio', 0):.3f}
  * 최대: {size_coverage.get('max_ratio', 0):.3f}
  * 최소: {size_coverage.get('min_ratio', 0):.3f}
  * 총 사이즈 수: {size_coverage.get('total_sizes', 0)}개
"""
        
        summary_text = f"""
========================================
실험 결과 요약 - {scenario_name}
========================================

실험 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
스타일: {params.get('target_style', 'N/A')}
설명: {params.get('description', 'N/A')}

📊 실험 파라미터:
- 다양성 가중치: {params.get('coverage_weight', 'N/A')}
- Priority Temperature: {params.get('priority_temperature', 'N/A')}

⚡ 최적화 결과:
- 상태: {optimization_summary.get('status', 'unknown')}
- 총 배분량: {optimization_summary.get('total_allocated', 'N/A')}
- 배분률: {optimization_summary.get('allocation_rate', 0)*100:.1f}%
- 배분 받은 매장: {optimization_summary.get('allocated_stores', 'N/A')}개
{coverage_info}
📁 생성된 파일들:
- allocation_results.csv: 상세 할당 결과
- experiment_params.json: 실험 파라미터
- experiment_summary.txt: 실험 요약

========================================
"""
        
        return summary_text