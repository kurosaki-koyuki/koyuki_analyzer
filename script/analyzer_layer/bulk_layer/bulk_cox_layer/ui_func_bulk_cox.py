# -*- coding: utf-8 -*-
"""
bulk COX分析界面功能脚本 - 负责UI控件内容更新和结果显示
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, TableSearcherMixin
from script.mods_layer.emoji_function_for_mods import wrong


class BulkCoxFunc(TableSearcherMixin):
    def __init__(self, bulk_cox_ui, parent_window):
        self.bulk_cox_ui = bulk_cox_ui
        self.parent_window = parent_window
        self.analysis = None
        self.result_df = None
        self._table_text_color = None
        self._table_row_color_even = None
        self._table_row_color_odd = None
        self._setup_gene_search()
    
    def _init_table_styles(self):
        """初始化表格样式颜色"""
        styles = get_mod_styles()
        self._table_text_color = styles.get('sub_text_color', '#87CEEB')
        self._table_row_color_even = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.2)')
        self._table_row_color_odd = styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.4)')

    def log(self, message):
        """在状态文本框中添加日志"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_status_text'):
            current_text = self.bulk_cox_ui.bulk_cox_status_text.toPlainText()
            new_text = current_text + message + '\n' if current_text else message + '\n'
            self.bulk_cox_ui.bulk_cox_status_text.setPlainText(new_text)
            self.bulk_cox_ui.bulk_cox_status_text.verticalScrollBar().setValue(
                self.bulk_cox_ui.bulk_cox_status_text.verticalScrollBar().maximum()
            )

    def clear_log(self):
        """清空状态文本框"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_status_text'):
            self.bulk_cox_ui.bulk_cox_status_text.setPlainText("")

    def update_clinical_combo(self, columns):
        """更新临床协变量下拉框"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_covariate_combo'):
            self.bulk_cox_ui.bulk_cox_covariate_combo.clear()
            for col in columns:
                self.bulk_cox_ui.bulk_cox_covariate_combo.addItem(col)

    def update_filter1_combo(self, columns):
        """更新筛选1下拉框"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter1_combo'):
            self.bulk_cox_ui.bulk_cox_filter1_combo.clear()
            for col in columns:
                self.bulk_cox_ui.bulk_cox_filter1_combo.addItem(col)

    def update_filter2_combo(self, columns):
        """更新筛选2下拉框"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter2_combo'):
            self.bulk_cox_ui.bulk_cox_filter2_combo.clear()
            for col in columns:
                self.bulk_cox_ui.bulk_cox_filter2_combo.addItem(col)

    def fill_checkable_list_widget(self, list_widget, items, check_all=True):
        """填充可多选列表控件"""
        list_widget.clear()
        for item_text in items:
            item = QListWidgetItem(str(item_text))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if check_all else Qt.Unchecked)
            list_widget.addItem(item)

    def fill_list_widget(self, list_widget, items):
        """填充列表控件"""
        list_widget.clear()
        for item_text in items:
            item = QListWidgetItem(str(item_text))
            list_widget.addItem(item)

    def get_selected_items(self, list_widget):
        """获取选中的项"""
        selected = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item and item.checkState() == Qt.Checked:
                selected.append(str(item.text()))
        return selected

    def update_stats(self, result_df, use_fdr=True, threshold=0.05):
        """更新统计信息标签"""
        if result_df is None or len(result_df) == 0:
            if hasattr(self.bulk_cox_ui, 'bulk_cox_total_label'):
                self.bulk_cox_ui.bulk_cox_total_label.setText("总基因: -")
            if hasattr(self.bulk_cox_ui, 'bulk_cox_risk_label'):
                self.bulk_cox_ui.bulk_cox_risk_label.setText("风险基因(HR>1): -")
            if hasattr(self.bulk_cox_ui, 'bulk_cox_protective_label'):
                self.bulk_cox_ui.bulk_cox_protective_label.setText("保护基因(HR<1): -")
            if hasattr(self.bulk_cox_ui, 'bulk_cox_sig_label'):
                self.bulk_cox_ui.bulk_cox_sig_label.setText("显著基因: -")
            return

        total_count = len(result_df)

        # 计算CI不跨1的掩码
        ci_not_cross_1 = (
            (result_df['HR_lower95'] > 1) & (result_df['HR_upper95'] > 1) |
            (result_df['HR_lower95'] < 1) & (result_df['HR_upper95'] < 1)
        )

        if use_fdr and 'FDR' in result_df.columns:
            sig_mask = (result_df['FDR'] < threshold) & ci_not_cross_1
            sig_col_name = 'FDR'
        else:
            sig_mask = (result_df['pvalue'] < threshold) & ci_not_cross_1
            sig_col_name = 'pvalue'

        sig_count = len(result_df[sig_mask])
        risk_count = len(result_df[sig_mask & (result_df['HR'] > 1)])
        protective_count = len(result_df[sig_mask & (result_df['HR'] < 1)])

        if hasattr(self.bulk_cox_ui, 'bulk_cox_total_label'):
            self.bulk_cox_ui.bulk_cox_total_label.setText(f"总基因: {total_count}")

        if hasattr(self.bulk_cox_ui, 'bulk_cox_risk_label'):
            self.bulk_cox_ui.bulk_cox_risk_label.setText(f"风险基因(HR>1,CI不跨1,{sig_col_name}<{threshold}): {risk_count}")

        if hasattr(self.bulk_cox_ui, 'bulk_cox_protective_label'):
            self.bulk_cox_ui.bulk_cox_protective_label.setText(f"保护基因(HR<1,CI不跨1,{sig_col_name}<{threshold}): {protective_count}")

        if hasattr(self.bulk_cox_ui, 'bulk_cox_sig_label'):
            self.bulk_cox_ui.bulk_cox_sig_label.setText(f"显著基因(CI不跨1,{sig_col_name}<{threshold}): {sig_count}")

    def _set_table_item(self, table, row_pos, col_pos, text, row_idx):
        """设置表格项，包含样式"""
        if self._table_text_color is None:
            self._init_table_styles()
        
        item = QTableWidgetItem(text)
        item.setForeground(QColor(self._table_text_color))
        
        bg_color = self._table_row_color_even if row_idx % 2 == 0 else self._table_row_color_odd
        item.setBackground(QColor(bg_color))
        
        table.setItem(row_pos, col_pos, item)

    def fill_overall_table(self, result_df):
        """填充总体列表表格"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_overall_table'):
            table = self.bulk_cox_ui.bulk_cox_overall_table
            table.setRowCount(0)

            if result_df is None or len(result_df) == 0:
                return

            for row_idx, (idx, row) in enumerate(result_df.iterrows()):
                row_pos = table.rowCount()
                table.insertRow(row_pos)

                self._set_table_item(table, row_pos, 0, str(row.get('gene', '')), row_idx)
                self._set_table_item(table, row_pos, 1, str(row.get('coef', '')), row_idx)
                self._set_table_item(table, row_pos, 2, str(row.get('HR', '')), row_idx)
                self._set_table_item(table, row_pos, 3, str(row.get('HR_lower95', '')), row_idx)
                self._set_table_item(table, row_pos, 4, str(row.get('HR_upper95', '')), row_idx)
                self._set_table_item(table, row_pos, 5, str(row.get('se', '')), row_idx)
                self._set_table_item(table, row_pos, 6, str(row.get('z', '')), row_idx)
                self._set_table_item(table, row_pos, 7, str(row.get('pvalue', '')), row_idx)
                self._set_table_item(table, row_pos, 8, str(row.get('FDR', '')), row_idx)
                self._set_table_item(table, row_pos, 9, str(row.get('direction', '')), row_idx)

            table.resizeColumnsToContents()

    def fill_risk_table(self, result_df, use_fdr=True, threshold=0.05):
        """填充风险基因表格（仅显示显著基因，CI不跨1）"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_risk_table'):
            table = self.bulk_cox_ui.bulk_cox_risk_table
            table.setRowCount(0)

            if result_df is None or len(result_df) == 0:
                return

            ci_not_cross_1 = (
                (result_df['HR_lower95'] > 1) & (result_df['HR_upper95'] > 1) |
                (result_df['HR_lower95'] < 1) & (result_df['HR_upper95'] < 1)
            )

            if use_fdr and 'FDR' in result_df.columns:
                sig_mask = (result_df['FDR'] < threshold) & ci_not_cross_1
            else:
                sig_mask = (result_df['pvalue'] < threshold) & ci_not_cross_1

            risk_df = result_df[sig_mask & (result_df['HR'] > 1)].copy()

            for row_idx, (idx, row) in enumerate(risk_df.iterrows()):
                row_pos = table.rowCount()
                table.insertRow(row_pos)

                self._set_table_item(table, row_pos, 0, str(row.get('gene', '')), row_idx)
                self._set_table_item(table, row_pos, 1, str(row.get('coef', '')), row_idx)
                self._set_table_item(table, row_pos, 2, str(row.get('HR', '')), row_idx)
                self._set_table_item(table, row_pos, 3, str(row.get('HR_lower95', '')), row_idx)
                self._set_table_item(table, row_pos, 4, str(row.get('HR_upper95', '')), row_idx)
                self._set_table_item(table, row_pos, 5, str(row.get('se', '')), row_idx)
                self._set_table_item(table, row_pos, 6, str(row.get('z', '')), row_idx)
                self._set_table_item(table, row_pos, 7, str(row.get('pvalue', '')), row_idx)
                self._set_table_item(table, row_pos, 8, str(row.get('FDR', '')), row_idx)
                self._set_table_item(table, row_pos, 9, str(row.get('direction', '')), row_idx)

            table.resizeColumnsToContents()

    def fill_protective_table(self, result_df, use_fdr=True, threshold=0.05):
        """填充保护基因表格（仅显示显著基因，CI不跨1）"""
        if hasattr(self.bulk_cox_ui, 'bulk_cox_protective_table'):
            table = self.bulk_cox_ui.bulk_cox_protective_table
            table.setRowCount(0)

            if result_df is None or len(result_df) == 0:
                return

            ci_not_cross_1 = (
                (result_df['HR_lower95'] > 1) & (result_df['HR_upper95'] > 1) |
                (result_df['HR_lower95'] < 1) & (result_df['HR_upper95'] < 1)
            )

            if use_fdr and 'FDR' in result_df.columns:
                sig_mask = (result_df['FDR'] < threshold) & ci_not_cross_1
            else:
                sig_mask = (result_df['pvalue'] < threshold) & ci_not_cross_1

            protective_df = result_df[sig_mask & (result_df['HR'] < 1)].copy()

            for row_idx, (idx, row) in enumerate(protective_df.iterrows()):
                row_pos = table.rowCount()
                table.insertRow(row_pos)

                self._set_table_item(table, row_pos, 0, str(row.get('gene', '')), row_idx)
                self._set_table_item(table, row_pos, 1, str(row.get('coef', '')), row_idx)
                self._set_table_item(table, row_pos, 2, str(row.get('HR', '')), row_idx)
                self._set_table_item(table, row_pos, 3, str(row.get('HR_lower95', '')), row_idx)
                self._set_table_item(table, row_pos, 4, str(row.get('HR_upper95', '')), row_idx)
                self._set_table_item(table, row_pos, 5, str(row.get('se', '')), row_idx)
                self._set_table_item(table, row_pos, 6, str(row.get('z', '')), row_idx)
                self._set_table_item(table, row_pos, 7, str(row.get('pvalue', '')), row_idx)
                self._set_table_item(table, row_pos, 8, str(row.get('FDR', '')), row_idx)
                self._set_table_item(table, row_pos, 9, str(row.get('direction', '')), row_idx)

            table.resizeColumnsToContents()

    def export_results(self, result_df, output_dir):
        """导出结果到CSV文件"""
        if result_df is None or len(result_df) == 0:
            return False

        try:
            os.makedirs(output_dir, exist_ok=True)

            overall_path = os.path.join(output_dir, "COX_overall_results.csv")
            result_df.to_csv(overall_path, index=False, encoding='utf-8')

            risk_df = result_df[result_df['HR'] > 1].copy()
            risk_path = os.path.join(output_dir, "COX_risk_genes.csv")
            risk_df.to_csv(risk_path, index=False, encoding='utf-8')

            protective_df = result_df[result_df['HR'] < 1].copy()
            protective_path = os.path.join(output_dir, "COX_protective_genes.csv")
            protective_df.to_csv(protective_path, index=False, encoding='utf-8')

            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False

    def update_r_version_label(self):
        """更新R版本标签"""
        if hasattr(self.bulk_cox_ui, 'r_version_label') and hasattr(self, 'analysis'):
            r_version = self.analysis.get_r_version()
            self.bulk_cox_ui.r_version_label.setText(f"R版本: {r_version}")

    def alert_error(self, message):
        if self.parent_window:
            wrong(self.parent_window, str(message))

    def _setup_gene_search(self):
        """初始化基因搜索功能"""
        if not hasattr(self.bulk_cox_ui, 'tab_widget'):
            return
        tables = [
            getattr(self.bulk_cox_ui, 'bulk_cox_overall_table', None),
            getattr(self.bulk_cox_ui, 'bulk_cox_risk_table', None),
            getattr(self.bulk_cox_ui, 'bulk_cox_protective_table', None),
        ]
        tables = [t for t in tables if t is not None]
        self.setup_gene_search(self.bulk_cox_ui.tab_widget, tables, gene_col=0)