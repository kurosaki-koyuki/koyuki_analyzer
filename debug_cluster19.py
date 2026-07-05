# -*- coding: utf-8 -*-
"""
调试脚本19：测试阶段三 k=2 热图生成
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
output_path = os.path.join(temp_dir, "test_heatmap_k2.png").replace('\\', '/')
print(f"输出路径: {output_path}")

# 阶段一参数
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

print("\n=== 执行 STAGE1 ===")
r_script_path = r'script\analyzer_layer\bulk_layer\bulk_cluster_layer\bulk_cluster_analysis.R'
with open(r_script_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def get_stage_code(stage_name):
    start_marker = f"# --- {stage_name}_BODY_START ---"
    end_marker = f"# --- {stage_name}_BODY_END ---"
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_marker in line:
            start_idx = i + 1
        if end_marker in line:
            end_idx = i
    return ''.join(lines[start_idx:end_idx])

stage1_code = get_stage_code("STAGE1")
try:
    robjects.r(stage1_code)
    print("STAGE1 成功！")
except Exception as e:
    print(f"STAGE1 失败: {e}")
    sys.exit(1)

# 阶段三参数
robjects.globalenv['final_k'] = robjects.IntVector([2])
robjects.globalenv['output_mode'] = robjects.IntVector([1])
robjects.globalenv['output_path'] = robjects.StrVector([output_path])
robjects.globalenv['heatmap_width'] = robjects.FloatVector([8])
robjects.globalenv['heatmap_height'] = robjects.FloatVector([8])
robjects.globalenv['color_scheme'] = robjects.StrVector(["blue"])
robjects.globalenv['title_font_size'] = robjects.IntVector([14])
robjects.globalenv['legend_font_size'] = robjects.IntVector([12])
robjects.globalenv['clustering_method'] = robjects.StrVector(["average"])

print("\n=== 执行 STAGE3 (k=2 热图) ===")
stage3_code = get_stage_code("STAGE3")
try:
    robjects.r(stage3_code)
    print("STAGE3 成功！")
    
    # 检查文件是否存在
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"热图已生成: {output_path}")
        print(f"文件大小: {file_size} bytes")
    else:
        print(f"警告: 热图文件不存在: {output_path}")
        
except Exception as e:
    print(f"STAGE3 失败: {e}")

print("\n完成")
