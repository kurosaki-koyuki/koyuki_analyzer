# -*- coding: utf-8 -*-
"""
基因集气泡图前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScGenelistBubbleFunc:
    """基因集气泡图前端功能类 - 纯前端显示操作"""

    def __init__(self, genelist_bubble_ui, parent_widget=None):
        self.genelist_bubble_ui = genelist_bubble_ui
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

    def update_bubble_list(self, combo_idx, unique_vals):
        """更新基因集气泡图列表框"""
        if combo_idx >= len(self.genelist_bubble_ui.genelist_bubble_panels):
            return
        panel = self.genelist_bubble_ui.genelist_bubble_panels[combo_idx]
        list_widget = panel['list']
        self.fill_list_widget(list_widget, unique_vals)

    def display_image(self, fig_path):
        """将图片显示到标签"""
        pixmap = QPixmap(fig_path)
        label = self.genelist_bubble_ui.genelist_bubble_image_label
        if label:
            if isinstance(label, ZoomableImageLabel):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap.scaled(
                    label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.genelist_bubble_ui, 'genelist_bubble_log'):
            self.genelist_bubble_ui.genelist_bubble_log.append(message)

    def toggle_collapse(self):
        """切换参数面板折叠状态"""
        collapsed = getattr(self.genelist_bubble_ui, 'genelist_bubble_collapsed', False)
        collapsed = not collapsed
        self.genelist_bubble_ui.genelist_bubble_collapsed = collapsed

        params_frame = getattr(self.genelist_bubble_ui, 'genelist_bubble_params_frame', None)
        collapse_btn = getattr(self.genelist_bubble_ui, 'genelist_bubble_collapse_btn', None)
        right_layout = getattr(self.genelist_bubble_ui, 'genelist_bubble_right_layout', None)

        if params_frame and collapse_btn and right_layout:
            if collapsed:
                params_frame.hide()
                collapse_btn.setText("▶ 展开参数面板")
                right_layout.setStretch(0, 0)
                right_layout.setStretch(1, 3)
            else:
                params_frame.show()
                collapse_btn.setText("▼ 收起参数面板")
                right_layout.setStretch(0, 1)
                right_layout.setStretch(1, 2)

    def save_template(self, template_name, template_data):
        """保存参数模板"""
        if not hasattr(self.genelist_bubble_ui, 'genelist_bubble_param_templates'):
            self.genelist_bubble_ui.genelist_bubble_param_templates = {}

        self.genelist_bubble_ui.genelist_bubble_param_templates[template_name] = template_data

        combo = getattr(self.genelist_bubble_ui, 'genelist_bubble_temp_combo', None)
        if combo:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(list(self.genelist_bubble_ui.genelist_bubble_param_templates.keys()))
            combo.blockSignals(False)

    def load_template(self, template_name):
        """加载参数模板"""
        if not hasattr(self.genelist_bubble_ui, 'genelist_bubble_param_templates'):
            return None
        return self.genelist_bubble_ui.genelist_bubble_param_templates.get(template_name)

    def get_template_names(self):
        """获取所有模板名称"""
        if not hasattr(self.genelist_bubble_ui, 'genelist_bubble_param_templates'):
            return []
        return list(self.genelist_bubble_ui.genelist_bubble_param_templates.keys())

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

    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""