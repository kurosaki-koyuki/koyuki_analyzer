# -*- coding: utf-8 -*-
# Monocle数据加载类子层R脚本
# 功能：加载带伪时间的CDS对象，生成带轨迹的伪时间测试图
# 用法：Rscript run_monocle_loading.R <cds_rds_path> <output_dir> <dataset_name>

library(monocle3)
library(ggplot2)
library(koyukiTraj)

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 3) {
  cat("Usage: Rscript run_monocle_loading.R <cds_rds_path> <output_dir> <dataset_name>\n")
  quit(status = 1)
}

cds_rds_path <- args[1]
output_dir <- args[2]
dataset_name <- args[3]

dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

if (!file.exists(cds_rds_path)) {
  cds_rds_path <- normalizePath(cds_rds_path, mustWork = FALSE)
  if (!file.exists(cds_rds_path)) {
    cat(paste("ERROR: CDS文件不存在:", cds_rds_path, "\n"))
    quit(status = 1)
  }
}

cat(paste("正在加载CDS对象:", cds_rds_path, "\n"))
cds <- readRDS(cds_rds_path)
cat(paste("CDS对象加载完成, 细胞数:", ncol(cds), "基因数:", nrow(cds), "\n"))

# 检查伪时间是否存在
pseudotime_vals <- tryCatch({
  monocle3::pseudotime(cds)
}, error = function(e) {
  cat(paste("WARNING: 无法获取伪时间:", e$message, "\n"))
  NULL
})

if (is.null(pseudotime_vals) || all(is.na(pseudotime_vals))) {
  cat("ERROR: CDS对象中未包含有效的伪时间数据，请确认rds文件来自初筛轨迹类阶段四导出\n")
  quit(status = 1)
}

valid_count <- sum(!is.na(pseudotime_vals) & is.finite(pseudotime_vals))
cat(paste("有效伪时间细胞数:", valid_count, "\n"))

# 生成带轨迹的伪时间测试图
cat("正在生成带轨迹的伪时间测试图...\n")
p_pseudotime <- koyukiTraj::koyuki_pseudotime_plot(cds) +
  ggplot2::ggtitle(paste(dataset_name, "Pseudotime Test (Loading)"))

test_png_path <- file.path(output_dir, paste0(dataset_name, "_pseudotime_test.png"))
png(file = test_png_path, width = 1200, height = 1200, res = 150)
print(p_pseudotime)
dev.off()

if (file.exists(test_png_path)) {
  cat(paste("Pseudotime测试图已保存:", test_png_path, "\n"))
  cat(test_png_path)
  cat("\n")
  quit(status = 0)
} else {
  cat("ERROR: 测试图保存失败\n")
  quit(status = 1)
}
