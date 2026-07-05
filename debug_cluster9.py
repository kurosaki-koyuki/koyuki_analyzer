# -*- coding: utf-8 -*-
"""
调试脚本9：用全部样本测试，reps=20快速跑
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
print(f"df shape: {df.shape}")

r_interface = get_r_kernel_interface()
robjects = r_interface.get_robjects()
pandas2ri = r_interface.get_pandas2ri()

ConsensusClusterPlus = importr('ConsensusClusterPlus')

# 取前1000个基因，全部325个样本
df_test = df.iloc[:1000, :]
print(f"测试数据: {df_test.shape}")

with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
print(f"临时目录: {temp_dir}")
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

# 预处理
print("\n预处理中...")
robjects.r('''
df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(5000, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))
print(paste("exprSet dim:", paste(dim(exprSet), collapse=" x ")))
''')

# 用 try 跑 CCP, reps=20 maxK=2
print("\n运行ConsensusClusterPlus (maxK=2, reps=20)...")
r_code = '''
tryCatch({
  results <- ConsensusClusterPlus(exprSet,
                                  maxK = 2,
                                  reps = 20,
                                  pItem = 0.8,
                                  pFeature = 1,
                                  title = title_dir,
                                  clusterAlg = "hc",
                                  distance = "pearson",
                                  seed = 123456,
                                  plot = NULL)
  print("成功！")
  print(paste("k=2 一致性矩阵维度:", paste(dim(results[[2]]$consensusMatrix), collapse=" x ")))
}, error = function(e) {
  print(paste("错误:", e$message))
  # 把调用栈打出来
  calls <- sys.calls()
  for(i in seq_along(calls)) {
    call_str <- deparse(calls[[i]])[1]
    print(paste0("[", i, "] ", call_str))
  }
})
'''

robjects.r(r_code)

print("\n完成")
