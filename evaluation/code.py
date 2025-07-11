import pandas as pd

# Read the CSV file
df = pd.read_csv('data/data_real.csv')

# Group by PROD_CD, COLOR_CD, and SIZ_CD, then sum QTY
result = df.groupby(['PROD_CD', 'COLOR_CD', 'SIZ_CD'])['QTY'].sum().reset_index()

# Rename columns to match 발주수량.csv format
result = result.rename(columns={
    'PROD_CD': 'PART_CD',
    'SIZ_CD': 'SIZE_CD',
    'QTY': 'ORD_QTY'
})

# Sort by PART_CD, COLOR_CD, SIZE_CD
result_sorted = result.sort_values(['PART_CD', 'COLOR_CD', 'SIZE_CD'])

# Display the results
print("PROD_CD, COLOR_CD, SIZ_CD별 QTY 합계:")
print("=" * 80)
print(f"{'PART_CD':<15} {'COLOR_CD':<10} {'SIZE_CD':<10} {'ORD_QTY':<10}")
print("-" * 80)

for _, row in result_sorted.iterrows():
    print(f"{row['PART_CD']:<15} {row['COLOR_CD']:<10} {row['SIZE_CD']:<10} {row['ORD_QTY']:<10}")

# Save to CSV file in the same format as 발주수량.csv
output_file = 'data/prod_color_size_qty_summary.csv'
result_sorted.to_csv(output_file, index=False)
print(f"\n결과가 {output_file}에 저장되었습니다.")

# Display some statistics
print(f"\n통계 정보:")
print(f"총 PART_CD 개수: {result_sorted['PART_CD'].nunique()}")
print(f"총 COLOR_CD 개수: {result_sorted['COLOR_CD'].nunique()}")
print(f"총 SIZE_CD 개수: {result_sorted['SIZE_CD'].nunique()}")
print(f"총 레코드 수: {len(result_sorted)}")
print(f"총 ORD_QTY 합계: {result_sorted['ORD_QTY'].sum():,}")
print(f"평균 ORD_QTY: {result_sorted['ORD_QTY'].mean():.2f}")
print(f"최대 ORD_QTY: {result_sorted['ORD_QTY'].max()}")
print(f"최소 ORD_QTY: {result_sorted['ORD_QTY'].min()}")

# Show sample of the output file format
print(f"\n저장된 파일 형식 샘플 (처음 10행):")
print("=" * 80)
sample_df = result_sorted.head(10)
for _, row in sample_df.iterrows():
    print(f"{row['PART_CD']:<15} {row['COLOR_CD']:<10} {row['SIZE_CD']:<10} {row['ORD_QTY']:<10}")
