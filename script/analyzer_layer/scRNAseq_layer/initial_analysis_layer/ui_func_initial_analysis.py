# -*- coding: utf-8 -*-
"""
初步分析前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class InitialAnalysisFunc:
    """初步分析前端功能类 - 纯前端显示操作"""

    def __init__(self, analysis_ui, parent_widget=None):
        self.analysis_ui = analysis_ui
        self.parent_widget = parent_widget

    # ---------- 下拉框/列表内容更新 ----------

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全地设置下拉框内容，可选保持当前选中项"""
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
        combo_widget.blockSignals(False)

    def set_combo_index(self, combo_widget, index):
        """安全地设置下拉框索引"""
        combo_widget.blockSignals(True)
        combo_widget.setCurrentIndex(index)
        combo_widget.blockSignals(False)

    # ---------- 数据信息显示 ----------

    def update_data_info(self, info_dict):
        """更新数据信息文本框
        info_dict 示例: {'cells': 1000, 'genes': 2000, 'umap_key': 'X_umap',
                         'dataset': 'name', 'valid_groups': ['a', 'b']}
        """
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

    # ---------- 图片显示 ----------

    def display_image(self, image_path):
        """将图片显示到 image_label 上"""
        if not hasattr(self.analysis_ui, 'image_label'):
            return
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.analysis_ui.image_label.setPixmap(pixmap.scaled(
                self.analysis_ui.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def get_current_pixmap(self):
        """获取当前 image_label 上的 pixmap"""
        if not hasattr(self.analysis_ui, 'image_label'):
            return None
        return self.analysis_ui.image_label.pixmap()

    # ---------- 日志 ----------

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.analysis_ui, 'status_text'):
            self.analysis_ui.status_text.append(message)

    def clear_log(self):
        """清空日志"""
        if hasattr(self.analysis_ui, 'status_text'):
            self.analysis_ui.status_text.clear()

    # ---------- 文件对话框 ----------

    def get_save_file_path(self, parent_widget, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径"""
        save_path, _ = QFileDialog.getSaveFileName(
            parent_widget, title, default_name, filter_text)
        return save_path

    # ---------- 导出提示信息 ----------

    def alert_no_image(self):
        """提示没有显示图片"""
        attention(self.parent_widget, "当前没有显示图片")

    def alert_export_success(self, save_path):
        """提示导出成功"""
        happy(self.parent_widget, f"图片已保存到:\n{save_path}")

    def alert_export_failed(self):
        """提示导出失败"""
        attention(self.parent_widget, "保存图片失败")

    def alert_export_error(self, error_msg):
        """提示导出错误"""
        wrong(self.parent_widget, f"导出失败: {str(error_msg)}")
