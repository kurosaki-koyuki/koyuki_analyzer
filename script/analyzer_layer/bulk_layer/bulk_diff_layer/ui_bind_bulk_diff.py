# -*- coding: utf-8 -*-
"""
bulk差异分析界面功能绑定脚本 - 主层容器，管理Python/R版本切换
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class BulkDiffBind:
    def __init__(self, main_window, bulk_diff_ui):
        self.main_window = main_window
        self.bulk_diff_ui = bulk_diff_ui
        self.py_bind = None
        self.r_bind = None
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        try:
            from script.analyzer_layer.bulk_layer.bulk_diff_layer.py_diff.ui_layout_bulk_diff_py import BulkDiffPyPageUI
            from script.analyzer_layer.bulk_layer.bulk_diff_layer.py_diff.ui_bind_bulk_diff_py import BulkDiffPyBind

            py_page = BulkDiffPyPageUI(
                self.bulk_diff_ui.py_page_container,
                self.bulk_diff_ui.screen_width - 220,
                self.bulk_diff_ui.screen_height
            )
            self.bulk_diff_ui.py_page_layout.addWidget(py_page.bulk_diff_page)
            self.bulk_diff_ui.py_ui = py_page
            self.py_bind = BulkDiffPyBind(self.main_window, py_page)
        except Exception as e:
            print(f"初始化Python版本bulk差异分析失败: {e}")
            import traceback
            traceback.print_exc()

        try:
            from script.analyzer_layer.bulk_layer.bulk_diff_layer.r_diff.ui_layout_bulk_diff_r import BulkDiffRPageUI
            from script.analyzer_layer.bulk_layer.bulk_diff_layer.r_diff.ui_bind_bulk_diff_r import BulkDiffRBind

            r_page = BulkDiffRPageUI(
                self.bulk_diff_ui.r_page_container,
                self.bulk_diff_ui.screen_width - 220,
                self.bulk_diff_ui.screen_height
            )
            self.bulk_diff_ui.r_page_layout.addWidget(r_page.bulk_diff_page)
            self.bulk_diff_ui.r_ui = r_page
            self.r_bind = BulkDiffRBind(self.main_window, r_page)
        except Exception as e:
            print(f"初始化R版本bulk差异分析失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_nav_buttons()

    def bind_navigation(self):
        if hasattr(self.bulk_diff_ui, 'nav_btn_back'):
            self.bulk_diff_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('bulk_top_page')
            )

    def bind_nav_buttons(self):
        if hasattr(self.bulk_diff_ui, 'nav_btn_python'):
            self.bulk_diff_ui.nav_btn_python.clicked.connect(lambda: self.switch_to_python())
        if hasattr(self.bulk_diff_ui, 'nav_btn_r'):
            self.bulk_diff_ui.nav_btn_r.clicked.connect(lambda: self.switch_to_r())

    def switch_to_python(self):
        if hasattr(self.bulk_diff_ui, 'content_stack'):
            self.bulk_diff_ui.content_stack.setCurrentIndex(0)
            self.bulk_diff_ui.nav_btn_python.setChecked(True)
            self.bulk_diff_ui.nav_btn_r.setChecked(False)

            bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
            if self.py_bind and hasattr(self.py_bind, 'sync_data_from_bulk_main') and bulk_top_bind:
                self.py_bind.sync_data_from_bulk_main(bulk_top_bind)

    def switch_to_r(self):
        if hasattr(self.bulk_diff_ui, 'content_stack'):
            self.bulk_diff_ui.content_stack.setCurrentIndex(1)
            self.bulk_diff_ui.nav_btn_r.setChecked(True)
            self.bulk_diff_ui.nav_btn_python.setChecked(False)

            bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
            if self.r_bind and hasattr(self.r_bind, 'sync_data_from_bulk_main') and bulk_top_bind:
                self.r_bind.sync_data_from_bulk_main(bulk_top_bind)

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        if self.py_bind and hasattr(self.py_bind, 'sync_data_from_bulk_main'):
            self.py_bind.sync_data_from_bulk_main(bulk_top_bind)
        if self.r_bind and hasattr(self.r_bind, 'sync_data_from_bulk_main'):
            self.r_bind.sync_data_from_bulk_main(bulk_top_bind)