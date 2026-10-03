#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# =============================================================================
# 空转「小提琴图」逐 spot 表达量 dump 脚本（独立工具，**不是构建脚本**）
# -----------------------------------------------------------------------------
# 与 spatial_gene_expression.R 的分工：
#   · spatial_gene_expression.R = 按需**出表达量图**（PNG/PDF 落在
#     08_GeneOnDemand/<基因>/）；本脚本**一张图都不画**，只把"逐 spot 的表达量 + 注释"
#     落成 CSV，交给 Python 侧（SpatialViolinAnalysis）用 seaborn/matplotlib 画小提琴图。
#   · 为什么要走 R：表达量必须与表达量图**同一层**（normalized data 层），只有 R 侧
#     能保证这一点；Python 侧不持有 .rds，也没有 adata。
#
# ★ 逐条照抄 spatial_gene_expression.R 已验证的纪律（同目录、同一套写法）：
#   1) 参数解析：位置参 + 具名选项混合、选项可出现在任意位置；--samples a,b,c
#   2) --rds/--out_dir/--dataset_id/--genes_file 全 ASCII 断言（不做任何兜底）
#   3) 必须包（Seurat / jsonlite）检查，缺包直接给机器可读 JSON + 非零退出
#   4) 基因名 sanitize（^[A-Za-z0-9][A-Za-z0-9_.-]*$）+ 上限 20（做文件名/第二道闸）
#   5) Idents(obj) <- obj@meta.data[["seurat_clusters"]]（含 droplevels）——M1 的 .rds 里
#      Idents 仍是样本名（merge 遗留），不修的话任何按 Idents 分组的东西会静默退化成"按样本"
#   6) pass_qc 过滤（与图集口径一致：图集里的 gene_spatial 也只在 QC 通过的 spot 上画）
#   7) --samples 过滤（用**显式 cells=**，不用 subset 表达式求值，避坑）
#   8) **绝不交互**：options(menu.graphics=FALSE)、无 readline/menu/file.choose/setwd
#   9) 失败一律 cat("##SPATIAL_VIOLIN_RESULT##{...ok:false...}") + quit(status=1)
#  10) 返回给 Python 的字符串**全 ASCII**（见文件末 .ascii_json 的说明）
#
# CLI（冻结）：
#   Rscript spatial_violin_dump.R <rds_path> <out_dir> <dataset_id> <genes_file> [--samples a,b,c]
#     genes_file : 纯文本，**每行一个基因**（由 Python 侧写好 —— 不靠 argv 传长列表）
#     out_dir    : **数据集输出根**（= OUTPUT/<dataset_id>）；
#                   本脚本在其下建 08_GeneOnDemand/_violin/<基因>.csv
#     --samples  : 可选；逗号分隔样本名（orig.ident）。**逗号会被当作分隔符**
#                  （与 spatial_gene_expression.R 的 --samples 口径完全一致 —— 样本名若含
#                   逗号，无论选谁都无法用这个选项表达，这是冻结的口径）。
#                  ★ 与 GEA 的唯一差别（本脚本按需求放宽）：请求的样本名在数据里**不存在**时
#                    **不硬失败**，而是放进 JSON 的 samples_missing，用 samples_used（命中集）
#                   继续出图 —— 空间页左侧的样本清单可能包含尚未进绘图模式的样本。
#
# 输出：最后一行 cat() 一段**机器可读 JSON**（前缀 ##SPATIAL_VIOLIN_RESULT##）：
#   {"ok":true,"run_id":"YYYYMMDD-HHMMSS","n":N,"genes":[...],
#    "files":{"<gene>":"<abs path>",...},"cached":[...],
#    "samples_used":[...],"samples_available":M,"samples_missing":[...],
#    "not_found":[...],"available_genes_n":N}
#   失败：{"ok":false,"error":"..."} + quit(status=1)
#
# 缓存：<gene>.csv 已存在且**比 rds 新** ⇒ 跳过重算（省 ~5.5 s/次），基因名进 "cached"。
#
# 本文件**字符串字面量与标识符均为 ASCII**（中文只在注释里），以把跨编码风险降到最低。
# =============================================================================

suppressPackageStartupMessages({
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    cat("##SPATIAL_VIOLIN_RESULT##{\"ok\":false,\"error\":\"R package 'Seurat' not available\"}\n")
    quit(status = 3, save = "no")
  }
  library(Seurat)
})

options(menu.graphics = FALSE)   # 双保险：即便被交互式调用也不弹图形菜单

# -----------------------------------------------------------------------------
# 只读、不交互的小工具
# -----------------------------------------------------------------------------
.is_ascii <- function(p) is.character(p) && length(p) == 1L && !is.na(p) && !grepl("[^ -~]", p)

# 基因名做**文件名**使用，必须收窄字符集（Python 侧也会过滤，这里是第二道闸）
.is_safe_gene <- function(g) grepl("^[A-Za-z0-9][A-Za-z0-9_.-]*$", g)

# ★ ASCII 化：返回给 Python 的字符串**必须是全 ASCII**（需求硬约束）。
#   实现：任何非 ASCII 的**取值**（样本名等）用 iconv 转写成 ASCII（不可转写的字符丢成 "?"）；
#   这一步顺带解决 Windows 上 R 的 toJSON 按 **native 编码**（本机 = UTF-8，见实测
#   `Chinese (Simplified)_China.utf8`）输出、而 Python 侧按 utf-8 解码的跨编码风险：
#   一旦全 ASCII，任何一侧按哪种编码解码都得到同一串字节。
#   ⚠ 只作用于 JSON 载荷，**CSV 的原值一律保持 UTF-8 原样**（cell_type 等注释不许被改写）。
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
# 改写**（缺包那两条硬编码错误字符串本身就是 ASCII，保持与 GEA 逐字一致）。
.emit_json <- function(obj, ok = TRUE) {
  if (isTRUE(ok)) {
    obj <- rapply(obj, .ascii_scalar, classes = "character", how = "replace")
  }
  cat("##SPATIAL_VIOLIN_RESULT##",
      jsonlite::toJSON(obj, auto_unbox = TRUE, null = "null", digits = 6), "\n", sep = "")
}

.fail <- function(msg, code = 1L) {
  # 硬失败：**不抛异常给调用栈**，而是打印机器可读结果后以非零码退出
  # （需求冻结：失败一律 quit(status=1)）
  .emit_json(list(ok = FALSE, error = msg), ok = FALSE)
  quit(status = code, save = "no")
}

# -----------------------------------------------------------------------------
# 0. 参数解析
# -----------------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
.USAGE_VIOLIN <- paste0(
  "usage: Rscript spatial_violin_dump.R <rds_path> <out_dir> <dataset_id> <genes_file> ",
  "[--samples GSM7596587,GSM7596588]\n")

# 位置参数 + 具名选项混合解析：**选项可出现在任意位置**
rds_path <- NULL; out_dir <- NULL; dataset_id <- NULL; genes_file <- NULL
samples_arg <- NULL
.i <- 1L
while (.i <= length(args)) {
  .a <- args[.i]
  if (identical(.a, "--samples")) {
    if (.i + 1L > length(args)) { cat(.USAGE_VIOLIN); quit(status = 2, save = "no") }
    .raw_s <- trimws(strsplit(args[.i + 1L], ",", fixed = TRUE)[[1]])
    samples_arg <- .raw_s[nzchar(.raw_s)]
    if (length(samples_arg) == 0L) samples_arg <- NULL
    .i <- .i + 2L; next
  }
  if (grepl("^--", .a)) {
    cat("unknown option: ", .a, "\n", sep = "")
    cat(.USAGE_VIOLIN); quit(status = 2, save = "no")
  }
  if (is.null(rds_path))        rds_path   <- .a
  else if (is.null(out_dir))    out_dir    <- .a
  else if (is.null(dataset_id)) dataset_id <- .a
  else if (is.null(genes_file)) genes_file <- .a
  else { cat("too many positional arguments\n"); cat(.USAGE_VIOLIN); quit(status = 2, save = "no") }
  .i <- .i + 1L
}
if (is.null(rds_path) || is.null(out_dir) || is.null(dataset_id) || is.null(genes_file)) {
  cat(.USAGE_VIOLIN)
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
if (!file.exists(genes_file)) {
  .fail(paste0("genes_file not found: ", genes_file))
}

# -----------------------------------------------------------------------------
# 1. 读基因列表（每行一个；去空、去重保序）
# -----------------------------------------------------------------------------
genes_raw <- tryCatch(readLines(genes_file, encoding = "UTF-8", warn = FALSE),
                      error = function(e) character(0))
genes <- trimws(genes_raw)
genes <- genes[nzchar(genes)]
unsafe_genes <- genes[!.is_safe_gene(genes)]           # 非法字符（做文件名不安全）
genes <- genes[.is_safe_gene(genes)]
genes <- genes[!duplicated(genes)]
if (length(genes) == 0L) {
  .fail("no valid gene names after parsing genes_file")
}
# 上限 20（与 GEA 同一道闸；Python 侧也会拦截）
if (length(genes) > 20L) {
  .fail(paste0("too many genes (", length(genes), "); limit is 20"))
}

t_start <- Sys.time()
run_id <- format(t_start, "%Y%m%d-%H%M%S")

# -----------------------------------------------------------------------------
# 2. 输出目录（先建再断言存在；**绝不依赖 R 的交互式建目录**）
# -----------------------------------------------------------------------------
.od_root   <- file.path(out_dir, "08_GeneOnDemand")
.violin_dir <- file.path(.od_root, "_violin")
dir.create(.violin_dir, showWarnings = FALSE, recursive = TRUE)
if (!dir.exists(.violin_dir)) {
  .fail(paste0("cannot create violin dump dir: ", .violin_dir))
}

# -----------------------------------------------------------------------------
# 3. 一次 readRDS + Idents 修复 + pass_qc 过滤 + --samples 过滤 + data 层
# -----------------------------------------------------------------------------
t_read0 <- Sys.time()
obj <- readRDS(rds_path)
readRDS_sec <- as.numeric(difftime(Sys.time(), t_read0, units = "secs"))

rds_mtime <- tryCatch(as.numeric(file.info(rds_path)$mtime), error = function(e) NA_real_)

# 契约 §9.6：M1 的 .rds 里 Idents 仍是样本名（merge 遗留），必须显式重设
idents_fixed <- FALSE
if ("seurat_clusters" %in% colnames(obj@meta.data)) {
  obj@meta.data[["seurat_clusters"]] <- droplevels(obj@meta.data[["seurat_clusters"]])
  Idents(obj) <- obj@meta.data[["seurat_clusters"]]
  idents_fixed <- TRUE
}

# 与图集 / 表达量图一致：只在 QC 通过的 spot 上出图（这里是"出 CSV"）
n_spots_raw <- ncol(obj)
spots_filtered <- FALSE
if ("pass_qc" %in% colnames(obj@meta.data)) {
  keep <- colnames(obj)[which(obj@meta.data[["pass_qc"]])]
  if (length(keep) > 0L && length(keep) < n_spots_raw) {
    obj <- subset(obj, cells = keep)
    spots_filtered <- TRUE
  }
}

# ★ 样本子集（用户选择）。写法选**显式 cells=**，与 GEA 同款。
n_samples_available <- length(unique(as.character(obj@meta.data[["orig.ident"]])))
samples_requested <- if (is.null(samples_arg)) character(0) else as.character(samples_arg)
samples_used <- unique(as.character(obj@meta.data[["orig.ident"]]))   # 默认 = 全部（已过 QC）
samples_missing <- character(0)
samples_filtered <- FALSE
if (length(samples_requested) > 0L) {
  .avail <- unique(as.character(obj@meta.data[["orig.ident"]]))
  samples_used <- intersect(samples_requested, .avail)
  # ★ 与 GEA 的唯一差别：缺失样本**不硬失败**，如实记进 samples_missing 后继续
  samples_missing <- setdiff(samples_requested, .avail)
  if (length(samples_used) == 0L) {
    .fail(paste0("no requested sample exists in the object: requested=[",
                 paste(samples_requested, collapse = ","), "] | available=[",
                 paste(.avail, collapse = ","), "]"))
  }
  cl <- colnames(obj)[as.character(obj@meta.data[["orig.ident"]]) %in% samples_used]
  if (length(cl) == 0L) {
    .fail(paste0("no cells matched the requested samples: [",
                 paste(samples_used, collapse = ","), "]"))
  }
  obj <- subset(obj, cells = cl)
  samples_filtered <- TRUE
}

# 明确 print 出来，便于在 stdout 里直接看到"到底 dump 了哪些样本"
cat("[spatial_violin] samples_available =", n_samples_available,
    "| samples_requested =", if (length(samples_requested)) paste(samples_requested, collapse = ",") else "(all)",
    "| samples_used =", paste(samples_used, collapse = ","),
    "| samples_missing =", if (length(samples_missing)) paste(samples_missing, collapse = ",") else "(none)",
    "| spots =", ncol(obj), "\n")

# ---- 表达量矩阵：**与表达量图同一层**（normalized data）----
# ★ 本机实测（Seurat 5.5.0，GSE237183.rds）：DefaultAssay 是 **"Spatial"** 而不是 "RNA"，
#   且 `GetAssayData(obj, slot=)` 在 SeuratObject >= 5.0 已 **defunct**（不是 deprecated 警告，
#   是直接报错："The `slot` argument of `GetAssayData()` was deprecated ... and is now defunct"）。
#   ⇒ 三种取法逐个试，取到即可（需求原文："两种都试"）：
#     ① LayerData(obj, layer="data")                    —— v5 首选，走 DefaultAssay
#     ② GetAssayData(obj, assay="RNA", layer="data")    —— 兼容 assay 名真为 RNA 的数据集
#     ③ GetAssayData(obj, assay="RNA", slot="data")     —— 老 v4 兜底（v5 会报错，被 tryCatch 吃掉）
#   ⚠ 顺序刻意把 ① 放第一位：本机 DefaultAssay="Spatial"，用 ② 会直接失败。
.expr_layer <- ""
.expr_mat <- NULL
.expr_try <- list(
  list(name = "LayerData(layer='data')", f = function() SeuratObject::LayerData(obj, layer = "data")),
  list(name = "GetAssayData(assay='RNA',layer='data')",
       f = function() Seurat::GetAssayData(obj, assay = "RNA", layer = "data")),
  list(name = "GetAssayData(assay='RNA',slot='data')",
       f = function() Seurat::GetAssayData(obj, assay = "RNA", slot = "data"))
)
for (.cand in .expr_try) {
  .m <- tryCatch(.cand$f(), error = function(e) {
    cat("[spatial_violin] data layer via", .cand$name, "failed:", conditionMessage(e), "\n", file = stderr())
    NULL
  })
  if (!is.null(.m)) { .expr_mat <- .m; .expr_layer <- .cand$name; break }
}
if (is.null(.expr_mat)) {
  .fail("cannot obtain the normalized data layer (tried LayerData(layer='data') and GetAssayData(assay='RNA', layer/slot='data'))")
}
if (!identical(colnames(.expr_mat), colnames(obj))) {
  # 理论上不可能（同一对象），一旦发生就是严重的对齐事故 —— 必须显式失败，不许静默错位
  .fail("expression matrix columns are not aligned with the (filtered) object cell names")
}
# ⚠ range() 对 dgCMatrix 直接报错（"only defined on a data frame with all numeric variables"），
#   而 ExpressionMatrix 在 v5 里就是 dgCMatrix ⇒ 显式取两者的 min/max 并 tryCatch，只做诊断打印
.mat_range <- tryCatch(range(.expr_mat), error = function(e) c(NA_real_, NA_real_))
cat("[spatial_violin] data layer =", .expr_layer,
    "| dim =", paste(dim(.expr_mat), collapse = "x"),
    "| range = [", round(.mat_range[1], 4), ",", round(.mat_range[2], 4), "]\n")

all_genes <- rownames(obj)
n_all_genes <- length(all_genes)

# meta 列（**逐字**按需求取；缺列一律降级成空串/NA，绝不崩）
meta_spot    <- colnames(obj)
meta_sample  <- as.character(obj@meta.data[["orig.ident"]])
meta_cluster <- if ("seurat_clusters" %in% colnames(obj@meta.data))
                  as.character(obj@meta.data[["seurat_clusters"]]) else rep("", ncol(obj))
# cell_type 缺失 ⇒ 空串（需求）。★ 本机实测：该列**存在但全 NA**（细胞注释产物其实在
#   OUTPUT/<ds>/_region_workbench/spots.csv 的 cell_type 列里）—— Python 侧会用 spots.csv 补，
#   这里按需求"该列不存在就写空串"的同款口径，NA 也写空串（NA 进 CSV 会变字符串 "NA"）。
meta_celltype <- if ("cell_type" %in% colnames(obj@meta.data))
                   as.character(obj@meta.data[["cell_type"]]) else rep("", ncol(obj))
meta_celltype[is.na(meta_celltype)] <- ""

# -----------------------------------------------------------------------------
# 4. 逐基因写 CSV（硬安全要求：单基因失败不中断）
# -----------------------------------------------------------------------------
per_gene_files   <- list()
cached_genes     <- character(0)
written_genes    <- character(0)
not_found        <- character(0)
failed           <- list()

for (i in seq_along(genes)) {
  g <- genes[i]
  ts <- Sys.time()
  f_csv <- file.path(.violin_dir, paste0(g, ".csv"))
  if (!(g %in% all_genes)) {
    not_found <- c(not_found, g)
    cat("[spatial_violin] gene not found:", g, "\n", file = stderr())
    next
  }
  # 缓存：CSV 已存在且**比 rds 新** ⇒ 跳过重算
  if (file.exists(f_csv) && !is.na(rds_mtime) && !is.na(file.info(f_csv)$mtime) &&
      as.numeric(file.info(f_csv)$mtime) > rds_mtime) {
    cached_genes <- c(cached_genes, g)
    per_gene_files[[g]] <- f_csv
    cat("[spatial_violin] cached:", g, "\n")
    next
  }
  res <- tryCatch({
    expr <- as.numeric(.expr_mat[g, ])
    # 表头**逐字**：spot,sample,cluster,cell_type,expr（顺序不许动）
    df <- data.frame(spot = meta_spot,
                     sample = meta_sample,
                     cluster = meta_cluster,
                     cell_type = meta_celltype,
                     expr = expr,
                     stringsAsFactors = FALSE)
    # 空 cell_type 必须是**空串**而不是 NA
    df$cell_type[is.na(df$cell_type)] <- ""
    df$sample[is.na(df$sample)] <- ""
    df$cluster[is.na(df$cluster)] <- ""
    # 表达值理论上不该有 NA（log-normalized data 层）；真出现就写 0 并留痕，别把 NA 写进 CSV
    n_na <- sum(is.na(df$expr))
    if (n_na > 0L) {
      cat("[spatial_violin] WARNING:", g, "has", n_na, "NA expression value(s); replaced with 0\n",
          file = stderr())
      df$expr[is.na(df$expr)] <- 0
    }
    write.csv(df, f_csv, row.names = FALSE, fileEncoding = "UTF-8")
    if (!file.exists(f_csv) || file.size(f_csv) < 16) {
      stop("csv not written (missing or suspiciously small): ", f_csv)
    }
    list(ok = TRUE, err = "", n = nrow(df))
  }, error = function(e) {
    list(ok = FALSE, err = conditionMessage(e), n = 0L)
  })
  if (isTRUE(res$ok)) {
    written_genes <- c(written_genes, g)
    per_gene_files[[g]] <- f_csv
    cat("[spatial_violin] wrote:", g, "| rows =", res$n, "|",
        round(as.numeric(difftime(Sys.time(), ts, units = "secs")), 2), "s\n")
  } else {
    failed[[g]] <- res$err
    cat("[spatial_violin] FAILED:", g, "|", res$err, "\n", file = stderr())
  }
}

# 一个基因都没成（且不是"全不存在"）⇒ 硬失败，让 Python 侧拿到明确原因
if (length(per_gene_files) == 0L) {
  .fail(paste0("no violin csv produced: not_found=[", paste(not_found, collapse = ","),
               "] errors=[",
               paste(vapply(names(failed), function(k) paste0(k, ":", failed[[k]]), character(1)),
                     collapse = " | "),
               "]"))
}

# -----------------------------------------------------------------------------
# 5. 机器可读结果（**最后一行**，前缀 ##SPATIAL_VIOLIN_RESULT##）
# -----------------------------------------------------------------------------
elapsed <- as.numeric(difftime(Sys.time(), t_start, units = "secs"))
# files：gene -> 绝对路径（jsonlite 对**具名 list** 会输出对象；空名字不可能出现，
#   因为 genes 已 sanitize 过）。用 I() 保证长度 1 时也是对象而不是被 auto_unbox 脱形。
files_map <- as.list(vapply(per_gene_files, function(p) normalizePath(p, winslash = "/", mustWork = FALSE),
                            character(1)))
result <- list(
  ok = TRUE,
  run_id = run_id,
  n = length(genes),
  # 下列向量一律用 I() 包住：auto_unbox=TRUE 会把**长度为 1** 的向量脱成标量，调用方必踩
  genes = .ascii_vec(genes),
  files = files_map,
  cached = .ascii_vec(cached_genes),
  samples_used = .ascii_vec(samples_used),
  samples_available = n_samples_available,
  samples_missing = .ascii_vec(samples_missing),
  not_found = .ascii_vec(not_found),
  available_genes_n = n_all_genes,
  # ---- 排障用附加字段（不影响冻结字段的语义与顺序）----
  written = .ascii_vec(written_genes),
  dropped_unsafe_genes = .ascii_vec(unsafe_genes),
  dataset_id = dataset_id,
  out_dir = out_dir,
  violin_dir = .violin_dir,
  rds_path = rds_path,
  data_layer = .expr_layer,
  n_spots = ncol(obj),
  n_spots_raw = n_spots_raw,
  spots_filtered_to_pass_qc = spots_filtered,
  idents_fixed = idents_fixed,
  samples_requested = .ascii_vec(samples_requested),
  samples_filtered = samples_filtered,
  failed = if (length(failed) == 0L) structure(list(), names = character(0)) else failed,
  readRDS_sec = round(readRDS_sec, 2),
  elapsed_sec = round(elapsed, 2)
)
.emit_json(result, ok = TRUE)
quit(status = 0, save = "no")
