# -*- coding: utf-8 -*-
# Monocle基因列表类子层 - 阶段四R脚本
# 功能：基于阶段三结果绘制火山图（带基因名称标记和指向线）
# 用法：Rscript run_monocle_genelists_stage4.R <input_tsv> <output_dir> <dataset_name> <x_axis> <y_axis> <fc_threshold> <p_threshold> <top_n> [cds_rds_path]
#   x_axis: "rho" or "log2fc"
#   y_axis: "p_value" or "q_value"
#   fc_threshold: 数值，如0.5
#   p_threshold: 数值，如0.05
#   top_n: 标记基因数量，如10
#   cds_rds_path: 可选，当x_axis=log2fc时需要

library(ggplot2)
library(ggrepel)

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 8) {
  cat("Usage: Rscript run_monocle_genelists_stage4.R <input_tsv> <output_dir> <dataset_name> <x_axis> <y_axis> <fc_threshold> <p_threshold> <top_n> [cds_rds_path]\n")
  cat("  x_axis: rho / log2fc\n")
  cat("  y_axis: p_value / q_value\n")
  cat("  fc_threshold: numeric, e.g., 0.5\n")
  cat("  p_threshold: numeric, e.g., 0.05\n")
  cat("  top_n: number of genes to label, e.g., 10\n")
  quit(status = 1)
}

input_tsv <- args[1]
output_dir <- args[2]
dataset_name <- args[3]
x_axis <- args[4]
y_axis <- args[5]
fc_threshold <- as.numeric(args[6])
p_threshold <- as.numeric(args[7])
top_n <- as.integer(args[8])
cds_rds_path <- if (length(args) >= 9) args[9] else ""

if (!(x_axis %in% c("rho", "log2fc"))) {
  cat(paste("ERROR: 未知X轴指标:", x_axis, "\n"))
  quit(status = 1)
}
if (!(y_axis %in% c("p_value", "q_value"))) {
  cat(paste("ERROR: 未知Y轴指标:", y_axis, "\n"))
  quit(status = 1)
}

dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

if (!file.exists(input_tsv)) {
  cat(paste("ERROR: 输入TSV文件不存在:", input_tsv, "\n"))
  quit(status = 1)
}

cat(paste0("[Stage4] 正在读取阶段三结果: ", input_tsv, "\n"))
results <- read.table(input_tsv, sep = "\t", header = TRUE, stringsAsFactors = FALSE)
cat(paste0("[Stage4] 读取完成, 基因数: ", nrow(results), "\n"))

if (!"gene_id" %in% colnames(results)) {
  cat("ERROR: 输入数据缺少gene_id列\n")
  quit(status = 1)
}
if (!"rho" %in% colnames(results)) {
  cat("ERROR: 输入数据缺少rho列\n")
  quit(status = 1)
}
if (!y_axis %in% colnames(results)) {
  cat(paste("ERROR: 输入数据缺少", y_axis, "列\n"))
  quit(status = 1)
}

cat(paste0("[Stage4] 数据列名: ", paste(colnames(results), collapse = ", "), "\n"))
cat(paste0("[Stage4] rho范围: ", round(min(results$rho, na.rm = TRUE), 4), " ~ ", round(max(results$rho, na.rm = TRUE), 4), "\n"))
cat(paste0("[Stage4] ", y_axis, "范围: ", format(min(results[[y_axis]], na.rm = TRUE), scientific = TRUE), " ~ ", round(max(results[[y_axis]], na.rm = TRUE), 4), "\n"))

# 准备X轴数据
if (x_axis == "rho") {
  cat("[Stage4] X轴指标: rho\n")
  results$x_val <- results$rho
  x_label <- expression(rho ~ "(Spearman correlation)")
} else {
  cat("[Stage4] X轴指标: log2FC\n")
  if (cds_rds_path == "" || !file.exists(cds_rds_path)) {
    cat("WARNING: 未提供CDS路径，使用rho*2.5近似log2FC\n")
    results$x_val <- results$rho * 2.5
    x_label <- "Approximate log2FC (rho*2.5)"
  } else {
    cat(paste0("[Stage4] 正在加载CDS对象计算log2FC: ", cds_rds_path, "\n"))
    cds <- readRDS(cds_rds_path)
    pseudotime_vals <- monocle3::pseudotime(cds)
    pt_median <- median(pseudotime_vals, na.rm = TRUE)
    early_mask <- pseudotime_vals <= pt_median
    exprs_mat <- SummarizedExperiment::assay(cds, "counts")
    
    log2fc_vals <- numeric(nrow(results))
    for (i in seq_len(nrow(results))) {
      gene <- results$gene_id[i]
      if (gene %in% rownames(exprs_mat)) {
        early_expr <- exprs_mat[gene, early_mask]
        late_expr <- exprs_mat[gene, !early_mask]
        early_mean <- mean(early_expr, na.rm = TRUE)
        late_mean <- mean(late_expr, na.rm = TRUE)
        log2fc_vals[i] <- log2((late_mean + 1e-5) / (early_mean + 1e-5))
      } else {
        log2fc_vals[i] <- results$rho[i] * 2.5
      }
    }
    results$x_val <- log2fc_vals
    x_label <- expression(log[2] ~ "(Fold Change)")
  }
}

# 准备Y轴数据
cat(paste0("[Stage4] Y轴指标: -log10(", y_axis, ")\n"))
results$y_val <- -log10(results[[y_axis]] + 1e-300)
y_label <- bquote(-log[10](.(y_axis)))

# 标记上下调（使用用户指定的y轴指标进行阈值判断）
significance_col <- y_axis
cat(paste0("[Stage4] 阈值: FC=", fc_threshold, ", ", significance_col, "<", p_threshold, "\n"))
results$direction <- "stable"
results$direction[results$x_val > fc_threshold & results[[significance_col]] < p_threshold] <- "up"
results$direction[results$x_val < -fc_threshold & results[[significance_col]] < p_threshold] <- "down"

# 筛选前N个显著基因用于标记（按显著性排序）
cat(paste0("[Stage4] 标记基因数量: ", top_n, "\n"))
up_genes <- results[results$direction == "up", ]
up_genes <- up_genes[order(up_genes[[significance_col]])[1:min(top_n, nrow(up_genes))], ]

down_genes <- results[results$direction == "down", ]
down_genes <- down_genes[order(down_genes[[significance_col]])[1:min(top_n, nrow(down_genes))], ]

label_genes <- rbind(up_genes, down_genes)
cat(paste0("[Stage4] 共标记: ", nrow(label_genes), " 个基因 (上调", nrow(up_genes), " + 下调", nrow(down_genes), ")\n"))

# 统计信息
up_count <- sum(results$direction == "up")
down_count <- sum(results$direction == "down")
stable_count <- sum(results$direction == "stable")
cat(paste0("[Stage4] 上调基因: ", up_count, ", 下调基因: ", down_count, ", 稳定基因: ", stable_count, "\n"))

# 绘制火山图（优化版）
cat("[Stage4] 正在绘制火山图...\n")
volcano_plot <- ggplot(results, aes(x = x_val, y = y_val)) +
    geom_point(aes(color = direction), alpha = 0.5, size = 1.8) +
    
    geom_vline(xintercept = c(-fc_threshold, fc_threshold), 
               linetype = "dashed", color = "#999999", linewidth = 0.8) +
    geom_hline(yintercept = -log10(p_threshold), 
               linetype = "dashed", color = "#999999", linewidth = 0.8) +
    
    scale_color_manual(values = c(
        "up" = "#E74C3C",
        "down" = "#3498DB",
        "stable" = "#BDC3C7"
    )) +
    
    theme_bw() +
    theme(
        plot.title = element_text(color = "#2C3E50", size = 18, face = "bold", hjust = 0.5),
        axis.title = element_text(color = "#2C3E50", size = 14),
        axis.text = element_text(color = "#34495E", size = 11),
        legend.title = element_text(color = "#2C3E50", size = 12),
        legend.text = element_text(color = "#34495E", size = 10),
        panel.grid.major = element_line(color = "#ECF0F1", linewidth = 0.5),
        panel.grid.minor = element_line(color = "#ECF0F1", linewidth = 0.3),
        panel.border = element_rect(color = "#BDC3C7"),
        legend.position = "bottom",
        plot.margin = margin(20, 20, 20, 20)
    ) +
    
    labs(
        x = x_label,
        y = y_label,
        color = "Expression Change",
        title = paste0("Volcano Plot - ", dataset_name)
    )

# 添加基因标签（仅当有显著基因时）
if (nrow(label_genes) > 0) {
    volcano_plot <- volcano_plot +
        geom_text_repel(
            data = label_genes,
            aes(label = gene_id),
            color = "#2C3E50",
            size = 4.5,
            fontface = "bold",
            box.padding = unit(0.5, "lines"),
            point.padding = unit(0.8, "lines"),
            segment.color = "#7F8C8D",
            segment.size = 0.6,
            segment.alpha = 0.7,
            max.overlaps = Inf,
            min.segment.length = unit(0.5, "lines"),
            force = 10,
            force_pull = 1,
            direction = "both"
        )
}

# 保存图片
volcano_path <- file.path(output_dir, paste0(dataset_name, "_volcano.png"))
ggsave(volcano_path, volcano_plot, width = 14, height = 10, dpi = 300, bg = "white")
cat(paste0("[Stage4] 火山图已保存: ", volcano_path, "\n"))

# 输出统计信息
cat(paste0("[Stage4] === 统计信息 ===\n"))
cat(paste0("[Stage4] 上调基因: ", up_count, "\n"))
cat(paste0("[Stage4] 下调基因: ", down_count, "\n"))
cat(paste0("[Stage4] 稳定基因: ", stable_count, "\n"))

cat(volcano_path)
cat("\n")
quit(status = 0)