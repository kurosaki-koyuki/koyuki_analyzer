library(monocle3)
library(Seurat)
library(dplyr)
library(ggplot2)
seurat_obj<-readRDS("GSE84465seurat_obj_with_anno.rds")
# seurat_obj是之前注释好的Seurat 对象
cds <- monocle3::new_cell_data_set(
  expression_data = SeuratObject::GetAssayData(seurat_obj, assay = "RNA", layer = "counts"),
  cell_metadata = seurat_obj@meta.data,
  gene_metadata = data.frame(gene_short_name = rownames(seurat_obj), row.names = rownames(seurat_obj))
)
colnames(colData(cds))
#预处理步骤与聚类分析完全相同，包括数据标准化和批次效应校正等。在批次校正中，可以使用align_cds()函数，并通过alignment_group指定批次分组
# 数据预处理
cds <- preprocess_cds(cds, num_dim = 50)
# 批次校正
cds <- align_cds(cds, alignment_group = "Patient")
# 降维，接下来进行数据降维，对于轨迹分析，强烈建议使用UMAP方法（默认方法）。降维后可以使用plot_cells()函数可视化结果，通过不同的颜色编码展示细胞类型等信息。
cds <- reduce_dimension(cds)

#用 Seurat 对象中的 UMAP 替换 CDS 中的
cds.embed <- cds@int_colData$reducedDims$UMAP
int.embed <- Embeddings(seurat_obj, reduction = "umap")
int.embed <- int.embed[rownames(cds.embed), ]
cds@int_colData$reducedDims$UMAP <- int.embed




# 细胞聚类
cds <- cluster_cells(cds)

cds <- cluster_cells(
  cds,
  reduction_method = "PCA",  # 关键！
  k = 20,
  resolution = 1e-3
)
#定义一片颜色（后续会有大用！）
colors <- c('#E59CC4', '#90EE90', '#F1BB72', '#F3B1A0', '#D6E7A3', '#57C3F3','#0FA3A8',
            '#E95C59', '#E5D2DD', '#AB3282', '#33452F', '#BD956A', '#8C549C', '#585658',
            '#476D87', '#E0D4CA', '#5F3D69', '#C5DEBA', '#58A4C3', '#E4C755', '#F7F398',
            '#AA9A59', '#E63863', '#E39A35', '#C1E6F3', '#6778AE', '#91D0BE', '#B53E2B',
            '#712820', '#DCC1DD', '#CCE0F5', '#CCC9E6', '#625D9E', '#68A180', '#968175')


#第一张图：无轨迹 UMAP 图
plot_cells(
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





# 学习轨迹
cds <- learn_graph(cds)

# 第二张图：可视化轨迹图
plot_cells(cds, color_cells_by = "Celltype (minor-lineage)", label_groups_by_cluster = FALSE, label_leaves = FALSE, label_branch_points = FALSE)




# 按分区可视化
plot_cells(cds, color_cells_by = "partition")

#手选轨迹图（按伪时间排序细胞）
cds <- order_cells(cds)
#什么是伪时间？ 伪时间是一个抽象的进展单位，它表示细胞沿着学习到的轨迹从起始状态到结束状态所经历的距离。在许多生物学过程中，细胞的发育并不同步，伪时间很好地解决了这种不同步发育带来的分析难题。
#在排序过程中，需要指定轨迹图的根节点（root nodes）
#可以通过图形界面手动选择，也可以通过编程方式指定。例如，可根据最早时间点的细胞分布来自动确定根节点

# 按伪时间可视化
plot_cells(cds, color_cells_by = "pseudotime")

cds <- reduce_dimension(cds, reduction_method = "UMAP")
cds <- learn_graph(cds, reduction_method = "UMAP")
colnames(colData(cds))
#下边这个函数可以帮助我们选择发育起点，比如我们可以修改为从某一类细胞发育作为 root，"Celltype (minor-lineage)"为你想要的注释
#"OPC"为你想要设定的最早演化的那个细胞类型
# 编程方式指定根节点
get_earliest_principal_node <- function(cds, time_bin="130-170"){
  cell_ids <- which(colData(cds)[, "Celltype (minor-lineage)"] == "OPC")
  
  closest_vertex <-
    cds@principal_graph_aux[["UMAP"]]$pr_graph_cell_proj_closest_vertex
  closest_vertex <- as.matrix(closest_vertex[colnames(cds), ])
  root_pr_nodes <-
    igraph::V(principal_graph(cds)[["UMAP"]])$name[as.numeric(names
                                                              (which.max(table(closest_vertex[cell_ids,]))))]
  
  root_pr_nodes
}
cds <- order_cells(cds, root_pr_nodes = get_earliest_principal_node(cds))
#看机器计算的结果（如果你的降维聚类太碎，会找不着连接点，这个时候就得考虑连在一起（dim值调低之类的））
plot_cells(cds, color_cells_by = "pseudotime")



#寻找随着伪时间变化或在不同分支中表达发生变化的基因，下面找的是前10个，
genes <- monocle3::graph_test(cds, neighbor_graph = "principal_graph", reduction_method = "UMAP", cores = 32)
top10 <- genes %>%
  top_n(n = 10, morans_I) %>%
  pull(gene_short_name) %>%
  as.character()

#展示目的基因随时间变化图
target_genes <- c("APOD")
target_celltype <- "AC-like Malignant"
target_lineage_cds <- cds[rowData(cds)$gene_short_name %in% target_genes, ]

target_lineage_cds <- cds[rowData(cds)$gene_short_name %in% target_genes,
                          colData(cds)[["Celltype (minor-lineage)"]] %in% c("OPC")]
target_lineage_cds <- order_cells(target_lineage_cds)

plot_genes_in_pseudotime(target_lineage_cds,
                         color_cells_by="Celltype (minor-lineage)",
                         min_expr=0.5)
plot_genes_in_pseudotime(target_lineage_cds,
                         color_cells_by = "pseudotime",  # 把原来的Celltype列换成伪时间，完全避开列名问题
                         min_expr = 0.1)  # 把0.5调低，避免APOD表达量低画不出点












#暂时无法实现的代码部分
top50 <- genes %>%
  top_n(n = 50, morans_I) %>%
  pull(gene_short_name) %>%
  as.character()
#存个列表
mat <- SingleCellExperiment::counts(cds, normalized = TRUE)

# 2. 只保留你筛选的top50基因
mat <- mat[rownames(mat) %in% top50, ]



library(ClusterGVis)
# kmeans
ck <- clusterData(mat,
                  cluster.method = "kmeans",
                  cluster.num = 5)


# add line annotation
pdf('monocle3.pdf',height = 10,width = 8,onefile = F)
visCluster(object = ck,
           plot.type = "both",
           add.sampleanno = F,
           markGenes = sample(rownames(mat),30,replace = F))
dev.off()