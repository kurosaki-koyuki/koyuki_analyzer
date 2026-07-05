# -*- coding: utf-8 -*-
"""
自定义小提琴图界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_spinbox, create_styled_text_edit,
    create_styled_tab_widget, create_styled_image_tab, create_zoomable_image_label
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class ViolinPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()
    
    def update_background(self):
        """更新背景图"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.violin_page.findChild(QLabel, "violin_bg")
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

        title_label = self.violin_page.findChild(QLabel, "violin_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.violin_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_load_gene'):
            self.btn_load_gene.setStyleSheet(get_stylesheet_for_widget('import_button'))
        if hasattr(self, 'btn_draw_violin'):
            self.btn_draw_violin.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_violin_png'):
            self.btn_export_violin_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_violin_pdf'):
            self.btn_export_violin_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_violin_svg'):
            self.btn_export_violin_svg.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_violin_plot_csv'):
            self.btn_export_violin_plot_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.violin_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.violin_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.violin_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.violin_page.findChildren(QLabel):
            if child.objectName() != "violin_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.violin_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.violin_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.violin_page.findChild(QWidget, "violin_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")
    
    def create_page(self):
        self.violin_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.violin_page)
        bg_label.setObjectName("violin_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height, 
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.violin_page)
        overlay.setObjectName("violin_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_violin = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_violin)

        title_label = QLabel("自定义小提琴图")
        title_label.setObjectName("violin_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.violin_page, mod_instance)

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

        self.violin_log = create_styled_text_edit(read_only=True, variant='sub')
        self.violin_log.setMaximumHeight(80)
        layout.addWidget(self.violin_log)

        main_layout = QHBoxLayout()

        left_panel, left_layout = create_styled_panel(fixed_width=280)

        gene_label = create_styled_label("基因名称", font_size=12, bold=True)
        left_layout.addWidget(gene_label)

        self.violin_gene_input = create_styled_line_edit()
        left_layout.addWidget(self.violin_gene_input)

        self.btn_load_gene = create_styled_button("加载基因", font_size=12, variant='import')
        left_layout.addWidget(self.btn_load_gene)

        left_layout.addSpacing(10)

        main_anno_label = create_styled_label("主注释（分组）", font_size=12, bold=True)
        left_layout.addWidget(main_anno_label)

        self.violin_main_combo = create_styled_combo_box()
        left_layout.addWidget(self.violin_main_combo)

        self.violin_main_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        left_layout.addWidget(self.violin_main_list)

        anno_filter_note = create_styled_label("选择注释类别以筛选细胞显示", font_size=9, bold=False)
        anno_filter_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(anno_filter_note)

        filter1_frame = QFrame()
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.violin_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.violin_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.violin_filter1_combo = create_styled_combo_box()
        self.violin_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.violin_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.violin_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.violin_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.violin_filter1_list)

        left_layout.addWidget(filter1_frame)

        filter2_frame = QFrame()
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.violin_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.violin_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.violin_filter2_combo = create_styled_combo_box()
        self.violin_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.violin_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.violin_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.violin_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.violin_filter2_list)

        left_layout.addWidget(filter2_frame)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        center_panel, center_layout = create_styled_panel(fixed_width=280)

        param_title = create_styled_label("参数调整", font_size=14, bold=True)
        center_layout.addWidget(param_title)

        center_layout.addSpacing(8)

        title_name_layout = QHBoxLayout()
        title_name_label = create_styled_label("标题名称", font_size=10, bold=False)
        title_name_layout.addWidget(title_name_label)
        self.violin_title_name = create_styled_line_edit(fixed_width=160)
        title_name_layout.addWidget(self.violin_title_name)
        center_layout.addLayout(title_name_layout)
        center_layout.addSpacing(5)

        title_size_layout = QHBoxLayout()
        title_size_label = create_styled_label("标题字体大小", font_size=10, bold=False)
        title_size_layout.addWidget(title_size_label)
        self.violin_title_size = create_styled_spinbox(min_value=8, max_value=40, default_value=16)
        title_size_layout.addWidget(self.violin_title_size)
        center_layout.addLayout(title_size_layout)
        center_layout.addSpacing(5)

        ylabel_name_layout = QHBoxLayout()
        ylabel_name_label = create_styled_label("纵坐标名称", font_size=10, bold=False)
        ylabel_name_layout.addWidget(ylabel_name_label)
        self.violin_ylabel_name = create_styled_line_edit(fixed_width=160)
        ylabel_name_layout.addWidget(self.violin_ylabel_name)
        center_layout.addLayout(ylabel_name_layout)
        center_layout.addSpacing(5)

        axis_size_layout = QHBoxLayout()
        axis_size_label = create_styled_label("坐标字体大小", font_size=10, bold=False)
        axis_size_layout.addWidget(axis_size_label)
        self.violin_axis_size = create_styled_spinbox(min_value=8, max_value=30, default_value=12)
        axis_size_layout.addWidget(self.violin_axis_size)
        center_layout.addLayout(axis_size_layout)
        center_layout.addSpacing(5)

        pairwise_size_layout = QHBoxLayout()
        pairwise_size_label = create_styled_label("组间比较字体", font_size=10, bold=False)
        pairwise_size_layout.addWidget(pairwise_size_label)
        self.violin_pairwise_size = create_styled_spinbox(min_value=8, max_value=30, default_value=11)
        pairwise_size_layout.addWidget(self.violin_pairwise_size)
        center_layout.addLayout(pairwise_size_layout)
        center_layout.addSpacing(5)

        pairwise_frame = QFrame()
        pairwise_frame.setObjectName("styled_panel_pairwise")
        pairwise_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 8px;")
        pairwise_layout = QVBoxLayout(pairwise_frame)
        pairwise_layout.setContentsMargins(5, 5, 5, 5)

        self.violin_pairwise_enable = create_styled_checkbox("启用组间比较")
        self.violin_pairwise_enable.setChecked(True)
        pairwise_layout.addWidget(self.violin_pairwise_enable)

        self.violin_pairwise_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        pairwise_layout.addWidget(self.violin_pairwise_list)

        pairwise_select_all_btn = create_styled_button("全选", font_size=9)
        pairwise_select_all_btn.clicked.connect(lambda: self.violin_pairwise_list.selectAll())
        pairwise_layout.addWidget(pairwise_select_all_btn)

        self.violin_overall_pvalue = create_styled_checkbox("总体比较p值")
        self.violin_overall_pvalue.setChecked(False)
        pairwise_layout.addWidget(self.violin_overall_pvalue)

        pvalue_mode_layout = QHBoxLayout()
        pvalue_mode_label = create_styled_label("p值模式", font_size=9, bold=False)
        self.violin_pvalue_mode = create_styled_combo_box()
        self.violin_pvalue_mode.addItems([
            "*表示显著，n.s.表示不显著",
            "*表示显著，不显著显示具体值",
            "n.s.表示不显著，显著显示具体值",
            "全部用具体值表示（p=?）"
        ])
        self.violin_pvalue_mode.setCurrentIndex(0)
        pvalue_mode_layout.addWidget(pvalue_mode_label)
        pvalue_mode_layout.addWidget(self.violin_pvalue_mode)
        pairwise_layout.addLayout(pvalue_mode_layout)

        self.violin_pairwise_enable.stateChanged.connect(lambda state: self.on_pairwise_enable_changed(state, pairwise_select_all_btn))

        center_layout.addWidget(pairwise_frame)

        center_layout.addSpacing(15)

        self.btn_draw_violin = create_styled_button("▶ 生成结果图", font_size=12, button_type='run')
        center_layout.addWidget(self.btn_draw_violin)

        center_layout.addStretch()
        main_layout.addWidget(center_panel)

        export_panel, export_layout = create_styled_panel(fixed_width=200)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        export_layout.addWidget(export_title)

        export_layout.addSpacing(8)

        export_size_frame = QFrame()
        export_size_frame.setObjectName("styled_panel_export_size")
        export_size_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        export_size_layout = QVBoxLayout(export_size_frame)
        export_size_layout.setContentsMargins(5, 5, 5, 5)

        export_size_label = create_styled_label("导出尺寸", font_size=10, bold=False)
        export_size_layout.addWidget(export_size_label)

        width_row = QHBoxLayout()
        width_row.addSpacing(5)

        width_label = create_styled_label("宽度:", font_size=10, bold=False)
        width_row.addWidget(width_label)

        self.violin_export_width = create_styled_spinbox(min_value=1, max_value=100, default_value=10)
        width_row.addWidget(self.violin_export_width)

        width_row.addStretch()

        export_size_layout.addLayout(width_row)

        height_row = QHBoxLayout()
        height_row.addSpacing(5)

        height_label = create_styled_label("高度:", font_size=10, bold=False)
        height_row.addWidget(height_label)

        self.violin_export_height = create_styled_spinbox(min_value=1, max_value=100, default_value=8)
        height_row.addWidget(self.violin_export_height)

        height_row.addStretch()

        export_size_layout.addLayout(height_row)
        export_layout.addWidget(export_size_frame)

        export_layout.addSpacing(8)

        self.btn_export_violin_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_violin_png)

        self.btn_export_violin_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_violin_pdf)

        self.btn_export_violin_svg = create_styled_button("导出SVG", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_violin_svg)

        self.btn_export_violin_plot_csv = create_styled_button("导出绘图CSV", font_size=10, button_type='export')
        export_layout.addWidget(self.btn_export_violin_plot_csv)

        export_layout.addStretch()
        main_layout.addWidget(export_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.violin_plot_tabs = create_styled_tab_widget()

        _, self.violin_box_label = create_styled_image_tab(self.violin_plot_tabs, "箱线小提琴图")

        _, self.violin_box_only_label = create_styled_image_tab(self.violin_plot_tabs, "箱线图")

        _, self.violin_only_label = create_styled_image_tab(self.violin_plot_tabs, "小提琴图")

        right_layout.addWidget(self.violin_plot_tabs)
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()
    
    def on_pairwise_enable_changed(self, state, select_all_btn):
        """启用/禁用组间比较"""
        enabled = state == Qt.Checked
        self.violin_pairwise_list.setEnabled(enabled)
        select_all_btn.setEnabled(enabled)
        self.violin_overall_pvalue.setEnabled(enabled)
        self.violin_pvalue_mode.setEnabled(enabled)