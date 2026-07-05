# -*- coding: utf-8 -*-
"""
调试脚本8：查找1:nrow(m)在CCP中的位置
"""
import sys
import os

os.chdir(r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')
sys.path.insert(0, r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from rpy2.robjects.packages import importr

r_interface = get_r_kernel_interface()
robjects = r_interface.get_robjects()

ConsensusClusterPlus = importr('ConsensusClusterPlus')

# 打印函数源代码中包含 nrow(m) 的行
r_code = '''
src <- capture.output(print(ConsensusClusterPlus))
lines_with_nrow_m <- grep("nrow\\(m\\)", src, value = TRUE)
print(lines_with_nrow_m)
print("---")
# 看看包含m的上下文
idx <- grep("nrow\\(m\\)", src)
for(i in idx) {
  print(paste("Line", i, ":", src[max(1, i-2):min(length(src), i+2)]))
  print("---")
}
'''

robjects.r(r_code)

print("完成")
