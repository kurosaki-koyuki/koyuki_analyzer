#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# =============================================================================
# M4「绘制区域」· 按 labels 重绘（**自绘版**，契约 §15.4b）
# -----------------------------------------------------------------------------
# 这是一个**傻脚本**：判定逻辑（点在多边形内、重叠、区域名）**全在 Python 侧**，
# R 只负责"给我逐 spot 标签 + 轮廓折线，我把图画出来"。
#
# ★★ 为什么**不再用 `SpatialDimPlot`**（2026-09-19 架构裁决，协调者实测认定）：
#   实测解出 `SpatialDimPlot` 的绘图空间 = **lowres 像素空间**（自校准系数 a=c=0.14211275
#   = `tissue_lowres_scalef`）。于是：
#     · `image.scale="hires"` 只换图像层、**不换点的坐标空间** ⇒ 高清图(1799×2000)比点云
#       (~540×600)大约 3.3 倍 ⇒ 图占满面板、点被挤到左上角一小簇；
#     · 组织片与 spot **在同一个 `GeomSpatial` 层**里 ⇒ **点摘不掉**（无点图做不出来）；
#     · 轮廓是数据坐标、点是绘图坐标 ⇒ **两个坐标系不一致**，轮廓必落在图外。
#   ⇒ 这三个坑是同一个根因，补丁打不赢。**改成我们自己用 ggplot2 画**，三个坑一次性消失：
#     · 底图：hires 原图，`annotation_raster(img, 0, w, 0, h)` —— 范围就是 **hires 像素空间**；
#     · 点/轮廓/标签：全部 `× tissue_hires_scalef`（**不再需要反解校准**）；
#     · 无点图 = **不画 `geom_point` 层**（天生正确，不用"把点参数置零"）。
#
# CLI（§15.4b）：
#   Rscript spatial_region_render.R --rds <p> --labels <region_labels.csv> --spots <spots.csv> \
#          --sample <sid> --out-dir <d> [--outline <outline.json>] [--no-spots] \
#          [--raw-root <ASCII 暂存目录>] [--dpi 300] [--width 8] [--height 7] \
#          [--point-size 1.3] [--no-flip-y]
#   region_labels.csv：表头**逐字** `spot,label`；**label 为空串 = NA**（未落入任何区域）
#   spots.csv        ：dump 的产物，表头 `spot,sample,x,y,cluster,cell_type`；**原始坐标**
#   outline.json     ：`segments`/`labels` 都是**原始数据坐标**；顶层可选 `default_style`
#
# 产物（全在 `--out-dir`，**绝不动图集**）：
#   Spatial_<样本>.png/.pdf          带点（+ 轮廓层）
#   SpatialNoSpots_<样本>.png/.pdf   不带点（仅当 --no-spots）：组织片 + 轮廓 + 注释
#
# 硬安全（沿用 spatial_rpy2_recipe.md §5 的教训）：
#   · `--out-dir` / `--rds` / `--labels` / `--spots` / `--outline` / `--raw-root` 必须**全 ASCII**
#     （非 ASCII 路径会让 R 弹交互式目录菜单 → 在 rpy2 下无限循环 + GB 级日志）；
#     `--raw-root` 非 ASCII 时**拒绝读**并降级，不冒这个险；
#   · 绝不交互：无 readline/menu/file.choose/setwd；缺包/缺文件一律 stop()；
#   · 落盘后**校验存在且 >512 B**（失败不静默）；
#   · 末尾打印**两行**：带标记的 JSON + 裸 JSON 最后一行（两种调用方都能解析）。
# =============================================================================

suppressPackageStartupMessages({
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    cat("##SPATIAL_REGION_RENDER##{\"ok\":false,\"error\":\"R package 'jsonlite' not available\"}\n")
    quit(status = 3, save = "no")
  }
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    cat("##SPATIAL_REGION_RENDER##{\"ok\":false,\"error\":\"R package 'Seurat' not available\"}\n")
    quit(status = 3, save = "no")
  }
  library(Seurat)
})

options(menu.graphics = FALSE)

.is_ascii <- function(p) is.character(p) && length(p) == 1L && !is.na(p) && !grepl("[^ -~]", p)

.fail <- function(msg, code = 2L) {
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    j <- jsonlite::toJSON(list(ok = FALSE, error = msg), auto_unbox = TRUE)
    cat("##SPATIAL_REGION_RENDER##", j, "\n", sep = "")
    cat(j, "\n", sep = "")
  } else {
    cat("##SPATIAL_REGION_RENDER##{\"ok\":false,\"error\":\"jsonlite unavailable\"}\n")
  }
  quit(status = code, save = "no")
}

# -----------------------------------------------------------------------------
# ★ 读 CSV：**绕开 read.csv 的编码推断**（用户第②条乱码 bug 的真正根因）
# -----------------------------------------------------------------------------
# Windows 上 `read.csv()` 默认按**本地编码（本机 GBK）**解码，而 W2 写的 CSV 是 **UTF-8**
# ⇒ 中文在"读进来"那一刻就已经烂了。此时 showtext / cairo / 字体路径**全都白搭**。
# 更糟的是：烂串如果被送进 colour 位置，`col2rgb()` 会直接 `Unknown colour name` 崩掉。
# 所以这里按**字节**读、**显式声明** UTF-8、断言合法、断言字节级往返：
#   · `validUTF8()` 不成立 ⇒ **拒绝出图**（绝不"猜编码"然后交一张乱码图）；
#   · `charToRaw() == 原字节` ⇒ 证明字符串没有在往返中被改写。
enc_report <- list()
.read_table_utf8 <- function(path) {
  con <- file(path, open = "rb"); on.exit(close(con), add = TRUE)
  rb <- readBin(con, what = "raw", n = file.size(path))
  bom <- length(rb) >= 3L && identical(rb[1:3], as.raw(c(0xEF, 0xBB, 0xBF)))
  if (bom) rb <- rb[-(1:3)]
  txt <- rawToChar(rb)                 # 字节 -> 字符串（按字节原样）
  Encoding(txt) <- "UTF-8"             # ★ 明确声明：这些字节就是 UTF-8，不许按 GBK 解释
  if (!validUTF8(txt)) {
    .fail(paste0("input file is not valid UTF-8 (refusing to guess the encoding): ", path))
  }
  if (!identical(charToRaw(txt), rb)) {
    .fail(paste0("UTF-8 byte round-trip mismatch (text was re-encoded while reading): ", path))
  }
  enc_report[[length(enc_report) + 1L]] <<- list(file = basename(path), bom = bom,
                                                 bytes = length(rb), utf8_ok = TRUE)
  utils::read.csv(text = txt, stringsAsFactors = FALSE, colClasses = "character")
}

# -----------------------------------------------------------------------------
# 0. 参数解析（位置无关 + 支持开关型选项）
# -----------------------------------------------------------------------------
argv <- commandArgs(trailingOnly = TRUE)
.USAGE <- paste0(
  "usage: Rscript spatial_region_render.R --rds <p> --labels <region_labels.csv> ",
  "--spots <spots.csv> --sample <sid> --out-dir <d>\n",
  "       [--outline <outline.json>] [--no-spots] [--raw-root <dir>] [--dpi 300]\n",
  "       [--width 8] [--height 7] [--point-size <mm>] [--base-image <p>] ",
  "[--base-scalef <num>] [--no-flip-y]\n",
  "  base image is chosen from --base-image, else --raw-root, preferring CLEAN images:\n",
  "    tissue_hires_image.png > aligned_fiducials.jpg > detected_tissue_image.jpg > lowres\n",
  "  (detected_tissue_image.jpg is a Space Ranger QC overlay: its spot grid is baked into\n",
  "   the pixels, so it must never be the primary choice.)\n")
opt <- list()
i <- 1L
flag_keys <- c("no-spots", "no-flip-y")
while (i <= length(argv)) {
  a <- argv[i]
  if (grepl("^--", a)) {
    key <- sub("^--", "", a)
    if (key %in% flag_keys) { opt[[key]] <- TRUE; i <- i + 1L; next }
    if (i + 1L > length(argv)) { cat(.USAGE); quit(status = 2, save = "no") }
    opt[[key]] <- argv[i + 1L]
    i <- i + 2L
  } else {
    i <- i + 1L
  }
}
if (is.null(opt$rds) || is.null(opt$labels) || is.null(opt$spots) ||
    is.null(opt$sample) || is.null(opt[["out-dir"]])) {
  cat(.USAGE)
  quit(status = 2, save = "no")
}
rds_path  <- opt$rds
lab_path  <- opt$labels
spots_path <- opt$spots
sample_id <- opt$sample
out_dir   <- opt[["out-dir"]]
outline_requested <- !is.null(opt$outline) && nzchar(opt$outline)
outline_path <- if (outline_requested) opt$outline else NULL
no_spots  <- isTRUE(opt[["no-spots"]])
flip_y    <- !isTRUE(opt[["no-flip-y"]])      # 默认翻转（见下面 y 朝向的论证）
raw_root_opt <- if (!is.null(opt[["raw-root"]]) && nzchar(opt[["raw-root"]])) opt[["raw-root"]] else NULL
dpi_val <- 300L
if (!is.null(opt$dpi)) {
  dpi_val <- suppressWarnings(as.integer(opt$dpi))
  if (is.na(dpi_val) || dpi_val < 50L || dpi_val > 1200L) .fail("invalid --dpi (expect 50..1200)")
}
fig_w <- 8; fig_h <- 7
if (!is.null(opt$width))  { v <- suppressWarnings(as.numeric(opt$width));  if (!is.na(v) && v > 0) fig_w <- v }
if (!is.null(opt$height)) { v <- suppressWarnings(as.numeric(opt$height)); if (!is.na(v) && v > 0) fig_h <- v }
point_size_arg <- NA_real_          # 显式覆盖；NA = 由 spot_diameter_fullres × scalef 自动推
if (!is.null(opt[["point-size"]])) {
  v <- suppressWarnings(as.numeric(opt[["point-size"]])); if (!is.na(v) && v > 0) point_size_arg <- v
}
base_scalef_arg <- NA_real_         # 未知来源底图时手工指定 scalef
if (!is.null(opt[["base-scalef"]])) {
  v <- suppressWarnings(as.numeric(opt[["base-scalef"]])); if (!is.na(v) && v > 0) base_scalef_arg <- v
}
base_image_opt <- if (!is.null(opt[["base-image"]]) && nzchar(opt[["base-image"]])) opt[["base-image"]] else NULL

# ---- 硬安全：路径断言（不做兜底）----
if (!.is_ascii(out_dir))   .fail("out-dir contains non-ASCII characters; refusing to run")
if (!.is_ascii(rds_path))  .fail("rds path contains non-ASCII characters; refusing to run")
if (!.is_ascii(lab_path))  .fail("labels path contains non-ASCII characters; refusing to run")
if (!.is_ascii(spots_path)) .fail("spots path contains non-ASCII characters; refusing to run")
if (!.is_ascii(sample_id)) .fail("sample id contains non-ASCII characters; refusing to run")
if (outline_requested && !.is_ascii(outline_path)) .fail("outline path contains non-ASCII characters; refusing to run")
if (!is.null(base_image_opt) && !.is_ascii(base_image_opt)) .fail("base-image path contains non-ASCII characters; refusing to run")
if (!is.null(base_image_opt) && !file.exists(base_image_opt)) .fail(paste0("base-image not found: ", base_image_opt))
if (!file.exists(rds_path))   .fail(paste0("rds not found: ", rds_path))
if (!file.exists(lab_path))   .fail(paste0("region labels csv not found: ", lab_path))
if (!file.exists(spots_path)) .fail(paste0("spots csv not found: ", spots_path))
if (outline_requested && !file.exists(outline_path)) .fail(paste0("outline json not found: ", outline_path))

t0 <- Sys.time()

# =============================================================================
# 1. 中文字体（用户第②条 —— **这是修 bug**）
# =============================================================================
# 默认设备字体没有中文字形 ⇒ 区域名画成方块/乱码。三重保险：
#   ① sysfonts::font_add 给 **showtext** 用（showtext 只接管 cairo 系设备）
#   ② systemfonts::register_font 给 **ragg 系设备**用
#   ③ **自己开 cairo 设备**（下面 .save_fig_file），把设备钉死成 showtext 支持的路径
#      —— 因为 ggplot2 4.x 的 `ggsave(".png")` 会优先挑 ragg::agg_png（绕过 showtext）。
.cjk_font_path <- NA_character_
sf_ok <- FALSE            # ⚠ 顶层声明（函数内用 <<- 写回；否则运行期 object not found）
.setup_cjk_font <- function() {
  if (!requireNamespace("sysfonts", quietly = TRUE) ||
      !requireNamespace("showtext", quietly = TRUE)) {
    cat("[spatial_region_render] WARNING: showtext/sysfonts unavailable ->",
        "Chinese labels MAY render as boxes (tofu)\n", file = stderr())
    return(FALSE)
  }
  cands <- c("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
             "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf",
             "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/simkai.ttf",
             "C:/Windows/Fonts/Deng.ttf", "C:/Windows/Fonts/msjh.ttc")
  hit <- cands[file.exists(cands)]
  if (length(hit) == 0L) {
    cat("[spatial_region_render] WARNING: no CJK font found -> Chinese labels MAY render as boxes;",
        "probed:", paste(cands, collapse = " | "), "\n", file = stderr())
    return(FALSE)
  }
  ok <- tryCatch({
    sysfonts::font_add(family = "cjk", regular = hit[1])
    showtext::showtext_auto()
    showtext::showtext_opts(dpi = dpi_val)
    TRUE
  }, error = function(e) {
    cat("[spatial_region_render] WARNING: font_add/showtext failed:", conditionMessage(e), "\n",
        file = stderr())
    FALSE
  })
  sf_ok <<- tryCatch({
    if (requireNamespace("systemfonts", quietly = TRUE) &&
        "register_font" %in% getNamespaceExports("systemfonts")) {
      systemfonts::register_font(name = "cjk", plain = hit[1], bold = hit[1])
      TRUE
    } else FALSE
  }, error = function(e) FALSE)
  if (ok) {
    .cjk_font_path <<- hit[1]
    cat("[spatial_region_render] CJK font =", hit[1], "| showtext =", ok,
        "| systemfonts_registered =", sf_ok, "\n", file = stderr())
  }
  ok
}
cjk_font_ok <- .setup_cjk_font()
cjk_systemfonts_ok <- isTRUE(sf_ok)

cairo_ok <- isTRUE(capabilities("cairo"))
png_type_use <- if (cairo_ok) "cairo" else getOption("bitmapType", "windows")
pdf_dev_use  <- if (cairo_ok) "cairo_pdf" else "pdf"
cat("[spatial_region_render] text device: png(type=", png_type_use, ") /", pdf_dev_use,
    "| capabilities(cairo) =", cairo_ok, "\n", file = stderr())

# =============================================================================
# 2. 输入
# =============================================================================
obj <- readRDS(rds_path)
if (!"orig.ident" %in% colnames(obj@meta.data)) .fail("object has no `orig.ident` column")
avail <- unique(as.character(obj@meta.data[["orig.ident"]]))
if (!(sample_id %in% avail)) {
  .fail(paste0("sample not found in object: [", sample_id, "] | available: [",
               paste(avail, collapse = ","), "]"))
}

lab_df <- tryCatch(.read_table_utf8(lab_path), error = function(e) NULL)
if (is.null(lab_df) || !all(c("spot", "label") %in% colnames(lab_df))) {
  .fail("region labels csv must have columns exactly `spot,label` (and be valid UTF-8)")
}
spots_df <- tryCatch(.read_table_utf8(spots_path), error = function(e) NULL)
if (is.null(spots_df) || !all(c("spot", "sample", "x", "y") %in% colnames(spots_df))) {
  .fail("spots csv must have columns `spot,sample,x,y,cluster,cell_type` (and be valid UTF-8)")
}
spots_df <- spots_df[spots_df$sample == sample_id, , drop = FALSE]
if (nrow(spots_df) == 0L) .fail(paste0("no rows in spots csv for sample: ", sample_id))
spots_df$x <- suppressWarnings(as.numeric(spots_df$x))
spots_df$y <- suppressWarnings(as.numeric(spots_df$y))
spots_df <- spots_df[is.finite(spots_df$x) & is.finite(spots_df$y), , drop = FALSE]
if (nrow(spots_df) == 0L) .fail("spots csv has no finite x/y for this sample")

# 标签：**以 spots.csv 的行为准**（= 画布上可圈选的点集），join labels
m <- match(spots_df$spot, lab_df$spot)
lab <- lab_df$label[m]
lab[is.na(lab)] <- ""
lab <- trimws(lab)
lab[!nzchar(lab)] <- NA_character_
na_count <- sum(is.na(lab))
labeled <- nrow(spots_df) - na_count
if (na_count > 0L) {
  cat("[spatial_region_render] NOTE: NA (user-did-not-circle) spots =", na_count, "\n", file = stderr())
}
lab_filled <- ifelse(is.na(lab), "NA", lab)
labs <- sort(unique(lab_filled))
spots_df$label <- lab_filled

# 轮廓（原始数据坐标；坐标变换靠 × scalef，**不再反解校准**）
.clamp_dash <- function(v, default = 2L) {
  n <- suppressWarnings(as.integer(v)); if (is.na(n)) n <- default
  max(1L, min(15L, n))       # ★ hex linetype 每位只能是 1..15，0 会报错 ⇒ 必须夹紧
}
.hex_linetype <- function(dw, dg) sprintf("%x%x", .clamp_dash(dw), .clamp_dash(dg))
.read_outline <- function(path) {
  j <- tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE), error = function(e) NULL)
  if (is.null(j)) stop("cannot parse outline json: ", path)
  segs_raw <- j$segments
  # ★ 前缀 `EMPTY_SEGMENTS:` 是**稳定判据**：调用处据此把"合法空集"与"坏文件"分开措辞。
  if (is.null(segs_raw) || length(segs_raw) == 0L) stop("EMPTY_SEGMENTS: outline json has no segments")
  ds <- j$default_style
  def_col <- if (!is.null(ds$color) && nzchar(as.character(ds$color))) as.character(ds$color) else "#FF6B35"
  def_dw <- if (!is.null(ds$dash_width)) ds$dash_width else 2L
  def_dg <- if (!is.null(ds$dash_gap))   ds$dash_gap   else 6L
  segs <- list(); n_styled <- 0L; n_skipped <- 0L
  for (k in seq_along(segs_raw)) {
    s <- segs_raw[[k]]
    col <- def_col; dw <- def_dw; dg <- def_dg; rsn <- NA_character_
    if (is.list(s) && !is.null(s$points)) {          # 形状 B（§15.4 v2 为准）
      pts <- s$points
      if (!is.null(s$color) && nzchar(as.character(s$color))) col <- as.character(s$color)
      if (!is.null(s$dash_width)) dw <- s$dash_width
      if (!is.null(s$dash_gap))   dg <- s$dash_gap
      # §16.2：`reason`（nested/adjacent/isolated）由 W2 给。**W3 只画、不判断几何**，
      # 该字段仅进日志与摘要（reasons_drawn），用来核对"W2 认为该画几条"。
      if (!is.null(s[["reason"]]) && nzchar(as.character(s[["reason"]]))) {
        rsn <- as.character(s[["reason"]])
      }
      n_styled <- n_styled + 1L
    } else {
      pts <- s                                        # 形状 A（兼容保留）
    }
    if (!is.list(pts) || length(pts) < 2L) { n_skipped <- n_skipped + 1L; next }
    xs <- vapply(pts, function(p) as.numeric(p[[1]]), numeric(1))
    ys <- vapply(pts, function(p) as.numeric(p[[2]]), numeric(1))
    if (anyNA(xs) || anyNA(ys)) { n_skipped <- n_skipped + 1L; next }
    segs[[length(segs) + 1L]] <- data.frame(x = xs, y = ys, grp = k, col = col,
                                            lt = .hex_linetype(dw, dg), reason = rsn,
                                            stringsAsFactors = FALSE)
  }
  if (length(segs) == 0L) stop("EMPTY_SEGMENTS: outline json produced zero drawable segments")
  lab_out <- NULL
  if (!is.null(j$labels) && length(j$labels) > 0L) {
    lab_out <- do.call(rbind, lapply(j$labels, function(L) data.frame(
      x = as.numeric(L$x), y = as.numeric(L$y), name = as.character(L$name),
      color = if (!is.null(L$color) && nzchar(as.character(L$color))) as.character(L$color) else "#FFFFFF",
      font_size = if (!is.null(L$font_size)) as.numeric(L$font_size) else 12,
      # §16.2 注释圆角外框：来自 W1 的 chk_label_frame。缺字段 -> NA -> 按 FALSE 处理
      frame = if (!is.null(L$frame)) as.character(L$frame) else NA_character_,
      # §v4 第 3 点：圆角矩形**底框颜色**（来自 W1 调色板）。缺失/NA -> 由 .safe_fill 退回默认。
      frame_color = if (!is.null(L$frame_color)) as.character(L$frame_color) else NA_character_,
      stringsAsFactors = FALSE)))
    lab_out <- lab_out[!is.na(lab_out$x) & !is.na(lab_out$y), , drop = FALSE]
  }
  list(seg = do.call(rbind, segs), lab = lab_out, n_segments = length(segs),
       n_skipped = n_skipped, n_styled = n_styled,
       shape = if (n_styled > 0L) "styled" else "bare", px_per_data = j$px_per_data)
}

# =============================================================================
# 3. 底图：hires（优先）或 lowres，并确定 scalef `s`
# -----------------------------------------------------------------------------
# 映射（协调者已在 19/19 样本上验过）：**图像像素 = 原始数据坐标 × <对应档的 scalef>**
.read_raw_root <- function() {
  if (!is.null(raw_root_opt)) return(raw_root_opt)
  ev <- Sys.getenv("SPATIAL_RAW_ROOT"); if (nzchar(ev)) return(ev)
  NULL
}
.read_scalef_json <- function(raw_root, sid) {
  p <- file.path(raw_root, sid, "scalefactors_json.json")
  if (!file.exists(p)) return(NULL)
  j <- tryCatch(jsonlite::fromJSON(p), error = function(e) NULL)
  if (is.null(j)) NULL else j
}
base_image <- "lowres"; base_image_path <- ""; base_image_dims <- ""
base_image_note <- ""; base_hires_scalef <- NA_real_; base_lowres_scalef <- NA_real_
base_spot_diam_fullres <- NA_real_
base_overlay <- "none"; base_image_skip <- ""
img <- NULL; s <- NA_real_; img_w <- NA_real_; img_h <- NA_real_

.read_img_file <- function(p) {
  ext <- tolower(tools::file_ext(p))
  a <- NULL
  if (ext %in% c("jpg", "jpeg")) {
    if (!requireNamespace("jpeg", quietly = TRUE)) return(NULL)
    a <- tryCatch(jpeg::readJPEG(p), error = function(e) NULL)
  } else if (ext == "png") {
    if (!requireNamespace("png", quietly = TRUE)) return(NULL)
    a <- tryCatch(png::readPNG(p), error = function(e) NULL)
  }
  if (is.null(a)) return(NULL)
  if (length(dim(a)) == 2L) a <- array(rep(a, 3L), dim = c(dim(a), 3L))
  a
}

.raw_root <- .read_raw_root()
if (!is.null(.raw_root) && !.is_ascii(.raw_root)) {
  base_image_note <- "raw root contains non-ASCII characters; refusing to read it"
  cat("[spatial_region_render] NOTE:", base_image_note, "\n", file = stderr())
  .raw_root <- NULL
}
if (!is.null(.raw_root)) {
  cat("[spatial_region_render] raw_root (as given) =", .raw_root, "\n", file = stderr())
  sc <- .read_scalef_json(.raw_root, sample_id)
  if (!is.null(sc)) {
    if (!is.null(sc$tissue_hires_scalef))   base_hires_scalef      <- as.numeric(sc$tissue_hires_scalef)
    if (!is.null(sc$tissue_lowres_scalef))  base_lowres_scalef     <- as.numeric(sc$tissue_lowres_scalef)
    if (!is.null(sc$spot_diameter_fullres)) base_spot_diam_fullres <- as.numeric(sc$spot_diameter_fullres)
  }
}

# ★ 底图挑选：**必须优先"干净"图**（实测教训）。
#   Space Ranger 的 `detected_tissue_image.jpg` 是 **QC 叠加图**：蓝色 spot 网格是
#   **烧进 JPEG 像素**的 ⇒ 拿它当底图，连"无点图"都会满屏蓝点（已肉眼确认）。
#   `aligned_fiducials.jpg` 组织本身干净，只有外圈红色 fiducial 环 —— 可被"裁到内容"裁掉。
.pick_base <- function() {
  cands <- list()
  add <- function(p, kind, overlay) {
    if (is.null(p) || !nzchar(p) || !file.exists(p)) return(invisible(NULL))
    if (any(vapply(cands, function(cc) identical(cc$path, p), logical(1)))) return(invisible(NULL))
    cands[[length(cands) + 1L]] <<- list(path = p, kind = kind, overlay = overlay)
    invisible(NULL)
  }
  if (!is.null(base_image_opt)) {
    b <- tolower(basename(base_image_opt))
    k  <- if (grepl("lowres", b)) "lowres" else if (grepl("hires|fiducial|detected", b)) "hires" else "unknown"
    ov <- if (grepl("detected_tissue", b)) "spots_grid" else if (grepl("fiducial", b)) "fiducial_frame" else "none"
    add(base_image_opt, k, ov)
  } else if (!is.null(.raw_root)) {
    g <- function(pat) { h <- list.files(.raw_root, pattern = pat, full.names = TRUE); if (length(h)) h[1] else "" }
    add(g(paste0("^", sample_id, ".*tissue_hires_image\\.(png|jpg|jpeg)$")), "hires", "none")
    add(file.path(.raw_root, sample_id, "tissue_hires_image.png"), "hires", "none")
    add(g(paste0("^", sample_id, ".*aligned_fiducials\\.jpg$")), "hires", "fiducial_frame")
    add(g(paste0("^", sample_id, ".*detected_tissue_image\\.jpg$")), "hires", "spots_grid")
    add(file.path(.raw_root, sample_id, "tissue_lowres_image.png"), "lowres", "none")
  }
  cands
}
for (cand in .pick_base()) {
  sf <- if (identical(cand$kind, "lowres")) base_lowres_scalef
        else if (identical(cand$kind, "hires")) base_hires_scalef
        else base_scalef_arg
  if (is.na(sf) || sf <= 0) {
    base_image_skip <- paste0(base_image_skip, if (nzchar(base_image_skip)) "; " else "",
                              "skip ", basename(cand$path), " (no scale factor for kind=", cand$kind, ")")
    next
  }
  a <- .read_img_file(cand$path)
  if (is.null(a)) {
    base_image_skip <- paste0(base_image_skip, if (nzchar(base_image_skip)) "; " else "",
                              "skip ", basename(cand$path), " (unreadable)")
    next
  }
  img <- a; s <- sf
  img_h <- dim(img)[1]; img_w <- dim(img)[2]
  base_image <- cand$kind; base_image_path <- cand$path; base_overlay <- cand$overlay
  base_image_dims <- paste0(img_w, "x", img_h)
  cat("[spatial_region_render] base image =", base_image, "|", basename(cand$path), "|",
      img_w, "x", img_h, "| scalef =", s, "| overlay =", base_overlay, "\n", file = stderr())
  break
}
if (!is.null(img) && !identical(base_overlay, "none")) {
  cat("[spatial_region_render] WARNING: base image is a Space Ranger QC overlay (", base_overlay,
      ") -> those marks are BAKED INTO the pixels; omitting layers cannot remove them\n", file = stderr())
}
if (is.null(img)) {
  # 最后退回 .rds 里的 lowres 图（**干净**，无叠加）
  imobj <- tryCatch(obj@images[[sample_id]], error = function(e) NULL)
  if (is.null(imobj)) {
    base_image_note <- paste0(base_image_note,
      if (nzchar(base_image_note)) "; " else "", "no image object in .rds for ", sample_id)
    .fail(paste0("no usable base image: ", base_image_note))
  }
  im <- tryCatch(imobj@image, error = function(e) NULL)
  sl <- tryCatch(as.numeric(imobj@scale.factors$lowres), error = function(e) NA_real_)
  if (!is.na(base_lowres_scalef)) sl <- base_lowres_scalef
  if (is.null(im) || is.na(sl) || sl <= 0) {
    .fail("cannot obtain a usable lowres base image / scale factor from the .rds")
  }
  img <- im; s <- sl
  img_h <- dim(img)[1]; img_w <- dim(img)[2]
  base_image <- "lowres"; base_overlay <- "none"; base_image_dims <- paste0(img_w, "x", img_h)
  base_image_note <- paste0(base_image_note, if (nzchar(base_image_note)) "; " else "",
                            "fell back to lowres base image from .rds")
  cat("[spatial_region_render] NOTE:", base_image_note, "\n", file = stderr())
  cat("[spatial_region_render] base image = lowres (.rds) |", img_w, "x", img_h,
      "| scalef =", s, "| overlay = none\n", file = stderr())
}

# =============================================================================
# 4. 坐标变换 + **断言**（要求 2）
# =============================================================================
# y 朝向：`GetTissueCoordinates`/spots.csv 的 y（= Visium 的 imagerow）**向下增长**；
#   而 `annotation_raster(img, ymin=0, ymax=img_h)` 会把**图像第 1 行画在 viewport 顶端**。
#   ⇒ 只有把 y 轴**反向**（`scale_y_reverse`）时，"raw_y=0（组织顶端）"与"图像第 1 行"
#     才落在同一侧（屏幕顶端）。所以默认 `scale_y_reverse()`；
#   若实测发现反了，加 `--no-flip-y` 即可（一个二选一，**不改代码**）。
px <- spots_df$x * s
py <- spots_df$y * s
if (flip_y) py <- img_h - py          # ← 等价于 scale_y_reverse 的坐标写法，便于断言
in_rect <- all(px >= 0 & px <= img_w & py >= 0 & py <= img_h)
cat("[spatial_region_render] transform: x*s / (img_h - y*s) | flip_y =", flip_y,
    "| all_spots_in_raster_rect =", in_rect, "\n", file = stderr())
if (!in_rect) {
  # 要求 2：不满足就**留痕 + 拒绝出图**（宁可不出，也不交一张对不齐的图）
  .fail(paste0("spots fall OUTSIDE the base image rect after scaling (scalef=", s,
               ", image=", img_w, "x", img_h, "); refusing to render misaligned figures"))
}
spots_df$px <- px; spots_df$py <- py

# ---- 点大小：由 `spot_diameter_fullres × scalef` 推出 ----
# 这样算出来的是 **spot 的物理直径**，与底图用哪一档（hires/lowres）无关，换样本也不用重调。
if (!is.na(point_size_arg)) {
  point_size <- point_size_arg; point_size_src <- "explicit --point-size"
} else if (!is.na(base_spot_diam_fullres) && !is.na(s) && s > 0) {
  diam_img <- base_spot_diam_fullres * s              # spot 直径，单位 = 底图像素
  panel_w_in <- min(fig_w, fig_h * (img_w / img_h))   # coord_equal 下按纵横比缩放后的面板宽(in)
  point_size <- max(0.2, min(6, diam_img * panel_w_in * 25.4 / img_w))
  point_size_src <- "derived from spot_diameter_fullres x scalef"
} else {
  point_size <- 1.3; point_size_src <- "fallback constant"
}
cat("[spatial_region_render] point size =", round(point_size, 3), "mm (", point_size_src,
    ") | spot_diameter_fullres =", base_spot_diam_fullres, "\n", file = stderr())

# ---- y 朝向的**定量旁证**（我看不到对齐，就把可判读的数算出来）----
tissue_row_centroid <- NA_real_; tissue_col_centroid <- NA_real_; tissue_frac <- NA_real_
spots_row_centroid <- mean(spots_df$y * s)     # 以"图像行号(自上而下)"计
y_delta_frac <- NA_real_
if (!is.null(img) && length(dim(img)) == 3L) {
  .m <- (img[, , 1] < 0.92) | (img[, , 2] < 0.92) | (img[, , 3] < 0.92)   # 非白像素 ≈ 组织
  .rs <- rowMeans(.m); .cs <- colMeans(.m)
  if (sum(.rs) > 0 && sum(.cs) > 0) {
    tissue_row_centroid <- weighted.mean(seq_len(img_h), .rs)
    tissue_col_centroid <- weighted.mean(seq_len(img_w), .cs)
    tissue_frac <- mean(.m)
    y_delta_frac <- abs(tissue_row_centroid - spots_row_centroid) / img_h
  }
}
cat("[spatial_region_render] y-orientation check: tissue_row_centroid =",
    round(tissue_row_centroid, 1), "| spots_row_centroid =", round(spots_row_centroid, 1),
    "| delta =", round(100 * y_delta_frac, 2), "% of image height | tissue_frac =",
    round(tissue_frac, 3), "\n", file = stderr())

# ★ 颜色：**区域名绝不进 colour 位置**（协调者要求 2 —— 这正是上一版崩溃的直接原因）
#   给每个区域名分配一个**纯 ASCII 合成键** `L001..`，colour 位置**只用键**；
#   中文名只出现在**图例文字**（`labels=` / `breaks=`）里。
#   ⇒ 即使标签里有怪字符，最坏也只是图例文字难看，**绝不会被 col2rgb 当颜色名解析**。
region_keys <- sprintf("L%03d", seq_along(labs))
hex <- grDevices::hcl.colors(max(1L, length(labs)), "Dark 3")
NA_COL <- "#CCCCCC"                     # ★ 必须是 **hex**：下面那道守卫只放行 hex（grey80 会被自己挡下）
if (any(labs == "NA")) hex[which(labs == "NA")] <- NA_COL
cols_map <- stats::setNames(hex, region_keys)   # 值=hex, 名字=ASCII 键
spots_df$lab_key <- region_keys[match(lab_filled, labs)]
if (anyNA(spots_df$lab_key)) .fail("internal error: some spot label did not map to a colour key")
if (any(!grepl("^#[0-9A-Fa-f]{6}$", hex))) .fail("internal error: colour table holds a non-hex value")

# 轮廓：原始坐标 → 同一变换
# ⚠ 不变量：**回传给 Python 的所有字符串（outline_calib_note / base_image_note / frame_note /
#   clip_refused_reason 等）一律 ASCII**。原因：这些值要经 Rsummary→JSON→Python 日志通路，
#   实测中文在该通路上曾被打成乱码（高位被 &0x7F 削掉）。中文解释只写在**代码注释**里，
#   面向用户的本地化文案放在 **Python 侧日志**。
ol <- NULL; outline_calib_note <- ""; outline_provided <- FALSE; ol_err <- ""
reasons_drawn <- list(); reasons_missing <- NA_integer_; labels_with_frame <- 0L
ol_names <- character(0)      # outline.json 里的 labels[].name（用于与 CSV 区域名交叉核对）
n_segments <- 0L; n_labels <- 0L; seg_styled <- 0L; seg_skipped <- 0L
outline_shape <- ""; px_per_data <- NULL; px_per_data_img <- NULL
if (outline_requested) {
  # ★ 把错误消息留一份，仅供"合法空集 vs 坏文件"分流措辞用（结果仍是 ol = NULL）
  ol <- tryCatch(.read_outline(outline_path),
                 error = function(e) { ol_err <<- conditionMessage(e); NULL })
  if (!is.null(ol)) {
    # §16.2：reason 只用于**日志/摘要汇总**；画哪几条完全由 W2 决定（W3 不判断几何）
    .sr <- ol$seg$reason[match(unique(ol$seg$grp), ol$seg$grp)]
    reasons_drawn <- as.list(table(.sr, useNA = "no"))
    reasons_missing <- sum(is.na(.sr))
    cat("[spatial_region_render] segment reasons: ",
        paste(names(reasons_drawn), unlist(reasons_drawn), sep = "x", collapse = ", "),
        " | missing =", reasons_missing, "\n", file = stderr())
    if (!is.null(ol$lab) && nrow(ol$lab) > 0L && !is.null(ol$lab[["frame"]])) {
      labels_with_frame <- sum(!is.na(ol$lab[["frame"]]) &
        toupper(as.character(ol$lab[["frame"]])) %in% c("TRUE", "T", "1", "YES"))
    }
  }
  if (is.null(ol)) {
    # ★ 合法空集 vs 坏文件：`segments == []` 是**正常**的（该样本只有范围层、没有普通区域），
    #   不能用 "unusable" 把好文件说成坏的。其余错误**保留原文案不变**。
    #   ⚠ 这里只改**措辞与日志级别**：不画轮廓层、`outline_provided` 仍为 FALSE，行为完全不变。
    if (grepl("^EMPTY_SEGMENTS:", ol_err)) {
      outline_calib_note <- paste0(
        "outline segments = 0 => nothing to draw under the two-layer rule ",
        "(legitimate empty selection, NOT a broken file); drawing WITHOUT outline layer")
      cat("[spatial_region_render] INFO:", outline_calib_note, "\n", file = stderr())
    } else {
      outline_calib_note <- "outline json unusable; drawn WITHOUT outline layer"
      cat("[spatial_region_render] WARNING:", outline_calib_note, "\n", file = stderr())
    }
  } else {
    ol$seg$x <- ol$seg$x * s
    ol$seg$y <- if (flip_y) img_h - ol$seg$y * s else ol$seg$y * s
    if (!is.null(ol$lab) && nrow(ol$lab) > 0L) {
      ol$lab$x <- ol$lab$x * s
      ol$lab$y <- if (flip_y) img_h - ol$lab$y * s else ol$lab$y * s
    }
    outline_provided <- TRUE
    n_segments <- ol$n_segments; seg_styled <- ol$n_styled; seg_skipped <- ol$n_skipped
    n_labels <- if (is.null(ol$lab)) 0L else nrow(ol$lab)
    if (!is.null(ol$lab) && nrow(ol$lab) > 0L) {
      ol_names <- as.character(ol$lab$name)
      # 交叉核对：outline 的区域名必须也是合法 UTF-8（jsonlite 正常，这里只是留痕）
      if (!all(validUTF8(ol_names))) {
        cat("[spatial_region_render] WARNING: outline label names are not valid UTF-8\n",
            file = stderr())
      }
      ov <- intersect(ol_names, labs)
      cat("[spatial_region_render] outline label names = [", paste(ol_names, collapse = ","),
          "] | overlap with csv region labels = [", paste(ov, collapse = ","), "]\n", file = stderr())
    }
    outline_shape <- ol$shape
    px_per_data <- ol$px_per_data
    if (!is.null(px_per_data)) px_per_data_img <- as.numeric(px_per_data) * s
    # 轮廓是否落在 raster 矩形内（越界就拒绝画轮廓层，但**不**影响两张图产出）
    seg_in <- all(ol$seg$x >= 0 & ol$seg$x <= img_w & ol$seg$y >= 0 & ol$seg$y <= img_h)
    if (!seg_in) {
      outline_calib_note <- "outline segments fall OUTSIDE the base image rect; outline layer SKIPPED"
      cat("[spatial_region_render] WARNING:", outline_calib_note, "\n", file = stderr())
      ol <- NULL; outline_provided <- FALSE
    }
  }
}

# ---- 视野：**裁到内容**（点 ∪ 轮廓 ∪ 注释 + 4% 边距），再夹回 raster 矩形 ----
# 两个目的：① `annotation_raster` **不训练标度**，limits 必须自己给；
#           ② 裁掉大片空白边距，以及 `aligned_fiducials.jpg` 外圈的红色 fiducial 环
#              （它在组织之外，正是我们要甩掉的东西）。
vx0 <- min(spots_df$px); vx1 <- max(spots_df$px)
vy0 <- min(spots_df$py); vy1 <- max(spots_df$py)
if (!is.null(ol)) {
  vx0 <- min(vx0, ol$seg$x); vx1 <- max(vx1, ol$seg$x)
  vy0 <- min(vy0, ol$seg$y); vy1 <- max(vy1, ol$seg$y)
  if (!is.null(ol$lab) && nrow(ol$lab) > 0L) {
    vx0 <- min(vx0, ol$lab$x); vx1 <- max(vx1, ol$lab$x)
    vy0 <- min(vy0, ol$lab$y); vy1 <- max(vy1, ol$lab$y)
  }
}
.mx <- 0.04 * (vx1 - vx0); .my <- 0.04 * (vy1 - vy0)
view_x <- c(max(0, vx0 - .mx), min(img_w, vx1 + .mx))
view_y <- c(max(0, vy0 - .my), min(img_h, vy1 + .my))
if (diff(view_x) <= 0 || diff(view_y) <= 0) .fail("degenerate view rect after cropping")
cat("[spatial_region_render] view x = [", round(view_x[1], 1), ",", round(view_x[2], 1),
    "] y = [", round(view_y[1], 1), ",", round(view_y[2], 1), "] of raster", img_w, "x", img_h,
    "\n", file = stderr())

# ---- fiducial 环：**按颜色定位、按几何裁掉视野**（不涂白、不动一个组织像素）----
# `aligned_fiducials.jpg` 的组织是干净的，唯一瑕疵是外圈 Space Ranger 红色 fiducial 环。
# 直接"按颜色涂白"是启发式的，而且环的下带**压在组织边缘上** ⇒ 涂白会啃掉组织。
# 这里改成：用红色像素的行/列剖面**认出环这个矩形**，再把**视野夹到环内** ——
# 环落到视野外，图上自然没有它，而且一个组织像素都没碰。
frame_detected <- FALSE; frame_inner_rows <- NULL; frame_inner_cols <- NULL
frame_rows_band <- NULL; frame_cols_band <- NULL; view_clipped_to_frame <- FALSE
frame_red_frac <- NA_real_; frame_note <- ""
# ★ 裁决（Phase 4）：**轮廓/点是用户的数据，红环只是图面美观** ⇒ 夹取一旦会切到数据就放弃。
#   `clip_refused_reason` 让用户/下游知道"图上露红环"是**有意为之**，不是 bug。
clip_refused_reason <- ""
if (!is.null(img) && length(dim(img)) == 3L) {
  .r <- img[, , 1]; .g <- img[, , 2]; .b <- img[, , 3]
  .red <- (.r > 0.40) & (.r - pmax(.g, .b) > 0.12)      # 高饱和红/品红
  frame_red_frac <- mean(.red)
  if (frame_red_frac > 0.005) {                          # 红色成规模才当作 fiducial 环
    .rs <- rowSums(.red); .cs <- colSums(.red)
    # ★ 阈值**不能用 `0.5*max`**：横向带在"整行"上都有红，而两侧竖带在**每一行**也贡献一份
    #   基线（实测：基线≈60，横向带约 240..760）。必须取「基线 + 0.35×(峰值-基线)」，
    #   才能把两条横向带与"中间只有竖带"的那些行分开。
    .thr <- function(v) { b <- stats::median(v); b + 0.35 * (max(v) - b) }
    # ★ 不能取"第一个/最后一个分组"：图里还有**贴边的细亮线**，会自成小组 ⇒ "环内"会错成
    #   整幅（实测踩过）。改为**从外向内找最外一圈红色结构的连续段**：fiducial 圆点是网格，
    #   剖面本来就会起伏，所以允许 <=30 行/列的小间隙。
    .thr <- function(v) { b <- stats::median(v); b + 0.35 * (max(v) - b) }
    .run_fwd <- function(hi, G = 30L) {
      idx <- which(hi); if (!length(idx)) return(c(NA_integer_, NA_integer_))
      s <- idx[1]; e <- s
      for (i in idx[-1]) { if (i - e <= G) e <- i else break }
      c(s, e)
    }
    .run_rev <- function(hi, G = 30L) {
      idx <- which(hi); if (!length(idx)) return(c(NA_integer_, NA_integer_))
      e <- idx[length(idx)]; s <- e
      for (i in rev(idx[-length(idx)])) { if (s - i <= G) s <- i else break }
      c(s, e)
    }
    hi_r <- .rs > .thr(.rs); hi_c <- .cs > .thr(.cs)
    rt <- .run_fwd(hi_r); rb2 <- .run_rev(hi_r)
    ct <- .run_fwd(hi_c); cb2 <- .run_rev(hi_c)
    if (!anyNA(c(rt, rb2, ct, cb2))) {
      fr <- c(rt[2] + 1L, rb2[1] - 1L)
      fc <- c(ct[2] + 1L, cb2[1] - 1L)
      # 自检：识别出来的"环内"不能几乎是整幅，否则说明阈值没抓住环（宁可报 no-frame）
      ok_frame <- fr[2] > fr[1] && fc[2] > fc[1] &&
                  (fr[2] - fr[1]) < 0.98 * img_h && (fc[2] - fc[1]) < 0.98 * img_w
      if (ok_frame) {
        frame_detected <- TRUE
        frame_inner_rows <- fr; frame_inner_cols <- fc
        frame_rows_band <- c(rt[1], rb2[2])
        frame_cols_band <- c(ct[1], cb2[2])
        cat("[spatial_region_render] fiducial frame detected: rows", frame_rows_band[1], "..",
            frame_rows_band[2], "| cols", frame_cols_band[1], "..", frame_cols_band[2],
            "| red =", round(100 * frame_red_frac, 2), "%\n", file = stderr())
      }
    }
  }
  if (frame_detected) {
    fx <- as.numeric(frame_inner_cols)
    fy <- c(img_h - frame_inner_rows[2], img_h - frame_inner_rows[1])   # 行号 -> 绘图 y
    nx0 <- max(view_x[1], fx[1]); nx1 <- min(view_x[2], fx[2])
    ny0 <- max(view_y[1], fy[1]); ny1 <- min(view_y[2], fy[2])
    keep <- all(spots_df$px >= nx0 & spots_df$px <= nx1 &
                spots_df$py >= ny0 & spots_df$py <= ny1)
    if (keep && !is.null(ol)) {
      keep <- all(ol$seg$x >= nx0 & ol$seg$x <= nx1 & ol$seg$y >= ny0 & ol$seg$y <= ny1)
    }
    if (keep && nx1 > nx0 && ny1 > ny0) {
      view_x <- c(nx0, nx1); view_y <- c(ny0, ny1); view_clipped_to_frame <- TRUE
      cat("[spatial_region_render] view clipped inside fiducial frame -> x = [",
          round(view_x[1], 1), ",", round(view_x[2], 1), "] y = [", round(view_y[1], 1), ",",
          round(view_y[2], 1), "]\n", file = stderr())
    } else {
      frame_note <- "frame detected but clipping would cut points/outline; NOT clipped"
      clip_refused_reason <- paste0(
        "view clipping would cut user data (spots/outline extend beyond the fiducial frame ",
        "inner rect rows ", frame_inner_rows[1], "..", frame_inner_rows[2],
        ", cols ", frame_inner_cols[1], "..", frame_inner_cols[2],
        "); clipping abandoned to protect user data")
      cat("[spatial_region_render] WARNING:", frame_note, "\n", file = stderr())
      cat("\u26a0 \u89c6\u56fe\u5939\u53d6\u4f1a\u5207\u6389\u8f6e\u5ed3/\u70b9 \u2192 \u5df2\u653e\u5f03\u5939\u53d6\uff08\u56fe\u9762\u53ef\u80fd\u9732\u51fa\u7ea2\u8272\u57fa\u51c6\u73af\uff0c\u5c5e\u6b63\u5e38\uff09\n",
          file = stderr())
    }
  }
}
# =============================================================================
# 5. 出图（两张共用同一底座，唯一差别 = 有没有 geom_point）
# =============================================================================
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
if (!dir.exists(out_dir)) .fail(paste0("cannot create out-dir: ", out_dir))
f_png <- file.path(out_dir, paste0("Spatial_", sample_id, ".png"))
f_pdf <- file.path(out_dir, paste0("Spatial_", sample_id, ".pdf"))

.save_fig_file <- function(plot, path, w, h) {
  # ★ 自己开设备（不用 ggsave）：钉死成 **cairo**，因为 showtext 只接管 cairo 系设备，
  #   而 ggsave(".png") 在 ggplot2 4.x 下会优先挑 ragg::agg_png（绕过 showtext）⇒ 中文乱码。
  is_pdf <- grepl("\\.pdf$", path, ignore.case = TRUE)
  opened <- FALSE
  ok <- tryCatch({
    if (is_pdf) {
      if (identical(pdf_dev_use, "cairo_pdf")) grDevices::cairo_pdf(filename = path, width = w, height = h, bg = "#FFFFFF")
      else grDevices::pdf(file = path, width = w, height = h, bg = "#FFFFFF")
    } else {
      grDevices::png(filename = path, width = w, height = h, units = "in",
                     res = dpi_val, type = png_type_use, bg = "#FFFFFF")
    }
    opened <- TRUE
    print(plot)
    grDevices::dev.off(); opened <- FALSE
    TRUE
  }, error = function(e) {
    cat("[spatial_region_render] device/plot error:", conditionMessage(e), "\n", file = stderr())
    if (isTRUE(opened)) try(grDevices::dev.off(), silent = TRUE)
    FALSE
  })
  if (!isTRUE(ok) || !file.exists(path) || file.size(path) < 512) {
    stop("figure not written (missing or smaller than 512 bytes): ", path)
  }
  invisible(TRUE)
}

# 底座：hires 图 + 等比例坐标 + 无主题
base_plot <- function() {
  p <- ggplot2::ggplot() +
    ggplot2::annotation_raster(img, xmin = 0, xmax = img_w, ymin = 0, ymax = img_h,
                               interpolate = TRUE) +
    # ★ `annotation_raster` **不参与标度训练**！若不显式给 limits，面板范围只由点决定
    #   ⇒ 底图会被**裁切**到点云 bbox（就交不出完整画布）。这里把 limits 钉死在"视野矩形"上；
    #   该矩形 ⊇ 点 ∪ 轮廓 ∪ 注释，所以在 §4 的断言成立时不会丢任何元素。
    ggplot2::scale_x_continuous(limits = view_x, expand = c(0, 0)) +
    ggplot2::scale_y_continuous(limits = view_y, expand = c(0, 0)) +
    ggplot2::coord_equal() +
    ggplot2::theme_void()
  if (isTRUE(cjk_font_ok)) p <- p + ggplot2::theme(text = ggplot2::element_text(family = "cjk"))
  p
}
.HEX_RE <- "^#[0-9A-Fa-f]{6}$"
.safe_col <- function(v, fallback) {
  v <- as.character(v)
  ifelse(!is.na(v) & grepl(.HEX_RE, v), v, fallback)
}
# `frame_color` 允许 `#RRGGBB` 或 `#RRGGBBAA`（带透明度）；非法/缺失 -> 默认，绝不让脏值进 ggplot
.HEX_FILL_RE <- "^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"
.safe_fill <- function(v, fallback) {
  v <- as.character(v)
  ifelse(!is.na(v) & grepl(.HEX_FILL_RE, v), v, fallback)
}

# ★ 轮廓层**不占用 colour / linetype 标度**：每段一个 geom_path，颜色与线型作为**固定参数**传入。
#   上一版这里写的是 `aes(colour = col) + scale_colour_identity()`，而它**顶掉了**点的
#   `scale_colour_manual` ⇒ 点的"区域名"被拿去当颜色名 ⇒ `Unknown colour name` 崩溃。
#   改成固定参数后，全图**只剩一个 colour 标度**（点的那个），这类崩溃被根除。
add_outline <- function(p) {
  if (is.null(ol)) return(p)
  seg <- ol$seg
  for (g in unique(seg$grp)) {
    si <- seg[seg$grp == g, , drop = FALSE]
    p <- p + ggplot2::geom_path(data = si, ggplot2::aes(x = x, y = y),
                                colour = .safe_col(si$col[1], "#FF6B35"),
                                linetype = si$lt[1],
                                lineend = "round", linejoin = "round",
                                linewidth = 0.8, inherit.aes = FALSE)
  }
  if (!is.null(ol$lab) && nrow(ol$lab) > 0L) {
    .pt2mm <- 72.27 / 25.4        # ggplot size 单位是 mm；把 pt 字号换算过去
    lb <- ol$lab
    lb$size_mm <- pmax(2, pmin(60, lb$font_size)) / .pt2mm
    lb$col_safe <- .safe_col(lb$color, "#FFFFFF")
    .fam <- if (isTRUE(cjk_font_ok)) "cjk" else ""
    # §16.2 注释圆角外框：labels[].frame（来自 W1 的 chk_label_frame 勾选框）。
    # TRUE -> geom_label（自带圆角矩形底）；FALSE / 缺字段 -> geom_text（向后兼容）。
    .fr <- rep(FALSE, nrow(lb))
    if (!is.null(lb[["frame"]])) {
      .fr <- !is.na(lb[["frame"]]) &
             toupper(as.character(lb[["frame"]])) %in% c("TRUE", "T", "1", "YES")
    }
    if (any(!.fr)) {
      a <- lb[!.fr, , drop = FALSE]
      p <- p + ggplot2::geom_text(data = a, ggplot2::aes(x = x, y = y, label = name),
                                  colour = a$col_safe, size = a$size_mm, family = .fam,
                                  fontface = "bold", inherit.aes = FALSE)
    }
    if (any(.fr)) {
      b <- lb[.fr, , drop = FALSE]
      # §v4 第 3 点：底框色 = 该行自己的 `labels[].frame_color`；缺失/非法 -> "#FFFFFFCC"。
      #   ★ 实现用**按 fill 值分组画多个层**，而不是依赖 `fill` 参数向量的逐行回收
      #     （后者行为在不同 ggplot2 版本间不保证一致）。组数 = 不同 fill 的个数，通常 1~3 组。
      .fc <- if (is.null(b[["frame_color"]])) rep(NA_character_, nrow(b)) else as.character(b[["frame_color"]])
      b$fill_safe <- .safe_fill(.fc, "#FFFFFFCC")
      for (fv in unique(b$fill_safe)) {
        bi <- b[b$fill_safe == fv, , drop = FALSE]
        p <- p + ggplot2::geom_label(data = bi, ggplot2::aes(x = x, y = y, label = name),
                                     colour = bi$col_safe, size = bi$size_mm, family = .fam,
                                     fontface = "bold", fill = fv, linewidth = 0.15,
                                     label.padding = grid::unit(0.15, "lines"),
                                     label.r = grid::unit(0.15, "lines"), inherit.aes = FALSE)
      }
    }
  }
  p
}
add_spots <- function(p) {
  p + ggplot2::geom_point(data = spots_df, ggplot2::aes(x = px, y = py, colour = lab_key),
                          size = point_size, inherit.aes = FALSE) +
    ggplot2::scale_colour_manual(values = cols_map, breaks = region_keys,
                                 labels = labs, name = NULL, na.value = "#BEBEBE")
}

# ---- 带点那张 ----
p_with <- add_outline(add_spots(base_plot()))

# ★ 自证"画上去的图例文字到底是什么"：把将要渲染的字符串连 UTF-8 字节一起打出来。
#   没有眼睛也能验：`未命名` 的 UTF-8 字节必须是 e6 9c aa e5 91 bd e5 90 8d。
.hexbytes <- function(s) paste(sprintf("%02x", as.integer(charToRaw(enc2utf8(s)))), collapse = " ")
cat("[spatial_region_render] legend labels as drawn:\n", file = stderr())
for (k in seq_along(labs)) {
  cat("    ", region_keys[k], " = [", labs[k], "]  utf8_bytes = ", .hexbytes(labs[k]), "\n",
      sep = "", file = stderr())
}
if (length(ol_names) > 0L) {
  for (nm in ol_names) {
    cat("     outline label = [", nm, "]  utf8_bytes = ", .hexbytes(nm), "\n", sep = "", file = stderr())
  }
}
lg <- tryCatch({
  gb <- ggplot2::ggplot_build(p_with)
  sc <- gb$plot$scales$get_scales("colour")
  if (is.null(sc)) "" else paste(sc$get_labels(), collapse = " | ")
}, error = function(e) paste0("<legend introspect failed: ", conditionMessage(e), ">"))
cat("[spatial_region_render] built colour-scale labels = [", lg, "]\n", sep = "", file = stderr())

.save_fig_file(p_with, f_png, fig_w, fig_h)
.save_fig_file(p_with, f_pdf, fig_w, fig_h)

# ★ 判据必须是"**图上到底有没有点**"，而不是"参数是否置零"（上一版就是活证据：参数置零，
#   但底图自带烧进去的点阵，看着满屏是点）。自绘之后这件事是**构造性**的：直接数 `geom_point` 层。
.count_geom_layers <- function(p, cls) {
  if (is.null(p$layers) || length(p$layers) == 0L) return(0L)
  sum(vapply(p$layers, function(L) inherits(L$geom, cls), logical(1)))
}
point_layers_with <- .count_geom_layers(p_with, "GeomPoint")

# ---- 不带点那张（**不画 geom_point 层** ⇒ 天生正确，不用"把点参数置零"）----
f_np_png <- ""; f_np_pdf <- ""; nospot_error <- ""
point_layers_nospot <- NA_integer_
if (no_spots) {
  f_np_png <- file.path(out_dir, paste0("SpatialNoSpots_", sample_id, ".png"))
  f_np_pdf <- file.path(out_dir, paste0("SpatialNoSpots_", sample_id, ".pdf"))
  p_np <- add_outline(base_plot())      # 同底座，**根本不拼点层**
  point_layers_nospot <- .count_geom_layers(p_np, "GeomPoint")
  nospot_error <- tryCatch({
    .save_fig_file(p_np, f_np_png, fig_w, fig_h)
    .save_fig_file(p_np, f_np_pdf, fig_w, fig_h)
    ""
  }, error = function(e) {
    cat("[spatial_region_render] WARNING: no-spots figure failed:", conditionMessage(e), "\n", file = stderr())
    conditionMessage(e)
  })
}
nospot_ok <- nzchar(f_np_png) && !nzchar(nospot_error) &&
             file.exists(f_np_png) && file.size(f_np_png) >= 512 &&
             !is.na(point_layers_nospot) && point_layers_nospot == 0L
spots_hidden <- isTRUE(no_spots) && !is.na(point_layers_nospot) && point_layers_nospot == 0L
cat("[spatial_region_render] geom_point layers: with-spots =", point_layers_with,
    "| no-spots =", point_layers_nospot, "| spots_hidden =", spots_hidden, "\n", file = stderr())
if (isTRUE(no_spots) && !isTRUE(spots_hidden)) {
  cat("[spatial_region_render] WARNING: no-spots figure STILL contains", point_layers_nospot,
      "geom_point layer(s)\n", file = stderr())
}

# =============================================================================
# 6. JSON 摘要（两行：带标记 + 裸 JSON 最后一行）
# =============================================================================
summ <- list(
  ok = TRUE, sample = sample_id,
  spots = nrow(spots_df), spots_plotted = nrow(spots_df),
  labeled = labeled, na = na_count,
  out_png = f_png, out_pdf = f_pdf,
  n_region_labels = length(labs),
  region_labels = I(as.character(labs)),
  region_keys = I(region_keys),
  # ★ 编码自检（协调者要求 3 的第一道闸）：按字节读 + 显式 UTF-8 + 合法 + 字节往返
  encoding_ok = length(enc_report) == 2L,
  encoding = I(enc_report),
  outline_label_names = I(ol_names),
  label_name_overlap = I(intersect(ol_names, labs)),
  png_bytes = as.numeric(file.size(f_png)),
  pdf_bytes = as.numeric(file.size(f_pdf)),
  no_spots_requested = no_spots,
  out_nospot_png = f_np_png, out_nospot_pdf = f_np_pdf,
  nospot_ok = nospot_ok, nospot_error = nospot_error,
  nospot_png_bytes = if (nzchar(f_np_png) && file.exists(f_np_png)) as.numeric(file.size(f_np_png)) else 0,
  nospot_pdf_bytes = if (nzchar(f_np_pdf) && file.exists(f_np_pdf)) as.numeric(file.size(f_np_pdf)) else 0,
  # 自绘后"点是否隐藏"= **geom_point 层数**，不再靠参数置零（参数置零不等于图上没有点）
  spots_hidden = spots_hidden,
  spots_hidden_method = "count of geom_point layers in the no-spots plot (must be 0)",
  point_layers_with_spots = as.integer(point_layers_with),
  point_layers_no_spots = if (is.na(point_layers_nospot)) NULL else as.integer(point_layers_nospot),
  base_image = base_image, base_image_path = base_image_path, base_image_dims = base_image_dims,
  base_image_note = base_image_note, base_image_skip = base_image_skip,
  # ★ 底图上的 QC 叠加是**烧进像素**的：overlay != none 时，任何图都甩不掉那些标记
  base_overlay = base_overlay,
  base_spot_diam_fullres = base_spot_diam_fullres,
  view_x = I(as.numeric(view_x)), view_y = I(as.numeric(view_y)),
  # ★ fiducial 环：按颜色定位、按几何把视野夹到环内（不涂白、不动组织像素）
  fiducial_frame_detected = frame_detected,
  frame_rows_band = if (is.null(frame_rows_band)) NULL else I(as.integer(frame_rows_band)),
  frame_cols_band = if (is.null(frame_cols_band)) NULL else I(as.integer(frame_cols_band)),
  frame_inner_rows = if (is.null(frame_inner_rows)) NULL else I(as.integer(frame_inner_rows)),
  frame_inner_cols = if (is.null(frame_inner_cols)) NULL else I(as.integer(frame_inner_cols)),
  frame_red_frac = frame_red_frac,
  view_clipped_to_frame = view_clipped_to_frame,
  frame_note = frame_note,
  tissue_row_centroid = tissue_row_centroid, tissue_col_centroid = tissue_col_centroid,
  spots_row_centroid = spots_row_centroid, y_delta_frac_of_height = y_delta_frac,
  tissue_frac = tissue_frac,
  base_hires_scalef = base_hires_scalef, base_lowres_scalef = base_lowres_scalef,
  base_fit = in_rect, raw_root = if (is.null(.raw_root)) "" else .raw_root,
  outline_requested = outline_requested, outline_provided = outline_provided,
  outline_shape = outline_shape, n_segments = as.integer(n_segments),
  segments_styled = as.integer(seg_styled), segments_skipped = as.integer(seg_skipped),
  n_labels = as.integer(n_labels),
  # §16.2：reason 汇总（只作核对用）；画什么**完全由 payload 的 segments 决定**（relation 字段已作废并删除）
  reasons_drawn = reasons_drawn, reasons_missing = reasons_missing,
  # ★ 与 reasons_drawn 同级：夹取被放弃的原因（空串 = 没放弃）
  clip_refused_reason = clip_refused_reason,
  labels_with_frame = as.integer(labels_with_frame),
  first_segment_first_point = if (is.null(ol)) NULL else
    I(as.numeric(c(ol$seg$x[1], ol$seg$y[1]))),
  px_per_data = px_per_data, px_per_data_img = px_per_data_img,
  outline_note = outline_calib_note,
  flip_y = flip_y, point_size = point_size, point_size_src = point_size_src,
  cjk_font_ok = cjk_font_ok, cjk_systemfonts_ok = cjk_systemfonts_ok,
  cjk_font_path = if (is.na(.cjk_font_path)) "" else .cjk_font_path,
  text_device = paste0("png(type=", png_type_use, ")/", pdf_dev_use),
  dpi = dpi_val, width_in = fig_w, height_in = fig_h,
  elapsed_sec = round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 2)
)
j <- jsonlite::toJSON(summ, auto_unbox = TRUE, null = "null", digits = 8)
cat("##SPATIAL_REGION_RENDER##", j, "\n", sep = "")
cat(j, "\n", sep = "")
quit(status = 0, save = "no")
