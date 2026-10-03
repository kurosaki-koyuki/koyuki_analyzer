# -*- coding: utf-8 -*-
"""
空转审查模式页面UI布局脚本 - 只负责创建控件、规划窗口布局、设置样式尺寸
完全不写按钮点击、触发逻辑

布局：左「样本列表」+ 中「图类型页签 + 大图」+ 右「打分」
★ 硬约束（协调者冻结）：本文件**任何地方都不读数据** ——
  不读 manifest/csv/json、不扫目录、不建 QPixmap（背景图除外，与主页同款）、
  不 import/实例化 SpatialDataManager / SpatialReviewAnalysis。
  图类型页签只建**空容器**，由 bind 在进入页面时动态填充。
  因此"没有数据"时本页是一个可正常显示的空状态，而不是报错页。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_panel, create_styled_label,
    create_styled_list_widget, create_styled_group_box, create_styled_text_edit,
    create_navigation_panel, create_navigation_button, create_navigation_divider,
    create_navigation_header,
    create_zoomable_image_label, create_wrapping_tab_strip, create_styled_image_tab,
    create_styled_star_rating, create_styled_star_rating_row
)
from script.mods_layer.mod_manager import global_mod_manager


class SpatialReviewPageUI:
    """审查模式页面布局类（只建控件）"""

    # 操作日志出口的固定高度（L3）——别被布局拉高
    H_LOG = 110

    # 逐格评分的 5 个维度（只作记录，不决定颜色）——供 bind/func 共用，避免两处各写一份
    DIMENSIONS = [
        ("structure", "组织结构保留"),
        ("noise", "噪声水平"),
        ("cluster", "聚类可分性"),
        ("color", "配色与可读性"),
        ("usability", "总体可用性"),
    ]

    # 图类型 id → 中文标签（6 个图集逐样本图型 + 1 个原始组织切片，协调者冻结；
    # id 以 W2 的 list_review_figures 为准）
    #   ★ `tissue_raw` 必须**放在最后**：bind 用 `tabs.currentIndex()` 索引
    #     `list_review_figures()['figure_types']`，而 W3 也把它追加在最后 ⇒ 两边同构。
    #     它是**原始数据集里的 H&E（不带 spot）**，不是图集产物（重跑图集也变不出来）。
    FIGURE_TYPE_LABELS = {
        "load_per_sample": "逐样本 nCount 概览",
        "persample_umap": "逐样本 UMAP",
        "persample_spatial_cluster": "逐样本空间聚类",
        "persample_gene_spatial": "逐样本基因空间图",
        "celltype_umap_persample": "逐样本 UMAP（细胞类型）",
        "celltype_spatial_persample": "逐样本空间图（细胞类型）",
        "tissue_raw": "原始组织切片（H&E，无 spot）",
    }

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
        bg_label = self.spatial_review_page.findChild(QLabel, "spatial_review_bg")
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

        ★ 本页的星级控件由工厂自行注册主题（gui_styles._register_theme_widget），
          不在这里遍历重刷，避免把打分控件套成普通控件样式。
        """
        styles = get_mod_styles()

        button_style = get_stylesheet_for_widget('button')
        nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
        for child in self.spatial_review_page.findChildren(QPushButton):
            if child in nav_buttons:
                continue
            # 折行页签条内部的按钮是"标签式"，不要被普通按钮 QSS 覆盖
            if self.figure_tabs is not None and self.figure_tabs.isAncestorOf(child):
                continue
            child.setStyleSheet(button_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_review_page.findChildren(QLabel):
            if child.objectName() == "spatial_review_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)

        title_label = self.spatial_review_page.findChild(QLabel, "spatial_review_title")
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
        for child in self.spatial_review_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        # ★ L3：操作日志出口**显式**随模组刷样式（不能只在构造期设一次）
        log_widget = getattr(self, 'review_log_text', None)
        if log_widget is not None:
            log_widget.setStyleSheet(get_stylesheet_for_widget('text_edit'))
            if log_widget.height() != self.H_LOG:
                log_widget.setFixedHeight(self.H_LOG)

    # ------------------------------------------------------------------
    def _create_sample_panel(self, parent, layout):
        """左栏：样本列表 + 审查进度（只建控件）"""
        title = create_styled_label("样本列表", font_size=12, parent=parent)
        layout.addWidget(title)

        self.review_sample_list = create_styled_list_widget(
            parent=parent, fixed_height=420, multi_selection=False)
        layout.addWidget(self.review_sample_list)

        self.review_progress_label = create_styled_label(
            "尚未载入样本", font_size=10, bold=False, parent=parent)
        layout.addWidget(self.review_progress_label)
        layout.addStretch()

    def _create_figure_panel(self, parent, layout):
        """中栏：★ 布局期直接建 7 个静态图类型页签（每个含可缩放图 + 图注）

        - 图型清单 `FIGURE_TYPE_LABELS` 是**布局常量**（已冻结 7 个 = 6 个图集逐样本型
          + 1 个原始组织切片 `tissue_raw`），建空页签**不读任何文件**。
        - bind 只负责 setPixmap / setText / setVisible，**不建控件**（房style：bind 不建控件）。
        - `figure_empty_hint` 与 `figure_tabs` 的显隐关系由 bind 决定，本层只保证两者都存在。
        """
        # 无数据时的空状态提示（纯静态文案，不读数据）
        self.figure_empty_hint = create_styled_label(
            "尚未载入图集", font_size=11, bold=False, parent=parent)
        self.figure_empty_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.figure_empty_hint)

        # ★ 用折行页签条（Qt5 的 QTabBar 不折行）；6 项自然 1 行，外观与 QTabWidget 几乎一致
        self.figure_tabs = create_wrapping_tab_strip(parent=parent)

        # 每个图类型一个页签：可缩放图控件 + 该图说明标签
        self.figure_views = {}
        self.figure_notes = {}
        # 冻结的显示顺序（bind 遍历用；与页签索引一一对应）
        self.figure_type_order = list(self.FIGURE_TYPE_LABELS.keys())
        for figure_type in self.figure_type_order:
            title = self.FIGURE_TYPE_LABELS[figure_type]
            # ★ 老样式：页内图片区用 `create_styled_image_tab`（"老样式图片页"的唯一真相源：
            #   objectName=styled_image_label、image_label 样式表、Expanding 尺寸策略）。
            #   它内部已 addTab，别再自己 addTab。
            page, image_label = create_styled_image_tab(
                self.figure_tabs, title, default_text="该图类型暂无图片")
            image_label.setAlignment(Qt.AlignCenter)

            note_label = create_styled_label(
                "尚未载入图集", font_size=10, bold=False, parent=page)
            note_label.setAlignment(Qt.AlignCenter)
            page.layout().addWidget(note_label)

            self.figure_views[figure_type] = image_label
            self.figure_notes[figure_type] = note_label

        layout.addWidget(self.figure_tabs, stretch=1)

        self.figure_caption_label = create_styled_label(
            "", font_size=10, bold=False, parent=parent)
        self.figure_caption_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.figure_caption_label)

    def _create_score_panel(self, parent, layout):
        """右栏：样本总分（唯一染色源）+ 逐格 5 维 + 备注 + 底部两按钮"""
        # ---- ① 样本总分：唯一染色源，最醒目（star_size=28）----
        total_panel, total_layout = create_styled_panel(parent=parent)
        total_layout.setContentsMargins(10, 10, 10, 10)

        total_title = create_styled_label("样本总分（决定样本名颜色）", font_size=11, parent=total_panel)
        total_title.setAlignment(Qt.AlignCenter)
        total_layout.addWidget(total_title)

        self.sample_total_stars = create_styled_star_rating(
            parent=total_panel, rating=0, max_stars=5, star_size=28)
        total_layout.addWidget(self.sample_total_stars, alignment=Qt.AlignCenter)

        self.sample_total_value_label = create_styled_label(
            "未打分", font_size=16, parent=total_panel)
        self.sample_total_value_label.setAlignment(Qt.AlignCenter)
        total_layout.addWidget(self.sample_total_value_label)

        # ★ 已按用户要求删除「色块 + 色值文字」两个控件（无效信息）
        layout.addWidget(total_panel)

        # ---- ② 逐格 5 维：只作记录，不决定颜色（star_size=16）----
        # 注意：create_styled_group_box 只返回 QGroupBox（不是元组），需自建布局
        dim_group = create_styled_group_box(
            "本图评分（记录用，不决定颜色）", parent=parent)
        dim_layout = QVBoxLayout(dim_group)
        dim_layout.setContentsMargins(10, 14, 10, 10)
        dim_layout.setSpacing(4)
        self.dimension_stars = {}
        for key, text in self.DIMENSIONS:
            row_widget, star = create_styled_star_rating_row(
                text, parent=dim_group, rating=0, max_stars=5, star_size=16)
            self.dimension_stars[key] = star
            dim_layout.addWidget(row_widget)
        dim_layout.addStretch()
        layout.addWidget(dim_group)

        # ---- ③ 逐格汇总（小字，仅提示）----
        self.dimension_summary_label = create_styled_label(
            "本图未评分", font_size=10, bold=False, parent=parent)
        self.dimension_summary_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.dimension_summary_label)

        # ---- ④ 备注输入框：读写归 bind，本层只建控件 ----
        note_title = create_styled_label("备注", font_size=10, bold=False, parent=parent)
        layout.addWidget(note_title)
        self.sample_note_edit = create_styled_text_edit(parent=parent)
        self.sample_note_edit.setPlaceholderText("备注：悬停样本名时会显示这段文字")
        self.sample_note_edit.setMaximumHeight(80)
        layout.addWidget(self.sample_note_edit)

        # ---- ④b 操作日志出口（清理旧账 L3：`review_log_text`，只读、定高）----
        #   用户此前看不到审查页做了什么（日志只进 stdout）；W2 的
        #   `SpatialReviewFunc.log()` 往这里写。
        log_title = create_styled_label("操作日志", font_size=10, bold=False, parent=parent)
        layout.addWidget(log_title)
        self.review_log_text = create_styled_text_edit(parent=parent, read_only=True)
        self.review_log_text.setFixedHeight(self.H_LOG)
        self.review_log_text.setText("等待操作...")
        layout.addWidget(self.review_log_text)

        # ---- ⑤ 两按钮分两行、撑满该列、贴底（addStretch 顶开）----
        layout.addStretch()
        self.btn_review_save = create_styled_button(
            "保存并下一个", font_size=11, parent=parent, button_type='run')
        layout.addWidget(self.btn_review_save)
        self.btn_review_skip = create_styled_button(
            "跳过", font_size=11, parent=parent, button_type='normal')
        layout.addWidget(self.btn_review_skip)

    # ------------------------------------------------------------------
    def create_page(self):
        self.spatial_review_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.spatial_review_page)
        bg_label.setObjectName("spatial_review_bg")
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

        overlay = QWidget(self.spatial_review_page)
        overlay.setObjectName("spatial_review_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_header("审查模式", font_size=11, parent=nav_panel))

        self.review_nav_hint = create_styled_label(
            "按样本逐格审查，\n给样本总分即可\n为样本名着色。",
            font_size=10, bold=False, parent=nav_panel)
        self.review_nav_hint.setWordWrap(True)
        nav_layout.addWidget(self.review_nav_hint)

        # ⛔ v4（用户 2026-09-20）：本页的「绘制区域」入口控件（`nav_btn_region`）
        #   已删除 —— 「绘制区域」卡片改由主页 hub 的 `overview_review_panel` 承载
        #   （`btn_card_region`）。W2 会同步删掉这里的接线。

        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # ===== 顶部外框 + 标题 + 音乐控制器（与主页同构）=====
        top_bar, top_bar_layout = create_styled_panel(parent=content_panel)
        top_bar_layout.setContentsMargins(15, 8, 15, 8)

        title_row_layout = QHBoxLayout()

        title_label = QLabel("审查模式")
        title_label.setObjectName("spatial_review_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)

        mod_instance = global_mod_manager.get_current_mod()
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.spatial_review_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub')
        title_row_layout.addWidget(music_container)

        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)
        top_bar_layout.addLayout(title_row_layout)
        content_layout.addWidget(top_bar)

        # ===== 图集 id 变化提示条（默认隐藏；bind 判定后显示）=====
        self.atlas_warning_panel, atlas_warning_layout = create_styled_panel(parent=content_panel)
        atlas_warning_layout.setContentsMargins(10, 6, 10, 6)
        self.atlas_warning_label = create_styled_label(
            "⚠ 当前评分对应的是旧图集", font_size=11, parent=self.atlas_warning_panel)
        atlas_warning_layout.addWidget(self.atlas_warning_label)
        warning_btn_row = QHBoxLayout()
        self.btn_keep_old_scores = create_styled_button(
            "按旧评分继续", font_size=11, parent=self.atlas_warning_panel, button_type='normal')
        warning_btn_row.addWidget(self.btn_keep_old_scores)
        self.btn_clear_scores = create_styled_button(
            "清空重审", font_size=11, parent=self.atlas_warning_panel, button_type='normal')
        warning_btn_row.addWidget(self.btn_clear_scores)
        warning_btn_row.addStretch()
        atlas_warning_layout.addLayout(warning_btn_row)
        self.atlas_warning_panel.setVisible(False)   # 默认隐藏，绝不静默沿用/静默清空
        content_layout.addWidget(self.atlas_warning_panel)

        # ===== 三栏主体 =====
        body = QWidget(content_panel)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 10, 20, 20)
        body_layout.setSpacing(12)

        # 左：样本列表（固定宽）
        left_panel, left_layout = create_styled_panel(parent=body, fixed_width=220)
        left_layout.setContentsMargins(8, 8, 8, 8)
        self._create_sample_panel(left_panel, left_layout)
        body_layout.addWidget(left_panel)

        # 中：图类型页签（空容器）+ 大图（自适应，占比最大）
        center_panel, center_layout = create_styled_panel(parent=body)
        center_layout.setContentsMargins(8, 8, 8, 8)
        self._create_figure_panel(center_panel, center_layout)
        body_layout.addWidget(center_panel, stretch=1)

        # 右：打分（固定宽）
        right_panel, right_layout = create_styled_panel(parent=body, fixed_width=260)
        right_layout.setContentsMargins(8, 8, 8, 8)
        self._create_score_panel(right_panel, right_layout)
        body_layout.addWidget(right_panel)

        content_layout.addWidget(body, stretch=1)
        main_layout.addWidget(content_panel)

        return self.spatial_review_page


__all__ = ['SpatialReviewPageUI']
