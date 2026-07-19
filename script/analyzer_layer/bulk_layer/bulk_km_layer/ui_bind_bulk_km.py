# -*- coding: utf-8 -*-
"""
bulk KM曲线界面功能绑定脚本 - 主层容器，管理Python/R版本切换
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class BulkKmBind:
    def __init__(self, main_window, bulk_km_ui):
        self.main_window = main_window
        self.bulk_km_ui = bulk_km_ui
        self.py_bind = None
        self.r_bind = None
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        try:
            from script.analyzer_layer.bulk_layer.bulk_km_layer.py_diff.ui_layout_bulk_km_py import BulkKmPyPageUI
            from script.analyzer_layer.bulk_layer.bulk_km_layer.py_diff.ui_bind_bulk_km_py import BulkKmPyBind

            py_page = BulkKmPyPageUI(
                self.bulk_km_ui.py_page_container,
                self.bulk_km_ui.screen_width - 220,
                self.bulk_km_ui.screen_height
            )
            self.bulk_km_ui.py_page_layout.addWidget(py_page.bulk_km_page)
            self.bulk_km_ui.py_ui = py_page
            self.py_bind = BulkKmPyBind(self.main_window, py_page)
        except Exception as e:
            print(f"初始化Python版本bulk KM曲线失败: {e}")
            import traceback
            traceback.print_exc()

        try:
            from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.ui_layout_bulk_km_r import BulkKmRPageUI
            from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.ui_bind_bulk_km_r import BulkKmRBind

            r_page = BulkKmRPageUI(
                self.bulk_km_ui.r_page_container,
                self.bulk_km_ui.screen_width - 220,
                self.bulk_km_ui.screen_height
            )
            self.bulk_km_ui.r_page_layout.addWidget(r_page.bulk_km_r_page)
            self.bulk_km_ui.r_ui = r_page
            self.r_bind = BulkKmRBind(self.main_window, r_page)
        except Exception as e:
            print(f"初始化R版本bulk KM曲线失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_nav_buttons()

    def bind_navigation(self):
        if hasattr(self.bulk_km_ui, 'nav_btn_back'):
            self.bulk_km_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('bulk_top_page')
            )

    def bind_nav_buttons(self):
        if hasattr(self.bulk_km_ui, 'nav_btn_python'):
            self.bulk_km_ui.nav_btn_python.clicked.connect(lambda: self.switch_to_python())
        if hasattr(self.bulk_km_ui, 'nav_btn_r'):
            self.bulk_km_ui.nav_btn_r.clicked.connect(lambda: self.switch_to_r())

    def switch_to_python(self):
        if hasattr(self.bulk_km_ui, 'content_stack'):
            self.bulk_km_ui.content_stack.setCurrentIndex(0)
            self.bulk_km_ui.nav_btn_python.setChecked(True)
            self.bulk_km_ui.nav_btn_r.setChecked(False)

            bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
            if self.py_bind and hasattr(self.py_bind, 'sync_data_from_bulk_main') and bulk_top_bind:
                self.py_bind.sync_data_from_bulk_main(bulk_top_bind)

    def switch_to_r(self):
        if hasattr(self.bulk_km_ui, 'content_stack'):
            self.bulk_km_ui.content_stack.setCurrentIndex(1)
            self.bulk_km_ui.nav_btn_r.setChecked(True)
            self.bulk_km_ui.nav_btn_python.setChecked(False)

            bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
            if self.r_bind and hasattr(self.r_bind, 'sync_data_from_bulk_main') and bulk_top_bind:
                self.r_bind.sync_data_from_bulk_main(bulk_top_bind)

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        if self.py_bind and hasattr(self.py_bind, 'sync_data_from_bulk_main'):
            self.py_bind.sync_data_from_bulk_main(bulk_top_bind)
        if self.r_bind and hasattr(self.r_bind, 'sync_data_from_bulk_main'):
            self.r_bind.sync_data_from_bulk_main(bulk_top_bind)