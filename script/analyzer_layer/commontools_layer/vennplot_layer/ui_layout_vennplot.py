# -*- coding: utf-8 -*-
"""
韦恩图界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_text_edit, create_styled_label,
    create_styled_panel, create_styled_group_box, create_styled_tab_widget,
    create_styled_tab_page, create_styled_table, create_editable_input_table,
    create_styled_spinbox, create_zoomable_image_label
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class VennPlotPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.vennplot_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.vennplot_page.findChild(QLabel, "vennplot_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """更新所有控件的样式（不修改控件尺寸）"""
        styles = get_mod_styles()

        title_label = self.vennplot_page.findChild(QLabel, "vennplot_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.vennplot_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_run'):
            self.btn_run.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_apply'):
            self.btn_apply.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_gene_set'):
            self.btn_export_gene_set.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_matrix'):
            self.btn_export_matrix.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_pdf'):
            self.btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_png'):
            self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))

        label_style = get_stylesheet_for_widget('label')
        for child in self.vennplot_page.findChildren(QLabel):
            if child.objectName() != "vennplot_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.vennplot_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.vennplot_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        group_box_style = get_stylesheet_for_widget('group_box')
        for child in self.vennplot_page.findChildren(QGroupBox):
            child.setStyleSheet(group_box_style)

        table_style = get_stylesheet_for_widget('table')
        for child in self.vennplot_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)

        tab_widget_style = self._get_tab_widget_style()
        for child in self.vennplot_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_widget_style)

        overlay = self.vennplot_page.findChild(QWidget, "vennplot_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

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

    def create_page(self):
        self.vennplot_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.vennplot_page)
        bg_label.setObjectName("vennplot_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.vennplot_page)
        overlay.setObjectName("vennplot_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        main_layout = QVBoxLayout(overlay)
        main_layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_vennplot = create_styled_button("← 返回主页", font_size=12)
        top_layout.addWidget(self.btn_back_vennplot)

        title_label = QLabel("韦恩图")
        title_label.setObjectName("vennplot_title")
        title_label.setFont(get_font_for_widget('button', 28, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.vennplot_page, mod_instance)

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
        main_layout.addLayout(top_layout)

        content_layout = QHBoxLayout()

        left_panel, left_layout = create_styled_panel(fixed_width=200)
        left_layout.setContentsMargins(5, 10, 5, 10)

        self.btn_clear = create_styled_button("清空", font_size=9)
        left_layout.addWidget(self.btn_clear)

        self.btn_run = create_styled_button("▶ 运行", font_size=9, button_type='run')
        left_layout.addWidget(self.btn_run)

        export_panel, export_layout = create_styled_panel()
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(5)

        self.btn_export_gene_set = create_styled_button("导出基因集合", font_size=9, button_type='export')
        export_layout.addWidget(self.btn_export_gene_set)

        self.btn_export_matrix = create_styled_button("导出交集矩阵", font_size=9, button_type='export')
        export_layout.addWidget(self.btn_export_matrix)

        self.btn_export_pdf = create_styled_button("导出韦恩图PDF", font_size=9, button_type='export')
        export_layout.addWidget(self.btn_export_pdf)

        self.btn_export_png = create_styled_button("导出韦恩图PNG", font_size=9, button_type='export')
        export_layout.addWidget(self.btn_export_png)

        left_layout.addWidget(export_panel)

        param_panel, param_layout = create_styled_panel()
        param_layout.setContentsMargins(3, 3, 3, 3)
        param_layout.setSpacing(3)

        param_title = create_styled_label("表格参数", font_size=9, bold=True)
        param_title.setAlignment(Qt.AlignCenter)
        param_layout.addWidget(param_title)

        row_panel, row_layout = create_styled_panel()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(3)

        row_label = create_styled_label("行数：", font_size=8, bold=False)
        row_layout.addWidget(row_label)

        self.venn_row_spin = create_styled_spinbox(min_value=1, max_value=100000, default_value=5000)
        row_layout.addWidget(self.venn_row_spin)
        param_layout.addWidget(row_panel)

        col_panel, col_layout = create_styled_panel()
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(3)

        col_label = create_styled_label("列数：", font_size=8, bold=False)
        col_layout.addWidget(col_label)

        self.venn_col_spin = create_styled_spinbox(min_value=1, max_value=100, default_value=30)
        col_layout.addWidget(self.venn_col_spin)
        param_layout.addWidget(col_panel)

        self.btn_apply = create_styled_button("应用", font_size=8, button_type='run')
        param_layout.addWidget(self.btn_apply)

        left_layout.addWidget(param_panel)
        left_layout.addStretch()
        content_layout.addWidget(left_panel, 1)

        right_panel, right_layout = create_styled_panel()

        log_group = create_styled_group_box("运行信息")
        log_layout = QVBoxLayout(log_group)

        self.venn_log = create_styled_text_edit(read_only=True)
        self.venn_log.setMaximumHeight(100)
        log_layout.addWidget(self.venn_log)

        right_layout.addWidget(log_group, 1)

        top_content_layout = QHBoxLayout()

        table_group = create_styled_group_box("基因集合编辑")
        table_layout = QVBoxLayout(table_group)

        self.venn_tabs = create_styled_tab_widget(movable=True, document_mode=True)

        gene_set_panel, gene_set_layout = create_styled_panel()
        gene_set_layout.setContentsMargins(0, 0, 0, 0)

        self.venn_table = create_editable_input_table(row_count=5000, col_count=30)
        gene_set_layout.addWidget(self.venn_table)

        self.venn_tabs.addTab(gene_set_panel, "基因集合")

        intersection_matrix_panel, intersection_matrix_layout = create_styled_panel()
        intersection_matrix_layout.setContentsMargins(0, 0, 0, 0)

        self.venn_intersection_matrix_table = create_styled_table()
        intersection_matrix_layout.addWidget(self.venn_intersection_matrix_table)

        self.venn_tabs.addTab(intersection_matrix_panel, "交集矩阵")

        table_layout.addWidget(self.venn_tabs)
        top_content_layout.addWidget(table_group, 3)

        plot_group = create_styled_group_box("出图结果")
        plot_layout = QVBoxLayout(plot_group)

        self.venn_plot_label = create_zoomable_image_label()
        self.venn_plot_label.setMinimumSize(450, 400)
        plot_layout.addWidget(self.venn_plot_label)

        top_content_layout.addWidget(plot_group, 3)

        right_layout.addLayout(top_content_layout, 3)

        content_layout.addWidget(right_panel, 4)

        main_layout.addLayout(content_layout, 4)
        main_layout.addStretch()

        self.update_styles()

        return self.vennplot_page