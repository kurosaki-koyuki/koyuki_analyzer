# -*- coding: utf-8 -*-
"""
bulk差异分析界面功能绑定脚本 - Python版本
全权负责粘合内外，绑定信号 + 编排 analysis 与 func 的协作
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class BulkDiffPyBind:
    def __init__(self, main_window, bulk_diff_ui):
        self.main_window = main_window
        self.bulk_diff_ui = bulk_diff_ui
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()

    def bind_navigation(self):
        if hasattr(self.bulk_diff_ui, 'btn_back_bulk_diff'):
            self.bulk_diff_ui.btn_back_bulk_diff.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

    def sync_data_from_bulk_main(self, bulk_top_bind):
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return

        self.adata = bulk_top_bind.analysis.adata
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir

        if self.adata is not None:
            if hasattr(self, 'func') and hasattr(self.func, 'log'):
                self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")