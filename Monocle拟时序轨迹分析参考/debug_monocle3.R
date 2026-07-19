library(monocle3)
library(Seurat)
library(dplyr)
library(ggplot2)

output_dir <- file.path(getwd(), "monocle3_output")
dir.create(output_dir, showWarnings = FALSE)

rds_path <- file.path(getwd(), "GSE84465seurat_obj_with_anno.rds")

if (!file.exists(rds_path)) {
  stop(paste("找不到RDS文件:", rds_path))
}

cat("RDS文件路径:", rds_path, "\n")

seurat_obj <- readRDS(rds_path)
cat("Seurat对象加载成功\n")
cat("细胞数:", ncol(seurat_obj), "\n")
cat("基因数:", nrow(seurat_obj), "\n")
cat("元数据列:", colnames(seurat_obj@meta.data), "\n")

cds <- monocle3::new_cell_data_set(
  expression_data = SeuratObject::GetAssayData(seurat_obj, assay = "RNA", layer = "counts"),
  cell_metadata = seurat_obj@meta.data,
  gene_metadata = data.frame(gene_short_name = rownames(seurat_obj), row.names = rownames(seurat_obj))
)
cat("CDS对象创建成功\n")

cds <- preprocess_cds(cds, num_dim = 50)
cat("数据预处理完成\n")

cds <- align_cds(cds, alignment_group = "Patient")
cat("批次校正完成\n")

cds <- reduce_dimension(cds)
cat("降维完成\n")

cds.embed <- cds@int_colData$reducedDims$UMAP
int.embed <- Embeddings(seurat_obj, reduction = "umap")
int.embed <- int.embed[rownames(cds.embed), ]
cds@int_colData$reducedDims$UMAP <- int.embed
cat("UMAP替换完成\n")

cds <- cluster_cells(cds, reduction_method = "UMAP")
cat("细胞聚类完成\n")

colors <- c('#E59CC4', '#90EE90', '#F1BB72', '#F3B1A0', '#D6E7A3', '#57C3F3','#0FA3A8',
            '#E95C59', '#E5D2DD', '#AB3282', '#33452F', '#BD956A', '#8C549C', '#585658',
            '#476D87', '#E0D4CA', '#5F3D69', '#C5DEBA', '#58A4C3', '#E4C755', '#F7F398',
            '#AA9A59', '#E63863', '#E39A35', '#C1E6F3', '#6778AE', '#91D0BE', '#B53E2B',
            '#712820', '#DCC1DD', '#CCE0F5', '#CCC9E6', '#625D9E', '#68A180', '#968175')

p1 <- plot_cells(
  cds,
  label_groups_by_cluster = FALSE,
  color_cells_by = "Celltype (minor-lineage)",
  show_trajectory_graph = FALSE,
  label_branch_points = FALSE,
  label_roots = FALSE,
  label_leaves = FALSE,
  cell_size = 0.3,
  label_cell_groups = TRUE,
  group_label_size = 4
) +
  theme(legend.position = "none")
ggsave(file.path(output_dir, "1_umap_no_trajectory.png"), p1, width = 10, height = 8, dpi = 300)
cat("图1: 无轨迹UMAP图 已保存\n")

cds <- learn_graph(cds)
cat("轨迹学习完成\n")

p2 <- plot_cells(cds, color_cells_by = "Celltype (minor-lineage)", label_groups_by_cluster = FALSE, label_leaves = FALSE, label_branch_points = FALSE)
ggsave(file.path(output_dir, "2_trajectory_plot.png"), p2, width = 10, height = 8, dpi = 300)
cat("图2: 轨迹图 已保存\n")

p3 <- plot_cells(cds, color_cells_by = "partition")
ggsave(file.path(output_dir, "3_partition_plot.png"), p3, width = 10, height = 8, dpi = 300)
cat("图3: 分区图 已保存\n")

get_earliest_principal_node <- function(cds, celltype="OPC"){
  cell_ids <- which(colData(cds)[, "Celltype (minor-lineage)"] == celltype)
  
  closest_vertex <-
    cds@principal_graph_aux[["UMAP"]]$pr_graph_cell_proj_closest_vertex
  closest_vertex <- as.matrix(closest_vertex[colnames(cds), ])
  root_pr_nodes <-
    igraph::V(principal_graph(cds)[["UMAP"]])$name[as.numeric(names
                                                              (which.max(table(closest_vertex[cell_ids,]))))]
  
  root_pr_nodes
}

root_nodes <- get_earliest_principal_node(cds, "OPC")
cat("根节点:", root_nodes, "\n")

cds <- order_cells(cds, root_pr_nodes = root_nodes)
cat("细胞排序完成\n")

p4 <- plot_cells(cds, color_cells_by = "pseudotime")
ggsave(file.path(output_dir, "4_pseudotime_plot.png"), p4, width = 10, height = 8, dpi = 300)
cat("图4: 伪时间图 已保存\n")

p5 <- plot_cells(cds, color_cells_by = "Celltype (malignancy)", label_groups_by_cluster = FALSE, label_leaves = FALSE, label_branch_points = FALSE)
ggsave(file.path(output_dir, "5_celltype_malignancy.png"), p5, width = 10, height = 8, dpi = 300)
cat("图5: 按malignancy着色的轨迹图 已保存\n")

p6 <- plot_cells(cds, color_cells_by = "Celltype (major-lineage)", label_groups_by_cluster = FALSE, label_leaves = FALSE, label_branch_points = FALSE)
ggsave(file.path(output_dir, "6_celltype_major_lineage.png"), p6, width = 10, height = 8, dpi = 300)
cat("图6: 按major-lineage着色的轨迹图 已保存\n")

cat("\n开始graph_test差异基因检测（可能需要较长时间）...\n")
genes <- monocle3::graph_test(cds, neighbor_graph = "principal_graph", reduction_method = "UMAP", cores = 1)
top10 <- genes %>%
  top_n(n = 10, morans_I) %>%
  pull(gene_short_name) %>%
  as.character()
cat("差异基因检测完成，Top10基因:", top10, "\n")

write.csv(genes, file.path(output_dir, "differential_genes.csv"))
cat("差异基因列表已保存到 differential_genes.csv\n")

top50 <- genes %>%
  top_n(n = 50, morans_I) %>%
  pull(gene_short_name) %>%
  as.character()
cat("Top50差异基因:", top50, "\n")

target_genes <- c("APOD")
if ("APOD" %in% rownames(cds)) {
  colData(cds)$celltype_for_plot <- colData(cds)[, "Celltype (minor-lineage)"]
  
  p7 <- plot_genes_in_pseudotime(cds[rowData(cds)$gene_short_name %in% target_genes, ],
                                 color_cells_by="celltype_for_plot",
                                 min_expr=0.5)
  ggsave(file.path(output_dir, "7_gene_pseudotime_celltype.png"), p7, width = 10, height = 8, dpi = 300)
  cat("图7: APOD基因伪时间图(按细胞类型着色) 已保存\n")
  
  p8 <- plot_genes_in_pseudotime(cds[rowData(cds)$gene_short_name %in% target_genes, ],
                                 color_cells_by = "pseudotime",
                                 min_expr = 0.1)
  ggsave(file.path(output_dir, "8_gene_pseudotime_color.png"), p8, width = 10, height = 8, dpi = 300)
  cat("图8: APOD基因伪时间图(按伪时间着色) 已保存\n")
} else {
  cat("APOD基因不在数据集中，跳过基因伪时间图\n")
}

saveRDS(cds, file.path(output_dir, "monocle3_cds.rds"))
cat("CDS对象已保存\n")

cat("\n所有出图完成！输出目录:", output_dir, "\n")
