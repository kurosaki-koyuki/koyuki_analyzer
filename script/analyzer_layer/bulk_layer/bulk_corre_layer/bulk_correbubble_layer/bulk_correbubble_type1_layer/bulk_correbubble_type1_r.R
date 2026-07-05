# bulk相关性气泡图（椭圆） R绘图代码
# 该代码用于绘制基因之间的相关性椭圆图（下三角显示）
# 使用 ggcorrplot2 包绘制，椭圆形状和颜色表示相关性
# 参考风格：下三角椭圆图 + 显著性星号标记
# 
# 全局参数变量（由Python传入）:
#   exprSet         - 表达矩阵 (data.frame)
#   plot_title      - 图表标题 (character)
#   title_size      - 标题字体大小 (integer)
#   axis_text_size  - 坐标轴文字大小 (integer)
#   width_ratio     - 宽度比例 (numeric, 0-1)
#   height_ratio    - 高度比例 (numeric, 0-1)
#   show_sig        - 是否显示显著性 (logical)
#   anno_size       - 注释大小/pch.cex (numeric)
#   legend_key_width  - 图例键宽度 (numeric)
#   legend_key_height - 图例键高度 (numeric)
#   output_path     - 输出路径 (character)
#
# 依赖的R包: ggplot2, ggcorrplot2, psych
#
# --- FUNCTION_BODY_START ---

library(ggplot2)
library(ggcorrplot2)
library(psych)

# 计算相关性矩阵
cor_value <- cor(exprSet, use = "pairwise.complete.obs")

# 计算相关性P值矩阵
cor_test_result <- corr.test(exprSet, adjust = "BH")
cor_test_mat <- cor_test_result$p

# 确定显著性显示方式
if (show_sig) {
  insig_mode <- "label_sig"
  sig_levels <- c(0.05, 0.01, 0.001)
} else {
  insig_mode <- "blank"
  sig.levels <- NULL
}

# 绘制椭圆相关性图（下三角）
cor_pp1 <- ggcorrplot(cor_value, method = "ellipse", type = "lower",
                      p.mat = cor_test_mat,
                      col = c("#8aa3db", "white", "#fd9a9a"),
                      pch.cex = anno_size,
                      insig = insig_mode,
                      sig.lvl = if (show_sig) c(0.05, 0.01, 0.001) else NULL
) +
  guides(color = guide_legend(override.aes = list(size = 1))) + 
  theme(
    axis.text = element_text(size = axis_text_size),
    legend.key.width = unit(legend_key_width, "lines"),
    legend.key.height = unit(legend_key_height, "lines"),
    plot.title = element_text(size = title_size, hjust = 0.5)
  ) +
  ggtitle(plot_title)

# 保存图片
if (output_path != "") {
  ggsave(output_path, plot = cor_pp1, width = plot_width, height = plot_height, dpi = 300)
}

# --- FUNCTION_BODY_END ---
