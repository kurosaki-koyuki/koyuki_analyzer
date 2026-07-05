# -*- coding: utf-8 -*-
"""
调试脚本15：追踪 CCP 主循环中的错误
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
d <- exprSet
print(paste("d dim:", paste(dim(d), collapse=" x ")))
print(paste("d colnames count:", length(colnames(d))))
''')

print("\n=== 手动模拟 CCP 主循环 ===")
r_code = '''
library(ConsensusClusterPlus)

maxK <- 2
reps <- 20
pItem <- 0.8
pFeature <- 1
clusterAlg <- "hc"
distance <- "pearson"
seed <- 123456
innerLinkage <- "average"
finalLinkage <- "average"

# 运行 ccRun
print("运行 ccRun...")
ml <- ConsensusClusterPlus:::ccRun(d = d, maxK = maxK, repCount = reps, diss = FALSE,
            pItem = pItem, pFeature = pFeature, innerLinkage = innerLinkage,
            clusterAlg = clusterAlg, distance = distance,
            verbose = FALSE, corUse = "everything")
print(paste("ml 长度:", length(ml)))
for (i in 1:length(ml)) {
  print(paste("  ml[[", i, "]] class:", class(ml[[i]])))
  if (is.matrix(ml[[i]])) {
    print(paste("  ml[[", i, "]] dim:", paste(dim(ml[[i]]), collapse=" x ")))
  }
}

# 初始化主循环变量
print("\\n初始化主循环变量...")
res <- list()
colorList <- list()
colorM <- rbind()

thisPal <- c("#A6CEE3", "#1F78B4", "#B2DF8A", "#33A02C",
    "#FB9A99", "#E31A1C", "#FDBF6F", "#FF7F00", "#CAB2D6",
    "#6A3D9A", "#FFFF99", "#B15928", "#bd18ea", "#2ef4ca",
    "#f4cced", "#f4cc03", "#05188a", "#e5a25a", "#06f106",
    "#85848f", "#000000", "#076f25", "#93cd7f", "#4d0776",
    "#ffffff")

print(paste("res 初始长度:", length(res)))
print(paste("colorList 初始长度:", length(colorList)))
print(paste("colorM dim:", paste(dim(colorM), collapse=" x ")))

# 主循环
for (tk in 2:maxK) {
  print(paste("\\n===== tk =", tk, "====="))
  fm <- ml[[tk]]
  print(paste("fm class:", class(fm)))
  print(paste("fm dim:", paste(dim(fm), collapse=" x ")))
  
  print("hclust...")
  hc <- hclust(as.dist(1 - fm), method = finalLinkage)
  print("clustered")
  
  ct <- cutree(hc, tk)
  print(paste("ct 长度:", length(ct)))
  print(paste("ct table:", paste(table(ct), collapse=",")))
  
  names(ct) <- colnames(d)
  print(paste("names(ct) 长度:", length(names(ct))))
  
  c <- fm
  
  print(paste("res[[tk - 1]] 是否存在:", (tk - 1) <= length(res)))
  if ((tk - 1) <= length(res)) {
    print(paste("res[[", tk - 1, "]] 长度:", length(res[[tk - 1]])))
  }
  
  print("调用 setClusterColors...")
  print(paste("  past_ct = res[[", tk - 1, "]][[3]]", sep=""))
  print(paste("  ct 长度:", length(ct)))
  print(paste("  colorList 长度:", length(colorList)))
  
  tryCatch({
    colorList <- ConsensusClusterPlus:::setClusterColors(res[[tk - 1]][[3]], ct, thisPal, colorList)
    print("setClusterColors 成功")
    print(paste("  返回 colorList 长度:", length(colorList)))
  }, error = function(e) {
    print(paste("setClusterColors 错误:", e$message))
    traceback()
  })
  
  # 继续后面的步骤...
  print("继续后面步骤...")
  pc <- c
  pc <- pc[hc$order, ]
  
  res[[tk]] <- list(consensusMatrix = c, consensusTree = hc,
                    consensusClass = ct, ml = ml[[tk]], clrs = colorList)
  print(paste("res[[", tk, "]] 已保存，长度:", length(res[[tk]])))
  
  colorM <- rbind(colorM, colorList[[1]])
  print(paste("colorM dim:", paste(dim(colorM), collapse=" x ")))
}

print("\\n主循环完成")
print(paste("最终 res 长度:", length(res)))
'''

try:
    robjects.r(r_code)
except Exception as e:
    print(f"\nPython 捕获到错误: {e}")

print("\n完成")
