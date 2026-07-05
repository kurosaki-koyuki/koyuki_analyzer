# -*- coding: utf-8 -*-
"""
调试脚本7：查看traceback
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

df_test = df.iloc[:50, :15]
print(f"测试数据: {df_test.shape}")

with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

# 预处理
robjects.r('''
df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(50, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))
''')

print(f"exprSet dim: {robjects.r('dim(exprSet)')}")

# 用 tryCatch 捕获 traceback
r_code = '''
tryCatch({
  results <- ConsensusClusterPlus(exprSet,
                                  maxK = 2,
                                  reps = 5,
                                  pItem = 0.8,
                                  pFeature = 1,
                                  title = title_dir,
                                  clusterAlg = "hc",
                                  distance = "pearson",
                                  seed = 123456,
                                  plot = NULL)
  print("成功")
}, error = function(e) {
  print(paste("错误:", e$message))
  traceback()
})
'''

print("\n运行中...")
robjects.r(r_code)

print("\n完成")
