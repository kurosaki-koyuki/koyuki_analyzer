# -*- coding: utf-8 -*-
"""
bulk Log-rank分析界面功能绑定脚本 - Python版本
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class BulkLogrankBind:
    def __init__(self, main_window, bulk_logrank_ui):
        self.main_window = main_window
        self.bulk_logrank_ui = bulk_logrank_ui
        self.py_bind = None
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        try:
            from script.analyzer_layer.bulk_layer.bulk_logrank_layer.py_diff.ui_layout_bulk_logrank_py import BulkLogrankPyPageUI
            from script.analyzer_layer.bulk_layer.bulk_logrank_layer.py_diff.ui_bind_bulk_logrank_py import BulkLogrankPyBind

            py_page = BulkLogrankPyPageUI(
                self.bulk_logrank_ui.py_page_container,
                self.bulk_logrank_ui.screen_width - 220,
                self.bulk_logrank_ui.screen_height
            )
            self.bulk_logrank_ui.py_page_layout.addWidget(py_page.bulk_logrank_page)
            self.bulk_logrank_ui.py_ui = py_page
            self.py_bind = BulkLogrankPyBind(self.main_window, py_page)
        except Exception as e:
            print(f"初始化Python版本bulk Log-rank分析失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_navigation()

    def bind_navigation(self):
        if hasattr(self.bulk_logrank_ui, 'nav_btn_back'):
            self.bulk_logrank_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('bulk_top_page')
            )

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        if self.py_bind and hasattr(self.py_bind, 'sync_data_from_bulk_main'):
            self.py_bind.sync_data_from_bulk_main(bulk_top_bind)