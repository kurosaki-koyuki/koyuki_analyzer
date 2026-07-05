# -*- coding: utf-8 -*-
"""
bulk表达量分析前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkExprFunc:
    """bulk表达量分析前端功能类 - 纯前端显示操作"""

    def __init__(self, bulk_expr_ui, parent_widget=None):
        self.bulk_expr_ui = bulk_expr_ui
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

    def update_clinical_combo(self, columns):
        """更新分类列下拉框"""
        self.set_combo_items(self.bulk_expr_ui.bulk_clinical_combo, ["全部"] + columns)

    def update_group_list(self, groups):
        """更新组别列表"""
        self.fill_list_widget(self.bulk_expr_ui.bulk_group_list, groups)

    def update_clinical_col_list(self, columns):
        """更新分类列多选列表"""
        self.fill_list_widget(self.bulk_expr_ui.bulk_clinical_col_list, columns)

    def update_pairwise_list(self, pairs):
        """更新两两比较列表"""
        self.bulk_expr_ui.bulk_pairwise_list.clear()
        for pair in pairs:
            self.bulk_expr_ui.bulk_pairwise_list.addItem(f"{pair[0]} vs {pair[1]}")
        for i in range(self.bulk_expr_ui.bulk_pairwise_list.count()):
            self.bulk_expr_ui.bulk_pairwise_list.item(i).setSelected(True)

    def update_filter_combo(self, combo_widget, values):
        """更新筛选下拉框"""
        self.set_combo_items(combo_widget, values)

    def update_filter_list(self, list_widget, values):
        """更新筛选列表"""
        self.fill_list_widget(list_widget, values)

    # ---------- 界面状态控制 ----------

    def show_clinical_col_list(self, show=True):
        """显示/隐藏分类列多选列表"""
        if show:
            self.bulk_expr_ui.bulk_clinical_col_list_label.show()
            self.bulk_expr_ui.bulk_clinical_col_list.show()
            self.bulk_expr_ui.bulk_group_list_label.hide()
            self.bulk_expr_ui.bulk_group_list.hide()
        else:
            self.bulk_expr_ui.bulk_clinical_col_list_label.hide()
            self.bulk_expr_ui.bulk_clinical_col_list.hide()
            self.bulk_expr_ui.bulk_group_list_label.show()
            self.bulk_expr_ui.bulk_group_list.show()

    def enable_pairwise_controls(self, enable=True):
        """启用/禁用两两比较控件"""
        if hasattr(self.bulk_expr_ui, 'bulk_pairwise_enable'):
            self.bulk_expr_ui.bulk_pairwise_enable.setEnabled(enable)
            if enable:
                self.bulk_expr_ui.bulk_pairwise_enable.setChecked(True)
            else:
                self.bulk_expr_ui.bulk_pairwise_enable.setChecked(False)

    def set_filter_enabled(self, filter_combo, filter_list, enabled):
        """设置筛选控件启用状态"""
        filter_combo.setEnabled(enabled)
        filter_list.setEnabled(enabled)

    # ---------- 图片显示 ----------

    def display_image(self, label_widget, fig_or_path):
        """将图片显示到标签上（支持fig对象或文件路径）"""
        if not label_widget:
            print(f"[DEBUG] display_image: label_widget is None")
            return

        import io

        if hasattr(fig_or_path, 'savefig'):
            print(f"[DEBUG] display_image: got matplotlib figure")
            buf = io.BytesIO()
            fig_or_path.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            data = buf.read()
            print(f"[DEBUG] display_image: image data size: {len(data)} bytes")
            pixmap = QPixmap()
            success = pixmap.loadFromData(data)
            print(f"[DEBUG] display_image: pixmap load success: {success}")
        elif isinstance(fig_or_path, str) and os.path.exists(fig_or_path):
            print(f"[DEBUG] display_image: got file path: {fig_or_path}")
            pixmap = QPixmap(fig_or_path)
        else:
            print(f"[DEBUG] display_image: invalid input: {type(fig_or_path)}")
            return

        if pixmap.isNull():
            print(f"[DEBUG] display_image: pixmap is null")
            return

        print(f"[DEBUG] display_image: setting pixmap to label")
        if isinstance(label_widget, ZoomableImageLabel):
            label_widget.set_pixmap(pixmap)
        else:
            label_widget.setPixmap(pixmap.scaled(
                label_widget.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def clear_image(self, label_widget):
        """清空图片显示"""
        if label_widget:
            label_widget.clear()
            label_widget.setText("请加载数据并生成图表")

    def set_hint_text(self, label_widget, text):
        """设置提示文本"""
        if label_widget:
            label_widget.setText(text)

    # ---------- 日志/状态 ----------

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.bulk_expr_ui, 'bulk_status_text'):
            self.bulk_expr_ui.bulk_status_text.append(message)
            self.bulk_expr_ui.bulk_status_text.verticalScrollBar().setValue(
                self.bulk_expr_ui.bulk_status_text.verticalScrollBar().maximum()
            )

    def log_clear(self):
        """清空日志"""
        if hasattr(self.bulk_expr_ui, 'bulk_status_text'):
            self.bulk_expr_ui.bulk_status_text.clear()

    def log_set_default(self, text="数据未加载\n请扫描数据路径"):
        """设置默认日志文本"""
        if hasattr(self.bulk_expr_ui, 'bulk_status_text'):
            self.bulk_expr_ui.bulk_status_text.setText(text)

    # ---------- 数据信息显示 ----------

    def update_data_info(self, dataset_name, n_samples, n_genes, n_cols):
        """更新数据信息到状态区域"""
        self.log_clear()
        self.log(f"样本数: {n_samples}")
        self.log(f"基因数: {n_genes}")
        self.log(f"数据集: {dataset_name}")
        self.log(f"可用注释列: {n_cols} 个")
        self.log("数据加载完成")

    def update_hint_text(self, dataset_name, n_samples, n_genes):
        """更新图表区域的提示文本"""
        labels = [
            getattr(self.bulk_expr_ui, 'bulk_violin_box_label', None),
            getattr(self.bulk_expr_ui, 'bulk_box_label', None),
            getattr(self.bulk_expr_ui, 'bulk_violin_label', None)
        ]
        
        for label in labels:
            if label and hasattr(label, 'data_hint_template'):
                hint_text = label.data_hint_template.format(
                    dataset_name=dataset_name,
                    n_samples=n_samples,
                    n_genes=n_genes
                )
                label.setText(hint_text)

    # ---------- 导出辅助 ----------

    def get_export_size(self):
        """获取导出宽高（从界面spinbox读取）"""
        width = None
        height = None

        if hasattr(self.bulk_expr_ui, 'bulk_export_width'):
            width = self.bulk_expr_ui.bulk_export_width.value()

        if hasattr(self.bulk_expr_ui, 'bulk_export_height'):
            height = self.bulk_expr_ui.bulk_export_height.value()

        return width, height

    # ---------- 下拉框选择相关（前端刚需） ----------

    def load_clinical_columns_to_filter1(self):
        """加载分类列到筛选1下拉框"""
        if hasattr(self.bulk_expr_ui, 'bulk_filter1_combo') and hasattr(self, 'analysis'):
            columns = self.analysis.get_obs_columns()
            self.update_filter_combo(self.bulk_expr_ui.bulk_filter1_combo, columns)

    def load_clinical_columns_to_filter2(self):
        """加载分类列到筛选2下拉框"""
        if hasattr(self.bulk_expr_ui, 'bulk_filter2_combo') and hasattr(self, 'analysis'):
            columns = self.analysis.get_obs_columns()
            self.update_filter_combo(self.bulk_expr_ui.bulk_filter2_combo, columns)

    def on_filter1_enabled(self, enabled):
        """筛选1启用状态改变"""
        if hasattr(self.bulk_expr_ui, 'bulk_filter1_combo') and hasattr(self.bulk_expr_ui, 'bulk_filter1_list'):
            self.set_filter_enabled(self.bulk_expr_ui.bulk_filter1_combo, self.bulk_expr_ui.bulk_filter1_list, enabled)

    def on_filter2_enabled(self, enabled):
        """筛选2启用状态改变"""
        if hasattr(self.bulk_expr_ui, 'bulk_filter2_combo') and hasattr(self.bulk_expr_ui, 'bulk_filter2_list'):
            self.set_filter_enabled(self.bulk_expr_ui.bulk_filter2_combo, self.bulk_expr_ui.bulk_filter2_list, enabled)

    def on_pairwise_enable_changed(self, enabled, select_all_btn):
        """两两比较启用状态改变"""
        if hasattr(self.bulk_expr_ui, 'bulk_pairwise_list'):
            self.bulk_expr_ui.bulk_pairwise_list.setEnabled(enabled)
        if select_all_btn:
            select_all_btn.setEnabled(enabled)

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
