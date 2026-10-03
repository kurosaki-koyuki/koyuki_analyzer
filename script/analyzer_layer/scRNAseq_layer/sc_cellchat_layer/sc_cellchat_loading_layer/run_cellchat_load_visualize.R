# -*- coding: utf-8 -*-
# CellChat数据加载类 - 从RDS文件重新出图
# 读取CellChat RDS对象，重新生成通讯数量图、通讯强度图和通路信息表
# 参数：
#   rds_path: CellChat RDS文件路径
#   output_dir: 输出目录
#   dataset_name: 数据集名称

suppressPackageStartupMessages({
  library(CellChat)
})

cellchat_visualize <- function(rds_path, output_dir, dataset_name) {
  cat("=== CellChat数据加载可视化 ===\n")
  
  # 读取CellChat对象
  cat(paste("读取CellChat对象:", rds_path, "\n"))
  cellchat <- readRDS(rds_path)
  cat(paste("读取完成\n"))
  
  # 创建输出目录
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  
  # 获取细胞类型分组大小
  groupSize <- as.numeric(table(cellchat@idents))
  cat(paste("细胞类型数:", length(groupSize), "\n"))
  
  # 图1：Number of interactions
  count_output <- file.path(output_dir, paste0(dataset_name, "_cellchat_count.png"))
  cat("绘制通讯数量图...\n")
  png(count_output, width = 1200, height = 1000, res = 150)
  netVisual_circle(cellchat@net$count, vertex.weight = groupSize,
                   weight.scale = TRUE, label.edge = FALSE, 
                   title.name = "Number of interactions")
  dev.off()
  cat(paste("通讯数量图已保存:", count_output, "\n"))
  
  # 图2：Interaction weights/strength
  weight_output <- file.path(output_dir, paste0(dataset_name, "_cellchat_weight.png"))
  cat("绘制通讯强度图...\n")
  png(weight_output, width = 1200, height = 1000, res = 150)
  netVisual_circle(cellchat@net$weight, vertex.weight = groupSize,
                   weight.scale = TRUE, label.edge = FALSE, 
                   title.name = "Interaction weights/strength")
  dev.off()
  cat(paste("通讯强度图已保存:", weight_output, "\n"))
  
  # 生成通路信息表
  cat("\n生成通路信息表...\n")
  info_file <- file.path(output_dir, "pathway_info.csv")
  
  tryCatch({
    # 检查netP结构
    if (!is.null(cellchat@netP) && !is.null(cellchat@netP$pathways)) {
      all_pathways <- cellchat@netP$pathways
      cat(paste("通路数量:", length(all_pathways), "\n"))
      
      # 获取pvalue和prob
      net_pval <- cellchat@net$pval
      net_prob <- cellchat@net$prob
      
      # 为每个通路计算pvalue和prob
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
      write.csv(pathway_info, info_file, row.names = FALSE, fileEncoding = "UTF-8")
      cat(paste("通路信息表已保存:", info_file, "\n"))
      cat(paste("通路数量:", nrow(pathway_info), "\n"))
    } else {
      cat("警告: netP或pathways为空，跳过通路信息表生成\n")
    }
  }, error = function(e) {
    cat(paste("警告: 生成通路信息表失败:", e$message, "\n"))
  })
  
  cat("\n=== 可视化完成 ===\n")
}

# 解析命令行参数
args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 3) {
  cat("参数不足\n")
  cat("用法: Rscript run_cellchat_load_visualize.R <rds_path> <output_dir> <dataset_name>\n")
  quit(status=1)
}

rds_path <- args[1]
output_dir <- args[2]
dataset_name <- args[3]

# 运行
cellchat_visualize(rds_path, output_dir, dataset_name)
