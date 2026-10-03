# -*- coding: utf-8 -*-
"""空转「表达量分析」页面UI布局脚本 - 只负责创建控件、规划窗口布局、设置样式尺寸

完全不写按钮点击、触发逻辑；**任何地方都不读数据**
（不读 manifest/csv/json、不扫目录、不建 QPixmap（背景图除外，与其它页同款）、
 不 import/实例化 analysis 类）。

## v4（用户 2026-09-20）由来
原「初步分析」页把**两个大类**（总体概览 / 表达分析）塞在一个页签栈控件里，
现按用户拍板**拆成两个独立子页**：本页 = 表达量分析（`spatial_expression_page`），
另一个 = 总体概览（`ui_layout_spatial_initial.py` 瘦身后只剩图集与导出）。
⇒ 本文件的基因/表达控件与建法是**从 `ui_layout_spatial_initial.py` 逐字搬过来**的，
  只把 `parent` 换成新页；**不要**在这里顺手重构逻辑。

## v11（2026-09-25）由来：**小提琴图已整块解离出本页**（规格 `_d_spec_v11_split_and_bubble.md` §1）
用户原话：小提琴图要**从表达量分析页解离**成主页「初步分析类」里的新按钮 + 新页，
且**文件夹也解离**（搬去它自己的层目录 —— 目录名见规格 §1.1 的目录表）。
⇒ 本页如今**只留「基础表达」**，本次删除的东西（⛔ 一个引用都不许再出现在本文件里）：
  · 双模式页签栈容器与它的"小提琴"成员页；
  · 左导航里的模式切换（小标题「表达模式」+ 两个模式按钮）—— 导航**只剩**「← 返回主页」；
  · 整块小提琴三栏（原私有建页方法，已按 **31 项冻结清单逐字**搬到新页目录）；
  · 只服务小提琴的样式补偿（`update_styles` 的变体清单）与只服务小提琴的纯控件联动方法。
★ **有意保留**容器 `basic_panel`（不再挂在页签栈上，**直接作为页面主体**）——
  它的语义仍然准确（"基础表达内容容器"），且既有父子断言（`_EXPR_BASIC_PANEL_ATTRS`）
  一条都不用重写。
★ 页面级样本列（`sample_panel` / `sample_list` / `sample_count_label` /
  `btn_sample_all` / `btn_sample_high_score` / `btn_sample_invert`）**留在本页**：
  基础表达仍以"左侧选中的样本"为输入。

## 布局（v11）
```
spatial_expression_page（根）
└── overlay（遮罩）
      ├── nav_panel(220)：nav_btn_back「← 返回主页」+ 弹簧（★ 导航只剩这一件）
      └── content_panel
            ├── top_bar（标题「表达量分析」+ 音乐控件，不动）
            └── body（横向，20/10/20/20，间距 12）
                  ├── sample_panel(260)「样本选择」= 页面级样本列
                  └── basic_panel：左列 fixed_width=420 控制区 + 右列结果区（结果页签常驻可见）
```

★ 本文件**只建控件**：不做业务逻辑（不读数据、不调 R、不写盘、不弹对话框），
  按钮点击后的编排全部归 W2 的 bind。

## v6（2026-09-23）由来
基础表达新增「注释分组」下拉 `anno_group_combo`（契约 `_d_spec_region_naming_v2.md` §5.1）：
`basic_panel` 左列里、`btn_draw_anno_figure` **上一行**，固定三项
`["group_graphed", "cell_type", "cluster"]`、默认 index 0。
**本层只建控件**：按 `currentText()` 分流取预渲染产物的是 W2（§5.2）。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_panel, create_styled_label,
    create_styled_list_widget, create_styled_text_edit,
    create_styled_combo_box, create_wrapping_tab_strip,
    create_navigation_panel, create_navigation_button
)
from script.mods_layer.mod_manager import global_mod_manager


class SpatialExpressionPageUI:
    """「表达量分析」页面布局类（只建控件）"""

    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    # ------------------------------------------------------------------
    def update_background(self):
        """切换模组时重载背景图（只碰背景 QLabel，不读任何数据）"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.spatial_expression_page.findChild(QLabel, "spatial_expression_bg")
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
        """刷新样式：跳过导航按钮与背景标签；只刷普通按钮/标签/标题配色/面板底色"""
        styles = get_mod_styles()

        button_style = get_stylesheet_for_widget('button')
        nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
        export_names = ('btn_gene_export_png', 'btn_gene_export_pdf')
        export_buttons = [getattr(self, n) for n in export_names if hasattr(self, n)]
        for child in self.spatial_expression_page.findChildren(QPushButton):
            if child in nav_buttons:
                continue
            # 折行页签条内部的按钮是"标签式"，不要被普通按钮 QSS 覆盖
            # （`gene_result_tabs` 是 WrappingTabStrip，内部全是标签式按钮）
            if self.gene_result_tabs is not None and self.gene_result_tabs.isAncestorOf(child):
                continue
            # 「一键批量导出」按钮用 export 专用样式，别被普通按钮 QSS 覆盖（下面显式刷）
            if child in export_buttons or child.objectName() == 'styled_btn_export':
                continue
            child.setStyleSheet(button_style)

        export_style = get_stylesheet_for_widget('export_button')
        for btn in export_buttons:
            btn.setStyleSheet(export_style)

        # ★ v5（只**新增**补偿，不动上面既有分支）：变体色按钮在上面的通用 `button`
        #   QSS 里会被刷成普通按钮 → 这里按各自变体再刷回来（拿不到就跳过）。
        #   ★ v11：小提琴整块解离出本页 ⇒ 清单里**只剩基础表达**的两个"运行"按钮
        #   （`btn_draw_expression` 与 `btn_draw_anno_figure` 是**同一行**的两个运行按钮，
        #    只补一个会让一个红一个蓝、看起来像 bug）。
        #   ★ 只重刷"样式表"，不碰控件本体/名字/信号。
        variant_button_map = (
            ('btn_draw_expression', 'run_button'),
            ('btn_draw_anno_figure', 'run_button'),
        )
        for attr_name, widget_type in variant_button_map:
            variant_btn = getattr(self, attr_name, None)
            if variant_btn is not None:
                variant_btn.setStyleSheet(get_stylesheet_for_widget(widget_type))

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_expression_page.findChildren(QLabel):
            if child.objectName() == "spatial_expression_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)

        title_label = self.spatial_expression_page.findChild(QLabel, "spatial_expression_title")
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
        for child in self.spatial_expression_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    # ------------------------------------------------------------------
    # 本页自己的样本选择面板（与「总体概览」页**同名同形**）
    # ------------------------------------------------------------------
    def _create_sample_panel(self, parent, layout):
        """左栏：样本多选列表 + 三个快捷按钮 + 计数（★ 默认全不选，列表为空）"""
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
    # 表达量：输入区 + 结果区（★ 从 ui_layout_spatial_initial.py 逐字搬来）
    # ------------------------------------------------------------------
    def _create_gene_panel(self, parent, layout):
        """「表达量分析」页里的**输入区**（★ 只建控件；不读数据、不写 R/subprocess）"""
        gene_title = create_styled_label("基因表达量图（按需）", font_size=12, parent=parent)
        layout.addWidget(gene_title)

        # ★ 第 4 轮实测要求：左列控件**高度写死**，不要自适应拉伸。
        #   原因：`gene_log_text` 是 QTextEdit（可垂直扩张），不写死就会吃掉整列余高、
        #   被拉得很高（用户原话"控件高度被拉伸的太高，不美观"）。
        #   余量统一交给末尾的 addStretch()。
        self.gene_input = create_styled_text_edit(parent=parent)
        self.gene_input.setPlaceholderText("每行一个基因（最多 20 个）；输入多个基因 = 基因集合")
        self.gene_input.setFixedHeight(70)
        layout.addWidget(self.gene_input)

        self.btn_draw_expression = create_styled_button(
            "绘制表达量图", font_size=11, parent=parent, button_type='run')
        self.btn_draw_expression.setFixedHeight(34)

        # ★ §2：新增「绘图模式注释图」（与 `btn_draw_expression` **同一行**）
        #   只建控件 —— 点它之后"对当前选中样本出注释图页签"的编排归 W2。
        self.btn_draw_anno_figure = create_styled_button(
            "绘图模式注释图", font_size=12, parent=parent, button_type='run')
        self.btn_draw_anno_figure.setFixedHeight(34)

        # ★ v6（契约 `_d_spec_region_naming_v2.md` §5.1，2026-09-23）：新增
        #   「注释分组」下拉 —— 注释图按哪个分组取预渲染产物
        #   （`group_graphed` 默认 / `cell_type` / `cluster`）。
        #   ★ 本层**只建控件 + 填固定三项**：按 `currentText()` 分流取图的是 W2（§5.2）。
        #   ★ 位置：`btn_draw_anno_figure` 的**上一行**（同一区域）—— 左列 fixed_width=420，
        #     "两个 run 按钮 + label + combo" 硬挤一行会宽度不足，故单独成行；
        #     现有控件（基因输入/状态/日志/导出按钮/小提琴全部）**一个都不挤、一个都不动**。
        anno_group_row = QHBoxLayout()
        anno_group_row.addWidget(create_styled_label("注释分组", font_size=10,
                                                     bold=False, parent=parent))
        self.anno_group_combo = create_styled_combo_box(parent=parent)
        self.anno_group_combo.addItems(["group_graphed", "cell_type", "cluster"])
        self.anno_group_combo.setCurrentIndex(0)
        anno_group_row.addWidget(self.anno_group_combo, stretch=1)
        layout.addLayout(anno_group_row)

        draw_row = QHBoxLayout()
        draw_row.addWidget(self.btn_draw_expression)
        draw_row.addWidget(self.btn_draw_anno_figure)
        layout.addLayout(draw_row)

        self.gene_status_label = create_styled_label(
            "尚未输入基因", font_size=10, bold=False, parent=parent)
        self.gene_status_label.setWordWrap(True)
        self.gene_status_label.setFixedHeight(38)
        layout.addWidget(self.gene_status_label)

        self.gene_log_text = create_styled_text_edit(read_only=True)
        self.gene_log_text.setFixedHeight(70)
        self.gene_log_text.setFont(get_font_for_widget('label', 10))
        self.gene_log_text.setText("等待操作...")
        layout.addWidget(self.gene_log_text)

        # ★ 表达量页的「一键批量导出」一对按钮（并排一行，固定高度 34）
        #   位置：`addStretch()` **之前**（否则会被弹簧顶到底部）
        self.btn_gene_export_png, self.btn_gene_export_pdf = self._create_export_buttons(parent)
        gene_export_row = QHBoxLayout()
        gene_export_row.addWidget(self.btn_gene_export_png)
        gene_export_row.addWidget(self.btn_gene_export_pdf)
        layout.addLayout(gene_export_row)

        # ★ 余量交给弹簧（这样窗口拉高时是弹簧变高，而不是控件被拉伸）
        layout.addStretch()

    def _create_gene_result_panel(self, parent, layout):
        """「表达量分析」右列：基因表达量图的**结果区**（★ 常驻可见）

        - `gene_result_tabs` **一开始就可见**（用户第三轮实测：原来"输入后才在下方弹出"很难看）；
          空的时候用 `gene_result_empty_hint` 占位，不留白板。
        - 结果数量随基因数增长，**页签不可能在布局期预建** → 由 func 的
          `add_gene_result()` 逐张 `addTab`（这一处建控件归 func，已在契约里注明）。
        """
        self.gene_result_title = create_styled_label(
            "基因表达量图结果", font_size=12, parent=parent)
        layout.addWidget(self.gene_result_title)

        # ★ 常驻可见（不再 setVisible(False)）
        self.gene_result_tabs = create_wrapping_tab_strip(parent=parent)
        layout.addWidget(self.gene_result_tabs, stretch=1)

        # 空状态占位（由 bind 在"有结果/无结果"时切显隐）
        self.gene_result_empty_hint = create_styled_label(
            "尚未绘制任何基因；在左侧输入基因名后点『绘制表达量图』",
            font_size=10, bold=False, parent=parent)
        self.gene_result_empty_hint.setAlignment(Qt.AlignCenter)
        self.gene_result_empty_hint.setWordWrap(True)
        layout.addWidget(self.gene_result_empty_hint)

    def _create_export_buttons(self, parent):
        """建一对「一键批量导出」按钮（PNG / PDF），返回 `(png_btn, pdf_btn)`。

        用户第 5 轮原话：「弄简单粗暴些一键批量导出，可选路径…导出一键所有 PDF，
        或者导出一键所有 png，就别一个一个选了导出了」
        ★ 只建控件：**不读数据、不写文件、不弹对话框**（对话框与复制逻辑归 W2 的 bind）。
        ★ 用 `button_type='export'`（objectName = `styled_btn_export`），
          与 bulk_expr 的 `get_stylesheet_for_widget('export_button')` 同一套样式。
        """
        png_btn = create_styled_button(
            "导出全部PNG", font_size=10, parent=parent, button_type='export')
        pdf_btn = create_styled_button(
            "导出全部PDF", font_size=10, parent=parent, button_type='export')
        for btn in (png_btn, pdf_btn):
            btn.setFixedHeight(34)
        return png_btn, pdf_btn

    def _create_expression_category(self, parent):
        """表达量**整页**：分两列（左=控制 / 右=结果，结果页签常驻）

        用户第三轮原话：「表达分析类的图标签页能不能放在右侧并且一直存在？
        现在属于是输入基因后它才能在下方弹出来，这样非常不美观，我们需要分两列来呈现」
        """
        page = QWidget(parent)
        row = QHBoxLayout(page)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(12)

        # 左列（控制）：输入 + 按钮 + 状态 + 日志
        left_col, left_layout = create_styled_panel(parent=page, fixed_width=420)
        left_layout.setContentsMargins(8, 8, 8, 8)
        self._create_gene_panel(left_col, left_layout)
        row.addWidget(left_col)

        # 右列（结果）：结果页签常驻 + 空状态占位
        right_col, right_layout = create_styled_panel(parent=page)
        right_layout.setContentsMargins(8, 8, 8, 8)
        self._create_gene_result_panel(right_col, right_layout)
        row.addWidget(right_col, stretch=1)

        return page

    # ------------------------------------------------------------------
    def create_page(self):
        self.spatial_expression_page = QWidget(self.parent)
        self.gene_result_tabs = None      # 先占位，供 update_styles 的守卫使用

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.spatial_expression_page)
        bg_label.setObjectName("spatial_expression_bg")
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

        overlay = QWidget(self.spatial_expression_page)
        overlay.setObjectName("spatial_expression_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 左导航：**只有「← 返回主页」**（v11：双模式导航随小提琴解离一并删除）=====
        #   ★ 按钮属性名必须是 `nav_btn_*` 前缀：`update_styles()` 按该前缀收集并跳过上色。
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # ===== 顶部外框 + 标题 + 音乐控制器 =====
        top_bar, top_bar_layout = create_styled_panel(parent=content_panel)
        top_bar_layout.setContentsMargins(15, 8, 15, 8)

        title_row_layout = QHBoxLayout()

        title_label = QLabel("表达量分析")
        title_label.setObjectName("spatial_expression_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)

        mod_instance = global_mod_manager.get_current_mod()
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.spatial_expression_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub')
        title_row_layout.addWidget(music_container)

        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)
        top_bar_layout.addLayout(title_row_layout)
        content_layout.addWidget(top_bar)

        # ===== 主体：**页面级样本列**(260) + 基础表达（v11：已无模式栈）=====
        #   v5.1（2026-09-23）把样本选择面板从 `basic_panel` **提上来**，成为页面级常驻列
        #   —— 基础表达的输入正是"左侧当前选中的样本"。
        #   ★ v11（2026-09-25）：小提琴整块解离后本页只剩基础表达 ⇒ `basic_panel` 不再挂在
        #     页签栈容器上，**直接作为页面主体**（有意保留该容器，见模块头）。
        #   ★ 控件属性名 / objectName / 冻结控件面**一个都没动**，只是换了父级。
        body = QWidget(content_panel)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 10, 20, 20)
        body_layout.setSpacing(12)

        # 样本列：固定宽 260（与 v4 一致，不缩控件）
        self.sample_panel, sample_layout = create_styled_panel(parent=body, fixed_width=260)
        sample_layout.setContentsMargins(8, 8, 8, 8)
        self._create_sample_panel(self.sample_panel, sample_layout)
        body_layout.addWidget(self.sample_panel)

        # 基础表达（v4 的"表达量两列"：左列 420 控制区 + 右列结果区，样本列已提到外层）
        self.basic_panel = QWidget(body)
        basic_layout = QHBoxLayout(self.basic_panel)
        basic_layout.setContentsMargins(0, 0, 0, 0)   # 外层的 20/10/20/20 已经给了页边距
        basic_layout.setSpacing(12)
        basic_layout.addWidget(self._create_expression_category(self.basic_panel), stretch=1)

        body_layout.addWidget(self.basic_panel, stretch=1)

        content_layout.addWidget(body, stretch=1)
        main_layout.addWidget(content_panel)

        return self.spatial_expression_page


__all__ = ['SpatialExpressionPageUI']
