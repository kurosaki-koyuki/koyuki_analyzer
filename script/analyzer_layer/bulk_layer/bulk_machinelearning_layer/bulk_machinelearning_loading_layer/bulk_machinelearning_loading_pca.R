# -*- coding: utf-8 -*-
# ============================================================
# bulk 机器学习 - 数据加载类 PCA 主成分分析 R 脚本
# 参考: PCA参考代码.R / run_merged_pca_analysis.R (prcomp + factoextra)
#
# 命令行参数（顺序传入）:
#   args[1] = work_dir     工作目录（合并输入文件所在目录）
#   args[2] = expr_file    表达矩阵文件名（行=基因, 列=样本, tab分隔, 第一列 Gene）
#   args[3] = group_file   分组文件名（SampleID, Dataset）
#   args[4] = output_dir   PCA 输出目录
#
# 一次性输出 4 种预处理方法的 PCA 对比:
#   方法1: 不处理（原始TPM）, scale=FALSE       -> 后缀 raw
#   方法2: log2(x+1), scale=FALSE              -> 后缀 log2
#   方法3: log2(x+1), scale=TRUE (z-score)     -> 后缀 log2_scaled
#   方法4: 无 log2, scale=TRUE (z-score)       -> 后缀 scaled
#
# 每种方法输出:
#   pca_plot_<method>.png        PCA 散点图（9x10, dpi=300）
#   pca_results_<method>.csv     前10个主成分
#   pca_variance_<method>.png    主成分贡献率图
# ============================================================

# ---- 命令行参数解析 ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop("用法: Rscript bulk_machinelearning_loading_pca.R <work_dir> <expr_file> <group_file> <output_dir>")
}
work_dir   <- args[1]
expr_file  <- args[2]
group_file <- args[3]
output_dir <- args[4]

# ---- 加载包 ----
if (!requireNamespace("factoextra", quietly = TRUE)) {
  stop("factoextra 包未安装，请在 R 中运行: install.packages('factoextra')")
}
library(factoextra)

# ---- 准备目录 ----
if (!dir.exists(work_dir)) {
  stop(paste("工作目录不存在:", work_dir))
}
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
}

setwd(work_dir)
cat("工作目录:", getwd(), "\n")
cat("输出目录:", output_dir, "\n")

# ---- 读取表达数据 ----
expr_path <- file.path(work_dir, expr_file)
if (!file.exists(expr_path)) {
  stop(paste("表达矩阵文件不存在:", expr_path))
}
data_raw <- read.table(expr_path, sep = "\t", header = TRUE, stringsAsFactors = FALSE, check.names = FALSE)
# 去除重复基因名
data_raw <- data_raw[!duplicated(data_raw[, 1]), ]
rownames(data_raw) <- data_raw[, 1]
data_raw <- data_raw[, -1]

# ---- 读取分组 ----
group_path <- file.path(work_dir, group_file)
if (!file.exists(group_path)) {
  stop(paste("分组文件不存在:", group_path))
}
group <- read.csv(group_path, stringsAsFactors = FALSE)

# 兼容 Group / Dataset 两种列名（统一为 Dataset）
if (!"Dataset" %in% colnames(group) && "Group" %in% colnames(group)) {
  colnames(group)[colnames(group) == "Group"] <- "Dataset"
}

# 仅保留分组文件中出现的样本
common_samples <- intersect(colnames(data_raw), group$SampleID)
data_raw <- data_raw[, common_samples]
group <- group[match(common_samples, group$SampleID), ]

cat("样本数:", ncol(data_raw), " 基因数:", nrow(data_raw), "\n")
cat("分组统计:\n")
print(table(group$Dataset))

# ---- 过滤低表达基因（sum>0） ----
keep <- apply(data_raw, 1, sum) > 0
data_raw <- data_raw[keep, ]
cat("过滤低表达后基因数:", nrow(data_raw), "\n\n")

# ---- 调色板（根据数据集数动态生成足够颜色） ----
# 2 数据集时保留原配色，更多时用 RColorBrewer Set2 / viridis / hcl.colors 依次尝试
n_datasets <- length(unique(group$Dataset))
if (n_datasets <= 2) {
  palette <- c("#00AFBB", "#FC4E07")
} else if (requireNamespace("RColorBrewer", quietly = TRUE) && n_datasets <= 8) {
  palette <- RColorBrewer::brewer.pal(max(n_datasets, 3), "Set2")[1:n_datasets]
} else if (requireNamespace("viridisLite", quietly = TRUE)) {
  palette <- viridisLite::viridis(n_datasets, option = "D")
} else {
  palette <- hcl.colors(n_datasets, palette = "Dark 3")
}
cat("数据集数:", n_datasets, " 使用调色板颜色:\n")
print(palette)

# ============================================================
# 定义 4 种预处理方法
# ============================================================
methods <- list(
  list(suffix = "raw",         desc = "Raw TPM, scale=FALSE",            log_transform = FALSE, scale = FALSE),
  list(suffix = "log2",        desc = "log2(x+1), scale=FALSE",          log_transform = TRUE,  scale = FALSE),
  list(suffix = "log2_scaled", desc = "log2(x+1), scale=TRUE (z-score)", log_transform = TRUE,  scale = TRUE),
  list(suffix = "scaled",      desc = "Raw TPM, scale=TRUE (z-score)",   log_transform = FALSE, scale = TRUE)
)

for (m in methods) {
  cat("============================================================\n")
  cat("方法: ", m$desc, "\n")
  cat("============================================================\n")

  data <- data_raw
  if (m$log_transform) {
    data <- log2(data + 1)
    cat("  已做 log2(x+1) 转换\n")
  }
  if (m$scale) {
    cat("  使用 z-score 标准化 (scale.=TRUE)\n")
  } else {
    cat("  不做标准化 (scale.=FALSE)\n")
  }

  # ---- PCA ----
  res.pca <- prcomp(t(data), scale. = m$scale)

  # 固定 PC1 方向：无条件反转 PC1 符号（与参考方向一致）
  # 原因：prcomp 的主成分符号是任意的，样本顺序不同会导致 PC1 符号系统性反转
  res.pca$x[, 1] <- -res.pca$x[, 1]
  res.pca$rotation[, 1] <- -res.pca$rotation[, 1]
  cat("  已固定 PC1 方向（反转符号以与参考一致）\n")

  cat("  PCA summary (前10个主成分):\n")
  print(summary(res.pca)[[6]][, 1:min(10, ncol(res.pca$x))])

  # ---- 保存前10个主成分 ----
  pc_out <- as.data.frame(res.pca$x[, 1:min(10, ncol(res.pca$x))])
  pc_out$SampleID <- rownames(pc_out)
  pc_out$Dataset <- group$Dataset[match(rownames(pc_out), group$SampleID)]
  pc_csv <- file.path(output_dir, paste0("pca_results_", m$suffix, ".csv"))
  write.csv(pc_out, file = pc_csv, quote = FALSE, row.names = FALSE)
  cat("  主成分已保存:", pc_csv, "\n")

  # ---- 绘图: PCA 散点图（按 Dataset 着色 + 椭圆） ----
  pca_plot <- fviz_pca_ind(
    res.pca,
    geom.ind = "point",
    pointshape = 21,
    fill.ind = group$Dataset,
    col.ind = group$Dataset,
    pointsize = 2,
    palette = palette,
    addEllipses = TRUE,
    legend.title = "Dataset"
  ) +
    theme_bw() +
    theme(panel.grid = element_blank(), legend.position = "top") +
    labs(title = paste0("PCA (", m$desc, ")"))

  # 移除通过原点的虚线（geom_vline / geom_hline）
  pca_plot$layers <- Filter(function(layer) {
    !("GeomVline" %in% class(layer$geom) || "GeomHline" %in% class(layer$geom))
  }, pca_plot$layers)

  # 修改坐标轴标签为 PC1 / PC2（附带方差解释比例）
  var_pct <- summary(res.pca)$importance[2, ]
  pc1_label <- sprintf("PC1 (%.2f%%)", var_pct[1] * 100)
  pc2_label <- sprintf("PC2 (%.2f%%)", var_pct[2] * 100)
  pca_plot <- pca_plot + xlab(pc1_label) + ylab(pc2_label)

  pca_png <- file.path(output_dir, paste0("pca_plot_", m$suffix, ".png"))
  ggsave(pca_png, pca_plot, width = 9, height = 10, dpi = 300)
  # PDF 出图（矢量，便于后续编辑/出版）
  pca_pdf <- file.path(output_dir, paste0("pca_plot_", m$suffix, ".pdf"))
  ggsave(pca_pdf, pca_plot, width = 9, height = 10)
  cat("  PCA 散点图已保存:", pca_png, "/", pca_pdf, "\n")

  # ---- 绘图: 各主成分贡献率 ----
  var_plot <- fviz_eig(res.pca, addlabels = TRUE, barfill = "#00AFBB", barcolor = "#00AFBB") +
    theme_bw() +
    theme(panel.grid = element_blank()) +
    labs(title = paste0("PC Variance Explained (", m$desc, ")"))
  var_png <- file.path(output_dir, paste0("pca_variance_", m$suffix, ".png"))
  ggsave(var_png, var_plot, width = 8, height = 5, dpi = 300)
  var_pdf <- file.path(output_dir, paste0("pca_variance_", m$suffix, ".pdf"))
  ggsave(var_pdf, var_plot, width = 8, height = 5)
  cat("  主成分贡献率图已保存:", var_png, "/", var_pdf, "\n\n")
}

cat("============================================================\n")
cat("全部 4 种预处理方法 PCA 分析完成\n")
cat("输出目录:", output_dir, "\n")
cat("生成的方法: raw / log2 / log2_scaled / scaled\n")
