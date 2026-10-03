# -*- coding: utf-8 -*-
# ============================================================
# bulk 机器学习 - 批次去除类 PCA + ComBat 去批次 R 脚本
#
# 命令行参数（顺序传入）:
#   args[1] = mode             运行模式: stage1 或 stage2
#   args[2] = work_dir         工作目录（合并输入文件所在目录）
#   args[3] = expr_file        表达矩阵文件名（行=基因, 列=样本, tab分隔, 第一列 Gene）
#   args[4] = group_file       分组文件名（SampleID, Dataset）
#   args[5] = output_dir       输出目录
#   args[6] = preprocessing    预处理方法: raw / log2 / log2_scaled / scaled
#
# stage1: 根据选定预处理方法生成去批次前 PCA
# stage2: log2(x+1) 预处理 -> ComBat 去批次 -> 去批次后 PCA
#
# 输出文件:
#   stage1: pca_plot_stage1.png, pca_results_stage1.csv
#   stage2: pca_plot_stage2.png, pca_results_stage2.csv, combat_corrected_exprdata.txt
# ============================================================

# ---- 命令行参数解析 ----
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 6) {
  stop("用法: Rscript bulk_machinelearning_pca_combat.R <mode> <work_dir> <expr_file> <group_file> <output_dir> <preprocessing>")
}
mode         <- args[1]
work_dir     <- args[2]
expr_file    <- args[3]
group_file   <- args[4]
output_dir   <- args[5]
preprocessing <- args[6]

cat("============================================================\n")
cat("批次去除类 PCA + ComBat 分析\n")
cat("模式:", mode, " 预处理:", preprocessing, "\n")
cat("============================================================\n")

# ---- 加载包 ----
if (!requireNamespace("factoextra", quietly = TRUE)) {
  stop("factoextra 包未安装，请在 R 中运行: install.packages('factoextra')")
}
library(factoextra)
if (mode == "stage2") {
  if (!requireNamespace("sva", quietly = TRUE)) {
    stop("sva 包未安装，请在 R 中运行: BiocManager::install('sva')")
  }
  library(sva)
}

# ---- 准备目录 ----
if (!dir.exists(work_dir)) stop(paste("工作目录不存在:", work_dir))
if (!dir.exists(output_dir)) dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
setwd(work_dir)

# ---- 读取表达数据 ----
expr_path <- file.path(work_dir, expr_file)
if (!file.exists(expr_path)) stop(paste("表达矩阵文件不存在:", expr_path))
data_raw <- read.table(expr_path, sep = "\t", header = TRUE, stringsAsFactors = FALSE, check.names = FALSE)
data_raw <- data_raw[!duplicated(data_raw[, 1]), ]
rownames(data_raw) <- data_raw[, 1]
data_raw <- data_raw[, -1]

# ---- 读取分组 ----
group_path <- file.path(work_dir, group_file)
if (!file.exists(group_path)) stop(paste("分组文件不存在:", group_path))
group <- read.csv(group_path, stringsAsFactors = FALSE)
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

# ---- 过滤低表达基因 ----
keep <- apply(data_raw, 1, sum) > 0
data_raw <- data_raw[keep, ]
cat("过滤低表达后基因数:", nrow(data_raw), "\n\n")

# ---- 调色板（根据数据集数动态生成足够颜色） ----
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

# ---- 辅助函数：PCA + 绘图 ----
run_pca_and_plot <- function(data, title, output_prefix, do_log2, do_scale) {
  data_proc <- data
  if (do_log2) data_proc <- log2(data_proc + 1)

  res.pca <- prcomp(t(data_proc), scale. = do_scale)

  # 固定 PC1 方向：无条件反转（与参考一致）
  res.pca$x[, 1] <- -res.pca$x[, 1]
  res.pca$rotation[, 1] <- -res.pca$rotation[, 1]

  # 保存 PCA 结果
  pc_out <- as.data.frame(res.pca$x[, 1:min(10, ncol(res.pca$x))])
  pc_out$SampleID <- rownames(pc_out)
  pc_out$Dataset <- group$Dataset[match(rownames(pc_out), group$SampleID)]
  write.csv(pc_out, file = file.path(output_dir, paste0(output_prefix, "_results.csv")), quote = FALSE, row.names = FALSE)

  # 绘图
  pca_plot <- fviz_pca_ind(
    res.pca, geom.ind = "point", pointshape = 21,
    fill.ind = group$Dataset, col.ind = group$Dataset,
    pointsize = 2, palette = palette, addEllipses = TRUE, legend.title = "Dataset"
  ) + theme_bw() + theme(panel.grid = element_blank(), legend.position = "top") + labs(title = title)

  # 移除通过原点的虚线
  pca_plot$layers <- Filter(function(layer) {
    !("GeomVline" %in% class(layer$geom) || "GeomHline" %in% class(layer$geom))
  }, pca_plot$layers)

  # 坐标轴标签
  var_pct <- summary(res.pca)$importance[2, ]
  pca_plot <- pca_plot + xlab(sprintf("PC1 (%.2f%%)", var_pct[1] * 100)) + ylab(sprintf("PC2 (%.2f%%)", var_pct[2] * 100))

  # PNG 出图
  ggsave(file.path(output_dir, paste0(output_prefix, "_plot.png")), pca_plot, width = 9, height = 10, dpi = 300)
  # PDF 出图（矢量，便于后续编辑/出版）
  ggsave(file.path(output_dir, paste0(output_prefix, "_plot.pdf")), pca_plot, width = 9, height = 10)
  cat("PCA 图已保存:", paste0(output_prefix, "_plot.png / .pdf"), "\n")
  cat("方差解释: PC1=", sprintf("%.2f%%", var_pct[1] * 100), " PC2=", sprintf("%.2f%%", var_pct[2] * 100), "\n")
}

# ============================================================
# 阶段一: 去批次前 PCA
# ============================================================
if (mode == "stage1") {
  cat("============================================================\n")
  cat("阶段一: 去批次前 PCA\n")
  cat("============================================================\n")

  do_log2 <- preprocessing %in% c("log2", "log2_scaled")
  do_scale <- preprocessing %in% c("log2_scaled", "scaled")
  if (do_log2) cat("已做 log2(x+1) 转换\n")
  if (do_scale) cat("使用 z-score 标准化\n")

  run_pca_and_plot(data_raw, paste0("去批次前 PCA (", preprocessing, ")"), "pca_stage1", do_log2, do_scale)

  cat("\n阶段一完成\n")
}

# ============================================================
# 阶段二: ComBat 去批次 + PCA
# ============================================================
if (mode == "stage2") {
  cat("============================================================\n")
  cat("阶段二: ComBat 去批次\n")
  cat("============================================================\n")

  # log2(x+1) 预处理
  data_log2 <- log2(data_raw + 1)
  cat("已做 log2(x+1) 转换\n")

  # 准备 batch 向量
  batch <- as.factor(group$Dataset)
  cat("批次因子水平:", levels(batch), "\n")

  # 过滤全为 0 的基因
  nonzero <- apply(data_log2, 1, function(x) sum(x > 0) > 0)
  data_log2_filtered <- data_log2[nonzero, ]
  cat("ComBat 过滤后基因数:", nrow(data_log2_filtered), "\n")

  cat("正在运行 ComBat...\n")
  combat_time <- system.time({
    data_corrected <- ComBat(dat = as.matrix(data_log2_filtered), batch = batch)
  })
  cat("ComBat 运行耗时:", combat_time["elapsed"], "秒\n")

  # 保存去批次后的表达矩阵
  expr_out <- as.data.frame(data_corrected)
  expr_out <- cbind(Gene = rownames(expr_out), expr_out)
  write.table(expr_out, file = file.path(output_dir, "combat_corrected_exprdata.txt"),
              sep = "\t", row.names = FALSE, quote = FALSE)
  cat("去批次后表达矩阵已保存\n")

  # 去批次后 PCA（不再做 log2，因为已经做过；不做 scale）
  run_pca_and_plot(data_corrected, "去批次后 PCA (ComBat, log2(x+1))", "pca_stage2", FALSE, FALSE)

  cat("\n阶段二完成\n")
}

cat("============================================================\n")
cat("输出目录:", output_dir, "\n")
cat("============================================================\n")
