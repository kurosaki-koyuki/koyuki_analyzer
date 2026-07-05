# -*- coding: utf-8 -*-
"""
调试脚本11：获取完整的错误调用栈
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

# 取前1000个基因，全部325个样本
df_test = df.iloc[:1000, :]
print(f"测试数据: {df_test.shape}")

with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
print(f"临时目录: {temp_dir}")
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

# 预处理
robjects.r('''
df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(5000, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))
''')

print("\n=== 运行 CCP 并获取完整错误追踪 ===")
r_code = '''
options(showWarnCalls = TRUE, showErrorCalls = TRUE)

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
}, error = function(e) {
  cat("\\n========== 错误信息 ==========\\n")
  print(e)
  cat("\\n========== traceback() ==========\\n")
  traceback()
  cat("\\n========== sys.calls() ==========\\n")
  calls <- sys.calls()
  for(i in rev(seq_along(calls))) {
    call_str <- deparse(calls[[i]])[1]
    cat(sprintf("[%d] %s\\n", i, call_str))
  }
})
'''

robjects.r(r_code)

print("\n完成")
