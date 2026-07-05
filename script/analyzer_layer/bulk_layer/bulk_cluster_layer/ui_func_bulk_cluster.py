# -*- coding: utf-8 -*-
"""
bulk 一致性分析前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkClusterFunc:
    """bulk 一致性分析前端功能类 - 纯前端显示操作"""

    def __init__(self, bulk_cluster_ui, parent_widget=None):
        self.bulk_cluster_ui = bulk_cluster_ui
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
        self.set_combo_items(self.bulk_cluster_ui.bulk_cluster_clinical_combo, ["全部"] + columns)

    def update_group_list(self, groups):
        """更新组别列表"""
        self.bulk_cluster_ui.bulk_cluster_group_list_label.show()
        self.bulk_cluster_ui.bulk_cluster_group_list.show()
        self.fill_checkable_list_widget(self.bulk_cluster_ui.bulk_cluster_group_list, groups)

    def hide_group_list(self):
        """隐藏组别列表"""
        self.bulk_cluster_ui.bulk_cluster_group_list_label.hide()
        self.bulk_cluster_ui.bulk_cluster_group_list.hide()

    def update_filter_combo(self, combo_widget, values):
        """更新筛选下拉框"""
        self.set_combo_items(combo_widget, values)

    def update_filter_list(self, list_widget, values):
        """更新筛选列表"""
        self.fill_checkable_list_widget(list_widget, values)

    def on_filter1_enabled(self, enabled):
        """筛选1启用状态改变"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter1_combo'):
            self.bulk_cluster_ui.bulk_cluster_filter1_combo.setEnabled(enabled)
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter1_list'):
            self.bulk_cluster_ui.bulk_cluster_filter1_list.setEnabled(enabled)

    def on_filter2_enabled(self, enabled):
        """筛选2启用状态改变"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter2_combo'):
            self.bulk_cluster_ui.bulk_cluster_filter2_combo.setEnabled(enabled)
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter2_list'):
            self.bulk_cluster_ui.bulk_cluster_filter2_list.setEnabled(enabled)

    def load_clinical_columns_to_filter1(self):
        """加载分类列到筛选1下拉框"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter1_combo'):
            valid_cols = []
            if hasattr(self, 'analysis') and self.analysis.adata is not None:
                for col in self.analysis.adata.obs.columns:
                    valid_cols.append(col)
            self.update_filter_combo(self.bulk_cluster_ui.bulk_cluster_filter1_combo, valid_cols)

    def load_clinical_columns_to_filter2(self):
        """加载分类列到筛选2下拉框"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter2_combo'):
            valid_cols = []
            if hasattr(self, 'analysis') and self.analysis.adata is not None:
                for col in self.analysis.adata.obs.columns:
                    valid_cols.append(col)
            self.update_filter_combo(self.bulk_cluster_ui.bulk_cluster_filter2_combo, valid_cols)

    # ---------- 图片显示 ----------

    def display_image(self, label_widget, fig_or_path):
        """将图片显示到标签上（支持fig对象或文件路径）"""
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
        """清空标签上的图片"""
        if label_widget:
            label_widget.clear()

    def set_hint_text(self, text, label_attr='bulk_cluster_label_consensus'):
        """设置提示文本"""
        if hasattr(self.bulk_cluster_ui, label_attr):
            getattr(self.bulk_cluster_ui, label_attr).setText(text)

    # ---------- 日志操作 ----------

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_status_text'):
            self.bulk_cluster_ui.bulk_cluster_status_text.append(message)
            self.bulk_cluster_ui.bulk_cluster_status_text.verticalScrollBar().setValue(
                self.bulk_cluster_ui.bulk_cluster_status_text.verticalScrollBar().maximum()
            )

    def log_clear(self):
        """清空日志"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_status_text'):
            self.bulk_cluster_ui.bulk_cluster_status_text.clear()

    def log_set_default(self):
        """设置默认日志文本"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_status_text'):
            self.bulk_cluster_ui.bulk_cluster_status_text.setText("数据未加载\n请先在bulk主页加载数据")

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
        """获取导出宽高"""
        width = None
        height = None

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_export_width'):
            width_text = str(self.bulk_cluster_ui.bulk_cluster_export_width.text())
            if width_text:
                try:
                    width = float(width_text)
                except ValueError:
                    width = None

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_export_height'):
            height_text = str(self.bulk_cluster_ui.bulk_cluster_export_height.text())
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
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_group_list'):
            for i in range(self.bulk_cluster_ui.bulk_cluster_group_list.count()):
                item = self.bulk_cluster_ui.bulk_cluster_group_list.item(i)
                if item.checkState() == Qt.Checked:
                    selected_groups.append(item.text())
        return selected_groups

    def get_filter1_groups(self):
        """获取筛选1选中的组别"""
        groups = []
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter1_list'):
            for i in range(self.bulk_cluster_ui.bulk_cluster_filter1_list.count()):
                item = self.bulk_cluster_ui.bulk_cluster_filter1_list.item(i)
                if item.checkState() == Qt.Checked:
                    groups.append(item.text())
        return groups

    def get_filter2_groups(self):
        """获取筛选2选中的组别"""
        groups = []
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter2_list'):
            for i in range(self.bulk_cluster_ui.bulk_cluster_filter2_list.count()):
                item = self.bulk_cluster_ui.bulk_cluster_filter2_list.item(i)
                if item.checkState() == Qt.Checked:
                    groups.append(item.text())
        return groups

    def get_clinical_col(self):
        """获取分类列"""
        clinical_col = "全部"
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_clinical_combo'):
            clinical_col = self.bulk_cluster_ui.bulk_cluster_clinical_combo.currentText()
        return clinical_col

    def get_stage1_params(self):
        """获取阶段一参数"""
        params = {
            'mad_threshold': 5000,
            'reps': 1000,
            'cluster_alg': 'hc',
            'distance': 'pearson',
            'p_item': 0.8,
            'p_feature': 1.0,
            'min_k': 2,
            'max_k': 9,
            'plot_format': 'png'
        }

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_mad_input'):
            val = str(self.bulk_cluster_ui.bulk_cluster_mad_input.text()).strip()
            if val.isdigit():
                params['mad_threshold'] = int(val)

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_reps_input'):
            val = str(self.bulk_cluster_ui.bulk_cluster_reps_input.text()).strip()
            if val.isdigit():
                params['reps'] = int(val)

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_alg_combo'):
            params['cluster_alg'] = self.bulk_cluster_ui.bulk_cluster_alg_combo.currentText()

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_distance_combo'):
            params['distance'] = self.bulk_cluster_ui.bulk_cluster_distance_combo.currentText()

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_pitem_input'):
            val = str(self.bulk_cluster_ui.bulk_cluster_pitem_input.text()).strip()
            try:
                params['p_item'] = float(val)
            except ValueError:
                pass

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_pfeature_input'):
            val = str(self.bulk_cluster_ui.bulk_cluster_pfeature_input.text()).strip()
            try:
                params['p_feature'] = float(val)
            except ValueError:
                pass

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_min_k_input'):
            val = str(self.bulk_cluster_ui.bulk_cluster_min_k_input.text()).strip()
            if val.isdigit():
                params['min_k'] = int(val)

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_max_k_input'):
            val = str(self.bulk_cluster_ui.bulk_cluster_max_k_input.text()).strip()
            if val.isdigit():
                params['max_k'] = int(val)

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_plot_format_combo'):
            params['plot_format'] = self.bulk_cluster_ui.bulk_cluster_plot_format_combo.currentText()

        return params

    def get_stage3_params(self):
        """获取阶段三参数"""
        params = {
            'final_k': 2,
            'output_mode': 1,
            'heatmap_width': 8,
            'heatmap_height': 8,
            'color_scheme': 'blue',
            'title_font_size': 14,
            'legend_font_size': 12,
            'clustering_method': 'average'
        }

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_final_k_combo'):
            val = self.bulk_cluster_ui.bulk_cluster_final_k_combo.currentText()
            try:
                params['final_k'] = int(val)
            except ValueError:
                pass

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_output_mode_combo'):
            mode_idx = self.bulk_cluster_ui.bulk_cluster_output_mode_combo.currentIndex()
            params['output_mode'] = mode_idx + 1

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_heatmap_width'):
            val = str(self.bulk_cluster_ui.bulk_cluster_heatmap_width.text()).strip()
            try:
                params['heatmap_width'] = float(val)
            except ValueError:
                pass

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_heatmap_height'):
            val = str(self.bulk_cluster_ui.bulk_cluster_heatmap_height.text()).strip()
            try:
                params['heatmap_height'] = float(val)
            except ValueError:
                pass

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_color_scheme_combo'):
            params['color_scheme'] = self.bulk_cluster_ui.bulk_cluster_color_scheme_combo.currentText()

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_title_font_size'):
            val = str(self.bulk_cluster_ui.bulk_cluster_title_font_size.text()).strip()
            if val.isdigit():
                params['title_font_size'] = int(val)

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_legend_font_size'):
            val = str(self.bulk_cluster_ui.bulk_cluster_legend_font_size.text()).strip()
            if val.isdigit():
                params['legend_font_size'] = int(val)

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_clust_method_combo'):
            params['clustering_method'] = self.bulk_cluster_ui.bulk_cluster_clust_method_combo.currentText()

        return params

    # ---------- R版本更新 ----------

    def update_r_version_label(self):
        """更新R版本标签"""
        if hasattr(self.bulk_cluster_ui, 'r_version_label') and hasattr(self, 'analysis'):
            r_version = self.analysis.get_r_version()
            self.bulk_cluster_ui.r_version_label.setText(f"R版本: {r_version}")

    # ---------- 阶段状态更新 ----------

    def update_stage_status(self, stage_status):
        """根据阶段状态更新UI"""
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_btn_stage2'):
            self.bulk_cluster_ui.bulk_cluster_btn_stage2.setEnabled(stage_status.get('stage1', False))
        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_btn_stage3'):
            self.bulk_cluster_ui.bulk_cluster_btn_stage3.setEnabled(stage_status.get('stage1', False))

    def is_filtered(self):
        """判断当前是否启用了任何筛选条件"""
        clinical_col = self.get_clinical_col()
        if clinical_col and clinical_col != "全部":
            groups = self.get_selected_groups()
            if len(groups) > 0:
                return True

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter1_enable'):
            if self.bulk_cluster_ui.bulk_cluster_filter1_enable.isChecked():
                groups = self.get_filter1_groups()
                if len(groups) > 0:
                    return True

        if hasattr(self.bulk_cluster_ui, 'bulk_cluster_filter2_enable'):
            if self.bulk_cluster_ui.bulk_cluster_filter2_enable.isChecked():
                groups = self.get_filter2_groups()
                if len(groups) > 0:
                    return True

        return False
