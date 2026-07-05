# -*- coding: utf-8 -*-
"""
bulk相关性分析算法脚本 - bulk相关性分析页面的核心生信分析方法
包含数据加载、数据筛选、相关性分析、导出等功能
"""

from script.utils_layer.import_config import *

class BulkCorreAnalysis:
    """bulk相关性分析类"""

    def __init__(self):
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None

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
        """获取obs列名"""
        if self.adata is None:
            return []
        return list(self.adata.obs.columns)

    def get_gene_exists(self, gene_name):
        """检查基因是否存在"""
        if self.adata is None:
            return False
        return gene_name in self.adata.var_names or gene_name in self.adata.obs.columns