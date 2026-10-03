rm(list=ls())
options(scipen = 1000)
# 加载seurat数据集 
library(tidyverse)
library(ggpubr)
library(magrittr)
library(ggsignif)
library(ggrastr)
# devtools::install_github("LKremer/ggpointdensity")
library(ggpointdensity)
# InstallData("pbmc3k")
# BiocManager::install('caijun/ggcorrplot2')
library(ggcorrplot2) # 绘制下三角相关性椭圆图ggcorrplot
library(ggplot2)
library(sur)
library(reshape2)
library(psych) # 相关性计算

## 加载数据
load("/nas2/zhangj/project/02-bulk-rnaseq/2019-GSE126848-nash病人的4分组转录组/GSE126848/step1-output.Rdata")
ls()
head(dat) # cpm标准化值
symbol_matrix[1:5,1:5] # counts值
table(group_list) # 57个样本，分组信息
length(group_list)

# 选择差异变化大的基因算相关性
# mad: 绝对中位差
# sd:标准差
exprSet <- dat
exprSet <- exprSet[names(sort(apply(exprSet, 1, mad),decreasing = T)[1:20]),]
exprSet <- t(exprSet)
dim(exprSet)
pheatmap::pheatmap(cor(exprSet))


cor_value <- cor(exprSet)
cor_test_mat <- corr.test(exprSet)$p

cor_pp1 <- ggcorrplot(cor_value, method = "ellipse",type = "lower",
                      p.mat = cor_test_mat,
                      col = c("#8aa3db", "white", "#fd9a9a"),
                      pch.cex = 4.5, # 显著性*号的大小
                      insig = "label_sig", sig.lvl = c(0.05, 0.01, 0.001) # (e.g. "*", "**", "***") 
)  +
  guides(color = guide_legend(override.aes = list(size = 1))) + 
  theme(axis.text = element_text(size=10),
        legend.key.width = unit(0.5, "lines"),  # 调整图例键的宽度
        legend.key.height = unit(0.5, "lines")  # 调整图例键的高度
  )

cor_pp1 
ggsave(filename = 'gene_cor.pdf',width = 8,height = 8,plot = cor_pp1 )