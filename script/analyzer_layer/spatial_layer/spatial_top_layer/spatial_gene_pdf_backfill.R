#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# =============================================================================
# L2 补账（Phase 4）：为 `gene_spatial` / `gene_panel` 两个图型**补 PDF**
# -----------------------------------------------------------------------------
# 背景：`spatial_pipeline.R` 里其他图型都是 PNG+PDF 成对（`if (do_pdf) .save_fig(...)`），
#       **唯独 STAGE5 的 `gene_spatial`（:458）与 `gene_panel`（:463）漏了 PDF 那两行**，
#       所以图集里这两个图型只有 PNG ⇒「导出全部 PDF」比 PNG 少 2 张。
#
# ★ 本脚本**只补 PDF**，严格做到：
#     1. **只写 `<fig_root>/03_GeneSpatial/*.pdf`** —— 绝不动既有 PNG（它们是对的）；
#     2. **绝不写 `_figure_manifest.csv`**
#        （`spatial_pipeline.R` 的 `.merge_write_fig_csv()` 会用 `write.csv` **重排既有行**，
#         那会违反"只追加、不改既有 297 行"；追加由外层按字节做）；
#     3. 绘图代码**逐字复刻** `spatial_pipeline.R:452-463`，参数取自同一份
#        `default_fig_opts()` / `.fig_theme()`，所以 PDF 是当初那些 PNG 的矢量孪生。
#     ⇒ 因此**不重跑** `run_spatial_figures_only()`（它会把 7 张 PNG 重画一遍）。
#
# CLI：
#   Rscript spatial_gene_pdf_backfill.R --rds <p> --fig-root <OUTPUT/ds> --pipeline <spatial_pipeline.R>
# =============================================================================

suppressPackageStartupMessages({
  if (!requireNamespace("jsonlite", quietly = TRUE)) { cat("##PDF_BACKFILL##{\"ok\":false,\"error\":\"jsonlite missing\"}\n"); quit(status = 3, save = "no") }
})
options(menu.graphics = FALSE)
.is_ascii <- function(p) is.character(p) && length(p) == 1L && !is.na(p) && !grepl("[^ -~]", p)

argv <- commandArgs(trailingOnly = TRUE)
opt <- list(); i <- 1L
while (i <= length(argv)) {
  a <- argv[i]
  if (grepl("^--", a)) {
    k <- sub("^--", "", a)
    if (i + 1L > length(argv)) { cat("bad args\n"); quit(status = 2, save = "no") }
    opt[[k]] <- argv[i + 1L]; i <- i + 2L
  } else i <- i + 1L
}
if (is.null(opt$rds) || is.null(opt[["fig-root"]]) || is.null(opt$pipeline)) {
  cat("usage: Rscript spatial_gene_pdf_backfill.R --rds <p> --fig-root <d> --pipeline <p>\n")
  quit(status = 2, save = "no")
}
rds_path <- opt$rds; fig_root <- opt[["fig-root"]]; pipe_path <- opt$pipeline
for (p in list(rds_path, fig_root, pipe_path)) {
  if (!.is_ascii(p)) { cat("##PDF_BACKFILL##{\"ok\":false,\"error\":\"non-ASCII path refused\"}\n"); quit(status = 2, save = "no") }
}
if (!file.exists(rds_path))  { cat("##PDF_BACKFILL##{\"ok\":false,\"error\":\"rds not found\"}\n"); quit(status = 2, save = "no") }
if (!file.exists(pipe_path)) { cat("##PDF_BACKFILL##{\"ok\":false,\"error\":\"pipeline not found\"}\n"); quit(status = 2, save = "no") }

t0 <- Sys.time()
# ★ 关键：spatial_pipeline.R 末尾是 `if (sys.nframe() == 0L) .cli_main()`，
#   所以 source() **只定义函数、不干重活**（这是它给出的官方用法）。
source(pipe_path, encoding = "UTF-8")
# ★ .make_figures() 是在**函数内** library(ggplot2/patchwork) 的；本脚本在函数外调 ggtitle()，
#   所以必须自己把它们挂上（漏了这一步会 `could not find function "ggtitle"`，已踩过）。
suppressPackageStartupMessages({ library(ggplot2); library(patchwork); library(Seurat) })
d5 <- file.path(fig_root, "03_GeneSpatial")
if (!dir.exists(d5)) { cat("##PDF_BACKFILL##{\"ok\":false,\"error\":\"03_GeneSpatial missing\"}\n"); quit(status = 2, save = "no") }

cat("[pdf_backfill] readRDS ", rds_path, " (", round(file.size(rds_path) / 1048576, 1), " MB)\n", sep = "", file = stderr())
obj <- readRDS(rds_path)

## ---- 与 spatial_pipeline.R `.make_figures()` 完全同构的对象准备（:329-350）----
fopts <- default_fig_opts()
lit_theme <- .fig_theme()
dpi <- fopts$dpi
psv <- fopts$pt_size_factor
sub <- subset(obj, subset = pass_qc)
sub <- .set_cluster_ident(sub)          # ★ 与出图入口同一行（修复 1），保证口径一致
genes_show <- intersect(fopts$genes_show, rownames(sub))
cat("[pdf_backfill] dpi=", dpi, " psv=", psv, " genes=[", paste(genes_show, collapse = ","),
    "] | QC spots=", ncol(sub), "\n", sep = "", file = stderr())
if (length(genes_show) == 0L) { cat("##PDF_BACKFILL##{\"ok\":false,\"error\":\"no genes intersect\"}\n"); quit(status = 2, save = "no") }

out <- list(); n_ok <- 0L; n_bad <- 0L
.save_pdf_only <- function(plot, path, w, h) {
  note <- ""
  tryCatch(
    ggplot2::ggsave(filename = path, plot = plot, width = w, height = h, dpi = dpi, limitsize = FALSE),
    error = function(e) note <<- conditionMessage(e)
  )
  ok <- file.exists(path) && file.size(path) > 512 && !nzchar(note)
  cat("[pdf_backfill] ", if (ok) "OK  " else "FAIL", " ", basename(path), " bytes=",
      if (file.exists(path)) file.size(path) else 0, if (nzchar(note)) paste0(" | ", note) else "",
      "\n", sep = "", file = stderr())
  ok
}

## ---- 逐字复刻 spatial_pipeline.R:452-463（只把 .png 换成 .pdf）----
for (g in genes_show) {
  p <- SpatialFeaturePlot(sub, features = g, pt.size.factor = psv, stroke = NA, ncol = 5) +
    lit_theme + ggtitle(g)
  fp <- file.path(d5, paste0(g, "_Spatial.pdf"))
  ok <- .save_pdf_only(p, fp, 20, 13)
  out[[length(out) + 1L]] <- list(figure_type = "gene_spatial", path = fp,
                                  bytes = if (file.exists(fp)) as.numeric(file.size(fp)) else 0,
                                  ok = ok)
  if (ok) n_ok <- n_ok + 1L else n_bad <- n_bad + 1L
}
p_panel <- SpatialFeaturePlot(sub, features = genes_show, pt.size.factor = psv,
                              stroke = NA, ncol = 3) + lit_theme
fp <- file.path(d5, "00_Genes_Expression_Panel.pdf")
ok <- .save_pdf_only(p_panel, fp, 18, 15)
out[[length(out) + 1L]] <- list(figure_type = "gene_panel", path = fp,
                                bytes = if (file.exists(fp)) as.numeric(file.size(fp)) else 0,
                                ok = ok)
if (ok) n_ok <- n_ok + 1L else n_bad <- n_bad + 1L

res <- list(ok = (n_bad == 0L), n_pdf = length(out), n_ok = n_ok, n_bad = n_bad,
            genes = I(as.character(genes_show)), fig_root = fig_root, items = out,
            manifest_written = FALSE,
            elapsed_sec = round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 1))
j <- jsonlite::toJSON(res, auto_unbox = TRUE, null = "null", digits = 8)
cat("##PDF_BACKFILL##", j, "\n", sep = "")
cat(j, "\n", sep = "")
quit(status = if (n_bad == 0L) 0 else 1, save = "no")
