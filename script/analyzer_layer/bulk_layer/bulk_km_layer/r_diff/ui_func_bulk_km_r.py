# -*- coding: utf-8 -*-
"""
bulk KM曲线 R模式前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkKmRFunc:
    """bulk KM曲线 R模式前端功能类 - 纯前端显示操作"""

    def __init__(self, bulk_km_r_ui, parent_widget=None):
        self.bulk_km_r_ui = bulk_km_r_ui
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

    def update_clinical_combo(self, columns):
        """更新分类列下拉框"""
        self.set_combo_items(self.bulk_km_r_ui.bulk_km_clinical_combo, ["全部"] + columns)

    def update_group_list(self, groups):
        """更新组别列表"""
        self.bulk_km_r_ui.bulk_km_group_list_label.show()
        self.bulk_km_r_ui.bulk_km_group_list.show()
        self.bulk_km_r_ui.bulk_km_clinical_col_list_label.hide()
        self.bulk_km_r_ui.bulk_km_clinical_col_list.hide()
        self.fill_checkable_list_widget(self.bulk_km_r_ui.bulk_km_group_list, groups)

    def update_clinical_col_list(self, columns):
        """更新分类列多选列表"""
        self.bulk_km_r_ui.bulk_km_clinical_col_list_label.show()
        self.bulk_km_r_ui.bulk_km_clinical_col_list.show()
        self.bulk_km_r_ui.bulk_km_group_list_label.hide()
        self.bulk_km_r_ui.bulk_km_group_list.hide()
        self.fill_list_widget(self.bulk_km_r_ui.bulk_km_clinical_col_list, columns, select_all=True)

    def update_pairwise_list(self, groups):
        """更新两两比较列表（同一组高低表达之间的比较）"""
        self.bulk_km_r_ui.bulk_km_pairwise_list.clear()
        pairwise_items = []
        for g in groups:
            pairwise_items.append(f"{g} High vs {g} Low")
        for g in pairwise_items:
            self.bulk_km_r_ui.bulk_km_pairwise_list.addItem(g)
        self.bulk_km_r_ui.bulk_km_pairwise_list.selectAll()

    def update_filter_combo(self, combo_widget, values):
        """更新筛选下拉框"""
        self.set_combo_items(combo_widget, values)

    def update_filter_list(self, list_widget, values):
        """更新筛选列表"""
        self.fill_checkable_list_widget(list_widget, values)

    def show_clinical_col_list(self, show=True):
        """显示/隐藏分类列多选列表"""
        if show:
            self.bulk_km_r_ui.bulk_km_clinical_col_list_label.show()
            self.bulk_km_r_ui.bulk_km_clinical_col_list.show()
            self.bulk_km_r_ui.bulk_km_group_list_label.hide()
            self.bulk_km_r_ui.bulk_km_group_list.hide()
        else:
            self.bulk_km_r_ui.bulk_km_clinical_col_list_label.hide()
            self.bulk_km_r_ui.bulk_km_clinical_col_list.hide()
            self.bulk_km_r_ui.bulk_km_group_list_label.show()
            self.bulk_km_r_ui.bulk_km_group_list.show()

    def enable_pairwise_controls(self, enable=True):
        """启用/禁用两两比较控件"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_pairwise_enable'):
            self.bulk_km_r_ui.bulk_km_pairwise_enable.setEnabled(enable)
            if enable:
                self.bulk_km_r_ui.bulk_km_pairwise_enable.setChecked(True)
            else:
                self.bulk_km_r_ui.bulk_km_pairwise_enable.setChecked(False)

    def set_filter_enabled(self, filter_combo, filter_list, enabled):
        """设置筛选控件启用状态"""
        filter_combo.setEnabled(enabled)
        filter_list.setEnabled(enabled)

    def on_filter1_enabled(self, enabled):
        """筛选1启用状态改变"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter1_combo'):
            self.bulk_km_r_ui.bulk_km_filter1_combo.setEnabled(enabled)
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter1_list'):
            self.bulk_km_r_ui.bulk_km_filter1_list.setEnabled(enabled)

    def on_filter2_enabled(self, enabled):
        """筛选2启用状态改变"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter2_combo'):
            self.bulk_km_r_ui.bulk_km_filter2_combo.setEnabled(enabled)
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter2_list'):
            self.bulk_km_r_ui.bulk_km_filter2_list.setEnabled(enabled)

    def hide_group_list(self):
        """隐藏组别列表"""
        self.bulk_km_r_ui.bulk_km_group_list_label.hide()
        self.bulk_km_r_ui.bulk_km_group_list.hide()
        self.bulk_km_r_ui.bulk_km_clinical_col_list_label.hide()
        self.bulk_km_r_ui.bulk_km_clinical_col_list.hide()

    def show_group_list(self):
        """显示组别列表"""
        self.bulk_km_r_ui.bulk_km_group_list_label.show()
        self.bulk_km_r_ui.bulk_km_group_list.show()

    # ---------- 图片显示 ----------

    def display_image(self, label_widget, fig_or_path):
        """将图片显示到标签上（支持fig对象或文件路径）"""
        if not label_widget:
            print(f"[DEBUG] display_image: label_widget is None")
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
        """清空标签上的图片"""
        if label_widget:
            if isinstance(label_widget, ZoomableImageLabel):
                label_widget.clear()
            else:
                label_widget.clear()

    def set_hint_text(self, text):
        """设置提示文本"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_label'):
            self.bulk_km_r_ui.bulk_km_label.setText(text)

    # ---------- 日志操作 ----------

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_status_text'):
            self.bulk_km_r_ui.bulk_km_status_text.append(message)
            self.bulk_km_r_ui.bulk_km_status_text.verticalScrollBar().setValue(
                self.bulk_km_r_ui.bulk_km_status_text.verticalScrollBar().maximum()
            )

    def log_clear(self):
        """清空日志"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_status_text'):
            self.bulk_km_r_ui.bulk_km_status_text.clear()

    def log_set_default(self):
        """设置默认日志文本"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_status_text'):
            self.bulk_km_r_ui.bulk_km_status_text.setText("数据未加载\n请先在KM模式页面加载数据")

    # ---------- 数据信息更新 ----------

    def update_data_info(self, dataset_name, n_samples, n_genes, n_obs_columns):
        """更新数据信息"""
        pass

    def update_hint_text(self, dataset_name, n_samples, n_genes):
        """更新提示文本"""
        hint_text = f"数据: {dataset_name}\n样本数: {n_samples}\n基因数: {n_genes}\n\n请输入基因名称并点击「生成KM曲线」"
        self.set_hint_text(hint_text)

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

    def get_export_size(self):
        """获取导出宽高（从界面输入框读取）"""
        width = None
        height = None

        if hasattr(self.bulk_km_r_ui, 'bulk_km_export_width'):
            width_text = str(self.bulk_km_r_ui.bulk_km_export_width.text())
            if width_text:
                try:
                    width = float(width_text)
                except ValueError:
                    width = None

        if hasattr(self.bulk_km_r_ui, 'bulk_km_export_height'):
            height_text = str(self.bulk_km_r_ui.bulk_km_export_height.text())
            if height_text:
                try:
                    height = float(height_text)
                except ValueError:
                    height = None

        return width, height

    # ---------- 界面数据获取 ----------

    def get_selected_groups(self):
        """获取选中的组别列表"""
        selected_groups = []
        if hasattr(self.bulk_km_r_ui, 'bulk_km_group_list'):
            for i in range(self.bulk_km_r_ui.bulk_km_group_list.count()):
                item = self.bulk_km_r_ui.bulk_km_group_list.item(i)
                if item.checkState() == Qt.Checked:
                    selected_groups.append(item.text())
        return selected_groups

    def get_filter1_groups(self):
        """获取筛选1选中的组别"""
        groups = []
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter1_list'):
            for i in range(self.bulk_km_r_ui.bulk_km_filter1_list.count()):
                item = self.bulk_km_r_ui.bulk_km_filter1_list.item(i)
                if item.checkState() == Qt.Checked:
                    groups.append(item.text())
        return groups

    def get_filter2_groups(self):
        """获取筛选2选中的组别"""
        groups = []
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter2_list'):
            for i in range(self.bulk_km_r_ui.bulk_km_filter2_list.count()):
                item = self.bulk_km_r_ui.bulk_km_filter2_list.item(i)
                if item.checkState() == Qt.Checked:
                    groups.append(item.text())
        return groups

    def load_clinical_columns_to_filter1(self):
        """加载分类列到筛选1下拉框"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter1_combo'):
            survival_cols = ['time', 'time (month)', 'state']
            valid_cols = []
            if hasattr(self, 'analysis') and self.analysis.adata is not None:
                for col in self.analysis.adata.obs.columns:
                    if col.strip() not in survival_cols:
                        valid_cols.append(col)
            self.update_filter_combo(self.bulk_km_r_ui.bulk_km_filter1_combo, valid_cols)

    def load_clinical_columns_to_filter2(self):
        """加载分类列到筛选2下拉框"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_filter2_combo'):
            survival_cols = ['time', 'time (month)', 'state']
            valid_cols = []
            if hasattr(self, 'analysis') and self.analysis.adata is not None:
                for col in self.analysis.adata.obs.columns:
                    if col.strip() not in survival_cols:
                        valid_cols.append(col)
            self.update_filter_combo(self.bulk_km_r_ui.bulk_km_filter2_combo, valid_cols)

    def get_multi_gene_list(self):
        """获取多基因输入列表"""
        multi_gene_text = ""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_multi_gene_input'):
            multi_gene_text = self.bulk_km_r_ui.bulk_km_multi_gene_input.toPlainText().strip()
        return multi_gene_text

    def get_gene_name(self):
        """获取单基因名称"""
        gene_name = ""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_gene_input'):
            gene_name = self.bulk_km_r_ui.bulk_km_gene_input.text().strip()
        return gene_name

    def get_time_unit(self):
        """获取时间单位"""
        time_unit = "month"
        if hasattr(self.bulk_km_r_ui, 'bulk_km_time_unit_combo'):
            time_unit = self.bulk_km_r_ui.bulk_km_time_unit_combo.currentText()
        return time_unit

    def get_plot_params(self):
        """获取绘图参数"""
        params = {
            'title_size': 18,
            'legend_size': 12,
            'axis_size': 16,
            'pval_size': 5,
            'table_size': 5,
            'show_ci': True,
            'show_n': True,
            'pval_mode': 0,
            'show_global_pval': True,
            'show_pairwise': False,
            'selected_pairwise': [],
            'plot_width': 6,
            'plot_height': 8,
            'show_table': True
        }

        if hasattr(self.bulk_km_r_ui, 'bulk_km_titlesize_input'):
            title_size_str = str(self.bulk_km_r_ui.bulk_km_titlesize_input.text()).strip()
            if title_size_str.isdigit():
                params['title_size'] = int(title_size_str)

        if hasattr(self.bulk_km_r_ui, 'bulk_km_legendsize_input'):
            legend_size_str = str(self.bulk_km_r_ui.bulk_km_legendsize_input.text()).strip()
            if legend_size_str.isdigit():
                params['legend_size'] = int(legend_size_str)

        if hasattr(self.bulk_km_r_ui, 'bulk_km_axissize_input'):
            axis_size_str = str(self.bulk_km_r_ui.bulk_km_axissize_input.text()).strip()
            if axis_size_str.isdigit():
                params['axis_size'] = int(axis_size_str)

        if hasattr(self.bulk_km_r_ui, 'bulk_km_pvalsize_input'):
            pval_size_str = str(self.bulk_km_r_ui.bulk_km_pvalsize_input.text()).strip()
            if pval_size_str.isdigit():
                params['pval_size'] = int(pval_size_str)

        if hasattr(self.bulk_km_r_ui, 'bulk_km_show_table_check'):
            params['show_table'] = self.bulk_km_r_ui.bulk_km_show_table_check.isChecked()

        if hasattr(self.bulk_km_r_ui, 'bulk_km_tablesize_input'):
            table_size_str = str(self.bulk_km_r_ui.bulk_km_tablesize_input.text()).strip()
            if table_size_str.isdigit():
                params['table_size'] = int(table_size_str)

        if hasattr(self.bulk_km_r_ui, 'bulk_km_show_ci_check'):
            params['show_ci'] = self.bulk_km_r_ui.bulk_km_show_ci_check.isChecked()

        if hasattr(self.bulk_km_r_ui, 'bulk_km_show_n_check'):
            params['show_n'] = self.bulk_km_r_ui.bulk_km_show_n_check.isChecked()

        if hasattr(self.bulk_km_r_ui, 'bulk_km_pval_mode_combo'):
            params['pval_mode'] = self.bulk_km_r_ui.bulk_km_pval_mode_combo.currentIndex()

        if hasattr(self.bulk_km_r_ui, 'bulk_km_show_global_check'):
            params['show_global_pval'] = self.bulk_km_r_ui.bulk_km_show_global_check.isChecked()

        if hasattr(self.bulk_km_r_ui, 'bulk_km_pairwise_enable'):
            params['show_pairwise'] = self.bulk_km_r_ui.bulk_km_pairwise_enable.isChecked()

        if hasattr(self.bulk_km_r_ui, 'bulk_km_pairwise_list'):
            params['selected_pairwise'] = [item.text() for item in self.bulk_km_r_ui.bulk_km_pairwise_list.selectedItems()]

        if hasattr(self.bulk_km_r_ui, 'bulk_km_plot_width_input'):
            plot_width_str = str(self.bulk_km_r_ui.bulk_km_plot_width_input.text()).strip()
            if plot_width_str.replace('.', '').isdigit():
                params['plot_width'] = float(plot_width_str)

        if hasattr(self.bulk_km_r_ui, 'bulk_km_plot_height_input'):
            plot_height_str = str(self.bulk_km_r_ui.bulk_km_plot_height_input.text()).strip()
            if plot_height_str.replace('.', '').isdigit():
                params['plot_height'] = float(plot_height_str)

        return params

    def get_title(self, default_title=""):
        """获取标题"""
        title = ""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_title_input'):
            title = self.bulk_km_r_ui.bulk_km_title_input.text().strip()
        return title if title else default_title

    def get_clinical_col(self):
        """获取分类列"""
        clinical_col = "全部"
        if hasattr(self.bulk_km_r_ui, 'bulk_km_clinical_combo'):
            clinical_col = self.bulk_km_r_ui.bulk_km_clinical_combo.currentText()
        return clinical_col

    # ---------- 尺寸同步 ----------

    def on_table_check_changed(self, state):
        """显示风险表格选项变化时更新出图尺寸"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_plot_width_input') and hasattr(self.bulk_km_r_ui, 'bulk_km_plot_height_input'):
            if state == Qt.Checked:
                self.bulk_km_r_ui.bulk_km_plot_width_input.setText("6")
                self.bulk_km_r_ui.bulk_km_plot_height_input.setText("8")
                if hasattr(self.bulk_km_r_ui, 'bulk_km_export_width'):
                    self.bulk_km_r_ui.bulk_km_export_width.setText("6")
                if hasattr(self.bulk_km_r_ui, 'bulk_km_export_height'):
                    self.bulk_km_r_ui.bulk_km_export_height.setText("8")
            else:
                self.bulk_km_r_ui.bulk_km_plot_width_input.setText("6")
                self.bulk_km_r_ui.bulk_km_plot_height_input.setText("6")
                if hasattr(self.bulk_km_r_ui, 'bulk_km_export_width'):
                    self.bulk_km_r_ui.bulk_km_export_width.setText("6")
                if hasattr(self.bulk_km_r_ui, 'bulk_km_export_height'):
                    self.bulk_km_r_ui.bulk_km_export_height.setText("6")

    def sync_plot_size_to_export(self, width, height):
        """同步出图尺寸到导出尺寸"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_export_width'):
            self.bulk_km_r_ui.bulk_km_export_width.setText(str(width))
        if hasattr(self.bulk_km_r_ui, 'bulk_km_export_height'):
            self.bulk_km_r_ui.bulk_km_export_height.setText(str(height))

    def sync_export_size_to_plot(self, width, height):
        """同步导出尺寸到出图尺寸"""
        if hasattr(self.bulk_km_r_ui, 'bulk_km_plot_width_input'):
            self.bulk_km_r_ui.bulk_km_plot_width_input.setText(str(width))
        if hasattr(self.bulk_km_r_ui, 'bulk_km_plot_height_input'):
            self.bulk_km_r_ui.bulk_km_plot_height_input.setText(str(height))

    def update_r_version_label(self):
        """更新R版本标签"""
        if hasattr(self.bulk_km_r_ui, 'r_version_label') and hasattr(self, 'analysis'):
            r_version = self.analysis.get_r_version()
            self.bulk_km_r_ui.r_version_label.setText(f"R版本: {r_version}")
