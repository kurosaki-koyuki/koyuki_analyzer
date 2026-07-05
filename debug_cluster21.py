# -*- coding: utf-8 -*-
"""
调试脚本21：测试筛选条件是否生效
"""
import sys
import os

os.chdir(r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')
sys.path.insert(0, r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')

import scanpy as sc

adata = sc.read_h5ad(r'appdata\bulk_main\CGGA325_TPM.h5ad')
print(f"adata shape: {adata.shape}")
print(f"obs columns: {list(adata.obs.columns)}")
print(f"obs 前5行:")
print(adata.obs.head())

# 检查第一个列的唯一值
if len(adata.obs.columns) > 0:
    first_col = adata.obs.columns[0]
    print(f"\n第一列 {first_col} 的唯一值:")
    print(adata.obs[first_col].unique())

# 模拟 prepare_expr_data
from script.analyzer_layer.bulk_layer.bulk_cluster_layer.bulk_cluster_analysis import get_bulk_cluster_analysis

analysis = get_bulk_cluster_analysis()
analysis.set_adata(adata)

print("\n=== 测试1: 不筛选（全部样本） ===")
df_all = analysis.prepare_expr_data()
print(f"结果 shape: {df_all.shape}")

print("\n=== 测试2: 用第一列筛选 ===")
if len(adata.obs.columns) > 0:
    first_col = adata.obs.columns[0]
    unique_vals = list(adata.obs[first_col].unique())
    if len(unique_vals) >= 2:
        filter_groups = [str(unique_vals[0])]
        print(f"筛选列: {first_col}")
        print(f"筛选值: {filter_groups}")
        df_filtered = analysis.prepare_expr_data(
            clinical_col=first_col,
            clinical_groups=filter_groups
        )
        if df_filtered is not None:
            print(f"筛选后 shape: {df_filtered.shape}")
            print(f"筛选后样本数: {df_filtered.shape[1]}")
        else:
            print("筛选结果为 None")

print("\n完成")
