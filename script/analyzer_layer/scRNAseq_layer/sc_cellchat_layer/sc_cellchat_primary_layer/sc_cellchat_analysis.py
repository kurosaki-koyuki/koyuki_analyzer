# -*- coding: utf-8 -*-
"""
CellChat初步分析类分析层
负责调用R脚本进行CellChat分析
"""

import os
import subprocess
from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager


class ScCellChatAnalysis:
    def __init__(self):
        self.seurat_path = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.seurat_metadata_columns = []
        self.seurat_metadata_values = {}
        self.filtered_seurat_path = None  # 筛选后的RDS路径
        self._r_script_path = "A:\\TOOLS\\R\\R-4.6.1\\bin\\Rscript.exe"

    def set_seurat_path(self, path):
        self.seurat_path = path
        self.filtered_seurat_path = None  # 重置筛选路径

    def set_dataset_name(self, name):
        self.dataset_name = name

    def set_dataset_output_dir(self, output_dir):
        self.dataset_output_dir = output_dir

    def set_seurat_metadata_columns(self, columns):
        self.seurat_metadata_columns = columns

    def set_seurat_metadata_values(self, values):
        self.seurat_metadata_values = values

    def _get_output_dir(self):
        """获取输出目录：OUTPUT/cellchat/数据集名称/"""
        if self.dataset_output_dir:
            return self.dataset_output_dir
        # 使用项目OUTPUT目录下的cellchat子文件夹
        if self.dataset_name:
            return os.path.join(OUT_BASE, "cellchat", self.dataset_name)
        return os.path.join(OUT_BASE, "cellchat", "default")

    def generate_umap_plot(self, annotation_col):
        """按注释列生成UMAP图"""
        if not self.seurat_path:
            return False, "请先加载RDS文件"

        if annotation_col == "选择注释列" or not annotation_col:
            return False, "请先选择注释列"

        try:
            output_dir = self._get_output_dir()
            os.makedirs(output_dir, exist_ok=True)

            output_path = os.path.join(output_dir, f"{self.dataset_name}_umap_{annotation_col}.png")

            # R脚本路径
            r_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "run_cellchat_stage1_umap.R"
            )

            # 构建命令行参数
            cmd_args = [
                self._r_script_path,
                r_script,
                self.seurat_path,
                annotation_col,
                output_path
            ]

            # 运行R脚本（使用utf-8编码避免中文乱码）
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return False, f"R脚本执行失败: {error_msg}"

            if os.path.exists(output_path):
                return True, output_path
            else:
                return False, "图片生成失败"

        except subprocess.TimeoutExpired:
            return False, "R脚本执行超时"
        except Exception as e:
            return False, str(e)

    def filter_cells_and_reduce(self, celltypes, re_reduce, dim_val, plot_annot, filter_params=None):
        """筛选细胞类型并可选重新降维，保存筛选后的RDS"""
        if not self.seurat_path:
            return False, "请先加载RDS文件"

        try:
            output_dir = self._get_output_dir()
            os.makedirs(output_dir, exist_ok=True)

            output_path = os.path.join(output_dir, f"{self.dataset_name}_filtered_umap.png")
            filtered_rds_path = os.path.join(output_dir, f"{self.dataset_name}_filtered_seurat.rds")

            # R脚本路径
            r_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "run_cellchat_stage2_filter.R"
            )

            # 获取主注释列
            main_annot = ""
            if filter_params and 'main_annot' in filter_params:
                main_annot = filter_params['main_annot']

            # 构建命令行参数
            celltypes_str = ",".join(celltypes) if celltypes else ""
            re_reduce_str = "TRUE" if re_reduce else "FALSE"

            cmd_args = [
                self._r_script_path,
                r_script,
                self.seurat_path,
                main_annot,  # 主注释列
                celltypes_str,  # 要保留的细胞类型
                re_reduce_str,
                str(dim_val),
                plot_annot,
                output_path,
                filtered_rds_path  # 新增：筛选后RDS保存路径
            ]

            # 运行R脚本（使用utf-8编码避免中文乱码）
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return False, f"R脚本执行失败: {error_msg}"

            # 保存筛选后的RDS路径
            if os.path.exists(filtered_rds_path):
                self.filtered_seurat_path = filtered_rds_path

            if os.path.exists(output_path):
                return True, output_path
            else:
                return False, "图片生成失败"

        except subprocess.TimeoutExpired:
            return False, "R脚本执行超时"
        except Exception as e:
            return False, str(e)

    def run_cellchat_analysis(self, main_annot, celltypes, db_type, db_search,
                              mean_method, min_cells, raw_use):
        """运行CellChat通讯分析（步骤2-7）"""
        # 使用筛选后的RDS（如果存在），否则使用原始RDS
        seurat_path = self.filtered_seurat_path if self.filtered_seurat_path else self.seurat_path
        
        if not seurat_path:
            return False, "请先加载RDS文件"

        try:
            output_dir = self._get_output_dir()
            os.makedirs(output_dir, exist_ok=True)

            count_output = os.path.join(output_dir, f"{self.dataset_name}_cellchat_count.png")
            weight_output = os.path.join(output_dir, f"{self.dataset_name}_cellchat_weight.png")

            # R脚本路径
            r_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "run_cellchat_stage3_analysis.R"
            )

            # 构建命令行参数
            celltypes_str = ",".join(celltypes) if celltypes else ""
            raw_use_str = "TRUE" if raw_use else "FALSE"

            cmd_args = [
                self._r_script_path,
                r_script,
                seurat_path,
                main_annot,
                celltypes_str,
                db_type,
                db_search,
                mean_method,
                str(min_cells),
                raw_use_str,
                output_dir,
                count_output,
                weight_output,
                self.dataset_name
            ]

            # 运行R脚本
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=1800  # 30分钟超时
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return False, f"R脚本执行失败: {error_msg}"

            if os.path.exists(count_output) and os.path.exists(weight_output):
                return True, {
                    'count': count_output,
                    'weight': weight_output
                }
            else:
                return False, "图片生成失败"

        except subprocess.TimeoutExpired:
            return False, "R脚本执行超时"
        except Exception as e:
            return False, str(e)

    def run_subgroup_analysis(self, subgroups):
        """运行阶段四：细分亚组circle图"""
        if not self.dataset_name:
            return False, "请先运行阶段三生成CellChat对象"

        try:
            output_dir = self._get_output_dir()
            os.makedirs(output_dir, exist_ok=True)

            # CellChat对象路径（使用正斜杠避免R解析问题）
            cellchat_rds_path = os.path.join(output_dir, f"{self.dataset_name}_cellchat.rds").replace('\\', '/')
            if not os.path.exists(cellchat_rds_path):
                return False, "请先运行阶段三生成CellChat对象"

            output_path = os.path.join(output_dir, f"{self.dataset_name}_subgroup_circle.png").replace('\\', '/')

            # R脚本路径（使用正斜杠避免R解析问题）
            r_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "run_cellchat_stage4_subgroup.R"
            ).replace('\\', '/')

            # 构建命令行参数（打包成一个字符串，分号分隔）
            subgroups_str = ",".join(subgroups) if subgroups else "__ALL__"
            params_str = f"{cellchat_rds_path};{subgroups_str};{output_path}"

            cmd_args = [
                self._r_script_path,
                r_script,
                params_str
            ]

            # 运行R脚本
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return False, f"R脚本执行失败: {error_msg}"

            if os.path.exists(output_path):
                return True, output_path
            else:
                return False, "图片生成失败"

        except subprocess.TimeoutExpired:
            return False, "R脚本执行超时"
        except Exception as e:
            return False, str(e)

    def run_pathway_visualization(self, pathways, pval_threshold=0.05, pathway_count=5, viz_types=None):
        """运行阶段五：信号通路可视化"""
        if not self.dataset_name:
            return False, "请先运行阶段三生成CellChat对象"

        if viz_types is None:
            viz_types = ["hierarchy", "circle", "chord", "heatmap"]

        try:
            output_dir = self._get_output_dir()
            os.makedirs(output_dir, exist_ok=True)

            # CellChat对象路径
            cellchat_rds_path = os.path.join(output_dir, f"{self.dataset_name}_cellchat.rds").replace('\\', '/')
            if not os.path.exists(cellchat_rds_path):
                return False, "请先运行阶段三生成CellChat对象"

            # R脚本路径
            r_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "run_cellchat_stage5_pathway.R"
            ).replace('\\', '/')

            # 构建参数
            if pathways == "__AUTO__":
                pathways_param = "__AUTO__"
            else:
                pathways_param = ",".join(pathways)

            viz_types_str = ",".join(viz_types)
            output_dir_str = output_dir.replace('\\', '/')

            # 打包参数为一个字符串
            params_str = f"{cellchat_rds_path};{pathways_param};{pval_threshold};{pathway_count};{viz_types_str};{output_dir_str}"

            cmd_args = [
                self._r_script_path,
                r_script,
                params_str
            ]

            # 运行R脚本
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return False, f"R脚本执行失败: {error_msg}"

            # 收集生成的图片（优先使用组合图）
            generated_images = {}
            for viz_type in viz_types:
                combined_file = os.path.join(output_dir, f"{viz_type}_combined.png")
                if os.path.exists(combined_file):
                    generated_images[viz_type] = combined_file
                else:
                    # 如果没有组合图，查找单个通路的图
                    images = []
                    for f in os.listdir(output_dir):
                        if f.startswith(viz_type + "_") and f.endswith(".png") and "combined" not in f:
                            images.append(os.path.join(output_dir, f))
                    if images:
                        generated_images[viz_type] = images[0]
            
            # 检查通路信息表格
            info_file = os.path.join(output_dir, "pathway_info.csv")
            info_data = None
            if os.path.exists(info_file):
                import pandas as pd
                try:
                    info_data = pd.read_csv(info_file)
                except:
                    pass

            if generated_images or os.path.exists(info_file):
                result = {'images': generated_images}
                if info_data is not None:
                    result['info_data'] = info_data
                return True, result
            else:
                return False, "图片生成失败"

        except subprocess.TimeoutExpired:
            return False, "R脚本执行超时"
        except Exception as e:
            return False, str(e)