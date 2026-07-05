# -*- coding: utf-8 -*-
"""
调试脚本2：逐步排查 mad 报错
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
print(f"adata shape: {adata.shape}")

X = adata.X
if hasattr(X, 'toarray'):
    X = X.toarray()
df = pd.DataFrame(X.T, index=adata.var_names, columns=adata.obs_names)
print(f"df shape: {df.shape}")
print(f"df前3行前3列:")
print(df.iloc[:3, :3])
print(f"df.dtypes: {df.dtypes.value_counts().to_dict()}")

r_interface = get_r_kernel_interface()
robjects = r_interface.get_robjects()
pandas2ri = r_interface.get_pandas2ri()

# 只取前50个基因测试
df_test = df.iloc[:50, :10]
print(f"\n测试数据形状: {df_test.shape}")
print(df_test)

with localconverter(pandas2ri.converter):
    r_df = robjects.globalenv['expr_data'] = df_test

print(f"\nR中 dim(expr_data): {robjects.r('dim(expr_data)')}")
print(f"R中 class(expr_data): {robjects.r('class(expr_data)')}")
print(f"R中 typeof(expr_data): {robjects.r('typeof(expr_data)')}")

# 转成matrix
robjects.r('df <- as.matrix(expr_data)')
print(f"R中 dim(df): {robjects.r('dim(df)')}")
print(f"R中 class(df): {robjects.r('class(df)')}")
print(f"R中 typeof(df): {robjects.r('typeof(df)')}")

# 测试apply
robjects.r('mads <- apply(df, 1, mad)')
print(f"R中 length(mads): {robjects.r('length(mads)')}")
print(f"R中 head(mads): {robjects.r('head(mads)')}")

print("\n成功！")
