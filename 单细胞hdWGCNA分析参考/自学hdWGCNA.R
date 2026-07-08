rm(list = ls())
library(WGCNA)
library(hdWGCNA)
library(tidyverse)
library(cowplot)
library(patchwork)
library(qs)
library(Seurat)

set.seed(12345)#WGCNA 软阈值、层次聚类、模块划分存在随机过程，设种子保证每次运行结果完全一致，可重复。
#enableWGCNAThreads(nThreads = 8)


#这里加载的是seurat对象，替换自己的数据即可
scRNA <- readRDS("GSE102130seurat_obj_with_anno.rds")
qsave(scRNA, "GSE102130seurat_obj_with_anno.qs")
scRNA <- qread("GSE102130seurat_obj_with_anno.qs")


###样本所在注释列：Sample
sample_group<- "Sample"
###想要进行hdWGCNA所在的的注释列
analyze_group<- "Celltype (minor-lineage)"


#检查自己的注释
colnames(scRNA@meta.data)
#看一下，看一看你的样本所在的注释列
table(scRNA[[sample_group]])


#检查一下自己导入进来的数据
Idents(scRNA) <- analyze_group
DimPlot(scRNA,reduction = 'umap',
        label = TRUE,pt.size = 0.5) +NoLegend()

# V5版本需要这行代码，V4不需要
scRNA <- SeuratObject::UpdateSeuratObject(scRNA)
seurat_obj <- SetupForWGCNA(
  scRNA,
  gene_select = "fraction", # 默认fraction;其他有variable(Seurat对象中存储的基因),custom(自定义)
  fraction = 0.05, # fraction of cells that a gene needs to be expressed in order to be included
  wgcna_name = "GSE102130" # the name of the hdWGCNA experiment
)

###########我之前处理的seurat对象是没有harmony降维的，所以要先降维
library(harmony)
#看看你之前有没有处理harmony，若输出只有 "pca" "umap"，就是没有 harmony：
names(seurat_obj@reductions)


seurat_obj <- RunHarmony(
  object = seurat_obj,
  group.by.vars = sample_group,  # 替换成真正存样本的列
  reduction.use = "pca",
  reduction.save = "harmony",
  dims.use = 1:ncol(Embeddings(seurat_obj, "pca")),
  verbose = F
)
#再看看，是不是有harmony了
names(seurat_obj@reductions)







#如果你的注释带括号或者一些其他特殊符号，请运行下面几行（新建干净无特殊字符的分型列，当然，日常也可用）：
seurat_obj$wgcna_type_fixed_analyze <- factor(seurat_obj@meta.data[[analyze_group]])
#干净注释定义
seurat_anno_type_fixed_analyze_group <- "wgcna_type_fixed_analyze"
#如果你的注释带括号或者一些其他特殊符号，请运行下面几行（新建干净无特殊字符的分型列，当然，日常也可用）：
seurat_obj$wgcna_type_fixed_sample <- factor(seurat_obj@meta.data[[sample_group]])
#干净注释定义
seurat_anno_type_fixed_sample_group <- "wgcna_type_fixed_sample"






# 各组构建metacell
seurat_obj <- MetacellsByGroups(
  seurat_obj = seurat_obj,
  group.by = seurat_anno_type_fixed_analyze_group , #指定seurat_obj@meta.data中要分组的列，如果你的样本量很大而且想要用到样本去批次，那就把“=”后面改成：c(seurat_anno_type_fixed_analyze_group, seurat_anno_type_fixed_sample_group)
  reduction = 'harmony', # 选择要执行KNN的降维
  k = 25, # 最近邻居参数
  max_shared = 10, # 两个metacell之间共享细胞的最大数目
  ident.group = seurat_anno_type_fixed_analyze_group , # 设置metacell安全对象的标识
  min_cells = 80 # 排除数量小于80的细胞亚群,但示例中的用的默认值是100
)




# normalize metacell expression matrix:
seurat_obj <- NormalizeMetacells(seurat_obj)




#请选择你的某一类群细胞，分析内部功能marker基因（分析这一类细胞的增殖，免疫等相关基因）
table(seurat_obj[[seurat_anno_type_fixed_analyze_group]])
target_cell_type <- "OPC-like Malignant"
#也可以试试好几组，但这就属于同时分析这几组共有的内部功能marker基因了，所以不是很推荐，除非这几类细胞很相似：target_cell_type <-c("OPC-like Malignant", "M1")


#设置表达式矩阵，使用hdWGCNA对目标细胞亚群进行共表达网络分析
seurat_obj <- SetDatExpr(
  seurat_obj,
  group_name = target_cell_type, # the name of the group of interest in the group.by column
  group.by=seurat_anno_type_fixed_analyze_group, # the metadata column containing the cell type info. This same column should have also been used in MetacellsByGroups
  assay = 'RNA', # using RNA assay
  slot = 'data' # using normalized data
)




# Test different soft powers:
seurat_obj <- TestSoftPowers(
  seurat_obj,
  powers = c(seq(1, 10, by = 1), seq(12, 30, by = 2)),
  networkType = 'unsigned' # you can also use "unsigned" or "signed hybrid"
)

# plot the results:
plot_list <- PlotSoftPowers(seurat_obj)
# 1     1 0.4193109 -2.829398      0.9708088 551.0532441 532.1816874 1079.59624
# 2     2 0.7722457 -2.846229      0.9935455  90.8116702  80.0299812  331.23789
# 3     3 0.8469701 -2.813601      0.9812133  19.9509707  15.0395890  127.98068
# 4     4 0.8914758 -2.532259      0.9884110   5.4419966   3.2775043   57.54649
# 5     5 0.9024030 -2.199419      0.9834531   1.7820619   0.7925626   28.86319
# 6     6 0.9511793 -1.813044      0.9753076   0.6868952   0.2083341   15.72666

# assemble with patchwork
wrap_plots(plot_list, ncol=2)

# check以下数据
power_table <- GetPowerTable(seurat_obj)
head(power_table)
#   Power   SFT.R.sq     slope truncated.R.sq   mean.k. median.k.    max.k.
# 1     1 0.02536182  3.273051      0.9541434 4370.9149 4379.0629 4736.8927
# 2     2 0.11091306 -3.571441      0.8008960 2322.5480 2286.2454 2871.2953
# 3     3 0.50454728 -4.960822      0.8035027 1286.6453 1241.8414 1898.5501
# 4     4 0.79569568 -4.812735      0.9183803  740.0525  697.1193 1338.0185
# 5     5 0.86641323 -4.110731      0.9517671  440.6141  402.5530  985.0984
# 6     6 0.88593187 -3.582879      0.9624951  270.9020  237.8831  750.2825



# 如果没有指定软阈值，construcNetwork会自动指定软阈值
# construct co-expression network:
seurat_obj <- ConstructNetwork(
  seurat_obj,
  soft_power = 4, # 自定义了4，如果是自动选择的话可能会是3
  tom_outdir = "TOM",
  tom_name = target_cell_type, # name of the topoligical overlap matrix written to disk
  overwrite_tom = TRUE # 允许覆盖已存在的同名文件
)

# 可视化WGCNA树状图
# “灰色”模块由那些未被归入任何共表达模块的基因组成。对于所有下游分析和解释，应忽略灰色模块。
PlotDendrogram(
  seurat_obj, 
  main = paste0(target_cell_type, " hdWGCNA Dendrogram")
)

# 可选：检查拓扑重叠矩阵(topoligcal overlap matrix，TOM)
# TOM <- GetTOM(seurat_obj)
# TOM



# 需要先运行ScaleData，否则harmony会报错:
# seurat_obj <- ScaleData(seurat_obj, features=VariableFeatures(seurat_obj))

# 计算完整单细胞数据集中的所有MEs
seurat_obj <- ModuleEigengenes(
 seurat_obj,
 group.by.vars=seurat_anno_type_fixed_sample_group
)

# 协调模特征基因:
# 允许用户对MEs应用Harmony批量校正，生成协调模块特征基因(hMEs)
hMEs <- GetMEs(seurat_obj)

# module eigengenes:
#MEs <- GetMEs(seurat_obj, harmonized=FALSE)



# 计算基于特征基因的连接性(kME)：
# 关注枢纽基因
seurat_obj <- ModuleConnectivity(
  seurat_obj,
  group.by = seurat_anno_type_fixed_analyze_group, 
  group_name = target_cell_type
)

# 模块重命名
seurat_obj <- ResetModuleNames(
  seurat_obj,
  new_name = paste0(target_cell_type, "_New")
)

# 绘制每个模块按kME排序的基因
p <- PlotKMEs(seurat_obj, ncol=4)
p



# 获取模块内部信息:
# 个人认为这一部分很关键，毕竟咱们就是想要得到不同模块的基因
# 这一步去除了不需要的灰色模块基因
modules <- GetModules(seurat_obj) %>% 
  subset(module != 'grey')

# 显示前六列:
head(modules[,1:6])
#          gene_name    module     color   kME_grey kME_Treg_NEW1 kME_Treg_NEW2
# ISG15        ISG15 Treg_NEW1 turquoise 0.09485063    0.31618006     0.2177907
# TNFRSF18  TNFRSF18 Treg_NEW1 turquoise 0.12119087    0.39886246     0.4605542
# TNFRSF4    TNFRSF4 Treg_NEW1 turquoise 0.08844463    0.35922337     0.3728684
# SDF4          SDF4 Treg_NEW2     black 0.11518097    0.11212155     0.1883993
# B3GALT6    B3GALT6 Treg_NEW3    purple 0.03314139    0.08610811     0.1067775
# AURKAIP1  AURKAIP1 Treg_NEW1 turquoise 0.09062613    0.26244827     0.1252306

# 得到枢纽基因
# 可以提取按kME排序的前N个枢纽基因的表格,这里选择了10
hub_df <- GetHubGenes(seurat_obj, n_hubs = 10)
head(hub_df)
#   gene_name    module       kME
# 1     GAPDH Treg_NEW1 0.6160237
# 2    S100A4 Treg_NEW1 0.5886924
# 3      MYL6 Treg_NEW1 0.5558792
# 4    TMSB10 Treg_NEW1 0.5371290
# 5      IL32 Treg_NEW1 0.5161320
# 6    ARPC1B Treg_NEW1 0.5138853

# 保存数据
qsave(seurat_obj, 'hdWGCNA_object.qs')



# 计算每个模块前25个枢纽基因的kME得分
# 使用UCell方法
library(UCell)
seurat_obj <- ModuleExprScore(
  seurat_obj,
  n_genes = 25,
  method='UCell' # Seurat方法(AddModuleScore)
)



# 每个模块制作hMEs的特征图
plot_list <- ModuleFeaturePlot(
  seurat_obj,
  features='hMEs', # plot the hMEs
  order=TRUE # order so the points with highest hMEs are on top
)

# stitch together with patchwork
wrap_plots(plot_list, ncol=4)



# 每个模块制作hub scores的特征图
plot_list <- ModuleFeaturePlot(
  seurat_obj,
  features='scores', # plot the hub gene scores
  order='shuffle', # order so cells are shuffled
  ucell = TRUE # depending on Seurat vs UCell for gene scoring
)
# stitch together with patchwork
wrap_plots(plot_list, ncol=4)



# 每个模块在不同样本中的情况
seurat_obj$cluster <- do.call(rbind, strsplit(as.character(seurat_obj$orig.ident), ' '))[,1]

ModuleRadarPlot(
  seurat_obj,
  group.by = 'cluster',
  barcodes = seurat_obj@meta.data %>% 
    subset(celltype == 'Treg') %>% 
    rownames(),
  axis.label.size=4,
  grid.label.size=4
)



# 查看模块相关图
ModuleCorrelogram(seurat_obj)



# get hMEs from seurat object
MEs <- GetMEs(seurat_obj, harmonized=TRUE)
modules <- GetModules(seurat_obj)
mods <- levels(modules$module); mods <- mods[mods != 'grey']

# add hMEs to Seurat meta-data:
seurat_obj@meta.data <- cbind(seurat_obj@meta.data, MEs)

# plot with Seurat's DotPlot function
p <- DotPlot(seurat_obj, features=mods, group.by = 'celltype')

# flip the x/y axes, rotate the axis labels, and change color scheme:
p <- p +
  RotatedAxis() +
  scale_color_gradient2(high='red', mid='grey95', low='blue')

# plot output
p




# 使用ModuleNetworkPlot可视化每个模块前50(数值可自定)的hub gene
ModuleNetworkPlot(
    seurat_obj, 
    outdir='ModuleNetworks', # new folder name
    n_inner = 20, # number of genes in inner ring
    n_outer = 30, # number of genes in outer ring
    n_conns = Inf, # show all of the connections
    plot_size=c(10,10), # larger plotting area
    vertex.label.cex=1 # font size
)




options(future.globals.maxSize = 5 * 1024^3)  # 5GB

# hubgene network(基因数可自定)
HubGeneNetworkPlot(
  seurat_obj,
  n_hubs = 2, 
  n_other=2,
  edge_prop = 0.75,
  mods = 'all'
)

# 可以选择模块数
g <- HubGeneNetworkPlot(seurat_obj,  return_graph=TRUE)
# get the list of modules:
modules <- GetModules(seurat_obj)
mods <- levels(modules$module); mods <- mods[mods != 'grey']
# hubgene network
HubGeneNetworkPlot(
  seurat_obj,
  n_hubs = 2, 
  n_other= 2,
  edge_prop = 0.75,
  mods = mods[1:5] # only select 5 modules
)



seurat_obj <- RunModuleUMAP(
  seurat_obj,
  n_hubs = 10, # number of hub genes to include for the UMAP embedding
  n_neighbors=15, # neighbors parameter for UMAP
  min_dist=0.1 # min distance between points in UMAP space
)

# get the hub gene UMAP table from the seurat object
umap_df <- GetModuleUMAP(seurat_obj)

# plot with ggplot
ggplot(umap_df, aes(x=UMAP1, y=UMAP2)) +
  geom_point(
   color=umap_df$color, # color each point by WGCNA module
   size=umap_df$kME*2 # size of each point based on intramodular connectivity
  ) +
  umap_theme()


ModuleUMAPPlot(
  seurat_obj,
  edge.alpha=0.25,
  sample_edges=TRUE,
  edge_prop=0.1, # proportion of edges to sample (20% here)
  label_hubs=2 ,# how many hub genes to plot per module?
  keep_grey_edges=FALSE
)





library(Seurat)
library(tidyverse)
library(cowplot)
library(patchwork)
library(WGCNA)
library(hdWGCNA)
library(enrichR)
library(GeneOverlap)
library(qs)

#dir.create("14-hdWGCNA")
#setwd("14-hdWGCNA")

seurat_obj <- qread("hdWGCNA_object.qs")

# 定义enrichr databases
dbs <- c('GO_Biological_Process_2023',
         'GO_Cellular_Component_2023',
         'GO_Molecular_Function_2023')

# 富集分析
seurat_obj <- RunEnrichr(
  seurat_obj,
  dbs=dbs,
  max_genes = 100 # use max_genes = Inf to choose all genes
)

# 检索输出表
enrich_df <- GetEnrichrTable(seurat_obj)

# 查看结果
head(enrich_df)

# make GO term plots:
EnrichrBarPlot(
  seurat_obj,
  outdir = "enrichr_plots", # name of output directory
  n_terms = 10, # number of enriched terms to show (sometimes more are shown if there are ties)
  plot_size = c(5,7), # width, height of the output .pdfs
  logscale=TRUE # do you want to show the enrichment as a log scale?
)

# enrichr dotplot
EnrichrDotPlot(
  seurat_obj,
  mods = "all", # use all modules (default)
  database = "GO_Biological_Process_2023", # this must match one of the dbs used previously
  n_terms=2, # number of terms per module
  term_size=8, # font size for the terms
  p_adj = FALSE # show the p-val or adjusted p-val?
)  + scale_color_stepsn(colors=rev(viridis::magma(256)))




library(fgsea)

# load the GO Biological Pathways file (downloaded from EnrichR website)
pathways <- fgsea::gmtPathways('GO_Biological_Process_2023.txt')

# optionally, remove the GO term ID from the pathway names to make the downstream plots look cleaner
names(pathways) <- stringr::str_replace(names(pathways), " \\s*\\([^\\)]+\\)", "")


# get the modules table and remove grey genes
modules <- GetModules(seurat_obj) %>% subset(module != 'grey')

# rank by Treg_NEW1 genes only by kME
cur_mod <- 'Treg_NEW1'
modules <- GetModules(seurat_obj) %>% subset(module == cur_mod)
cur_genes <- modules[,(c('gene_name', 'module', paste0('kME_', cur_mod)))]
ranks <- cur_genes$kME; names(ranks) <- cur_genes$gene_name
ranks <- ranks[order(ranks)]

# run fgsea to compute enrichments
gsea_df2 <- fgsea::fgsea(
  pathways = pathways, 
  stats = ranks,
  minSize = 3,
  maxSize = 500
)

# 可视化
top_pathways <- gsea_df2 %>% 
    subset(pval < 0.05) %>% 
    slice_max(order_by=NES, n=25) %>% 
    .$pathway

plotGseaTable(
    pathways[top_pathways], 
    ranks, 
    gsea_df2, 
    gseaParam=0.5,
    colwidths = c(10, 4, 1, 1, 1)
)

# name of the pathway to plot 
selected_pathway <- 'Cellular Respiration'
plotEnrichment(
    pathways[[selected_pathway]],
    ranks
) + labs(title=selected_pathway)






library(Seurat)
library(tidyverse)
library(cowplot)
library(patchwork)
library(magrittr)
library(WGCNA)
library(hdWGCNA)
library(igraph)
library(JASPAR2020)
library(JASPAR2024)
library(motifmatchr)
library(TFBSTools)
library(EnsDb.Hsapiens.v86)
library(BSgenome.Hsapiens.UCSC.hg38)
library(GenomicRanges)
library(xgboost)
library(JASPAR2024)
library(RSQLite)
library(EnsDb.Hsapiens.v86)
library(qs)

#dir.create("14-hdWGCNA")
#setwd("14-hdWGCNA")

seurat_obj <- qread("hdWGCNA_object.qs")

# JASPAR 2020
pfm_core <- TFBSTools::getMatrixSet(
  x = JASPAR2020,
  opts = list(collection = "CORE", 
              tax_group = 'vertebrates', 
              all_versions = FALSE)
)

# JASPAR 2024 (not used for this tutorial)
# JASPAR2024 <- JASPAR2024()
# sq24 <- RSQLite::dbConnect(RSQLite::SQLite(), db(JASPAR2024))
# pfm_core <- TFBSTools::getMatrixSet(
#   x = sq24,
#   opts = list(collection = "CORE", tax_group = 'vertebrates', all_versions = FALSE)
# )

# 进行motif分析
seurat_obj <- MotifScan(
  seurat_obj,
  species_genome = 'hg38',
  pfm = pfm_core,
  EnsDb = EnsDb.Hsapiens.v86
)

# 获取motif df:
motif_df <- GetMotifs(seurat_obj)

# 保留所有TFs, 并去除灰色模块基因
tf_genes <- unique(motif_df$gene_name)
modules <- GetModules(seurat_obj)
nongrey_genes <- subset(modules, module != 'grey') %>% .$gene_name
genes_use <- c(tf_genes, nongrey_genes)

# update the gene list and re-run SetDatExpr
seurat_obj <- SetWGCNAGenes(seurat_obj, genes_use)
seurat_obj <- SetDatExpr(seurat_obj, group.by = 'celltype', group_name='Treg')

# define model params:
model_params <- list(
    objective = 'reg:squarederror',
    max_depth = 1,
    eta = 0.1,
    nthread=16,
    alpha=0.5
)

# 构建转录因子网络
seurat_obj <- ConstructTFNetwork(seurat_obj, model_params)
results <- GetTFNetwork(seurat_obj)
head(results)
#        tf  gene       Gain      Cover  Frequency         Cor
# 1 ZKSCAN1 FOXD1 0.11708119 0.04695019 0.04695019 -0.19391353
# 2   NFIL3 FOXD1 0.10931756 0.05379589 0.05379589  0.19738680
# 3  ZNF652 FOXD1 0.09789632 0.07897635 0.07897635 -0.17072678
# 4   NR4A1 FOXD1 0.09624640 0.04498028 0.04498028  0.18091337
# 5   ZNF24 FOXD1 0.05250378 0.02255133 0.02255133 -0.09566174
# 6   NFKB2 FOXD1 0.05148296 0.06481095 0.06481095  0.16717336

# 策略“A”为每个基因选择前10个TF
# 策略“B”选择每个转录因子的顶级基因
# 策略“C”保留所有高于一定调控分数的TF-基因对
seurat_obj <- AssignTFRegulons(
    seurat_obj,
    strategy = "A", # 还有B和C策略
    reg_thresh = 0.01,
    n_tfs = 10
)

# 可视化
# 根据基因表达分为与TF正相关(右侧)或负相关(左侧)的目标基因
p1 <- RegulonBarPlot(seurat_obj, selected_tf='ZNF652')
p2 <- RegulonBarPlot(seurat_obj, selected_tf='NFKB2', cutoff=0.15)
p1 | p2







# 正向regulons
seurat_obj <- RegulonScores(
    seurat_obj,
    target_type = 'positive',
    ncores=8
)

# 负向regulons
seurat_obj <- RegulonScores(
    seurat_obj,
    target_type = 'negative',
    cor_thresh = -0.05,
    ncores=8
)

# 获取数据结果:
pos_regulon_scores <- GetRegulonScores(seurat_obj, target_type='positive')
neg_regulon_scores <- GetRegulonScores(seurat_obj, target_type='negative')

# 选择感兴趣的TF
cur_tf <- 'FOXP3'

# 把regulon分数添加到Seurat metadata
seurat_obj$pos_regulon_score <- pos_regulon_scores[,cur_tf]
seurat_obj$neg_regulon_score <- neg_regulon_scores[,cur_tf]

# plot using FeaturePlot
p1 <- FeaturePlot(seurat_obj, feature=cur_tf) + umap_theme()
p2 <- FeaturePlot(seurat_obj, feature='pos_regulon_score', cols=c('lightgrey', 'red')) + umap_theme()
p3 <- FeaturePlot(seurat_obj, feature='neg_regulon_score', cols=c('lightgrey', 'seagreen')) + umap_theme()

p1 | p2 | p3




# select TF of interest
cur_tf <- 'FOXP3'

# plot with default settings
p <- TFNetworkPlot(seurat_obj, selected_tfs=cur_tf)
p

# plot the FOXP3 network with primary, secondary, and tertiary targets
p1 <- TFNetworkPlot(seurat_obj, selected_tfs=cur_tf, depth=1, no_labels=TRUE)
p2 <- TFNetworkPlot(seurat_obj, selected_tfs=cur_tf, depth=2, no_labels=TRUE)
p3 <- TFNetworkPlot(seurat_obj, selected_tfs=cur_tf, depth=3, no_labels=TRUE)

p1 | p2 | p3