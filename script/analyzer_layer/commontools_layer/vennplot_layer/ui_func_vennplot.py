# -*- coding: utf-8 -*-
"""
韦恩图前端功能脚本 - 只负责前端显示、控件内容更新等
不绑定信号，不写业务算法，不处理导出逻辑
表格相关功能已移至EditableInputTable类（gui_styles.py）
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class VennPlotFunc:
    """韦恩图前端功能类 - 纯前端显示操作"""

    def __init__(self, vennplot_ui, parent_widget=None):
        self.vennplot_ui = vennplot_ui
        self.parent_widget = parent_widget

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.vennplot_ui, 'venn_log'):
            self.vennplot_ui.venn_log.append(message)

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

    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    def clear_table(self):
        """清空表格数据"""
        if hasattr(self.vennplot_ui, 'venn_table'):
            self.vennplot_ui.venn_table.clear_table()
            self.log("[INFO] 已清空表格数据")

    def undo_table(self):
        """撤销上一步操作"""
        if hasattr(self.vennplot_ui, 'venn_table'):
            result = self.vennplot_ui.venn_table.undo()
            if result:
                self.log("[INFO] 已撤销上一步操作")
            else:
                self.log("[INFO] 没有可撤销的操作")

    def apply_table_params(self):
        """应用表格参数（行列数）"""
        if not hasattr(self.vennplot_ui, 'venn_table'):
            return

        new_rows = self.vennplot_ui.venn_row_spin.value()
        new_cols = self.vennplot_ui.venn_col_spin.value()
        
        self.log(f"[INFO] 正在调整表格到 {new_rows} 行 × {new_cols} 列...")
        QApplication.processEvents()

        restore_count = self.vennplot_ui.venn_table.apply_params(new_rows, new_cols)
        
        self.log(f"[INFO] 表格已调整为 {new_rows} 行 × {new_cols} 列")

    def copy_table(self):
        """复制选中的单元格内容"""
        if hasattr(self.vennplot_ui, 'venn_table'):
            result = self.vennplot_ui.venn_table.copy_selection()
            if result:
                self.log(f"[INFO] 已复制数据")

    def cut_table(self):
        """剪切选中的单元格内容"""
        if hasattr(self.vennplot_ui, 'venn_table'):
            result = self.vennplot_ui.venn_table.cut_selection()
            if result:
                self.log(f"[INFO] 已剪切数据")

    def paste_table(self):
        """从剪贴板粘贴数据"""
        if hasattr(self.vennplot_ui, 'venn_table'):
            count = self.vennplot_ui.venn_table.paste_from_clipboard()
            if count > 0:
                self.log(f"[INFO] 已粘贴 {count} 个单元格")

    def handle_key_press_event(self, event):
        """处理表格的键盘事件"""
        if not hasattr(self.vennplot_ui, 'venn_table'):
            return

        if event.key() == Qt.Key_Delete:
            count = self.vennplot_ui.venn_table.delete_selected()
            if count > 0:
                self.log(f"[INFO] 已删除 {count} 个单元格")
        else:
            QTableWidget.keyPressEvent(self.vennplot_ui.venn_table, event)

    def fill_intersection_matrix(self, header, matrix_data):
        """填充交集矩阵表格（参考差异分析表格填充方式）"""
        from script.utils_layer.gui_styles import get_mod_styles

        if not hasattr(self.vennplot_ui, 'venn_intersection_matrix_table'):
            return

        table_widget = self.vennplot_ui.venn_intersection_matrix_table
        styles = get_mod_styles()

        table_text_color = styles.get('sub_text_color', '#87CEEB')
        table_fill_color = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        table_fill_alt = styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')

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

        num_rows = len(matrix_data)
        num_cols = len(header)

        table_widget.setRowCount(num_rows)
        table_widget.setColumnCount(num_cols)
        table_widget.setHorizontalHeaderLabels(header)

        for i, row_data in enumerate(matrix_data):
            row_bg = table_fill_alt if (i % 2 == 0) else table_fill_color
            row_bg_color = parse_color(row_bg)

            for j, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setForeground(parse_color(table_text_color))
                item.setBackground(row_bg_color)
                item.setTextAlignment(Qt.AlignCenter)

                table_widget.setItem(i, j, item)

        table_widget.resizeColumnsToContents()
        table_widget.horizontalHeader().setStretchLastSection(True)