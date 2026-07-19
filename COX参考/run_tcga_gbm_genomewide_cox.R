options(stringsAsFactors = FALSE)

suppressPackageStartupMessages({
  library(data.table)
  library(survival)
})

base_dir <- file.path(
  "D:",
  "\u5b9e\u9a8c",
  "3.\u8bfe\u9898-\u5728\u7814",
  "0.CGGA TCGA\u6570\u636e",
  "2.260609tcga_gbm_lgg"
)
out_dir <- file.path(
  "C:/Users/mgj74/Documents/New project 2",
  "TCGA_GBM_genomewide_Cox"
)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

count_file <- file.path(base_dir, "TCGA_GBM_LGG_STAR_counts.csv")
tpm_file <- file.path(base_dir, "TCGA_GBM_LGG_STAR_TPM.csv")
clinical_file <- file.path(base_dir, "TCGA_GBM_LGG_sample_matched_clinical.molecular_enhanced.csv")
annotation_file <- file.path(base_dir, "gene_annotation.csv")

min_tpm <- 1
min_samples <- 10
candidate_p_cutoff <- 0.05
candidate_fdr_cutoff <- 0.05

clean_factor <- function(x) {
  x <- trimws(as.character(x))
  x[is.na(x) | x == ""] <- "Unknown"
  x <- gsub("[^A-Za-z0-9]+", "_", x)
  x <- gsub("^_+|_+$", "", x)
  x[x == ""] <- "Unknown"
  factor(x)
}

clean_numeric <- function(x) {
  suppressWarnings(as.numeric(trimws(as.character(x))))
}

cox_one_gene <- function(expr_z, surv_obj, base_df = NULL, adjusted = FALSE) {
  if (all(is.na(expr_z)) || stats::sd(expr_z, na.rm = TRUE) == 0) {
    return(c(
      n = sum(!is.na(expr_z)), events = NA_real_, coef = NA_real_, HR = NA_real_,
      HR_lower95 = NA_real_, HR_upper95 = NA_real_, se = NA_real_, z = NA_real_,
      pvalue = NA_real_
    ))
  }
  dat <- data.frame(expr_z = as.numeric(expr_z))
  if (!is.null(base_df)) {
    dat <- cbind(dat, base_df)
  }
  dat$time <- surv_obj[, "time"]
  dat$event <- surv_obj[, "status"]
  dat <- dat[stats::complete.cases(dat), , drop = FALSE]
  if (nrow(dat) < 20 || length(unique(dat$event)) < 2) {
    return(c(
      n = nrow(dat), events = sum(dat$event), coef = NA_real_, HR = NA_real_,
      HR_lower95 = NA_real_, HR_upper95 = NA_real_, se = NA_real_, z = NA_real_,
      pvalue = NA_real_
    ))
  }
  fit <- tryCatch({
    suppressWarnings({
      if (adjusted) {
        coxph(Surv(time, event) ~ expr_z + age_scaled + sex + idh_status + mgmt_status,
              data = dat, ties = "efron")
      } else {
        coxph(Surv(time, event) ~ expr_z, data = dat, ties = "efron")
      }
    })
  }, error = function(e) NULL)
  if (is.null(fit)) {
    return(c(
      n = nrow(dat), events = sum(dat$event), coef = NA_real_, HR = NA_real_,
      HR_lower95 = NA_real_, HR_upper95 = NA_real_, se = NA_real_, z = NA_real_,
      pvalue = NA_real_
    ))
  }
  sm <- summary(fit)
  if (!"expr_z" %in% rownames(sm$coefficients)) {
    return(c(
      n = nrow(dat), events = sum(dat$event), coef = NA_real_, HR = NA_real_,
      HR_lower95 = NA_real_, HR_upper95 = NA_real_, se = NA_real_, z = NA_real_,
      pvalue = NA_real_
    ))
  }
  coef_val <- sm$coefficients["expr_z", "coef"]
  se_val <- sm$coefficients["expr_z", "se(coef)"]
  z_val <- sm$coefficients["expr_z", "z"]
  p_val <- sm$coefficients["expr_z", "Pr(>|z|)"]
  hr_val <- exp(coef_val)
  c(
    n = nrow(dat),
    events = sum(dat$event),
    coef = coef_val,
    HR = hr_val,
    HR_lower95 = exp(coef_val - 1.96 * se_val),
    HR_upper95 = exp(coef_val + 1.96 * se_val),
    se = se_val,
    z = z_val,
    pvalue = p_val
  )
}

message("Reading clinical metadata...")
clinical <- fread(clinical_file, data.table = FALSE, check.names = FALSE)
clinical$sample_type_code <- substr(clinical$matrix_column_id, 14, 15)
clinical <- clinical[
  clinical$project_id == "TCGA-GBM" & clinical$sample_type_code == "01",
  ,
  drop = FALSE
]

message("Computing library sizes from raw counts for duplicate selection...")
gbm_cols <- intersect(clinical$matrix_column_id, names(fread(count_file, nrows = 0, data.table = FALSE)))
count_dt <- fread(count_file, select = c("gene_id", gbm_cols), data.table = FALSE, check.names = FALSE)
count_mat <- as.matrix(count_dt[, gbm_cols, drop = FALSE])
storage.mode(count_mat) <- "numeric"
lib_size <- colSums(count_mat, na.rm = TRUE)
rm(count_dt, count_mat)
gc()

clinical <- clinical[match(names(lib_size), clinical$matrix_column_id), , drop = FALSE]
clinical$lib_size <- as.numeric(lib_size)
keep_idx <- unlist(tapply(seq_len(nrow(clinical)), clinical$case_submitter_id, function(i) {
  i[which.max(clinical$lib_size[i])]
}))
clinical <- clinical[sort(keep_idx), , drop = FALSE]

clinical$os_months <- clean_numeric(clinical$cbio_OS_MONTHS)
clinical$os_event <- grepl("DECEASED", clinical$cbio_OS_STATUS, ignore.case = TRUE)
clinical <- clinical[
  !is.na(clinical$os_months) &
    clinical$os_months > 0 &
    !is.na(clinical$cbio_OS_STATUS) &
    clinical$cbio_OS_STATUS != "",
  ,
  drop = FALSE
]

clinical$age_years <- clean_numeric(clinical$cbio_AGE)
if (all(is.na(clinical$age_years)) && "demographic.age_at_index" %in% names(clinical)) {
  clinical$age_years <- clean_numeric(clinical$demographic.age_at_index)
}
clinical$age_years[is.na(clinical$age_years)] <- median(clinical$age_years, na.rm = TRUE)
clinical$age_scaled <- as.numeric(scale(clinical$age_years))
clinical$age_scaled[is.na(clinical$age_scaled)] <- 0
clinical$sex <- clean_factor(clinical$cbio_SEX)
clinical$idh_status <- clean_factor(clinical$cbio_IDH_STATUS)
clinical$mgmt_status <- clean_factor(clinical$cbio_MGMT_PROMOTER_STATUS)

write.csv(
  clinical,
  file.path(out_dir, "TCGA_GBM_Cox_samples_used.full_clinical.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
sample_file <- clinical[, c(
  "matrix_column_id", "sample_submitter_id", "case_submitter_id", "project_id",
  "os_months", "os_event", "cbio_OS_STATUS", "age_years", "cbio_SEX",
  "cbio_IDH_STATUS", "cbio_MGMT_PROMOTER_STATUS", "lib_size"
), drop = FALSE]
write.csv(
  sample_file,
  file.path(out_dir, "TCGA_GBM_Cox_samples_used.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)

message("Reading TPM matrix for selected GBM samples...")
tpm_cols <- intersect(clinical$matrix_column_id, names(fread(tpm_file, nrows = 0, data.table = FALSE)))
tpm_dt <- fread(tpm_file, select = c("gene_id", tpm_cols), data.table = FALSE, check.names = FALSE)
gene_id <- tpm_dt$gene_id
tpm_mat <- as.matrix(tpm_dt[, tpm_cols, drop = FALSE])
storage.mode(tpm_mat) <- "numeric"
rownames(tpm_mat) <- gene_id
rm(tpm_dt)
gc()

clinical <- clinical[match(colnames(tpm_mat), clinical$matrix_column_id), , drop = FALSE]
if (!all(clinical$matrix_column_id == colnames(tpm_mat))) {
  stop("Clinical metadata and TPM columns are not aligned.")
}

message("Filtering genes and transforming expression...")
keep_gene <- rowSums(tpm_mat >= min_tpm, na.rm = TRUE) >= min_samples
tpm_mat <- tpm_mat[keep_gene, , drop = FALSE]
log_expr <- log2(tpm_mat + 1)
rm(tpm_mat)
gc()

gene_sd <- apply(log_expr, 1, stats::sd, na.rm = TRUE)
keep_variable <- is.finite(gene_sd) & gene_sd > 0
log_expr <- log_expr[keep_variable, , drop = FALSE]
gene_sd <- gene_sd[keep_variable]
expr_z_mat <- t(scale(t(log_expr)))
rm(log_expr)
gc()

surv_obj <- Surv(time = clinical$os_months, event = clinical$os_event)
base_df <- data.frame(
  age_scaled = clinical$age_scaled,
  sex = clinical$sex,
  idh_status = clinical$idh_status,
  mgmt_status = clinical$mgmt_status
)

message("Running genome-wide univariate Cox models...")
univ_res <- t(apply(expr_z_mat, 1, cox_one_gene, surv_obj = surv_obj, adjusted = FALSE))
univ_df <- as.data.frame(univ_res)
univ_df$gene_id <- rownames(expr_z_mat)

message("Adding annotation and selecting candidates...")
annot <- fread(annotation_file, data.table = FALSE, check.names = FALSE)
univ_df$gene_id_no_version <- sub("\\..*$", "", univ_df$gene_id)
univ_df$gene_name <- annot$gene_name[match(univ_df$gene_id, annot$gene_id)]
univ_df$gene_type <- annot$gene_type[match(univ_df$gene_id, annot$gene_id)]
univ_df$gene_name[is.na(univ_df$gene_name)] <- ""
univ_df$gene_type[is.na(univ_df$gene_type)] <- ""
univ_df$FDR <- p.adjust(univ_df$pvalue, method = "BH")
univ_df$direction <- ifelse(
  is.na(univ_df$HR),
  "NA",
  ifelse(univ_df$HR > 1, "Risk_high_expression", "Protective_high_expression")
)
univ_df$screen_status <- "Not_significant"
univ_df$screen_status[!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff & univ_df$HR > 1] <- "P_lt_0.05_Risk"
univ_df$screen_status[!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff & univ_df$HR < 1] <- "P_lt_0.05_Protective"
univ_df$FDR_status <- "Not_significant"
univ_df$FDR_status[!is.na(univ_df$FDR) & univ_df$FDR < candidate_fdr_cutoff & univ_df$HR > 1] <- "FDR_lt_0.05_Risk"
univ_df$FDR_status[!is.na(univ_df$FDR) & univ_df$FDR < candidate_fdr_cutoff & univ_df$HR < 1] <- "FDR_lt_0.05_Protective"
univ_df <- univ_df[, c(
  "gene_id", "gene_id_no_version", "gene_name", "gene_type",
  "n", "events", "coef", "HR", "HR_lower95", "HR_upper95", "se", "z",
  "pvalue", "FDR", "direction", "screen_status", "FDR_status"
)]
univ_df <- univ_df[order(univ_df$pvalue, univ_df$FDR, na.last = TRUE), ]

write.csv(
  univ_df,
  file.path(out_dir, "TCGA_GBM_genomewide_univariate_Cox_log2TPM_zscore_all_genes.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
write.csv(
  univ_df[!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff & univ_df$HR > 1, ],
  file.path(out_dir, "TCGA_GBM_univariate_Cox_p_lt_0.05_risk_genes.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
write.csv(
  univ_df[!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff & univ_df$HR < 1, ],
  file.path(out_dir, "TCGA_GBM_univariate_Cox_p_lt_0.05_protective_genes.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
write.csv(
  univ_df[!is.na(univ_df$FDR) & univ_df$FDR < candidate_fdr_cutoff & univ_df$HR > 1, ],
  file.path(out_dir, "TCGA_GBM_univariate_Cox_FDR_lt_0.05_risk_genes.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
write.csv(
  univ_df[!is.na(univ_df$FDR) & univ_df$FDR < candidate_fdr_cutoff & univ_df$HR < 1, ],
  file.path(out_dir, "TCGA_GBM_univariate_Cox_FDR_lt_0.05_protective_genes.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)

candidate_gene_ids <- univ_df$gene_id[!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff]
message("Running adjusted Cox models for ", length(candidate_gene_ids), " univariate p<0.05 candidates...")
candidate_mat <- expr_z_mat[candidate_gene_ids, , drop = FALSE]
adj_res <- t(apply(candidate_mat, 1, cox_one_gene, surv_obj = surv_obj, base_df = base_df, adjusted = TRUE))
adj_df <- as.data.frame(adj_res)
adj_df$gene_id <- rownames(candidate_mat)
adj_df$gene_id_no_version <- sub("\\..*$", "", adj_df$gene_id)
adj_df$gene_name <- annot$gene_name[match(adj_df$gene_id, annot$gene_id)]
adj_df$gene_type <- annot$gene_type[match(adj_df$gene_id, annot$gene_id)]
adj_df$gene_name[is.na(adj_df$gene_name)] <- ""
adj_df$gene_type[is.na(adj_df$gene_type)] <- ""
adj_df$FDR <- p.adjust(adj_df$pvalue, method = "BH")
adj_df$direction <- ifelse(
  is.na(adj_df$HR),
  "NA",
  ifelse(adj_df$HR > 1, "Adjusted_risk_high_expression", "Adjusted_protective_high_expression")
)
adj_df$screen_status <- "Not_significant"
adj_df$screen_status[!is.na(adj_df$pvalue) & adj_df$pvalue < candidate_p_cutoff & adj_df$HR > 1] <- "Adjusted_P_lt_0.05_Risk"
adj_df$screen_status[!is.na(adj_df$pvalue) & adj_df$pvalue < candidate_p_cutoff & adj_df$HR < 1] <- "Adjusted_P_lt_0.05_Protective"
adj_df$FDR_status <- "Not_significant"
adj_df$FDR_status[!is.na(adj_df$FDR) & adj_df$FDR < candidate_fdr_cutoff & adj_df$HR > 1] <- "Adjusted_FDR_lt_0.05_Risk"
adj_df$FDR_status[!is.na(adj_df$FDR) & adj_df$FDR < candidate_fdr_cutoff & adj_df$HR < 1] <- "Adjusted_FDR_lt_0.05_Protective"
adj_df <- adj_df[, c(
  "gene_id", "gene_id_no_version", "gene_name", "gene_type",
  "n", "events", "coef", "HR", "HR_lower95", "HR_upper95", "se", "z",
  "pvalue", "FDR", "direction", "screen_status", "FDR_status"
)]
adj_df <- adj_df[order(adj_df$pvalue, adj_df$FDR, na.last = TRUE), ]
write.csv(
  adj_df,
  file.path(out_dir, "TCGA_GBM_adjusted_Cox_for_univariate_p_lt_0.05_candidates.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
write.csv(
  adj_df[!is.na(adj_df$pvalue) & adj_df$pvalue < candidate_p_cutoff & adj_df$HR > 1, ],
  file.path(out_dir, "TCGA_GBM_adjusted_Cox_p_lt_0.05_risk_genes.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
write.csv(
  adj_df[!is.na(adj_df$pvalue) & adj_df$pvalue < candidate_p_cutoff & adj_df$HR < 1, ],
  file.path(out_dir, "TCGA_GBM_adjusted_Cox_p_lt_0.05_protective_genes.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)

summary_df <- data.frame(
  item = c(
    "input_expression_file",
    "input_clinical_file",
    "expression_for_cox",
    "univariate_model",
    "adjusted_model_for_univariate_candidates",
    "sample_filter",
    "deduplication",
    "gene_filter",
    "candidate_gene_rule_common",
    "strict_gene_rule",
    "gbm_primary_tumor_expression_columns",
    "unique_gbm_cases_after_deduplication",
    "os_complete_cases_used",
    "events_deaths",
    "censored_living",
    "genes_before_filter",
    "genes_after_tpm_filter",
    "genes_after_variable_filter",
    "univariate_p_lt_0.05_total",
    "univariate_p_lt_0.05_risk",
    "univariate_p_lt_0.05_protective",
    "univariate_FDR_lt_0.05_total",
    "univariate_FDR_lt_0.05_risk",
    "univariate_FDR_lt_0.05_protective",
    "adjusted_p_lt_0.05_total",
    "adjusted_p_lt_0.05_risk",
    "adjusted_p_lt_0.05_protective",
    "adjusted_FDR_lt_0.05_total",
    "adjusted_FDR_lt_0.05_risk",
    "adjusted_FDR_lt_0.05_protective"
  ),
  value = c(
    basename(tpm_file),
    basename(clinical_file),
    "z-score of log2(TPM + 1); HR is per 1 SD higher expression",
    "Surv(OS_months, event) ~ gene_expression_zscore",
    "Surv(OS_months, event) ~ gene_expression_zscore + age_scaled + sex + IDH_status + MGMT_promoter_status",
    "TCGA-GBM primary tumor samples only, sample type code 01, OS complete",
    "one RNA-seq aliquot per case_submitter_id; kept sample with maximum raw-count library size",
    paste0("rowSums(TPM >= ", min_tpm, ") >= ", min_samples, " and nonzero expression variance"),
    paste0("univariate Cox p < ", candidate_p_cutoff, "; commonly used as candidate set before LASSO/multivariate validation"),
    paste0("BH FDR < ", candidate_fdr_cutoff),
    as.character(length(gbm_cols)),
    as.character(length(unique(clinical$case_submitter_id))),
    as.character(nrow(clinical)),
    as.character(sum(clinical$os_event)),
    as.character(sum(!clinical$os_event)),
    as.character(length(gene_id)),
    as.character(sum(keep_gene)),
    as.character(nrow(expr_z_mat)),
    as.character(sum(!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff)),
    as.character(sum(!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff & univ_df$HR > 1)),
    as.character(sum(!is.na(univ_df$pvalue) & univ_df$pvalue < candidate_p_cutoff & univ_df$HR < 1)),
    as.character(sum(!is.na(univ_df$FDR) & univ_df$FDR < candidate_fdr_cutoff)),
    as.character(sum(!is.na(univ_df$FDR) & univ_df$FDR < candidate_fdr_cutoff & univ_df$HR > 1)),
    as.character(sum(!is.na(univ_df$FDR) & univ_df$FDR < candidate_fdr_cutoff & univ_df$HR < 1)),
    as.character(sum(!is.na(adj_df$pvalue) & adj_df$pvalue < candidate_p_cutoff)),
    as.character(sum(!is.na(adj_df$pvalue) & adj_df$pvalue < candidate_p_cutoff & adj_df$HR > 1)),
    as.character(sum(!is.na(adj_df$pvalue) & adj_df$pvalue < candidate_p_cutoff & adj_df$HR < 1)),
    as.character(sum(!is.na(adj_df$FDR) & adj_df$FDR < candidate_fdr_cutoff)),
    as.character(sum(!is.na(adj_df$FDR) & adj_df$FDR < candidate_fdr_cutoff & adj_df$HR > 1)),
    as.character(sum(!is.na(adj_df$FDR) & adj_df$FDR < candidate_fdr_cutoff & adj_df$HR < 1))
  )
)
write.csv(
  summary_df,
  file.path(out_dir, "TCGA_GBM_genomewide_Cox_analysis_summary.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)

readme <- c(
  "TCGA GBM genome-wide Cox survival screening",
  "",
  "This analysis screens prognostic genes directly with Cox regression, not by artificial OS-group DESeq2.",
  "Expression input: TCGA_GBM_LGG_STAR_TPM.csv.",
  "Clinical input: TCGA_GBM_LGG_sample_matched_clinical.molecular_enhanced.csv.",
  "Samples: TCGA-GBM primary tumors, one aliquot per case selected by maximum raw-count library size, OS complete.",
  "Expression variable: z-score of log2(TPM + 1); HR is per 1 SD higher expression.",
  "Gene filter: TPM >= 1 in at least 10 samples and nonzero expression variance.",
  "Univariate model: Surv(OS_months, event) ~ gene_expression_zscore.",
  "Adjusted model for univariate p<0.05 candidates: Surv(OS_months, event) ~ gene_expression_zscore + age_scaled + sex + IDH_status + MGMT_promoter_status.",
  "",
  "Interpretation:",
  "HR > 1: higher expression is associated with worse OS (risk gene).",
  "HR < 1: higher expression is associated with better OS (protective gene).",
  "Many papers use univariate p < 0.05 as a candidate pool before LASSO/multivariate/validation, but FDR < 0.05 is stricter for genome-wide screening.",
  "",
  "Main files:",
  "- TCGA_GBM_genomewide_univariate_Cox_log2TPM_zscore_all_genes.csv",
  "- TCGA_GBM_univariate_Cox_p_lt_0.05_risk_genes.csv",
  "- TCGA_GBM_univariate_Cox_p_lt_0.05_protective_genes.csv",
  "- TCGA_GBM_univariate_Cox_FDR_lt_0.05_risk_genes.csv",
  "- TCGA_GBM_univariate_Cox_FDR_lt_0.05_protective_genes.csv",
  "- TCGA_GBM_adjusted_Cox_for_univariate_p_lt_0.05_candidates.csv",
  "- TCGA_GBM_adjusted_Cox_p_lt_0.05_risk_genes.csv",
  "- TCGA_GBM_adjusted_Cox_p_lt_0.05_protective_genes.csv",
  "- TCGA_GBM_Cox_samples_used.csv",
  "- TCGA_GBM_genomewide_Cox_analysis_summary.csv"
)
writeLines(readme, file.path(out_dir, "README_TCGA_GBM_genomewide_Cox.txt"), useBytes = TRUE)
capture.output(sessionInfo(), file = file.path(out_dir, "sessionInfo_R.txt"))

message("Done. Results written to: ", out_dir)
