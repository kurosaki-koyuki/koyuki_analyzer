# -*- coding: utf-8 -*-
"""
UMAP初步作图R版本界面UI布局脚本 - 子层，无背景，无外框面板
使用标签页方式：第一个标签页显示注释出图，第二个标签页显示表达量图
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget, create_styled_button, create_styled_combo_box, create_styled_line_edit, create_styled_label, create_styled_panel, create_styled_tab_widget, create_styled_image_tab, create_styled_text_edit, get_unified_font
from script.mods_layer.mod_manager import global_mod_manager


class ScUmapInitialRPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_styles(self):
        styles = get_mod_styles()

        title_label = self.sc_umap_initial_r_page.findChild(QLabel, "sc_umap_initial_r_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.sc_umap_initial_r_page.findChildren(QPushButton):
            if child == self.btn_generate_annotations:
                continue
            elif child == self.btn_draw_expression:
                continue
            elif child in [self.btn_export_png, self.btn_export_pdf]:
                continue
            child.setStyleSheet(button_style)

        self.btn_generate_annotations.setStyleSheet(get_stylesheet_for_widget('run_button'))
        self.btn_draw_expression.setStyleSheet(get_stylesheet_for_widget('run_button'))
        self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        self.btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.sc_umap_initial_r_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.sc_umap_initial_r_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.sc_umap_initial_r_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_umap_initial_r_page.findChildren(QLabel):
            if child.objectName() != "sc_umap_initial_r_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        panel_bg = styles.get('sub_panel_bg', styles.get('panel_background', 'rgba(30, 58, 95, 0.5)'))
        panel_border = styles.get('sub_panel_border', styles.get('panel_border_color', '#1E3A5F'))
        panel_radius = styles.get('panel_border_radius', '8px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_umap_initial_r_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    def create_page(self):
        self.sc_umap_initial_r_page = QWidget(self.parent)

        styles = get_mod_styles()

        layout = QVBoxLayout(self.sc_umap_initial_r_page)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        title_label = QLabel("R版本 - UMAP初步作图")
        title_label.setObjectName("sc_umap_initial_r_title")
        title_label.setFont(get_font_for_widget('button', 28, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.sc_umap_initial_r_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')

        music_container_x = styles.get('music_container_x', 0.85)
        music_container_y = styles.get('music_container_y', 15)
        if isinstance(music_container_x, float):
            music_container_x = int(self.screen_width * music_container_x)
        music_container.move(music_container_x, music_container_y)

        top_layout.addWidget(music_container)

        top_layout.setStretch(0, 3)
        top_layout.setStretch(1, 1)

        layout.addLayout(top_layout)

        self.status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.status_text.setMaximumHeight(80)
        layout.addWidget(self.status_text)

        main_layout = QHBoxLayout()

        left_panel, left_layout = create_styled_panel(fixed_width=280)

        info_title = QLabel("数据信息")
        info_title.setFont(get_font_for_widget('label', 14, bold=True))
        info_title.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(info_title)

        self.data_info_text = create_styled_text_edit(read_only=True, variant='sub')
        self.data_info_text.setMaximumHeight(120)
        self.data_info_text.setFont(get_font_for_widget('label', 10))
        self.data_info_text.setStyleSheet(get_stylesheet_for_widget('text_edit'))
        self.data_info_text.setText("数据未加载\n请从主页加载RDS文件")
        left_layout.addWidget(self.data_info_text)

        left_layout.addSpacing(15)

        anno_title = QLabel("注释出图")
        anno_title.setFont(get_font_for_widget('label', 14, bold=True))
        anno_title.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(anno_title)

        self.annotation_combo = create_styled_combo_box()
        left_layout.addWidget(self.annotation_combo)

        self.btn_generate_annotations = create_styled_button("生成注释出图", font_size=12, button_type='run')
        left_layout.addWidget(self.btn_generate_annotations)

        left_layout.addSpacing(15)

        expr_title = QLabel("表达量出图")
        expr_title.setFont(get_font_for_widget('label', 14, bold=True))
        expr_title.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(expr_title)

        gene_label = QLabel("基因名（每行一个）")
        gene_label.setFont(get_font_for_widget('label', 12, bold=True))
        gene_label.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(gene_label)

        self.gene_input = create_styled_text_edit()
        self.gene_input.setPlaceholderText("TP53\nKRAS\nEGFR")
        self.gene_input.setMaximumHeight(100)
        left_layout.addWidget(self.gene_input)

        self.btn_draw_expression = create_styled_button("绘制表达量图", font_size=12, button_type='run')
        left_layout.addWidget(self.btn_draw_expression)

        left_layout.addSpacing(15)

        export_title = QLabel("导出选项")
        export_title.setFont(get_font_for_widget('label', 14, bold=True))
        export_title.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(export_title)

        self.btn_export_png = create_styled_button("导出当前图片PNG", font_size=12, button_type='export')
        left_layout.addWidget(self.btn_export_png)

        self.btn_export_pdf = create_styled_button("导出当前图片PDF", font_size=12, button_type='export')
        left_layout.addWidget(self.btn_export_pdf)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.umap_plot_tabs = create_styled_tab_widget()

        _, self.annotation_label = create_styled_image_tab(self.umap_plot_tabs, "注释出图")

        expression_tab = QWidget()
        expression_tab_layout = QVBoxLayout(expression_tab)
        self.expression_layout = QVBoxLayout()
        expression_tab_layout.addLayout(self.expression_layout)
        self.umap_plot_tabs.addTab(expression_tab, "表达量出图")

        right_layout.addWidget(self.umap_plot_tabs)
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.sc_umap_initial_r_page