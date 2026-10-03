# -*- coding: utf-8 -*-
# =============================================================================
# 空转（spatial）M1 流水线脚本 - 产出程序可直接加载的 Seurat 成品
# -----------------------------------------------------------------------------
# 血统（lineage，非调用）：
#   参考脚本「空间转录组代码参考/练习/改进版_GSE237183_逐步构建.R」（985 行 / 10 个 STAGE）。
#   本文件是它的**衍生物**；参考目录**全程只读，一字节未改**。
#
#   衍生差异（仅 5 处，算法步骤一行未改）：
#     1) 顶层脚本式代码 → 函数 run_spatial_pipeline(data_root, samples, out_root, params)
#     2) 样本集合由硬编码发现（参考 :27-38 + N_SAMPLES 只能取前 N 个）→ 显式 samples 参数（支持任意子集）
#     3) 新增最终 saveRDS（参考脚本只存中间检查点 :302/:380/:498/:723，**没有最终成品**）
#     4) 保留「未过滤全量 spot」+ pass_qc 列（参考 :376 用 `sce.all <- sce.all.qc` 覆盖了对象，
#        导致被滤掉的 spot 永久丢失、用户调小 min_nFeature 也回不来 —— 这是不可逆设计点，必须避免）
#     5) 归一化改为对**全量 spot**做（LogNormalize 是逐 spot 运算，参考 :414-415；
#        对全量做与对子集做逐 spot 等价，但能让成品对全部 spot 自洽）
#
#   M2a 起，本文件**同时负责出图**（图集写进 fig_root = OUTPUT/<dataset_id>）：
#     · 全部在 **Rscript** 下出图（离线构建阶段）；**程序内不经 rpy2 出图**（那是 M2b）。
#     · 设备沿用参考脚本的 `ggsave()`（在本机 ggplot2 4.0.3 + ragg 1.5.2 下会走 ragg::agg_png）。
#       ★ 有意**不**改设备：Rscript 路径已被 W5 实测证明可全程通过；若真出现
#       `agg could not write to the given file`，靠 §"落盘后校验"如实清点并上报，而不是换设备乱试。
#     · 逐图落盘后立刻校验（<512 字节视为失败），结果写进 <fig_root>/_figure_manifest.csv，
#       使「ggsave 只报 warning、产物静默缺失」这种失败**可被清点**。
#
# 三条入口：
#   A. CLI 全量（流水线 + 出图）：
#        Rscript spatial_pipeline.R --data_root <dir> --out_root <dir> --fig_root <dir> \
#                                   [--samples GSM7596587,GSM7596588] [--min_nFeature 200] ...
#   A2. CLI 仅出图（读已有 .rds，不重跑流水线、不覆盖 .rds）：
#        Rscript spatial_pipeline.R --figures_only --out_root <dir> --fig_root <dir>
#   B. 被 source() 调用（M2b 的 rpy2 路径）：
#        source(path)  之后调 run_spatial_pipeline(...) 或 run_spatial_figures_only(...)
#
# ⚠ source() 的 encoding 参数行为**取决于调用方 R 进程的 locale / codepage**。
#   两边的实测**相反**，所以下面把两个环境都写上 —— 只写一句就一定有一半环境是假的：
#   (1) 【Rscript 独立进程】本机实测 LC_CTYPE = Chinese (Simplified)_China.utf8、
#       l10n_info() = 1|1|0|65001|65001（codepage = 65001 / UTF-8）：
#         source(path, encoding="UTF-8") / encoding="utf8" / **不带 encoding**
#         —— 三种写法**均 defined = TRUE，全部正常**。
#   (2) 【rpy2 嵌入进程】W5 实测 LC_CTYPE = C、l10n_info() = 0|0|0|0|936（codepage = 936 / GBK）：
#         encoding="UTF-8" 会**静默无效**（0.00 s、函数未定义、**不报错**）；
#         R 原生 base::source(path, encoding="UTF-8") 与 "utf8" **同样 defined = FALSE**。
#         ⇒ 那一侧请改用 robjects.r(<str>) 或 **source(path) 不带 encoding**。
#   依据与完整配方见 docs/features/spatial_rpy2_recipe.md §5。
#   本文件的**字符串字面量与标识符均为 ASCII**，中文只出现在注释里，以把该类风险降到最低。
#
# ★★ Idents 纪律（2026-09-19 踩过的坑，改本文件前务必先读）：
#   `.rds` 里 `Idents(obj)` **可能仍是样本名**（merge 的遗留；M1 构建时只回写了
#   `@meta.data$seurat_clusters`，**没有同步 Idents**）。所以：
#     · **任何依赖 Idents 的代码都必须在入口显式重设**，不要假设对象自洽；
#     · 出图入口的重设点 = `.make_figures()` 里的 `sub <- .set_cluster_ident(sub)`（修复 1）；
#     · 构建路径的重设点 = `run_spatial_pipeline()` 里的 `full <- .set_cluster_ident(full)`（修复 2）；
#     · 能用显式写法就别靠 Idents：`group.by = "seurat_clusters"`、
#       `split(..., obj@meta.data[["seurat_clusters"]])`、或用 seurat_clusters 查表。
#   不这么做的后果（已实际发生）：`FindAllMarkers` 变成"比样本之间"、注释按样本贴、
#   未写 group.by 的 DimPlot/SpatialDimPlot 每张只剩单色 —— 全部**静默**，不报错。
# =============================================================================


suppressPackageStartupMessages({
  library(Seurat)
  library(Matrix)
})


# -----------------------------------------------------------------------------
# 参数默认值（对齐参考脚本的当前取值，逐条给出参考行号）
# -----------------------------------------------------------------------------
default_params <- function() {
  list(
    min_cells        = 3,       # 参考 :65  CreateSeuratObject(min.cells = 3)
    min_nFeature     = 200,     # 参考 :330 min_nFeature <- 200
    min_nCount       = 500,     # 参考 :331 min_nCount   <- 500
    scale_factor     = 10000,   # 参考 :415 scale.factor = 10000
    nfeatures        = 3000,    # 参考 :419 nfeatures = 3000
    npcs             = 30,      # 参考 :432 npc_use <- 30
    pc_use           = 30,      # 参考 :451 pc.use <- 1:30
    resolution       = 0.8,     # 参考 :452 res.use <- 0.8
    umap_n_neighbors = 30,      # 参考 :461 n_neighbors = 30
    umap_seed        = 42,      # 参考 :460 set.seed(42)
    do_umap          = TRUE,    # 参考 :459-466
    mito_pattern     = NULL     # NULL = 参考 :228/:232 的两级探测（^MT- 优先，落空退 ^M-）
  )
}


# -----------------------------------------------------------------------------
# 小工具
# -----------------------------------------------------------------------------
.sp_log <- function(...) {
  cat(sprintf("[%s] ", format(Sys.time(), "%H:%M:%S")), ..., "\n", sep = "")
}

#' 探测某样本的“样本代号”，用于 manifest 的 label 字段
#' 来源：数据根**顶层散件**文件名 `<GSM>_<代号>_matrix.mtx[.gz]`（房内台账 §5.1 的对应关系）
#' 取不到就退化为只用 GSM 编号 —— **不报错**，label 是展示用，不是身份键
.detect_sample_label <- function(data_root, gsm) {
  pat <- paste0("^", gsm, "_.*_matrix\\.mtx(\\.gz)?$")
  files <- list.files(data_root, pattern = pat, full.names = FALSE)
  if (length(files) == 0) return(gsm)
  code <- sub(paste0("^", gsm, "_(.*)_matrix\\.mtx(\\.gz)?$"), "\\1", files[1])
  if (!nzchar(code) || identical(code, files[1])) return(gsm)
  paste0(gsm, " / ", code)
}

#' 读单个 Visium 样本目录 → Seurat 对象（对应参考 :51-84）
.read_one_sample <- function(data_root, pro, min_cells) {
  h5 <- file.path(data_root, pro, "filtered_feature_bc_matrix.h5")
  if (!file.exists(h5)) stop("sample matrix not found: ", h5)
  data <- Read10X_h5(filename = h5)
  # Read10X_h5 在多 feature 类型时返回 list，这里只取 Gene Expression
  if (is.list(data) && !is.null(data[["Gene Expression"]])) data <- data[["Gene Expression"]]

  obj <- CreateSeuratObject(counts = data, assay = "Spatial",
                            min.cells = min_cells, project = pro)

  # 空间图像（参考 :69-81）；图像目录本身在样本目录内，文件名固定
  img <- tryCatch(
    Read10X_Image(image.dir = file.path(data_root, pro),
                  image.name = "tissue_lowres_image.png",
                  filter.matrix = TRUE),
    error = function(e) NULL
  )
  if (!is.null(img)) {
    img <- img[Cells(obj)]
    DefaultAssay(img) <- "Spatial"
    obj[[pro]] <- img
  }
  obj
}

#' 把在子集（QC 通过）上算出的降维结果搬回全量对象：非该子集的 spot 一律 NA
#' 这样成品既保留**全量 spot**，又带有可用的降维/聚类结果
.transfer_reduction <- function(full, sub, reduction, key) {
  src <- sub[[reduction]]
  if (is.null(src)) return(full)
  emb <- Embeddings(src)
  m <- matrix(NA_real_, nrow = ncol(full), ncol = ncol(emb),
              dimnames = list(colnames(full), colnames(emb)))
  m[rownames(emb), ] <- emb
  args <- list(embeddings = m, key = key, assay = DefaultAssay(full))
  if (length(src@stdev) == ncol(emb)) args$stdev <- src@stdev
  ld <- tryCatch(Loadings(src, projected = FALSE), error = function(e) NULL)
  if (!is.null(ld) && nrow(ld) > 0) args$loadings <- ld
  full[[reduction]] <- do.call(CreateDimReducObject, args)
  full
}


#' 把对象的 identity 显式设成 cluster 标签（"出图不再漂"的闸门）
#' 背景：`full` 来自 merge ⇒ `Idents(full)` 是 `orig.ident`（样本名）；聚类是在**子集**上做的，
#' 我只回写了 `@meta.data$seurat_clusters`，**没有同步 Idents**。而 `subset()` 会继承父对象的 identity
#' ⇒ 出图阶段 `Idents(sub)` 变成**样本**，于是 split(..., Idents(sub)) 按样本分组、
#' 未写 group.by 的 DimPlot/SpatialDimPlot 每张只剩单色。
#' 实测（2026-09-19）：对含 1894 个 NA 的全量对象执行 `Idents(obj) <- <带 NA 的 factor>` **不报错**，
#' nlevels 正确变为 24（0..23）。
.set_cluster_ident <- function(obj, col = "seurat_clusters") {
  if (!col %in% colnames(obj@meta.data)) return(obj)
  v <- obj@meta.data[[col]]
  if (is.null(v)) return(obj)
  if (!is.factor(v)) v <- factor(as.character(v))
  Idents(obj) <- v
  obj
}


# =============================================================================
# 出图（M2a）—— 把参考脚本各步的画图代码搬进来
# -----------------------------------------------------------------------------
# 全部在 **Rscript** 下运行（离线构建阶段）；**程序内不经 rpy2 出图**（那是 M2b）。
#   · 输出根 = fig_root（驱动传入 OUTPUT/<dataset_id>），
#     **绝不**写进 appdata/spatial_main/（那里只放 .rds + manifest，扫描白名单只认 manifest），
#     也**绝不**写进只读的 空间转录组代码参考/**。
#   · 目录名沿用参考脚本的阶段名（00_DataLoadingCheck / 00_QC / 01_Filtering / 02_Clustering /
#     03_GeneSpatial / 05_CellStateScore / 05_SpatialViz / 06_Markers / 07_CellTypeAnno），
#     使台账里"阶段目录 ⇄ 参考脚本"的映射继续成立。
#   · 图上的**标题与坐标轴文案一律英文**（与参考 :362 同一理由：避免 PDF 的中文 mbcs 编码告警）。
#     这也是我上一轮定位出的 rpy2 编码风险的规避措施，虽然本轮走 Rscript 本来就不会触发。
#   · ★ 逐图**落盘后立即校验存在性与大小**（<512 字节视为失败），并把结果记进 _figure_manifest.csv。
#     理由：`ggsave` 出图失败在 R 里是 **warning 而非 error**，脚本会**静默继续**、
#     产物永久缺失却毫无报错（这是前任 rpy2 方案的真实教训）。校验把"静默"变成"可清点"。
# =============================================================================

#' 出图选项（默认值逐条对齐参考脚本）
default_fig_opts <- function() {
  list(
    dpi            = 300,
    pt_size_factor = 2,      # 参考 :144/:290/:489/:533
    image_alpha    = 0.6,    # 参考 :145
    genes_show     = c("ACTB", "VIM", "COL1A1", "PECAM1", "PTPRC", "EPCAM"),  # 参考 :522
    genes_to_plot  = c("EGFR"),                                              # 参考 :773
    spatial_sigs   = c("Hypoxia", "MES", "Myeloid", "Oligo", "Vessel"),      # 参考 :707
    sig_list       = list(                                                   # 参考 :631-641
      MES     = c("CHI3L1", "CD44", "VIM", "FN1", "SLC1A3", "TAGLN"),
      NPC     = c("SOX4", "DCX", "DLL3", "ASCL1", "C1QL1"),
      OPC     = c("PDGFRA", "OLIG1", "OLIG2", "PTPRZ1"),
      AC      = c("GFAP", "AQP4", "ID3", "PON2"),
      Hypoxia = c("VEGFA", "CA9", "LDHA", "SLC2A1", "PGK1"),
      Myeloid = c("CD68", "AIF1", "C1QB", "GPNMB"),
      Tcell   = c("CD3D", "CD3E", "CD2"),
      Oligo   = c("MBP", "MOBP", "MAG", "MOG"),
      Vessel  = c("FLT1", "CLDN5", "VWF", "PECAM1")
    ),
    marker_min_pct   = 0.25,           # 参考 :839
    marker_logfc     = 0.25,           # 参考 :840
    marker_max_cells = 500,            # 参考 :841
    marker_test_use  = "wilcox_limma", # 参考 :842
    module_ctrl      = 100,            # 参考 :656
    module_seed      = 1
  )
}

#' 文献级统一样式（参考 :206-217，逐项对齐）
.fig_theme <- function() {
  ggplot2::theme_classic(base_size = 12, base_family = "") +
    ggplot2::theme(
      axis.line    = ggplot2::element_line(linewidth = 0.6, colour = "grey20"),
      axis.ticks   = ggplot2::element_line(linewidth = 0.6, colour = "grey20"),
      panel.grid   = ggplot2::element_blank(),
      legend.key   = ggplot2::element_blank(),
      plot.title   = ggplot2::element_text(size = 13, face = "bold", hjust = 0.5),
      axis.text    = ggplot2::element_text(size = 10, colour = "black"),
      axis.title   = ggplot2::element_text(size = 11, colour = "black"),
      legend.text  = ggplot2::element_text(size = 9, colour = "black"),
      legend.title = ggplot2::element_text(size = 10, colour = "black")
    )
}

#' 色板（参考 :220-223）
.fig_palettes <- function() {
  list(
    cat  = grDevices::colorRampPalette(ggsci::pal_nejm("default")(8))(50),
    cont = grDevices::colorRampPalette(c("grey92", "gold", "firebrick"))(256)
  )
}

#' 出图记录器：每张图落盘后立刻核对，失败也能被清点（不中断构建）
.new_fig_recorder <- function() {
  e <- new.env(parent = emptyenv())
  e$rows <- list()
  e$add <- function(figure_type, path, note = "") {
    size <- if (file.exists(path)) file.size(path) else NA_real_
    ok <- !is.na(size) && size >= 512
    e$rows[[length(e$rows) + 1L]] <- data.frame(
      figure_type = figure_type, path = path,
      bytes = if (is.na(size)) 0 else as.numeric(size),
      ok = ok, note = note, stringsAsFactors = FALSE)
    invisible(ok)
  }
  e
}

#' 画一张图并落盘（带落盘后校验）
.save_fig <- function(rec, figure_type, plot, path, width, height, dpi) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  note <- ""
  tryCatch(
    ggplot2::ggsave(filename = path, plot = plot, width = width, height = height,
                    dpi = dpi, limitsize = FALSE),
    error = function(err) { note <<- paste0("error: ", conditionMessage(err)) }
  )
  ok <- rec$add(figure_type, path, note)
  if (!isTRUE(ok)) message("FIG_MISSING ", figure_type, " | ", path, " | ", note)
  invisible(ok)
}

#' 把逐图记录合并写进 <fig_root>/_figure_manifest.csv
#' ★ 分节构建（--fig_groups）时**不能覆盖**前几节的记录：与已有 CSV 合并，按 path 去重（新记录优先）。
#'   这样一次构建被切成多段跑，最终仍能得到一份完整的逐图记录。
#' ★ 每条记录带 `run_id`：**它标出这张图是"哪一次运行"最后写出的**。
#'   审查模式要把评分绑定到某一版图集，就靠这一列（否则重跑一次评分即失效）。
.merge_write_fig_csv <- function(fm, fig_root, run_id = NA_character_) {
  fm$run_id <- run_id
  fm_path <- file.path(fig_root, "_figure_manifest.csv")
  if (file.exists(fm_path)) {
    prev <- tryCatch(utils::read.csv(fm_path, stringsAsFactors = FALSE),
                     error = function(e) NULL)
    if (!is.null(prev) && nrow(prev) > 0 && "path" %in% colnames(prev)) {
      if (nrow(fm) > 0) prev <- prev[!(prev$path %in% fm$path), , drop = FALSE]
      # 旧记录缺列时补齐，保证 rbind 可行
      for (cc in setdiff(colnames(fm), colnames(prev))) prev[[cc]] <- NA
      if (nrow(prev) > 0) {
        fm <- rbind(prev[, colnames(fm), drop = FALSE], fm)
      }
    }
  }
  utils::write.csv(fm, fm_path, row.names = FALSE, fileEncoding = "UTF-8")
  invisible(fm)
}

#' 写"本次运行"的独立记录目录 <fig_root>/runs/<run_id>/
#' 目的：图**累积**在同一目录里，但每次运行的汇总必须各自留档、互不覆盖
#' （外面才能判断某张图是哪次产出的；也是审查模式绑定图集版本的前提）。
.write_run_record <- function(fm, fig_root, run_id, extra = list()) {
  if (is.na(run_id) || !nzchar(run_id)) return(invisible(NULL))
  rdir <- file.path(fig_root, "runs", run_id)
  dir.create(rdir, showWarnings = FALSE, recursive = TRUE)
  if (!is.null(fm) && nrow(fm) > 0) {
    utils::write.csv(fm, file.path(rdir, "figure_manifest.csv"),
                     row.names = FALSE, fileEncoding = "UTF-8")
  }
  rec <- c(list(run_id = run_id,
                written_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"),
                files = if (is.null(fm)) 0L else nrow(fm),
                files_ok = if (is.null(fm)) 0L else sum(fm$ok),
                files_missing = if (is.null(fm)) 0L else sum(!fm$ok),
                bytes = if (is.null(fm)) 0 else sum(fm$bytes)), extra)
  writeLines(jsonlite::toJSON(rec, auto_unbox = TRUE, pretty = TRUE, null = "null"),
             file.path(rdir, "run.json"))
  invisible(rdir)
}

#' 生成图集。返回逐图记录 data.frame。
#' obj       : 成品 Seurat 对象（含全量 spot + pass_qc + seurat_clusters + pca/umap + images）
#' fig_root  : 图集输出根（OUTPUT/<dataset_id>）
#' do_pdf    : 是否同时出 PDF（参考脚本 PNG+PDF 都出；关掉可显著省时省盘）
#' groups    : NULL = 全出；否则只出列出的阶段组。**用于把长跑切成若干短段**
#'             （本机每条命令有硬性超时，19 样本全量出图约需 9~10 分钟，必须分节）
#'             可选：early(读取/QC/过滤/聚类/基因) score(状态评分图) persample(逐样本)
#'                   marker(Marker 基因) celltype(细胞类型注释)
#'             ⚠ score 与 celltype 都需要 Score_* 列，所以只请求 celltype 时也会**重算**评分。
.make_figures <- function(obj, fig_root, fig_opts, params, rec, do_pdf = TRUE,
                          groups = NULL, run_id = NA_character_) {
  has_g <- function(g) is.null(groups) || (g %in% groups)
  suppressPackageStartupMessages({
    library(ggplot2); library(patchwork); library(ggsci); library(viridis)
  })
  lit_theme   <- .fig_theme()
  pals        <- .fig_palettes()
  cat_palette <- pals$cat
  cont_palette <- pals$cont
  dpi <- fig_opts$dpi
  psv <- fig_opts$pt_size_factor
  ial <- fig_opts$image_alpha
  D   <- function(...) file.path(fig_root, ...)
  mkdir <- function(p) dir.create(p, showWarnings = FALSE, recursive = TRUE)

  # 图都画在 **QC 通过的子集** 上（与参考脚本一致：参考 :376 之后 sce.all 就是过滤后的对象）
  sub <- subset(obj, subset = pass_qc)
  # ★★ 修复 1（主修）：出图入口显式把 identity 设成 cluster。
  #   不依赖上游 .rds 的 Idents 是否正确 —— 这是"不再漂"的第一道闸。
  # ★ 依赖 Idents 的代码锚点：**本函数入口已显式重设**（修复 1 = 下一行）。
  #   本函数内所有 `FindAllMarkers` / `RenameIdents` / DimPlot 都建立在这一行之上；
  #   若有人把这一行删掉或前移，它们会**静默**退化成"按样本"，不会报错。
  sub <- .set_cluster_ident(sub)
  sample_names <- sort(unique(as.character(obj$orig.ident)))
  .sp_log("[fig] Idents(sub) after fix = ", nlevels(Idents(sub)), " levels: ",
          paste(head(levels(Idents(sub)), 6), collapse = ","))
  .sp_log("[fig] plotting on ", ncol(sub), " QC-passed spots; samples = ", length(sample_names))

  ## ---------------------------------------------------------------- STAGE1 读取验证
  if (has_g("early")) {
  d1 <- D("00_DataLoadingCheck"); mkdir(d1)
  plist <- lapply(sample_names, function(samp) {
    s <- subset(obj, subset = orig.ident == samp)
    SpatialFeaturePlot(s, features = "nCount_Spatial", pt.size.factor = psv,
                       image.alpha = ial, stroke = NA) +
      ggtitle(samp) + theme(legend.position = "none")
  })
  n <- length(plist); cols <- 4; rows <- ceiling(n / cols)
  patch <- plist[[1]]
  if (n > 1) for (i in 2:n) patch <- patch + plist[[i]]
  overview <- patch + plot_layout(ncol = cols)
  .save_fig(rec, "load_overview", overview, file.path(d1, "00_Spatial_nCount_Overview.png"), cols * 5, rows * 5, 150)
  if (do_pdf) .save_fig(rec, "load_overview", overview, file.path(d1, "00_Spatial_nCount_Overview.pdf"), cols * 5, rows * 5, 150)
  for (i in seq_along(sample_names)) {
    .save_fig(rec, "load_per_sample", plist[[i]],
              file.path(d1, paste0("01_nCount_", sample_names[i], ".png")), 5, 5, 150)
    if (do_pdf) .save_fig(rec, "load_per_sample", plist[[i]],
                          file.path(d1, paste0("01_nCount_", sample_names[i], ".pdf")), 5, 5, 150)
  }
  rm(plist); invisible(gc(verbose = FALSE))

  ## ---------------------------------------------------------------- STAGE2 QC
  d2 <- D("00_QC"); mkdir(d2)
  p_vln <- VlnPlot(obj, features = c("nCount_Spatial", "nFeature_Spatial", "percent_mito"),
                   pt.size = 0, ncol = 3, cols = cat_palette, combine = TRUE) &
    NoLegend() & lit_theme &
    theme(axis.text.x = element_text(angle = 45, hjust = 1, size = 8))
  .save_fig(rec, "qc_violin", p_vln, file.path(d2, "01_VlnPlot_QC.png"), 15, 5, dpi)
  if (do_pdf) .save_fig(rec, "qc_violin", p_vln, file.path(d2, "01_VlnPlot_QC.pdf"), 15, 5, dpi)

  md <- obj@meta.data
  mk_hist <- function(col, lab, col_fill) {
    ggplot(md, aes(x = .data[[col]])) +
      geom_histogram(bins = 100, fill = col_fill, colour = NA) +
      lit_theme + labs(x = lab, y = "spot count", title = NULL)
  }
  hc1 <- mk_hist("nCount_Spatial",   "nCount_Spatial",   "steelblue")
  hc2 <- mk_hist("nFeature_Spatial", "nFeature_Spatial", "darkseagreen")
  hc3 <- mk_hist("percent_mito",     "percent_mito",     "tomato")
  hist_all <- (hc1 | hc2) / hc3
  .save_fig(rec, "qc_histogram", hist_all, file.path(d2, "02_Histograms_Distribution.png"), 12, 8, dpi)
  if (do_pdf) .save_fig(rec, "qc_histogram", hist_all, file.path(d2, "02_Histograms_Distribution.pdf"), 12, 8, dpi)

  sp_overview <- list()
  for (f in c("nCount_Spatial", "nFeature_Spatial", "percent_mito")) {
    sp_overview[[f]] <- SpatialFeaturePlot(obj, features = f, pt.size.factor = psv,
                                           image.alpha = ial, stroke = NA) +
      ggtitle(f) + lit_theme + theme(legend.position = "none")
  }
  sp_patch <- sp_overview[[1]] / sp_overview[[2]] / sp_overview[[3]]
  .save_fig(rec, "qc_spatial", sp_patch, file.path(d2, "03_Spatial_QC_Overview.png"), 8, 15, dpi)
  if (do_pdf) .save_fig(rec, "qc_spatial", sp_patch, file.path(d2, "03_Spatial_QC_Overview.pdf"), 8, 15, dpi)
  rm(sp_overview); invisible(gc(verbose = FALSE))

  ## ---------------------------------------------------------------- STAGE3 过滤概览
  d3 <- D("01_Filtering"); mkdir(d3)
  sp_filter <- SpatialDimPlot(sub, group.by = "orig.ident", pt.size.factor = psv,
                              stroke = NA, ncol = 5) +
    ggtitle(paste0("Spatial overview after QC (", ncol(sub), " spots)")) +
    lit_theme + theme(legend.position = "bottom")
  .save_fig(rec, "filter_overview", sp_filter, file.path(d3, "02_Spatial_AfterFilter_Overview.png"), 20, 13, dpi)
  if (do_pdf) .save_fig(rec, "filter_overview", sp_filter, file.path(d3, "02_Spatial_AfterFilter_Overview.pdf"), 20, 13, dpi)
  tab <- table(obj$orig.ident); tab_after <- table(sub$orig.ident)
  cmp <- data.frame(
    Sample            = names(tab),
    BeforeFilterSpots = as.integer(tab),
    AfterFilterSpots  = as.integer(tab_after[match(names(tab), names(tab_after))]),
    RetentionPct      = round(as.integer(tab_after[match(names(tab), names(tab_after))]) /
                                as.integer(tab) * 100, 2),
    stringsAsFactors  = FALSE)
  utils::write.csv(cmp, file.path(d3, "01_filter_stats.csv"), row.names = FALSE)

  ## ---------------------------------------------------------------- STAGE4 降维聚类
  d4 <- D("02_Clustering"); mkdir(d4)
  nd <- ncol(Embeddings(sub, "pca"))
  p_elbow <- ElbowPlot(sub, ndims = nd) + lit_theme
  .save_fig(rec, "pca_elbow", p_elbow, file.path(d4, "01_ElbowPlot.png"), 6, 5, dpi)
  if (do_pdf) .save_fig(rec, "pca_elbow", p_elbow, file.path(d4, "01_ElbowPlot.pdf"), 6, 5, dpi)

  p_umap_sample <- DimPlot(sub, reduction = "umap", group.by = "orig.ident",
                           cols = cat_palette, pt.size = 0.4) +
    lit_theme + ggtitle("UMAP by sample") + theme(legend.position = "bottom")
  # ★ 修复 3：标题声称 "by cluster" 就必须写显式 group.by，不能靠隐式 Idents
  #   （否则一旦 Idents 漂成样本，这张图会静默变成"按样本着色"，标题却是 by cluster）
  p_umap_cluster <- DimPlot(sub, reduction = "umap", group.by = "seurat_clusters",
                            pt.size = 0.4) +
    lit_theme + ggtitle("UMAP by cluster")
  umap_comb <- p_umap_sample + p_umap_cluster
  .save_fig(rec, "umap_sample_cluster", umap_comb, file.path(d4, "02_UMAP_Sample_Cluster.png"), 14, 6, dpi)
  if (do_pdf) .save_fig(rec, "umap_sample_cluster", umap_comb, file.path(d4, "02_UMAP_Sample_Cluster.pdf"), 14, 6, dpi)

  p_spatial_cluster <- SpatialDimPlot(sub, group.by = "seurat_clusters", pt.size.factor = psv,
                                      stroke = NA, ncol = 5) +
    lit_theme + ggtitle("Spatial clusters")
  .save_fig(rec, "cluster_spatial", p_spatial_cluster, file.path(d4, "03_Spatial_Clusters_Overview.png"), 20, 13, dpi)
  if (do_pdf) .save_fig(rec, "cluster_spatial", p_spatial_cluster, file.path(d4, "03_Spatial_Clusters_Overview.pdf"), 20, 13, dpi)

  ## ---------------------------------------------------------------- STAGE5 基因空间表达
  d5 <- D("03_GeneSpatial"); mkdir(d5)
  genes_show <- intersect(fig_opts$genes_show, rownames(sub))
  .sp_log("[fig] gene_spatial genes: ", paste(genes_show, collapse = ", "))
  for (g in genes_show) {
    p <- SpatialFeaturePlot(sub, features = g, pt.size.factor = psv, stroke = NA, ncol = 5) +
      lit_theme + ggtitle(g)
    .save_fig(rec, "gene_spatial", p, file.path(d5, paste0(g, "_Spatial.png")), 20, 13, dpi)
  }
  if (length(genes_show) > 0) {
    p_panel <- SpatialFeaturePlot(sub, features = genes_show, pt.size.factor = psv,
                                  stroke = NA, ncol = 3) + lit_theme
    .save_fig(rec, "gene_panel", p_panel, file.path(d5, "00_Genes_Expression_Panel.png"), 18, 15, dpi)
  }
  }  # end of group "early"

  ## ---------------------------------------------------------------- STAGE7 细胞状态评分
  # ★ score 与 celltype 两组都依赖 Score_* 列：只请求 celltype 时也要算分（但不出分图）
  if (has_g("score") || has_g("celltype")) {
  d7 <- D("05_CellStateScore"); mkdir(d7)
  sig_names <- names(fig_opts$sig_list)
  prev_tmp <- character(0)
  for (s in sig_names) {
    genes <- intersect(fig_opts$sig_list[[s]], rownames(sub))
    if (length(genes) < 3) {
      .sp_log("[fig] signature ", s, " skipped (only ", length(genes), " genes)")
      next
    }
    sub <- AddModuleScore(sub, features = list(genes), name = "XXX_tmp", assay = "Spatial",
                          ctrl = fig_opts$module_ctrl, seed = fig_opts$module_seed, verbose = FALSE)
    tmp_cols <- grep("^XXX_tmp", colnames(sub@meta.data), value = TRUE)
    score_col <- tmp_cols[!tmp_cols %in% prev_tmp][1]
    if (is.na(score_col)) score_col <- tmp_cols[1]
    sub@meta.data[[paste0("Score_", s)]] <- sub@meta.data[[score_col]]
    prev_tmp <- c(prev_tmp, score_col)
    sub@meta.data[[score_col]] <- NULL
  }
  score_cols <- grep("^Score_", colnames(sub@meta.data), value = TRUE)
  .sp_log("[fig] score columns: ", paste(score_cols, collapse = ", "), "")

  if (has_g("score") && length(score_cols) > 0) {
    # ★ 修复 3：显式按 seurat_clusters 分组，不用隐式 Idents（原写法曾按样本切成 19 组）
    mean_score <- do.call(rbind, lapply(
      split(seq_len(nrow(sub@meta.data)), sub@meta.data[["seurat_clusters"]]),
      function(idx) colMeans(sub@meta.data[idx, score_cols, drop = FALSE])))
    mean_score <- as.data.frame(mean_score); mean_score$cluster <- rownames(mean_score)
    mean_score_long <- data.frame(
      cluster   = rep(mean_score$cluster, times = length(score_cols)),
      Signature = rep(score_cols, each = nrow(mean_score)),
      score     = unlist(mean_score[, score_cols, drop = FALSE], use.names = FALSE))
    p_heat <- ggplot(mean_score_long, aes(x = Signature, y = cluster, fill = score)) +
      geom_tile(color = "white") +
      scale_fill_gradient2(low = "#3B4CC0", mid = "white", high = "#B52628", midpoint = 0) +
      lit_theme + labs(title = "Cluster x signature mean score", x = NULL, y = "Cluster") +
      theme(axis.text.x = element_text(angle = 45, hjust = 1))
    .save_fig(rec, "score_heatmap", p_heat, file.path(d7, "01_Score_Heatmap_by_Cluster.png"), 8, 6, dpi)
    if (do_pdf) .save_fig(rec, "score_heatmap", p_heat, file.path(d7, "01_Score_Heatmap_by_Cluster.pdf"), 8, 6, dpi)

    for (s in sig_names) {
      sn <- paste0("Score_", s)
      if (!sn %in% colnames(sub@meta.data)) next
      p <- FeaturePlot(sub, features = sn, reduction = "umap", pt.size = 0.3) +
        scale_color_gradient2(low = "grey90", high = "firebrick") +
        lit_theme + ggtitle(s)
      .save_fig(rec, "score_umap", p, file.path(d7, paste0("02_UMAP_", s, ".png")), 7, 6, dpi)
      if (do_pdf) .save_fig(rec, "score_umap", p, file.path(d7, paste0("02_UMAP_", s, ".pdf")), 7, 6, dpi)
    }
    # ★ 修复 4（协调者批准）：出满**全部 9 个基因集**的空间图。
    #   原先只出 spatial_sigs 里的 5 个（那 5 个与参考 :707 逐条对齐，保留在 :157 作"未偏离参考"的证据锚点）；
    #   NPC/OPC/AC/Tcell 的 Score_* 早已算出、UMAP 图也早已有，**仅空间图缺失** ⇒ 近乎零边际成本。
    for (s in sig_names) {
      sn <- paste0("Score_", s)
      if (!sn %in% colnames(sub@meta.data)) next
      p <- SpatialFeaturePlot(sub, features = sn, pt.size.factor = psv, stroke = NA, ncol = 5) +
        scale_fill_gradient2(low = "grey92", high = "firebrick", midpoint = 0) +
        lit_theme + ggtitle(s)
      .save_fig(rec, "score_spatial", p, file.path(d7, paste0("03_Spatial_", s, ".png")), 20, 13, dpi)
      if (do_pdf) .save_fig(rec, "score_spatial", p, file.path(d7, paste0("03_Spatial_", s, ".pdf")), 20, 13, dpi)
    }
  }
  }  # end of group "score"

  ## ---------------------------------------------------------------- STAGE8 逐样本可视化
  if (has_g("persample")) {
  # 每个样本只 subset 一次（参考脚本在基因循环里会重复 subset，这里合并以省时间，产物一致）
  d8 <- D("05_SpatialViz"); mkdir(d8)
  genes_to_plot <- intersect(fig_opts$genes_to_plot, rownames(sub))
  .sp_log("[fig] per-sample genes: ", paste(genes_to_plot, collapse = ", "))
  for (samp in sample_names) {
    s2 <- subset(sub, subset = orig.ident == samp)
    p1 <- DimPlot(s2, reduction = "umap", group.by = "seurat_clusters",
                  label = TRUE, label.size = 7, repel = TRUE) +
      lit_theme + ggtitle(samp)
    .save_fig(rec, "persample_umap", p1, file.path(d8, "01_UMAP", paste0("UMAP_", samp, ".png")), 5, 5, dpi)
    if (do_pdf) .save_fig(rec, "persample_umap", p1, file.path(d8, "01_UMAP", paste0("UMAP_", samp, ".pdf")), 5, 5, dpi)

    p2 <- SpatialDimPlot(s2, group.by = "seurat_clusters", label = TRUE, label.size = 3,
                         pt.size.factor = psv, image.alpha = ial, repel = TRUE) +
      lit_theme + ggtitle(samp)
    .save_fig(rec, "persample_spatial_cluster", p2,
              file.path(d8, "02_Spatial_Cluster", paste0("Spatial_Cluster_", samp, ".png")), 6, 6, dpi)
    if (do_pdf) .save_fig(rec, "persample_spatial_cluster", p2,
                          file.path(d8, "02_Spatial_Cluster", paste0("Spatial_Cluster_", samp, ".pdf")), 6, 6, dpi)

    for (gene in genes_to_plot) {
      p3 <- SpatialFeaturePlot(s2, features = gene, pt.size.factor = psv, stroke = NA,
                               image.alpha = ial) +
        scale_fill_gradientn(colors = cont_palette) +
        lit_theme + ggtitle(paste0(gene, " - ", samp))
      .save_fig(rec, "persample_gene_spatial", p3,
                file.path(d8, "03_Genes", gene, "PNG", paste0(gene, "_", samp, ".png")), 5, 5, dpi)
      if (do_pdf) .save_fig(rec, "persample_gene_spatial", p3,
                            file.path(d8, "03_Genes", gene, "PDF", paste0(gene, "_", samp, ".pdf")), 5, 5, dpi)
    }
    rm(s2); invisible(gc(verbose = FALSE))
  }
  }  # end of group "persample"

  ## ---------------------------------------------------------------- STAGE9 Marker 基因
  if (has_g("marker")) {
  d9 <- D("06_Markers"); mkdir(d9)
  if (length(VariableFeatures(sub)) == 0) {
    .sp_log("[fig] object has no VariableFeatures; recomputing (vst)")
    sub <- FindVariableFeatures(sub, selection.method = "vst",
                                nfeatures = params$nfeatures, verbose = FALSE)
  }
  # ★ 依赖 Idents 的代码锚点：FindAllMarkers **没有 group.by 参数**，只能吃 Idents
  #   ⇒ 它的正确性完全押在上面 `.set_cluster_ident(sub)`（修复 1）上。
  #   历史上这里曾按样本比差异（19 个 GSM 而不是 24 个 cluster），且不报错。
  markers <- FindAllMarkers(sub, assay = "Spatial", features = VariableFeatures(sub),
                            only.pos = TRUE, min.pct = fig_opts$marker_min_pct,
                            logfc.threshold = fig_opts$marker_logfc,
                            max.cells.per.ident = fig_opts$marker_max_cells,
                            test.use = fig_opts$marker_test_use, verbose = FALSE)
  utils::write.csv(markers, file.path(d9, "01_all_markers.csv"), row.names = FALSE)
  if (nrow(markers) > 0) {
    pick_top <- function(d, k) {
      d <- d[order(-d$avg_log2FC), , drop = FALSE]
      d[seq_len(min(k, nrow(d))), , drop = FALSE]
    }
    top10 <- do.call(rbind, lapply(split(markers, markers$cluster), pick_top, k = 10))
    top5  <- do.call(rbind, lapply(split(markers, markers$cluster), pick_top, k = 5))
    utils::write.csv(top10, file.path(d9, "02_top10_markers_by_cluster.csv"), row.names = FALSE)
    top_genes <- unique(top5$gene)
    p_dot <- DotPlot(sub, features = top_genes, assay = "Spatial",
                     group.by = "seurat_clusters") +
      RotatedAxis() + lit_theme + labs(x = NULL, y = "Cluster") +
      theme(axis.text.x = element_text(size = 8, angle = 45, hjust = 1))
    wd <- max(12, length(top_genes) * 0.5)
    .save_fig(rec, "marker_dotplot", p_dot, file.path(d9, "03_DotPlot_top5.png"), wd, 6, dpi)
    if (do_pdf) .save_fig(rec, "marker_dotplot", p_dot, file.path(d9, "03_DotPlot_top5.pdf"), wd, 6, dpi)

    avg <- AverageExpression(sub, assays = "Spatial", layer = "data",
                             features = top_genes, group.by = "seurat_clusters", verbose = FALSE)
    avg_mat <- as.matrix(avg$Spatial)
    avg_z <- t(scale(t(avg_mat)))
    heat_df <- data.frame(gene = rep(rownames(avg_z), times = ncol(avg_z)),
                          cluster = rep(colnames(avg_z), each = nrow(avg_z)),
                          z = as.vector(avg_z), stringsAsFactors = FALSE)
    heat_df <- heat_df[is.finite(heat_df$z), , drop = FALSE]
    p_heat2 <- ggplot(heat_df, aes(x = gene, y = cluster, fill = z)) +
      geom_tile(color = "white") +
      scale_fill_gradient2(low = "#3B4CC0", mid = "white", high = "#B52628", midpoint = 0) +
      lit_theme + labs(x = NULL, y = "Cluster", fill = "z-score") +
      theme(axis.text.x = element_text(size = 8, angle = 45, hjust = 1))
    .save_fig(rec, "marker_heatmap", p_heat2, file.path(d9, "04_Heatmap_top5.png"), wd, 6, dpi)
    if (do_pdf) .save_fig(rec, "marker_heatmap", p_heat2, file.path(d9, "04_Heatmap_top5.pdf"), wd, 6, dpi)
  }
  }  # end of group "marker"

  ## ---------------------------------------------------------------- STAGE10 细胞类型注释
  d10 <- D("07_CellTypeAnno"); mkdir(d10)
  if (!has_g("celltype")) {
    .sp_log("[fig] group 'celltype' not requested -> skip STAGE10 figures")
  } else if (length(score_cols) == 0) {
    .sp_log("[fig] no Score_* columns -> skip STAGE10 annotation figures")
  } else {
    # ★ 修复 3：显式按 seurat_clusters 分组（原写法按 Idents，曾切成 19 个样本 ⇒ cluster 列装 GSM）
    cluster_mean <- do.call(rbind, lapply(
      split(seq_len(nrow(sub@meta.data)), sub@meta.data[["seurat_clusters"]]),
      function(idx) colMeans(sub@meta.data[idx, score_cols, drop = FALSE])))
    cluster_mean <- as.data.frame(cluster_mean); cluster_mean$cluster <- rownames(cluster_mean)
    utils::write.csv(cluster_mean, file.path(d10, "01_cluster_signature_mean.csv"), row.names = FALSE)

    sig_label <- sub("^Score_", "", score_cols)
    suggested <- sig_label[apply(cluster_mean[, score_cols, drop = FALSE], 1, which.max)]
    names(suggested) <- cluster_mean$cluster
    .sp_log("[fig] suggested cell types: ", paste(names(suggested), suggested, sep = "=", collapse = ", "))
    new.cluster.ids <- suggested
    names(new.cluster.ids) <- names(suggested)
    # ★ 修复 3：cell_type 由 seurat_clusters **查表**得到，不依赖 Idents 是否恰好为 cluster
    #   （原写法 `as.character(Idents(sub))` 在 Idents 漂成样本时会把**整个样本**贴成一种细胞类型）
    sub@meta.data$cell_type <- as.character(
      new.cluster.ids[as.character(sub@meta.data[["seurat_clusters"]])])
    # ★ 依赖 Idents 的代码锚点：RenameIdents 的 names 必须与被改名对象的**当前 identity 层级**匹配。
    #   这里依赖上面 `.set_cluster_ident(sub)`（修复 1）保证 Idents = cluster；
    #   否则 names 会去匹配样本名（历史上确实匹配上过），把**整个样本**改名成一种细胞类型。
    sub <- RenameIdents(sub, new.cluster.ids)
    utils::write.csv(data.frame(spot = rownames(sub@meta.data),
                                sample = as.character(sub$orig.ident),
                                cluster = as.character(sub$seurat_clusters),
                                cell_type = as.character(sub$cell_type),
                                stringsAsFactors = FALSE),
                     file.path(d10, "02_cell_type_annotation.csv"), row.names = FALSE)

    p_umap_ct <- DimPlot(sub, reduction = "umap", group.by = "cell_type",
                         cols = cat_palette, pt.size = 0.4) +
      lit_theme + ggtitle("UMAP by cell type") + theme(legend.position = "bottom")
    .save_fig(rec, "celltype_umap", p_umap_ct, file.path(d10, "03_UMAP_celltype.png"), 8, 7, dpi)
    if (do_pdf) .save_fig(rec, "celltype_umap", p_umap_ct, file.path(d10, "03_UMAP_celltype.pdf"), 8, 7, dpi)

    p_sp_ct <- SpatialDimPlot(sub, group.by = "cell_type", pt.size.factor = psv,
                              stroke = NA, ncol = 4) +
      lit_theme + ggtitle("Spatial by cell type")
    .save_fig(rec, "celltype_spatial", p_sp_ct, file.path(d10, "04_Spatial_celltype.png"), 20, 14, dpi)
    if (do_pdf) .save_fig(rec, "celltype_spatial", p_sp_ct, file.path(d10, "04_Spatial_celltype.pdf"), 20, 14, dpi)

    for (samp in sample_names) {
      s3 <- subset(sub, subset = orig.ident == samp)
      q1 <- DimPlot(s3, reduction = "umap", group.by = "cell_type", cols = cat_palette, pt.size = 0.5) +
        lit_theme + ggtitle(samp) + theme(legend.position = "bottom")
      .save_fig(rec, "celltype_umap_persample", q1,
                file.path(d10, "05_UMAP_per_sample", paste0("UMAP_", samp, ".png")), 6, 6, dpi)
      if (do_pdf) .save_fig(rec, "celltype_umap_persample", q1,
                            file.path(d10, "05_UMAP_per_sample", paste0("UMAP_", samp, ".pdf")), 6, 6, dpi)
      q2 <- SpatialDimPlot(s3, group.by = "cell_type", pt.size.factor = psv, stroke = NA) +
        lit_theme + ggtitle(samp)
      .save_fig(rec, "celltype_spatial_persample", q2,
                file.path(d10, "06_Spatial_per_sample", paste0("Spatial_", samp, ".png")), 6, 6, dpi)
      if (do_pdf) .save_fig(rec, "celltype_spatial_persample", q2,
                            file.path(d10, "06_Spatial_per_sample", paste0("Spatial_", samp, ".pdf")), 6, 6, dpi)
      rm(s3); invisible(gc(verbose = FALSE))
    }
  }

  ## ---------------------------------------------------------------- 汇总逐图记录
  fm <- if (length(rec$rows) == 0) {
    data.frame(figure_type = character(0), path = character(0), bytes = numeric(0),
               ok = logical(0), note = character(0), stringsAsFactors = FALSE)
  } else {
    do.call(rbind, rec$rows)
  }
  fm <- .merge_write_fig_csv(fm, fig_root, run_id)
  fm
}


# =============================================================================
# 主函数（M2 的 rpy2 路径直接调它）
# -----------------------------------------------------------------------------
# 参数：
#   data_root : 原始 10X 数据根目录（其下为 19 个 GSM*/ 样本目录）
#   samples   : character 向量，**显式样本名单**；NULL/空 表示自动发现全部 GSM*/
#   out_root  : 输出根目录（写成  appdata/spatial_main/ ）
#   params    : list，覆盖 default_params() 的任意键
#   fig_root  : 图集输出根（写成 OUTPUT/<dataset_id>）；**NULL = 不出图**（M1 行为）
#   fig_opts  : list，覆盖 default_fig_opts() 的任意键
#   do_pdf    : 图集是否同时出 PDF（参考脚本 PNG+PDF 都出）
# 返回（纯数据 list，供 CLI 打印；**不抛业务异常之外的东西**）：
#   list(ok, dataset_id, artifact, samples_csv, summary_json, figure_manifest,
#        n_spots, n_genes, n_spots_pass_qc, n_clusters, n_samples,
#        elapsed_sec, detail)
# =============================================================================
run_spatial_pipeline <- function(data_root, samples = NULL, out_root,
                                 params = list(), dataset_id = "GSE237183",
                                 fig_root = NULL, fig_opts = list(),
                                 do_pdf = TRUE, fig_groups = NULL) {
  t0 <- Sys.time()
  run_id <- format(t0, "%Y%m%d-%H%M%S")   # ★ 本次运行的稳定标识
  p <- utils::modifyList(default_params(), params)

  # ---- 0. 前置校验（宁可早失败，也不产出半成品）----
  if (!dir.exists(data_root)) stop("data_root not found: ", data_root)
  if (missing(out_root) || is.null(out_root) || !nzchar(out_root)) stop("out_root is required")
  dir.create(out_root, showWarnings = FALSE, recursive = TRUE)
  if (!dir.exists(out_root)) stop("cannot create out_root: ", out_root)
  # 出图/产物根目录必须是纯 ASCII（相对路径留给调用者拼，这里只校验非 ASCII 字符）
  if (grepl("[^ -~]", out_root)) {
    stop("out_root must be pure ASCII (non-ASCII characters found): ", out_root)
  }
  if (!is.null(fig_root) && grepl("[^ -~]", fig_root)) {
    stop("fig_root must be pure ASCII (non-ASCII characters found): ", fig_root)
  }

  # ---- 1. 样本集合（对应参考 :31-38，但改为显式名单优先）----
  if (is.null(samples) || length(samples) == 0) {
    found <- list.dirs(data_root, recursive = FALSE, full.names = FALSE)
    samples <- sort(found[grepl("^GSM", found)])
  }
  samples <- as.character(samples)
  if (length(samples) == 0) stop("no samples resolved under: ", data_root)
  missing_dirs <- samples[!dir.exists(file.path(data_root, samples))]
  if (length(missing_dirs) > 0) {
    stop("sample dir(s) not found: ", paste(missing_dirs, collapse = ", "))
  }
  .sp_log("samples (", length(samples), "): ", paste(samples, collapse = ", "))

  # ---- 2. 逐样本读取 + 建对象（参考 :51-86）----
  obj_list <- vector("list", length(samples))
  names(obj_list) <- samples
  for (i in seq_along(samples)) {
    pro <- samples[i]
    .sp_log("reading sample ", i, "/", length(samples), ": ", pro)
    obj_list[[i]] <- .read_one_sample(data_root, pro, p$min_cells)
  }

  # ---- 3. 合并 + JoinLayers（参考 :91-96）----
  if (length(obj_list) == 1L) {
    full <- obj_list[[1]]
  } else {
    full <- merge(x = obj_list[[1]], y = obj_list[-1], add.cell.ids = samples)
  }
  rm(obj_list); invisible(gc(verbose = FALSE))
  full <- JoinLayers(full)
  .sp_log("merged: ", nrow(full), " genes x ", ncol(full), " spots (unfiltered)")

  # ---- 4. QC 指标：percent_mito（参考 :228-236）----
  if (is.null(p$mito_pattern)) {
    mito_genes <- grep("^MT-", rownames(full), ignore.case = TRUE, value = TRUE)
    if (length(mito_genes) == 0) {
      mito_genes <- grep("^M-", rownames(full), ignore.case = TRUE, value = TRUE)
    }
  } else {
    mito_genes <- grep(p$mito_pattern, rownames(full), ignore.case = TRUE, value = TRUE)
  }
  .sp_log("mito genes detected: ", length(mito_genes))
  if (length(mito_genes) > 0) {
    full <- PercentageFeatureSet(full, features = mito_genes, col.name = "percent_mito")
  } else {
    # 一个线粒体基因都没有时，参考脚本会留下 NaN 列；这里显式给 0 以免下游 is.finite 全灭
    full$percent_mito <- 0
  }
  # 便于下游与 manifest 使用（参考脚本靠 orig.ident，这里显式化一列）
  full$sample <- as.character(full$orig.ident)

  # ---- 5. ★ pass_qc 布尔列（**保留全量 spot**，不覆盖对象）----
  #     判据与参考 :333-336 的 subset 条件逐字一致
  pass_qc <- (full$nFeature_Spatial >= p$min_nFeature) &
             (full$nCount_Spatial   >= p$min_nCount) &
             is.finite(full$percent_mito)
  pass_qc[is.na(pass_qc)] <- FALSE
  full$pass_qc <- pass_qc
  n_spots_total <- ncol(full)
  n_spots_pass  <- sum(pass_qc)
  .sp_log("pass_qc: ", n_spots_pass, " / ", n_spots_total,
          " (min_nFeature=", p$min_nFeature, ", min_nCount=", p$min_nCount, ")")
  if (n_spots_pass < 3) stop("too few spots passed QC: ", n_spots_pass)

  # ---- 6. 归一化：对**全量** spot 做（逐 spot 运算，见文件头衍生差异 5）----
  full <- NormalizeData(full, normalization.method = "LogNormalize",
                        scale.factor = p$scale_factor, verbose = FALSE)

  # ---- 7. 降维/聚类/UMAP：只在 QC 通过的子集上算（参考 :418-466）----
  sub <- subset(full, subset = pass_qc)
  sub <- FindVariableFeatures(sub, selection.method = "vst",
                              nfeatures = p$nfeatures, verbose = FALSE)
  n_hvg <- length(VariableFeatures(sub))
  .sp_log("variable features: ", n_hvg)

  sub <- ScaleData(sub, features = VariableFeatures(sub), verbose = FALSE)
  sub <- RunPCA(sub, npcs = p$npcs, features = VariableFeatures(sub), verbose = FALSE)

  pc_use <- seq_len(min(p$pc_use, ncol(Embeddings(sub, "pca"))))
  sub <- FindNeighbors(sub, reduction = "pca", dims = pc_use, verbose = FALSE)
  sub <- FindClusters(sub, resolution = p$resolution, verbose = FALSE)

  if (isTRUE(p$do_umap)) {
    # 与参考 :456-466 同一策略（绕开 Seurat v5 RunUMAP 的 Annoy/RSpectra 崩溃点）
    pca_emb <- Embeddings(sub, reduction = "pca")[, pc_use, drop = FALSE]
    set.seed(p$umap_seed)
    umap_emb <- uwot::umap(pca_emb, n_neighbors = p$umap_n_neighbors,
                           metric = "euclidean", init = "random",
                           n_components = 2, verbose = FALSE)
    rownames(umap_emb) <- Cells(sub)
    colnames(umap_emb) <- paste0("UMAP_", seq_len(ncol(umap_emb)))
    sub[["umap"]] <- CreateDimReducObject(embeddings = umap_emb, key = "UMAP_",
                                          assay = "Spatial")
  }
  # ★ 依赖 Idents 的代码锚点（构建路径）：下面两处用 `Idents(sub)` 是**安全**的，
  #   因为 `sub` 刚刚 `FindClusters` 过，其 Idents 就是 cluster。
  #   ⚠ 但**注意**：这只保证 `seurat_clusters` 这一列取值正确；`full` 的 Idents 需要
  #   下面 `full <- .set_cluster_ident(full)`（修复 2）才自洽 —— 而 M1 那次构建**没有**这一步，
  #   所以现存 `.rds` 的 `Idents` 仍是样本名（留给 M2b 的已知缺口）。
  n_clusters <- length(levels(Idents(sub)))
  .sp_log("clusters (res=", p$resolution, "): ", n_clusters)

  # ---- 8. 把子集结果搬回全量对象（非子集 spot 置 NA）----
  # 注意：这里刻意用 `@meta.data$col <-` 而不是 `obj$col <-`。
  #   Seurat v5 的 `[[<-.Seurat` 在「长度等于 cell 数」的分支里会做
  #   `all(names(value) == colnames(x))` 比对；当 value 是带 NA 的 factor 时该比对会返回 NA，
  #   于是 `if (NA)` 直接报 `missing value where TRUE/FALSE needed`（本轮实测踩到过）。
  #   直接操作 `@meta.data` 绕过该分支；参考脚本本身也是这么写的（如 :661/:664）。
  clu <- as.character(Idents(sub))
  names(clu) <- colnames(sub)
  full@meta.data$seurat_clusters <- factor(clu[colnames(full)], levels = levels(Idents(sub)))
  # ★★ 修复 2（治本）：同步 identity，让 .rds 自洽。
  #   不同步的后果见 .set_cluster_ident 的注释（Idents 会一直是 merge 来的样本名，
  #   于是任何隐式用 Idents 的下游/出图都会按样本分组）。
  #   实测：含 1894 个 NA（被过滤 spot）时赋值不报错，nlevels 正确为 24。
  full <- .set_cluster_ident(full)
  full@meta.data$cell_type <- NA_character_   # M1 不做注释；占位以保证下游列名稳定
  full <- .transfer_reduction(full, sub, "pca", "PC_")
  if (isTRUE(p$do_umap)) full <- .transfer_reduction(full, sub, "umap", "UMAP_")

  # ---- 9. 逐样本统计（供 manifest 用）----
  sample_stats <- do.call(rbind, lapply(samples, function(s) {
    is_s <- full$sample == s
    ok_s <- is_s & full$pass_qc
    data.frame(
      sample_id           = s,
      label               = .detect_sample_label(data_root, s),
      spots               = sum(is_s),
      spots_pass_qc       = sum(ok_s),
      n_genes             = if (sum(ok_s) > 0) {
                              sum(Matrix::rowSums(LayerData(full, layer = "counts")[, ok_s, drop = FALSE]) > 0)
                            } else 0L,
      median_nFeature     = if (sum(ok_s) > 0) stats::median(full$nFeature_Spatial[ok_s]) else NA_real_,
      median_nCount       = if (sum(ok_s) > 0) stats::median(full$nCount_Spatial[ok_s])   else NA_real_,
      median_percent_mito = if (sum(ok_s) > 0) stats::median(full$percent_mito[ok_s])     else NA_real_,
      stringsAsFactors    = FALSE
    )
  }))
  rownames(sample_stats) <- NULL

  # ---- 10. 落盘：最终 Seurat 成品 + 逐样本统计 + 构建摘要 ----
  artifact_path <- file.path(out_root, paste0(dataset_id, ".rds"))
  samples_csv   <- file.path(out_root, paste0(dataset_id, ".samples.csv"))
  summary_json  <- file.path(out_root, paste0(dataset_id, ".build_summary.json"))

  # 溯源信息写进对象 misc（不参与任何计算，纯自描述）
  full@misc$koyuki_spatial <- list(
    schema           = 1,
    dataset_id       = dataset_id,
    samples          = samples,
    params           = p,
    n_spots_total    = n_spots_total,
    n_spots_pass_qc  = as.integer(n_spots_pass),
    n_genes          = nrow(full),
    n_hvg            = n_hvg,
    n_clusters       = n_clusters,
    engine           = "rscript",
    r_version        = R.version.string,
    derived_from     = "空间转录组代码参考/练习/改进版_GSE237183_逐步构建.R",
    derived_script   = "script/analyzer_layer/spatial_layer/spatial_top_layer/spatial_pipeline.R",
    built_at         = format(Sys.time(), "%Y-%m-%dT%H:%M:%S")
  )

  .sp_log("saveRDS -> ", artifact_path, " (this can take a while: local disk ~6-9 MB/s)")
  saveRDS(full, artifact_path)
  utils::write.csv(sample_stats, samples_csv, row.names = FALSE, fileEncoding = "UTF-8")

  # ---- 11. 出图（M2a，可选）----
  #  图集写进 fig_root（OUTPUT/<dataset_id>），**不进 appdata/spatial_main/**。
  #  ★ 出图失败**不让构建崩**：记录错误、把已产出的图照实登记，缺图由驱动侧清点。
  figure_manifest_csv <- ""
  fig_df <- NULL
  fig_err <- ""
  n_fig_ok <- 0L
  n_fig_missing <- 0L
  fig_bytes <- 0
  if (!is.null(fig_root)) {
    dir.create(fig_root, showWarnings = FALSE, recursive = TRUE)
    fopts <- utils::modifyList(default_fig_opts(), fig_opts)
    rec <- .new_fig_recorder()
    t_fig <- Sys.time()
    tryCatch(.make_figures(full, fig_root, fopts, p, rec, do_pdf = do_pdf,
                           groups = fig_groups, run_id = run_id),
             error = function(e) {
               fig_err <<- conditionMessage(e)
               .sp_log("[fig] FAILED (partial figures kept): ", fig_err)
             })
    if (length(rec$rows) > 0) {
      fig_df <- do.call(rbind, rec$rows)
      n_fig_ok      <- sum(fig_df$ok)
      n_fig_missing <- sum(!fig_df$ok)
      fig_bytes     <- sum(fig_df$bytes)
      # 无论 .make_figures 是否中途出错，都在这里补写一次逐图记录（合并式，不覆盖既有分节）
      figure_manifest_csv <- file.path(fig_root, "_figure_manifest.csv")
      .merge_write_fig_csv(fig_df, fig_root, run_id)
      fig_df$run_id <- run_id
      .write_run_record(fig_df, fig_root, run_id,
                        extra = list(mode = "full",
                                     figure_groups = if (is.null(fig_groups)) "all" else paste(fig_groups, collapse = ",")))
    }
    .sp_log("[fig] done in ", round(as.numeric(difftime(Sys.time(), t_fig, units = "secs")), 1),
            "s | ok=", n_fig_ok, " missing=", n_fig_missing,
            " bytes=", fig_bytes)
  }

  elapsed <- as.numeric(difftime(Sys.time(), t0, units = "secs"))
  summary <- list(
    ok               = TRUE,
    dataset_id       = dataset_id,
    run_id           = run_id,
    finished_at      = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"),
    started_at       = format(t0, "%Y-%m-%dT%H:%M:%S"),
    elapsed_sec      = round(elapsed, 1),
    n_samples        = length(samples),
    n_spots          = n_spots_total,
    n_genes          = nrow(full),
    n_spots_pass_qc  = as.integer(n_spots_pass),
    n_clusters       = n_clusters,
    n_hvg            = n_hvg,
    artifact         = basename(artifact_path),
    artifact_bytes   = file.info(artifact_path)$size,
    samples_csv      = basename(samples_csv),
    figures_root     = if (is.null(fig_root)) "" else fig_root,
    figures_pdf      = do_pdf,
    figure_files_ok  = n_fig_ok,
    figure_files_missing = n_fig_missing,
    figure_bytes     = fig_bytes,
    figure_error     = fig_err,
    r_version        = R.version.string,
    params           = p
  )
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    writeLines(jsonlite::toJSON(summary, auto_unbox = TRUE, pretty = TRUE, null = "null"),
               summary_json)
  }
  .sp_log("done in ", round(elapsed, 1), "s")
  invisible(list(ok = TRUE, dataset_id = dataset_id,
                 artifact = artifact_path, samples_csv = samples_csv,
                 summary_json = summary_json, summary = summary,
                 figure_manifest = figure_manifest_csv, figure_df = fig_df,
                 sample_stats = sample_stats, detail = ""))
}


# =============================================================================
# 仅出图入口（M2a 的 `--figures-only`）—— **读已有成品，不重跑流水线、不覆盖 .rds**
# -----------------------------------------------------------------------------
# 用途：M1 的 .rds 已存在时，省掉约 200 s 的流水线，只花"读盘 + 出图"的时间。
# 硬保证：**绝不写 out_root 下的任何文件**（只读 .rds），图全部落在 fig_root。
# =============================================================================
run_spatial_figures_only <- function(out_root, fig_root, dataset_id = "GSE237183",
                                     params = list(), fig_opts = list(), do_pdf = TRUE,
                                     samples = NULL, fig_groups = NULL) {
  t0 <- Sys.time()
  run_id <- format(t0, "%Y%m%d-%H%M%S")   # ★ 本次运行的稳定标识，写进 manifest / summary / runs/
  p <- utils::modifyList(default_params(), params)
  if (!dir.exists(out_root)) stop("out_root not found: ", out_root)
  if (missing(fig_root) || is.null(fig_root) || !nzchar(fig_root)) stop("fig_root is required")
  if (grepl("[^ -~]", fig_root)) stop("fig_root must be pure ASCII: ", fig_root)
  artifact <- file.path(out_root, paste0(dataset_id, ".rds"))
  if (!file.exists(artifact)) stop("artifact not found: ", artifact)

  dir.create(fig_root, showWarnings = FALSE, recursive = TRUE)
  .sp_log("[figures-only] readRDS ", artifact,
          " (", round(file.size(artifact) / 1048576, 1), " MB)")
  obj <- readRDS(artifact)
  if (!"pass_qc" %in% colnames(obj@meta.data)) {
    stop("object has no `pass_qc` column - not an M1 artifact: ", artifact)
  }
  .sp_log("[figures-only] loaded: ", nrow(obj), " x ", ncol(obj),
          " | pass_qc=", sum(obj@meta.data$pass_qc),
          " | clusters=", length(levels(obj@meta.data$seurat_clusters)),
          " | var.features=", length(VariableFeatures(obj)))

  # 冒烟探测用：只保留选中的样本（**只影响本次出图，绝不回写 .rds**）
  if (!is.null(samples) && length(samples) > 0) {
    keep <- colnames(obj)[as.character(obj@meta.data$sample) %in% as.character(samples)]
    if (length(keep) == 0) {
      stop("no cells matched the requested samples: ", paste(samples, collapse = ","))
    }
    obj <- subset(obj, cells = keep)
    .sp_log("[figures-only] subset to ", length(samples), " sample(s) [",
            paste(samples, collapse = ","), "] -> ", ncol(obj), " spots")
  }

  fopts <- utils::modifyList(default_fig_opts(), fig_opts)
  rec <- .new_fig_recorder()
  fig_err <- ""
  tryCatch(.make_figures(obj, fig_root, fopts, p, rec, do_pdf = do_pdf,
                         groups = fig_groups, run_id = run_id),
           error = function(e) {
             fig_err <<- conditionMessage(e)
             .sp_log("[figures-only] FAILED (partial figures kept): ", fig_err)
           })
  fig_df <- if (length(rec$rows) == 0) NULL else do.call(rbind, rec$rows)
  n_ok <- if (is.null(fig_df)) 0L else sum(fig_df$ok)
  n_missing <- if (is.null(fig_df)) 0L else sum(!fig_df$ok)
  fig_bytes <- if (is.null(fig_df)) 0 else sum(fig_df$bytes)
  fm_csv <- file.path(fig_root, "_figure_manifest.csv")
  if (!is.null(fig_df)) .merge_write_fig_csv(fig_df, fig_root, run_id)

  elapsed <- as.numeric(difftime(Sys.time(), t0, units = "secs"))
  summary <- list(
    ok = TRUE, mode = "figures_only", dataset_id = dataset_id,
    run_id = run_id,
    finished_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"),
    elapsed_sec = round(elapsed, 1),
    artifact = artifact, figures_root = fig_root, figures_pdf = do_pdf,
    figure_groups = if (is.null(fig_groups)) "all" else paste(fig_groups, collapse = ","),
    figure_files_ok = n_ok, figure_files_missing = n_missing,
    figure_bytes = fig_bytes, figure_error = fig_err,
    note = paste0("本文件只反映「run_id=", run_id, "」这一次运行；图集是累积的，",
                  "全量真值见 _atlas_summary.json，逐图归属见 _figure_manifest.csv 的 run_id 列"),
    r_version = R.version.string)
  writeLines(jsonlite::toJSON(summary, auto_unbox = TRUE, pretty = TRUE, null = "null"),
             file.path(fig_root, "_figures_summary.json"))
  # ★ 每次运行的独立留档目录，永不覆盖
  if (!is.null(fig_df)) {
    fig_df$run_id <- run_id
    .write_run_record(fig_df, fig_root, run_id,
                      extra = list(mode = "figures_only",
                                   figure_groups = if (is.null(fig_groups)) "all" else paste(fig_groups, collapse = ","),
                                   elapsed_sec = round(elapsed, 1)))
  }
  .sp_log("[figures-only] done in ", round(elapsed, 1), "s | ok=", n_ok,
          " missing=", n_missing, " bytes=", fig_bytes)
  invisible(list(ok = TRUE, dataset_id = dataset_id, artifact = artifact,
                 figure_manifest = fm_csv, figure_df = fig_df, summary = summary, detail = ""))
}


# =============================================================================
# CLI 入口
# =============================================================================
.parse_cli <- function(argv) {
  # 支持  --key value  与  --flag
  flag_keys <- c("no_umap", "no_figures", "figures_only", "fig_png_only")
  out <- list()
  i <- 1L
  while (i <= length(argv)) {
    a <- argv[i]
    if (grepl("^--", a)) {
      key <- sub("^--", "", a)
      if (key %in% flag_keys) {
        out[[key]] <- TRUE; i <- i + 1L; next
      }
      if (i + 1L > length(argv)) stop("missing value for --", key)
      out[[key]] <- argv[i + 1L]
      i <- i + 2L
    } else {
      i <- i + 1L
    }
  }
  out
}

.USAGE <- paste0(
  "usage:\n",
  "  # 全量构建（流水线 + 出图）\n",
  "  Rscript spatial_pipeline.R --data_root <dir> --out_root <dir> --fig_root <dir> \\\n",
  "      [--samples A,B,C] [--dataset_id ID] [--min_nFeature N] [--min_nCount N]\n",
  "      [--nfeatures N] [--npcs N] [--pc_use N] [--resolution R] [--umap_n_neighbors N]\n",
  "      [--no_umap] [--no_figures] [--fig_png_only] [--fig_genes A,B] [--fig_sample_genes X]\n",
  "      [--fig_groups early,score,persample,marker,celltype]  # 分节出图（规避单条命令超时）\n",
  "  # 仅出图（读已有 <out_root>/<dataset_id>.rds，不重跑流水线、不覆盖 .rds）\n",
  "  Rscript spatial_pipeline.R --figures_only --out_root <dir> --fig_root <dir> [--dataset_id ID]\n")

.cli_main <- function() {
  a <- .parse_cli(commandArgs(trailingOnly = TRUE))
  figs_only <- isTRUE(a$figures_only)
  if (figs_only) {
    if (is.null(a$out_root) || is.null(a$fig_root)) { cat(.USAGE); quit(status = 2) }
  } else {
    if (is.null(a$data_root) || is.null(a$out_root)) { cat(.USAGE); quit(status = 2) }
  }
  samples <- NULL
  if (!is.null(a$samples) && nzchar(a$samples)) {
    samples <- trimws(strsplit(a$samples, ",", fixed = TRUE)[[1]])
    samples <- samples[nzchar(samples)]
  }
  params <- list()
  num_keys <- c("min_cells", "min_nFeature", "min_nCount", "scale_factor", "nfeatures",
                "npcs", "pc_use", "resolution", "umap_n_neighbors", "umap_seed")
  for (k in num_keys) {
    if (!is.null(a[[k]])) {
      v <- suppressWarnings(as.numeric(a[[k]]))
      if (is.na(v)) stop("invalid numeric value for --", k, ": ", a[[k]])
      params[[k]] <- v
    }
  }
  if (isTRUE(a$no_umap)) params$do_umap <- FALSE

  # 出图选项
  fig_opts <- list()
  if (!is.null(a$fig_genes) && nzchar(a$fig_genes)) {
    fig_opts$genes_show <- trimws(strsplit(a$fig_genes, ",", fixed = TRUE)[[1]])
  }
  if (!is.null(a$fig_sample_genes) && nzchar(a$fig_sample_genes)) {
    fig_opts$genes_to_plot <- trimws(strsplit(a$fig_sample_genes, ",", fixed = TRUE)[[1]])
  }
  do_pdf <- !isTRUE(a$fig_png_only)
  ds_id <- if (is.null(a$dataset_id)) "GSE237183" else a$dataset_id

  # ★ 分节出图：本机每条命令有硬性超时（实测 ~6 分钟），19 样本全量出图约 9~10 分钟，
  #   必须切成 early / score / persample / marker / celltype 若干段分别跑。
  fig_groups <- NULL
  if (!is.null(a$fig_groups) && nzchar(a$fig_groups)) {
    fig_groups <- trimws(strsplit(a$fig_groups, ",", fixed = TRUE)[[1]])
    fig_groups <- fig_groups[nzchar(fig_groups)]
    if (length(fig_groups) == 0) fig_groups <- NULL
  }

  if (figs_only) {
    res <- run_spatial_figures_only(out_root = a$out_root, fig_root = a$fig_root,
                                    dataset_id = ds_id, params = params,
                                    fig_opts = fig_opts, do_pdf = do_pdf,
                                    samples = samples, fig_groups = fig_groups)
  } else {
    res <- run_spatial_pipeline(data_root = a$data_root, samples = samples,
                                out_root = a$out_root, params = params, dataset_id = ds_id,
                                fig_root = if (isTRUE(a$no_figures)) NULL else a$fig_root,
                                fig_opts = fig_opts, do_pdf = do_pdf,
                                fig_groups = fig_groups)
  }
  # 给驱动用的单行结果标记（ASCII，避免编码问题）
  cat("##SPATIAL_RESULT##", jsonlite::toJSON(res$summary, auto_unbox = TRUE), "\n", sep = "")
  invisible(NULL)
}


# 只在被当作脚本执行时运行；被 source() 时**只定义函数，不做任何重活**
if (sys.nframe() == 0L) {
  .cli_main()
}
