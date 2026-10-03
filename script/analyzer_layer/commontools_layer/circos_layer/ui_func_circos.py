# -*- coding: utf-8 -*-
"""
Circos 圈图前端功能脚本 - 只负责前端显示（日志、下拉框内容、计数标签、表格填充、图片显示）
不绑定信号、不写业务算法、不解析基因列表文件（那是内核 CircosAnalysis 的事）
（风格照抄 commontools_layer/vennplot_layer/ui_func_vennplot.py）
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


def _parse_color(color_str):
    """解析主题色字符串（#hex / rgba(...)）为QColor"""
    if isinstance(color_str, QColor):
        return color_str
    if isinstance(color_str, str) and color_str.startswith('#'):
        return QColor(color_str)
    if isinstance(color_str, str) and color_str.startswith('rgba'):
        import re
        match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
        if match:
            r, g, b, a = match.groups()
            return QColor(int(r), int(g), int(b), int(float(a) * 255))
    return QColor(color_str)


def _fmt_num(value, nd=4):
    """数字安全格式化（None/NaN/非数字 → 原样字符串）"""
    try:
        if value is None:
            return ""
        f = float(value)
        if f != f:                       # NaN
            return "NaN"
        if abs(f - round(f)) < 1e-9:
            return str(int(round(f)))
        return ("%." + str(int(nd)) + "f") % f
    except (TypeError, ValueError):
        return str(value)


class CircosFunc:
    """Circos 前端功能类 - 纯前端显示操作"""

    def __init__(self, circos_ui, parent_widget=None):
        self.circos_ui = circos_ui
        self.parent_widget = parent_widget

    # ------------------------------------------------------------ 日志与提示
    def log(self, message):
        """追加日志消息"""
        if hasattr(self.circos_ui, 'circos_log'):
            self.circos_ui.circos_log.append(str(message))

    def clear_log(self):
        if hasattr(self.circos_ui, 'circos_log'):
            self.circos_ui.circos_log.clear()

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
        """弹出保存文件对话框，返回用户选择的路径"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    def update_styles(self):
        """转发主题刷新到布局层"""
        if hasattr(self.circos_ui, 'update_styles'):
            self.circos_ui.update_styles()

    # ---------------------------------------------------------- 下拉框与标签
    def set_combo_items(self, combo, items, keep_current=True):
        """重填下拉框（保持当前项尽量不变）"""
        if combo is None:
            return
        old_text = combo.currentText() if keep_current else ""
        combo.blockSignals(True)
        try:
            combo.clear()
            for it in items:
                combo.addItem(str(it))
            if keep_current and old_text:
                idx = combo.findText(old_text)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        finally:
            combo.blockSignals(False)

    def update_genelist_combo(self, paths):
        """用内核 scan_gene_lists() 的结果填充基因列表下拉（显示文件名，itemData 存绝对路径）"""
        combo = getattr(self.circos_ui, 'circos_genelist_combo', None)
        if combo is None:
            return 0

        paths = list(paths or [])
        combo.blockSignals(True)
        try:
            combo.clear()
            for p in paths:
                text = os.path.basename(str(p))
                combo.addItem(text, str(p))
            if combo.count() > 0:
                combo.setCurrentIndex(0)
        finally:
            combo.blockSignals(False)

        self.update_genelist_hint(len(paths))
        return len(paths)

    def update_genelist_hint(self, count):
        """更新「共 N 个基因列表文件」提示"""
        if hasattr(self.circos_ui, 'circos_genelist_hint'):
            self.circos_ui.circos_genelist_hint.setText(f"共 {int(count)} 个基因列表文件")

    def update_gene_count(self, count):
        """更新「解析到 N 个基因」计数标签"""
        if hasattr(self.circos_ui, 'circos_gene_count_label'):
            self.circos_ui.circos_gene_count_label.setText(f"解析到 {int(count)} 个基因")

    def clear_gene_count(self):
        self.update_gene_count(0)

    # -------------------------------------------------------------- 图片显示
    def display_plot(self, plot_path):
        """把结果图显示到可缩放图片标签上"""
        label = getattr(self.circos_ui, 'circos_plot_label', None)
        if label is None:
            return False
        if not plot_path or not os.path.exists(plot_path):
            return False
        pixmap = QPixmap(plot_path)
        if pixmap.isNull():
            return False
        if hasattr(label, 'set_pixmap'):
            label.set_pixmap(pixmap)
        else:
            label.setPixmap(pixmap)
        return True

    # ------------------------------------------------------------ 表格填充
    def _table_style_tokens(self):
        from script.utils_layer.gui_styles import get_mod_styles
        styles = get_mod_styles()
        return (styles.get('sub_text_color', '#87CEEB'),
                styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)'),
                styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)'))

    def _fill_table(self, table_widget, headers, rows, stretch_last=True):
        """通用表格填充（斑马纹 + 主题色，照抄韦恩图页的做法）"""
        if table_widget is None:
            return

        table_text_color, table_fill_color, table_fill_alt = self._table_style_tokens()

        table_widget.clear()
        table_widget.setRowCount(len(rows))
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)

        for i, row_data in enumerate(rows):
            row_bg = table_fill_alt if (i % 2 == 0) else table_fill_color
            row_bg_color = _parse_color(row_bg)
            for j, val in enumerate(row_data):
                item = QTableWidgetItem("" if val is None else str(val))
                item.setForeground(_parse_color(table_text_color))
                item.setBackground(row_bg_color)
                item.setTextAlignment(Qt.AlignCenter)
                table_widget.setItem(i, j, item)

        table_widget.resizeColumnsToContents()
        table_widget.horizontalHeader().setStretchLastSection(bool(stretch_last))

    def fill_genes_table(self, genes):
        """页签「基因定位表」：
        symbol/chrom/start/end/length/cytoband/gene_density/gc/status"""
        headers = ["symbol", "chrom", "start", "end", "length",
                   "cytoband", "gene_density", "gc", "status"]
        rows = []
        for g in (genes or []):
            if not isinstance(g, dict):
                continue
            rows.append([
                g.get('symbol', ''),
                g.get('chrom', ''),
                g.get('start', ''),
                g.get('end', ''),
                g.get('length', ''),
                g.get('cytoband', ''),
                _fmt_num(g.get('gene_density')),
                _fmt_num(g.get('gc')),
                g.get('status', 'OK'),
            ])
        self._fill_table(getattr(self.circos_ui, 'circos_table', None), headers, rows)

    def fill_missing_table(self, missing):
        """页签「未匹配基因」：symbol/reason（未匹配的必须可见，不许静默丢弃）

        missing 既支持 ['NOTAGENE'] 也支持 [{'symbol':..,'reason':..}]
        """
        headers = ["symbol", "reason"]
        rows = []
        for m in (missing or []):
            if isinstance(m, dict):
                rows.append([m.get('symbol', ''), m.get('reason', '未匹配（不在基因坐标表中）')])
            else:
                rows.append([m, '未匹配（不在基因坐标表中）'])
        self._fill_table(getattr(self.circos_ui, 'circos_missing_table', None), headers, rows)

    def clear_tables(self):
        self._fill_table(getattr(self.circos_ui, 'circos_table', None),
                         ["symbol", "chrom", "start", "end", "length",
                          "cytoband", "gene_density", "gc", "status"], [])
        self._fill_table(getattr(self.circos_ui, 'circos_missing_table', None),
                         ["symbol", "reason"], [])

    def clear_plot(self):
        """把图片标签恢复成空白"""
        label = getattr(self.circos_ui, 'circos_plot_label', None)
        if label is None:
            return
        try:
            if hasattr(label, '_original_pixmap'):
                label._original_pixmap = None
            if hasattr(label, '_scaled_pixmap'):
                label._scaled_pixmap = None
            label.clear()
        except Exception:
            pass
