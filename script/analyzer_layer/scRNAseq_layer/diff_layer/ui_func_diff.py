# -*- coding: utf-8 -*-
"""
差异分析前端功能脚本 - 只负责前端显示、控件内容更新、表格填充、火山图渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class DiffFunc:
    """差异分析前端功能类 - 纯前端显示操作"""

    def __init__(self, diff_ui, parent_widget=None):
        self.diff_ui = diff_ui
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

    def fill_list_widget(self, list_widget, items, select_all=True):
        """填充列表控件并可选全选"""
        list_widget.clear()
        list_widget.addItems(items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def update_group_list(self, group_col, unique_vals):
        """更新分组列表"""
        if hasattr(self.diff_ui, 'diff_group_list'):
            self.fill_list_widget(self.diff_ui.diff_group_list, unique_vals)

    # ---------- 统计标签更新 ----------

    def update_diff_stats(self, df, selected_groups):
        """更新差异分析统计结果显示"""
        group1_name = selected_groups[0] if len(selected_groups) > 0 else "组1"
        group2_name = selected_groups[1] if len(selected_groups) > 1 else "组2"

        total_count = len(df)
        up_count = len(df[df['change'] == 'up'])
        down_count = len(df[df['change'] == 'down'])
        stable_count = len(df[df['change'] == 'stable'])

        group1_cells = df['n_cells_group1'].iloc[0] if len(df) > 0 else 0
        group2_cells = df['n_cells_group2'].iloc[0] if len(df) > 0 else 0

        self.diff_ui.diff_group1_cell_label.setText(f"{group1_name}细胞数: {group1_cells}")
        self.diff_ui.diff_group2_cell_label.setText(f"{group2_name}细胞数: {group2_cells}")
        self.diff_ui.diff_up_label.setText(f"{group1_name}显著上调: {up_count}")
        self.diff_ui.diff_down_label.setText(f"{group1_name}显著下调: {down_count}")
        self.diff_ui.diff_stable_label.setText(f"稳定基因: {stable_count}")
        self.diff_ui.diff_total_label.setText(f"总基因: {total_count}")

        if hasattr(self.diff_ui, 'diff_result_tabs'):
            self.diff_ui.diff_result_tabs.setTabText(1, f"{group1_name}显著上调")
            self.diff_ui.diff_result_tabs.setTabText(2, f"{group1_name}显著下调")

    # ---------- 表格填充 ----------

    def fill_result_tables(self, df, df_up, df_down):
        """填充三个结果表格"""
        self._fill_table(self.diff_ui.diff_result_table, df)
        self._fill_table(self.diff_ui.diff_result_table_up, df_up)
        self._fill_table(self.diff_ui.diff_result_table_down, df_down)

    def _fill_table(self, table_widget, df):
        """填充单个表格"""
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
                    if df.columns[j] in ["log2FC", "p_val", "p_val_adj"]:
                        val_str = f"{val:.4f}"
                    else:
                        val_str = f"{val:.2f}"
                else:
                    val_str = str(val)

                item = QTableWidgetItem(val_str)
                item.setForeground(parse_color(table_text_color))
                item.setBackground(row_bg_color)

                if df.columns[j] == "p_val_adj" and isinstance(val, float) and val < 0.05:
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

    # ---------- 火山图渲染 ----------

    def render_volcano_plot(self, df, group_col, selected_groups):
        """渲染火山图到 QLabel"""
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
            df_plot['-log10(p值)'] = -np.log10(df_plot['p_val'] + 1e-300)

            ax.set_facecolor(volcano_bg)
            fig.patch.set_alpha(0)

            ax.scatter(df_plot[df_plot['change'] != 'up']['log2FC'],
                      df_plot[df_plot['change'] != 'up']['-log10(p值)'],
                      c=volcano_stable_hex, alpha=0.5, s=20, label='Not significant')
            ax.scatter(df_plot[df_plot['change'] == 'up']['log2FC'],
                      df_plot[df_plot['change'] == 'up']['-log10(p值)'],
                      c=volcano_mutant_hex, alpha=0.7, s=30, label='Up')
            ax.scatter(df_plot[df_plot['change'] == 'down']['log2FC'],
                      df_plot[df_plot['change'] == 'down']['-log10(p值)'],
                      c=volcano_text_hex, alpha=0.7, s=30, label='Down')

            ax.set_xlabel('log2 Fold Change', fontsize=12, color=volcano_text_hex)
            ax.set_ylabel('-log10(p-value)', fontsize=12, color=volcano_text_hex)
            ax.set_title(f'Differential Expression', fontsize=14, color=volcano_text_hex)
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
            self.diff_ui.diff_volcano_label.setPixmap(pixmap)

            import matplotlib.pyplot as plt
            plt.close(fig)
        except Exception as e:
            if hasattr(self.diff_ui, 'diff_log'):
                self.diff_ui.diff_log.append(f"火山图绘制失败: {str(e)}")

    # ---------- 日志 ----------

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.diff_ui, 'diff_log'):
            self.diff_ui.diff_log.append(message)

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
