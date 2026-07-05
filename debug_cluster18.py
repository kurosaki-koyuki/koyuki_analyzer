# -*- coding: utf-8 -*-
"""
调试脚本18：测试修复后的阶段一代码
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
pheatmap = importr('pheatmap')
grDevices = importr('grDevices')

df_test = df.iloc[:1000, :]
print(f"测试数据: {df_test.shape}")

with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
print(f"临时目录: {temp_dir}")
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

# 模拟阶段一参数
robjects.globalenv['mad_threshold'] = robjects.IntVector([5000])
robjects.globalenv['reps'] = robjects.IntVector([20])
robjects.globalenv['cluster_alg'] = robjects.StrVector(["hc"])
robjects.globalenv['distance'] = robjects.StrVector(["pearson"])
robjects.globalenv['p_item'] = robjects.FloatVector([0.8])
robjects.globalenv['p_feature'] = robjects.FloatVector([1.0])
robjects.globalenv['min_k'] = robjects.IntVector([2])
robjects.globalenv['max_k'] = robjects.IntVector([9])
robjects.globalenv['plot_format'] = robjects.StrVector(["png"])
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

print("\n=== 执行 STAGE1 代码 ===")
# 读取R脚本中的STAGE1代码
r_script_path = r'script\analyzer_layer\bulk_layer\bulk_cluster_layer\bulk_cluster_analysis.R'
with open(r_script_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_marker = "# --- STAGE1_BODY_START ---"
end_marker = "# --- STAGE1_BODY_END ---"
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if start_marker in line:
        start_idx = i + 1
    if end_marker in line:
        end_idx = i

stage1_code = ''.join(lines[start_idx:end_idx])
print(f"STAGE1 代码长度: {len(stage1_code)} 字符")

try:
    robjects.r(stage1_code)
    print("\n=== STAGE1 成功！ ===")
    
    # 检查结果
    result_check = '''
    print(paste("ccp_results 长度:", length(ccp_results)))
    for (k in 2:9) {
      print(paste("k=", k, ":", sep=""))
      print(paste("  consensusMatrix dim:", paste(dim(ccp_results[[k]]$consensusMatrix), collapse=" x ")))
      print(paste("  consensusTree 标签数:", length(ccp_results[[k]]$consensusTree$labels)))
      print(paste("  consensusClass 长度:", length(ccp_results[[k]]$consensusClass)))
      print(paste("  consensusClass table:", paste(table(ccp_results[[k]]$consensusClass), collapse=",")))
    }
    print(paste("ccp_exprSet dim:", paste(dim(ccp_exprSet), collapse=" x ")))
    '''
    robjects.r(result_check)
    
except Exception as e:
    print(f"\n=== STAGE1 失败: {e} ===")

print("\n完成")
