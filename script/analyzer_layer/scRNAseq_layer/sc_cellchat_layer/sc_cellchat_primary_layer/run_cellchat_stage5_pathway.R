# -*- coding: utf-8 -*-
# CellChat初步分析 - 阶段五：信号通路可视化
# 参数（打包成一个字符串，分号分隔）：
#   cellchat_rds_path;pathways;pval_threshold;pathway_count;viz_types;output_dir
#   - pathways: 信号通路（逗号分隔），__AUTO__表示自动选择
#   - pval_threshold: p值阈值（自动模式用）
#   - pathway_count: 选择数量（自动模式用）
#   - viz_types: 可视化类型（hierarchy,circle,chord,heatmap），逗号分隔

pathway_visualization <- function(params_str) {
  
  suppressPackageStartupMessages({
    library(CellChat)
    library(patchwork)
    library(ggplot2)
  })
  
  cat("=== 信号通路可视化 ===\n")
  
  # 解析参数（分号分隔）
  params <- strsplit(params_str, ";")[[1]]
  cellchat_rds_path <- params[1]
  pathways_param <- if (length(params) >= 2) params[2] else "__AUTO__"
  pval_threshold <- if (length(params) >= 3) as.numeric(params[3]) else 0.05
  pathway_count <- if (length(params) >= 4) as.numeric(params[4]) else 5
  viz_types <- if (length(params) >= 5) params[5] else "hierarchy,circle,chord,heatmap"
  output_dir <- if (length(params) >= 6) params[6] else "."
  
  cat(paste("参数数量:", length(params), "\n"))
  cat(paste("cellchat_rds_path:", cellchat_rds_path, "\n"))
  cat(paste("pathways:", pathways_param, "\n"))
  cat(paste("pval_threshold:", pval_threshold, "\n"))
  cat(paste("pathway_count:", pathway_count, "\n"))
  cat(paste("viz_types:", viz_types, "\n"))
  cat(paste("output_dir:", output_dir, "\n"))
  
  # 读取CellChat对象
  if (!file.exists(cellchat_rds_path)) {
    cat("ERROR: CellChat RDS文件不存在\n")
    quit(status=1)
  }
  
  cellchat <- readRDS(cellchat_rds_path)
  cat("读取CellChat对象完成\n")
  
  # 获取可用通路
  all_pathways <- cellchat@netP$pathways
  cat(paste("可用通路数量:", length(all_pathways), "\n"))
  
  # 确定要显示的通路
  if (pathways_param == "__AUTO__") {
    # 自动模式：按通信强度排序选择前N个通路
    cat(paste("自动模式: 按pvalue<", pval_threshold, "筛选前", pathway_count, "个通路\n"))
    
    # 获取每个通路的pvalue
    path_pvalues <- cellchat@netP$pvalue
    path_probs <- cellchat@netP$prob
    
    # 筛选显著通路
    sig_pathways <- names(which(path_pvalues < pval_threshold))
    cat(paste("显著通路数量:", length(sig_pathways), "\n"))
    
    if (length(sig_pathways) > 0) {
      # 按通信强度排序
      sig_probs <- path_probs[sig_pathways]
      sorted_idx <- order(sig_probs, decreasing = TRUE)
      selected_pathways <- sig_pathways[sorted_idx][1:min(pathway_count, length(sig_pathways))]
    } else {
      # 如果没有显著通路，选择通信强度最高的
      cat("没有显著通路，选择通信强度最高的\n")
      sorted_idx <- order(path_probs, decreasing = TRUE)
      selected_pathways <- all_pathways[sorted_idx][1:min(pathway_count, length(all_pathways))]
    }
    
    cat(paste("自动选择通路:", paste(selected_pathways, collapse=", "), "\n"))
  } else {
    # 手动模式：直接使用指定的通路
    selected_pathways <- strsplit(pathways_param, ",")[[1]]
    # 过滤掉不存在的通路
    valid_pathways <- selected_pathways[selected_pathways %in% all_pathways]
    if (length(valid_pathways) == 0) {
      cat("ERROR: 没有有效的通路\n")
      cat(paste("可用通路:", paste(all_pathways, collapse=", "), "\n"))
      quit(status=1)
    }
    selected_pathways <- valid_pathways
    cat(paste("手动选择通路:", paste(selected_pathways, collapse=", "), "\n"))
  }
  
  # 解析可视化类型
  viz_list <- strsplit(viz_types, ",")[[1]]
  
  # 创建输出目录
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  
  # 获取细胞类型列表
  cell_types <- levels(cellchat@idents)
  cat(paste("细胞类型:", paste(cell_types, collapse=", "), "\n"))
  
  # 设置vertex.receiver（用于层次结构图）
  n_celltypes <- length(cell_types)
  vertex.receiver <- seq(1, min(3, n_celltypes))
  
  # === 生成通路信息表格 ===
  cat("\n生成通路信息表格...\n")
  path_pvalues <- cellchat@netP$pvalue
  path_probs <- cellchat@netP$prob
  
  # 创建通路信息数据框
  pathway_info <- data.frame(
    pathway = selected_pathways,
    pvalue = as.numeric(path_pvalues[selected_pathways]),
    prob = as.numeric(path_probs[selected_pathways]),
    stringsAsFactors = FALSE
  )
  pathway_info$pvalue <- format(pathway_info$pvalue, digits = 4, scientific = TRUE)
  pathway_info$prob <- round(pathway_info$prob, 4)
  
  # 保存为CSV
  info_file <- file.path(output_dir, "pathway_info.csv")
  write.csv(pathway_info, info_file, row.names = FALSE, fileEncoding = "UTF-8")
  cat(paste("通路信息表格已保存:", basename(info_file), "\n"))
  print(pathway_info)
  
  # === 为多个通路生成组合图 ===
  
  # 计算布局参数
  n_pathways <- length(selected_pathways)
  
  if ("hierarchy" %in% viz_list) {
    cat("\n绘制层次结构图（组合展示）...\n")
    tryCatch({
      output_file <- file.path(output_dir, "hierarchy_combined.png")
      # 根据通路数量设置合适的绘图区域
      png(output_file, width = max(800, 400 * n_pathways), height = 1200, res = 150)
      par(mfrow = c(ceiling(n_pathways/2), min(2, n_pathways)), 
          mar = c(4, 4, 6, 2) + 0.1,
          cex.main = 1.2, cex.axis = 0.8, cex.lab = 0.9)
      
      for (i in seq_along(selected_pathways)) {
        pathway <- selected_pathways[i]
        cat(paste("  绘制通路:", pathway, "\n"))
        netVisual_aggregate(cellchat, signaling = pathway,
                            vertex.receiver = vertex.receiver, layout = "hierarchy",
                            title.name = pathway)
      }
      dev.off()
      cat(paste("  层次结构图已保存:", basename(output_file), "\n"))
    }, error = function(e) {
      cat(paste("  警告: 层次结构图绘制失败:", e$message, "\n"))
    })
  }
  
  if ("circle" %in% viz_list) {
    cat("\n绘制circle图（组合展示）...\n")
    tryCatch({
      output_file <- file.path(output_dir, "circle_combined.png")
      png(output_file, width = max(800, 400 * n_pathways), height = 1200, res = 150)
      par(mfrow = c(ceiling(n_pathways/2), min(2, n_pathways)),
          mar = c(4, 4, 6, 2) + 0.1,
          cex.main = 1.2)
      
      for (i in seq_along(selected_pathways)) {
        pathway <- selected_pathways[i]
        cat(paste("  绘制通路:", pathway, "\n"))
        netVisual_aggregate(cellchat, signaling = pathway, layout = "circle",
                            title.name = pathway)
      }
      dev.off()
      cat(paste("  circle图已保存:", basename(output_file), "\n"))
    }, error = function(e) {
      cat(paste("  警告: circle图绘制失败:", e$message, "\n"))
    })
  }
  
  if ("chord" %in% viz_list) {
    cat("\n绘制弦图（组合展示）...\n")
    tryCatch({
      output_file <- file.path(output_dir, "chord_combined.png")
      png(output_file, width = max(1000, 500 * n_pathways), height = 1200, res = 150)
      par(mfrow = c(ceiling(n_pathways/2), min(2, n_pathways)),
          mar = c(4, 4, 6, 2) + 0.1,
          cex.main = 1.2)
      
      for (i in seq_along(selected_pathways)) {
        pathway <- selected_pathways[i]
        cat(paste("  绘制通路:", pathway, "\n"))
        # 弦图使用netVisual_aggregate的chord布局，设置合适的参数
        netVisual_aggregate(cellchat, signaling = pathway, layout = "chord",
                            title.name = pathway)
      }
      dev.off()
      cat(paste("  弦图已保存:", basename(output_file), "\n"))
    }, error = function(e) {
      cat(paste("  警告: 弦图绘制失败:", e$message, "\n"))
    })
  }
  
  if ("heatmap" %in% viz_list) {
    cat("\n绘制热图（组合展示）...\n")
    tryCatch({
      output_file <- file.path(output_dir, "heatmap_combined.png")
      png(output_file, width = max(800, 400 * n_pathways), height = 1200, res = 150)
      par(mfrow = c(ceiling(n_pathways/2), min(2, n_pathways)),
          mar = c(6, 8, 6, 2) + 0.1,
          cex.main = 1.2, cex.axis = 0.7)
      
      for (i in seq_along(selected_pathways)) {
        pathway <- selected_pathways[i]
        cat(paste("  绘制通路:", pathway, "\n"))
        # 使用netVisual_heatmap绘制热图
        netVisual_heatmap(cellchat, signaling = pathway, 
                          color.heatmap = "Reds",
                          title.name = pathway)
      }
      dev.off()
      cat(paste("  热图已保存:", basename(output_file), "\n"))
    }, error = function(e) {
      cat(paste("  警告: 热图绘制失败:", e$message, "\n"))
    })
  }
  
  cat("\n=== 信号通路可视化完成 ===\n")
}

# 解析命令行参数
args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 1) {
  params_str <- args[1]
  
  tryCatch({
    pathway_visualization(params_str)
  }, error = function(e) {
    cat(paste("ERROR:", e$message, "\n"))
    quit(status=1)
  })
} else {
  cat("用法: Rscript run_cellchat_stage5_pathway.R <params_str>\n")
  cat("params_str格式: cellchat_rds_path;pathways;pval_threshold;pathway_count;viz_types;output_dir\n")
}
