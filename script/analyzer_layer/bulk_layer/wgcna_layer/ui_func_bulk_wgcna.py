# -*- coding: utf-8 -*-
"""
bulk WGCNA分析前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel


class BulkWgcnaFunc:
    def __init__(self, wgcna_ui, parent_widget=None):
        self.wgcna_ui = wgcna_ui
        self.parent_widget = parent_widget

    def set_combo_items(self, combo_widget, items, keep_selection=False):
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        list_widget.clear()
        list_widget.addItems(items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def display_image(self, label_widget, fig_or_path):
        if not label_widget:
            return

        if isinstance(fig_or_path, str) and os.path.exists(fig_or_path):
            pixmap = QPixmap(fig_or_path)
        else:
            return

        if isinstance(label_widget, ZoomableImageLabel):
            label_widget.set_pixmap(pixmap)
        else:
            label_widget.setPixmap(pixmap.scaled(
                label_widget.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def clear_image(self, label_widget):
        if label_widget:
            label_widget.clear()

    def log(self, message):
        if hasattr(self.wgcna_ui, 'bulk_wgcna_status_text'):
            self.wgcna_ui.bulk_wgcna_status_text.append(message)
            self.wgcna_ui.bulk_wgcna_status_text.verticalScrollBar().setValue(
                self.wgcna_ui.bulk_wgcna_status_text.verticalScrollBar().maximum()
            )

    def log_clear(self):
        if hasattr(self.wgcna_ui, 'bulk_wgcna_status_text'):
            self.wgcna_ui.bulk_wgcna_status_text.clear()

    def log_set_default(self):
        if hasattr(self.wgcna_ui, 'bulk_wgcna_status_text'):
            self.wgcna_ui.bulk_wgcna_status_text.setText("数据未加载\n请先在bulk主页加载数据")

    def get_save_file_path(self, title, default_name, filter_text):
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    def get_export_size(self):
        width = None
        height = None

        if hasattr(self.wgcna_ui, 'bulk_wgcna_export_width'):
            width_text = str(self.wgcna_ui.bulk_wgcna_export_width.text())
            if width_text:
                try:
                    width = float(width_text)
                except ValueError:
                    width = None

        if hasattr(self.wgcna_ui, 'bulk_wgcna_export_height'):
            height_text = str(self.wgcna_ui.bulk_wgcna_export_height.text())
            if height_text:
                try:
                    height = float(height_text)
                except ValueError:
                    height = None

        return width, height

    def get_selected_groups(self, list_widget):
        selected_groups = []
        if list_widget:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.isSelected():
                    selected_groups.append(item.text())
        return selected_groups