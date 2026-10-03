# -*- coding: utf-8 -*-
"""
bulk Log-rank分析界面前端功能脚本 - Python版本
只负责前端显示、控件内容更新等，不绑定信号，不写业务算法
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import TableSearcherMixin
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkLogrankPyFunc(TableSearcherMixin):
    def __init__(self, bulk_logrank_ui, parent_widget=None):
        self.bulk_logrank_ui = bulk_logrank_ui
        self.parent_widget = parent_widget
        self.analysis = None
        self._setup_gene_search()

    def set_combo_items(self, combo_widget, items, keep_selection=False):
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        list_widget.clear()
        str_items = [str(item) for item in items]
        list_widget.addItems(str_items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def fill_checkable_list_widget(self, list_widget, items, check_all=True):
        list_widget.clear()
        for item_text in items:
            item = QListWidgetItem(str(item_text))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if check_all else Qt.Unchecked)
            list_widget.addItem(item)

    def update_clinical_combo(self, columns):
        self.set_combo_items(self.bulk_logrank_ui.bulk_logrank_clinical_combo, ["全部"] + columns)

    def update_group_list(self, groups):
        self.bulk_logrank_ui.bulk_logrank_group_list_label.show()
        self.bulk_logrank_ui.bulk_logrank_group_list.show()
        self.bulk_logrank_ui.bulk_logrank_clinical_col_list_label.hide()
        self.bulk_logrank_ui.bulk_logrank_clinical_col_list.hide()
        self.fill_checkable_list_widget(self.bulk_logrank_ui.bulk_logrank_group_list, groups)

    def update_clinical_col_list(self, columns):
        self.bulk_logrank_ui.bulk_logrank_clinical_col_list_label.show()
        self.bulk_logrank_ui.bulk_logrank_clinical_col_list.show()
        self.bulk_logrank_ui.bulk_logrank_group_list_label.hide()
        self.bulk_logrank_ui.bulk_logrank_group_list.hide()
        self.fill_list_widget(self.bulk_logrank_ui.bulk_logrank_clinical_col_list, columns, select_all=True)

    def update_filter_combo(self, combo_widget, values):
        self.set_combo_items(combo_widget, values)

    def update_filter_list(self, list_widget, values):
        self.fill_checkable_list_widget(list_widget, values)

    def set_filter_enabled(self, filter_combo, filter_list, enabled):
        filter_combo.setEnabled(enabled)
        filter_list.setEnabled(enabled)

    def show_clinical_col_list(self, show=True):
        if show:
            self.bulk_logrank_ui.bulk_logrank_clinical_col_list_label.show()
            self.bulk_logrank_ui.bulk_logrank_clinical_col_list.show()
            self.bulk_logrank_ui.bulk_logrank_group_list_label.hide()
            self.bulk_logrank_ui.bulk_logrank_group_list.hide()
        else:
            self.bulk_logrank_ui.bulk_logrank_clinical_col_list_label.hide()
            self.bulk_logrank_ui.bulk_logrank_clinical_col_list.hide()
            self.bulk_logrank_ui.bulk_logrank_group_list_label.show()
            self.bulk_logrank_ui.bulk_logrank_group_list.show()

    def hide_group_list(self):
        self.bulk_logrank_ui.bulk_logrank_group_list_label.hide()
        self.bulk_logrank_ui.bulk_logrank_group_list.hide()
        self.bulk_logrank_ui.bulk_logrank_clinical_col_list_label.hide()
        self.bulk_logrank_ui.bulk_logrank_clinical_col_list.hide()

    def show_group_list(self):
        self.bulk_logrank_ui.bulk_logrank_group_list_label.show()
        self.bulk_logrank_ui.bulk_logrank_group_list.show()

    def log(self, message):
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_log'):
            self.bulk_logrank_ui.bulk_logrank_log.append(message)
            self.bulk_logrank_ui.bulk_logrank_log.verticalScrollBar().setValue(
                self.bulk_logrank_ui.bulk_logrank_log.verticalScrollBar().maximum()
            )

    def log_clear(self):
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_log'):
            self.bulk_logrank_ui.bulk_logrank_log.clear()

    def log_set_default(self):
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_log'):
            self.bulk_logrank_ui.bulk_logrank_log.setText("数据未加载\n请扫描数据路径")

    def update_data_info(self, dataset_name, n_samples, n_genes, n_cols):
        self.log_clear()
        self.log(f"数据集: {dataset_name}")
        self.log(f"样本数: {n_samples}")
        self.log(f"基因数: {n_genes}")
        self.log(f"可用注释列: {n_cols} 个")
        self.log("数据加载完成")

    def load_clinical_columns_to_filter1(self):
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter1_combo'):
            survival_cols = ['time', 'time (month)', 'state']
            valid_cols = []
            if hasattr(self, 'analysis') and self.analysis.adata is not None:
                for col in self.analysis.adata.obs.columns:
                    if col.strip() not in survival_cols:
                        valid_cols.append(col)
            self.update_filter_combo(self.bulk_logrank_ui.bulk_logrank_filter1_combo, valid_cols)

    def load_clinical_columns_to_filter2(self):
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter2_combo'):
            survival_cols = ['time', 'time (month)', 'state']
            valid_cols = []
            if hasattr(self, 'analysis') and self.analysis.adata is not None:
                for col in self.analysis.adata.obs.columns:
                    if col.strip() not in survival_cols:
                        valid_cols.append(col)
            self.update_filter_combo(self.bulk_logrank_ui.bulk_logrank_filter2_combo, valid_cols)

    def on_filter1_enabled(self, enabled):
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter1_combo'):
            self.bulk_logrank_ui.bulk_logrank_filter1_combo.setEnabled(enabled)
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter1_list'):
            self.bulk_logrank_ui.bulk_logrank_filter1_list.setEnabled(enabled)

    def on_filter2_enabled(self, enabled):
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter2_combo'):
            self.bulk_logrank_ui.bulk_logrank_filter2_combo.setEnabled(enabled)
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter2_list'):
            self.bulk_logrank_ui.bulk_logrank_filter2_list.setEnabled(enabled)

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def _setup_gene_search(self):
        """初始化基因搜索功能"""
        if not hasattr(self.bulk_logrank_ui, 'bulk_logrank_result_tabs'):
            return
        tables = [
            getattr(self.bulk_logrank_ui, 'bulk_logrank_result_table', None),
            getattr(self.bulk_logrank_ui, 'bulk_logrank_result_table_favorable', None),
            getattr(self.bulk_logrank_ui, 'bulk_logrank_result_table_unfavorable', None),
        ]
        tables = [t for t in tables if t is not None]
        self.setup_gene_search(self.bulk_logrank_ui.bulk_logrank_result_tabs, tables, gene_col=0)

    def get_save_file_path(self, title, default_name, filter_text):
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    def get_selected_groups(self):
        selected_groups = []
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_group_list'):
            for i in range(self.bulk_logrank_ui.bulk_logrank_group_list.count()):
                item = self.bulk_logrank_ui.bulk_logrank_group_list.item(i)
                if item.checkState() == Qt.Checked:
                    selected_groups.append(item.text())
        return selected_groups

    def get_filter1_groups(self):
        groups = []
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter1_list'):
            for i in range(self.bulk_logrank_ui.bulk_logrank_filter1_list.count()):
                item = self.bulk_logrank_ui.bulk_logrank_filter1_list.item(i)
                if item.checkState() == Qt.Checked:
                    groups.append(item.text())
        return groups

    def get_filter2_groups(self):
        groups = []
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter2_list'):
            for i in range(self.bulk_logrank_ui.bulk_logrank_filter2_list.count()):
                item = self.bulk_logrank_ui.bulk_logrank_filter2_list.item(i)
                if item.checkState() == Qt.Checked:
                    groups.append(item.text())
        return groups

    def get_clinical_col(self):
        clinical_col = "全部"
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_clinical_combo'):
            clinical_col = self.bulk_logrank_ui.bulk_logrank_clinical_combo.currentText()
        return clinical_col

    def update_stats(self, result_df):
        """更新统计信息标签"""
        total_samples = result_df['total_samples'].iloc[0] if 'total_samples' in result_df.columns and len(result_df) > 0 else 0
        
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_high_cell_label'):
            avg_high = int(result_df['n_high'].mean()) if 'n_high' in result_df.columns else 0
            self.bulk_logrank_ui.bulk_logrank_high_cell_label.setText(f"高表达组样本数: {avg_high}")
        
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_low_cell_label'):
            avg_low = int(result_df['n_low'].mean()) if 'n_low' in result_df.columns else 0
            self.bulk_logrank_ui.bulk_logrank_low_cell_label.setText(f"低表达组样本数: {avg_low}")
        
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_favorable_label'):
            favorable_count = len(result_df[result_df['prognosis'] == 'favorable'])
            self.bulk_logrank_ui.bulk_logrank_favorable_label.setText(f"良好预后基因: {favorable_count}")
        
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_unfavorable_label'):
            unfavorable_count = len(result_df[result_df['prognosis'] == 'unfavorable'])
            self.bulk_logrank_ui.bulk_logrank_unfavorable_label.setText(f"不良预后基因: {unfavorable_count}")
        
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_not_significant_label'):
            not_significant_count = len(result_df[result_df['prognosis'] == 'not_significant'])
            self.bulk_logrank_ui.bulk_logrank_not_significant_label.setText(f"不显著基因: {not_significant_count}")
        
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_total_label'):
            total_count = len(result_df)
            self.bulk_logrank_ui.bulk_logrank_total_label.setText(f"总基因: {total_count}")

    def display_results(self, result_df):
        """显示结果到表格"""
        self._display_table(self.bulk_logrank_ui.bulk_logrank_result_table, result_df)
        
        favorable_df = result_df[result_df['prognosis'] == 'favorable']
        self._display_table(self.bulk_logrank_ui.bulk_logrank_result_table_favorable, favorable_df)
        
        unfavorable_df = result_df[result_df['prognosis'] == 'unfavorable']
        self._display_table(self.bulk_logrank_ui.bulk_logrank_result_table_unfavorable, unfavorable_df)

    def _display_table(self, table_widget, df):
        """在表格中显示数据"""
        if table_widget is None or df is None or df.empty:
            return
        
        table_widget.setRowCount(len(df))
        
        columns = ['gene', 'median_high', 'median_low', 'HR', 'p_val', 'p_val_adj', 'prognosis']
        
        for row_idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, col_name in enumerate(columns):
                if col_name in row:
                    value = row[col_name]
                    if isinstance(value, float):
                        if col_name in ['p_val', 'p_val_adj']:
                            if value < 0.0001:
                                item_text = f"{value:.2e}"
                            else:
                                item_text = f"{value:.4f}"
                        elif col_name == 'HR':
                            item_text = f"{value:.3f}"
                        elif col_name in ['median_high', 'median_low']:
                            item_text = f"{value:.1f}"
                        else:
                            item_text = str(value)
                    else:
                        item_text = str(value)
                    table_widget.setItem(row_idx, col_idx, QTableWidgetItem(item_text))