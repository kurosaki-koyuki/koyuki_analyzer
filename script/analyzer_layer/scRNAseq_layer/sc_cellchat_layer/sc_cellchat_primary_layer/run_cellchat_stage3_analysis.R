# -*- coding: utf-8 -*-
# CellChat初步分析 - 阶段三：CellChat通讯分析
# 整合步骤2-7：创建CellChat对象到可视化通讯网络
# 参数：
#   seurat_path: Seurat对象的rds文件路径
#   main_annot: 主注释列
#   celltypes: 要保留的细胞类型（逗号分隔，可为空）
#   db_type: 数据库类型（human/mouse）
#   db_search: 数据库筛选类别
#   mean_method: 均值计算方法（triMean/mean/median）
#   min_cells: 最少细胞数过滤
#   raw_use: 是否使用原始数据（TRUE/FALSE）
#   output_dir: 输出目录
#   count_output: 通讯数量图输出路径
#   weight_output: 通讯强度图输出路径

cellchat_analysis <- function(seurat_path, main_annot, celltypes = "", 
                              db_type = "human", db_search = "全部",
                              mean_method = "triMean", min_cells = 10, 
                              raw_use = TRUE, output_dir = ".",
                              count_output = "cellchat_count.png", 
                              weight_output = "cellchat_weight.png") {
  
  library(CellChat)
  library(Seurat)
  library(patchwork)
  
  cat("=== CellChat通讯分析 ===\n")
  
  # ============================================================
  # 步骤2：创建cellchat对象
  # ============================================================
  cat("\n步骤2：创建CellChat对象\n")
  
  # 读取Seurat对象
  seurat_obj <- readRDS(seurat_path)
  cat(paste("读取Seurat对象完成:", ncol(seurat_obj), "细胞,", nrow(seurat_obj), "基因\n"))
  
  # 获取表达数据
  data.input <- GetAssayData(seurat_obj, layer = 'data')
  
  # 获取元数据
  meta <- seurat_obj@meta.data
  if (!main_annot %in% colnames(meta)) {
    cat(paste("ERROR: 主注释列", main_annot, "不存在\n"))
    quit(status=1)
  }
  
  # 构建CellChat所需的元数据
  meta_cellchat <- data.frame(
    group = meta$orig.ident,
    celltypes = meta[[main_annot]],
    row.names = rownames(meta)
  )
  
  # 处理细胞类型名称
  meta_cellchat$celltypes <- gsub(" cells|-cells", "", meta_cellchat$celltypes)
  
  # 如果有指定细胞类型，进行筛选
  if (nchar(celltypes) > 0) {
    celltype_list <- strsplit(celltypes, ",")[[1]]
    selected_cells <- rownames(meta_cellchat)[meta_cellchat$celltypes %in% celltype_list]
    cat(paste("筛选细胞类型:", paste(celltype_list, collapse=", "), "\n"))
    cat(paste("筛选后细胞数:", length(selected_cells), "\n"))
    
    data.input <- data.input[, selected_cells]
    meta_cellchat <- meta_cellchat[selected_cells, ]
  }
  
  # 对细胞类型进行排序
  celltype_order <- sort(unique(meta_cellchat$celltypes))
  meta_cellchat$celltypes <- factor(meta_cellchat$celltypes, levels = celltype_order)
  ordered_indices <- order(meta_cellchat$celltypes)
  meta_cellchat <- meta_cellchat[ordered_indices, ]
  data.input <- data.input[, ordered_indices]
  
  cat(paste("最终细胞数:", ncol(data.input), "\n"))
  
  # 创建CellChat对象
  cellchat <- createCellChat(object = data.input, meta = meta_cellchat, group.by = "celltypes")
  cat("CellChat对象创建完成\n")
  
  # ============================================================
  # 步骤3：设置配体-受体相互作用数据库
  # ============================================================
  cat("\n步骤3：设置数据库\n")
  
  # 选择数据库
  if (db_type == "human") {
    CellChatDB <- CellChatDB.human
  } else {
    CellChatDB <- CellChatDB.mouse
  }
  
  # 筛选数据库类别
  if (db_search != "全部") {
    CellChatDB.use <- subsetDB(CellChatDB, search = db_search, key = "annotation")
  } else {
    CellChatDB.use <- CellChatDB
  }
  
  cellchat@DB <- CellChatDB.use
  cat(paste("使用数据库:", db_type, "-", db_search, "(", nrow(CellChatDB.use$interaction), "个互作)\n"))
  
  # ============================================================
  # 步骤4：预处理表达数据
  # ============================================================
  cat("\n步骤4：预处理表达数据\n")
  
  cellchat <- subsetData(cellchat)
  cat("subsetData完成\n")
  
  cellchat <- identifyOverExpressedGenes(cellchat)
  cat("identifyOverExpressedGenes完成\n")
  
  cellchat <- identifyOverExpressedInteractions(cellchat)
  cat("identifyOverExpressedInteractions完成\n")
  
  # ============================================================
  # 步骤5：预测细胞-细胞通信网络
  # ============================================================
  cat("\n步骤5：预测通信网络\n")
  
  cellchat <- computeCommunProb(cellchat, type = mean_method, raw.use = raw_use)
  cat(paste("computeCommunProb完成 (方法:", mean_method, ")\n"))
  
  cellchat <- filterCommunication(cellchat, min.cells = min_cells)
  cat(paste("filterCommunication完成 (min.cells:", min_cells, ")\n"))
  
  # ============================================================
  # 步骤6：通路水平推断
  # ============================================================
  cat("\n步骤6：通路水平推断\n")
  
  cellchat <- computeCommunProbPathway(cellchat)
  cat("computeCommunProbPathway完成\n")
  
  cellchat <- aggregateNet(cellchat)
  cat("aggregateNet完成\n")
  
  # ============================================================
  # 步骤7：可视化通讯网络
  # ============================================================
  cat("\n步骤7：可视化通讯网络\n")
  
  # 创建输出目录
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  
  groupSize <- as.numeric(table(cellchat@idents))
  cat(paste("细胞类型数:", length(groupSize), "\n"))
  
  # 图1：Number of interactions
  cat("绘制通讯数量图...\n")
  png(count_output, width = 1200, height = 1000, res = 150)
  netVisual_circle(cellchat@net$count, vertex.weight = groupSize,
                   weight.scale = TRUE, label.edge = FALSE, 
                   title.name = "Number of interactions")
  dev.off()
  cat(paste("通讯数量图已保存:", count_output, "\n"))
  
  # 图2：Interaction weights/strength
  cat("绘制通讯强度图...\n")
  png(weight_output, width = 1200, height = 1000, res = 150)
  netVisual_circle(cellchat@net$weight, vertex.weight = groupSize,
                   weight.scale = TRUE, label.edge = FALSE, 
                   title.name = "Interaction weights/strength")
  dev.off()
  cat(paste("通讯强度图已保存:", weight_output, "\n"))
  
  # 保存CellChat对象
  cellchat_save_path <- file.path(output_dir, paste0(dataset_name, "_cellchat.rds"))
  saveRDS(cellchat, cellchat_save_path)
  cat(paste("CellChat对象已保存:", cellchat_save_path, "\n"))
  
  # 生成通路信息表
  cat("\n生成通路信息表...\n")
  tryCatch({
    # 检查netP结构
    cat(paste("netP结构:", paste(names(cellchat@netP), collapse=", "), "\n"))
    cat(paste("net结构:", paste(names(cellchat@net), collapse=", "), "\n"))
    
    # 获取通路名
    if (!is.null(cellchat@netP) && !is.null(cellchat@netP$pathways)) {
      all_pathways <- cellchat@netP$pathways
      cat(paste("通路数量:", length(all_pathways), "\n"))
      
      # 获取pvalue和prob
      # netP$prob可能是向量或矩阵，net$pval和net$prob是三维数组
      netP_prob <- cellchat@netP$prob
      net_pval <- cellchat@net$pval
      net_prob <- cellchat@net$prob
      
      cat(paste("netP$prob长度:", length(netP_prob), "\n"))
      cat(paste("net$pval维度:", paste(dim(net_pval), collapse=" x "), "\n"))
      cat(paste("net$prob维度:", paste(dim(net_prob), collapse=" x "), "\n"))
      
      # 为每个通路计算pvalue和prob
      # net是三维数组：[sender, receiver, pathway]
      # 我们需要对每个通路，取所有sender-receiver对中的最小值pvalue和最大值prob
      pathway_pvalues <- sapply(seq_along(all_pathways), function(i) {
        if (i <= dim(net_pval)[3]) {
          vals <- as.numeric(net_pval[, , i])
          vals <- vals[!is.na(vals) & vals > 0]
          if (length(vals) > 0) min(vals) else NA
        } else {
          NA
        }
      })
      
      pathway_probs <- sapply(seq_along(all_pathways), function(i) {
        if (i <= dim(net_prob)[3]) {
          vals <- as.numeric(net_prob[, , i])
          vals <- vals[!is.na(vals)]
          if (length(vals) > 0) max(vals) else NA
        } else {
          NA
        }
      })
      
      # 创建通路信息数据框
      pathway_info <- data.frame(
        pathway = all_pathways,
        pvalue = pathway_pvalues,
        prob = pathway_probs,
        stringsAsFactors = FALSE
      )
      pathway_info$pvalue <- format(pathway_info$pvalue, digits = 4, scientific = TRUE)
      pathway_info$prob <- round(pathway_info$prob, 4)
      
      # 保存为CSV
      info_file <- file.path(output_dir, "pathway_info.csv")
      write.csv(pathway_info, info_file, row.names = FALSE, fileEncoding = "UTF-8")
      cat(paste("通路信息表已保存:", info_file, "\n"))
      cat(paste("通路数量:", nrow(pathway_info), "\n"))
    } else {
      cat("警告: netP或pathways为空，跳过通路信息表生成\n")
    }
  }, error = function(e) {
    cat(paste("警告: 生成通路信息表失败:", e$message, "\n"))
  })
  
  cat("\n=== CellChat分析完成 ===\n")
}

# 解析命令行参数
args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 9) {
  seurat_path <- args[1]
  main_annot <- args[2]
  celltypes <- args[3]
  db_type <- args[4]
  db_search <- args[5]
  mean_method <- args[6]
  min_cells <- as.integer(args[7])
  raw_use <- as.logical(args[8])
  output_dir <- args[9]
  count_output <- if (length(args) >= 10) args[10] else file.path(output_dir, "cellchat_count.png")
  weight_output <- if (length(args) >= 11) args[11] else file.path(output_dir, "cellchat_weight.png")
  dataset_name <- if (length(args) >= 12) args[12] else "cellchat"
  
  tryCatch({
    cellchat_analysis(seurat_path, main_annot, celltypes, db_type, db_search,
                      mean_method, min_cells, raw_use, output_dir,
                      count_output, weight_output)
  }, error = function(e) {
    cat(paste("ERROR:", e$message, "\n"))
    quit(status=1)
  })
} else {
  cat("用法: Rscript run_cellchat_stage3_analysis.R <seurat_path> <main_annot> <celltypes> <db_type> <db_search> <mean_method> <min_cells> <raw_use> <output_dir> [count_output] [weight_output] [dataset_name]\n")
}
