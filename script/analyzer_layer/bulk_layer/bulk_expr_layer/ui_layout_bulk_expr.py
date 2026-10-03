# -*- coding: utf-8 -*-
"""
bulk表达量分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_spinbox, create_styled_text_edit,
    create_styled_tab_widget, create_styled_image_tab, create_zoomable_image_label,
    create_navigation_panel, create_navigation_button,
    create_navigation_divider, create_navigation_header,
    create_labeled_param_with_help
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.bulk_layer.bulk_gene_set_utils import (
    GENE_SET_METHODS, GENE_SET_METHOD_HELP, list_gene_set_files
)

class BulkExprPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        """更新背景图"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_expr_page.findChild(QLabel, "bulk_expr_bg")
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

        title_label = self.bulk_expr_page.findChild(QLabel, "bulk_expr_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        # 更新按钮样式（导航按钮/特殊按钮单独处理，避免通用样式覆盖其 checked/hover 态）
        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_expr_page.findChildren(QPushButton):
            name = child.objectName() or ""
            if name.startswith("styled_btn_") or name.startswith("number_input_btn_") or name.startswith("nav_btn_"):
                continue
            child.setStyleSheet(button_style)

        # 重新应用特殊按钮样式（确保不被通用样式覆盖）
        if hasattr(self, 'bulk_btn_plot'):
            self.bulk_btn_plot.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_btn_export_csv'):
            self.bulk_btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_btn_export_png'):
            self.bulk_btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_btn_export_pdf'):
            self.bulk_btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))

        # 基因集页特殊按钮
        if hasattr(self, 'bulk_geneset_btn_plot'):
            self.bulk_geneset_btn_plot.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_geneset_btn_export_csv'):
            self.bulk_geneset_btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_geneset_btn_export_png'):
            self.bulk_geneset_btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_geneset_btn_export_pdf'):
            self.bulk_geneset_btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_expr_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_expr_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_expr_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_expr_page.findChildren(QLabel):
            if child.objectName() != "bulk_expr_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        slider_style = get_stylesheet_for_widget('slider')
        for child in self.bulk_expr_page.findChildren(QSlider):
            child.setStyleSheet(slider_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_expr_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_expr_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.bulk_expr_page.findChild(QWidget, "bulk_expr_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

    def create_page(self):
        self.bulk_expr_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        # 背景图
        bg_label = QLabel(self.bulk_expr_page)
        bg_label.setObjectName("bulk_expr_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        # 覆盖层
        overlay = QWidget(self.bulk_expr_page)
        overlay.setObjectName("bulk_expr_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        root_layout = QHBoxLayout(overlay)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 左侧导航栏
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回上一页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        nav_layout.addSpacing(10)

        nav_layout.addWidget(create_navigation_header("分析类型", font_size=11, parent=nav_panel))

        self.nav_btn_single = create_navigation_button("单基因分析", font_size=13, parent=nav_panel)
        self.nav_btn_single.setObjectName("nav_btn_single")
        self.nav_btn_single.setChecked(True)
        nav_layout.addWidget(self.nav_btn_single)

        self.nav_btn_geneset = create_navigation_button("基因集分析", font_size=13, parent=nav_panel)
        self.nav_btn_geneset.setObjectName("nav_btn_geneset")
        nav_layout.addWidget(self.nav_btn_geneset)

        nav_layout.addStretch()
        root_layout.addWidget(nav_panel)

        # 右侧内容区
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # 顶部标题栏（两页共用）
        top_layout = QHBoxLayout()

        title_label = QLabel("bulk表达量分析")
        title_label.setObjectName("bulk_expr_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.bulk_expr_page, mod_instance)

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
        content_layout.addLayout(top_layout)

        # 状态区域（两页共用）
        self.bulk_status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.bulk_status_text.setMaximumHeight(80)
        content_layout.addWidget(self.bulk_status_text)

        # 内容栈：index 0 = 单基因页，index 1 = 基因集页
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: transparent;")
        content_layout.addWidget(self.content_stack, 1)

        self._build_single_gene_page()
        self._build_gene_set_page()

        root_layout.addWidget(content_panel, 1)

    def _build_single_gene_page(self):
        """index 0：原单基因分析页（控件属性名保持原样）"""
        styles = get_mod_styles()

        self.single_page_container = QWidget()
        main_layout = QHBoxLayout(self.single_page_container)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 左侧控制面板
        left_panel, left_layout = create_styled_panel(fixed_width=280)

        # 基因输入
        gene_label = create_styled_label("基因名称", font_size=12, bold=True)
        left_layout.addWidget(gene_label)

        self.bulk_gene_input = create_styled_line_edit()
        left_layout.addWidget(self.bulk_gene_input)

        # 分类选择下拉框
        clinical_label = create_styled_label("分类列选择", font_size=12, bold=True)
        left_layout.addWidget(clinical_label)

        self.bulk_clinical_combo = create_styled_combo_box()
        self.bulk_clinical_combo.addItem("全部")
        left_layout.addWidget(self.bulk_clinical_combo)

        # 分类列多选列表（当选择"全部"时显示）
        self.bulk_clinical_col_list_label = create_styled_label("分类列（可多选）", font_size=11, bold=False)
        self.bulk_clinical_col_list_label.hide()
        left_layout.addWidget(self.bulk_clinical_col_list_label)

        self.bulk_clinical_col_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_clinical_col_list.hide()
        left_layout.addWidget(self.bulk_clinical_col_list)

        # 组别多选列表（当选择具体分类时显示）
        self.bulk_group_list_label = create_styled_label("组别（可多选）", font_size=11, bold=False)
        self.bulk_group_list_label.hide()
        left_layout.addWidget(self.bulk_group_list_label)

        self.bulk_group_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_group_list.hide()
        left_layout.addWidget(self.bulk_group_list)

        # 筛选1框架
        filter1_frame = QFrame()
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.bulk_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.bulk_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.bulk_filter1_combo = create_styled_combo_box()
        self.bulk_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.bulk_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.bulk_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.bulk_filter1_list)

        left_layout.addWidget(filter1_frame)

        # 筛选2框架
        filter2_frame = QFrame()
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.bulk_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.bulk_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.bulk_filter2_combo = create_styled_combo_box()
        self.bulk_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.bulk_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.bulk_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.bulk_filter2_list)

        left_layout.addWidget(filter2_frame)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # 中间参数调整面板
        center_panel, center_layout = create_styled_panel(fixed_width=280)

        param_title = create_styled_label("参数调整", font_size=14, bold=True)
        center_layout.addWidget(param_title)

        # 多基因测定区域
        multi_gene_frame = QFrame()
        multi_gene_frame.setObjectName("styled_panel_multigene")
        multi_gene_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        multi_gene_layout = QVBoxLayout(multi_gene_frame)
        multi_gene_layout.setContentsMargins(5, 5, 5, 5)

        multi_gene_label = create_styled_label("多基因测定（逐个基因分析）", font_size=11, bold=True)
        multi_gene_layout.addWidget(multi_gene_label)

        multi_gene_hint = create_styled_label("每输入一个基因请另起一行", font_size=9, bold=False)
        multi_gene_layout.addWidget(multi_gene_hint)

        self.bulk_multi_gene_input = create_styled_text_edit(variant='sub')
        self.bulk_multi_gene_input.setMaximumHeight(80)
        multi_gene_layout.addWidget(self.bulk_multi_gene_input)

        center_layout.addWidget(multi_gene_frame)

        center_layout.addSpacing(8)

        # 标题名称
        title_name_layout = QHBoxLayout()
        title_name_label = create_styled_label("标题名称", font_size=10, bold=False)
        title_name_layout.addWidget(title_name_label)
        self.bulk_title_name = create_styled_line_edit(fixed_width=160)
        title_name_layout.addWidget(self.bulk_title_name)
        center_layout.addLayout(title_name_layout)
        center_layout.addSpacing(5)

        # 标题字体大小
        title_size_layout = QHBoxLayout()
        title_size_label = create_styled_label("标题字体大小", font_size=10, bold=False)
        title_size_layout.addWidget(title_size_label)
        self.bulk_title_size = create_styled_spinbox(min_value=8, max_value=40, default_value=16)
        title_size_layout.addWidget(self.bulk_title_size)
        center_layout.addLayout(title_size_layout)
        center_layout.addSpacing(5)

        # 纵坐标名称
        ylabel_name_layout = QHBoxLayout()
        ylabel_name_label = create_styled_label("纵坐标名称", font_size=10, bold=False)
        ylabel_name_layout.addWidget(ylabel_name_label)
        self.bulk_ylabel_name = create_styled_line_edit(fixed_width=160)
        ylabel_name_layout.addWidget(self.bulk_ylabel_name)
        center_layout.addLayout(ylabel_name_layout)
        center_layout.addSpacing(5)

        # 坐标字体大小
        axis_size_layout = QHBoxLayout()
        axis_size_label = create_styled_label("坐标字体大小", font_size=10, bold=False)
        axis_size_layout.addWidget(axis_size_label)
        self.bulk_axis_size = create_styled_spinbox(min_value=8, max_value=30, default_value=12)
        axis_size_layout.addWidget(self.bulk_axis_size)
        center_layout.addLayout(axis_size_layout)
        center_layout.addSpacing(5)

        # 组间比较字体大小
        pairwise_size_layout = QHBoxLayout()
        pairwise_size_label = create_styled_label("组间比较字体", font_size=10, bold=False)
        pairwise_size_layout.addWidget(pairwise_size_label)
        self.bulk_pairwise_size = create_styled_spinbox(min_value=8, max_value=30, default_value=11)
        pairwise_size_layout.addWidget(self.bulk_pairwise_size)
        center_layout.addLayout(pairwise_size_layout)
        center_layout.addSpacing(5)

        # 组间比较选择框架
        pairwise_frame = QFrame()
        pairwise_frame.setObjectName("styled_panel_pairwise")
        pairwise_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 8px;")
        pairwise_layout = QVBoxLayout(pairwise_frame)
        pairwise_layout.setContentsMargins(5, 5, 5, 5)

        self.bulk_pairwise_enable = create_styled_checkbox("启用组间比较")
        pairwise_layout.addWidget(self.bulk_pairwise_enable)

        self.bulk_pairwise_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        pairwise_layout.addWidget(self.bulk_pairwise_list)

        pairwise_select_all_btn = create_styled_button("全选", font_size=9)
        pairwise_layout.addWidget(pairwise_select_all_btn)

        center_layout.addWidget(pairwise_frame)

        # 全局比较字体大小
        global_size_layout = QHBoxLayout()
        global_size_label = create_styled_label("全局比较字体", font_size=10, bold=False)
        global_size_layout.addWidget(global_size_label)
        self.bulk_global_size = create_styled_spinbox(min_value=8, max_value=30, default_value=12)
        global_size_layout.addWidget(self.bulk_global_size)
        center_layout.addLayout(global_size_layout)

        # 全局比较勾选框
        self.bulk_global_check = create_styled_checkbox("是否开启全局比较")
        center_layout.addWidget(self.bulk_global_check)

        # 显著性显示设置
        sig_setting_label = create_styled_label("显著性显示设置", font_size=10, bold=False)
        center_layout.addWidget(sig_setting_label)

        self.bulk_show_insig = create_styled_checkbox("不显著对比是否显示")
        self.bulk_show_insig.setChecked(True)
        center_layout.addWidget(self.bulk_show_insig)

        self.bulk_ns_replace = create_styled_checkbox("不显著对比是否用n.s.代替")
        center_layout.addWidget(self.bulk_ns_replace)

        self.bulk_star_replace = create_styled_checkbox("显著对比是否用*代替数值")
        center_layout.addWidget(self.bulk_star_replace)

        # 生成结果图按钮
        self.bulk_btn_plot = QPushButton("▶ 生成结果图")
        self.bulk_btn_plot.setFont(get_font_for_widget('button', 12, bold=True))
        self.bulk_btn_plot.setStyleSheet(get_stylesheet_for_widget('run_button'))
        center_layout.addWidget(self.bulk_btn_plot)

        center_layout.addStretch()
        main_layout.addWidget(center_panel)

        # 导出面板
        export_panel, export_layout = create_styled_panel(fixed_width=200)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        export_layout.addWidget(export_title)

        export_layout.addSpacing(8)

        # 导出尺寸设置
        export_size_frame = QFrame()
        export_size_frame.setObjectName("styled_panel_export_size")
        export_size_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        export_size_layout = QVBoxLayout(export_size_frame)
        export_size_layout.setContentsMargins(5, 5, 5, 5)

        export_size_label = create_styled_label("导出尺寸", font_size=10, bold=False)
        export_size_layout.addWidget(export_size_label)

        # 宽度行
        width_row = QHBoxLayout()
        width_row.addSpacing(5)

        width_label = create_styled_label("宽度:", font_size=10, bold=False)
        width_row.addWidget(width_label)

        self.bulk_export_width = create_styled_spinbox(min_value=1, max_value=100, default_value=10)
        width_row.addWidget(self.bulk_export_width)

        width_row.addStretch()

        export_size_layout.addLayout(width_row)

        # 高度行
        height_row = QHBoxLayout()
        height_row.addSpacing(5)

        height_label = create_styled_label("高度:", font_size=10, bold=False)
        height_row.addWidget(height_label)

        self.bulk_export_height = create_styled_spinbox(min_value=1, max_value=100, default_value=8)
        height_row.addWidget(self.bulk_export_height)

        height_row.addStretch()

        export_size_layout.addLayout(height_row)
        export_layout.addWidget(export_size_frame)

        export_layout.addSpacing(8)

        # 导出CSV按钮
        self.bulk_btn_export_csv = QPushButton("导出CSV数据")
        self.bulk_btn_export_csv.setFont(get_font_for_widget('button', 10))
        self.bulk_btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        export_layout.addWidget(self.bulk_btn_export_csv)

        # 导出PNG按钮
        self.bulk_btn_export_png = QPushButton("导出全部PNG")
        self.bulk_btn_export_png.setFont(get_font_for_widget('button', 10))
        self.bulk_btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        export_layout.addWidget(self.bulk_btn_export_png)

        # 导出PDF按钮
        self.bulk_btn_export_pdf = QPushButton("导出全部PDF")
        self.bulk_btn_export_pdf.setFont(get_font_for_widget('button', 10))
        self.bulk_btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        export_layout.addWidget(self.bulk_btn_export_pdf)

        export_layout.addStretch()
        main_layout.addWidget(export_panel)

        # 右侧图表区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 标签页
        self.bulk_plot_tabs = create_styled_tab_widget()

        # 箱线小提琴图标签页
        _, self.bulk_violin_box_label = create_styled_image_tab(self.bulk_plot_tabs, "箱线小提琴图")

        # 箱线图标签页
        _, self.bulk_box_label = create_styled_image_tab(self.bulk_plot_tabs, "箱线图")

        # 小提琴图标签页
        _, self.bulk_violin_label = create_styled_image_tab(self.bulk_plot_tabs, "小提琴图")

        right_layout.addWidget(self.bulk_plot_tabs)
        main_layout.addWidget(right_panel, 1)

        self.content_stack.addWidget(self.single_page_container)

    def _build_gene_set_page(self):
        """index 1：基因集分析页（单基因页近副本，输入控件换成基因集四控件，属性名加 bulk_geneset_ 前缀）"""
        styles = get_mod_styles()

        self.geneset_page_container = QWidget()
        main_layout = QHBoxLayout(self.geneset_page_container)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 左侧控制面板
        left_panel, left_layout = create_styled_panel(fixed_width=280)

        # 基因集输入（§2 四控件）
        geneset_label = create_styled_label("基因集输入", font_size=12, bold=True)
        left_layout.addWidget(geneset_label)

        self.bulk_geneset_input_mode_combo = create_styled_combo_box()
        self.bulk_geneset_input_mode_combo.addItems(["外部列表", "手动输入"])
        left_layout.addWidget(self.bulk_geneset_input_mode_combo)

        self.bulk_geneset_file_combo = create_styled_combo_box()
        file_items = list_gene_set_files()
        self.bulk_geneset_file_combo.addItems(file_items)
        self.bulk_geneset_file_combo.setEnabled(bool(file_items))
        left_layout.addWidget(self.bulk_geneset_file_combo)

        self.bulk_geneset_manual_input = create_styled_text_edit(variant='sub')
        self.bulk_geneset_manual_input.setPlaceholderText("每行一个基因")
        self.bulk_geneset_manual_input.setMaximumHeight(80)
        self.bulk_geneset_manual_input.setEnabled(False)
        left_layout.addWidget(self.bulk_geneset_manual_input)

        method_label, method_qbtn = create_labeled_param_with_help(
            "聚合方法", GENE_SET_METHOD_HELP, font_size=12, bold=True)
        method_row = QHBoxLayout()
        method_row.addWidget(method_label)
        method_row.addWidget(method_qbtn)
        method_row.addStretch()
        left_layout.addLayout(method_row)

        self.bulk_geneset_method_combo = create_styled_combo_box()
        for _, mlabel in GENE_SET_METHODS:
            self.bulk_geneset_method_combo.addItem(mlabel)
        left_layout.addWidget(self.bulk_geneset_method_combo)

        # 分类选择下拉框
        clinical_label = create_styled_label("分类列选择", font_size=12, bold=True)
        left_layout.addWidget(clinical_label)

        self.bulk_geneset_clinical_combo = create_styled_combo_box()
        self.bulk_geneset_clinical_combo.addItem("全部")
        left_layout.addWidget(self.bulk_geneset_clinical_combo)

        # 分类列多选列表（当选择"全部"时显示）
        self.bulk_geneset_clinical_col_list_label = create_styled_label("分类列（可多选）", font_size=11, bold=False)
        self.bulk_geneset_clinical_col_list_label.hide()
        left_layout.addWidget(self.bulk_geneset_clinical_col_list_label)

        self.bulk_geneset_clinical_col_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_geneset_clinical_col_list.hide()
        left_layout.addWidget(self.bulk_geneset_clinical_col_list)

        # 组别多选列表（当选择具体分类时显示）
        self.bulk_geneset_group_list_label = create_styled_label("组别（可多选）", font_size=11, bold=False)
        self.bulk_geneset_group_list_label.hide()
        left_layout.addWidget(self.bulk_geneset_group_list_label)

        self.bulk_geneset_group_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_geneset_group_list.hide()
        left_layout.addWidget(self.bulk_geneset_group_list)

        # 筛选1框架
        filter1_frame = QFrame()
        filter1_frame.setObjectName("styled_panel_geneset_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.bulk_geneset_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.bulk_geneset_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.bulk_geneset_filter1_combo = create_styled_combo_box()
        self.bulk_geneset_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.bulk_geneset_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.bulk_geneset_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_geneset_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.bulk_geneset_filter1_list)

        left_layout.addWidget(filter1_frame)

        # 筛选2框架
        filter2_frame = QFrame()
        filter2_frame.setObjectName("styled_panel_geneset_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.bulk_geneset_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.bulk_geneset_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.bulk_geneset_filter2_combo = create_styled_combo_box()
        self.bulk_geneset_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.bulk_geneset_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.bulk_geneset_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_geneset_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.bulk_geneset_filter2_list)

        left_layout.addWidget(filter2_frame)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # 中间参数调整面板（无多基因测定区域）
        center_panel, center_layout = create_styled_panel(fixed_width=280)

        param_title = create_styled_label("参数调整", font_size=14, bold=True)
        center_layout.addWidget(param_title)

        # 标题名称
        title_name_layout = QHBoxLayout()
        title_name_label = create_styled_label("标题名称", font_size=10, bold=False)
        title_name_layout.addWidget(title_name_label)
        self.bulk_geneset_title_name = create_styled_line_edit(fixed_width=160)
        title_name_layout.addWidget(self.bulk_geneset_title_name)
        center_layout.addLayout(title_name_layout)
        center_layout.addSpacing(5)

        # 标题字体大小
        title_size_layout = QHBoxLayout()
        title_size_label = create_styled_label("标题字体大小", font_size=10, bold=False)
        title_size_layout.addWidget(title_size_label)
        self.bulk_geneset_title_size = create_styled_spinbox(min_value=8, max_value=40, default_value=16)
        title_size_layout.addWidget(self.bulk_geneset_title_size)
        center_layout.addLayout(title_size_layout)
        center_layout.addSpacing(5)

        # 纵坐标名称
        ylabel_name_layout = QHBoxLayout()
        ylabel_name_label = create_styled_label("纵坐标名称", font_size=10, bold=False)
        ylabel_name_layout.addWidget(ylabel_name_label)
        self.bulk_geneset_ylabel_name = create_styled_line_edit(fixed_width=160)
        ylabel_name_layout.addWidget(self.bulk_geneset_ylabel_name)
        center_layout.addLayout(ylabel_name_layout)
        center_layout.addSpacing(5)

        # 坐标字体大小
        axis_size_layout = QHBoxLayout()
        axis_size_label = create_styled_label("坐标字体大小", font_size=10, bold=False)
        axis_size_layout.addWidget(axis_size_label)
        self.bulk_geneset_axis_size = create_styled_spinbox(min_value=8, max_value=30, default_value=12)
        axis_size_layout.addWidget(self.bulk_geneset_axis_size)
        center_layout.addLayout(axis_size_layout)
        center_layout.addSpacing(5)

        # 组间比较字体大小
        pairwise_size_layout = QHBoxLayout()
        pairwise_size_label = create_styled_label("组间比较字体", font_size=10, bold=False)
        pairwise_size_layout.addWidget(pairwise_size_label)
        self.bulk_geneset_pairwise_size = create_styled_spinbox(min_value=8, max_value=30, default_value=11)
        pairwise_size_layout.addWidget(self.bulk_geneset_pairwise_size)
        center_layout.addLayout(pairwise_size_layout)
        center_layout.addSpacing(5)

        # 组间比较选择框架
        pairwise_frame = QFrame()
        pairwise_frame.setObjectName("styled_panel_geneset_pairwise")
        pairwise_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 8px;")
        pairwise_layout = QVBoxLayout(pairwise_frame)
        pairwise_layout.setContentsMargins(5, 5, 5, 5)

        self.bulk_geneset_pairwise_enable = create_styled_checkbox("启用组间比较")
        pairwise_layout.addWidget(self.bulk_geneset_pairwise_enable)

        self.bulk_geneset_pairwise_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        pairwise_layout.addWidget(self.bulk_geneset_pairwise_list)

        pairwise_select_all_btn = create_styled_button("全选", font_size=9)
        pairwise_layout.addWidget(pairwise_select_all_btn)

        center_layout.addWidget(pairwise_frame)

        # 全局比较字体大小
        global_size_layout = QHBoxLayout()
        global_size_label = create_styled_label("全局比较字体", font_size=10, bold=False)
        global_size_layout.addWidget(global_size_label)
        self.bulk_geneset_global_size = create_styled_spinbox(min_value=8, max_value=30, default_value=12)
        global_size_layout.addWidget(self.bulk_geneset_global_size)
        center_layout.addLayout(global_size_layout)

        # 全局比较勾选框
        self.bulk_geneset_global_check = create_styled_checkbox("是否开启全局比较")
        center_layout.addWidget(self.bulk_geneset_global_check)

        # 显著性显示设置
        sig_setting_label = create_styled_label("显著性显示设置", font_size=10, bold=False)
        center_layout.addWidget(sig_setting_label)

        self.bulk_geneset_show_insig = create_styled_checkbox("不显著对比是否显示")
        self.bulk_geneset_show_insig.setChecked(True)
        center_layout.addWidget(self.bulk_geneset_show_insig)

        self.bulk_geneset_ns_replace = create_styled_checkbox("不显著对比是否用n.s.代替")
        center_layout.addWidget(self.bulk_geneset_ns_replace)

        self.bulk_geneset_star_replace = create_styled_checkbox("显著对比是否用*代替数值")
        center_layout.addWidget(self.bulk_geneset_star_replace)

        # 生成结果图按钮
        self.bulk_geneset_btn_plot = QPushButton("▶ 生成结果图")
        self.bulk_geneset_btn_plot.setFont(get_font_for_widget('button', 12, bold=True))
        self.bulk_geneset_btn_plot.setStyleSheet(get_stylesheet_for_widget('run_button'))
        center_layout.addWidget(self.bulk_geneset_btn_plot)

        center_layout.addStretch()
        main_layout.addWidget(center_panel)

        # 导出面板
        export_panel, export_layout = create_styled_panel(fixed_width=200)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        export_layout.addWidget(export_title)

        export_layout.addSpacing(8)

        # 导出尺寸设置
        export_size_frame = QFrame()
        export_size_frame.setObjectName("styled_panel_geneset_export_size")
        export_size_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        export_size_layout = QVBoxLayout(export_size_frame)
        export_size_layout.setContentsMargins(5, 5, 5, 5)

        export_size_label = create_styled_label("导出尺寸", font_size=10, bold=False)
        export_size_layout.addWidget(export_size_label)

        # 宽度行
        width_row = QHBoxLayout()
        width_row.addSpacing(5)

        width_label = create_styled_label("宽度:", font_size=10, bold=False)
        width_row.addWidget(width_label)

        self.bulk_geneset_export_width = create_styled_spinbox(min_value=1, max_value=100, default_value=10)
        width_row.addWidget(self.bulk_geneset_export_width)

        width_row.addStretch()

        export_size_layout.addLayout(width_row)

        # 高度行
        height_row = QHBoxLayout()
        height_row.addSpacing(5)

        height_label = create_styled_label("高度:", font_size=10, bold=False)
        height_row.addWidget(height_label)

        self.bulk_geneset_export_height = create_styled_spinbox(min_value=1, max_value=100, default_value=8)
        height_row.addWidget(self.bulk_geneset_export_height)

        height_row.addStretch()

        export_size_layout.addLayout(height_row)
        export_layout.addWidget(export_size_frame)

        export_layout.addSpacing(8)

        # 导出CSV按钮
        self.bulk_geneset_btn_export_csv = QPushButton("导出CSV数据")
        self.bulk_geneset_btn_export_csv.setFont(get_font_for_widget('button', 10))
        self.bulk_geneset_btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        export_layout.addWidget(self.bulk_geneset_btn_export_csv)

        # 导出PNG按钮
        self.bulk_geneset_btn_export_png = QPushButton("导出全部PNG")
        self.bulk_geneset_btn_export_png.setFont(get_font_for_widget('button', 10))
        self.bulk_geneset_btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        export_layout.addWidget(self.bulk_geneset_btn_export_png)

        # 导出PDF按钮
        self.bulk_geneset_btn_export_pdf = QPushButton("导出全部PDF")
        self.bulk_geneset_btn_export_pdf.setFont(get_font_for_widget('button', 10))
        self.bulk_geneset_btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        export_layout.addWidget(self.bulk_geneset_btn_export_pdf)

        export_layout.addStretch()
        main_layout.addWidget(export_panel)

        # 右侧图表区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 标签页
        self.bulk_geneset_plot_tabs = create_styled_tab_widget()

        # 箱线小提琴图标签页
        _, self.bulk_geneset_violin_box_label = create_styled_image_tab(self.bulk_geneset_plot_tabs, "箱线小提琴图")

        # 箱线图标签页
        _, self.bulk_geneset_box_label = create_styled_image_tab(self.bulk_geneset_plot_tabs, "箱线图")

        # 小提琴图标签页
        _, self.bulk_geneset_violin_label = create_styled_image_tab(self.bulk_geneset_plot_tabs, "小提琴图")

        right_layout.addWidget(self.bulk_geneset_plot_tabs)
        main_layout.addWidget(right_panel, 1)

        self.content_stack.addWidget(self.geneset_page_container)


class ScalableLabel(QLabel):
    """可缩放的标签控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap = None

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        super().setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled)
