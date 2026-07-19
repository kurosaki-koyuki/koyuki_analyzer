# -*- coding: utf-8 -*-
# R版本差异分析脚本
# 通过Seurat的FindMarkers函数进行差异表达分析

# --- DIFF_ANALYSIS_BODY_START ---
cat("=== R版本差异分析开始 ===\n")

if (!require("Seurat")) {
    stop("Seurat包未安装，请先运行: install.packages('Seurat')")
}
if (!require("SeuratObject")) {
    stop("SeuratObject包未安装，请先运行: install.packages('SeuratObject')")
}
if (!require("dplyr")) {
    stop("dplyr包未安装，请先运行: install.packages('dplyr')")
}
if (!require("openxlsx")) {
    stop("openxlsx包未安装，请先运行: install.packages('openxlsx')")
}
if (!require("ggplot2")) {
    stop("ggplot2包未安装，请先运行: install.packages('ggplot2')")
}

library(Seurat)
library(SeuratObject)
library(dplyr)
library(openxlsx)
library(ggplot2)

cat("R包加载完成\n")

if (!exists("seurat_path") || is.null(seurat_path) || length(seurat_path) == 0 || seurat_path == "") {
    stop("请提供Seurat对象路径 (seurat_path)")
}

seurat_path <- as.character(seurat_path)
cat(paste("Seurat对象路径:", seurat_path, "\n"))

if (!file.exists(seurat_path)) {
    stop(paste("Seurat对象文件不存在:", seurat_path))
}

cat("正在加载Seurat对象...\n")
seurat_obj <- readRDS(seurat_path)
cat(paste("Seurat对象加载完成:", class(seurat_obj), "\n"))
cat(paste("细胞数:", ncol(seurat_obj), "\n"))
cat(paste("基因数:", nrow(seurat_obj), "\n"))

if (!exists("group_col") || is.null(group_col) || length(group_col) == 0 || group_col == "") {
    stop("请提供分组列名 (group_col)")
}

group_col <- as.character(group_col)
cat(paste("分组列:", group_col, "\n"))

if (!group_col %in% colnames(seurat_obj@meta.data)) {
    stop(paste("分组列不存在于元数据中:", group_col))
}

if (!exists("group1_items") || is.null(group1_items) || length(group1_items) == 0) {
    stop("请提供组别1的项目 (group1_items)")
}

if (!exists("group2_items") || is.null(group2_items) || length(group2_items) == 0) {
    stop("请提供组别2的项目 (group2_items)")
}

group1_items <- as.character(group1_items)
group2_items <- as.character(group2_items)

cat(paste("组别1:", paste(group1_items, collapse=", "), "\n"))
cat(paste("组别2:", paste(group2_items, collapse=", "), "\n"))

if (!exists("output_dir") || is.null(output_dir) || length(output_dir) == 0 || output_dir == "") {
    output_dir <- tempdir()
}

output_dir <- as.character(output_dir)
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
cat(paste("输出目录:", output_dir, "\n"))

min_cells <- if (exists("min_cells") && !is.null(min_cells)) as.integer(min_cells) else 3
min_expr <- if (exists("min_expr") && !is.null(min_expr)) as.numeric(min_expr) else 0
pval_threshold <- if (exists("pval_threshold") && !is.null(pval_threshold)) as.numeric(pval_threshold) else 0.05
logfc_threshold <- if (exists("logfc_threshold") && !is.null(logfc_threshold)) as.numeric(logfc_threshold) else 0.25
pct_threshold <- if (exists("pct_threshold") && !is.null(pct_threshold)) as.numeric(pct_threshold) else 0.1

cat(paste("参数: min_cells=", min_cells, ", min_expr=", min_expr, ", pval_threshold=", pval_threshold, ", logfc_threshold=", logfc_threshold, ", pct_threshold=", pct_threshold, "\n", sep=""))

filter_enabled <- if (exists("filter_enabled") && !is.null(filter_enabled) && length(filter_enabled) > 0) {
    as.logical(filter_enabled[1])
} else {
    FALSE
}
cat(paste("筛选启用:", filter_enabled, "\n"))

# ===== 阶段1: 创建组合注释列 =====
cat("=== 阶段1: 创建组合注释列 ===\n")

seurat_obj@meta.data$diff_filter_group <- "other"

if (filter_enabled) {
    cat(paste("应用筛选条件\n"))
    
    filter_mask <- rep(TRUE, ncol(seurat_obj))
    
    if (exists("filter_col") && !is.null(filter_col) && filter_col != "") {
        filter_col <- as.character(filter_col)
        cat(paste("筛选列1:", filter_col, "\n"))
        
        if (exists("filter_groups") && !is.null(filter_groups) && length(filter_groups) > 0) {
            filter_groups <- as.character(filter_groups)
            cat(paste("筛选值1:", paste(filter_groups, collapse=", "), "\n"))
            
            filter_mask <- filter_mask & (seurat_obj@meta.data[[filter_col]] %in% filter_groups)
            cat(paste("筛选1后保留:", sum(filter_mask), "个细胞\n"))
        }
    }
    
    if (exists("filter_col2") && !is.null(filter_col2) && filter_col2 != "") {
        filter_col2 <- as.character(filter_col2)
        cat(paste("筛选列2:", filter_col2, "\n"))
        
        if (exists("filter_groups2") && !is.null(filter_groups2) && length(filter_groups2) > 0) {
            filter_groups2 <- as.character(filter_groups2)
            cat(paste("筛选值2:", paste(filter_groups2, collapse=", "), "\n"))
            
            filter_mask <- filter_mask & (seurat_obj@meta.data[[filter_col2]] %in% filter_groups2)
            cat(paste("筛选2后保留:", sum(filter_mask), "个细胞\n"))
        }
    }
    
    seurat_obj <- seurat_obj[, filter_mask]
    cat(paste("筛选后总细胞数:", ncol(seurat_obj), "\n"))
}

group1_cells <- colnames(seurat_obj)[seurat_obj@meta.data[[group_col]] %in% group1_items]
group2_cells <- colnames(seurat_obj)[seurat_obj@meta.data[[group_col]] %in% group2_items]

cat(paste("组1细胞数:", length(group1_cells), "\n"))
cat(paste("组2细胞数:", length(group2_cells), "\n"))

if (length(group1_cells) < min_cells) {
    stop(paste("组1细胞数不足，要求至少", min_cells, "个细胞，当前只有", length(group1_cells), "个"))
}
if (length(group2_cells) < min_cells) {
    stop(paste("组2细胞数不足，要求至少", min_cells, "个细胞，当前只有", length(group2_cells), "个"))
}

seurat_obj@meta.data$diff_filter_group[colnames(seurat_obj) %in% group1_cells] <- "group1"
seurat_obj@meta.data$diff_filter_group[colnames(seurat_obj) %in% group2_cells] <- "group2"

n_others <- sum(seurat_obj@meta.data$diff_filter_group == "other")
cat(paste("Others类群细胞数:", n_others, "\n"))

seurat_obj_before_filter <- seurat_obj
seurat_obj <- seurat_obj[, seurat_obj@meta.data$diff_filter_group %in% c("group1", "group2")]
cat(paste("已过滤Others类群细胞数:", ncol(seurat_obj_before_filter) - ncol(seurat_obj), "\n"))

cat(paste("最终用于分析的细胞数:", ncol(seurat_obj), "\n"))
cat(paste("最终组1细胞数:", sum(seurat_obj@meta.data$diff_filter_group == "group1"), "\n"))
cat(paste("最终组2细胞数:", sum(seurat_obj@meta.data$diff_filter_group == "group2"), "\n"))

# ===== 阶段2: 使用组合注释列进行差异分析 =====
cat("=== 阶段2: 执行FindMarkers差异分析 ===\n")

markers <- FindMarkers(
    object = seurat_obj,
    ident.1 = "group1",
    ident.2 = "group2",
    group.by = "diff_filter_group",
    test.use = "MAST",
    min.pct = pct_threshold,
    logfc.threshold = logfc_threshold,
    min.cells.feature = min_cells,
    min.cells.group = min_cells
)

cat(paste("差异分析完成，找到", nrow(markers), "个差异基因\n"))

markers$gene <- rownames(markers)
markers <- markers[, c("gene", setdiff(colnames(markers), "gene"))]

markers$pct_expr_group1 <- markers$pct.1
markers$pct_expr_group2 <- markers$pct.2
markers$mean_expr_group1 <- markers$avg_log2FC + log2(2^markers$pct.1)
markers$mean_expr_group2 <- log2(2^markers$pct.2)

markers$n_cells_group1 <- sum(seurat_obj@meta.data$diff_filter_group == "group1")
markers$n_cells_group2 <- sum(seurat_obj@meta.data$diff_filter_group == "group2")

markers$significant <- (markers$p_val_adj < pval_threshold) & (abs(markers$avg_log2FC) > logfc_threshold)

markers$change <- "stable"
markers$change[markers$p_val_adj < pval_threshold & markers$avg_log2FC > logfc_threshold] <- "up"
markers$change[markers$p_val_adj < pval_threshold & markers$avg_log2FC < -logfc_threshold] <- "down"

markers <- markers[order(markers$p_val_adj, markers$p_val, markers$gene), ]

rownames(markers) <- NULL

cat("结果数据整理完成\n")

output_file <- file.path(output_dir, "r_diff_results.csv")
write.csv(markers, output_file, row.names = FALSE, fileEncoding = "UTF-8")
cat(paste("结果已保存到:", output_file, "\n"))

up_genes <- markers[markers$change == "up", ]
down_genes <- markers[markers$change == "down", ]

cat(paste("显著上调基因:", nrow(up_genes), "\n"))
cat(paste("显著下调基因:", nrow(down_genes), "\n"))

if (!is.null(markers) && nrow(markers) > 0) {
    volcano_plot <- ggplot(markers, aes(x = avg_log2FC, y = -log10(p_val_adj + 1e-300))) +
        geom_point(aes(color = change), alpha = 0.6, size = 2) +
        scale_color_manual(values = c("up" = "#FF6B35", "down" = "#87CEEB", "stable" = "#666666")) +
        geom_vline(xintercept = c(-logfc_threshold, logfc_threshold), linetype = "dashed", color = "#666666", alpha = 0.5) +
        geom_hline(yintercept = -log10(pval_threshold), linetype = "dashed", color = "#666666", alpha = 0.5) +
        labs(x = "log2 Fold Change", y = "-log10(adj.p-value)", title = "R MAST Differential Expression") +
        theme_minimal() +
        theme(
            plot.title = element_text(color = "#87CEEB", size = 14, face = "bold"),
            axis.title = element_text(color = "#87CEEB", size = 12),
            axis.text = element_text(color = "#87CEEB", size = 10),
            legend.title = element_text(color = "#87CEEB", size = 12),
            legend.text = element_text(color = "#87CEEB", size = 10),
            panel.background = element_rect(fill = "#1E3A5F"),
            plot.background = element_rect(fill = "#1A1A2E")
        )
    
    volcano_path <- file.path(output_dir, "r_diff_volcano.png")
    ggsave(volcano_path, volcano_plot, width = 10, height = 8, dpi = 300, bg = "transparent")
    cat(paste("火山图已保存到:", volcano_path, "\n"))
}

r_diff_result <- list(
    markers = markers,
    n_cells_group1 = sum(seurat_obj@meta.data$diff_filter_group == "group1"),
    n_cells_group2 = sum(seurat_obj@meta.data$diff_filter_group == "group2"),
    up_count = nrow(up_genes),
    down_count = nrow(down_genes),
    total_count = nrow(markers),
    output_file = output_file,
    volcano_path = if (exists("volcano_path")) volcano_path else NULL
)

cat("=== R版本差异分析结束 ===\n")
# --- DIFF_ANALYSIS_BODY_END ---
