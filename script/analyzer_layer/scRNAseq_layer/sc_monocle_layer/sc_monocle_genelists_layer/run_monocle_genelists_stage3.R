# -*- coding: utf-8 -*-
# Monocle基因列表类子层 - 阶段三R脚本
# 功能：基于CDS对象运行基因表达与伪时间关系分析，支持多种算法
#       输出上下调分类结果（up/down/not_significant）
# 用法：Rscript run_monocle_genelists_stage3.R <cds_rds_path> <gene_list_path> <output_dir> <dataset_name> <algorithm>
#   algorithm: spearman / loess / wilcoxon

library(monocle3)

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 5) {
  cat("Usage: Rscript run_monocle_genelists_stage3.R <cds_rds_path> <gene_list_path> <output_dir> <dataset_name> <algorithm>\n")
  cat("  algorithm: spearman / loess / wilcoxon\n")
  quit(status = 1)
}

cds_rds_path <- args[1]
gene_list_path <- args[2]
output_dir <- args[3]
dataset_name <- args[4]
algorithm <- args[5]

if (!(algorithm %in% c("spearman", "loess", "wilcoxon"))) {
  cat(paste("ERROR: 未知算法:", algorithm, "\n"))
  cat("支持的算法: spearman / loess / wilcoxon\n")
  quit(status = 1)
}

dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

if (!file.exists(cds_rds_path)) {
  cds_rds_path <- normalizePath(cds_rds_path, mustWork = FALSE)
  if (!file.exists(cds_rds_path)) {
    cat(paste("ERROR: CDS文件不存在:", cds_rds_path, "\n"))
    quit(status = 1)
  }
}

cat(paste0("[Stage3] 正在加载CDS对象: ", cds_rds_path, "\n"))
cds <- readRDS(cds_rds_path)
cat(paste0("[Stage3] CDS对象加载完成, 细胞数: ", ncol(cds), " 基因数: ", nrow(cds), "\n"))
cat(paste0("[Stage3] 算法: ", algorithm, "\n"))

# 获取伪时间
cat("[Stage3] 正在获取伪时间...\n")
pseudotime_vals <- tryCatch({
  monocle3::pseudotime(cds)
}, error = function(e) {
  cat(paste("ERROR: 无法获取伪时间:", e$message, "\n"))
  quit(status = 1)
})

if (is.null(pseudotime_vals) || all(is.na(pseudotime_vals))) {
  cat("ERROR: CDS对象中未包含有效的伪时间数据，请确认rds文件来自初筛轨迹类阶段四导出\n")
  quit(status = 1)
}

valid_pt_mask <- !is.na(pseudotime_vals) & is.finite(pseudotime_vals)
valid_pt_count <- sum(valid_pt_mask)
cat(paste0("[Stage3] 有效伪时间细胞数: ", valid_pt_count, " / ", length(pseudotime_vals), "\n"))

if (valid_pt_count < 10) {
  cat("ERROR: 有效伪时间细胞数过少(<10)，无法进行相关性分析\n")
  quit(status = 1)
}

# 获取表达量矩阵
cat("[Stage3] 正在获取表达量矩阵...\n")
exprs_mat <- tryCatch({
  SummarizedExperiment::assay(cds, "counts")
}, error = function(e) {
  cat(paste0("[Stage3] WARNING: assay(cds, 'counts')失败: ", e$message, "\n"))
  NULL
})

if (is.null(exprs_mat)) {
  cat("[Stage3] 尝试 assay(cds, 1) 获取第一个assay...\n")
  exprs_mat <- tryCatch({
    SummarizedExperiment::assay(cds, 1)
  }, error = function(e) {
    cat(paste0("[Stage3] WARNING: assay(cds, 1)失败: ", e$message, "\n"))
    NULL
  })
}

if (is.null(exprs_mat)) {
  cat("ERROR: 无法获取表达量矩阵（所有assay访问方式均失败）\n")
  cat(paste0("[Debug] 可用assay名称: ", paste(names(SummarizedExperiment::assays(cds)), collapse=", "), "\n"))
  quit(status = 1)
}

# 检查数据是否已经是log-normalized
if (inherits(exprs_mat, "dgCMatrix")) {
  max_val <- max(exprs_mat@x, na.rm = TRUE)
} else {
  max_val <- max(exprs_mat, na.rm = TRUE)
}
cat(paste0("[Stage3] 表达量矩阵最大值: ", round(max_val, 4), "\n"))
if (max_val > 100) {
  cat("[Stage3] 检测到原始counts，应用log1p转换...\n")
  exprs_mat <- log1p(exprs_mat)
}

cat(paste0("[Stage3] 表达量矩阵维度: ", nrow(exprs_mat), " 基因 x ", ncol(exprs_mat), " 细胞\n"))

# 读取基因列表
if (!file.exists(gene_list_path)) {
  cat(paste("ERROR: 基因列表文件不存在:", gene_list_path, "\n"))
  quit(status = 1)
}

file_content <- readLines(gene_list_path, encoding = "UTF-8")
genes_raw <- unlist(strsplit(file_content, ",|\\s+|\\t|;"))
genes_clean <- trimws(genes_raw)
genes_clean <- genes_clean[genes_clean != ""]

cat(paste0("[Stage3] 基因列表文件中基因数: ", length(genes_clean), "\n"))

# 取交集
all_genes <- rownames(exprs_mat)
selected_genes <- intersect(genes_clean, all_genes)
cat(paste0("[Stage3] 与CDS取交集后: ", length(selected_genes), " 个基因\n"))

if (length(selected_genes) == 0) {
  cat("ERROR: 基因列表与CDS中基因无交集\n")
  quit(status = 1)
}

# 提取有效细胞的表达量子集
exprs_subset <- exprs_mat[selected_genes, valid_pt_mask, drop = FALSE]
pt_subset <- pseudotime_vals[valid_pt_mask]

cat(paste0("[Stage3] 实际计算矩阵: ", nrow(exprs_subset), " 基因 x ", ncol(exprs_subset), " 细胞\n"))

# ========== 算法实现 ==========

n_genes <- length(selected_genes)
results <- data.frame(
  gene_id = character(n_genes),
  rho = numeric(n_genes),
  p_value = numeric(n_genes),
  stringsAsFactors = FALSE
)

if (algorithm == "spearman") {
  cat("[Stage3] 开始计算Spearman相关性...\n")
  
  for (i in seq_len(n_genes)) {
    gene <- selected_genes[i]
    expr_vec <- as.numeric(exprs_subset[i, ])
    
    if (sd(expr_vec) == 0) {
      results$gene_id[i] <- gene
      results$rho[i] <- NA
      results$p_value[i] <- NA
    } else {
      ct <- tryCatch({
        cor.test(expr_vec, pt_subset, method = "spearman", exact = FALSE)
      }, error = function(e) NULL)
      
      if (is.null(ct)) {
        results$gene_id[i] <- gene
        results$rho[i] <- NA
        results$p_value[i] <- NA
      } else {
        results$gene_id[i] <- gene
        results$rho[i] <- ct$estimate
        results$p_value[i] <- ct$p.value
      }
    }
    
    if (i %% 100 == 0 || i == n_genes) {
      cat(paste0("[Stage3] 进度: ", i, " / ", n_genes, " (", round(i / n_genes * 100), "%)\n"))
    }
  }
  cat("[Stage3] Spearman相关性计算完成\n")
  
} else if (algorithm == "loess") {
  cat("[Stage3] 开始计算LOESS回归...\n")
  cat("[Stage3] 提示: LOESS算法较慢，对于大量基因请考虑使用Spearman\n")
  
  for (i in seq_len(n_genes)) {
    gene <- selected_genes[i]
    expr_vec <- as.numeric(exprs_subset[i, ])
    
    if (sd(expr_vec) == 0) {
      results$gene_id[i] <- gene
      results$rho[i] <- NA
      results$p_value[i] <- NA
    } else {
      # LOESS回归：拟合表达量随伪时间变化的平滑曲线
      loess_fit <- tryCatch({
        loess(expr_vec ~ pt_subset, span = 0.75)
      }, error = function(e) NULL)
      
      if (is.null(loess_fit)) {
        results$gene_id[i] <- gene
        results$rho[i] <- NA
        results$p_value[i] <- NA
      } else {
        # 计算LOESS曲线的整体斜率（用Spearman相关系数近似趋势方向）
        loess_pred <- predict(loess_fit)
        trend_cor <- tryCatch({
          cor(pt_subset, loess_pred, method = "spearman")
        }, error = function(e) 0)
        
        # 用anova检验LOESS拟合是否显著
        loess_anova <- tryCatch({
          anova(loess_fit)
        }, error = function(e) NULL)
        
        if (!is.null(loess_anova) && nrow(loess_anova) > 0) {
          p_val <- loess_anova$"Pr(>F)"[1]
        } else {
          # 备用：用t检验比较LOESS预测值与均值的差异
          p_val <- tryCatch({
            t.test(loess_pred, mu = mean(expr_vec))$p.value
          }, error = function(e) 1)
        }
        
        results$gene_id[i] <- gene
        results$rho[i] <- trend_cor
        results$p_value[i] <- p_val
      }
    }
    
    if (i %% 50 == 0 || i == n_genes) {
      cat(paste0("[Stage3] 进度: ", i, " / ", n_genes, " (", round(i / n_genes * 100), "%)\n"))
    }
  }
  cat("[Stage3] LOESS回归计算完成\n")
  
} else if (algorithm == "wilcoxon") {
  cat("[Stage3] 开始计算Wilcoxon检验（早期vs晚期细胞）...\n")
  
  # 按伪时间中位数划分早期/晚期细胞
  pt_median <- median(pt_subset, na.rm = TRUE)
  early_mask <- pt_subset <= pt_median
  late_mask <- pt_subset > pt_median
  
  early_count <- sum(early_mask)
  late_count <- sum(late_mask)
  cat(paste0("[Stage3] 早期细胞数: ", early_count, ", 晚期细胞数: ", late_count, "\n"))
  
  for (i in seq_len(n_genes)) {
    gene <- selected_genes[i]
    expr_vec <- as.numeric(exprs_subset[i, ])
    
    early_expr <- expr_vec[early_mask]
    late_expr <- expr_vec[late_mask]
    
    if (sd(c(early_expr, late_expr)) == 0) {
      results$gene_id[i] <- gene
      results$rho[i] <- NA
      results$p_value[i] <- NA
    } else {
      wc <- tryCatch({
        wilcox.test(early_expr, late_expr, exact = FALSE)
      }, error = function(e) NULL)
      
      if (is.null(wc)) {
        results$gene_id[i] <- gene
        results$rho[i] <- NA
        results$p_value[i] <- NA
      } else {
        # rho表示趋势方向：晚期均值 - 早期均值
        early_mean <- mean(early_expr, na.rm = TRUE)
        late_mean <- mean(late_expr, na.rm = TRUE)
        trend_dir <- sign(late_mean - early_mean)
        
        results$gene_id[i] <- gene
        results$rho[i] <- trend_dir
        results$p_value[i] <- wc$p.value
      }
    }
    
    if (i %% 100 == 0 || i == n_genes) {
      cat(paste0("[Stage3] 进度: ", i, " / ", n_genes, " (", round(i / n_genes * 100), "%)\n"))
    }
  }
  cat("[Stage3] Wilcoxon检验计算完成\n")
}

# BH-FDR校正
valid_p_mask <- !is.na(results$p_value)
results$q_value <- NA_real_
if (sum(valid_p_mask) > 0) {
  results$q_value[valid_p_mask] <- p.adjust(results$p_value[valid_p_mask], method = "BH")
}

cat(paste0("[Stage3] BH-FDR校正完成\n"))

# 输出到TSV文件
output_tsv <- file.path(output_dir, paste0(dataset_name, "_", algorithm, "_result.tsv"))
write.table(results, file = output_tsv, sep = "\t", row.names = FALSE, quote = FALSE)
cat(paste0("[Stage3] 结果已保存: ", output_tsv, "\n"))

# 输出统计信息
cat(paste0("[Stage3] === 统计信息 ===\n"))
cat(paste0("[Stage3] 总基因数: ", nrow(results), "\n"))
valid_rho_mask <- !is.na(results$rho)
cat(paste0("[Stage3] 有效rho基因数: ", sum(valid_rho_mask), "\n"))
if (sum(valid_rho_mask) > 0) {
  up_count <- sum(results$rho > 0, na.rm = TRUE)
  down_count <- sum(results$rho < 0, na.rm = TRUE)
  cat(paste0("[Stage3] rho>0 (上调候选): ", up_count, "\n"))
  cat(paste0("[Stage3] rho<0 (下调候选): ", down_count, "\n"))
}
if ("p_value" %in% colnames(results)) {
  sig_p <- sum(results$p_value < 0.05, na.rm = TRUE)
  cat(paste0("[Stage3] p<0.05基因数: ", sig_p, "\n"))
}
if ("q_value" %in% colnames(results)) {
  sig_q <- sum(results$q_value < 0.05, na.rm = TRUE)
  cat(paste0("[Stage3] q<0.05基因数: ", sig_q, "\n"))
}

cat(output_tsv)
cat("\n")
quit(status = 0)
