# -*- coding: utf-8 -*-
# Monocle基因列表类子层R脚本
# 功能：基于CDS对象运行graph_test(Moran's I检验)，输出所有基因的Moran's I结果到TSV
# 用法：Rscript run_monocle_genelists.R <cds_rds_path> <output_dir> <dataset_name> <gene_filter_mode> [n_top] [gene_list_path]
#   gene_filter_mode: "all"=全部基因 / "hvg"=高变基因前N个(CDS ordering_genes) / "list"=外部基因列表
#   n_top: 当mode=hvg时使用，默认2000
#   gene_list_path: 当mode=list时使用，txt文件(每行一个基因名或逗号分隔)

library(monocle3)
library(dplyr)

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 4) {
  cat("Usage: Rscript run_monocle_genelists.R <cds_rds_path> <output_dir> <dataset_name> <gene_filter_mode> [n_top] [gene_list_path]\n")
  quit(status = 1)
}

cds_rds_path <- args[1]
output_dir <- args[2]
dataset_name <- args[3]
gene_filter_mode <- args[4]
n_top <- if (length(args) >= 5) as.integer(args[5]) else 2000
gene_list_path <- if (length(args) >= 6) args[6] else ""

dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

if (!file.exists(cds_rds_path)) {
  cds_rds_path <- normalizePath(cds_rds_path, mustWork = FALSE)
  if (!file.exists(cds_rds_path)) {
    cat(paste("ERROR: CDS文件不存在:", cds_rds_path, "\n"))
    quit(status = 1)
  }
}

cat(paste("[Genelists] 正在加载CDS对象:", cds_rds_path, "\n"))
cds <- readRDS(cds_rds_path)
cat(paste("[Genelists] CDS对象加载完成, 细胞数:", ncol(cds), "基因数:", nrow(cds), "\n"))

# 检查principal_graph是否存在（graph_test依赖）
has_principal_graph <- tryCatch({
  colData(cds)
  reducedDims(cds)
  ("UMAP" %in% names(reducedDims(cds))) || ("PCA" %in% names(reducedDims(cds)))
}, error = function(e) FALSE)

if (!has_principal_graph) {
  cat("ERROR: CDS对象缺少降维结果(UMAP/PCA)，无法运行graph_test\n")
  quit(status = 1)
}

# 检查principal_graph是否已设置
has_pr_graph <- tryCatch({
  g <- principal_graph(cds)
  length(g) > 0
}, error = function(e) FALSE)

if (!has_pr_graph) {
  cat("ERROR: CDS对象缺少principal_graph，请确认rds来自初筛轨迹类阶段四导出\n")
  quit(status = 1)
}

cat(paste("[Genelists] 降维与principal_graph检查通过\n"))

# 按筛选模式处理基因子集
selected_genes <- NULL

if (gene_filter_mode == "all") {
  cat("[Genelists] 筛选模式: 全部基因\n")
  selected_genes <- rownames(cds)

} else if (gene_filter_mode == "hvg") {
  cat(paste0("[Genelists] 筛选模式: 高变基因前", n_top, "个\n"))
  # 优先使用CDS的ordering_genes
  ordering_genes <- tryCatch({
    cds@preprocessed_data$ordering_genes
  }, error = function(e) NULL)

  if (is.null(ordering_genes) || length(ordering_genes) == 0) {
    # 备用方案：使用highly_variable_genes属性
    ordering_genes <- tryCatch({
      fData(cds)$use_for_ordering
    }, error = function(e) NULL)
    if (!is.null(ordering_genes)) {
      ordering_genes <- rownames(fData(cds))[which(ordering_genes)]
    }
  }

  if (is.null(ordering_genes) || length(ordering_genes) == 0) {
    # 最终备用方案：计算高变基因
    cat(paste0("[Genelists] WARNING: 未找到ordering_genes，正在计算高变基因...\n"))
    
    expr_mat <- tryCatch({
      SummarizedExperiment::assay(cds, "counts")
    }, error = function(e) {
      tryCatch({
        SummarizedExperiment::assay(cds, "logcounts")
      }, error = function(e) {
        cat("ERROR: 无法获取表达量矩阵\n")
        quit(status = 1)
      })
    })
    
    if (is.null(expr_mat)) {
      cat("ERROR: 无法获取表达量矩阵\n")
      quit(status = 1)
    }
    
    gene_vars <- apply(expr_mat, 1, var)
    gene_means <- rowMeans(expr_mat)
    
    gene_vars <- gene_vars[gene_means > 0]
    gene_means <- gene_means[gene_means > 0]
    
    if (length(gene_vars) == 0) {
      cat(paste0("[Genelists] WARNING: 表达量全部为0，使用全部基因的前", n_top, "个\n"))
      selected_genes <- rownames(cds)[1:min(n_top, nrow(cds))]
    } else {
      cv <- sqrt(gene_vars) / gene_means
      cv[is.infinite(cv) | is.na(cv)] <- 0
      
      top_hvg <- names(sort(cv, decreasing = TRUE)[1:min(n_top, length(cv))])
      
      cat(paste0("[Genelists] 计算得到高变基因: ", length(top_hvg), " 个\n"))
      selected_genes <- top_hvg
    }
  } else {
    cat(paste0("[Genelists] 找到ordering_genes: ", length(ordering_genes), " 个\n"))
    selected_genes <- ordering_genes[1:min(n_top, length(ordering_genes))]
  }

} else if (gene_filter_mode == "list") {
  cat(paste0("[Genelists] 筛选模式: 外部基因列表, 文件: ", gene_list_path, "\n"))
  if (gene_list_path == "" || !file.exists(gene_list_path)) {
    cat(paste("ERROR: 基因列表文件不存在:", gene_list_path, "\n"))
    quit(status = 1)
  }
  # 读取txt文件（每行一个基因名或逗号分隔）
  file_content <- readLines(gene_list_path, encoding = "UTF-8")
  genes_raw <- unlist(strsplit(file_content, ",|\\s+|\\t|;"))
  genes_clean <- trimws(genes_raw)
  genes_clean <- genes_clean[genes_clean != ""]
  # 取交集（仅保留CDS中存在的基因）
  all_genes <- rownames(cds)
  selected_genes <- intersect(genes_clean, all_genes)
  cat(paste0("[Genelists] 列表中基因数: ", length(genes_clean), ", 与CDS取交集后: ", length(selected_genes), " 个\n"))

  if (length(selected_genes) == 0) {
    cat("ERROR: 基因列表与CDS中基因无交集\n")
    quit(status = 1)
  }

} else {
  cat(paste("ERROR: 未知筛选模式:", gene_filter_mode, "\n"))
  quit(status = 1)
}

cat(paste0("[Genelists] 实际计算基因数: ", length(selected_genes), "\n"))

# 对CDS进行基因子集化（保留降维结果和principal_graph）
if (length(selected_genes) < nrow(cds)) {
  cat("[Genelists] 正在subset CDS对象...\n")
  cds <- cds[selected_genes, ]
  cat(paste0("[Genelists] subset完成, 剩余基因数: ", nrow(cds), "\n"))
}

# 运行graph_test
cat("[Genelists] 开始运行graph_test(Moran's I检验)...\n")
cat("[Genelists] 这可能需要几分钟，请耐心等待...\n")

pr_test_res <- tryCatch({
  monocle3::graph_test(cds, neighbor_graph = "principal_graph", cores = 1)
}, error = function(e) {
  cat(paste("ERROR: graph_test执行失败:", e$message, "\n"))
  quit(status = 1)
})

cat(paste0("[Genelists] graph_test完成, 结果行数: ", nrow(pr_test_res), "\n"))

# 输出到TSV文件（保留所有列）
output_tsv <- file.path(output_dir, paste0(dataset_name, "_graph_test_result.tsv"))

# 确保gene_id列存在
if (!"gene_id" %in% colnames(pr_test_res)) {
  pr_test_res$gene_id <- rownames(pr_test_res)
}

# 重新排列列顺序：gene_id在前
col_order <- c("gene_id", setdiff(colnames(pr_test_res), "gene_id"))
pr_test_res <- pr_test_res[, col_order]

write.table(pr_test_res, file = output_tsv, sep = "\t", row.names = FALSE, quote = FALSE)

cat(paste0("[Genelists] 结果已保存: ", output_tsv, "\n"))

# 输出统计信息
cat(paste0("[Genelists] === 统计信息 ===\n"))
cat(paste0("[Genelists] 总基因数: ", nrow(pr_test_res), "\n"))
if ("p_value" %in% colnames(pr_test_res)) {
  sig_p <- sum(pr_test_res$p_value < 0.05, na.rm = TRUE)
  cat(paste0("[Genelists] p<0.05显著基因数: ", sig_p, "\n"))
}
if ("q_value" %in% colnames(pr_test_res)) {
  sig_q <- sum(pr_test_res$q_value < 0.05, na.rm = TRUE)
  cat(paste0("[Genelists] q<0.05显著基因数: ", sig_q, "\n"))
}

cat(output_tsv)
cat("\n")
quit(status = 0)
