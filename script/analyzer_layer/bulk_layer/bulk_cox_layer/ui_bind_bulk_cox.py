# -*- coding: utf-8 -*-
"""
bulk Cox分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class BulkCoxBind:
    def __init__(self, main_window, bulk_cox_ui):
        self.main_window = main_window
        self.bulk_cox_ui = bulk_cox_ui
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.bulk_cox_ui, 'btn_back_bulk_cox'):
            self.bulk_cox_ui.btn_back_bulk_cox.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return
        
        self.adata = bulk_top_bind.analysis.adata
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir
        
        if self.adata is not None:
            if hasattr(self, 'func') and hasattr(self.func, 'log'):
                self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")
