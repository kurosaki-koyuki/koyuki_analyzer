# -*- coding: utf-8 -*-
"""
调试脚本5：逐步排查 ConsensusClusterPlus 内部报错
"""
import sys
import os
import tempfile

os.chdir(r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')
sys.path.insert(0, r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')

import scanpy as sc
import pandas as pd
import numpy as np

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from rpy2.robjects.packages import importr
from rpy2.robjects.conversion import localconverter

adata = sc.read_h5ad(r'appdata\bulk_main\CGGA325_TPM.h5ad')

X = adata.X
if hasattr(X, 'toarray'):
    X = X.toarray()
df = pd.DataFrame(X.T, index=adata.var_names, columns=adata.obs_names)

r_interface = get_r_kernel_interface()
robjects = r_interface.get_robjects()
pandas2ri = r_interface.get_pandas2ri()

ConsensusClusterPlus = importr('ConsensusClusterPlus')
pheatmap_pkg = importr('pheatmap')

# 测试：200个基因，k=2，reps=50
df_test = df.iloc[:200, :30]
print(f"测试数据: {df_test.shape}")

with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

# 逐步检查
print("\n步骤1: as.matrix")
robjects.r('df <- as.matrix(expr_data)')
print(f"  dim(df) = {robjects.r('dim(df)')}")
print(f"  class(df) = {robjects.r('class(df)')}")
print(f"  rownames(df)[1:3] = {robjects.r('head(rownames(df), 3)')}")
print(f"  colnames(df)[1:3] = {robjects.r('head(colnames(df), 3)')}")

print("\n步骤2: MAD筛选")
robjects.r('mads <- apply(df, 1, mad)')
print(f"  length(mads) = {robjects.r('length(mads)')}")
print(f"  anyNA(mads) = {robjects.r('anyNA(mads)')}")
print(f"  all(mads == 0) = {robjects.r('all(mads == 0)')}")

robjects.r('n_genes <- min(500, nrow(df))')
robjects.r('df_filtered <- df[rev(order(mads))[1:n_genes], ]')
print(f"  dim(df_filtered) = {robjects.r('dim(df_filtered)')}")

print("\n步骤3: 减中位数标准化")
robjects.r('gene_medians <- apply(df_filtered, 1, median, na.rm = TRUE)')
print(f"  length(gene_medians) = {robjects.r('length(gene_medians)')}")
print(f"  anyNA(gene_medians) = {robjects.r('anyNA(gene_medians)')}")

robjects.r('exprSet <- sweep(df_filtered, 1, gene_medians)')
print(f"  dim(exprSet) = {robjects.r('dim(exprSet)')}")
print(f"  class(exprSet) = {robjects.r('class(exprSet)')}")
print(f"  anyNA(exprSet) = {robjects.r('anyNA(exprSet)')}")
print(f"  all(is.finite(exprSet)) = {robjects.r('all(is.finite(exprSet))')}")

print("\n步骤4: 检查行名列名")
print(f"  rownames(exprSet)[1:3] = {robjects.r('head(rownames(exprSet), 3)')}")
print(f"  colnames(exprSet)[1:3] = {robjects.r('head(colnames(exprSet), 3)')}")
print(f"  is.null(rownames(exprSet)) = {robjects.r('is.null(rownames(exprSet))')}")
print(f"  is.null(colnames(exprSet)) = {robjects.r('is.null(colnames(exprSet))')}")

print("\n步骤5: 运行ConsensusClusterPlus (reps=10)")
r_code_ccp = """
results <- ConsensusClusterPlus(exprSet,
                                maxK = 2,
                                reps = 10,
                                pItem = 0.8,
                                pFeature = 1,
                                title = title_dir,
                                clusterAlg = "hc",
                                distance = "pearson",
                                seed = 123456,
                                plot = "png")
print("聚类完成")
"""
try:
    robjects.r(r_code_ccp)
    print("  成功！")
except Exception as e:
    print(f"  失败: {e}")

print("\n测试完成")
