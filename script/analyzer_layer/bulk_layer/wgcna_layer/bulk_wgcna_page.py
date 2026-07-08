# -*- coding: utf-8 -*-
"""
bulk WGCNA分析页面主入口
注册页面路由，初始化UI和绑定层
"""

from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.bulk_layer.wgcna_layer.ui_layout_bulk_wgcna import BulkWgcnaPageUI
from script.analyzer_layer.bulk_layer.wgcna_layer.ui_bind_bulk_wgcna import BulkWgcnaPageBind


class BulkWgcnaPage:
    PAGE_NAME = "bulk_wgcna"

    def __init__(self, parent_widget, main_window):
        self.parent = parent_widget
        self.main_window = main_window
        self.screen_width = main_window.width()
        self.screen_height = main_window.height()

        self.ui = BulkWgcnaPageUI(parent_widget, self.screen_width, self.screen_height)
        self.bind = BulkWgcnaPageBind(self.ui, main_window)

        self.page_widget = self.ui.bulk_wgcna_page

    def get_widget(self):
        return self.page_widget

    def update_styles(self):
        self.ui.update_styles()

    def update_background(self):
        self.ui.update_background()


def register_bulk_wgcna_page():
    page_intersect.register_page(
        "bulk_wgcna_page",
        lambda parent, main_window: BulkWgcnaPage(parent, main_window).get_widget()
    )


register_bulk_wgcna_page()