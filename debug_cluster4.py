# -*- coding: utf-8 -*-
"""
调试脚本4：完整测试 ConsensusClusterPlus + 热图
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

# 加载R包
ConsensusClusterPlus = importr('ConsensusClusterPlus')
pheatmap_pkg = importr('pheatmap')
grDevices = importr('grDevices')
print("R包加载完成")

# 测试：500个基因，k=2，reps=100
df_test = df.iloc[:500, :]
print(f"\n测试数据: {df_test.shape}")

with localconverter(pandas2ri.converter):
    robjects.globalenv['expr_data'] = df_test

temp_dir = tempfile.mkdtemp(prefix="ccp_test_")
print(f"临时目录: {temp_dir}")

robjects.globalenv['title_dir'] = robjects.StrVector([temp_dir.replace('\\', '/')])

# 预处理 + 聚类
r_code = """
df <- as.matrix(expr_data)
mads <- apply(df, 1, mad)
n_genes <- min(5000, nrow(df))
df_filtered <- df[rev(order(mads))[1:n_genes], ]
exprSet <- sweep(df_filtered, 1, apply(df_filtered, 1, median, na.rm = TRUE))
print(paste("exprSet dim:", dim(exprSet)))
print(paste("exprSet class:", class(exprSet)))

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
print(paste("k=2一致性矩阵维度:", dim(results[[2]]$consensusMatrix)))
"""

print("\n运行ConsensusClusterPlus...")
try:
    robjects.r(r_code)
    print("成功！")
except Exception as e:
    print(f"失败: {e}")
    import traceback
    traceback.print_exc()

# 测试热图
r_code_hm = """
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

print(paste("热图生成:", heatmap_path))
print(paste("文件存在:", file.exists(heatmap_path)))
"""

print("\n生成热图...")
try:
    robjects.r(r_code_hm)
    print("热图成功！")
    # 验证
    hm_path = os.path.join(temp_dir, "test_heatmap_k2.png")
    print(f"Python验证文件存在: {os.path.exists(hm_path)}")
    if os.path.exists(hm_path):
        print(f"文件大小: {os.path.getsize(hm_path)} bytes")
except Exception as e:
    print(f"热图失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
