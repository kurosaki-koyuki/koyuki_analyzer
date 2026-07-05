# -*- coding: utf-8 -*-
"""
调试脚本22：用分类列测试筛选
"""
import sys
import os

os.chdir(r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')
sys.path.insert(0, r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')

import scanpy as sc

adata = sc.read_h5ad(r'appdata\bulk_main\CGGA325_TPM.h5ad')

# 找一个分类列
for col in ['grade', 'gender', 'state', 'IDH_mutation_status', 'molecular_subtype_3types']:
    if col in adata.obs.columns:
        print(f"\n{col} 的唯一值:")
        print(adata.obs[col].value_counts())

from script.analyzer_layer.bulk_layer.bulk_cluster_layer.bulk_cluster_analysis import get_bulk_cluster_analysis

analysis = get_bulk_cluster_analysis()
analysis.set_adata(adata)

# 用 grade 列测试
print("\n=== 测试 grade 列筛选 ===")
col = 'grade'
if col in adata.obs.columns:
    unique_vals = list(adata.obs[col].dropna().unique())
    print(f"筛选列: {col}")
    print(f"所有唯一值: {unique_vals}")
    
    # 筛选前两个值
    filter_groups = [str(v) for v in unique_vals[:2]]
    print(f"筛选值: {filter_groups}")
    
    df_filtered = analysis.prepare_expr_data(
        clinical_col=col,
        clinical_groups=filter_groups
    )
    if df_filtered is not None:
        print(f"筛选后 shape: {df_filtered.shape}")
        print(f"筛选后样本数: {df_filtered.shape[1]}")
    else:
        print("筛选结果为 None")

# 用 molecular_subtype_3types 列测试
print("\n=== 测试 molecular_subtype_3types 列筛选 ===")
col = 'molecular_subtype_3types'
if col in adata.obs.columns:
    unique_vals = list(adata.obs[col].dropna().unique())
    print(f"筛选列: {col}")
    print(f"所有唯一值: {unique_vals}")
    
    filter_groups = [str(v) for v in unique_vals[:1]]  # 只选第一个
    print(f"筛选值: {filter_groups}")
    
    df_filtered = analysis.prepare_expr_data(
        clinical_col=col,
        clinical_groups=filter_groups
    )
    if df_filtered is not None:
        print(f"筛选后 shape: {df_filtered.shape}")
        print(f"筛选后样本数: {df_filtered.shape[1]}")
        print(f"筛选后样本名前5个: {list(df_filtered.columns[:5])}")
    else:
        print("筛选结果为 None")

print("\n完成")
