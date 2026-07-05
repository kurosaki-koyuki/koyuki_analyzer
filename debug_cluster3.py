# -*- coding: utf-8 -*-
"""
调试脚本3：测试500基因时为什么报错
"""
import sys
import os

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
print(f"df shape: {df.shape}")

r_interface = get_r_kernel_interface()
robjects = r_interface.get_robjects()
pandas2ri = r_interface.get_pandas2ri()

# 测试不同数量的基因
for n_genes in [100, 200, 500, 1000, 2000]:
    df_test = df.iloc[:n_genes, :]
    print(f"\n--- 测试 {n_genes} 个基因 ---")

    with localconverter(pandas2ri.converter):
        robjects.globalenv['expr_data'] = df_test

    try:
        robjects.r('df <- as.matrix(expr_data)')
        print(f"  as.matrix成功, dim={robjects.r('dim(df)')}")

        robjects.r('mads <- apply(df, 1, mad)')
        print(f"  mad成功, length={robjects.r('length(mads)')}")

        robjects.r('n_genes <- min(5000, nrow(df))')
        robjects.r('df_filtered <- df[rev(order(mads))[1:n_genes], ]')
        print(f"  筛选成功, dim={robjects.r('dim(df_filtered)')}")

        robjects.r('exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))')
        print(f"  sweep成功, dim={robjects.r('dim(exprSet)')}")

        print(f"  全部通过！")

    except Exception as e:
        print(f"  失败: {e}")
        break
