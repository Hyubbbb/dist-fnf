"""
SKU 분배 최적화 설정
"""

# 기본 경로 설정
DATA_PATH = './data'
OUTPUT_PATH = './output'

# 매장 Tier 설정
TIER_CONFIG = {
    'TIER_1_HIGH': {
        'name': 'TIER_1_HIGH',
        'display': '🥇 T1 (HIGH)',
        'ratio': 0.3,
        'max_sku_limit': 3
    },
    'TIER_2_MEDIUM': {
        'name': 'TIER_2_MEDIUM', 
        'display': '🥈 T2 (MED)',
        'ratio': 0.2,
        'max_sku_limit': 2
    },
    'TIER_3_LOW': {
        'name': 'TIER_3_LOW',
        'display': '🥉 T3 (LOW)', 
        'ratio': 0.5,
        'max_sku_limit': 1
    }
}

# 기본 실행 설정
DEFAULT_TARGET_STYLE = "DWLG42044"
DEFAULT_SCENARIO = "deterministic"

# 실험 시나리오 설정
EXPERIMENT_SCENARIOS = {    
    "deterministic": {
        "description": "결정론적 배분",
        "coverage_weight": 1.0,
        "priority_temperature": 0.0,
        "coverage_method": "normalized"
    },
    
    "temperature_50": {
        "description": "temperature 0.5",
        "coverage_weight": 1.0,
        "priority_temperature": 0.5,
        "coverage_method": "normalized"
    },
    
    "random": {
        "description": "랜덤 배분",
        "coverage_weight": 1.0,
        "priority_temperature": 1.0,
        "coverage_method": "normalized"
    }
}