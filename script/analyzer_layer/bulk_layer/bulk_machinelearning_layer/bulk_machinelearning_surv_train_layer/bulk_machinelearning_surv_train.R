# -*- coding: utf-8 -*-
# ============================================================
# bulk 机器学习 - 生存训练类(surv_train) R 脚本
#
# 集成自调试脚本 surv_analysis.R / plot_surv_heatmap.R，
# 拆分为 CLI 参数化的 4 个阶段：
#   stage1: 数据准备  读 loading 产物(去批次表达+临床) + 基因集 + 生存元数据(surv_meta)
#                      -> 按样本名前缀拆分数据集 -> 标准化 -> 打包存 TRAIN_set.Rdata
#   stage2: 批量建模  对所有算法用 event 二分类标签训练 ML.Dev.Class.Sig，
#                     并用 ExtractVarTopN 提取每个算法选中的基因子集，存 gene_model.Rdata
#   stage3: 生存分析  逐算法: 选中基因单变量cox(p<0.05) -> 多变量cox(前15) -> 预测风险
#                     -> 三队列 time-dependent AUC(求均值= iAUC) + C-index
#                     排序存 method_performance.txt + 绘制 iAUC 热图
#   stage4: 最优基因  取 iAUC 最高算法，列出其生存意义基因(单变量Cox HR/HR_low/HR_high/p/FDR)
#
# 命令行参数:
#   args[1] = mode               运行阶段: stage1/2/3/4
#   args[2] = work_dir           工作目录（loading 产物所在目录）
#   args[3] = expr_file          表达矩阵文件名（行=基因, 列=样本；combat_corrected_exprdata.txt）
#   args[4] = clinical_file      临床信息文件名（merged_clinical.txt，含 SampleID）
#   args[5] = out_dir            输出目录（OUT_BASE/machinelearning/surv_train/）
#   args[6] = gene_file          基因集文件路径（xlsx/txt，传 NONE 用全部交集基因）
#   args[7] = surv_meta_file     生存元数据文件名（out_dir 下，Py 生成的 surv_meta.txt 副本）
#   可选:
#   args[8]  = methods_file      算法组合文件路径（NONE 回退脚本目录 methods.txt）
#   args[9]  = max_genes         高变异基因截断数（默认 1000）
#   args[10] = seed              随机种子（默认 1234）
#   args[11] = max_features      每个算法提取基因数上限（默认 50）
#   args[12] = top_frac          重要性Top-N比例（默认 0.3）
#   args[13] = time_points       生存评价时间点（逗号分隔，默认 6,12,24,36）
#   args[14] = plot_width_cm     热图设备宽度(cm，默认 12)
#   args[15] = plot_height_cm    热图设备高度(cm，默认 8)
#
# 输出文件（写入 out_dir）:
#   surv_train.Rdata               stage1（expr/名单/生存表/数据集拆分）
#   gene_model.Rdata               stage2（method_gene）
#   surv_analysis_results.Rdata    stage3（perf/res_list/TRAIN/VAL列表）
#   method_performance.txt          stage3 算法性能排序表
#   surv_iAUC_heatmap.png/pdf       stage3 iAUC 热图
#   best_method_genes_T.txt        stage4 最优算法显著基因表
#   surv_best_gene_list.txt        stage4 全基因表(供 UI 表格)
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
  stop("用法: Rscript bulk_machinelearning_surv_train.R <mode> <work_dir> <expr_file> <clinical_file> <out_dir> <gene_file> <surv_meta_file> [<methods_file> <max_genes> <seed> <max_features> <top_frac> <time_points> <plot_width_cm> <plot_height_cm>]")
}
mode          <- args[1]
work_dir      <- args[2]
expr_file     <- args[3]
clinical_file <- args[4]
out_dir       <- args[5]
gene_file     <- args[6]
surv_meta_file<- args[7]
# 可选参数
methods_file  <- if (length(args) >= 8) args[8] else "NONE"
max_genes     <- if (length(args) >= 9) as.numeric(args[9]) else 1000
seed          <- if (length(args) >= 10) as.numeric(args[10]) else 1234
max_features  <- if (length(args) >= 11) as.numeric(args[11]) else 50
top_frac      <- if (length(args) >= 12) as.numeric(args[12]) else 0.3
time_points   <- if (length(args) >= 13) as.numeric(strsplit(args[13], ",")[[1]]) else c(6, 12, 24, 36)
plot_width_cm <- if (length(args) >= 14) as.numeric(args[14]) else 12      # 热图设备宽度(cm)
plot_height_cm<- if (length(args) >= 15) as.numeric(args[15]) else 8       # 热图设备高度(cm)
if (is.na(max_genes)) max_genes <- 1000
if (is.na(seed)) seed <- 1234
if (is.na(max_features)) max_features <- 50
if (is.na(top_frac)) top_frac <- 0.3
if (is.na(plot_width_cm) || plot_width_cm <= 0)  plot_width_cm  <- 12
if (is.na(plot_height_cm) || plot_height_cm <= 0) plot_height_cm <- 8
cat(sprintf("参数: mode=%s max_genes=%s seed=%s max_features=%s top_frac=%s time_points=%s plot_width=%scm plot_height=%scm\n",
            mode, max_genes, seed, max_features, top_frac, paste(time_points, collapse=","), plot_width_cm, plot_height_cm))

# ---- 加载引擎与包装函数 ----
engine <- file.path(script_dir, "00_Class_ML_Engine.R")
if (!file.exists(engine)) engine <- file.path(script_dir, "..", "bulk_machinelearning_diff_train_layer", "00_Class_ML_Engine.R")
wrapper <- file.path(script_dir, "00_Class_Mime_Wrappers.R")
if (!file.exists(wrapper)) wrapper <- file.path(script_dir, "..", "bulk_machinelearning_diff_train_layer", "00_Class_Mime_Wrappers.R")
source(engine)
if (file.exists(wrapper)) source(wrapper)
# 仅加载需要的依赖（避免未安装 Wrappers 中绘图包导致报错）
suppressMessages({
  library(survival)
  library(glmnet)
  library(randomForest)
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
})

cat("============================================================\n")
cat("机器学习生存训练(surv_train)分析 - 阶段:", mode, "\n")
cat("============================================================\n")

# 中间文件路径
train_data_file <- file.path(out_dir, "surv_train.Rdata")      # stage1 输出
gene_model_file <- file.path(out_dir, "gene_model.Rdata")      # stage2 输出
results_file    <- file.path(out_dir, "surv_analysis_results.Rdata")  # stage3 输出

if (!dir.exists(work_dir)) stop(paste("工作目录不存在:", work_dir))
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

# ============================================================
# 阶段一：数据准备
# 读 loading 产物 + 基因集 + 生存元数据，拆分数据集 + 标准化，存 Rdata
# ============================================================
run_stage1 <- function() {
  library(openxlsx)
  library(stringr)

  # 1. 表达矩阵
  expr_path <- file.path(work_dir, expr_file)
  if (!file.exists(expr_path)) stop(paste("表达矩阵文件不存在:", expr_path))
  expr <- as.matrix(read.table(expr_path, sep="\t", header=TRUE, row.names=1, check.names=FALSE))
  cat("表达矩阵: ", nrow(expr), "基因 x", ncol(expr), "样本\n")

  # 2. 临床信息（仅取 SampleID 列，用于样本名映射）
  cli_path <- file.path(work_dir, clinical_file)
  if (!file.exists(cli_path)) stop(paste("临床信息不存在:", cli_path))
  cli <- read.delim(cli_path, stringsAsFactors=FALSE, check.names=FALSE)
  # 若临床含组别列 _synced，记录备用（本分析不强制）
  synced_col <- grep("_synced$", colnames(cli), value=TRUE)
  if (length(synced_col) > 0) { synced_col <- synced_col[1]; cat("临床含分组列:", synced_col, "\n") }
  else synced_col <- NULL

  # 3. 基因集过滤（可选）
  if (gene_file != "" && gene_file != "NONE" && file.exists(gene_file)) {
    ext <- tolower(tools::file_ext(gene_file))
    if (ext %in% c("xlsx","xls")) gdf <- read.xlsx(gene_file, colNames=FALSE)
    else gdf <- read.table(gene_file, header=FALSE, stringsAsFactors=FALSE, fill=TRUE, comment.char="#")
    gene_vec <- trimws(as.character(gdf[[1]][!is.na(gdf[[1]]) & as.character(gdf[[1]])!=""]))
    common_genes <- intersect(rownames(expr), gene_vec)
    cat("基因集:", length(gene_vec), "个；与表达交集:", length(common_genes), "个\n")
  } else {
    common_genes <- rownames(expr); cat("未指定基因集，使用全部基因:", length(common_genes), "个\n")
  }
  if (length(common_genes)==0) stop("未找到可用基因")
  expr <- expr[common_genes, , drop=FALSE]

  # 4. 生存元数据（Py 端从 h5ad obs 提取，写入 out_dir/surv_meta.txt 的副本）
  #    列为: sample(带数据集前缀或原始), time, status, cohort(数据集名)
  surv_path <- file.path(out_dir, surv_meta_file)
  if (!file.exists(surv_path)) stop(paste("生存元数据不存在:", surv_path, "\n请先在界面运行「提取生存信息」(Py端生成)"))
  surv <- read.delim(surv_path, stringsAsFactors=FALSE, check.names=FALSE)
  cat("生存元数据: ", nrow(surv), "样本 x", ncol(surv), "列 [", paste(colnames(surv), collapse=","), "]\n")

  # 5. 高变异基因限制（供批量建模特征空间）
  if (nrow(expr) > max_genes) {
    rv <- apply(expr, 1, var, na.rm=TRUE)
    expr <- expr[order(rv, decreasing=TRUE)[seq_len(max_genes)], , drop=FALSE]
    cat("高变异基因限制: 截取前 ", max_genes, " 个\n", sep="")
  }
  # 基因名安全化（引擎公式需要 make.names），保存映射
  safe_genes <- make.names(rownames(expr), unique=TRUE)
  gene_map <- data.frame(safe=safe_genes, original=rownames(expr), stringsAsFactors=FALSE)

  # 6. 样本交集：表达 ∩ 生存元数据（按 sample 列对应表达列名）
  surv_samples <- surv$sample[surv$sample %in% colnames(expr)]
  if (length(surv_samples)==0) stop("表达矩阵列名与生存元数据 sample 列无交集，请检查样本名对齐")
  expr <- expr[, surv_samples, drop=FALSE]
  surv <- surv[match(surv_samples, surv$sample), , drop=FALSE]
  cat("对齐后生存样本数:", nrow(surv), "\n")

  # 7. 拆分数据集（按 cohort 列，或从样本名前缀推导）
  if ("cohort" %in% colnames(surv) && any(!is.na(surv$cohort) & surv$cohort!="")) {
    dataset <- surv$cohort
  } else {
    dataset <- sub("_.*$", "", surv_samples)
  }
  uniq_pfx <- unique(dataset)
  cat("检测到数据集(cohort): ", paste(uniq_pfx, collapse=", "), "\n")
  if (length(uniq_pfx) < 1) stop("未检测到任何数据集")

  # 训练集 = 第一个数据集；验证集 = 其余
  train_name <- uniq_pfx[1]
  val_names  <- setdiff(uniq_pfx, train_name)
  cat("训练集:", train_name, " 验证集:", paste(val_names, collapse=", "), "\n")

  # 8. 逐数据集标准化 + 组织数据
  list(list())  # placeholder
  ExprList <- list(); SurvList <- list(); MatList <- list()
  for (i in seq_along(uniq_pfx)) {
    pfx <- uniq_pfx[i]
    idx <- which(dataset == pfx)
    if (length(idx) < 2) { cat(sprintf("  [%s] 样本过少(%d)，跳过\n", pfx, length(idx))); next }
    sub_expr <- expr[, idx, drop=FALSE]
    sub_surv <- surv[idx, , drop=FALSE]
    # 仅保留 time>0 且 status 有效
    keep <- !is.na(sub_surv$time) & sub_surv$time > 0 &
            !is.na(sub_surv$status) & sub_surv$status %in% c(0,1)
    sub_expr <- sub_expr[, which(keep), drop=FALSE]
    sub_surv <- sub_surv[keep, , drop=FALSE]
    if (ncol(sub_expr) < 2) { cat(sprintf("  [%s] 有效生存样本过少，跳过\n", pfx)); next }
    # 转置为 样本x基因（暂不标准化，标准差放在下面统一按训练集基准做，与调试版一致）
    m <- t(sub_expr); colnames(m) <- safe_genes; rownames(m) <- colnames(sub_expr)
    ExprList[[pfx]] <- m
    SurvList[[pfx]] <- data.frame(time=as.numeric(sub_surv$time), status=as.integer(sub_surv$status),
                                   stringsAsFactors=FALSE, check.names=FALSE)
    MatList[[pfx]] <- sub_expr
    cat(sprintf("  [%s] 样本=%d 基因=%d, 生存中位time=%.1f, 事件%d\n",
                pfx, nrow(m), ncol(m), median(sub_surv$time), sum(sub_surv$status==1)))
  }
  if (length(ExprList) < 1) stop("所有数据集均无有效生存样本")
  if (!(train_name %in% names(ExprList))) {
    # 训练集缺样本则取第一个有数据的
    cand <- names(ExprList)
    train_name <- cand[1]
  }
  cat("最终训练集:", train_name, "\n")

  # 统一按训练集基准 z-score 标准化（防数据污染；训练集和验证集都只用一次，与调试版完全一致）
  T_ref <- ExprList[[train_name]]
  mu <- colMeans(T_ref); sdv <- apply(T_ref, 2, sd); sdv[sdv==0] <- 1
  std_fn <- function(m) scale(m, center=mu, scale=sdv)
  for (pfx in names(ExprList)) {
    ExprList[[pfx]] <- std_fn(ExprList[[pfx]])
  }
  T_Expr <- ExprList[[train_name]]

  save(ExprList, SurvList, train_name, val_names, gene_map, common_genes,
       file=train_data_file)
  cat("生存训练数据已保存:", train_data_file, "\n")

  # 供 UI 展示的概要
  write.table(data.frame(Item=c("Gene","TrainSamples","Cohorts","TrainCohort","ValCohorts"),
                         Value=c(ncol(T_Expr), nrow(T_Expr),
                                 paste(names(ExprList), collapse=","), train_name,
                                 paste(val_names, collapse=","))),
              file=file.path(out_dir,"train_ready.txt"), sep="\t", quote=FALSE, row.names=FALSE)
  cat("阶段一完成\n")
}

# ============================================================
# 阶段二：批量建模（算法选基因）
# 用 event 二分类标签训练各个算法，ExtractVarTopN 提取基因子集
# ============================================================
run_stage2 <- function() {
  if (!file.exists(train_data_file)) stop("请先运行阶段一生成训练数据")
  load(train_data_file)

  # 使用指定的算法组合文件（可来自 APPDATA/machinelearning 下拉框选择）
  chosen_methods_file <- if (methods_file != "" && methods_file != "NONE" && file.exists(methods_file)) methods_file else
                            file.path(script_dir, "methods.txt")
  if (!file.exists(chosen_methods_file)) stop(paste("算法组合文件不存在:", chosen_methods_file))
  methods_list <- readLines(chosen_methods_file)
  methods_list <- methods_list[!is.na(methods_list) & methods_list != ""]
  cat("共读取", length(methods_list), "种算法组合:", basename(chosen_methods_file), "\n")

  # 训练表达（样本x基因）+ 生存
  T_Expr <- ExprList[[train_name]]
  T_Surv <- SurvList[[train_name]]
  if (sum(T_Surv$status==1) < 2) stop("训练集事件过少，无法建模")

  # 缓存：算法组合 + 训练数据指纹共同作为缓存 key，避免换文件/增删算法/数据预处理变更时误用旧缓存
  cache_key_file <- file.path(out_dir, "gene_model_cache_key.txt")
  data_fp <- paste(nrow(T_Expr), ncol(T_Expr), sum(T_Surv$status==1), seed,
                   tryCatch(paste(as.integer(round(rowSums(T_Expr, na.rm=TRUE)*1e6, 0))[seq_len(min(3,nrow(T_Expr)))], collapse="_"), error=function(e) "na"))
  cur_key <- paste(paste(sort(methods_list), collapse="\n"), "||DATA_FP||", data_fp, sep="")
  method_gene <- NULL
  if (file.exists(gene_model_file) && file.exists(cache_key_file)) {
    old_key <- paste(readLines(cache_key_file), collapse="\n")
    if (identical(old_key, cur_key)) {
      load(gene_model_file)
      cat("加载已保存的算法基因集缓存\n")
    } else {
      cat("检测到算法组合变更，重新建模\n")
    }
  }
  if (is.null(method_gene)) {
    cat("开始批量建模(event二分类)...\n")
    set.seed(seed)
    fit_by_method <- ML.Dev.Class.Sig(
      list_train_vali_Data = list(TRAIN=data.frame(outcome=T_Surv$status, T_Expr, check.names=FALSE)),
      methods=methods_list,
      classVar="outcome",
      min.selected.var=3,
      seed=seed
    )
    cat("成功训练模型数:", length(fit_by_method$model), "\n")

    # 提取每个算法选中基因（重要性 Top-N 比例法；无重要性算法截断到 max_features 高方差基因）
    method_gene <- list()
    for (m in names(fit_by_method$model)) {
      genes <- tryCatch(ExtractVarTopN(fit_by_method$model[[m]], top_frac=top_frac, min_keep=5),
                        error=function(e) NULL)
      if (is.null(genes) || length(genes) < 1) next
      if (length(genes) > max_features) {
        feats <- intersect(genes, colnames(T_Expr))
        v <- if (length(feats)>1) apply(T_Expr[, feats, drop=FALSE], 2, var) else setNames(1, feats)
        v <- v[is.finite(v)]
        genes <- names(sort(v, decreasing=TRUE))[seq_len(max_features)]
      }
      method_gene[[m]] <- intersect(genes, colnames(T_Expr))
    }
    cat("有基因输出的算法数:", length(method_gene), "\n")
    save(method_gene, file=gene_model_file)
    writeLines(cur_key, cache_key_file)
  }
  cat("阶段二完成\n")
}

# ============================================================
# 阶段三：生存分析（Cox + timeROC iAUC/C-index）+ iAUC 热图 + 排序
# ============================================================
run_stage3 <- function() {
  suppressMessages({ library(timeROC); library(ComplexHeatmap); library(circlize) })
  if (!file.exists(train_data_file)) stop("请先运行阶段一生成训练数据")
  if (!file.exists(gene_model_file)) stop("请先运行阶段二生成算法基因集")
  load(train_data_file); load(gene_model_file)

  T_Expr <- ExprList[[train_name]]
  T_Surv <- SurvList[[train_name]]
  TRAIN  <- data.frame(time=T_Surv$time, status=T_Surv$status, T_Expr, check.names=FALSE)

  cat("训练集:", nrow(T_Expr), "样本 x", ncol(T_Expr), "基因\n")

  # ---- 单变量 Cox 显著性评估 + 多变量 Cox + 风险预测 + iAUC/CI ----
  EvalOne <- function(genes, mname){
    genes <- intersect(genes, colnames(T_Expr))
    if (length(genes) < 1) return(NULL)
    # 1) 单变量 Cox 挑显著基因 (p<0.05)
    sig_genes <- character(0)
    for (g in genes) {
      rr <- tryCatch(summary(coxph(Surv(time, status) ~ x, data=data.frame(time=TRAIN$time, status=TRAIN$status, x=T_Expr[,g]))),
                     error=function(e) NULL)
      if (!is.null(rr)) {
        pv <- rr$coefficients[1, "Pr(>|z|)"]
        if (!is.na(pv) && pv < 0.05) sig_genes <- c(sig_genes, g)
      }
    }
    if (length(sig_genes)==0) { cat(sprintf("  [%s] 无显著基因，跳过\n", mname)); return(NULL) }
    # 2) 按 p 排序，多变量 Cox 取前 15
    sig_p <- sapply(sig_genes, function(g){
      rr <- tryCatch(summary(coxph(Surv(time,status)~x,data=data.frame(time=TRAIN$time,status=TRAIN$status,x=T_Expr[,g]))),
                     error=function(e) NULL)
      if (is.null(rr)) Inf else as.numeric(rr$coefficients[1,"Pr(>|z|)"])
    })
    sig_genes <- sig_genes[order(sig_p, sig_genes)]
    model_genes <- head(sig_genes, 15)
    fml <- as.formula(paste("Surv(time,status) ~", paste("`",model_genes,"`",sep="",collapse=" + ")))
    cx <- tryCatch(coxph(fml, data=data.frame(time=TRAIN$time,status=TRAIN$status,T_Expr[,model_genes,drop=FALSE])),
                   error=function(e) NULL)
    if (is.null(cx)) {
      g1 <- sig_genes[1]
      cx <- tryCatch(coxph(Surv(time,status)~x,data=data.frame(time=TRAIN$time,status=TRAIN$status,x=T_Expr[,g1])),
                     error=function(e) NULL)
      model_genes <- g1
      if (is.null(cx)) return(NULL)
    }
    # 3) 预测三队列风险
    predict_risk <- function(datx){
      nm <- intersect(model_genes, colnames(datx))
      if (length(nm)==0) return(rep(0, nrow(datx)))
      tryCatch(as.numeric(predict(cx, newdata=data.frame(datx[,nm,drop=FALSE]))),
               error=function(e) rep(0, nrow(datx)))
    }
    r_tr <- predict_risk(T_Expr)
    risks <- list(); for (pfx in val_names) risks[[pfx]] <- predict_risk(ExprList[[pfx]])
    # 4) time-dependent AUC（多时点均值 = iAUC）+ C-index：三队列
    calc_iAUC <- function(tt, st, risk){
      if (length(unique(risk))<2 || sum(st, na.rm=TRUE)<2) return(NA)
      aucs <- sapply(time_points, function(tp){
        tryCatch({
          roc1 <- timeROC(T=tt, delta=st, marker=risk, cause=1, weighting="marginal", times=tp, iid=FALSE)
          loc <- which(roc1$times==tp)
          if (length(loc)>0) as.numeric(roc1$AUC[loc]) else NA
        }, error=function(e) NA)
      })
      if (all(is.na(aucs))) NA else mean(aucs, na.rm=TRUE)
    }
    calc_CI <- function(tt, st, risk){
      dd <- data.frame(time=tt,status=st,risk=risk); dd <- dd[complete.cases(dd),]
      if (nrow(dd)<5 || length(unique(dd$risk))<2) return(NA)
      tryCatch(unname(concordance(coxph(Surv(time,status)~risk,data=dd))$concordance), error=function(e) NA)
    }
    auc_tr <- calc_iAUC(T_Surv$time, T_Surv$status, r_tr)
    auc_val <- sapply(val_names, function(pfx) calc_iAUC(SurvList[[pfx]]$time, SurvList[[pfx]]$status, risks[[pfx]]))
    ci_tr <- calc_CI(T_Surv$time, T_Surv$status, r_tr)
    ci_val <- sapply(val_names, function(pfx) calc_CI(SurvList[[pfx]]$time, SurvList[[pfx]]$status, risks[[pfx]]))
    cat(sprintf("  [%s] 选中%d 显著%d | iAUC 训练%.3f 验证[%s]| CI 训练%.3f\n",
                mname, length(genes), length(sig_genes), auc_tr,
                paste(round(auc_val,3), collapse="/"), ci_tr))
    # 训练/验证 iAUC 与 C-index 按数据集原名命名（与 all_cohorts 一致）
    auc_res <- c(auc_tr, auc_val); names(auc_res) <- c(train_name, names(auc_val))
    ci_res  <- c(ci_tr,  ci_val ); names(ci_res)  <- c(train_name, names(ci_val))
    list(method=mname, genes=model_genes, sig_genes=sig_genes, model_genes=model_genes, cox=cx,
         auc=auc_res, cindex=ci_res,
         risk_train=r_tr, risks_val=risks)
  }

  cat("=== 逐算法 Cox 建模 + 生存评价 ===\n")
  res_list <- list()
  for (m in names(method_gene)) {
    rr <- tryCatch(EvalOne(method_gene[[m]], m), error=function(e){ cat("  Cox失败:",conditionMessage(e),"\n"); NULL })
    if (!is.null(rr)) res_list[[m]] <- rr
  }
  cat("成功完成生存评价的算法数:", length(res_list), "\n")
  if (length(res_list)==0) stop("所有算法均无有效生存模型")

  # ---- 性能表 ----
  # 列顺序: method, n_selected, n_significant, 训练iAUC, 每验证集iAUC, 训练CI, 每验证集CI
  all_cohorts <- c(train_name, val_names)
  perf <- data.frame(method=names(res_list),
                     n_selected=sapply(res_list, function(x) length(x$genes)),
                     n_significant=sapply(res_list, function(x) length(x$sig_genes)),
                     stringsAsFactors=FALSE, check.names=FALSE)
  for (cn in paste0("iAUC_", make.names(all_cohorts))) perf[[cn]] <- NA_real_
  for (cn in paste0("CI_", make.names(all_cohorts))) perf[[cn]] <- NA_real_
  for (m in names(res_list)) {
    x <- res_list[[m]]
    for (k in seq_along(all_cohorts)) {
      cname <- all_cohorts[k]
      perf[[paste0("iAUC_", make.names(cname))]][perf$method==m] <- as.numeric(x$auc[[cname]])
      perf[[paste0("CI_", make.names(cname))]][perf$method==m] <- as.numeric(x$cindex[[cname]])
    }
  }
  perf$avg_iAUC <- rowMeans(perf[, paste0("iAUC_", make.names(all_cohorts)), drop=FALSE], na.rm=TRUE)
  perf <- perf[order(-perf$avg_iAUC), ]
  rownames(perf) <- NULL
  write.table(perf, file.path(out_dir, "method_performance.txt"), sep="\t", row.names=FALSE, quote=FALSE)
  cat("算法性能排序已保存:", file.path(out_dir, "method_performance.txt"), "\n")

  # ---- iAUC 热图（复用已认可的 plot_surv_heatmap.R 第4版写法）----
  plot_iAUC_heatmap(perf, all_cohorts, train_name, val_names)
  cat("iAUC 热图已保存\n")

  # 保存中间结果
  save(perf, res_list, file=results_file, envir=environment())
  cat("阶段三完成\n")
}

# ============================================================
# iAUC 热图（第4版：不设固定width、row_names_max_width 保行名、横排列名、
# 数据集原名、右侧 Overall/Testing 双bar黑字数值、gap 拉开间距、窄色块）
# ============================================================
plot_iAUC_heatmap <- function(perf, all_cohorts, train_name, val_names){
  library(ComplexHeatmap); library(grid); library(circlize)
  AUC <- as.data.frame(perf[, paste0("iAUC_", make.names(all_cohorts)), drop=FALSE], check.names=FALSE)
  colnames(AUC) <- all_cohorts
  rownames(AUC) <- perf$method

  # 行排序：按平均 iAUC 降序
  avg_iAUC <- apply(as.matrix(AUC),1,mean,na.rm=TRUE)
  ord <- order(avg_iAUC, decreasing=TRUE)
  AUC <- AUC[ord,,drop=FALSE]; avg_iAUC <- avg_iAUC[ord]

  # Cohort 注解（训练集 + 验证集）
  cohort_fac <- factor(ifelse(colnames(AUC)==train_name, "Training", paste0("Test", match(colnames(AUC), setdiff(colnames(AUC), train_name)))),
                       levels=c("Training", setdiff(paste0("Test", seq_along(val_names)), "Training")))
  # 颜色按实际 cohort 数量取前 N 种，names 与 levels(cohort_fac) 严格一致
  ntest <- length(all_cohorts) - 1
  cc_levels <- c("Training", if (ntest>=1) paste0("Test", seq_len(ntest)))
  cohort_pal <- c("#66C2A5","#FC8D62","#8DA0CB","#A6D854")
  CohortCol <- setNames(cohort_pal[seq_len(length(cc_levels))], cc_levels)

  test_cols <- which(colnames(AUC) != train_name)
  test_avg <- if (length(test_cols)>0) apply(as.matrix(AUC[,test_cols,drop=FALSE]),1,mean,na.rm=TRUE) else rep(NA,nrow(AUC))
  avg_iAUC_fmt  <- as.numeric(format(avg_iAUC,digits=3,nsmall=3))
  test_avg_fmt  <- as.numeric(format(test_avg,digits=3,nsmall=3))

  col_ha <- columnAnnotation("Cohort"=cohort_fac,
                             col=list("Cohort"=CohortCol),
                             show_annotation_name=TRUE,
                             annotation_name_gp=gpar(fontsize=11,fontface="bold"),
                             simple_anno_size=unit(0.4,"cm"))
  bar_colors <- c("steelblue","#79ae96")
  make_bar <- function(vals, fill){
    anno_barplot(vals, which="row", bar_width=0.7, border=FALSE, gp=gpar(fill=fill,col=NA),
                 add_numbers=TRUE, numbers_gp=gpar(fontsize=9,col="black",fontface="bold"),
                 axis_param=list(at=c(0,0.5,1),labels_rot=0), width=unit(4,"cm"))
  }
  # 仅当存在验证集时显示 Testing bar
  # 每个 bar 作为独立命名参数传入 rowAnnotation（对齐认可写法），而非包成 list
  anno_list <- list("Overall_Avg"=make_bar(avg_iAUC_fmt, bar_colors[1]))
  if (length(test_cols)>0) anno_list[["Testing_Avg"]] <- make_bar(test_avg_fmt, bar_colors[2])
  row_ha <- do.call(rowAnnotation, c(anno_list, list(
    show_annotation_name=TRUE,
    annotation_name_gp=gpar(fontsize=10,fontface="bold"),
    gap=if(length(test_cols)>0) unit(0.8,"cm") else unit(0.3,"cm"))))

  cell_fun <- function(j,i,x,y,w,h,fill){
    v <- as.numeric(AUC[i,j])
    grid.text(ifelse(is.na(v), "--", sprintf("%.3f",v)), x,y, gp=gpar(fontsize=8))
  }
  # 热图主体尺寸(固定 cm) 由算法数/队列数决定，Heatmap 与设备画布共享同一组值，
  # 保证画布恰好包裹热图(无大留白)，新增算法/队列自动放大。
  body_w_cm <- 1.6 * ncol(AUC)                 # 热图主体宽(cm)
  body_h_cm <- 0.45 * nrow(AUC)                # 热图主体高(cm)
  hm <- Heatmap(as.matrix(AUC), name="iAUC",
                col=colorRamp2(c(0,0.5,1), c("#4195C1","#FFFFFF","#CB5746")),
                right_annotation=row_ha, top_annotation=col_ha,
                cluster_columns=FALSE, cluster_rows=FALSE,
                row_names_side="left", show_row_names=TRUE, row_names_gp=gpar(fontsize=9),
                row_names_max_width=unit(2.6,"cm"),
                show_column_names=TRUE, column_names_side="top",
                column_names_rot=0, column_names_centered=FALSE,
                column_names_gp=gpar(fontsize=11,fontface="bold"),
                width=unit(body_w_cm,"cm"), height=unit(body_h_cm,"cm"),
                cell_fun=cell_fun)
  bar_legend <- Legend(labels=c("Overall Average","Testing Average"), title="Average Types",
                       legend_gp=gpar(fill=bar_colors))

  # 设备画布尺寸由用户参数 plot_width_cm / plot_height_cm 控制（可自调）
  pdf(file.path(out_dir,"surv_iAUC_heatmap.pdf"), width=plot_width_cm, height=plot_height_cm)
  draw(hm, annotation_legend_list=list(bar_legend)); dev.off()
  png(file.path(out_dir,"surv_iAUC_heatmap.png"),
      width=as.integer(plot_width_cm*200), height=as.integer(plot_height_cm*200), res=200)
  draw(hm, annotation_legend_list=list(bar_legend)); dev.off()

  df <- data.frame(Model=rownames(AUC), Avg_iAUC=round(avg_iAUC,4))
  write.table(df, file.path(out_dir,"surv_iAUC_sorted.txt"), sep="\t", row.names=FALSE, quote=FALSE)
}

# ============================================================
# 阶段四：最优基因（最优算法 + 其生存意义基因单变量Cox表）
# ============================================================
run_stage4 <- function() {
  library(pROC)
  if (!file.exists(results_file)) stop("请先运行阶段三生成生存分析结果")
  load(results_file)
  load(train_data_file)
  if (length(res_list)==0) stop("无有效生存模型结果")

  best_method <- perf$method[1]
  best <- res_list[[best_method]]
  cat("最优算法:", best_method, "\n")

  T_Expr <- ExprList[[train_name]]
  T_Surv <- SurvList[[train_name]]
  TRAIN  <- data.frame(time=T_Surv$time, status=T_Surv$status, T_Expr, check.names=FALSE)

  # 显著基因单变量 Cox 表（HR, HR_low, HR_high, p, FDR, direction）
  single_df <- do.call(rbind, lapply(best$sig_genes, function(g){
    rr <- tryCatch(summary(coxph(Surv(time,status)~x,data=data.frame(time=TRAIN$time,status=TRAIN$status,x=T_Expr[,g]))),
                   error=function(e) NULL)
    if (is.null(rr)) return(NULL)
    co <- rr$coefficients[1,]; conf <- rr$conf.int[1,]
    data.frame(gene=g, beta=co[["coef"]], HR=conf[["exp(coef)"]],
               HR_low=conf[["lower .95"]], HR_high=conf[["upper .95"]],
               pvalue=co[["Pr(>|z|)"]], stringsAsFactors=FALSE)
  }))
  if (is.null(single_df)) stop("最优算法无显著基因")
  single_df$FDR <- p.adjust(single_df$pvalue, method="BH")
  single_df$direction <- ifelse(single_df$HR > 1, "Risk(高表达风险)", "Protective(保护)")
  single_df <- single_df[order(single_df$pvalue), ]
  # 还原原始基因名
  if (nrow(gene_map)>0) {
    lut <- setNames(gene_map$original, gene_map$safe)
    mapped <- lut[single_df$gene]; single_df$gene[!is.na(mapped)] <- mapped[!is.na(mapped)]
  }
  safe_m <- gsub("[^A-Za-z0-9]","_",best_method)
  write.table(single_df, file.path(out_dir, paste0("best_method_genes_",safe_m,".txt")),
              sep="\t", row.names=FALSE, quote=FALSE)
  cat("最优算法生存意义基因已保存\n")

  # 供 UI 表格展示的全基因表（含最终选入基因 + 单变量指标）
  full <- single_df
  full$Method <- best_method
  write.table(full, file.path(out_dir,"surv_best_gene_list.txt"), sep="\t", row.names=FALSE, quote=FALSE)

  # 简单森林图？不强制；输出表格即可。控制台展示
  print(head(single_df, 15), digits=3)
  cat("阶段四完成\n")
}

# ============================================================
# 阶段分发
# ============================================================
switch(mode,
  "stage1" = run_stage1(),
  "stage2" = run_stage2(),
  "stage3" = run_stage3(),
  "stage4" = run_stage4(),
  stop(paste("未知阶段:", mode))
)
cat("============================================================\n")
cat("阶段 [", mode, "] 已成功完成\n")
cat("输出目录:", out_dir, "\n")
cat("============================================================\n")
