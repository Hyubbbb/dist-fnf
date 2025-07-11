"""
3-Step 최적화 모듈 (Step1: Coverage MILP + Step2: 1개씩 배분 + Step3: 잔여 배분)
"""

from pulp import (
    LpProblem, LpVariable, LpBinary, LpInteger,
    LpMaximize, lpSum, PULP_CBC_CMD, value
)
import numpy as np
import time
import random
import math


class ThreeStepOptimizer:
    """3-Step 최적화를 담당하는 클래스
    
    Step 1: 바이너리 커버리지 최적화 (MILP)
    Step 2: 아직 해당 SKU를 받지 못한 매장에 1개씩 배분 (rule-based)
    Step 3: 남은 재고를 추가 배분 (rule-based)
    """
    
    def __init__(self, target_style):
        self.target_style = target_style
        self.step1_prob = None
        self.step1_objective = 0
        self.step1_time = 0
        self.step2_time = 0
        self.step3_time = 0
        self.step2_additional_allocation = 0
        self.step3_additional_allocation = 0
        self.final_allocation = {}
        
        # Step별 allocation 결과 초기화 (시각화용)
        self.step1_allocation = {}
        self.allocation_after_step2 = {}
        self.allocation_after_step3 = {}
        
    def optimize_three_step(self, data, scarce_skus, abundant_skus, target_stores, 
                         store_allocation_limits, df_sku_filtered, tier_system, 
                         scenario_params):
        """3-Step 최적화 실행"""
        A = data['A']
        stores = data['stores']
        SKUs = data['SKUs']
        K_s = data['K_s']
        L_s = data['L_s']
        QSUM = data['QSUM']
        
        print(f"🎯 3-Step 최적화 시작 (스타일: {self.target_style})")
        if 'priority_temperature' in scenario_params:
            print(f"   우선순위 temperature: {scenario_params['priority_temperature']}")
        
        # Step 1: 바이너리 커버리지 최적화
        step1_result = self._step1_coverage_optimization(
            data, SKUs, stores, target_stores, store_allocation_limits, 
            df_sku_filtered, K_s, L_s, scenario_params
        )
        
        if step1_result['status'] != 'success':
            return {
                'status': 'failed',
                'step': 1,
                'final_allocation': {}
            }
        
        # Step 2: 1개씩 배분
        print(f"\n📊 Step 2: L2 다양성 최대화 Rule-based 배분 (미배분 매장 1개씩 배분)")
        step2_result = self._step2_single_allocation(
            data, SKUs, stores, target_stores, store_allocation_limits, 
            step1_result['allocation'], scenario_params
        )
        
        if step2_result['status'] != 'success':
            return {'status': 'failed', 'step': 'step2'}
        
        # Step 3: 잔여 배분
        print(f"\n📊 Step 3: 배분량 최대화 Rule-based 잔여 수량 추가 배분")
        step3_result = self._step3_remaining_allocation(
            data, SKUs, stores, target_stores, store_allocation_limits, 
            step2_result['allocation'], scenario_params
        )
        
        return self._get_optimization_summary(data, target_stores, step1_result, step2_result, step3_result)
    
    def _step1_coverage_optimization(self, data, SKUs, stores, target_stores, 
                                    store_allocation_limits, df_sku_filtered, K_s, L_s, scenario_params):
        """Step 1: L1 다양성 최적화"""
        print(f"📊 Step 1: L1 다양성 최적화")
        
        start_time = time.time()
        
        # 1. LP 문제 초기화
        self.step1_prob = LpProblem("Step1_Coverage_Optimization", LpMaximize)
        
        # 2. 바이너리 변수 및 커버리지 변수 생성
        b = self._create_binary_variables(SKUs, stores, target_stores)
        color_coverage, size_coverage = self._create_coverage_variables(stores, target_stores, K_s, L_s)
        
        # 3. 커버리지 목적함수 설정 (정규화 방식)
        self._set_coverage_objective(color_coverage, size_coverage, stores, target_stores, K_s, L_s)
        
        # 4. 제약조건 추가
        self._add_step1_constraints(b, color_coverage, size_coverage, SKUs, stores, 
                                   target_stores, store_allocation_limits, 
                                   df_sku_filtered, K_s, L_s, data)
        
        # 5. 최적화 실행
        self.step1_prob.solve(PULP_CBC_CMD(msg=0))
        
        end_time = time.time()
        self.step1_time = end_time - start_time
        
        # 6. 결과 처리
        if self.step1_prob.status == 1:  # 최적해 찾음
            print(f"   ✅ Step1 최적화 성공 ({self.step1_time:.2f}초)")
            
            # 선택된 조합 추출
            selected_combinations = []
            for i in SKUs:
                for j in stores:
                    if j in target_stores and b[i][j].varValue and b[i][j].varValue > 0.5:
                        selected_combinations.append((i, j))
            
            # 목적함수 값 계산
            self.step1_objective = value(self.step1_prob.objective)
            
            # Step1 배분 결과 생성
            step1_allocation = {}
            for i, j in selected_combinations:
                step1_allocation[(i, j)] = 1
            
            # Store Step1 allocation for external access (visualization)
            self.step1_allocation = step1_allocation.copy()
            
            return {
                'status': 'success',
                'allocation': step1_allocation,
                'objective': self.step1_objective,
                'combinations': len(selected_combinations),
                'time': self.step1_time
            }
        else:
            print(f"   ❌ Step1 최적화 실패")
            return {
                'status': 'failed',
                'time': self.step1_time
            }
    
    def _step2_single_allocation(self, data, SKUs, stores, target_stores, 
                                store_allocation_limits, step1_allocation, scenario_params):
        """Step 2: 아직 해당 SKU를 받지 못한 매장에 1개씩만 배분"""
        start_time = time.time()
        
        # 초기화 (Step1 결과 복사)
        self.final_allocation = step1_allocation.copy()
        
        # 매장 우선순위 계산
        priority_temperature = scenario_params.get('priority_temperature', 0.0)
        store_priority_weights = self._calculate_store_priorities(target_stores, data['QSUM'], priority_temperature)
        
        total_additional = 0
        
        # 각 SKU에 대해 처리
        for i in SKUs:
            # 현재 해당 SKU를 받지 못한 매장들 찾기
            unfilled_stores = []
            for j in target_stores:
                if (i, j) not in self.final_allocation or self.final_allocation[(i, j)] == 0:
                    unfilled_stores.append(j)
            
            if not unfilled_stores:
                continue
                
            # 남은 수량 계산
            allocated_quantity = sum(
                self.final_allocation.get((i, j), 0) 
                for j in target_stores
            )
            remaining_quantity = data['A'][i] - allocated_quantity
            
            if remaining_quantity <= 0:
                continue
            
            # 우선순위에 따라 매장 정렬
            weighted_stores = [
                (j, store_priority_weights.get(j, 0)) 
                for j in unfilled_stores
            ]
            weighted_stores.sort(key=lambda x: x[1], reverse=True)
            
            # 1개씩 배분
            allocated_this_sku = 0
            for j, weight in weighted_stores:
                if allocated_this_sku >= remaining_quantity:
                    break
                    
                # 매장 한도 확인
                current_qty = self.final_allocation.get((i, j), 0)
                max_qty_per_sku = store_allocation_limits.get(j, 0)
                if current_qty >= max_qty_per_sku:
                    continue
                
                # 배분 실행
                self.final_allocation[(i, j)] = self.final_allocation.get((i, j), 0) + 1
                allocated_this_sku += 1
                total_additional += 1
        
        self.step2_time = time.time() - start_time
        self.step2_additional_allocation = total_additional
        
        # Preserve allocation snapshot after Step2 for visualization
        self.allocation_after_step2 = self.final_allocation.copy()
        
        print(f"   ✅ Step2 완료: {total_additional}개 추가 배분 ({self.step2_time:.2f}초)")
        
        return {
            'status': 'success', 
            'additional_allocation': total_additional,
            'allocation': self.final_allocation,
            'time': self.step2_time
        }
    
    def _step3_remaining_allocation(self, data, SKUs, stores, target_stores, 
                                    store_allocation_limits, step2_allocation, scenario_params):
        """Step 3: 남은 재고를 우선순위에 따라 (Tier limit까지) 추가 배분"""
        start_time = time.time()
        
        # 초기화 (Step2 결과 복사)
        self.final_allocation = step2_allocation.copy()
        
        # 우선순위 가중치 계산
        priority_temperature = scenario_params.get('priority_temperature', 0.0)
        store_priority_weights = self._calculate_store_priorities(target_stores, data['QSUM'], priority_temperature)
        
        total_additional = 0
        
        # 각 SKU에 대해 처리
        for i in SKUs:
            # 남은 수량 계산
            allocated_quantity = sum(
                self.final_allocation.get((i, j), 0) 
                for j in target_stores
            )
            remaining_quantity = data['A'][i] - allocated_quantity
            
            if remaining_quantity <= 0:
                continue
            
            # 추가 배분 가능한 매장들 찾기
            eligible_stores = []
            for j in target_stores:
                current_qty = self.final_allocation.get((i, j), 0)
                max_qty_per_sku = store_allocation_limits.get(j, 0)
                if current_qty < max_qty_per_sku:
                    eligible_stores.append(j)
            
            if not eligible_stores:
                continue
                
            # 우선순위에 따라 매장 정렬
            weighted_stores = [
                (j, store_priority_weights.get(j, 0)) 
                for j in eligible_stores
            ]
            weighted_stores.sort(key=lambda x: x[1], reverse=True)
            
            # 가능한 만큼 배분
            for j, weight in weighted_stores:
                if remaining_quantity <= 0:
                    break
                
                # 해당 매장에 추가 배분 가능한 수량 계산
                current_qty = self.final_allocation.get((i, j), 0)
                max_qty_per_sku = store_allocation_limits.get(j, 0)
                available_capacity = max_qty_per_sku - current_qty
                
                if available_capacity <= 0:
                    continue
                
                # 배분할 수량 결정
                allocate_quantity = min(remaining_quantity, available_capacity)
                
                # 배분 실행
                self.final_allocation[(i, j)] = self.final_allocation.get((i, j), 0) + allocate_quantity
                remaining_quantity -= allocate_quantity
                total_additional += allocate_quantity
        
        self.step3_time = time.time() - start_time
        # Store additional allocation count for step analysis
        self.step3_additional_allocation = total_additional
        
        print(f"   ✅ Step3 완료: {total_additional}개 추가 배분 ({self.step3_time:.2f}초)")
        
        return {
            'status': 'success', 
            'additional_allocation': total_additional,
            'allocation': self.final_allocation,
            'time': self.step3_time
        }
    
    def _create_binary_variables(self, SKUs, stores, target_stores):
        """바이너리 할당 변수 생성"""
        b = {}
        for i in SKUs:
            b[i] = {}
            for j in stores:
                if j in target_stores:
                    b[i][j] = LpVariable(f'b_{i}_{j}', cat=LpBinary)
                else:
                    b[i][j] = 0
        return b
    
    def _create_coverage_variables(self, stores, target_stores, K_s, L_s):
        """커버리지 변수 생성"""
        color_coverage = {}
        size_coverage = {}
        s = self.target_style
        
        for j in stores:
            if j in target_stores:
                color_coverage[(s,j)] = LpVariable(f"color_coverage_{s}_{j}", 
                                                 lowBound=0, upBound=len(K_s[s]), cat=LpInteger)
                size_coverage[(s,j)] = LpVariable(f"size_coverage_{s}_{j}", 
                                                lowBound=0, upBound=len(L_s[s]), cat=LpInteger)
            else:
                color_coverage[(s,j)] = 0
                size_coverage[(s,j)] = 0
        
        return color_coverage, size_coverage
    
    def _set_coverage_objective(self, color_coverage, size_coverage, stores, target_stores, K_s, L_s):
        """L1 커버리지 목적함수 설정 (정규화: 스타일별 색상/사이즈 개수 반영)"""
        s = self.target_style
        
        # 스타일별 색상과 사이즈 개수 파악
        total_colors = len(K_s[s])
        total_sizes = len(L_s[s])
        
        # 가중치 정규화 - 스타일별 색상/사이즈 개수를 반영하여 공정한 평가
        color_weight = 1.0 / total_colors if total_colors > 0 else 1.0
        size_weight = 1.0 / total_sizes if total_sizes > 0 else 1.0
        
        # 정규화된 커버리지 합계 최대화
        normalized_coverage_sum = lpSum(
            color_weight * color_coverage[(s,j)] + size_weight * size_coverage[(s,j)]
            for j in stores if j in target_stores and isinstance(color_coverage[(s,j)], LpVariable)
        )
        
        self.step1_prob += normalized_coverage_sum
        
        print(f"   🎯 목적함수: 간접 다양성 최대화 (정규화: 스타일별 색상/사이즈 개수 반영)")
    
    def _add_step1_constraints(self, b, color_coverage, size_coverage, SKUs, stores, 
                              target_stores, store_allocation_limits, df_sku_filtered, 
                              K_s, L_s, data):
        """Step 1 제약조건 추가"""
        
        # 1. 각 SKU는 최대 1개만 배분 (바이너리)
        for i in SKUs:
            sku_allocation = lpSum(
                b[i][j] for j in stores if isinstance(b[i][j], LpVariable)
            )
            self.step1_prob += sku_allocation <= data['A'][i]  # 공급량 제한
        
        # 2. 커버리지 제약조건
        self._add_coverage_constraints_step1(b, color_coverage, size_coverage, SKUs, stores, 
                                           target_stores, K_s, L_s, df_sku_filtered)
        
        print(f"   📋 제약조건: 바이너리 배분 + 다양성")
    
    def _add_coverage_constraints_step1(self, b, color_coverage, size_coverage, SKUs, stores, 
                                      target_stores, K_s, L_s, df_sku_filtered):
        """Step 1 커버리지 제약조건"""
        s = self.target_style
        
        # 색상별/사이즈별 SKU 그룹 미리 계산
        color_sku_groups = {}
        size_sku_groups = {}
        
        for sku in SKUs:
            try:
                sku_info = df_sku_filtered.loc[df_sku_filtered['SKU']==sku].iloc[0]
                color = sku_info['COLOR_CD']
                size = sku_info['SIZE_CD']
                
                if color not in color_sku_groups:
                    color_sku_groups[color] = []
                color_sku_groups[color].append(sku)
                
                if size not in size_sku_groups:
                    size_sku_groups[size] = []
                size_sku_groups[size].append(sku)
            except:
                continue
        
        for j in stores:
            if j not in target_stores:
                continue
                
            if not isinstance(color_coverage[(s,j)], LpVariable):
                continue
            
            # 색상 다양성 제약
            color_binaries = []
            for color, color_skus in color_sku_groups.items():
                color_allocation = lpSum(b[sku][j] for sku in color_skus if isinstance(b[sku][j], LpVariable))
                
                color_binary = LpVariable(f"color_bin_{color}_{j}", cat=LpBinary)
                
                self.step1_prob += color_allocation >= color_binary
                self.step1_prob += color_allocation <= len(color_skus) * color_binary
                
                color_binaries.append(color_binary)
            
            self.step1_prob += color_coverage[(s,j)] == lpSum(color_binaries)
            
            # 사이즈 다양성 제약
            size_binaries = []
            for size, size_skus in size_sku_groups.items():
                size_allocation = lpSum(b[sku][j] for sku in size_skus if isinstance(b[sku][j], LpVariable))
                
                size_binary = LpVariable(f"size_bin_{size}_{j}", cat=LpBinary)
                
                self.step1_prob += size_allocation >= size_binary
                self.step1_prob += size_allocation <= len(size_skus) * size_binary
                
                size_binaries.append(size_binary)
            
            self.step1_prob += size_coverage[(s,j)] == lpSum(size_binaries)
    
    def _calculate_store_priorities(self, target_stores, QSUM, priority_temperature=0.0):
        """매장별 우선순위 가중치 계산"""
        # alpha 값으로 혼합 가중치 계산 (default 0.0 => 순차적, 1.0 => 완전 랜덤)
        alpha = max(0.0, min(1.0, float(priority_temperature)))
        scores = self._compute_mixed_weights(target_stores, QSUM, alpha)

        print(f"   🎲 priority_temperature={alpha:.2f}")
        return scores
    
    def _compute_mixed_weights(self, target_stores, QSUM, alpha):
        """Deterministic(QSUM)과 Random 사이를 alpha로 혼합한 가중치 계산"""
        import random
        # 1) QSUM 정규화 (0~1)
        q_vals = [QSUM[j] for j in target_stores]
        qmin, qmax = min(q_vals), max(q_vals)
        if qmax > qmin:
            w = {j: (QSUM[j] - qmin)/(qmax - qmin) for j in target_stores}
        else:
            w = {j: 1.0 for j in target_stores}

        # 2) 무작위 0~1 값
        r = {j: random.random() for j in target_stores}

        # 3) 혼합 점수 계산
        s = {j: (1-alpha)*w[j] + alpha*r[j] for j in target_stores}
        return s
    
    def _get_optimization_summary(self, data, target_stores, step1_result, step2_result, step3_result):
        """최적화 결과 요약"""
        
        total_allocated = sum(self.final_allocation.values())
        total_supply = sum(data['A'].values())
        allocation_rate = total_allocated / total_supply if total_supply > 0 else 0
        
        allocated_stores = len(set(store for (sku, store), qty in self.final_allocation.items() if qty > 0))
        
        print(f"\n✅ 3-Step 최적화 완료!")
        print(f"   Step 1 간접 다양성: {step1_result['objective']:.1f}")
        print(f"   Step 2 추가 배분: {step2_result['additional_allocation']}개")
        print(f"   Step 3 추가 배분: {step3_result['additional_allocation']}개")
        
        # 최종 배분 결과 설정
        self.final_allocation = step3_result['allocation']
        
        # Step3 최종 결과 저장 (시각화용)
        self.allocation_after_step3 = self.final_allocation.copy()
        
        # 총 배분량 계산
        total_allocated = sum(self.final_allocation.values())
        
        # 결과 반환
        return {
            'status': 'success',
            'final_allocation': self.final_allocation,
            'total_allocated': total_allocated,
            'allocation_rate': total_allocated / sum(data['A'].values()) if sum(data['A'].values()) > 0 else 0,
            'allocated_stores': len(set(j for i, j in self.final_allocation.keys() if self.final_allocation[(i, j)] > 0)),
            'step1_combinations': step1_result['combinations'],
            'step1_objective': step1_result['objective'],
            'step2_additional': step2_result['additional_allocation'],
            'step3_additional': step3_result['additional_allocation'],
            'step_analysis': {
                'step1': {
                    'objective': step1_result['objective'],
                    'combinations': step1_result['combinations'],
                    'time': step1_result['time']
                },
                'step2': {
                    'additional_allocation': step2_result['additional_allocation'],
                    'time': step2_result['time']
                },
                'step3': {
                    'additional_allocation': step3_result['additional_allocation'],
                    'time': step3_result['time']
                }
            }
        }
    
    def get_final_allocation(self):
        """최종 배분 결과 반환"""
        return self.final_allocation
    
    def get_step_analysis(self):
        """3-Step 분해 분석 정보 반환"""
        return {
            'step1': {
                'objective': self.step1_objective,
                'time': self.step1_time,
                'combinations': len([k for k, v in self.step1_allocation.items() if v > 0]) if hasattr(self, 'step1_allocation') else 0
            },
            'step2': {
                'additional_allocation': self.step2_additional_allocation,
                'time': self.step2_time
            },
            'step3': {
                'additional_allocation': getattr(self, 'step3_additional_allocation', 0),
                'time': self.step3_time
            }
        } 