# -*- coding: utf-8 -*-
"""
UMAP初步作图界面功能绑定脚本 - 主层容器，管理Python/R版本切换
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class ScUmapInitialBind:
    def __init__(self, main_window, sc_umap_initial_ui):
        self.main_window = main_window
        self.sc_umap_initial_ui = sc_umap_initial_ui
        self.py_bind = None
        self.r_bind = None
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.py_initial_analysis.ui_layout_sc_umap_initial_py import ScUmapInitialPyPageUI
            from script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.py_initial_analysis.ui_bind_sc_umap_initial_py import ScUmapInitialPyBind

            py_page = ScUmapInitialPyPageUI(
                self.sc_umap_initial_ui.py_page_container,
                self.sc_umap_initial_ui.screen_width - 220,
                self.sc_umap_initial_ui.screen_height
            )
            self.sc_umap_initial_ui.py_page_layout.addWidget(py_page.analysis_page)
            self.sc_umap_initial_ui.py_ui = py_page
            self.py_bind = ScUmapInitialPyBind(self.main_window, py_page)
        except Exception as e:
            print(f"初始化Python版本UMAP初步作图失败: {e}")
            import traceback
            traceback.print_exc()

        try:
            from script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.r_initial_analysis.ui_layout_sc_umap_initial_r import ScUmapInitialRPageUI
            from script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.r_initial_analysis.ui_bind_sc_umap_initial_r import ScUmapInitialRBind

            r_page = ScUmapInitialRPageUI(
                self.sc_umap_initial_ui.r_page_container,
                self.sc_umap_initial_ui.screen_width - 220,
                self.sc_umap_initial_ui.screen_height
            )
            self.sc_umap_initial_ui.r_page_layout.addWidget(r_page.sc_umap_initial_r_page)
            self.sc_umap_initial_ui.r_ui = r_page
            self.r_bind = ScUmapInitialRBind(self.main_window, r_page)
        except Exception as e:
            print(f"初始化R版本UMAP初步作图失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_nav_buttons()

    def bind_navigation(self):
        if hasattr(self.sc_umap_initial_ui, 'nav_btn_back'):
            self.sc_umap_initial_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page')
            )

    def bind_nav_buttons(self):
        if hasattr(self.sc_umap_initial_ui, 'nav_btn_python'):
            self.sc_umap_initial_ui.nav_btn_python.clicked.connect(lambda: self.switch_to_python())
        if hasattr(self.sc_umap_initial_ui, 'nav_btn_r'):
            self.sc_umap_initial_ui.nav_btn_r.clicked.connect(lambda: self.switch_to_r())

    def switch_to_python(self):
        if hasattr(self.sc_umap_initial_ui, 'content_stack'):
            self.sc_umap_initial_ui.content_stack.setCurrentIndex(0)
            self.sc_umap_initial_ui.nav_btn_python.setChecked(True)
            self.sc_umap_initial_ui.nav_btn_r.setChecked(False)

            sc_top_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
            if self.py_bind and hasattr(self.py_bind, 'sync_data_from_single_cell_main') and sc_top_bind:
                self.py_bind.sync_data_from_single_cell_main(sc_top_bind)

    def switch_to_r(self):
        if hasattr(self.sc_umap_initial_ui, 'content_stack'):
            self.sc_umap_initial_ui.content_stack.setCurrentIndex(1)
            self.sc_umap_initial_ui.nav_btn_r.setChecked(True)
            self.sc_umap_initial_ui.nav_btn_python.setChecked(False)

            sc_top_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
            if self.r_bind and hasattr(self.r_bind, 'sync_data_from_single_cell_main') and sc_top_bind:
                self.r_bind.sync_data_from_single_cell_main(sc_top_bind)

    def sync_data_from_single_cell_main(self, sc_top_bind=None):
        if self.py_bind and hasattr(self.py_bind, 'sync_data_from_single_cell_main'):
            self.py_bind.sync_data_from_single_cell_main(sc_top_bind)
        if self.r_bind and hasattr(self.r_bind, 'sync_data_from_single_cell_main'):
            self.r_bind.sync_data_from_single_cell_main(sc_top_bind)