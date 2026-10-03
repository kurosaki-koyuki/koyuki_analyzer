# -*- coding: utf-8 -*-
"""
scRNAseq Monocle目的基因分析子层Func脚本
负责UI辅助方法：日志、图片显示、按钮状态等
"""

import os

from PyQt5.QtWidgets import QLabel, QTextEdit
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, create_styled_text_edit
)
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScMonocleTargetgeneFunc:
    def __init__(self, ui_instance, parent_widget=None):
        self.sc_monocle_targetgene_ui = ui_instance
        self.ui = ui_instance
        self.parent_widget = parent_widget if parent_widget else ui_instance.sc_monocle_targetgene_page
        
        self._output_image_label = None
        
        self.log_text_edit = create_styled_text_edit(read_only=True)
        self.log_text_edit.setMaximumHeight(150)

    def log(self, msg):
        """输出日志"""
        if hasattr(self.ui, 'log_text_edit') and self.ui.log_text_edit:
            self.ui.log_text_edit.append(msg)

    def alert_error(self, msg):
        """显示错误弹窗（使用emoji_trigger系统）"""
        if self.parent_widget:
            attention(self.parent_widget, str(msg))

    def alert_success(self, msg):
        """显示成功弹窗（使用emoji_trigger系统）"""
        if self.parent_widget:
            happy(self.parent_widget, str(msg))

    def alert_failure(self, msg):
        """显示失败弹窗（使用emoji_trigger系统）"""
        if self.parent_widget:
            wrong(self.parent_widget, str(msg))

    def show_plot_image(self, image_path):
        """显示趋势图图片"""
        if hasattr(self.ui, 'plot_image_label') and image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if hasattr(self.ui.plot_image_label, 'set_pixmap'):
                self.ui.plot_image_label.set_pixmap(pixmap)
            else:
                self.ui.plot_image_label.setPixmap(pixmap)

    def set_run_button_enabled(self, enabled):
        """启用/禁用运行按钮"""
        if hasattr(self.ui, 'btn_run_plot'):
            self.ui.btn_run_plot.setEnabled(enabled)

    def update_data_info(self, info_dict):
        """更新数据信息显示"""
        if hasattr(self.ui, 'data_info_text'):
            text = f"数据集: {info_dict.get('dataset', '未共享')}\n"
            text += f"RDS路径: {info_dict.get('rds_path', '请先加载')}"
            self.ui.data_info_text.setText(text)

    def get_gene_list_from_input(self):
        """从输入框获取基因列表"""
        if hasattr(self.ui, 'gene_input_edit'):
            text = self.ui.gene_input_edit.toPlainText().strip()
            if not text:
                return []
            genes = [g.strip() for g in text.split('\n') if g.strip()]
            return genes
        return []