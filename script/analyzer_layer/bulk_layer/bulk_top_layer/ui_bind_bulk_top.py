# -*- coding: utf-8 -*-
"""
bulk分析顶层导航界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.bulk_layer.bulk_top_layer.ui_func_bulk_top import BulkTopFunc
from script.analyzer_layer.bulk_layer.bulk_top_layer.bulk_data_analysis import BulkDataManager
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkTopBind:
    """bulk分析顶层导航界面功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, ui_instance):
        self.parent = parent_window
        self.ui = ui_instance
        self.func = BulkTopFunc(ui_instance, parent_window)
        self.analysis = BulkDataManager()
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_data_loading()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.ui, 'btn_back_bulk'):
            self.ui.btn_back_bulk.clicked.connect(page_intersect.go_to_home)

        if hasattr(self.ui, 'btn_expression'):
            self.ui.btn_expression.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_expr_page'))

        if hasattr(self.ui, 'btn_corre'):
            self.ui.btn_corre.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_corre_page'))

        if hasattr(self.ui, 'btn_cox'):
            self.ui.btn_cox.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_cox_page'))

        if hasattr(self.ui, 'btn_cluster'):
            self.ui.btn_cluster.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_cluster_page'))

        if hasattr(self.ui, 'btn_km'):
            self.ui.btn_km.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_km_page'))

        if hasattr(self.ui, 'btn_wgcna'):
            self.ui.btn_wgcna.clicked.connect(lambda: page_intersect.go_to_page_with_bind('wgcna_page'))

        if hasattr(self.ui, 'btn_immune'):
            self.ui.btn_immune.clicked.connect(self.show_immune_dialog)

    def show_immune_dialog(self):
        """显示bulk免疫分析弹窗"""
        from script.analyzer_layer.bulk_layer.immune_top_layer.immune_dialog import ImmuneDialog
        dialog = ImmuneDialog(self.parent)
        dialog.exec_()

    def bind_data_loading(self):
        """绑定数据加载相关控件"""
        if hasattr(self.ui, 'btn_select_path'):
            self.ui.btn_select_path.clicked.connect(self.select_data_path)

        if hasattr(self.ui, 'btn_load'):
            self.ui.btn_load.clicked.connect(self.load_data)

    def select_data_path(self):
        """扫描数据路径"""
        self.func.log(f"开始扫描数据路径...")
        self.func.log(f"BULK_SCAN_DATA_PATH: {BULK_SCAN_DATA_PATH}")
        self.func.log(f"路径是否存在: {os.path.exists(BULK_SCAN_DATA_PATH)}")
        
        success, files, error = self.analysis.scan_data_folder()
        if not success:
            self.func.log(f"扫描失败: {error}")
            attention(self.parent, error)
            return
        self.func.log(f"扫描成功，找到 {len(files)} 个文件")
        self.func.set_combo_items(self.ui.h5ad_combo, files, keep_selection=False)
        self.func.log(f"已更新下拉框，共 {self.ui.h5ad_combo.count()} 项")

    def load_data(self):
        """加载数据"""
        selected_file = self.ui.h5ad_combo.currentText()
        
        self.func.log("正在加载数据...")
        success, data_info, error = self.analysis.load_data(selected_file)
        
        if not success:
            attention(self.parent, error)
            self.func.log(error)
            return
        
        self.func.update_data_info(data_info)
        self.func.log("数据加载完成")

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.ui, 'music_controller'):
            fix_music_controller_bindings(self, self.ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)