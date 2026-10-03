#!/usr/bin/env Rscript

library(optparse)
library(monocle3)
library(ggplot2)
library(dplyr)
library(cowplot)

option_list <- list(
    make_option(c("--rds"), type="character", help="CDS RDS文件路径"),
    make_option(c("--genes"), type="character", help="基因名称列表（逗号分隔）"),
    make_option(c("--output"), type="character", help="输出图片路径"),
    make_option(c("--anno"), type="character", default=NULL, help="注释列名（用于着色分组）"),
    make_option(c("--yaxis"), type="character", default="count", help="Y轴数据格式: count, log2, normalized")
)

parser <- OptionParser(option_list=option_list)
args <- parse_args(parser)

if (is.null(args$rds) || is.null(args$genes) || is.null(args$output)) {
    print_help(parser)
    quit(status=1)
}

cat(paste0("Loading CDS from: ", args$rds, "\n"))
cds <- readRDS(args$rds)

gene_list <- strsplit(args$genes, ",")[[1]]
cat(paste0("Genes to plot: ", paste(gene_list, collapse=", "), "\n"))
cat(paste0("Y-axis format: ", args$yaxis, "\n"))

found_genes <- c()
for (gene in gene_list) {
    if (gene %in% rownames(cds)) {
        found_genes <- c(found_genes, gene)
    } else if (gene %in% rowData(cds)$gene_short_name) {
        gene_id <- rownames(cds)[rowData(cds)$gene_short_name == gene]
        found_genes <- c(found_genes, gene_id)
    } else {
        cat(paste0("WARNING: Gene ", gene, " not found in CDS\n"))
    }
}

if (length(found_genes) == 0) {
    cat("ERROR: No genes found in CDS!\n")
    quit(status=1)
}

cat(paste0("Found genes: ", paste(found_genes, collapse=", "), "\n"))

if (args$yaxis == "log2") {
    expr_mat <- log1p(SummarizedExperiment::assay(cds, "counts"))
    SummarizedExperiment::assay(cds, "counts") <- expr_mat
    y_label <- "Expression (log2(count+1))"
} else if (args$yaxis == "normalized") {
    size_factors <- sizeFactors(cds)
    if (is.null(size_factors)) {
        size_factors <- rep(1, ncol(cds))
    }
    expr_mat <- SummarizedExperiment::assay(cds, "counts") / size_factors
    SummarizedExperiment::assay(cds, "counts") <- expr_mat
    y_label <- "Expression (normalized)"
} else {
    y_label <- "Expression (counts)"
}

plots <- list()

for (gene_name in found_genes) {
    if (!is.null(args$anno) && args$anno %in% colnames(colData(cds))) {
        cat(paste0("Coloring by: ", args$anno, "\n"))
        p <- plot_genes_in_pseudotime(
            cds[gene_name, ],
            color_cells_by = args$anno
        ) +
            labs(y = y_label) +
            theme(
                plot.title = element_text(color = "#2C3E50", size = 28, face = "bold", hjust = 0.5),
                axis.title = element_text(color = "#000000", size = 16),
                axis.text = element_text(color = "#000000", size = 14),
                legend.title = element_text(color = "#000000", size = 14),
                legend.text = element_text(color = "#000000", size = 12),
                panel.grid.major = element_line(color = "#ECF0F1", linewidth = 0.3),
                panel.grid.minor = element_line(color = "#ECF0F1", linewidth = 0.2),
                panel.border = element_rect(color = "#BDC3C7"),
                legend.position = "bottom",
                legend.key.size = unit(1.5, "cm"),
                plot.margin = margin(10, 10, 10, 10)
            )
    } else {
        cat("Coloring by: pseudotime\n")
        p <- plot_genes_in_pseudotime(
            cds[gene_name, ],
            color_cells_by = "pseudotime"
        ) +
            labs(y = y_label) +
            theme(
                plot.title = element_text(color = "#2C3E50", size = 28, face = "bold", hjust = 0.5),
                axis.title = element_text(color = "#000000", size = 16),
                axis.text = element_text(color = "#000000", size = 14),
                legend.title = element_text(color = "#000000", size = 14),
                legend.text = element_text(color = "#000000", size = 12),
                panel.grid.major = element_line(color = "#ECF0F1", linewidth = 0.3),
                panel.grid.minor = element_line(color = "#ECF0F1", linewidth = 0.2),
                panel.border = element_rect(color = "#BDC3C7"),
                legend.position = "bottom",
                legend.key.size = unit(1.5, "cm"),
                plot.margin = margin(10, 10, 10, 10)
            )
    }
    
    plots[[gene_name]] <- p
}

if (length(plots) == 1) {
    combined_plot <- plots[[1]]
    plot_width <- 12
    plot_height <- 12
} else {
    n_cols <- min(3, length(plots))
    n_rows <- ceiling(length(plots) / n_cols)
    combined_plot <- plot_grid(plotlist = plots, ncol = n_cols, nrow = n_rows, align = "hv", axis = "lr")
    plot_width <- 12 * n_cols
    plot_height <- 12 * n_rows
}

dir.create(dirname(args$output), showWarnings = FALSE, recursive = TRUE)
ggsave(args$output, combined_plot, width = plot_width, height = plot_height, dpi = 300)
cat(paste0("Plot saved to: ", args$output, "\n"))