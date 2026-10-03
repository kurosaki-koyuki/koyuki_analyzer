# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 数据加载类子层前端功能层

只负责：
1. 状态文本框日志输出
2. 数据集列表控件内容更新与选中读取
3. PCA 图片渲染到标签
不绑定信号，不写业务算法
"""

from script.utils_layer.import_config import os
from script.utils_layer.gui_styles import ZoomableImageLabel


class BulkMachineLearningLoadingFunc:
    """机器学习数据加载类前端功能类"""

    def __init__(self, ui_instance):
        self.ui = ui_instance

    # ---------- 日志 ----------

    def log(self, message):
        """追加状态消息到状态文本框"""
        if hasattr(self.ui, 'status_text') and self.ui.status_text is not None:
            self.ui.status_text.append(str(message))
            # 滚动到底部
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

    # ---------- 数据集列表 ----------

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
            # 不确定模式（忙碌指示器）
            self.ui.progress_bar.setRange(0, 0)
        else:
            self.ui.progress_bar.setRange(0, 100)
            self.ui.progress_bar.setValue(int(value))

    def set_dataset_list(self, files, keep_selection=False):
        """设置数据集列表内容

        Args:
            files: 文件名列表
            keep_selection: 是否保留当前选中项
        """
        if not hasattr(self.ui, 'dataset_list') or self.ui.dataset_list is None:
            return
        # 记录当前选中
        selected = []
        if keep_selection:
            selected = [self.ui.dataset_list.item(i).text()
                        for i in range(self.ui.dataset_list.count())
                        if self.ui.dataset_list.item(i).isSelected()]
        self.ui.dataset_list.clear()
        for f in files:
            self.ui.dataset_list.addItem(f)
        # 恢复选中
        if keep_selection and selected:
            for i in range(self.ui.dataset_list.count()):
                if self.ui.dataset_list.item(i).text() in selected:
                    self.ui.dataset_list.item(i).setSelected(True)

    def get_selected_datasets(self):
        """获取选中的数据集文件名列表"""
        if not hasattr(self.ui, 'dataset_list') or self.ui.dataset_list is None:
            return []
        return [self.ui.dataset_list.item(i).text()
                for i in range(self.ui.dataset_list.count())
                if self.ui.dataset_list.item(i).isSelected()]

    # ---------- 预处理方法（阶段二） ----------

    def get_preprocessing_method(self):
        """获取选中的预处理方法代码

        Returns:
            str: raw / log2 / log2_scaled / scaled
        """
        if not hasattr(self.ui, 'preprocessing_combo') or self.ui.preprocessing_combo is None:
            return 'log2'
        return self.ui.preprocessing_combo.currentData()

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

    # ---------- 临床信息表格（阶段三） ----------

    def set_clinical_table(self, clinical_df):
        """填充同步临床信息表格

        Args:
            clinical_df: DataFrame，包含 SampleID 和映射列

        参照韦恩图表格：显式 setForeground/setBackground，避免 item 字色默认黑色。
        """
        if not hasattr(self.ui, 'clinical_table') or self.ui.clinical_table is None:
            return
        if clinical_df is None or clinical_df.empty:
            self.ui.clinical_table.setRowCount(0)
            self.ui.clinical_table.setColumnCount(0)
            return

        from PyQt5.QtWidgets import QTableWidgetItem, QHeaderView
        from PyQt5.QtCore import Qt as _Qt
        from PyQt5.QtGui import QColor
        from script.utils_layer.gui_styles import get_mod_styles

        styles = get_mod_styles()
        text_color = styles.get('sub_text_color', '#87CEEB')
        fill_color = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        fill_alt = styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')

        def _parse_color(color_str):
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

        text_qcolor = _parse_color(text_color)
        fill_qcolor = _parse_color(fill_color)
        fill_alt_qcolor = _parse_color(fill_alt)

        cols = list(clinical_df.columns)
        self.ui.clinical_table.setRowCount(len(clinical_df))
        self.ui.clinical_table.setColumnCount(len(cols))
        self.ui.clinical_table.setHorizontalHeaderLabels(cols)
        # 启用横向滚动条（列多时可拖动查看）
        self.ui.clinical_table.setHorizontalScrollBarPolicy(_Qt.ScrollBarAsNeeded)
        # 列宽自适应内容（列名+数据），用户仍可手动拖动调整
        self.ui.clinical_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.ui.clinical_table.horizontalHeader().setStretchLastSection(False)

        for i, row in enumerate(clinical_df.itertuples(index=False)):
            row_bg = fill_alt_qcolor if (i % 2 == 0) else fill_qcolor
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~_Qt.ItemIsEditable)
                item.setForeground(text_qcolor)
                item.setBackground(row_bg)
                self.ui.clinical_table.setItem(i, j, item)

        # 填充完成后自适应列宽
        self.ui.clinical_table.resizeColumnsToContents()
