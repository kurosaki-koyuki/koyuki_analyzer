# -*- coding: utf-8 -*-
"""
scRNAseq Monocle分析核心算法层 - 使用subprocess调用R脚本
"""

import os
import subprocess
import traceback
import ctypes

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class ScMonocleAnalysis:
    def __init__(self):
        self.seurat_path = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self._r_script_path = os.path.join(os.path.dirname(__file__), 'run_monocle.R')
        
        self._r_interface = get_r_kernel_interface()
        self._rscript_path = self._get_rscript_path()

    def _get_rscript_path(self):
        r_path = self._r_interface.get_r_path()
        if r_path:
            return os.path.join(r_path, "bin", "Rscript.exe")
        return r"A:\TOOLS\R\R-4.6.1\bin\Rscript.exe"

    def _get_short_path(self, path):
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetShortPathNameW(path, buf, 260)
            return buf.value
        except:
            return path

    def _run_r_script(self, args):
        try:
            rscript_path = self._rscript_path
            
            short_args = []
            for arg in args:
                if isinstance(arg, str) and ('\\' in arg or '/' in arg):
                    short_path = self._get_short_path(arg)
                    short_args.append(short_path if short_path else arg)
                else:
                    short_args.append(arg)
            
            cmd = [rscript_path, self._get_short_path(self._r_script_path)] + short_args
            
            result = subprocess.run(cmd, capture_output=True, text=False, timeout=600)
            
            stdout = result.stdout.decode('utf-8', errors='ignore').strip() if result.stdout else ""
            stderr = result.stderr.decode('utf-8', errors='ignore').strip() if result.stderr else ""
            
            if result.returncode != 0:
                print(f"R脚本执行失败: {stderr}")
                return None, stderr
            
            return stdout, None
        except subprocess.TimeoutExpired:
            return None, "R脚本执行超时"
        except Exception as e:
            print(f"调用R脚本异常: {e}")
            traceback.print_exc()
            return None, str(e)

    def set_seurat_path(self, seurat_path):
        self.seurat_path = seurat_path

    def set_dataset_name(self, dataset_name):
        self.dataset_name = dataset_name

    def set_dataset_output_dir(self, dataset_output_dir):
        self.dataset_output_dir = dataset_output_dir

    def _get_monocle_output_dir(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        output_dir = os.path.join(project_root, "OUTPUT", "monocle3", self.dataset_name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def run_stage1_simple(self):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return False, "Seurat对象路径不存在"
        
        if not self.dataset_name:
            return False, "数据集名称未设置"
        
        output_dir = self._get_monocle_output_dir()
        
        try:
            print("[Monocle] 正在执行阶段一分析（简单UMAP出图）...")
            
            return self._run_stage1_simple_subprocess(output_dir)
        
        except Exception as e:
            print(f"阶段一分析失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def _run_stage1_simple_subprocess(self, output_dir):
        args = [
            self.seurat_path,
            output_dir,
            self.dataset_name,
            "stage1_simple"
        ]
        
        stdout, stderr = self._run_r_script(args)
        
        if stdout and "ERROR" not in stdout:
            print(f"[Monocle] 阶段一分析完成: {stdout}")
            return True, stdout
        
        return False, stderr if stderr else stdout if stdout else "阶段一分析失败"

    def _run_stage1_simple_rpy2(self, output_dir):
        try:
            robjects = self._r_interface.get_robjects()
            if robjects is None:
                return False, "R环境不可用"
            
            seurat_path = self.seurat_path.replace("\\", "/")
            output_dir = output_dir.replace("\\", "/")
            
            r_code = f"""
            library(Seurat)
            library(dplyr)
            library(ggplot2)
            library(grid)
            library(ggrepel)
            library(tidydr)

            cat("Loading Seurat object...\\n")
            seurat_obj <- readRDS("{seurat_path}")
            cat(paste("Loaded: ", ncol(seurat_obj), " cells, ", nrow(seurat_obj), " genes\\n"))

            assign("seurat_obj", seurat_obj, envir = .GlobalEnv)
            cat("已将Seurat对象保存到全局环境\\n")

            if (!"umap" %in% names(seurat_obj@reductions)) {{
                cat("ERROR: No UMAP reduction found")
                quit(status = 1)
            }}

            cat("Extracting UMAP coordinates...\\n")
            umap_df <- as.data.frame(Embeddings(seurat_obj, reduction = "umap"))
            colnames(umap_df) <- c("umap_1", "umap_2")
            umap_df$cell <- rownames(umap_df)

            cluster_colors <- c(
                '#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00',
                '#cab2d6','#6a3d9a','#b15928','#49beaa','#611c35','#2708a0','#E59CC4','#90EE90',
                '#F1BB72','#57C3F3','#E59C59','#D6E7A3','#0FA3A8','#F3B1A0','#E5D2DD','#AB3282',
                '#33452F','#BD956A','#8C549C','#585658','#476D87','#E0D4CA','#5F3D69','#C5DEBA',
                '#58A4C3','#E4C755','#F7F398','#AA9A59','#E63863','#E39A35','#C1E6F3','#6778AE',
                '#91D0BE','#B53E2B','#712820','#DCC1DD','#CCE0F5','#CCC9E6','#625D9E','#68A180',
                '#968175','#778899','#B0C4DE','#E6E6FA','#DDA0DD','#FFDAB9','#F0E68C','#ADFF2F',
                '#00CED1','#FF69B4','#CD5C5C','#F08080','#FA8072','#E9967A','#FFA07A','#FF7F50',
                '#FF6347','#FF4500','#FF8C00','#FFA500','#FFD700','#FFFF00','#FFFFE0','#FFFFF0'
            )

            if ("seurat_clusters" %in% colnames(seurat_obj@meta.data)) {{
                umap_df$cellType <- as.factor(seurat_obj@meta.data$seurat_clusters)
                unique_types <- unique(umap_df$cellType)
                num_types <- length(unique_types)
                if (num_types > length(cluster_colors)) {{
                    type_colors <- grDevices::colorRampPalette(cluster_colors)(num_types)
                }} else {{
                    type_colors <- cluster_colors[1:num_types]
                }}
                names(type_colors) <- unique_types
                celltypepos <- umap_df %>% group_by(cellType) %>% summarise(umap_1=median(umap_1), umap_2=median(umap_2))
                p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
                    geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
                    scale_color_manual(values = type_colors) +
                    geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType), fontface = "bold", data = celltypepos, box.padding = 0.5, point.padding = 0.5, size = 6, label.size = 0.5, fill = "white", alpha = 0.75) +
                    theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
                    ggtitle(paste("{self.dataset_name}", "Clusters"))
            }} else {{
                umap_df$cellType <- "all"
                p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
                    geom_point(size = 0.6, color = "#33a02c") +
                    theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
                    ggtitle(paste("{self.dataset_name}", "Cells"))
            }}

            cat("Plotting UMAP...\\n")
            png_path <- file.path("{output_dir}", paste0("{self.dataset_name}", "_1_umap_no_trajectory.png"))
            png(file = png_path, width = 1200, height = 1200, res = 150)
            print(p)
            dev.off()
            cat("UMAP plot saved!\\n")

            cat("{output_dir}")
            """
            
            result = self._r_interface.execute_r_code(r_code)
            
            if result is not None:
                result_str = str(result)
                if "ERROR" not in result_str:
                    print(f"[Monocle] 阶段一分析完成")
                    return True, result_str
            
            return False, self._r_interface.get_error_message() or "阶段一分析失败"
        
        except Exception as e:
            print(f"阶段一分析失败(rpy2): {e}")
            traceback.print_exc()
            return False, str(e)

    def run_stage1_analysis(self):
        return self.run_stage1_simple()

    def generate_annotation_plot(self, annotation_col):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return False, "Seurat对象路径不存在"
        
        if not self.dataset_name:
            return False, "数据集名称未设置"
        
        if not annotation_col:
            return False, "请选择注释列"
        
        output_dir = self._get_monocle_output_dir()
        
        try:
            print(f"[Monocle] 正在绘制注释图: {annotation_col}...")
            
            args = [
                self.seurat_path,
                output_dir,
                self.dataset_name,
                "annotation_plot",
                annotation_col
            ]
            
            stdout, stderr = self._run_r_script(args)
            
            if stdout and "ERROR" not in stdout:
                print(f"[Monocle] 注释图绘制完成: {stdout}")
                return True, stdout
            
            return False, stderr if stderr else stdout if stdout else "注释图绘制失败"
        except Exception as e:
            print(f"绘制注释图失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def run_stage2_filter(self, main_col, main_groups, filter1_col, filter1_groups, filter2_col, filter2_groups, re_reduce, dim_val, plot_annotation_col):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return False, "Seurat对象路径不存在"
        
        if not self.dataset_name:
            return False, "数据集名称未设置"
        
        output_dir = self._get_monocle_output_dir()
        
        try:
            print("[Monocle] 正在执行阶段二分析（细胞筛选）...")
            
            return self._run_stage2_filter_subprocess(main_col, main_groups, filter1_col, filter1_groups, filter2_col, filter2_groups, re_reduce, dim_val, plot_annotation_col, output_dir)
        
        except Exception as e:
            print(f"阶段二分析失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def _run_stage2_filter_subprocess(self, main_col, main_groups, filter1_col, filter1_groups, filter2_col, filter2_groups, re_reduce, dim_val, plot_annotation_col, output_dir):
        main_groups_str = ",".join(main_groups) if main_groups else ""
        filter1_groups_str = ",".join(filter1_groups) if filter1_groups else ""
        filter2_groups_str = ",".join(filter2_groups) if filter2_groups else ""
        
        args = [
            self.seurat_path,
            output_dir,
            self.dataset_name,
            "stage2_filter",
            main_col,
            main_groups_str,
            filter1_col,
            filter1_groups_str,
            filter2_col,
            filter2_groups_str,
            str(re_reduce).upper(),
            str(dim_val),
            plot_annotation_col
        ]
        
        stdout, stderr = self._run_r_script(args)
        
        if stdout and "ERROR" not in stdout:
            print(f"[Monocle] 阶段二分析完成: {stdout}")
            return True, stdout
        
        return False, stderr if stderr else stdout if stdout else "阶段二分析失败"

    def _run_stage2_filter_rpy2(self, main_col, main_groups, filter1_col, filter1_groups, filter2_col, filter2_groups, re_reduce, dim_val, plot_annotation_col, output_dir):
        try:
            robjects = self._r_interface.get_robjects()
            if robjects is None:
                return False, "R环境不可用"
            
            seurat_path = self.seurat_path.replace("\\", "/")
            output_dir = output_dir.replace("\\", "/")
            
            main_groups_str = ",".join(main_groups) if main_groups else ""
            filter1_groups_str = ",".join(filter1_groups) if filter1_groups else ""
            filter2_groups_str = ",".join(filter2_groups) if filter2_groups else ""
            
            r_code = f"""
            library(Seurat)
            library(dplyr)
            library(ggplot2)
            library(grid)
            library(ggrepel)
            library(tidydr)

            if (!exists("seurat_obj", envir = .GlobalEnv)) {{
                seurat_obj <- readRDS("{seurat_path}")
                cat(paste("已加载原始Seurat对象: ", ncol(seurat_obj), " cells\\n"))
            }} else {{
                seurat_obj <- get("seurat_obj", envir = .GlobalEnv)
                cat(paste("已从全局环境加载Seurat对象: ", ncol(seurat_obj), " cells\\n"))
            }}

            cat("开始筛选细胞...\\n")
            cat(paste("原始细胞数: ", ncol(seurat_obj), "\\n"))

            filtered_seurat <- seurat_obj

            main_col <- "{main_col}"
            main_groups <- if ("{main_groups_str}" != "") unlist(strsplit("{main_groups_str}", ",")) else character(0)
            if (main_col != "" && length(main_groups) > 0 && main_col %in% colnames(filtered_seurat@meta.data)) {{
                filtered_seurat <- filtered_seurat[, filtered_seurat@meta.data[[main_col]] %in% main_groups]
                cat(paste("主注释筛选: ", main_col, " in ", paste(main_groups, collapse=", "), ", 剩余细胞数: ", ncol(filtered_seurat), "\\n"))
            }}

            filter1_col <- "{filter1_col}"
            filter1_groups <- if ("{filter1_groups_str}" != "") unlist(strsplit("{filter1_groups_str}", ",")) else character(0)
            if (filter1_col != "" && length(filter1_groups) > 0 && filter1_col %in% colnames(filtered_seurat@meta.data)) {{
                filtered_seurat <- filtered_seurat[, filtered_seurat@meta.data[[filter1_col]] %in% filter1_groups]
                cat(paste("筛选条件1: ", filter1_col, " in ", paste(filter1_groups, collapse=", "), ", 剩余细胞数: ", ncol(filtered_seurat), "\\n"))
            }}

            filter2_col <- "{filter2_col}"
            filter2_groups <- if ("{filter2_groups_str}" != "") unlist(strsplit("{filter2_groups_str}", ",")) else character(0)
            if (filter2_col != "" && length(filter2_groups) > 0 && filter2_col %in% colnames(filtered_seurat@meta.data)) {{
                filtered_seurat <- filtered_seurat[, filtered_seurat@meta.data[[filter2_col]] %in% filter2_groups]
                cat(paste("筛选条件2: ", filter2_col, " in ", paste(filter2_groups, collapse=", "), ", 剩余细胞数: ", ncol(filtered_seurat), "\\n"))
            }}

            if (ncol(filtered_seurat) == 0) {{
                cat("ERROR: 筛选后无细胞")
                quit(status = 1)
            }}

            re_reduce <- as.logical({re_reduce})
            dim_val <- as.integer({dim_val})
            if (re_reduce) {{
                cat("重新降维...\\n")
                filtered_seurat <- Seurat::ScaleData(filtered_seurat)
                filtered_seurat <- Seurat::RunPCA(filtered_seurat, npcs = dim_val)
                filtered_seurat <- Seurat::RunUMAP(filtered_seurat, dims = 1:dim_val)
                cat(paste("重新降维完成，使用PCA维度: ", dim_val, "\\n"))
            }} else {{
                cat("使用原始UMAP坐标\\n")
            }}

            assign("seurat_obj", filtered_seurat, envir = .GlobalEnv)
            cat("已更新seurat对象为筛选后的数据\\n")

            if (!"umap" %in% names(filtered_seurat@reductions)) {{
                cat("ERROR: 筛选后的对象没有UMAP降维")
                quit(status = 1)
            }}

            plot_annotation_col <- "{plot_annotation_col}"
            if (plot_annotation_col == "") {{
                plot_annotation_col <- main_col
            }}

            if (plot_annotation_col == "" || !(plot_annotation_col %in% colnames(filtered_seurat@meta.data))) {{
                plot_annotation_col <- if ("seurat_clusters" %in% colnames(filtered_seurat@meta.data)) "seurat_clusters" else colnames(filtered_seurat@meta.data)[1]
            }}

            umap_df <- as.data.frame(Embeddings(filtered_seurat, reduction = "umap"))
            colnames(umap_df) <- c("umap_1", "umap_2")
            umap_df$cellType <- as.factor(filtered_seurat@meta.data[[plot_annotation_col]])

            cluster_colors <- c(
                '#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00',
                '#cab2d6','#6a3d9a','#b15928','#49beaa','#611c35','#2708a0','#E59CC4','#90EE90',
                '#F1BB72','#57C3F3','#E59C59','#D6E7A3','#0FA3A8','#F3B1A0','#E5D2DD','#AB3282',
                '#33452F','#BD956A','#8C549C','#585658','#476D87','#E0D4CA','#5F3D69','#C5DEBA',
                '#58A4C3','#E4C755','#F7F398','#AA9A59','#E63863','#E39A35','#C1E6F3','#6778AE',
                '#91D0BE','#B53E2B','#712820','#DCC1DD','#CCE0F5','#CCC9E6','#625D9E','#68A180',
                '#968175','#778899','#B0C4DE','#E6E6FA','#DDA0DD','#FFDAB9','#F0E68C','#ADFF2F',
                '#00CED1','#FF69B4','#CD5C5C','#F08080','#FA8072','#E9967A','#FFA07A','#FF7F50',
                '#FF6347','#FF4500','#FF8C00','#FFA500','#FFD700','#FFFF00','#FFFFE0','#FFFFF0'
            )

            unique_types <- unique(umap_df$cellType)
            num_types <- length(unique_types)
            if (num_types > length(cluster_colors)) {{
                type_colors <- grDevices::colorRampPalette(cluster_colors)(num_types)
            }} else {{
                type_colors <- cluster_colors[1:num_types]
            }}
            names(type_colors) <- unique_types

            celltypepos <- umap_df %>% group_by(cellType) %>% summarise(umap_1=median(umap_1), umap_2=median(umap_2))

            p <- ggplot(umap_df, aes(x = umap_1, y = umap_2)) +
                geom_point(aes(color = cellType), size = 0.6, show.legend = FALSE) +
                scale_color_manual(values = type_colors) +
                geom_label_repel(aes(x = umap_1, y = umap_2, label = cellType, color = cellType), fontface = "bold", data = celltypepos, box.padding = 0.5, point.padding = 0.5, size = 6, label.size = 0.5, fill = "white", alpha = 0.75) +
                theme_dr() + theme(aspect.ratio = 1, panel.background = element_blank(), panel.grid = element_blank(), axis.line = element_line(color = "black", linewidth = 0.5), axis.ticks = element_blank(), axis.ticks.length = unit(0.2, "cm"), axis.title = element_text(hjust = 0.05, size = 12), plot.title = element_text(hjust = 0.5, size = 20, face = "bold", color = "black"), legend.position = "none") +
                ggtitle(paste("{self.dataset_name}", "Filtered -", plot_annotation_col))

            annotation_name <- gsub("\\s|\\(|\\)", "_", plot_annotation_col)
            png_path <- file.path("{output_dir}", paste0("{self.dataset_name}", "_filtered_", annotation_name, "_umap.png"))
            png(file = png_path, width = 1200, height = 1200, res = 150)
            print(p)
            dev.off()

            cat(paste("筛选后细胞数: ", ncol(filtered_seurat), "\\n"))
            cat(png_path)
            """
            
            result = self._r_interface.execute_r_code(r_code)
            
            if result is not None:
                result_str = str(result)
                if "ERROR" not in result_str:
                    print(f"[Monocle] 阶段二分析完成")
                    return True, result_str
            
            return False, self._r_interface.get_error_message() or "阶段二分析失败"
        
        except Exception as e:
            print(f"阶段二分析失败(rpy2): {e}")
            traceback.print_exc()
            return False, str(e)

    def run_stage2_analysis(self):
        return self.run_stage2_filter("", [], "", [], "", [], False, 2, "")

    def run_stage3_cds(self, num_dim=50, alignment_col="", plot_annotation_col="", coord_mode="UMAP"):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return False, "Seurat对象路径不存在"
        
        if not self.dataset_name:
            return False, "数据集名称未设置"
        
        output_dir = self._get_monocle_output_dir()
        
        try:
            print("[Monocle] 正在执行阶段三分析（CDS创建）...")
            
            return self._run_stage3_cds_subprocess(num_dim, alignment_col, plot_annotation_col, coord_mode, output_dir)
        
        except Exception as e:
            print(f"阶段三分析失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def _run_stage3_cds_subprocess(self, num_dim, alignment_col, plot_annotation_col, coord_mode, output_dir):
        args = [
            self.seurat_path,
            output_dir,
            self.dataset_name,
            "stage3_cds",
            str(num_dim),
            alignment_col,
            plot_annotation_col,
            coord_mode
        ]
        
        stdout, stderr = self._run_r_script(args)
        
        if stdout and "ERROR" not in stdout:
            print(f"[Monocle] 阶段三分析完成")
            return True, stdout
        
        return False, stderr if stderr else stdout if stdout else "阶段三分析失败"

    def _run_stage3_cds_rpy2(self, num_dim, alignment_col, plot_annotation_col, coord_mode, output_dir):
        try:
            robjects = self._r_interface.get_robjects()
            if robjects is None:
                return False, "R环境不可用"
            
            seurat_path = self.seurat_path.replace("\\", "/")
            output_dir = output_dir.replace("\\", "/")
            
            r_code = f"""
            library(monocle3)
            library(Seurat)
            library(dplyr)
            library(ggplot2)
            library(grid)
            library(ggrepel)
            library(tidydr)
            library(koyukiTraj)

            if (!exists("seurat_obj", envir = .GlobalEnv)) {{
                cat("未找到全局环境中的Seurat对象，从文件加载...\\n")
                seurat_obj <- readRDS("{seurat_path}")
                cat(paste("已加载原始Seurat对象: ", ncol(seurat_obj), " cells\\n"))
            }} else {{
                seurat_obj <- get("seurat_obj", envir = .GlobalEnv)
                cat(paste("已从全局环境加载Seurat对象: ", ncol(seurat_obj), " cells\\n"))
            }}

            cat("开始创建CDS对象...\\n")
            cds <- monocle3::new_cell_data_set(
                expression_data = SeuratObject::GetAssayData(seurat_obj, assay = "RNA", layer = "counts"),
                cell_metadata = seurat_obj@meta.data,
                gene_metadata = data.frame(gene_short_name = rownames(seurat_obj), row.names = rownames(seurat_obj))
            )
            cat("CDS对象创建完成\\n")

            cds <- preprocess_cds(cds, num_dim = {num_dim})
            cat(paste("数据预处理完成，num_dim: {num_dim}\\n"))

            alignment_col <- "{alignment_col}"
            if (alignment_col != "" && alignment_col %in% colnames(cds@colData)) {{
                cds <- align_cds(cds, alignment_group = alignment_col)
                cat(paste("批次校正完成，使用: ", alignment_col, "\\n"))
            }} else {{
                cat("跳过批次校正\\n")
            }}

            cds <- reduce_dimension(cds, max_components = 2)
            cat("CDS降维完成\\n")

            coord_mode <- "{coord_mode}"
            if (coord_mode == "UMAP" && "umap" %in% names(seurat_obj@reductions)) {{
                cds_embed <- cds@int_colData$reducedDims$UMAP
                seurat_embed <- Embeddings(seurat_obj, reduction = "umap")
                seurat_embed <- seurat_embed[rownames(cds_embed), ]
                cds@int_colData$reducedDims$UMAP <- seurat_embed
                cat("已使用Seurat的UMAP坐标替换CDS坐标\\n")
            }}

            cds <- cluster_cells(cds)
            cat("细胞聚类完成\\n")

            cds <- learn_graph(cds)
            cat("轨迹学习完成\\n")

            assign("cds_obj", cds, envir = .GlobalEnv)
            cat("已将CDS对象保存到全局环境\\n")

            plot_annotation_col <- "{plot_annotation_col}"
            if (plot_annotation_col == "" || !(plot_annotation_col %in% colnames(cds@colData))) {{
                plot_annotation_col <- if ("seurat_clusters" %in% colnames(cds@colData)) "seurat_clusters" else colnames(cds@colData)[1]
            }}

            p_traj <- koyukiTraj::koyuki_trajectory_plot(cds, annotation_col = plot_annotation_col) +
                ggplot2::ggtitle(paste("{self.dataset_name}", "Trajectory -", plot_annotation_col))

            traj_png_path <- file.path("{output_dir}", paste0("{self.dataset_name}", "_trajectory.png"))
            png(file = traj_png_path, width = 1200, height = 1200, res = 150)
            print(p_traj)
            dev.off()
            cat(paste("Trajectory图已保存: ", traj_png_path, "\\n"))

            p_partition <- koyukiTraj::koyuki_partition_plot(cds) +
                ggplot2::ggtitle(paste("{self.dataset_name}", "Partition"))

            partition_png_path <- file.path("{output_dir}", paste0("{self.dataset_name}", "_partition.png"))
            png(file = partition_png_path, width = 1200, height = 1200, res = 150)
            print(p_partition)
            dev.off()
            cat(paste("Partition图已保存: ", partition_png_path, "\\n"))

            paste(traj_png_path, partition_png_path, sep = "\\n")
            """
            
            result = self._r_interface.execute_r_code(r_code)
            
            if result is not None:
                result_str = str(result)
                if "ERROR" not in result_str:
                    print(f"[Monocle] 阶段三分析完成")
                    return True, result_str
            
            return False, self._r_interface.get_error_message() or "阶段三分析失败"
        
        except Exception as e:
            print(f"阶段三分析失败(rpy2): {e}")
            traceback.print_exc()
            return False, str(e)

    def get_stage1_plot_paths(self):
        if not self.dataset_name:
            return []
        
        output_dir = self._get_monocle_output_dir()
        plots = []
        
        plot_files = [
            f"{self.dataset_name}_1_umap_no_trajectory.png"
        ]
        
        for plot_file in plot_files:
            plot_path = os.path.join(output_dir, plot_file)
            if os.path.exists(plot_path):
                plots.append(plot_path)
        
        return plots

    def get_stage2_plot_paths(self):
        if not self.dataset_name:
            return []
        
        output_dir = self._get_monocle_output_dir()
        plots = []
        
        import glob
        pattern = os.path.join(output_dir, f"{self.dataset_name}_filtered_*.png")
        for plot_path in glob.glob(pattern):
            if os.path.exists(plot_path):
                plots.append(plot_path)
        
        return sorted(plots)

    def run_stage4_pseudotime(self, node_select_mode="auto", root_celltype=""):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return False, "Seurat对象路径不存在"

        if not self.dataset_name:
            return False, "数据集名称未设置"

        output_dir = self._get_monocle_output_dir()

        try:
            print("[Monocle] 正在执行阶段四分析（Pseudotime）...")

            args = [
                self.seurat_path,
                output_dir,
                self.dataset_name,
                "stage4_pseudotime",
                node_select_mode,
                root_celltype
            ]

            # manual模式：非阻塞启动R脚本，返回Shiny URL
            if node_select_mode == "manual":
                return self._start_stage4_manual(args)

            stdout, stderr = self._run_r_script(args)

            if stdout and "ERROR" not in stdout:
                print(f"[Monocle] 阶段四分析完成")
                return True, stdout

            return False, stderr if stderr else stdout if stdout else "阶段四分析失败"
        except Exception as e:
            print(f"阶段四分析失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def kill_port_8787_occupants(self):
        """杀掉占用8787端口的进程（仅Windows）
        在阶段四manual模式启动前调用，防止端口冲突导致Shiny启动失败
        返回: (killed_pids: list, message: str)
        """
        if os.name != 'nt':
            return [], "非Windows系统，跳过8787端口检查"
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 8787))
            sock.close()
            if result != 0:
                # 端口未被占用，无需清理
                return [], "8787端口未被占用，无需清理"

            # 端口被占用，查找占用进程
            find_proc = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            pids_to_kill = set()
            for line in find_proc.stdout.split('\n'):
                if ':8787' in line and 'LISTENING' in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit() and pid != '0':
                            pids_to_kill.add(pid)

            killed_pids = []
            for pid in pids_to_kill:
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/PID', pid],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    killed_pids.append(pid)
                    print(f"[Monocle] 已杀掉占用8787端口的进程: PID={pid}")
                except Exception as e:
                    print(f"[Monocle] 杀掉进程{pid}失败: {e}")

            # 等待端口释放
            if killed_pids:
                import time
                time.sleep(2)
                msg = f"已自动清理占用8787端口的残留进程: PID={', '.join(killed_pids)}"
            else:
                msg = "8787端口被占用但未能杀掉占用进程"
            return killed_pids, msg
        except Exception as e:
            print(f"[Monocle] 检查端口8787失败: {e}")
            return [], f"端口检查失败: {e}"

    def _start_stage4_manual(self, args):
        """manual模式：启动R脚本进程（非阻塞），不读取stdout
        注：8787端口清理已提升到UI层 _run_stage4_manual 入口处执行
        """
        try:
            rscript_path = self._rscript_path
            short_args = []
            for arg in args:
                if isinstance(arg, str) and ('\\' in arg or '/' in arg):
                    short_path = self._get_short_path(arg)
                    short_args.append(short_path if short_path else arg)
                else:
                    short_args.append(arg)
            cmd = [rscript_path, self._get_short_path(self._r_script_path)] + short_args

            # 非阻塞启动（不创建新控制台窗口），stderr合并到stdout
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
            self._stage4_process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                cwd=os.getcwd()
            )

            self._stage4_stdout_lines = []
            print(f"[Monocle] R脚本已启动，等待Shiny URL...")
            return True, "started"
        except Exception as e:
            print(f"manual模式启动失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def read_stage4_line(self):
        """读取R脚本stdout的一行（非阻塞），返回行字符串或None"""
        proc = getattr(self, '_stage4_process', None)
        if proc is None or proc.stdout is None:
            return None

        try:
            import select
            # Windows下select不支持管道，用threading+Queue替代
            if not hasattr(self, '_stage4_reader_thread'):
                import queue
                import threading as _threading
                self._stage4_line_queue = queue.Queue()
                def _reader():
                    while True:
                        line = proc.stdout.readline()
                        if not line:
                            break
                        try:
                            self._stage4_line_queue.put(line.decode('utf-8', errors='ignore').strip())
                        except Exception:
                            self._stage4_line_queue.put(str(line))
                    self._stage4_line_queue.put(None)  # EOF标记
                self._stage4_reader_thread = _threading.Thread(target=_reader, daemon=True)
                self._stage4_reader_thread.start()

            try:
                line = self._stage4_line_queue.get_nowait()
                if line is None:
                    return "EOF"
                self._stage4_stdout_lines.append(line)
                print(f"[Stage4] {line}")
                return line
            except Exception:
                return None
        except Exception as e:
            print(f"读取stdout失败: {e}")
            return None

    def get_stage4_shiny_url(self):
        """检查是否有Shiny URL，返回 (status, data)
        status: 'waiting' | 'url' | 'error' | 'eof'
        data: 对于waiting是最近读取的行（可能为None）；url是URL字符串；error是错误信息
        """
        line = self.read_stage4_line()
        if line is None:
            return "waiting", None
        if line == "EOF":
            return "eof", ""
        if line.startswith("SHINY_START:"):
            url = line.replace("SHINY_START:", "").strip()
            print(f"[Monocle] Shiny已启动: {url}")
            return "url", url
        if "ERROR" in line:
            return "error", line
        return "waiting", line

    def poll_stage4(self):
        """检查manual模式的R脚本是否完成，返回 (finished, result_str)"""
        proc = getattr(self, '_stage4_process', None)
        if proc is None:
            return False, ""

        if proc.poll() is None:
            return False, ""

        # 先读取_line_queue中剩余的行（后台线程已读取但未被消费的行）
        line_queue = getattr(self, '_stage4_line_queue', None)
        if line_queue is not None:
            try:
                while True:
                    try:
                        line = line_queue.get_nowait()
                        if line is None:
                            # EOF标记，跳过
                            break
                        self._stage4_stdout_lines.append(line)
                        print(f"[Stage4] {line}")
                    except Exception:
                        break
            except Exception as e:
                print(f"[Monocle] 读取剩余queue行失败: {e}")

        # 等待后台线程结束
        reader_thread = getattr(self, '_stage4_reader_thread', None)
        if reader_thread is not None and reader_thread.is_alive():
            try:
                reader_thread.join(timeout=2)
            except Exception:
                pass

        # 读取剩余输出（stderr已合并到stdout，通常后台线程已读取完毕，这里返回空）
        try:
            stdout, _ = proc.communicate(timeout=5)
            stdout_str = stdout.decode('utf-8', errors='ignore').strip() if stdout else ""
        except Exception:
            stdout_str = ""

        # 合并所有行
        all_lines = "\n".join(getattr(self, '_stage4_stdout_lines', []))
        if stdout_str:
            all_lines = all_lines + "\n" + stdout_str if all_lines else stdout_str

        self._stage4_process = None
        self._stage4_reader_thread = None

        if proc.returncode != 0:
            return True, f"ERROR: {all_lines}"

        if all_lines and "ERROR" not in all_lines:
            print(f"[Monocle] 阶段四分析完成")
            return True, all_lines

        return True, all_lines or "阶段四分析失败"

    def get_stage3_plot_paths(self):
        if not self.dataset_name:
            return []
        
        output_dir = self._get_monocle_output_dir()
        plots = []
        
        import glob
        pattern = os.path.join(output_dir, f"{self.dataset_name}_trajectory.png")
        for plot_path in glob.glob(pattern):
            if os.path.exists(plot_path):
                plots.append(plot_path)
        
        pattern = os.path.join(output_dir, f"{self.dataset_name}_partition.png")
        for plot_path in glob.glob(pattern):
            if os.path.exists(plot_path):
                plots.append(plot_path)
        
        return sorted(plots)

    def get_stage4_plot_paths(self):
        if not self.dataset_name:
            return []
        
        output_dir = self._get_monocle_output_dir()
        plots = []
        
        import glob
        pattern = os.path.join(output_dir, f"{self.dataset_name}_pseudotime.png")
        for plot_path in glob.glob(pattern):
            if os.path.exists(plot_path):
                plots.append(plot_path)
        
        return sorted(plots)


__all__ = ['ScMonocleAnalysis']