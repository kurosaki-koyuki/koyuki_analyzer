# -*- coding: utf-8 -*-
"""
R版本差异分析前端功能脚本 - 只负责前端显示、控件内容更新、表格填充、火山图渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, TableSearcherMixin
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class RDiffFunc(TableSearcherMixin):
    """R版本差异分析前端功能类 - 纯前端显示操作"""

    def __init__(self, r_diff_ui, parent_widget=None):
        self.r_diff_ui = r_diff_ui
        self.parent_widget = parent_widget
        self._setup_gene_search()

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
        combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        list_widget.clear()
        list_widget.addItems(items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def update_group_lists(self, group_col, unique_vals):
        if hasattr(self.r_diff_ui, 'r_diff_group1_list'):
            self.fill_list_widget(self.r_diff_ui.r_diff_group1_list, unique_vals, select_all=False)
        if hasattr(self.r_diff_ui, 'r_diff_group2_list'):
            self.fill_list_widget(self.r_diff_ui.r_diff_group2_list, unique_vals, select_all=False)

    def update_diff_stats(self, df, group1_items, group2_items=None):
        if group2_items is None:
            group2_items = []
        
        group1_name = "+".join(group1_items) if len(group1_items) > 1 else (group1_items[0] if group1_items else "组1")
        group2_name = "+".join(group2_items) if len(group2_items) > 1 else (group2_items[0] if group2_items else "组2")

        total_count = len(df)
        up_count = len(df[df['change'] == 'up']) if 'change' in df.columns else 0
        down_count = len(df[df['change'] == 'down']) if 'change' in df.columns else 0
        stable_count = len(df[df['change'] == 'stable']) if 'change' in df.columns else 0

        group1_cells = df['n_cells_group1'].iloc[0] if len(df) > 0 and 'n_cells_group1' in df.columns else 0
        group2_cells = df['n_cells_group2'].iloc[0] if len(df) > 0 and 'n_cells_group2' in df.columns else 0

        self.r_diff_ui.r_diff_group1_cell_label.setText(f"{group1_name}细胞数: {group1_cells}")
        self.r_diff_ui.r_diff_group2_cell_label.setText(f"{group2_name}细胞数: {group2_cells}")
        self.r_diff_ui.r_diff_up_label.setText(f"{group1_name}显著上调: {up_count}")
        self.r_diff_ui.r_diff_down_label.setText(f"{group1_name}显著下调: {down_count}")
        self.r_diff_ui.r_diff_stable_label.setText(f"稳定基因: {stable_count}")
        self.r_diff_ui.r_diff_total_label.setText(f"总基因: {total_count}")

        if hasattr(self.r_diff_ui, 'r_diff_result_tabs'):
            self.r_diff_ui.r_diff_result_tabs.setTabText(1, f"{group1_name}显著上调")
            self.r_diff_ui.r_diff_result_tabs.setTabText(2, f"{group1_name}显著下调")

    def fill_result_tables(self, df, df_up=None, df_down=None):
        self._fill_table(self.r_diff_ui.r_diff_result_table, df)
        if df_up is not None:
            self._fill_table(self.r_diff_ui.r_diff_result_table_up, df_up)
        if df_down is not None:
            self._fill_table(self.r_diff_ui.r_diff_result_table_down, df_down)
        self.update_stats_info(df, df_up, df_down)

    def update_stats_info(self, df, df_up, df_down):
        """更新统计信息显示"""
        if not hasattr(self.r_diff_ui, 'r_diff_group1_cell_label'):
            return
        
        n_cells_group1 = int(df['n_cells_group1'].iloc[0]) if len(df) > 0 and 'n_cells_group1' in df.columns else 0
        n_cells_group2 = int(df['n_cells_group2'].iloc[0]) if len(df) > 0 and 'n_cells_group2' in df.columns else 0
        
        up_count = len(df_up) if df_up is not None else 0
        down_count = len(df_down) if df_down is not None else 0
        stable_count = len(df) - up_count - down_count if df is not None else 0
        total_count = len(df) if df is not None else 0
        
        self.r_diff_ui.r_diff_group1_cell_label.setText(f"组1细胞数: {n_cells_group1}")
        self.r_diff_ui.r_diff_group2_cell_label.setText(f"组2细胞数: {n_cells_group2}")
        self.r_diff_ui.r_diff_up_label.setText(f"组1显著上调: {up_count}")
        self.r_diff_ui.r_diff_down_label.setText(f"组1显著下调: {down_count}")
        self.r_diff_ui.r_diff_stable_label.setText(f"稳定基因: {stable_count}")
        self.r_diff_ui.r_diff_total_label.setText(f"总基因: {total_count}")

    def _fill_table(self, table_widget, df):
        styles = get_mod_styles()

        table_text_color = styles.get('sub_text_color', '#87CEEB')
        table_fill_color = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        table_fill_alt = styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')
        table_highlight_bg = styles.get('sub_mutant_color', 'rgba(255, 255, 200, 0.3)')
        table_log2fc_up = styles.get('sub_mutant_color', '#FF6B35')
        table_log2fc_down = styles.get('sub_text_color', '#87CEEB')

        def parse_color(color_str):
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

        table_widget.setRowCount(len(df))
        table_widget.setColumnCount(len(df.columns))
        table_widget.setHorizontalHeaderLabels(list(df.columns))

        for i, row in enumerate(df.itertuples(index=False)):
            row_bg = table_fill_alt if (i % 2 == 0) else table_fill_color
            row_bg_color = parse_color(row_bg)

            for j, val in enumerate(row):
                if isinstance(val, float):
                    if df.columns[j] in ["log2FC", "p_val", "p_val_adj", "p_val_adj_BH"]:
                        val_str = f"{val:.4f}"
                    else:
                        val_str = f"{val:.2f}"
                else:
                    val_str = str(val)

                item = QTableWidgetItem(val_str)
                item.setForeground(parse_color(table_text_color))
                item.setBackground(row_bg_color)

                if df.columns[j] in ["p_val_adj", "p_val_adj_BH"] and isinstance(val, float) and val < 0.05:
                    item.setBackground(parse_color(table_highlight_bg))
                    item.setForeground(parse_color(table_text_color))
                elif df.columns[j] == "log2FC":
                    if isinstance(val, float):
                        if val > 1:
                            item.setForeground(parse_color(table_log2fc_up))
                        elif val < -1:
                            item.setForeground(parse_color(table_log2fc_down))

                table_widget.setItem(i, j, item)

        table_widget.resizeColumnsToContents()
        table_widget.horizontalHeader().setStretchLastSection(True)

    def render_volcano_plot(self, df, group_col, selected_groups):
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            import numpy as np

            styles = get_mod_styles()

            volcano_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
            volcano_text = styles.get('sub_text_color', '#87CEEB')
            volcano_mutant = styles.get('sub_mutant_color', '#FF6B35')
            volcano_stable = styles.get('sub_border_color', '#666666')

            def convert_to_hex(rgba_str):
                import re
                if rgba_str.startswith('#'):
                    return rgba_str
                match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*[\d.]+\)', rgba_str)
                if match:
                    r, g, b = match.groups()
                    return f'#{int(r):02x}{int(g):02x}{int(b):02x}'
                return rgba_str

            volcano_text_hex = convert_to_hex(volcano_text)
            volcano_mutant_hex = convert_to_hex(volcano_mutant)
            volcano_stable_hex = convert_to_hex(volcano_stable)

            fig = Figure(figsize=(8, 6), dpi=100)
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)

            df_plot = df.copy()
            pval_col = 'p_val_adj' if 'p_val_adj' in df.columns else ('p_val_adj_BH' if 'p_val_adj_BH' in df.columns else 'p_val')
            df_plot['-log10(p值)'] = -np.log10(df_plot[pval_col] + 1e-300)

            ax.set_facecolor(volcano_bg)
            fig.patch.set_alpha(0)

            if 'change' in df_plot.columns:
                ax.scatter(df_plot[df_plot['change'] != 'up']['log2FC'],
                          df_plot[df_plot['change'] != 'up']['-log10(p值)'],
                          c=volcano_stable_hex, alpha=0.5, s=20, label='Not significant')
                ax.scatter(df_plot[df_plot['change'] == 'up']['log2FC'],
                          df_plot[df_plot['change'] == 'up']['-log10(p值)'],
                          c=volcano_mutant_hex, alpha=0.7, s=30, label='Up')
                ax.scatter(df_plot[df_plot['change'] == 'down']['log2FC'],
                          df_plot[df_plot['change'] == 'down']['-log10(p值)'],
                          c=volcano_text_hex, alpha=0.7, s=30, label='Down')
            else:
                ax.scatter(df_plot['log2FC'], df_plot['-log10(p值)'],
                          c=volcano_stable_hex, alpha=0.5, s=20)

            ax.set_xlabel('log2 Fold Change', fontsize=12, color=volcano_text_hex)
            ax.set_ylabel('-log10(p-value)', fontsize=12, color=volcano_text_hex)
            ax.set_title(f'Differential Expression (R MAST)', fontsize=14, color=volcano_text_hex)
            if 'change' in df_plot.columns:
                ax.legend()

            ax.axhline(y=-np.log10(0.05), color=volcano_stable_hex, linestyle='--', alpha=0.5)
            ax.axvline(x=1, color=volcano_stable_hex, linestyle='--', alpha=0.5)
            ax.axvline(x=-1, color=volcano_stable_hex, linestyle='--', alpha=0.5)

            ax.tick_params(axis='x', colors=volcano_text_hex)
            ax.tick_params(axis='y', colors=volcano_text_hex)
            ax.spines['bottom'].set_color(volcano_stable_hex)
            ax.spines['top'].set_color(volcano_stable_hex)
            ax.spines['left'].set_color(volcano_stable_hex)
            ax.spines['right'].set_color(volcano_stable_hex)

            fig.tight_layout()

            canvas.draw()
            pixmap = canvas.grab()
            self.r_diff_ui.r_diff_volcano_label.setPixmap(pixmap)

            import matplotlib.pyplot as plt
            plt.close(fig)
        except Exception as e:
            if hasattr(self.r_diff_ui, 'r_diff_log'):
                self.r_diff_ui.r_diff_log.append(f"火山图绘制失败: {str(e)}")

    def log(self, message):
        if hasattr(self.r_diff_ui, 'r_diff_log'):
            self.r_diff_ui.r_diff_log.append(message)

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
        """初始化基因搜索功能"""
        if not hasattr(self.r_diff_ui, 'r_diff_result_tabs'):
            return
        tables = [
            getattr(self.r_diff_ui, 'r_diff_result_table', None),
            getattr(self.r_diff_ui, 'r_diff_result_table_up', None),
            getattr(self.r_diff_ui, 'r_diff_result_table_down', None),
        ]
        tables = [t for t in tables if t is not None]
        self.setup_gene_search(self.r_diff_ui.r_diff_result_tabs, tables, gene_col=0)
