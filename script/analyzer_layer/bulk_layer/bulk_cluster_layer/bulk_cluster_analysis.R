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
# - seed: 随机种子（默认123456，由Python端传入）
# - analysis_mode: 分析模式，"traditional"（MAD前N基因）| "signature"（外部基因列表）
# - gene_list: signature 模式的基因列表（字符向量，可不存在）
# - mad_filter_in_list: signature 模式下是否在列表内再按 MAD 过滤
# - title_dir: 临时输出目录
# - final_k: 阶段三/阶段四选定的最终k值
# - output_mode: 阶段三输出模式（1=只热图, 2=热图+树+样本表, 3=热图+树+ICL）
# - heatmap_width: 热图宽度
# - heatmap_height: 热图高度
# - color_scheme: 颜色方案
# - title_font_size: 标题字体大小
# - legend_font_size: 图例字体大小
# - clustering_method: 聚类方法，默认"average"
# - fix_k_enable / fixed_k: 阶段二固定k（跳过PAC自动选k）
# - 阶段四：min_k, max_k, final_k, eval_ref_col, ref_labels, silhouette_enable,
#   gene_heatmap_enable, gene_heatmap_max, eval_plot_path, gene_heatmap_path,
#   eval_text_path, color_scheme, heatmap_width, heatmap_height,
#   title_font_size, legend_font_size, clustering_method


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

# === 模式与随机种子参数（契约 §5.1） ===
if (exists("analysis_mode")) {
  analysis_mode_val <- as.character(analysis_mode)[1]
} else {
  analysis_mode_val <- "traditional"
}
if (is.na(analysis_mode_val) || analysis_mode_val == "") {
  analysis_mode_val <- "traditional"
}
if (exists("mad_filter_in_list")) {
  mad_filter_in_list_val <- as.logical(as.integer(mad_filter_in_list)[1])
} else {
  mad_filter_in_list_val <- FALSE
}
if (is.na(mad_filter_in_list_val)) mad_filter_in_list_val <- FALSE
if (exists("seed")) {
  seed_val <- as.integer(seed)[1]
} else {
  seed_val <- 123456L
}
if (is.na(seed_val)) seed_val <- 123456L
set.seed(seed_val)                       # ★ 修 P1：必须放在 ccRun 之前
# ★ ASCII 标记行（LC_CTYPE=C 下 rpy2 会毁掉中文字面量，中文一律由 Python 侧生成）
cat(sprintf("[VK] SEED|%d\n", seed_val))

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

# === 数据预处理 / 基因选择（按模式分流，契约 §5.1） ===
# ★ 必须在 mad() 之前分流，否则 signature 列表会被静默二次筛选
if (identical(analysis_mode_val, "signature")) {
  if (!exists("gene_list") || length(gene_list) == 0) stop("VKERR|NO_GENE_LIST")
  gl <- as.character(gene_list)
  gl <- gl[gl %in% rownames(df)]                       # 保序取交集
  if (length(gl) < 10) stop(sprintf("VKERR|TOO_FEW_GENES|%d", length(gl)))
  if (isTRUE(mad_filter_in_list_val)) {
    mads_sub <- apply(df[gl, , drop = FALSE], 1, mad)
    n_g <- min(mad_val, length(gl))
    gl <- gl[rev(order(mads_sub))[1:n_g]]
    cat(sprintf("[VK] MADFILTER|%d|%d\n", length(mads_sub), length(gl)))
  }
  df <- df[gl, , drop = FALSE]
  cat(sprintf("[VK] PANEL|mode=signature|genes=%d\n", nrow(df)))
} else {
  # 计算每个基因的中位数绝对偏差（MAD）
  mads <- apply(df, 1, mad)
  # 选择MAD最高的前N个基因（N由mad_threshold控制）
  n_genes <- min(mad_val, nrow(df))
  df <- df[rev(order(mads))[1:n_genes], , drop = FALSE]
  cat(sprintf("[VK] PANEL|mode=traditional|genes=%d\n", nrow(df)))
}
ccp_mode <<- analysis_mode_val          # 供 STAGE4 文本回显（数据，非字面量，安全）

# 减中位数标准化
exprSet <- sweep(df, 1, apply(df, 1, median, na.rm = TRUE))   # 中心化保留
ccp_gene_panel <<- rownames(exprSet)                          # 新增：供 STAGE4 用

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

# === 固定k参数（契约 §5.2） ===
if (exists("fix_k_enable")) {
  fix_k_enable_val <- as.logical(as.integer(fix_k_enable)[1])
} else {
  fix_k_enable_val <- FALSE
}
if (is.na(fix_k_enable_val)) fix_k_enable_val <- FALSE
if (exists("fixed_k")) {
  fixed_k_val <- as.integer(fixed_k)[1]
} else {
  fixed_k_val <- NA_integer_
}

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

# === 固定k模式（契约 §5.2） ===
pac_best_k <- opt_k
if (isTRUE(fix_k_enable_val)) {
  if (is.na(fixed_k_val) || !(fixed_k_val %in% Kvec))
    stop(sprintf("VKERR|FIXK_RANGE|%s|%d|%d", fixed_k_val, min_k_val, max_k_val))
  opt_k <- fixed_k_val
  cat(sprintf("[VK] FIXK|%d|pacbest=%d\n", opt_k, pac_best_k))
}

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
if (isTRUE(fix_k_enable_val)) {
  text(opt_k, min(pac_values) + diff(range(pac_values)) * 0.1,
       labels = paste("Fixed K =", opt_k), col = "red", cex = 0.8, pos = 4)
} else {
  text(opt_k, min(pac_values) + diff(range(pac_values)) * 0.1,
       labels = paste("Optimal K =", opt_k), col = "red", cex = 0.8, pos = 4)
}

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


# ========================================
# 阶段四：分型评估 + signature 表达热图
# ========================================
# --- STAGE4_BODY_START ---

# === 参数获取 ===
min_k_val <- as.integer(min_k)[1]
max_k_val <- as.integer(max_k)[1]
final_k_val <- as.integer(final_k)[1]
silhouette_enable_val <- as.logical(as.integer(silhouette_enable)[1])
gene_heatmap_enable_val <- as.logical(as.integer(gene_heatmap_enable)[1])
gene_heatmap_max_val <- as.integer(gene_heatmap_max)[1]
eval_plot_path_val <- as.character(eval_plot_path)[1]
gene_heatmap_path_val <- as.character(gene_heatmap_path)[1]
eval_text_path_val <- as.character(eval_text_path)[1]
color_scheme_val <- as.character(color_scheme)[1]
heatmap_width_val <- as.numeric(heatmap_width)[1]
heatmap_height_val <- as.numeric(heatmap_height)[1]
title_font_size_val <- as.integer(title_font_size)[1]
legend_font_size_val <- as.integer(legend_font_size)[1]
clustering_method_val <- as.character(clustering_method)[1]

# 参考分组列名（仅用于文本回显，契约 §5.4；不参与"是否做 ARI/NMI"的判断）
if (exists("eval_ref_col")) {
  eval_ref_col_val <- as.character(eval_ref_col)[1]
} else {
  eval_ref_col_val <- "不使用"
}
if (is.na(eval_ref_col_val) || eval_ref_col_val == "") {
  eval_ref_col_val <- "不使用"
}

if (exists("analysis_mode")) {
  analysis_mode_val <- as.character(analysis_mode)[1]
} else {
  analysis_mode_val <- "traditional"
}
if (is.na(analysis_mode_val) || analysis_mode_val == "") {
  analysis_mode_val <- "traditional"
}

if (is.na(silhouette_enable_val)) silhouette_enable_val <- FALSE
if (is.na(gene_heatmap_enable_val)) gene_heatmap_enable_val <- FALSE
if (is.na(gene_heatmap_max_val) || gene_heatmap_max_val < 1) gene_heatmap_max_val <- 200L

# === 参数验证 ===
if (!exists("ccp_results") || !exists("ccp_exprSet")) {
  stop("VKERR|NEED_STAGE1")
}

if (is.na(final_k_val) || final_k_val < 2) {
  stop("VKERR|FINAL_K_MIN")
}

if (is.na(min_k_val)) min_k_val <- 2L
if (is.na(max_k_val)) max_k_val <- 9L
if (final_k_val < min_k_val || final_k_val > max_k_val) {
  stop(sprintf("VKERR|FINAL_K_RANGE|%s|%d|%d", final_k_val, min_k_val, max_k_val))
}

if (is.null(dim(ccp_exprSet))) {
  stop("VKERR|DIM_ERROR")
}
expr_mat <- as.matrix(ccp_exprSet)

# === ARI / NMI 本地实现（契约 §5.3 冻结，不依赖 fpc/mclust） ===
.ari <- function(a, b) {
  tab <- table(as.character(a), as.character(b)); n <- sum(tab)
  if (n == 0 || nrow(tab) < 2 || ncol(tab) < 2) return(NA_real_)
  c2 <- function(x) x * (x - 1) / 2
  sij <- sum(c2(tab)); si <- sum(c2(rowSums(tab))); sj <- sum(c2(colSums(tab)))
  exp_i <- si * sj / c2(n); mx <- (si + sj) / 2
  if (isTRUE(all.equal(mx, exp_i))) return(1)
  (sij - exp_i) / (mx - exp_i)
}
.nmi <- function(a, b) {
  tab <- table(as.character(a), as.character(b)); n <- sum(tab)
  if (n == 0 || nrow(tab) < 2 || ncol(tab) < 2) return(NA_real_)
  p <- tab / n; pi <- rowSums(p); pj <- colSums(p)
  H <- function(v) { v <- v[v > 0]; -sum(v * log(v)) }
  nz <- p > 0
  I <- sum(p[nz] * log(p[nz] / (outer(pi, pj)[nz])))
  den <- sqrt(H(pi) * H(pj))
  if (den == 0) return(0)
  I / den
}
# 注：数字格式化（NA→NA / 科学计数）已移到 Python 侧（_fmt_eval_num），与文本生成同处

# === 参考分组校验（契约 §5.3） ===
ref_used <- FALSE
ref_chr <- character(0)
if (exists("ref_labels") && length(ref_labels) > 0) {
  ref_chr <- as.character(ref_labels)
  if (length(ref_chr) != ncol(expr_mat)) {
    stop(sprintf("VKERR|REF_LABEL_LEN|%d|%d", length(ref_chr), ncol(expr_mat)))
  }
  ref_used <- TRUE
}

Kvec <- min_k_val:max_k_val
n_k <- length(Kvec)

# === PAC 来源（契约裁决①）===
# 阶段二不跑也必须能出 PAC：自己按 STAGE2 相同公式算；
# 仅当 pac_values_global 存在且 k 范围与本次完全一致时可优先采用。
pac_from_stage2 <- FALSE
if (exists("pac_values_global")) {
  pac_global <- as.numeric(pac_values_global)
  if (length(pac_global) == n_k && identical(names(pac_values_global),
                                             paste("K=", Kvec, sep = ""))) {
    pac_vec <- pac_global
    pac_from_stage2 <- TRUE
  }
}
if (!pac_from_stage2) {
  pac_vec <- rep(NA_real_, n_k)
  for (idx in seq_len(n_k)) {
    M <- ccp_results[[Kvec[idx]]]$consensusMatrix
    Fn <- ecdf(M[lower.tri(M)])
    pac_vec[idx] <- Fn(0.9) - Fn(0.1)
  }
}

sil_vec <- rep(NA_real_, n_k)
size_vec <- rep(NA_integer_, n_k)
ari_vec <- rep(NA_real_, n_k)
nmi_vec <- rep(NA_real_, n_k)
pval_vec <- rep(NA_real_, n_k)

# === 逐 k 评估 ===
for (idx in seq_len(n_k)) {
  k <- Kvec[idx]
  M <- ccp_results[[k]]$consensusMatrix
  dimnames(M) <- list(colnames(expr_mat), colnames(expr_mat))

  # 契约裁决⑥：标签唯一来源 = consensusClass（与 STAGE3/export_csv/save_consensus_to_adata 同源）
  cl <- ccp_results[[k]]$consensusClass[colnames(expr_mat)]
  if (is.null(cl) || length(cl) != ncol(expr_mat) || any(is.na(cl))) {
    cl <- cutree(hclust(as.dist(1 - M), method = "average"), k)
    names(cl) <- colnames(expr_mat)
  }

  # 轮廓系数（契约 §5.3 冻结实现）
  sil_mean <- NA_real_; min_size <- NA_integer_
  if (isTRUE(silhouette_enable_val)) {
    M  <- ccp_results[[k]]$consensusMatrix
    dimnames(M) <- list(colnames(ccp_exprSet), colnames(ccp_exprSet))
    cl <- ccp_results[[k]]$consensusClass[colnames(ccp_exprSet)]
    min_size <- min(table(cl))
    sil_mean <- tryCatch({
      s <- cluster::silhouette(as.integer(cl), as.dist(1 - M))
      mean(s[, 3], na.rm = TRUE)
    }, error = function(e) NA_real_)
  }
  sil_vec[idx] <- sil_mean
  size_vec[idx] <- min_size
  # silhouette 关闭时 min_size 仍要算
  if (is.na(min_size)) {
    cl2 <- ccp_results[[k]]$consensusClass[colnames(expr_mat)]
    if (is.null(cl2) || length(cl2) != ncol(expr_mat) || any(is.na(cl2))) {
      cl2 <- cutree(hclust(as.dist(1 - M), method = "average"), k)
    }
    size_vec[idx] <- min(table(cl2))
  }

  if (ref_used) {
    ari_vec[idx] <- .ari(ref_chr, cl)
    nmi_vec[idx] <- .nmi(ref_chr, cl)
    tab_k <- table(ref_chr, cl)
    pval_vec[idx] <- tryCatch(
      suppressWarnings(chisq.test(tab_k)$p.value),
      error = function(e) NA_real_)
  }
}

# === 最终 k 的交叉表 ===
final_cluster_labels <- ccp_results[[final_k_val]]$consensusClass[colnames(expr_mat)]
if (is.null(final_cluster_labels) || length(final_cluster_labels) != ncol(expr_mat) ||
    any(is.na(final_cluster_labels))) {
  Mf <- ccp_results[[final_k_val]]$consensusMatrix
  dimnames(Mf) <- list(colnames(expr_mat), colnames(expr_mat))
  final_cluster_labels <- cutree(hclust(as.dist(1 - Mf), method = "average"), final_k_val)
  names(final_cluster_labels) <- colnames(expr_mat)
}

# === 产物3 的数据（文本由 Python 生成：LC_CTYPE=C 下 R 的中文字面量会被毁） ===
final_ari <- NA_real_; final_nmi <- NA_real_; final_p <- NA_real_
eval_crosstab <<- NULL
if (ref_used) {
  final_tab <- table(ref_group = ref_chr,
                     consensus_cluster = paste0("Cluster", final_cluster_labels))
  final_ari <- .ari(ref_chr, final_cluster_labels)
  final_nmi <- .nmi(ref_chr, final_cluster_labels)
  final_p <- tryCatch(suppressWarnings(chisq.test(final_tab)$p.value),
                      error = function(e) NA_real_)
  eval_crosstab <<- final_tab
}

# === 全局回写（契约 §5.3） ===
eval_k_table <<- data.frame(
  K = Kvec,
  PAC = as.numeric(pac_vec),
  silhouette = sil_vec,
  minClusterSize = size_vec,
  ARI = ari_vec,
  NMI = nmi_vec,
  chisq_p = pval_vec,
  stringsAsFactors = FALSE
)
eval_final_k <<- final_k_val
eval_ref_used <<- ref_used
eval_pac_from_stage2 <<- pac_from_stage2
eval_ref_col_value <<- eval_ref_col_val
eval_final_ari <<- final_ari
eval_final_nmi <<- final_nmi
eval_final_p <<- final_p
cat(sprintf("[VK] EVAL|k=%d|pac_src=%s|silhouette=%s|heatmap=%s|ref=%s\n",
            final_k_val,
            if (isTRUE(pac_from_stage2)) "stage2" else "local",
            if (isTRUE(silhouette_enable_val)) "on" else "off",
            if (isTRUE(gene_heatmap_enable_val)) "on" else "off",
            if (isTRUE(ref_used)) "on" else "off"))

# === 产物1：双联评估图 ===
eval_dir <- dirname(eval_plot_path_val)
if (!is.na(eval_dir) && eval_dir != "" && eval_dir != "." && !dir.exists(eval_dir)) {
  dir.create(eval_dir, recursive = TRUE, showWarnings = FALSE)
}
png(eval_plot_path_val, width = 12 * 100, height = 5 * 100, res = 100)
par(mfrow = c(1, 2), mar = c(4, 4, 3, 1))

# 左：各 k 平均轮廓系数
sil_plot <- sil_vec
if (all(is.na(sil_plot))) sil_plot <- rep(0, n_k)
plot(Kvec, sil_plot, type = "b", pch = 19, col = "steelblue", lwd = 2,
     xlab = "Number of Clusters (K)", ylab = "Mean Silhouette Width",
     main = "Mean Silhouette by K")
if (!all(is.na(sil_vec))) {
  abline(v = final_k_val, col = "red", lty = 2, lwd = 1.5)
  text(final_k_val, max(sil_plot, na.rm = TRUE),
       labels = paste("Final K =", final_k_val), col = "red", cex = 0.8, pos = 4)
}

# 右：ARI 柱状图 或 最终 k 的簇大小
if (ref_used) {
  ari_plot <- ari_vec
  ari_plot[is.na(ari_plot)] <- 0
  bp <- barplot(ari_plot, names.arg = Kvec, col = "steelblue",
                xlab = "Number of Clusters (K)", ylab = "ARI",
                main = "ARI vs Reference Groups", ylim = c(0, max(1, max(ari_plot) * 1.2)))
  abline(h = 0, col = "gray40")
  abline(v = bp[which(Kvec == final_k_val)], col = "red", lty = 2, lwd = 1.5)
  text(bp[which(Kvec == final_k_val)], max(1, max(ari_plot) * 1.2) * 0.95,
       labels = paste("Final K =", final_k_val), col = "red", cex = 0.8, pos = 4)
} else {
  barplot(table(paste0("Cluster", final_cluster_labels)), col = "steelblue",
          xlab = "Cluster", ylab = "Sample Count",
          main = paste("Cluster sizes (K =", final_k_val, ")"))
}
dev.off()

# === 产物2：基因×样本表达热图 ===
gene_heatmap_done <- FALSE
if (isTRUE(gene_heatmap_enable_val) &&
    !is.na(gene_heatmap_path_val) && gene_heatmap_path_val != "" &&
    gene_heatmap_path_val != "NA") {
  ord <- ccp_results[[final_k_val]]$consensusTree$order
  if (length(ord) != ncol(expr_mat)) ord <- seq_len(ncol(expr_mat))
  sub <- expr_mat[, ord, drop = FALSE]
  cl <- final_cluster_labels[ord]
  n_genes_total <- nrow(sub)
  title_suffix <- ""
  if (n_genes_total > gene_heatmap_max_val) {
    # 按"各分群均值极差"排序取前 N
    grp_mat <- sapply(split(seq_len(ncol(sub)), cl), function(ii) {
      rowMeans(sub[, ii, drop = FALSE])
    })
    if (is.null(dim(grp_mat))) {
      grp_mat <- matrix(grp_mat, ncol = 1)
    }
    rng <- apply(grp_mat, 1, function(v) diff(range(v)))
    keep <- order(rng, decreasing = TRUE)[seq_len(gene_heatmap_max_val)]
    sub <- sub[keep, , drop = FALSE]
    title_suffix <- paste0(" (top ", gene_heatmap_max_val, " of ", n_genes_total, ")")
  }
  annotation_col <- data.frame(Cluster = paste0("Cluster", cl))
  rownames(annotation_col) <- colnames(sub)

  heatmap_colors <- if (identical(color_scheme_val, "red")) {
    colorRampPalette(c("white", "#db6968"))(100)
  } else if (identical(color_scheme_val, "green")) {
    colorRampPalette(c("white", "#459943"))(100)
  } else {
    colorRampPalette(c("white", "steelblue"))(100)
  }

  heatmap_dir <- dirname(gene_heatmap_path_val)
  if (!is.na(heatmap_dir) && heatmap_dir != "" && heatmap_dir != "." &&
      !dir.exists(heatmap_dir)) {
    dir.create(heatmap_dir, recursive = TRUE, showWarnings = FALSE)
  }
  png(gene_heatmap_path_val, width = heatmap_width_val * 100,
      height = heatmap_height_val * 100, res = 100)
  pheatmap::pheatmap(sub,
                     color = heatmap_colors,
                     cluster_cols = FALSE,
                     cluster_rows = TRUE,
                     annotation_col = annotation_col,
                     show_colnames = FALSE,
                     show_rownames = nrow(sub) <= 60,
                     fontsize_row = 6,
                     fontsize = legend_font_size_val,
                     main = paste0("Signature Expression Heatmap (K = ", final_k_val, ")",
                                   title_suffix))
  dev.off()
  gene_heatmap_done <- TRUE
}

# === 产物3 已改为“只回传数据”，文本由 Python 生成 ===
# ★ 原因：rpy2 嵌入会话 LC_CTYPE=C，R 代码里的非 ASCII 字面量在解析期就被转义成
#   "<U+57FA>" 这类文本（实测 nchar("=== 基因面板 ===") == 40），改任何写文件写法都救不回来。
#   故 R 端只用 ASCII，用户可见中文一律在 Python 侧拼装（eval_k_table / eval_crosstab 已回写）。
cat("[VK] DONE|stage4\n")

# --- STAGE4_BODY_END ---
