# -*- coding: utf-8 -*-
"""
单细胞分析数据管理脚本 - 负责数据加载、扫描等通用数据操作
供所有单细胞分析子界面共享数据
"""

from script.utils_layer.import_config import *

class ScRNADataManager:
    """单细胞RNA-seq数据管理类 - 供所有单细胞分析子界面共享数据"""
    
    def __init__(self):
        self.adata = None
        self.current_gene = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.static_umap_dir = None
        self.umap_key = "X_umap"
        self.valid_groups = []
        self.current_data_folder = None
        self.data_info = {}
        self.seurat_path = None
        self.seurat_loaded = False
    
    def scan_data_folder(self):
        """扫描数据路径，返回h5ad文件列表（纯数据，不操作控件）"""
        folder_path = SCAN_DATA_PATH
        if not os.path.exists(folder_path):
            return False, [], f"扫描路径不存在: {folder_path}"

        h5ad_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.h5ad')])
        if not h5ad_files:
            return False, [], f"{folder_path} 中没有找到h5ad文件"

        self.current_data_folder = folder_path
        return True, h5ad_files, ""
    
    def scan_rds_folder(self):
        """扫描rds数据路径，返回rds文件列表（纯数据，不操作控件）"""
        folder_path = os.path.join(APPDATA_PATH, "R_sc_main")
        if not os.path.exists(folder_path):
            return False, [], f"rds扫描路径不存在: {folder_path}"

        rds_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.rds')])
        if not rds_files:
            return False, [], f"{folder_path} 中没有找到rds文件"

        return True, rds_files, ""
    
    def load_data(self, selected_file):
        """加载数据（纯算法，不操作控件）
        返回: (success, data_info_dict, error_msg)
        data_info_dict: {'cells', 'genes', 'umap_key', 'dataset', 'valid_groups'}
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

            possible_keys = ["X_umap", "X_UMAP"]
            for key in possible_keys:
                if key in self.adata.obsm:
                    self.umap_key = key
                    break

            PREFERRED_GROUPS = ["cell_type", "group", "sample_type", "sample"]
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

            self.static_umap_dir = os.path.join(self.dataset_output_dir, "_static_umap_groups")
            os.makedirs(self.static_umap_dir, exist_ok=True)

            self.data_info = {
                'cells': self.adata.shape[0],
                'genes': self.adata.shape[1],
                'umap_key': self.umap_key,
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
        self.static_umap_dir = None
        self.valid_groups = []
        self.data_info = {}
    
    def load_rds_data(self, selected_file):
        """加载rds数据（在R内核中创建seurat_obj）
        返回: (success, data_info_dict, error_msg)
        """
        folder_path = os.path.join(APPDATA_PATH, "R_sc_main")
        
        if not os.path.exists(folder_path):
            return False, {}, f"rds路径不存在: {folder_path}"

        if not selected_file:
            return False, {}, "请选择要加载的rds文件"

        rds_path = os.path.join(folder_path, selected_file)
        if not os.path.exists(rds_path):
            return False, {}, f"rds文件不存在: {rds_path}"

        try:
            from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            
            r_interface = get_r_kernel_interface()
            robjects = r_interface.get_robjects()
            
            if robjects is None:
                return False, {}, "R环境不可用"

            robjects.globalenv['seurat_obj_path'] = robjects.StrVector([rds_path])
            robjects.r('seurat_obj <- readRDS(seurat_obj_path)')
            
            cell_count = int(robjects.r('ncol(seurat_obj)')[0])
            gene_count = int(robjects.r('nrow(seurat_obj)')[0])
            
            self.seurat_path = rds_path
            self.seurat_loaded = True
            self.dataset_name = os.path.splitext(selected_file)[0]
            
            rds_info = {
                'cells': cell_count,
                'genes': gene_count,
                'dataset': self.dataset_name,
                'seurat_path': rds_path,
                'seurat_loaded': True
            }
            
            return True, rds_info, ""

        except Exception as e:
            traceback.print_exc()
            return False, {}, f"加载rds数据失败: {str(e)}"
    
    def is_data_loaded(self):
        """检查数据是否已加载"""
        return self.adata is not None
    
    def is_seurat_loaded(self):
        """检查seurat对象是否已加载"""
        return self.seurat_loaded
    
    def get_seurat_path(self):
        """获取当前seurat对象路径"""
        return self.seurat_path
    
    def get_data_info(self):
        """获取当前数据信息"""
        return self.data_info