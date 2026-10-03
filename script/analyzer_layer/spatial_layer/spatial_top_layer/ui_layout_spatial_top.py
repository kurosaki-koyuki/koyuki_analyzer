# -*- coding: utf-8 -*-
"""
空转分析顶层导航界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/面板、设置样式尺寸
完全不写按钮点击、触发逻辑

采用左侧导航栏+右侧内容面板的布局风格（逐行对齐 bulk_top_layer/ui_layout_bulk_top.py）
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_panel, create_styled_text_edit,
    create_styled_table,
    create_navigation_panel, create_navigation_button, create_navigation_divider, create_navigation_header,
    create_styled_image_button
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


def _page_pic(name):
    """页面示例图：存在就用，否则退回 NULL.png（传统页对无示例图的分析就是这么做的）

    ★ `create_styled_image_button` 在**路径不存在**时会显示「图片加载失败」占位文字
      ⇒ 必须显式传一个存在的路径；本页四个卡片现在都还没真图 ⇒ 全部退回 NULL.png，
      将来放了真图（同名文件）即自动生效。
    """
    p = os.path.join(APPDATA_PATH, 'elements', 'page_pics', name)
    if os.path.exists(p):
        return p
    return os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'NULL.png')


class SpatialTopPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        """切换模组时重载背景图"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.spatial_top_page.findChild(QLabel, "spatial_top_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """刷新样式：只刷普通按钮/标签/标题配色/面板底色，必须跳过导航按钮与背景标签"""
        styles = get_mod_styles()

        button_style = get_stylesheet_for_widget('button')
        for child in self.spatial_top_page.findChildren(QPushButton):
            # 导航按钮自带标签式样式，不能被普通按钮 QSS 覆盖
            nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
            if child in nav_buttons:
                continue
            child.setStyleSheet(button_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_top_page.findChildren(QLabel):
            if child.objectName() == "spatial_top_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)

        title_label = self.spatial_top_page.findChild(QLabel, "spatial_top_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.spatial_top_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    def _create_data_load_panel(self, parent):
        """创建数据加载面板内容 - 数据集扫描/选择/加载 + 只读样本清单

        控件顺序与间距逐行对齐 bulk_top_layer/ui_layout_bulk_top.py:82-132，
        只换控件名与文案；空转比 bulk 多一个「样本清单」表格（M1 只展示不可多选）。
        ★ 本方法只建空控件，绝不读数据、绝不碰文件系统（create_page 会在每次启动时被调用）。
        """
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)

        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        # 「数据加载」类面板用 subtitle_color（不是 mutant_color，更不是不存在的 sub_text_color）
        subtitle_color = styles.get('subtitle_color', '#87CEEB')

        title_label = QLabel("数据加载")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))

        status_title = QLabel("运行状态")
        status_title.setFont(QFont(subtitle_font, 14, QFont.Bold))
        status_title.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        status_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_title)

        self.spatial_status_text = create_styled_text_edit(read_only=True)
        self.spatial_status_text.setMaximumHeight(100)
        self.spatial_status_text.setFont(get_font_for_widget('label', 10))
        self.spatial_status_text.setText("等待数据加载...")
        layout.addWidget(self.spatial_status_text)

        layout.addSpacing(30)

        self.btn_spatial_select_path = create_styled_button(
            "扫描数据路径", font_size=14, button_type='import', parent=panel)
        layout.addWidget(self.btn_spatial_select_path, alignment=Qt.AlignCenter)

        layout.addSpacing(20)

        self.spatial_dataset_combo = create_styled_combo_box(parent=panel)
        self.spatial_dataset_combo.setMinimumWidth(300)
        layout.addWidget(self.spatial_dataset_combo, alignment=Qt.AlignCenter)

        layout.addSpacing(20)

        self.btn_spatial_load = create_styled_button(
            "加载数据集", font_size=14, button_type='run', parent=panel)
        layout.addWidget(self.btn_spatial_load, alignment=Qt.AlignCenter)

        layout.addSpacing(30)

        sample_title = QLabel("样本清单")
        sample_title.setFont(QFont(subtitle_font, 14, QFont.Bold))
        sample_title.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        sample_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(sample_title)

        # 只读样本清单：NonEditableTable（create_styled_table → gui_styles.py:1067/951）
        # M1 只展示、选中无任何行为（故本层不调用任何选择模式 API）；
        # M2 接「样本选择」时，由 bind 层显式设置选择模式（如 MultiSelection / NoSelection）。
        # 数据填充由 W2 的 func 层负责（照 ui_func_*.fill_list_widget 一族）。
        self.spatial_sample_list = create_styled_table(parent=panel)
        self.spatial_sample_list.setMinimumHeight(180)
        layout.addWidget(self.spatial_sample_list)

        layout.addStretch()

        return panel

    def _create_card_panel(self, parent, title, cards):
        """一个分类面板：标题 + 一行**图片卡片**（照抄传统 hub 的手法）

        参考 `scRNAseq_top_layer/ui_layout_scRNAseq_top.py:164-207`：
        `create_styled_panel` + 一行 `QHBoxLayout` 放若干 `create_styled_image_button`。

        Args:
            title: 面板标题（分类名）
            cards: `[(控件属性名, 卡片文案, 示例图文件名), ...]`
                   ★ 控件名由调用处**冻结**，这里只负责建控件与摆位；
                     **不连任何点击逻辑**（跳转归 W2 的 bind）。
        """
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)

        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        subtitle_color = styles.get('subtitle_color', '#87CEEB')

        title_label = QLabel(title)
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(30)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(15)
        row_layout.setContentsMargins(20, 0, 20, 0)
        for attr_name, text, pic_name in cards:
            btn = create_styled_image_button(text, _page_pic(pic_name), parent=panel)
            setattr(self, attr_name, btn)
            row_layout.addWidget(btn, alignment=Qt.AlignCenter)
        layout.addLayout(row_layout)

        layout.addStretch()

        return panel

    def _create_overview_review_panel(self, parent):
        """「概览审查类」：总览 / 审查 / **绘制区域** 三张卡片（同一行）

        ★ v4（用户 2026-09-20）：取消「绘图模式」分类，`btn_card_region`（绘制区域）
          搬到这里，与另两张卡**同一行**。
        ★ 2026-09-25 用户纠正图名：总览卡的示例图用 **`spatial_initial_layer.png`**
          （= 该层**自己的目录名**；此前写的是 `spatial_overview_layer.png`，与真实资产
          对不上 ⇒ 一直退化成 `NULL.png` 占位图）。图名与层目录名一致是本页统一口径：
          表达量 = `spatial_expression_layer.png` 同理。
          另三张（审查 / 绘制区域 / 差异分析）仍无真图 ⇒ 继续走 `_page_pic()` 的
          `NULL.png` 回退；**把同名文件放进同一目录即自动生效，无需改码**。
        """
        return self._create_card_panel(parent, "概览审查类", [
            ('btn_card_overview', "总览", 'spatial_initial_layer.png'),
            ('btn_card_review', "审查", 'spatial_review_layer.png'),
            ('btn_card_region', "绘制区域", 'spatial_region_layer.png'),
        ])

    def _create_initial_analysis_panel(self, parent):
        """「初步分析类」：**一行 4 张卡**（★ v11 顺序冻结，规格 `_d_spec_v11_split_and_bubble.md` §2.2）

        卡片顺序 1:1 对应单细胞「基础表达类」(`ui_layout_scRNAseq_top.py:164-207`) 的
        `btn_initial_analysis` / `btn_violin_plot` / `btn_bubble_plot`（自定义）/
        `btn_gene_bubble_plot`（基因集）—— 同为 4 卡横排，布局宽度已被单细胞验证：
          1. `btn_card_expression`        表达量分析    `spatial_expression_layer.png`
          2. `btn_card_violin`            小提琴图      `spatial_violin_layer.png`
          3. `btn_card_targetgene_bubble` 自定义气泡图  `spatial_targetgene_bubble_layer.png`
          4. `btn_card_genelist_bubble`   基因集气泡图  `spatial_genelist_bubble_layer.png`
        ★ 图片名一律 = **层目录名** + `.png`，缺失仍走 `_page_pic()` 的 `NULL.png` 回退（I10）
          —— 用户把同名 PNG 丢进 `appdata/elements/page_pics/` 即自动生效，无需改码。
        ★ 只建控件：**不连任何点击逻辑**（3 条新跳转归 W2 的 `ui_bind_spatial_top.py`）。
        """
        return self._create_card_panel(parent, "初步分析类", [
            ('btn_card_expression', "表达量分析", 'spatial_expression_layer.png'),
            ('btn_card_violin', "小提琴图", 'spatial_violin_layer.png'),
            ('btn_card_targetgene_bubble', "自定义气泡图", 'spatial_targetgene_bubble_layer.png'),
            ('btn_card_genelist_bubble', "基因集气泡图", 'spatial_genelist_bubble_layer.png'),
        ])

    def _create_genelist_panel(self, parent):
        """「基因列表类」：差异分析 卡片（★ 第 4 分类，规格 `_d_spec_spatial_diff.md` §2 A2）

        卡片名 `btn_card_spatial_diff` / 文案「差异分析」/ 图 `spatial_diff_layer.png`
        逐字照规格冻结（文案与单细胞 `btn_diff_analysis` 一致；分类名由面板标题表达）。
        ★ 图片仍走 `_page_pic()`（缺失自动回退 NULL.png），否则
          `test_hub_card_images_not_placeholder` 会红。
        ★ 只建控件：**不连任何点击逻辑**（跳转归 W2 的 `ui_bind_spatial_top.py`）。
        """
        return self._create_card_panel(parent, "基因列表类", [
            ('btn_card_spatial_diff', "差异分析", 'spatial_diff_layer.png'),
        ])

    # 面板名 → 对应左侧导航按钮的属性名
    #   ★ 分类按钮叫 `nav_btn_cat_*`，而面板键叫 `overview_review` / `initial_analysis`
    #     ⇒ 两者不是简单拼接，`show_panel()` 必须靠这张表来勾选（别改成字符串拼接）。
    #   ★ v4：`'draw'` 分类已取消，本表随之删掉那一条。
    PANEL_NAV_BUTTONS = {
        'data': 'nav_btn_data',
        'overview_review': 'nav_btn_cat_overview',
        'initial_analysis': 'nav_btn_cat_initial',
        # ★ 规格 `_d_spec_spatial_diff.md` §2 A3（2026-09-24）：第 4 分类「基因列表类」
        #   （属性名必须与 A1 里建的 `nav_btn_cat_genelist` **逐字一致**；
        #    `show_panel()` 靠这张表勾选，本表之外不动 `show_panel`）
        'genelist': 'nav_btn_cat_genelist',
    }

    def show_panel(self, panel_name):
        """显示指定面板，隐藏其他面板（带淡入效果）"""
        for name, panel in self.panels.items():
            if name == panel_name:
                panel.show()
                panel.raise_()
                self._fade_in(panel)
            else:
                panel.hide()

        want = self.PANEL_NAV_BUTTONS.get(panel_name, f'nav_btn_{panel_name}')
        for attr in dir(self):
            if attr.startswith('nav_btn_'):
                btn = getattr(self, attr)
                btn.setChecked(attr == want)

    def _fade_in(self, widget):
        """淡入动画效果"""
        widget.setWindowOpacity(1)
        widget.show()

    def create_page(self):
        self.spatial_top_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.spatial_top_page)
        bg_label.setObjectName("spatial_top_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.spatial_top_page)
        overlay.setObjectName("spatial_top_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回主界面", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addSpacing(10)

        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))

        nav_layout.addSpacing(10)

        nav_layout.addWidget(create_navigation_header("数据管理", font_size=11, parent=nav_panel))

        self.nav_btn_data = create_navigation_button("加载数据", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_data)

        nav_layout.addSpacing(10)

        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))

        nav_layout.addSpacing(10)

        # ★ v4（用户 2026-09-20）：传统 hub 样式 —— **一个小标题 + 并列分类按钮**
        #   （原来是每个分类各带一个小标题；现在只留「分析方法」一个）
        nav_layout.addWidget(create_navigation_header("分析方法", font_size=11, parent=nav_panel))

        self.nav_btn_cat_overview = create_navigation_button("概览审查类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_cat_overview)

        self.nav_btn_cat_initial = create_navigation_button("初步分析类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_cat_initial)

        # ★ 规格 `_d_spec_spatial_diff.md` §2 A1（2026-09-24）：第 4 分类「基因列表类」
        #   （单细胞的差异分析就在「基因列表类」里；卡片见 `_create_genelist_panel`）
        self.nav_btn_cat_genelist = create_navigation_button("基因列表类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_cat_genelist)

        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)

        top_bar, top_bar_layout = create_styled_panel(parent=content_panel)
        top_bar_layout.setContentsMargins(15, 8, 15, 8)

        title_row_layout = QHBoxLayout()

        title_label = QLabel("空转分析")
        title_label.setObjectName("spatial_top_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.spatial_top_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')

        title_row_layout.addWidget(music_container)

        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)

        top_bar_layout.addLayout(title_row_layout)

        content_layout.addWidget(top_bar)

        panels_container = QWidget(content_panel)
        panels_layout = QVBoxLayout(panels_container)
        panels_layout.setContentsMargins(20, 20, 20, 20)

        self.data_panel = self._create_data_load_panel(panels_container)

        # ---- 「分类 + 图片卡片」面板（卡片都只建控件；跳转由 W2 的 bind 负责）----
        #   ★ v4：原「绘图模式」分类取消，`btn_card_region` 已并入 overview_review 面板。
        #   ★ v7（2026-09-24）：新增第 4 分类「基因列表类」（规格 `_d_spec_spatial_diff.md` §2）。
        self.overview_review_panel = self._create_overview_review_panel(panels_container)
        self.initial_analysis_panel = self._create_initial_analysis_panel(panels_container)
        # ★ 规格 `_d_spec_spatial_diff.md` §2 A4（2026-09-24）：第 4 分类面板
        self.genelist_panel = self._create_genelist_panel(panels_container)

        self.panels = {
            'data': self.data_panel,
            'overview_review': self.overview_review_panel,
            'initial_analysis': self.initial_analysis_panel,
            'genelist': self.genelist_panel,
        }

        panels_layout.addWidget(self.data_panel)
        panels_layout.addWidget(self.overview_review_panel)
        panels_layout.addWidget(self.initial_analysis_panel)
        panels_layout.addWidget(self.genelist_panel)

        content_layout.addWidget(panels_container)

        main_layout.addWidget(content_panel)

        self.show_panel('data')

        self.update_styles()

        return self.spatial_top_page


__all__ = ['SpatialTopPageUI']
