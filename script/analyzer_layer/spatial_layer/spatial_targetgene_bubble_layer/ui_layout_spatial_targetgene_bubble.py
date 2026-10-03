# -*- coding: utf-8 -*-
"""空转「自定义气泡图」页面UI布局脚本 - 只负责创建控件、规划窗口布局、设置样式尺寸

完全不写按钮点击、触发逻辑（跳转/信号/取数/写盘/绘图全部归 W2 的
`ui_bind_spatial_targetgene_bubble.py` 与 W3b 的 `ui_func_spatial_targetgene_bubble.py` /
`spatial_targetgene_bubble_analysis.py`）；**任何地方都不读数据**
（不读 manifest/csv/json、不扫目录、不建 QPixmap（背景图除外，与其它空转页同款）、
 不 import/实例化 analysis 类）。

## v11 由来（规格 `_d_spec_v11_split_and_bubble.md` §2 / §2.1 / §2.3，用户原话"基本一比一复刻"）
本页 = 单细胞 `scRNAseq_layer/sc_targetgene_bubble_layer/ui_layout_sc_targetgene_bubble.py`
（458 行）的空转版：
```
左栏（批量基因输入 → X轴主注释 → Y轴主注释 → 筛选1 → 筛选2 → 筛选并绘图）
中栏（参数调整：标题/色条/尺寸/字号/间距/主图右边界）
右栏（导出选项：导出尺寸 + 5 个导出按钮）
出图区（**单页签** `ZoomableImageLabel`，图贴 `spatial_targetgene_bubble_image_label`）
```
外加空转独有件（§2.4 的输入侧）：**页面级样本列**（复刻差异页，属性名同差异页）。

★ 与「基因集气泡图」页的唯一控件面差异（照抄单细胞的差异，规格 §2.3 末表）：
  分组轴是**两个**（`..._x_combo` / `..._x_list` =「X轴主注释」，`..._y_combo` / `..._y_list`
  =「Y轴主注释」），而不是基因集页的一个 `..._main_combo` / `..._main_list`；
  主图标题默认 `"Target Gene Expression Bubble Plot"`。

## 命名规则（★ 与规格 §2.3 的 `P` 缩写对照，W2/W3b/W5 请照此取名）
规格 §2.3 用 `P_xxx` 简写这一族的控件名，并在正文写明"控件属性名统一加 `spatial_` 前缀"。
本文件采用的**唯一规则 = `spatial_` + 单细胞原属性名逐字**，理由是规格表里
不带 `P_` 的项（`btn_draw_bubble` / `btn_export_png…csv` /
`btn_back_bubble` / `music_controller`）**就是单细胞原名一字不改**，故带 `P_` 的项
只能是同一份单细胞名字再加统一前缀：
```
单细胞 targetgene_text_input             → spatial_targetgene_text_input
单细胞 targetgene_bubble_x_combo         → spatial_targetgene_bubble_x_combo      （规格 P_x_combo）
单细胞 targetgene_bubble_y_list          → spatial_targetgene_bubble_y_list       （规格 P_y_list）
单细胞 targetgene_bubble_filter1_enable  → spatial_targetgene_bubble_filter1_enable
单细胞 targetgene_bubble_main_title      → spatial_targetgene_bubble_main_title   （规格 P_bubble_main_title）
单细胞 targetgene_bubble_log             → spatial_targetgene_bubble_log          （规格 P_bubble_log）
单细胞 targetgene_bubble_image_label     → spatial_targetgene_bubble_image_label  （规格 P_bubble_image_label）
```
★ 规格的 `P` 也可以被读成"整段前缀 `spatial_targetgene_bubble`"，那样 `P_bubble_*`
会展开成 `spatial_targetgene_bubble_bubble_*`（双 `bubble`）。为免 W2/W3b/W5 三种读法
互相打架，本页额外挂一组兼容别名（`_COMPAT_ALIASES`，指向**同一个控件对象**，
不是新控件）：① 上述有歧义的 6 个 `P_bubble_*`；② 样本列的 `spatial_sample_*`
（规格 §2.4 用 `spatial_sample_list`，差异页口径是 `sample_list`，W2 两个名字都探）。
名字以本文件的主名称为准。

## 布局骨架
```
spatial_targetgene_bubble_page（根，objectName = 'spatial_targetgene_bubble_page'）
└── spatial_targetgene_bubble_overlay（遮罩）
      └── QVBoxLayout(20,20,20,20)
            ├── 顶栏：btn_back_bubble「← 返回上一页」+ 标题(32pt「自定义气泡图」) + music_controller
            ├── spatial_targetgene_bubble_log（QTextEdit，read_only，高 80）
            └── 主体（横向，间距 12）
                  ├── sample_panel(260)「样本选择」= 页面级样本列（复刻差异页）
                  ├── 左栏(280)：批量基因 / X轴主注释 / Y轴主注释 / 筛选1 / 筛选2 / 筛选并绘图
                  ├── 中栏(280)：参数调整
                  ├── 右栏(200)：导出选项
                  └── 出图区：单页签 `spatial_targetgene_bubble_plot_tabs`（图贴 image_label）
```

## ⛔ 本文件**不做**的事（规格 §2.8 / §9.5）
- **不建模板控件**（`*_temp_combo` / `*_temp_name`）、**不建**「保存模板/加载模板」按钮
  —— 单细胞那套是死代码（§2.8 缺陷 1）；
- ★★ **不建「加载基因」按钮**（v11.2 用户拍板删除）：基因输入**只有文本框一个入口**，
  点「筛选并绘图」时由 bind 自行解析（见本文件 `create_page` 里那段说明）；
- **不 import** `script.utils_layer.page_intersect`（单细胞那行是未使用的导入，§2.8 缺陷 4）；
- 单细胞 `sc_targetgene_bubble_layer/` **缺 `__init__.py`**（§2.8 缺陷 3）⇒ 本目录**必须有**
  `__init__.py`（导出 `SpatialTargetgeneBubblePageUI` / `SpatialTargetgeneBubbleBind` /
  `SpatialTargetgeneBubbleFunc`）。★ 该文件按分工归 W2/W3b，**本层不建任何 `__init__.py`**；
- 不建业务按钮以外的任何编排：**不连任何 clicked/selectionChanged 信号**；
- 不读任何数据、不写盘（含 `appdata/`、`OUTPUT/`）、不调 R。

## ⚠ 两处已留痕的处置（一处是规格冲突的**裁决**，一处是规格缺陷 4 的绕行）
1. **音乐控件取 mod 单例的方式**：单细胞 layout 顶部有 `from script.mods_layer.mod_manager
   import global_mod_manager`，而本层被要求"不 import `global_mod_manager`"（§2.8 缺陷 4
   认为该行未使用）。但 `music_controller` 是冻结件、**必须**拿到当前模组的音乐控件类，
   故这里改为**复用 `gui_styles` 已持有的同一个 mod 单例**（`gui_styles.global_mod_manager`），
   本文件因此**没有**模组管理器的 import 行，而音乐控件照旧建出。
2. **色条标签默认值 = `"Mean Expression (CP10K)"`**（协调者 2026-09-25 裁决，取代规格
   §2.3/§2.6 互相打架的两句）：
   · 盘上事实：空转 dump **只取 counts 层**（R 侧还做「非负 + 整数」完整性检查）⇒
     `adata.X` = **原始 counts**，**不是** LogNormalize/CP10K；
   · 差异分析**内部**才做 CP10K（`mean_CP10K`），两个页面必须同口径；
   · 颜色若用原始 counts，测序深度大的 spot 会对所有基因都显得高表达 ⇒ 色标退化成
     **文库大小的伪影**；故气泡图颜色 = 组内 **mean CP10K**（`expr / libsize * 10000`，
     libsize 下限 1），由 W3b 的 analysis 落地；
   · `percent_expressed` 不受影响（线性缩放，零仍是零）；
   · 本控件**可编辑**，用户可自行改字符串。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_text_edit, create_styled_spinbox,
    create_styled_tab_widget, create_styled_image_tab
)
# ★ 只为借它已持有的 mod_manager 单例建 `music_controller`（见模块头「偏差 1」）；
#   本层**不**直接 import `script.mods_layer.mod_manager`，也**不** import `page_intersect`。
from script.utils_layer import gui_styles


class SpatialTargetgeneBubblePageUI:
    """空转「自定义气泡图」页面 UI 类（只建控件，不连任何逻辑）"""

    # ------------------------------------------------------------------
    # ★ v11 协调者收敛：**不再挂任何兼容别名**。
    #   原先这里有一张 `_COMPAT_ALIASES`（把 `..._bubble_bubble_*` 另一种读法也接上），
    #   但实测 `ui_bind_*` / `ui_func_*` 的候选名列表**已经包含本层主名**，
    #   别名纯属「一个控件两个名字」⇒ 只会让冻结断言/文档/后人分不清哪个是真名
    #   （本项目 D 系列事故正是"名字对不上 ⇒ 控件建成 ≠ 数据路径通"）。
    #   故删表；控件名以本层主名为**唯一**口径（见模块头「命名规则」）。
    # ------------------------------------------------------------------

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
        bg_label = self.spatial_targetgene_bubble_page.findChild(
            QLabel, "spatial_targetgene_bubble_bg")
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
        """刷新样式：逐行照抄单细胞 `ui_layout_sc_targetgene_bubble.py:39-103`，只做两处删减

        · 找不到控件就跳过（`if title_label:` / `getattr(..., None)`）—— 不抛异常、不静默吞异常；
        · 背景标签与标题标签、`styled_image_label` 不套普通标签 QSS（否则会盖掉背景图/图占位样式）。
        """
        styles = get_mod_styles()

        title_label = self.spatial_targetgene_bubble_page.findChild(
            QLabel, "spatial_targetgene_bubble_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.spatial_targetgene_bubble_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_")
                                       or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        # ★ 变体色按钮（import / run / export）在上面的通用 `button` QSS 里会被刷成普通按钮，
        #   这里按各自变体再刷回来（与单细胞 `:52-65` 同一份清单）。
        for attr_name, widget_type in (('btn_draw_bubble', 'run_button'),
                                       ('btn_export_png', 'export_button'),
                                       ('btn_export_pdf', 'export_button'),
                                       ('btn_export_svg', 'export_button'),
                                       ('btn_export_eps', 'export_button'),
                                       ('btn_export_csv', 'export_button')):
            button = getattr(self, attr_name, None)
            if button is not None:
                button.setStyleSheet(get_stylesheet_for_widget(widget_type))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.spatial_targetgene_bubble_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.spatial_targetgene_bubble_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.spatial_targetgene_bubble_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_targetgene_bubble_page.findChildren(QLabel):
            if child.objectName() == "spatial_targetgene_bubble_bg":
                continue
            if child.objectName() == "spatial_targetgene_bubble_title":
                continue
            if child.objectName().startswith("styled_image_label"):
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.spatial_targetgene_bubble_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.spatial_targetgene_bubble_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.spatial_targetgene_bubble_page.findChild(
            QWidget, "spatial_targetgene_bubble_overlay")
        if overlay:
            overlay.setStyleSheet(
                f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

    # ------------------------------------------------------------------
    # ★ 空转独有：页面级「样本选择」面板（规格 §2.4）
    #   形状照差异页/表达页/小提琴页（属性名逐字一致）：
    #     sample_panel / sample_list / sample_count_label /
    #     btn_sample_all / btn_sample_high_score / btn_sample_invert
    #   ★ 默认全不选、列表为空：填内容与"按样本重算注释选项"全归 W2（本层只建控件）。
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
    # 左栏（280）：批量基因输入 → X轴主注释 → Y轴主注释 → 筛选1 → 筛选2 → 筛选并绘图
    #   逐行复刻单细胞 `ui_layout_sc_targetgene_bubble.py:170-266`
    # ------------------------------------------------------------------
    def _create_left_panel(self, parent):
        """左栏（fixed_width=280）：基因集输入 + **两个**分组轴（X/Y）+ 两套筛选 + 绘图按钮"""
        left_panel, left_layout = create_styled_panel(parent=parent, fixed_width=280)

        # ---- 批量基因输入 ----
        gene_input_frame, gene_input_layout = create_styled_panel(
            parent=left_panel, variant='sub')

        gene_label = create_styled_label(
            "批量基因（每行一个）", font_size=12, bold=True, parent=gene_input_frame)
        gene_input_layout.addWidget(gene_label)

        self.spatial_targetgene_text_input = create_styled_text_edit(
            parent=gene_input_frame, variant='sub')
        self.spatial_targetgene_text_input.setPlaceholderText("请输入基因列表，每行一个基因")
        self.spatial_targetgene_text_input.setMaximumHeight(120)
        gene_input_layout.addWidget(self.spatial_targetgene_text_input)

        # ★★ v11.2（2026-09-25 用户拍板）：**删掉「加载基因」按钮** ——
        #   用户原话：「把加载基因这个按钮控件去掉，我们只保留绘图按钮即可」。
        #   空转不需要"先加载基因"这一步：点「筛选并绘图」时绘图会**自己**按当前文本框
        #   解析基因（`ui_bind_*. _ensure_genes_loaded_for_draw()`），文本框就是唯一输入源。
        # ⛔ 别再建 `btn_load_gene_set`：bind 侧已删掉它的接线，建了就是**没人连的死控件**。

        left_layout.addWidget(gene_input_frame)
        left_layout.addSpacing(10)

        # ---- X轴主注释（第 1 个分组轴）----
        x_anno_label = create_styled_label(
            "X轴主注释", font_size=12, bold=True, parent=left_panel)
        left_layout.addWidget(x_anno_label)

        # ★ 选项内容由 W2 按"选中样本的注释并集"重算（§2.4）：本层只建**空**控件
        self.spatial_targetgene_bubble_x_combo = create_styled_combo_box(parent=left_panel)
        left_layout.addWidget(self.spatial_targetgene_bubble_x_combo)

        self.spatial_targetgene_bubble_x_list = create_styled_list_widget(
            parent=left_panel, fixed_height=100, multi_selection=True)
        left_layout.addWidget(self.spatial_targetgene_bubble_x_list)

        left_layout.addSpacing(10)

        # ---- Y轴主注释（第 2 个分组轴）----
        y_anno_label = create_styled_label(
            "Y轴主注释", font_size=12, bold=True, parent=left_panel)
        left_layout.addWidget(y_anno_label)

        self.spatial_targetgene_bubble_y_combo = create_styled_combo_box(parent=left_panel)
        left_layout.addWidget(self.spatial_targetgene_bubble_y_combo)

        self.spatial_targetgene_bubble_y_list = create_styled_list_widget(
            parent=left_panel, fixed_height=100, multi_selection=True)
        left_layout.addWidget(self.spatial_targetgene_bubble_y_list)

        left_layout.addSpacing(10)

        # ---- 筛选1 ----
        filter1_frame, filter1_layout = create_styled_panel(parent=left_panel)

        filter1_header = QHBoxLayout()
        self.spatial_targetgene_bubble_filter1_enable = create_styled_checkbox(
            "启用筛选1", parent=filter1_frame)
        filter1_header.addWidget(self.spatial_targetgene_bubble_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label(
            "筛选分类列1", font_size=11, bold=False, parent=filter1_frame)
        filter1_layout.addWidget(filter1_col_label)

        self.spatial_targetgene_bubble_filter1_combo = create_styled_combo_box(parent=filter1_frame)
        self.spatial_targetgene_bubble_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.spatial_targetgene_bubble_filter1_combo)

        filter1_group_label = create_styled_label(
            "筛选组别1（可多选）", font_size=11, bold=False, parent=filter1_frame)
        filter1_layout.addWidget(filter1_group_label)

        self.spatial_targetgene_bubble_filter1_list = create_styled_list_widget(
            parent=filter1_frame, fixed_height=80, multi_selection=True)
        self.spatial_targetgene_bubble_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.spatial_targetgene_bubble_filter1_list)

        left_layout.addWidget(filter1_frame)
        left_layout.addSpacing(5)

        # ---- 筛选2 ----
        filter2_frame, filter2_layout = create_styled_panel(parent=left_panel)

        filter2_header = QHBoxLayout()
        self.spatial_targetgene_bubble_filter2_enable = create_styled_checkbox(
            "启用筛选2", parent=filter2_frame)
        filter2_header.addWidget(self.spatial_targetgene_bubble_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label(
            "筛选分类列2", font_size=11, bold=False, parent=filter2_frame)
        filter2_layout.addWidget(filter2_col_label)

        self.spatial_targetgene_bubble_filter2_combo = create_styled_combo_box(parent=filter2_frame)
        self.spatial_targetgene_bubble_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.spatial_targetgene_bubble_filter2_combo)

        filter2_group_label = create_styled_label(
            "筛选组别2（可多选）", font_size=11, bold=False, parent=filter2_frame)
        filter2_layout.addWidget(filter2_group_label)

        self.spatial_targetgene_bubble_filter2_list = create_styled_list_widget(
            parent=filter2_frame, fixed_height=80, multi_selection=True)
        self.spatial_targetgene_bubble_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.spatial_targetgene_bubble_filter2_list)

        left_layout.addWidget(filter2_frame)
        left_layout.addSpacing(10)

        # ---- 绘图按钮（★ 只建按钮，"筛选 + 取数 + 绘图"全归 W2/W3b）----
        self.btn_draw_bubble = create_styled_button(
            "筛选并绘图", font_size=12, parent=left_panel, button_type='run')
        self.btn_draw_bubble.setFixedHeight(35)
        left_layout.addWidget(self.btn_draw_bubble)

        left_layout.addStretch()
        return left_panel

    # ------------------------------------------------------------------
    # 中栏（280）：参数调整 —— 默认值/范围逐字照抄单细胞 `:268-382`
    # ------------------------------------------------------------------
    def _create_center_panel(self, parent):
        """中栏（fixed_width=280）：标题 / 色条 / 画布尺寸 / 字号 / 间距 / 主图右边界"""
        center_panel, center_layout = create_styled_panel(parent=parent, fixed_width=280)

        param_title = create_styled_label("参数调整", font_size=14, bold=True, parent=center_panel)
        center_layout.addWidget(param_title)
        center_layout.addSpacing(8)

        main_title_layout = QHBoxLayout()
        main_title_layout.addWidget(create_styled_label(
            "主图标题", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_main_title = create_styled_line_edit(
            parent=center_panel, fixed_width=160)
        self.spatial_targetgene_bubble_main_title.setText("Target Gene Expression Bubble Plot")
        main_title_layout.addWidget(self.spatial_targetgene_bubble_main_title)
        center_layout.addLayout(main_title_layout)
        center_layout.addSpacing(5)

        cbar_label_layout = QHBoxLayout()
        cbar_label_layout.addWidget(create_styled_label(
            "色条标签", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_cbar_label = create_styled_line_edit(
            parent=center_panel, fixed_width=160)
        # ★ 色条口径（协调者 2026-09-25 裁决）：颜色 = 组内 **mean CP10K**（不是原始 counts）
        #   —— 与差异页的 `mean_CP10K` 同口径；理由与出处见模块头「处置 2」。用户可改。
        self.spatial_targetgene_bubble_cbar_label.setText("Mean Expression (CP10K)")
        cbar_label_layout.addWidget(self.spatial_targetgene_bubble_cbar_label)
        center_layout.addLayout(cbar_label_layout)
        center_layout.addSpacing(5)

        fig_width_layout = QHBoxLayout()
        fig_width_layout.addWidget(create_styled_label(
            "宽度", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_fig_width = create_styled_spinbox(
            parent=center_panel, min_value=1, max_value=100, default_value=9)
        fig_width_layout.addWidget(self.spatial_targetgene_bubble_fig_width)
        center_layout.addLayout(fig_width_layout)
        center_layout.addSpacing(5)

        fig_height_layout = QHBoxLayout()
        fig_height_layout.addWidget(create_styled_label(
            "高度", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_fig_height = create_styled_spinbox(
            parent=center_panel, min_value=1, max_value=100, default_value=7)
        fig_height_layout.addWidget(self.spatial_targetgene_bubble_fig_height)
        center_layout.addLayout(fig_height_layout)
        center_layout.addSpacing(5)

        scale_factor_layout = QHBoxLayout()
        scale_factor_layout.addWidget(create_styled_label(
            "气泡缩放系数", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_scale_factor = create_styled_spinbox(
            parent=center_panel, min_value=100, max_value=2000, default_value=750)
        scale_factor_layout.addWidget(self.spatial_targetgene_bubble_scale_factor)
        center_layout.addLayout(scale_factor_layout)
        center_layout.addSpacing(5)

        legend_scale_layout = QHBoxLayout()
        legend_scale_layout.addWidget(create_styled_label(
            "图例整体缩放", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_legend_scale = create_styled_spinbox(
            parent=center_panel, min_value=10, max_value=30, default_value=10)
        legend_scale_layout.addWidget(self.spatial_targetgene_bubble_legend_scale)
        center_layout.addLayout(legend_scale_layout)
        center_layout.addSpacing(5)

        title_fontsize_layout = QHBoxLayout()
        title_fontsize_layout.addWidget(create_styled_label(
            "标题字号", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_title_fontsize = create_styled_spinbox(
            parent=center_panel, min_value=8, max_value=30, default_value=14)
        title_fontsize_layout.addWidget(self.spatial_targetgene_bubble_title_fontsize)
        center_layout.addLayout(title_fontsize_layout)
        center_layout.addSpacing(5)

        x_label_fontsize_layout = QHBoxLayout()
        x_label_fontsize_layout.addWidget(create_styled_label(
            "X轴标签字号", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_x_label_fontsize = create_styled_spinbox(
            parent=center_panel, min_value=8, max_value=30, default_value=12)
        x_label_fontsize_layout.addWidget(self.spatial_targetgene_bubble_x_label_fontsize)
        center_layout.addLayout(x_label_fontsize_layout)
        center_layout.addSpacing(5)

        y_label_fontsize_layout = QHBoxLayout()
        y_label_fontsize_layout.addWidget(create_styled_label(
            "Y轴标签字号", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_y_label_fontsize = create_styled_spinbox(
            parent=center_panel, min_value=8, max_value=30, default_value=12)
        y_label_fontsize_layout.addWidget(self.spatial_targetgene_bubble_y_label_fontsize)
        center_layout.addLayout(y_label_fontsize_layout)
        center_layout.addSpacing(5)

        legend_label_fontsize_layout = QHBoxLayout()
        legend_label_fontsize_layout.addWidget(create_styled_label(
            "图例标签字号", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_legend_label_fontsize = create_styled_spinbox(
            parent=center_panel, min_value=6, max_value=20, default_value=10)
        legend_label_fontsize_layout.addWidget(self.spatial_targetgene_bubble_legend_label_fontsize)
        center_layout.addLayout(legend_label_fontsize_layout)
        center_layout.addSpacing(5)

        cbar_label_fontsize_layout = QHBoxLayout()
        cbar_label_fontsize_layout.addWidget(create_styled_label(
            "色条标签字号", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_cbar_label_fontsize = create_styled_spinbox(
            parent=center_panel, min_value=6, max_value=20, default_value=10)
        cbar_label_fontsize_layout.addWidget(self.spatial_targetgene_bubble_cbar_label_fontsize)
        center_layout.addLayout(cbar_label_fontsize_layout)
        center_layout.addSpacing(5)

        label_spacing_layout = QHBoxLayout()
        label_spacing_layout.addWidget(create_styled_label(
            "图例行间距", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_label_spacing = create_styled_spinbox(
            parent=center_panel, min_value=10, max_value=50, default_value=25)
        label_spacing_layout.addWidget(self.spatial_targetgene_bubble_label_spacing)
        center_layout.addLayout(label_spacing_layout)
        center_layout.addSpacing(5)

        main_right_ratio_layout = QHBoxLayout()
        main_right_ratio_layout.addWidget(create_styled_label(
            "主图右边界", font_size=10, bold=False, parent=center_panel))
        self.spatial_targetgene_bubble_main_right_ratio = create_styled_spinbox(
            parent=center_panel, min_value=50, max_value=90, default_value=65)
        main_right_ratio_layout.addWidget(self.spatial_targetgene_bubble_main_right_ratio)
        center_layout.addLayout(main_right_ratio_layout)
        center_layout.addSpacing(5)

        center_layout.addStretch()
        return center_panel

    # ------------------------------------------------------------------
    # 右栏（200）：导出选项 —— 逐行照抄单细胞 `:384-441`
    # ------------------------------------------------------------------
    def _create_export_panel(self, parent):
        """右栏（fixed_width=200）：导出尺寸（9×7）+ 5 个导出按钮

        ★ 只建按钮；`QFileDialog` 选路径、落盘、重画全归 W2/W3b（§2.7）。
        """
        export_panel, export_layout = create_styled_panel(parent=parent, fixed_width=200)

        export_layout.addWidget(create_styled_label(
            "导出选项", font_size=12, bold=True, parent=export_panel))
        export_layout.addSpacing(8)

        export_size_frame, export_size_layout = create_styled_panel(parent=export_panel)
        export_size_layout.addWidget(create_styled_label(
            "导出尺寸", font_size=10, bold=False, parent=export_size_frame))

        width_row = QHBoxLayout()
        width_row.addSpacing(5)
        width_row.addWidget(create_styled_label(
            "宽度:", font_size=10, bold=False, parent=export_size_frame))
        self.spatial_targetgene_bubble_export_width = create_styled_spinbox(
            parent=export_size_frame, min_value=1, max_value=100, default_value=9)
        width_row.addWidget(self.spatial_targetgene_bubble_export_width)
        width_row.addStretch()
        export_size_layout.addLayout(width_row)

        height_row = QHBoxLayout()
        height_row.addSpacing(5)
        height_row.addWidget(create_styled_label(
            "高度:", font_size=10, bold=False, parent=export_size_frame))
        self.spatial_targetgene_bubble_export_height = create_styled_spinbox(
            parent=export_size_frame, min_value=1, max_value=100, default_value=7)
        height_row.addWidget(self.spatial_targetgene_bubble_export_height)
        height_row.addStretch()
        export_size_layout.addLayout(height_row)

        export_layout.addWidget(export_size_frame)
        export_layout.addSpacing(8)

        self.btn_export_png = create_styled_button(
            "导出PNG", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_png)

        self.btn_export_pdf = create_styled_button(
            "导出PDF", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_pdf)

        self.btn_export_svg = create_styled_button(
            "导出SVG", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_svg)

        self.btn_export_eps = create_styled_button(
            "导出EPS", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_eps)

        self.btn_export_csv = create_styled_button(
            "导出CSV", font_size=10, parent=export_panel, button_type='export')
        export_layout.addWidget(self.btn_export_csv)

        export_layout.addStretch()
        return export_panel

    # ------------------------------------------------------------------
    # 出图区：**单页签**（页签名 = 页标题；图贴 `..._image_label`）
    # ------------------------------------------------------------------
    def _create_plot_panel(self, parent):
        """出图区：单页签 `QTabWidget` + `create_styled_image_tab` 的 `ZoomableImageLabel`"""
        plot_panel = QWidget(parent)
        plot_layout = QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        self.spatial_targetgene_bubble_plot_tabs = create_styled_tab_widget(parent=plot_panel)

        _, self.spatial_targetgene_bubble_image_label = create_styled_image_tab(
            self.spatial_targetgene_bubble_plot_tabs, "自定义气泡图")

        # ★ `create_styled_image_tab` 给 label 的**硬最小**是 400×300（为整页图集设计的）；
        #   本页样本列(260)+三栏(280/280/200)之后，1600×900 下出图区不足 400 宽
        #   ⇒ 给本页显示 label 一个更合适的地板 240×180（图本身可滚轮缩放/拖动）。
        #   ★ 与已解离的小提琴页 `ui_layout_spatial_violin.py` 同一处置，三栏与样本列**一列都没缩**。
        self.spatial_targetgene_bubble_image_label.setMinimumSize(240, 180)

        plot_layout.addWidget(self.spatial_targetgene_bubble_plot_tabs)
        return plot_panel

    # ------------------------------------------------------------------
    def create_page(self):
        """创建「自定义气泡图」页面（★ 只建控件；不读数据、不写盘、不连信号）"""
        self.spatial_targetgene_bubble_page = QWidget(self.parent)
        self.spatial_targetgene_bubble_page.setObjectName("spatial_targetgene_bubble_page")

        styles = get_mod_styles()
        paths = get_mod_paths()

        # ========== 1. 背景层 ==========
        bg_label = QLabel(self.spatial_targetgene_bubble_page)
        bg_label.setObjectName("spatial_targetgene_bubble_bg")
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
        overlay = QWidget(self.spatial_targetgene_bubble_page)
        overlay.setObjectName("spatial_targetgene_bubble_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== 3. 顶栏：返回 / 标题(32pt) / 音乐控件 ==========
        top_layout = QHBoxLayout()

        self.btn_back_bubble = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_bubble)

        title_label = QLabel("自定义气泡图")
        title_label.setObjectName("spatial_targetgene_bubble_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # ★ 音乐控件：借用 `gui_styles` 已持有的 mod 单例（见模块头「偏差 1」）
        mod_instance = gui_styles.global_mod_manager.get_current_mod()
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(
            self.spatial_targetgene_bubble_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub')

        music_container_x = styles.get('music_container_x', 0.85)
        music_container_y = styles.get('music_container_y', 15)
        if isinstance(music_container_x, float):
            music_container_x = int(self.screen_width * music_container_x)
        music_container.move(music_container_x, music_container_y)

        top_layout.addWidget(music_container)

        top_layout.setStretch(0, 1)
        top_layout.setStretch(1, 3)
        top_layout.setStretch(2, 1)
        layout.addLayout(top_layout)

        # ========== 4. 日志（QTextEdit，read_only，高 80；内容全归 W2/W3b）==========
        self.spatial_targetgene_bubble_log = create_styled_text_edit(
            read_only=True, variant='sub')
        self.spatial_targetgene_bubble_log.setMaximumHeight(80)
        layout.addWidget(self.spatial_targetgene_bubble_log)

        # ========== 5. 主体：样本列(260) + 左(280)/中(280)/右(200) + 出图区 ==========
        main_layout = QHBoxLayout()
        main_layout.setSpacing(12)

        # 样本列：固定宽 260（与差异页/表达页/小提琴页一致，不缩控件）
        self.sample_panel, sample_layout = create_styled_panel(
            parent=self.spatial_targetgene_bubble_page, fixed_width=260)
        sample_layout.setContentsMargins(8, 8, 8, 8)
        self._create_sample_panel(self.sample_panel, sample_layout)
        main_layout.addWidget(self.sample_panel)

        # 左栏：批量基因 / X轴主注释 / Y轴主注释 / 筛选1 / 筛选2 / 筛选并绘图
        main_layout.addWidget(self._create_left_panel(self.spatial_targetgene_bubble_page))

        # 中栏：参数调整
        main_layout.addWidget(self._create_center_panel(self.spatial_targetgene_bubble_page))

        # 右栏：导出选项
        main_layout.addWidget(self._create_export_panel(self.spatial_targetgene_bubble_page))

        # 出图区（可伸缩）
        main_layout.addWidget(self._create_plot_panel(self.spatial_targetgene_bubble_page), 1)

        layout.addLayout(main_layout)

        # ★ 初始化完成后立即应用样式（与单细胞 `:455` 一致）
        self.update_styles()

        # ★ 供 page_intersect 取根控件（`attr_name='spatial_targetgene_bubble_page'` 逐字）
        return self.spatial_targetgene_bubble_page


__all__ = ['SpatialTargetgeneBubblePageUI']
