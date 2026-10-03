# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 生存训练类(surv_train)子层前端功能层

只负责：
1. 状态文本框日志输出
2. 进度条更新
3. 图片渲染到标签（各阶段出图）
4. 基因列表表格填充
不绑定信号，不写业务算法
"""

from script.utils_layer.import_config import os
from script.utils_layer.gui_styles import ZoomableImageLabel


class BulkMachineLearningSurvTrainFunc:
    """机器学习生存训练类前端功能类"""

    def __init__(self, ui_instance):
        self.ui = ui_instance

    # ---------- 日志 ----------

    def log(self, message):
        """追加状态消息到状态文本框"""
        if hasattr(self.ui, 'status_text') and self.ui.status_text is not None:
            self.ui.status_text.append(str(message))
            try:
                bar = self.ui.status_text.verticalScrollBar()
                if bar is not None:
                    bar.setValue(bar.maximum())
            except Exception:
                pass

    def log_clear(self):
        """清空状态文本框"""
        if hasattr(self.ui, 'status_text') and self.ui.status_text is not None:
            self.ui.status_text.clear()

    # ---------- 进度条 ----------

    def set_progress(self, value, visible=True):
        """更新进度条
        Args:
            value: 进度值 (0-100)，None 表示不确定模式
            visible: 是否显示进度条
        """
        if not hasattr(self.ui, 'progress_bar') or self.ui.progress_bar is None:
            return
        self.ui.progress_bar.setVisible(visible)
        if value is None:
            self.ui.progress_bar.setRange(0, 0)
        else:
            self.ui.progress_bar.setRange(0, 100)
            self.ui.progress_bar.setValue(int(value))

    # ---------- 图片显示 ----------

    def set_image(self, image_label, image_path):
        """将图片显示到标签（支持 ZoomableImageLabel 与普通 QLabel）"""
        if image_label is None:
            return
        if image_path and os.path.exists(image_path):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                if isinstance(image_label, ZoomableImageLabel):
                    image_label.set_pixmap(pixmap)
                else:
                    image_label.setPixmap(pixmap)
                return
        if isinstance(image_label, ZoomableImageLabel):
            try:
                image_label.set_pixmap(None)
            except Exception:
                pass
        image_label.setText("图片加载失败或未生成")

    # ---------- 下拉框填充 ----------

    def fill_gene_combo(self, gene_files, keep_selection=True):
        """填充基因集文件下拉框（来自 APPDATA/genelists 扫描）"""
        if not hasattr(self.ui, 'gene_file_combo') or self.ui.gene_file_combo is None:
            return
        combo = self.ui.gene_file_combo
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("不使用基因集")
        for f in gene_files:
            combo.addItem(f)
        if keep_selection and current and combo.findText(current) >= 0:
            combo.setCurrentText(current)
        combo.blockSignals(False)

    def fill_methods_combo(self, methods_files, keep_selection=True):
        """填充算法组合文件下拉框（来自 APPDATA/machinelearning 扫描）"""
        if not hasattr(self.ui, 'methods_combo') or self.ui.methods_combo is None:
            return
        combo = self.ui.methods_combo
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        for f in methods_files:
            combo.addItem(f)
        if keep_selection and current and combo.findText(current) >= 0:
            combo.setCurrentText(current)
        combo.blockSignals(False)

    # ---------- 结果表格填充 ----------

    def _table_styles(self):
        """初始化表格填充所需颜色（交替行 + 文本色）"""
        from script.utils_layer.gui_styles import get_mod_styles
        styles = get_mod_styles()
        return {
            'text': styles.get('sub_text_color', '#87CEEB'),
            'even': styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.2)'),
            'odd': styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.4)'),
        }

    def fill_method_table(self, table, txt_path):
        """将算法性能排序表填充到「算法性能」表格（method_performance.txt）"""
        if table is None:
            return
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtGui import QColor
        col_colors = self._table_styles()

        def _clear():
            table.setRowCount(0)
            table.setColumnCount(0)
            table.setHorizontalHeaderLabels([])

        if not txt_path or not os.path.exists(txt_path):
            _clear()
            table.setRowCount(1)
            table.setColumnCount(1)
            cell = QTableWidgetItem("未找到算法性能表，请先运行阶段三 (method_performance.txt)")
            cell.setForeground(QColor(col_colors['text']))
            table.setHorizontalHeaderLabels(["提示"])
            table.setItem(0, 0, cell)
            return

        import csv as _csv
        sep = '\t'
        first_lines = []
        try:
            with open(txt_path, encoding='utf-8', errors='replace') as f:
                first_lines = [next(f, '') for _ in range(3)]
        except Exception:
            first_lines = []
        if first_lines and any(l.count(',') > l.count('\t') for l in first_lines):
            sep = ','
        rows = []
        with open(txt_path, encoding='utf-8', errors='replace', newline='') as f:
            rd = list(_csv.reader(f, delimiter=sep))
        header = rd[0] if rd else []
        rows = rd[1:]
        _clear()
        table.setColumnCount(len(header))
        table.setHorizontalHeaderLabels(header)
        table.setRowCount(len(rows))
        table.setSortingEnabled(False)
        for r, rdata in enumerate(rows):
            if not rdata:
                continue
            bg = QColor(col_colors['even'] if r % 2 == 0 else col_colors['odd'])
            for c in range(len(header)):
                v = rdata[c] if c < len(rdata) else ""
                # 数值保留 3 位
                try:
                    v = f"{float(v):.3f}"
                except (ValueError, TypeError):
                    pass
                item = QTableWidgetItem(str(v))
                item.setForeground(QColor(col_colors['text']))
                item.setBackground(bg)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        table.viewport().update()

    def fill_gene_table(self, table, txt_path):
        """将最优算法生存基因表填充到「最优基因」表格（surv_best_gene_list.txt / best_method_genes_*.txt）"""
        if table is None:
            return
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtGui import QColor
        col_colors = self._table_styles()

        def _clear():
            table.setRowCount(0)
            table.setColumnCount(0)
            table.setHorizontalHeaderLabels([])

        if not txt_path or not os.path.exists(txt_path):
            _clear()
            table.setRowCount(1)
            table.setColumnCount(1)
            cell = QTableWidgetItem("未找到生存基因表，请先运行阶段四 (surv_best_gene_list.txt)")
            cell.setForeground(QColor(col_colors['text']))
            table.setHorizontalHeaderLabels(["提示"])
            table.setItem(0, 0, cell)
            return

        import csv as _csv
        sep = '\t'
        first_lines = []
        try:
            with open(txt_path, encoding='utf-8', errors='replace') as f:
                first_lines = [next(f, '') for _ in range(3)]
        except Exception:
            first_lines = []
        if first_lines and any(l.count(',') > l.count('\t') for l in first_lines):
            sep = ','
        rows = []
        with open(txt_path, encoding='utf-8', errors='replace', newline='') as f:
            rd = list(_csv.reader(f, delimiter=sep))
        header = rd[0] if rd else []
        rows = rd[1:]
        _clear()
        table.setColumnCount(len(header))
        table.setHorizontalHeaderLabels(header)
        table.setRowCount(len(rows))
        table.setSortingEnabled(False)
        for r, rdata in enumerate(rows):
            if not rdata:
                continue
            bg = QColor(col_colors['even'] if r % 2 == 0 else col_colors['odd'])
            for c in range(len(header)):
                v = rdata[c] if c < len(rdata) else ""
                try:
                    v = f"{float(v):.3f}"
                except (ValueError, TypeError):
                    pass
                item = QTableWidgetItem(str(v))
                item.setForeground(QColor(col_colors['text']))
                item.setBackground(bg)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        table.viewport().update()
