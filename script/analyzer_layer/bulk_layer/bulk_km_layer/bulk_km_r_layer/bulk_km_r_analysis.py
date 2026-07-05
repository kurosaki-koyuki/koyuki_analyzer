# -*- coding: utf-8 -*-
"""
bulk KM曲线 R模式分析脚本 - Python接口层
此文件不包含任何R代码，只负责：
1. 数据准备和处理
2. 参数传递到R环境
3. 调用R脚本中的函数
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path
from typing import Optional, List, Dict, Any

# 从统一R接口获取R环境
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from script.utils_layer.import_config import importr as _importr


class BulkKmRAnalysis:
    """bulk KM曲线 R模式分析类 - Python接口层，不含R代码"""
    
    # R交互调试日志（累积所有问题）
    _r_debug_log: List[Dict[str, Any]] = []
    
    # R脚本路径
    R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_km_r.R")
    
    HIGH_COLORS = [
        '#e41a1c', '#ff7f00', '#f781bf', '#a65628', '#e6194b',
        '#ff0000', '#ff69b4', '#ffb6c1', '#ff6347', '#ff4500',
        '#dc143c', '#c71585', '#ff1493', '#ff7f50', '#ffa500'
    ]

    LOW_COLORS = [
        '#0000ff', '#377eb8', '#4daf4a', '#984ea3', '#56b4e9',
        '#00ced1', '#008080', '#40e0d0', '#87ceeb', '#6495ed',
        '#4682b4', '#5f9ea0', '#708090', '#2f4f4f', '#1e90ff'
    ]

    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.pandas2ri = None
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.current_km_fig_path = None
        self.filtered_df = None
        self._r_script_loaded = False
        self._init_r_environment()
    
    def _init_r_environment(self):
        """初始化R环境"""
        if self.r_interface.is_r_available():
            self.robjects = self.r_interface.get_robjects()
            self.pandas2ri = self.r_interface.get_pandas2ri()
        else:
            # R不可用时，尝试重新加载R配置并初始化
            self._reinit_r_environment()
    
    def _reinit_r_environment(self):
        """重新初始化R环境（从配置文件加载R路径）"""
        # 先尝试从配置文件加载R路径
        saved_path = self.r_interface._load_saved_r_path()
        if saved_path:
            # 设置R路径
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
        # 打印到stderr以便实时查看
        print(f"[R_DEBUG:{operation}] {type(error).__name__}: {error}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    @classmethod
    def get_r_debug_log(cls) -> List[Dict[str, Any]]:
        """获取R交互调试日志"""
        return cls._r_debug_log

    @classmethod
    def clear_r_debug_log(cls):
        """清空R交互调试日志"""
        cls._r_debug_log.clear()

    @classmethod
    def print_r_debug_summary(cls):
        """打印R交互调试日志摘要"""
        if not cls._r_debug_log:
            print("[R_DEBUG] 没有记录到任何R相关错误")
            return
        print(f"[R_DEBUG] 共记录 {len(cls._r_debug_log)} 个R相关错误:")
        for i, entry in enumerate(cls._r_debug_log, 1):
            print(f"\n--- 错误 {i} ---")
            print(f"  时间: {entry['timestamp']}")
            print(f"  操作: {entry['operation']}")
            print(f"  类型: {entry['error_type']}")
            print(f"  消息: {entry['error_message']}")
            if entry['context']:
                print(f"  上下文: {entry['context']}")
    
    def is_available(self) -> bool:
        """检查R环境是否可用"""
        if self.robjects is not None:
            return True
        # 尝试重新初始化
        self._reinit_r_environment()
        return self.robjects is not None
    
    def get_r_version(self) -> str:
        """获取R版本信息"""
        if self.robjects:
            try:
                return str(self.robjects.r('R.version.string')[0])
            except:
                pass
        # 尝试重新初始化
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

    def get_obs_columns(self):
        """获取obs列名列表（排除生存信息列）"""
        if self.adata is None:
            return []
        survival_cols = ['time', 'time (month)', 'state']
        valid_cols = []
        for col in self.adata.obs.columns:
            if col.strip() in survival_cols:
                continue
            valid_cols.append(col)
        return valid_cols

    def get_obs_unique_values(self, col_name):
        """获取某obs列的唯一值列表"""
        if self.adata is None or col_name not in self.adata.obs.columns:
            return []
        unique_vals = self.adata.obs[col_name].unique()
        return sorted([str(v) for v in unique_vals if pd.notna(v)])

    def get_gene_exists(self, gene_name):
        """检查基因是否存在于数据集中"""
        if self.adata is None:
            return False
        return gene_name in self.adata.var_names

    def prepare_km_data(self, gene_name, time_unit='days'):
        """准备KM分析数据"""
        adata = self.adata
        gene_name = gene_name.strip()

        if gene_name not in adata.var_names:
            return None

        gene_expr = adata[:, gene_name].X.flatten()

        if time_unit == 'days':
            time_col = 'time'
        else:
            time_col = 'time (month)'

        if time_col not in adata.obs.columns:
            return None

        time_data = adata.obs[time_col].values
        state_data = adata.obs['state'].values

        df = pd.DataFrame({
            'time': time_data,
            'state': state_data,
            'expression': gene_expr
        }, index=adata.obs.index)

        df['time'] = pd.to_numeric(df['time'], errors='coerce')
        df['state'] = pd.to_numeric(df['state'], errors='coerce')
        df['expression'] = pd.to_numeric(df['expression'], errors='coerce')

        df = df[df['time'].notna() & df['state'].notna() & df['expression'].notna()]
        df = df[df['time'] > 0]

        if len(df) < 10:
            return None

        return df

    def filter_data(self, df, filter1_col=None, filter1_groups=None,
                    filter2_col=None, filter2_groups=None):
        """根据筛选条件过滤数据"""
        if df is None:
            return None

        filtered = df.copy()

        if filter1_col and filter1_groups and filter1_col in self.adata.obs.columns:
            filtered[filter1_col] = self.adata.obs.loc[filtered.index, filter1_col].values
            filtered = filtered[filtered[filter1_col].astype(str).isin(filter1_groups)]

        if filter2_col and filter2_groups and filter2_col in self.adata.obs.columns:
            filtered[filter2_col] = self.adata.obs.loc[filtered.index, filter2_col].values
            filtered = filtered[filtered[filter2_col].astype(str).isin(filter2_groups)]

        if len(filtered) < 10:
            return None

        return filtered

    def split_groups_by_clinical(self, df, clinical_col, selected_groups=None):
        """根据临床分类列分组数据"""
        if df is None:
            return []

        df = df.copy()
        df[clinical_col] = self.adata.obs.loc[df.index, clinical_col].values
        
        # 删除临床列中的NA值，防止后续分组时出现长度不一致问题
        df = df.dropna(subset=[clinical_col])

        if selected_groups:
            df = df[df[clinical_col].astype(str).isin(selected_groups)]
            unique_groups = selected_groups
        else:
            unique_groups = sorted(df[clinical_col].dropna().unique().astype(str))

        grouped_dfs = []
        for group_name in unique_groups:
            group_df = df[df[clinical_col].astype(str) == group_name].copy()
            if len(group_df) < 5:
                continue

            median_expr = group_df['expression'].median()
            high_idx = group_df['expression'] >= median_expr
            low_idx = group_df['expression'] < median_expr

            high_df = group_df[high_idx].copy()
            low_df = group_df[low_idx].copy()

            if len(high_df) >= 2:
                high_df['group'] = f'{group_name} High ({len(high_df)})'
                grouped_dfs.append(high_df)
            if len(low_df) >= 2:
                low_df['group'] = f'{group_name} Low ({len(low_df)})'
                grouped_dfs.append(low_df)

        if not grouped_dfs:
            return []

        return pd.concat(grouped_dfs, ignore_index=True)

    def split_groups_simple(self, df):
        """简单分组（High vs Low）"""
        if df is None:
            return None, 0, 0

        df = df.copy()
        median_expr = df['expression'].median()
        high_idx = df['expression'] >= median_expr
        low_idx = df['expression'] < median_expr

        n_high = high_idx.sum()
        n_low = low_idx.sum()

        df['group'] = np.where(high_idx, f'High ({n_high})', f'Low ({n_low})')

        return df, n_high, n_low

    def _load_r_script(self):
        """检查R脚本是否存在"""
        if self._r_script_loaded:
            return True
        
        if not os.path.exists(self.R_SCRIPT_PATH):
            self._log_r_debug("load_r_script", 
                             FileNotFoundError(f"R脚本不存在: {self.R_SCRIPT_PATH}"),
                             {"script_path": self.R_SCRIPT_PATH})
            return False
        
        # R脚本存在，标记为已加载
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
            _importr('survival')
            _importr('survminer')
            _importr('ggplot2')
            _importr('cowplot')
            self._r_packages_loaded = True
            print("[R包加载] survival, survminer, ggplot2, cowplot 已通过importr加载")
            return True
        except Exception as e:
            self._log_r_debug("load_r_packages", e, {"importr": str(_importr)})
            return False

    def draw_km_plot_r(self, 
                       survival_data,
                       time_col: str,
                       event_col: str,
                       group_col: str,
                       gene_name: str = "",
                       output_path: str = None,
                       title: str = None,
                       show_risk_table: bool = True,
                       plot_width: float = 10,
                       plot_height: float = 8,
                       pval_mode: int = 0,
                       title_font_size: int = 14,
                       axis_font_size: int = 12,
                       legend_font_size: int = 12,
                       pval_font_size: int = 12,
                       risk_table_font_size: int = 10,
                       show_conf_int: bool = False,
                       show_n: bool = True,
                       show_global_pval: bool = True,
                       show_pairwise: bool = False,
                       selected_pairwise: list = None,
                       **kwargs) -> str:
        """
        使用R绘制KM曲线 - Python接口
        
        此方法只负责：
        1. 数据准备和参数验证
        2. 将参数传递到R环境
        3. 调用R脚本中的draw_km_plot_r函数
        
        所有R代码逻辑都在bulk_km_r.R脚本中
        
        Parameters:
        -----------
        survival_data : pandas.DataFrame
            生存数据，包含时间、事件和分组信息
        time_col : str
            时间列名
        event_col : str
            事件列名（0=存活，1=死亡）
        group_col : str
            分组列名
        gene_name : str
            基因名称（用于标题）
        output_path : str
            输出图片路径
        title : str
            图表标题
        show_risk_table : bool
            是否显示风险表格
        plot_width : float
            图表宽度
        plot_height : float
            图表高度
        pval_mode : int
            p值显示模式 (0=具体值, 1=模糊值, 2=模糊值+具体值)
        title_font_size : int
            标题字体大小
        axis_font_size : int
            坐标轴字体大小
        legend_font_size : int
            图例字体大小
        pval_font_size : int
            显著性(p值)字体大小
        risk_table_font_size : int
            风险表格字体大小
        show_conf_int : bool
            是否显示置信区间
        show_n : bool
            是否显示n值
        show_global_pval : bool
            是否显示总体p值
        show_pairwise : bool
            是否显示组间比较
        selected_pairwise : list
            选中的组间比较列表
        
        Returns:
        --------
        str : 生成的图片路径
        """
        if not self.robjects:
            raise RuntimeError("R环境不可用")
        
        # 确保R包已加载
        if not self._load_r_packages():
            raise RuntimeError("R包加载失败，请检查R环境")
        
        # 确保R脚本已加载
        if not self._load_r_script():
            raise RuntimeError("R脚本加载失败，请检查R脚本路径")
        
        # 记录参数类型信息（用于调试）
        param_types = {
            "survival_data": f"type={type(survival_data).__name__}, shape={getattr(survival_data, 'shape', 'N/A')}",
            "time_col": f"type={type(time_col).__name__}",
            "event_col": f"type={type(event_col).__name__}",
            "group_col": f"type={type(group_col).__name__}",
            "gene_name": f"type={type(gene_name).__name__}",
            "output_path": f"type={type(output_path).__name__}",
            "title": f"type={type(title).__name__}",
            "show_risk_table": f"type={type(show_risk_table).__name__}",
            "plot_width": f"type={type(plot_width).__name__}",
            "plot_height": f"type={type(plot_height).__name__}",
            "pval_mode": f"type={type(pval_mode).__name__}",
            "title_font_size": f"type={type(title_font_size).__name__}",
            "axis_font_size": f"type={type(axis_font_size).__name__}",
            "legend_font_size": f"type={type(legend_font_size).__name__}",
            "pval_font_size": f"type={type(pval_font_size).__name__}",
            "risk_table_font_size": f"type={type(risk_table_font_size).__name__}",
            "show_conf_int": f"type={type(show_conf_int).__name__}",
            "show_n": f"type={type(show_n).__name__}",
            "show_global_pval": f"type={type(show_global_pval).__name__}",
            "show_pairwise": f"type={type(show_pairwise).__name__}",
            "selected_pairwise": f"type={type(selected_pairwise).__name__}",
        }
        
        # 导入rpy2向量类型
        from rpy2.robjects import pandas2ri, StrVector, BoolVector
        from rpy2.robjects.vectors import FloatVector, IntVector
        from rpy2.robjects.conversion import localconverter
        
        try:
            # 数据预处理：删除time/event/group列中的NA值，确保向量长度一致
            original_shape = survival_data.shape
            survival_data = survival_data.dropna(subset=[time_col, event_col, group_col])
            cleaned_shape = survival_data.shape
            
            if original_shape[0] != cleaned_shape[0]:
                print(f"[R数据预处理] 删除了 {original_shape[0] - cleaned_shape[0]} 行含NA的样本")
            
            # 长度验证
            if survival_data.empty:
                raise RuntimeError("数据清洗后为空，无法进行KM分析")
            
            # 将数据传递到R环境
            with localconverter(pandas2ri.converter):
                self.robjects.globalenv['survival_data'] = survival_data
            
            # 将其他参数传递到R环境（使用rpy2向量类型包装）
            self.robjects.globalenv['time_col'] = StrVector([time_col])
            self.robjects.globalenv['event_col'] = StrVector([event_col])
            self.robjects.globalenv['group_col'] = StrVector([group_col])
            self.robjects.globalenv['gene_name'] = StrVector([gene_name])
            self.robjects.globalenv['output_path'] = StrVector([output_path if output_path else ''])
            self.robjects.globalenv['plot_title'] = StrVector([title if title else ''])
            self.robjects.globalenv['show_risk_table'] = BoolVector([show_risk_table])
            self.robjects.globalenv['plot_width'] = FloatVector([float(plot_width)])
            self.robjects.globalenv['plot_height'] = FloatVector([float(plot_height)])
            self.robjects.globalenv['pval_mode'] = IntVector([int(pval_mode)])
            
            # 新增参数 - 字体大小
            self.robjects.globalenv['title_font_size'] = IntVector([int(title_font_size)])
            self.robjects.globalenv['axis_font_size'] = IntVector([int(axis_font_size)])
            self.robjects.globalenv['legend_font_size'] = IntVector([int(legend_font_size)])
            self.robjects.globalenv['pval_font_size'] = IntVector([int(pval_font_size)])
            self.robjects.globalenv['risk_table_font_size'] = IntVector([int(risk_table_font_size)])
            
            # 新增参数 - 显示选项
            self.robjects.globalenv['show_conf_int'] = BoolVector([show_conf_int])
            self.robjects.globalenv['show_n'] = BoolVector([show_n])
            self.robjects.globalenv['show_global_pval'] = BoolVector([show_global_pval])
            self.robjects.globalenv['show_pairwise'] = BoolVector([show_pairwise])
            
            # 新增参数 - 组间比较列表
            if selected_pairwise and isinstance(selected_pairwise, list):
                self.robjects.globalenv['selected_pairwise'] = StrVector(selected_pairwise)
            else:
                self.robjects.globalenv['selected_pairwise'] = StrVector([])
            
        except Exception as e:
            self._log_r_debug("set_globalenv", e, {"params": param_types})
            raise RuntimeError(f"参数传递到R环境失败: {str(e)}")
        
        # 调用R脚本中的绘图逻辑
        # 注意：由于rpy2的环境问题，不直接调用R函数
        # 而是读取R脚本中的绘图代码并直接执行
        try:
            # 读取R脚本内容
            with open(self.R_SCRIPT_PATH, 'r', encoding='utf-8') as f:
                r_script_lines = f.readlines()
            
            # 按标记行提取代码段执行
            # R脚本中需要用以下标记行包裹代码：
            # # --- FUNCTION_BODY_START ---
            # # --- FUNCTION_BODY_END ---
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
                raise RuntimeError("标记行顺序错误，FUNCTION_BODY_START必须在FUNCTION_BODY_END之前")
            
            # 提取并合并代码段
            r_code_body = ''.join(r_script_lines[start_idx:end_idx]).strip()
            
            if not r_code_body:
                raise RuntimeError("提取的代码段为空")
            
            # 直接执行R代码（在全局环境中）
            self.robjects.r(r_code_body)
            return output_path if output_path else None
            
        except Exception as e:
            self._log_r_debug("execute_r_code", e, {"script_path": self.R_SCRIPT_PATH})
            raise RuntimeError(f"R绘图代码执行失败: {str(e)}")

# 单例模式
_instance = None

def get_bulk_km_r_analysis() -> BulkKmRAnalysis:
    """获取bulk KM R分析单例"""
    global _instance
    if _instance is None:
        _instance = BulkKmRAnalysis()
    return _instance