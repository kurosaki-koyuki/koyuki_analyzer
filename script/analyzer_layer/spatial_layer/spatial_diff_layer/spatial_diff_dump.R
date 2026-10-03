#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# =============================================================================
# 空转「差异分析」按需取数 dump 脚本（独立工具，**不是构建脚本**）
# -----------------------------------------------------------------------------
# 与 spatial_violin_dump.R 的分工 / 为什么**必须新写**一个：
#   · 小提琴 dump 一次只 dump **一个基因**（`genes_file` 且上限 20），而每次 readRDS
#     实测 ≈5.5 s ⇒ 全基因差异分析（22,426 个基因）按那个口径要 readRDS 两万多次，
#     完全不可行；
#   · 本脚本**一次 readRDS**，把**参与样本**的基因×spot 计数矩阵（`Spatial` assay 的
#     **counts 层**）整块 dump 出来，交给 Python 侧 (`SpatialDiffAnalysis`) 装 `AnnData`
#     并跑继承自单细胞的 Mann-Whitney U 统计（**统计不在本脚本里**）。
#
# ★ 逐条照抄 spatial_violin_dump.R 已验证的纪律（同目录、同一套写法）：
#   1) 参数解析：位置参 + 具名选项混合、选项可出现在任意位置；--samples a,b,c
#   2) `<rds_path> / <out_dir> / <dataset_id>` 全 ASCII 断言（不做任何兜底）
#   3) 必须包（Seurat / jsonlite）检查，缺包直接给机器可读 JSON + 非零退出
#   4) Idents(obj) <- obj@meta.data[["seurat_clusters"]]（含 droplevels）——M1 的 .rds 里
#      Idents 仍是样本名（merge 遗留），照抄这条，保证与其它空转脚本同一套"对象状态"口径
#      （本脚本不按 Idents 分组，属于纪律一致性而非功能需要，特此说明）
#   5) pass_qc 过滤（与图集/表达量图口径一致：不 QC 通过的 spot 一律不进统计）
#   6) --samples 过滤（**显式按列下标子集**，不用 subset 表达式求值，避坑）；
#      请求的样本在数据里不存在 ⇒ **不硬失败**，放进 samples_missing 后继续
#   7) **绝不交互**：options(menu.graphics=FALSE)、无 readline/menu/file.choose/setwd
#   8) 失败一律 cat("##SPATIAL_DIFF_RESULT##{...ok:false...}") + quit(status=1)
#   9) 返回给 Python 的字符串**全 ASCII**（见 .ascii_scalar 的说明）
#
# CLI（冻结）：
#   Rscript spatial_diff_dump.R <rds_path> <out_dir> <dataset_id> [--samples a,b,c]
#     out_dir    : **数据集输出根**（= OUTPUT/<dataset_id>）；
#                   本脚本在其下建 08_GeneOnDemand/_diff/（**只写这一个新增子目录**）
#     --samples  : 可选；逗号分隔样本名（orig.ident）。**逗号会被当作分隔符**
#                  （与 spatial_violin_dump.R / spatial_gene_expression.R 口径完全一致）。
#                  不传 = 全部样本（QC 通过者）。
#
# -----------------------------------------------------------------------------
# 输出格式（**由 W3 决定并在 Python 侧同一口径读取**）
# -----------------------------------------------------------------------------
#   08_GeneOnDemand/_diff/
#     genes.txt            每行一个基因，顺序 = 每个 .mtx 的**行序**（全样本共用一份）
#     <sample>.mtx         MatrixMarket `coordinate real general`，**行 = 基因、列 = spot**，
#                          只写非零元（原始 counts，整数）；列序 = 对应 <sample>.obs.csv 的行序
#     <sample>.obs.csv     表头 `spot,sample,cluster,cell_type`（列序 = .mtx 的列序）
#
# ★★ 为什么是**稀疏矩阵**而不是「非零长表 CSV」、更不是「dense 宽表 CSV」：
#   · 真实规模：QC 后 37,672 spot × 22,426 基因（`docs/features/spatial_algo_design_w3.md`
#     §3.5；19 个样本）。每 spot 约 3,000 检出基因 ⇒ 全量非零 ≈1.13 亿。
#   · dense 宽表：每样本 ~2,000 spot × 22,426 基因 ≈ 4,500 万个数字，其中 >99.5% 是 0；
#     单样本就要几百 MB 文本，Python 侧还要再吃掉一份 dense float64（≈360 MB/样本），
#     与"我们只需要非零计数"完全背离 ⇒ **绝不使用**。
#   · 非零长表 `spot,gene,count`：每行约 35–40 B（barcode 18 + 基因名 10–15 + 计数 + 分隔符），
#     1.13 亿行 ≈ **4 GB**（19 样本），且 Python 要解析 1.13 亿行文本。
#   · 稀疏三件套：`.mtx` 每非零一行 `i j x`（≈10–14 B），单样本 59–127 MB、
#     19 样本合计 ≈**1.19 GB** —— 与数据集里**原始 10x `<GSM>_matrix.mtx` 的体积台账完全同量级**
#     （`docs/features/spatial_data_storage_recon_ledger.md`：19 个 .mtx 合计 1,187,229,760 B），
#     因为它就是同一份"gene × spot 稀疏整数矩阵"。比长表小 ~2.5 倍，且
#     `scipy.io.mmread` 直接给出稀疏矩阵，**不需要**先读成 dense 再稀疏化。
#   · 中间产物在 Python 装完 AnnData 后**默认删除**（`SpatialDiffAnalysis.keep_dump_files`），
#     所以稳态占用 ≈0；峰值 ≈ 选中样本数 × ~100 MB。
#
# 返回给 Python 的 JSON（**最后一行**，前缀 ##SPATIAL_DIFF_RESULT##）：
#   {"ok":true,"run_id":"...","samples_used":[...],"samples_missing":[...],
#    "genes_n":N,"spots_n":N,"layer_used":"...","out_files":{"genes_txt":"...",
#    "obs_csv":{"<sample>":"..."},"mtx":{"<sample>":"..."},"nnz_per_sample":{...},...}, ...}
#   失败：{"ok":false,"error":"..."} + quit(status=1)
#
# 本文件**字符串字面量与标识符均为 ASCII**（中文只在注释里），以把跨编码风险降到最低。
# =============================================================================

suppressPackageStartupMessages({
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    cat("##SPATIAL_DIFF_RESULT##{\"ok\":false,\"error\":\"R package 'Seurat' not available\"}\n")
    quit(status = 3, save = "no")
  }
  library(Seurat)
})

options(menu.graphics = FALSE)   # 双保险：即便被交互式调用也不弹图形菜单

# -----------------------------------------------------------------------------
# 只读、不交互的小工具（与 spatial_violin_dump.R 逐字同款）
# -----------------------------------------------------------------------------
.is_ascii <- function(p) is.character(p) && length(p) == 1L && !is.na(p) && !grepl("[^ -~]", p)

# 样本名会被当作**文件名**使用（<sample>.mtx / <sample>.obs.csv），字符集必须收窄
.is_safe_name <- function(s) {
  is.character(s) && length(s) == 1L && !is.na(s) && grepl("^[A-Za-z0-9][A-Za-z0-9_.-]*$", s)
}

# ★ ASCII 化：返回给 Python 的字符串**必须是全 ASCII**（需求硬约束）。
#   实现：任何非 ASCII 的**取值**（样本名等）用 iconv 转写成 ASCII（不可转写的字符丢成 "?"）；
#   这一步顺带解决 Windows 上 R 的 toJSON 按 **native 编码**输出、而 Python 侧按 utf-8
#   解码的跨编码风险：一旦全 ASCII，任何一侧按哪种编码解码都得到同一串字节。
#   ⚠ 只作用于 JSON 载荷，**落盘 CSV / genes.txt 的原值一律保持 UTF-8 原样**
#     （cell_type 等注释不许被改写）。
.ascii_scalar <- function(x) {
  x <- as.character(x)
  bad <- is.na(x) | !grepl("^[ -~]*$", x)
  if (any(bad)) {
    conv <- suppressWarnings(iconv(x[bad], from = "UTF-8", to = "ASCII//TRANSLIT"))
    conv[is.na(conv)] <- "?"
    conv <- gsub("[^ -~]", "?", conv)
    x[bad] <- conv
  }
  x
}
.ascii_vec <- function(v) I(.ascii_scalar(v))

# JSON 输出：ok=TRUE 走完整结果（跑 .ascii_scalar 兜底），ok=FALSE 结构极小、**不做任何
# 改写**（缺包那两条硬编码错误字符串本身就是 ASCII）。
.emit_json <- function(obj, ok = TRUE) {
  if (isTRUE(ok)) {
    obj <- rapply(obj, .ascii_scalar, classes = "character", how = "replace")
  }
  cat("##SPATIAL_DIFF_RESULT##",
      jsonlite::toJSON(obj, auto_unbox = TRUE, null = "null", digits = 6), "\n", sep = "")
}

.fail <- function(msg, code = 1L) {
  # 硬失败：**不抛异常给调用栈**，而是打印机器可读结果后以非零码退出
  # （需求冻结：失败一律 quit(status=1)）
  .emit_json(list(ok = FALSE, error = msg), ok = FALSE)
  quit(status = code, save = "no")
}

# 稀疏矩阵非零个数（异常/不支持时返回 -1，只做诊断用，不参与业务判断）
.nnz_of <- function(m) {
  tryCatch({
    if (inherits(m, "sparseMatrix") && ("x" %in% slotNames(m))) length(m@x) else sum(m != 0)
  }, error = function(e) -1L)
}

# -----------------------------------------------------------------------------
# 0. 参数解析
# -----------------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
.USAGE_DIFF <- paste0(
  "usage: Rscript spatial_diff_dump.R <rds_path> <out_dir> <dataset_id> ",
  "[--samples GSM7596587,GSM7596588]\n")

# 位置参数 + 具名选项混合解析：**选项可出现在任意位置**
rds_path <- NULL; out_dir <- NULL; dataset_id <- NULL
samples_arg <- NULL
.i <- 1L
while (.i <= length(args)) {
  .a <- args[.i]
  if (identical(.a, "--samples")) {
    if (.i + 1L > length(args)) { cat(.USAGE_DIFF); quit(status = 2, save = "no") }
    .raw_s <- trimws(strsplit(args[.i + 1L], ",", fixed = TRUE)[[1]])
    samples_arg <- .raw_s[nzchar(.raw_s)]
    if (length(samples_arg) == 0L) samples_arg <- NULL
    .i <- .i + 2L; next
  }
  if (grepl("^--", .a)) {
    cat("unknown option: ", .a, "\n", sep = "")
    cat(.USAGE_DIFF); quit(status = 2, save = "no")
  }
  if (is.null(rds_path))        rds_path   <- .a
  else if (is.null(out_dir))    out_dir    <- .a
  else if (is.null(dataset_id)) dataset_id <- .a
  else { cat("too many positional arguments\n"); cat(.USAGE_DIFF); quit(status = 2, save = "no") }
  .i <- .i + 1L
}
if (is.null(rds_path) || is.null(out_dir) || is.null(dataset_id)) {
  cat(.USAGE_DIFF)
  quit(status = 2, save = "no")
}

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  .emit_json(list(ok = FALSE, error = "R package 'jsonlite' not available"), ok = FALSE)
  quit(status = 3, save = "no")
}

# ---- 硬安全要求：路径必须全 ASCII（不做兜底）----
if (!.is_ascii(out_dir)) {
  .fail("out_dir contains non-ASCII characters; refusing to run (would risk R interactive prompt / rpy2 hang)")
}
if (!.is_ascii(rds_path)) {
  .fail("rds_path contains non-ASCII characters; refusing to run")
}
if (!.is_ascii(dataset_id)) {
  .fail("dataset_id contains non-ASCII characters; refusing to run")
}
if (!is.null(samples_arg) && !all(grepl("^[ -~]*$", samples_arg))) {
  .fail("--samples contains non-ASCII characters; refusing to run (sample ids are ASCII in this dataset)")
}
if (!file.exists(rds_path)) {
  .fail(paste0("rds not found: ", rds_path))
}

t_start <- Sys.time()
run_id <- format(t_start, "%Y%m%d-%H%M%S")

# -----------------------------------------------------------------------------
# 1. 输出目录（先建再断言存在；**绝不依赖 R 的交互式建目录**）
# -----------------------------------------------------------------------------
.od_root <- file.path(out_dir, "08_GeneOnDemand")
.diff_dir <- file.path(.od_root, "_diff")
dir.create(.diff_dir, showWarnings = FALSE, recursive = TRUE)
if (!dir.exists(.diff_dir)) {
  .fail(paste0("cannot create diff dump dir: ", .diff_dir))
}

# -----------------------------------------------------------------------------
# 2. 一次 readRDS + Idents 修复 + pass_qc + 样本过滤（**全是列下标运算**）
# -----------------------------------------------------------------------------
t_read0 <- Sys.time()
obj <- readRDS(rds_path)
readRDS_sec <- as.numeric(difftime(Sys.time(), t_read0, units = "secs"))

# 契约 §9.6：M1 的 .rds 里 Idents 仍是样本名（merge 遗留），必须显式重设
idents_fixed <- FALSE
if ("seurat_clusters" %in% colnames(obj@meta.data)) {
  obj@meta.data[["seurat_clusters"]] <- droplevels(obj@meta.data[["seurat_clusters"]])
  Idents(obj) <- obj@meta.data[["seurat_clusters"]]
  idents_fixed <- TRUE
}

if (!"orig.ident" %in% colnames(obj@meta.data)) {
  .fail("meta.data has no 'orig.ident' column; cannot split spots by sample")
}
meta <- obj@meta.data
n_spots_raw <- ncol(obj)
if (is.null(n_spots_raw) || n_spots_raw < 1L) {
  .fail("the object has zero spots")
}
.cells_all <- colnames(obj)
.sample_of  <- as.character(meta[["orig.ident"]])
if (length(.sample_of) != n_spots_raw) {
  .fail("meta.data row count does not match the number of spots")
}

# 与图集 / 表达量图一致：只在 QC 通过的 spot 上做统计
spots_filtered <- FALSE
if ("pass_qc" %in% colnames(meta)) {
  .keep_qc_mask <- seq_len(n_spots_raw) %in% which(meta[["pass_qc"]])
  spots_filtered <- any(!.keep_qc_mask)
} else {
  .keep_qc_mask <- rep(TRUE, n_spots_raw)
}
if (!any(.keep_qc_mask)) {
  .fail("no spot passed QC (pass_qc is all FALSE)")
}

n_samples_available <- length(unique(.sample_of[.keep_qc_mask]))
samples_requested <- if (is.null(samples_arg)) character(0) else as.character(samples_arg)
.avail <- unique(.sample_of[.keep_qc_mask])
samples_used <- if (length(samples_requested) > 0L) {
  intersect(samples_requested, .avail)
} else {
  .avail
}
# ★ 与小提琴 dump 的口径一致：缺失样本**不硬失败**，如实记进 samples_missing 后继续
samples_missing <- if (length(samples_requested) > 0L) setdiff(samples_requested, .avail) else character(0)
if (length(samples_used) == 0L) {
  .fail(paste0("no requested sample exists in the object: requested=[",
               paste(samples_requested, collapse = ","), "] | available=[",
               paste(.avail, collapse = ","), "]"))
}
# ★ 必须**逐元素**调用：`.is_safe_name()` 是**标量**断言（内部有 `length(s) == 1L` 守卫），
#   直接作用在向量上时它对整条向量只返回一个 FALSE（`length(s)==1L` 不成立）
#   ⇒ `samples_used[!f(samples_used)]` 会把**全部**样本都列为非法。
#   实测事故（2026-09-25 用户真机）：选 4 个样本时报
#   `sample name(s) cannot be used as file names ... : GSM7596590,GSM7596591,GSM7596592,GSM7596593`
#   —— 而 `GSM7596590` 完全符合 `[A-Za-z0-9_.-]`；错的不是样本名，是这个调用形态。
.bad_names <- samples_used[!vapply(samples_used, .is_safe_name, logical(1))]
if (length(.bad_names) > 0L) {
  .fail(paste0("sample name(s) cannot be used as file names (allowed: [A-Za-z0-9_.-], must start alnum): ",
               paste(.bad_names, collapse = ",")))
}

# 明确 print 出来，便于在 stdout 里直接看到"到底 dump 了哪些样本"
cat("[spatial_diff] samples_available =", n_samples_available,
    "| samples_requested =", if (length(samples_requested)) paste(samples_requested, collapse = ",") else "(all)",
    "| samples_used =", paste(samples_used, collapse = ","),
    "| samples_missing =", if (length(samples_missing)) paste(samples_missing, collapse = ",") else "(none)",
    "| spots(qc) =", sum(.keep_qc_mask), "| spots(raw) =", n_spots_raw, "\n")

# -----------------------------------------------------------------------------
# 3. **counts 层**（★ 绝不用 data 层；基类自己算 CP10K + log1p）
# -----------------------------------------------------------------------------
# ★ 为什么必须显式取 counts：空转 Seurat 对象的 `Spatial` assay 有 `counts`/`data` 两层，
#   `data` 是 LogNormalize 之后的表达；差异分析的原型契约要求**原始 counts**
#   （`docs/features/spatial_algo_design_w3.md:233` 记录了"两层不可混用"）。
# ★ 取法逐个试（本机实测 DefaultAssay = "Spatial"；`GetAssayData(slot=)` 在
#   SeuratObject >= 5 已 defunct ⇒ 必须 tryCatch 吃掉失败再试下一种）：
#     ① SeuratObject::LayerData(assay=<a>, layer="counts")        —— v5 首选
#     ② SeuratObject::GetAssayData(assay=<a>, layer="counts")     —— v5 另一种入口
#     ③ SeuratObject::GetAssayData(assay=<a>, slot="counts")      —— 老 v4 兜底
#   ⛔ **绝不回退到 data 层**：取不到 counts 就硬失败（错层的统计比失败更坏）。
assay_used <- ""
.counts_mat <- NULL
.layer_used <- ""
.assays_all <- tryCatch(as.character(Seurat::Assays(obj)), error = function(e) character(0))
.assay_order <- unique(c(Seurat::DefaultAssay(obj), "Spatial", "RNA", .assays_all))
.assay_order <- .assay_order[.assay_order %in% .assays_all]
if (length(.assay_order) == 0L) {
  .fail("cannot determine any assay name from the object")
}
.counts_try <- list()
for (.a in .assay_order) {
  .counts_try[[length(.counts_try) + 1L]] <- list(
    name = paste0("LayerData(assay='", .a, "',layer='counts')"),
    f = local({ aa <- .a; function() SeuratObject::LayerData(obj, assay = aa, layer = "counts") }))
  .counts_try[[length(.counts_try) + 1L]] <- list(
    name = paste0("GetAssayData(assay='", .a, "',layer='counts')"),
    f = local({ aa <- .a; function() SeuratObject::GetAssayData(obj, assay = aa, layer = "counts") }))
  .counts_try[[length(.counts_try) + 1L]] <- list(
    name = paste0("GetAssayData(assay='", .a, "',slot='counts')"),
    f = local({ aa <- .a; function() SeuratObject::GetAssayData(obj, assay = aa, slot = "counts") }))
}
for (.cand in .counts_try) {
  .m <- tryCatch(.cand$f(), error = function(e) {
    cat("[spatial_diff] counts layer via", .cand$name, "failed:", conditionMessage(e), "\n",
        file = stderr())
    NULL
  })
  if (!is.null(.m) && length(dim(.m)) == 2L && nrow(.m) > 0L && ncol(.m) > 0L) {
    .counts_mat <- .m
    .layer_used <- .cand$name
    assay_used <- sub("^[^(]*\\(assay='([^']*)'.*$", "\\1", .cand$name)
    break
  }
}
if (is.null(.counts_mat)) {
  .fail(paste0("cannot obtain the counts layer (tried ", length(.counts_try),
               " accessor(s) over assays [", paste(.assay_order, collapse = ","),
               "]); refusing to fall back to the normalized 'data' layer"))
}
if (is.null(colnames(.counts_mat)) || !identical(as.character(colnames(.counts_mat)), as.character(.cells_all))) {
  # 理论上不可能（同一对象）——一旦发生就是严重的对齐事故，必须显式失败，不许静默错位
  .fail("counts matrix columns are not aligned with the object cell names")
}
all_genes <- rownames(.counts_mat)
if (is.null(all_genes) || length(all_genes) == 0L) {
  all_genes <- rownames(obj)
}
if (is.null(all_genes) || length(all_genes) == 0L) {
  .fail("cannot obtain gene names (rownames) from the counts layer")
}
all_genes <- as.character(all_genes)

# 计数层的体检：只做**如实报告**（负值直接失败；非整数只大声留痕并写进 JSON）
.xs <- tryCatch({
  if (inherits(.counts_mat, "sparseMatrix") && ("x" %in% slotNames(.counts_mat))) {
    .counts_mat@x
  } else {
    as.numeric(.counts_mat[seq_len(min(length(.counts_mat), 100000L))])
  }
}, error = function(e) numeric(0))
counts_min <- if (length(.xs)) suppressWarnings(min(.xs, na.rm = TRUE)) else NA_real_
counts_max <- if (length(.xs)) suppressWarnings(max(.xs, na.rm = TRUE)) else NA_real_
counts_noninteger_n <- if (length(.xs)) as.integer(sum(abs(.xs - round(.xs)) > 1e-8, na.rm = TRUE)) else NA_integer_
if (length(.xs) && is.finite(counts_min) && counts_min < 0) {
  .fail("counts layer contains negative values -> this is not a raw counts layer")
}
if (length(counts_noninteger_n) && !is.na(counts_noninteger_n) && counts_noninteger_n > 0L) {
  cat("[spatial_diff] WARNING:", counts_noninteger_n,
      "non-integer value(s) found in the counts layer; expected raw integer counts\n",
      file = stderr())
}
cat("[spatial_diff] layer =", .layer_used,
    "| assay =", assay_used,
    "| dim =", paste(dim(.counts_mat), collapse = "x"),
    "| range = [", round(counts_min, 4), ",", round(counts_max, 4), "]\n")

# -----------------------------------------------------------------------------
# 4. genes.txt（全样本共用一份；行序 = 每个 .mtx 的行序）
# -----------------------------------------------------------------------------
f_genes <- file.path(.diff_dir, "genes.txt")
.con_g <- file(f_genes, "w", encoding = "UTF-8")
writeLines(all_genes, .con_g)
close(.con_g)
if (!file.exists(f_genes) || file.size(f_genes) < 2) {
  .fail(paste0("genes.txt not written or too small: ", f_genes))
}
n_all_genes <- length(all_genes)

# -----------------------------------------------------------------------------
# 5. 逐 spot 元数据（**逐字**按需求取；缺列一律降级成空串/NA，绝不崩）
# -----------------------------------------------------------------------------
.spot_all     <- as.character(.cells_all)
.cluster_all  <- if ("seurat_clusters" %in% colnames(meta)) as.character(meta[["seurat_clusters"]]) else rep("", n_spots_raw)
# ★ 本机实测：`.rds` 的 `cell_type` 列**存在但全 NA**（细胞注释产物其实在
#   OUTPUT/<ds>/_region_workbench/spots.csv 的 cell_type 列里）—— Python 侧会用
#   spots.csv 补（"spots.csv 有值就用它，为空再回退这里"）。NA 一律写空串。
.celltype_all <- if ("cell_type" %in% colnames(meta)) as.character(meta[["cell_type"]]) else rep("", n_spots_raw)
.cluster_all[is.na(.cluster_all)] <- ""
.celltype_all[is.na(.celltype_all)] <- ""
.spot_all[is.na(.spot_all)] <- ""

# -----------------------------------------------------------------------------
# 6. 逐样本写 `.mtx`（基因 × spot，稀疏三件套之一）+ `.obs.csv`
# -----------------------------------------------------------------------------
mtx_files    <- list()
obs_files    <- list()
nnz_map      <- list()
spots_map    <- list()
failed_samples <- list()
samples_empty  <- character(0)
n_spots_dumped <- 0L

for (s in samples_used) {
  ts <- Sys.time()
  .idx <- which(.keep_qc_mask & .sample_of == s)
  if (length(.idx) == 0L) {
    # QC 后该样本一个 spot 都没有 ⇒ 跳过（Python 侧会看到 samples_empty 并留痕）
    samples_empty <- c(samples_empty, s)
    cat("[spatial_diff] sample", s, "has zero QC-passed spots; skipped\n", file = stderr())
    next
  }
  .f_mtx <- file.path(.diff_dir, paste0(s, ".mtx"))
  .f_obs <- file.path(.diff_dir, paste0(s, ".obs.csv"))
  res <- tryCatch({
    sub <- .counts_mat[, .idx, drop = FALSE]
    # 基因顺序必须与 genes.txt 逐行一致（用同一份 rownames，且显式重设一次）
    rownames(sub) <- all_genes
    colnames(sub) <- .spot_all[.idx]
    if (!inherits(sub, "sparseMatrix")) {
      sub <- Matrix::Matrix(sub, sparse = TRUE)   # writeMM 只接受 sparseMatrix
    }
    Matrix::writeMM(sub, .f_mtx)
    if (!file.exists(.f_mtx) || file.size(.f_mtx) < 64) {
      stop("mtx not written (missing or suspiciously small): ", .f_mtx)
    }
    # 表头**逐字**：spot,sample,cluster,cell_type（顺序不许动；列序 = .mtx 的列序）
    # ★ 这里用 write.csv（需要时自动加引号）而不是 write.table(quote=FALSE)：
    #   `cell_type` 的取值域来自 `.rds` 的 meta.data，**无法证明**它不含逗号；
    #   pandas 侧能正确解析标准 CSV 引号 ⇒ 安全优先。
    od <- data.frame(spot = .spot_all[.idx],
                     sample = rep(s, length(.idx)),
                     cluster = .cluster_all[.idx],
                     cell_type = .celltype_all[.idx],
                     stringsAsFactors = FALSE)
    if (nrow(od) != ncol(sub)) {
      stop("obs rows (", nrow(od), ") != mtx columns (", ncol(sub), ")")
    }
    utils::write.csv(od, .f_obs, row.names = FALSE, fileEncoding = "UTF-8")
    if (!file.exists(.f_obs) || file.size(.f_obs) < 16) {
      stop("obs csv not written (missing or suspiciously small): ", .f_obs)
    }
    list(ok = TRUE, err = "", n = ncol(sub), nnz = .nnz_of(sub))
  }, error = function(e) {
    list(ok = FALSE, err = conditionMessage(e), n = 0L, nnz = -1L)
  })
  if (isTRUE(res$ok)) {
    mtx_files[[s]] <- normalizePath(.f_mtx, winslash = "/", mustWork = FALSE)
    obs_files[[s]] <- normalizePath(.f_obs, winslash = "/", mustWork = FALSE)
    nnz_map[[s]]   <- as.integer(res$nnz)
    spots_map[[s]] <- as.integer(res$n)
    n_spots_dumped <- n_spots_dumped + as.integer(res$n)
    cat("[spatial_diff] wrote:", s, "| spots =", res$n, "| nnz =", res$nnz, "|",
        round(as.numeric(difftime(Sys.time(), ts, units = "secs")), 2), "s\n")
  } else {
    # 单样本失败**不中断整批**（照 E4 精神）：如实记进 JSON，Python 侧留痕
    failed_samples[[s]] <- res$err
    cat("[spatial_diff] FAILED sample:", s, "|", res$err, "\n", file = stderr())
  }
}

# 一个样本都没成 ⇒ 硬失败，让 Python 侧拿到明确原因
if (length(mtx_files) == 0L) {
  .fail(paste0("no sample matrix produced: empty=[", paste(samples_empty, collapse = ","),
               "] errors=[",
               paste(vapply(names(failed_samples),
                            function(k) paste0(k, ":", failed_samples[[k]]), character(1)),
                     collapse = " | "),
               "]"))
}

# -----------------------------------------------------------------------------
# 7. 机器可读结果（**最后一行**，前缀 ##SPATIAL_DIFF_RESULT##）
# -----------------------------------------------------------------------------
elapsed <- as.numeric(difftime(Sys.time(), t_start, units = "secs"))
# ⚠ 下列向量一律用 I() 包住（见 .ascii_vec）：auto_unbox=TRUE 会把**长度为 1** 的向量
#   脱成标量，调用方必踩。具名 list（obs_csv / mtx 等）本身会序列化成对象，无需 I()。
result <- list(
  ok = TRUE,
  run_id = run_id,
  # ---- 冻结字段（与 violin dump 的字段风格一致）----
  samples_used = .ascii_vec(samples_used),
  samples_missing = .ascii_vec(samples_missing),
  genes_n = as.integer(n_all_genes),
  spots_n = as.integer(n_spots_dumped),
  layer_used = .layer_used,
  out_files = list(
    genes_txt = normalizePath(f_genes, winslash = "/", mustWork = FALSE),
    obs_csv = obs_files,
    mtx = mtx_files,
    nnz_per_sample = nnz_map,
    spots_per_sample = spots_map
  ),
  # ---- 排障用附加字段（不影响冻结字段的语义与顺序）----
  samples_available = as.integer(n_samples_available),
  samples_requested = .ascii_vec(samples_requested),
  samples_empty = .ascii_vec(samples_empty),
  diff_dir = .diff_dir,
  dataset_id = dataset_id,
  out_dir = out_dir,
  rds_path = rds_path,
  assays_available = .ascii_vec(.assays_all),
  assay_used = assay_used,
  counts_min = round(counts_min, 6),
  counts_max = round(counts_max, 6),
  counts_noninteger_n = counts_noninteger_n,
  n_spots_raw = as.integer(n_spots_raw),
  n_spots_qc = as.integer(sum(.keep_qc_mask)),
  spots_filtered_to_pass_qc = spots_filtered,
  idents_fixed = idents_fixed,
  samples_filtered = length(samples_requested) > 0L,
  failed_samples = if (length(failed_samples) == 0L) structure(list(), names = character(0)) else failed_samples,
  readRDS_sec = round(readRDS_sec, 2),
  elapsed_sec = round(elapsed, 2)
)
.emit_json(result, ok = TRUE)
quit(status = 0, save = "no")
