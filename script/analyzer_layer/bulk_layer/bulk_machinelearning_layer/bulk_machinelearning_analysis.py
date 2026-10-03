# -*- coding: utf-8 -*-
"""
bulk 机器学习分析核心算法层 - 主层容器
负责存储合并后的数据集和PCA结果，供所有子层共享
子层各自由自己的 analysis 层管理具体业务逻辑
"""

from script.utils_layer.import_config import os, pd, np


class BulkMachineLearningAnalysis:
    """机器学习主层数据管理类 - 存储合并数据集和PCA结果，供所有子层共享"""

    def __init__(self):
        # === 合并数据集相关 ===
        self.merged_expr_df = None       # 合并后表达矩阵（行=样本, 列=基因）
        self.merged_group_df = None      # 分组信息（SampleID, Dataset）
        self.dataset_names = []          # 选中的数据集名称列表
        self.common_genes = []           # 基因交集
        self.merged_output_dir = None    # 合并数据输出目录

        # === PCA结果相关 ===
        # {method_name: {'plot_path': str, 'variance_csv': str, 'pc_csv': str, 'variance_explained': list}}
        self.pca_results = {}

        # === 同步临床信息相关（阶段三产出） ===
        self.clinical_df = None          # 同步后的临床信息 DataFrame（SampleID, <主注释列名>）
        self.clinical_column_name = None # 映射列名（= 主注释列名）
        self.clinical_group_names = {}   # 组别命名 {'group1': str, 'group2': str}

        # === R环境状态 ===
        self.r_available = False

    def set_merged_data(self, expr_df, group_df, dataset_names, common_genes):
        """设置合并后的数据"""
        self.merged_expr_df = expr_df
        self.merged_group_df = group_df
        self.dataset_names = dataset_names
        self.common_genes = common_genes

    def set_pca_result(self, method_name, result_dict):
        """设置某个预处理方法的PCA结果"""
        self.pca_results[method_name] = result_dict

    def set_clinical_data(self, clinical_df, column_name=None, group_names=None):
        """设置同步后的临床信息（阶段三产出）

        Args:
            clinical_df: DataFrame，包含 SampleID 和映射列
            column_name: 映射列名（= 主注释列名）
            group_names: {'group1': str, 'group2': str} 组别命名
        """
        self.clinical_df = clinical_df
        if column_name is not None:
            self.clinical_column_name = column_name
        if group_names is not None:
            self.clinical_group_names = group_names

    def get_clinical_data(self):
        """获取同步后的临床信息（供后续子层使用）"""
        return self.clinical_df

    def get_merged_data(self):
        """获取合并后的数据（供子层使用）"""
        return self.merged_expr_df, self.merged_group_df

    def is_data_loaded(self):
        """检查数据是否已加载"""
        return self.merged_expr_df is not None

    def clear_data(self):
        """清空数据"""
        self.merged_expr_df = None
        self.merged_group_df = None
        self.dataset_names = []
        self.common_genes = []
        self.pca_results = {}
        self.clinical_df = None
        self.clinical_column_name = None
        self.clinical_group_names = {}
