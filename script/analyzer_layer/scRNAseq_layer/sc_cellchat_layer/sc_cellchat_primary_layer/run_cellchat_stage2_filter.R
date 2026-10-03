# CellChat初步分析 - 阶段二：筛选细胞并可选重新降维
# 参数：
#   seurat_path: Seurat对象的rds文件路径
#   main_annot: 主注释列
#   celltypes: 要保留的细胞类型（逗号分隔）
#   re_reduce: 是否重新降维（TRUE/FALSE）
#   dim_val: 降维维度
#   plot_annot: 出图注释列
#   output_path: 输出图片路径
#   filtered_rds_path: 筛选后RDS保存路径

filter_and_reduce <- function(seurat_path, main_annot, celltypes, re_reduce = FALSE, dim_val = 30, plot_annot, output_path, filtered_rds_path = NULL) {
  library(Seurat)
  library(ggplot2)
  library(grid)
  library(ggrepel)
  library(dplyr)
  library(tidydr)
  
  cat("读取Seurat对象...\n")
  seurat_obj <- readRDS(seurat_path)
  
  cat(paste("主注释列:", main_annot, "\n"))
  cat(paste("筛选细胞类型:", paste(celltypes, collapse=", "), "\n"))
  
  # 使用主注释列进行筛选
  celltype_col <- main_annot
  
  if (!celltype_col %in% colnames(seurat_obj@meta.data)) {
    cat("ERROR: 主注释列不存在\n")
    cat(paste("可用的列:", paste(colnames(seurat_obj@meta.data), collapse=", "), "\n"))
    quit(status=1)
  }
  
  cat(paste("使用主注释列:", celltype_col, "\n"))
  
  # 筛选细胞
  meta <- seurat_obj@meta.data
  selected_cells <- rownames(meta)[meta[[celltype_col]] %in% celltypes]
  
  cat(paste("筛选前细胞数:", nrow(meta), "\n"))
  cat(paste("筛选后细胞数:", length(selected_cells), "\n"))
  
  if (length(selected_cells) == 0) {
    cat("ERROR: 筛选后没有细胞\n")
    quit(status=1)
  }
  
  # 子集化Seurat对象
  seurat_sub <- subset(seurat_obj, cells = selected_cells)
  
  # 可选重新降维
  if (re_reduce) {
    cat(paste("重新降维，dim =", dim_val, "\n"))
    
    # 重新运行PCA
    seurat_sub <- RunPCA(seurat_sub, npcs = dim_val, verbose = FALSE)
    
    # 重新运行UMAP
    seurat_sub <- RunUMAP(seurat_sub, reduction = "pca", dims = 1:dim_val, verbose = FALSE)
    
    cat("重新降维完成\n")
  }
  
  # 保存筛选后的RDS
  if (!is.null(filtered_rds_path)) {
    cat(paste("保存筛选后Seurat对象到:", filtered_rds_path, "\n"))
    dir.create(dirname(filtered_rds_path), showWarnings = FALSE, recursive = TRUE)
    saveRDS(seurat_sub, filtered_rds_path)
    cat("筛选后RDS保存完成\n")
  }
  
  # 确定出图注释列
  if (plot_annot %in% colnames(seurat_sub@meta.data)) {
    annot_col <- plot_annot
  } else {
    annot_col <- celltype_col
  }
  
  cat(paste("生成UMAP图，使用注释列:", annot_col, "\n"))
  
  # 提取UMAP坐标
  umap_df <- as.data.frame(Embeddings(seurat_sub, reduction = "umap"))
  colnames(umap_df) <- c("umap_1", "umap_2")
  umap_df$cellType <- as.factor(seurat_sub@meta.data[[annot_col]])
  
  # 生成颜色
  cluster_colors <- c(
    '#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00',
    '#cab2d6','#6a3d9a','#b15928','#49beaa','#611c35','#2708a0','#E59CC4','#90EE90',
    '#F1BB72','#57C3F3','#E59C59','#D6E7A3','#0FA3A8','#F3B1A0','#E5D2DD','#AB3282',
    '#33452F','#BD956A','#8C549C','#585658','#476D87','#E0D4CA','#5F3D69','#C5DEBA',
    '#58A4C3','#E4C755','#F7F398','#AA9A59','#E63863','#E39A35','#C1E6F3','#6778AE',
    '#91D0BE','#B53E2B','#712820','#DCC1DD','#CCE0F5','#CCC9E6','#625D9E','#68A180',
    '#968175','#778899','#B0C4DE','#E6E6FA','#DDA0DD','#FFDAB9','#F0E68C','#ADFF2F'
  )
  
  unique_types <- unique(umap_df$cellType)
  num_types <- length(unique_types)
  if (num_types > length(cluster_colors)) {
    type_colors <- colorRampPalette(cluster_colors)(num_types)
  } else {
    type_colors <- cluster_colors[1:num_types]
  }
  names(type_colors) <- unique_types
  
  # 计算每个细胞类型的中位位置用于标签
  celltypepos <- umap_df %>%
    group_by(cellType) %>%
    summarise(umap_1 = median(umap_1), umap_2 = median(umap_2))
  
  # 绘制UMAP图（使用theme_dr风格）
  p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
    geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
    scale_color_manual(values = type_colors) +
    geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType),
               fontface = "bold", data = celltypepos,
               box.padding = 0.5, point.padding = 0.5, size = 6,
               label.size = 0.5, fill = "white", alpha = 0.75) +
    theme_dr() + theme(aspect.ratio = 1,
          panel.background = element_blank(),
          panel.grid = element_blank(),
          axis.line = element_line(color = "black", linewidth = 0.5),
          axis.ticks = element_blank(),
          axis.ticks.length = unit(0.2, "cm"),
          axis.title = element_text(hjust = 0.05, size = 12),
          plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"),
          legend.position = "none") +
    ggtitle(paste("UMAP -", annot_col))
  
  # 保存图片
  dir.create(dirname(output_path), showWarnings = FALSE, recursive = TRUE)
  
  png(file = output_path, width = 1200, height = 1200, res = 150)
  print(p)
  dev.off()
  
  cat(paste("图片已保存:", output_path, "\n"))
}

# 解析命令行参数
args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 7) {
  seurat_path <- args[1]
  main_annot <- args[2]
  celltypes <- strsplit(args[3], ",")[[1]]
  re_reduce <- as.logical(args[4])
  dim_val <- as.integer(args[5])
  plot_annot <- args[6]
  output_path <- args[7]
  filtered_rds_path <- if (length(args) >= 8) args[8] else NULL
  
  tryCatch({
    filter_and_reduce(seurat_path, main_annot, celltypes, re_reduce, dim_val, plot_annot, output_path, filtered_rds_path)
  }, error = function(e) {
    cat(paste("ERROR:", e$message, "\n"))
    quit(status=1)
  })
} else {
  cat("用法: Rscript run_cellchat_stage2_filter.R <seurat_path> <main_annot> <celltypes> <re_reduce> <dim_val> <plot_annot> <output_path> [filtered_rds_path]\n")
}