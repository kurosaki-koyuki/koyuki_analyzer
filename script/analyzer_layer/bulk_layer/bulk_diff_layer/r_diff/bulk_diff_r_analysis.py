# -*- coding: utf-8 -*-
"""
bulk差异分析核心算法脚本 - R版本
Python接口层，负责数据准备、参数传递到R环境、调用R脚本函数
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path
from typing import Optional, List, Dict, Any

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class BulkDiffRAnalysis:
    """bulk差异分析 R模式分析类 - Python接口层"""

    R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_diff_r.R")

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

    def set_adata(self, adata, dataset_name=None, dataset_output_dir=None):
        """设置分析数据"""
        self.adata = adata
        self.dataset_name = dataset_name
        self.dataset_output_dir = dataset_output_dir

    def _load_r_script(self):
        """加载R脚本"""
        if self._r_script_loaded:
            return

        if not os.path.exists(self.R_SCRIPT_PATH):
            raise RuntimeError(f"R脚本不存在: {self.R_SCRIPT_PATH}")

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
                raise RuntimeError("R脚本中未找到标记行")

            r_code_body = ''.join(r_script_lines[start_idx:end_idx]).strip()

            self.robjects.r(r_code_body)
            self._r_script_loaded = True
            print("[DiffR] R脚本加载成功")

        except Exception as e:
            print(f"[DiffR] R脚本加载失败: {e}")
            traceback.print_exc()
            raise

    def run_diff_analysis(self, group_col, group1_list, group2_list,
                          method="limma", gene_names=None,
                          filter1_col=None, filter1_groups=None,
                          filter2_col=None, filter2_groups=None):
        """
        运行差异分析

        Args:
            group_col: 分组列名
            group1_list: 组1的组别列表（可多选合并）
            group2_list: 组2的组别列表（可多选合并）
            method: 分析方法，"limma"或"edger"
            gene_names: 要分析的基因列表，None表示全部
            filter1_col: 筛选条件1列名
            filter1_groups: 筛选条件1组别列表
            filter2_col: 筛选条件2列名
            filter2_groups: 筛选条件2组别列表

        Returns:
            结果DataFrame
        """
        if not self.is_available():
            raise RuntimeError("R环境不可用")

        if self.adata is None:
            raise RuntimeError("数据未加载")

        # 加载R脚本
        self._load_r_script()

        # 筛选样本
        adata = self.adata.copy()

        # 样本筛选
        if filter1_col and filter1_groups and len(filter1_groups) > 0:
            mask1 = adata.obs[filter1_col].astype(str).isin(filter1_groups)
            adata = adata[mask1, :]

        if filter2_col and filter2_groups and len(filter2_groups) > 0:
            mask2 = adata.obs[filter2_col].astype(str).isin(filter2_groups)
            adata = adata[mask2, :]

        # 分组筛选
        group1_mask = adata.obs[group_col].astype(str).isin(group1_list)
        group2_mask = adata.obs[group_col].astype(str).isin(group2_list)

        if group1_mask.sum() == 0:
            raise ValueError("组1没有样本")
        if group2_mask.sum() == 0:
            raise ValueError("组2没有样本")

        combined_mask = group1_mask | group2_mask
        adata = adata[combined_mask, :]

        # 准备样本标签
        sample_labels = []
        for val in adata.obs[group_col].astype(str):
            if val in group1_list:
                sample_labels.append("group1")
            else:
                sample_labels.append("group2")

        # 基因筛选
        if gene_names is not None and len(gene_names) > 0:
            available_genes = [g for g in gene_names if g in adata.var_names]
            if len(available_genes) == 0:
                raise ValueError("没有匹配的基因")
            adata = adata[:, available_genes]

        print(f"[DiffR] 样本数: {adata.shape[0]}, 基因数: {adata.shape[1]}")
        print(f"[DiffR] 组1样本数: {sum(1 for s in sample_labels if s == 'group1')}")
        print(f"[DiffR] 组2样本数: {sum(1 for s in sample_labels if s == 'group2')}")
        print(f"[DiffR] 方法: {method}")

        # 准备表达矩阵（行是基因，列是样本）
        expr_data = adata.X.T
        if hasattr(expr_data, 'toarray'):
            expr_data = expr_data.toarray()

        # edgeR需要整数
        if method == "edger":
            expr_data = np.round(expr_data).astype(int)

        expr_df = pd.DataFrame(
            expr_data,
            index=adata.var_names,
            columns=adata.obs_names
        )

        # 传递到R并运行
        try:
            from rpy2.robjects import pandas2ri
            from rpy2.robjects.conversion import localconverter

            with localconverter(pandas2ri.converter):
                self.robjects.globalenv['expr_mat'] = expr_df

            self.robjects.globalenv['sample_labels'] = self.robjects.StrVector(sample_labels)
            self.robjects.globalenv['group1_name'] = self.robjects.StrVector(['group1'])[0]
            self.robjects.globalenv['group2_name'] = self.robjects.StrVector(['group2'])[0]
            self.robjects.globalenv['method'] = self.robjects.StrVector([method])[0]

            r_result = self.robjects.r(
                'run_diff_analysis(expr_mat, sample_labels, group1_name, group2_name, method)'
            )

            with localconverter(pandas2ri.converter):
                self.result_df = pd.DataFrame(self.robjects.conversion.rpy2py(r_result))

            # 将列名转换为普通字符串
            self.result_df.columns = [str(col) for col in self.result_df.columns]

            # 确保数值列是正确的数值类型
            numeric_cols = ['mean_group1', 'mean_group2', 'log2FC', 'p_val', 'adj_p_val']
            for col in numeric_cols:
                if col in self.result_df.columns:
                    self.result_df[col] = pd.to_numeric(self.result_df[col], errors='coerce')

            return self.result_df

        except Exception as e:
            print(f"[DiffR] 分析失败: {e}")
            traceback.print_exc()
            raise

    def get_diff_summary(self, pval_threshold=0.05, logfc_threshold=0.25):
        """获取差异分析统计"""
        if self.result_df is None or len(self.result_df) == 0:
            return {
                'total': 0,
                'up': 0,
                'down': 0,
                'stable': 0
            }

        df = self.result_df
        sig_mask = df['adj_p_val'] < pval_threshold
        up_mask = sig_mask & (df['log2FC'] > logfc_threshold)
        down_mask = sig_mask & (df['log2FC'] < -logfc_threshold)
        stable_mask = ~(up_mask | down_mask)

        return {
            'total': len(df),
            'up': int(up_mask.sum()),
            'down': int(down_mask.sum()),
            'stable': int(stable_mask.sum())
        }

    def export_to_excel(self, file_path, pval_threshold=0.05, logfc_threshold=0.25):
        """导出结果到Excel"""
        if self.result_df is None:
            return

        df = self.result_df.copy()
        sig_mask = df['adj_p_val'] < pval_threshold
        up_df = df[sig_mask & (df['log2FC'] > logfc_threshold)].copy()
        down_df = df[sig_mask & (df['log2FC'] < -logfc_threshold)].copy()

        with pd.ExcelWriter(file_path) as writer:
            df.to_excel(writer, sheet_name='总体列表', index=False)
            up_df.to_excel(writer, sheet_name='显著上调', index=False)
            down_df.to_excel(writer, sheet_name='显著下调', index=False)
