##############箱线图

mycolor <- c("#45739e","#d38641","#518d6b","#b34644")




p1 <- ggboxplot(df1_m, x = "variable", y = "value", 
                fill = "variable", # 箱线图填充色
                alpha = 0.3, # 箱线图填充色透明度
                color = "variable",  # 设置箱线图的边框颜色
                palette = mycolor,
                add = "jitter",  # 添加散点
                jitter = list(width = 0.2, size = 1, alpha = 0.6),
                size = 1.2,  # 设置箱线图的描边粗细为2
                legend = "none", # 不展示图例
                font.x = 15, font.y = 15,
                x.text.angle = 45, y.text.angle = 90,
                font.tickslab = c(20, "plain", "black")) +
  labs(x = NULL, y = "KDM4A-AS1 Expression", title = "TCGA MES") +  # 设置图片标题，不展示横、纵轴的标题
  theme(plot.title = element_text(hjust = 0.5, size = 30), # 设置图片标题居中和字体大小
        axis.line = element_line(color = "black", size = 1.2), # 设置坐标轴线的粗细
        axis.ticks = element_line(color = "black", size = 1.2), # 设置刻度线的粗细
        axis.ticks.length = unit(3, "mm"), # 设置刻度线的长度为3毫米
        axis.title.y = element_text(size = 30)) + # 设置y轴标题的字体大小为15
  geom_signif(  # 添加显著性标记
    comparisons = df1_cmp, # 指定比较对象
    map_signif_level = F,  # 指定显著性差异表示方式，布尔型变量，如果为TRUE，就用***形式来展示显著性差异，"***"=0.001, "**"=0.01, "*"=0.05
    textsize = 6, # 标记文字的大小  
    test = t.test, # 指定检验方法  含wilcox.test、 t.test
    step_increase = 0.2, # 多个组时，差异标注的距离 
    size = 1.2, # 显著性描线线条的粗细
    tip_length = 0.02,   # 标记短竖线的长度
    y_position = max(df1_m$value) # 标记在纵轴方向上的位置
  ) +
  scale_fill_manual(values = mycolor) +  # 确保箱线图的填充颜色
  scale_color_manual(values = mycolor)   # 确保箱线图的边框颜色与填充颜色一致






#这个出图的颜色配色太少了