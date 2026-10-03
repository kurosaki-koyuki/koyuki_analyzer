# =========================================================================
# Script Name: 00_Class_Mime_Wrappers.R
# =========================================================================

# Helper: from a prediction probability matrix, extract the column corresponding
# to the positive class (label "1"). If the matrix has a single column, return
# that column directly. If a column named "1" exists, use it; otherwise use the
# last column (common for 2-class models where the last column is the event).
pickPosClass <- function(mat){
  if (is.null(mat)) return(rep(NA, length(mat)))
  m <- as.matrix(mat)
  if (ncol(m) <= 1) return(m[, 1])
  if ("1" %in% colnames(m)) return(m[, "1"])
  return(m[, ncol(m)])
}

# list_train_vali_Data: List of datasets. The first item must be the training set. Rows are samples, the first column is the grouping variable, and the rest are gene expressions.
# methods: Vector of algorithm combinations, e.g., c("Lasso + RF", "Stepglm + XGBoost").
# classVar: Column name of the categorical variable, default is "outcome".
# min.selected.var: Minimum number of features to retain, default is 5.
# seed: Random seed.
ML.Dev.Class.Sig <- function(list_train_vali_Data, methods, classVar = "outcome", min.selected.var = 5, seed = 777) {
  
  Train_data <- list_train_vali_Data[[1]] 
  Train_label <- Train_data[, classVar, drop = FALSE]
  Train_set <- Train_data[, setdiff(colnames(Train_data), classVar), drop = FALSE]
  
  methods_clean <- gsub("-| ", "", methods)
  preTrain_methods <- unique(unlist(lapply(strsplit(methods_clean, "\\+"), function(x) rev(x)[-1])))
  
  preTrain.var <- list()
  set.seed(seed)
  message("=== Step 1: Feature Pre-selection ===")
  for (m in preTrain_methods) {
    v <- tryCatch(
      RunML(method = m, Train_set = Train_set, Train_label = Train_label, mode = "Variable", classVar = classVar),
      error = function(e) { message("   --> 预筛算法 <", m, "> 失败: ", conditionMessage(e)); NULL }
    )
    # 预筛失败时回退为全特征，避免后续组合因此中断
    preTrain.var[[m]] <- if (is.null(v) || length(v) == 0) colnames(Train_set) else v
  }
  preTrain.var[["simple"]] <- colnames(Train_set) 
  
  models <- list()
  set.seed(seed)
  message("=== Step 2: Model Training ===")
  for (i in seq_along(methods_clean)) {
    method_str <- methods_clean[i]
    method_parts <- strsplit(method_str, "\\+")[[1]]
    
    if (length(method_parts) == 1) method_parts <- c("simple", method_parts)
    
    cat(sprintf("[%d/%d] Training Combination: %s\n", i, length(methods_clean), method_str))
    
    sel_vars <- preTrain.var[[method_parts[1]]]
    if (is.null(sel_vars) || length(sel_vars) == 0) {
      message("   --> Skipped: 预筛特征为空 (<", method_parts[1], ">)")
      next
    }
    Train_sub <- Train_set[, sel_vars, drop = FALSE]

    # 单个算法训练或特征提取失败只跳过该模型，不中断整批建模：
    # 不同算法(尤其新增的 NN/qda 等对特征数敏感)在特定数据上失败是正常的，
    # 不应让一个算法拖垮整个阶段三。
    fit <- tryCatch(
      RunML(method = method_parts[2], Train_set = Train_sub, Train_label = Train_label, mode = "Model", classVar = classVar),
      error = function(e) {
        message("   --> Failed to train <", method_str, ">: ", conditionMessage(e))
        NULL
      }
    )
    if (is.null(fit)) next

    sel_feats <- tryCatch(
      ExtractVar(fit),
      error = function(e) { message("   --> ExtractVar failed <", method_str, ">: ", conditionMessage(e)); NULL }
    )
    if (is.null(sel_feats)) next
    if(length(sel_feats) > min.selected.var) {
      models[[method_str]] <- fit
    } else {
      message("   --> Dropped: Selected features <= ", min.selected.var)
    }
  }
  
  message("=== Model Training Completed ===")
  return(list(model = models, methods = methods_clean, classVar = classVar))
}


# res_obj: Output object from ML.Dev.Class.Sig.
# list_train_vali_Data: List of datasets including validation cohorts.
Cal.AUC.Class.All <- function(res_obj, list_train_vali_Data) {
  
  models <- res_obj$model
  classVar <- res_obj$classVar
  
  AUC_mat <- matrix(NA, nrow = length(models), ncol = length(list_train_vali_Data))
  rownames(AUC_mat) <- names(models)
  colnames(AUC_mat) <- names(list_train_vali_Data)
  
  message("=== Step 3: Calculating AUC for all cohorts ===")
  for (m_idx in seq_along(models)) {
    m_name <- names(models)[m_idx]
    fit <- models[[m_name]]
    
    for (d_idx in seq_along(list_train_vali_Data)) {
      dataset_name <- names(list_train_vali_Data)[d_idx]
      dt <- list_train_vali_Data[[dataset_name]]
      
      # 单个(模型,数据集)的预测或 roc 异常不再中断整体热图：
      # 捕获后记为 NA，避免某个模型无法 predict 时整段阶段四崩溃。
      auc_val <- tryCatch({
        RS <- suppressWarnings(CalPredictScore(fit = fit, new_data = dt))
        if (length(RS) == 0 || all(is.na(RS))) NA else {
          rr <- suppressMessages(roc(dt[[classVar]], RS))
          as.numeric(auc(rr))
        }
      }, error = function(e) {
        message("  [AUC] 模型<", m_name, ">数据集<", dataset_name, ">计算失败: ",
                conditionMessage(e))
        NA
      }, warning = function(w) {
        NA
      })
      AUC_mat[m_name, dataset_name] <- auc_val
    }
  }
  return(as.data.frame(AUC_mat))
}

# AUC_mat: AUC matrix.
# display_names: Optional character vector for column names.
# heatmap_colors: Color vector for heatmap gradient (low, mid, high).
# bar_colors: Color vector for right-side barplots (overall avg, testing avg).
# dataset_colors: Color vector for top cohort annotation.
# out_pdf: Output PDF path.
Plot.Class.Heatmap <- function(AUC_mat, 
                               display_names = NULL, 
                               heatmap_colors = c("#4195C1", "#FFFFFF", "#CB5746"),
                               bar_colors = c("steelblue", "#79ae96"),
                               dataset_colors = NULL,
                               out_pdf = NULL) {
  
  library(ComplexHeatmap)
  library(RColorBrewer)

  # 防御：AUC_mat 为 NULL/空时给出清晰报错，避免 setdiff(1:ncol()) 抛"argument of length 0"
  if (is.null(AUC_mat)) stop("AUC_mat 为空(NULL)，无法绘制热图。")
  ncol_auc <- ncol(AUC_mat)
  if (is.null(ncol_auc) || ncol_auc == 0) {
    stop("AUC_mat 没有任何数据集列（ncol=0），无法绘制热图。\n可能是所有模型在该数据集上预测/roc 都失败，或 list_train_vali_Data 为空。")
  }
  if (is.null(rownames(AUC_mat)) || nrow(AUC_mat) == 0) {
    stop("AUC_mat 没有模型行，无法绘制热图。")
  }

  if (!is.null(display_names)) {
    if (length(display_names) == ncol(AUC_mat)) {
      colnames(AUC_mat) <- display_names
    } else {
      stop("Length of display_names must match the number of datasets in AUC_mat.")
    }
  }
  
  # 先识别Test列（避免TCGA出现在Test名称中被误判为Train）
  test_pattern <- "Test|Validation|Valid|Vali"
  test_idx <- grep(test_pattern, colnames(AUC_mat), ignore.case = TRUE)
  if (length(test_idx) == 0) {
    # 无明确Test标记时，第一列为Train，其余为Test
    train_idx <- 1
    test_idx <- setdiff(1:ncol(AUC_mat), train_idx)
  } else {
    train_idx <- setdiff(1:ncol(AUC_mat), test_idx)
  }
  
  ## 仅训练（单列 / 无 Test 列）兼容：
  ## 参考脚本为 Train+Test 双列热图；本项目目前仅训练（单列）。为保持参考热图的外观
  ## （含右侧 Overall_Avg / Testing_Avg 双 barplot），单列时将 Testing 显示为 Training 值，
  ## 但**绝不重复列**（重复列会触发 columnAnnotation 因子水平重复报错）。
  single_col <- (ncol(AUC_mat) == 1)
  if (length(test_idx) == 0) {
    test_idx <- integer(0)
  }
  if (length(test_idx) == length(unique(test_idx)) &&
      length(c(train_idx, test_idx)) == ncol(AUC_mat)) {
    sorted_cols <- colnames(AUC_mat)[c(train_idx, test_idx)]
  } else {
    sorted_cols <- colnames(AUC_mat)
  }
  AUC_mat <- AUC_mat[, sorted_cols, drop = FALSE]
  # 更新索引：排序后 train/test 在矩阵中的绝对位置可能变化，改为按列名定位
  train_idx <- which(colnames(AUC_mat) %in% colnames(AUC_mat)[train_idx])
  test_idx  <- which(colnames(AUC_mat) %in% colnames(AUC_mat)[test_idx])
  
  avg_AUC_unsorted <- apply(AUC_mat, 1, mean, na.rm = TRUE)
  sort_names <- names(sort(avg_AUC_unsorted, decreasing = TRUE))
  AUC_mat <- AUC_mat[sort_names, , drop = FALSE]
  
  avg_AUC <- apply(AUC_mat, 1, mean, na.rm = TRUE)
  if (length(test_idx) > 0) {
    test_avg_AUC <- apply(AUC_mat[, test_idx, drop = FALSE], 1, mean, na.rm = TRUE)
  } else {
    # 仅训练时 Testing_Avg 展示 Training 平均值，保持热图双 barplot 参考外观
    test_avg_AUC <- avg_AUC
  }
  
  avg_AUC_format <- as.numeric(format(avg_AUC, digits = 3, nsmall = 3))
  test_avg_AUC_format <- as.numeric(format(test_avg_AUC, digits = 3, nsmall = 3))
  
  if(is.null(dataset_colors)) {
    CohortCol <- brewer.pal(n = max(3, ncol(AUC_mat)), name = "Paired")[1:ncol(AUC_mat)]
  } else {
    CohortCol <- dataset_colors[1:ncol(AUC_mat)]
  }
  names(CohortCol) <- colnames(AUC_mat)
  
  cellwidth = 1; cellheight = 0.5
  
  col_ha = columnAnnotation(
    "Cohort" = factor(colnames(AUC_mat), levels = sorted_cols), 
    col = list("Cohort" = CohortCol), 
    show_annotation_name = FALSE
  )
  
  row_ha = rowAnnotation(
    "Overall_Avg" = anno_barplot(avg_AUC_format, bar_width = 0.8, border = FALSE,
                                 gp = gpar(fill = bar_colors[1], col = NA),
                                 add_numbers = TRUE, numbers_offset = unit(-10, "mm"),
                                 axis_param = list("labels_rot" = 0),
                                 numbers_gp = gpar(fontsize = 9, col = "white"),
                                 width = unit(3, "cm")),
    
    "Testing_Avg" = anno_barplot(test_avg_AUC_format, bar_width = 0.8, border = FALSE,
                                 gp = gpar(fill = bar_colors[2], col = NA),
                                 add_numbers = TRUE, numbers_offset = unit(-10, "mm"),
                                 axis_param = list("labels_rot" = 0),
                                 numbers_gp = gpar(fontsize = 9, col = "white"),
                                 width = unit(3, "cm")),
    
    show_annotation_name = TRUE,
    annotation_name_gp = gpar(fontsize = 10, fontface = "bold")
  )
  
  hm <- Heatmap(as.matrix(AUC_mat), name = "AUC",
                right_annotation = row_ha, top_annotation = col_ha,
                col = heatmap_colors, rect_gp = gpar(col = "black", lwd = 1), 
                cluster_columns = FALSE, cluster_rows = FALSE, 
                show_column_names = FALSE, show_row_names = TRUE, row_names_side = "left",
                width = unit(cellwidth * ncol(AUC_mat) + 2, "cm"),
                height = unit(cellheight * nrow(AUC_mat), "cm"),
                cell_fun = function(j, i, x, y, w, h, col) { 
                  grid.text(label = format(AUC_mat[i, j], digits = 3, nsmall = 3), x, y, gp = gpar(fontsize = 10))
                }
  )
  
  bar_legend = Legend(labels = c("Overall Average", "Testing Average"),
                      title = "Average Types",
                      legend_gp = gpar(fill = bar_colors))
  
  if (!is.null(out_pdf)) {
    pdf(out_pdf, width = cellwidth * ncol(AUC_mat) + 9, height = cellheight * nrow(AUC_mat) * 0.45)
    draw(hm, annotation_legend_list = list(bar_legend))
    invisible(dev.off())
    cat("Heatmap saved to:", out_pdf, "\n")
  }
  
  drawn_hm <- draw(hm, annotation_legend_list = list(bar_legend))
  return(invisible(drawn_hm))
}