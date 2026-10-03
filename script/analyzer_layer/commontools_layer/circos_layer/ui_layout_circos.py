# -*- coding: utf-8 -*-
"""
Circos 圈图界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/图片标签、设置样式尺寸
完全不写按钮点击、不绑信号、不解析文件、不调内核
（骨架逐项照抄 commontools_layer/vennplot_layer/ui_layout_vennplot.py）
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_text_edit, create_styled_label,
    create_styled_panel, create_styled_group_box, create_styled_tab_widget,
    create_styled_table, create_styled_combo_box, create_styled_line_edit,
    create_styled_checkbox, create_styled_number_input, create_zoomable_image_label
)
from script.mods_layer.mod_manager import global_mod_manager


class CircosPageUI:
    """Circos 圈图页界面布局类（纯布局，无逻辑）"""

    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.circos_page = None
        self.create_page()

    # ------------------------------------------------------------------ 主题
    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.circos_page.findChild(QLabel, "circos_bg")
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
        """更新所有控件的样式（不修改控件尺寸）"""
        styles = get_mod_styles()

        title_label = self.circos_page.findChild(QLabel, "circos_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.circos_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or
                                       child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_run_circos'):
            self.btn_run_circos.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_circos'):
            self.btn_export_circos.setStyleSheet(get_stylesheet_for_widget('export_button'))

        label_style = get_stylesheet_for_widget('label')
        for child in self.circos_page.findChildren(QLabel):
            if child.objectName() != "circos_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.circos_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.circos_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        group_box_style = get_stylesheet_for_widget('group_box')
        for child in self.circos_page.findChildren(QGroupBox):
            child.setStyleSheet(group_box_style)

        table_style = get_stylesheet_for_widget('table')
        for child in self.circos_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)

        tab_widget_style = self._get_tab_widget_style()
        for child in self.circos_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_widget_style)

        overlay = self.circos_page.findChild(QWidget, "circos_overlay")
        if overlay:
            overlay.setStyleSheet(
                f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    def _get_tab_widget_style(self):
        """获取标签页样式"""
        styles = get_mod_styles()
        primary_color = styles.get('sub_text_color', styles.get('text_color', '#87CEEB'))
        secondary_color = styles.get('sub_border_color', styles.get('border_color', '#1E3A5F'))
        dark_bg = styles.get('sub_fill_alt', styles.get('fill_alt', 'rgba(30, 58, 95, 0.6)'))
        hover_color = styles.get('sub_hover_color', styles.get('hover_color', 'rgba(30, 58, 95, 0.5)'))
        tab_selected_bg = styles.get('sub_active_color', styles.get('active_color', 'rgba(135, 206, 235, 0.2)'))
        return f"""
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

    # ------------------------------------------------------------ 局部小工具
    def _section_label(self, text):
        """小标题（纯布局辅助，非业务）"""
        label = create_styled_label(text, font_size=9, bold=True)
        label.setAlignment(Qt.AlignCenter)
        return label

    # ---------------------------------------------------------------- 建页面
    def create_page(self):
        self.circos_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.circos_page)
        bg_label.setObjectName("circos_bg")
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

        overlay = QWidget(self.circos_page)
        overlay.setObjectName("circos_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        main_layout = QVBoxLayout(overlay)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ------------------------------------------------------------ 顶栏
        top_layout = QHBoxLayout()

        self.btn_back_circos = create_styled_button("← 返回小工具主页", font_size=12)
        top_layout.addWidget(self.btn_back_circos)

        self.circos_title_label = QLabel("Circos 圈图")
        self.circos_title_label.setObjectName("circos_title")
        self.circos_title_label.setFont(get_font_for_widget('button', 28, bold=True))
        self.circos_title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        self.circos_title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(self.circos_title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.circos_page, mod_instance)

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
        main_layout.addLayout(top_layout)

        # -------------------------------------------------------- 主体左右
        content_layout = QHBoxLayout()

        # ============ 左：参数面板（可滚动，内容高于屏幕时不出画布） ============
        outer_panel, outer_layout = create_styled_panel(fixed_width=320)
        outer_layout.setContentsMargins(3, 6, 3, 6)

        param_scroll = QScrollArea()
        param_scroll.setWidgetResizable(True)
        param_scroll.setFrameShape(QFrame.NoFrame)
        param_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        param_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        param_host = QWidget()
        param_host.setStyleSheet("background: transparent;")
        param_layout = QVBoxLayout(param_host)
        param_layout.setContentsMargins(4, 4, 4, 4)
        param_layout.setSpacing(5)

        # ---- 基因输入 ----
        param_layout.addWidget(self._section_label("基因输入"))

        self.circos_input_mode_combo = create_styled_combo_box()
        self.circos_input_mode_combo.addItems(["手动输入", "外部列表"])
        param_layout.addWidget(self.circos_input_mode_combo)

        self.circos_genes_text = create_styled_text_edit()
        self.circos_genes_text.setPlaceholderText("每行一个基因名（也支持逗号/空格分隔）")
        self.circos_genes_text.setMinimumHeight(120)
        self.circos_genes_text.setMaximumHeight(160)
        param_layout.addWidget(self.circos_genes_text)

        self.circos_genelist_combo = create_styled_combo_box()
        param_layout.addWidget(self.circos_genelist_combo)

        self.btn_refresh_genelists = create_styled_button("刷新列表", font_size=9)
        param_layout.addWidget(self.btn_refresh_genelists)

        self.circos_genelist_hint = create_styled_label("共 0 个基因列表文件", font_size=8, bold=False)
        param_layout.addWidget(self.circos_genelist_hint)

        self.circos_gene_count_label = create_styled_label("解析到 0 个基因", font_size=8, bold=False)
        param_layout.addWidget(self.circos_gene_count_label)

        # ---- 参考基因组与窗口 ----
        param_layout.addWidget(self._section_label("参考基因组与窗口"))

        self.circos_assembly_combo = create_styled_combo_box()
        self.circos_assembly_combo.addItems(["hg38"])
        param_layout.addWidget(self.circos_assembly_combo)

        self.circos_tier_combo = create_styled_combo_box()
        self.circos_tier_combo.addItems(["1 Mb", "2 Mb", "5 Mb", "10 Mb", "20 Mb"])
        self.circos_tier_combo.setCurrentText("5 Mb")
        param_layout.addWidget(self.circos_tier_combo)

        # ---- 环开关 ----
        param_layout.addWidget(self._section_label("显示环开关"))

        self.circos_show_ideogram_check = create_styled_checkbox("染色体核型条带环")
        self.circos_show_ideogram_check.setChecked(True)
        param_layout.addWidget(self.circos_show_ideogram_check)

        self.circos_show_gc_check = create_styled_checkbox("GC 含量环")
        self.circos_show_gc_check.setChecked(True)
        param_layout.addWidget(self.circos_show_gc_check)

        self.circos_show_density_heatmap_check = create_styled_checkbox("基因密度热图环")
        self.circos_show_density_heatmap_check.setChecked(True)
        param_layout.addWidget(self.circos_show_density_heatmap_check)

        self.circos_show_density_bars_check = create_styled_checkbox("基因密度柱状环")
        self.circos_show_density_bars_check.setChecked(True)
        param_layout.addWidget(self.circos_show_density_bars_check)

        self.circos_show_loci_check = create_styled_checkbox("输入基因位点环")
        self.circos_show_loci_check.setChecked(True)
        param_layout.addWidget(self.circos_show_loci_check)

        self.circos_show_gene_labels_check = create_styled_checkbox("基因注释（名称+牵引线）")
        self.circos_show_gene_labels_check.setChecked(True)
        param_layout.addWidget(self.circos_show_gene_labels_check)

        self.circos_show_legend_check = create_styled_checkbox("图例")
        self.circos_show_legend_check.setChecked(True)
        param_layout.addWidget(self.circos_show_legend_check)

        self.circos_show_title_check = create_styled_checkbox("显示标题")
        self.circos_show_title_check.setChecked(True)
        param_layout.addWidget(self.circos_show_title_check)

        # ---- 标题与标注 ----
        param_layout.addWidget(self._section_label("标题与标注"))

        self.circos_title_input = create_styled_line_edit()
        self.circos_title_input.setText("Chromosomal Distribution of Genes")
        param_layout.addWidget(self.circos_title_input)

        max_label_row = QHBoxLayout()
        max_label_row.addWidget(create_styled_label("最多标注基因数：", font_size=8, bold=False))
        self.circos_max_labels_input = create_styled_number_input(
            min_value=0, max_value=2000, default_value=40)
        max_label_row.addWidget(self.circos_max_labels_input)
        param_layout.addLayout(max_label_row)

        # ---- 基因名标签参数（契约 §14.3：紧跟「最多标注基因数」之后）----
        # 用户诉求：基因一多标签就会叠字，要能用字号/层数/最小角度间隔三个旋钮调开。

        fontsize_row = QHBoxLayout()
        fontsize_row.addWidget(create_styled_label("基因名字号：", font_size=8, bold=False))
        self.circos_label_fontsize_input = create_styled_number_input(
            min_value=4, max_value=16, default_value=9)
        fontsize_row.addWidget(self.circos_label_fontsize_input)
        param_layout.addLayout(fontsize_row)

        layers_row = QHBoxLayout()
        layers_row.addWidget(create_styled_label("标签层数：", font_size=8, bold=False))
        self.circos_label_layers_input = create_styled_number_input(
            min_value=1, max_value=4, default_value=2)
        layers_row.addWidget(self.circos_label_layers_input)
        param_layout.addLayout(layers_row)

        minsep_row = QHBoxLayout()
        minsep_row.addWidget(create_styled_label("标签最小角度间隔：", font_size=8, bold=False))
        self.circos_label_minsep_input = create_styled_number_input(
            min_value=2, max_value=30, default_value=10)
        minsep_row.addWidget(self.circos_label_minsep_input)
        param_layout.addLayout(minsep_row)

        # ---- 连线 ----
        param_layout.addWidget(self._section_label("PPI 连线"))

        self.circos_links_check = create_styled_checkbox("PPI 连线（需联网 STRING）")
        self.circos_links_check.setChecked(False)
        param_layout.addWidget(self.circos_links_check)

        score_row = QHBoxLayout()
        score_row.addWidget(create_styled_label("连线最低置信度：", font_size=8, bold=False))
        self.circos_links_score_input = create_styled_number_input(
            min_value=0, max_value=1, default_value=0.7, step=0.05)
        score_row.addWidget(self.circos_links_score_input)
        param_layout.addLayout(score_row)

        # ---- 出图参数 ----
        param_layout.addWidget(self._section_label("出图参数"))

        dpi_row = QHBoxLayout()
        dpi_row.addWidget(create_styled_label("DPI：", font_size=8, bold=False))
        self.circos_dpi_input = create_styled_number_input(
            min_value=36, max_value=1200, default_value=300)
        dpi_row.addWidget(self.circos_dpi_input)
        param_layout.addLayout(dpi_row)

        size_row = QHBoxLayout()
        size_row.addWidget(create_styled_label("图幅（英寸）：", font_size=8, bold=False))
        self.circos_size_input = create_styled_number_input(
            min_value=3, max_value=50, default_value=10)
        size_row.addWidget(self.circos_size_input)
        param_layout.addLayout(size_row)

        self.circos_fmt_png_check = create_styled_checkbox("PNG")
        self.circos_fmt_png_check.setChecked(True)
        param_layout.addWidget(self.circos_fmt_png_check)

        self.circos_fmt_svg_check = create_styled_checkbox("SVG")
        self.circos_fmt_svg_check.setChecked(True)
        param_layout.addWidget(self.circos_fmt_svg_check)

        self.circos_fmt_pdf_check = create_styled_checkbox("PDF")
        self.circos_fmt_pdf_check.setChecked(False)
        param_layout.addWidget(self.circos_fmt_pdf_check)

        # ---- 操作按钮 ----
        self.btn_run_circos = create_styled_button("▶ 运行", font_size=9, button_type='run')
        param_layout.addWidget(self.btn_run_circos)

        self.btn_clear_circos = create_styled_button("清空", font_size=9)
        param_layout.addWidget(self.btn_clear_circos)

        self.btn_export_circos = create_styled_button("导出图片…", font_size=9, button_type='export')
        param_layout.addWidget(self.btn_export_circos)

        self.btn_open_out_dir = create_styled_button("打开输出目录", font_size=9)
        param_layout.addWidget(self.btn_open_out_dir)

        param_layout.addStretch()

        param_scroll.setWidget(param_host)
        outer_layout.addWidget(param_scroll, 1)

        content_layout.addWidget(outer_panel, 0)

        # ================= 右：结果页签 + 运行日志 =================
        right_panel, right_layout = create_styled_panel()

        result_group = create_styled_group_box("出图结果")
        result_layout = QVBoxLayout(result_group)

        self.circos_tabs = create_styled_tab_widget(movable=True, document_mode=True)

        # 页签 1：圈图
        plot_panel, plot_panel_layout = create_styled_panel()
        plot_panel_layout.setContentsMargins(0, 0, 0, 0)

        self.circos_plot_label = create_zoomable_image_label()
        self.circos_plot_label.setMinimumSize(450, 400)
        plot_panel_layout.addWidget(self.circos_plot_label)

        self.circos_tabs.addTab(plot_panel, "圈图")

        # 页签 2：基因定位表
        genes_panel, genes_panel_layout = create_styled_panel()
        genes_panel_layout.setContentsMargins(0, 0, 0, 0)

        self.circos_table = create_styled_table()
        genes_panel_layout.addWidget(self.circos_table)

        self.circos_tabs.addTab(genes_panel, "基因定位表")

        # 页签 3：未匹配基因
        missing_panel, missing_panel_layout = create_styled_panel()
        missing_panel_layout.setContentsMargins(0, 0, 0, 0)

        self.circos_missing_table = create_styled_table()
        missing_panel_layout.addWidget(self.circos_missing_table)

        self.circos_tabs.addTab(missing_panel, "未匹配基因")

        result_layout.addWidget(self.circos_tabs)

        right_layout.addWidget(result_group, 4)

        log_group = create_styled_group_box("运行信息")
        log_layout = QVBoxLayout(log_group)

        self.circos_log = create_styled_text_edit(read_only=True)
        self.circos_log.setMaximumHeight(110)
        log_layout.addWidget(self.circos_log)

        right_layout.addWidget(log_group, 1)

        content_layout.addWidget(right_panel, 1)

        main_layout.addLayout(content_layout, 4)

        self.update_styles()

        return self.circos_page
