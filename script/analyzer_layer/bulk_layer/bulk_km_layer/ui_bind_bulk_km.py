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
        self.py_geneset_bind = None
        self.r_geneset_bind = None
        self.mode = 'python'        # 'python' | 'r'
        self.type = 'single'        # 'single' | 'geneset'
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

        # ★ 基因集分析（2026-09 新增）：py/r 各一个近副本页
        try:
            from script.analyzer_layer.bulk_layer.bulk_km_layer.py_diff.ui_layout_bulk_km_py_geneset import BulkKmPyGeneSetPageUI
            from script.analyzer_layer.bulk_layer.bulk_km_layer.py_diff.ui_bind_bulk_km_py_geneset import BulkKmPyGeneSetBind

            py_gs_page = BulkKmPyGeneSetPageUI(
                self.bulk_km_ui.py_geneset_page_container,
                self.bulk_km_ui.screen_width - 220,
                self.bulk_km_ui.screen_height
            )
            self.bulk_km_ui.py_geneset_page_layout.addWidget(py_gs_page.bulk_km_py_geneset_page)
            self.bulk_km_ui.py_geneset_ui = py_gs_page
            self.py_geneset_bind = BulkKmPyGeneSetBind(self.main_window, py_gs_page)
        except Exception as e:
            print(f"初始化Python版本基因集KM曲线失败: {e}")
            import traceback
            traceback.print_exc()

        try:
            from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.ui_layout_bulk_km_r_geneset import BulkKmRGeneSetPageUI
            from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.ui_bind_bulk_km_r_geneset import BulkKmRGeneSetBind

            r_gs_page = BulkKmRGeneSetPageUI(
                self.bulk_km_ui.r_geneset_page_container,
                self.bulk_km_ui.screen_width - 220,
                self.bulk_km_ui.screen_height
            )
            self.bulk_km_ui.r_geneset_page_layout.addWidget(r_gs_page.bulk_km_r_geneset_page)
            self.bulk_km_ui.r_geneset_ui = r_gs_page
            self.r_geneset_bind = BulkKmRGeneSetBind(self.main_window, r_gs_page)
        except Exception as e:
            print(f"初始化R版本基因集KM曲线失败: {e}")
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
            self.bulk_km_ui.nav_btn_python.clicked.connect(lambda: self._set_mode('python'))
        if hasattr(self.bulk_km_ui, 'nav_btn_r'):
            self.bulk_km_ui.nav_btn_r.clicked.connect(lambda: self._set_mode('r'))
        if hasattr(self.bulk_km_ui, 'nav_btn_single'):
            self.bulk_km_ui.nav_btn_single.clicked.connect(lambda: self._set_type('single'))
        if hasattr(self.bulk_km_ui, 'nav_btn_geneset'):
            self.bulk_km_ui.nav_btn_geneset.clicked.connect(lambda: self._set_type('geneset'))

    def _page_index(self):
        """4 页：0=py-单基因 1=py-基因集 2=r-单基因 3=r-基因集"""
        mode_idx = 0 if self.mode == 'python' else 1
        type_idx = 0 if self.type == 'single' else 1
        return mode_idx * 2 + type_idx

    def _active_bind(self):
        if self.mode == 'python':
            return self.py_bind if self.type == 'single' else self.py_geneset_bind
        return self.r_bind if self.type == 'single' else self.r_geneset_bind

    def _sync_active(self):
        bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
        active = self._active_bind()
        if active and hasattr(active, 'sync_data_from_bulk_main') and bulk_top_bind:
            active.sync_data_from_bulk_main(bulk_top_bind)

    def _set_mode(self, mode):
        self.mode = mode
        self._apply_nav_and_stack()

    def _set_type(self, type_):
        self.type = type_
        self._apply_nav_and_stack()

    def _apply_nav_and_stack(self):
        ui = self.bulk_km_ui
        if hasattr(ui, 'content_stack'):
            ui.content_stack.setCurrentIndex(self._page_index())
        if hasattr(ui, 'nav_btn_python'):
            ui.nav_btn_python.setChecked(self.mode == 'python')
        if hasattr(ui, 'nav_btn_r'):
            ui.nav_btn_r.setChecked(self.mode == 'r')
        if hasattr(ui, 'nav_btn_single'):
            ui.nav_btn_single.setChecked(self.type == 'single')
        if hasattr(ui, 'nav_btn_geneset'):
            ui.nav_btn_geneset.setChecked(self.type == 'geneset')
        self._sync_active()

    def switch_to_python(self):
        self._set_mode('python')

    def switch_to_r(self):
        self._set_mode('r')

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        for bind in (self.py_bind, self.py_geneset_bind, self.r_bind, self.r_geneset_bind):
            if bind and hasattr(bind, 'sync_data_from_bulk_main'):
                bind.sync_data_from_bulk_main(bulk_top_bind)