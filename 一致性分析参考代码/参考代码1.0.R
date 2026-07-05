



library(ALL)
data(ALL)
df <- exprs(ALL)
dim(df)## [1] 12625   128
df[1:4,1:4]
# ##              01005    01010    03002    04006
# ## 1000_at   7.597323 7.479445 7.567593 7.384684
# ## 1001_at   5.046194 4.932537 4.799294 4.922627
# ## 1002_f_at 3.900466 4.208155 3.886169 4.206798
# ## 1003_s_at 5.903856 6.169024 5.860459 6.116890



# 计算每个基因的中位数绝对偏差
mads <- apply(df,1,mad)
# 选择 MAD 最高的前 5000 个基因
df <- df[rev(order(mads))[1:5000],]




#sweep函数减去中位数进行标准化
exprSet = sweep(df,1, apply(df,1,median,na.rm = T))
par(mfrow = c(1,2))
boxplot(df[,1:20],main = "before")
boxplot(exprSet[,1:20],main = "after")







#BiocManager::install("ConsensusClusterPlus")
library(ConsensusClusterPlus)
title <- "./ConsensusCluster"
results <- ConsensusClusterPlus(exprSet, 
                                maxK = 6, 
                                reps = 500, 
                                pItem = 0.8, 
                                pFeature = 1,
                                title = title, 
                                clusterAlg = "hc", 
                                distance = "pearson", 
                                seed = 123456, 
                                plot = "png")


#输出K = 2时的一致性矩阵
results[[2]][["consensusMatrix"]][1:5,1:5]
#        [,1]      [,2]      [,3]      [,4]      [,5]
#[1,] 1.0000000 1.0000000 0.9166667 1.0000000 1.0000000
#[2,] 1.0000000 1.0000000 0.9393939 1.0000000 1.0000000
#[3,] 0.9166667 0.9393939 1.0000000 0.9090909 0.9428571
#[4,] 1.0000000 1.0000000 0.9090909 1.0000000 1.0000000
#[5,] 1.0000000 1.0000000 0.9428571 1.0000000 1.0000000
consensusMatrix_select <- results[[2]][["consensusMatrix"]]
colnames(consensusMatrix_select) <- colnames(exprSet)
rownames(consensusMatrix_select) <- colnames(exprSet)
consensusMatrix_select[1:5,1:5]

#hclust聚类树
results[[2]][["consensusTree"]]
#Call:
#hclust(d = as.dist(1 - fm), method = finalLinkage)
#Cluster method   : average 
#Number of objects: 128 
plot(results[[2]][["consensusTree"]])

#查看样本所属的聚类群
table(results[[2]]$consensusClass)
#  1  2 
# 97 31
results[[2]][["consensusClass"]][1:5]
#01005 01010 03002 04006 04007 
#    1     1     1     1     1 





#聚类图
ConsensusMatrix  <- data.frame(results[[4]][["consensusMatrix"]])
ConsensusMatrix <- ConsensusMatrix[results[[4]]$consensusTree$order,
                                   results[[4]]$consensusTree$order]           
# 创建注释列数据框
annCol <- data.frame(results = paste0("Cluster", 
                                      results[[4]][['consensusClass']]
                                      [results[[4]]$consensusTree$order]),
                     row.names = colnames(ConsensusMatrix))
head(annCol)
annColors <- list(results = c("Cluster1" = "#db6968",
                              "Cluster2" = "#4d97cd",
                              "Cluster3" = "#99cbeb", 
                              "Cluster4" = "#459943"))
# 绘制热图
library(pheatmap)
Heatmap <- pheatmap(ConsensusMatrix,
                    color = colorRampPalette((c("white", "steelblue")))(100),
                    #cluster_cols = FALSE,cluster_rows = FALSE,
                    clustering_distance_cols = "correlation", clustering_method = "average",
                    border_color = NA,
                    annotation_col = annCol,
                    annotation_colors = annColors,
                    show_colnames = FALSE,
                    show_rownames = FALSE)
Heatmap




#累积分布函数
maxK = 6
Kvec = 2:maxK
x1 = 0.1; x2 = 0.9 # threshold defining the intermediate sub-interval
PAC = rep(NA,length(Kvec))
names(PAC) = paste("K=",Kvec,sep = "") # from 2 to maxK

for(i in Kvec){
  M = results[[i]]$consensusMatrix
  Fn = ecdf(M[lower.tri(M)])
  PAC[i-1] = Fn(x2) - Fn(x1)
}#end for i

# The optimal K
optK = Kvec[which.min(PAC)]
optK## [1] 6












#计算聚类一致性与样本一致性（可选，结果往往比较抽象）

icl <- calcICL(results, title = "./ConsensusCluster",plot = "png", writeTable = TRUE)
## 返回了具有两个元素的list
dim(icl[["clusterConsensus"]])#[1] 20  3
icl[["clusterConsensus"]] 
# k cluster clusterConsensus
# [1,] 2       1        0.7785895
# [2,] 2       2        0.9840360
# [3,] 3       1        0.6262968
# [4,] 3       2        0.9103636
# [5,] 3       3        0.9828577
# [6,] 4       1        0.8640214
# [7,] 4       2        0.8879848
# [8,] 4       3        0.7032581
# [9,] 4       4        0.9796581
#[10,] 5       1        0.8151022
#[11,] 5       2        0.8816634
#[12,] 5       3        0.6641143
#[13,] 5       4        0.8249247
#[14,] 5       5        1.0000000
#[15,] 6       1        0.8742257
#[16,] 6       2        0.8726505
#[17,] 6       3        0.6419156
#[18,] 6       4        0.6912868
#[19,] 6       5        0.8249247
#[20,] 6       6        1.0000000

dim(icl[["itemConsensus"]])#[1] 2560    4
icl[["itemConsensus"]][1:5,] 
#  k cluster  item itemConsensus
#1 2       1 26003     0.7640120
#2 2       1 24022     0.7340306
#3 2       1 62002     0.7677255
#4 2       1 31011     0.7564733
#5 2       1 28001     0.7235542