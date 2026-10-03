# -*- coding: utf-8 -*-
"""空转「差异分析」页面UI布局脚本 - 只负责创建控件、规划窗口布局、设置样式尺寸

完全不写按钮点击、触发逻辑（跳转/信号/取数/写盘全部归 W2 的
`ui_bind_spatial_diff.py`）；**任何地方都不读数据**
（不读 manifest/csv/json、不扫目录、不建 QPixmap（背景图除外，与其它页同款）、
 不 import/实例化 analysis 类）。

## 由来（契约 `_d_spec_spatial_diff.md`，唯一接口契约）
本页 = 单细胞 `scRNAseq_layer/diff_layer/py_diff/ui_layout_diff.py`（553 行）的
**近似 1:1 复刻**：
- 控件属性名**逐个照规格 §5.1 表**（与原型同名同义：`diff_group_combo` /
  `diff_group1_list` / … / `btn_run_diff` / `btn_export_csv` / `btn_export_png`）；
- 精确默认值 / 范围 / 文案照 §5.3（`diff_logfc_spin` 默认 **0.25**、
  `diff_pval_spin` 0.05、`diff_pct_spin` 0.1、`diff_min_cells` 3、`diff_min_expr` 0、
  `diff_use_fdr` 默认勾选、`diff_method_combo` = **禁用**单选项）；
- **统计标签是 6 个**（不是 4 个）：`diff_group1_cell_label` / `diff_group2_cell_label`
  / `diff_up_label` / `diff_down_label` / `diff_stable_label` / `diff_total_label`；
- 表头在原型里是"建页时**写死 10 列**"（不含 `significant` / `change`，三张表各写一次）
  —— 本页照此。★ 数据层（`SpatialDiffAnalysis.run_diff_analysis`）返回的是
  **12 列**（多 `significant` 与 `change`，见契约 §6.2）；表格显示前 10 列。
- 结果页签顺序 **0/1/2/3 = 总体列表 / 显著上调 / 显著下调 / 火山图**；
  `_setup_gene_search`（W2）把前三个按 tab index 0/1/2 绑给既有 Mixin
  ⇒ **火山图必须留在 index 3，表格顺序不许动**。

### 空转独有（原型没有，全是新增）
1. **页面级「样本选择」面板**（`fixed_width=260`，两种模式/整页常驻；形状照
   `spatial_expression_layer/ui_layout_spatial_expression.py:164-192` 与 `:773-776`）：
   `sample_list`（多选，fixed_height≈300）+ `sample_count_label`「已选 N / M」+
   `btn_sample_all`「全选」+ `btn_sample_invert`「反选」。
   ⇒ 规格 §4「样本多选驱动注释选项」的**输入控件**（按样本并集算可用分组 / 注释值、
   以及"哪些样本实际参与分析"的判据与重算**全归 W2/W3**，本层只建控件）。
2. **导航栏只有** `nav_btn_back`「← 返回主页」。
   ⛔ **不复制**原型左导航里的 `nav_btn_python`「Python版本」/ `nav_btn_r`「R版本」
   （本轮只做一种实现；规格 §5.2 明令不要留一个点了没反应的按钮）。
3. 页面标题「空间差异分析」；根控件 / 背景 / 遮罩的 objectName 用
   `spatial_diff_bg` / `spatial_diff_overlay`（与其它空转子页同款命名）。

### 布局骨架（照原型 + 样本列）
```
spatial_diff_page
└── overlay（objectName `spatial_diff_overlay`）
      ├── nav_panel(220)：nav_btn_back「← 返回主页」+ 弹簧
      └── content_panel
            ├── top_bar（标题「空间差异分析」+ 音乐控件）
            └── body（横向，20/10/20/20，间距 12）
                  ├── sample_panel(260)「样本选择」（页面级常驻）
                  └── inner_main_layout
                        ├── left_panel(380)：分组 / 组别1 / 组别2 / 筛选1 / 筛选2 /
                        │     参数（检验方法+问号 / 最小表达细胞数 / 最小表达量 /
                        │     p值 / log2FC / 百分比 / FDR / 日志）
                        ├── right_panel（结果：6 个统计标签 + 搜索 + 4 页签 3 表 1 图）
                        └── run_panel(200)：▶ 执行差异分析 / 导出Excel / 导出火山图
```

### ⛔ 统计口径提示（契约 §5.3 末条 / §7.8，必须如实保留）
本复刻与单细胞原型一样**以 spot 为独立观测**做 Mann-Whitney U，**未做 pseudobulk**
（同一样本内 spot 空间自相关 ⇒ p 值偏乐观）。这是**对原型的忠实复刻**，
故方法帮助文案 `diff_method_help_btn` 末尾**追加**一段如实注明
（原型三行文案前两行逐字保留）；后续是否改 pseudobulk 由用户决定。

★ 本文件**只建控件**：不读数据、不调 R、不写盘、不弹对话框、不连任何点击信号。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_spinbox, create_styled_tab_widget,
    create_styled_tab_page, create_styled_table,
    create_navigation_panel, create_navigation_button,
    create_navigation_divider, create_navigation_header, create_questions_button
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class SpatialDiffPageUI:
    """空转「差异分析」页面 UI 类（只建控件，不连任何逻辑）"""

    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    # ------------------------------------------------------------------
    # 主题刷新（与其它空转子页同款：切模组时调用）
    # ------------------------------------------------------------------
    def update_background(self):
        """切换模组时重载背景图（只碰背景 QLabel，不读任何数据）"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.spatial_diff_page.findChild(QLabel, "spatial_diff_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(
                    f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """刷新样式：跳过导航按钮 / 背景标签 / 火山图标签；只刷普通按钮/标签/面板底色

        ★ 逐行照抄原型 `py_diff/ui_layout_diff.py:36-157`，只做了两处**删减/保留**：
          · 删掉 `nav_btn_python` / `nav_btn_r` 两个版本切换导航按钮的分支（本页没有）；
          · 导航按钮统一走 `nav_btn_*` 前缀收集（与空转其它页一致），
            这样"导航按钮自带标签式样式、不能被普通按钮 QSS 覆盖"照旧成立。
        """
        styles = get_mod_styles()

        title_label = self.spatial_diff_page.findChild(QLabel, "spatial_diff_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        # 只更新样式，不修改控件尺寸
        # 注意：QSpinBox、QCheckBox、QListWidget等控件现在通过style层的create_styled_*函数创建
        # 样式已经在创建时设置好了，不需要在这里重复设置

        nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]

        # 更新按钮样式
        button_style = get_stylesheet_for_widget('button')
        for child in self.spatial_diff_page.findChildren(QPushButton):
            # 特殊按钮保持自己的样式
            if child.objectName() and child.objectName().startswith("number_input_btn_"):
                continue  # 数字输入框按钮保持自己的样式
            if child in nav_buttons:
                continue  # 导航按钮（`nav_btn_back`）保持标签式样式
            if child == self.btn_run_diff:
                continue  # 运行按钮保持run_button样式
            elif child in [self.btn_export_csv, self.btn_export_png,
                           getattr(self, 'btn_send_to_genelist', None)]:
                continue  # 导出/发送按钮保持export_button样式
            child.setStyleSheet(button_style)

        # 重新应用特殊按钮样式
        self.btn_run_diff.setStyleSheet(get_stylesheet_for_widget('run_button'))
        self.btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        # ★ 「发送到列表文件夹」与两个导出按钮**同族同尺寸**（契约 §4.1 / §4.3）
        if hasattr(self, 'btn_send_to_genelist'):
            self.btn_send_to_genelist.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.spatial_diff_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.spatial_diff_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.spatial_diff_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.spatial_diff_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_diff_page.findChildren(QLabel):
            if child.objectName() == "spatial_diff_title":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            # 火山图标签自带"边框 + 底色"，不能被普通标签 QSS 抹掉
            if child is self.diff_volcano_label:
                continue
            child.setStyleSheet(label_style)

        # 更新表格样式
        table_style = get_stylesheet_for_widget('table')
        for child in self.spatial_diff_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)

        # 更新标签页样式
        primary_color = styles.get('sub_text_color', styles.get('text_color', '#87CEEB'))
        secondary_color = styles.get('sub_border_color', styles.get('border_color', '#1E3A5F'))
        dark_bg = styles.get('sub_fill_alt', styles.get('fill_alt', 'rgba(30, 58, 95, 0.6)'))
        hover_color = styles.get('sub_hover_color', styles.get('hover_color', 'rgba(30, 58, 95, 0.5)'))
        tab_selected_bg = styles.get('sub_active_color', styles.get('active_color', 'rgba(135, 206, 235, 0.2)'))
        tab_style = f"""
            QTabWidget::tab-bar {{
                alignment: left;
            }}
            QTabBar::tab {{
                color: {primary_color};
                background: {dark_bg};
                padding: 5px 15px;
                border: 1px solid {secondary_color};
                border-bottom: none;
            }}
            QTabBar::tab:hover {{
                background: {hover_color};
            }}
            QTabBar::tab:selected {{
                background: {tab_selected_bg};
            }}
            QTabWidget::pane {{
                border: 1px solid {secondary_color};
                background: rgba(0, 0, 0, 0.3);
            }}
        """
        for child in self.spatial_diff_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_style)

        # 更新统计标签颜色（6 个，与原型 :128-140 一致）
        if hasattr(self, 'diff_group1_cell_label'):
            self.diff_group1_cell_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#98FB98')};")
        if hasattr(self, 'diff_group2_cell_label'):
            self.diff_group2_cell_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#FFB6C1')};")
        if hasattr(self, 'diff_up_label'):
            self.diff_up_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#FF6B35')};")
        if hasattr(self, 'diff_down_label'):
            self.diff_down_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        if hasattr(self, 'diff_stable_label'):
            self.diff_stable_label.setStyleSheet(f"color: {styles.get('sub_border_color', '#666666')};")
        if hasattr(self, 'diff_total_label'):
            self.diff_total_label.setStyleSheet(f"color: {primary_color};")

        panel_bg = styles.get('sub_panel_bg', styles.get('panel_background', 'rgba(30, 58, 95, 0.5)'))
        panel_border = styles.get('sub_panel_border', styles.get('panel_border_color', '#1E3A5F'))
        panel_radius = styles.get('panel_border_radius', '8px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.spatial_diff_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.spatial_diff_page.findChild(QWidget, "spatial_diff_overlay")
        if overlay:
            overlay.setStyleSheet(
                f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

    # ------------------------------------------------------------------
    # ★ 空转独有：页面级「样本选择」面板（规格 §5.2）
    #   形状逐行照 `spatial_expression_layer/ui_layout_spatial_expression.py:164-192`
    #   （少一个「选已审查高分」按钮 —— 那是表达页的业务快捷项，差异页契约里没有）。
    #   ★ 默认全不选、列表为空：填内容与"按样本重算注释选项"全归 W2。
    # ------------------------------------------------------------------
    def _create_sample_panel(self, parent, layout):
        """左栏：样本多选列表 + 计数 + 全选/反选（★ 只建控件，不查任何数据）"""
        title = create_styled_label("样本选择", font_size=12, parent=parent)
        layout.addWidget(title)

        # ★ 返回单个 widget；multi_selection=True → QListWidget.MultiSelection
        # ★ fixed_height 走 setMaximumHeight，必须显式传，否则会被主题默认值压到 100px
        #   （规格 §5.2 要求 h≈300）
        self.sample_list = create_styled_list_widget(
            parent=parent, fixed_height=300, multi_selection=True)
        layout.addWidget(self.sample_list)

        self.sample_count_label = create_styled_label(
            "已选 0 / 0", font_size=10, bold=False, parent=parent)
        layout.addWidget(self.sample_count_label)

        layout.addSpacing(8)

        # 两个快捷选择按钮：★ 只建按钮，"选中全部/反选"的编排归 W2
        self.btn_sample_all = create_styled_button("全选", font_size=10, parent=parent)
        layout.addWidget(self.btn_sample_all)

        self.btn_sample_invert = create_styled_button("反选", font_size=10, parent=parent)
        layout.addWidget(self.btn_sample_invert)

        layout.addStretch()

    # ------------------------------------------------------------------
    # 左列控制面板（分组 / 组别 / 筛选 / 参数 / 日志）—— 逐行复刻原型 :256-405
    # ------------------------------------------------------------------
    def _create_left_control_panel(self, parent):
        """左列（fixed_width=380）：分组选择 + 组别1/2 + 细胞筛选 + 参数设置 + 日志"""
        styles = get_mod_styles()

        left_panel, left_layout = create_styled_panel(parent=parent, fixed_width=380)

        # 【分组选择】
        group_label = create_styled_label("分组选择", font_size=12, bold=True, parent=left_panel)
        left_layout.addWidget(group_label)

        group_desc_label = create_styled_label(
            "选择用于分组的注释列", font_size=9, bold=False, parent=left_panel)
        group_desc_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(group_desc_label)

        # 分组下拉框（选择注释列）
        # ★ 选项内容由 W2 按所选样本重算（规格 §4.2/§4.3）：本层只建**空**控件
        self.diff_group_combo = create_styled_combo_box(parent=left_panel)
        left_layout.addWidget(self.diff_group_combo)

        left_layout.addSpacing(5)

        # 组别1选择框
        group1_label = create_styled_label("组别1（多选）", font_size=10, bold=True, parent=left_panel)
        left_layout.addWidget(group1_label)
        self.diff_group1_list = create_styled_list_widget(
            parent=left_panel, fixed_height=80, multi_selection=True)
        left_layout.addWidget(self.diff_group1_list)

        # 组别2选择框
        group2_label = create_styled_label("组别2（多选）", font_size=10, bold=True, parent=left_panel)
        left_layout.addWidget(group2_label)
        self.diff_group2_list = create_styled_list_widget(
            parent=left_panel, fixed_height=80, multi_selection=True)
        left_layout.addWidget(self.diff_group2_list)

        group_list_hint = create_styled_label(
            "在两个列表中分别选择要比较的分组", font_size=9, bold=False, parent=left_panel)
        group_list_hint.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(group_list_hint)

        left_layout.addSpacing(10)

        # 【细胞筛选】
        filter_label = create_styled_label("细胞筛选", font_size=12, bold=True, parent=left_panel)
        left_layout.addWidget(filter_label)

        filter_desc_label = create_styled_label(
            "可选：筛选特定细胞用于分析（多选）", font_size=9, bold=False, parent=left_panel)
        filter_desc_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(filter_desc_label)

        # 筛选条件1：列选择 + 多选列表
        filter1_col_label = create_styled_label("筛选条件1:", font_size=9, bold=True, parent=left_panel)
        left_layout.addWidget(filter1_col_label)
        self.diff_filter1_col = create_styled_combo_box(parent=left_panel)
        left_layout.addWidget(self.diff_filter1_col)
        self.diff_filter1_list = create_styled_list_widget(
            parent=left_panel, fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.diff_filter1_list)

        # 筛选条件2：列选择 + 多选列表
        filter2_col_label = create_styled_label("筛选条件2:", font_size=9, bold=True, parent=left_panel)
        left_layout.addWidget(filter2_col_label)
        self.diff_filter2_col = create_styled_combo_box(parent=left_panel)
        left_layout.addWidget(self.diff_filter2_col)
        self.diff_filter2_list = create_styled_list_widget(
            parent=left_panel, fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.diff_filter2_list)

        left_layout.addSpacing(10)

        # 【参数设置】
        param_label = create_styled_label("参数设置", font_size=12, bold=True, parent=left_panel)
        left_layout.addWidget(param_label)

        # 检验方法（★ 禁用的单选项 + 问号帮助，规格 §5.3）
        method_layout = QHBoxLayout()
        method_label = create_styled_label("检验方法", font_size=10, bold=False, parent=left_panel)
        self.diff_method_combo = create_styled_combo_box(parent=left_panel)
        self.diff_method_combo.addItems(["Mann-Whitney U检验"])
        self.diff_method_combo.setCurrentIndex(0)
        self.diff_method_combo.setEnabled(False)
        # ★ 前两行逐字照原型 :328-330；末段是契约 §5.3 / §7.8 要求的**统计口径如实注明**
        #   （"以 spot 为独立观测、未做 pseudobulk ⇒ p 值偏乐观"）—— 不许删。
        self.diff_method_help_btn = create_questions_button(
            "Mann-Whitney U 检验是非参数检验方法，适用于单细胞差异表达分析。\n"
            "该方法对数据分布假设要求较低，稳定性好，结果可靠。\n"
            "分析前会自动进行CP10K标准化和log1p转换。\n"
            "★ 与单细胞原型一致：以每个 spot 为独立观测做检验，**未做 pseudobulk**；\n"
            "  同一样本内 spot 存在空间自相关，故 p 值偏乐观（后续是否改 pseudobulk 待定）。",
            parent=left_panel
        )
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.diff_method_combo)
        method_layout.addWidget(self.diff_method_help_btn)
        left_layout.addLayout(method_layout)

        # 最小表达细胞数（默认 3）
        min_cells_layout = QHBoxLayout()
        min_cells_label = create_styled_label("最小表达细胞数", font_size=10, bold=False, parent=left_panel)
        self.diff_min_cells = create_styled_spinbox(
            parent=left_panel, min_value=1, max_value=1000, default_value=3)
        min_cells_layout.addWidget(min_cells_label)
        min_cells_layout.addWidget(self.diff_min_cells)
        left_layout.addLayout(min_cells_layout)

        # 最小表达量（默认 0）★ 契约 §6.2：分析层"收下但不用"，控件照原型保留
        min_expr_layout = QHBoxLayout()
        min_expr_label = create_styled_label("最小表达量", font_size=10, bold=False, parent=left_panel)
        self.diff_min_expr = create_styled_spinbox(
            parent=left_panel, min_value=0, max_value=100, default_value=0)
        min_expr_layout.addWidget(min_expr_label)
        min_expr_layout.addWidget(self.diff_min_expr)
        left_layout.addLayout(min_expr_layout)

        # p值阈值（0.001~0.1，step 0.001，默认 0.05）
        pval_layout = QHBoxLayout()
        pval_label = create_styled_label("p值阈值", font_size=10, bold=False, parent=left_panel)
        self.diff_pval_spin = QDoubleSpinBox()
        self.diff_pval_spin.setFont(get_font_for_widget('label', 9))
        self.diff_pval_spin.setRange(0.001, 0.1)
        self.diff_pval_spin.setSingleStep(0.001)
        self.diff_pval_spin.setValue(0.05)
        self.diff_pval_spin.setStyleSheet(get_stylesheet_for_widget('spinbox'))
        pval_layout.addWidget(pval_label)
        pval_layout.addWidget(self.diff_pval_spin)
        left_layout.addLayout(pval_layout)

        # log2FC阈值（0~2.0，step 0.05，★ 默认 0.25）
        logfc_layout = QHBoxLayout()
        logfc_label = create_styled_label("log2FC阈值", font_size=10, bold=False, parent=left_panel)
        self.diff_logfc_spin = QDoubleSpinBox()
        self.diff_logfc_spin.setFont(get_font_for_widget('label', 9))
        self.diff_logfc_spin.setRange(0, 2.0)
        self.diff_logfc_spin.setSingleStep(0.05)
        self.diff_logfc_spin.setValue(0.25)
        self.diff_logfc_spin.setStyleSheet(get_stylesheet_for_widget('spinbox'))
        logfc_layout.addWidget(logfc_label)
        logfc_layout.addWidget(self.diff_logfc_spin)
        left_layout.addLayout(logfc_layout)

        # 表达量百分比阈值（0.0~1.0，step 0.05，默认 0.1）★ 同 min_expr："收下但不用"
        pct_layout = QHBoxLayout()
        pct_label = create_styled_label("表达量百分比阈值", font_size=10, bold=False, parent=left_panel)
        self.diff_pct_spin = QDoubleSpinBox()
        self.diff_pct_spin.setFont(get_font_for_widget('label', 9))
        self.diff_pct_spin.setRange(0.0, 1.0)
        self.diff_pct_spin.setSingleStep(0.05)
        self.diff_pct_spin.setValue(0.1)
        self.diff_pct_spin.setStyleSheet(get_stylesheet_for_widget('spinbox'))
        pct_layout.addWidget(pct_label)
        pct_layout.addWidget(self.diff_pct_spin)
        left_layout.addLayout(pct_layout)

        # FDR校正（★ 默认勾选）
        self.diff_use_fdr = create_styled_checkbox("使用FDR校正", parent=left_panel)
        self.diff_use_fdr.setChecked(True)
        left_layout.addWidget(self.diff_use_fdr)

        # 日志面板（内容由 W2 写；本层只建只读控件）
        self.diff_log = QTextEdit()
        self.diff_log.setReadOnly(True)
        self.diff_log.setMaximumHeight(80)
        self.diff_log.setFont(get_font_for_widget('label', 10))
        self.diff_log.setStyleSheet(get_stylesheet_for_widget('text_edit'))
        left_layout.addWidget(self.diff_log)

        left_layout.addStretch()

        return left_panel

    # ------------------------------------------------------------------
    # 中列结果面板（6 统计标签 + 搜索 + 4 页签 3 表 1 图）—— 复刻原型 :409-518
    # ------------------------------------------------------------------
    def _create_result_panel(self, parent):
        """中列：分析结果统计（6 个标签）+ 基因搜索 + 结果页签（固定顺序 0/1/2/3）"""
        styles = get_mod_styles()

        right_panel, right_layout = create_styled_panel(parent=parent)

        # ===== 分析结果统计面板（★ 6 个标签，原型 :419-457）=====
        stats_group = QWidget(right_panel)
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(4)

        row1_layout = QHBoxLayout()
        self.diff_group1_cell_label = QLabel("组1细胞数: 0")
        self.diff_group1_cell_label.setFont(QFont("幼圆", 10))
        self.diff_group1_cell_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#98FB98')};")
        row1_layout.addWidget(self.diff_group1_cell_label)

        row1_layout.addStretch()

        self.diff_group2_cell_label = QLabel("组2细胞数: 0")
        self.diff_group2_cell_label.setFont(QFont("幼圆", 10))
        self.diff_group2_cell_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#FFB6C1')};")
        row1_layout.addWidget(self.diff_group2_cell_label)
        stats_layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        self.diff_up_label = QLabel("组1显著上调: 0")
        self.diff_up_label.setFont(QFont("幼圆", 10))
        self.diff_up_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#FF6B35')};")
        row2_layout.addWidget(self.diff_up_label)

        row2_layout.addStretch()

        self.diff_down_label = QLabel("组1显著下调: 0")
        self.diff_down_label.setFont(QFont("幼圆", 10))
        self.diff_down_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        row2_layout.addWidget(self.diff_down_label)
        stats_layout.addLayout(row2_layout)

        row3_layout = QHBoxLayout()
        self.diff_stable_label = QLabel("稳定基因: 0")
        self.diff_stable_label.setFont(QFont("幼圆", 10))
        self.diff_stable_label.setStyleSheet(f"color: {styles.get('sub_border_color', '#666666')};")
        row3_layout.addWidget(self.diff_stable_label)

        row3_layout.addStretch()

        self.diff_total_label = QLabel("总基因: 0")
        self.diff_total_label.setFont(QFont("幼圆", 10))
        self.diff_total_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        row3_layout.addWidget(self.diff_total_label)
        stats_layout.addLayout(row3_layout)

        right_layout.addWidget(stats_group)

        # 结果表格（使用标签页展示不同类型）
        result_label = create_styled_label("差异基因列表", font_size=12, bold=True, parent=right_panel)
        right_layout.addWidget(result_label)

        search_layout = QHBoxLayout()
        self.gene_search_input = create_styled_line_edit(parent=right_panel)
        self.gene_search_input.setPlaceholderText("输入基因名称搜索...")
        search_layout.addWidget(self.gene_search_input)
        self.gene_search_btn = create_styled_button("搜索", font_size=11, parent=right_panel)
        search_layout.addWidget(self.gene_search_btn)
        right_layout.addLayout(search_layout)

        # 创建标签页（★ 顺序冻结：0 总体列表 / 1 显著上调 / 2 显著下调 / 3 火山图）
        self.diff_result_tabs = create_styled_tab_widget(parent=right_panel)
        right_layout.addWidget(self.diff_result_tabs)

        # ★ 表头写死 10 列（原型口径；数据层是 12 列 —— 见本模块 docstring）
        result_header = [
            "基因", "mean_CP10K_group1", "mean_CP10K_group2", "log2FC",
            "pct_expr_group1", "pct_expr_group2", "p_val", "p_val_adj",
            "n_cells_group1", "n_cells_group2"
        ]

        # 总体差异分析列表（index 0）
        self.diff_table_all_page, self.diff_table_all_layout = create_styled_tab_page(
            self.diff_result_tabs, "总体列表")
        self.diff_result_table = create_styled_table(parent=self.diff_table_all_page)
        self.diff_table_all_layout.addWidget(self.diff_result_table)
        self.diff_result_table.setColumnCount(10)
        self.diff_result_table.setHorizontalHeaderLabels(list(result_header))

        # 显著上调基因（index 1）
        self.diff_table_up_page, self.diff_table_up_layout = create_styled_tab_page(
            self.diff_result_tabs, "显著上调")
        self.diff_result_table_up = create_styled_table(parent=self.diff_table_up_page)
        self.diff_table_up_layout.addWidget(self.diff_result_table_up)
        self.diff_result_table_up.setColumnCount(10)
        self.diff_result_table_up.setHorizontalHeaderLabels(list(result_header))

        # 显著下调基因（index 2）
        self.diff_table_down_page, self.diff_table_down_layout = create_styled_tab_page(
            self.diff_result_tabs, "显著下调")
        self.diff_result_table_down = create_styled_table(parent=self.diff_table_down_page)
        self.diff_table_down_layout.addWidget(self.diff_result_table_down)
        self.diff_result_table_down.setColumnCount(10)
        self.diff_result_table_down.setHorizontalHeaderLabels(list(result_header))

        # 火山图页（★ 必须留在 index 3：`_setup_gene_search` 只绑前三个 tab 的 gene_col=0）
        self.diff_volcano_page, self.diff_volcano_layout = create_styled_tab_page(
            self.diff_result_tabs, "火山图")
        self.diff_volcano_label = QLabel()
        self.diff_volcano_label.setStyleSheet(
            f"border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; "
            f"background: {styles.get('sub_fill_color', 'rgba(0,0,0,0.3)')};")
        self.diff_volcano_label.setAlignment(Qt.AlignCenter)
        self.diff_volcano_layout.addWidget(self.diff_volcano_label)

        return right_panel

    # ------------------------------------------------------------------
    # 右列运行区域（运行 + 两个导出）—— 复刻原型 :520-546
    # ------------------------------------------------------------------
    def _create_run_panel(self, parent):
        """最右列（fixed_width=200）：「运行区域」+ 导出选项

        ★ 只建按钮；`QFileDialog` 导出（不自动落盘）与编排全归 W2。
        """
        run_panel, run_layout = create_styled_panel(parent=parent, fixed_width=200)

        run_title = create_styled_label("运行区域", font_size=12, bold=True, parent=run_panel)
        run_layout.addWidget(run_title)

        run_layout.addSpacing(10)

        self.btn_run_diff = create_styled_button(
            "▶ 执行差异分析", font_size=11, parent=run_panel, button_type='run')
        run_layout.addWidget(self.btn_run_diff)

        run_layout.addSpacing(10)

        export_title = create_styled_label("导出选项", font_size=12, bold=True, parent=run_panel)
        run_layout.addWidget(export_title)

        run_layout.addSpacing(8)

        self.btn_export_csv = create_styled_button(
            "导出Excel", font_size=10, parent=run_panel, button_type='export')
        run_layout.addWidget(self.btn_export_csv)

        self.btn_export_png = create_styled_button(
            "导出火山图", font_size=10, parent=run_panel, button_type='export')
        run_layout.addWidget(self.btn_export_png)

        # ★ 「发送到列表文件夹」（契约 `docs/features/gene_list_send_contract.md` §4）：
        #   与上面两个导出按钮**同族同尺寸**（gui_styles 工厂 + export_button 样式）、
        #   **紧邻**摆放。语义与导出不同：导出到用户自选路径；本按钮把当前阈值下的
        #   显著基因（上调+下调）写进 `appdata/genelists`，供后续分析下拉框直接选用。
        #   ⛔ 本层**只建控件**：不 `clicked.connect`、不 `QFileDialog`、不 `os.startfile`
        #      （连接与取数/落盘全在 `ui_bind_spatial_diff.py`）。
        self.btn_send_to_genelist = create_styled_button(
            "发送到列表文件夹", font_size=10, parent=run_panel)
        run_layout.addWidget(self.btn_send_to_genelist)

        run_layout.addStretch()

        return run_panel

    # ------------------------------------------------------------------
    def create_page(self):
        """创建差异分析页面（★ 只建控件；不读数据、不写盘、不连信号）"""
        self.spatial_diff_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        # ========== 1. 背景层 ==========
        bg_label = QLabel(self.spatial_diff_page)
        bg_label.setObjectName("spatial_diff_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(
                f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        # ========== 2. 遮罩层 ==========
        overlay = QWidget(self.spatial_diff_page)
        overlay.setObjectName("spatial_diff_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== 3. 左侧导航栏（★ 只有「← 返回主页」）==========
        #   ⛔ 规格 §5.2：原型左导航里的 `nav_btn_python` / `nav_btn_r` **不复制**
        #     （本轮只做一种实现；不要留一个点了没反应的按钮）。
        #   ★ 属性名必须是 `nav_btn_*` 前缀：`update_styles()` 按该前缀收集并跳过上色。
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_header("差异分析", font_size=11, parent=nav_panel))

        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        # ========== 4. 右侧内容区（标题 + 音乐控件 + 主体）==========
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # ---- 顶部栏（标题 + 音乐控制）----
        top_bar, top_bar_layout = create_styled_panel(parent=content_panel)
        top_bar_layout.setContentsMargins(15, 8, 15, 8)

        title_row_layout = QHBoxLayout()

        title_label = QLabel("空间差异分析")
        title_label.setObjectName("spatial_diff_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)

        mod_instance = global_mod_manager.get_current_mod()
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.spatial_diff_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub')
        title_row_layout.addWidget(music_container)

        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)

        top_bar_layout.addLayout(title_row_layout)
        content_layout.addWidget(top_bar)

        # ---- 主体：页面级「样本选择」列(260) + 三栏（左控制 380 / 中结果 / 右运行 200）----
        #   ★ 规格 §5.2：样本面板是**页面级常驻**（可见性与表达页一致），故放在三栏之外。
        body = QWidget(content_panel)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 10, 20, 20)
        body_layout.setSpacing(12)

        self.sample_panel, sample_layout = create_styled_panel(parent=body, fixed_width=260)
        sample_layout.setContentsMargins(8, 8, 8, 8)
        self._create_sample_panel(self.sample_panel, sample_layout)
        body_layout.addWidget(self.sample_panel)

        inner_main_layout = QHBoxLayout()
        inner_main_layout.setContentsMargins(0, 0, 0, 0)
        inner_main_layout.setSpacing(12)

        # 左列（控制，380）
        self.left_panel = self._create_left_control_panel(body)
        inner_main_layout.addWidget(self.left_panel)

        # 中列（结果）
        self.result_panel = self._create_result_panel(body)
        inner_main_layout.addWidget(self.result_panel, 1)

        # 右列（运行，200）
        self.run_panel = self._create_run_panel(body)
        inner_main_layout.addWidget(self.run_panel)

        body_layout.addLayout(inner_main_layout, stretch=1)

        content_layout.addWidget(body, stretch=1)

        main_layout.addWidget(content_panel)

        # ★ 初始化完成后立即应用样式（与原型 `:552-553` 一致）
        self.update_styles()

        # ★ 供 page_intersect 取根控件（`attr_name='spatial_diff_page'` 逐字）
        return self.spatial_diff_page


__all__ = ['SpatialDiffPageUI']
