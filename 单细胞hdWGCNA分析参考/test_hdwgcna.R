rm(list = ls())

cat("========== 开始测试hdWGCNA环境 ==========\n")

cat("1. 加载必需的包...\n")
required_packages <- c("WGCNA", "hdWGCNA", "tidyverse", "cowplot", "patchwork", "Seurat")
for (pkg in required_packages) {
    if (!require(pkg, character.only = TRUE)) {
        cat(paste0("  包 ", pkg, " 未安装，尝试安装...\n"))
        tryCatch({
            install.packages(pkg, dependencies = TRUE)
            library(pkg, character.only = TRUE)
            cat(paste0("  包 ", pkg, " 安装成功\n"))
        }, error = function(e) {
            cat(paste0("  包 ", pkg, " 安装失败: ", e$message, "\n"))
        })
    } else {
        cat(paste0("  包 ", pkg, " 已加载\n"))
    }
}

cat("\n2. 设置随机种子...\n")
set.seed(12345)

cat("\n3. 加载Seurat对象...\n")
seurat_path <- "A:/PYidea/koyuki_analyzer/test_files/koyuki_beta2.5test/单细胞hdWGCNA分析参考/GSE102130seurat_obj_with_anno.rds"
cat(paste0("  文件路径: ", seurat_path, "\n"))
if (file.exists(seurat_path)) {
    cat(paste0("  文件存在，正在加载: ", seurat_path, "\n"))
    scRNA <- readRDS(seurat_path)
    cat(paste0("  加载成功！对象类型: ", class(scRNA), "\n"))
    cat(paste0("  细胞数: ", ncol(scRNA), "\n"))
    cat(paste0("  基因数: ", nrow(scRNA), "\n"))
} else {
    cat(paste0("  错误: 文件不存在: ", seurat_path, "\n"))
    quit(status = 1)
}

cat("\n4. 检查metadata列...\n")
cat("  metadata列名:\n")
print(colnames(scRNA@meta.data))

cat("\n5. 运行SetupForWGCNA...\n")
tryCatch({
    seurat_obj <- SetupForWGCNA(
        scRNA,
        gene_select = "fraction",
        fraction = 0.05,
        wgcna_name = "GSE102130"
    )
    cat("  SetupForWGCNA成功！\n")
    cat(paste0("  wgcna_name: ", seurat_obj@misc$wgcna_name, "\n"))
}, error = function(e) {
    cat(paste0("  SetupForWGCNA失败: ", e$message, "\n"))
    quit(status = 1)
})

cat("\n6. 检查降维...\n")
cat("  当前降维方法:\n")
print(names(seurat_obj@reductions))

cat("\n7. 创建干净的注释列...\n")
seurat_obj$wgcna_type_fixed_analyze <- factor(seurat_obj@meta.data[["Celltype (minor-lineage)"]])
seurat_obj$wgcna_type_fixed_sample <- factor(seurat_obj@meta.data[["Sample"]])
cat("  已创建干净注释列: wgcna_type_fixed_analyze, wgcna_type_fixed_sample\n")

cat("\n8. 运行Harmony降维...\n")
seurat_obj <- RunHarmony(
    object = seurat_obj,
    group.by.vars = "wgcna_type_fixed_sample",
    reduction.use = "pca",
    reduction.save = "harmony",
    dims.use = 1:ncol(Embeddings(seurat_obj, "pca")),
    verbose = F
)
cat("  Harmony降维成功！\n")
cat("  当前降维方法:\n")
print(names(seurat_obj@reductions))

cat("\n9. 运行MetacellsByGroups...\n")
tryCatch({
    seurat_obj <- MetacellsByGroups(
        seurat_obj = seurat_obj,
        group.by = "wgcna_type_fixed_analyze",
        reduction = 'harmony',
        k = 25,
        max_shared = 10,
        ident.group = "wgcna_type_fixed_analyze",
        min_cells = 80
    )
    cat("  MetacellsByGroups成功！\n")
}, error = function(e) {
    cat(paste0("  MetacellsByGroups失败: ", e$message, "\n"))
    cat("  尝试使用pca降维...\n")
    tryCatch({
        seurat_obj <- MetacellsByGroups(
            seurat_obj = seurat_obj,
            group.by = "wgcna_type_fixed_analyze",
            reduction = 'pca',
            k = 25,
            max_shared = 10,
            ident.group = "wgcna_type_fixed_analyze",
            min_cells = 80
        )
        cat("  MetacellsByGroups(pca)成功！\n")
    }, error = function(e2) {
        cat(paste0("  MetacellsByGroups(pca)也失败: ", e2$message, "\n"))
        quit(status = 1)
    })
})

cat("\n10. 运行NormalizeMetacells...\n")
tryCatch({
    seurat_obj <- NormalizeMetacells(seurat_obj)
    cat("  NormalizeMetacells成功！\n")
}, error = function(e) {
    cat(paste0("  NormalizeMetacells失败: ", e$message, "\n"))
    quit(status = 1)
})

cat("\n11. 设置目标细胞类型...\n")
target_cell_type <- "OPC-like Malignant"
cat(paste0("  目标细胞类型: ", target_cell_type, "\n"))

cat("\n12. 运行SetDatExpr...\n")
tryCatch({
    seurat_obj <- SetDatExpr(
        seurat_obj,
        group_name = target_cell_type,
        group.by = "wgcna_type_fixed_analyze",
        assay = 'RNA',
        slot = 'data'
    )
    cat("  SetDatExpr成功！\n")
}, error = function(e) {
    cat(paste0("  SetDatExpr失败: ", e$message, "\n"))
    quit(status = 1)
})

cat("\n13. 运行TestSoftPowers...\n")
tryCatch({
    seurat_obj <- TestSoftPowers(
        seurat_obj,
        powers = c(seq(1, 10, by = 1), seq(12, 30, by = 2)),
        networkType = 'unsigned'
    )
    cat("  TestSoftPowers成功！\n")
    
    power_table <- GetPowerTable(seurat_obj)
    cat("  软阈值表前6行:\n")
    print(head(power_table))
}, error = function(e) {
    cat(paste0("  TestSoftPowers失败: ", e$message, "\n"))
    quit(status = 1)
})

cat("\n14. 运行ConstructNetwork...\n")
tryCatch({
    seurat_obj <- ConstructNetwork(
        seurat_obj,
        soft_power = 4,
        tom_outdir = "TOM",
        tom_name = target_cell_type,
        overwrite_tom = TRUE
    )
    cat("  ConstructNetwork成功！\n")
}, error = function(e) {
    cat(paste0("  ConstructNetwork失败: ", e$message, "\n"))
    quit(status = 1)
})

cat("\n15. 保存测试结果...\n")
saveRDS(seurat_obj, "hdWGCNA_test_result.rds")
cat("  结果已保存到: hdWGCNA_test_result.rds\n")

cat("\n========== 测试完成！ ==========\n")
cat("  所有核心步骤均成功运行！\n")