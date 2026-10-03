# -*- coding: utf-8 -*-
"""
相关性散点图界面功能绑定脚本
"""

from script.utils_layer.page_intersect import page_intersect


class BulkCorredotBind:
    def __init__(self, main_window, bulk_corredot_ui):
        self.main_window = main_window
        self.parent = main_window
        self.bulk_corredot_ui = bulk_corredot_ui
        self.adata = None
        self.dataset_name = None
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.bulk_corredot_ui, 'btn_back_bulk_corredot'):
            self.bulk_corredot_ui.btn_back_bulk_corredot.clicked.connect(lambda: page_intersect.go_to_parent_page('bulk_corredot_page'))

    def sync_data_from_corre(self, corre_bind=None):
        """从相关性分析页面同步数据"""
        try:
            if corre_bind is None:
                corre_bind = getattr(self.parent, 'bulk_corre_bind', None)
            
            if corre_bind is None:
                return

            if hasattr(corre_bind, 'adata') and corre_bind.adata is not None:
                self.adata = corre_bind.adata
            
            if hasattr(corre_bind, 'dataset_name'):
                self.dataset_name = corre_bind.dataset_name

        except Exception as e:
            print(f"相关性散点图同步数据时出错: {str(e)}")