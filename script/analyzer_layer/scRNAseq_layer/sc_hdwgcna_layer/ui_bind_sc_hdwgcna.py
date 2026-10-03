# -*- coding: utf-8 -*-
"""
scRNAseq hdWGCNA分析界面功能绑定脚本 - 主层容器，管理R版本
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class ScHdWgcnaBind:
    def __init__(self, main_window, sc_hdwgcna_ui):
        self.main_window = main_window
        self.sc_hdwgcna_ui = sc_hdwgcna_ui
        self.r_bind = None
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_hdwgcna_layer.r_hdwgcna.ui_layout_sc_hdwgcna import ScHdWgcnaPageUI as RScHdWgcnaPageUI
            from script.analyzer_layer.scRNAseq_layer.sc_hdwgcna_layer.r_hdwgcna.ui_bind_sc_hdwgcna import ScHdWgcnaBind as RScHdWgcnaBind

            r_page = RScHdWgcnaPageUI(
                self.sc_hdwgcna_ui.r_page_container,
                self.sc_hdwgcna_ui.screen_width - 220,
                self.sc_hdwgcna_ui.screen_height
            )
            self.sc_hdwgcna_ui.r_page_layout.addWidget(r_page.sc_hdwgcna_page)
            self.r_bind = RScHdWgcnaBind(self.main_window, r_page)
        except Exception as e:
            print(f"初始化R版本hdWGCNA失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_nav_buttons()

    def bind_navigation(self):
        if hasattr(self.sc_hdwgcna_ui, 'nav_btn_back'):
            self.sc_hdwgcna_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page')
            )

    def bind_nav_buttons(self):
        if hasattr(self.sc_hdwgcna_ui, 'nav_btn_r'):
            self.sc_hdwgcna_ui.nav_btn_r.clicked.connect(lambda: self.switch_to_r())

    def switch_to_r(self):
        if hasattr(self.sc_hdwgcna_ui, 'content_stack'):
            self.sc_hdwgcna_ui.content_stack.setCurrentIndex(0)
            self.sc_hdwgcna_ui.nav_btn_r.setChecked(True)

            single_cell_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
            if self.r_bind and hasattr(self.r_bind, 'sync_data_from_single_cell_main') and single_cell_bind:
                self.r_bind.sync_data_from_single_cell_main(single_cell_bind)

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        if self.r_bind and hasattr(self.r_bind, 'sync_data_from_single_cell_main'):
            self.r_bind.sync_data_from_single_cell_main(single_cell_bind)
