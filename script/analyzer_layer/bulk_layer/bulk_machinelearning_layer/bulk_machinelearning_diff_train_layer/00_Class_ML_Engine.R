# =========================================================================
# Script Name: 00_Class_ML_Engine.R
# =========================================================================

# 0. Stepglm 步数常量 -----------------------------------------------------
# 原先 30/50/50 是散落在 step() 调用里的魔法数字，已提为具名常量：
#   - 便于集中说明取值含义；
#   - 便于缓存键比对（bulk_machinelearning_diff_train.R 阶段三会把这里的取值
#     并入缓存 tag，避免改了上限却静默复用旧模型）。
# 注意：数值与改造前完全一致，未改变算法行为。
STEPGLM_STEPS_BACKWARD_PRE <- 30  # backward 方向：先 forward 预筛的步数上限
STEPGLM_STEPS_FORWARD      <- 50  # forward / both 方向的步数上限
STEPGLM_STEPS_BACKWARD     <- 50  # backward 方向：消除阶段的步数上限

# 记录 step() 实际走了几步、是否撞到步数上限，挂到 fit 的 "step_info" 属性上。
# step() 返回对象带 anova 分量（每步一行，含首行 <none>），故实际步数 = nrow - 1；
# 若该分量缺失则退路为记录最终保留的变量数。
# 整段用 tryCatch 包裹：统计失败绝不影响建模主流程。
attach_step_info <- function(fit, steps_limit) {
  tryCatch({
    a <- fit$anova
    n_steps <- if (is.null(a) || is.null(nrow(a))) NA_integer_ else as.integer(nrow(a) - 1L)
    n_terms <- tryCatch(length(attr(terms(fit), "term.labels")), error = function(e) NA_integer_)
    attr(fit, "step_info") <- list(
      steps_limit = as.integer(steps_limit),
      steps_used  = n_steps,
      terms_kept  = n_terms,
      hit_limit   = (!is.na(n_steps) && !is.na(steps_limit) && n_steps >= steps_limit)
    )
  }, error = function(e) NULL)
  return(fit)
}

# 1. Main Algorithm Dispatcher --------------------------------------------
RunML <- function(method, Train_set, Train_label, mode = "Model", classVar){
  method = gsub(" ", "", method) 
  method_name = gsub("(\\w+)\\[(.+)\\]", "\\1", method)  
  method_param = gsub("(\\w+)\\[(.+)\\]", "\\2", method) 
  
  method_param = if (grepl("\\[\\S+\\]", method)) {
    suppressWarnings(switch(
      EXPR = method_name,
      "Enet" = list("alpha" = as.numeric(gsub("alpha=", "", method_param))),
      "Stepglm" = list("direction" = method_param),
      "NN" = list(
        "size" = as.numeric(sub(".*size=(\\d+).*", "\\1", method_param)),
        "decay" = as.numeric(sub(".*decay=(\\S+).*", "\\1", method_param))
      ),
      "RF" = list("mtry" = as.numeric(sub(".*mtry=(\\d+).*", "\\1", method_param))),
      "SVM" = list(
        "cost" = as.numeric(sub(".*cost=(\\S+).*", "\\1", method_param)),
        "gamma" = as.numeric(sub(".*gamma=(\\S+).*", "\\1", method_param))
      ),
      "XGBoost" = list("max_depth" = as.numeric(sub(".*max_depth=(\\d+).*", "\\1", method_param))),
      "GBM" = list(
        "shr" = as.numeric(sub(".*shr=(\\S+).*", "\\1", method_param)),
        "id" = as.numeric(sub(".*id=(\\d+).*", "\\1", method_param))
      ),
      NULL
    ))
  } else {
    # 无方括号参数：保留内部参数提取（Enet/Stepglm 也可能无参数）
    switch(
      EXPR = method_name,
      "Enet" = list("alpha" = as.numeric(gsub("alpha=", "", method_param))),
      "Stepglm" = list("direction" = method_param),
      NULL
    )
  }
  message(">> Running [", method_name, "] for [", mode, "] | Params: ", method_param, " | Features: ", ncol(Train_set))
  
  args = list("Train_set" = Train_set, "Train_label" = Train_label, "mode" = mode, "classVar" = classVar)
  args = c(args, method_param)
  obj <- do.call(what = paste0("Run", method_name), args = args) 
  
  if(mode == "Variable") message("   Retained: ", length(obj), " variables.\n") else message("\n")
  return(obj)
}

# 2. Specific Algorithm Modules -------------------------------------------
RunEnet <- function(Train_set, Train_label, mode, classVar, alpha){
  x_mat <- as.matrix(Train_set)
  cv.fit = cv.glmnet(x = x_mat, y = Train_label[[classVar]], family = "binomial", alpha = alpha, nfolds = 10)
  fit = glmnet(x = x_mat, y = Train_label[[classVar]], family = "binomial", alpha = alpha, lambda = cv.fit$lambda.min)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunLasso <- function(Train_set, Train_label, mode, classVar){ RunEnet(Train_set, Train_label, mode, classVar, alpha = 1) }
RunRidge <- function(Train_set, Train_label, mode, classVar){ RunEnet(Train_set, Train_label, mode, classVar, alpha = 0) }

RunStepglm <- function(Train_set, Train_label, mode, classVar, direction){
  # 从空模型开始的forward选择，避免在771特征上拟合全模型过慢
  data <- as.data.frame(Train_set)
  data[[classVar]] <- Train_label[[classVar]]
  n_obs <- nrow(data)

  null_model <- glm(formula = as.formula(paste(classVar, "~ 1")),
                    family = "binomial", data = data)
  full_form <- as.formula(paste(classVar, "~",
                                paste(colnames(Train_set), collapse = " + ")))

  if (direction == "backward") {
    # backward需要从全模型开始；先forward预筛选30特征，再backward消除
    forward_fit <- step(null_model,
                        scope = list(lower = null_model, upper = full_form),
                        direction = "forward", trace = 0, steps = STEPGLM_STEPS_BACKWARD_PRE,
                        k = log(n_obs))
    fit <- step(forward_fit,
                direction = "backward", trace = 0, steps = STEPGLM_STEPS_BACKWARD,
                k = log(n_obs))
    fit <- attach_step_info(fit, STEPGLM_STEPS_BACKWARD)
  } else {
    # forward和both都从空模型开始
    fit <- step(null_model,
                scope = list(lower = null_model, upper = full_form),
                direction = direction, trace = 0, steps = STEPGLM_STEPS_FORWARD,
                k = log(n_obs))
    fit <- attach_step_info(fit, STEPGLM_STEPS_FORWARD)
  }
  # 回显实际步数，便于在日志里确认是否撞到上限（W5 运行时读这一行/读 attr(fit,"step_info")）
  si <- attr(fit, "step_info")
  if (!is.null(si)) {
    message("   [Stepglm-", direction, "] 实际步数=", si$steps_used,
            " 上限=", si$steps_limit, " 触发上限=", si$hit_limit,
            " 保留变量=", si$terms_kept)
  }
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunSVM <- function(Train_set, Train_label, mode, classVar, cost = NA, gamma = NA){
  data <- as.data.frame(Train_set)
  data[[classVar]] <- as.factor(Train_label[[classVar]])
  args_svm <- list(formula = eval(parse(text = paste(classVar, "~."))), data = data, probability = T, kernel = "radial")
  # cost / gamma 通过 SVM[cost=..,gamma=..] 指定，未指定时长用 e1071 默认
  if (!is.na(cost) && length(cost) > 0 && is.numeric(cost)) args_svm$cost <- cost
  if (!is.na(gamma) && length(gamma) > 0 && is.numeric(gamma)) args_svm$gamma <- gamma
  fit <- do.call(svm, args_svm)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunLDA <- function(Train_set, Train_label, mode, classVar){
  data <- as.data.frame(Train_set)
  data[[classVar]] <- as.factor(Train_label[[classVar]])
  fit = train(eval(parse(text = paste(classVar, "~."))), data = data, method="lda", trControl = trainControl(method = "cv"))
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunglmBoost <- function(Train_set, Train_label, mode, classVar){
  data <- cbind(Train_set, Train_label[classVar])
  data[[classVar]] <- as.factor(data[[classVar]])
  fit <- glmboost(eval(parse(text = paste(classVar, "~."))), data = data, family = Binomial())
  cvm <- cvrisk(fit, papply = lapply, folds = cv(model.weights(fit), type = "kfold"))
  fit <- glmboost(eval(parse(text = paste(classVar, "~."))), data = data, family = Binomial(), control = boost_control(mstop = max(mstop(cvm), 40)))
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunplsRglm <- function(Train_set, Train_label, mode, classVar){
  cv.plsRglm.res = cv.plsRglm(formula = Train_label[[classVar]] ~ ., data = as.data.frame(Train_set), nt=10, verbose = FALSE)
  fit <- plsRglm(Train_label[[classVar]], as.data.frame(Train_set), modele = "pls-glm-logistic", verbose = F, sparse = T)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}


RunRF <- function(Train_set, Train_label, mode, classVar, mtry = NA){
  rf_nodesize = 5 
  Train_label[[classVar]] <- as.factor(Train_label[[classVar]])
  args_rf <- list(formula = formula(paste0(classVar, "~.")),
                  data = cbind(Train_set, Train_label[classVar]),
                  ntree = 1000, nodesize = rf_nodesize, importance = T,
                  proximity = T, forest = T)
  # mtry 通过 RF[mtry=..] 指定；rfsrc 的 mtry 需整数，未指定时保持默认(不传)
  if (!is.na(mtry) && length(mtry) > 0 && is.numeric(mtry) && mtry > 0) {
    args_rf$mtry <- as.integer(mtry)
  }
  fit <- do.call(rfsrc, args_rf)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunGBM <- function(Train_set, Train_label, mode, classVar, shr = NA, id = NA){
  if (is.na(shr) || !is.numeric(shr)) shr <- 0.001
  if (is.na(id) || !is.numeric(id)) id <- 3
  fit <- gbm(formula = Train_label[[classVar]] ~ ., data = as.data.frame(Train_set), distribution = 'bernoulli', n.trees = 10000, interaction.depth = id, n.minobsinnode = 10, shrinkage = shr, cv.folds = 10, n.cores = 6)
  best <- which.min(fit$cv.error)
  fit <- gbm(formula = Train_label[[classVar]] ~ ., data = as.data.frame(Train_set), distribution = 'bernoulli', n.trees = best, interaction.depth = id, n.minobsinnode = 10, shrinkage = shr, n.cores = 6)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunXGBoost <- function(Train_set, Train_label, mode, classVar, max_depth = NA){
  feat_names <- colnames(Train_set)
  if (is.na(max_depth) || !is.numeric(max_depth)) max_depth <- 2
  y_vector <- as.integer(factor(Train_label[[classVar]], levels = sort(unique(Train_label[[classVar]])))) - 1L
  X_matrix <- data.matrix(Train_set)
  dtrain_full <- xgb.DMatrix(data = X_matrix, label = y_vector)
  # xgboost 3.x: eta->learning_rate, verbose=FALSE
  xgb_params <- list(max_depth = as.integer(max_depth), learning_rate = 1, nthread = 2,
                     objective = "binary:logistic", eval_metric = "logloss")
  cv_res <- suppressMessages(xgb.cv(params = xgb_params, data = dtrain_full,
                                     nrounds = 10, nfold = 5, stratified = TRUE, verbose = FALSE))
  nround <- which.min(cv_res$evaluation_log$test_logloss_mean)
  if (length(nround) == 0 || is.na(nround)) nround <- 10
  fit <- xgb.train(params = xgb_params, data = dtrain_full, nrounds = nround)
  # xgboost 3.x: Booster是externalptr，不能用fit$xxx赋值，用attr()
  attr(fit, "subFeature") <- feat_names
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(feat_names)
}

RunNaiveBayes <- function(Train_set, Train_label, mode, classVar){
  data <- cbind(Train_set, Train_label[classVar])
  data[[classVar]] <- as.factor(data[[classVar]])
  fit <- naiveBayes(eval(parse(text = paste(classVar, "~."))), data = data)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

# --- 14算法扩展：NN / Logistic / QDA / KNN / DecisionTree ---
RunLogistic <- function(Train_set, Train_label, mode, classVar){
  data <- as.data.frame(Train_set)
  data[[classVar]] <- Train_label[[classVar]]
  # 纯逻辑回归（stats::glm，二分类）。返回 class="glm"，predict/ExtractVar 复用已有 glm 分支
  fit <- glm(as.formula(paste(classVar, "~ .")), data = data, family = "binomial")
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunNN <- function(Train_set, Train_label, mode, classVar, size = 3, decay = 1e-4){
  data <- as.data.frame(Train_set)
  data[[classVar]] <- as.factor(Train_label[[classVar]])
  # MaxNWts 需大于 (n_features+1)*size + (size+1)*n_class，否则全特征下的 NN 权重数会超默认上限(1000)报错；
  # size 由 NN[size=..,decay=..] 参数控制，decay 作为正则/抗过拟合(近似表达 dropout 强度)
  if (is.na(size) || size <= 0) size <- 3
  if (is.na(decay)) decay <- 1e-4
  fit <- nnet(as.formula(paste(classVar, "~ .")), data = data,
              size = size, decay = decay, maxit = 200, trace = FALSE,
              MaxNWts = 50000)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunQDA <- function(Train_set, Train_label, mode, classVar){
  data <- as.data.frame(Train_set)
  data[[classVar]] <- as.factor(Train_label[[classVar]])
  fit <- qda(as.formula(paste(classVar, "~ .")), data = data)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}

RunKNN <- function(Train_set, Train_label, mode, classVar){
  data <- as.data.frame(Train_set)
  data[[classVar]] <- as.factor(Train_label[[classVar]])
  fit <- knn3(as.formula(paste(classVar, "~ .")), data = data, k = 5)
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(fit$subFeature)
}

RunDecisionTree <- function(Train_set, Train_label, mode, classVar){
  data <- as.data.frame(Train_set)
  data[[classVar]] <- as.factor(Train_label[[classVar]])
  fit <- rpart(as.formula(paste(classVar, "~ .")), data = data,
               method = "class", control = rpart.control(minsplit = 10, cp = 0.01))
  fit$subFeature = colnames(Train_set)
  if (mode == "Model") return(fit)
  if (mode == "Variable") return(ExtractVar(fit))
}


# 3. Helper Modules -------------------------------------------------------
quiet <- function(..., messages=FALSE, cat=FALSE){
  if(!cat){ sink(tempfile()); on.exit(sink()) }
  out <- if(messages) eval(...) else suppressMessages(eval(...))
  out
}

ExtractVar <- function(fit){
  Feature <- quiet(switch(
    EXPR = class(fit)[1],
    "lognet"       = rownames(coef(fit))[which(coef(fit)[, 1] != 0)],
    "glm"          = names(coef(fit)[!is.na(coef(fit))]),
    "svm.formula"  = fit$subFeature, 
    "train"        = fit$coefnames, 
    "glmboost"     = names(coef(fit)[abs(coef(fit)) > 0]), 
    "plsRglmmodel" = rownames(fit$Coeffs)[fit$Coeffs != 0], 
    "rfsrc"        = {
      imp <- fit$importance
      if(is.null(imp)) {
        fit$subFeature
      } else if (is.matrix(imp)) {
        # randomForestSRC的importance是矩阵，取"importance"列(VIMP)
        imp_col <- if ("importance" %in% colnames(imp)) imp[, "importance"] else imp[, 1]
        sel <- names(imp_col)[imp_col > 0]
        # 若正VIMP特征过少(<5)，退回到按|VIMP|排序取top30
        if(length(sel) < 5) sel <- names(sort(abs(imp_col), decreasing = TRUE))[1:min(30, length(imp_col))]
        sel
      } else {
        sel <- names(imp)[imp > 0]
        if(length(sel) < 5) sel <- names(sort(abs(imp), decreasing = TRUE))[1:min(30, length(imp))]
        sel
      }
    },
    "gbm"          = rownames(summary.gbm(fit, plotit = F))[summary.gbm(fit, plotit = F)$rel.inf > 0], 
    "xgb.Booster"  = attr(fit, "subFeature"),
    "naiveBayes"   = fit$subFeature,
    "nnet.formula" = fit$subFeature,
    "qda"          = fit$subFeature,
    "knn3"         = fit$subFeature,
    "rpart"        = fit$subFeature
  ))
  Feature <- setdiff(Feature, c("(Intercept)", "Intercept"))
  return(Feature)
}

# ---- 重要性提取：为每个模型计算按特征命名的重要性分数向量 ----
# 供阶段五「重要性Top-N比例法」使用：各算法先用自带机制给全部输入特征打分，
# 然后只保留重要性排名靠前的基因作为该模型的“纳入基因”。
# 对确实无法计算重要性(SVM径向核/KNN)返回 NULL，调用方保留其全部 subFeature。
varImportance <- function(fit){
  cls <- class(fit)[1]
  imp <- tryCatch(switch(
    EXPR = cls,
    "lognet"       = { b <- coef(fit)[, 1]; abs(b[setdiff(names(b), c("(Intercept)","Intercept"))]) },
    "glm"          = { b <- coef(fit); abs(b[setdiff(names(b), c("(Intercept)","Intercept"))]) },
    "glmboost"     = { b <- coef(fit); abs(b[setdiff(names(b), c("(Intercept)","Intercept"))]) },
    "plsRglmmodel" = { b <- fit$Coeffs; abs(if (is.matrix(b)) b[, 1] else b) },
    "rfsrc"        = {
      impi <- fit$importance
      if (is.null(impi)) NULL else if (is.matrix(impi)) {
        col_i <- if ("importance" %in% colnames(impi)) impi[, "importance"] else impi[, 1]
        abs(col_i)
      } else abs(impi)
    },
    "gbm"          = {
      s <- summary.gbm(fit, plotit = FALSE)
      vals <- s$rel.inf; names(vals) <- s$var
      vals
    },
    "xgb.Booster"  = {
      ximp <- tryCatch(xgb.importance(model = fit), error = function(e) NULL)
      if (!is.null(ximp) && nrow(ximp) > 0) {
        vals <- ximp$Gain; names(vals) <- ximp$Feature
        vals
      } else NULL
    },
    "rpart"        = {
      vi <- fit$variable.importance
      if (is.null(vi)) NULL else abs(vi)
    },
    "train"        = {
      # caret 训练对象：lda 由 RunLDA 使用，取 w 系数绝对值和；无法取则返回 NULL
      cm <- fit$finalModel
      vi <- tryCatch(abs(if (is.matrix(cm$scaling)) abs(cm$scaling)[, 1] else varImp(fit)$importance),
                     error = function(e) NULL)
      vi
    },
    "nnet.formula" = {
      # nnet 连接权重：输入→隐藏层权重绝对值和(仅当有隐藏层时可算)
      n <- fit$n
      w <- fit$wts
      if (is.null(n) || length(w) == 0) NULL else {
        n.in <- n[1]; n.hid <- n[2]
        if (is.na(n.hid) || n.hid < 1 || n.hid > 100) NULL else {
          n.input.hid <- n.in * n.hid
          if (length(w) < n.input.hid) NULL else {
            input_hid_w <- w[1:n.input.hid]
            m <- matrix(input_hid_w, nrow = n.in, ncol = n.hid)
            v <- rowSums(abs(m)); names(v) <- fit$coefnames
            v
          }
        }
      }
    },
    "naiveBayes"   = {
      tabs <- fit$tables
      if (is.null(tabs)) NULL else {
        v <- sapply(tabs, function(tb) {
          if (is.matrix(tb)) abs(diff(as.numeric(tb[1, , drop = FALSE])))
          else NA
        })
        # 无行列名的表返回无名向量 → 用 fit$coefnames 兜底
        if (is.null(names(v))) { names(v) <- fit$coefnames; v <- abs(v) }
        v
      }
    },
    "qda"          = {
      sc <- fit$scaling
      if (is.null(sc)) NULL else {
        v <- apply(abs(sc), 1, sum)
        if (is.null(names(v))) names(v) <- colnames(fit$x)
        v
      }
    },
    NULL
  ), error = function(e) NULL)
  # 统一：只保留数值、非 NA 有限值，名称非空
  if (is.null(imp)) return(NULL)
  imp <- imp[is.finite(imp) & !is.na(imp) & imp > 0]
  if (length(imp) == 0) return(NULL)
  return(imp)
}

# ---- 重要性Top-N比例法提取基因 ----
# 保留重要性排名前 top_frac(比例) 的特征作为该模型纳入基因，至少保留 min_keep 个；
# 对无法计算重要性的算法返回 fit$subFeature(全量)，保证不崩。
ExtractVarTopN <- function(fit, top_frac = 0.3, min_keep = 5){
  feat_all <- setdiff(ExtractVar(fit), c("(Intercept)", "Intercept"))
  if (length(feat_all) == 0) return(character(0))
  imp <- varImportance(fit)
  if (is.null(imp) || length(imp) == 0) {
    # 无重要性算法(SVM径向/KNN等)：保留全部 subFeature
    return(feat_all)
  }
  # 只考虑重要性中出现的特征
  imp_f <- imp[intersect(names(imp), feat_all)]
  if (length(imp_f) == 0) return(feat_all)
  imp_sort <- sort(imp_f, decreasing = TRUE)
  n_keep <- max(min_keep, min(length(imp_sort), ceiling(length(imp_sort) * top_frac)))
  return(names(imp_sort)[1:n_keep])
}

CalPredictScore <- function(fit, new_data, type = "lp"){
  features <- if (inherits(fit, "xgb.Booster")) attr(fit, "subFeature") else fit$subFeature
  new_data <- new_data[, features, drop = FALSE]
  RS <- quiet(switch(
    EXPR = class(fit)[1],
    "lognet"       = predict(fit, type = 'response', as.matrix(new_data)), 
    "glm"          = predict(fit, type = 'response', as.data.frame(new_data)), 
    "svm.formula"  = predict(fit, as.data.frame(new_data), probability = T),  
    "train"        = predict(fit, new_data, type = "prob")[[2]],
    "glmboost"     = predict(fit, type = "response", as.data.frame(new_data)), 
    "plsRglmmodel" = predict(fit, type = "response", as.data.frame(new_data)), 
    "rfsrc"        = predict(fit, as.data.frame(new_data))$predicted[, "1"],
    "gbm"          = predict(fit, newdata = as.data.frame(new_data), n.trees = fit$n.trees, type = 'response'),
    "xgb.Booster"  = predict(fit, as.matrix(new_data)),
    "naiveBayes"   = pickPosClass(predict(object = fit, type = "raw", newdata = new_data)),
    "nnet.formula" = pickPosClass(predict(fit, newdata = as.data.frame(new_data), type = "raw")),
    "qda"          = pickPosClass(predict(fit, newdata = as.data.frame(new_data))$posterior),
    "knn3"         = pickPosClass(predict(fit, newdata = as.data.frame(new_data), type = "prob")),
    "rpart"        = pickPosClass(predict(fit, newdata = as.data.frame(new_data), type = "prob"))
  ))
  RS = as.numeric(as.vector(RS))
  names(RS) = rownames(new_data)
  return(RS)
}

PredictClass <- function(fit, new_data){
  features <- if (inherits(fit, "xgb.Booster")) attr(fit, "subFeature") else fit$subFeature
  new_data <- new_data[, features, drop = FALSE]
  label <- quiet(switch(
    EXPR = class(fit)[1],
    "lognet"       = predict(fit, type = 'class', as.matrix(new_data)),
    "glm"          = ifelse(predict(fit, type = 'response', as.data.frame(new_data)) > 0.5, "1", "0"), 
    "svm.formula"  = predict(fit, as.data.frame(new_data), decision.values = T), 
    "train"        = predict(fit, new_data, type = "raw"),
    "glmboost"     = predict(fit, type = "class", as.data.frame(new_data)), 
    "plsRglmmodel" = ifelse(predict(fit, type = 'response', as.data.frame(new_data)) > 0.5, "1", "0"), 
    "rfsrc"        = predict(fit, as.data.frame(new_data))$class,
    "gbm"          = ifelse(predict(fit, newdata = as.data.frame(new_data), n.trees = fit$n.trees, type = 'response') > 0.5, "1", "0"),
    "xgb.Booster"  = ifelse(predict(fit, as.matrix(new_data)) > 0.5, "1", "0"), 
    "naiveBayes"   = predict(object = fit, type = "class", newdata = new_data),
    "nnet.formula" = predict(fit, newdata = as.data.frame(new_data), type = "class"),
    "qda"          = as.character(predict(fit, newdata = as.data.frame(new_data))$class),
    "knn3"         = as.character(predict(fit, newdata = as.data.frame(new_data), type = "class")),
    "rpart"        = as.character(predict(fit, newdata = as.data.frame(new_data), type = "class"))
  ))
  label = as.character(as.vector(label))
  names(label) = rownames(new_data)
  return(label)
}

# 4. Data Standardization Module ------------------------------------------
standarize.fun <- function(indata, centerFlag, scaleFlag) {  
  scale(indata, center=centerFlag, scale=scaleFlag)
}

scaleData <- function(data, cohort = NULL, centerFlags = NULL, scaleFlags = NULL){
  samplename = rownames(data)
  if (is.null(cohort)){
    data <- list(data); names(data) = "training"
  }else{
    data <- split(as.data.frame(data), cohort)
  }
  
  if (is.null(centerFlags)){
    centerFlags = F; message("No centerFlags found, set as FALSE")
  }
  if (length(centerFlags)==1){
    centerFlags = rep(centerFlags, length(data)); message("Set centerFlags for all cohorts as ", unique(centerFlags))
  }
  if (is.null(names(centerFlags))){
    names(centerFlags) <- names(data); message("Match centerFlags with cohort by order\n")
  }
  
  if (is.null(scaleFlags)){
    scaleFlags = F; message("No scaleFlags found, set as FALSE")
  }
  if (length(scaleFlags)==1){
    scaleFlags = rep(scaleFlags, length(data)); message("Set scaleFlags for all cohorts as ", unique(scaleFlags))
  }
  if (is.null(names(scaleFlags))){
    names(scaleFlags) <- names(data); message("Match scaleFlags with cohort by order\n")
  }
  
  centerFlags <- centerFlags[names(data)]; scaleFlags <- scaleFlags[names(data)]
  outdata <- mapply(standarize.fun, indata = data, centerFlag = centerFlags, scaleFlag = scaleFlags, SIMPLIFY = F)
  outdata <- do.call(rbind, outdata)
  outdata <- outdata[samplename, ]
  return(outdata)
}