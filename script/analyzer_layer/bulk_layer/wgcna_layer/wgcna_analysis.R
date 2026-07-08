# bulk WGCNA分析 R脚本
# 此文件包含所有R代码，用于通过rpy2调用R进行WGCNA分析
#
# 使用方式：
# Python端通过rpy2将参数设置到全局环境，然后提取标记行内的代码执行
# 参数直接从全局环境获取，不需要显式传递
# R包必须通过Python端的importr()预加载，禁止在脚本中使用library()
#
# 四阶段架构：
# 阶段一：STAGE1 - 数据准备+MAD筛选+样本聚类树
# 阶段二：STAGE2 - 软阈值选择
# 阶段三：STAGE3 - 网络构建+模块识别
# 阶段四：STAGE4 - 模块-性状关联+出图
#
# 参数列表（从全局环境获取）：
# - expr_data: 表达矩阵数据框（行为基因，列为样本）
# - trait_data: 性状数据框（行名为样本，列为性状）
# - mad_threshold: MAD阈值，默认5000
# - output_dir: 输出目录
# - network_type: 网络类型，默认"unsigned"
# - power_val: 软阈值power值
# - min_module_size: 最小模块大小，默认30
# - merge_cut_height: 模块合并阈值，默认0.25


# ========================================
# 阶段一：数据准备+MAD筛选+样本聚类树
# ========================================
# --- STAGE1_BODY_START ---

df <- as.matrix(expr_data)
mad_val <- as.integer(mad_threshold)[1]
output_dir_val <- as.character(output_dir)[1]
filter_mode_val <- if (exists('filter_mode')) as.character(filter_mode)[1] else "MAD筛选"

if (!exists('expr_data')) {
  stop("表达矩阵 expr_data 不存在")
}

cat("阶段一：数据准备+基因筛选\n")
cat("筛选方式: ", filter_mode_val, "\n")
cat("原始数据维度: ", nrow(df), " x ", ncol(df), "\n")
cat("数据类型: ", class(df), "\n")

if (nrow(df) > ncol(df)) {
  cat("行 > 列，假设当前是 genes x samples，需要转置为 samples x genes\n")
  df <- t(df)
}

cat("转置后数据维度: ", nrow(df), " samples x ", ncol(df), " genes\n")
cat("数据范围: ", range(df, na.rm = TRUE), "\n")
cat("NaN数量: ", sum(is.na(df)), "\n")
cat("Inf数量: ", sum(is.infinite(df)), "\n")

if (filter_mode_val == "MAD筛选") {
  cat("Step 1: 计算MAD...\n")
  mads <- apply(df, 2, mad, na.rm = TRUE)
  mads[is.na(mads) | is.infinite(mads)] <- 0
  cat("MAD范围: ", range(mads), "\n")
  cat("MAD为0的基因数: ", sum(mads == 0), "\n")

  cat("Step 2: 筛选基因...\n")
  n_genes <- min(mad_val, ncol(df))
  df <- df[, rev(order(mads))[1:n_genes]]
  cat("筛选后基因数: ", ncol(df), "\n")
} else {
  cat("使用外部基因列表，跳过MAD筛选\n")
  cat("当前基因数: ", ncol(df), "\n")
}

cat("Step 3: 数据中心化...\n")
medians <- apply(df, 2, median, na.rm = TRUE)
cat("中位数范围: ", range(medians, na.rm = TRUE), "\n")
exprSet <- sweep(df, 2, medians)

cat("Step 4: 数据质量检查...\n")
gsg <- goodSamplesGenes(exprSet, verbose = 3)
if (!gsg$allOK) {
  if (sum(!gsg$goodGenes) > 0) {
    cat("移除不良基因数: ", sum(!gsg$goodGenes), "\n")
  }
  if (sum(!gsg$goodSamples) > 0) {
    cat("移除不良样本数: ", sum(!gsg$goodSamples), "\n")
  }
  exprSet <- exprSet[gsg$goodSamples, gsg$goodGenes]
}
cat("QC后数据维度: ", nrow(exprSet), " samples x ", ncol(exprSet), " genes\n")

wgcna_exprSet <<- exprSet
if (exists('trait_data') && !is.null(trait_data)) {
  wgcna_trait_data <<- trait_data
} else {
  wgcna_trait_data <<- NULL
}

sample_tree <- hclust(dist(exprSet), method = "average")

sample_dendro_path <- file.path(output_dir_val, "sample_dendrogram.png")
png(sample_dendro_path, width = 1200, height = 800, res = 100)

if (exists('trait_data') && !is.null(trait_data) && ncol(trait_data) > 0 && nrow(trait_data) == ncol(exprSet)) {
  trait_colors <- numbers2colors(as.numeric(factor(trait_data$Cluster)),
                                colors = rainbow(length(unique(trait_data$Cluster))),
                                signed = FALSE)
  
  plotDendroAndColors(sample_tree, trait_colors,
                      groupLabels = "Cluster",
                      cex.dendroLabels = 0.8,
                      marAll = c(1, 4, 3, 1),
                      cex.rowText = 0.01,
                      main = "Sample dendrogram and trait heatmap")
} else {
  par(mar = c(0, 4, 2, 0))
  plot(sample_tree, 
       main = "Sample Clustering", 
       sub = "", 
       xlab = "", 
       cex.lab = 1.5,
       cex.axis = 1, 
       cex.main = 1.5)
}

dev.off()
cat("阶段一完成: 样本聚类树已保存\n")
cat("数据维度:", nrow(exprSet), "samples,", ncol(exprSet), "genes\n")

# --- STAGE1_BODY_END ---


# ========================================
# 阶段二：软阈值选择
# ========================================
# --- STAGE2_BODY_START ---

output_dir_val <- as.character(output_dir)[1]
network_type_val <- as.character(network_type)[1]

if (!exists('wgcna_exprSet')) {
  stop("请先运行阶段一")
}

cat("阶段二：软阈值选择\n")
cat("数据维度:", nrow(wgcna_exprSet), "genes x", ncol(wgcna_exprSet), "samples\n")

powers <- c(seq(1, 10, by = 1), seq(12, 20, by = 2))

rsquared_cut_val <- if (exists('rsquared_cut') && !is.null(rsquared_cut)) as.numeric(rsquared_cut)[1] else 0.85

sft <- pickSoftThreshold(
  wgcna_exprSet,
  networkType = network_type_val,
  powerVector = powers,
  RsquaredCut = rsquared_cut_val,
  verbose = 5
)

wgcna_sft <<- sft

if (exists('manual_power') && !is.null(manual_power) && !is.na(manual_power)) {
  manual_power_val <- as.integer(manual_power)[1]
  cat("使用手动设置的软阈值:", manual_power_val, "\n")
  wgcna_power_estimate <<- manual_power_val
} else {
  wgcna_power_estimate <<- sft$powerEstimate
}

sft_data <- data.frame(
  Power = sft$fitIndices[, 1],
  SFT_R2 = -sign(sft$fitIndices[, 3]) * sft$fitIndices[, 2],
  Mean_Connectivity = sft$fitIndices[, 5]
)

soft_threshold_path <- file.path(output_dir_val, "soft_threshold.png")
png(soft_threshold_path, width = 1400, height = 600, res = 100)

library(ggplot2)
library(gridExtra)

p1 <- ggplot(sft_data, aes(x = Power, y = SFT_R2)) +
  geom_point(size = 3, color = "#2C3E50") +
  geom_text(aes(label = Power), hjust = -0.3, vjust = -0.3, size = 3.5) +
  geom_hline(yintercept = rsquared_cut_val, color = "#E74C3C", linetype = "dashed", size = 1) +
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

cat("阶段二完成: 推荐软阈值 =", sft$powerEstimate, "\n")

# --- STAGE2_BODY_END ---


# ========================================
# 阶段三：网络构建+模块识别
# ========================================
# --- STAGE3_BODY_START ---

output_dir_val <- as.character(output_dir)[1]
power_val <- as.integer(power)[1]
min_module_size_val <- as.integer(min_module_size)[1]
merge_cut_height_val <- as.numeric(merge_cut_height)[1]

if (!exists('wgcna_exprSet')) {
  stop("请先运行阶段一")
}

cat("阶段三：网络构建+模块识别\n")
cat("Power:", power_val, "\n")
cat("Minimum module size:", min_module_size_val, "\n")
cat("Merge cut height:", merge_cut_height_val, "\n")

if (!exists('stage3_width')) {
  stage3_width <- 1200
} else {
  stage3_width <- as.numeric(stage3_width)[1]
}
cat("Stage3 width:", stage3_width, "\n")

if (!exists('stage3_height')) {
  stage3_height <- 1200
} else {
  stage3_height <- as.numeric(stage3_height)[1]
}
cat("Stage3 height:", stage3_height, "\n")

dissTOM <- 1 - TOMsimilarityFromExpr(wgcna_exprSet, power = power_val)
gene_tree <- hclust(as.dist(dissTOM), method = "average")

dynamicMods <- cutreeDynamic(dendro = gene_tree, distM = dissTOM,
                             deepSplit = 2, pamRespectsDendro = FALSE,
                             minClusterSize = min_module_size_val)
moduleColors <- labels2colors(dynamicMods)
cat("检测到", length(unique(moduleColors)), "个模块\n")

MEs0 <- moduleEigengenes(wgcna_exprSet, moduleColors)$eigengenes
MEs <- orderMEs(MEs0)

MEDiss <- 1 - cor(MEs)
METree <- hclust(as.dist(MEDiss), method = "average")

module_merge_analysis_path <- file.path(output_dir_val, "module_merge_analysis.png")
png(module_merge_analysis_path, width = stage3_width, height = stage3_height * 0.6, res = 100)

par(cex = 0.8, mar = c(4, 6, 4, 2))
plot(METree, main = "Clustering of Module Eigengenes",
     xlab = "", sub = "", cex.main = 1.5)
abline(h = merge_cut_height_val, col = "#E74C3C", lwd = 2, lty = 2)
text(x = length(METree$order)/2, y = merge_cut_height_val + 0.05,
     labels = paste("Merge threshold =", merge_cut_height_val),
     col = "#E74C3C", cex = 1.2)
dev.off()

merge <- mergeCloseModules(wgcna_exprSet, moduleColors, cutHeight = merge_cut_height_val, verbose = 3)
mergedColors <- merge$colors
mergedMEs <- merge$newMEs

module_comparison_path <- file.path(output_dir_val, "module_colors_comparison.png")
png(module_comparison_path, width = stage3_width, height = stage3_height * 0.7, res = 100)

plotDendroAndColors(gene_tree, cbind(moduleColors, mergedColors),
                    c("Original", "Merged"), dendroLabels = FALSE, hang = 0.03,
                    addGuide = TRUE, guideHang = 0.05,
                    main = "Module Assignment: Before and After Merging")
dev.off()

wgcna_module_labels <<- mergedColors

module_table <- table(wgcna_module_labels)
cat("\n合并后模块大小:\n")
print(module_table)

wgcna_net <<- list(
  colors = dynamicMods,
  mergedColors = as.integer(factor(mergedColors)),
  MEs = mergedMEs
)

gene_dendro_path <- file.path(output_dir_val, "gene_dendrogram_with_modules.png")
png(gene_dendro_path, width = stage3_width, height = stage3_height, res = 100)

plotDendroAndColors(
  gene_tree,
  wgcna_module_labels,
  groupLabels = "Module",
  cex.dendroLabels = 0.1,
  marAll = c(0, 4, 3, 1),
  cex.rowText = 0.8,
  main = "Gene dendrogram and module colors"
)

dev.off()

cat("阶段三完成: 基因聚类树已保存\n")

# --- STAGE3_BODY_END ---


# ========================================
# 阶段四：模块-性状关联+出图
# ========================================
# --- STAGE4_BODY_START ---

output_dir_val <- as.character(output_dir)[1]

if (!exists('wgcna_net')) {
  stop("请先运行阶段三")
}

cat("阶段四：模块-性状关联+出图\n")

if (!exists('stage4_width')) {
  stage4_width <- 1200
} else {
  stage4_width <- as.numeric(stage4_width)[1]
}
cat("Stage4 width:", stage4_width, "\n")

if (!exists('stage4_height')) {
  stage4_height <- 1000
} else {
  stage4_height <- as.numeric(stage4_height)[1]
}
cat("Stage4 height:", stage4_height, "\n")

if (!exists('cell_width')) {
  cell_width <- 80
} else {
  cell_width <- as.numeric(cell_width)[1]
}
cat("Cell width:", cell_width, "\n")

if (!exists('cell_height')) {
  cell_height <- 35
} else {
  cell_height <- as.numeric(cell_height)[1]
}
cat("Cell height:", cell_height, "\n")

if (!exists('show_significance')) {
  show_significance <- TRUE
} else {
  show_significance <- as.logical(show_significance)[1]
}
cat("Show significance:", show_significance, "\n")

MEs <- wgcna_net$MEs
cat("原始MEs维度:", nrow(MEs), "x", ncol(MEs), "\n")
cat("原始MEs列名:", colnames(MEs), "\n")

MEs <- orderMEs(MEs)

cat("处理后MEs维度:", nrow(MEs), "x", ncol(MEs), "\n")
cat("处理后MEs列名:", colnames(MEs), "\n")

has_trait <- exists('wgcna_trait_data') && !is.null(wgcna_trait_data) && ncol(wgcna_trait_data) > 0
if (has_trait) {
  cat("性状数据维度:", nrow(wgcna_trait_data), "x", ncol(wgcna_trait_data), "\n")
  cat("性状数据行名:", head(rownames(wgcna_trait_data)), "\n")
  cat("MEs行名:", head(rownames(MEs)), "\n")
} else {
  cat("性状数据不存在或为空\n")
}

wgcna_module_trait <<- list(
  module_eigengenes = MEs,
  correlation = NULL,
  p_value = NULL
)

if (has_trait) {
  if (nrow(MEs) != nrow(wgcna_trait_data)) {
    cat("MEs行数(", nrow(MEs), ")与性状数据行数(", nrow(wgcna_trait_data), ")不匹配\n")
    cat("尝试对齐行名...\n")
    common_rows <- intersect(rownames(MEs), rownames(wgcna_trait_data))
    cat("共有", length(common_rows), "个共同行\n")
    if (length(common_rows) > 0) {
      MEs <- MEs[common_rows, , drop = FALSE]
      wgcna_trait_data <- wgcna_trait_data[common_rows, , drop = FALSE]
      cat("对齐后MEs维度:", nrow(MEs), "x", ncol(MEs), "\n")
      cat("对齐后性状数据维度:", nrow(wgcna_trait_data), "x", ncol(wgcna_trait_data), "\n")
    } else {
      cat("没有共同行，无法对齐\n")
      has_trait <- FALSE
    }
  }
  trait_numeric <- wgcna_trait_data
  for (col in colnames(trait_numeric)) {
    if (is.character(trait_numeric[[col]]) || is.factor(trait_numeric[[col]])) {
      trait_numeric[[col]] <- as.numeric(factor(trait_numeric[[col]]))
    }
  }

  module_trait_cor <- cor(MEs, trait_numeric, use = "p")
  module_trait_p <- corPvalueStudent(module_trait_cor, nrow(trait_numeric))

  wgcna_module_trait <<- list(
    module_eigengenes = MEs,
    correlation = module_trait_cor,
    p_value = module_trait_p
  )

  cor_matrix <- as.matrix(module_trait_cor)
  p_matrix <- as.matrix(module_trait_p)

  text_labels <- matrix(paste(sprintf("%.2f", cor_matrix),
                             "\n(",
                             ifelse(p_matrix < 1e-100, "< 1e-100",
                                   sprintf("%.0e", p_matrix)),
                             ")", sep = ""),
                       nrow = nrow(cor_matrix))

  module_trait_path <- file.path(output_dir_val, "module_trait_heatmap.png")
  png(module_trait_path, width = stage4_width, height = stage4_height, res = 100)
  par(mar = c(8, 8.5, 3, 3))
  labeledHeatmap(
    Matrix = module_trait_cor,
    xLabels = colnames(module_trait_cor),
    yLabels = rownames(module_trait_cor),
    ySymbols = rownames(module_trait_cor),
    colorLabels = FALSE,
    colors = blueWhiteRed(50),
    textMatrix = text_labels,
    setStdMargins = FALSE,
    cex.text = 0.8,
    cex.lab = 1,
    zlim = c(-1, 1),
    main = "Module-trait relationships"
  )
  dev.off()
  cat("模块-性状关联热图PNG已保存\n")
  
  module_trait_pdf_path <- file.path(output_dir_val, "module_trait_heatmap.pdf")
  pdf(module_trait_pdf_path, width = stage4_width / 100, height = stage4_height / 100)
  par(mar = c(8, 8.5, 3, 3))
  labeledHeatmap(
    Matrix = module_trait_cor,
    xLabels = colnames(module_trait_cor),
    yLabels = rownames(module_trait_cor),
    ySymbols = rownames(module_trait_cor),
    colorLabels = FALSE,
    colors = blueWhiteRed(50),
    textMatrix = text_labels,
    setStdMargins = FALSE,
    cex.text = 0.8,
    cex.lab = 1,
    zlim = c(-1, 1),
    main = "Module-trait relationships"
  )
  dev.off()
  cat("模块-性状关联热图PDF已保存\n")

  cat("开始生成模块特征基因箱线图...\n")
  use_ggpubr <- require(ggpubr, quietly = TRUE)
  cat(paste0("ggpubr可用: ", use_ggpubr, "\n"))
  
  valid_me_names <- colnames(MEs)[colnames(MEs) != "MEgrey"]
  n_modules <- length(valid_me_names)
  
  plots_list <- list()
  
  if (n_modules > 0 && use_ggpubr) {
    n_traits <- ncol(wgcna_trait_data)
    total_plots <- n_modules * n_traits
    n_cols <- ceiling(sqrt(total_plots))
    n_rows <- ceiling(total_plots / n_cols)
    
    for (trait_idx in 1:n_traits) {
      trait_col_name <- colnames(wgcna_trait_data)[trait_idx]
      if (is.character(wgcna_trait_data[[trait_col_name]]) || is.factor(wgcna_trait_data[[trait_col_name]])) {
        trait_factor <- as.factor(wgcna_trait_data[[trait_col_name]])
      } else {
        trait_factor <- as.factor(ifelse(wgcna_trait_data[[trait_col_name]] > median(wgcna_trait_data[[trait_col_name]], na.rm=TRUE), "High", "Low"))
      }
      
      for (me_name in valid_me_names) {
        mod_color <- substring(me_name, 3)
        
        me_values <- as.numeric(MEs[, me_name])
        
        if (length(me_values) == length(trait_factor)) {
          plot_data <- data.frame(
            Group = trait_factor,
            Value = me_values
          )
          
          group_levels <- levels(trait_factor)
          if (length(group_levels) == 2) {
            comparisons_list <- list(c(group_levels[1], group_levels[2]))
          } else {
            comparisons_list <- combn(group_levels, 2, simplify = FALSE)
          }
          
          p_box <- ggboxplot(plot_data, x = "Group", y = "Value",
                             fill = "Group",
                             alpha = 0.3,
                             color = "Group",
                             palette = NULL,
                             add = "jitter",
                             jitter = list(width = 0.2, size = 1, alpha = 0.6),
                             size = 1.2,
                             legend = "none",
                             font.x = 12, font.y = 12) +
            labs(x = NULL, y = "Module Eigengene", 
                 title = paste(mod_color, "-", trait_col_name)) +
            theme_bw() +
            theme(
              plot.title = element_text(hjust = 0.5, size = 14, face = "bold"),
              axis.line = element_line(color = "black", size = 1.2),
              axis.ticks = element_line(color = "black", size = 1.2),
              axis.ticks.length = unit(3, "mm"),
              axis.title.y = element_text(size = 14, face = "bold"),
              axis.text.x = element_text(color = "black", size = 12, angle = 45, hjust = 1),
              axis.text.y = element_text(color = "black", size = 12),
              panel.grid = element_blank(),
              panel.border = element_rect(color = "black", size = 1.2),
              plot.margin = margin(10, 10, 10, 10)
            ) +
            scale_fill_brewer(palette = "Set2") +
            scale_color_brewer(palette = "Set2")
            
          if (show_significance) {
            p_box <- p_box + geom_signif(
              comparisons = comparisons_list,
              map_signif_level = FALSE,
              textsize = 4,
              test = t.test,
              step_increase = 0.2,
              size = 1.2,
              tip_length = 0.02
            )
          }
          
          plots_list[[paste(mod_color, trait_col_name, sep = "_")]] <- p_box
        } else {
          cat(paste0("模块 ", mod_color, ": ME值与性状长度不匹配，跳过\n"))
        }
      }
    }
  }
  
  me_boxplot_path <- file.path(output_dir_val, "module_me_boxplot.png")
  png(me_boxplot_path, width = stage4_width, height = stage4_height, res = 100)
  if (length(plots_list) > 0) {
    grid.arrange(grobs = plots_list, ncol = n_cols)
  } else {
    plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
    text(0, 0, "无有效模块，无法生成箱线图", cex = 1.2)
  }
  dev.off()
  cat("模块特征基因箱线图PNG已保存\n")
  
  me_boxplot_pdf_path <- file.path(output_dir_val, "module_me_boxplot.pdf")
  pdf(me_boxplot_pdf_path, width = stage4_width / 100, height = stage4_height / 100)
  if (length(plots_list) > 0) {
    grid.arrange(grobs = plots_list, ncol = n_cols)
  } else {
    plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
    text(0, 0, "无有效模块，无法生成箱线图", cex = 1.2)
  }
  dev.off()
  cat("模块特征基因箱线图PDF已保存\n")
} else {
  cat("性状数据不可用或维度不匹配，跳过模块-性状关联分析\n")
  
  module_trait_path <- file.path(output_dir_val, "module_trait_heatmap.png")
  png(module_trait_path, width = stage4_width, height = stage4_height, res = 100)
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "性状数据不可用", cex = 1.2)
  dev.off()
  
  pdf(file.path(output_dir_val, "module_trait_heatmap.pdf"), width = stage4_width / 100, height = stage4_height / 100)
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "性状数据不可用", cex = 1.2)
  dev.off()
  
  me_boxplot_path <- file.path(output_dir_val, "module_me_boxplot.png")
  png(me_boxplot_path, width = stage4_width, height = stage4_height, res = 100)
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "性状数据不可用", cex = 1.2)
  dev.off()
  
  pdf(file.path(output_dir_val, "module_me_boxplot.pdf"), width = stage4_width / 100, height = stage4_height / 100)
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "性状数据不可用", cex = 1.2)
  dev.off()
}

cat("开始生成模块-模块关联热图...\n")
MEs_no_grey <- MEs[, colnames(MEs) != "MEgrey", drop = FALSE]

if (ncol(MEs_no_grey) > 1) {
  me_cor <- cor(MEs_no_grey, use = "p")
  me_p <- corPvalueStudent(me_cor, nrow(MEs_no_grey))

  me_cor_matrix <- as.matrix(me_cor)
  me_p_matrix <- as.matrix(me_p)

  me_text_labels <- matrix(paste(sprintf("%.2f", me_cor_matrix),
                                 "\n(",
                                 ifelse(me_p_matrix < 1e-100, "< 1e-100",
                                       sprintf("%.0e", me_p_matrix)),
                                 ")", sep = ""),
                           nrow = nrow(me_cor_matrix))
}

module_cluster_path <- file.path(output_dir_val, "module_cluster_heatmap.png")
png(module_cluster_path, width = stage4_width, height = stage4_height, res = 100)
if (ncol(MEs_no_grey) > 1) {
  pheatmap(me_cor_matrix,
           color = colorRampPalette(c("#053061", "#2166AC", "#4393C3", "#92C5DE",
                                     "#D1E5F0", "#FFFFFF", "#FDDBC7", "#F4A582",
                                     "#D6604D", "#B2182B", "#67001F"))(100),
           breaks = seq(-1, 1, length.out = 101),
           cluster_rows = TRUE,
           cluster_cols = TRUE,
           show_rownames = TRUE,
           show_colnames = TRUE,
           fontsize = 12,
           fontsize_row = 12,
           fontsize_col = 12,
           main = "Module-Module Relationships",
           border_color = "white",
           display_numbers = me_text_labels,
           number_color = "black",
           fontsize_number = 9,
           legend = TRUE,
           legend_breaks = c(-1, -0.5, 0, 0.5, 1),
           legend_labels = c("-1", "-0.5", "0", "0.5", "1"))
} else {
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "模块数量不足，无法生成热图", cex = 1.2)
}
dev.off()
cat("模块-模块关联热图PNG已保存\n")

module_cluster_pdf_path <- file.path(output_dir_val, "module_cluster_heatmap.pdf")
pdf(module_cluster_pdf_path, width = stage4_width / 100, height = stage4_height / 100)
if (ncol(MEs_no_grey) > 1) {
  pheatmap(me_cor_matrix,
           color = colorRampPalette(c("#053061", "#2166AC", "#4393C3", "#92C5DE",
                                     "#D1E5F0", "#FFFFFF", "#FDDBC7", "#F4A582",
                                     "#D6604D", "#B2182B", "#67001F"))(100),
           breaks = seq(-1, 1, length.out = 101),
           cluster_rows = TRUE,
           cluster_cols = TRUE,
           show_rownames = TRUE,
           show_colnames = TRUE,
           fontsize = 12,
           fontsize_row = 12,
           fontsize_col = 12,
           main = "Module-Module Relationships",
           border_color = "white",
           display_numbers = me_text_labels,
           number_color = "black",
           fontsize_number = 9,
           legend = TRUE,
           legend_breaks = c(-1, -0.5, 0, 0.5, 1),
           legend_labels = c("-1", "-0.5", "0", "0.5", "1"))
} else {
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "模块数量不足，无法生成热图", cex = 1.2)
}
dev.off()
cat("模块-模块关联热图PDF已保存\n")

cat("开始生成基因显著性散点图...\n")
plots_list_gs <- list()

if (has_trait && ncol(wgcna_trait_data) > 0 && exists('wgcna_exprSet')) {
  trait_numeric_for_gs <- wgcna_trait_data
  for (col in colnames(trait_numeric_for_gs)) {
    if (is.character(trait_numeric_for_gs[[col]]) || is.factor(trait_numeric_for_gs[[col]])) {
      trait_numeric_for_gs[[col]] <- as.numeric(factor(trait_numeric_for_gs[[col]]))
    }
  }
  
  exprSet_for_gs <- wgcna_exprSet
  if (nrow(exprSet_for_gs) != nrow(MEs)) {
    common_rows <- intersect(rownames(exprSet_for_gs), rownames(MEs))
    if (length(common_rows) > 0) {
      exprSet_for_gs <- exprSet_for_gs[common_rows, , drop = FALSE]
    } else {
      cat("基因显著性散点图：表达矩阵与MEs无共同行\n")
    }
  }
  
  geneModuleMembership <- as.data.frame(cor(exprSet_for_gs, MEs, use = "p"))
  geneTraitSignificance <- as.data.frame(cor(exprSet_for_gs, trait_numeric_for_gs, use = "p"))
  
  module_labels <- wgcna_module_labels
  unique_modules <- unique(module_labels)
  unique_modules <- unique_modules[unique_modules != "grey"]
  
  n_modules <- length(unique_modules)
  
  if (n_modules > 0) {
    n_cols <- ceiling(sqrt(n_modules))
    n_rows <- ceiling(n_modules / n_cols)
    
    for (mod in unique_modules) {
      moduleGenes <- (module_labels == mod)
      mm_column <- paste0("ME", mod)
      
      if (mm_column %in% colnames(geneModuleMembership) && sum(moduleGenes) > 10) {
        MM <- abs(geneModuleMembership[moduleGenes, mm_column])
        GS <- abs(geneTraitSignificance[moduleGenes, 1])
        
        cor_test <- cor.test(MM, GS, method = "pearson")
        cor_value <- round(cor_test$estimate, 3)
        p_value <- format(cor_test$p.value, scientific = TRUE, digits = 2)
        
        plot_data <- data.frame(MM = MM, GS = GS)
        
        p_scatter <- ggplot(plot_data, aes(x = MM, y = GS)) +
          geom_point(color = mod, alpha = 0.7, size = 2) +
          geom_smooth(method = "lm", color = "black", linetype = "dashed", se = FALSE) +
          labs(x = paste("Module Membership in", mod, "module"),
               y = "Gene Significance",
               title = paste0("Module: ", mod,
                             "\nCorrelation = ", cor_value, ", P-value = ", p_value)) +
          theme_bw(base_size = 10) +
          theme(
            panel.grid.major = element_blank(),
            panel.grid.minor = element_blank(),
            panel.border = element_rect(color = "black", size = 1),
            axis.text = element_text(color = "black", size = 8),
            axis.title = element_text(color = "black", size = 10, face = "bold"),
            plot.title = element_text(hjust = 0.5, size = 10, face = "bold"),
            legend.position = "none"
          ) +
          annotate("text", x = Inf, y = Inf,
                   label = paste("n =", sum(moduleGenes)),
                   hjust = 1.1, vjust = 1.1, size = 3.5)
        
        plots_list_gs[[mod]] <- p_scatter
      }
    }
  }
}

gene_significance_path <- file.path(output_dir_val, "gene_significance_scatter.png")
png(gene_significance_path, width = stage4_width, height = stage4_height, res = 100)
if (length(plots_list_gs) > 0) {
  grid.arrange(grobs = plots_list_gs, ncol = n_cols)
} else {
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "无有效模块或数据不可用", cex = 1.2)
}
dev.off()
cat("基因显著性散点图PNG已保存\n")

gene_significance_pdf_path <- file.path(output_dir_val, "gene_significance_scatter.pdf")
pdf(gene_significance_pdf_path, width = stage4_width / 100, height = stage4_height / 100)
if (length(plots_list_gs) > 0) {
  grid.arrange(grobs = plots_list_gs, ncol = n_cols)
} else {
  plot(0, 0, type = "n", axes = FALSE, xlab = "", ylab = "")
  text(0, 0, "无有效模块或数据不可用", cex = 1.2)
}
dev.off()
cat("基因显著性散点图PDF已保存\n")

cat("阶段四完成: 图表已保存\n")

# --- STAGE4_BODY_END ---

# ========================================
# 阶段五：GO和KEGG富集分析
# ========================================
# --- STAGE5_BODY_START ---
cat("阶段五：GO和KEGG富集分析\n")

output_dir_val <- as.character(output_dir)[1]
cat("输出目录: ", output_dir_val, "\n")

if (!exists('wgcna_net') || is.null(wgcna_net)) {
  stop("wgcna_net不存在，请先运行阶段三")
}

if (!exists('selected_modules') || is.null(selected_modules)) {
  stop("请选择要分析的模块")
}

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
  organism <- "hsa"
} else {
  organism <- as.character(organism)[1]
}
cat("物种: ", organism, "\n")

if (organism == "hsa") {
  if (!use_orgHsEgDb) {
    stop("org.Hs.eg.db包未安装或未加载，请先安装org.Hs.eg.db")
  }
} else if (organism == "mmu") {
  if (!use_orgMmEgDb) {
    stop("org.Mm.eg.db包未安装或未加载，请先安装org.Mm.eg.db")
  }
} else if (organism == "rno") {
  if (!use_orgRnEgDb) {
    stop("org.Rn.eg.db包未安装或未加载，请先安装org.Rn.eg.db")
  }
} else if (organism == "dme") {
  if (!use_orgDmEgDb) {
    stop("org.Dm.eg.db包未安装或未加载，请先安装org.Dm.eg.db")
  }
} else {
  stop(paste0("不支持的物种: ", organism))
}

if (!exists('go_padj_cutoff')) {
  go_padj_cutoff <- 0.05
} else {
  go_padj_cutoff <- as.numeric(go_padj_cutoff)[1]
}
cat("GO校正p值阈值: ", go_padj_cutoff, "\n")

if (!exists('kegg_padj_cutoff')) {
  kegg_padj_cutoff <- 0.05
} else {
  kegg_padj_cutoff <- as.numeric(kegg_padj_cutoff)[1]
}
cat("KEGG校正p值阈值: ", kegg_padj_cutoff, "\n")

if (!exists('go_top_n')) {
  go_top_n <- 15
} else {
  go_top_n <- as.integer(go_top_n)[1]
}
cat("GO展示条目数: ", go_top_n, "\n")

if (!exists('kegg_top_n')) {
  kegg_top_n <- 15
} else {
  kegg_top_n <- as.integer(kegg_top_n)[1]
}
cat("KEGG展示条目数: ", kegg_top_n, "\n")

gene_names <- colnames(wgcna_exprSet)
module_labels <- labels2colors(wgcna_net$colors)
selected_modules <- as.character(selected_modules)

for (mod in selected_modules) {
  cat(paste0("\n=== 处理模块 ", mod, " ===\n"))
  mod_genes <- gene_names[module_labels == mod]
  cat(paste0("模块 ", mod, ": ", length(mod_genes), " 个基因\n"))
  
  if (length(mod_genes) < 10) {
    cat(paste0("模块 ", mod, " 基因数太少(<10)，跳过富集分析\n"))
    next
  }
  
  cat("转换基因ID为ENTREZ格式...\n")
  if (organism == "hsa") {
    mod_genes_entrez <- mapIds(org.Hs.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else if (organism == "mmu") {
    mod_genes_entrez <- mapIds(org.Mm.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else if (organism == "rno") {
    mod_genes_entrez <- mapIds(org.Rn.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else if (organism == "dme") {
    mod_genes_entrez <- mapIds(org.Dm.eg.db, mod_genes, "ENTREZID", "SYMBOL")
  } else {
    cat(paste0("不支持的物种: ", organism, "，跳过分析\n"))
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
    if (organism == "hsa") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Hs.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff,
        qvalueCutoff = go_padj_cutoff,
        readable = TRUE
      )
    } else if (organism == "mmu") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Mm.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff,
        qvalueCutoff = go_padj_cutoff,
        readable = TRUE
      )
    } else if (organism == "rno") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Rn.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff,
        qvalueCutoff = go_padj_cutoff,
        readable = TRUE
      )
    } else if (organism == "dme") {
      enrichGO(
        gene = mod_genes_entrez,
        OrgDb = org.Dm.eg.db,
        keyType = "ENTREZID",
        ont = "all",
        pvalueCutoff = go_padj_cutoff,
        qvalueCutoff = go_padj_cutoff,
        readable = TRUE
      )
    } else {
      cat(paste0("不支持的物种: ", organism, "，跳过GO分析\n"))
      return(NULL)
    }
  }, error = function(e) {
    cat(paste0("GO分析出错: ", e$message, "\n"))
    cat("尝试不使用readable参数重新运行...\n")
    tryCatch({
      if (organism == "hsa") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Hs.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff,
          qvalueCutoff = go_padj_cutoff,
          readable = FALSE
        )
      } else if (organism == "mmu") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Mm.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff,
          qvalueCutoff = go_padj_cutoff,
          readable = FALSE
        )
      } else if (organism == "rno") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Rn.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff,
          qvalueCutoff = go_padj_cutoff,
          readable = FALSE
        )
      } else if (organism == "dme") {
        enrichGO(
          gene = mod_genes_entrez,
          OrgDb = org.Dm.eg.db,
          keyType = "ENTREZID",
          ont = "all",
          pvalueCutoff = go_padj_cutoff,
          qvalueCutoff = go_padj_cutoff,
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
    print(dotplot(go_result, showCategory = go_top_n, label_format=100, split="ONTOLOGY") + 
            facet_grid(ONTOLOGY~., scale='free') + 
            ggtitle(go_title))
    dev.off()
    cat(paste0("GO气泡图PNG已保存: ", go_bubble_path, "\n"))
    
    go_bubble_pdf_path <- file.path(output_dir_val, paste0("GO_bubble_", mod, ".pdf"))
    pdf(go_bubble_pdf_path, width = 10, height = 15)
    print(dotplot(go_result, showCategory = go_top_n, label_format=100, split="ONTOLOGY") + 
            facet_grid(ONTOLOGY~., scale='free') + 
            ggtitle(go_title))
    dev.off()
    cat(paste0("GO气泡图PDF已保存: ", go_bubble_pdf_path, "\n"))
    
    go_bar_path <- file.path(output_dir_val, paste0("GO_bar_", mod, ".png"))
    png(go_bar_path, width = 1000, height = 1500, res = 100)
    print(barplot(go_result, drop = TRUE, showCategory = go_top_n, label_format=100, split="ONTOLOGY") + 
            facet_grid(ONTOLOGY~., scale='free') + 
            ggtitle(go_title))
    dev.off()
    cat(paste0("GO条图PNG已保存: ", go_bar_path, "\n"))
    
    go_bar_pdf_path <- file.path(output_dir_val, paste0("GO_bar_", mod, ".pdf"))
    pdf(go_bar_pdf_path, width = 10, height = 15)
    print(barplot(go_result, drop = TRUE, showCategory = go_top_n, label_format=100, split="ONTOLOGY") + 
            facet_grid(ONTOLOGY~., scale='free') + 
            ggtitle(go_title))
    dev.off()
    cat(paste0("GO条图PDF已保存: ", go_bar_pdf_path, "\n"))
    
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
      organism = organism,
      pvalueCutoff = kegg_padj_cutoff,
      qvalueCutoff = kegg_padj_cutoff,
      pAdjustMethod = "fdr"
    )
  }, error = function(e) {
    cat(paste0("KEGG分析出错: ", e$message, "\n"))
    cat("可能是网络问题，尝试使用本地数据库...\n")
    return(NULL)
  })
  
  if (!is.null(kegg_result) && nrow(kegg_result) > 0) {
    kegg_result_df <- as.data.frame(kegg_result)
    write.table(kegg_result_df, file.path(output_dir_val, paste0("KEGG_", mod, ".txt")), sep="\t", quote=F, row.names=F)
    
    kegg_title <- paste0("KEGG Enrichment Analysis - Module ", mod)
    
    kegg_bar_path <- file.path(output_dir_val, paste0("KEGG_bar_", mod, ".png"))
    png(kegg_bar_path, width = 1000, height = 1300, res = 100)
    print(barplot(kegg_result, drop = TRUE, showCategory = kegg_top_n, label_format=100) + 
            ggtitle(kegg_title))
    dev.off()
    cat(paste0("KEGG条图PNG已保存: ", kegg_bar_path, "\n"))
    
    kegg_bar_pdf_path <- file.path(output_dir_val, paste0("KEGG_bar_", mod, ".pdf"))
    pdf(kegg_bar_pdf_path, width = 10, height = 13)
    print(barplot(kegg_result, drop = TRUE, showCategory = kegg_top_n, label_format=100) + 
            ggtitle(kegg_title))
    dev.off()
    cat(paste0("KEGG条图PDF已保存: ", kegg_bar_pdf_path, "\n"))
    
    kegg_bubble_path <- file.path(output_dir_val, paste0("KEGG_bubble_", mod, ".png"))
    png(kegg_bubble_path, width = 1000, height = 600, res = 100)
    print(dotplot(kegg_result, showCategory = kegg_top_n, label_format=100) + 
            ggtitle(kegg_title))
    dev.off()
    cat(paste0("KEGG气泡图PNG已保存: ", kegg_bubble_path, "\n"))
    
    kegg_bubble_pdf_path <- file.path(output_dir_val, paste0("KEGG_bubble_", mod, ".pdf"))
    pdf(kegg_bubble_pdf_path, width = 10, height = 6)
    print(dotplot(kegg_result, showCategory = kegg_top_n, label_format=100) + 
            ggtitle(kegg_title))
    dev.off()
    cat(paste0("KEGG气泡图PDF已保存: ", kegg_bubble_pdf_path, "\n"))
    
    kegg_result_df <- as.data.frame(kegg_result)
    kegg_table_path <- file.path(output_dir_val, paste0("KEGG_result_", mod, ".xlsx"))
    openxlsx::write.xlsx(kegg_result_df, kegg_table_path, rowNames = FALSE)
    cat(paste0("KEGG结果表格已保存: ", kegg_table_path, "\n"))
  } else {
    cat(paste0("模块 ", mod, " KEGG富集分析无显著结果\n"))
  }
}

cat("阶段五完成: GO和KEGG富集分析完成\n")

# --- STAGE5_BODY_END ---

# ========================================
# 阶段六：导出基因集合
# ========================================
# --- STAGE6_BODY_START ---
cat("阶段六：导出基因集合\n")

output_dir_val <- as.character(output_dir)[1]
cat("输出目录: ", output_dir_val, "\n")
cat("目录是否存在: ", dir.exists(output_dir_val), "\n")

if (!exists('wgcna_net') || is.null(wgcna_net)) {
  stop("wgcna_net不存在，请先运行阶段三")
}

if (!exists('selected_modules') || is.null(selected_modules)) {
  stop("请选择要导出的模块")
}

if (!exists('base_name')) {
  base_name <- "module_genes"
} else {
  base_name <- as.character(base_name)[1]
}
cat("基础文件名: ", base_name, "\n")

if (!exists('merge_modules')) {
  merge_modules <- FALSE
} else {
  merge_modules <- as.logical(merge_modules)[1]
}
cat("是否合并模块: ", merge_modules, "\n")

selected_modules <- as.character(selected_modules)
cat("要导出的模块: ", paste(selected_modules, collapse=", "), "\n")

gene_names <- colnames(wgcna_exprSet)
module_labels <- labels2colors(wgcna_net$colors)

if (merge_modules && length(selected_modules) > 0) {
  all_genes <- c()
  
  for (mod in selected_modules) {
    mod_genes <- gene_names[module_labels == mod]
    cat(paste0("模块 ", mod, ": ", length(mod_genes), " 个基因\n"))
    
    if (length(mod_genes) > 0) {
      all_genes <- c(all_genes, mod_genes)
    }
  }
  
  if (length(all_genes) > 0) {
    gene_df <- data.frame(Gene = all_genes)
    
    file_path <- file.path(output_dir_val, paste0(base_name, ".xlsx"))
    openxlsx::write.xlsx(gene_df, file_path, rowNames = FALSE, colNames = FALSE)
    cat(paste0("已导出合并表格: ", file_path, "\n"))
  }
} else {
  for (mod in selected_modules) {
    mod_genes <- gene_names[module_labels == mod]
    cat(paste0("模块 ", mod, ": ", length(mod_genes), " 个基因\n"))
    
    if (length(mod_genes) > 0) {
      gene_df <- data.frame(Gene = mod_genes)
      
      file_path <- file.path(output_dir_val, paste0(base_name, "_", mod, ".xlsx"))
      openxlsx::write.xlsx(gene_df, file_path, rowNames = FALSE, colNames = FALSE)
      cat(paste0("已导出: ", file_path, "\n"))
    }
  }
}

cat("阶段六完成: 基因集合已导出\n")

# --- STAGE6_BODY_END ---