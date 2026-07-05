library(corrplot)

# 读取数据
rt <- read.table("input.txt",
                 sep = "\t",
                 header = TRUE,
                 check.names = FALSE,
                 row.names = 1)

rt <- t(rt)

# 相关矩阵
cor_matrix <- cor(rt)

# 输出PDF
pdf("plot2.pdf", width = 8, height = 8)

corrplot.mixed(cor_matrix,
               lower = "circle",
               upper = "color",
               tl.col = "black",
               tl.pos = "lt",
               tl.srt = 45,
               lower.col = colorRampPalette(c("#2166AC", "white", "#B2182B"))(200),
               upper.col = colorRampPalette(c("#2166AC", "white", "#B2182B"))(200))

dev.off()