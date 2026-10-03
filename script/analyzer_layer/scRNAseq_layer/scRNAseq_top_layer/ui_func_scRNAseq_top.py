# -*- coding: utf-8 -*-
"""
单细胞分析顶层导航界面前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScRNAseqTopFunc:
    """单细胞分析顶层导航界面前端功能类 - 纯前端显示操作"""

    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget

    def update_styles(self):
        """更新界面样式"""
        if hasattr(self.ui, 'update_styles'):
            self.ui.update_styles()

    def update_background(self):
        """更新背景图"""
        if hasattr(self.ui, 'update_background'):
            self.ui.update_background()
    
    def log(self, message):
        """在状态文本框中记录日志"""
        if hasattr(self.ui, 'status_text') and self.ui.status_text:
            self.ui.status_text.append(message)
    
    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全地设置下拉框内容，可选保持当前选中项"""
        if combo_widget is None:
            return
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
    
    def update_data_info(self, info_dict):
        """更新数据信息到状态框"""
        if not info_dict:
            return
        self.log(f"数据集: {info_dict.get('dataset', '')}")
        self.log(f"细胞数: {info_dict.get('cells', 0)}")
        self.log(f"基因数: {info_dict.get('genes', 0)}")
        self.log(f"UMAP键: {info_dict.get('umap_key', '')}")
        if info_dict.get('valid_groups'):
            self.log("可用注释: " + ", ".join(info_dict['valid_groups']))