# sc_hdwgcna分析 R脚本
# 使用hdWGCNA包进行单细胞加权基因共表达网络分析
#
# 阶段架构：
# 阶段一：STAGE1 - 加载Seurat对象+基因选择+重新降维
# 阶段二：STAGE2 - SetupForWGCNA+Metacell构建
# 阶段三：STAGE3 - 软阈值选择
# 阶段四：STAGE4 - 网络构建(ConstructNetwork)
# 阶段五：STAGE5 - 模块可视化(Dendrogram+KMEs)
# 阶段六：STAGE6 - 模块特征图(hMEs)
# 阶段七：STAGE7 - 模块相关图(Correlogram+DotPlot)
# 阶段八：STAGE8 - ModuleUMAP
# 阶段九：STAGE9 - Enrichr富集分析
# 阶段十：STAGE10 - 导出基因集合

# 参数列表（从全局环境获取）：
# - seurat_path: Seurat对象rds文件路径
# - output_dir: 输出目录
# - analyze_group: 分析分组列名（细胞类型列）
# - sample_group: 样本列名
# - target_cell_type: 目标细胞类型名称
# - gene_select_mode: 基因选择模式（fraction, custom, variable）
# - fraction_value: fraction模式的比例值
# - variable_gene_count: 高变基因数量
# - custom_gene_list_path: 自定义基因列表路径
# - network_type: 网络类型，默认"unsigned"
# - soft_power: 软阈值power值
# - k: Metacell近邻数
# - max_shared: metacell共享细胞数
# - min_cells: 最小细胞数
# - min_module_size: 最小模块大小

# ========================================
# 阶段一：加载Seurat对象+数据准备+重新降维
# ========================================
# --- STAGE1_BODY_START ---

output_dir_val <- as.character(output_dir)[1]
seurat_path_val <- as.character(seurat_path)[1]
analyze_group_val <- if (exists('analyze_group')) as.character(analyze_group)[1] else "Celltype (major-lineage)"
sample_group_val <- if (exists('sample_group')) as.character(sample_group)[1] else "Sample"
target_cell_type_val <- if (exists('target_cell_type')) as.character(target_cell_type)[1] else NULL
gene_select_mode_val <- if (exists('gene_select_mode')) as.character(gene_select_mode)[1] else "fraction"
fraction_value_val <- if (exists('fraction_value')) as.numeric(fraction_value)[1] else 0.05
variable_gene_count_val <- if (exists('variable_gene_count')) as.integer(variable_gene_count)[1] else 3000
custom_gene_list_path_val <- if (exists('custom_gene_list_path')) as.character(custom_gene_list_path)[1] else NULL
recluster_val <- if (exists('recluster')) as.logical(recluster)[1] else TRUE
dims_val <- if (exists('dims')) as.integer(dims)[1] else 30
filter_enabled_val <- if (exists('filter_enabled')) as.logical(filter_enabled)[1] else FALSE
filter_col_val <- if (exists('filter_col')) as.character(filter_col)[1] else NULL
filter_groups_val <- if (exists('filter_groups')) as.character(filter_groups) else NULL
plot_width_val <- if (exists('plot_width')) as.integer(plot_width)[1] else 1200
plot_height_val <- if (exists('plot_height')) as.integer(plot_height)[1] else 800

cat("阶段一：加载Seurat对象+基因选择+重新降维\n")
cat("Seurat文件路径: ", seurat_path_val, "\n")
cat("输出目录: ", output_dir_val, "\n")
cat("分析分组列: ", analyze_group_val, "\n")
cat("样本列: ", sample_group_val, "\n")
cat("基因选择模式: ", gene_select_mode_val, "\n")
if (gene_select_mode_val == "fraction") {
  cat("fraction值: ", fraction_value_val, "\n")
} else if (gene_select_mode_val == "variable") {
  cat("高变基因数量: ", variable_gene_count_val, "\n")
} else if (gene_select_mode_val == "custom") {
  cat("自定义基因列表: ", custom_gene_list_path_val, "\n")
}
if (!is.null(target_cell_type_val)) {
  cat("目标细胞类型: ", target_cell_type_val, "\n")
}

if (!file.exists(seurat_path_val)) {
  stop(paste("Seurat文件不存在: ", seurat_path_val))
}

scRNA <- readRDS(seurat_path_val)
cat(paste0("Seurat对象加载成功！细胞数: ", ncol(scRNA), ", 基因数: ", nrow(scRNA), "\n"))

cat("使用RNA assay的data层（logNormalized数据）\n")
DefaultAssay(scRNA) <- "RNA"
cat("当前assay: ", DefaultAssay(scRNA), "\n")

cat("检查分析分组列...\n")
if (!analyze_group_val %in% colnames(scRNA@meta.data)) {
  stop(paste("分析分组列不存在: ", analyze_group_val))
}
analyze_col_values <- scRNA@meta.data[[analyze_group_val]]
if (is.data.frame(analyze_col_values)) {
  analyze_col_values <- analyze_col_values[[1]]
}
cat("分析分组类别:\n")
print(table(analyze_col_values))

cat("检查样本列...\n")
if (!sample_group_val %in% colnames(scRNA@meta.data)) {
  stop(paste("样本列不存在: ", sample_group_val))
}

original_cell_count <- ncol(scRNA)

if (!is.null(target_cell_type_val) && target_cell_type_val != "" && target_cell_type_val != "全部") {
  cat("筛选目标细胞类型...\n")
  cell_types <- unique(as.character(analyze_col_values))
  cat("可用类型: ", paste(cell_types, collapse=", "), "\n")
  if (!target_cell_type_val %in% cell_types) {
    stop(paste("目标细胞类型不存在: ", target_cell_type_val, "\n可用类型: ", paste(cell_types, collapse=", ")))
  }
  scRNA <- scRNA[, as.character(analyze_col_values) == target_cell_type_val]
  cat(paste0("筛选后细胞数: ", ncol(scRNA), "\n"))
  
  if (recluster_val) {
    cat("重新运行PCA降维...\n")
    scRNA <- RunPCA(scRNA, npcs = 50, verbose = FALSE)
    cat("PCA完成！\n")
    
    cat("重新运行UMAP降维...\n")
    scRNA <- RunUMAP(scRNA, dims = 1:dims_val, verbose = FALSE)
    cat("UMAP完成！\n")
  } else {
    cat("跳过重新降维\n")
  }
}

if (filter_enabled_val && !is.null(filter_col_val) && !is.null(filter_groups_val) && length(filter_groups_val) > 0) {
  cat("应用筛选条件...\n")
  cat("筛选列: ", filter_col_val, "\n")
  cat("筛选组别: ", paste(filter_groups_val, collapse=", "), "\n")
  
  if (!filter_col_val %in% colnames(scRNA@meta.data)) {
    stop(paste("筛选列不存在: ", filter_col_val))
  }
  
  filter_col_values <- scRNA@meta.data[[filter_col_val]]
  scRNA <- scRNA[, as.character(filter_col_values) %in% filter_groups_val]
  cat(paste0("筛选后细胞数: ", ncol(scRNA), "\n"))
}

set.seed(12345)

cat("选择基因用于分析...\n")
all_genes <- rownames(scRNA)
total_genes <- length(all_genes)

if (gene_select_mode_val == "fraction") {
  cat(paste0("使用fraction模式: ", fraction_value_val, "\n"))
  n_select <- ceiling(total_genes * fraction_value_val)
  gene_list <- sample(all_genes, n_select)
  cat(paste0("选择基因数: ", length(gene_list), " (", round(length(gene_list)/total_genes*100, 1), "%)\n"))
  
} else if (gene_select_mode_val == "custom") {
  cat("使用custom模式: 自定义基因列表\n")
  if (is.null(custom_gene_list_path_val) || !file.exists(custom_gene_list_path_val)) {
    stop(paste("自定义基因列表文件不存在: ", custom_gene_list_path_val))
  }
  
  library(readxl)
  custom_genes <- read_excel(custom_gene_list_path_val, col_names = FALSE)
  custom_genes <- as.character(custom_genes[[1]])
  cat(paste0("基因列表中基因数: ", length(custom_genes), "\n"))
  
  gene_list <- intersect(custom_genes, all_genes)
  cat(paste0("匹配到的基因数: ", length(gene_list), "\n"))
  
  if (length(gene_list) < 10) {
    stop("匹配到的基因数量太少（<10），请检查基因列表")
  }
  
} else if (gene_select_mode_val == "variable") {
  cat(paste0("使用高变基因模式: ", variable_gene_count_val, "个\n"))
  
  scRNA <- FindVariableFeatures(scRNA, nfeatures = variable_gene_count_val, verbose = FALSE)
  gene_list <- VariableFeatures(scRNA)
  cat(paste0("高变基因数: ", length(gene_list), "\n"))
  
} else {
  cat("未知基因选择模式，使用全部基因\n")
  gene_list <- all_genes
}

scRNA <- scRNA[gene_list, ]
cat(paste0("最终分析基因数: ", nrow(scRNA), "\n"))

sc_hdwgcna_seurat <<- scRNA
sc_hdwgcna_analyze_group <<- analyze_group_val
sc_hdwgcna_sample_group <<- sample_group_val
sc_hdwgcna_target_cell_type <<- target_cell_type_val

cat("生成UMAP图...\n")
umap_path <- file.path(output_dir_val, "umap_plot.png")
if ('umap' %in% names(scRNA@reductions)) {
  umap_coords <- Embeddings(scRNA, reduction = "umap")
  umap_df <- as.data.frame(umap_coords)
  umap_df$cell_type <- scRNA@meta.data[[analyze_group_val]]
  
  png(umap_path, width = plot_width_val, height = plot_height_val, res = 100)
  p <- ggplot(umap_df, aes(x = umap_1, y = umap_2, color = cell_type)) +
    geom_point(size = 0.8, alpha = 0.8) +
    ggtitle("UMAP - Cell Type Distribution") +
    xlab("UMAP 1") +
    ylab("UMAP 2") +
    theme_bw() +
    theme(
      plot.title = element_text(hjust = 0.5, size = 16, face = "bold"),
      legend.title = element_text(size = 12, face = "bold"),
      legend.text = element_text(size = 10),
      axis.title.x = element_text(size = 12, face = "bold", color = "black"),
      axis.title.y = element_text(size = 12, face = "bold", color = "black"),
      axis.text.x = element_text(size = 10, color = "black"),
      axis.text.y = element_text(size = 10, color = "black"),
      panel.border = element_rect(color = "black", size = 1)
    )
  print(p)
  dev.off()
  cat("UMAP图已保存\n")
} else {
  cat("Seurat对象没有UMAP降维结果\n")
}

stage1_result <- paste0("阶段一完成：\n")
stage1_result <- paste0(stage1_result, "  原始细胞数: ", original_cell_count, "\n")
stage1_result <- paste0(stage1_result, "  当前细胞数: ", ncol(scRNA), "\n")
stage1_result <- paste0(stage1_result, "  基因数: ", nrow(scRNA), "\n")
stage1_result <- paste0(stage1_result, "  分析分组列: ", analyze_group_val, "\n")
stage1_result <- paste0(stage1_result, "  样本列: ", sample_group_val, "\n")
if (!is.null(target_cell_type_val)) {
  stage1_result <- paste0(stage1_result, "  目标细胞类型: ", target_cell_type_val, "\n")
}
sc_hdwgcna_stage1_result <<- stage1_result

cat("阶段一完成: Seurat对象已加载\n")

# --- STAGE1_BODY_END ---


# ========================================
# 阶段二：SetupForWGCNA+Metacell构建
# ========================================
# --- STAGE2_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat')) {
  stop("请先运行阶段一")
}

cat("阶段二：SetupForWGCNA+Metacell构建\n")

scRNA <- sc_hdwgcna_seurat

cat("创建干净的注释列...\n")
scRNA@meta.data[['wgcna_type_fixed_analyze']] <- as.factor(scRNA@meta.data[[sc_hdwgcna_analyze_group]])
scRNA@meta.data[['wgcna_type_fixed_sample']] <- as.factor(scRNA@meta.data[[sc_hdwgcna_sample_group]])

cat("运行SetupForWGCNA...\n")
seurat_obj <- SetupForWGCNA(
  scRNA,
  gene_select = "all",
  wgcna_name = "sc_hdwgcna_test",
  assay = "RNA"
)
cat("SetupForWGCNA成功！\n")

wgcna_genes <- GetWGCNAGenes(seurat_obj)
cat(paste0("WGCNA基因数: ", length(wgcna_genes), "\n"))

cat("运行Harmony...\n")
seurat_obj <- RunHarmony(
  object = seurat_obj,
  group.by.vars = "wgcna_type_fixed_sample",
  reduction.use = "pca",
  reduction.save = "harmony",
  dims.use = 1:ncol(Embeddings(seurat_obj, "pca")),
  verbose = F
)
cat("Harmony运行成功！\n")
cat("Reductions: ", paste(names(seurat_obj@reductions), collapse=", "), "\n")

k_val <- if (exists('k')) as.integer(k)[1] else 25
max_shared_val <- if (exists('max_shared')) as.integer(max_shared)[1] else 10
min_cells_val <- if (exists('min_cells')) as.integer(min_cells)[1] else 80

cat(paste0("Metacell参数: k=", k_val, ", max_shared=", max_shared_val, ", min_cells=", min_cells_val, "\n"))

cat("运行MetacellsByGroups...\n")
seurat_obj <- MetacellsByGroups(
  seurat_obj = seurat_obj,
  group.by = "wgcna_type_fixed_analyze",
  reduction = 'harmony',
  k = k_val,
  max_shared = max_shared_val,
  ident.group = "wgcna_type_fixed_analyze",
  min_cells = min_cells_val
)
cat("MetacellsByGroups成功！\n")

cat("运行NormalizeMetacells...\n")
seurat_obj <- NormalizeMetacells(seurat_obj)
cat("NormalizeMetacells成功！\n")

sc_hdwgcna_seurat_obj <<- seurat_obj

stage2_result <- paste0("阶段二完成：\n")
stage2_result <- paste0(stage2_result, "  Metacell参数: k=", k_val, ", max_shared=", max_shared_val, ", min_cells=", min_cells_val, "\n")
stage2_result <- paste0(stage2_result, "  Metacell构建成功\n")
sc_hdwgcna_stage2_result <<- stage2_result

cat("阶段二完成: Metacell构建完成\n")

# --- STAGE2_BODY_END ---


# ========================================
# 阶段三：设置表达矩阵+软阈值选择
# ========================================
# --- STAGE3_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段二")
}

cat("阶段三：设置表达矩阵+软阈值选择\n")

seurat_obj <- sc_hdwgcna_seurat_obj

target_cell_type_val <- if (!is.null(sc_hdwgcna_target_cell_type) && sc_hdwgcna_target_cell_type != "" && sc_hdwgcna_target_cell_type != "全部") {
  sc_hdwgcna_target_cell_type
} else {
  levels(as.factor(seurat_obj@meta.data[["wgcna_type_fixed_analyze"]]))[1]
}
cat("目标细胞类型: ", target_cell_type_val, "\n")

cat("运行SetDatExpr...\n")
seurat_obj <- SetDatExpr(
  seurat_obj,
  group_name = target_cell_type_val,
  group.by = "wgcna_type_fixed_analyze",
  assay = 'RNA',
  slot = 'data'
)
datExpr <- GetDatExpr(seurat_obj)
cat(paste0("分析基因数: ", nrow(datExpr), "\n"))

network_type_val <- if (exists('network_type')) as.character(network_type)[1] else "signed"
cat("网络类型: ", network_type_val, "\n")

cat("运行TestSoftPowers...\n")
tryCatch({
  seurat_obj <- TestSoftPowers(
    seurat_obj,
    powers = c(seq(1, 10, by = 1), seq(12, 20, by = 2)),
    networkType = network_type_val
  )
  cat("TestSoftPowers成功！\n")
}, error = function(e) {
  cat(paste0("TestSoftPowers错误: ", e$message, "\n"))
  stop(paste0("TestSoftPowers失败: ", e$message))
})

power_table <- GetPowerTable(seurat_obj)
cat("软阈值表:\n")
print(head(power_table))

if (exists('manual_power') && !is.null(manual_power) && !is.na(manual_power)) {
  manual_power_val <- as.integer(manual_power)[1]
  cat("使用手动设置的软阈值:", manual_power_val, "\n")
  sc_hdwgcna_power_estimate <<- manual_power_val
} else {
  sc_hdwgcna_power_estimate <<- power_table$Power[which.max(power_table$SFT.R.sq)]
}

cat(paste0("推荐软阈值: ", sc_hdwgcna_power_estimate, "\n"))

sft_data <- data.frame(
  Power = power_table$Power,
  SFT_R2 = power_table$SFT.R.sq,
  Mean_Connectivity = power_table$mean.k.
)

soft_threshold_path <- file.path(output_dir_val, "soft_threshold.png")
png(soft_threshold_path, width = plot_width_val, height = plot_height_val, res = 100)

p1 <- ggplot(sft_data, aes(x = Power, y = SFT_R2)) +
  geom_point(size = 3, color = "#2C3E50") +
  geom_text(aes(label = Power), hjust = -0.3, vjust = -0.3, size = 3.5) +
  geom_hline(yintercept = 0.85, color = "#E74C3C", linetype = "dashed", size = 1) +
  labs(x = "Soft Threshold (power)",
       y = "Scale Free Topology Model Fit (signed R²)",
       title = "Scale Independence") +
  theme_bw(base_size = 12) +
  theme(
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank(),
    panel.border = element_rect(color = "black", size = 1),
    axis.text = element_text(color = "black", size = 10),
    axis.title = element_text(color = "black", size = 12, face = "bold"),
    plot.title = element_text(hjust = 0.5, size = 14, face = "bold"),
    legend.position = "none"
  ) +
  ylim(c(0, 1))

p2 <- ggplot(sft_data, aes(x = Power, y = Mean_Connectivity)) +
  geom_point(size = 3, color = "#8E44AD") +
  geom_text(aes(label = Power), hjust = -0.3, vjust = -0.3, size = 3.5) +
  labs(x = "Soft Threshold (power)",
       y = "Mean Connectivity",
       title = "Mean Connectivity") +
  theme_bw(base_size = 12) +
  theme(
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank(),
    panel.border = element_rect(color = "black", size = 1),
    axis.text = element_text(color = "black", size = 10),
    axis.title = element_text(color = "black", size = 12, face = "bold"),
    plot.title = element_text(hjust = 0.5, size = 14, face = "bold"),
    legend.position = "none"
  )

grid.arrange(p1, p2, ncol = 2)
dev.off()

sc_hdwgcna_seurat_obj <<- seurat_obj

cat("阶段三完成: 软阈值分析完成\n")

# --- STAGE3_BODY_END ---


# ========================================
# 阶段四：网络构建(ConstructNetwork)
# ========================================
# --- STAGE4_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段三")
}

cat("阶段四：网络构建(ConstructNetwork)\n")

seurat_obj <- sc_hdwgcna_seurat_obj

if (!exists('soft_power')) {
  soft_power_val <- sc_hdwgcna_power_estimate
} else {
  soft_power_val <- as.integer(soft_power)[1]
}
cat("软阈值: ", soft_power_val, "\n")

min_module_size_val <- if (exists('min_module_size')) as.integer(min_module_size)[1] else 30
cat(paste0("最小模块大小: ", min_module_size_val, "\n"))

cat("运行ConstructNetwork...\n")
cat(paste0("可用内存: ", memory.limit(size = NA), " MB\n"))
cat(paste0("当前使用内存: ", memory.size(max = FALSE), " MB\n"))

n_genes_current <- length(GetWGCNAGenes(seurat_obj))
cat(paste0("当前基因数: ", n_genes_current, "\n"))

gc()
cat("GC完成\n")

tryCatch({
  seurat_obj <- ConstructNetwork(
    seurat_obj,
    soft_power = soft_power_val,
    tom_outdir = file.path(output_dir_val, "TOM"),
    tom_name = "sc_hdwgcna_test",
    overwrite_tom = TRUE,
    minModuleSize = min_module_size_val
  )
  cat("ConstructNetwork成功！\n")
  
  gc()
  cat(paste0("运行后内存使用: ", memory.size(max = FALSE), " MB\n"))
  
}, error = function(e) {
  cat(paste0("ConstructNetwork错误: ", e$message, "\n"))
  stop(paste0("ConstructNetwork失败: ", e$message))
})

cat("获取模块信息...\n")
modules_df <- tryCatch({
  GetModules(seurat_obj, wgcna_name = "sc_hdwgcna_test")
}, error = function(e) {
  cat(paste0("GetModules失败: ", e$message, "\n"))
  NULL
})

if (is.null(modules_df) || nrow(modules_df) == 0) {
  cat("警告：未检测到任何模块！\n")
  cat("可能的原因：1) 基因表达量差异不大；2) 软阈值参数不合适；3) 数据质量问题\n")
  sc_hdwgcna_seurat_obj <<- seurat_obj
  stop("未检测到任何模块，请检查数据和参数")
}

module_table <- table(modules_df$module)
cat("\n模块大小统计:\n")
print(module_table)

sc_hdwgcna_seurat_obj <<- seurat_obj

cat("生成模块基因树...\n")
gene_dendro_path <- file.path(output_dir_val, "gene_dendrogram.png")
tryCatch({
  png(gene_dendro_path, width = plot_width_val, height = plot_height_val, res = 100)
  PlotDendrogram(seurat_obj)
  dev.off()
  cat("模块基因树已保存\n")
}, error = function(e) {
  cat(paste0("生成基因树失败: ", e$message, "\n"))
  cat("跳过基因树生成，继续后续步骤\n")
})

cat("阶段四完成: 网络构建完成\n")

# --- STAGE4_BODY_END ---


# ========================================
# 阶段五：模块可视化(Dendrogram+KMEs)
# ========================================
# --- STAGE5_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段四")
}

cat("阶段五：模块可视化(Dendrogram+KMEs)\n")

seurat_obj <- sc_hdwgcna_seurat_obj

cat("运行ModuleEigengenes...\n")
seurat_obj <- ModuleEigengenes(
  seurat_obj,
  group.by.vars = "wgcna_type_fixed_sample"
)
cat("ModuleEigengenes成功！\n")

target_cell_type_val <- if (!is.null(sc_hdwgcna_target_cell_type) && sc_hdwgcna_target_cell_type != "" && sc_hdwgcna_target_cell_type != "全部") {
  sc_hdwgcna_target_cell_type
} else {
  levels(as.factor(seurat_obj@meta.data[["wgcna_type_fixed_analyze"]]))[1]
}

cat("运行ModuleConnectivity...\n")
seurat_obj <- ModuleConnectivity(
  seurat_obj,
  group.by = "wgcna_type_fixed_analyze", 
  group_name = target_cell_type_val
)
cat("ModuleConnectivity成功！\n")

cat("模块命名使用默认颜色名称...\n")

sc_hdwgcna_seurat_obj <<- seurat_obj

cat("生成PlotKMEs...\n")
tryCatch({
  kme_plot <- PlotKMEs(seurat_obj, ncol=4)
  kme_path <- file.path(output_dir_val, "kme_plot.png")
  png(kme_path, width = plot_width_val, height = plot_height_val, res = 100)
  print(kme_plot)
  dev.off()
  cat("PlotKMEs已保存\n")
}, error = function(e) {
  cat(paste0("PlotKMEs错误: ", e$message, "\n"))
})

cat("阶段五完成: 模块可视化完成\n")

# --- STAGE5_BODY_END ---


# ========================================
# 阶段六：模块特征图(hMEs)
# ========================================
# --- STAGE6_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段五")
}

cat("阶段六：模块特征图(hMEs)\n")

seurat_obj <- sc_hdwgcna_seurat_obj

cat("运行ModuleExprScore...\n")
tryCatch({
  seurat_obj <- ModuleExprScore(
    seurat_obj,
    n_genes = 25,
    method='UCell'
  )
  cat("ModuleExprScore成功！\n")
}, error = function(e) {
  cat(paste0("ModuleExprScore错误: ", e$message, "\n"))
})

cat("生成ModuleFeaturePlot(hMEs)...\n")
tryCatch({
  hme_plot_list <- ModuleFeaturePlot(
    seurat_obj,
    features='hMEs',
    order=TRUE
  )
  hme_path <- file.path(output_dir_val, "module_feature_hmes.png")
  n_plots <- length(hme_plot_list)
  n_cols <- if (n_plots <= 4) n_plots else 4
  n_rows <- ceiling(n_plots / n_cols)
  png(hme_path, width = 400 * n_cols, height = 400 * n_rows, res = 150)
  print(wrap_plots(hme_plot_list, ncol=n_cols))
  dev.off()
  cat("ModuleFeaturePlot(hMEs)已保存\n")
  
  hme_individual_dir <- file.path(output_dir_val, "hME_individual")
  dir.create(hme_individual_dir, showWarnings = FALSE)
  for (i in seq_along(hme_plot_list)) {
    plot_path <- file.path(hme_individual_dir, paste0("hME_", names(hme_plot_list)[i], ".png"))
    png(plot_path, width = 600, height = 500, res = 150)
    print(hme_plot_list[[i]])
    dev.off()
  }
  cat("hME单独图已保存\n")
}, error = function(e) {
  cat(paste0("ModuleFeaturePlot(hMEs)错误: ", e$message, "\n"))
})

sc_hdwgcna_seurat_obj <<- seurat_obj

cat("阶段六完成: 模块特征图完成\n")

# --- STAGE6_BODY_END ---


# ========================================
# 阶段七：模块相关图(Correlogram+DotPlot)
# ========================================
# --- STAGE7_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段六")
}

cat("阶段七：相关图\n")

seurat_obj <- sc_hdwgcna_seurat_obj



cat("获取模块特征基因...\n")
MEs <- GetMEs(seurat_obj, harmonized=TRUE)
modules <- GetModules(seurat_obj)
mods <- levels(modules$module); mods <- mods[mods != 'grey']

seurat_obj@meta.data <- cbind(seurat_obj@meta.data, MEs)

cat("生成模块相关图(基于MEs相关性)...\n")
MEs_no_grey <- MEs[, colnames(MEs) != "MEgrey", drop = FALSE]
module_cor <- cor(MEs_no_grey)

correlogram_path <- file.path(output_dir_val, "module_correlogram.png")
png(correlogram_path, width = plot_width_val, height = plot_height_val, res = 100)
p_cor <- ggplot(reshape2::melt(module_cor), aes(x = Var1, y = Var2, fill = value)) +
  geom_tile(color = "white", size = 0.5) +
  geom_text(aes(label = sprintf("%.2f", value)), color = "black", size = 3) +
  scale_fill_gradient2(low = "blue", mid = "white", high = "red", 
                      midpoint = 0, limit = c(-1, 1), space = "Lab") +
  labs(title = "Module Correlation", x = "Modules", y = "Modules") +
  theme_bw(base_size = 10) +
  theme(
    plot.title = element_text(hjust = 0.5, size = 14, face = "bold"),
    axis.title.x = element_text(size = 10, face = "bold"),
    axis.title.y = element_text(size = 10, face = "bold"),
    axis.text.x = element_text(size = 8, angle = 45, hjust = 1),
    axis.text.y = element_text(size = 8),
    legend.title = element_text(size = 10, face = "bold"),
    legend.text = element_text(size = 8),
    panel.border = element_rect(color = "black", size = 1)
  )
print(p_cor)
dev.off()
cat("模块相关图已保存\n")

cat("生成DotPlot...\n")
dotplot_path <- file.path(output_dir_val, "module_dotplot.png")
png(dotplot_path, width = plot_width_val, height = plot_height_val, res = 100)
p <- DotPlot(seurat_obj, features=mods, group.by = "wgcna_type_fixed_analyze") +
  RotatedAxis() +
  scale_color_gradient2(high='red', mid='grey95', low='blue')
print(p)
dev.off()
cat("DotPlot已保存\n")



sc_hdwgcna_seurat_obj <<- seurat_obj

cat("阶段七完成: 相关图完成\n")

# --- STAGE7_BODY_END ---


# ========================================
# 阶段八：ModuleUMAP
# ========================================
# --- STAGE8_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段七")
}

cat("阶段八：ModuleUMAP\n")

seurat_obj <- sc_hdwgcna_seurat_obj

cat("运行RunModuleUMAP...\n")
seurat_obj <- tryCatch({
  RunModuleUMAP(
    seurat_obj,
    n_hubs = 10,
    n_neighbors=15,
    min_dist=0.1
  )
}, error = function(e) {
  cat(paste0("RunModuleUMAP错误: ", e$message, "\n"))
  cat("跳过RunModuleUMAP\n")
  return(seurat_obj)
})

cat("尝试获取ModuleUMAP数据...\n")
umap_df <- tryCatch({
  GetModuleUMAP(seurat_obj)
}, error = function(e) {
  cat(paste0("GetModuleUMAP错误: ", e$message, "\n"))
  cat("跳过ModuleUMAP图\n")
  return(NULL)
})

if (!is.null(umap_df)) {
  module_umap_path <- file.path(output_dir_val, "module_umap.png")
  png(module_umap_path, width = plot_width_val, height = plot_height_val, res = 100)
  p <- ggplot(umap_df, aes(x=UMAP1, y=UMAP2)) +
    geom_point(color=umap_df$color, size=umap_df$kME*2) +
    theme_bw() +
    ggtitle("Module UMAP") +
    xlab("UMAP 1") +
    ylab("UMAP 2") +
    theme(
      plot.title = element_text(hjust = 0.5, size = 16, face = "bold"),
      axis.title.x = element_text(size = 12, face = "bold", color = "black"),
      axis.title.y = element_text(size = 12, face = "bold", color = "black"),
      axis.text.x = element_text(size = 10, color = "black"),
      axis.text.y = element_text(size = 10, color = "black"),
      panel.border = element_rect(color = "black", size = 1)
    )
  print(p)
dev.off()
cat("ModuleUMAP已保存\n")
}

sc_hdwgcna_seurat_obj <<- seurat_obj

cat("阶段八完成: ModuleUMAP完成\n")

# --- STAGE8_BODY_END ---


# ========================================
# 阶段九：GO和KEGG富集分析
# ========================================
# --- STAGE9_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段四")
}

cat("阶段九：GO和KEGG富集分析\n")

seurat_obj <- sc_hdwgcna_seurat_obj

cat("检查必需的R包...\n")
use_clusterProfiler <- require(clusterProfiler, quietly = TRUE)
use_orgHsEgDb <- require(org.Hs.eg.db, quietly = TRUE)
use_orgMmEgDb <- require(org.Mm.eg.db, quietly = TRUE)
use_orgRnEgDb <- require(org.Rn.eg.db, quietly = TRUE)
use_orgDmEgDb <- require(org.Dm.eg.db, quietly = TRUE)

if (!use_clusterProfiler) {
  stop("clusterProfiler包未安装或未加载，请先安装clusterProfiler")
}

if (!exists('organism')) {
  organism_val <- "hsa"
} else {
  organism_val <- as.character(organism)[1]
}
cat("物种: ", organism_val, "\n")

if (organism_val == "hsa") {
  if (!use_orgHsEgDb) {
    stop("org.Hs.eg.db包未安装或未加载，请先安装org.Hs.eg.db")
  }
} else if (organism_val == "mmu") {
  if (!use_orgMmEgDb) {
    stop("org.Mm.eg.db包未安装或未加载，请先安装org.Mm.eg.db")
  }
} else if (organism_val == "rno") {
  if (!use_orgRnEgDb) {
    stop("org.Rn.eg.db包未安装或未加载，请先安装org.Rn.eg.db")
  }
} else if (organism_val == "dme") {
  if (!use_orgDmEgDb) {
    stop("org.Dm.eg.db包未安装或未加载，请先安装org.Dm.eg.db")
  }
} else {
  stop(paste0("不支持的物种: ", organism_val))
}

if (!exists('go_padj_cutoff')) {
  go_padj_cutoff_val <- 0.05
} else {
  go_padj_cutoff_val <- as.numeric(go_padj_cutoff)[1]
}
cat("GO校正p值阈值: ", go_padj_cutoff_val, "\n")

if (!exists('kegg_padj_cutoff')) {
  kegg_padj_cutoff_val <- 0.05
} else {
  kegg_padj_cutoff_val <- as.numeric(kegg_padj_cutoff)[1]
}
cat("KEGG校正p值阈值: ", kegg_padj_cutoff_val, "\n")

if (!exists('go_top_n')) {
  go_top_n_val <- 15
} else {
  go_top_n_val <- as.integer(go_top_n)[1]
}
cat("GO展示条目数: ", go_top_n_val, "\n")

if (!exists('kegg_top_n')) {
  kegg_top_n_val <- 15
} else {
  kegg_top_n_val <- as.integer(kegg_top_n)[1]
}
cat("KEGG展示条目数: ", kegg_top_n_val, "\n")

modules <- GetModules(seurat_obj)
gene_names <- modules$gene_name
module_labels <- modules$module

if (!exists('selected_modules') || is.null(selected_modules)) {
  selected_modules_val <- unique(module_labels)
  selected_modules_val <- selected_modules_val[selected_modules_val != 'grey']
} else {
  selected_modules_val <- as.character(selected_modules)
}

cat("要分析的模块: ", paste(selected_modules_val, collapse=", "), "\n")

for (mod in selected_modules_val) {
  cat(paste0("\n=== 处理模块 ", mod, " ===\n"))
  mod_genes <- gene_names[module_labels == mod]
  cat(paste0("模块 ", mod, ": ", length(mod_genes), " 个基因\n"))
  
  if (length(mod_genes) < 10) {
    cat(paste0("模块 ", mod, " 基因数太少(<10)，跳过富集分析\n"))
    next
  }
  
  cat("转换基因ID为ENTREZ格式...\n")
  if (organism_val == "hsa") {
    mod_genes_entrez <- mapIds(org.Hs.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else if (organism_val == "mmu") {
    mod_genes_entrez <- mapIds(org.Mm.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else if (organism_val == "rno") {
    mod_genes_entrez <- mapIds(org.Rn.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else if (organism_val == "dme") {
    mod_genes_entrez <- mapIds(org.Dm.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else {
    cat(paste0("不支持的物种: ", organism_val, "，跳过分析\n"))
    next
  }
  mod_genes_entrez <- as.character(mod_genes_entrez[!is.na(mod_genes_entrez)])
  
  if (length(mod_genes_entrez) < 5) {
    cat(paste0("模块 ", mod, " 有效ENTREZ基因数太少(<5)，跳过富集分析\n"))
    next
  }
  
  cat(paste0("有效ENTREZ基因数: ", length(mod_genes_entrez), "\n"))
  
  cat("进行GO富集分析...\n")
  go_result <- tryCatch({
    if (organism_val == "hsa") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Hs.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff_val,
        qvalueCutoff = go_padj_cutoff_val,
        readable = TRUE
      )
    } else if (organism_val == "mmu") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Mm.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff_val,
        qvalueCutoff = go_padj_cutoff_val,
        readable = TRUE
      )
    } else if (organism_val == "rno") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Rn.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff_val,
        qvalueCutoff = go_padj_cutoff_val,
        readable = TRUE
      )
    } else if (organism_val == "dme") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Dm.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff_val,
        qvalueCutoff = go_padj_cutoff_val,
        readable = TRUE
      )
    } else {
      cat(paste0("不支持的物种: ", organism_val, "，跳过GO分析\n"))
      return(NULL)
    }
  }, error = function(e) {
    cat(paste0("GO分析出错: ", e$message, "\n"))
    cat("尝试不使用readable参数重新运行...\n")
    tryCatch({
      if (organism_val == "hsa") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Hs.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff_val,
          qvalueCutoff = go_padj_cutoff_val,
          readable = FALSE
        )
      } else if (organism_val == "mmu") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Mm.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff_val,
          qvalueCutoff = go_padj_cutoff_val,
          readable = FALSE
        )
      } else if (organism_val == "rno") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Rn.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff_val,
          qvalueCutoff = go_padj_cutoff_val,
          readable = FALSE
        )
      } else if (organism_val == "dme") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Dm.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff_val,
          qvalueCutoff = go_padj_cutoff_val,
          readable = FALSE
        )
      } else {
        return(NULL)
      }
    }, error = function(e2) {
      cat(paste0("GO分析再次失败: ", e2$message, "\n"))
      return(NULL)
    })
  })
  
  if (!is.null(go_result) && nrow(go_result) > 0) {
    go_result_df <- as.data.frame(go_result)
    write.table(go_result_df, file.path(output_dir_val, paste0("GO_", mod, ".txt")), sep="\t", quote=F, row.names=F)
    
    go_title <- paste0("GO Enrichment Analysis - Module ", mod)
    
    go_bubble_path <- file.path(output_dir_val, paste0("GO_bubble_", mod, ".png"))
    png(go_bubble_path, width = 1000, height = 1500, res = 100)
    print(dotplot(go_result, showCategory = go_top_n_val, label_format=100, split="ONTOLOGY") + 
            facet_grid(ONTOLOGY~., scale='free') + 
            ggtitle(go_title))
    dev.off()
    cat(paste0("GO气泡图PNG已保存: ", go_bubble_path, "\n"))
    
    go_bar_path <- file.path(output_dir_val, paste0("GO_bar_", mod, ".png"))
    png(go_bar_path, width = 1000, height = 1500, res = 100)
    print(barplot(go_result, drop = TRUE, showCategory = go_top_n_val, label_format=100, split="ONTOLOGY") + 
            facet_grid(ONTOLOGY~., scale='free') + 
            ggtitle(go_title))
    dev.off()
    cat(paste0("GO条图PNG已保存: ", go_bar_path, "\n"))
    
    go_result_df <- as.data.frame(go_result)
    go_table_path <- file.path(output_dir_val, paste0("GO_result_", mod, ".xlsx"))
    openxlsx::write.xlsx(go_result_df, go_table_path, rowNames = FALSE)
    cat(paste0("GO结果表格已保存: ", go_table_path, "\n"))
  } else {
    cat(paste0("模块 ", mod, " GO富集分析无显著结果\n"))
  }
  
  cat("进行KEGG富集分析...\n")
  kegg_result <- tryCatch({
    options(timeout = 300)
    enrichKEGG(
      gene = mod_genes_entrez,
      keyType = "kegg",
      organism = organism_val,
      pvalueCutoff = kegg_padj_cutoff_val,
      qvalueCutoff = kegg_padj_cutoff_val,
      pAdjustMethod = "fdr"
    )
  }, error = function(e) {
    cat(paste0("KEGG分析网络错误: ", e$message, "\n"))
    cat("尝试使用clusterProfiler本地数据库重新运行...\n")
    tryCatch({
      enrichKEGG(
        gene = mod_genes_entrez,
        keyType = "kegg",
        organism = organism_val,
        pvalueCutoff = kegg_padj_cutoff_val,
        qvalueCutoff = kegg_padj_cutoff_val,
        pAdjustMethod = "fdr",
        use_internal_data = TRUE
      )
    }, error = function(e2) {
      cat(paste0("KEGG分析本地数据库也失败: ", e2$message, "\n"))
      return(NULL)
    })
  })
  
  if (!is.null(kegg_result)) {
    if (nrow(kegg_result) > 0) {
      kegg_result_df <- as.data.frame(kegg_result)
      write.table(kegg_result_df, file.path(output_dir_val, paste0("KEGG_", mod, ".txt")), sep="\t", quote=F, row.names=F)
      
      kegg_title <- paste0("KEGG Enrichment Analysis - Module ", mod)
      
      kegg_bar_path <- file.path(output_dir_val, paste0("KEGG_bar_", mod, ".png"))
      png(kegg_bar_path, width = 1000, height = 1300, res = 100)
      print(barplot(kegg_result, drop = TRUE, showCategory = kegg_top_n_val, label_format=100) + 
              ggtitle(kegg_title))
      dev.off()
      cat(paste0("KEGG条图PNG已保存: ", kegg_bar_path, "\n"))
      
      kegg_bubble_path <- file.path(output_dir_val, paste0("KEGG_bubble_", mod, ".png"))
      png(kegg_bubble_path, width = 1000, height = 600, res = 100)
      print(dotplot(kegg_result, showCategory = kegg_top_n_val, label_format=100) + 
              ggtitle(kegg_title))
      dev.off()
      cat(paste0("KEGG气泡图PNG已保存: ", kegg_bubble_path, "\n"))
      
      kegg_result_df <- as.data.frame(kegg_result)
      kegg_table_path <- file.path(output_dir_val, paste0("KEGG_result_", mod, ".xlsx"))
      openxlsx::write.xlsx(kegg_result_df, kegg_table_path, rowNames = FALSE)
      cat(paste0("KEGG结果表格已保存: ", kegg_table_path, "\n"))
    } else {
      cat(paste0("模块 ", mod, " KEGG富集分析无显著结果(padj >= ", kegg_padj_cutoff_val, ")\n"))
    }
  } else {
    cat(paste0("模块 ", mod, " KEGG富集分析失败(网络/数据库问题)\n"))
  }
}

cat("阶段九完成: GO和KEGG富集分析完成\n")

# --- STAGE9_BODY_END ---


# ========================================
# 阶段十：导出基因集合和枢纽基因
# ========================================
# --- STAGE10_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('sc_hdwgcna_seurat_obj')) {
  stop("请先运行阶段四")
}

cat("阶段十：导出基因集合和枢纽基因\n")

seurat_obj <- sc_hdwgcna_seurat_obj

modules <- GetModules(seurat_obj)
all_modules <- unique(modules$module)
cat("所有模块: ", paste(all_modules, collapse=", "), "\n")

for (mod in all_modules) {
  mod_genes <- modules$gene_name[modules$module == mod]
  cat(paste0("模块 ", mod, ": ", length(mod_genes), " 个基因\n"))
  
  if (length(mod_genes) > 0) {
    gene_df <- data.frame(Gene = mod_genes)
    
    file_path <- file.path(output_dir_val, paste0("module_genes_", mod, ".xlsx"))
    openxlsx::write.xlsx(gene_df, file_path, rowNames = FALSE, colNames = FALSE)
    cat(paste0("已导出: ", file_path, "\n"))
  }
}

cat("\n获取枢纽基因...\n")
tryCatch({
  hub_df <- GetHubGenes(seurat_obj, n_hubs = 10)
  hub_file_path <- file.path(output_dir_val, "hub_genes.xlsx")
  openxlsx::write.xlsx(hub_df, hub_file_path, rowNames = FALSE)
  cat(paste0("枢纽基因已导出: ", hub_file_path, "\n"))
  cat("前6个枢纽基因:\n")
  print(head(hub_df))
}, error = function(e) {
  cat(paste0("获取枢纽基因错误: ", e$message, "\n"))
})

cat("\n导出完整模块信息表...\n")
tryCatch({
  module_info_df <- modules[modules$module != 'grey', ]
  module_info_path <- file.path(output_dir_val, "module_info.xlsx")
  openxlsx::write.xlsx(module_info_df, module_info_path, rowNames = FALSE)
  cat(paste0("模块信息已导出: ", module_info_path, "\n"))
}, error = function(e) {
  cat(paste0("导出模块信息错误: ", e$message, "\n"))
})

cat("阶段十完成: 基因集合和枢纽基因已导出\n")

# --- STAGE10_BODY_END ---

# ========================================
# 辅助函数
# ========================================

get_hdwgcna_modules <- function() {
  if (!exists('sc_hdwgcna_seurat_obj')) {
    return(c())
  }
  seurat_obj <- sc_hdwgcna_seurat_obj
  modules <- GetModules(seurat_obj)
  return(unique(modules$module))
}
