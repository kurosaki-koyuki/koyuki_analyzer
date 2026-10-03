# -*- coding: utf-8 -*-
"""空转「小提琴图」页面UI布局脚本 - 只负责创建控件、规划窗口布局、设置样式尺寸

完全不写按钮点击、触发逻辑；**任何地方都不读数据**
（不读 manifest/csv/json、不扫目录、不建 QPixmap（背景图除外，与其它页同款）、
 不 import/实例化 analysis 类）。

## v11 由来（`_d_spec_v11_split_and_bubble.md` §1，2026-09-25 用户拍板"解离"）
用户原话：小提琴图要**从表达量分析页解离**成主页「初步分析类」里的新按钮 + 新页，
且**文件夹也解离**（小提琴自己的目录 `spatial_violin_layer/`）。

⇒ 本文件 = **整块搬移**后的「小提琴图」独立页布局，来源两处：
  ① 页壳（根/背景/遮罩/标题/音乐控件/左导航「← 返回主页」）
     照 `spatial_expression_layer/ui_layout_spatial_expression.py:676-760`；
  ② 小提琴三栏 + 出图区（**31 个冻结控件逐字不变**）
     整块搬自 `ui_layout_spatial_expression.py:337-662` 的 `_create_violin_panel`。
  ★ 搬家时控件**属性名 / 文案 / 默认值 / 范围 / 页签顺序 / objectName 一个字都没动**
    （§1.3 的 31 项冻结清单是本次验收的硬判据）。

## 样本列：**新页自建一份**（§1.4 决策 ①，不复用表达页的）
形状逐行照**差异页** `spatial_diff_layer/ui_layout_spatial_diff.py:248-276`
（属性名 `sample_panel` / `sample_list` / `sample_count_label` / `btn_sample_all` /
 `btn_sample_high_score` / `btn_sample_invert` 与表达页/差异页**逐字一致**）。
理由：两页各自独立样本选择，页与页解耦（与差异页同款）。

## 布局骨架
```
spatial_violin_page（根，objectName = 'spatial_violin_page'）
└── overlay（objectName `spatial_violin_overlay`）
      ├── nav_panel(220)：nav_btn_back「← 返回主页」+ 分隔线 + 小标题 + 弹簧
      └── content_panel
            ├── top_bar（标题「小提琴图」+ 音乐控件）
            └── body（横向，20/10/20/20，间距 12）
                  ├── sample_panel(260)「样本选择」（页面级常驻，新页自建）
                  └── violin_panel：左=基因/分组/筛选(280) 中=参数调整(280)
                        右=导出选项(200) ｜ 最右=出图区（三页签，固定顺序）
```

## ⛔ 本文件**不做**的事
- 不读数据、不调 R、不写盘、不弹对话框、不连任何业务点击信号；
- **不建**「基础表达」那套控件（`gene_input` / `gene_result_tabs` / `anno_group_combo` …）
  —— 它们留在表达量页（§1.2-D）；
- **不建**「表达模式」双模式导航（`nav_btn_basic` / `nav_btn_violin`）与 `expression_stack`
  —— v11 之后不存在"两模式"，本页就是小提琴；返回一律回 hub。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_panel, create_styled_label,
    create_styled_list_widget, create_styled_text_edit,
    create_styled_combo_box, create_styled_line_edit, create_styled_checkbox,
    create_styled_spinbox, create_styled_tab_widget, create_styled_image_tab,
    create_navigation_panel, create_navigation_button,
    create_navigation_divider, create_navigation_header
)
from script.mods_layer.mod_manager import global_mod_manager


class SpatialViolinPageUI:
    """「小提琴图」页面布局类（只建控件，不连任何逻辑）"""

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
        bg_label = self.spatial_violin_page.findChild(QLabel, "spatial_violin_bg")
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
        """刷新样式：跳过导航按钮与背景标签；只刷普通按钮/标签/标题配色/面板底色

        ★ 与表达页 `update_styles()`（`:90-159`）同款，只做两处删减：
          · 本页**没有** `gene_result_tabs`（WrappingTabStrip）与 `btn_gene_export_*`
            ⇒ 那两条分支去掉（它们引用的控件在本页不存在）；
          · 小提琴变体色补偿**完整保留**（`btn_load_gene`=import / `btn_draw_violin`=run /
            4 个导出按钮=export），这正是 §1.2-A「样式：update_styles 的小提琴变体补偿」。
        """
        styles = get_mod_styles()

        button_style = get_stylesheet_for_widget('button')
        nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
        for child in self.spatial_violin_page.findChildren(QPushButton):
            if child in nav_buttons:
                continue
            # 导出按钮/带 export 变体的按钮保持自身样式（下面显式刷回来）
            if child.objectName() == 'styled_btn_export':
                continue
            child.setStyleSheet(button_style)

        # ★ 变体色按钮在上面的通用 `button` QSS 里会被刷成普通按钮
        #   ⇒ 这里按各自变体再刷回来（拿不到就跳过）。清单照表达页 `:120-129`，
        #     只去掉不属于本页的 `btn_draw_expression` / `btn_draw_anno_figure`。
        variant_button_map = (
            ('btn_load_gene', 'import_button'),
            ('btn_draw_violin', 'run_button'),
            ('btn_export_violin_png', 'export_button'),
            ('btn_export_violin_pdf', 'export_button'),
            ('btn_export_violin_svg', 'export_button'),
            ('btn_export_violin_plot_csv', 'export_button'),
        )
        for attr_name, widget_type in variant_button_map:
            variant_btn = getattr(self, attr_name, None)
            if variant_btn is not None:
                variant_btn.setStyleSheet(get_stylesheet_for_widget(widget_type))

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_violin_page.findChildren(QLabel):
            if child.objectName() == "spatial_violin_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)

        title_label = self.spatial_violin_page.findChild(QLabel, "spatial_violin_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        # ★ 四个局部 objectName（`styled_panel_filter1`/`filter2`/`pairwise`/`export_size`）
        #   也以 `styled_panel` 开头 ⇒ 与三栏面板一起被刷新（与表达页同款行为）
        for child in self.spatial_violin_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.spatial_violin_page.findChild(QWidget, "spatial_violin_overlay")
        if overlay:
            overlay.setStyleSheet(
                f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

    # ------------------------------------------------------------------
    # ★ 新页**自建**的样本选择面板（§1.4 决策 ①：不复用表达页的）
    #   形状逐行照差异页 `ui_layout_spatial_diff.py:248-276`，
    #   属性名与表达页/差异页**逐字一致**：
    #     sample_panel / sample_list / sample_count_label /
    #     btn_sample_all / btn_sample_high_score / btn_sample_invert
    #   ★ 默认全不选、列表为空：填内容与"按样本重算"全归 bind（本层只建控件）。
    # ------------------------------------------------------------------
    def _create_sample_panel(self, parent, layout):
        """左栏：样本多选列表 + 计数 + 全选/选高分/反选（★ 只建控件，不查任何数据）"""
        title = create_styled_label("样本选择", font_size=12, parent=parent)
        layout.addWidget(title)

        # ★ 返回单个 widget；multi_selection=True → QListWidget.MultiSelection
        # ★ fixed_height 走 setMaximumHeight，必须显式传，否则会被主题默认值压到 100px
        self.sample_list = create_styled_list_widget(
            parent=parent, fixed_height=360, multi_selection=True)
        layout.addWidget(self.sample_list)

        self.sample_count_label = create_styled_label(
            "已选 0 / 0", font_size=10, bold=False, parent=parent)
        layout.addWidget(self.sample_count_label)

        layout.addSpacing(8)

        # 三个快捷选择按钮：★ 只建按钮，不查任何评分（"≥4★" 的判断属 bind）
        self.btn_sample_all = create_styled_button("全选", font_size=10, parent=parent)
        layout.addWidget(self.btn_sample_all)

        self.btn_sample_high_score = create_styled_button(
            "选已审查高分（总分≥4★）", font_size=10, parent=parent)
        layout.addWidget(self.btn_sample_high_score)

        self.btn_sample_invert = create_styled_button("反选", font_size=10, parent=parent)
        layout.addWidget(self.btn_sample_invert)

        layout.addStretch()

    # ------------------------------------------------------------------
    # 小提琴图整页（左 280 / 中 280 / 右 200 + 出图区）
    #   = 单细胞 `scRNAseq_layer/violin_layer/ui_layout_violin.py` 的近乎一比一复刻，
    #     全部控件属性名加 `violin_` 前缀（名字/参数/文案逐字照规格书，不得自创）。
    #   ★ v11：从 `ui_layout_spatial_expression.py:337-662` **整块搬来**，
    #     控件面**一行都没动**；只把外层注释里的"模式"字样改成"页面"。
    # ------------------------------------------------------------------
    def _create_violin_panel(self, panel):
        """「小提琴图」页面主体：左=基因/分组/筛选(280) 中=参数调整(280)
        右=导出选项(200) ｜ 最右=出图区（三页签，固定顺序）"""
        styles = get_mod_styles()

        row = QHBoxLayout(panel)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        # ================= 左面板：基因 + 主注释（分组）+ 筛选1/2 + 日志 =================
        left_panel, left_layout = create_styled_panel(parent=panel, fixed_width=280)
        left_layout.setContentsMargins(8, 8, 8, 8)

        left_layout.addWidget(create_styled_label(
            "基因名称", font_size=12, bold=True, parent=left_panel))

        self.violin_gene_input = create_styled_line_edit(parent=left_panel)
        left_layout.addWidget(self.violin_gene_input)

        self.btn_load_gene = create_styled_button(
            "加载基因", font_size=12, parent=left_panel, variant='import')
        left_layout.addWidget(self.btn_load_gene)

        left_layout.addSpacing(10)

        left_layout.addWidget(create_styled_label(
            "主注释（分组）", font_size=12, bold=True, parent=left_panel))

        self.violin_main_combo = create_styled_combo_box(parent=left_panel)
        left_layout.addWidget(self.violin_main_combo)

        self.violin_main_list = create_styled_list_widget(
            parent=left_panel, fixed_height=100, multi_selection=True)
        left_layout.addWidget(self.violin_main_list)

        anno_filter_note = create_styled_label(
            "选择注释类别以筛选细胞显示", font_size=9, bold=False, parent=left_panel)
        anno_filter_note.setStyleSheet(
            f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(anno_filter_note)

        # ---- 筛选1 ----
        filter1_frame = QFrame(left_panel)
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(
            f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; "
            f"border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.violin_filter1_enable = create_styled_checkbox("启用筛选1", parent=filter1_frame)
        filter1_header.addWidget(self.violin_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_layout.addWidget(create_styled_label(
            "筛选分类列1", font_size=11, bold=False, parent=filter1_frame))

        self.violin_filter1_combo = create_styled_combo_box(parent=filter1_frame)
        self.violin_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.violin_filter1_combo)

        filter1_layout.addWidget(create_styled_label(
            "筛选组别1（可多选）", font_size=11, bold=False, parent=filter1_frame))

        self.violin_filter1_list = create_styled_list_widget(
            parent=filter1_frame, fixed_height=80, multi_selection=True)
        self.violin_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.violin_filter1_list)

        left_layout.addWidget(filter1_frame)

        # ---- 筛选2 ----
        filter2_frame = QFrame(left_panel)
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(
            f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; "
            f"border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.violin_filter2_enable = create_styled_checkbox("启用筛选2", parent=filter2_frame)
        filter2_header.addWidget(self.violin_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_layout.addWidget(create_styled_label(
            "筛选分类列2", font_size=11, bold=False, parent=filter2_frame))

        self.violin_filter2_combo = create_styled_combo_box(parent=filter2_frame)
        self.violin_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.violin_filter2_combo)

        filter2_layout.addWidget(create_styled_label(
            "筛选组别2（可多选）", font_size=11, bold=False, parent=filter2_frame))

        self.violin_filter2_list = create_styled_list_widget(
            parent=filter2_frame, fixed_height=80, multi_selection=True)
        self.violin_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.violin_filter2_list)

        left_layout.addWidget(filter2_frame)

        # 日志（§3.1 最后一行；只写控件，内容归 W2/W3）
        self.violin_log = create_styled_text_edit(
            parent=left_panel, read_only=True, variant='sub')
        self.violin_log.setMaximumHeight(80)
        left_layout.addWidget(self.violin_log)

        left_layout.addStretch()
        row.addWidget(left_panel)

        # ================= 中面板：参数调整 =================
        center_panel, center_layout = create_styled_panel(parent=panel, fixed_width=280)

        center_layout.addWidget(create_styled_label(
            "参数调整", font_size=14, bold=True, parent=center_panel))
        center_layout.addSpacing(8)

        title_name_layout = QHBoxLayout()
        title_name_layout.addWidget(create_styled_label(
            "标题名称", font_size=10, bold=False, parent=center_panel))
        self.violin_title_name = create_styled_line_edit(parent=center_panel, fixed_width=160)
        title_name_layout.addWidget(self.violin_title_name)
        center_layout.addLayout(title_name_layout)
        center_layout.addSpacing(5)

        title_size_layout = QHBoxLayout()
        title_size_layout.addWidget(create_styled_label(
            "标题字体大小", font_size=10, bold=False, parent=center_panel))
        self.violin_title_size = create_styled_spinbox(
            parent=center_panel, min_value=8, max_value=40, default_value=16)
        title_size_layout.addWidget(self.violin_title_size)
        center_layout.addLayout(title_size_layout)
        center_layout.addSpacing(5)

        ylabel_name_layout = QHBoxLayout()
        ylabel_name_layout.addWidget(create_styled_label(
            "纵坐标名称", font_size=10, bold=False, parent=center_panel))
        self.violin_ylabel_name = create_styled_line_edit(parent=center_panel, fixed_width=160)
        ylabel_name_layout.addWidget(self.violin_ylabel_name)
        center_layout.addLayout(ylabel_name_layout)
        center_layout.addSpacing(5)

        axis_size_layout = QHBoxLayout()
        axis_size_layout.addWidget(create_styled_label(
            "坐标字体大小", font_size=10, bold=False, parent=center_panel))
        self.violin_axis_size = create_styled_spinbox(
            parent=center_panel, min_value=8, max_value=30, default_value=12)
        axis_size_layout.addWidget(self.violin_axis_size)
        center_layout.addLayout(axis_size_layout)
        center_layout.addSpacing(5)

        pairwise_size_layout = QHBoxLayout()
        pairwise_size_layout.addWidget(create_styled_label(
            "组间比较字体", font_size=10, bold=False, parent=center_panel))
        self.violin_pairwise_size = create_styled_spinbox(
            parent=center_panel, min_value=8, max_value=30, default_value=11)
        pairwise_size_layout.addWidget(self.violin_pairwise_size)
        center_layout.addLayout(pairwise_size_layout)
        center_layout.addSpacing(5)

        # ---- 组间比较框（`styled_panel_pairwise`，与单细胞同款 objectName）----
        pairwise_frame = QFrame(center_panel)
        pairwise_frame.setObjectName("styled_panel_pairwise")
        pairwise_frame.setStyleSheet(
            f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; "
            f"border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; "
            f"border-radius: 5px; padding: 8px;")
        pairwise_layout = QVBoxLayout(pairwise_frame)
        pairwise_layout.setContentsMargins(5, 5, 5, 5)

        self.violin_pairwise_enable = create_styled_checkbox(
            "启用组间比较", parent=pairwise_frame)
        self.violin_pairwise_enable.setChecked(True)
        pairwise_layout.addWidget(self.violin_pairwise_enable)

        self.violin_pairwise_list = create_styled_list_widget(
            parent=pairwise_frame, fixed_height=80, multi_selection=True)
        pairwise_layout.addWidget(self.violin_pairwise_list)

        # 局部「全选」（§3.2：与单细胞同名同行为 —— 只点一下列表全选，无业务逻辑）
        pairwise_select_all_btn = create_styled_button(
            "全选", font_size=9, parent=pairwise_frame)
        pairwise_select_all_btn.clicked.connect(
            lambda: self.violin_pairwise_list.selectAll())
        pairwise_layout.addWidget(pairwise_select_all_btn)

        self.violin_overall_pvalue = create_styled_checkbox(
            "总体比较p值", parent=pairwise_frame)
        self.violin_overall_pvalue.setChecked(False)
        pairwise_layout.addWidget(self.violin_overall_pvalue)

        pvalue_mode_layout = QHBoxLayout()
        pvalue_mode_layout.addWidget(create_styled_label(
            "p值模式", font_size=9, bold=False, parent=pairwise_frame))
        self.violin_pvalue_mode = create_styled_combo_box(parent=pairwise_frame)
        self.violin_pvalue_mode.addItems([
            "*表示显著，n.s.表示不显著",
            "*表示显著，不显著显示具体值",
            "n.s.表示不显著，显著显示具体值",
            "全部用具体值表示（p=?）"
        ])
        self.violin_pvalue_mode.setCurrentIndex(0)
        pvalue_mode_layout.addWidget(self.violin_pvalue_mode)
        pairwise_layout.addLayout(pvalue_mode_layout)

        # 勾选联动（复刻 `on_pairwise_enable_changed`：纯控件显隐，不是业务逻辑）
        self.violin_pairwise_enable.stateChanged.connect(
            lambda state: self.on_pairwise_enable_changed(state, pairwise_select_all_btn))

        center_layout.addWidget(pairwise_frame)
        center_layout.addSpacing(15)

        self.btn_draw_violin = create_styled_button(
            "▶ 生成结果图", font_size=12, parent=center_panel, button_type='run')
        center_layout.addWidget(self.btn_draw_violin)

        center_layout.addStretch()
        row.addWidget(center_panel)

        # ================= 右面板：导出选项 =================
        export_panel, export_layout = create_styled_panel(parent=panel, fixed_width=200)

        export_layout.addWidget(create_styled_label(
            "导出选项", font_size=12, bold=True, parent=export_panel))
        export_layout.addSpacing(8)

        export_size_frame = QFrame(export_panel)
        export_size_frame.setObjectName("styled_panel_export_size")
        export_size_frame.setStyleSheet(
            f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; "
            f"border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; "
            f"border-radius: 5px; padding: 5px;")
        export_size_layout = QVBoxLayout(export_size_frame)
        export_size_layout.setContentsMargins(5, 5, 5, 5)

        export_size_layout.addWidget(create_styled_label(
            "导出尺寸", font_size=10, bold=False, parent=export_size_frame))

        width_row = QHBoxLayout()
        width_row.addSpacing(5)
        width_row.addWidget(create_styled_label(
            "宽度:", font_size=10, bold=False, parent=export_size_frame))
        self.violin_export_width = create_styled_spinbox(
            parent=export_size_frame, min_value=1, max_value=100, default_value=10)
        width_row.addWidget(self.violin_export_width)
        width_row.addStretch()
        export_size_layout.addLayout(width_row)

        height_row = QHBoxLayout()
        height_row.addSpacing(5)
        height_row.addWidget(create_styled_label(
            "高度:", font_size=10, bold=False, parent=export_size_frame))
        self.violin_export_height = create_styled_spinbox(
            parent=export_size_frame, min_value=1, max_value=100, default_value=8)
        height_row.addWidget(self.violin_export_height)
        height_row.addStretch()
        export_size_layout.addLayout(height_row)

        export_layout.addWidget(export_size_frame)
        export_layout.addSpacing(8)

        self.btn_export_violin_png = create_styled_button(
            "导出PNG", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_violin_png)

        self.btn_export_violin_pdf = create_styled_button(
            "导出PDF", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_violin_pdf)

        self.btn_export_violin_svg = create_styled_button(
            "导出SVG", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_violin_svg)

        self.btn_export_violin_plot_csv = create_styled_button(
            "导出绘图CSV", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_violin_plot_csv)

        export_layout.addStretch()
        row.addWidget(export_panel)

        # ================= 出图区：三页签（固定顺序）=================
        #   ★ 用 `create_styled_image_tab(tabs, 标题)` 的返回 label 接图（与单细胞一致，
        #     label 是 ZoomableImageLabel → 支持滚轮缩放/拖动）。
        plot_panel = QWidget(panel)
        plot_layout = QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        self.violin_plot_tabs = create_styled_tab_widget(parent=plot_panel)

        _, self.violin_box_label = create_styled_image_tab(
            self.violin_plot_tabs, "箱线小提琴图")

        _, self.violin_box_only_label = create_styled_image_tab(
            self.violin_plot_tabs, "箱线图")

        _, self.violin_only_label = create_styled_image_tab(
            self.violin_plot_tabs, "小提琴图")

        # ★ v5.1 实测（保留原注释，v11 搬家后同样适用）：样本列(260) + 三栏面板之后，
        #   1600×900 下出图区只剩 ~278px；而 `create_styled_image_tab` 给 label 的**硬最小**
        #   是 400×300（那是为整页图集设计的）⇒ 不放松就会把图**裁掉**。
        #   这里只给**本页的**三个显示 label 一个更合适的地板 240×180：
        #   出图区本就是可伸缩区（图可滚轮缩放/拖动，见 ZoomableImageLabel），
        #   小提琴三面板(280/280/200)与样本列(260)**一个都没缩**。
        for _label in (self.violin_box_label, self.violin_box_only_label,
                       self.violin_only_label):
            _label.setMinimumSize(240, 180)

        plot_layout.addWidget(self.violin_plot_tabs)
        row.addWidget(plot_panel, stretch=1)

        # ★ 变体配色：`btn_load_gene` 走的是 `variant='import'` + `button_type='normal'`，
        #   工厂 `_reapply_styled_button` 的 else 分支取不到 `import_*` 主题键 ⇒ 只是普通底色；
        #   单细胞靠页尾 `update_styles()` 里那句 `import_button` 专用 QSS 才变紫。
        #   这里**只对新按钮**显式刷这一句（幂等；`update_styles()` 里也会再刷一次）。
        for _name, _widget_type in (('btn_load_gene', 'import_button'),
                                    ('btn_draw_violin', 'run_button')):
            _btn = getattr(self, _name, None)
            if _btn is not None:
                _btn.setStyleSheet(get_stylesheet_for_widget(_widget_type))

    def on_pairwise_enable_changed(self, state, select_all_btn):
        """「启用组间比较」的纯控件联动（复刻单细胞同名方法）

        ★ 只是启用/禁用控件，不做任何分析/取数（业务归 bind/analysis）。
        """
        enabled = state == Qt.Checked
        self.violin_pairwise_list.setEnabled(enabled)
        select_all_btn.setEnabled(enabled)
        self.violin_overall_pvalue.setEnabled(enabled)
        self.violin_pvalue_mode.setEnabled(enabled)

    # ------------------------------------------------------------------
    def create_page(self):
        """创建「小提琴图」页面（★ 只建控件；不读数据、不写盘、不连信号）"""
        self.spatial_violin_page = QWidget(self.parent)
        # ★ 页根控件的 objectName **逐字等于页名**（§1 硬要求；`attr_name` 也等于 `name`）
        self.spatial_violin_page.setObjectName("spatial_violin_page")

        styles = get_mod_styles()
        paths = get_mod_paths()

        # ========== 1. 背景层 ==========
        bg_label = QLabel(self.spatial_violin_page)
        bg_label.setObjectName("spatial_violin_bg")
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
        overlay = QWidget(self.spatial_violin_page)
        overlay.setObjectName("spatial_violin_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== 3. 左侧导航栏（★ 只有「← 返回主页」）==========
        #   ★ 按钮属性名必须是 `nav_btn_*` 前缀：`update_styles()` 按该前缀收集并跳过上色。
        #   ⛔ **不建**表达页那两个模式导航（`nav_btn_basic` / `nav_btn_violin`）
        #     —— v11 解离后不存在"两模式"，返回一律回 hub（§1.2-D）。
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_header("小提琴图", font_size=11, parent=nav_panel))

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

        title_label = QLabel("小提琴图")
        title_label.setObjectName("spatial_violin_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        # ★ v11 协调者补齐：页面标题必须**挂成属性**（= `spatial_violin_title`），
        #   与兄弟页 `spatial_expression_title` / `spatial_initial_title` 同一口径；
        #   只 setObjectName 不挂属性的话 `hasattr(ui, 'spatial_violin_title')` 为假，
        #   自检/验收拿不到它（`update_styles` 里那处 `findChild` 也说明它本来就该是公开控件）。
        self.spatial_violin_title = title_label
        title_row_layout.addWidget(title_label)

        mod_instance = global_mod_manager.get_current_mod()
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.spatial_violin_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub')
        title_row_layout.addWidget(music_container)

        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)
        top_bar_layout.addLayout(title_row_layout)
        content_layout.addWidget(top_bar)

        # ---- 主体：页面级「样本选择」列(260) + 小提琴三栏 + 出图区 ----
        body = QWidget(content_panel)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 10, 20, 20)
        body_layout.setSpacing(12)

        # 样本列：固定宽 260（与表达页/差异页一致，不缩控件）
        self.sample_panel, sample_layout = create_styled_panel(parent=body, fixed_width=260)
        sample_layout.setContentsMargins(8, 8, 8, 8)
        self._create_sample_panel(self.sample_panel, sample_layout)
        body_layout.addWidget(self.sample_panel)

        # 小提琴主体（左/中/右三栏 + 出图区）
        self.violin_panel = QWidget(body)
        self._create_violin_panel(self.violin_panel)
        body_layout.addWidget(self.violin_panel, stretch=1)

        content_layout.addWidget(body, stretch=1)
        main_layout.addWidget(content_panel)

        # ★ 初始化完成后立即应用样式（与原型 `:552-553` 一致）
        self.update_styles()

        # ★ 供 page_intersect 取根控件（`attr_name='spatial_violin_page'` 逐字）
        return self.spatial_violin_page


__all__ = ['SpatialViolinPageUI']
