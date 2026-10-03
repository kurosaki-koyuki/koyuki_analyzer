#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# =============================================================================
# virtual_knockout.R —— 单细胞「虚拟敲除」层 R 端全流程（scTenifoldKnk）
#
# 规格来源：虚拟敲除参考/虚拟敲除层_实装说明书_交付乙方.md
#           （§0 TL;DR / §2 环境 / §7 参数契约 / §8.0-§8.9 实现规格 / §9 产物 / §11 内存 / §14 已定决策）
# 算法蓝本：虚拟敲除参考/实践测试_GSE131928/scripts/11_HVG面板_去靶校准_出图.R（甲方实测通过）
#
# 用法（★ 只允许命名参数 --key=value，禁止位置参数 —— 说明书 §7.1 的本仓真实事故）：
#   Rscript virtual_knockout.R --rds=<绝对路径> --out_dir=<绝对路径> --dataset=<名> --gko=SOX2 \
#           --group_col="Celltype (major-lineage)" --gene_mode=hvg --n_top_genes=1000 \
#           --qc=TRUE --exclude_gko=TRUE --fdr=0.05 --seed=1 --n_cores=4 [其余参数见 --help]
#   Rscript virtual_knockout.R --help
#
# 日志协议（说明书 §8.9，前端按正则解析，格式不许改）：本脚本自有的用户可见输出行一律以 "[VK] " 开头。
# 产物一律落 --out_dir（本脚本 **不 setwd()**，也不向 script/ 或项目根写任何东西；见说明书 §3.5-6/§14-10）。
#
# 顺序铁律（说明书 §0/§8.3）：① 先在「全部基因 × 候选细胞」矩阵上 scQC，做完再取基因面板；
#                              ② 靶基因强制加入面板；是否从校准里排除由 --exclude_gko 控制（两种口径都写盘）；
#                              ③ 传给包内部的 qc 恒为 FALSE（外层已质控，避免二次质控）。
# =============================================================================

## ---- 0. 环境准备 ------------------------------------------------------------
## 打开一个"空设备"：防止任何误开的图形设备在项目根/脚本目录留下 Rplots.pdf。
## （不 chdir —— 收到的是绝对路径，chdir 反而会让相对路径落到 script/ 里。见说明书 §3.5-6）
pdf(NULL)

suppressPackageStartupMessages({
  library(Seurat); library(Matrix); library(scTenifoldKnk); library(ggplot2)
})

# =============================================================================
# 1. 日志工具（说明书 §8.9：所有面向用户的行以 "[VK] " 开头）
# =============================================================================

## 有格式参数时走 sprintf；只有 1 个参数时原样输出（避免自由文本里的 % 触发 sprintf 报错）
vk <- function(fmt, ...) {
  s <- if (nargs() > 1L) sprintf(fmt, ...) else fmt
  cat(paste0("[VK] ", s), "\n", sep = "")
  flush(stdout())
}

## 8 步进度行（说明书 §8.9 表：STEP|<i>|<n>|<描述>）
step_line <- function(i, desc) vk("STEP|%d|8|%s", i, desc)

## 参数/校验类致命错误：合同行打到 stdout（前端要抓 [VK] 前缀），再以非 0 退出码中止
vfatal <- function(msg) {
  vk("ERROR|%s", msg)
  quit(save = "no", status = 1L)
}

## 合同错误：先打逐字的合同消息（§8.8），再打底层原因（不许吞异常），然后以非 0 退出码中止
vbort <- function(contract_msg, reason = NULL) {
  vk("ERROR|%s", contract_msg)
  if (!is.null(reason) && length(reason) && nzchar(as.character(reason)[1]))
    vk(paste0("NOTE|底层原因：", paste(as.character(reason), collapse = " / ")))
  quit(save = "no", status = 1L)
}

# =============================================================================
# 2. 参数默认值（说明书 §6 唯一权威表，逐字一致；命令行缺项一律走默认、不报错）
# =============================================================================

## 逗号分隔的"列表型"参数（空串 = 不筛选）
LIST_KEYS <- c("group_values", "filter1_values", "filter2_values")

DEFAULTS <- list(
  ## 路径与标识
  rds               = "",
  out_dir           = "",
  dataset           = "",
  ## 细胞选择（本层筛细胞用）
  gko               = "",
  group_col         = "Celltype (major-lineage)",
  group_values      = character(0),
  filter1_col       = "",
  filter1_values    = character(0),
  filter2_col       = "",
  filter2_values    = character(0),
  ## 基因面板
  gene_mode         = "hvg",
  n_top_genes       = 1000,
  gene_list_file    = "",
  drop_mt           = TRUE,
  drop_ribo         = TRUE,
  ## 质控
  qc                = TRUE,
  qc_min_lib_size   = 1000,
  qc_min_pct        = 0.05,
  qc_max_mt_ratio   = 0.1,
  qc_remove_outlier = TRUE,
  ## 网络
  n_net             = 10,
  n_cells           = 500,
  n_comp            = 3,
  q                 = 0.9,
  scale_scores      = TRUE,
  symmetric         = FALSE,
  lambda            = 0,
  ## 张量分解 / 流形对齐
  td_k              = 3,
  td_max_iter       = 1000,
  td_max_error      = 1e-05,
  td_n_decimal      = 3,
  ma_ndim           = 2,
  ## 统计与校准
  exclude_gko       = TRUE,
  fdr               = 0.05,
  empirical_null    = FALSE,
  ## 运行控制
  seed              = 1,
  n_cores           = 4,
  ## 自检开关（正式可用：只解析参数并写 params.json，然后正常退出）
  dry_run           = FALSE
)

print_usage <- function() {
  cat("virtual_knockout.R —— 单细胞虚拟敲除（scTenifoldKnk）R 端全流程\n")
  cat("★ 只接受命名参数 --key=value；位置参数一律报错（说明书 §7.1）。\n")
  cat("用法：\n")
  cat("  Rscript virtual_knockout.R --rds=<绝对路径> --out_dir=<绝对路径> --dataset=<名> --gko=SOX2 [其它参数]\n")
  cat("参数（括号内为默认值，缺项即用默认值、不报错）：\n")
  for (k in names(DEFAULTS)) {
    d <- DEFAULTS[[k]]
    ds <- if (length(d) == 0L) "(空)" else paste(as.character(d), collapse = ",")
    cat(sprintf("  --%-18s = %s\n", k, ds))
  }
  cat("  --help / -h          = 显示本帮助（退出码 0）\n")
}

# =============================================================================
# 3. 命令行解析（手写 --key=value；不依赖 optparse）
# =============================================================================

.args <- commandArgs(trailingOnly = TRUE)

## --help：唯一不带值的开关；显式支持，避免被当成"未知参数"
if (any(.args %in% c("-h", "--help", "--h"))) {
  print_usage()
  quit(save = "no", status = 0L)
}

.raw <- list()      # key -> 命令行原样字符串
for (a in .args) {
  ## 位置参数：说明书 §7.1 明令禁止（曾造成整串错位、静默算错）
  if (!grepl("^--", a))
    vfatal(sprintf("未知参数：%s（本脚本只接受 --key=value 命名参数，禁止位置参数）", a))
  body <- sub("^--", "", a)
  if (!grepl("=", body, fixed = TRUE))
    vfatal(sprintf("未知参数：--%s（缺少 = 分隔，正确写法 --%s=值）", body, body))
  key <- sub("=.*$", "", body)
  val <- sub("^[^=]*=", "", body)
  ## 未知参数必须报错退出，并点名该参数（防止拼写错静默失效）
  if (!key %in% names(DEFAULTS))
    vfatal(sprintf("未知参数：--%s", key))
  if (key %in% names(.raw)) vk("NOTE|参数 --%s 重复给出，后一次覆盖前一次", key)
  .raw[[key]] <- val
}

## 按默认值的类型做转换（TRUE/FALSE、数值、字符串、逗号列表）
.coerce <- function(key, s, def) {
  if (key %in% LIST_KEYS) {
    v <- trimws(strsplit(s, ",", fixed = TRUE)[[1]])
    return(v[nzchar(v)])
  }
  if (is.logical(def)) {
    u <- toupper(trimws(s))
    if (u %in% c("TRUE", "T", "1", "YES", "Y", "ON")) return(TRUE)
    if (u %in% c("FALSE", "F", "0", "NO", "N", "OFF")) return(FALSE)
    vfatal(sprintf("参数 --%s 需要 TRUE/FALSE，收到：%s", key, s))
  }
  if (is.numeric(def)) {
    v <- suppressWarnings(as.numeric(trimws(s)))
    if (is.na(v)) vfatal(sprintf("参数 --%s 需要数值，收到：%s", key, s))
    return(v)
  }
  as.character(s)
}

p <- DEFAULTS
for (k in names(.raw)) p[[k]] <- .coerce(k, .raw[[k]], DEFAULTS[[k]])

# =============================================================================
# 4. 输出目录 + params.json（说明书 §7.2-3：全部参数原样写盘 = 参数指纹）
# =============================================================================

if (!nzchar(p$out_dir)) {
  p$out_dir <- file.path(tempdir(), "virtual_knockout_out")
  vk("NOTE|未提供 --out_dir，已回退到临时目录：%s", p$out_dir)
}
if (!dir.exists(p$out_dir)) {
  dir.create(p$out_dir, showWarnings = FALSE, recursive = TRUE)
  if (!dir.exists(p$out_dir)) vbort(sprintf("无法创建输出目录：%s", p$out_dir), NULL)
}
opath <- function(...) file.path(p$out_dir, ...)

## ---- JSON 工具：优先 jsonlite，缺失/失败则手写合法 JSON（绝不允许跳过这一步）----
.json_escape <- function(s) {
  s <- gsub("\\", "\\\\", s, fixed = TRUE)
  s <- gsub("\"", "\\\"", s, fixed = TRUE)
  s <- gsub("\n", "\\n", s, fixed = TRUE)
  s <- gsub("\r", "\\r", s, fixed = TRUE)
  s <- gsub("\t", "\\t", s, fixed = TRUE)
  s
}

.json_hand <- function(x) {
  n <- names(x)
  items <- vapply(seq_along(x), function(i) {
    v <- x[[i]]
    val <- if (is.logical(v)) {
      paste0(ifelse(v, "true", "false"))
    } else if (is.numeric(v)) {
      format(v, scientific = FALSE, trim = TRUE, digits = 15)
    } else if (length(v) == 1L) {
      paste0("\"", .json_escape(as.character(v)), "\"")
    } else {
      paste0("[", paste0("\"", vapply(as.character(v), .json_escape, ""), "\"", collapse = ", "), "]")
    }
    if (length(val) > 1L) val <- paste0("[", paste0(val, collapse = ", "), "]")
    paste0("  \"", .json_escape(n[i]), "\": ", val)
  }, character(1))
  paste0("{\n", paste(items, collapse = ",\n"), "\n}\n")
}

.write_params_json <- function(pp, path) {
  ok <- FALSE
  reason <- ""
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    pj <- pp
    for (k in LIST_KEYS) pj[[k]] <- I(as.character(pp[[k]]))
    txt <- tryCatch(jsonlite::toJSON(pj, auto_unbox = TRUE, pretty = TRUE, null = "null", digits = NA),
                    error = function(e) { reason <<- conditionMessage(e); NULL })
    if (!is.null(txt)) {
      wr <- tryCatch({
        con <- file(path, open = "wb")
        writeLines(as.character(txt), con, useBytes = TRUE)
        close(con)
        TRUE
      }, error = function(e) { reason <<- conditionMessage(e); FALSE })
      if (isTRUE(wr)) {
        chk <- tryCatch(jsonlite::fromJSON(path), error = function(e) NULL)
        ok <- !is.null(chk) && setequal(names(chk), names(pp))
        if (!ok) reason <- "jsonlite 写出的 params.json 回读校验未通过"
      }
    }
  } else {
    reason <- "jsonlite 未安装"
  }
  if (!ok) {
    vk(paste0("NOTE|params.json 改用内置序列化写出（原因：", reason, "）"))
    con <- file(path, open = "wb")
    writeLines(.json_hand(pp), con, useBytes = TRUE)
    close(con)
  }
  invisible(path)
}

.write_params_json(p, opath("params.json"))

if (isTRUE(p$dry_run)) {
  vk("NOTE|dry_run=TRUE：只解析参数并写出 params.json，不执行算法")
  vk("DONE|out_dir=%s", p$out_dir)
  quit(save = "no", status = 0L)
}

## 置灰项自检：empirical_null 需要 locfdr（本环境未装，说明书 §2.1/§8.8）——先报先停，不浪费一次全流程
if (isTRUE(p$empirical_null) && !requireNamespace("locfdr", quietly = TRUE))
  vbort("empirical_null=TRUE 需要 locfdr 包（当前未安装）", NULL)

# =============================================================================
# 5. 通用小工具
# =============================================================================

## panel 非零占比（@x 要求稀疏矩阵，前面已保证）
nnz_pct <- function(M) 100 * length(M@x) / prod(dim(M))

## 基因列表目录定位：优先环境变量，其次从 CWD 逐级向上找 appdata/genelists
.find_genelists_dir <- function() {
  cand <- character(0)
  ev <- Sys.getenv("KOYUKI_APPDATA", "")
  if (nzchar(ev)) cand <- c(cand, file.path(ev, "genelists"))
  wd <- getwd()
  for (up in 0:4) {
    base <- if (up == 0L) wd else file.path(wd, paste(rep("..", up), collapse = "/"))
    cand <- c(cand, file.path(base, "appdata", "genelists"))
  }
  cand <- unique(normalizePath(cand, winslash = "/", mustWork = FALSE))
  hit <- cand[dir.exists(cand)]
  if (length(hit)) hit[1] else NA_character_
}

## 基因列表读取：xlsx 第一列 / txt(或 csv) 每行一个
.read_gene_list <- function(path) {
  ext <- tolower(tools::file_ext(path))
  if (ext %in% c("xlsx", "xls")) {
    if (!requireNamespace("readxl", quietly = TRUE)) stop("readxl 包未安装，无法读取 xlsx")
    df <- readxl::read_excel(path, col_names = FALSE, sheet = 1)
    v <- as.character(df[[1]])
  } else {
    ln <- readLines(path, warn = FALSE, encoding = "UTF-8")
    v <- unlist(strsplit(ln, "[,\t;]"))
  }
  v <- sub("^\uFEFF", "", v)          # 去 BOM
  v <- trimws(v)
  unique(v[!is.na(v) & nzchar(v)])
}

## ★ 写图带重试（逐字照抄蓝本 save_png，仅把最终 stop 的消息换成说明书 §8.8 的合同文案）
##   本机实测出现过 `dev.off(): agg could not write to the given file`
##   —— 图片被其它进程占用时 R 只发 warning、文件保持旧版、脚本继续跑。
save_png <- function(p, file, side, dpi = 200, tries = 4) {
  for (i in seq_len(tries)) {
    bad <- FALSE
    withCallingHandlers(
      tryCatch(ggplot2::ggsave(file, p, width = side, height = side, dpi = dpi),
               error = function(e) { bad <<- TRUE; message("  出错: ", conditionMessage(e)) }),
      warning = function(w) {
        if (grepl("could not write", conditionMessage(w))) {
          bad <<- TRUE; invokeRestart("muffleWarning")
        }
      })
    if (!bad && file.exists(file)) return(invisible(TRUE))
    message(sprintf("  [重试 %d/%d] 写 %s 失败（文件可能被占用），等 2 秒", i, tries, basename(file)))
    Sys.sleep(2)
  }
  stop(sprintf("[VK] ERROR|图片写入失败：%s（可能被占用）", basename(file)), call. = FALSE)
}

# =============================================================================
# 6. 主流程（说明书 §8.1 - §8.7）
# =============================================================================

## run_summary.txt 累积器（key<TAB>value，UTF-8）
SM <- character(0)
sm_set <- function(k, v) { SM[[k]] <<- paste(as.character(v), collapse = ","); invisible(NULL) }

t_wall <- Sys.time()

tryCatch({

  sm_set("out_dir", p$out_dir)
  sm_set("params_json", opath("params.json"))

  # ---------------------------------------------------------------------------
  ## §8.1 步骤 1：读取数据
  # ---------------------------------------------------------------------------
  step_line(1, "读取数据")

  if (!nzchar(p$rds)) vbort(sprintf("读不到数据集：%s", p$rds), "未提供 --rds")
  if (!file.exists(p$rds)) vbort(sprintf("读不到数据集：%s", p$rds), "文件不存在")

  obj <- tryCatch(readRDS(p$rds),
                  error = function(e) vbort(sprintf("读不到数据集：%s", p$rds), conditionMessage(e)))

  asy <- tryCatch(DefaultAssay(obj),
                  error = function(e) vbort(sprintf("读不到数据集：%s", p$rds),
                                            paste0("不是含 assay 的 Seurat 对象：", conditionMessage(e))))

  ## Seurat v5.5.0：layer = "counts"；失败则退回 slot = "counts"（说明书 §8.1）
  ct <- tryCatch(
    GetAssayData(obj, assay = asy, layer = "counts"),
    error = function(e) {
      vk(paste0("NOTE|GetAssayData(layer=\"counts\") 失败：", conditionMessage(e), "；退回 slot=\"counts\""))
      tryCatch(GetAssayData(obj, assay = asy, slot = "counts"),
               error = function(e2) vbort(sprintf("读不到数据集：%s", p$rds),
                                          paste0("assay=", asy, " 的 layer/slot=counts 均取不到：", conditionMessage(e2))))
    })

  if (!inherits(ct, "sparseMatrix")) {
    vk(paste0("NOTE|counts 不是稀疏矩阵（class=", paste(class(ct), collapse = "/"), "），已转 CsparseMatrix"))
    ct <- as(ct, "CsparseMatrix")
  }

  vk("DATA|genes=%d|cells=%d", nrow(ct), ncol(ct))

  ## 非整数计数只提示、不中止（说明书 §8.1）
  .xv <- ct@x
  if (length(.xv) && any(.xv != floor(.xv)))
    vk("NOTE|counts 非整数（可能是 RSEM/归一化产物），继续")

  sm_set("dataset", p$dataset)
  sm_set("source_rds", p$rds)
  sm_set("assay", asy)
  sm_set("genes_input", nrow(ct))
  sm_set("cells_input", ncol(ct))

  # ---------------------------------------------------------------------------
  ## §8.2 步骤 2：选择细胞（分组列 ∈ 选中组别 AND 筛选1 AND 筛选2）
  # ---------------------------------------------------------------------------
  step_line(2, "选择细胞")

  cells <- colnames(ct)
  md <- obj@meta.data

  if (nzchar(p$group_col)) {
    if (!p$group_col %in% colnames(md))
      vbort(sprintf("分组列不存在：%s", p$group_col),
            paste0("meta.data 可用列：", paste(utils::head(colnames(md), 50), collapse = ", ")))
    v <- as.character(md[cells, p$group_col])
    if (length(p$group_values)) cells <- cells[v %in% p$group_values]
  }

  for (i in 1:2) {
    fcol <- p[[sprintf("filter%d_col", i)]]
    fvals <- p[[sprintf("filter%d_values", i)]]
    if (nzchar(fcol) && length(fvals)) {
      if (!fcol %in% colnames(md))
        vbort(sprintf("分组列不存在：%s", fcol), "筛选列不在 meta.data 中")
      v <- as.character(md[cells, fcol])
      cells <- cells[v %in% fvals]
    }
  }

  vk("CELLS|after_filter=%d", length(cells))
  if (length(cells) < 30)
    vbort(sprintf("可用细胞仅 %d 个，过少（建议 ≥100）", length(cells)), NULL)

  sm_set("group_col", p$group_col)
  sm_set("group_values", if (length(p$group_values)) p$group_values else "ALL")
  sm_set("filter1_col", p$filter1_col)
  sm_set("filter1_values", if (length(p$filter1_values)) p$filter1_values else "")
  sm_set("filter2_col", p$filter2_col)
  sm_set("filter2_values", if (length(p$filter2_values)) p$filter2_values else "")
  sm_set("cells_after_filter", length(cells))

  # ---------------------------------------------------------------------------
  ## §8.3 步骤 3：★ 先在全基因矩阵上质控，再取基因面板（顺序不能反）
  # ---------------------------------------------------------------------------
  step_line(3, "质控与基因选择")

  if (!nzchar(p$gko) || !p$gko %in% rownames(ct))
    vbort(sprintf("靶基因 %s 不在表达矩阵中", p$gko), NULL)

  sub_all <- ct[, cells, drop = FALSE]

  if (isTRUE(p$qc)) {
    ## scQC 自己只发 warning；说明书 §8.8 要求的那行提示由我们补
    if (!any(grepl("^MT-", toupper(rownames(sub_all)))))
      vk("NOTE|未找到线粒体基因（^MT-），该过滤已跳过")
    sub_all <- tryCatch(
      scQC(sub_all,
           minLibSize = p$qc_min_lib_size,
           removeOutlierCells = p$qc_remove_outlier,
           minPCT = p$qc_min_pct,
           maxMTratio = p$qc_max_mt_ratio,
           label = "VK"),
      error = function(e) vbort("质控（scQC）执行失败", conditionMessage(e)))
  }
  if (!inherits(sub_all, "sparseMatrix")) sub_all <- as(sub_all, "CsparseMatrix")

  vk("QC|genes=%d|cells=%d", nrow(sub_all), ncol(sub_all))
  sm_set("qc", if (isTRUE(p$qc)) "TRUE" else "FALSE")
  sm_set("qc_min_lib_size", p$qc_min_lib_size)
  sm_set("qc_min_pct", p$qc_min_pct)
  sm_set("qc_max_mt_ratio", p$qc_max_mt_ratio)
  sm_set("qc_remove_outlier", if (isTRUE(p$qc_remove_outlier)) "TRUE" else "FALSE")
  sm_set("qc_genes", nrow(sub_all))
  sm_set("qc_cells", ncol(sub_all))

  ## —— 基因面板（蓝本 41-55 行，逐字沿用）——
  g <- rownames(sub_all)
  isMT   <- grepl("^MT-", toupper(g)) | grepl("^MTRNR", toupper(g)) | grepl("^MTATP", toupper(g)) |
            grepl("^MTCO", toupper(g)) | grepl("^MTCYB", toupper(g)) | grepl("^MTND", toupper(g))
  isRIBO <- grepl("^RP[SL]", g) | grepl("^MRP[SL]", g)
  keep   <- g[!((isTRUE(p$drop_mt) & isMT) | (isTRUE(p$drop_ribo) & isRIBO))]

  sm_set("drop_mt", if (isTRUE(p$drop_mt)) "TRUE" else "FALSE")
  sm_set("drop_ribo", if (isTRUE(p$drop_ribo)) "TRUE" else "FALSE")
  sm_set("panel_excluded_MT", if (isTRUE(p$drop_mt)) sum(isMT) else 0L)
  sm_set("panel_excluded_ribo", if (isTRUE(p$drop_ribo)) sum(isRIBO) else 0L)

  ## 高变基因 = 直接在 counts 上按方差取 top-N（蓝本 50-51 行，逐字沿用）
  pick_hvg <- function() {
    if (!length(keep)) return(character(0))
    v <- apply(as.matrix(sub_all[keep, , drop = FALSE]), 1, var)
    keep[order(v, decreasing = TRUE)][seq_len(min(p$n_top_genes, length(keep)))]
  }

  mode <- tolower(trimws(p$gene_mode))
  if (!mode %in% c("all", "hvg", "list"))
    vbort(sprintf("未知的 gene_mode：%s（应为 all/hvg/list）", p$gene_mode), NULL)

  if (mode == "all") {
    genes <- keep
  } else if (mode == "list") {
    gl <- NULL
    if (!nzchar(p$gene_list_file)) {
      vk("NOTE|gene_mode=list 但未指定 --gene_list_file，已按 hvg 兜底")
    } else {
      gdir <- .find_genelists_dir()
      ## 以"文件名"为主（Python 侧只给 basename）；若传入的本身就是一个存在的路径，优先原样使用（防御）
      f <- if (file.exists(p$gene_list_file)) p$gene_list_file
           else if (!is.na(gdir)) file.path(gdir, p$gene_list_file)
           else ""
      if (nzchar(f) && file.exists(f)) {
        gl <- tryCatch(.read_gene_list(f), error = function(e) {
          vk(paste0("NOTE|读取基因列表失败：", conditionMessage(e)))
          NULL
        })
        if (is.null(gl) || !length(gl)) {
          vk(paste0("NOTE|基因列表 ", basename(f), " 内容为空，已按 hvg 兜底"))
          gl <- NULL
        }
      } else {
        vk(paste0("NOTE|未找到基因列表文件（", p$gene_list_file, "），已按 hvg 兜底；查找目录=",
                  if (is.na(gdir)) "appdata/genelists 不存在" else gdir))
      }
    }
    genes <- if (is.null(gl)) pick_hvg() else intersect(keep, gl)
  } else {
    genes <- pick_hvg()
  }

  if (!length(genes)) vbort("基因面板为空（检查基因列表文件或 HVG 个数）", NULL)

  ## ★ 靶基因强制加入，且 **固定排在第 1 行**（蓝图第 53 行 `unique(c(GKO, pick))` 的语义）
  ##   ⚠ 行序会改变 CP 张量分解的随机初始化落点 ⇒ 让 distance 产生约 2e-3 的相对差；
  ##     必须与蓝图逐字一致：**无条件前置** + unique 去重（去重删掉的是后面那个重复项）。
  if (!p$gko %in% genes) vk("NOTE|%s 不在面板中，已强制加入", p$gko)
  genes <- unique(c(p$gko, genes))
  X <- sub_all[genes, , drop = FALSE]

  nz_pct <- nnz_pct(X)
  vk("PANEL|genes=%d|cells=%d|nonzero=%.2f%%", nrow(X), ncol(X), nz_pct)
  vk("TARGET|gko=%s|detected_cells=%d|total_counts=%g",
     p$gko, sum(X[p$gko, ] != 0), sum(X[p$gko, ]))
  if (nz_pct > 90)
    vk("NOTE|面板非零占比 %.2f%% > 90%%，面板过稠密，网络可能退化", nz_pct)

  sm_set("gene_mode", mode)
  sm_set("n_top_genes", p$n_top_genes)
  sm_set("gene_list_file", p$gene_list_file)
  sm_set("panel_genes", nrow(X))
  sm_set("panel_cells", ncol(X))
  sm_set("panel_nonzero_pct", sprintf("%.2f", nz_pct))
  sm_set("target_detected_cells", sum(X[p$gko, ] != 0))
  sm_set("target_total_counts", sum(X[p$gko, ]))
  ## 兼容甲方 11_运行小结.txt 的键名（同一数值多写一行）
  sm_set("genes", nrow(X))
  sm_set("cells", ncol(X))   # ★ 面板细胞数（与 panel_cells 同值；甲方 11_运行小结.txt 就是这个含义）
                             #    QC 前的过滤后细胞数由 cells_after_filter 承载，信息不丢

  # ---------------------------------------------------------------------------
  ## §8.4 步骤 4：nc_nCells 自动夹取（超了 makeNetworks 会直接报错）
  # ---------------------------------------------------------------------------
  step_line(4, "每网络细胞数夹取")
  n_cells_eff <- as.integer(min(p$n_cells, ncol(X)))
  vk("NCELLS|effective=%d", n_cells_eff)
  sm_set("n_cells_requested", p$n_cells)
  sm_set("n_cells_effective", n_cells_eff)

  # ---------------------------------------------------------------------------
  ## §8.5 步骤 5：内存预估（包自带；只警告/返回清单，不中止）
  # ---------------------------------------------------------------------------
  step_line(5, "内存检查")
  mem <- tryCatch(scTenifoldNet::checkMemory(nrow(X), nNet = p$n_net, nConditions = 1, warn = TRUE),
                  error = function(e) {
                    vk(paste0("NOTE|checkMemory 预估失败：", conditionMessage(e)))
                    NULL
                  })
  if (!is.null(mem)) {
    vk("NOTE|内存预估：需要 %s GB / 系统可用 %s GB / 本机最多约 %s 基因",
       format(round(mem$required / 1e9, 1), nsmall = 1),
       ifelse(is.na(mem$available), "NA", format(round(mem$available / 1e9, 1), nsmall = 1)),
       ifelse(is.na(mem$maxGenes), "NA", format(mem$maxGenes, big.mark = ",")))
    sm_set("mem_required_gb", round(mem$required / 1e9, 2))
    sm_set("mem_available_gb", ifelse(is.na(mem$available), "NA", round(mem$available / 1e9, 2)))
    sm_set("mem_max_genes", ifelse(is.na(mem$maxGenes), "NA", mem$maxGenes))
  }

  # ---------------------------------------------------------------------------
  ## §8.6 步骤 6：跑主流程 + 两种校准（★★核心）
  # ---------------------------------------------------------------------------
  step_line(6, "网络重建与虚拟敲除")

  set.seed(p$seed)
  t_pipe <- Sys.time()
  res <- tryCatch(
    scTenifoldKnk(countMatrix = X, gKO = p$gko, transcriptomeWide = FALSE,
                  qc = FALSE,                       # ★ 外层已质控，避免二次质控
                  nc_lambda = p$lambda, nc_nNet = as.integer(p$n_net), nc_nCells = n_cells_eff,
                  nc_nComp = as.integer(p$n_comp), nc_scaleScores = p$scale_scores,
                  nc_symmetric = p$symmetric, nc_q = p$q,
                  td_K = as.integer(p$td_k), td_maxIter = as.integer(p$td_max_iter),
                  td_maxError = p$td_max_error, td_nDecimal = as.integer(p$td_n_decimal),
                  ma_nDim = as.integer(p$ma_ndim), dr_empiricalNull = p$empirical_null,
                  nCores = as.integer(p$n_cores), seed = as.integer(p$seed)),
    error = function(e) vbort("scTenifoldKnk 主流程执行失败", conditionMessage(e)))
  elapsed <- as.numeric(difftime(Sys.time(), t_pipe, units = "secs"))

  dr  <- res$diffRegulation
  d2  <- as.numeric(dr$distance)^2
  isK <- as.character(dr$gene) == p$gko

  ## —— 出边自检（包只发 warning，界面要红字）——
  outdeg <- as.integer(sum(res$tensorNetworks$WT[p$gko, ] != 0))
  vk("OUTDEG|gko=%s|edges=%d", p$gko, outdeg)
  if (outdeg == 0)
    vk("NOTE|%s 在网络中没有出边，敲除等于没敲，结果仅为数值噪声", p$gko)

  ## —— 口径 A：包的原生（E 与 BH 都含靶基因）——
  E_a <- mean(d2); FC_a <- d2 / E_a
  p_a <- pchisq(FC_a, df = 1, lower.tail = FALSE); padj_a <- p.adjust(p_a, "fdr")

  ## —— 口径 B：排除靶基因（★默认口径；距离不变，只换参考系）——
  E_b <- mean(d2[!isK]); FC_b <- d2[!isK] / E_b
  p_b <- pchisq(FC_b, df = 1, lower.tail = FALSE); padj_b <- p.adjust(p_b, "fdr")

  ## 自证：我复现的口径 A 应与包原生 p.adj 完全一致（蓝本 82 行）
  self_diff <- max(abs(padj_a - as.numeric(dr$p.adj)))

  share_target <- 100 * d2[isK][1] / sum(d2)
  vk("E|share_of_target=%.1f%%|E_pkg=%.4e|E_noKO=%.4e", share_target, E_a, E_b)
  vk("SIG|calib_pkg=%d|calib_noKO=%d|fdr=%.3g", sum(padj_a < p$fdr), sum(padj_b < p$fdr), p$fdr)

  sm_set("n_net", as.integer(p$n_net))
  sm_set("n_comp", as.integer(p$n_comp))
  sm_set("nc_q", p$q)
  sm_set("td_k", as.integer(p$td_k))
  sm_set("ma_ndim", as.integer(p$ma_ndim))
  sm_set("seed", as.integer(p$seed))
  sm_set("n_cores", as.integer(p$n_cores))
  sm_set("elapsed_s", sprintf("%.1f", elapsed))
  sm_set("target_outdeg", outdeg)
  sm_set("sox2_outdeg", outdeg)          # 兼容甲方 11_运行小结.txt 的键名（逐字，不改）
  sm_set("target_share_of_sumd2", sprintf("%.1f%%", share_target))
  sm_set("E_pkg", sprintf("%.4e", E_a))
  sm_set("E_noKO", sprintf("%.4e", E_b))
  sm_set("calib_pkg_significant", sum(padj_a < p$fdr))
  sm_set("calib_noKO_significant", sum(padj_b < p$fdr))
  sm_set("calibA_significant", sum(padj_a < p$fdr))    # 兼容甲方键名
  sm_set("calibB_significant", sum(padj_b < p$fdr))    # 兼容甲方键名
  sm_set("fdr", p$fdr)
  sm_set("exclude_gko", if (isTRUE(p$exclude_gko)) "TRUE" else "FALSE")
  sm_set("self_check_max_abs_diff_padj", sprintf("%.3e", self_diff))

  # ---------------------------------------------------------------------------
  ## §8.7 步骤 7：出表与出图
  # ---------------------------------------------------------------------------
  step_line(7, "导出结果")

  ## 列名逐字（说明书 §8.7）：gene,distance,Z,is_target,FC_package,p_package,FDR_package,
  ##                       FC_noKO,p_noKO,FDR_noKO,logFC,negLog10P
  ## ★ 口径 B 的向量长 m-1，必须逐列赋值（不能写 ifelse(isK,NA,FC_b)：长度不匹配会静默循环补齐错位）
  full <- data.frame(
    gene        = as.character(dr$gene),
    distance    = as.numeric(dr$distance),
    Z           = as.numeric(dr$Z),
    is_target   = isK,
    FC_package  = FC_a,
    p_package   = p_a,
    FDR_package = padj_a,
    FC_noKO     = NA_real_,
    p_noKO      = NA_real_,
    FDR_noKO    = NA_real_,
    stringsAsFactors = FALSE
  )
  full$FC_noKO[!isK]  <- FC_b
  full$p_noKO[!isK]   <- p_b
  full$FDR_noKO[!isK] <- padj_b
  full$logFC <- log2(full$FC_noKO)
  full$negLog10P <- -log10(full$p_noKO)
  rownames(full) <- NULL

  ## 两种口径都写盘；"显著表"按 --exclude_gko 选口径（默认 B，说明书 §14-2）
  if (isTRUE(p$exclude_gko)) {
    sig <- full[!full$is_target & !is.na(full$FDR_noKO) & full$FDR_noKO < p$fdr, , drop = FALSE]
    sig <- sig[order(sig$p_noKO), , drop = FALSE]
    calib_used <- "noKO"
    plot_all <- data.frame(gene = full$gene, logFC = full$logFC, negLog10P = full$negLog10P,
                           FDR = full$FDR_noKO, stringsAsFactors = FALSE)
    plot_all <- plot_all[!is.na(plot_all$negLog10P), , drop = FALSE]
  } else {
    sig <- full[!is.na(full$FDR_package) & full$FDR_package < p$fdr, , drop = FALSE]
    sig <- sig[order(sig$p_package), , drop = FALSE]
    calib_used <- "package"
    plot_all <- data.frame(gene = full$gene, logFC = log2(full$FC_package), negLog10P = -log10(full$p_package),
                           FDR = full$FDR_package, stringsAsFactors = FALSE)
  }
  rownames(sig) <- NULL
  plot_sig <- plot_all[!is.na(plot_all$FDR) & plot_all$FDR < p$fdr, , drop = FALSE]
  rownames(plot_sig) <- NULL

  f_full <- opath("diffRegulation_full.csv")
  f_sig  <- opath("diffRegulation_significant.csv")
  write.csv(full, f_full, row.names = FALSE, fileEncoding = "UTF-8")
  write.csv(sig,  f_sig,  row.names = FALSE, fileEncoding = "UTF-8")
  sm_set("full_csv", f_full)
  sm_set("sig_csv", f_sig)
  sm_set("sig_genes", nrow(sig))
  sm_set("calibration_used", calib_used)

  ## —— 两张图（正方形、宽高相等、dpi=200、共用同一个 SIDE）——
  SUB <- sprintf("Virtual knockout of %s  |  HVG panel %d genes (MT/ribo removed)  |  calibration: %s",
                 p$gko, nrow(X),
                 if (isTRUE(p$exclude_gko)) "target gene excluded" else "package default (target included)")
  n_sig <- nrow(plot_sig)
  if (n_sig != nrow(sig))
    vk("NOTE|绘图口径的显著数（%d）与显著表行数（%d）不一致，请检查校准口径", n_sig, nrow(sig))

  SIDE <- max(8, 0.20 * max(1, n_sig) + 3.2)
  vk("NOTE|出图尺寸：两张均为正方形 %.1f x %.1f 英寸（dpi=200）", SIDE, SIDE)

  f1 <- opath("fig1_bar_Differentially_Related_Genes.png")
  if (n_sig > 0) {
    s <- plot_sig; s$gene <- factor(s$gene, levels = s$gene[order(s$logFC)])
    p1 <- ggplot(s, aes(x = logFC, y = gene)) +
      geom_col(fill = "#C0504D", width = 0.7) +
      geom_vline(xintercept = 0, colour = "grey40", linewidth = 0.3) +
      labs(title = "Differentially Related Genes", subtitle = SUB, x = "logFC", y = NULL) +
      theme_bw(base_size = 11) +
      theme(plot.title = element_text(face = "bold", hjust = 0.5),
            plot.subtitle = element_text(hjust = 0.5, size = 8),
            panel.grid.major.y = element_blank())
  } else {
    vk("NOTE|显著基因数为 0，柱状图按空面板出图（保证 §9 的 6 件产物齐全）")
    p1 <- ggplot() +
      annotate("text", x = 0, y = 0, label = "no significant genes", size = 4, colour = "grey40") +
      labs(title = "Differentially Related Genes", subtitle = SUB, x = "logFC", y = NULL) +
      theme_bw(base_size = 11) +
      theme(plot.title = element_text(face = "bold", hjust = 0.5),
            plot.subtitle = element_text(hjust = 0.5, size = 8))
  }
  save_png(p1, f1, SIDE)
  vk(paste0("NOTE|已写出：", f1))

  ## 散点图：显著 = #C0504D / 不显著 = #4F81BD；图例在底部；yintercept = -log10(FDR) 虚线
  d <- plot_all
  sig_lab <- sprintf("significant (FDR<%g), n=%d", p$fdr, n_sig)
  d$sigFlag <- ifelse(!is.na(d$FDR) & d$FDR < p$fdr, sig_lab, "not significant")
  p2 <- ggplot(d, aes(x = logFC, y = negLog10P)) +
    geom_hline(yintercept = -log10(p$fdr), linetype = "dashed", colour = "grey50", linewidth = 0.3) +
    geom_point(aes(colour = sigFlag), size = 1.8, alpha = 0.8) +
    scale_colour_manual(values = setNames(c("#C0504D", "#4F81BD"), c(sig_lab, "not significant")), name = NULL) +
    labs(title = "Differentially Related Genes", subtitle = SUB,
         x = "logFC", y = "-log10 (Pvalue)") +
    theme_bw(base_size = 11) +
    theme(plot.title = element_text(face = "bold", hjust = 0.5),
          plot.subtitle = element_text(hjust = 0.5, size = 8), legend.position = "bottom")
  f2 <- opath("fig2_scatter_Differentially_Related_Genes.png")
  save_png(p2, f2, SIDE)
  vk(paste0("NOTE|已写出：", f2))

  ## 完整结果对象（网络 + 对齐，供将来 plotKO 用）
  f_rds <- opath("virtual_knockout_result.rds")
  saveRDS(res, f_rds)
  sm_set("fig1_bar", f1)
  sm_set("fig2_scatter", f2)
  sm_set("result_rds", f_rds)
  sm_set("fig_side_inch", SIDE)

  # ---------------------------------------------------------------------------
  ## §9 收尾：run_summary.txt（key<TAB>value，UTF-8）+ DONE
  # ---------------------------------------------------------------------------
  step_line(8, "写出运行小结")

  sm_set("elapsed_total_s", sprintf("%.1f", as.numeric(difftime(Sys.time(), t_wall, units = "secs"))))
  f_sum <- opath("run_summary.txt")
  con <- file(f_sum, open = "wb")
  writeLines(sprintf("%s\t%s", names(SM), SM), con, useBytes = TRUE)
  close(con)

  vk("DONE|out_dir=%s", p$out_dir)
  quit(save = "no", status = 0L)

}, error = function(e) {
  ## 兜底：非合同错误（例如包内部报错）也要把原因打进 [VK] 日志，不许静默
  msg <- conditionMessage(e)
  if (!grepl("^\\[VK\\] ERROR\\|", msg)) vk("ERROR|%s", msg)
  cc <- tryCatch(paste(utils::head(deparse(conditionCall(e)), 5), collapse = " "), error = function(e2) "")
  if (nzchar(cc)) vk(paste0("NOTE|出错调用：", cc))
  quit(save = "no", status = 1L)
})
