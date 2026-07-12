rm(list = ls())

cat("========== 开始测试hdWGCNA环境（简化版）==========\n")

cat("1. 加载必需的包...\n")
required_packages <- c("WGCNA", "hdWGCNA", "tidyverse", "Seurat")
for (pkg in required_packages) {
    if (!require(pkg, character.only = TRUE)) {
        cat(paste0("  包 ", pkg, " 未安装\n"))
        quit(status = 1)
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
    scRNA <- readRDS(seurat_path)
    cat(paste0("  加载成功！细胞数: ", ncol(scRNA), ", 基因数: ", nrow(scRNA), "\n"))
} else {
    cat("  文件不存在！\n")
    quit(status = 1)
}

cat("\n4. 筛选AC-like Malignant细胞...\n")
scRNA <- subset(scRNA, subset = `Celltype (major-lineage)` == "AC-like Malignant")
cat(paste0("  AC-like Malignant细胞数: ", ncol(scRNA), ", 基因数: ", nrow(scRNA), "\n"))

cat("\n5. 限制基因数量为1000...\n")
all_genes <- rownames(scRNA)
if (length(all_genes) > 1000) {
    scRNA <- scRNA[all_genes[1:1000], ]
}
cat(paste0("  限制后基因数: ", nrow(scRNA), "\n"))

cat("\n6. 创建干净的注释列...\n")
scRNA$wgcna_type_fixed <- factor(scRNA@meta.data[["Celltype (major-lineage)"]])
scRNA$wgcna_sample_fixed <- factor(scRNA@meta.data[["Sample"]])

cat("\n7. 运行SetupForWGCNA...\n")
seurat_obj <- SetupForWGCNA(
    scRNA,
    gene_select = "fraction",
    fraction = 0.05,
    wgcna_name = "GSE102130_test"
)
cat("  SetupForWGCNA成功！\n")

cat("\n8. 运行MetacellsByGroups...\n")
seurat_obj <- MetacellsByGroups(
    seurat_obj = seurat_obj,
    group.by = "wgcna_type_fixed",
    reduction = 'pca',
    k = 10,
    max_shared = 5,
    ident.group = "wgcna_type_fixed",
    min_cells = 20
)
cat("  MetacellsByGroups成功！\n")

cat("\n9. 运行NormalizeMetacells...\n")
seurat_obj <- NormalizeMetacells(seurat_obj)
cat("  NormalizeMetacells成功！\n")

cat("\n10. 运行SetDatExpr...\n")
seurat_obj <- SetDatExpr(
    seurat_obj,
    group_name = "AC-like Malignant",
    group.by = "wgcna_type_fixed",
    assay = 'RNA',
    slot = 'data'
)
datExpr <- GetDatExpr(seurat_obj)
cat(paste0("  分析基因数: ", nrow(datExpr), "\n"))

cat("\n11. 运行TestSoftPowers（简化范围）...\n")
seurat_obj <- TestSoftPowers(
    seurat_obj,
    powers = c(seq(1, 10, by = 1)),
    networkType = 'unsigned'
)
cat("  TestSoftPowers成功！\n")

power_table <- GetPowerTable(seurat_obj)
cat("  软阈值表:\n")
print(head(power_table))

cat("\n12. 运行ConstructNetwork（简化参数）...\n")
seurat_obj <- ConstructNetwork(
    seurat_obj,
    soft_power = 4,
    tom_outdir = "TOM_test",
    tom_name = "AC-like",
    overwrite_tom = TRUE
)
cat("  ConstructNetwork成功！\n")

cat("\n13. 保存测试结果...\n")
saveRDS(seurat_obj, "hdWGCNA_test_result_simple.rds")
cat("  结果已保存到: hdWGCNA_test_result_simple.rds\n")

cat("\n========== 测试完成！ ==========\n")