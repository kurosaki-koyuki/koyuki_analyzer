#目的基因：PAXIP1-AS2


#清空环境
rm(list = ls())

#获取原始项目所在路径（方便以后改回原始路径）
initial_workplace=getwd()
#先回到最初路径
setwd(initial_workplace)
#先回到最初路径
setwd(initial_workplace)
#设置读取路径
setwd("DISPOSED_DATA/PAXIP1-AS2")
library(dplyr)
library(clusterProfiler)
library(org.Hs.eg.db)
library(enrichplot)
library(ggplot2)
library(org.Hs.eg.db)
library(GOplot)


#读入数据
# 读取数据，假设第一行是列名
rt <- read.table("TCGA_LIMMA_DEG_PAXIP1-AS2.txt", sep="\t", header=TRUE, check.names=FALSE)

# 保留第一列数据
first_column <- rt[, 1]


#转换为ENTREZID
entrezIDs = bitr(first_column, fromType = "SYMBOL", toType = "ENTREZID", OrgDb= "org.Hs.eg.db", drop = TRUE)
#使用entrezIDs
gene<- entrezIDs$ENTREZID


##GO富集分析
go<- enrichGO(gene = gene,OrgDb = org.Hs.eg.db, pvalueCutoff =0.05, qvalueCutoff = 0.05,ont="all",readable =T)
write.table(go,file="GO.txt",sep="\t",quote=F,row.names = F) #
#######找出前十表达
#形成一个矩阵
GO=as.data.frame(go)
##BP前十
# 找出第一列分类为"GO"的所有行
rows_to_select <- GO[, 1] == "BP"
# 使用逻辑索引提取这些行
BP <- GO[rows_to_select, ]
#选出前十
BP <- BP %>%
  arrange(p.adjust) %>%
  ungroup()  # 去掉分组
write.table(BP,file="TCGA_DEG_GO_BP_PAXIP1-AS2.txt",sep="\t",quote=F,row.names = F)
##CC前十
rows_to_select <- GO[, 1] == "CC"
# 使用逻辑索引提取这些行
CC <- GO[rows_to_select, ]
#选出前十
CC <- CC %>%
  arrange(p.adjust) %>%
  ungroup()  # 去掉分组
write.table(CC,file="TCGA_DEG_GO_CC_PAXIP1-AS2.txt",sep="\t",quote=F,row.names = F)
##MF前十
rows_to_select <- GO[, 1] == "MF"
# 使用逻辑索引提取这些行
MF <- GO[rows_to_select, ]
#选出前十
MF <- MF %>%
  arrange(p.adjust) %>%
  ungroup()  # 去掉分组
write.table(MF,file="TCGA_DEG_GO_MF_PAXIP1-AS2.txt",sep="\t",quote=F,row.names = F)
##可视化
#先回到最初路径
setwd(initial_workplace)
# 检查路径是否存在，如果不存在则创建
path <- "OUTPUT/PAXIP1-AS2/DEG"
if (!dir.exists(path)) {
  dir.create(path, recursive = TRUE)
}
setwd("OUTPUT/PAXIP1-AS2/DEG")
##条形图
pdf(file="TCGA_GO_barplot_PAXIP1-AS2.pdf",width = 10,height = 15)
barplot(go, drop = TRUE, showCategory =10,label_format=100,split="ONTOLOGY") + facet_grid(ONTOLOGY~., scale='free')
dev.off()


##气泡图
pdf(file="TCGA_GO_bubble_PAXIP1-AS2.pdf",width = 10,height = 15)
dotplot(go,showCategory = 10,label_format=100,split="ONTOLOGY") + facet_grid(ONTOLOGY~., scale='free')
dev.off()
#先回到最初路径
setwd(initial_workplace)
#kegg分析
kk <- enrichKEGG(gene = gene,keyType = "kegg",organism = "hsa", pvalueCutoff =0.05, qvalueCutoff =0.05, pAdjustMethod = "fdr") 
###接下来写一段仅导出差异基因的KEGG
KEGG=as.data.frame(kk)
KEGG$geneID=as.character(sapply(KEGG$geneID,function(x)paste(first_column[match(strsplit(x,"/")[[1]],as.character(gene))],collapse="/")))
write.table(KEGG, file="KEGG.txt", sep="\t", quote=F, row.names = F)
kegg_results <- read.table("KEGG.txt", sep = "\t", header = TRUE, check.names = FALSE)
#######找出前十表达
KEGG2 <- KEGG
KEGG2 <- KEGG2 %>%
  arrange(p.adjust) %>%
  ungroup()  # 去掉分组
write.table(KEGG2,file="KEGG前十.txt",sep="\t",quote=F,row.names = F)

# 处理 geneID 列
kegg_results$geneID <- sapply(kegg_results$geneID, function(x) {
  # 按照 "/" 分割字符串
  elements <- unlist(strsplit(x, "/"))
  # 移除名为 "NA" 的元素
  elements <- elements[elements != "NA"]
  # 如果有剩余元素，重新组合为字符串；如果没有剩余元素，返回空字符串
  if (length(elements) > 0) {
    return(paste(elements, collapse = "/"))
  } else {
    return("")
  }
})
write.table(kegg_results, file="TCGA_DEG_KEGG_PAXIP1-AS2.txt", sep="\t", quote=F, row.names = F)
#先回到最初路径
setwd(initial_workplace)
# 检查路径是否存在，如果不存在则创建
path <- "OUTPUT/PAXIP1-AS2/DEG"
if (!dir.exists(path)) {
  dir.create(path, recursive = TRUE)
}
setwd("OUTPUT/PAXIP1-AS2/DEG")


# 准备数据
kegg_data <- as.data.frame(kk)
kegg_data_top <- kegg_data %>% 
  arrange(p.adjust) %>%  # 按照 p.adjust 升序排列
  head(10)  # 取前 10 个

# 将这 10 个结果按照 RichFactor 升序排列
kegg_data_top <- kegg_data_top %>% 
  arrange(RichFactor)
# 将GeneRatio列的内容转换为比值结果，并赋值给RichFactor列
kegg_data_top$RichFactor <- sapply(kegg_data_top$GeneRatio, function(x) {
  parts <- strsplit(x, "/")[[1]]
  as.numeric(parts[1]) / as.numeric(parts[2])
})
# 绘制气泡图
library(ggplot2)
library(stringr)

kegg_bubble <- ggplot(kegg_data_top, aes(x = RichFactor, y = reorder(Description, RichFactor), color = p.adjust)) + 
  geom_point(aes(size = Count)) +  # 绘制散点图
  theme_bw() +  # 白色主题
  scale_y_discrete(labels = function(y) str_wrap(y, width = 50)) +  # 设置Term名称过长时换行
  labs(size = "Counts", x = "Rich Factor", y = "KEGG Pathways", title = "KEGG Enrichment") +
  scale_color_gradient(low = "#b34644", high = "#45739e") +  # 颜色渐变设置
  theme(axis.text = element_text(size = 10, color = "black"),  # 轴标签大小和颜色
        axis.title = element_text(size = 16),  # 轴标题大小
        title = element_text(size = 13)) +  # 图标题大小
  guides(color = guide_colorbar(reverse = TRUE))  # 颜色渐变设置，高值颜色在下方，低值颜色在上方

# 显示气泡图
kegg_bubble




##可视化
##条形图
pdf(file="TCGA_KEGG_barplot_PAXIP1-AS2.pdf",width = 10,height = 13)
barplot(kk, drop = TRUE, showCategory = 15,label_format=100)
dev.off()

##气泡图
pdf(file="TCGA_KEGG_bubble_PAXIP1-AS2.pdf",width = 10,height = 6)
dotplot(kk, showCategory = 15,label_format=100)
dev.off()


#回到最初路径
setwd(initial_workplace)