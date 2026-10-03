# -*- coding: utf-8 -*-
"""
R版本差异分析 Python接口层
参考hdWGCNA模式，通过rpy2调用R脚本进行差异表达分析

此文件不包含任何R代码，只负责：
1. 数据准备和处理
2. 参数传递到R环境
3. 调用R脚本中的分析代码
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path, tempfile, shutil
from typing import Optional, List, Dict, Any

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from script.utils_layer.import_config import importr as _importr


class RDiffAnalysis:
    """R版本差异分析 Python接口层 - 不含R代码"""

    R_SCRIPT_PATH = get_r_script_path(__file__, "r_diff_analysis.R")

    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.seurat_path = None
        self.output_dir = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self._r_script_loaded = False
        self._r_packages_loaded = False
        self.diff_gene_df = None
        self._analysis_completed = False
        self._metadata_cache = {}
        self._external_metadata_columns = []
        self._external_metadata_values = {}
        self._progress_callback = None
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

    def set_seurat_path(self, path):
        """设置Seurat对象路径（rds文件）"""
        self.seurat_path = path

    def set_dataset_name(self, name):
        """设置数据集名称"""
        self.dataset_name = name

    def set_dataset_output_dir(self, output_dir):
        """设置数据集输出目录"""
        from script.utils_layer.import_config import OUT_BASE
        diff_output = os.path.join(OUT_BASE, "diff")
        os.makedirs(diff_output, exist_ok=True)
        self.dataset_output_dir = diff_output

    def set_external_metadata(self, columns: list, values: dict):
        """设置外部缓存的元数据"""
        self._external_metadata_columns = columns
        self._external_metadata_values = values

    def set_progress_callback(self, callback):
        """设置进度回调函数，用于输出R执行日志到UI"""
        self._progress_callback = callback

    def get_seurat_metadata_columns(self) -> list:
        """获取Seurat对象的元数据列（优先使用外部缓存）"""
        if self._external_metadata_columns:
            return self._external_metadata_columns
        
        if not self.robjects or not self.seurat_path:
            return []
        
        cache_key = ('columns', self.seurat_path)
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]
        
        try:
            from rpy2.robjects import StrVector
            
            r_path = self.seurat_path.replace('\\', '/')
            self.robjects.globalenv['seurat_path'] = StrVector([r_path])
            
            cols = self.robjects.r('''
                seurat_obj <- readRDS(seurat_path)
                colnames(seurat_obj@meta.data)
            ''')
            result = [str(x) for x in cols]
            self._metadata_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"[获取元数据列失败] {e}")
            return []

    def get_seurat_column_values(self, column_name: str) -> list:
        """获取指定列的唯一值（优先使用外部缓存）"""
        if self._external_metadata_values and column_name in self._external_metadata_values:
            return self._external_metadata_values[column_name]
        
        if not self.robjects or not self.seurat_path:
            return []
        
        cache_key = (self.seurat_path, column_name)
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]
        
        try:
            from rpy2.robjects import StrVector
            
            r_path = self.seurat_path.replace('\\', '/')
            self.robjects.globalenv['seurat_path'] = StrVector([r_path])
            self.robjects.globalenv['column_name'] = StrVector([column_name])
            
            values = self.robjects.r('''
                seurat_obj <- readRDS(seurat_path)
                unique(as.character(seurat_obj@meta.data[[column_name]]))
            ''')
            result = [str(x) for x in values]
            self._metadata_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"[获取列值失败] {e}")
            return []

    def _load_r_packages(self):
        """加载R包"""
        if self._r_packages_loaded:
            return True
        if _importr is None:
            return False
        try:
            _importr('Seurat')
            _importr('SeuratObject')
            _importr('dplyr')
            _importr('openxlsx')
            _importr('ggplot2')
            self._r_packages_loaded = True
            print("[R包加载] Seurat, SeuratObject, dplyr, openxlsx, ggplot2 已加载")
            return True
        except Exception as e:
            print(f"[R包加载失败] {e}")
            return False

    def _read_stage_code(self, stage: str) -> str:
        """读取R脚本中的指定阶段代码"""
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

    def run_diff_analysis(self, group_col: str, group1_items: list, group2_items: list,
                          min_cells: int = 3, min_expr: int = 0,
                          pval_threshold: float = 0.05, logfc_threshold: float = 0.25,
                          pct_threshold: float = 0.1,
                          filter_enabled: bool = False, filter_col: str = "", filter_groups: list = None,
                          filter_col2: str = "", filter_groups2: list = None):
        """执行R差异分析
        
        Args:
            group_col: 分组列名
            group1_items: 组别1的项目列表
            group2_items: 组别2的项目列表
            min_cells: 最小表达细胞数
            min_expr: 最小表达量
            pval_threshold: p值阈值
            logfc_threshold: logFC阈值
            pct_threshold: 表达百分比阈值
            filter_enabled: 是否启用筛选
            filter_col: 筛选列1
            filter_groups: 筛选值1列表
            filter_col2: 筛选列2
            filter_groups2: 筛选值2列表
        """
        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if not self._load_r_packages():
            raise RuntimeError("R包加载失败")

        if self.seurat_path is None:
            raise RuntimeError("请先加载Seurat对象（rds文件）")

        if self.dataset_output_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="r_diff_")
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector, FloatVector, BoolVector

            log_file = os.path.join(output_dir, "r_diff_progress.log")
            if os.path.exists(log_file):
                os.remove(log_file)

            self.robjects.globalenv['log_file'] = StrVector([log_file.replace('\\', '/')])
            self.robjects.r('sink(log_file, split = TRUE)')

            self.robjects.globalenv['seurat_path'] = StrVector([self.seurat_path.replace('\\', '/')])
            self.robjects.globalenv['output_dir'] = StrVector([output_dir.replace('\\', '/')])
            self.robjects.globalenv['group_col'] = StrVector([group_col])
            self.robjects.globalenv['group1_items'] = StrVector(group1_items)
            self.robjects.globalenv['group2_items'] = StrVector(group2_items)
            self.robjects.globalenv['min_cells'] = IntVector([int(min_cells)])
            self.robjects.globalenv['min_expr'] = IntVector([int(min_expr)])
            self.robjects.globalenv['pval_threshold'] = FloatVector([pval_threshold])
            self.robjects.globalenv['logfc_threshold'] = FloatVector([logfc_threshold])
            self.robjects.globalenv['pct_threshold'] = FloatVector([pct_threshold])
            self.robjects.globalenv['filter_enabled'] = BoolVector([filter_enabled])

            if filter_enabled and filter_col:
                self.robjects.globalenv['filter_col'] = StrVector([filter_col])
                if filter_groups and len(filter_groups) > 0:
                    self.robjects.globalenv['filter_groups'] = StrVector(filter_groups)
            else:
                if 'filter_col' in self.robjects.globalenv:
                    del self.robjects.globalenv['filter_col']
                if 'filter_groups' in self.robjects.globalenv:
                    del self.robjects.globalenv['filter_groups']

            if filter_enabled and filter_col2:
                self.robjects.globalenv['filter_col2'] = StrVector([filter_col2])
                if filter_groups2 and len(filter_groups2) > 0:
                    self.robjects.globalenv['filter_groups2'] = StrVector(filter_groups2)
            else:
                if 'filter_col2' in self.robjects.globalenv:
                    del self.robjects.globalenv['filter_col2']
                if 'filter_groups2' in self.robjects.globalenv:
                    del self.robjects.globalenv['filter_groups2']

            r_code = self._read_stage_code("DIFF_ANALYSIS")
            result = self.robjects.r(r_code)

            self.robjects.r('sink()')

            log_file = os.path.join(output_dir, "r_diff_progress.log")
            if self._progress_callback and os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.strip():
                            self._progress_callback(line.strip())

            self._analysis_completed = True

            result_file = os.path.join(output_dir, "r_diff_results.csv")
            if os.path.exists(result_file):
                self.diff_gene_df = pd.read_csv(result_file)
                print(f"[R差异分析] 结果已读取，共 {len(self.diff_gene_df)} 个差异基因")
            else:
                raise RuntimeError("R脚本执行完成但未生成结果文件")

            return self.diff_gene_df

        except Exception as e:
            try:
                self.robjects.r('sink()')
            except:
                pass
            print(f"[R差异分析失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"R差异分析失败: {str(e)}")

    def get_results(self):
        """获取差异分析结果"""
        return self.diff_gene_df

    def get_volcano_path(self):
        """获取火山图路径"""
        if self.dataset_output_dir:
            path = os.path.join(self.dataset_output_dir, "r_diff_volcano.png")
        elif hasattr(self, '_temp_dir'):
            path = os.path.join(self._temp_dir, "r_diff_volcano.png")
        else:
            return None
        return path if os.path.exists(path) else None

    def export_csv(self, save_path):
        """导出结果为CSV"""
        if self.diff_gene_df is None or len(self.diff_gene_df) == 0:
            raise ValueError("没有可导出的结果")

        if not save_path.endswith('.csv'):
            save_path += '.csv'

        self.diff_gene_df.to_csv(save_path, index=False, encoding='utf-8-sig')

    def export_png(self, save_path):
        """导出火山图为PNG"""
        volcano_path = self.get_volcano_path()
        if not volcano_path:
            raise ValueError("未找到火山图文件")

        if not save_path.endswith('.png'):
            save_path += '.png'

        shutil.copy2(volcano_path, save_path)
