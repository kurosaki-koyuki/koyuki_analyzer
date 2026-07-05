# -*- coding: utf-8 -*-
"""
调试脚本14：查看 connectivityMatrix 和 triangle 函数源码
"""
import sys
import os

os.chdir(r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')
sys.path.insert(0, r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface

r_interface = get_r_kernel_interface()
robjects = r_interface.get_robjects()

print("=== connectivityMatrix 函数 ===")
r_code = '''
library(ConsensusClusterPlus)
connectivityMatrix <- ConsensusClusterPlus:::connectivityMatrix
print(connectivityMatrix)
'''

try:
    result = robjects.r(r_code)
except Exception as e:
    print(f"错误: {e}")

print("\n\n=== triangle 函数 ===")
r_code2 = '''
triangle <- ConsensusClusterPlus:::triangle
print(triangle)
'''

try:
    result = robjects.r(r_code2)
except Exception as e:
    print(f"错误: {e}")

print("\n\n=== setClusterColors 函数 ===")
r_code3 = '''
setClusterColors <- ConsensusClusterPlus:::setClusterColors
print(setClusterColors)
'''

try:
    result = robjects.r(r_code3)
except Exception as e:
    print(f"错误: {e}")

print("\n\n=== CDF 函数 ===")
r_code4 = '''
CDF <- ConsensusClusterPlus:::CDF
print(CDF)
'''

try:
    result = robjects.r(r_code4)
except Exception as e:
    print(f"错误: {e}")

print("\n完成")
