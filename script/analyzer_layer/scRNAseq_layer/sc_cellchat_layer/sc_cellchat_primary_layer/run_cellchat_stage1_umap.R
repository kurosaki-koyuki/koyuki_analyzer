# CellChat初步分析 - 阶段一：按注释列生成UMAP图
# 参考Monocle的R脚本风格

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 3) {
  cat("Usage: Rscript run_cellchat_stage1_umap.R <seurat_path> <annotation_col> <output_path>\n")
  quit(status = 1)
}

seurat_path <- args[1]
annotation_col <- args[2]
output_path <- args[3]

cat(paste("读取Seurat对象:", seurat_path, "\n"))

if (!file.exists(seurat_path)) {
  cat(paste("ERROR: 文件不存在:", seurat_path, "\n"))
  quit(status = 1)
}

# 加载所需包
suppressPackageStartupMessages({
  library(Seurat)
  library(SeuratObject)
  library(ggplot2)
  library(dplyr)
  library(grid)
  library(ggrepel)
  library(tidydr)
})

cat("读取Seurat对象...\n")
seurat_obj <- readRDS(seurat_path)

cat(paste("Seurat对象加载成功: ", ncol(seurat_obj), " cells, ", nrow(seurat_obj), " genes\n"))

# 检查UMAP降维是否存在
if (!"umap" %in% names(seurat_obj@reductions)) {
  cat("ERROR: Seurat对象没有UMAP降维\n")
  cat("可用的降维: ", paste(names(seurat_obj@reductions), collapse = ", "), "\n")
  quit(status = 1)
}

# 检查注释列是否存在
if (!annotation_col %in% colnames(seurat_obj@meta.data)) {
  cat(paste("ERROR: 注释列", annotation_col, "不存在\n"))
  cat("可用的列:", paste(colnames(seurat_obj@meta.data), collapse = ", "), "\n")
  quit(status = 1)
}

cat(paste("使用注释列:", annotation_col, "\n"))

# 提取UMAP坐标
cat("提取UMAP坐标...\n")
umap_df <- as.data.frame(Embeddings(seurat_obj, reduction = "umap"))
colnames(umap_df) <- c("umap_1", "umap_2")

# 添加注释信息
umap_df$cellType <- as.factor(seurat_obj@meta.data[[annotation_col]])

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

# 绘制UMAP图
cat("生成UMAP图...\n")

# 转义注释列名用于文件名
annotation_name <- gsub("\\s|\\(|\\)|/", "_", annotation_col)

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
  ggtitle(paste("UMAP -", annotation_col))

# 保存图片
dir.create(dirname(output_path), showWarnings = FALSE, recursive = TRUE)

png(file = output_path, width = 1200, height = 1200, res = 150)
print(p)
dev.off()

cat(paste("图片已保存:", output_path, "\n"))
cat("SUCCESS\n")
quit(status = 0)
