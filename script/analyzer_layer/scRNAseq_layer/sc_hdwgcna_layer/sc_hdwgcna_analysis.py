# -*- coding: utf-8 -*-
"""
sc_hdwgcna分析 Python接口层
此文件不包含任何R代码，只负责：
1. 数据准备和处理
2. 参数传递到R环境
3. 调用R脚本中的阶段代码
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path, tempfile, shutil
from typing import Optional, List, Dict, Any
from PIL import Image

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from script.utils_layer.import_config import importr as _importr


class ScHdWgcnaAnalysis:
    """sc_hdwgcna分析 Python接口层 - 不含R代码"""

    _r_debug_log: List[Dict[str, Any]] = []

    R_SCRIPT_PATH = get_r_script_path(__file__, "sc_hdwgcna_analysis.R")
    R_UTILS_SCRIPT_PATH = get_r_script_path(__file__, "sc_hdwgcna_utils.R")

    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.seurat_path = None
        self.output_dir = None
        self._utils_sourced = False
        self.dataset_name = None
        self.dataset_output_dir = None
        self._r_script_loaded = False
        self._r_packages_loaded = False
        self._stage1_completed = False
        self._stage2_completed = False
        self._stage3_completed = False
        self._stage4_completed = False
        self._stage5_completed = False
        self._stage6_completed = False
        self._stage7_completed = False
        self._stage8_completed = False
        self._stage9_completed = False
        self._stage10_completed = False
        self._init_r_environment()

    def _init_r_environment(self):
        if self.r_interface.is_r_available():
            self.robjects = self.r_interface.get_robjects()
            self.pandas2ri = self.r_interface.get_pandas2ri()
        else:
            self._reinit_r_environment()

    def _reinit_r_environment(self):
        saved_path = self.r_interface._load_saved_r_path()
        if saved_path:
            success = self.r_interface.set_r_path(saved_path)
            if success:
                self.robjects = self.r_interface.get_robjects()
                self.pandas2ri = self.r_interface.get_pandas2ri()

    def is_available(self) -> bool:
        if self.robjects is not None:
            return True
        self._reinit_r_environment()
        return self.robjects is not None

    def get_r_version(self) -> str:
        if self.robjects:
            try:
                return str(self.robjects.r('R.version.string')[0])
            except:
                pass
        self._reinit_r_environment()
        if self.robjects:
            try:
                return str(self.robjects.r('R.version.string')[0])
            except:
                pass
        return "R环境不可用"

    def set_seurat_path(self, path):
        self.seurat_path = path

    def set_dataset_name(self, name):
        self.dataset_name = name

    def set_dataset_output_dir(self, output_dir):
        from script.utils_layer.import_config import OUT_BASE
        hdwgcna_output = os.path.join(OUT_BASE, "hdWGCNA")
        os.makedirs(hdwgcna_output, exist_ok=True)
        self.dataset_output_dir = hdwgcna_output

    def get_dataset_name(self):
        return self.dataset_name

    def _load_r_script(self):
        if self._r_script_loaded:
            return True
        if not os.path.exists(self.R_SCRIPT_PATH):
            print(f"[R脚本检查] 脚本不存在: {self.R_SCRIPT_PATH}")
            return False
        self._r_script_loaded = True
        print(f"[R脚本检查] 脚本存在: {self.R_SCRIPT_PATH}")
        return True

    def _load_r_packages(self):
        if self._r_packages_loaded:
            return True
        if _importr is None:
            return False
        try:
            _importr('WGCNA')
            _importr('hdWGCNA')
            _importr('Seurat')
            _importr('SeuratObject')
            _importr('dplyr')
            _importr('ggplot2')
            _importr('gridExtra')
            _importr('openxlsx')
            _importr('harmony')
            _importr('patchwork')
            _importr('enrichR')
            self._r_packages_loaded = True
            print("[R包加载] WGCNA, hdWGCNA, Seurat, SeuratObject, dplyr, ggplot2, gridExtra, openxlsx, harmony, patchwork, enrichR 已通过importr加载")
            return True
        except Exception as e:
            print(f"[R包加载失败] {e}")
            return False

    def _read_stage_code(self, stage: str) -> str:
        with open(self.R_SCRIPT_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        start_marker = f"# --- {stage}_BODY_START ---"
        end_marker = f"# --- {stage}_BODY_END ---"

        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if start_marker in line:
                start_idx = i + 1
            if end_marker in line:
                end_idx = i

        if start_idx is None or end_idx is None:
            raise RuntimeError(f"未找到标记行: {start_marker} / {end_marker}")

        if start_idx >= end_idx:
            raise RuntimeError(f"标记行顺序错误: {stage}")

        code = ''.join(lines[start_idx:end_idx]).strip()
        if not code:
            raise RuntimeError(f"提取的代码段为空: {stage}")
        return code

    def _source_utils_once(self):
        if not self._utils_sourced and self.robjects:
            self.robjects.r.source(self.R_UTILS_SCRIPT_PATH)
            self._utils_sourced = True

    def get_seurat_metadata_columns(self) -> list:
        if not self.robjects or not self.seurat_path:
            return []
        try:
            from rpy2.robjects import StrVector
            if not hasattr(self, '_metadata_cache'):
                self._metadata_cache = {}
            
            cache_key = ('columns', self.seurat_path)
            if cache_key in self._metadata_cache:
                return self._metadata_cache[cache_key]
            
            self._source_utils_once()
            r_path = self.seurat_path.replace('\\', '/')
            self.robjects.globalenv['seurat_path'] = StrVector([r_path])
            cols = self.robjects.r('get_seurat_metadata_columns(seurat_path)')
            result = [str(x) for x in cols]
            
            self._metadata_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"[获取元数据列失败] {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_seurat_cell_types(self, analyze_group: str = "Celltype (major-lineage)") -> list:
        return self.get_seurat_column_values(analyze_group)

    def get_seurat_info(self) -> str:
        if not self.robjects or not self.seurat_path:
            return ""
        try:
            from rpy2.robjects import StrVector
            if not hasattr(self, '_metadata_cache'):
                self._metadata_cache = {}
            
            cache_key = ('info', self.seurat_path)
            if cache_key in self._metadata_cache:
                return self._metadata_cache[cache_key]
            
            self._source_utils_once()
            r_path = self.seurat_path.replace('\\', '/')
            self.robjects.globalenv['seurat_path'] = StrVector([r_path])
            info = self.robjects.r('get_seurat_info(seurat_path)')
            result = '\n'.join([str(x) for x in info])
            
            self._metadata_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"[获取Seurat信息失败] {e}")
            import traceback
            traceback.print_exc()
            return ""

    def get_seurat_column_values(self, column_name: str) -> list:
        if not self.robjects or not self.seurat_path:
            return []
        try:
            from rpy2.robjects import StrVector
            if not hasattr(self, '_metadata_cache'):
                self._metadata_cache = {}
            
            cache_key = (self.seurat_path, column_name)
            if cache_key in self._metadata_cache:
                return self._metadata_cache[cache_key]
            
            self._source_utils_once()
            r_path = self.seurat_path.replace('\\', '/')
            self.robjects.globalenv['seurat_path'] = StrVector([r_path])
            self.robjects.globalenv['column_name'] = StrVector([column_name])
            values = self.robjects.r('get_seurat_column_values(seurat_path, column_name)')
            try:
                if values is None or len(values) == 0:
                    result = []
                else:
                    result = [str(x) for x in values]
            except (TypeError, AttributeError):
                result = []
            
            self._metadata_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"[获取列值失败] {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_stage1_result(self) -> str:
        if not self.robjects:
            return ""
        try:
            if self.robjects.r('exists("sc_hdwgcna_stage1_result")')[0]:
                result = self.robjects.r('sc_hdwgcna_stage1_result')
                return str(result[0]) if len(result) > 0 else ""
        except Exception as e:
            print(f"[获取阶段一结果失败] {e}")
        return ""

    def run_stage1_load_seurat(self, seurat_path: str = None,
                              analyze_group: str = "Celltype (major-lineage)",
                              sample_group: str = "Sample",
                              target_cell_type: str = None,
                              gene_select_mode: str = "fraction",
                              fraction_value: float = 0.05,
                              variable_gene_count: int = 3000,
                              custom_gene_list_path: str = None,
                              recluster: bool = True,
                              dims: int = 30,
                              filter_enabled: bool = False,
                              filter_col: str = "",
                              filter_groups: list = None) -> bool:
        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if not self._load_r_packages():
            raise RuntimeError("R包加载失败")

        if not self._load_r_script():
            raise RuntimeError("R脚本加载失败")

        if seurat_path:
            self.seurat_path = seurat_path

        if self.seurat_path is None:
            raise RuntimeError("请提供Seurat对象路径")

        if self.dataset_output_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="sc_hdwgcna_")
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector, FloatVector

            self.robjects.globalenv['seurat_path'] = StrVector([self.seurat_path])
            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['analyze_group'] = StrVector([analyze_group])
            self.robjects.globalenv['sample_group'] = StrVector([sample_group])
            self.robjects.globalenv['gene_select_mode'] = StrVector([gene_select_mode])
            self.robjects.globalenv['fraction_value'] = FloatVector([fraction_value])
            self.robjects.globalenv['variable_gene_count'] = IntVector([int(variable_gene_count)])
            
            if custom_gene_list_path:
                self.robjects.globalenv['custom_gene_list_path'] = StrVector([custom_gene_list_path])
            elif 'custom_gene_list_path' in self.robjects.globalenv:
                del self.robjects.globalenv['custom_gene_list_path']
            
            self.robjects.globalenv['recluster'] = self.robjects.r.c(recluster)
            self.robjects.globalenv['dims'] = IntVector([int(dims)])

            if target_cell_type and target_cell_type != "" and target_cell_type != "全部":
                self.robjects.globalenv['target_cell_type'] = StrVector([target_cell_type])
            elif 'target_cell_type' in self.robjects.globalenv:
                del self.robjects.globalenv['target_cell_type']

            self.robjects.globalenv['filter_enabled'] = self.robjects.r.c(filter_enabled)
            if filter_enabled and filter_col:
                self.robjects.globalenv['filter_col'] = StrVector([filter_col])
                if filter_groups and len(filter_groups) > 0:
                    self.robjects.globalenv['filter_groups'] = StrVector(filter_groups)
            elif 'filter_col' in self.robjects.globalenv:
                del self.robjects.globalenv['filter_col']
            elif 'filter_groups' in self.robjects.globalenv:
                del self.robjects.globalenv['filter_groups']

            r_code = self._read_stage_code("STAGE1")
            self.robjects.r(r_code)

            self._stage1_completed = True
            self._stage2_completed = False
            self._stage3_completed = False
            self._stage4_completed = False
            self._stage5_completed = False
            self._stage6_completed = False
            self._stage7_completed = False
            self._stage8_completed = False
            self._stage9_completed = False
            self._stage10_completed = False
            print(f"[阶段一] 加载Seurat对象完成")
            return True

        except Exception as e:
            print(f"[阶段一失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段一R代码执行失败: {str(e)}")

    def get_stage1_umap_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "umap_plot.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "umap_plot.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def run_stage2_metacell(self,
                          k: int = 25,
                          max_shared: int = 10,
                          min_cells: int = 80) -> bool:
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['k'] = IntVector([int(k)])
            self.robjects.globalenv['max_shared'] = IntVector([int(max_shared)])
            self.robjects.globalenv['min_cells'] = IntVector([int(min_cells)])
            self.robjects.globalenv['plot_width'] = IntVector([1200])
            self.robjects.globalenv['plot_height'] = IntVector([800])

            r_code = self._read_stage_code("STAGE2")
            self.robjects.r(r_code)

            self._stage2_completed = True
            print(f"[阶段二] SetupForWGCNA+Metacell构建完成")
            return True

        except Exception as e:
            print(f"[阶段二失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段二R代码执行失败: {str(e)}")

    def get_stage2_result(self) -> str:
        if not self.robjects:
            return ""
        try:
            if self.robjects.r('exists("sc_hdwgcna_stage2_result")')[0]:
                result = self.robjects.r('sc_hdwgcna_stage2_result')
                return str(result[0]) if len(result) > 0 else ""
        except Exception as e:
            print(f"[获取阶段二结果失败] {e}")
        return ""

    def run_stage3_soft_threshold(self,
                                network_type: str = "unsigned",
                                manual_power: int = None) -> str:
        if not self._stage2_completed:
            raise RuntimeError("请先运行阶段二")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['network_type'] = StrVector([network_type])
            self.robjects.globalenv['plot_width'] = IntVector([1200])
            self.robjects.globalenv['plot_height'] = IntVector([800])

            if manual_power is not None:
                self.robjects.globalenv['manual_power'] = IntVector([manual_power])

            r_code = self._read_stage_code("STAGE3")
            
            print("[阶段三] 开始执行R代码...")
            result = self.robjects.r(r_code)
            print("[阶段三] R代码执行完成")

            self._stage3_completed = True
            print(f"[阶段三] 表达矩阵设置+软阈值选择完成")

            try:
                power_estimate = int(self.robjects.r('sc_hdwgcna_power_estimate')[0])
                print(f"[阶段三] 推荐软阈值: {power_estimate}")
                return str(power_estimate)
            except Exception as e:
                print(f"[阶段三] 获取推荐软阈值失败: {e}")
                return None

        except Exception as e:
            print(f"[阶段三失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段三R代码执行失败: {str(e)}")

    def get_power_estimate(self) -> int:
        if not self.robjects:
            return None
        try:
            if self.robjects.r('exists("sc_hdwgcna_power_estimate")')[0]:
                return int(self.robjects.r('sc_hdwgcna_power_estimate')[0])
        except Exception as e:
            print(f"[获取推荐软阈值失败] {e}")
        return None

    def get_stage3_soft_threshold_plot_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "soft_threshold.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "soft_threshold.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def run_stage4_network_construction(self,
                                      soft_power: int = None,
                                      min_module_size: int = 30,
                                      merge_threshold: float = 0.25) -> bool:
        if not self._stage3_completed:
            raise RuntimeError("请先运行阶段三")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['plot_width'] = IntVector([1200])
            self.robjects.globalenv['plot_height'] = IntVector([800])

            if soft_power is not None:
                self.robjects.globalenv['soft_power'] = IntVector([soft_power])

            self.robjects.globalenv['min_module_size'] = IntVector([min_module_size])
            self.robjects.globalenv['merge_threshold'] = self.robjects.r.c(merge_threshold)

            r_code = self._read_stage_code("STAGE4")
            
            print("[阶段四] 开始执行R代码...")
            result = self.robjects.r(r_code)
            print("[阶段四] R代码执行完成")

            self._stage4_completed = True
            print(f"[阶段四] 网络构建完成")
            return True

        except Exception as e:
            print(f"[阶段四失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段四R代码执行失败: {str(e)}")

    def get_stage4_gene_dendro_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "gene_dendrogram.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "gene_dendrogram.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def run_stage5_module_visualization(self) -> bool:
        if not self._stage4_completed:
            raise RuntimeError("请先运行阶段四")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['plot_width'] = IntVector([1200])
            self.robjects.globalenv['plot_height'] = IntVector([800])

            r_code = self._read_stage_code("STAGE5")
            self.robjects.r(r_code)

            self._stage5_completed = True
            print(f"[阶段五] 模块可视化完成")
            return True

        except Exception as e:
            print(f"[阶段五失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段五R代码执行失败: {str(e)}")

    def get_stage5_kme_plot_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "kme_plot.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "kme_plot.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def run_stage6_hme_plots(self) -> bool:
        if not self._stage5_completed:
            raise RuntimeError("请先运行阶段五")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['plot_width'] = IntVector([1200])
            self.robjects.globalenv['plot_height'] = IntVector([800])

            r_code = self._read_stage_code("STAGE6")
            self.robjects.r(r_code)

            self._stage6_completed = True
            print(f"[阶段六] 模块特征图完成")
            return True

        except Exception as e:
            print(f"[阶段六失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段六R代码执行失败: {str(e)}")

    def get_stage6_hme_plot_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "module_feature_hmes.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "module_feature_hmes.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def run_stage7_correlogram_and_dotplot(self, trait_cols=None) -> bool:
        if not self._stage6_completed:
            raise RuntimeError("请先运行阶段六")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['plot_width'] = IntVector([1200])
            self.robjects.globalenv['plot_height'] = IntVector([800])

            if trait_cols and len(trait_cols) > 0:
                self.robjects.globalenv['trait_cols'] = StrVector(trait_cols)

            r_code = self._read_stage_code("STAGE7")
            self.robjects.r(r_code)

            self._stage7_completed = True
            print(f"[阶段七] 模块相关图完成")
            return True

        except Exception as e:
            print(f"[阶段七失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段七R代码执行失败: {str(e)}")

    def get_stage7_correlogram_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "module_correlogram.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "module_correlogram.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def get_stage7_dotplot_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "module_dotplot.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "module_dotplot.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def get_stage7_module_trait_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "module_trait_heatmap.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "module_trait_heatmap.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def run_stage8_module_umap(self) -> bool:
        if not self._stage7_completed:
            raise RuntimeError("请先运行阶段七")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['plot_width'] = IntVector([1200])
            self.robjects.globalenv['plot_height'] = IntVector([800])

            r_code = self._read_stage_code("STAGE8")
            self.robjects.r(r_code)

            self._stage8_completed = True
            print(f"[阶段八] ModuleUMAP完成")
            return True

        except Exception as e:
            print(f"[阶段八失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段八R代码执行失败: {str(e)}")

    def get_stage8_module_umap_path(self) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "module_umap.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "module_umap.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def run_stage9_go_kegg_enrichment(self, organism="hsa", selected_modules=None,
                                      go_padj_cutoff=0.05, kegg_padj_cutoff=0.05,
                                      go_top_n=15, kegg_top_n=15) -> bool:
        if not self._stage4_completed:
            raise RuntimeError("请先运行阶段四")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        output_dir = self.dataset_output_dir if self.dataset_output_dir else self._temp_dir

        try:
            from rpy2.robjects import StrVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['organism'] = StrVector([organism])
            self.robjects.globalenv['go_padj_cutoff'] = self.robjects.r.c(go_padj_cutoff)
            self.robjects.globalenv['kegg_padj_cutoff'] = self.robjects.r.c(kegg_padj_cutoff)
            self.robjects.globalenv['go_top_n'] = IntVector([go_top_n])
            self.robjects.globalenv['kegg_top_n'] = IntVector([kegg_top_n])

            if selected_modules and len(selected_modules) > 0:
                self.robjects.globalenv['selected_modules'] = StrVector(selected_modules)

            r_code = self._read_stage_code("STAGE9")
            self.robjects.r(r_code)

            self._stage9_completed = True
            print(f"[阶段九] GO和KEGG富集分析完成")
            return True

        except Exception as e:
            print(f"[阶段九失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段九R代码执行失败: {str(e)}")

    def get_stage9_go_bubble_path(self, module_name) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, f"GO_bubble_{module_name}.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, f"GO_bubble_{module_name}.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def get_stage9_go_bar_path(self, module_name) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, f"GO_bar_{module_name}.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, f"GO_bar_{module_name}.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def get_stage9_kegg_bar_path(self, module_name) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, f"KEGG_bar_{module_name}.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, f"KEGG_bar_{module_name}.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def get_stage9_kegg_bubble_path(self, module_name) -> str:
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, f"KEGG_bubble_{module_name}.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, f"KEGG_bubble_{module_name}.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def _get_output_dir(self) -> str:
        return self.dataset_output_dir if self.dataset_output_dir else self._temp_dir

    def _get_stage9_images(self, modules: List[str], image_type: str) -> List[str]:
        image_paths = []
        output_dir = self._get_output_dir()
        for mod in modules:
            if image_type == 'go_bubble':
                path = os.path.join(output_dir, f"GO_bubble_{mod}.png")
            elif image_type == 'go_bar':
                path = os.path.join(output_dir, f"GO_bar_{mod}.png")
            elif image_type == 'kegg_bar':
                path = os.path.join(output_dir, f"KEGG_bar_{mod}.png")
            elif image_type == 'kegg_bubble':
                path = os.path.join(output_dir, f"KEGG_bubble_{mod}.png")
            else:
                continue
            if os.path.exists(path):
                image_paths.append(path)
        return image_paths

    def _stitch_images(self, image_paths: List[str], max_cols: int = 3) -> str:
        if not image_paths:
            return None
        
        output_dir = self._get_output_dir()
        
        if len(image_paths) == 1:
            return image_paths[0]
        
        images = [Image.open(p) for p in image_paths]
        
        num_images = len(images)
        num_cols = min(num_images, max_cols)
        num_rows = (num_images + num_cols - 1) // num_cols
        
        max_width = max(img.width for img in images)
        max_height = max(img.height for img in images)
        
        padding = 20
        
        total_width = num_cols * max_width + (num_cols - 1) * padding
        total_height = num_rows * max_height + (num_rows - 1) * padding
        
        new_image = Image.new('RGB', (total_width, total_height), color=(255, 255, 255))
        
        for i, img in enumerate(images):
            row = i // num_cols
            col = i % num_cols
            
            x = col * (max_width + padding)
            y = row * (max_height + padding)
            
            paste_x = x + (max_width - img.width) // 2
            paste_y = y + (max_height - img.height) // 2
            
            new_image.paste(img, (paste_x, paste_y))
        
        base_name = os.path.basename(image_paths[0])
        combined_path = os.path.join(output_dir, f"combined_{base_name}")
        new_image.save(combined_path, 'PNG')
        
        for img in images:
            img.close()
        
        return combined_path

    def get_stage9_combined_image(self, modules: List[str], image_type: str) -> str:
        image_paths = self._get_stage9_images(modules, image_type)
        if not image_paths:
            return None
        return self._stitch_images(image_paths)

    def run_stage10_export_modules(self) -> bool:
        if not self._stage4_completed:
            raise RuntimeError("请先运行阶段四")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        output_dir = self.dataset_output_dir if self.dataset_output_dir else self._temp_dir

        try:
            from rpy2.robjects import StrVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])

            r_code = self._read_stage_code("STAGE10")
            self.robjects.r(r_code)

            self._stage10_completed = True
            print(f"[阶段十] 基因集合导出完成")
            return True

        except Exception as e:
            print(f"[阶段十失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段十R代码执行失败: {str(e)}")

    def get_stage10_export_path(self) -> str:
        return self.dataset_output_dir if self.dataset_output_dir else self._temp_dir

    def get_modules(self):
        if not self._stage4_completed or not self.robjects:
            print(f"[get_modules] 阶段四未完成或R环境不可用: stage4={self._stage4_completed}, robjects={self.robjects is not None}")
            return []

        try:
            result = self.robjects.r('''
                cat("=== 获取模块列表调试 ===\n")
                if (!exists("sc_hdwgcna_seurat_obj")) {
                    cat("错误: sc_hdwgcna_seurat_obj不存在\n")
                    list(modules=character(0), debug="obj_not_found")
                } else if (is.null(sc_hdwgcna_seurat_obj)) {
                    cat("错误: sc_hdwgcna_seurat_obj为空\n")
                    list(modules=character(0), debug="obj_null")
                } else {
                    tryCatch({
                        mods <- GetModules(sc_hdwgcna_seurat_obj, wgcna_name = "sc_hdwgcna_test")
                        cat("GetModules返回类型: ", class(mods), "\n")
                        cat("GetModules行数: ", nrow(mods), "\n")
                        if (!is.null(mods) && nrow(mods) > 0) {
                            cat("GetModules列名: ", paste(colnames(mods), collapse=", "), "\n")
                            if ("module" %in% colnames(mods)) {
                                unique_mods <- unique(as.character(mods$module))
                                cat("从GetModules获取的模块: ", paste(unique_mods, collapse=", "), "\n")
                                list(modules=unique_mods, debug="success_getmodules")
                            } else {
                                cat("module列不存在\n")
                                list(modules=character(0), debug="no_module_col")
                            }
                        } else {
                            cat("GetModules返回空\n")
                            list(modules=character(0), debug="getmodules_null")
                        }
                    }, error = function(e) {
                        cat("GetModules错误: ", e$message, "\n")
                        list(modules=character(0), debug=paste("getmodules_error:", e$message))
                    })
                }
            ''')
            if result is not None and hasattr(result, 'rx2'):
                modules_r = result.rx2('modules')
                module_list = [str(m) for m in modules_r]
                debug_info = str(result.rx2('debug')) if hasattr(result.rx2('debug'), '__iter__') else str(result.rx2('debug'))
                print(f"[get_modules] 获取到模块: {module_list}, 调试信息: {debug_info}")
                return module_list
            return []
        except Exception as e:
            print(f"[获取模块列表失败] {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_stage_status(self):
        return {
            'stage1': self._stage1_completed,
            'stage2': self._stage2_completed,
            'stage3': self._stage3_completed,
            'stage4': self._stage4_completed,
            'stage5': self._stage5_completed,
            'stage6': self._stage6_completed,
            'stage7': self._stage7_completed,
            'stage8': self._stage8_completed,
            'stage9': self._stage9_completed,
            'stage10': self._stage10_completed
        }


_analysis_instance = None


def get_sc_hdwgcna_analysis() -> ScHdWgcnaAnalysis:
    global _analysis_instance
    if _analysis_instance is None:
        _analysis_instance = ScHdWgcnaAnalysis()
    return _analysis_instance