# -*- coding: utf-8 -*-
# CellChat初步分析 - 阶段四：细分亚组的circle图
# 参数：
#   所有参数打包成一个字符串，用分号分隔
#   格式: cellchat_rds_path;subgroups;output_path

subgroup_circle_plot <- function(params_str) {
  
  suppressPackageStartupMessages({
    library(CellChat)
  })
  
  cat("=== 细分亚组circle图 ===\n")
  
  # 解析参数（分号分隔）
  params <- strsplit(params_str, ";")[[1]]
  cellchat_rds_path <- params[1]
  subgroups <- if (length(params) >= 2) params[2] else "__ALL__"
  output_path <- if (length(params) >= 3) params[3] else "subgroup_circle.png"
  
  cat(paste("参数数量:", length(params), "\n"))
  cat(paste("cellchat_rds_path:", cellchat_rds_path, "\n"))
  cat(paste("subgroups:", subgroups, "\n"))
  cat(paste("output_path:", output_path, "\n"))
  
  # 读取CellChat对象
  if (!file.exists(cellchat_rds_path)) {
    cat(paste("ERROR: CellChat RDS文件不存在\n"))
    quit(status=1)
  }
  
  cellchat <- readRDS(cellchat_rds_path)
  cat("读取CellChat对象完成\n")
  
  # 获取权重矩阵
  if (!is.null(cellchat@net) && !is.null(cellchat@net$weight)) {
    mat <- cellchat@net$weight
    cat(paste("权重矩阵维度:", nrow(mat), "x", ncol(mat), "\n"))
    cat(paste("细胞类型:", paste(rownames(mat), collapse=", "), "\n"))
  } else {
    cat("ERROR: CellChat对象中没有net$weight数据\n")
    quit(status=1)
  }
  
  # 获取细胞组大小
  if (!is.null(cellchat@idents)) {
    groupSize <- as.numeric(table(cellchat@idents))
  } else {
    groupSize <- rep(1, nrow(mat))
    names(groupSize) <- rownames(mat)
  }
  
  # 确定要显示的亚组
  if (nchar(subgroups) > 0 && subgroups != "__ALL__") {
    subgroup_list <- strsplit(subgroups, ",")[[1]]
    valid_subgroups <- subgroup_list[subgroup_list %in% rownames(mat)]
    if (length(valid_subgroups) == 0) {
      cat("ERROR: 没有有效的亚组\n")
      quit(status=1)
    }
    cat(paste("显示亚组:", paste(valid_subgroups, collapse=", "), "\n"))
  } else {
    valid_subgroups <- rownames(mat)
    cat("显示所有亚组\n")
  }
  
  # 计算布局
  n_subgroups <- length(valid_subgroups)
  n_cols <- min(3, n_subgroups)
  n_rows <- ceiling(n_subgroups / n_cols)
  cat(paste("布局:", n_rows, "x", n_cols, "=", n_subgroups, "个亚组\n"))
  
  # 创建输出目录
  output_dir <- dirname(output_path)
  if (nchar(output_dir) > 0) {
    dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  }
  
  # 绘图（提高分辨率到200）
  cat(paste("保存图片到:", output_path, "\n"))
  png(output_path, width = 500 * n_cols, height = 450 * n_rows, res = 200)
  par(mfrow = c(n_rows, n_cols), xpd = TRUE, mar = c(3, 2, 4, 2))
  
  for (subgroup in valid_subgroups) {
    cat(paste("绘制亚组:", subgroup, "\n"))
    mat2 <- matrix(0, nrow = nrow(mat), ncol = ncol(mat), dimnames = dimnames(mat))
    mat2[subgroup, ] <- mat[subgroup, ]
    
    tryCatch({
      # 先绘制circle图
      netVisual_circle(mat2, vertex.weight = groupSize,
                       weight.scale = TRUE, label.edge = FALSE,
                       title.name = "")
      # 添加更大的标题
      title(subgroup, line = 2.5, cex.main = 1.5)
    }, error = function(e) {
      cat(paste("  警告: 绘制", subgroup, "失败:", e$message, "\n"))
      plot(1, 1, type = "n", xlab = "", ylab = "", axes = FALSE)
      text(1, 1, paste(subgroup, "\n(绘图失败)"), cex = 1.5)
    })
  }
  
  dev.off()
  cat(paste("细分亚组circle图已保存:", output_path, "\n"))
  cat("=== 细分亚组circle图完成 ===\n")
}

# 解析命令行参数
args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 1) {
  params_str <- args[1]
  
  tryCatch({
    subgroup_circle_plot(params_str)
  }, error = function(e) {
    cat(paste("ERROR:", e$message, "\n"))
    quit(status=1)
  })
} else {
  cat("用法: Rscript run_cellchat_stage4_subgroup.R <params_str>\n")
  cat("params_str格式: cellchat_rds_path;subgroups;output_path\n")
}
