# -*- coding: utf-8 -*-
"""
小提琴图前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ViolinFunc:
    """小提琴图前端功能类 - 纯前端显示操作"""

    def __init__(self, violin_ui, parent_widget=None):
        self.violin_ui = violin_ui
        self.parent_widget = parent_widget

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全地设置下拉框内容，可选保持当前选中项"""
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
        combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        """填充列表控件并可选全选"""
        list_widget.clear()
        list_widget.addItems(items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def update_main_list(self, group, unique_vals):
        """更新主注释列表和配对列表"""
        self.fill_list_widget(self.violin_ui.violin_main_list, unique_vals)
        if hasattr(self.violin_ui, 'violin_pairwise_list'):
            self._update_pairwise_list(unique_vals)

    def update_filter1_list(self, group, unique_vals):
        """更新筛选1列表"""
        if hasattr(self.violin_ui, 'violin_filter1_list'):
            self.fill_list_widget(self.violin_ui.violin_filter1_list, unique_vals)

    def update_filter2_list(self, group, unique_vals):
        """更新筛选2列表"""
        if hasattr(self.violin_ui, 'violin_filter2_list'):
            self.fill_list_widget(self.violin_ui.violin_filter2_list, unique_vals)

    def _update_pairwise_list(self, unique_vals):
        """更新两两比较列表"""
        pairs = list(itertools.combinations(unique_vals, 2))
        self.violin_ui.violin_pairwise_list.clear()
        for pair in pairs:
            self.violin_ui.violin_pairwise_list.addItem(f"{pair[0]} vs {pair[1]}")
        for i in range(self.violin_ui.violin_pairwise_list.count()):
            self.violin_ui.violin_pairwise_list.item(i).setSelected(True)

    def display_image(self, fig_path, fig_type='violin_box'):
        """将图片显示到对应标签页"""
        pixmap = QPixmap(fig_path)
        label_map = {
            'violin_box': getattr(self.violin_ui, 'violin_box_label', None),
            'box': getattr(self.violin_ui, 'violin_box_only_label', None),
            'violin': getattr(self.violin_ui, 'violin_only_label', None)
        }
        label = label_map.get(fig_type)
        if label:
            if isinstance(label, ZoomableImageLabel):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap.scaled(
                    label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.violin_ui, 'violin_log'):
            self.violin_ui.violin_log.append(message)

    def get_export_size(self):
        """获取导出宽高（从界面输入框读取）"""
        width = None
        height = None

        if hasattr(self.violin_ui, 'violin_export_width'):
            width_text = str(self.violin_ui.violin_export_width.value())
            if width_text:
                try:
                    width = float(width_text)
                except ValueError:
                    width = None

        if hasattr(self.violin_ui, 'violin_export_height'):
            height_text = str(self.violin_ui.violin_export_height.value())
            if height_text:
                try:
                    height = float(height_text)
                except ValueError:
                    height = None

        return width, height

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
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""