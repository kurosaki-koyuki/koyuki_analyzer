# bulk KM曲线 R模式绘图脚本
# 此文件包含所有R代码，用于通过rpy2调用R绘制KM曲线
# 
# 使用方式：
# Python端通过rpy2将参数设置到全局环境，然后提取标记行内的代码执行
# 参数直接从全局环境获取，不需要显式传递
# R包必须通过Python端的importr()预加载，禁止在脚本中使用library()

#' 绘制KM曲线
#' 
#' 参数列表（从全局环境获取）：
#' - survival_data: 生存数据框
#' - time_col: 时间列名
#' - event_col: 事件列名
#' - group_col: 分组列名
#' - gene_name: 基因名称
#' - output_path: 输出路径
#' - plot_title: 图表标题
#' - show_risk_table: 是否显示风险表格
#' - plot_width: 图表宽度
#' - plot_height: 图表高度
#' - pval_mode: p值显示模式 (0=具体值, 1=模糊值, 2=模糊值+具体值)
#' - title_font_size: 标题字体大小
#' - axis_font_size: 坐标轴字体大小
#' - legend_font_size: 图例字体大小
#' - pval_font_size: 显著性(p值)字体大小
#' - risk_table_font_size: 风险表格字体大小
#' - show_conf_int: 是否显示置信区间
#' - show_n: 是否显示n值
#' - show_global_pval: 是否显示总体p值
#' - show_pairwise: 是否显示组间比较
#' - selected_pairwise: 选中的组间比较列表

# --- FUNCTION_BODY_START ---

# === 参数获取 ===
df <- survival_data
time_col_name <- as.character(time_col)[1]
event_col_name <- as.character(event_col)[1]
group_col_name <- as.character(group_col)[1]
gene_name_val <- as.character(gene_name)[1]
output_path_val <- as.character(output_path)[1]
title_val <- as.character(plot_title)[1]
show_table <- as.logical(show_risk_table)[1]
width_val <- as.numeric(plot_width)[1]
height_val <- as.numeric(plot_height)[1]
pval_mode_val <- as.integer(pval_mode)[1]

# 字体大小参数
title_font_size_val <- as.integer(title_font_size)[1]
axis_font_size_val <- as.integer(axis_font_size)[1]
legend_font_size_val <- as.integer(legend_font_size)[1]
pval_font_size_val <- as.integer(pval_font_size)[1]
risk_table_font_size_val <- as.integer(risk_table_font_size)[1]

# 显示选项参数
show_conf_int_val <- as.logical(show_conf_int)[1]
show_n_val <- as.logical(show_n)[1]
show_global_pval_val <- as.logical(show_global_pval)[1]
show_pairwise_val <- as.logical(show_pairwise)[1]
selected_pairwise_val <- if(exists('selected_pairwise')) as.character(selected_pairwise) else character(0)

# === 参数验证 ===
if (!exists('df')) {
  stop("数据框 survival_data 不存在")
}

if (is.na(output_path_val) || output_path_val == "") {
  stop("输出路径 output_path 不能为空")
}

# === 准备数据 ===
# 重命名time/event列为简单名称，确保公式中所有变量从data=df一致解析
names(df)[names(df) == time_col_name] <- 'time_val'
names(df)[names(df) == event_col_name] <- 'event_val'

# 创建名为group的列，确保ggsurvplot能找到分组变量
df$group <- as.factor(df[[group_col_name]])

# === 创建生存对象并拟合生存曲线 ===
fit <- survfit(Surv(time_val, event_val) ~ group, data = df)

# === p值计算 ===
surv_diff <- survdiff(Surv(time_val, event_val) ~ group, data = df)
p_val <- 1 - pchisq(surv_diff$chisq, length(surv_diff$n) - 1)

# === p值显示模式（含科学计数法）===
pval_text <- if(p_val < 0.0001) {
  sprintf("p = %.1e", p_val)
} else if(pval_mode_val == 0) {
  sprintf("p = %.4f", p_val)
} else if(pval_mode_val == 1) {
  if(p_val < 0.001) {
    "p < 0.001"
  } else if(p_val < 0.01) {
    "p < 0.01"
  } else if(p_val < 0.05) {
    "p < 0.05"
  } else {
    "p >= 0.05"
  }
} else {
  if(p_val < 0.001) {
    sprintf("p < 0.001 (%.1e)", p_val)
  } else if(p_val < 0.01) {
    sprintf("p < 0.01 (%.4f)", p_val)
  } else if(p_val < 0.05) {
    sprintf("p < 0.05 (%.4f)", p_val)
  } else {
    sprintf("p >= 0.05 (%.4f)", p_val)
  }
}

# === 生成标题 ===
if(title_val != "" && !is.na(title_val) && title_val != "NA") {
  plot_title_final <- title_val
} else {
  plot_title_final <- paste0(gene_name_val, " KM Curve")
}

# === 设置颜色调色板 ===
n_groups <- length(levels(df$group))
if(n_groups == 2) {
  palette <- c("#E74C3C", "#3498DB")
} else {
  palette <- NULL
}

# === 设置主题 ===
plot_theme <- theme_survminer() + 
  theme(
    plot.title = element_text(hjust = 0.5, size = title_font_size_val, face = "bold"),
    axis.text = element_text(size = axis_font_size_val),
    axis.title = element_text(size = axis_font_size_val),
    legend.text = element_text(size = legend_font_size_val),
    legend.title = element_text(size = legend_font_size_val)
  )

# === 设置风险表格主题 ===
risk_table_theme <- theme_cleantable() +
  theme(
    axis.text.x = element_text(size = axis_font_size_val),
    axis.text.y = element_text(size = risk_table_font_size_val)
  )

# === 设置文件输出 ===
if(output_path_val != "" && !is.na(output_path_val) && output_path_val != "NA" && output_path_val != FALSE) {
  if(grepl("\\.png$", output_path_val, ignore.case = TRUE)) {
    png(output_path_val, width = width_val * 100, height = height_val * 100, res = 100)
  } else if(grepl("\\.pdf$", output_path_val, ignore.case = TRUE)) {
    pdf(output_path_val, width = width_val, height = height_val)
  } else if(grepl("\\.svg$", output_path_val, ignore.case = TRUE)) {
    svg(output_path_val, width = width_val, height = height_val)
  } else {
    png(output_path_val, width = width_val * 100, height = height_val * 100, res = 100)
  }
}

# === 绘制KM曲线 ===
ggsurv <- ggsurvplot(fit,
                     data = df,
                     risk.table = show_table,
                     risk.table.y.text.col = TRUE,
                     risk.table.y.text = FALSE,
                     risk.table.fontsize = risk_table_font_size_val,
                     tables.theme = risk_table_theme,
                     palette = palette,
                     surv.median.line = "hv",
                     conf.int = show_conf_int_val,
                     legend = "top",
                     legend.title = "Group",
                     ggtheme = plot_theme,
                     title = plot_title_final,
                     xlab = "Time",
                     ylab = "Survival probability",
                     
                     # p值显示控制
                     pval = if(show_global_pval_val) pval_text else FALSE,
                     pval.size = pval_font_size_val,
                     
                     # n值显示控制
                     ncensor.plot = FALSE,
                     legend.labs = if(show_n_val) levels(df$group) else gsub("\\s*\\(\\d+\\)", "", levels(df$group))
)

# === 组间比较 ===
if(show_pairwise_val && n_groups >= 2) {
  pairwise_comparisons <- pairwise_survdiff(Surv(time_val, event_val) ~ group, data = df)
  
  pw_results <- pairwise_comparisons$p.value
  group_levels <- levels(df$group)
  
  comparison_text <- character(0)
  
  clinical_groups <- unique(gsub("\\s+(High|Low)\\s*\\(\\d+\\)", "", group_levels))
  
  for(clinical_group in clinical_groups) {
    high_name <- paste0(clinical_group, " High")
    low_name <- paste0(clinical_group, " Low")
    
    high_idx <- which(grepl(paste0("^", clinical_group, " High"), group_levels))
    low_idx <- which(grepl(paste0("^", clinical_group, " Low"), group_levels))
    
    if(length(high_idx) > 0 && length(low_idx) > 0) {
      i <- min(high_idx, low_idx)
      j <- max(high_idx, low_idx)
      
      idx <- 0
      count <- 0
      for(x in 1:(length(group_levels)-1)) {
        for(y in (x+1):length(group_levels)) {
          count <- count + 1
          if(x == i && y == j) {
            idx <- count
            break
          }
        }
        if(idx > 0) break
      }
      
      if(idx > 0 && idx <= length(pw_results)) {
        p_val <- pw_results[idx]
        display_label <- clinical_group
        filter_label <- paste(gsub("\\s*\\(\\d+\\)", "", group_levels[i]), "vs", gsub("\\s*\\(\\d+\\)", "", group_levels[j]))
        
        if(!is.na(p_val)) {
          if(length(selected_pairwise_val) > 0 && !filter_label %in% selected_pairwise_val) {
            next
          }
          
          p_formatted <- if(p_val < 0.001) sprintf("%.3e", p_val) else sprintf("%.3f", p_val)
          comparison_text <- c(comparison_text, paste0(display_label, ": p=", p_formatted))
        }
      }
    }
  }
  
  if(length(comparison_text) > 0) {
    ggsurv$plot <- ggsurv$plot + 
      annotate("text", x = max(df$time_val) * 0.8, y = 0.1, 
               label = paste(comparison_text, collapse = "\n"),
               size = pval_font_size_val / 3)
  }
}

# === 打印图表 ===
if(show_table) {
  combined_plot <- cowplot::plot_grid(ggsurv$plot, ggsurv$table, ncol = 1, rel_heights = c(3, 1))
  print(combined_plot)
} else {
  print(ggsurv$plot)
}

# === 关闭设备 ===
if(output_path_val != "" && !is.na(output_path_val) && output_path_val != "NA" && output_path_val != FALSE) {
  dev.off()
}

# --- FUNCTION_BODY_END ---