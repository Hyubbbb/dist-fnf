"""
시각화 모듈
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os


class ResultVisualizer:
    """배분 매트릭스 히트맵 시각화를 담당하는 클래스"""
    
    def __init__(self):
        # 한글 폰트 설정
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['axes.unicode_minus'] = False

    def create_allocation_matrix_heatmap(self, final_allocation, target_stores, SKUs, QSUM,
                                       df_sku_filtered, A, tier_system, save_path=None, max_stores=None, max_skus=None, fixed_max=None, SHOP_NAMES=None):
        """
        배분 결과를 매장 × SKU 매트릭스 히트맵으로 시각화
        
        Args:
            max_stores: 표시할 최대 매장 수 (None이면 모든 매장)
            max_skus: 표시할 최대 SKU 수 (None이면 모든 SKU)
            SHOP_NAMES: 매장별 매장명 딕셔너리
        """
        print("📊 배분 매트릭스 히트맵 생성 중...")
        
        # 기본값 설정
        if max_stores is None:
            max_stores = len(target_stores)
        if max_skus is None:
            max_skus = len(SKUs)
        
        # 0. Tier 기반 배분 가능량 계산 메서드 정의
        def calculate_max_allocatable_by_tier(sku, target_stores, tier_system, A, QSUM):
            """SKU별 tier 기반 최대 배분 가능량 계산"""
            # 기본 target_stores 사용 (SKU별 지정 매장 기능 제거됨)
            sku_target_stores = target_stores
            
            if not sku_target_stores:
                return A.get(sku, 0)
            
            # 각 매장별 tier에 따른 최대 배분량 합계
            tier_based_capacity = 0
            for store in sku_target_stores:
                tier_info = tier_system.get_store_tier_info(store, target_stores)
                tier_based_capacity += tier_info['max_sku_limit']
            
            # 실제 공급량과 tier 기반 용량 중 작은 값
            actual_supply = A.get(sku, 0)
            return min(actual_supply, tier_based_capacity)
        
        # 1. 모든 매장을 포함하되 QTY_SUM 기준으로 정렬
        all_stores_with_stats = []
        for store in target_stores:
            store_total = sum(final_allocation.get((sku, store), 0) for sku in SKUs)
            all_stores_with_stats.append((store, store_total, QSUM[store]))
        
        # QTY_SUM 기준으로 정렬하고 상위 max_stores개 선택
        all_stores_with_stats.sort(key=lambda x: x[2], reverse=True)
        selected_stores = [store[0] for store in all_stores_with_stats[:max_stores]]
        
        # 2. 모든 SKU를 포함하되 컬러-사이즈 기준으로 정렬
        all_skus_with_stats = []
        for sku in SKUs:
            sku_total = sum(final_allocation.get((sku, store), 0) for store in selected_stores)
            try:
                sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                color = sku_info['COLOR_CD']
                size = sku_info['SIZE_CD']
            except:
                parts = sku.split('_')
                color = parts[1] if len(parts) >= 3 else 'Unknown'
                size = parts[2] if len(parts) >= 3 else 'Unknown'
            all_skus_with_stats.append((sku, sku_total, color, size))
        
        def get_size_sort_key(size):
            text_sizes = {'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5, 'XXL': 6}
            if size in text_sizes:
                return (0, text_sizes[size])
            try:
                numeric_size = int(size)
                return (1, numeric_size)
            except:
                return (2, size)
        
        all_skus_with_stats.sort(key=lambda x: (x[2], get_size_sort_key(x[3])))
        selected_skus = [sku[0] for sku in all_skus_with_stats[:max_skus]]
        
        # 3. 매트릭스 데이터 생성
        matrix_data = []
        store_labels = []
        for store in selected_stores:
            row = [final_allocation.get((sku, store), 0) for sku in selected_skus]
            matrix_data.append(row)
            
            # 매장 라벨 생성 (매장명 + QTY_SUM)
            if SHOP_NAMES and store in SHOP_NAMES:
                store_name = SHOP_NAMES[store]
                store_labels.append(f"{store_name}\n({QSUM[store]:,})")
            else:
                store_labels.append(f"{store}\n({QSUM[store]:,})")
        
        # 4. SKU 라벨 생성
        sku_labels = []
        for sku in selected_skus:
            try:
                sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                color = sku_info['COLOR_CD']
                size = sku_info['SIZE_CD']
            except:
                parts = sku.split('_')
                color = parts[1] if len(parts) >= 3 else 'Unknown'
                size = parts[2] if len(parts) >= 3 else 'Unknown'
            total_allocated = sum(final_allocation.get((sku, store), 0) for store in target_stores)
            max_allocatable_qty = calculate_max_allocatable_by_tier(sku, target_stores, tier_system, A, QSUM)
            sku_labels.append(f"{color}-{size}\n({total_allocated}/{max_allocatable_qty})")
        
        # 5. 부가 통계 계산 (빈 셀, 색상/사이즈 다양성)

        total_colors_style = df_sku_filtered['COLOR_CD'].nunique()
        total_sizes_style = df_sku_filtered['SIZE_CD'].nunique()

        empty_cells_counts = []
        color_cov_ratios = []
        size_cov_ratios = []

        for row_idx, store in enumerate(selected_stores):
            row_qties = matrix_data[row_idx]
            # row_qties is a list here – use count(0) instead of numpy comparison
            empty_cells_counts.append(row_qties.count(0))

            # 색상/사이즈 다양성
            allocated_skus_row = [selected_skus[col_idx] for col_idx, qty in enumerate(row_qties) if qty > 0]
            colors = set()
            sizes = set()
            for sku in allocated_skus_row:
                try:
                    sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                    colors.add(sku_info['COLOR_CD'])
                    sizes.add(sku_info['SIZE_CD'])
                except:
                    parts = sku.split('_')
                    if len(parts) >= 3:
                        colors.add(parts[1])
                        sizes.add(parts[2])

            color_cov_ratios.append(len(colors)/total_colors_style if total_colors_style else 0)
            size_cov_ratios.append(len(sizes)/total_sizes_style if total_sizes_style else 0)

        avg_empty_cells = np.mean(empty_cells_counts) if empty_cells_counts else 0
        avg_color_cov = np.mean(color_cov_ratios) if color_cov_ratios else 0
        avg_size_cov = np.mean(size_cov_ratios) if size_cov_ratios else 0

        # 6. 히트맵 생성 - 동적 크기 조절
        matrix_data = np.array(matrix_data)
        vmax_val = fixed_max if fixed_max is not None else max(1, matrix_data.max())
        
        # 매트릭스 크기에 따른 동적 figure size 계산
        width = max(12, len(selected_skus) * 1.2)  # SKU 수에 따라 너비 조절
        height = max(8, len(selected_stores) * 0.3)  # 매장 수에 따라 높이 조절
        
        # 너무 큰 경우 제한
        width = min(width, 30)
        height = min(height, 20)
        
        fig, ax = plt.subplots(figsize=(width, height))
        im = ax.imshow(matrix_data, cmap='Blues', aspect='auto', vmin=0, vmax=vmax_val)
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('Allocated Quantity', rotation=270, labelpad=15)
        
        ax.set_xticks(range(len(selected_skus)))
        ax.set_yticks(range(len(selected_stores)))
        
        # 폰트 크기 동적 조절
        sku_fontsize = max(8, min(12, 120 // len(selected_skus)))
        store_fontsize = max(8, min(12, 120 // len(selected_stores)))
        
        ax.set_xticklabels(sku_labels, rotation=45, ha='right', fontsize=sku_fontsize)
        ax.set_yticklabels(store_labels, ha='right', fontsize=store_fontsize)
        
        # 텍스트 크기 동적 조절
        text_fontsize = max(6, min(10, 60 // max(len(selected_skus), len(selected_stores))))
        
        for i in range(len(selected_stores)):
            for j in range(len(selected_skus)):
                qty = matrix_data[i, j]
                if qty > 0:
                    text_color = 'white' if qty > matrix_data.max()*0.6 else 'black'
                    ax.text(j, i, str(int(qty)), ha='center', va='center', 
                           color=text_color, fontweight='bold', fontsize=text_fontsize)
        
        # ----- Right-side axis showing empty cell count per store -----
        ax_right = ax.twinx()
        ax_right.set_ylim(ax.get_ylim())
        ax_right.set_yticks(np.arange(len(selected_stores)))
        # 빈 셀 수가 0인 경우 라벨을 비워서 표시하지 않음
        right_labels = [str(c) if c > 0 else '' for c in empty_cells_counts]
        ax_right.set_yticklabels(right_labels, fontsize=9)
        # 1 이상 값은 빨간 볼드체로 강조
        for tick, cnt in zip(ax_right.get_yticklabels(), empty_cells_counts):
            if cnt > 0:
                tick.set_color('red')
                tick.set_fontweight('bold')
        ax_right.set_ylabel('Empty SKU Cells', fontsize=12)
        ax_right.tick_params(axis='y', direction='in')

        # Stats box (move to figure upper-right, above colorbar)
        total_allocated = matrix_data.sum()
        filled_combinations = np.count_nonzero(matrix_data)
        stats_text = (
            f"Total Allocated: {total_allocated:,}\n"
            f"Filled Cells: {filled_combinations}\n"
            f"Avg Empty Cells/store: {avg_empty_cells:.1f}\n"
            f"Avg Color Coverage: {avg_color_cov:.2f}\n"
            f"Avg Size Coverage:  {avg_size_cov:.2f}"
        )

        # Figure-level coordinates (transFigure) so it sits above the colorbar area
        fig.text(0.98, 0.98, stats_text, transform=fig.transFigure,
                 fontsize=11, ha='right', va='top',
                 bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))
        
        ax.set_title(f'SKU Allocation Matrix\n(Top {len(selected_stores)} Stores × Top {len(selected_skus)} SKUs)', fontsize=14, fontweight='bold', pad=20)
        ax.set_xlabel('SKU (Color-Size)', fontsize=12)
        ax.set_ylabel('Store Name (QTY_SUM)', fontsize=12)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"   📊 배분 매트릭스 저장: {save_path}")
            plt.close()
        else:
            plt.show()
        
        print(f"   📋 매트릭스 요약:")
        print(f"      표시된 매장: {len(selected_stores)}개")
        print(f"      표시된 SKU: {len(selected_skus)}개")
        print(f"      총 배분량: {total_allocated:,}개")
        
        return {
            'selected_stores': selected_stores,
            'selected_skus': selected_skus,
            'matrix_data': matrix_data,
            'total_allocated': total_allocated
        }

    def create_allocation_matrix_excel(self, final_allocation, target_stores, SKUs, QSUM,
                                     df_sku_filtered, A, tier_system, save_path=None, SHOP_NAMES=None, optimization_time=0):
        """
        배분 결과를 엑셀 매트릭스로 생성
        
        Args:
            final_allocation: 최종 배분 결과
            target_stores: 배분 대상 매장 리스트
            SKUs: SKU 리스트
            QSUM: 매장별 QTY_SUM
            df_sku_filtered: 필터링된 SKU 데이터프레임
            A: SKU별 공급량
            tier_system: 매장 tier 시스템
            save_path: 엑셀 파일 저장 경로
            SHOP_NAMES: 매장별 매장명 딕셔너리
            optimization_time: 최적화 소요 시간 (초)
        """
        print("📊 배분 매트릭스 엑셀 생성 중...")
        
        # 1. 모든 매장을 QTY_SUM 기준으로 내림차순 정렬
        all_stores_with_stats = []
        for store in target_stores:
            store_total = sum(final_allocation.get((sku, store), 0) for sku in SKUs)
            all_stores_with_stats.append((store, store_total, QSUM[store]))
        
        all_stores_with_stats.sort(key=lambda x: x[2], reverse=True)
        sorted_stores = [store[0] for store in all_stores_with_stats]
        
        # 2. 모든 SKU를 컬러-사이즈 기준으로 정렬
        all_skus_with_stats = []
        for sku in SKUs:
            try:
                sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                color = sku_info['COLOR_CD']
                size = sku_info['SIZE_CD']
            except:
                parts = sku.split('_')
                color = parts[1] if len(parts) >= 3 else 'Unknown'
                size = parts[2] if len(parts) >= 3 else 'Unknown'
            all_skus_with_stats.append((sku, color, size))
        
        def get_size_sort_key(size):
            text_sizes = {'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5, 'XXL': 6}
            if size in text_sizes:
                return (0, text_sizes[size])
            try:
                numeric_size = int(size)
                return (1, numeric_size)
            except:
                return (2, size)
        
        all_skus_with_stats.sort(key=lambda x: (x[1], get_size_sort_key(x[2])))
        sorted_skus = [sku[0] for sku in all_skus_with_stats]
        
        # 3. 배분 매트릭스 데이터 생성
        matrix_data = []
        for store in sorted_stores:
            row = [final_allocation.get((sku, store), 0) for sku in sorted_skus]
            matrix_data.append(row)
        
        # 4. DataFrame 생성
        # 매장 인덱스 (매장명 + QTY_SUM)
        store_indices = []
        for store in sorted_stores:
            if SHOP_NAMES and store in SHOP_NAMES:
                store_name = SHOP_NAMES[store]
                store_indices.append(f"{store_name} (QTY:{QSUM[store]:,})")
            else:
                store_indices.append(f"{store} (QTY:{QSUM[store]:,})")
        
        # SKU 컬럼명 (색상-사이즈 + 총배분량/공급량)
        sku_columns = []
        for sku in sorted_skus:
            try:
                sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                color = sku_info['COLOR_CD']
                size = sku_info['SIZE_CD']
            except:
                parts = sku.split('_')
                color = parts[1] if len(parts) >= 3 else 'Unknown'
                size = parts[2] if len(parts) >= 3 else 'Unknown'
            
            total_allocated = sum(final_allocation.get((sku, store), 0) for store in target_stores)
            supply_qty = A.get(sku, 0)
            sku_columns.append(f"{color}-{size} ({total_allocated}/{supply_qty})")
        
        # DataFrame 생성
        df_matrix = pd.DataFrame(matrix_data, index=store_indices, columns=sku_columns)
        
        # 5. 추가 통계 시트 생성
        # 매장별 통계
        store_stats = []
        for store in sorted_stores:
            store_total = sum(final_allocation.get((sku, store), 0) for sku in SKUs)
            sku_count = sum(1 for sku in SKUs if final_allocation.get((sku, store), 0) > 0)
            
            # 색상/사이즈 다양성 계산
            allocated_skus_for_store = [sku for sku in SKUs if final_allocation.get((sku, store), 0) > 0]
            colors = set()
            sizes = set()
            for sku in allocated_skus_for_store:
                try:
                    sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                    colors.add(sku_info['COLOR_CD'])
                    sizes.add(sku_info['SIZE_CD'])
                except:
                    parts = sku.split('_')
                    if len(parts) >= 3:
                        colors.add(parts[1])
                        sizes.add(parts[2])
            
            total_colors = df_sku_filtered['COLOR_CD'].nunique()
            total_sizes = df_sku_filtered['SIZE_CD'].nunique()
            color_coverage = len(colors) / total_colors if total_colors > 0 else 0
            size_coverage = len(sizes) / total_sizes if total_sizes > 0 else 0
            
            # 매장 tier 정보
            try:
                tier_info = tier_system.get_store_tier_info(store, target_stores)
                store_tier = tier_info['tier_name']
            except:
                store_tier = 'Unknown'
            
            # 매장명 가져오기
            store_name = SHOP_NAMES.get(store, store) if SHOP_NAMES else store
            
            store_stats.append({
                '매장ID': store,
                '매장명': store_name,
                'QTY_SUM': QSUM[store],
                '매장_TIER': store_tier,
                '총_배분량': store_total,
                '배분_SKU수': sku_count,
                '색상_다양성': f"{color_coverage:.2%}",
                '사이즈_다양성': f"{size_coverage:.2%}",
                '배분된_색상수': len(colors),
                '배분된_사이즈수': len(sizes)
            })
        
        df_store_stats = pd.DataFrame(store_stats)
        
        # SKU별 통계
        sku_stats = []
        for sku in sorted_skus:
            total_allocated = sum(final_allocation.get((sku, store), 0) for store in target_stores)
            allocated_stores = sum(1 for store in target_stores if final_allocation.get((sku, store), 0) > 0)
            supply_qty = A.get(sku, 0)
            allocation_rate = total_allocated / supply_qty if supply_qty > 0 else 0
            
            try:
                sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                color = sku_info['COLOR_CD']
                size = sku_info['SIZE_CD']
            except:
                parts = sku.split('_')
                color = parts[1] if len(parts) >= 3 else 'Unknown'
                size = parts[2] if len(parts) >= 3 else 'Unknown'
            
            sku_stats.append({
                'SKU': sku,
                '색상': color,
                '사이즈': size,
                '공급량': supply_qty,
                '총_배분량': total_allocated,
                '배분률': f"{allocation_rate:.1%}",
                '배분_매장수': allocated_stores,
                '잔여_수량': supply_qty - total_allocated
            })
        
        df_sku_stats = pd.DataFrame(sku_stats)
        
        # 6. 엑셀 파일 저장
        if save_path:
            with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                # 메인 배분 매트릭스
                df_matrix.to_excel(writer, sheet_name='배분_매트릭스', index=True)
                
                # 매장별 통계
                df_store_stats.to_excel(writer, sheet_name='매장별_통계', index=False)
                
                # SKU별 통계
                df_sku_stats.to_excel(writer, sheet_name='SKU별_통계', index=False)
                
                # 요약 정보
                total_allocated = sum(final_allocation.values())
                total_supply = sum(A.values())
                allocation_rate = total_allocated / total_supply if total_supply > 0 else 0
                allocated_stores = len([s for s in target_stores if sum(final_allocation.get((sku, s), 0) for sku in SKUs) > 0])
                allocated_skus = len([sku for sku in SKUs if sum(final_allocation.get((sku, s), 0) for s in target_stores) > 0])
                avg_store_allocation = total_allocated / len(target_stores) if len(target_stores) > 0 else 0
                
                # 매장별 평균 다양성 계산
                store_color_coverages = []
                store_size_coverages = []
                store_filled_cells = []
                
                for store in target_stores:
                    # 해당 매장에 배분된 SKU들
                    allocated_skus_for_store = [sku for sku in SKUs if final_allocation.get((sku, store), 0) > 0]
                    
                    # 색상/사이즈 다양성 계산
                    colors = set()
                    sizes = set()
                    for sku in allocated_skus_for_store:
                        try:
                            sku_info = df_sku_filtered[df_sku_filtered['SKU'] == sku].iloc[0]
                            colors.add(sku_info['COLOR_CD'])
                            sizes.add(sku_info['SIZE_CD'])
                        except:
                            parts = sku.split('_')
                            if len(parts) >= 3:
                                colors.add(parts[1])
                                sizes.add(parts[2])
                    
                    total_colors = df_sku_filtered['COLOR_CD'].nunique()
                    total_sizes = df_sku_filtered['SIZE_CD'].nunique()
                    
                    color_coverage = len(colors) / total_colors if total_colors > 0 else 0
                    size_coverage = len(sizes) / total_sizes if total_sizes > 0 else 0
                    
                    store_color_coverages.append(color_coverage)
                    store_size_coverages.append(size_coverage)
                    store_filled_cells.append(len(allocated_skus_for_store))
                
                avg_color_coverage = np.mean(store_color_coverages) if store_color_coverages else 0
                avg_size_coverage = np.mean(store_size_coverages) if store_size_coverages else 0
                avg_filled_cells = np.mean(store_filled_cells) if store_filled_cells else 0
                
                summary_data = {
                    '항목': [
                        '총_매장수', '총_SKU수', '총_배분량', '전체_공급량', '전체_배분률',
                        '배분받은_매장수', '배분된_SKU수', '평균_매장당_배분량',
                        '평균_색상_다양성', '평균_사이즈_다양성', '평균_피팅_다양성',
                        '최적화_소요_시간'
                    ],
                    '값': [
                        len(target_stores),
                        len(SKUs),
                        total_allocated,
                        total_supply,
                        f"{allocation_rate:.1%}",
                        allocated_stores,
                        allocated_skus,
                        f"{avg_store_allocation:.1f}",
                        f"{avg_color_coverage:.3f}",
                        f"{avg_size_coverage:.3f}",
                        f"{avg_filled_cells:.1f}",
                        f"{optimization_time:.2f}초"
                    ]
                }
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='요약', index=False)
            
            print(f"   📊 배분 매트릭스 엑셀 저장: {save_path}")
        
        print(f"   📋 엑셀 매트릭스 요약:")
        print(f"      매장: {len(sorted_stores)}개")
        print(f"      SKU: {len(sorted_skus)}개")
        print(f"      총 배분량: {sum(final_allocation.values()):,}개")
        
        return {
            'df_matrix': df_matrix,
            'df_store_stats': df_store_stats,
            'df_sku_stats': df_sku_stats,
            'df_summary': df_summary
        }
