# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 差异训练类(diff_train)子层前端功能层

只负责：
1. 状态文本框日志输出
2. 进度条更新
3. 图片渲染到标签（各阶段出图）
4. 基因集文件选择显示
不绑定信号，不写业务算法
"""

from script.utils_layer.import_config import os
from script.utils_layer.gui_styles import ZoomableImageLabel


class BulkMachineLearningDiffTrainFunc:
    """机器学习差异训练类前端功能类"""

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
        """将图片显示到标签（支持 ZoomableImageLabel 与普通 QLabel）

        Args:
            image_label: 图片标签控件
            image_path: 图片文件路径
        """
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
        # 加载失败或未生成
        if isinstance(image_label, ZoomableImageLabel):
            try:
                image_label.set_pixmap(None)
            except Exception:
                pass
        image_label.setText("图片加载失败或未生成")

    # ---------- 下拉框填充 ----------

    def fill_gene_combo(self, gene_files, keep_selection=True):
        """填充基因集文件下拉框（来自 APPDATA/genelists 扫描）

        Args:
            gene_files: 基因集文件名列表
            keep_selection: 是否保留当前选择
        """
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
        """填充算法组合文件下拉框（来自 APPDATA/machinelearning 扫描）

        Args:
            methods_files: 算法组合文件名列表
            keep_selection: 是否保留当前选择
        """
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

    # ---------- 结果表格 / 文本展示辅助 ----------

    def _table_styles(self):
        """初始化表格填充所需颜色（交替行 + 文本色）"""
        from script.utils_layer.gui_styles import get_mod_styles
        styles = get_mod_styles()
        return {
            'text': styles.get('sub_text_color', '#87CEEB'),
            'even': styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.2)'),
            'odd': styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.4)'),
        }

    def fill_gene_table(self, table, txt_path):
        """将全基因列表填充到「基因列表」表格中（需求4/5：表格展示全部基因）

        Args:
            table: create_styled_table 返回的 QTableWidget
            txt_path: R 输出的全基因表（gene_all_list.txt，tab 分隔）
        """
        if table is None:
            return
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtGui import QColor

        col_colors = self._table_styles()

        def _clear():
            table.setRowCount(0)
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(
                ["基因名 (Gene)", "纳入模型数 (NModels)", "频率 (Frequency)", "平均排名 (AvgRank)"])
            table.horizontalHeader().setStretchLastSection(True)

        if not txt_path or not os.path.exists(txt_path):
            _clear()
            table.setRowCount(1)
            cell = QTableWidgetItem("未找到基因列表，请先运行阶段五 (gene_all_list.txt)")
            cell.setForeground(QColor(col_colors['text']))
            table.setSpan(0, 0, 1, 4)
            table.setItem(0, 0, cell)
            return

        import csv as _csv
        # 兼容按内容自动识别分隔符（gene_all_list.txt 为 tab 分隔）
        try:
            prober = open(txt_path, encoding='utf-8', errors='replace')
            first_lines = [next(prober, '') for _ in range(3)]
            prober.close()
        except Exception:
            first_lines = []
        sep = '\t'
        if first_lines and any(l.count(',') > l.count('\t') for l in first_lines):
            sep = ','
        rows = []
        with open(txt_path, encoding='utf-8', errors='replace', newline='') as f:
            rd = list(_csv.reader(f, delimiter=sep))
        header = rd[0] if rd else []
        rows = rd[1:]
        _clear()
        # 按表头索引填充，保证列顺序
        gene_col = header.index('Gene') if 'Gene' in header else 0
        nm_col = header.index('NModels') if 'NModels' in header else (1 if len(header) > 1 else 0)
        freq_col = header.index('Frequency') if 'Frequency' in header else (2 if len(header) > 2 else 0)
        rank_col = header.index('AvgRank') if 'AvgRank' in header else (3 if len(header) > 3 else 0)
        table.setRowCount(len(rows))
        table.setSortingEnabled(False)
        for r, rdata in enumerate(rows):
            if not rdata or len(rdata) < max(gene_col, nm_col, freq_col, rank_col) + 1:
                continue
            vals = [
                str(rdata[gene_col]),
                str(rdata[nm_col]),
                str(rdata[freq_col]),
                str(round(float(rdata[rank_col]), 3)) if rdata[rank_col] not in ('', 'Inf', 'nan') else 'Inf',
            ]
            bg = QColor(col_colors['even'] if r % 2 == 0 else col_colors['odd'])
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setForeground(QColor(col_colors['text']))
                item.setBackground(bg)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        table.viewport().update()

    def set_text_tab(self, tab_widget, text, tab_title):
        """在指定标签页显示文本内容（用于展示基因筛选等文本结果）

        Args:
            tab_widget: 标签页控件
            text: 要显示的文本
            tab_title: 标签页标题（用于选中）
        """
        if tab_widget is None or not text:
            return
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == tab_title:
                widget = tab_widget.widget(i)
                from PyQt5.QtWidgets import QPlainTextEdit
                te = widget.findChild(QPlainTextEdit)
                if te is not None:
                    te.setPlainText(text)
                tab_widget.setCurrentIndex(i)
                break
