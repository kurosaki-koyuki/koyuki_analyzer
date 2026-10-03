# -*- coding: utf-8 -*-
"""
临床信息同步向导弹窗
多页向导：选择主注释 → 定义组别 → 逐数据集映射
继承 StyledDialog 基类，样式由 gui_styles 统一管理
"""

from script.utils_layer.import_config import (
    os, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    Qt, QWidget, QStackedWidget, QCheckBox, QLineEdit, QMessageBox,
    QDialog, QTableWidgetItem, QHeaderView, QColor
)
from script.utils_layer.gui_styles import (
    StyledDialog, get_font_for_widget, get_mod_styles,
    create_styled_button, create_styled_label, create_styled_combo_box,
    create_styled_list_widget, create_styled_table, create_styled_panel
)


class ClinicalSyncDialog(StyledDialog):
    """临床信息同步向导弹窗

    多页向导结构：
    - 页面1：选择主注释数据集和临床列
    - 页面2：定义主注释的组别（组别1/组别2）
    - 页面3~N：逐数据集映射（跳过主注释数据集）
    """

    def __init__(self, main_window, dataset_obs_dict):
        self._dataset_obs_dict = dataset_obs_dict
        self._result = None
        self._main_dataset = None
        self._main_column = None
        self._group1_name = None
        self._group2_name = None
        self._mappings = {}
        self._mapping_pages = []
        self._non_main_datasets = []
        super().__init__(main_window, variant='sub', fixed_size=(700, 600))

    def _build_ui(self):
        """构建向导UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        layout.addWidget(self._stack)

        self._build_page1()

    # ==================== 页面1：主注释选择 ====================

    def _build_page1(self):
        """页面1 - 选择主注释数据集和临床列"""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(8)

        title = create_styled_label("第一步：选择主注释数据", font_size=14)
        page_layout.addWidget(title)

        # 数据集选择
        ds_row = QHBoxLayout()
        ds_label = create_styled_label("选择数据集：", font_size=11, bold=False)
        self._p1_dataset_combo = create_styled_combo_box()
        for name in self._dataset_obs_dict.keys():
            self._p1_dataset_combo.addItem(name)
        ds_row.addWidget(ds_label)
        ds_row.addWidget(self._p1_dataset_combo, 1)
        page_layout.addLayout(ds_row)

        # 临床列选择
        col_row = QHBoxLayout()
        col_label = create_styled_label("选择临床列：", font_size=11, bold=False)
        self._p1_column_combo = create_styled_combo_box()
        col_row.addWidget(col_label)
        col_row.addWidget(self._p1_column_combo, 1)
        page_layout.addLayout(col_row)

        # 唯一值预览表格
        preview_label = create_styled_label("唯一值预览：", font_size=11, bold=False)
        page_layout.addWidget(preview_label)
        self._p1_table = create_styled_table()
        page_layout.addWidget(self._p1_table, 1)

        # 导航按钮
        btn_row = self._make_nav_buttons("下一步", self._on_p1_next)
        page_layout.addLayout(btn_row)

        self._stack.addWidget(page)

        # 连接信号
        self._p1_dataset_combo.currentTextChanged.connect(self._on_p1_dataset_changed)
        self._p1_column_combo.currentTextChanged.connect(self._on_p1_column_changed)

        # 触发初始填充
        self._on_p1_dataset_changed(self._p1_dataset_combo.currentText())

    def _on_p1_dataset_changed(self, dataset_name):
        """数据集切换时更新临床列下拉框"""
        self._p1_column_combo.blockSignals(True)
        self._p1_column_combo.clear()
        if dataset_name and dataset_name in self._dataset_obs_dict:
            obs_df = self._dataset_obs_dict[dataset_name]
            for col in obs_df.columns:
                self._p1_column_combo.addItem(str(col))
        self._p1_column_combo.blockSignals(False)
        self._on_p1_column_changed(self._p1_column_combo.currentText())

    def _on_p1_column_changed(self, column_name):
        """临床列切换时更新表格预览"""
        dataset = self._p1_dataset_combo.currentText()
        if not dataset or not column_name or dataset not in self._dataset_obs_dict:
            self._p1_table.setRowCount(0)
            self._p1_table.setColumnCount(0)
            return
        obs_df = self._dataset_obs_dict[dataset]
        self._populate_value_table(self._p1_table, obs_df, column_name)

    def _on_p1_next(self):
        """页面1下一步 - 记录主注释选择并构建页面2"""
        dataset = self._p1_dataset_combo.currentText()
        column = self._p1_column_combo.currentText()
        if not dataset:
            QMessageBox.warning(self, "提示", "请选择数据集")
            return
        if not column:
            QMessageBox.warning(self, "提示", "请选择临床列")
            return
        self._main_dataset = dataset
        self._main_column = column
        self._non_main_datasets = [d for d in self._dataset_obs_dict.keys() if d != dataset]
        self._build_page2()
        self._stack.setCurrentWidget(self._p2_page)

    # ==================== 页面2：主注释组别定义 ====================

    def _build_page2(self):
        """页面2 - 定义组别1和组别2"""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(8)

        title_text = f"第二步：定义组别（主注释：{self._main_dataset} - {self._main_column}）"
        title_label = create_styled_label(title_text, font_size=14)
        page_layout.addWidget(title_label)

        # 获取主注释列的唯一值
        obs_df = self._dataset_obs_dict[self._main_dataset]
        value_counts = obs_df[self._main_column].value_counts()
        unique_values = [str(v) for v in value_counts.index.tolist()]

        # 组别1 区域
        g1_panel, g1_layout = create_styled_panel()
        g1_label = create_styled_label("组别1", font_size=12)
        g1_layout.addWidget(g1_label)
        self._p2_group1_list = create_styled_list_widget(multi_selection=True, fixed_height=120)
        for v in unique_values:
            self._p2_group1_list.addItem(v)
        g1_layout.addWidget(self._p2_group1_list)
        g1_name_row = QHBoxLayout()
        self._p2_group1_checkbox = self._make_checkbox("使用原名")
        self._p2_group1_checkbox.setChecked(True)
        self._p2_group1_lineedit = self._make_line_edit()
        self._p2_group1_lineedit.setEnabled(False)
        g1_name_row.addWidget(self._p2_group1_checkbox)
        g1_name_row.addWidget(self._p2_group1_lineedit, 1)
        g1_layout.addLayout(g1_name_row)
        page_layout.addWidget(g1_panel)

        # 组别2 区域
        g2_panel, g2_layout = create_styled_panel()
        g2_label = create_styled_label("组别2", font_size=12)
        g2_layout.addWidget(g2_label)
        self._p2_group2_list = create_styled_list_widget(multi_selection=True, fixed_height=120)
        for v in unique_values:
            self._p2_group2_list.addItem(v)
        g2_layout.addWidget(self._p2_group2_list)
        g2_name_row = QHBoxLayout()
        self._p2_group2_checkbox = self._make_checkbox("使用原名")
        self._p2_group2_checkbox.setChecked(True)
        self._p2_group2_lineedit = self._make_line_edit()
        self._p2_group2_lineedit.setEnabled(False)
        g2_name_row.addWidget(self._p2_group2_checkbox)
        g2_name_row.addWidget(self._p2_group2_lineedit, 1)
        g2_layout.addLayout(g2_name_row)
        page_layout.addWidget(g2_panel)

        # 导航按钮（无非主注释数据集时改为"完成"）
        has_non_main = len(self._non_main_datasets) > 0
        btn_text = "下一步" if has_non_main else "完成"
        btn_row = self._make_nav_buttons(btn_text, self._on_p2_next)
        page_layout.addLayout(btn_row)

        self._p2_page = page
        self._stack.addWidget(page)

        # 连接信号
        self._p2_group1_checkbox.toggled.connect(self._on_group1_checkbox_toggled)
        self._p2_group2_checkbox.toggled.connect(self._on_group2_checkbox_toggled)

    def _on_group1_checkbox_toggled(self, checked):
        """组别1使用原名勾选切换 - 启用/禁用自定义名称输入框"""
        self._p2_group1_lineedit.setEnabled(not checked)

    def _on_group2_checkbox_toggled(self, checked):
        """组别2使用原名勾选切换 - 启用/禁用自定义名称输入框"""
        self._p2_group2_lineedit.setEnabled(not checked)

    def _on_p2_next(self):
        """页面2下一步 - 校验组别定义并记录主注释映射"""
        g1_values = self._get_selected_list_values(self._p2_group1_list)
        g2_values = self._get_selected_list_values(self._p2_group2_list)

        if not g1_values:
            QMessageBox.warning(self, "提示", "组别1至少选择一个值")
            return
        if not g2_values:
            QMessageBox.warning(self, "提示", "组别2至少选择一个值")
            return

        g1_set = set(g1_values)
        g2_set = set(g2_values)
        if g1_set & g2_set:
            overlap = ", ".join(sorted(g1_set & g2_set))
            QMessageBox.warning(self, "提示", f"组别1和组别2不能选相同的值（重复：{overlap}）")
            return

        # 计算组别名
        if self._p2_group1_checkbox.isChecked():
            self._group1_name = "+".join(g1_values)
        else:
            name = self._p2_group1_lineedit.text().strip()
            if not name:
                QMessageBox.warning(self, "提示", "组别1的自定义名称不能为空")
                return
            self._group1_name = name

        if self._p2_group2_checkbox.isChecked():
            self._group2_name = "+".join(g2_values)
        else:
            name = self._p2_group2_lineedit.text().strip()
            if not name:
                QMessageBox.warning(self, "提示", "组别2的自定义名称不能为空")
                return
            self._group2_name = name

        # 记录主注释数据集的映射
        self._mappings[self._main_dataset] = {
            'column': self._main_column,
            'group1_values': g1_values,
            'group2_values': g2_values,
        }

        # 日志提示丢弃的值
        obs_df = self._dataset_obs_dict[self._main_dataset]
        value_counts = obs_df[self._main_column].value_counts()
        all_values = set(str(v) for v in value_counts.index.tolist())
        dropped = all_values - g1_set - g2_set
        if dropped:
            print(f"[ClinicalSync] 主注释数据集 {self._main_dataset} 丢弃的值: {sorted(dropped)}")

        # 构建映射页面或直接完成
        if self._non_main_datasets:
            self._build_mapping_pages()
            self._stack.setCurrentWidget(self._mapping_pages[0]['page'])
        else:
            self._finalize_result()
            self.accept()

    # ==================== 页面3~N：逐数据集映射 ====================

    def _build_mapping_pages(self):
        """构建所有非主注释数据集的映射页面"""
        total = len(self._non_main_datasets)
        for i, dataset_name in enumerate(self._non_main_datasets):
            is_last = (i == total - 1)
            self._build_mapping_page(dataset_name, i, total, is_last)

    def _build_mapping_page(self, dataset_name, idx, total, is_last):
        """构建单个数据集映射页面"""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(8)

        # 标题
        title_text = f"第三步：映射数据集 - {dataset_name}（{idx + 1}/{total}）"
        title_label = create_styled_label(title_text, font_size=14)
        page_layout.addWidget(title_label)

        # 组别命名提示
        hint_text = f"组别1 → {self._group1_name} | 组别2 → {self._group2_name}"
        hint_label = create_styled_label(hint_text, font_size=11, bold=False)
        page_layout.addWidget(hint_label)

        # 临床列选择
        col_row = QHBoxLayout()
        col_label = create_styled_label("选择临床列：", font_size=11, bold=False)
        column_combo = create_styled_combo_box()
        obs_df = self._dataset_obs_dict[dataset_name]
        for col in obs_df.columns:
            column_combo.addItem(str(col))
        col_row.addWidget(col_label)
        col_row.addWidget(column_combo, 1)
        page_layout.addLayout(col_row)

        # 唯一值预览表格
        table = create_styled_table()
        page_layout.addWidget(table, 1)

        # 组别1 多选列表
        g1_panel, g1_layout = create_styled_panel()
        g1_label = create_styled_label(f"组别1 ({self._group1_name})", font_size=12)
        g1_layout.addWidget(g1_label)
        group1_list = create_styled_list_widget(multi_selection=True, fixed_height=100)
        g1_layout.addWidget(group1_list)
        page_layout.addWidget(g1_panel)

        # 组别2 多选列表
        g2_panel, g2_layout = create_styled_panel()
        g2_label = create_styled_label(f"组别2 ({self._group2_name})", font_size=12)
        g2_layout.addWidget(g2_label)
        group2_list = create_styled_list_widget(multi_selection=True, fixed_height=100)
        g2_layout.addWidget(group2_list)
        page_layout.addWidget(g2_panel)

        # 存储页面信息（在连接信号前创建，供 lambda 捕获）
        page_info = {
            'dataset': dataset_name,
            'page': page,
            'column_combo': column_combo,
            'table': table,
            'group1_list': group1_list,
            'group2_list': group2_list,
            'idx': idx,
        }
        self._mapping_pages.append(page_info)

        # 导航按钮（最后一页改为"完成"）
        btn_text = "完成" if is_last else "下一步"
        btn_row = self._make_nav_buttons(btn_text, lambda pi=page_info: self._on_mapping_next(pi))
        page_layout.addLayout(btn_row)

        self._stack.addWidget(page)

        # 连接信号
        column_combo.currentTextChanged.connect(
            lambda text, pi=page_info: self._on_mapping_column_changed(text, pi)
        )

        # 触发初始填充
        self._on_mapping_column_changed(column_combo.currentText(), page_info)

    def _on_mapping_column_changed(self, column_name, page_info):
        """映射页面临床列切换时更新表格预览和组别列表"""
        table = page_info['table']
        group1_list = page_info['group1_list']
        group2_list = page_info['group2_list']
        dataset_name = page_info['dataset']

        if not column_name or dataset_name not in self._dataset_obs_dict:
            table.setRowCount(0)
            table.setColumnCount(0)
            group1_list.clear()
            group2_list.clear()
            return

        obs_df = self._dataset_obs_dict[dataset_name]
        if column_name not in obs_df.columns:
            table.setRowCount(0)
            table.setColumnCount(0)
            group1_list.clear()
            group2_list.clear()
            return

        value_counts = obs_df[column_name].value_counts()
        unique_values = [str(v) for v in value_counts.index.tolist()]

        # 更新表格
        self._populate_value_table_from_counts(table, value_counts)

        # 更新组别列表
        group1_list.clear()
        group2_list.clear()
        for v in unique_values:
            group1_list.addItem(v)
            group2_list.addItem(v)

    def _on_mapping_next(self, page_info):
        """映射页面下一步/完成 - 校验并记录该数据集映射"""
        column = page_info['column_combo'].currentText()
        if not column:
            QMessageBox.warning(self, "提示", "请选择临床列")
            return

        g1_values = self._get_selected_list_values(page_info['group1_list'])
        g2_values = self._get_selected_list_values(page_info['group2_list'])

        if not g1_values:
            QMessageBox.warning(self, "提示", "组别1至少选择一个值")
            return
        if not g2_values:
            QMessageBox.warning(self, "提示", "组别2至少选择一个值")
            return

        g1_set = set(g1_values)
        g2_set = set(g2_values)
        if g1_set & g2_set:
            overlap = ", ".join(sorted(g1_set & g2_set))
            QMessageBox.warning(self, "提示", f"组别1和组别2不能选相同的值（重复：{overlap}）")
            return

        # 记录映射
        self._mappings[page_info['dataset']] = {
            'column': column,
            'group1_values': g1_values,
            'group2_values': g2_values,
        }

        # 日志提示丢弃的值
        obs_df = self._dataset_obs_dict[page_info['dataset']]
        value_counts = obs_df[column].value_counts()
        all_values = set(str(v) for v in value_counts.index.tolist())
        dropped = all_values - g1_set - g2_set
        if dropped:
            print(f"[ClinicalSync] 数据集 {page_info['dataset']} 丢弃的值: {sorted(dropped)}")

        # 进入下一页或完成
        idx = page_info['idx']
        if idx + 1 < len(self._mapping_pages):
            self._stack.setCurrentWidget(self._mapping_pages[idx + 1]['page'])
        else:
            self._finalize_result()
            self.accept()

    # ==================== 辅助方法 ====================

    def _make_nav_buttons(self, next_text, next_handler):
        """创建导航按钮行：放弃（左）+ 下一步/完成（右）"""
        row = QHBoxLayout()
        abort_btn = create_styled_button("放弃", font_size=12, button_type='normal')
        abort_btn.clicked.connect(self.reject)
        next_btn = create_styled_button(next_text, font_size=12, button_type='run')
        # 用 lambda 隔离 clicked 信号的 bool 参数，避免覆盖 next_handler 的默认参数
        next_btn.clicked.connect(lambda _checked=False, h=next_handler: h())
        row.addWidget(abort_btn)
        row.addStretch()
        row.addWidget(next_btn)
        return row

    def _make_checkbox(self, text):
        """手动创建样式化的 QCheckBox（用 get_mod_styles 获取颜色，字体用 get_font_for_widget）"""
        s = get_mod_styles()
        cb = QCheckBox(text, self)
        cb.setFont(get_font_for_widget('label', 11))
        text_color = s.get('sub_text_primary', '#87CEEB')
        border_color = s.get('sub_border_default', '#1E3A5F')
        cb.setStyleSheet(f"""
            QCheckBox {{
                color: {text_color};
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {border_color};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background: {text_color};
                border: 1px solid {text_color};
            }}
        """)
        return cb

    def _make_line_edit(self):
        """手动创建样式化的 QLineEdit（用 get_mod_styles 获取颜色，字体用 get_font_for_widget）"""
        s = get_mod_styles()
        le = QLineEdit(self)
        le.setFont(get_font_for_widget('input', 11))
        input_text = s.get('sub_input_text', '#87CEEB')
        input_bg = s.get('sub_input_bg', 'rgba(30, 58, 95, 0.3)')
        input_border = s.get('sub_input_border', '#1E3A5F')
        input_focus_border = s.get('sub_input_focus_border', '#87CEEB')
        input_radius = s.get('sub_input_radius', '3px')
        le.setStyleSheet(f"""
            QLineEdit {{
                color: {input_text};
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: {input_radius};
                padding: 3px 8px;
            }}
            QLineEdit:focus {{
                border-color: {input_focus_border};
            }}
        """)
        return le

    def _populate_value_table(self, table, obs_df, column):
        """填充表格：显示选中列的唯一值和计数"""
        if column is None or column not in obs_df.columns:
            table.setRowCount(0)
            table.setColumnCount(0)
            return
        value_counts = obs_df[column].value_counts()
        self._populate_value_table_from_counts(table, value_counts)

    def _populate_value_table_from_counts(self, table, value_counts):
        """用 value_counts 结果填充表格（两列：值、计数）

        参照韦恩图表格：显式 setForeground/setBackground，避免 item 字色默认黑色。
        """
        s = get_mod_styles()
        text_color = s.get('sub_text_color', '#87CEEB')
        fill_color = s.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        fill_alt = s.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')

        text_qcolor = self._parse_color(text_color)
        fill_qcolor = self._parse_color(fill_color)
        fill_alt_qcolor = self._parse_color(fill_alt)

        table.setRowCount(len(value_counts))
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['值', '计数'])
        for i, (value, count) in enumerate(value_counts.items()):
            row_bg = fill_alt_qcolor if (i % 2 == 0) else fill_qcolor
            item0 = QTableWidgetItem(str(value))
            item0.setForeground(text_qcolor)
            item0.setBackground(row_bg)
            table.setItem(i, 0, item0)
            item1 = QTableWidgetItem(str(count))
            item1.setForeground(text_qcolor)
            item1.setBackground(row_bg)
            table.setItem(i, 1, item1)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

    @staticmethod
    def _parse_color(color_str):
        """解析颜色字符串为 QColor（支持 #hex 和 rgba() 格式）"""
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

    @staticmethod
    def _get_selected_list_values(list_widget):
        """获取多选列表中选中的值（按列表显示顺序）"""
        values = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.isSelected():
                values.append(item.text())
        return values

    def _finalize_result(self):
        """构建最终结果 dict"""
        self._result = {
            'column_name': self._main_column,
            'group1_name': self._group1_name,
            'group2_name': self._group2_name,
            'mappings': dict(self._mappings),
        }

    def get_result(self):
        """获取向导结果

        Returns:
            dict 或 None：用户点击"完成"返回结果 dict，点击"放弃"或关闭窗口返回 None
        """
        if self.result() == QDialog.Accepted:
            return self._result
        return None
