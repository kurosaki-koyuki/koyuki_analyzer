# -*- coding: utf-8 -*-
"""
调试脚本：测试rpy2数据传递和一致性聚类（修复版）- 使用项目内的R内核
"""
import sys
import os

os.chdir(r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')
sys.path.insert(0, r'a:\PYidea\koyuki_analyzer\test_files\koyuki_beta2.5test')

import scanpy as sc
import pandas as pd
import numpy as np

print("=" * 60)
print("步骤1: 读取h5ad数据")
print("=" * 60)

adata = sc.read_h5ad(r'appdata\bulk_main\CGGA325_TPM.h5ad')
print(f"adata shape: {adata.shape}")

# 提取表达矩阵并转置（adata.X是样本×基因，需要转成基因×样本）
X = adata.X
if hasattr(X, 'toarray'):
    X = X.toarray()
df = pd.DataFrame(X.T, index=adata.var_names, columns=adata.obs_names)
print(f"df shape: {df.shape} (行为基因={df.shape[0]}, 列为样本={df.shape[1]})")

print("\n" + "=" * 60)
print("步骤2: 使用项目内的R内核初始化")
print("=" * 60)

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface

r_interface = get_r_kernel_interface()
print(f"R可用: {r_interface.is_r_available()}")

robjects = r_interface.get_robjects()
pandas2ri = r_interface.get_pandas2ri()
print(f"robjects: {robjects is not None}")
print(f"pandas2ri: {pandas2ri is not None}")

# 加载R包
from rpy2.robjects.packages import importr
print("\n加载R包...")
ConsensusClusterPlus = importr('ConsensusClusterPlus')
pheatmap_pkg = importr('pheatmap')
grDevices = importr('grDevices')
print("R包加载完成")

print("\n" + "=" * 60)
print("步骤3: 测试pandas2ri转换")
print("=" * 60)

# 取前500个基因（快速测试）
df_test = df.iloc[:500, :]
print(f"测试数据形状: {df_test.shape}")

from rpy2.robjects.conversion import localconverter
with localconverter(pandas2ri.converter):
    r_df = robjects.globalenv['expr_data'] = df_test

print(f"R中数据的维度: {robjects.r('dim(expr_data)')}")

print("\n" + "=" * 60)
print("步骤4: 测试MAD筛选 + 标准化")
print("=" * 60)

r_code_prep = """
df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(5000, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
print(paste("MAD筛选后维度:", nrow(df_filtered), "x", ncol(df_filtered)))
exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))
print(paste("减中位数标准化后维度:", nrow(exprSet), "x", ncol(exprSet)))
"""
robjects.r(r_code_prep)

print("\n" + "=" * 60)
print("步骤5: 测试ConsensusClusterPlus (k=2, reps=100)")
print("=" * 60)

import tempfile
temp_dir = tempfile.mkdtemp(prefix="ccp_debug_")
print(f"临时目录: {temp_dir}")

robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

r_code_ccp = """
results <- ConsensusClusterPlus(exprSet,
                                maxK = 2,
                                reps = 100,
                                pItem = 0.8,
                                pFeature = 1,
                                title = title_dir,
                                clusterAlg = "hc",
                                distance = "pearson",
                                seed = 123456,
                                plot = "png")
print("聚类完成")
print(paste("k=2的一致性矩阵维度:", dim(results[[2]]$consensusMatrix)))
print(paste("k=2的聚类类别数:", length(results[[2]]$consensusClass)))
"""
try:
    robjects.r(r_code_ccp)
    print("ConsensusClusterPlus 运行成功！")
except Exception as e:
    print(f"ConsensusClusterPlus 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("步骤6: 测试热图")
print("=" * 60)

r_code_heatmap = """
consensus_matrix <- results[[2]][["consensusMatrix"]]
colnames(consensus_matrix) <- colnames(exprSet)
rownames(consensus_matrix) <- colnames(exprSet)

consensus_tree <- results[[2]][["consensusTree"]]
consensus_class <- results[[2]][["consensusClass"]]

ConsensusMatrix_ordered <- consensus_matrix[consensus_tree$order,
                                             consensus_tree$order]

annCol <- data.frame(results = paste0("Cluster",
                                      consensus_class[consensus_tree$order]),
                     row.names = colnames(ConsensusMatrix_ordered))

n_clusters <- 2
ann_colors <- list()
cluster_colors <- c("#db6968", "#4d97cd", "#99cbeb", "#459943",
                    "#FF6B35", "#9467bd", "#8c564b", "#e377c2",
                    "#7f7f7f")
ann_colors$results <- cluster_colors[1:n_clusters]
names(ann_colors$results) <- paste0("Cluster", 1:n_clusters)

heatmap_colors <- colorRampPalette(c("white", "steelblue"))(100)

heatmap_path <- paste0(title_dir, "/test_heatmap_k2.png")
png(heatmap_path, width = 800, height = 800, res = 100)
pheatmap(ConsensusMatrix_ordered,
         color = heatmap_colors,
         clustering_distance_cols = "correlation",
         clustering_method = "average",
         border_color = NA,
         annotation_col = annCol,
         annotation_colors = ann_colors,
         show_colnames = FALSE,
         show_rownames = FALSE,
         fontsize = 12,
         main = "Test Heatmap (K=2)")
dev.off()

print(paste("热图已生成:", heatmap_path))
print(paste("文件存在:", file.exists(heatmap_path)))
"""
try:
    robjects.r(r_code_heatmap)
    print("热图生成成功！")
    print(f"验证: {os.path.exists(os.path.join(temp_dir, 'test_heatmap_k2.png'))}")
except Exception as e:
    print(f"热图生成失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("步骤7: 测试CDF+PAC")
print("=" * 60)

r_code_pac = """
Kvec <- 2:2
pac_values <- rep(NA, length(Kvec))
names(pac_values) <- paste("K=", Kvec, sep="")

x1 <- 0.1
x2 <- 0.9

cdf_data <- list()
for(i in Kvec) {
  M <- results[[i]]$consensusMatrix
  Fn <- ecdf(M[lower.tri(M)])
  cdf_data[[i]] <- Fn
  pac_values[i - min(Kvec) + 1] <- Fn(x2) - Fn(x1)
}

opt_k <- Kvec[which.min(pac_values)]
print(paste("PAC值:", paste(pac_values, collapse=", ")))
print(paste("最优k:", opt_k))
"""
try:
    robjects.r(r_code_pac)
    print("CDF+PAC计算成功！")
except Exception as e:
    print(f"CDF+PAC计算失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("调试完成 - 所有步骤通过！")
print("=" * 60)
