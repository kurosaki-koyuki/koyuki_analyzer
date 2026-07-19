# -*- coding: utf-8 -*-
"""
UMAP初步作图Python版本前端功能脚本 - 纯前端显示操作
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScUmapInitialPyFunc:
    def __init__(self, analysis_ui, parent_widget=None):
        self.analysis_ui = analysis_ui
        self.parent_widget = parent_widget

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
        combo_widget.blockSignals(False)

    def set_combo_index(self, combo_widget, index):
        combo_widget.blockSignals(True)
        combo_widget.setCurrentIndex(index)
        combo_widget.blockSignals(False)

    def update_data_info(self, info_dict):
        if not hasattr(self.analysis_ui, 'data_info_text'):
            return
        text_edit = self.analysis_ui.data_info_text
        text_edit.clear()
        text_edit.append(f"细胞数: {info_dict.get('cells', 0)}")
        text_edit.append(f"基因数: {info_dict.get('genes', 0)}")
        text_edit.append(f"UMAP键: {info_dict.get('umap_key', '')}")
        text_edit.append(f"数据集: {info_dict.get('dataset', '')}")
        text_edit.append("\n可用注释:")
        for col in info_dict.get('valid_groups', []):
            text_edit.append(f"  - {col}")

    def display_image(self, image_path):
        if not hasattr(self.analysis_ui, 'image_label'):
            return
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.analysis_ui.image_label.setPixmap(pixmap.scaled(
                self.analysis_ui.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def get_current_pixmap(self):
        if not hasattr(self.analysis_ui, 'image_label'):
            return None
        return self.analysis_ui.image_label.pixmap()

    def log(self, message):
        if hasattr(self.analysis_ui, 'status_text'):
            self.analysis_ui.status_text.append(message)

    def clear_log(self):
        if hasattr(self.analysis_ui, 'status_text'):
            self.analysis_ui.status_text.clear()

    def get_save_file_path(self, parent_widget, title, default_name, filter_text):
        save_path, _ = QFileDialog.getSaveFileName(
            parent_widget, title, default_name, filter_text)
        return save_path

    def alert_no_image(self):
        attention(self.parent_widget, "当前没有显示图片")

    def alert_export_success(self, save_path):
        happy(self.parent_widget, f"图片已保存到:\n{save_path}")

    def alert_export_failed(self):
        attention(self.parent_widget, "保存图片失败")

    def alert_export_error(self, error_msg):
        wrong(self.parent_widget, f"导出失败: {str(error_msg)}")