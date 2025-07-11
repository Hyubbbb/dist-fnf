# 📦 SKU 초도 배분 최적화 시스템

이 배분 최적화 AI는 수치적 최적화 방법인 MILP(Mixed Integer Linear Programming)와 Rule-Based 방식을 결합한 **초도 배분 물량 최적화 시스템**입니다. 매장별 특성과 상품의 다양성을 고려하여, 제한된 물량을 가장 효과적으로 분배하는 것을 목표로 합니다.

## 🚀 주요 기능

-   **Tier 기반 차등 배분**: 매출(QTY_SUM) 기준 상위 매장을 TIER 1, 2, 3으로 자동 분류하여 차등적으로 물량을 배분합니다.
    - (배분 담당자의 스타일 별 배분대상 매장 & 각 매장의 등급 등을 수동적으로 반영할 수 있도록 보완 필요)
-   **다양성 최적화**: MILP와 규칙 기반 배분을 사용하여 매장별로 최대한 다양한 색상과 사이즈의 상품이 배분되도록 합니다.
-   **유연한 시나리오 설정**: 결정론적, 확률적(temperature), 랜덤 등 다양한 배분 시나리오를 설정하여 실험할 수 있습니다.
-   **상세 결과 리포트**: 배분 결과, 통계, 시각화 자료(히트맵)를 Excel 및 PNG 파일로 자동 생성합니다.
-   **세분화된 출력 제어**: `main.py`에서 생성할 결과물(csv, png, xlsx 등)을 개별적으로 선택할 수 있습니다.

## 💡 핵심 최적화 로직 (3-Step Optimization)

이 시스템은 복잡한 배분 문제를 세 단계로 나누어, 각 단계의 목표를 명확히 해결하는 **3-Step 최적화** 방식을 사용합니다.

-   **Step 1: 간접(색상/사이즈) 다양성 최적화: MILP**
    -   **목표**: **매장 방문 고객의 색상/사이즈 경험 극대화**
    -   **방식**: 
        1. 각 매장에 어떤 SKU를 배분할지 '조합'을 결정합니다. 
        2. 실제 수량이 아닌, 어떤 종류의 상품을 넣을지에 대한 최적의 조합을 MILP로 찾습니다. 
        3. 이를 통해, 모든 매장이 가능한 한 다양한 색상과 사이즈를 고르게 갖출 수 있는 최적해를 보장합니다.

-   **Step 2: 직접(피팅) 다양성 최적화: Rule-based**
    -   **목표**: **매장 방문 고객의 피팅 가능 SKU 극대화**
    -   **방식**: 
        1. Step 1에서 결정된 최적의 조합에 따라 각 SKU를 1개씩 우선 배분합니다. 
        2. 특정 SKU를 할당받지 못한 매장들에게도 시나리오에 따른 우선순위에 따라 1개씩 배분하여 피팅 다양성을 극대화 합니다.

-   **Step 3: 잔여 수량 효율적 배분 (Rule-based)**
    -   **목표**: **공급량 소진 및 매장 효율성 고려**
    -   **방식**: 
        - 남은 재고를 매장별 Tier에 설정된 최대 한도 내에서 우선순위가 높은 매장부터 추가로 배분하여, 공급량을 최대한 활용하고 매출이 높은 매장에 더 많은 기회를 제공합니다.

## 🏗️ 디렉토리 구조

```
dist-fnf/
├── main.py                             # 실험 실행 및 전체 최적화 파이프라인 시작점
├── config.py                           # 실험 설정값 (Tier, 시나리오 등) 관리
├── modules/                            # 핵심 최적화 및 분석 로직 모듈 모음
│   ├── data_loader.py                  # 발주량 및 매장 데이터 로딩 및 전처리
│   ├── store_tier_system.py            # 매장 매출 기준으로 Tier 분류 로직 (보완 필요)
│   ├── three_step_optimizer.py         # 3-Step 최적화 로직 (MILP + Rule-based + Rule-based)
│   ├── analyzer.py                     # 배분 결과 메트릭(직/간접 다양성) 및 통계 분석
│   ├── visualizer.py                   # 배분 결과 시각화 파일 생성(히트맵 & 엑셀)
│   └── experiment_manager.py           # 실험 관리 (결과 저장, 디렉토리 관리, 파일명 생성 등)
├── data/                               # Input 데이터 저장 폴더
│   ├── ord/                            # SKU 발주 데이터
│   │   └── *.csv                       # 스타일별 발주 데이터 파일들
│   └── shop/                           # 매장 정보 데이터
│       └── *.csv                       # 매장별 매출 데이터 파일들
└── output/                             # 실험 Output 저장 폴더
    └── {style}/                        # 스타일별 결과 하위 폴더
        └── {scenario}/                 # 시나리오별 결과 하위 폴더
            └── {timestamp}/            # 실행 시각 기준 결과 폴더 (결과물 자동 저장 위치)
```

## ⚙️ 사용법

### **Step 1. 환경 설정**

-   요구사항에 명시된 패키지를 설치합니다.
    ```bash
    pip install -r requirements.txt
    ```
-   **주요 패키지**: `pandas`, `numpy`, `pulp`, `matplotlib`, `seaborn`, `openpyxl`

### **Step 2. 데이터 준비**

1.   프로젝트 루트에 `data` 폴더와 그 하위의 `ord`, `shop` 폴더를 생성합니다. 
    
    -   이 폴더들은 `.gitignore`에 의해 버전 관리에서 제외되므로, 최초 실행 시 직접 생성해야 합니다.

2.   **`data/ord/`**: 발주(SKU) 데이터를 준비합니다.
    
    -   **필수 컬럼**: `PART_CD`, `COLOR_CD`, `SIZE_CD`, `ORD_QTY`
    -   **예시 (`ord.csv`)**:
        | PART_CD   | COLOR_CD | SIZE_CD | ORD_QTY |
        |-----------|----------|---------|---------|
        | ABC123456 | A        | 95      | 111     |
        | ABC123456 | A        | 100     | 222     |
        | ABC123456 | B        | 95      | 12345   |

3.   **`data/shop/`**: 매장 데이터를 준비합니다.
    -   **필수 컬럼**: `SHOP_ID`, `SHOP_NM_SHORT`, `QTY_SUM`
    -   **예시 (`shop.csv`)**:
        | SHOP_ID | SHOP_NM_SHORT        | QTY_SUM |
        |---------|----------------------|---------|
        | 11111   | 한국백화점(직)         | 1234    |
        | 22222   | 한국아울렛(직)         | 4567    |
        | 33333   | 한국본점              | 2345    |

### **Step 3. 실험 실행**

`main.py` 파일의 하단 `if __name__ == "__main__":` 부분을 수정하여 실험을 실행합니다.

```python
# main.py
if __name__ == "__main__":
    run_batch_experiments(
        target_styles=['DWWJ7D053'], # 실험할 스타일 코드
        scenarios=['deterministic', 'temperature_50', 'random'], # 실험할 시나리오
        sku_file='ord/ord_real_25s_DWWJ7D053.csv', # 사용할 SKU 데이터 파일
        store_file='shop/shop_real_control_25s.csv', # 사용할 매장 데이터 파일
        
        # --- 출력 파일 제어 ---
        save_allocation_results=True,  # allocation_results.csv 저장 여부
        save_experiment_summary=True,  # experiment_summary.txt 저장 여부
        save_png_matrices=True,        # PNG 히트맵 저장 여부
        save_excel_matrices=True       # Excel 리포트 저장 여부
    )
```

-   터미널에서 아래 명령어를 실행합니다.
    ```bash
    python main.py
    ```

## 📊 시나리오 및 파라미터 설정

-   모든 주요 설정은 **`config.py`** 파일에서 관리합니다.

### **Tier 설정 (`TIER_CONFIG`)**

-   매출 상위 매장을 어떤 비율로 나누고, Tier별로 SKU당 최대 몇 개까지 배분할지 정의합니다.
    ```python
    'TIER_1_HIGH': { 'ratio': 0.3, 'max_sku_limit': 3 }
    ```

### **시나리오 설정 (`EXPERIMENT_SCENARIOS`)**

-   실험 시나리오별로 매장 우선순위 계산 방식을 다르게 설정합니다.
    -   **`deterministic`**: 매출(QTY_SUM)이 높은 매장에 우선적으로 배분합니다.
        - `priority_temperature` = 0.0
    -   **`temperature_50`**: 매출 순위를 기반으로 하되, 약간의 무작위성을 부여하여 하위 매장에도 기회를 제공합니다.
        - `priority_temperature` = 0.5
    -   **`random`**: 매출과 상관없이 무작위로 매장 우선순위를 정합니다.
        - `priority_temperature` = 1.0

## 📁 결과물 설명

-   실행 결과는 `output/{스타일}/{시나리오}/{실행시간}/` 폴더에 저장됩니다.
-   **`..._allocation_results.csv`**: SKU-매장 단위의 상세 배분 결과.
-   **`..._experiment_summary.txt`**: 실험 파라미터, 최적화 결과, 다양성 분석 등 요약 정보.
-   **`..._step{N}_allocation_matrix.xlsx`**: 단계별 배분 결과를 담은 상세 리포트.
    -   `배분_매트릭스` 시트: 매장 x SKU 배분 현황
    -   `매장별_통계` 시트: 매장별 배분량 및 다양성 통계
    -   `SKU별_통계` 시트: SKU별 배분량 및 배분률
    -   `요약` 시트: 전체 실험 결과 요약
-   **`..._step{N}_allocation_matrix.png`**: 단계별 배분 매트릭스 히트맵 시각화. 