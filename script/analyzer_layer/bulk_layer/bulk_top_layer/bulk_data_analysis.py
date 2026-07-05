# -*- coding: utf-8 -*-
"""
bulk分析数据管理脚本 - 负责数据加载、扫描等通用数据操作
供所有bulk分析子界面共享数据
"""

from script.utils_layer.import_config import *


class BulkDataManager:
    """bulk RNA-seq数据管理类 - 供所有bulk分析子界面共享数据"""

    def __init__(self):
        self.adata = None
        self.current_gene = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.valid_groups = []
        self.current_data_folder = None
        self.data_info = {}

    def scan_data_folder(self):
        """扫描数据路径，返回h5ad文件列表（纯数据，不操作控件）"""
        folder_path = BULK_SCAN_DATA_PATH
        if not os.path.exists(folder_path):
            return False, [], f"扫描路径不存在: {folder_path}"

        h5ad_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.h5ad')])
        if not h5ad_files:
            return False, [], f"{folder_path} 中没有找到h5ad文件"

        self.current_data_folder = folder_path
        return True, h5ad_files, ""

    def load_data(self, selected_file):
        """加载数据（纯算法，不操作控件）
        返回: (success, data_info_dict, error_msg)
        data_info_dict: {'samples', 'genes', 'dataset', 'valid_groups'}
        """
        if not self.current_data_folder:
            return False, {}, "请先选择数据路径"

        if not selected_file:
            return False, {}, "请选择要加载的h5ad文件"

        self.clear_data()
        data_path = os.path.join(self.current_data_folder, selected_file)

        try:
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"数据文件不存在: {data_path}")

            import scanpy as sc
            self.adata = sc.read_h5ad(data_path)

            PREFERRED_GROUPS = ["group", "sample_type", "sample", "batch", "tissue", "disease"]
            self.valid_groups = []
            for col in PREFERRED_GROUPS:
                if col in self.adata.obs.columns and self.adata.obs[col].nunique() <= 50:
                    self.valid_groups.append(col)

            if not self.valid_groups:
                for col in self.adata.obs.columns:
                    try:
                        if self.adata.obs[col].nunique() <= 50:
                            self.valid_groups.append(col)
                    except Exception:
                        continue

            self.dataset_name = os.path.splitext(selected_file)[0]
            self.dataset_output_dir = os.path.join(OUT_BASE, self.dataset_name)
            os.makedirs(self.dataset_output_dir, exist_ok=True)

            self.data_info = {
                'samples': self.adata.shape[0],
                'genes': self.adata.shape[1],
                'dataset': self.dataset_name,
                'valid_groups': self.valid_groups,
            }

            return True, self.data_info, ""

        except Exception as e:
            traceback.print_exc()
            return False, {}, f"加载数据失败: {str(e)}"

    def clear_data(self):
        """清空数据"""
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.valid_groups = []
        self.data_info = {}

    def is_data_loaded(self):
        """检查数据是否已加载"""
        return self.adata is not None

    def get_data_info(self):
        """获取当前数据信息"""
        return self.data_info