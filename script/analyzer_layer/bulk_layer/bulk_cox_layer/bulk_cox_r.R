# bulk COX分析 R模式脚本
# 此文件包含所有R代码，用于通过rpy2调用R进行COX回归分析
# 
# 使用方式：
# Python端通过rpy2将参数设置到全局环境，然后提取标记行内的代码执行
# 参数直接从全局环境获取，不需要显式传递
# R包必须通过Python端的importr()预加载，禁止在脚本中使用library()

#' COX回归分析
#' 
#' 参数列表（从全局环境获取）：
#' - expr_data: 表达数据框（行为样本，列为基因）
#' - surv_data: 生存数据框（包含time和event列）
#' - gene_names: 基因名称向量
#' - clinical_covariates: 临床协变量数据框（可选）
#' - adjusted: 是否进行多因素校正（TRUE/FALSE）

# --- FUNCTION_BODY_START ---

# === 参数获取 ===
expr_data <- expr_data
surv_data <- surv_data
gene_names <- as.character(gene_names)
adjusted <- as.logical(adjusted)[1]

# 获取临床协变量
if (exists('clinical_covariates') && !is.null(clinical_covariates)) {
    base_df <- clinical_covariates
} else {
    base_df <- NULL
}

# === 单因素COX分析函数 ===
cox_one_gene <- function(expr_z, time_vec, event_vec, base_df = NULL, adjusted = FALSE) {
    if (all(is.na(expr_z)) || stats::sd(expr_z, na.rm = TRUE) == 0) {
        return(c(coef = NA_real_, HR = NA_real_, HR_lower95 = NA_real_, 
                 HR_upper95 = NA_real_, se = NA_real_, z = NA_real_, pvalue = NA_real_))
    }
    dat <- data.frame(expr_z = as.numeric(expr_z))
    if (!is.null(base_df)) {
        dat <- cbind(dat, base_df)
    }
    dat$time <- time_vec
    dat$event <- event_vec
    dat <- dat[stats::complete.cases(dat), , drop = FALSE]
    if (nrow(dat) < 20 || length(unique(dat$event)) < 2) {
        return(c(coef = NA_real_, HR = NA_real_, HR_lower95 = NA_real_, 
                 HR_upper95 = NA_real_, se = NA_real_, z = NA_real_, pvalue = NA_real_))
    }
    fit <- tryCatch({
        suppressWarnings({
            if (adjusted) {
                coxph(Surv(time, event) ~ expr_z + ., data = dat, ties = "efron")
            } else {
                coxph(Surv(time, event) ~ expr_z, data = dat, ties = "efron")
            }
        })
    }, error = function(e) NULL)
    if (is.null(fit)) {
        return(c(coef = NA_real_, HR = NA_real_, HR_lower95 = NA_real_, 
                 HR_upper95 = NA_real_, se = NA_real_, z = NA_real_, pvalue = NA_real_))
    }
    sm <- summary(fit)
    if (!"expr_z" %in% rownames(sm$coefficients)) {
        return(c(coef = NA_real_, HR = NA_real_, HR_lower95 = NA_real_, 
                 HR_upper95 = NA_real_, se = NA_real_, z = NA_real_, pvalue = NA_real_))
    }
    coef_val <- sm$coefficients["expr_z", "coef"]
    se_val <- sm$coefficients["expr_z", "se(coef)"]
    z_val <- sm$coefficients["expr_z", "z"]
    p_val <- sm$coefficients["expr_z", "Pr(>|z|)"]
    hr_val <- exp(coef_val)
    c(coef = coef_val, HR = hr_val, 
      HR_lower95 = exp(coef_val - 1.96 * se_val),
      HR_upper95 = exp(coef_val + 1.96 * se_val),
      se = se_val, z = z_val, pvalue = p_val)
}

# === 准备表达数据（log2(TPM + 1) + z-score标准化）===
log_expr <- log2(expr_data + 1)
expr_z_mat <- t(scale(t(log_expr)))

# === 提取生存数据向量 ===
time_vec <- as.numeric(surv_data$time)
event_vec <- as.numeric(surv_data$event)

# === 执行COX分析 ===
results <- data.frame()
total_genes <- length(gene_names)
progress_interval <- 200

for (i in seq_along(gene_names)) {
    gene <- gene_names[i]
    if (gene %in% colnames(expr_z_mat)) {
        expr_z <- expr_z_mat[, gene]
        res <- cox_one_gene(expr_z, time_vec, event_vec, base_df, adjusted)
        
        result_row <- data.frame(
            gene = gene,
            coef = res["coef"],
            HR = res["HR"],
            HR_lower95 = res["HR_lower95"],
            HR_upper95 = res["HR_upper95"],
            se = res["se"],
            z = res["z"],
            pvalue = res["pvalue"]
        )
        results <- rbind(results, result_row)
    }
    
    if (i %% progress_interval == 0 || i == total_genes) {
        cat(sprintf("[COX进度] %d/%d\n", i, total_genes))
        flush.console()
    }
}

# === 添加FDR校正 ===
results$FDR <- p.adjust(results$pvalue, method = "BH")

# === 添加方向判断 ===
results$direction <- ifelse(is.na(results$HR), "NA",
                           ifelse(results$HR > 1, "Risk_high_expression", "Protective_high_expression"))

# === 排序 ===
results <- results[order(results$pvalue, na.last = TRUE), ]

# === 返回结果 ===
results

# --- FUNCTION_BODY_END ---