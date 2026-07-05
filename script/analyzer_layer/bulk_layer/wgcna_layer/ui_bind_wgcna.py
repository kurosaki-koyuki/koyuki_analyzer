# -*- coding: utf-8 -*-
"""
bulk WGCNA分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class WgcnaBind:
    def __init__(self, main_window, wgcna_ui):
        self.main_window = main_window
        self.wgcna_ui = wgcna_ui
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.wgcna_ui, 'btn_back_wgcna'):
            self.wgcna_ui.btn_back_wgcna.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return
        
        self.adata = bulk_top_bind.analysis.adata
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir
