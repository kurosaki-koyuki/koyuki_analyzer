# -*- coding: utf-8 -*-
"""
CellChat数据加载类界面功能绑定脚本
"""

import os
from PyQt5.QtCore import Qt
from script.utils_layer.import_config import *
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_loading_layer.ui_func_sc_cellchat_loading import ScCellChatLoadingFunc


class ScCellChatLoadingBind:
    def __init__(self, main_window, sc_cellchat_loading_ui):
        self.main_window = main_window
        self.ui = sc_cellchat_loading_ui
        self.func = ScCellChatLoadingFunc(sc_cellchat_loading_ui, main_window)
        self.bind_functions()
    
    def bind_functions(self):
        """绑定所有功能"""
        try:
            # 扫描按钮
            if hasattr(self.ui, 'btn_scan'):
                self.ui.btn_scan.clicked.connect(self.on_scan_clicked)
                print("CellChat Loading: 扫描按钮已绑定")
            
            # 加载按钮
            if hasattr(self.ui, 'btn_load'):
                self.ui.btn_load.clicked.connect(self.on_load_clicked)
                print("CellChat Loading: 加载按钮已绑定")
            
            # RDS列表选择变化
            if hasattr(self.ui, 'list_rds_files'):
                self.ui.list_rds_files.itemSelectionChanged.connect(self.on_rds_selection_changed)
                print("CellChat Loading: RDS列表选择事件已绑定")
        except Exception as e:
            print(f"CellChat Loading: 绑定失败: {e}")
            import traceback
            traceback.print_exc()
    
    def on_scan_clicked(self):
        """扫描按钮点击"""
        try:
            print("CellChat Loading: 扫描按钮被点击")
            self.func.scan_rds_files()
        except Exception as e:
            print(f"CellChat Loading: 扫描失败: {e}")
            import traceback
            traceback.print_exc()
    
    def on_rds_selection_changed(self):
        """RDS文件选择变化"""
        try:
            if hasattr(self.ui, 'list_rds_files'):
                selected_items = self.ui.list_rds_files.selectedItems()
                if selected_items:
                    if hasattr(self.ui, 'btn_load'):
                        self.ui.btn_load.setEnabled(True)
                        print("CellChat Loading: 文件已选中，加载按钮已启用")
                else:
                    if hasattr(self.ui, 'btn_load'):
                        self.ui.btn_load.setEnabled(False)
        except Exception as e:
            print(f"CellChat Loading: 选择变化处理失败: {e}")
    
    def on_load_clicked(self):
        """加载按钮点击"""
        try:
            print("CellChat Loading: 加载按钮被点击")
            if hasattr(self.ui, 'list_rds_files'):
                selected_items = self.ui.list_rds_files.selectedItems()
                if selected_items:
                    item = selected_items[0]
                    rds_path = item.data(Qt.UserRole)
                    print(f"CellChat Loading: 选中的RDS路径: {rds_path}")
                    if rds_path:
                        self.func.load_rds_file(rds_path)
                        self.func.alert_success("RDS文件加载完成")
                    else:
                        self.func.alert_error("RDS路径无效")
                else:
                    self.func.alert_error("请先选择一个RDS文件")
        except Exception as e:
            print(f"CellChat Loading: 加载失败: {e}")
            import traceback
            traceback.print_exc()
            self.func.alert_failure(f"加载失败: {e}")
    
    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从scRNAseq主页同步数据（透传给子层）"""
        pass
    
    def on_page_activated(self):
        """页面激活时的回调"""
        pass
