options(repos = c(CRAN="https://mirrors.tuna.tsinghua.edu.cn/CRAN/"))
install.packages("BiocManager")

BiocManager::install(c("monocle3", "Seurat", "dplyr", "ggplot2", "SingleCellExperiment", "igraph"), ask=FALSE)

cat("所有包安装完成\n")
