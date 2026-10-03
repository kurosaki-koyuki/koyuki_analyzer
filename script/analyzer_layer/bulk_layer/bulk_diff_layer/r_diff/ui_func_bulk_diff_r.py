# -*- coding: utf-8 -*-
"""
bulk差异分析界面前端功能脚本 - R版本
负责界面控件的基本交互逻辑，如表格填充、日志输出等
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, TableSearcherMixin
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class BulkDiffRFunc(TableSearcherMixin):
    def __init__(self, bulk_diff_ui, parent_widget=None):
        self.bulk_diff_ui = bulk_diff_ui
        self.parent_widget = parent_widget
        self.result_df = None
        self._setup_gene_search()

    def log(self, message):
        """输出日志到日志框"""
        if hasattr(self.bulk_diff_ui, 'diff_log'):
            self.bulk_diff_ui.diff_log.append(message)

    def _parse_color(self, color_str):
        """解析颜色字符串为QColor"""
        if isinstance(color_str, QColor):
            return color_str
        if color_str.startswith('#'):
            return QColor(color_str)
        if color_str.startswith('rgba'):
            import re
            match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
            if match:
                r, g, b, a = match.groups()
                return QColor(int(r), int(g), int(b), int(float(a) * 255))
        return QColor(color_str)

    def update_stats(self, summary):
        """更新统计标签"""
        if hasattr(self.bulk_diff_ui, 'diff_total_label'):
            self.bulk_diff_ui.diff_total_label.setText(f"总基因: {summary['total']}")
        if hasattr(self.bulk_diff_ui, 'diff_up_label'):
            self.bulk_diff_ui.diff_up_label.setText(f"组1显著上调: {summary['up']}")
        if hasattr(self.bulk_diff_ui, 'diff_down_label'):
            self.bulk_diff_ui.diff_down_label.setText(f"组1显著下调: {summary['down']}")
        if hasattr(self.bulk_diff_ui, 'diff_stable_label'):
            self.bulk_diff_ui.diff_stable_label.setText(f"稳定基因: {summary['stable']}")

    def update_group_counts(self, group1_count, group2_count):
        """更新组样本数"""
        if hasattr(self.bulk_diff_ui, 'diff_group1_cell_label'):
            self.bulk_diff_ui.diff_group1_cell_label.setText(f"组1样本数: {group1_count}")
        if hasattr(self.bulk_diff_ui, 'diff_group2_cell_label'):
            self.bulk_diff_ui.diff_group2_cell_label.setText(f"组2样本数: {group2_count}")

    def fill_result_table(self, result_df, pval_threshold=0.05, logfc_threshold=0.25):
        """填充结果表格"""
        self.result_df = result_df

        if result_df is None or len(result_df) == 0:
            return

        # 总体列表
        self._fill_table(self.bulk_diff_ui.diff_result_table, result_df)

        # 显著上调
        up_df = result_df[(result_df['adj_p_val'] < pval_threshold) &
                          (result_df['log2FC'] > logfc_threshold)].copy()
        self._fill_table(self.bulk_diff_ui.diff_result_table_up, up_df)

        # 显著下调
        down_df = result_df[(result_df['adj_p_val'] < pval_threshold) &
                            (result_df['log2FC'] < -logfc_threshold)].copy()
        self._fill_table(self.bulk_diff_ui.diff_result_table_down, down_df)

    def _fill_table(self, table, df):
        """填充单个表格"""
        table.setRowCount(0)

        if df is None or len(df) == 0:
            return

        styles = get_mod_styles()
        table_text_color = styles.get('sub_text_color', '#87CEEB')
        table_fill_color = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        table_fill_alt = styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')
        table_highlight_bg = styles.get('sub_mutant_color', 'rgba(255, 107, 53, 0.3)')
        table_log2fc_up = styles.get('sub_mutant_color', '#FF6B35')
        table_log2fc_down = styles.get('sub_text_color', '#87CEEB')

        table.setRowCount(len(df))

        for row_idx, (_, row) in enumerate(df.iterrows()):
            row_bg = table_fill_alt if (row_idx % 2 == 0) else table_fill_color
            row_bg_color = self._parse_color(row_bg)

            adj_p = row.get('adj_p_val', 1)
            logfc = row.get('log2FC', 0)
            is_sig = adj_p < 0.05

            def format_pval(p):
                if p < 0.001:
                    return f"{p:.2e}"
                else:
                    return f"{p:.4f}"

            col_data = [
                str(row.get('gene', '')),
                f"{row.get('mean_group1', 0):.4f}",
                f"{row.get('mean_group2', 0):.4f}",
                f"{logfc:.4f}",
                format_pval(row.get('p_val', 1)),
                format_pval(adj_p),
                "yes" if is_sig else "no",
            ]

            if is_sig:
                if logfc > 0:
                    col_data.append("up")
                elif logfc < 0:
                    col_data.append("down")
                else:
                    col_data.append("stable")
            else:
                col_data.append("stable")

            for col_idx, val_str in enumerate(col_data):
                item = QTableWidgetItem(val_str)
                item.setForeground(self._parse_color(table_text_color))
                item.setBackground(row_bg_color)

                if col_idx == 5 and row.get('adj_p_val', 1) < 0.05:
                    item.setBackground(self._parse_color(table_highlight_bg))
                    item.setForeground(self._parse_color(table_text_color))
                elif col_idx == 3:
                    if isinstance(logfc, (int, float)) and logfc > 1:
                        item.setForeground(self._parse_color(table_log2fc_up))
                    elif isinstance(logfc, (int, float)) and logfc < -1:
                        item.setForeground(self._parse_color(table_log2fc_down))

                table.setItem(row_idx, col_idx, item)

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def get_selected_items(self, list_widget):
        """获取列表中选中的项"""
        selected = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item and item.checkState() == Qt.Checked:
                selected.append(str(item.text()))
        return selected

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def get_save_file_path(self, title, default_name, filter_text):
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    def _setup_gene_search(self):
        """初始化基因搜索功能 - 设置标签页和表格映射"""
        if not hasattr(self.bulk_diff_ui, 'diff_result_tabs'):
            return
        tables = [
            getattr(self.bulk_diff_ui, 'diff_result_table', None),
            getattr(self.bulk_diff_ui, 'diff_result_table_up', None),
            getattr(self.bulk_diff_ui, 'diff_result_table_down', None),
        ]
        tables = [t for t in tables if t is not None]
        self.setup_gene_search(self.bulk_diff_ui.diff_result_tabs, tables, gene_col=0)
