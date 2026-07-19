library(monocle3)
library(Seurat)
library(dplyr)
library(ggplot2)
library(grid)
library(ggrepel)
library(tidydr)
library(koyukiTraj)
library(shiny)

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

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 4) {
  cat("Usage: Rscript run_monocle.R <seurat_path> <output_dir> <dataset_name> <mode> [additional_args]")
  quit(status = 1)
}

seurat_path <- args[1]
output_dir <- args[2]
dataset_name <- args[3]
mode <- args[4]

dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

if (!file.exists(seurat_path)) {
  seurat_path <- normalizePath(seurat_path, mustWork = FALSE)
  if (!file.exists(seurat_path)) {
    cat(paste("ERROR: File not found:", seurat_path))
    quit(status = 1)
  }
}

# stage4_pseudotime模式不需要加载Seurat对象（从cds_path加载CDS对象），跳过以节省内存和时间
if (mode != "stage4_pseudotime") {
  seurat_obj <- readRDS(seurat_path)
}

if (mode == "info") {
  n_cells <- ncol(seurat_obj)
  n_genes <- nrow(seurat_obj)
  has_umap <- "umap" %in% names(seurat_obj@reductions)
  cat(paste(n_cells, "\t", n_genes, "\t", tolower(as.character(has_umap))))
  quit(status = 0)
}

if (mode == "metadata") {
  meta_cols <- colnames(seurat_obj@meta.data)
  cat(paste(meta_cols, collapse = "\t"))
  quit(status = 0)
}

if (mode == "genes") {
  gene_names <- rownames(seurat_obj)
  cat(paste(gene_names, collapse = "\t"))
  quit(status = 0)
}

if (mode == "celltypes") {
  col_name <- args[5]
  if (col_name %in% colnames(seurat_obj@meta.data)) {
    cell_types <- unique(as.character(seurat_obj@meta.data[[col_name]]))
    cat(paste(cell_types, collapse = "\t"))
  } else {
    cat("COLUMN_NOT_FOUND")
  }
  quit(status = 0)
}

if (mode == "stage1_simple") {
  cat("Loading Seurat object...\n")
  cat(paste("Loaded:", ncol(seurat_obj), "cells,", nrow(seurat_obj), "genes\n"))
  
  if (!"umap" %in% names(seurat_obj@reductions)) {
    cat("ERROR: No UMAP reduction found")
    quit(status = 1)
  }
  
  cat("Extracting UMAP coordinates...\n")
  umap_df <- as.data.frame(Embeddings(seurat_obj, reduction = "umap"))
  colnames(umap_df) <- c("umap_1", "umap_2")
  umap_df$cell <- rownames(umap_df)
  
  if ("seurat_clusters" %in% colnames(seurat_obj@meta.data)) {
    umap_df$cellType <- as.factor(seurat_obj@meta.data$seurat_clusters)
    unique_types <- unique(umap_df$cellType)
    num_types <- length(unique_types)
    if (num_types > length(cluster_colors)) {
      type_colors <- colorRampPalette(cluster_colors)(num_types)
    } else {
      type_colors <- cluster_colors[1:num_types]
    }
    names(type_colors) <- unique_types
    celltypepos <- umap_df %>% group_by(cellType) %>% summarise(umap_1=median(umap_1), umap_2=median(umap_2))
    p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
      geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
      scale_color_manual(values = type_colors) +
      geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType), fontface = "bold", data = celltypepos, box.padding = 0.5, point.padding = 0.5, size = 6, label.size = 0.5, fill = "white", alpha = 0.75) +
      theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
      ggtitle(paste(dataset_name, "Clusters"))
  } else {
    umap_df$cellType <- "all"
    p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
      geom_point(size = 0.6, color = "#33a02c") +
      theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
      ggtitle(paste(dataset_name, "Cells"))
  }
  
  cat("Plotting UMAP...\n")
  png(file = file.path(output_dir, paste0(dataset_name, "_1_umap_no_trajectory.png")), width = 1200, height = 1200, res = 150)
  print(p)
  dev.off()
  cat("UMAP plot saved!\n")
  
  cat(output_dir)
  quit(status = 0)
}

if (mode == "annotation_plot") {
  annotation_col <- args[5]
  
  if (!annotation_col %in% colnames(seurat_obj@meta.data)) {
    cat("ERROR: Column not found")
    quit(status = 1)
  }
  
  if (!"umap" %in% names(seurat_obj@reductions)) {
    cat("ERROR: No UMAP reduction found")
    quit(status = 1)
  }
  
  umap_df <- as.data.frame(Embeddings(seurat_obj, reduction = "umap"))
  colnames(umap_df) <- c("umap_1", "umap_2")
  umap_df$cellType <- as.factor(seurat_obj@meta.data[[annotation_col]])
  
  unique_types <- unique(umap_df$cellType)
  num_types <- length(unique_types)
  if (num_types > length(cluster_colors)) {
    type_colors <- colorRampPalette(cluster_colors)(num_types)
  } else {
    type_colors <- cluster_colors[1:num_types]
  }
  names(type_colors) <- unique_types
  
  celltypepos <- umap_df %>% group_by(cellType) %>% summarise(umap_1=median(umap_1), umap_2=median(umap_2))
  
  p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
    geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
    scale_color_manual(values = type_colors) +
    geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType), fontface = "bold", data = celltypepos, box.padding = 0.5, point.padding = 0.5, size = 6, label.size = 0.5, fill = "white", alpha = 0.75) +
    theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
    ggtitle(paste(dataset_name, annotation_col))
  
  annotation_name <- gsub("\\s|\\(|\\)", "_", annotation_col)
  png_path <- file.path(output_dir, paste0(dataset_name, "_", annotation_name, "_annotation.png"))
  png(file = png_path, width = 1200, height = 1200, res = 150)
  print(p)
  dev.off()
  
  cat(png_path)
  quit(status = 0)
}

if (mode == "stage2_filter") {
  main_col <- if (length(args) >= 5) args[5] else ""
  main_groups_str <- if (length(args) >= 6) args[6] else ""
  filter1_col <- if (length(args) >= 7) args[7] else ""
  filter1_groups_str <- if (length(args) >= 8) args[8] else ""
  filter2_col <- if (length(args) >= 9) args[9] else ""
  filter2_groups_str <- if (length(args) >= 10) args[10] else ""
  re_reduce <- if (length(args) >= 11) as.logical(args[11]) else FALSE
  dim_val <- if (length(args) >= 12) as.integer(args[12]) else 30
  plot_annotation_col <- if (length(args) >= 13) args[13] else main_col

  main_groups <- if (main_groups_str != "") unlist(strsplit(main_groups_str, ",")) else character(0)
  filter1_groups <- if (filter1_groups_str != "") unlist(strsplit(filter1_groups_str, ",")) else character(0)
  filter2_groups <- if (filter2_groups_str != "") unlist(strsplit(filter2_groups_str, ",")) else character(0)

  cat("开始筛选细胞...\n")
  cat(paste("原始细胞数: ", ncol(seurat_obj), "\n"))

  filtered_seurat <- seurat_obj

  if (main_col != "" && length(main_groups) > 0 && main_col %in% colnames(filtered_seurat@meta.data)) {
    filtered_seurat <- filtered_seurat[, filtered_seurat@meta.data[[main_col]] %in% main_groups]
    cat(paste("主注释筛选: ", main_col, " in ", paste(main_groups, collapse=", "), ", 剩余细胞数: ", ncol(filtered_seurat), "\n"))
  }

  if (filter1_col != "" && length(filter1_groups) > 0 && filter1_col %in% colnames(filtered_seurat@meta.data)) {
    filtered_seurat <- filtered_seurat[, filtered_seurat@meta.data[[filter1_col]] %in% filter1_groups]
    cat(paste("筛选条件1: ", filter1_col, " in ", paste(filter1_groups, collapse=", "), ", 剩余细胞数: ", ncol(filtered_seurat), "\n"))
  }

  if (filter2_col != "" && length(filter2_groups) > 0 && filter2_col %in% colnames(filtered_seurat@meta.data)) {
    filtered_seurat <- filtered_seurat[, filtered_seurat@meta.data[[filter2_col]] %in% filter2_groups]
    cat(paste("筛选条件2: ", filter2_col, " in ", paste(filter2_groups, collapse=", "), ", 剩余细胞数: ", ncol(filtered_seurat), "\n"))
  }

  if (ncol(filtered_seurat) == 0) {
    cat("ERROR: 筛选后无细胞")
    quit(status = 1)
  }

  if (re_reduce) {
    cat("重新降维...\n")
    filtered_seurat <- Seurat::ScaleData(filtered_seurat)
    filtered_seurat <- Seurat::RunPCA(filtered_seurat, npcs = dim_val)
    filtered_seurat <- Seurat::RunUMAP(filtered_seurat, dims = 1:dim_val)
    cat(paste("重新降维完成，使用PCA维度:", dim_val, "\n"))
  } else {
    cat("使用原始UMAP坐标\n")
  }

  filtered_path <- file.path(output_dir, paste0(dataset_name, "_filtered_seurat.rds"))
  saveRDS(filtered_seurat, filtered_path)
  cat(paste("筛选后Seurat对象已保存: ", filtered_path, "\n"))

  if (!"umap" %in% names(filtered_seurat@reductions)) {
    cat("ERROR: 筛选后的对象没有UMAP降维")
    quit(status = 1)
  }

  if (plot_annotation_col == "") {
    plot_annotation_col <- main_col
  }

  if (plot_annotation_col == "" || !(plot_annotation_col %in% colnames(filtered_seurat@meta.data))) {
    plot_annotation_col <- if ("seurat_clusters" %in% colnames(filtered_seurat@meta.data)) "seurat_clusters" else colnames(filtered_seurat@meta.data)[1]
  }

  umap_df <- as.data.frame(Embeddings(filtered_seurat, reduction = "umap"))
  colnames(umap_df) <- c("umap_1", "umap_2")
  umap_df$cellType <- as.factor(filtered_seurat@meta.data[[plot_annotation_col]])

  unique_types <- unique(umap_df$cellType)
  num_types <- length(unique_types)
  if (num_types > length(cluster_colors)) {
    type_colors <- colorRampPalette(cluster_colors)(num_types)
  } else {
    type_colors <- cluster_colors[1:num_types]
  }
  names(type_colors) <- unique_types

  celltypepos <- umap_df %>% group_by(cellType) %>% summarise(umap_1=median(umap_1), umap_2=median(umap_2))

  p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
    geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
    scale_color_manual(values = type_colors) +
    geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType), fontface = "bold", data = celltypepos, box.padding = 0.5, point.padding = 0.5, size = 6, label.size = 0.5, fill = "white", alpha = 0.75) +
    theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
    ggtitle(paste(dataset_name, "Filtered -", plot_annotation_col))

  annotation_name <- gsub("\\s|\\(|\\)", "_", plot_annotation_col)
  png_path <- file.path(output_dir, paste0(dataset_name, "_filtered_", annotation_name, "_umap.png"))
  png(file = png_path, width = 1200, height = 1200, res = 150)
  print(p)
  dev.off()

  cat(paste("筛选后细胞数: ", ncol(filtered_seurat), "\n"))
  cat(png_path)
  quit(status = 0)
}

if (mode == "stage3_cds") {
  num_dim <- if (length(args) >= 5) as.integer(args[5]) else 50
  alignment_col <- if (length(args) >= 6) args[6] else ""
  plot_annotation_col <- if (length(args) >= 7) args[7] else ""
  coord_mode <- if (length(args) >= 8) args[8] else "UMAP"

  filtered_path <- file.path(output_dir, paste0(dataset_name, "_filtered_seurat.rds"))
  if (file.exists(filtered_path)) {
    seurat_obj <- readRDS(filtered_path)
    cat(paste("已加载筛选后的Seurat对象: ", ncol(seurat_obj), " cells\n"))
  } else {
    cat("未找到筛选后的Seurat对象，使用原始数据\n")
  }

  cat("开始创建CDS对象...\n")
  cat(paste("细胞数: ", ncol(seurat_obj), "\n"))

  cds <- monocle3::new_cell_data_set(
    expression_data = SeuratObject::GetAssayData(seurat_obj, assay = "RNA", layer = "counts"),
    cell_metadata = seurat_obj@meta.data,
    gene_metadata = data.frame(gene_short_name = rownames(seurat_obj), row.names = rownames(seurat_obj))
  )
  cat("CDS对象创建完成\n")

  cds <- preprocess_cds(cds, num_dim = num_dim)
  cat(paste("数据预处理完成，num_dim:", num_dim, "\n"))

  if (alignment_col != "" && alignment_col %in% colnames(cds@colData)) {
    cds <- align_cds(cds, alignment_group = alignment_col)
    cat(paste("批次校正完成，使用:", alignment_col, "\n"))
  } else {
    cat("跳过批次校正\n")
  }

  cds <- reduce_dimension(cds, max_components = 2)
  cat("CDS降维完成\n")

  if (coord_mode == "UMAP" && "umap" %in% names(seurat_obj@reductions)) {
    cds_embed <- cds@int_colData$reducedDims$UMAP
    seurat_embed <- Embeddings(seurat_obj, reduction = "umap")
    seurat_embed <- seurat_embed[rownames(cds_embed), ]
    cds@int_colData$reducedDims$UMAP <- seurat_embed
    cat("已使用Seurat的UMAP坐标替换CDS坐标\n")
  }

  cds <- cluster_cells(cds)
  cat("细胞聚类完成\n")

  cds <- learn_graph(cds)
  cat("轨迹学习完成\n")

  cds_path <- file.path(output_dir, paste0(dataset_name, "_cds.rds"))
  saveRDS(cds, cds_path)
  cat(paste("CDS对象已保存: ", cds_path, "\n"))

  if (plot_annotation_col == "" || !(plot_annotation_col %in% colnames(cds@colData))) {
    plot_annotation_col <- if ("seurat_clusters" %in% colnames(cds@colData)) "seurat_clusters" else colnames(cds@colData)[1]
  }

  p_traj <- koyukiTraj::koyuki_trajectory_plot(cds, annotation_col = plot_annotation_col) +
    ggplot2::ggtitle(paste(dataset_name, "Trajectory -", plot_annotation_col))

  traj_png_path <- file.path(output_dir, paste0(dataset_name, "_trajectory.png"))
  png(file = traj_png_path, width = 1200, height = 1200, res = 150)
  print(p_traj)
  dev.off()
  cat(paste("Trajectory图已保存: ", traj_png_path, "\n"))

  p_partition <- koyukiTraj::koyuki_partition_plot(cds) +
    ggplot2::ggtitle(paste(dataset_name, "Partition"))

  partition_png_path <- file.path(output_dir, paste0(dataset_name, "_partition.png"))
  png(file = partition_png_path, width = 1200, height = 1200, res = 150)
  print(p_partition)
  dev.off()
  cat(paste("Partition图已保存: ", partition_png_path, "\n"))

  cat(traj_png_path, "\n")
  cat(partition_png_path)
  quit(status = 0)
}

if (mode == "stage4_pseudotime") {
  node_select_mode <- if (length(args) >= 5) args[5] else "auto"
  root_celltype <- if (length(args) >= 6) args[6] else ""

  cds_path <- file.path(output_dir, paste0(dataset_name, "_cds.rds"))
  if (!file.exists(cds_path)) {
    cat("ERROR: CDS对象未找到，请先运行阶段三\n")
    quit(status = 1)
  }

  cds <- readRDS(cds_path)
  cat("已加载CDS对象\n")

  if (node_select_mode == "manual") {
    # 设置Shiny选项：不弹出浏览器，固定端口8787
    options(shiny.launch.browser = FALSE, shiny.port = 8787)
    cat("SHINY_START:http://localhost:8787\n")
    flush.console()

    # 调用monocle3官方自带的select_trajectory_roots函数
    root_pr_nodes <- monocle3:::select_trajectory_roots(cds, reduction_method = "UMAP")
    cat(paste("已选择根节点: ", paste(root_pr_nodes, collapse=", "), "\n"))
  } else {
    graph <- monocle3::principal_graph(cds)[["UMAP"]]
    degrees <- igraph::degree(graph)
    root_pr_nodes <- names(which.max(degrees))
    cat(paste("自动选择根节点: ", root_pr_nodes, "\n"))
  }

  if (root_celltype != "" && root_celltype %in% colnames(cds@colData)) {
    cell_ids <- which(colData(cds)[, root_celltype] == root_celltype)
    closest_vertex <- cds@principal_graph_aux[["UMAP"]]$pr_graph_cell_proj_closest_vertex
    closest_vertex <- as.matrix(closest_vertex[colnames(cds), ])
    root_pr_nodes <- igraph::V(principal_graph(cds)[["UMAP"]])$name[as.numeric(names(which.max(table(closest_vertex[cell_ids,]))))]
    cat(paste("使用细胞类型", root_celltype, "确定根节点: ", root_pr_nodes, "\n"))
  }

  cds <- monocle3::order_cells(cds, root_pr_nodes = root_pr_nodes)
  cat("伪时间排序完成\n")

  assign("cds_obj", cds, envir = .GlobalEnv)

  p_pseudotime <- koyukiTraj::koyuki_pseudotime_plot(cds) +
    ggplot2::ggtitle(paste(dataset_name, "Pseudotime"))

  pseudotime_png_path <- file.path(output_dir, paste0(dataset_name, "_pseudotime.png"))
  png(file = pseudotime_png_path, width = 1200, height = 1200, res = 150)
  print(p_pseudotime)
  dev.off()
  cat(paste("Pseudotime图已保存: ", pseudotime_png_path, "\n"))

  cat(pseudotime_png_path)
  quit(status = 0)
}

if (mode == "stage1_preprocess") {
  main_col <- if (length(args) >= 5) args[5] else "Celltype (minor-lineage)"
  filter1_col <- if (length(args) >= 6) args[6] else ""
  filter1_type <- if (length(args) >= 7) args[7] else ""
  filter2_col <- if (length(args) >= 8) args[8] else ""
  filter2_type <- if (length(args) >= 9) args[9] else ""
  re_reduce <- if (length(args) >= 10) as.logical(args[10]) else FALSE
  dim_val <- if (length(args) >= 11) as.integer(args[11]) else 2
  num_dim <- if (length(args) >= 12) as.integer(args[12]) else 50
  alignment_col <- if (length(args) >= 13) args[13] else "Patient"

  if (!main_col %in% colnames(seurat_obj@meta.data)) {
    main_col <- colnames(seurat_obj@meta.data)[1]
  }

  if (filter1_col != "" && filter1_type != "" && filter1_col %in% colnames(seurat_obj@meta.data)) {
    seurat_obj <- seurat_obj[, seurat_obj@meta.data[[filter1_col]] == filter1_type]
    cat(paste("筛选1: ", filter1_col, "=", filter1_type, ", 剩余细胞数: ", ncol(seurat_obj), "\n"))
  }

  if (filter2_col != "" && filter2_type != "" && filter2_col %in% colnames(seurat_obj@meta.data)) {
    seurat_obj <- seurat_obj[, seurat_obj@meta.data[[filter2_col]] == filter2_type]
    cat(paste("筛选2: ", filter2_col, "=", filter2_type, ", 剩余细胞数: ", ncol(seurat_obj), "\n"))
  }

  cds <- monocle3::new_cell_data_set(
    expression_data = SeuratObject::GetAssayData(seurat_obj, assay = "RNA", layer = "counts"),
    cell_metadata = seurat_obj@meta.data,
    gene_metadata = data.frame(gene_short_name = rownames(seurat_obj), row.names = rownames(seurat_obj))
  )

  cds <- preprocess_cds(cds, num_dim = num_dim)
  cat("数据预处理完成\n")

  if (alignment_col %in% colnames(cds@colData)) {
    cds <- align_cds(cds, alignment_group = alignment_col)
    cat(paste("批次校正完成，使用:", alignment_col, "\n"))
  } else {
    cat("跳过批次校正（列不存在）\n")
  }

  cds <- reduce_dimension(cds, max_components = dim_val)
  cat(paste("降维完成，维度:", dim_val, "\n"))

  saveRDS(list(cds = cds, seurat_obj = seurat_obj, main_col = main_col), 
          file.path(output_dir, paste0(dataset_name, "_monocle3_stage1.rds")))
  
  cat(output_dir)
  quit(status = 0)
}

if (mode == "stage2_visualize") {
  stage1_path <- file.path(output_dir, paste0(dataset_name, "_monocle3_stage1.rds"))
  if (!file.exists(stage1_path)) {
    cat("ERROR: Stage1 output not found")
    quit(status = 1)
  }
  
  stage1_data <- readRDS(stage1_path)
  cds <- stage1_data$cds
  seurat_obj <- stage1_data$seurat_obj
  main_col <- stage1_data$main_col

  use_cds_coords <- if (length(args) >= 5) as.logical(args[5]) else FALSE

  if (!use_cds_coords && "umap" %in% names(seurat_obj@reductions)) {
    cds.embed <- cds@int_colData$reducedDims$UMAP
    int.embed <- Embeddings(seurat_obj, reduction = "umap")
    int.embed <- int.embed[rownames(cds.embed), ]
    cds@int_colData$reducedDims$UMAP <- int.embed
    cat("使用传统UMAP坐标\n")
  } else {
    cat("使用CDS降维坐标\n")
  }

  cds <- cluster_cells(cds, reduction_method = "UMAP")
  cat("细胞聚类完成\n")

  p1 <- plot_cells(
    cds,
    label_groups_by_cluster = FALSE,
    color_cells_by = main_col,
    show_trajectory_graph = FALSE,
    label_branch_points = FALSE,
    label_roots = FALSE,
    label_leaves = FALSE,
    cell_size = 0.3,
    label_cell_groups = TRUE,
    group_label_size = 4
  ) +
    theme(legend.position = "none")
  ggsave(file.path(output_dir, paste0(dataset_name, "_1_umap_no_trajectory.png")), p1, width = 10, height = 8, dpi = 300)
  cat("图1: 无轨迹UMAP图 已保存\n")

  saveRDS(cds, file.path(output_dir, paste0(dataset_name, "_monocle3_cds.rds")))
  
  cat(output_dir)
  quit(status = 0)
}

if (mode == "stage3_trajectory") {
  cds_path <- file.path(output_dir, paste0(dataset_name, "_monocle3_cds.rds"))
  if (!file.exists(cds_path)) {
    cat("ERROR: CDS not found")
    quit(status = 1)
  }
  
  cds <- readRDS(cds_path)
  stage1_path <- file.path(output_dir, paste0(dataset_name, "_monocle3_stage1.rds"))
  stage1_data <- readRDS(stage1_path)
  main_col <- stage1_data$main_col

  malignancy_column <- "Celltype (malignancy)"
  if (!malignancy_column %in% colnames(cds@colData)) {
    malignancy_column <- main_col
  }

  major_lineage_column <- "Celltype (major-lineage)"
  if (!major_lineage_column %in% colnames(cds@colData)) {
    major_lineage_column <- main_col
  }

  cds <- learn_graph(cds)
  cat("轨迹学习完成\n")

  p2 <- plot_cells(cds, color_cells_by = main_col, label_groups_by_cluster = FALSE, label_leaves = FALSE, label_branch_points = FALSE)
  ggsave(file.path(output_dir, paste0(dataset_name, "_2_trajectory_plot.png")), p2, width = 10, height = 8, dpi = 300)
  cat("图2: 轨迹图 已保存\n")

  p3 <- plot_cells(cds, color_cells_by = "partition")
  ggsave(file.path(output_dir, paste0(dataset_name, "_3_partition_plot.png")), p3, width = 10, height = 8, dpi = 300)
  cat("图3: 分区图 已保存\n")

  get_earliest_principal_node <- function(cds, celltype){
    cell_ids <- which(colData(cds)[, main_col] == celltype)
    
    if (length(cell_ids) == 0) {
      unique_types <- unique(as.character(colData(cds)[, main_col]))
      if (length(unique_types) > 0) {
        celltype <- unique_types[1]
        cell_ids <- which(colData(cds)[, main_col] == celltype)
      }
    }
    
    if (length(cell_ids) == 0) {
      return(igraph::V(principal_graph(cds)[["UMAP"]])$name[1])
    }
    
    closest_vertex <-
      cds@principal_graph_aux[["UMAP"]]$pr_graph_cell_proj_closest_vertex
    closest_vertex <- as.matrix(closest_vertex[colnames(cds), ])
    root_pr_nodes <-
      igraph::V(principal_graph(cds)[["UMAP"]])$name[as.numeric(names
                                                                (which.max(table(closest_vertex[cell_ids,]))))]
    
    root_pr_nodes
  }

  root_nodes <- get_earliest_principal_node(cds)

  cds <- order_cells(cds, root_pr_nodes = root_nodes)

  p4 <- plot_cells(cds, color_cells_by = "pseudotime")
  ggsave(file.path(output_dir, paste0(dataset_name, "_4_pseudotime_plot.png")), p4, width = 10, height = 8, dpi = 300)
  cat("图4: 伪时间图 已保存\n")

  p5 <- plot_cells(cds, color_cells_by = malignancy_column, label_groups_by_cluster = FALSE, label_leaves = FALSE, label_branch_points = FALSE)
  ggsave(file.path(output_dir, paste0(dataset_name, "_5_celltype_malignancy.png")), p5, width = 10, height = 8, dpi = 300)
  cat("图5: 按malignancy着色的轨迹图 已保存\n")

  p6 <- plot_cells(cds, color_cells_by = major_lineage_column, label_groups_by_cluster = FALSE, label_leaves = FALSE, label_branch_points = FALSE)
  ggsave(file.path(output_dir, paste0(dataset_name, "_6_celltype_major_lineage.png")), p6, width = 10, height = 8, dpi = 300)
  cat("图6: 按major-lineage着色的轨迹图 已保存\n")

  saveRDS(cds, file.path(output_dir, paste0(dataset_name, "_monocle3_cds.rds")))
  
  cat(output_dir)
  quit(status = 0)
}

if (mode == "stage4_graph_test") {
  cds_path <- file.path(output_dir, paste0(dataset_name, "_monocle3_cds.rds"))
  if (!file.exists(cds_path)) {
    cat("ERROR: CDS not found")
    quit(status = 1)
  }
  
  cds <- readRDS(cds_path)

  cat("Running graph_test...\n")
  genes <- monocle3::graph_test(cds, neighbor_graph = "principal_graph", reduction_method = "UMAP", cores = 1)
  
  write.csv(genes, file.path(output_dir, paste0(dataset_name, "_differential_genes.csv")))
  
  top50 <- genes %>%
    top_n(n = 50, morans_I) %>%
    pull(gene_short_name) %>%
    as.character()
  
  cat(paste(top50, collapse = "\t"))
  quit(status = 0)
}

if (mode == "gene_pseudotime") {
  gene_name <- args[5]
  
  cds_path <- file.path(output_dir, paste0(dataset_name, "_monocle3_cds.rds"))
  if (!file.exists(cds_path)) {
    cat("ERROR: CDS not found")
    quit(status = 1)
  }
  
  cds <- readRDS(cds_path)
  stage1_path <- file.path(output_dir, paste0(dataset_name, "_monocle3_stage1.rds"))
  stage1_data <- readRDS(stage1_path)
  main_col <- stage1_data$main_col

  colData(cds)$celltype_for_plot <- colData(cds)[, main_col]

  if (gene_name %in% rownames(cds)) {
    p7 <- plot_genes_in_pseudotime(cds[rowData(cds)$gene_short_name %in% gene_name, ],
                                   color_cells_by="celltype_for_plot",
                                   min_expr=0.5)
    ggsave(file.path(output_dir, paste0(dataset_name, "_", gene_name, "_pseudotime_celltype.png")), p7, width = 10, height = 8, dpi = 300)
    
    p8 <- plot_genes_in_pseudotime(cds[rowData(cds)$gene_short_name %in% gene_name, ],
                                   color_cells_by = "pseudotime",
                                   min_expr = 0.1)
    ggsave(file.path(output_dir, paste0(dataset_name, "_", gene_name, "_pseudotime_color.png")), p8, width = 10, height = 8, dpi = 300)
    
    cat("SUCCESS")
  } else {
    cat("GENE_NOT_FOUND")
  }
  quit(status = 0)
}

cat("Unknown mode:", mode)
quit(status = 1)
