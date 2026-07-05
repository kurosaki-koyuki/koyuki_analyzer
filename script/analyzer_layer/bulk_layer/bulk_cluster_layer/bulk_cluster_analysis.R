# bulk 一致性分析 R脚本
# 此文件包含所有R代码，用于通过rpy2调用R进行一致性聚类分析
#
# 使用方式：
# Python端通过rpy2将参数设置到全局环境，然后提取标记行内的代码执行
# 参数直接从全局环境获取，不需要显式传递
# R包必须通过Python端的importr()预加载，禁止在脚本中使用library()
#
# 三阶段架构：
# 阶段一：STAGE1 - 聚类计算（MAD筛选+标准化+ConsensusClusterPlus）
# 阶段二：STAGE2 - CDF曲线+PAC曲线（用于选k）
# 阶段三：STAGE3 - 最终热图+可选输出（聚类树、样本表、ICL）
#
# 参数列表（从全局环境获取）：
# - expr_data: 表达矩阵数据框（行为基因，列为样本）
# - mad_threshold: MAD阈值，默认5000
# - reps: 重抽样次数，默认1000
# - cluster_alg: 聚类算法，默认"hc"
# - distance: 距离度量，默认"pearson"
# - p_item: 样本抽样比例，默认0.8
# - p_feature: 特征抽样比例，默认1
# - min_k: 最小k值，默认2
# - max_k: 最大k值，默认9
# - plot_format: plot输出格式，默认"png"
# - seed: 随机种子，固定为123456（不可调）
# - title_dir: 临时输出目录
# - final_k: 阶段三选定的最终k值
# - output_mode: 阶段三输出模式（1=只热图, 2=热图+树+样本表, 3=热图+树+ICL）
# - heatmap_width: 热图宽度
# - heatmap_height: 热图高度
# - color_scheme: 颜色方案
# - title_font_size: 标题字体大小
# - legend_font_size: 图例字体大小
# - clustering_method: 聚类方法，默认"average"


# ========================================
# 阶段一：聚类计算
# ========================================
# --- STAGE1_BODY_START ---

# === 参数获取 ===
df <- as.matrix(expr_data)
mad_val <- as.integer(mad_threshold)[1]
reps_val <- as.integer(reps)[1]
cluster_alg_val <- as.character(cluster_alg)[1]
distance_val <- as.character(distance)[1]
p_item_val <- as.numeric(p_item)[1]
p_feature_val <- as.numeric(p_feature)[1]
min_k_val <- as.integer(min_k)[1]
max_k_val <- as.integer(max_k)[1]
plot_format_val <- as.character(plot_format)[1]
title_dir_val <- as.character(title_dir)[1]

# === 参数验证 ===
if (!exists('df')) {
  stop("表达矩阵 expr_data 不存在")
}

if (is.na(max_k_val) || max_k_val < 2) {
  stop("max_k 必须大于等于2")
}

if (min_k_val < 2) {
  min_k_val <- 2
}

if (min_k_val > max_k_val) {
  stop("min_k 不能大于 max_k")
}

# === 数据预处理 ===
# 计算每个基因的中位数绝对偏差（MAD）
mads <- apply(df, 1, mad)

# 选择MAD最高的前N个基因（N由mad_threshold控制）
n_genes <- min(mad_val, nrow(df))
df <- df[rev(order(mads))[1:n_genes], ]

# 减中位数标准化
exprSet <- sweep(df, 1, apply(df, 1, median, na.rm = TRUE))

# === 一致性聚类 ===
# 创建临时输出目录
if (!dir.exists(title_dir_val)) {
  dir.create(title_dir_val, recursive = TRUE)
}

# 使用内部函数 ccRun 计算聚类结果，避免 ConsensusClusterPlus 主函数中
# maxK=2 时 clusterTrackingPlot 的矩阵退化 bug
ml <- ConsensusClusterPlus:::ccRun(d = exprSet,
                                   maxK = max_k_val,
                                   repCount = reps_val,
                                   diss = FALSE,
                                   pItem = p_item_val,
                                   pFeature = p_feature_val,
                                   innerLinkage = "average",
                                   clusterAlg = cluster_alg_val,
                                   distance = distance_val,
                                   verbose = FALSE,
                                   corUse = "everything")

# 手动构建结果列表（与 ConsensusClusterPlus 返回格式一致）
results <- list()
results[[1]] <- NA  # 占位，与原包格式一致
for (tk in min_k_val:max_k_val) {
  fm <- ml[[tk]]
  hc <- hclust(as.dist(1 - fm), method = "average")
  hc$labels <- colnames(exprSet)
  ct <- cutree(hc, tk)
  names(ct) <- colnames(exprSet)
  results[[tk]] <- list(
    consensusMatrix = fm,
    consensusTree = hc,
    consensusClass = ct,
    ml = ml[[tk]]
  )
}

# 将结果保存到全局环境，供后续阶段使用
ccp_results <<- results
ccp_exprSet <<- exprSet

# --- STAGE1_BODY_END ---


# ========================================
# 阶段二：CDF曲线 + PAC曲线
# ========================================
# --- STAGE2_BODY_START ---

# === 参数获取 ===
min_k_val <- as.integer(min_k)[1]
max_k_val <- as.integer(max_k)[1]
output_path_val <- as.character(output_path)[1]
plot_width_val <- as.numeric(plot_width)[1]
plot_height_val <- as.numeric(plot_height)[1]

# === 参数验证 ===
if (!exists('ccp_results')) {
  stop("请先运行阶段一聚类计算")
}

if (is.na(output_path_val) || output_path_val == "") {
  stop("输出路径 output_path 不能为空")
}

# === CDF曲线计算 ===
Kvec <- min_k_val:max_k_val
pac_values <- rep(NA, length(Kvec))
names(pac_values) <- paste("K=", Kvec, sep = "")

# PAC阈值定义中间子区间
x1 <- 0.1
x2 <- 0.9

# 计算每个k值的CDF和PAC
cdf_data <- list()
for(i in Kvec) {
  M <- ccp_results[[i]]$consensusMatrix
  Fn <- ecdf(M[lower.tri(M)])
  cdf_data[[i]] <- Fn
  pac_values[i - min_k_val + 1] <- Fn(x2) - Fn(x1)
}

# 最优k值
opt_k <- Kvec[which.min(pac_values)]

# 将最优k保存到全局环境
optimal_k <<- opt_k
pac_values_global <<- pac_values

# === 设置文件输出 ===
if(output_path_val != "" && !is.na(output_path_val) && output_path_val != "NA") {
  if(grepl("\\.png$", output_path_val, ignore.case = TRUE)) {
    png(output_path_val, width = plot_width_val * 100, height = plot_height_val * 100, res = 100)
  } else if(grepl("\\.pdf$", output_path_val, ignore.case = TRUE)) {
    pdf(output_path_val, width = plot_width_val, height = plot_height_val)
  } else if(grepl("\\.svg$", output_path_val, ignore.case = TRUE)) {
    svg(output_path_val, width = plot_width_val, height = plot_height_val)
  } else {
    png(output_path_val, width = plot_width_val * 100, height = plot_height_val * 100, res = 100)
  }
}

# === 绘制CDF+PAC组合图 ===
par(mfrow = c(1, 2), mar = c(4, 4, 3, 1))

# CDF曲线
cols <- rainbow(length(Kvec))
for(i in seq_along(Kvec)) {
  k <- Kvec[i]
  Fn <- cdf_data[[k]]
  if(i == 1) {
    plot(Fn, main = "CDF Plot", xlab = "Consensus Values", ylab = "Cumulative Distribution", col = cols[i], lwd = 2)
  } else {
    plot(Fn, main = "CDF Plot", xlab = "Consensus Values", ylab = "Cumulative Distribution", col = cols[i], lwd = 2, add = TRUE)
  }
}
legend("bottomright", legend = paste("K =", Kvec), col = cols, lwd = 2, cex = 0.6, bty = "n")

# PAC曲线
plot(Kvec, pac_values, type = "b", pch = 19, col = "steelblue",
     main = "PAC Plot", xlab = "Number of Clusters (K)", ylab = "PAC Value",
     lwd = 2)
abline(v = opt_k, col = "red", lty = 2, lwd = 1.5)
text(opt_k, min(pac_values) + diff(range(pac_values)) * 0.1,
     labels = paste("Optimal K =", opt_k), col = "red", cex = 0.8, pos = 4)

# === 关闭设备 ===
if(output_path_val != "" && !is.na(output_path_val) && output_path_val != "NA") {
  dev.off()
}

# --- STAGE2_BODY_END ---


# ========================================
# 阶段三：最终热图 + 可选输出
# ========================================
# --- STAGE3_BODY_START ---

# === 参数获取 ===
final_k_val <- as.integer(final_k)[1]
output_mode_val <- as.integer(output_mode)[1]
output_path_val <- as.character(output_path)[1]
heatmap_width_val <- as.numeric(heatmap_width)[1]
heatmap_height_val <- as.numeric(heatmap_height)[1]
color_scheme_val <- as.character(color_scheme)[1]
title_font_size_val <- as.integer(title_font_size)[1]
legend_font_size_val <- as.integer(legend_font_size)[1]
clustering_method_val <- as.character(clustering_method)[1]

# === 参数验证 ===
if (!exists('ccp_results')) {
  stop("请先运行阶段一聚类计算")
}

if (is.na(final_k_val) || final_k_val < 2) {
  stop("final_k 必须大于等于2")
}

if (is.na(output_path_val) || output_path_val == "") {
  stop("输出路径 output_path 不能为空")
}

# === 准备数据 ===
# 获取选定k值的一致性矩阵
consensus_matrix <- ccp_results[[final_k_val]][["consensusMatrix"]]
colnames(consensus_matrix) <- colnames(ccp_exprSet)
rownames(consensus_matrix) <- colnames(ccp_exprSet)

# 按聚类树排序
consensus_tree <- ccp_results[[final_k_val]][["consensusTree"]]
consensus_class <- ccp_results[[final_k_val]][["consensusClass"]]

ConsensusMatrix_ordered <- consensus_matrix[consensus_tree$order,
                                             consensus_tree$order]

# 创建注释列数据框
annCol <- data.frame(results = paste0("Cluster",
                                      consensus_class[consensus_tree$order]),
                     row.names = colnames(ConsensusMatrix_ordered))

# === 设置颜色方案 ===
n_clusters <- final_k_val
ann_colors <- list()
cluster_colors <- c("#db6968", "#4d97cd", "#99cbeb", "#459943",
                    "#FF6B35", "#9467bd", "#8c564b", "#e377c2",
                    "#7f7f7f")
ann_colors$results <- cluster_colors[1:n_clusters]
names(ann_colors$results) <- paste0("Cluster", 1:n_clusters)

# 热图颜色
if(color_scheme_val == "blue") {
  heatmap_colors <- colorRampPalette(c("white", "steelblue"))(100)
} else if(color_scheme_val == "red") {
  heatmap_colors <- colorRampPalette(c("white", "#db6968"))(100)
} else if(color_scheme_val == "green") {
  heatmap_colors <- colorRampPalette(c("white", "#459943"))(100)
} else {
  heatmap_colors <- colorRampPalette(c("white", "steelblue"))(100)
}

# === 设置文件输出 ===
if(output_path_val != "" && !is.na(output_path_val) && output_path_val != "NA") {
  if(grepl("\\.png$", output_path_val, ignore.case = TRUE)) {
    png(output_path_val, width = heatmap_width_val * 100, height = heatmap_height_val * 100, res = 100)
  } else if(grepl("\\.pdf$", output_path_val, ignore.case = TRUE)) {
    pdf(output_path_val, width = heatmap_width_val, height = heatmap_height_val)
  } else if(grepl("\\.svg$", output_path_val, ignore.case = TRUE)) {
    svg(output_path_val, width = heatmap_width_val, height = heatmap_height_val)
  } else {
    png(output_path_val, width = heatmap_width_val * 100, height = heatmap_height_val * 100, res = 100)
  }
}

# === 绘制热图 ===
# 设置布局：热图为主，可选输出聚类树和ICL
if(output_mode_val == 1) {
  # 模式1：只出热图
  pheatmap(ConsensusMatrix_ordered,
           color = heatmap_colors,
           clustering_distance_cols = "correlation",
           clustering_method = clustering_method_val,
           border_color = NA,
           annotation_col = annCol,
           annotation_colors = ann_colors,
           show_colnames = FALSE,
           show_rownames = FALSE,
           fontsize = legend_font_size_val,
           main = paste("Consensus Heatmap (K =", final_k_val, ")"))

} else if(output_mode_val == 2) {
  # 模式2：热图+聚类树+样本表
  # 设置布局为两行：上面聚类树，下面热图
  layout(matrix(c(1, 2), nrow = 2), heights = c(1, 3))

  # 聚类树
  par(mar = c(0, 4, 2, 1))
  plot(consensus_tree, main = paste("Consensus Tree (K =", final_k_val, ")"),
       xlab = "", sub = "", ylab = "", cex = 0.6)

  # 热图
  par(mar = c(2, 4, 0, 1))
  pheatmap(ConsensusMatrix_ordered,
           color = heatmap_colors,
           clustering_distance_cols = "correlation",
           clustering_method = clustering_method_val,
           border_color = NA,
           annotation_col = annCol,
           annotation_colors = ann_colors,
           show_colnames = FALSE,
           show_rownames = FALSE,
           fontsize = legend_font_size_val,
           main = "")

  # 样本归属表保存到全局环境
  sample_class_df <- data.frame(
    Sample = names(consensus_class),
    Cluster = paste0("Cluster", consensus_class),
    stringsAsFactors = FALSE
  )
  sample_class_global <<- sample_class_df

} else if(output_mode_val == 3) {
  # 模式3：热图+聚类树+ICL
  # 计算ICL
  icl <- calcICL(ccp_results, plot = "png")

  # 设置布局为两行：上面聚类树，下面热图
  layout(matrix(c(1, 2), nrow = 2), heights = c(1, 3))

  # 聚类树
  par(mar = c(0, 4, 2, 1))
  plot(consensus_tree, main = paste("Consensus Tree (K =", final_k_val, ")"),
       xlab = "", sub = "", ylab = "", cex = 0.6)

  # 热图
  par(mar = c(2, 4, 0, 1))
  pheatmap(ConsensusMatrix_ordered,
           color = heatmap_colors,
           clustering_distance_cols = "correlation",
           clustering_method = clustering_method_val,
           border_color = NA,
           annotation_col = annCol,
           annotation_colors = ann_colors,
           show_colnames = FALSE,
           show_rownames = FALSE,
           fontsize = legend_font_size_val,
           main = "")

  # ICL保存到全局环境
  icl_cluster_global <<- icl[["clusterConsensus"]]
  icl_item_global <<- icl[["itemConsensus"]]
}

# === 保存最终k值到全局环境 ===
final_cluster_k <<- final_k_val

# === 关闭设备 ===
if(output_path_val != "" && !is.na(output_path_val) && output_path_val != "NA") {
  dev.off()
}

# --- STAGE3_BODY_END ---
