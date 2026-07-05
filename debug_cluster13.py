# -*- coding: utf-8 -*-
"""
调试脚本13：查看 ccRun 函数源码
"""
import sys
import os

os.chdir(r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')
sys.path.insert(0, r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface

r_interface = get_r_kernel_interface()
robjects = r_interface.get_robjects()

print("=== ccRun 函数源码 ===")
r_code = '''
library(ConsensusClusterPlus)
# 获取 ccRun 函数（未导出的函数，用 ::: 访问）
ccRun <- ConsensusClusterPlus:::ccRun
print(ccRun)
'''

try:
    result = robjects.r(r_code)
except Exception as e:
    print(f"错误: {e}")

print("\n\n=== 搜索 1:nrow 相关代码 ===")
r_code2 = '''
ccRun <- ConsensusClusterPlus:::ccRun
body_text <- deparse(body(ccRun))
nrow_lines <- grep("nrow", body_text, value = TRUE)
for (line in nrow_lines) {
  print(line)
}
'''

try:
    result = robjects.r(r_code2)
except Exception as e:
    print(f"错误: {e}")

print("\n完成")
