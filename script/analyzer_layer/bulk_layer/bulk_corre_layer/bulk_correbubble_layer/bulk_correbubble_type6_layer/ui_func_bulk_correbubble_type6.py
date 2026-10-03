# -*- coding: utf-8 -*-
"""
bulk相关性气泡图前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkCorreBubbleFunc:
    """bulk相关性气泡图前端功能类 - 纯前端显示操作"""

    def __init__(self, bulk_correbubble_ui, parent_widget=None):
        self.bulk_correbubble_ui = bulk_correbubble_ui
        self.parent_widget = parent_widget

    # ---------- 控件内容操作 ----------

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
            # 使用ZoomableImageLabel的自定义方法（小写set_pixmap），支持自动缩放和居中
            label_widget.set_pixmap(pixmap)
        else:
            label_widget.setPixmap(pixmap)
            label_widget.setScaledContents(True)

    def clear_image(self, label_widget):
        """清空标签上的图片"""
        if label_widget:
            if isinstance(label_widget, ZoomableImageLabel):
                # 使用自定义方法清空
                label_widget._original_pixmap = None
                label_widget._scaled_pixmap = None
                label_widget.clear()
                label_widget.update()
            else:
                label_widget.clear()

    # ---------- 日志功能 ----------

    def log(self, message):
        """添加日志"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_status_text'):
            current_text = self.bulk_correbubble_ui.correbubble_status_text.toPlainText()
            self.bulk_correbubble_ui.correbubble_status_text.setText(current_text + message + "\n")

    def log_clear(self):
        """清空日志"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_status_text'):
            self.bulk_correbubble_ui.correbubble_status_text.clear()

    def log_set_default(self):
        """设置默认日志文本"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_status_text'):
            self.bulk_correbubble_ui.correbubble_status_text.setText("数据未加载\n请在相关性分析页面加载数据后跳转")

    # ---------- 数据信息更新 ----------

    def update_hint_text(self, dataset_name, n_samples, n_genes):
        """更新提示文本"""
        hint_text = f"数据: {dataset_name}\n样本数: {n_samples}\n基因数: {n_genes}\n\n请输入基因列表后点击运行"
        if hasattr(self.bulk_correbubble_ui, 'correbubble_status_text'):
            self.bulk_correbubble_ui.correbubble_status_text.setText(hint_text)

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

    # ---------- 基因列表操作 ----------

    def get_gene_list(self):
        """获取用户输入的基因列表"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_gene_input'):
            text = self.bulk_correbubble_ui.correbubble_gene_input.toPlainText()
            genes = [g.strip() for g in text.split('\n') if g.strip()]
            return genes
        return []

    def set_gene_list(self, genes):
        """设置基因列表"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_gene_input'):
            text = '\n'.join(genes)
            self.bulk_correbubble_ui.correbubble_gene_input.setPlainText(text)

    def clear_gene_list(self):
        """清空基因列表"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_gene_input'):
            self.bulk_correbubble_ui.correbubble_gene_input.clear()

    # ---------- 参数控件读取 ----------

    def get_plot_title(self):
        """获取图表标题"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_title_input'):
            text = self.bulk_correbubble_ui.correbubble_title_input.text()
            return text if text.strip() else "Gene Correlation"
        return "Gene Correlation"

    def get_title_size(self):
        """获取标题字体大小"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_title_size'):
            # 直接从lineEdit读取值，确保获取最新输入
            try:
                return int(self.bulk_correbubble_ui.correbubble_title_size.line_edit.text())
            except:
                return self.bulk_correbubble_ui.correbubble_title_size.value()
        return 14

    def get_axis_text_size(self):
        """获取基因名字体大小"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_axis_size'):
            # 直接从lineEdit读取值，确保获取最新输入
            try:
                return int(self.bulk_correbubble_ui.correbubble_axis_size.line_edit.text())
            except:
                return self.bulk_correbubble_ui.correbubble_axis_size.value()
        return 10

    def get_width_ratio(self):
        """获取宽度比例 (0-1)"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_width_ratio'):
            # 直接从lineEdit读取值
            try:
                return int(self.bulk_correbubble_ui.correbubble_width_ratio.line_edit.text()) / 100.0
            except:
                return self.bulk_correbubble_ui.correbubble_width_ratio.value() / 100.0
        return 1.0

    def get_height_ratio(self):
        """获取高度比例 (0-1)"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_height_ratio'):
            # 直接从lineEdit读取值
            try:
                return int(self.bulk_correbubble_ui.correbubble_height_ratio.line_edit.text()) / 100.0
            except:
                return self.bulk_correbubble_ui.correbubble_height_ratio.value() / 100.0
        return 1.0

    def get_show_sig(self):
        """获取是否显示显著性"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_show_sig'):
            return self.bulk_correbubble_ui.correbubble_show_sig.isChecked()
        return True

    def get_anno_size(self):
        """获取注释大小"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_anno_size'):
            # 直接从lineEdit读取值
            try:
                return int(self.bulk_correbubble_ui.correbubble_anno_size.line_edit.text()) / 10.0
            except:
                return self.bulk_correbubble_ui.correbubble_anno_size.value() / 10.0
        return 4.5

    def get_legend_size(self):
        """获取图例条大小"""
        if hasattr(self.bulk_correbubble_ui, 'correbubble_legend_size'):
            # 直接从lineEdit读取值
            try:
                return int(self.bulk_correbubble_ui.correbubble_legend_size.line_edit.text()) / 10.0
            except:
                return self.bulk_correbubble_ui.correbubble_legend_size.value() / 10.0
        return 0.5
