# -*- coding: utf-8 -*-
"""
scRNAseq Monocle数据加载类子层 - 前端功能层
负责：日志、下拉框更新、图片渲染、提示框
"""

import os
from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, get_stylesheet_for_widget
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScMonocleLoadingFunc:
    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget if parent_widget else ui_instance.sc_monocle_loading_page
        self._test_plot_path = None

    def log(self, message):
        if hasattr(self.ui, 'loading_log'):
            current_text = self.ui.loading_log.toPlainText()
            new_text = current_text + "\n" + message if current_text else message
            self.ui.loading_log.setPlainText(new_text)
            self.ui.loading_log.verticalScrollBar().setValue(
                self.ui.loading_log.verticalScrollBar().maximum()
            )

    def set_combo_items(self, combo, items, keep_selection=False):
        """更新下拉框选项"""
        if combo is None:
            return
        current_text = combo.currentText() if keep_selection else None
        combo.blockSignals(True)
        combo.clear()
        if not items:
            combo.addItem("未找到rds文件")
        else:
            for item in items:
                combo.addItem(item)
        if keep_selection and current_text:
            idx = combo.findText(current_text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def display_test_image(self, image_path):
        """显示测试图"""
        self._test_plot_path = image_path
        if not hasattr(self.ui, 'test_plot_label'):
            return
        label = self.ui.test_plot_label
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignCenter)
        else:
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(None)
            else:
                label.clear()

    def update_data_info(self, info):
        """更新数据信息显示"""
        if hasattr(self.ui, 'data_info_text'):
            text = f"数据集: {info.get('dataset', '未知')}\n"
            text += f"rds路径: {info.get('rds_path', '未知')}\n"
            text += f"测试图: {info.get('test_plot', '未生成')}"
            self.ui.data_info_text.setPlainText(text)

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))
