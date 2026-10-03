#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# =============================================================================
# M4「绘制区域」· 一次性导出脚本 —— 把「逐 spot 坐标 + 当前细胞类型」join 成一张小表
# -----------------------------------------------------------------------------
# 目的（契约 §13.1/§13.2/§13.6）：
#   App 目前**没有**"读逐 spot 细胞类型"的能力 —— `.rds` 里的 `cell_type` 列 100% 是 NA
#   （39,566 个全空，细胞类型从未写回 .rds）。细胞类型**只存在于**
#   OUTPUT/<ds>/07_CellTypeAnno/02_cell_type_annotation.csv。
#   而画布要"自绘散点、按 cell_type 着色、像素↔数据坐标可逆"（不能用图集 PNG），
#   所以需要把**坐标**与**细胞类型**离线 join 成一张小表，供 Python 侧离线使用（避免每次读 R）。
#
# 输出（契约 §13.6 冻结）：
#   OUTPUT/<ds>/_region_workbench/spots.csv
#   表头**逐字**： spot,sample,x,y,cluster,cell_type
#   · `cell_type` 缺失写**空串**（不写 `NA` 字面量）
#   · `x`/`y` 为数值
#   · **37,672 行** = QC 通过 spot 数
#
# CLI：
#   Rscript spatial_region_dump.R --rds <path> --ann <02_cell_type_annotation.csv> --out <spots.csv>
#
# ⚠ 硬安全（沿用 spatial_rpy2_recipe.md §5 的教训）：
#   · `--out` 必须**全 ASCII**，否则直接报错退出（非 ASCII 路径会让 R 弹交互式目录菜单，
#     在 rpy2 下变成无限循环 + GB 级失控日志）；
#   · 绝不交互：无 readline/menu/file.choose/setwd；缺包/缺文件一律 stop()；
#   · 只读 `.rds` 与 ann CSV，**不写**除 `--out` 以外的任何东西；
#     **不碰** `_figure_manifest.csv`、**不改** `07_CellTypeAnno/` 里的既有文件。
#
# 最后两行：一行带标记的 JSON、一行**裸 JSON**（两种解析风格都能用）。
# =============================================================================

suppressPackageStartupMessages({
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    cat("##SPATIAL_REGION_DUMP##{\"ok\":false,\"error\":\"R package 'Seurat' not available\"}\n")
    quit(status = 3, save = "no")
  }
  library(Seurat)
})

options(menu.graphics = FALSE)

.is_ascii <- function(p) is.character(p) && length(p) == 1L && !is.na(p) && !grepl("[^ -~]", p)

.fail <- function(msg, code = 2L) {
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    j <- jsonlite::toJSON(list(ok = FALSE, error = msg), auto_unbox = TRUE)
    cat("##SPATIAL_REGION_DUMP##", j, "\n", sep = "")
    cat(j, "\n", sep = "")
  } else {
    cat("##SPATIAL_REGION_DUMP##{\"ok\":false,\"error\":\"jsonlite unavailable\"}\n")
  }
  quit(status = code, save = "no")
}

# -----------------------------------------------------------------------------
# 0. 参数解析（位置无关的具名选项）
# -----------------------------------------------------------------------------
argv <- commandArgs(trailingOnly = TRUE)
.USAGE <- paste0("usage: Rscript spatial_region_dump.R --rds <path> --out <spots.csv> ",
                 "[--ann <02_cell_type_annotation.csv>]\n",
                 "  --ann 可选：不传（或文件不存在）时照常导出坐标，cluster/cell_type 两列写空串\n")
opt <- list()
i <- 1L
while (i <= length(argv)) {
  a <- argv[i]
  if (grepl("^--", a)) {
    key <- sub("^--", "", a)
    if (i + 1L > length(argv)) { cat(.USAGE); quit(status = 2, save = "no") }
    opt[[key]] <- argv[i + 1L]
    i <- i + 2L
  } else {
    i <- i + 1L
  }
}
if (is.null(opt$rds) || is.null(opt$out)) {
  cat(.USAGE)
  quit(status = 2, save = "no")
}
rds_path <- opt$rds
out_path <- opt$out
# ★ `--ann` 自 Phase-1 生产化起**可选**（契约 §14）：
#   有些数据集**没跑过 07_CellTypeAnno**，根本没有注释 CSV。那种情况下**照常导出坐标**，
#   只把 `cluster`/`cell_type` 两列写成空串 —— 画布仍然可用（只是没有现成颜色可依），
#   比"整个绘制区域功能不可用"好得多。
ann_requested <- !is.null(opt$ann) && nzchar(opt$ann)
ann_path <- if (ann_requested) opt$ann else NULL

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  cat("##SPATIAL_REGION_DUMP##{\"ok\":false,\"error\":\"R package 'jsonlite' not available\"}\n")
  quit(status = 3, save = "no")
}

# ---- 硬安全：路径断言（不做兜底）----
if (!.is_ascii(out_path)) {
  .fail("out path contains non-ASCII characters; refusing to run (risk of R interactive prompt / rpy2 hang)")
}
if (!.is_ascii(rds_path)) .fail("rds path contains non-ASCII characters; refusing to run")
if (!file.exists(rds_path)) .fail(paste0("rds not found: ", rds_path))

# ⚠ `--ann` 的两类问题**不再致命**（契约 §14：坐标本身仍然有用）：
#   · 非 ASCII —— 无法安全传给 R，按"没给注释"降级；
#   · 文件不存在 —— 同上。
#   两种都**在 stderr 留一行说明**（不静默），但**不失败退出**。
ann_usable <- FALSE
if (ann_requested) {
  if (!.is_ascii(ann_path)) {
    cat("[spatial_region_dump] NOTE: --ann path contains non-ASCII characters;",
        "degrading to NO annotation (coordinates still exported)\n", file = stderr())
  } else if (!file.exists(ann_path)) {
    cat("[spatial_region_dump] NOTE: --ann file not found ->", ann_path,
        "; degrading to NO annotation (coordinates still exported)\n", file = stderr())
  } else {
    ann_usable <- TRUE
  }
}

# -----------------------------------------------------------------------------
# 1. 从图像对象取逐 spot 坐标
# -----------------------------------------------------------------------------
# `GetTissueCoordinates(obj[[样本]])` 在 Seurat v5 上对 VisiumV2 返回 data.frame：
#   · 行名 = barcode（与 meta.data rownames 逐字相同 ⇒ 可精确 join）
#   · 列名随版本不同：可能是 x/y，也可能是 imagecol/imagerow
# 这里按**列名优先**取，并把最终用到的列名回报进 JSON —— 万一以后 Seurat 改列名，
# 从摘要里一眼能看出取错了，不会静默产出错坐标。
.extract_xy <- function(coords) {
  nm <- colnames(coords)
  if (is.null(nm)) nm <- character(0)
  lownm <- tolower(nm)
  # x: 优先字面 x / imagecol；y: 优先字面 y / imagerow
  xi <- which(lownm %in% c("x", "imagecol"))[1]
  yi <- which(lownm %in% c("y", "imagerow"))[1]
  used <- c(NA_character_, NA_character_)
  if (is.na(xi) || is.na(yi)) {
    # 退化：取前两个数值列
    num_idx <- which(vapply(coords, is.numeric, logical(1)))
    if (length(num_idx) < 2L) stop("cannot locate two numeric coordinate columns")
    xi <- num_idx[1]; yi <- num_idx[2]
  }
  used <- c(nm[xi], nm[yi])
  # barcode：优先行名；若行名是 1..n 那种序号，则退回第一个字符列
  spot <- rownames(coords)
  if (is.null(spot) || all(spot == as.character(seq_len(nrow(coords))))) {
    ci <- which(vapply(coords, function(z) is.character(z) || is.factor(z), logical(1)))[1]
    if (!is.na(ci)) spot <- as.character(coords[[ci]])
  }
  if (is.null(spot)) stop("cannot locate barcode (rownames and no character column)")
  out <- data.frame(spot = as.character(spot),
                    x = as.numeric(coords[[xi]]),
                    y = as.numeric(coords[[yi]]),
                    stringsAsFactors = FALSE)
  attr(out, "cols") <- used   # 把"实际用了哪两列"带出去，回报进 JSON 摘要
  out
}

t0 <- Sys.time()
obj <- readRDS(rds_path)
if (!"images" %in% slotNames(obj)) .fail("object has no @images slot; not a Visium object")
img_names <- names(obj@images)
if (length(img_names) == 0L) .fail("object has zero images")

# 只导出 **QC 通过**的 spot（契约 §13.6 要求 37,672 行 = QC 通过数）。
# `.rds` 里同时保留了被过滤掉的 1,894 个 spot，这里**排除**它们并把差额如实回报。
has_pass_qc <- "pass_qc" %in% colnames(obj@meta.data)
qc_cells <- if (has_pass_qc) colnames(obj)[which(obj@meta.data[["pass_qc"]])] else colnames(obj)
n_spots_raw <- ncol(obj)

parts <- list()
coord_cols_used <- character(0)
for (s in img_names) {
  coords <- GetTissueCoordinates(obj[[s]])
  dt <- .extract_xy(coords)
  coord_cols_used <- unique(c(coord_cols_used, attr(dt, "cols")))
  dt$sample <- s
  # 该样本 ∩ QC 通过
  keep <- dt$spot %in% qc_cells
  dt <- dt[keep, , drop = FALSE]
  parts[[s]] <- dt
}
dt_all <- do.call(rbind, parts)
if (is.null(dt_all) || nrow(dt_all) == 0L) .fail("no coordinate rows collected")

# -----------------------------------------------------------------------------
# 2. 与细胞类型 CSV 左连接（**以坐标行为准**）
#    ★ `--ann` 未传 / 不可用 / 读失败 ⇒ **降级为"无注释"**：两列写空串，**不失败退出**
#      （契约 §14：坐标本身仍然有用）。降级一律在 stderr 留一行，不静默。
# -----------------------------------------------------------------------------
ann_rows <- 0L
unmatched <- 0L
ann_provided <- FALSE
ann <- NULL
if (ann_usable) {
  ann <- tryCatch(
    utils::read.csv(ann_path, stringsAsFactors = FALSE, colClasses = "character"),
    error = function(e) NULL)
  if (is.null(ann) || !"spot" %in% colnames(ann)) {
    cat("[spatial_region_dump] NOTE: annotation csv unreadable or has no `spot` column ->",
        ann_path, "; degrading to NO annotation (coordinates still exported)\n", file = stderr())
    ann <- NULL
  }
}
if (ann_usable && !is.null(ann)) {
  ann_provided <- TRUE
  ann_rows <- nrow(ann)
  m <- match(dt_all$spot, ann$spot)
  unmatched <- sum(is.na(m))
  # 逐条把 unmatched 报到 stderr（不许静默丢）
  if (unmatched > 0L) {
    cat("[spatial_region_dump] WARNING: unmatched spots (no annotation row) =", unmatched,
        "; first 5:", paste(utils::head(dt_all$spot[is.na(m)], 5L), collapse = ","), "\n",
        file = stderr())
  }
  if ("cluster" %in% colnames(ann))   dt_all$cluster   <- ann[["cluster"]][m]
  if ("cell_type" %in% colnames(ann)) dt_all$cell_type <- ann[["cell_type"]][m]
}
if (!"cluster" %in% colnames(dt_all))   dt_all$cluster   <- NA_character_
if (!"cell_type" %in% colnames(dt_all)) dt_all$cell_type <- NA_character_
# 缺失（含"无注释"降级）一律写**空串**（契约要求，不写 NA 字面量）
dt_all$cluster[is.na(dt_all$cluster)] <- ""
dt_all$cell_type[is.na(dt_all$cell_type)] <- ""
dt_all <- dt_all[, c("spot", "sample", "x", "y", "cluster", "cell_type"), drop = FALSE]

# -----------------------------------------------------------------------------
# 3. 落盘（表头**逐字**不带引号）
# -----------------------------------------------------------------------------
dir.create(dirname(out_path), showWarnings = FALSE, recursive = TRUE)
if (!dir.exists(dirname(out_path))) .fail(paste0("cannot create output dir: ", dirname(out_path)))
con <- file(out_path, "w", encoding = "UTF-8")
writeLines("spot,sample,x,y,cluster,cell_type", con)
# quote=FALSE：为了表头与 `cell_type` 逐字不带引号。
# 安全性依据：本表的取值域是我们自己的数据 —— spot=GSM前缀 barcode、sample=GSM 号、
# cluster=0..23、cell_type=9 个 signature 名，**均不含逗号/引号/换行**。
utils::write.table(dt_all, con, sep = ",", row.names = FALSE, col.names = FALSE,
                   quote = FALSE, na = "")
close(con)

if (!file.exists(out_path) || file.size(out_path) < 16) {
  .fail(paste0("output csv not written or too small: ", out_path))
}

# -----------------------------------------------------------------------------
# 4. JSON 摘要
# -----------------------------------------------------------------------------
summ <- list(
  ok = TRUE,
  rows = nrow(dt_all),
  samples = length(unique(dt_all$sample)),
  unmatched = as.integer(unmatched),
  out = out_path,
  out_bytes = as.numeric(file.size(out_path)),
  # ---- 注释状态（契约 §14：把"没给注释"与"给了但没匹配上"分清楚）----
  #   ann_requested = 命令行给了 --ann
  #   ann_provided  = 注释**真的被加载并用上了**（文件不存在/不可读/非 ASCII 一律 false）
  #   ann_rows      = 注释 CSV 的行数（未用上时为 0）
  #   unmatched     = 坐标行里没匹配到注释的条数（未用注释时恒为 0）
  #   cell_type_empty = 空 cell_type 的条数 —— 无注释模式下它 == rows，一眼可辨
  ann_requested = ann_requested,
  ann_provided = ann_provided,
  ann_rows = as.integer(ann_rows),
  # ---- 其余透明度字段 ----
  n_images = length(img_names),
  spots_in_object = n_spots_raw,
  spots_pass_qc = length(qc_cells),
  excluded_not_pass_qc = as.integer(n_spots_raw - length(qc_cells)),
  cell_type_empty = as.integer(sum(!nzchar(dt_all$cell_type))),
  coord_cols = I(as.character(coord_cols_used)),
  elapsed_sec = round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 2)
)
j <- jsonlite::toJSON(summ, auto_unbox = TRUE, null = "null", digits = 8)
cat("##SPATIAL_REGION_DUMP##", j, "\n", sep = "")
cat(j, "\n", sep = "")     # 裸 JSON 作为最后一行，兼容"直接 json.loads 最后一行"的调用方
quit(status = 0, save = "no")
