# -*- coding: utf-8 -*-
"""
bulk COX分析脚本 - Python接口层
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


class BulkCoxAnalysis:
    """bulk COX分析类 - Python接口层，不含R代码"""
    
    # R交互调试日志
    _r_debug_log: List[Dict[str, Any]] = []
    
    # R脚本路径
    R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_cox_r.R")
    
    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.pandas2ri = None
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.result_df = None
        self._r_script_loaded = False
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
    
    def get_gene_names(self):
        """获取所有基因名称"""
        if self.adata is None:
            return []
        return list(self.adata.var_names)
    
    def filter_genes_by_top_n(self, n=5000, method='variance'):
        """
        按表达量筛选前N个基因
        
        Parameters:
        -----------
        n : int
            保留基因数量
        method : str
            筛选方法: 'variance'(方差), 'mean'(均值)
        
        Returns:
        --------
        list : 筛选后的基因名称列表
        """
        if self.adata is None:
            return []
        
        expr_data = self.adata.X
        if isinstance(expr_data, np.ndarray):
            pass
        elif hasattr(expr_data, 'toarray'):
            expr_data = expr_data.toarray()
        
        if expr_data.shape[0] != self.adata.shape[0]:
            expr_data = expr_data.T
        
        if method == 'variance':
            gene_var = np.var(expr_data, axis=0)
        else:
            gene_var = np.mean(expr_data, axis=0)
        
        sorted_indices = np.argsort(gene_var)[::-1]
        top_n_indices = sorted_indices[:min(n, len(sorted_indices))]
        top_genes = [self.adata.var_names[i] for i in top_n_indices]
        
        return top_genes
    
    def prepare_survival_data(self):
        """准备生存数据"""
        adata = self.adata
        
        if 'time (month)' in adata.obs.columns:
            time_col = 'time (month)'
        elif 'time' in adata.obs.columns:
            time_col = 'time'
        else:
            return None
        
        if 'state' not in adata.obs.columns:
            return None
        
        time_data = pd.to_numeric(adata.obs[time_col].values, errors='coerce')
        state_data = pd.to_numeric(adata.obs['state'].values, errors='coerce')
        
        df = pd.DataFrame({
            'time': time_data,
            'event': state_data
        }, index=adata.obs.index)
        
        df = df[df['time'].notna() & df['event'].notna()]
        df = df[df['time'] > 0]
        
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
    
    def run_cox_analysis(self, gene_names=None, clinical_covariates=None,
                        adjusted=False, filter1_col=None, filter1_groups=None,
                        filter2_col=None, filter2_groups=None,
                        progress_callback=None):
        """
        运行COX分析
        
        Parameters:
        -----------
        gene_names : list
            基因名称列表，如果为None则分析所有基因
        clinical_covariates : list
            临床协变量列名列表
        adjusted : bool
            是否进行多因素校正
        filter1_col : str
            筛选1列名
        filter1_groups : list
            筛选1组别
        filter2_col : str
            筛选2列名
        filter2_groups : list
            筛选2组别
        
        Returns:
        --------
        pd.DataFrame : COX分析结果
        """
        if not self.robjects:
            raise RuntimeError("R环境不可用")
        
        if self.adata is None:
            raise RuntimeError("未加载数据")
        
        if not self._load_r_packages():
            raise RuntimeError("R包加载失败")
        
        if not self._load_r_script():
            raise RuntimeError("R脚本加载失败")
        
        # 准备生存数据
        surv_df = self.prepare_survival_data()
        if surv_df is None:
            raise RuntimeError("生存数据准备失败")
        
        # 应用筛选条件
        surv_df = self.filter_data(surv_df, filter1_col, filter1_groups, filter2_col, filter2_groups)
        if surv_df is None:
            raise RuntimeError("筛选后数据不足")
        
        # 获取基因列表
        if gene_names is None:
            gene_names = list(self.adata.var_names)
        else:
            gene_names = [g for g in gene_names if g in self.adata.var_names]
        
        if not gene_names:
            raise RuntimeError("没有有效的基因")
        
        # 获取表达数据
        expr_data = self.adata[:, gene_names].X
        if isinstance(expr_data, np.ndarray):
            pass
        elif hasattr(expr_data, 'toarray'):
            expr_data = expr_data.toarray()
        if expr_data.shape[0] != self.adata.shape[0]:
            expr_data = expr_data.T
        
        expr_df = pd.DataFrame(expr_data, 
                               columns=gene_names, 
                               index=self.adata.obs.index)
        
        # 合并数据
        combined_df = surv_df.join(expr_df)
        combined_df = combined_df.dropna(subset=['time', 'event'])
        
        # 准备临床协变量
        base_df = None
        if clinical_covariates:
            cov_data = {}
            for cov in clinical_covariates:
                if cov in self.adata.obs.columns:
                    cov_data[cov] = self.adata.obs.loc[combined_df.index, cov].values
            if cov_data:
                base_df = pd.DataFrame(cov_data, index=combined_df.index)
        
        # 分离表达数据和生存数据
        expr_data = combined_df[gene_names]
        surv_data = combined_df[['time', 'event']]
        
        print(f"[COX分析] 样本数: {len(surv_data)}")
        print(f"[COX分析] 事件数: {surv_data['event'].sum()}")
        print(f"[COX分析] 基因数: {len(gene_names)}")
        print(f"[COX分析] 校正模式: {'多因素' if adjusted else '单因素'}")
        
        # 将数据传递到R环境
        from rpy2.robjects import pandas2ri
        from rpy2.robjects.conversion import localconverter
        
        try:
            with localconverter(pandas2ri.converter):
                self.robjects.globalenv['expr_data'] = expr_data
                self.robjects.globalenv['surv_data'] = surv_data
            
            self.robjects.globalenv['gene_names'] = self.robjects.StrVector(gene_names)
            self.robjects.globalenv['adjusted'] = self.robjects.BoolVector([adjusted])
            
            if base_df is not None:
                with localconverter(pandas2ri.converter):
                    self.robjects.globalenv['clinical_covariates'] = base_df
            else:
                self.robjects.globalenv['clinical_covariates'] = self.robjects.NULL
            
        except Exception as e:
            print(f"参数传递失败: {e}")
            traceback.print_exc()
            raise
        
        # 读取并执行R脚本
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
                raise RuntimeError("未找到标记行")

            r_code_body = ''.join(r_script_lines[start_idx:end_idx]).strip()

            # 使用rpy2的输出回调捕获R的cat()输出
            from rpy2.rinterface_lib import callbacks as ri_callbacks

            r_output_lines = []

            def _capture_output(msg):
                r_output_lines.append(msg)

            old_writeconsole = ri_callbacks.consolewrite_print
            ri_callbacks.consolewrite_print = _capture_output

            try:
                r_result = self.robjects.r(r_code_body)
            finally:
                ri_callbacks.consolewrite_print = old_writeconsole

            full_output = ''.join(r_output_lines)
            for line in full_output.split('\n'):
                line = line.strip()
                if line.startswith('[COX进度]'):
                    print(line)
                    if progress_callback:
                        progress_callback(line)

            with localconverter(pandas2ri.converter):
                self.result_df = pd.DataFrame(self.robjects.conversion.rpy2py(r_result))

            return self.result_df

        except Exception as e:
            print(f"R代码执行失败: {e}")
            traceback.print_exc()
            raise
    
    def _load_r_script(self):
        """检查R脚本是否存在"""
        if self._r_script_loaded:
            return True
        
        if not os.path.exists(self.R_SCRIPT_PATH):
            print(f"R脚本不存在: {self.R_SCRIPT_PATH}")
            return False
        
        self._r_script_loaded = True
        print(f"R脚本检查通过: {self.R_SCRIPT_PATH}")
        return True
    
    def _load_r_packages(self):
        """预加载R包"""
        if getattr(self, '_r_packages_loaded', False):
            return True
        
        if _importr is None:
            return False
        
        try:
            _importr('survival')
            self._r_packages_loaded = True
            print("[R包加载] survival 已通过importr加载")
            return True
        except Exception as e:
            print(f"R包加载失败: {e}")
            return False


_instance = None

def get_bulk_cox_analysis() -> BulkCoxAnalysis:
    """获取bulk COX分析单例"""
    global _instance
    if _instance is None:
        _instance = BulkCoxAnalysis()
    return _instance