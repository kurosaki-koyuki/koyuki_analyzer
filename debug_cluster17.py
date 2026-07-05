# -*- coding: utf-8 -*-
"""
调试脚本17：定位 clusterTrackingPlot 调用中的问题
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

df_test = df.iloc[:1000, :]
with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

print("=== 逐步测试 CCP 主函数的每一步 ===")
r_code = '''
library(ConsensusClusterPlus)

df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(5000, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
d <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))

maxK <- 2
reps <- 20
pItem <- 0.8
pFeature <- 1
clusterAlg <- "hc"
distance <- "pearson"
seed <- 123456
innerLinkage <- "average"
finalLinkage <- "average"
title <- title_dir
plot <- NULL
writeTable <- FALSE

# 1. ccRun
print("1. 运行 ccRun...")
ml <- ConsensusClusterPlus:::ccRun(d = d, maxK = maxK, repCount = reps, diss = FALSE,
            pItem = pItem, pFeature = pFeature, innerLinkage = innerLinkage,
            clusterAlg = clusterAlg, distance = distance,
            verbose = FALSE, corUse = "everything")
print(paste("  ml 长度:", length(ml)))

# 2. 初始化变量
print("2. 初始化变量...")
res <- list()
colorList <- list()
colorM <- rbind()
thisPal <- ConsensusClusterPlus:::myPal(10)
print(paste("  colorM 初始 dim:", paste(dim(colorM), collapse=" x ")))

# 3. 色阶热图
print("3. 色阶热图...")
colBreaks <- 10
sc <- cbind(seq(0, 1, by = 1/(colBreaks)))
rownames(sc) <- sc[, 1]
sc <- cbind(sc, sc)
print(paste("  sc dim:", paste(dim(sc), collapse=" x ")))
# 不实际绘图，跳过

# 4. 主循环
print("4. 主循环...")
for (tk in 2:maxK) {
  print(paste("  tk =", tk))
  fm <- ml[[tk]]
  hc <- hclust(as.dist(1 - fm), method = finalLinkage)
  ct <- cutree(hc, tk)
  names(ct) <- colnames(d)
  c <- fm
  
  colorList <- ConsensusClusterPlus:::setClusterColors(res[[tk - 1]][[3]], ct, thisPal, colorList)
  
  pc <- c
  pc <- pc[hc$order, ]
  pc <- rbind(pc, 0)
  # 跳过 heatmap 绘制
  
  res[[tk]] <- list(consensusMatrix = c, consensusTree = hc, consensusClass = ct, ml = ml[[tk]], clrs = colorList)
  colorM <- rbind(colorM, colorList[[1]])
  print(paste("  colorM dim:", paste(dim(colorM), collapse=" x ")))
}
print(paste("  循环后 colorM dim:", paste(dim(colorM), collapse=" x ")))
print(paste("  res 长度:", length(res)))

# 5. CDF
print("5. CDF...")
# 跳过绘图

# 6. clusterTrackingPlot
print("6. clusterTrackingPlot...")
print(paste("  colorM dim:", paste(dim(colorM), collapse=" x ")))
print(paste("  res[[length(res)]] 长度:", length(res[[length(res)]])))
print(paste("  res[[length(res)]]$consensusTree$order 长度:", length(res[[length(res)]]$consensusTree$order)))
print(paste("  res[[length(res)]]$consensusTree$order 前10个:", paste(head(res[[length(res)]]$consensusTree$order), collapse=",")))

# 关键：检查 colorM[, res[[length(res)]]$consensusTree$order]
print("  检查 colorM 索引...")
ctp_input <- colorM[, res[[length(res)]]$consensusTree$order]
print(paste("  ctp_input dim:", paste(dim(ctp_input), collapse=" x ")))
print(paste("  ctp_input class:", class(ctp_input)))

# 如果是向量而不是矩阵，nrow() 会返回 NULL
if (is.matrix(ctp_input)) {
  print("  ctp_input 是矩阵")
} else {
  print("  ctp_input 不是矩阵！")
  print(paste("  ctp_input 长度:", length(ctp_input)))
}

# 尝试调用
tryCatch({
  ConsensusClusterPlus:::clusterTrackingPlot(ctp_input)
  print("  clusterTrackingPlot 成功")
}, error = function(e) {
  print(paste("  clusterTrackingPlot 错误:", e$message))
})

print("完成")
'''

try:
    robjects.r(r_code)
except Exception as e:
    print(f"Python 错误: {e}")

print("\n完成")
