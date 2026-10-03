# -*- coding: utf-8 -*-
# ============================================================
# bulk 机器学习 - 差异训练类(diff_train) R 脚本
# 参照「成功测试脚本.R」，改编为 CLI 参数化 + 阶段化 + 仅训练模式
#
# 命令行参数（顺序传入）:
#   args[1] = mode               运行阶段: stage1/2/3/4/5
#   args[2] = work_dir           工作目录（loading 产物所在目录）
#   args[3] = expr_file          表达矩阵文件名（行=基因, 列=样本, tab分隔, 第一列 Gene）
#   args[4] = clinical_file      临床信息文件名（含 SampleID 与 label_col 列）
#   args[5] = out_dir            输出目录（OUT_BASE/machinelearning/train/）
#   args[6] = gene_file          基因集文件路径（xlsx/txt，传空字符串表示用全部交集基因）
#   args[7] = label_col          二分类组别列名（阶段三同步的列，如 IDH_mutation_status_synced）
#
# 阶段说明（仅训练，训练=验证将来整合）:
#   stage1: 数据准备 -> 读取表达+临床+基因集，依赖: 无
#   stage2: 单模型(Lasso/RF/SVM + ROC)  依赖 stage1
#   stage3: 批量建模(113算法)           依赖 stage1
#   stage4: AUC 计算 + 热图             依赖 stage1,3
#   stage5: 核心基因筛选 + 出图         依赖 stage1,3,4
#
# 输出文件（全部写入 out_dir）:
#   TRAIN_set.Rdata / train_ready.txt     stage1
#   lasso_roc.png, rf_roc.png, svm_roc.png ... stage2
#   zz_model_results.rds                  stage3
#   AUC_matrix.txt / Classification_AUC.pdf  stage4
#   gene_frequency_recommended.txt / core_genes_top10_intersection.png ... stage5
# ============================================================

# ---- 获取脚本所在目录（用于 source 引擎文件） ----
all_args <- commandArgs(FALSE)
file_arg <- grep("^--file=", all_args, value = TRUE)
if (length(file_arg) > 0) {
  script_dir <- dirname(sub("^--file=", "", file_arg[1]))
} else {
  script_dir <- "."
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 7) {
  stop("用法: Rscript bulk_machinelearning_diff_train.R <mode> <work_dir> <expr_file> <clinical_file> <out_dir> <gene_file> <label_col> [<methods_file> <max_genes> <seed> <filter_mode> <top_n> <n_models> <avg_rank>]")
}
mode         <- args[1]
work_dir     <- args[2]
expr_file    <- args[3]
clinical_file<- args[4]
out_dir      <- args[5]
gene_file    <- args[6]
label_col    <- args[7]
# 可选参数（缺省时使用默认值）
methods_file <- if (length(args) >= 8) args[8] else "NONE"
max_genes    <- if (length(args) >= 9) as.numeric(args[9]) else 1000
# 种子默认 1234：与参考脚本「成功测试脚本.R」一致，保证可复现
seed         <- if (length(args) >= 10) as.numeric(args[10]) else 1234
# 阶段五核心基因筛选参数（args[11-14]，仅 stage5 使用）
#   筛选模式: composite / gene_rank / n_models / avg_rank
filter_mode  <- if (length(args) >= 11) args[11] else "composite"
top_n        <- if (length(args) >= 12) as.numeric(args[12]) else 30
n_models_min <- if (length(args) >= 13) as.numeric(args[13]) else 5
avg_rank_max <- if (length(args) >= 14) as.numeric(args[14]) else 0
# 阶段四/五 AUC 阈值筛选（args[15]；默认 0 = 不筛选，>0 时仅纳入 avg_AUC >= 该阈值的算法）
auc_threshold <- if (length(args) >= 15) as.numeric(args[15]) else 0
if (is.na(auc_threshold)) auc_threshold <- 0
cat(sprintf("筛选参数: mode=%s top_n=%s n_models_min=%s avg_rank_max=%s auc_threshold=%s\n",
            filter_mode, top_n, n_models_min, avg_rank_max, auc_threshold))

cat("============================================================\n")
cat("机器学习差异训练(diff_train)分析 - 阶段:", mode, "\n")
cat("============================================================\n")

# ---- 加载引擎和包装函数（含 scaleData / ExtractVar / ML.Dev.Class.Sig 等） ----
source(file.path(script_dir, "00_Class_ML_Engine.R"))
source(file.path(script_dir, "00_Class_Mime_Wrappers.R"))

# ---- 目录准备 ----
if (!dir.exists(work_dir)) stop(paste("工作目录不存在:", work_dir))
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

# TRAIN_set.Rdata 路径（stage1 产出，供后续阶段加载）
train_data_file <- file.path(out_dir, "TRAIN_set.Rdata")

# 根据选中的算法组合文件，生成模型结果缓存文件路径（区分简易/完整）
get_model_res_file <- function() {
  if (methods_file != "" && methods_file != "NONE" && file.exists(methods_file)) {
    return(file.path(out_dir, paste0("zz_model_results_",
                gsub("\\.txt$", "", basename(methods_file)), ".rds")))
  }
  return(file.path(out_dir, "zz_model_results_methods.rds"))
}

# 校验模型子特征(subFeature)是否都在当前训练数据列中。
# 若一致返回 TRUE；若不匹配返回缺失特征样本（用于 stage3 判断缓存是否失效）。
# stage4/5 里可通过 isTRUE(...) 判断并给出清晰中文报错，避免 `undefined columns selected` 硬崩溃。
check_model_features_outdated <- function(res.category.models, list_train_vali_Data) {
  train_data <- list_train_vali_Data[[1]]
  available <- colnames(train_data)
  for (mn in names(res.category.models$model)) {
    fit <- res.category.models$model[[mn]]
    feats <- if (inherits(fit, "xgb.Booster")) attr(fit, "subFeature") else fit$subFeature
    if (length(feats) > 0) {
      miss <- setdiff(feats, available)
      if (length(miss) > 0) {
        return(list(ok = FALSE, model = mn, missing = head(miss, 6)))
      }
    }
  }
  return(list(ok = TRUE, model = NULL, missing = character(0)))
}

# ============================================================
# 阶段一：数据准备（仅训练）
# ============================================================
run_stage1 <- function() {
  library(stringr)
  library(openxlsx)
  library(dplyr)

  # ---- 读取表达矩阵 ----
  expr_path <- file.path(work_dir, expr_file)
  if (!file.exists(expr_path)) stop(paste("表达矩阵文件不存在:", expr_path))
  expr <- read.table(expr_path, sep = "\t", header = TRUE,
                     row.names = 1, check.names = FALSE)
  expr <- as.matrix(expr)
  cat("表达矩阵: ", nrow(expr), "基因 x", ncol(expr), "样本\n")

  # ---- 读取临床信息 ----
  cli_path <- file.path(work_dir, clinical_file)
  if (!file.exists(cli_path)) stop(paste("临床信息文件不存在:", cli_path))
  cli <- read.delim(cli_path, stringsAsFactors = FALSE, check.names = FALSE)
  cat("临床信息: ", nrow(cli), "样本 x", ncol(cli), "列\n")
  if (!label_col %in% colnames(cli)) {
    stop(paste0("临床信息中不存在组别列: ", label_col, "，可用列: ",
               paste(colnames(cli), collapse = ", ")))
  }
  cat("组别列 [", label_col, "] 分布:\n"); print(table(cli[[label_col]]))

  # ---- 过滤表达矩阵与临床对齐 ----
  # 样本名需与临床 SampleID 对齐；若带数据集前缀需一致
  common_samples <- intersect(colnames(expr), cli$SampleID)
  cat("表达与临床共有样本: ", length(common_samples), "\n")
  expr <- expr[, common_samples, drop = FALSE]
  cli  <- cli[match(common_samples, cli$SampleID), , drop = FALSE]

  # ---- 基因集过滤（可选） ----
  if (gene_file != "" && gene_file != "NONE" && file.exists(gene_file)) {
    ext <- tolower(tools::file_ext(gene_file))
    if (ext %in% c("xlsx", "xls")) {
      gdf <- read.xlsx(gene_file, colNames = FALSE)
    } else {
      gdf <- read.table(gene_file, header = FALSE, stringsAsFactors = FALSE,
                        fill = TRUE, comment.char = "#")
    }
    gene_vec <- as.character(gdf[[1]])
    gene_vec <- trimws(gene_vec[!is.na(gene_vec) & gene_vec != ""])
    common_genes <- intersect(rownames(expr), gene_vec)
    cat("基因集: ", length(gene_vec), "个；与表达交集: ", length(common_genes), "个\n")
  } else {
    common_genes <- rownames(expr)
    cat("未指定基因集，使用全部交集基因: ", length(common_genes), "个\n")
  }
  if (length(common_genes) == 0) stop("未找到可用基因")

  expr <- expr[common_genes, , drop = FALSE]

  # ---- 分组 label（阶段三组别列，去 NA） ----
  keep <- !is.na(cli[[label_col]]) & cli[[label_col]] != ""
  cat("临床过滤: 保留 ", sum(keep), "/", length(keep), " 样本\n")
  expr <- expr[, keep, drop = FALSE]
  label_raw <- cli[[label_col]][keep]

  # 限定为二分类（取前两个唯一值作为两类）
  uval <- unique(as.character(label_raw))
  if (length(uval) < 2) stop("组别列不足两个类别，无法进行二分类")
  class1 <- uval[1]; class2 <- uval[2]
  label <- ifelse(as.character(label_raw) == class1, class1, class2)
  label <- factor(label, levels = c(class1, class2))
  cat("二分类类别: [", class1, "] vs [", class2, "]\n")
  cat("分组分布:\n"); print(table(label))

  # ---- 过滤低表达基因（在 >50% 样本中表达 >1） ----
  k <- apply(expr, 1, function(x) sum(x > 1) > 0.5 * ncol(expr))
  cat("低表达过滤: 保留 ", sum(k), "/", length(k), " 基因\n")
  expr <- expr[k, , drop = FALSE]

  # ---- 高变异基因限制（防止超长公式导致引擎失败 + 控制 Stepglm 运行时间） ----
  # 批量建模中 glmBoost/Stepglm 等基于公式的方法无法处理数万特征，
  # 且 Stepglm 逐步回归在超多特征上极慢，故截取前 max_genes 个高变异基因作为输入特征，
  # 与参考脚本（约 771 基因）量级相当。用户指定基因集时通常已较少，不触发截断。
  if (nrow(expr) > max_genes) {
    rv <- apply(expr, 1, var, na.rm = TRUE)
    keep_top <- order(rv, decreasing = TRUE)[seq_len(max_genes)]
    expr <- expr[keep_top, , drop = FALSE]
    cat("高变异基因限制: 截取前 ", max_genes, " 个基因\n")
  }
  cat("最终特征基因数: ", nrow(expr), "（各数据集共用此基因空间）\n")

  # ---- 按样本名前缀拆分数据集（cohort名 = 样本名第一个"_"之前的片段） ----
  # 训练与验证一起做：首个数据集作为训练集（用于批量建模），其余作为验证集，
  # 全部进入 list_train_vali_Data，阶段四热图将按这些数据集名显示多列 Cohort。
  sample_names <- colnames(expr)
  prefix <- sub("_.*$", "", sample_names)
  uniq_pfx <- unique(prefix)
  cat("检测到数据集(cohort): ", paste(uniq_pfx, collapse = ", "), "\n")
  if (length(uniq_pfx) < 1) stop("未检测到任何数据集前缀")
  if (length(uniq_pfx) == 1) {
    cat("仅检测到单一数据集 [", uniq_pfx, "]，将作为训练集（无独立验证集）\n", sep = "")
  } else {
    cat("数据集顺序：", paste(uniq_pfx[1], "(训练集)", sep = ""),
        paste0(uniq_pfx[-1], "(验证集)"), "\n")
  }

  # ---- 基因名安全化（make.names），统一应用于所有数据集 ----
  # 基因名可能含 "-"、"." 等非法字符，会破坏公式解析（如 glmBoost/Stepglm），
  # 故批量建模用的列名统一转成 R 安全名（make.names），并保存映射用于还原。
  safe_genes <- make.names(rownames(expr), unique = TRUE)
  gene_map <- data.frame(safe = safe_genes, original = rownames(expr),
                         stringsAsFactors = FALSE)

  # ---- 逐数据集标准化 + 打包为标准格式（转置，含 outcome 列） ----
  classVar <- "outcome"
  list_train_vali_Data <- list()
  TRAIN_expr_list <- list()
  TRAIN_group_list <- list()
  for (i in seq_along(uniq_pfx)) {
    pfx <- uniq_pfx[i]
    idx <- which(prefix == pfx)
    sub_expr <- expr[, idx, drop = FALSE]
    sub_label <- label[idx]
    # 该数据集内需两分类同时存在才能评估 AUC
    ulv <- unique(as.character(sub_label))
    if (length(ulv) < 2) {
      cat(sprintf("[%s] 仅含单类别(%s)，跳过该数据集\n", pfx, paste(ulv, collapse = ",")))
      next
    }
    # 独立 z-score 标准化
    TRAIN_expr <- t(scale(t(sub_expr)))
    rownames(TRAIN_expr) <- safe_genes  # 行名=安全基因名（供后续转置为列名）
    colnames(TRAIN_expr) <- colnames(sub_expr)
    # 转置为 样本x基因
    Train_expr <- t(TRAIN_expr)
    colnames(Train_expr) <- safe_genes
    Train_set <- scaleData(Train_expr, centerFlags = TRUE, scaleFlags = TRUE)
    group_vec <- factor(sub_label, levels = c(class1, class2))
    df_one <- cbind(outcome = as.integer(group_vec == class2),
                    as.data.frame(Train_set))
    list_train_vali_Data[[pfx]] <- df_one
    TRAIN_expr_list[[pfx]] <- TRAIN_expr
    TRAIN_group_list[[pfx]] <- group_vec
    cat(sprintf("[%s] 数据集: %d 样本 x %d 基因；分组 %s / %s\n",
                pfx, ncol(sub_expr), nrow(sub_expr),
                sum(group_vec == class1), sum(group_vec == class2)))
  }
  if (length(list_train_vali_Data) == 0) stop("所有数据集均无法用于二分类，请检查组别列")
  names(list_train_vali_Data) <- names(list_train_vali_Data)
  cat("共打包数据集: ", paste(names(list_train_vali_Data), collapse = ", "), "\n")

  # 训练集（第一个数据集）用于阶段二/三建模，保存其标准化表达与分组
  train_name <- names(list_train_vali_Data)[1]
  TRAIN_expr  <- TRAIN_expr_list[[train_name]]
  TRAIN_group <- TRAIN_group_list[[train_name]]
  cat("训练集 = ", train_name, " (", ncol(TRAIN_expr), "样本)\n", sep = "")

  save(TRAIN_expr, TRAIN_group, class1, class2, list_train_vali_Data, gene_map,
       file = train_data_file)
  cat("训练数据已保存（含 ", length(list_train_vali_Data), " 个数据集）: ",
      train_data_file, "\n", sep = "")

  # 供 Python 展示的摘要
  write.table(data.frame(Item = c("Gene", "TrainSample", "Class1", "Class2",
                                  "N1", "N2", "Cohorts"),
                         Value = c(nrow(TRAIN_expr), ncol(TRAIN_expr),
                                   class1, class2,
                                   sum(TRAIN_group==class1), sum(TRAIN_group==class2),
                                   paste(names(list_train_vali_Data), collapse = ","))),
              file = file.path(out_dir, "train_ready.txt"),
              sep = "\t", quote = FALSE, row.names = FALSE)
  cat("阶段一完成\n")
}

# ============================================================
# 阶段二：单模型(Lasso / RF / SVM) + ROC（仅训练集评估）
# ============================================================
run_stage2 <- function() {
  library(glmnet)
  library(randomForest)
  library(e1071)
  library(pROC)
  library(ggplot2)

  if (!file.exists(train_data_file)) stop("请先运行阶段一生成训练数据")
  load(train_data_file)
  TRAIN_expr <- TRAIN_expr; TRAIN_group <- TRAIN_group

  cat("训练集: ", nrow(TRAIN_expr), "基因 x", ncol(TRAIN_expr), "样本\n")

  set.seed(1234)

  # ---- 1. Lasso ----
  cat("---- 训练 Lasso 模型 ----\n")
  cv_fit <- cv.glmnet(x = t(TRAIN_expr), y = TRAIN_group, family = "binomial",
                      standardize = FALSE)
  png(file.path(out_dir, "lasso_cv_fit.png"), width = 1200, height = 1000, res = 150)
  plot(cv_fit); dev.off()
  models <- glmnet(x = t(TRAIN_expr), y = TRAIN_group, family = "binomial",
                   standardize = FALSE)
  png(file.path(out_dir, "lasso_coef_path.png"), width = 1200, height = 1000, res = 150)
  plot(models); dev.off()
  lasso.prob <- predict(cv_fit, newx = t(TRAIN_expr), s = cv_fit$lambda.1se,
                        type = "response")
  m_lasso <- roc(TRAIN_group, as.numeric(lasso.prob[, 1]))
  cat("Lasso 训练AUC = ", as.numeric(auc(m_lasso)), "\n")
  g <- ggroc(m_lasso, legacy.axes = TRUE, linewidth = 1, color = "#2fa1dd")
  roc_plot <- g + theme_bw() +
    geom_abline(slope = 1, intercept = 0, colour = "grey", linetype = "dashed") +
    annotate("text", x = .75, y = .25,
             label = paste("AUC of Lasso = ",
                           format(round(as.numeric(auc(m_lasso)), 2), nsmall = 2)),
             color = "#2fa1dd", size = 5) +
    labs(title = "Lasso Regression ROC (Training)")
  ggsave(file.path(out_dir, "lasso_roc.png"), roc_plot, width = 6, height = 6, dpi = 300)
  cat("Lasso ROC 已保存\n")

  # ---- 2. 随机森林 ----
  cat("---- 训练随机森林模型 ----\n")
  rf_output <- randomForest(x = t(TRAIN_expr), y = TRAIN_group,
                            importance = TRUE, proximity = TRUE)
  png(file.path(out_dir, "rf_varImp.png"), width = 1400, height = 1000, res = 150)
  varImpPlot(rf_output, type = 2, n.var = 30, scale = FALSE,
             main = "Variable Importance (Gini) for top 30 predictors", cex = 0.7)
  dev.off()
  rf.prob <- predict(rf_output, t(TRAIN_expr), type = "prob")
  pos_col_rf <- levels(TRAIN_group)[max(1, nlevels(TRAIN_group))]
  m_rf <- roc(TRAIN_group, rf.prob[, pos_col_rf])
  cat("RF 训练AUC = ", as.numeric(auc(m_rf)), "\n")
  g <- ggroc(m_rf, legacy.axes = TRUE, linewidth = 1, color = "#2fa1dd")
  roc_plot <- g + theme_bw() +
    geom_abline(slope = 1, intercept = 0, colour = "grey", linetype = "dashed") +
    annotate("text", x = .75, y = .25,
             label = paste("AUC of RF = ",
                           format(round(as.numeric(auc(m_rf)), 2), nsmall = 2)),
             color = "#2fa1dd", size = 5) +
    labs(title = "Random Forest ROC (Training)")
  ggsave(file.path(out_dir, "rf_roc.png"), roc_plot, width = 6, height = 6, dpi = 300)
  cat("RF ROC 已保存\n")

  # ---- 3. SVM ----
  cat("---- 训练 SVM 模型 ----\n")
  svm_model <- svm(t(TRAIN_expr), as.factor(TRAIN_group), kernel = "linear",
                   probability = TRUE)
  pred_prob <- predict(svm_model, t(TRAIN_expr), probability = TRUE)
  pos_col_svm <- levels(TRAIN_group)[max(1, nlevels(TRAIN_group))]
  prob_values <- as.numeric(attr(pred_prob, "probabilities")[, pos_col_svm])
  m_svm <- roc(TRAIN_group, prob_values)
  cat("SVM 训练AUC = ", as.numeric(auc(m_svm)), "\n")
  g <- ggroc(m_svm, legacy.axes = TRUE, linewidth = 1, color = "#2fa1dd")
  roc_plot <- g + theme_bw() +
    geom_abline(slope = 1, intercept = 0, colour = "grey", linetype = "dashed") +
    annotate("text", x = .75, y = .25,
             label = paste("AUC of SVM = ",
                           format(round(as.numeric(auc(m_svm)), 2), nsmall = 2)),
             color = "#2fa1dd", size = 5) +
    labs(title = "SVM ROC (Training)")
  ggsave(file.path(out_dir, "svm_roc.png"), roc_plot, width = 6, height = 6, dpi = 300)
  cat("SVM ROC 已保存\n")
  cat("阶段二完成\n")
}

# ============================================================
# 阶段三：批量模型开发（113种算法组合）
# ============================================================
run_stage3 <- function() {
  library(glmnet)
  library(randomForestSRC)
  library(plsRglm)
  library(gbm)
  library(caret)
  library(mboost)
  library(MASS)
  library(e1071)
  library(xgboost)
  library(nnet)
  library(class)
  library(rpart)

  if (!file.exists(train_data_file)) stop("请先运行阶段一生成训练数据")
  load(train_data_file)

  # 使用指定的算法组合文件（可来自 APPDATA/machinelearning 下拉框选择），
  # 若未指定则回退到脚本目录下的 methods.txt
  chosen_methods_file <- if (methods_file != "" && methods_file != "NONE" &&
                            file.exists(methods_file)) methods_file else
                            file.path(script_dir, "methods.txt")
  if (!file.exists(chosen_methods_file)) stop(paste("算法组合文件不存在:", chosen_methods_file))
  methods_list <- readLines(chosen_methods_file)
  methods_list <- methods_list[!is.na(methods_list) & methods_list != ""]
  cat("共读取", length(methods_list), "种算法组合:", basename(chosen_methods_file), "\n")

  model_res_file <- get_model_res_file()
  res.category.models <- NULL
  if (file.exists(model_res_file)) {
    cached <- readRDS(model_res_file)
    # 校验缓存模型与当前训练数据特征是否一致；若数据已更新导致不一致，则自动重建
    check <- check_model_features_outdated(cached, list_train_vali_Data)
    # 另校验：当前算法组合文件是否与缓存模型集合一致（换文件/增删算法时需重建）
    cur_method_tags <- sort(unique(gsub("-| ", "", methods_list)))
    # 另校验：影响建模结果的步数上限是否与缓存生成时一致
    # （改了 00_Class_ML_Engine.R 的 STEPGLM_STEPS_* 但算法名不变时，旧 cache_tags 会静默复用旧模型）
    cur_step_tag <- paste0("STEPGLM[", STEPGLM_STEPS_BACKWARD_PRE, ",",
                           STEPGLM_STEPS_FORWARD, ",", STEPGLM_STEPS_BACKWARD, "]")
    cur_method_tags <- sort(unique(c(cur_method_tags, cur_step_tag)))
    cache_tags <- sort(unique(names(cached$model)))
    methods_changed <- !identical(cur_method_tags, cache_tags)
    if (!check$ok) {
      cat("检测到缓存模型与当前训练数据不一致（特征 ", check$model,
          " 存在缺失），数据已更新，将自动重新训练...\n")
      unlink(model_res_file)
    } else if (methods_changed) {
      cat("检测到算法组合已变更（缓存", length(cache_tags), "种 → 当前",
          length(cur_method_tags), "种），将自动重新训练...\n")
      unlink(model_res_file)
    } else {
      cat("加载已保存的模型结果（特征与训练数据一致、算法组合未变更）...\n")
      res.category.models <- cached
    }
  }
  if (is.null(res.category.models)) {
    cat("开始批量模型训练（仅训练集）...\n")
    res.category.models <- ML.Dev.Class.Sig(
      list_train_vali_Data = list_train_vali_Data,
      methods              = methods_list,
      classVar             = "outcome",
      min.selected.var     = 5,
      seed                 = seed
    )
    saveRDS(res.category.models, file = model_res_file)
  }
  cat("成功构建模型数: ", length(res.category.models$model), "/",
      length(methods_list), "\n")
  cat("阶段三完成\n")
}

# ============================================================
# 阶段四：AUC 计算 + 热图（仅训练集）
# ============================================================
run_stage4 <- function() {
  library(ComplexHeatmap)
  library(RColorBrewer)
  library(pROC)
  # 加载所有模型类型的预测函数（独立运行阶段四时需保证 predict 的 S3 方法已注册）
  library(glmnet)
  library(randomForestSRC)
  library(plsRglm)
  library(gbm)
  library(caret)
  library(mboost)
  library(MASS)
  library(e1071)
  library(xgboost)
  library(nnet)
  library(class)
  library(rpart)
  library(ggplot2)

  if (!file.exists(train_data_file)) stop("请先运行阶段一生成训练数据")
  load(train_data_file)
  model_res_file <- get_model_res_file()
  if (!file.exists(model_res_file)) stop("请先运行阶段三生成批量模型")
  res.category.models <- readRDS(model_res_file)
  chk <- check_model_features_outdated(res.category.models, list_train_vali_Data)
  if (!chk$ok) {
    stop(paste0(
      "模型缓存（", basename(model_res_file), "）与当前训练数据特征不一致（模型 「",
      chk$model, "」使用 ", length(chk$missing),
      " 个当前不存在的特征，如 ", paste(chk$missing, collapse=", "), "）。\n",
      "可能原因：已重新运行「数据加载类」或「阶段一」/更换了基因集，但未重新运行阶段三。\n",
      "请按顺序重新运行：阶段一 -> 阶段三 -> 阶段四。"))
  }

  AUC <- Cal.AUC.Class.All(res_obj = res.category.models,
                           list_train_vali_Data = list_train_vali_Data)

  # ---- AUC 阈值筛选：仅保留 avg_AUC >= auc_threshold 的算法 ----
  # 即用户期望的“输入0.5-1，筛选高于该AUC值的算法纳入阶段四出图+阶段五计数”。
  # 先计算每个模型在全部数据集上的平均 AUC 并按阈值过滤。
  if (auc_threshold > 0) {
    mid_avg <- if (ncol(AUC) > 1) apply(AUC, 1, mean, na.rm = TRUE)
               else as.numeric(AUC[, 1])
    keep_names <- names(mid_avg)[!is.na(mid_avg) & mid_avg >= auc_threshold]
    drop_names <- setdiff(rownames(AUC), keep_names)
    if (length(keep_names) == 0) stop("AUC 阈值筛选后无剩余算法，请降低阈值或检查 AUC 计算。")
    AUC <- AUC[keep_names, , drop = FALSE]
    cat("AUC 阈值筛选: 保留 avg_AUC >=", auc_threshold, "的算法 ",
        length(keep_names), " 个，剔除 ", length(drop_names), " 个。\n", sep = "")
    if (length(drop_names) > 0) {
      cat("已剔除算法(avg_AUC < ", auc_threshold, "): ",
          paste(head(drop_names, 20), collapse = "; "),
          if (length(drop_names) > 20) paste0(" ...共", length(drop_names), "个"), "\n", sep = "")
    }
  }

  write.table(AUC, file = file.path(out_dir, "AUC_matrix.txt"),
              sep = "\t", quote = FALSE, col.names = NA)
  cat("AUC 矩阵维度: ", dim(AUC), "\n")

  # 忠实复刻参考脚本：一律使用 Plot.Class.Heatmap 绘制 AUC 热图（PDF + PNG 双输出）
  # PDF 供高清导出；PNG 供界面标签页展示
  heatmap_pdf <- file.path(out_dir, "Classification_AUC.pdf")
  heatmap_png <- file.path(out_dir, "Classification_AUC.png")
  # 计算适合图片的高度（行数多时拉高，避免文字重叠）
  nrows_hm <- nrow(AUC)
  hm_png_w <- 10
  hm_png_h <- max(6, 4 + nrows_hm * 0.22)
  cat("绘制 AUC 热图 (", nrows_hm, "模型 x ", ncol(AUC), "数据集 )...\n")
  Plot.Class.Heatmap(AUC_mat = AUC, out_pdf = heatmap_pdf)
  png(heatmap_png, width = hm_png_w, height = hm_png_h, units = "in", res = 200)
  Plot.Class.Heatmap(AUC_mat = AUC)
  invisible(dev.off())
  # 同时保存模型按AUC降序的文本
  avg_auc_df <- data.frame(Model = rownames(AUC),
                           Avg_AUC = round(apply(AUC, 1, mean, na.rm = TRUE), 4))
  avg_auc_df <- avg_auc_df[order(-avg_auc_df$Avg_AUC), ]
  write.table(avg_auc_df, file = file.path(out_dir, "AUC_sorted.txt"),
              sep = "\t", quote = FALSE, row.names = FALSE)
  cat("AUC 热图已保存: ", heatmap_pdf, " / ", heatmap_png, "\n")
  cat("阶段四完成\n")
}

# ============================================================
# 阶段五：核心基因筛选 + 出图
# ============================================================
run_stage5 <- function() {
  library(ggplot2)
  # 加载所有模型类型的基因提取函数（独立运行阶段五时需保证 coef/summary.gbm/xgb.importance 等可用）
  library(glmnet)
  library(randomForestSRC)
  library(plsRglm)
  library(gbm)
  library(caret)
  library(mboost)
  library(MASS)
  library(e1071)
  library(xgboost)
  library(nnet)
  library(class)
  library(rpart)

  if (!file.exists(train_data_file)) stop("请先运行阶段一生成训练数据")
  load(train_data_file)
  model_res_file <- get_model_res_file()
  if (!file.exists(model_res_file)) stop("请先运行阶段三生成批量模型")
  res.category.models <- readRDS(model_res_file)
  chk <- check_model_features_outdated(res.category.models, list_train_vali_Data)
  if (!chk$ok) {
    stop(paste0(
      "模型缓存（", basename(model_res_file), "）与当前训练数据特征不一致（模型 「",
      chk$model, "」使用 ", length(chk$missing),
      " 个当前不存在的特征，如 ", paste(chk$missing, collapse=", "), "）。\n",
      "请按顺序重新运行：阶段一 -> 阶段三 -> 阶段五。"))
  }

  auc_file <- file.path(out_dir, "AUC_matrix.txt")
  if (file.exists(auc_file)) {
    AUC <- read.table(auc_file, sep = "\t", header = TRUE, row.names = 1,
                      check.names = FALSE)
    avg_AUC <- apply(AUC, 1, mean, na.rm = TRUE)
  } else {
    stop("请先运行阶段四计算 AUC")
  }

  # 模型集合 = 阶段四 AUC 筛选后剩余的算法（AUC_matrix 行名 与 建模模型名的交集），
  # 保证“被筛选掉的不纳入阶段五计数”。
  auc_keep <- rownames(AUC)
  model_names <- intersect(names(res.category.models$model), auc_keep)
  n_models <- length(model_names)
  cat("阶段五使用模型数(为阶段四AUC筛选后剩余): ", n_models, "\n", sep = "")

  # ---- 辅助函数：提取模型基因及重要性排名 ----
  # 基因选择采用「重要性Top-N比例法」：对能计算重要性的算法，保留重要性排名
  # 前 ~30% 的基因作为该模型纳入基因(与 Engine 的 ExtractVarTopN 一致)，否则保留全部；
  # Rank 依据重要性分数排序(1 = 最重要)。无重要性算法(SVM径向/KNN)用输入的 subFeature 顺序兜底。
  ExtractVarWithRank <- function(fit) {
    genes <- tryCatch(ExtractVarTopN(fit, top_frac = 0.3, min_keep = 5),
                      error = function(e) character(0))
    if (length(genes) == 0) return(data.frame(Gene = character(0), Rank = integer(0)))
    imp <- tryCatch(varImportance(fit), error = function(e) NULL)
    if (is.null(imp) || length(imp) == 0) {
      # 无重要性算法：按 subFeature 顺序赋排名(仍有区分度，但不做重要性截断)
      return(data.frame(Gene = genes, Rank = as.integer(seq_along(genes))))
    }
    # 对全部特征计算重要性排名(越重要排名越小)；gene 必须已有重要性值才给有限 Rank
    all_imp <- imp[is.finite(imp) & !is.na(imp)]
    if (length(all_imp) == 0) {
      return(data.frame(Gene = genes, Rank = as.integer(seq_along(genes))))
    }
    valid_genes <- genes[genes %in% names(all_imp)]
    if (length(valid_genes) == 0) {
      return(data.frame(Gene = genes, Rank = as.integer(seq_along(genes))))
    }
    ord <- order(-all_imp[valid_genes], valid_genes)
    valid_genes <- valid_genes[ord]
    # 在整个 all_imp 上求重要性排名(越小越重要)
    global_rank <- rank(-all_imp[valid_genes], ties.method = "min")
    data.frame(Gene = valid_genes, Rank = as.integer(global_rank))
  }

  cat("一次性提取所有模型基因+排名...\n")
  all_records <- list()
  for (i in seq_along(model_names)) {
    mn <- model_names[i]
    fit <- res.category.models$model[[mn]]
    df <- tryCatch(ExtractVarWithRank(fit), error = function(e) NULL)
    if (!is.null(df) && nrow(df) > 0) {
      df$Model <- mn; df$ModelAUC <- avg_AUC[mn]
      all_records[[mn]] <- df
    }
    if (i %% 20 == 0) cat("  已处理", i, "/", n_models, "模型\n")
  }
  all_records_df <- do.call(rbind, all_records)
  cat("总记录数:", nrow(all_records_df), "\n")

  # ---- 基因名还原（模型使用 make.names 后的安全名，还原为原始基因名） ----
  if (exists("gene_map") && nrow(gene_map) > 0) {
    orig_lut <- setNames(gene_map$original, gene_map$safe)
    mapped <- orig_lut[all_records_df$Gene]
    all_records_df$Gene[!is.na(mapped)] <- mapped[!is.na(mapped)]
  }

  # ---- 全基因汇总表（Gene/NModels/Frequency/AvgRank，含全部基因，不筛选） ----
  freq_table <- table(all_records_df$Gene)
  freq_df <- data.frame(Gene = names(freq_table),
                        NModels = as.integer(freq_table),
                        Frequency = as.numeric(freq_table) / n_models,
                        stringsAsFactors = FALSE)
  avg_rank_list <- tapply(all_records_df$Rank, all_records_df$Gene, mean, na.rm = TRUE)
  freq_df$AvgRank <- as.numeric(avg_rank_list[freq_df$Gene])
  freq_df$AvgRank[is.na(freq_df$AvgRank)] <- Inf
  freq_df <- freq_df[order(-freq_df$NModels, freq_df$AvgRank), ]
  # 全基因列表（需求5：显示全部基因，不筛选）——供 Python 「基因列表」表格导出
  write.table(freq_df, file = file.path(out_dir, "gene_all_list.txt"),
              sep = "\t", quote = FALSE, row.names = FALSE)
  cat("全基因列表: 共", nrow(freq_df), "基因 -> gene_all_list.txt\n")

  # ============================================================
  # 依据参考脚本「方法2：交集法」计算最终核心基因集合
  # ============================================================
  # 参考定义（成功测试脚本.R 585-612 行）取 Top10 最优 AUC 模型。
  # 本项目按需求改造：交集统计的「模型基数」= 阶段四 AUC 筛选后剩余的【全部】算法
  # （即被筛选掉的不纳入本阶段计数），而非硬编码 Top10。
  #   - freq   = 每个基因被这些筛后模型纳入的次数（取值 0-n_models）
  #   - 核心基因池 = 在筛后全部模型中出现次数 >= 阈值(n_models_min) 的基因
  # 颜色与列表里的 NModels 即为此筛后模型池内的纳入次数（可达 n_models）。
  # 而 gene_all_list.txt 仍为「全部筛后模型」的频率统计，供基因列表表格导出。
  inter_freq <- table(all_records_df$Gene)   # 统计筛后全部模型的纳入次数
  inter_max_total <- n_models

  # 交集阈值默认5（UI 传入，若为0则回退5）
  inter_threshold <- if (is.na(n_models_min) || n_models_min <= 0) 5 else n_models_min
  intersect_genes <- names(inter_freq)[inter_freq >= inter_threshold]
  cat("筛后", inter_max_total, "个模型中出现>=", inter_threshold, "个的基因数: ",
      length(intersect_genes), "\n", sep = "")

  # 交集池数据框（Gene / NModels=筛后模型纳入次数 / AvgRank=筛后模型内平均排名）
  intersect_rank_df <- data.frame(
    Gene = intersect_genes,
    NModels = as.integer(inter_freq[intersect_genes]),
    stringsAsFactors = FALSE
  )
  inter_avg_rank <- tapply(all_records_df$Rank, all_records_df$Gene, mean, na.rm = TRUE)
  intersect_rank_df$AvgRank <- as.numeric(inter_avg_rank[intersect_genes])
  intersect_rank_df <- intersect_rank_df[order(-intersect_rank_df$NModels, intersect_rank_df$AvgRank), ]

  # 综合排名（参考 plot 的出图顺序：AvgRank 升序）
  pool_rank_order <- order(intersect_rank_df$AvgRank, -intersect_rank_df$NModels, intersect_rank_df$Gene)
  pool_ranked <- intersect_rank_df[pool_rank_order, ]

  # ---- 依据筛选模式从交集池中选取最终核心基因 ----
  #   n_models  : 交集池本身（基因在筛后模型中出现 >= inter_threshold 次）
  #   gene_rank : 交集池内综合排名前 top_n 个
  #   avg_rank  : 交集池内平均排名 <= avg_rank_max 的基因
  #   composite : 同时应用；各值为 0 表示该条件不生效（需至少一项>0，UI已校验）
  if (filter_mode == "n_models") {
    sel_df <- intersect_rank_df
    meth_note <- sprintf("交集法模式(筛后%d模型内出现>=%d次)", inter_max_total, inter_threshold)
    meth_note_en <- paste0("Intersection >= ", inter_threshold, " of ", inter_max_total)
  } else if (filter_mode == "gene_rank") {
    sel_df <- head(pool_ranked, max(1, top_n))
    meth_note <- sprintf("交集法+基因排名(筛后>=%d模型, 取Top%d)", inter_threshold, top_n)
    meth_note_en <- paste0("Intersection>= ", inter_threshold, " & Top", top_n)
  } else if (filter_mode == "avg_rank") {
    sel_df <- intersect_rank_df[intersect_rank_df$AvgRank <= max(1, avg_rank_max), ]
    meth_note <- sprintf("交集法+平均排名(筛后>=%d模型, AvgRank<=%d)", inter_threshold, max(1, avg_rank_max))
    meth_note_en <- paste0("Intersection & AvgRank<= ", max(1, avg_rank_max))
  } else {
    # 复合模式
    sel_df <- pool_ranked
    conds <- c(top_n > 0, inter_threshold > 0, avg_rank_max > 0)
    if (any(conds)) {
      if (avg_rank_max > 0) sel_df <- sel_df[sel_df$AvgRank <= avg_rank_max, ]
      if (top_n > 0)        sel_df <- head(sel_df, top_n)
    } else {
      sel_df <- head(pool_ranked, 30)
    }
    meth_note <- sprintf("复合模式(筛后%d模型交集>=%d, TopN=%s, AvgRank<=%s)",
                         inter_max_total, inter_threshold, top_n, avg_rank_max)
    meth_note_en <- paste0("Composite (inter>= ", inter_threshold, ", TopN=", top_n,
                           ", AvgRank<=", avg_rank_max, ")")
  }

  sel_df <- sel_df[order(sel_df$AvgRank, -sel_df$NModels), ]
  cat("筛选后核心基因数: ", nrow(sel_df), "（", meth_note, "）\n", sep = "")
  # 保存当前筛选模式的基因表（供 Python 读取/导出，NModels=Top10内纳入次数）
  write.table(sel_df, file = file.path(out_dir, "gene_filtered_result.txt"),
              sep = "\t", quote = FALSE, row.names = FALSE)
  cat("筛选基因表已保存 -> gene_filtered_result.txt\n")

  # ---- 出图：核心基因（严格参考「成功测试脚本.R」方法2 的绘图写法，仅数据随筛选模式变化） ----
  # 结构完全复用参考：x=Average Rank, y=reorder(Gene,-AvgRank), fill=NModels 渐变。
  # NModels 即筛后模型纳入次数，数值范围 [inter_threshold, inter_max_total]，自然呈现蓝→红渐变。
  plot_df <- sel_df
  if (nrow(plot_df) > 0) {
    plot_df <- plot_df[order(plot_df$AvgRank), ]
    core_plot_n <- min(60, nrow(plot_df))
    plot_df <- head(plot_df, core_plot_n)
    p <- ggplot(plot_df, aes(x = AvgRank, y = reorder(Gene, -AvgRank), fill = NModels)) +
      geom_bar(stat = "identity", width = 0.7) +
      scale_fill_gradient(low = "#4195C1", high = "#CB5746", name = "nModels") +
      labs(x = "Average Rank", y = "Genes",
           title = paste0("Core Genes (", meth_note_en, ")"),
           subtitle = paste0(core_plot_n, " genes, NModels = count in ", inter_max_total,
                             " models, >= ", inter_threshold)) +
      theme_bw() +
      theme(plot.title = element_text(size = 12, face = "bold", hjust = 0.5),
            plot.subtitle = element_text(size = 10, hjust = 0.5, color = "gray40"),
            axis.text.y = element_text(size = 8),
            axis.text.x = element_text(size = 10),
            axis.title = element_text(size = 11),
            legend.position = "right")
    plot_height <- max(6, nrow(plot_df) * 0.25 + 2)
    ggsave(file.path(out_dir, "core_genes_top10_intersection.png"),
           p, width = 10, height = plot_height, dpi = 300, limitsize = FALSE)
    cat("核心基因图已保存 (绘制 ", core_plot_n, " 基因, ", meth_note, ")\n")
  }
  cat("阶段五完成\n")
}

# ============================================================
# 阶段分发
# ============================================================
switch(mode,
  "stage1" = run_stage1(),
  "stage2" = run_stage2(),
  "stage3" = run_stage3(),
  "stage4" = run_stage4(),
  "stage5" = run_stage5(),
  stop(paste("未知阶段:", mode))
)
cat("============================================================\n")
cat("阶段 [", mode, "] 已成功完成\n")
cat("输出目录:", out_dir, "\n")
cat("============================================================\n")
