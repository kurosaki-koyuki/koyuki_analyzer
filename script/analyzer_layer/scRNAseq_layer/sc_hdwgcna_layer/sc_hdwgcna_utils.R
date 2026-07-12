# sc_hdwgcna分析工具函数 - 用于元数据查询
# 这些函数不依赖阶段代码，可以独立调用

# --- 缓存机制 ---
.seurat_cache <- new.env(hash = TRUE)

get_cached_seurat <- function(seurat_path_val) {
  cache_key <- seurat_path_val
  if (exists(cache_key, envir = .seurat_cache)) {
    return(get(cache_key, envir = .seurat_cache))
  }
  if (!file.exists(seurat_path_val)) {
    return(NULL)
  }
  scRNA <- readRDS(seurat_path_val)
  assign(cache_key, scRNA, envir = .seurat_cache)
  return(scRNA)
}

clear_seurat_cache <- function() {
  rm(list = ls(.seurat_cache), envir = .seurat_cache)
}

# --- 获取Seurat元数据列名 ---
get_seurat_metadata_columns <- function(seurat_path_val) {
  scRNA <- get_cached_seurat(seurat_path_val)
  if (is.null(scRNA)) {
    return(c())
  }
  return(colnames(scRNA@meta.data))
}

# --- 获取指定列的细胞类型 ---
get_seurat_column_values <- function(seurat_path_val, column_name) {
  scRNA <- get_cached_seurat(seurat_path_val)
  if (is.null(scRNA)) {
    return(c())
  }
  if (!column_name %in% colnames(scRNA@meta.data)) {
    return(c())
  }
  values <- scRNA@meta.data[[column_name]]
  values <- unique(values)
  values <- as.character(values)
  values <- sort(values)
  return(values)
}

# --- 获取Seurat对象信息 ---
get_seurat_info <- function(seurat_path_val) {
  scRNA <- get_cached_seurat(seurat_path_val)
  if (is.null(scRNA)) {
    return("")
  }
  info_lines <- c(
    paste0("Seurat对象信息"),
    paste0("  文件路径: ", seurat_path_val),
    paste0("  细胞数: ", ncol(scRNA)),
    paste0("  基因数: ", nrow(scRNA)),
    paste0("  Assays: ", paste(names(scRNA@assays), collapse=", ")),
    paste0("  Reductions: ", paste(names(scRNA@reductions), collapse=", ")),
    paste0("  元数据列: ", paste(colnames(scRNA@meta.data), collapse=", "))
  )
  return(info_lines)
}