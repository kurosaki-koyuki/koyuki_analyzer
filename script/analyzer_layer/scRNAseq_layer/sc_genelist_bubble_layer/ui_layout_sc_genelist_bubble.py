# -*- coding: utf-8 -*-
"""
基因集气泡图界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_text_edit, create_styled_spinbox,
    create_styled_tab_widget, create_styled_image_tab, create_zoomable_image_label
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class ScGenelistBubblePageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.genelist_bubble_page.findChild(QLabel, "genelist_bubble_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        styles = get_mod_styles()

        title_label = self.genelist_bubble_page.findChild(QLabel, "genelist_bubble_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.genelist_bubble_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_load_gene_set'):
            self.btn_load_gene_set.setStyleSheet(get_stylesheet_for_widget('import_button'))
        if hasattr(self, 'btn_draw_bubble'):
            self.btn_draw_bubble.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_png'):
            self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_csv'):
            self.btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_pdf'):
            self.btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_svg'):
            self.btn_export_svg.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_eps'):
            self.btn_export_eps.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.genelist_bubble_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.genelist_bubble_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.genelist_bubble_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.genelist_bubble_page.findChildren(QLabel):
            if child.objectName() != "genelist_bubble_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.genelist_bubble_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.genelist_bubble_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.genelist_bubble_page.findChild(QWidget, "genelist_bubble_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

    def create_page(self):
        self.genelist_bubble_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.genelist_bubble_page)
        bg_label.setObjectName("genelist_bubble_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.genelist_bubble_page)
        overlay.setObjectName("genelist_bubble_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_bubble = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_bubble)

        title_label = QLabel("基因集气泡图")
        title_label.setObjectName("genelist_bubble_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.genelist_bubble_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')

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

        self.genelist_bubble_log = create_styled_text_edit(read_only=True, variant='sub')
        self.genelist_bubble_log.setMaximumHeight(80)
        layout.addWidget(self.genelist_bubble_log)

        main_layout = QHBoxLayout()

        left_panel, left_layout = create_styled_panel(fixed_width=280)

        gene_input_frame, gene_input_layout = create_styled_panel(variant='sub')

        gene_label = create_styled_label("批量基因（每行一个）", font_size=12, bold=True)
        gene_input_layout.addWidget(gene_label)

        self.genelist_text_input = create_styled_text_edit(variant='sub')
        self.genelist_text_input.setPlaceholderText("请输入基因列表，每行一个基因")
        self.genelist_text_input.setMaximumHeight(120)
        gene_input_layout.addWidget(self.genelist_text_input)

        self.btn_load_gene_set = create_styled_button("加载基因", font_size=10, variant='import')
        gene_input_layout.addWidget(self.btn_load_gene_set)

        left_layout.addWidget(gene_input_frame)

        left_layout.addSpacing(10)

        main_anno_label = create_styled_label("X轴分组注释", font_size=12, bold=True)
        left_layout.addWidget(main_anno_label)

        self.genelist_bubble_main_combo = create_styled_combo_box()
        left_layout.addWidget(self.genelist_bubble_main_combo)

        self.genelist_bubble_main_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        left_layout.addWidget(self.genelist_bubble_main_list)

        left_layout.addSpacing(10)

        filter1_frame, filter1_layout = create_styled_panel()

        filter1_header = QHBoxLayout()
        self.genelist_bubble_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.genelist_bubble_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.genelist_bubble_filter1_combo = create_styled_combo_box()
        self.genelist_bubble_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.genelist_bubble_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.genelist_bubble_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.genelist_bubble_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.genelist_bubble_filter1_list)

        left_layout.addWidget(filter1_frame)

        left_layout.addSpacing(5)

        filter2_frame, filter2_layout = create_styled_panel()

        filter2_header = QHBoxLayout()
        self.genelist_bubble_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.genelist_bubble_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.genelist_bubble_filter2_combo = create_styled_combo_box()
        self.genelist_bubble_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.genelist_bubble_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.genelist_bubble_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.genelist_bubble_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.genelist_bubble_filter2_list)

        left_layout.addWidget(filter2_frame)

        left_layout.addSpacing(10)

        self.btn_draw_bubble = create_styled_button("筛选并绘图", font_size=12, button_type='run')
        self.btn_draw_bubble.setFixedHeight(35)
        left_layout.addWidget(self.btn_draw_bubble)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        center_panel, center_layout = create_styled_panel(fixed_width=280)

        param_title = create_styled_label("参数调整", font_size=14, bold=True)
        center_layout.addWidget(param_title)

        center_layout.addSpacing(8)

        main_title_layout = QHBoxLayout()
        main_title_label = create_styled_label("主图标题", font_size=10, bold=False)
        main_title_layout.addWidget(main_title_label)
        self.genelist_bubble_main_title = create_styled_line_edit(fixed_width=160)
        self.genelist_bubble_main_title.setText("Gene Set Expression Bubble Plot")
        main_title_layout.addWidget(self.genelist_bubble_main_title)
        center_layout.addLayout(main_title_layout)
        center_layout.addSpacing(5)

        cbar_label_layout = QHBoxLayout()
        cbar_label_label = create_styled_label("色条标签", font_size=10, bold=False)
        cbar_label_layout.addWidget(cbar_label_label)
        self.genelist_bubble_cbar_label = create_styled_line_edit(fixed_width=160)
        self.genelist_bubble_cbar_label.setText("Mean Expression")
        cbar_label_layout.addWidget(self.genelist_bubble_cbar_label)
        center_layout.addLayout(cbar_label_layout)
        center_layout.addSpacing(5)

        fig_width_layout = QHBoxLayout()
        fig_width_label = create_styled_label("宽度", font_size=10, bold=False)
        fig_width_layout.addWidget(fig_width_label)
        self.genelist_bubble_fig_width = create_styled_spinbox(min_value=1, max_value=100, default_value=9)
        fig_width_layout.addWidget(self.genelist_bubble_fig_width)
        center_layout.addLayout(fig_width_layout)
        center_layout.addSpacing(5)

        fig_height_layout = QHBoxLayout()
        fig_height_label = create_styled_label("高度", font_size=10, bold=False)
        fig_height_layout.addWidget(fig_height_label)
        self.genelist_bubble_fig_height = create_styled_spinbox(min_value=1, max_value=100, default_value=7)
        fig_height_layout.addWidget(self.genelist_bubble_fig_height)
        center_layout.addLayout(fig_height_layout)
        center_layout.addSpacing(5)

        scale_factor_layout = QHBoxLayout()
        scale_factor_label = create_styled_label("气泡缩放系数", font_size=10, bold=False)
        scale_factor_layout.addWidget(scale_factor_label)
        self.genelist_bubble_scale_factor = create_styled_spinbox(min_value=100, max_value=2000, default_value=750)
        scale_factor_layout.addWidget(self.genelist_bubble_scale_factor)
        center_layout.addLayout(scale_factor_layout)
        center_layout.addSpacing(5)

        legend_scale_layout = QHBoxLayout()
        legend_scale_label = create_styled_label("图例整体缩放", font_size=10, bold=False)
        legend_scale_layout.addWidget(legend_scale_label)
        self.genelist_bubble_legend_scale = create_styled_spinbox(min_value=10, max_value=30, default_value=10)
        legend_scale_layout.addWidget(self.genelist_bubble_legend_scale)
        center_layout.addLayout(legend_scale_layout)
        center_layout.addSpacing(5)

        title_fontsize_layout = QHBoxLayout()
        title_fontsize_label = create_styled_label("标题字号", font_size=10, bold=False)
        title_fontsize_layout.addWidget(title_fontsize_label)
        self.genelist_bubble_title_fontsize = create_styled_spinbox(min_value=8, max_value=30, default_value=14)
        title_fontsize_layout.addWidget(self.genelist_bubble_title_fontsize)
        center_layout.addLayout(title_fontsize_layout)
        center_layout.addSpacing(5)

        x_label_fontsize_layout = QHBoxLayout()
        x_label_fontsize_label = create_styled_label("X轴标签字号", font_size=10, bold=False)
        x_label_fontsize_layout.addWidget(x_label_fontsize_label)
        self.genelist_bubble_x_label_fontsize = create_styled_spinbox(min_value=8, max_value=30, default_value=12)
        x_label_fontsize_layout.addWidget(self.genelist_bubble_x_label_fontsize)
        center_layout.addLayout(x_label_fontsize_layout)
        center_layout.addSpacing(5)

        y_label_fontsize_layout = QHBoxLayout()
        y_label_fontsize_label = create_styled_label("Y轴标签字号", font_size=10, bold=False)
        y_label_fontsize_layout.addWidget(y_label_fontsize_label)
        self.genelist_bubble_y_label_fontsize = create_styled_spinbox(min_value=8, max_value=30, default_value=12)
        y_label_fontsize_layout.addWidget(self.genelist_bubble_y_label_fontsize)
        center_layout.addLayout(y_label_fontsize_layout)
        center_layout.addSpacing(5)

        legend_label_fontsize_layout = QHBoxLayout()
        legend_label_fontsize_label = create_styled_label("图例标签字号", font_size=10, bold=False)
        legend_label_fontsize_layout.addWidget(legend_label_fontsize_label)
        self.genelist_bubble_legend_label_fontsize = create_styled_spinbox(min_value=6, max_value=20, default_value=10)
        legend_label_fontsize_layout.addWidget(self.genelist_bubble_legend_label_fontsize)
        center_layout.addLayout(legend_label_fontsize_layout)
        center_layout.addSpacing(5)

        cbar_label_fontsize_layout = QHBoxLayout()
        cbar_label_fontsize_label = create_styled_label("色条标签字号", font_size=10, bold=False)
        cbar_label_fontsize_layout.addWidget(cbar_label_fontsize_label)
        self.genelist_bubble_cbar_label_fontsize = create_styled_spinbox(min_value=6, max_value=20, default_value=10)
        cbar_label_fontsize_layout.addWidget(self.genelist_bubble_cbar_label_fontsize)
        center_layout.addLayout(cbar_label_fontsize_layout)
        center_layout.addSpacing(5)

        label_spacing_layout = QHBoxLayout()
        label_spacing_label = create_styled_label("图例行间距", font_size=10, bold=False)
        label_spacing_layout.addWidget(label_spacing_label)
        self.genelist_bubble_label_spacing = create_styled_spinbox(min_value=10, max_value=50, default_value=25)
        label_spacing_layout.addWidget(self.genelist_bubble_label_spacing)
        center_layout.addLayout(label_spacing_layout)
        center_layout.addSpacing(5)

        main_right_ratio_layout = QHBoxLayout()
        main_right_ratio_label = create_styled_label("主图右边界", font_size=10, bold=False)
        main_right_ratio_layout.addWidget(main_right_ratio_label)
        self.genelist_bubble_main_right_ratio = create_styled_spinbox(min_value=50, max_value=90, default_value=65)
        main_right_ratio_layout.addWidget(self.genelist_bubble_main_right_ratio)
        center_layout.addLayout(main_right_ratio_layout)
        center_layout.addSpacing(5)

        center_layout.addStretch()
        main_layout.addWidget(center_panel)

        export_panel, export_layout = create_styled_panel(fixed_width=200)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        export_layout.addWidget(export_title)

        export_layout.addSpacing(8)

        export_size_frame, export_size_layout = create_styled_panel()

        export_size_label = create_styled_label("导出尺寸", font_size=10, bold=False)
        export_size_layout.addWidget(export_size_label)

        width_row = QHBoxLayout()
        width_row.addSpacing(5)

        width_label = create_styled_label("宽度:", font_size=10, bold=False)
        width_row.addWidget(width_label)

        self.genelist_bubble_export_width = create_styled_spinbox(min_value=1, max_value=100, default_value=9)
        width_row.addWidget(self.genelist_bubble_export_width)

        width_row.addStretch()

        export_size_layout.addLayout(width_row)

        height_row = QHBoxLayout()
        height_row.addSpacing(5)

        height_label = create_styled_label("高度:", font_size=10, bold=False)
        height_row.addWidget(height_label)

        self.genelist_bubble_export_height = create_styled_spinbox(min_value=1, max_value=100, default_value=7)
        height_row.addWidget(self.genelist_bubble_export_height)

        height_row.addStretch()

        export_size_layout.addLayout(height_row)
        export_layout.addWidget(export_size_frame)

        export_layout.addSpacing(8)

        self.btn_export_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_png)

        self.btn_export_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_pdf)

        self.btn_export_svg = create_styled_button("导出SVG", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_svg)

        self.btn_export_eps = create_styled_button("导出EPS", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_eps)

        self.btn_export_csv = create_styled_button("导出CSV", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_csv)

        export_layout.addStretch()
        main_layout.addWidget(export_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.genelist_bubble_plot_tabs = create_styled_tab_widget()

        _, self.genelist_bubble_image_label = create_styled_image_tab(self.genelist_bubble_plot_tabs, "基因集气泡图")

        right_layout.addWidget(self.genelist_bubble_plot_tabs)
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()