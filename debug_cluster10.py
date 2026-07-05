# -*- coding: utf-8 -*-
"""
调试脚本10：深入调试 ConsensusClusterPlus，逐步追踪
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
print("\n=== 步骤1: 预处理 ===")
robjects.r('''
df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(5000, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))
print(paste("exprSet dim:", paste(dim(exprSet), collapse=" x ")))
print(paste("exprSet class:", class(exprSet)))
print(paste("exprSet rownames count:", length(rownames(exprSet))))
print(paste("exprSet colnames count:", length(colnames(exprSet))))
''')

# 测试手动运行 CCP 的各个内部步骤
print("\n=== 步骤2: 测试 CCP 内部参数 ===")
robjects.r('''
maxK = 2
reps = 20
pItem = 0.8
pFeature = 1
clusterAlg = "hc"
distance = "pearson"
seed = 123456

print(paste("maxK:", maxK))
print(paste("reps:", reps))
print(paste("pItem:", pItem))
print(paste("pFeature:", pFeature))
print(paste("clusterAlg:", clusterAlg))
print(paste("distance:", distance))

# 样本数
n_samples <- ncol(exprSet)
n_genes <- nrow(exprSet)
print(paste("样本数 n_samples:", n_samples))
print(paste("基因数 n_genes:", n_genes))

# 每次抽样的样本数
sample_k <- floor(pItem * n_samples)
print(paste("每次抽样样本数 sample_k:", sample_k))

# 每次抽样的基因数
feature_k <- floor(pFeature * n_genes)
print(paste("每次抽样基因数 feature_k:", feature_k))
''')

# 测试单次聚类
print("\n=== 步骤3: 测试单次聚类循环 ===")
robjects.r('''
set.seed(seed)

# 模拟第一次迭代
print("第1次抽样...")

# 抽样样本
sample_index <- sample(1:n_samples, sample_k, replace = FALSE)
print(paste("抽样样本数:", length(sample_index)))
print(paste("sample_index 前10个:", paste(head(sample_index), collapse=",")))

# 抽样基因
if (pFeature < 1) {
  feature_index <- sample(1:n_genes, feature_k, replace = FALSE)
} else {
  feature_index <- 1:n_genes
}
print(paste("抽样基因数:", length(feature_index)))

# 子矩阵
sub_data <- exprSet[feature_index, sample_index]
print(paste("子矩阵维度:", paste(dim(sub_data), collapse=" x ")))

# 计算距离矩阵
print("计算距离矩阵...")
if (distance == "pearson") {
  d <- as.dist(1 - cor(sub_data, method = "pearson"))
} else {
  d <- dist(t(sub_data), method = distance)
}
print(paste("距离矩阵 class:", class(d)))
print(paste("距离矩阵 size:", attr(d, "Size")))
print(paste("距离矩阵长度:", length(d)))

# 层次聚类
print("进行层次聚类...")
if (clusterAlg == "hc") {
  hc <- hclust(d, method = "average")
  print(paste("hc class:", class(hc)))
  print(paste("hc 标签数:", length(hc$labels)))
  print(paste("hc merge dim:", paste(dim(hc$merge), collapse=" x ")))
}

# cutree
print("cutree...")
for (k in 2:maxK) {
  print(paste("  k=", k))
  ct <- cutree(hc, k = k)
  print(paste("  cutree 结果长度:", length(ct)))
  print(paste("  cutree table:", paste(table(ct), collapse=",")))
}

print("单次聚类成功！")
''')

print("\n完成")
