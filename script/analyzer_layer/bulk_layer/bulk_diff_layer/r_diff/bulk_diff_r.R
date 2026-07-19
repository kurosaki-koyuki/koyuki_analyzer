# -*- coding: utf-8 -*-
#
# bulk差异分析 R脚本
# 包含两种方法：
#   1. limma: 适用于标准化的TPM/微阵列数据
#   2. edgeR: 适用于Count计数数据
#
# 参数:
#   expr_mat: 表达矩阵，行是基因，列是样本
#   sample_labels: 样本分组标签
#   group1_name: 组1名称
#   group2_name: 组2名称
#   method: "limma" 或 "edger"
#
# 返回:
#   数据框，包含gene, mean_group1, mean_group2, log2FC, p_val, adj_p_val

# --- FUNCTION_BODY_START ---

library(limma)
library(edgeR)

run_diff_analysis <- function(expr_mat, sample_labels, group1_name, group2_name, method = "limma") {
    if (method == "limma") {
        result <- run_limma(expr_mat, sample_labels, group1_name, group2_name)
    } else if (method == "edger") {
        result <- run_edger(expr_mat, sample_labels, group1_name, group2_name)
    } else {
        stop(paste("未知方法:", method))
    }
    return(result)
}

run_limma <- function(expr_mat, sample_labels, group1_name, group2_name) {
    group <- factor(sample_labels, levels = c(group1_name, group2_name))
    design <- model.matrix(~group)

    expr_log <- log2(expr_mat + 1)

    fit <- lmFit(expr_log, design)
    fit <- eBayes(fit)

    results <- topTable(fit, coef = 2, number = Inf, adjust = "fdr")

    group1_samples <- sample_labels == group1_name
    group2_samples <- sample_labels == group2_name
    mean_group1 <- rowMeans(expr_log[, group1_samples, drop = FALSE])
    mean_group2 <- rowMeans(expr_log[, group2_samples, drop = FALSE])

    result_df <- data.frame(
        gene = rownames(results),
        mean_group1 = mean_group1[rownames(results)],
        mean_group2 = mean_group2[rownames(results)],
        log2FC = results$logFC,
        p_val = results$P.Value,
        adj_p_val = results$adj.P.Val,
        stringsAsFactors = FALSE
    )

    rownames(result_df) <- NULL
    return(result_df)
}

run_edger <- function(count_mat, sample_labels, group1_name, group2_name) {
    group <- factor(sample_labels, levels = c(group1_name, group2_name))

    y <- DGEList(counts = count_mat, group = group)

    keep <- filterByExpr(y)
    y <- y[keep, , keep.lib.sizes = FALSE]

    y <- normLibSizes(y)

    design <- model.matrix(~group)

    y <- estimateDisp(y, design)

    fit <- exactTest(y)

    results <- topTags(fit, n = Inf)

    logcpm <- cpm(y, log = TRUE)
    group1_samples <- sample_labels == group1_name
    group2_samples <- sample_labels == group2_name
    mean_group1 <- rowMeans(logcpm[, group1_samples, drop = FALSE])
    mean_group2 <- rowMeans(logcpm[, group2_samples, drop = FALSE])

    result_df <- data.frame(
        gene = rownames(results),
        mean_group1 = mean_group1[rownames(results)],
        mean_group2 = mean_group2[rownames(results)],
        log2FC = results$table$logFC,
        p_val = results$table$PValue,
        adj_p_val = results$table$FDR,
        stringsAsFactors = FALSE
    )

    rownames(result_df) <- NULL
    return(result_df)
}

# --- FUNCTION_BODY_END ---
