# -*- coding: utf-8 -*-
"""
bulk相关性分析前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkCorreFunc:
    """bulk相关性分析前端功能类 - 纯前端显示操作"""

    def __init__(self, bulk_corre_ui, parent_widget=None):
        self.bulk_corre_ui = bulk_corre_ui
        self.parent_widget = parent_widget

    # ---------- 列表/下拉框内容更新 ----------

    def set_combo_items(self, combo_widget, items, keep_selection=False):
        """安全地设置下拉框内容"""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        """填充列表控件并可选全选"""
        list_widget.clear()
        list_widget.addItems(items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def fill_checkable_list_widget(self, list_widget, items, check_all=True):
        """填充带复选框的列表控件"""
        list_widget.clear()
        for item_text in items:
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if check_all else Qt.Unchecked)
            list_widget.addItem(item)

    # ---------- 图片显示 ----------

    def display_image(self, label_widget, image_path):
        """在标签上显示图片"""
        if not label_widget or not os.path.exists(image_path):
            return

        pixmap = QPixmap(image_path)

        if isinstance(label_widget, ZoomableImageLabel):
            label_widget.setPixmap(pixmap)
        else:
            label_widget.setPixmap(pixmap)
            label_widget.setScaledContents(True)

    def clear_image(self, label_widget):
        """清空标签上的图片"""
        if label_widget:
            if isinstance(label_widget, ZoomableImageLabel):
                label_widget.clear()
            else:
                label_widget.clear()

    # ---------- 日志功能 ----------

    def log(self, message):
        """添加日志"""
        if hasattr(self.bulk_corre_ui, 'bulk_corre_status_text'):
            current_text = self.bulk_corre_ui.bulk_corre_status_text.toPlainText()
            self.bulk_corre_ui.bulk_corre_status_text.setText(current_text + message + "\n")

    def log_clear(self):
        """清空日志"""
        if hasattr(self.bulk_corre_ui, 'bulk_corre_status_text'):
            self.bulk_corre_ui.bulk_corre_status_text.clear()

    def log_set_default(self):
        """设置默认日志文本"""
        if hasattr(self.bulk_corre_ui, 'bulk_corre_status_text'):
            self.bulk_corre_ui.bulk_corre_status_text.setText("数据未加载\n请扫描数据路径")

    # ---------- 数据信息更新 ----------

    def update_hint_text(self, dataset_name, n_samples, n_genes):
        """更新提示文本（显示在日志框顶部）"""
        if hasattr(self.bulk_corre_ui, 'bulk_corre_status_text'):
            self.bulk_corre_ui.bulk_corre_status_text.setText(
                f"数据: {dataset_name}\n样本数: {n_samples}\n基因数: {n_genes}\n\n请选择相关性分析类型"
            )

    # ---------- 前端提示信息 ----------

    def alert_error(self, message):
        """显示错误提示"""
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def alert_failure(self, message):
        """显示失败提示"""
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_success(self, message):
        """显示成功提示"""
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    # ---------- 文件对话框 ----------

    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text
            )
            return save_path
        return None

    def get_open_file_path(self, title, filter_text):
        """弹出打开文件对话框，返回用户选择的路径"""
        if self.parent_widget:
            open_path, _ = QFileDialog.getOpenFileName(
                self.parent_widget, title, "", filter_text
            )
            return open_path
        return None