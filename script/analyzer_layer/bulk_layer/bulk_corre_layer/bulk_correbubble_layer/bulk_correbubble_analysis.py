# -*- coding: utf-8 -*-
"""
bulk相关性气泡图 R模式分析脚本 - Python接口层
此文件不包含任何R代码，只负责：
1. 数据准备和处理
2. 参数传递到R环境
3. 调用R脚本中的函数

R代码逻辑全部放在 bulk_correbubble_r.R 中
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path
from typing import Optional, List, Dict, Any

# 从统一R接口获取R环境
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from script.utils_layer.import_config import importr as _importr


class BulkCorreBubbleAnalysis:
    """bulk相关性气泡图 R模式分析类 - Python接口层，不含R代码"""
    
    # R交互调试日志（累积所有问题）
    _r_debug_log: List[Dict[str, Any]] = []
    
    # R脚本路径
    R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_correbubble_r.R")
    
    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.pandas2ri = None
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self._r_script_loaded = False
        self._r_packages_loaded = False
        self._init_r_environment()
    
    def _init_r_environment(self):
        """初始化R环境"""
        if self.r_interface.is_r_available():
            self.robjects = self.r_interface.get_robjects()
            self.pandas2ri = self.r_interface.get_pandas2ri()
        else:
            self._reinit_r_environment()
    
    def _reinit_r_environment(self):
        """重新初始化R环境"""
        saved_path = self.r_interface._load_saved_r_path()
        if saved_path:
            success = self.r_interface.set_r_path(saved_path)
            if success:
                self.robjects = self.r_interface.get_robjects()
                self.pandas2ri = self.r_interface.get_pandas2ri()

    def _log_r_debug(self, operation: str, error: Exception, context: Dict[str, Any] = None):
        """记录R交互调试信息"""
        import datetime
        debug_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }
        self._r_debug_log.append(debug_entry)
        print(f"[R_DEBUG:{operation}] {type(error).__name__}: {error}", file=sys.stderr)

    @classmethod
    def get_r_debug_log(cls) -> List[Dict[str, Any]]:
        """获取R交互调试日志"""
        return cls._r_debug_log

    @classmethod
    def clear_r_debug_log(cls):
        """清空R交互调试日志"""
        cls._r_debug_log.clear()

    def is_available(self) -> bool:
        """检查R环境是否可用"""
        if self.robjects is not None:
            return True
        self._reinit_r_environment()
        return self.robjects is not None
    
    def get_r_version(self) -> str:
        """获取R版本信息"""
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

    def set_adata(self, adata):
        """设置当前adata对象"""
        self.adata = adata

    def set_dataset_name(self, name):
        """设置数据集名称"""
        self.dataset_name = name

    def set_dataset_output_dir(self, output_dir):
        """设置数据集输出目录"""
        self.dataset_output_dir = output_dir

    def get_dataset_name(self):
        """获取数据集名称"""
        return self.dataset_name

    def get_adata_shape(self):
        """获取数据维度"""
        if self.adata is None:
            return 0, 0
        return self.adata.shape

    def get_gene_names(self):
        """获取所有基因名称"""
        if self.adata is None:
            return []
        return list(self.adata.var_names)

    def get_gene_exists(self, gene_name):
        """检查基因是否存在于数据集中"""
        if self.adata is None:
            return False
        return gene_name in self.adata.var_names

    def _load_r_script(self):
        """检查R脚本是否存在"""
        if self._r_script_loaded:
            return True
        
        if not os.path.exists(self.R_SCRIPT_PATH):
            self._log_r_debug("load_r_script", 
                             FileNotFoundError(f"R脚本不存在: {self.R_SCRIPT_PATH}"),
                             {"script_path": self.R_SCRIPT_PATH})
            return False
        
        self._r_script_loaded = True
        print(f"[R脚本检查] 脚本存在: {self.R_SCRIPT_PATH}")
        return True

    def _load_r_packages(self):
        """预加载R包"""
        if getattr(self, '_r_packages_loaded', False):
            return True
        
        if _importr is None:
            return False
        
        try:
            _importr('ggplot2')
            _importr('ggcorrplot2')
            _importr('psych')
            self._r_packages_loaded = True
            print("[R包加载] ggplot2, ggcorrplot2, psych 已通过importr加载")
            return True
        except Exception as e:
            # 如果ggcorrplot2不可用，尝试ggcorrplot
            try:
                _importr('ggplot2')
                _importr('ggcorrplot')
                _importr('psych')
                self._r_packages_loaded = True
                print("[R包加载] ggplot2, ggcorrplot, psych 已通过importr加载")
                return True
            except Exception as e2:
                self._log_r_debug("load_r_packages", e2, {"importr": str(_importr)})
                return False

    def prepare_correlation_data(self, gene_list: List[str]):
        """
        准备相关性分析数据
        
        Parameters:
        -----------
        gene_list : list
            基因名称列表
            
        Returns:
        --------
        pd.DataFrame or None
        """
        if self.adata is None:
            return None
            
        gene_list = [g.strip() for g in gene_list if g.strip()]
        if len(gene_list) < 2:
            return None
            
        # 检查基因是否存在
        valid_genes = []
        for gene in gene_list:
            if gene in self.adata.var_names:
                valid_genes.append(gene)
            else:
                print(f"[警告] 基因 {gene} 不存在于数据集中")
                
        if len(valid_genes) < 2:
            return None
            
        # 提取基因表达矩阵
        expr_matrix = self.adata[:, valid_genes].X
        if hasattr(expr_matrix, 'toarray'):
            expr_matrix = expr_matrix.toarray()
        expr_data = pd.DataFrame(expr_matrix, columns=valid_genes)
        
        return expr_data

    def draw_correlation_bubble_r(self, 
                                   gene_list: List[str],
                                   output_path: str = None,
                                   title: str = "Gene Correlation",
                                   title_size: int = 14,
                                   axis_text_size: int = 10,
                                   width_ratio: float = 1.0,
                                   height_ratio: float = 1.0,
                                   show_sig: bool = True,
                                   anno_size: float = 4.5,
                                   legend_key_width: float = 0.5,
                                   legend_key_height: float = 0.5,
                                   base_size: float = 8.0,
                                   **kwargs) -> str:
        """
        使用R绘制相关性椭圆气泡图（参考ggcorrplot2风格） - Python接口
        
        Parameters:
        -----------
        gene_list : list
            基因名称列表
        output_path : str
            输出图片路径
        title : str
            图表标题
        title_size : int
            标题字体大小
        axis_text_size : int
            坐标轴文字大小（基因名）
        width_ratio : float
            宽度比例 (0-1)
        height_ratio : float
            高度比例 (0-1)
        show_sig : bool
            是否显示显著性星号
        anno_size : float
            注释大小/pch.cex
        legend_key_width : float
            图例键宽度
        legend_key_height : float
            图例键高度
        base_size : float
            基础尺寸（宽高会乘以此值）
            
        Returns:
        --------
        str : 生成的图片路径
        """
        if not self.robjects:
            raise RuntimeError("R环境不可用")
        
        if not self._load_r_packages():
            raise RuntimeError("R包加载失败，请检查R环境")
        
        if not self._load_r_script():
            raise RuntimeError("R脚本加载失败，请检查R脚本路径")
        
        # 准备数据
        expr_data = self.prepare_correlation_data(gene_list)
        if expr_data is None:
            raise RuntimeError("数据准备失败，请检查基因列表")
        
        try:
            from rpy2.robjects import pandas2ri, StrVector, BoolVector, FloatVector, IntVector
            from rpy2.robjects.conversion import localconverter
            
            # 数据预处理：删除含NA的行
            original_shape = expr_data.shape
            expr_data = expr_data.dropna()
            cleaned_shape = expr_data.shape
            
            if original_shape[0] != cleaned_shape[0]:
                print(f"[R数据预处理] 删除了 {original_shape[0] - cleaned_shape[0]} 行含NA的样本")
            
            if expr_data.empty:
                raise RuntimeError("数据清洗后为空")
            
            # 计算实际宽高
            actual_width = base_size * width_ratio
            actual_height = base_size * height_ratio
            
            # 将数据传递到R环境（变量名exprSet与参考代码一致）
            with localconverter(pandas2ri.converter):
                self.robjects.globalenv['exprSet'] = expr_data
            
            # 将所有参数传递到R环境
            self.robjects.globalenv['plot_title'] = StrVector([title])
            self.robjects.globalenv['title_size'] = IntVector([title_size])
            self.robjects.globalenv['axis_text_size'] = IntVector([axis_text_size])
            self.robjects.globalenv['width_ratio'] = FloatVector([width_ratio])
            self.robjects.globalenv['height_ratio'] = FloatVector([height_ratio])
            self.robjects.globalenv['show_sig'] = BoolVector([show_sig])
            self.robjects.globalenv['anno_size'] = FloatVector([anno_size])
            self.robjects.globalenv['legend_key_width'] = FloatVector([legend_key_width])
            self.robjects.globalenv['legend_key_height'] = FloatVector([legend_key_height])
            self.robjects.globalenv['plot_width'] = FloatVector([actual_width])
            self.robjects.globalenv['plot_height'] = FloatVector([actual_height])
            self.robjects.globalenv['output_path'] = StrVector([output_path if output_path else ''])
            
        except Exception as e:
            self._log_r_debug("set_globalenv", e)
            raise RuntimeError(f"参数传递到R环境失败: {str(e)}")
        
        # 调用R脚本中的绘图逻辑
        try:
            with open(self.R_SCRIPT_PATH, 'r', encoding='utf-8') as f:
                r_script_lines = f.readlines()
            
            start_marker = "# --- FUNCTION_BODY_START ---"
            end_marker = "# --- FUNCTION_BODY_END ---"
            
            start_idx = None
            end_idx = None
            
            for i, line in enumerate(r_script_lines):
                if start_marker in line:
                    start_idx = i + 1
                if end_marker in line:
                    end_idx = i
            
            if start_idx is None or end_idx is None:
                raise RuntimeError(f"未找到标记行，请确保R脚本中包含:\n{start_marker}\n{end_marker}")
            
            if start_idx >= end_idx:
                raise RuntimeError("标记行顺序错误")
            
            r_code_body = ''.join(r_script_lines[start_idx:end_idx]).strip()
            
            if not r_code_body:
                raise RuntimeError("提取的代码段为空")
            
            self.robjects.r(r_code_body)
            return output_path if output_path else None
            
        except Exception as e:
            self._log_r_debug("execute_r_code", e, {"script_path": self.R_SCRIPT_PATH})
            raise RuntimeError(f"R绘图代码执行失败: {str(e)}")


# 单例模式
_instance = None

def get_bulk_correbubble_analysis() -> BulkCorreBubbleAnalysis:
    """获取bulk相关性气泡图分析单例"""
    global _instance
    if _instance is None:
        _instance = BulkCorreBubbleAnalysis()
    return _instance
