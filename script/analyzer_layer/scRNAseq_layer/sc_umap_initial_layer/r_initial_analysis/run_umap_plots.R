args <- commandArgs(trailingOnly=TRUE)

if (length(args) < 4) {
    cat("Usage: Rscript run_umap_plots.R <seurat_path> <output_dir> <output_name> <mode> [additional_args]\n")
    quit(status=1)
}

seurat_path <- args[1]
output_dir <- args[2]
output_name <- args[3]
mode <- args[4]

library(Seurat)
library(ggplot2)
library(dplyr)
library(grid)
library(ggrepel)
library(tidydr)
library(ggpubr)

cluster_colors <- c(
    '#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00',
    '#cab2d6','#6a3d9a','#b15928','#49beaa','#611c35','#2708a0','#E59CC4','#90EE90',
    '#F1BB72','#57C3F3','#E59C59','#D6E7A3','#0FA3A8','#F3B1A0','#E5D2DD','#AB3282',
    '#33452F','#BD956A','#8C549C','#585658','#476D87','#E0D4CA','#5F3D69','#C5DEBA',
    '#58A4C3','#E4C755','#F7F398','#AA9A59','#E63863','#E39A35','#C1E6F3','#6778AE',
    '#91D0BE','#B53E2B','#712820','#DCC1DD','#CCE0F5','#CCC9E6','#625D9E','#68A180',
    '#968175','#778899','#B0C4DE','#E6E6FA','#DDA0DD','#FFDAB9','#F0E68C','#ADFF2F',
    '#00CED1','#FF69B4','#CD5C5C','#F08080','#FA8072','#E9967A','#FFA07A','#FF7F50',
    '#FF6347','#FF4500','#FF8C00','#FFA500','#FFD700','#FFFF00','#FFFFE0','#FFFFF0'
)

scRNA <- readRDS(seurat_path)

is_categorical <- function(col) {
    is.factor(col) || is.character(col) || (is.integer(col) && length(unique(col)) < 50) || (is.numeric(col) && length(unique(col)) < 50)
}

if (mode == "info") {
    cells <- ncol(scRNA)
    genes <- nrow(scRNA)
    has_umap <- 'umap' %in% names(scRNA@reductions)
    cat(paste(cells, genes, ifelse(has_umap, "TRUE", "FALSE"), sep="\t"), "\n")
} else if (mode == "metadata") {
    cols <- colnames(scRNA@meta.data)
    categorical_cols <- c()
    for (col in cols) {
        if (is_categorical(scRNA@meta.data[[col]])) {
            categorical_cols <- c(categorical_cols, col)
        }
    }
    cat(paste(categorical_cols, collapse="\t"), "\n")
} else if (mode == "genes") {
    genes <- rownames(scRNA)
    cat(paste(genes, collapse="\t"), "\n")
} else if (mode == "annotation") {
    annotation_col <- args[5]
    
    if (!is_categorical(scRNA@meta.data[[annotation_col]])) {
        cat("SKIP_CONTINUOUS\n")
        quit(status=0)
    }
    
    if (annotation_col == "seurat_clusters") {
        unique_types <- unique(scRNA$seurat_clusters)
        num_types <- length(unique_types)
        if (num_types > length(cluster_colors)) {
            type_colors <- colorRampPalette(cluster_colors)(num_types)
        } else {
            type_colors <- cluster_colors[1:num_types]
        }
        names(type_colors) <- unique_types
        umap <- as.data.frame(scRNA@reductions$umap@cell.embeddings)
        colnames(umap) <- c("umap_1", "umap_2")
        umap$cellType <- as.factor(scRNA@meta.data$seurat_clusters)
        celltypepos <- umap %>% group_by(cellType) %>% summarise(umap_1=median(umap_1), umap_2=median(umap_2))
        p_cl <- ggplot(umap, aes(x = umap_1, y = umap_2)) +
            geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
            scale_color_manual(values = type_colors) +
            geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType), fontface = "bold", data = celltypepos, box.padding = 0.5, point.padding = 0.5, size = 6, label.size = 0.5, fill = "white", alpha = 0.75) +
            theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
            ggtitle(paste(output_name, "Clusters"))
        dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
        png_path <- file.path(output_dir, paste(output_name, "_Clusters_adv.png", sep = ""))
        png(file = png_path, width = 1200, height = 1200, res = 150)
        print(p_cl)
        dev.off()
        cat(png_path, "\n")
    } else {
        unique_types <- unique(scRNA@meta.data[[annotation_col]])
        num_types <- length(unique_types)
        if (num_types > length(cluster_colors)) {
            type_colors <- colorRampPalette(cluster_colors)(num_types)
        } else {
            type_colors <- cluster_colors[1:num_types]
        }
        names(type_colors) <- unique_types
        umap <- as.data.frame(scRNA@reductions$umap@cell.embeddings)
        colnames(umap) <- c("umap_1", "umap_2")
        umap$cellType <- as.factor(scRNA@meta.data[[annotation_col]])
        celltypepos <- umap %>% group_by(cellType) %>% summarise(umap_1=median(umap_1), umap_2=median(umap_2))
        p <- ggplot(umap, aes(x = umap_1, y = umap_2)) +
            geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
            scale_color_manual(values = type_colors) +
            geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType), fontface = "bold", data = celltypepos, box.padding = 0.5, point.padding = 0.5, size = 6, label.size = 0.5, fill = "white", alpha = 0.75) +
            theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
            ggtitle(paste(output_name, annotation_col))
        dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
        annotation_name <- gsub("\\s|\\(|\\)", "_", annotation_col)
        png_path <- file.path(output_dir, paste(output_name, "_", annotation_name, "_adv.png", sep = ""))
        png(file = png_path, width = 1200, height = 1200, res = 150)
        print(p)
        dev.off()
        cat(png_path, "\n")
    }
} else if (mode == "expression") {
    marker <- args[5]
    
    pg <- FeaturePlot(scRNA, features = marker)
    pg_italic <- pg + ggtitle(marker) + theme(plot.title = element_text(face = "bold.italic", size = 20))
    pg_italic <- pg_italic + theme_dr() + theme(plot.title = element_text(hjust = 0.5, size = 20, face = "bold.italic", color = "black"), legend.position = "right", legend.title = element_text(size = 12), legend.text = element_text(size = 10), panel.grid.major = element_blank(), panel.grid.minor = element_blank())
    dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
    marker_name <- gsub("\\s|\\(|\\)|-", "_", marker)
    png_path <- file.path(output_dir, paste(output_name, "_", marker_name, "_expression.png", sep = ""))
    png(file = png_path, width = 1200, height = 1200, res = 150)
    print(pg_italic)
    dev.off()
    cat(png_path, "\n")
} else {
    cat("Unknown mode:", mode, "\n")
    quit(status=1)
}
