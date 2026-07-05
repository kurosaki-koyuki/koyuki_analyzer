# -*- coding: utf-8 -*-
"""
调试脚本6：排查 plot=NULL 测试
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

# 小数据快速测试
df_test = df.iloc[:100, :20]
print(f"测试数据: {df_test.shape}")

with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

# 预处理
robjects.r('''
df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(500, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))
''')

print(f"exprSet dim: {robjects.r('dim(exprSet)')}")

# 测试1: plot=NULL
print("\n=== 测试1: plot=NULL ===")
try:
    robjects.r('''
    results <- ConsensusClusterPlus(exprSet,
                                    maxK = 2,
                                    reps = 10,
                                    pItem = 0.8,
                                    pFeature = 1,
                                    title = title_dir,
                                    clusterAlg = "hc",
                                    distance = "pearson",
                                    seed = 123456,
                                    plot = NULL)
    print("成功！")
    ''')
    print(f"  k=2 一致性矩阵维度: {robjects.r('dim(results[[2]]$consensusMatrix)')}")
except Exception as e:
    print(f"  失败: {e}")

# 测试2: plot="png" 但用一个简单的数据集
print("\n=== 测试2: 使用内置数据集 ===")
try:
    robjects.r('''
    data(Golub)
    r <- ConsensusClusterPlus(Golub, maxK=2, reps=10, pItem=0.8, pFeature=1,
                             title=title_dir, clusterAlg="hc", distance="pearson",
                             seed=123456, plot="png")
    print("内置数据集测试成功！")
    ''')
    print("  成功！")
except Exception as e:
    print(f"  失败: {e}")

print("\n测试完成")
