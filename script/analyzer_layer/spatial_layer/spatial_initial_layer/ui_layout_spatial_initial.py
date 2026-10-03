# -*- coding: utf-8 -*-
"""
空转「总体概览」页面UI布局脚本 - 只负责创建控件、规划窗口布局、设置样式尺寸
完全不写按钮点击、触发逻辑

布局：左「样本多选 + 快捷选择」+ 右「24 个图型页签（可折行，每页 1 张图）」

## v4（用户 2026-09-20）拆页
原「初步分析」页把两个大类塞在一个 `QStackedWidget` 里；现按用户拍板拆成两个独立子页：
  · **本页** = 总体概览（`spatial_initial_page`）：图集页签 + 运行/刷新 + 一键导出 + 日志；
  · 表达量分析 = 新页 `ui_layout_spatial_expression.py`（基因输入/结果页签已整体搬走）。
⇒ 本文件**不再有** `content_stack` / `nav_btn_overview` / `nav_btn_expression` / 任何 `gene_*` 控件。

★ 硬约束（协调者冻结）：本文件**任何地方都不读数据** ——
  不读 manifest/csv/json、不扫目录、不建 QPixmap（背景图除外，与主页同款）、
  不 import/实例化 SpatialDataManager / SpatialReviewAnalysis。
  样本列表与图集页签都只建**静态结构**，内容由 bind 填。
★ 接口与审查页同形：`figure_views` / `figure_notes` / `figure_type_order`
  （都是**平铺一层**，key = figure_type），便于 W2 两页复用同一套填充逻辑。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_panel, create_styled_label,
    create_styled_list_widget, create_styled_text_edit,
    create_wrapping_tab_strip, create_styled_image_tab,
    create_navigation_panel, create_navigation_button
)
from script.mods_layer.mod_manager import global_mod_manager


class SpatialInitialPageUI:
    """初步分析页面布局类（只建控件）"""

    # ★ 24 个图型 = 布局常量（不是数据），顺序 = manifest order。
    #   依据 OUTPUT/GSE237183/_figure_manifest.csv 实测 23 个 figure_type；
    #   **第 24 项** = M4 Phase 3 新增「无点成图」（契约 §15.5，路径
    #   `09_RegionOverride/SpatialNoSpots_<样本>.png`，由 W2 填图）。
    #   ⚠ 若将来 W3 新增图型，需在此表加一行（显式维护；func 会把"多出来的"报给 bind 打日志）。
    INITIAL_FIGURE_TYPES = [
        ("load_overview", "载入总览"),
        ("filter_overview", "过滤总览"),
        ("qc_violin", "QC 小提琴图"),
        ("qc_histogram", "QC 直方图"),
        ("qc_spatial", "QC 空间图"),
        ("pca_elbow", "PCA 肘图"),
        ("umap_sample_cluster", "样本×聚类 UMAP"),
        ("cluster_spatial", "聚类空间分布"),
        ("load_per_sample", "逐样本 nCount 概览"),
        ("persample_umap", "逐样本 UMAP"),
        ("persample_spatial_cluster", "逐样本空间聚类"),
        ("persample_gene_spatial", "逐样本基因空间图"),
        ("celltype_umap_persample", "逐样本 UMAP（细胞类型）"),
        ("celltype_spatial_persample", "逐样本空间图（细胞类型）"),
        ("gene_spatial", "基因空间表达"),
        ("gene_panel", "基因组合面板"),
        ("marker_dotplot", "Marker 点图"),
        ("marker_heatmap", "Marker 热图"),
        ("celltype_umap", "细胞类型 UMAP"),
        ("celltype_spatial", "细胞类型空间图"),
        ("score_umap", "评分 UMAP"),
        ("score_spatial", "评分空间图"),
        ("score_heatmap", "评分热图"),
        # ★ 第 24 项（M4 Phase 3 §15.5；**只追加，别动上面 23 项的顺序与文案**）
        ("celltype_spatial_nospot", "逐样本空间图（细胞类型·无点）"),
    ]

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
        bg_label = self.spatial_initial_page.findChild(QLabel, "spatial_initial_bg")
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
        export_names = ('btn_export_all_png', 'btn_export_all_pdf')
        export_buttons = [getattr(self, n) for n in export_names if hasattr(self, n)]
        for child in self.spatial_initial_page.findChildren(QPushButton):
            if child in nav_buttons:
                continue
            # 折行页签条内部的按钮是"标签式"，不要被普通按钮 QSS 覆盖
            if self.initial_tabs is not None and self.initial_tabs.isAncestorOf(child):
                continue
            # 2 个「一键批量导出」按钮用 export 专用样式，别被普通按钮 QSS 覆盖
            # （照 bulk_expr_layer/ui_layout_bulk_expr.py:59-62 的做法，在下面显式刷）
            if child in export_buttons or child.objectName() == 'styled_btn_export':
                continue
            child.setStyleSheet(button_style)

        # ★ 2 个导出按钮的样式刷新（房规：切模组/重刷时保持一致）
        export_style = get_stylesheet_for_widget('export_button')
        for btn in export_buttons:
            btn.setStyleSheet(export_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_initial_page.findChildren(QLabel):
            if child.objectName() == "spatial_initial_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)

        title_label = self.spatial_initial_page.findChild(QLabel, "spatial_initial_title")
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
        for child in self.spatial_initial_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    # ------------------------------------------------------------------
    def _create_sample_panel(self, parent, layout):
        """左栏：样本多选列表 + 三个快捷按钮 + 计数（★ 默认全不选，列表为空）"""
        title = create_styled_label("样本选择", font_size=12, parent=parent)
        layout.addWidget(title)

        # ★ 返回单个 widget（gui_styles.py:928-951）；multi_selection=True → QListWidget.MultiSelection
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

        # ★ 左栏只留样本选择（本页与「表达量分析」页各自持有一份，同名同形）
        layout.addStretch()

    def _create_export_buttons(self, parent):
        """建一对「一键批量导出」按钮（PNG / PDF），返回 `(png_btn, pdf_btn)`。

        用户第 5 轮原话：「弄简单粗暴些一键批量导出，可选路径…导出一键所有 PDF，
        或者导出一键所有 png，就别一个一个选了导出了」
        ★ 只建控件：**不读数据、不写文件、不弹对话框**（对话框与复制逻辑归 W2 的 bind）。
        ★ 用 `button_type='export'`（objectName = `styled_btn_export`），
          与 bulk_expr 的 `get_stylesheet_for_widget('export_button')` 同一套样式。
        ★ v4：表达量页搬去独立文件后，本方法只服务**概览页**的 `btn_export_all_png/pdf`
          （新页 `ui_layout_spatial_expression.py` 里有它自己的一份，互不影响）。
        """
        png_btn = create_styled_button(
            "导出全部PNG", font_size=10, parent=parent, button_type='export')
        pdf_btn = create_styled_button(
            "导出全部PDF", font_size=10, parent=parent, button_type='export')
        for btn in (png_btn, pdf_btn):
            btn.setFixedHeight(34)
        return png_btn, pdf_btn

    def _create_figure_panel(self, parent, layout):
        """右栏：24 个图型页签（每个页签恰好 1 张图 + 1 行说明）

        - 图型清单 `INITIAL_FIGURE_TYPES` 是**布局常量**（24 个），建空结构**不读文件**。
        - 页签容器用 `WrappingTabStrip`（Qt5 的 QTabBar 不折行，见 gui_styles 内注释）。
        - bind 只负责 setPixmap / setText / setVisible / setTabVisible，**不建控件**。
        """
        self.figure_views = {}
        self.figure_notes = {}
        self.figure_type_order = [ft for ft, _label in self.INITIAL_FIGURE_TYPES]

        self.initial_tabs = create_wrapping_tab_strip(parent=parent)

        for figure_type, figure_label in self.INITIAL_FIGURE_TYPES:
            # ★ 老样式（用户第 4 轮实测要求）：页内图片区一律用 `create_styled_image_tab`
            #   —— 它是"老样式图片页"的唯一真相源（objectName=styled_image_label、
            #   get_stylesheet_for_widget('image_label')、Expanding 尺寸策略）。
            #   ★ 它内部已经 `addTab(page, title)`，**不要再自己 addTab 一次**。
            page, image_label = create_styled_image_tab(
                self.initial_tabs, figure_label,
                default_text="该图尚未生成")
            image_label.setAlignment(Qt.AlignCenter)

            note_label = create_styled_label(
                figure_label, font_size=10, bold=False, parent=page)
            note_label.setAlignment(Qt.AlignCenter)
            page.layout().addWidget(note_label)

            self.figure_views[figure_type] = image_label
            self.figure_notes[figure_type] = note_label

        layout.addWidget(self.initial_tabs, stretch=1)

        self.initial_empty_hint = create_styled_label(
            "尚未载入图集，请先在主页「加载数据」后再运行出图。",
            font_size=10, bold=False, parent=parent)
        self.initial_empty_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.initial_empty_hint)

    def _create_action_panel(self, parent, layout):
        """概览页底部：运行/刷新 + 一键批量导出 + 日志"""
        row = QHBoxLayout()
        self.btn_initial_run = create_styled_button(
            "运行 / 刷新图集", font_size=11, parent=parent, button_type='run')
        row.addWidget(self.btn_initial_run)
        self.btn_initial_from_review = create_styled_button(
            "前往审查模式", font_size=11, parent=parent, button_type='normal')
        row.addWidget(self.btn_initial_from_review)
        layout.addLayout(row)

        # ★ 概览页的「一键批量导出」一对按钮（并排一行）
        self.btn_export_all_png, self.btn_export_all_pdf = self._create_export_buttons(parent)
        export_row = QHBoxLayout()
        export_row.addWidget(self.btn_export_all_png)
        export_row.addWidget(self.btn_export_all_pdf)
        layout.addLayout(export_row)

        self.initial_log_text = create_styled_text_edit(read_only=True)
        self.initial_log_text.setMaximumHeight(90)
        self.initial_log_text.setFont(get_font_for_widget('label', 10))
        self.initial_log_text.setText("等待操作...")
        layout.addWidget(self.initial_log_text)

    # ------------------------------------------------------------------
    def create_page(self):
        self.spatial_initial_page = QWidget(self.parent)
        self.initial_tabs = None          # 先占位，供 update_styles 的守卫使用

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.spatial_initial_page)
        bg_label.setObjectName("spatial_initial_bg")
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

        overlay = QWidget(self.spatial_initial_page)
        overlay.setObjectName("spatial_initial_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        # ⛔ v4（用户 2026-09-20）：本页**只剩一个内容**（总体概览）⇒ 左侧不再需要
        #   「分析类别」小标题与 `nav_btn_overview` / `nav_btn_expression` 两个大类按钮；
        #   表达量分析已独立成页（`ui_layout_spatial_expression.py`），由 hub 的卡片进入。

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

        title_label = QLabel("总体概览")
        title_label.setObjectName("spatial_initial_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)

        mod_instance = global_mod_manager.get_current_mod()
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.spatial_initial_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub')
        title_row_layout.addWidget(music_container)

        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)
        top_bar_layout.addLayout(title_row_layout)
        content_layout.addWidget(top_bar)

        # ===== 未审样本提示条（默认隐藏；bind 判定后显示，软阻断不禁止使用）=====
        self.unreviewed_notice_panel, unreviewed_layout = create_styled_panel(parent=content_panel)
        unreviewed_layout.setContentsMargins(10, 6, 10, 6)
        self.unreviewed_notice_label = create_styled_label(
            "", font_size=11, parent=self.unreviewed_notice_panel)
        unreviewed_layout.addWidget(self.unreviewed_notice_label)
        self.unreviewed_notice_panel.setVisible(False)
        content_layout.addWidget(self.unreviewed_notice_panel)

        # ===== 主体：[ 左栏样本面板(260) | 右栏：图集页签 + 底部操作条 ] =====
        body = QWidget(content_panel)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 10, 20, 20)
        body_layout.setSpacing(12)

        left_panel, left_layout = create_styled_panel(parent=body, fixed_width=260)
        left_layout.setContentsMargins(8, 8, 8, 8)
        self._create_sample_panel(left_panel, left_layout)
        body_layout.addWidget(left_panel)

        # ★ v4：本页只剩一个内容 ⇒ **不再需要 `content_stack`**，原来是「页 0」的内容
        #   （图集页签 + 操作条）直接放进右栏，边距/间距保持原观感（2,2,2,2 + 6）。
        right_panel, right_layout = create_styled_panel(parent=body)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(6)
        self._create_figure_panel(right_panel, right_layout)
        self._create_action_panel(right_panel, right_layout)

        body_layout.addWidget(right_panel, stretch=1)

        content_layout.addWidget(body, stretch=1)
        main_layout.addWidget(content_panel)

        return self.spatial_initial_page


__all__ = ['SpatialInitialPageUI']
