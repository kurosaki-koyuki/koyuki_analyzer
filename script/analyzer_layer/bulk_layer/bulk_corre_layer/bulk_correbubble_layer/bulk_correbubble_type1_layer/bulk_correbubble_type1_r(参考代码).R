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
pdf("plot1.pdf", width = 8, height = 8)

corrplot(cor_matrix,
         method = "pie",
         type = "upper",
         order = "hclust",
         col = colorRampPalette(c("#2166AC", "white", "#B2182B"))(200),
         tl.col = "black",
         tl.srt = 45)

dev.off()