#!/usr/bin/env Rscript
# -*- coding: utf-8 -*-
# =============================================================================
# 空转「输入基因 / 基因集 → 出表达量图」按需出图脚本（独立工具，**不是构建脚本**）
# -----------------------------------------------------------------------------
# 与 spatial_pipeline.R 的分工：
#   · spatial_pipeline.R = 逐条对齐参考脚本的**构建**脚本（产出 .rds + 全量图集）；
#   · 本脚本          = **按需**出图工具，一次进程、一次 readRDS、循环画完所有基因。
#   本脚本**不写** _figure_manifest.csv / _atlas_summary.json 等任何图集文件
#   （契约 §9.1 硬要求：按需图必须落在独立目录，figure_set_id 不许变、用户评分不受影响）。
#
# ★ 为什么要另起一个脚本而不是复用单细胞那套（侦察 §7 坑 1，实测依据）：
#   单细胞 R 版是「每个基因起一个独立 Rscript 子进程 + 每次子进程都 readRDS 整个数据集」
#   （sc_umap_initial_r_analysis.py:194-203 + run_umap_plots.R:33）⇒ **N 个基因 = N 次全量重载**。
#   空转成品 475 MB / readRDS 实测 5.53 s，照抄就是灾难。本脚本改成"一次加载 + 循环"。
#
# ★ 四条硬安全要求（契约 §9.4 + 本会话实测事故）：
#   1) 加载后**立刻**把 Idents 设成 seurat_clusters（契约 §9.6）——M1 的 .rds 里 Idents 仍是样本名
#      （merge 的遗留），不设的话任何按 Idents 分组的图会静默退化成"按样本"；
#   2) **绝不交互**：无 readline/menu/file.choose/setwd；缺包/缺目录一律 stop()；
#      options(menu.graphics = FALSE)。依据：本会话实测"非 ASCII 路径 → R 弹目录菜单 →
#      在 rpy2 下变成无限循环 + 1.14 GB 失控日志"（spatial_rpy2_recipe.md §5）；
#   3) **out_dir 与 rds_path 必须全 ASCII**，否则直接报错退出，**不做任何兜底**；
#   4) **逐基因 tryCatch**：某个基因画不出来**不中断**整次运行，原因记进结果，继续下一个。
#
# CLI（冻结）：
#   Rscript spatial_gene_expression.R <rds_path> <out_dir> <dataset_id> <genes_file> [--dpi 300]
#     genes_file : 纯文本，**每行一个基因**（由 Python 侧写好 —— 不靠 argv 传长列表，
#                  避免命令行长度与转义问题）
#     out_dir    : **数据集输出根**（即 OUTPUT/<dataset_id>）；
#                  本脚本在其下建 08_GeneOnDemand/<基因>/ 与 08_GeneOnDemand/_geneset/
# 输出：最后一行 cat() 一段**机器可读 JSON**（前缀 ##SPATIAL_GENE_RESULT##），字段见文件末。
#
# 本文件**字符串字面量与标识符均为 ASCII**（中文只在注释里），以把跨编码风险降到最低。
# =============================================================================

suppressPackageStartupMessages({
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    cat("##SPATIAL_GENE_RESULT##{\"ok\":false,\"error\":\"R package 'Seurat' not available\"}\n")
    quit(status = 3, save = "no")
  }
  library(Seurat)
})

options(menu.graphics = FALSE)   # 双保险：即便被交互式调用也不弹图形菜单

# -----------------------------------------------------------------------------
# 只读、不交互的小工具
# -----------------------------------------------------------------------------
.is_ascii <- function(p) is.character(p) && length(p) == 1L && !is.na(p) && !grepl("[^ -~]", p)

# 基因名做**目录名**使用，必须收窄字符集（Python 侧也会过滤，这里是第二道闸）
.is_safe_gene <- function(g) grepl("^[A-Za-z0-9][A-Za-z0-9_.-]*$", g)

.fail <- function(msg, code = 2L) {
  # 硬失败：**不抛异常给调用栈**，而是打印机器可读结果后以非零码退出
  cat("##SPATIAL_GENE_RESULT##",
      jsonlite::toJSON(list(ok = FALSE, error = msg), auto_unbox = TRUE), "\n", sep = "")
  quit(status = code, save = "no")
}

# -----------------------------------------------------------------------------
# 0. 参数解析
# -----------------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
.USAGE_GENEXPR <- paste0(
  "usage: Rscript spatial_gene_expression.R <rds_path> <out_dir> <dataset_id> <genes_file> ",
  "[--dpi 300] [--samples GSM7596587,GSM7596588]\n")

# 位置参数 + 具名选项混合解析：**选项可出现在任意位置**
# （旧的"args[5] 必须是 --dpi"写法在加第二个选项后必然出问题）
rds_path <- NULL; out_dir <- NULL; dataset_id <- NULL; genes_file <- NULL
dpi_val <- 300L
samples_arg <- NULL
.i <- 1L
while (.i <= length(args)) {
  .a <- args[.i]
  if (identical(.a, "--dpi")) {
    if (.i + 1L > length(args)) { cat(.USAGE_GENEXPR); quit(status = 2, save = "no") }
    dpi_val <- suppressWarnings(as.integer(args[.i + 1L]))
    if (is.na(dpi_val) || dpi_val < 50L || dpi_val > 1200L) {
      cat("##SPATIAL_GENE_RESULT##{\"ok\":false,\"error\":\"invalid --dpi (expect 50..1200)\"}\n")
      quit(status = 2, save = "no")
    }
    .i <- .i + 2L; next
  }
  if (identical(.a, "--samples")) {
    if (.i + 1L > length(args)) { cat(.USAGE_GENEXPR); quit(status = 2, save = "no") }
    .raw_s <- trimws(strsplit(args[.i + 1L], ",", fixed = TRUE)[[1]])
    samples_arg <- .raw_s[nzchar(.raw_s)]
    if (length(samples_arg) == 0L) samples_arg <- NULL
    .i <- .i + 2L; next
  }
  if (grepl("^--", .a)) {
    cat("unknown option: ", .a, "\n", sep = "")
    cat(.USAGE_GENEXPR); quit(status = 2, save = "no")
  }
  if (is.null(rds_path))        rds_path   <- .a
  else if (is.null(out_dir))    out_dir    <- .a
  else if (is.null(dataset_id)) dataset_id <- .a
  else if (is.null(genes_file)) genes_file <- .a
  else { cat("too many positional arguments\n"); cat(.USAGE_GENEXPR); quit(status = 2, save = "no") }
  .i <- .i + 1L
}
if (is.null(rds_path) || is.null(out_dir) || is.null(dataset_id) || is.null(genes_file)) {
  cat(.USAGE_GENEXPR)
  quit(status = 2, save = "no")
}

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  # 契约允许"jsonlite 不可用则退化为 key=value"，但**必须先断言**；这里直接判失败更安全
  cat("##SPATIAL_GENE_RESULT##{\"ok\":false,\"error\":\"R package 'jsonlite' not available\"}\n")
  quit(status = 3, save = "no")
}

# ---- 硬安全要求 3：路径必须全 ASCII（不做兜底）----
if (!.is_ascii(out_dir)) {
  .fail("out_dir contains non-ASCII characters; refusing to run (would risk R interactive prompt / rpy2 hang)")
}
if (!.is_ascii(rds_path)) {
  .fail("rds_path contains non-ASCII characters; refusing to run")
}
if (!.is_ascii(dataset_id)) {
  .fail("dataset_id contains non-ASCII characters; refusing to run")
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
unsafe_genes <- genes[!.is_safe_gene(genes)]           # 非法字符（做目录名不安全）
genes <- genes[.is_safe_gene(genes)]
genes <- genes[!duplicated(genes)]
if (length(genes) == 0L) {
  .fail("no valid gene names after parsing genes_file", code = 2L)
}
# 上限 20（契约 §9.3；Python 侧也会拦截，这里是第二道闸）
if (length(genes) > 20L) {
  .fail(paste0("too many genes (", length(genes), "); limit is 20"), code = 2L)
}

t_start <- Sys.time()
run_id <- format(t_start, "%Y%m%d-%H%M%S")

# -----------------------------------------------------------------------------
# 2. 输出目录（先建再断言存在；**绝不依赖 R 的交互式建目录**）
# -----------------------------------------------------------------------------
on_demand_root <- file.path(out_dir, "08_GeneOnDemand")
dir.create(on_demand_root, showWarnings = FALSE, recursive = TRUE)
if (!dir.exists(on_demand_root)) {
  .fail(paste0("cannot create on-demand figure root: ", on_demand_root))
}
progress_path <- file.path(on_demand_root, "_progress.jsonl")
try(writeLines(character(0), progress_path), silent = TRUE)   # 每次运行重置进度文件

# -----------------------------------------------------------------------------
# 3. 一次 readRDS（核心改进点）+ Idents 修复 + 与图集一致的 spot 范围
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

# 与图集一致：只在 QC 通过的 spot 上画（图集里的 gene_spatial 也是这么画的）
n_spots_raw <- ncol(obj)
spots_filtered <- FALSE
if ("pass_qc" %in% colnames(obj@meta.data)) {
  keep <- colnames(obj)[which(obj@meta.data[["pass_qc"]])]
  if (length(keep) > 0L && length(keep) < n_spots_raw) {
    obj <- subset(obj, cells = keep)
    spots_filtered <- TRUE
  }
}

# ★★ 留一份"已过 QC 的**全部样本**"对象（用户第 5 轮明确要求："表达量 UMAP 要画所有的样本"）。
#   ⚠ 必须是**这一次 pass_qc 过滤之后**的对象，不能用刚 readRDS 出来的原始对象 ——
#     图集里的 gene_spatial 也是在 QC 通过的 spot 上画的，用未过滤对象会让 UMAP 与图集口径不一致。
#   ⚠ 它**只服务 UMAP**；空间图 / 基因集评分空间图仍然走子集后的 obj（那才是"选样本"的意义）。
obj_all <- obj

# ★ 样本子集：只画用户选中的样本（用户第二轮实测："绘制表达量图依旧是搞的全部样本"）
#   写法选**显式 cells=**，而不是 `subset = orig.ident %in% samples`：
#     两者实测结果一致（都是 6404 个 spot、3 张 image），但 cells= 不依赖 subset() 内部表达式的
#     求值环境，也不会被 sample/orig.ident 这类名字遮蔽 ⇒ 更不容易再漂。
n_samples_available <- length(unique(as.character(obj@meta.data[["orig.ident"]])))
samples_requested <- if (is.null(samples_arg)) character(0) else as.character(samples_arg)
samples_used <- character(0)
samples_missing <- character(0)
samples_filtered <- FALSE
if (length(samples_requested) > 0L) {
  .avail <- unique(as.character(obj@meta.data[["orig.ident"]]))
  samples_used <- intersect(samples_requested, .avail)
  samples_missing <- setdiff(samples_requested, .avail)
  # ★ 如实报错，**绝不静默退化成"画全部"**（协调者硬要求）
  if (length(samples_missing) > 0L) {
    .fail(paste0("requested sample(s) not found in the object: [",
                 paste(samples_missing, collapse = ","), "] | available: [",
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
# 面板数 = 实际参与出图的样本数（也是下面自适应图幅的依据）
n_panels <- length(unique(as.character(obj@meta.data[["orig.ident"]])))

# 明确 print 出来，便于在 stdout 里直接看到"到底画了几个样本"
cat("[spatial_gene] samples_available =", n_samples_available,
    "| samples_requested =", if (length(samples_requested)) paste(samples_requested, collapse = ",") else "(all)",
    "| samples_used =", paste(unique(as.character(obj@meta.data[["orig.ident"]])), collapse = ","),
    "| n_panels =", n_panels,
    "| spots =", ncol(obj), "\n")

all_genes <- rownames(obj)
n_all_genes <- length(all_genes)
available_genes_sample <- head(all_genes, 5000L)

# -----------------------------------------------------------------------------
# 4. 逐基因出图（硬安全要求 4：单基因失败不中断）
# -----------------------------------------------------------------------------
# ★ 图幅**按样本数自适应**（用户第二轮实测："出图也是很不清晰……字都看不清"）：
#   每行**最多 3 列**（只有 1 个样本就 1 列），单面板保持约 6×5 英寸
#   ⇒ 面板不会再被摊成"19 个塞进 20×13 英寸"那种看不清的大小。
#   代价：样本数多时总图幅变大（19 样本 → 3 列 × 7 行 = 18×35 英寸），见文件末的实测/估算说明。
ncol_use <- max(1L, min(3L, n_panels))
nrow_use <- ceiling(n_panels / ncol_use)
spatial_w <- 6 * ncol_use
spatial_h <- 5 * nrow_use
umap_w <- 8; umap_h <- 6              # UMAP 是单面板，不需要网格自适应

# 单张图落盘（PNG / PDF 通用）：**设备由文件扩展名决定**，ggsave 自己认。
# 为什么一个函数同时管两种：本轮要给"一键导出全部 PDF"补 PDF（用户第 5 轮），
#   把落盘逻辑合成一处，避免 PNG/PDF 两条路径的校验行为分叉。
.save_fig_file <- function(plot, path, w, h) {
  # 出图 + **落盘后立刻校验**（ggsave 失败在 R 里常以 warning 而非 error 出现 ⇒ 会静默产出缺失）。
  # ⚠ 刻意**不**给 tryCatch 装 warning= 处理器：那会在任何 warning 上中断 ggsave，
  #   而 SpatialFeaturePlot/ggsave 的常规 warning（如 "Scale for fill is already present"）很常见。
  #   正确做法 = 让 warning 正常打印到 stderr，靠**文件存在性/大小**判定是否真失败。
  ok <- tryCatch({
    ggplot2::ggsave(filename = path, plot = plot, width = w, height = h,
                    dpi = dpi_val, limitsize = FALSE)
    TRUE
  }, error = function(e) {
    cat("[spatial_gene] ggsave error:", conditionMessage(e), "\n", file = stderr())
    FALSE
  })
  if (!isTRUE(ok) || !file.exists(path) || file.size(path) < 512) {
    stop("figure not written (missing or smaller than 512 bytes): ", path)
  }
  invisible(TRUE)
}

per_gene <- list()
n_ok <- 0L; n_not_found <- 0L; n_error <- 0L
for (i in seq_along(genes)) {
  g <- genes[i]
  ts <- Sys.time()
  # ⚠ pdf_files 是**本轮新增的独立字段**（用户第 5 轮要"一键导出全部 PDF"）。
  #   `files` 的语义与顺序**一个字都不许改**：bind 的 _gene_result_files() 把 files 里
  #   每一个文件摊成一个页签，PDF 若混进 files 会让同一基因出现两个页签、页面直接坏掉。
  rec <- list(gene = g, status = "error", files = character(0),
              pdf_files = character(0), error = "")
  gdir <- file.path(on_demand_root, g)
  if (!(g %in% all_genes)) {
    rec$status <- "not_found"
    rec$error <- "gene not present in rownames(object)"
    n_not_found <- n_not_found + 1L
  } else {
    res <- tryCatch({
      dir.create(gdir, showWarnings = FALSE, recursive = TRUE)
      if (!dir.exists(gdir)) stop("cannot create gene dir: ", gdir)
      f_spatial     <- file.path(gdir, paste0(g, "_spatial.png"))
      f_spatial_pdf <- file.path(gdir, paste0(g, "_spatial.pdf"))
      f_umap        <- file.path(gdir, paste0(g, "_umap.png"))
      f_umap_pdf    <- file.path(gdir, paste0(g, "_umap.pdf"))
      # 空间图：**只画选中样本**（obj）—— 这正是"选样本"的意义
      p1 <- SpatialFeaturePlot(obj, features = g, pt.size.factor = 2, stroke = NA, ncol = ncol_use)
      .save_fig_file(p1, f_spatial, spatial_w, spatial_h)
      .save_fig_file(p1, f_spatial_pdf, spatial_w, spatial_h)
      # ★ UMAP 表达图：**画全部样本**（obj_all，已过 QC）—— 用户第 5 轮明确要求；
      #   画幅/几何/文件名都不变，也不参与 n_panels 的网格自适应（UMAP 是单面板）。
      p2 <- FeaturePlot(obj_all, features = g, reduction = "umap", pt.size = 0.3)
      .save_fig_file(p2, f_umap, umap_w, umap_h)
      .save_fig_file(p2, f_umap_pdf, umap_w, umap_h)
      list(status = "ok",
           files = c(f_spatial, f_umap),                       # 仍然**只含 PNG**，顺序不变
           pdf_files = c(f_spatial_pdf, f_umap_pdf),           # 与 files 一一对应、顺序一致
           error = "")
    }, error = function(e) {
      list(status = "error", files = character(0), pdf_files = character(0),
           error = conditionMessage(e))
    })
    rec$status <- res$status
    # ⚠ 用 I() 包住：toJSON(auto_unbox=TRUE) 会把**长度为 1** 的向量脱成标量，
    #   于是 files 在"1 个文件"与"2 个文件"时 JSON 类型不同（字符串 vs 数组）⇒ 调用方会踩。
    #   I() 强制它永远序列化成数组。
    rec$files     <- I(as.character(res$files))
    rec$pdf_files <- I(as.character(res$pdf_files))
    rec$error     <- res$error
    if (identical(res$status, "ok")) n_ok <- n_ok + 1L else n_error <- n_error + 1L
  }
  per_gene[[g]] <- rec
  # 进度：stdout 在本机子进程里是全量缓冲的（拿不到中途进度），所以另写独立的进度文件
  try({
    line <- jsonlite::toJSON(list(run_id = run_id, i = i, n = length(genes), gene = g,
                                  status = rec$status,
                                  elapsed = round(as.numeric(difftime(Sys.time(), ts, units = "secs")), 2)),
                             auto_unbox = TRUE)
    cat(line, "\n", sep = "", file = progress_path, append = TRUE)
  }, silent = TRUE)
}

# -----------------------------------------------------------------------------
# 5. 基因集（≥2 个且在库的基因）→ AddModuleScore 空间评分图
# -----------------------------------------------------------------------------
gene_set <- list(enabled = FALSE, genes_used = character(0), files = character(0),
                 pdf_files = character(0), error = "")
found_genes <- genes[vapply(genes, function(g) g %in% all_genes, logical(1))]
if (length(genes) >= 2L) {
  gene_set$enabled <- TRUE
  if (length(found_genes) < 2L) {
    gene_set$error <- "fewer than 2 requested genes are present; score plot skipped"
  } else {
    res <- tryCatch({
      sdir <- file.path(on_demand_root, "_geneset")
      dir.create(sdir, showWarnings = FALSE, recursive = TRUE)
      if (!dir.exists(sdir)) stop("cannot create gene-set dir: ", sdir)
      # AddModuleScore 会给新列加后缀 "1"（与构建脚本 :479 同一策略）
      scored <- AddModuleScore(obj, features = list(found_genes), name = "GeneSetScore",
                               assay = DefaultAssay(obj), ctrl = 100, seed = 1, verbose = FALSE)
      score_col <- grep("^GeneSetScore", colnames(scored@meta.data), value = TRUE)[1]
      if (is.na(score_col)) stop("AddModuleScore did not produce a score column")
      f_score <- file.path(sdir, paste0(dataset_id, "_geneset_score_spatial.png"))
      f_score_pdf <- file.path(sdir, paste0(dataset_id, "_geneset_score_spatial.pdf"))
      p <- SpatialFeaturePlot(scored, features = score_col, pt.size.factor = 2,
                              stroke = NA, ncol = ncol_use)
      .save_fig_file(p, f_score, spatial_w, spatial_h)
      .save_fig_file(p, f_score_pdf, spatial_w, spatial_h)
      # 基因清单留档，便于回溯"这张评分图用的是哪几个基因"
      writeLines(genes, file.path(sdir, paste0(dataset_id, "_geneset_genes.txt")))
      list(err = "", files = c(f_score), pdf_files = c(f_score_pdf))
    }, error = function(e) {
      list(err = conditionMessage(e), files = character(0), pdf_files = character(0))
    })
    gene_set$error <- res$err
    gene_set$files <- I(as.character(res$files))            # I() 理由同上：保证永远是数组
    gene_set$pdf_files <- I(as.character(res$pdf_files))    # 与 files 一一对应、顺序一致
    gene_set$genes_used <- I(as.character(found_genes))
  }
}

# -----------------------------------------------------------------------------
# 6. 机器可读结果（**最后一行**，前缀 ##SPATIAL_GENE_RESULT##）
# -----------------------------------------------------------------------------
elapsed <- as.numeric(difftime(Sys.time(), t_start, units = "secs"))
result <- list(
  ok = TRUE,
  dataset_id = dataset_id,
  rds_path = rds_path,
  out_dir = out_dir,
  on_demand_root = on_demand_root,
  dpi = dpi_val,
  run_id = run_id,
  mode = if (length(genes) >= 2L) "set" else "single",
  n_total = length(genes),
  n_ok = n_ok, n_not_found = n_not_found, n_error = n_error,
  per_gene = per_gene,
  # 下列向量一律用 I() 包住，保证**长度 1 时也是 JSON 数组**（auto_unbox 会脱成标量）
  not_found = I(as.character(genes[vapply(genes, function(g) !(g %in% all_genes), logical(1))])),
  dropped_unsafe_genes = I(as.character(unsafe_genes)),
  # 基因空间预检：总基因数 + 一段样本（全量 22426 个名字不必要地占体积）
  available_genes = I(as.character(available_genes_sample)),
  available_genes_n = n_all_genes,
  available_genes_truncated = n_all_genes > length(available_genes_sample),
  gene_check = list(
    requested = I(as.character(genes)),
    hit = I(as.character(found_genes)),
    miss = I(as.character(genes[!(genes %in% all_genes)]))
  ),
  gene_set_score = gene_set,
  idents_fixed = idents_fixed,
  idents_nlevels = if (idents_fixed) nlevels(Idents(obj)) else 0L,
  n_spots_raw = n_spots_raw,
  n_spots_plotted = ncol(obj),
  spots_filtered_to_pass_qc = spots_filtered,
  # ★ 样本子集信息（用户第二轮实测新增）：让调用方能自证"真的只画了选中的样本"
  n_samples_available = n_samples_available,
  n_panels = n_panels,
  samples_requested = I(as.character(samples_requested)),
  samples_used = I(as.character(samples_used)),
  samples_missing = I(as.character(samples_missing)),
  samples_filtered = samples_filtered,
  figure_layout = list(ncol = ncol_use, nrow = nrow_use,
                       panel_width_in = 6, panel_height_in = 5,
                       spatial_width_in = spatial_w, spatial_height_in = spatial_h,
                       umap_width_in = umap_w, umap_height_in = umap_h),
  readRDS_sec = round(readRDS_sec, 2),
  elapsed_sec = round(elapsed, 2)
)
cat("##SPATIAL_GENE_RESULT##",
    jsonlite::toJSON(result, auto_unbox = TRUE, null = "null", digits = 6), "\n", sep = "")
quit(status = 0, save = "no")
