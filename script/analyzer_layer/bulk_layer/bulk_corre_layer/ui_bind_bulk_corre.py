# -*- coding: utf-8 -*-
"""
bulk相关性分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.bulk_layer.bulk_corre_layer.bulk_corre_analysis import BulkCorreAnalysis
from script.analyzer_layer.bulk_layer.bulk_corre_layer.ui_func_bulk_corre import BulkCorreFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect


class BulkCorreBind:
    """bulk相关性分析功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, bulk_corre_ui):
        self.parent = parent_window
        self.bulk_corre_ui = bulk_corre_ui
        self.analysis = BulkCorreAnalysis()
        self.func = BulkCorreFunc(bulk_corre_ui, parent_window)
        self.data_folder = None
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_bulk_corre_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.bulk_corre_ui, 'btn_back_bulk_corre'):
            self.bulk_corre_ui.btn_back_bulk_corre.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.bulk_corre_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.bulk_corre_ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def bind_bulk_corre_functions(self):
        """绑定bulk相关性分析功能信号"""
        log_widget = getattr(self.bulk_corre_ui, 'bulk_corre_status_text', None)

        if hasattr(self.bulk_corre_ui, 'btn_corredot'):
            page_intersect.bind_page_button(self.bulk_corre_ui.btn_corredot, 'bulk_corredot_page', self)

        if hasattr(self.bulk_corre_ui, 'btn_correbubble'):
            page_intersect.bind_page_button(self.bulk_corre_ui.btn_correbubble, 'bulk_correbubble_page', self)

    def scan_data_path(self):
        """扫描bulk数据路径"""
        folder_path = BULK_SCAN_DATA_PATH

        if not os.path.exists(folder_path):
            self.func.alert_error(f"扫描路径不存在: {folder_path}")
            return

        h5ad_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.h5ad')])

        if not h5ad_files:
            self.func.alert_error(f"{folder_path} 中没有找到h5ad文件")
            return

        self.data_folder = folder_path
        self.func.set_combo_items(self.bulk_corre_ui.bulk_corre_h5ad_combo, h5ad_files)

        self.func.log(f"已扫描数据路径: {folder_path}")
        self.func.log(f"找到 {len(h5ad_files)} 个h5ad文件")

    def load_data(self):
        """加载bulk数据"""
        if not self.data_folder:
            self.func.alert_error("请先扫描数据路径")
            return

        selected_file = self.bulk_corre_ui.bulk_corre_h5ad_combo.currentText()
        if not selected_file:
            self.func.alert_error("请选择要加载的h5ad文件")
            return

        self.clear_data()

        data_path = os.path.join(self.data_folder, selected_file)

        try:
            self.func.log("正在加载数据...")

            import scanpy as sc
            self.adata = sc.read_h5ad(data_path)
            self.analysis.set_adata(self.adata)

            self.dataset_name = os.path.splitext(selected_file)[0]
            self.dataset_output_dir = os.path.join(OUT_BASE, "bulk_corre", self.dataset_name)
            os.makedirs(self.dataset_output_dir, exist_ok=True)
            self.analysis.set_dataset_output_dir(self.dataset_output_dir)
            self.analysis.set_dataset_name(self.dataset_name)

            n_samples, n_genes = self.adata.shape
            self.func.log(f"样本数: {n_samples}")
            self.func.log(f"基因数: {n_genes}")
            self.func.log(f"数据集: {self.dataset_name}")

            # 更新提示文本
            self.func.update_hint_text(self.dataset_name, n_samples, n_genes)

            self.func.alert_success("数据加载完成")

        except Exception as e:
            self.func.log(f"加载失败: {str(e)}")
            self.func.alert_failure(f"加载失败: {str(e)}")
            traceback.print_exc()

    def clear_data(self):
        """清空已加载的数据"""
        self.adata = None
        self.analysis.set_adata(None)
        self.dataset_name = None
        self.dataset_output_dir = None

        self.func.log_clear()
        self.func.log_set_default()

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return
        
        adata = bulk_top_bind.analysis.adata
        if adata is None:
            self.func.log("bulk主页未加载数据")
            return
        
        self.adata = adata
        self.analysis.set_adata(adata)
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir
        
        self.analysis.set_dataset_output_dir(self.dataset_output_dir)
        self.analysis.set_dataset_name(self.dataset_name)
        
        n_samples, n_genes = adata.shape
        
        self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")
        self.func.log(f"样本数: {n_samples}")
        self.func.log(f"基因数: {n_genes}")
        self.func.update_hint_text(self.dataset_name, n_samples, n_genes)
