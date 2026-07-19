# -*- coding: utf-8 -*-
"""
差异分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget, create_styled_button, create_styled_combo_box, create_styled_line_edit, create_styled_label, create_styled_panel, create_styled_list_widget, create_styled_checkbox, create_styled_spinbox, create_styled_tab_widget, create_styled_tab_page, create_styled_table, create_navigation_panel, create_navigation_button, create_navigation_divider, create_navigation_header, create_questions_button
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class DiffPageUI:
    """差异分析页面 UI 类"""
    
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()
    
    def update_background(self):
        """更新背景图"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.diff_page.findChild(QLabel, "diff_bg")
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
        
        title_label = self.diff_page.findChild(QLabel, "diff_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        
        # 只更新样式，不修改控件尺寸
        # 注意：QSpinBox、QCheckBox、QListWidget等控件现在通过style层的create_styled_*函数创建
        # 样式已经在创建时设置好了，不需要在这里重复设置
        
        # 更新按钮样式
        button_style = get_stylesheet_for_widget('button')
        for child in self.diff_page.findChildren(QPushButton):
            # 特殊按钮保持自己的样式
            if child.objectName() and child.objectName().startswith("number_input_btn_"):
                continue  # 数字输入框按钮保持自己的样式
            if child == self.btn_run_diff:
                continue  # 运行按钮保持run_button样式
            elif child in [self.btn_export_csv, self.btn_export_png]:
                continue  # 导出按钮保持export_button样式
            elif hasattr(self, 'nav_btn_back') and child == self.nav_btn_back:
                continue  # 导航按钮保持自己的样式
            elif hasattr(self, 'nav_btn_python') and child == self.nav_btn_python:
                continue  # 导航按钮保持自己的样式
            elif hasattr(self, 'nav_btn_r') and child == self.nav_btn_r:
                continue  # R版本导航按钮保持自己的样式
            child.setStyleSheet(button_style)
        
        # 重新应用特殊按钮样式
        self.btn_run_diff.setStyleSheet(get_stylesheet_for_widget('run_button'))
        self.btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        
        combo_style = get_stylesheet_for_widget('combo')
        for child in self.diff_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)
        
        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.diff_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)
        
        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.diff_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)
        
        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.diff_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)
        
        label_style = get_stylesheet_for_widget('label')
        for child in self.diff_page.findChildren(QLabel):
            if child.objectName() != "diff_title":
                child.setStyleSheet(label_style)
        
        # 更新表格样式
        table_style = get_stylesheet_for_widget('table')
        for child in self.diff_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)
        
        # 更新标签页样式
        primary_color = styles.get('sub_text_color', styles.get('text_color', '#87CEEB'))
        secondary_color = styles.get('sub_border_color', styles.get('border_color', '#1E3A5F'))
        dark_bg = styles.get('sub_fill_alt', styles.get('fill_alt', 'rgba(30, 58, 95, 0.6)'))
        hover_color = styles.get('sub_hover_color', styles.get('hover_color', 'rgba(30, 58, 95, 0.5)'))
        tab_selected_bg = styles.get('sub_active_color', styles.get('active_color', 'rgba(135, 206, 235, 0.2)'))
        tab_style = f"""
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
        for child in self.diff_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_style)
        
        # 更新统计标签颜色
        if hasattr(self, 'diff_group1_cell_label'):
            self.diff_group1_cell_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#98FB98')};")
        if hasattr(self, 'diff_group2_cell_label'):
            self.diff_group2_cell_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#FFB6C1')};")
        if hasattr(self, 'diff_up_label'):
            self.diff_up_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#FF6B35')};")
        if hasattr(self, 'diff_down_label'):
            self.diff_down_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        if hasattr(self, 'diff_stable_label'):
            self.diff_stable_label.setStyleSheet(f"color: {styles.get('sub_border_color', '#666666')};")
        if hasattr(self, 'diff_total_label'):
            self.diff_total_label.setStyleSheet(f"color: {primary_color};")
        
        panel_bg = styles.get('sub_panel_bg', styles.get('panel_background', 'rgba(30, 58, 95, 0.5)'))
        panel_border = styles.get('sub_panel_border', styles.get('panel_border_color', '#1E3A5F'))
        panel_radius = styles.get('panel_border_radius', '8px')
        
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.diff_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)
        
        overlay = self.diff_page.findChild(QWidget, "diff_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")
    
    def create_page(self):
        """创建差异分析页面"""
        self.diff_page = QWidget(self.parent)
        
        styles = get_mod_styles()
        paths = get_mod_paths()
        
        # ========== 1. 背景层 ==========
        bg_label = QLabel(self.diff_page)
        bg_label.setObjectName("diff_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height, 
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()
        
        # ========== 2. 遮罩层 ==========
        overlay = QWidget(self.diff_page)
        overlay.setObjectName("diff_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")
        
        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ========== 3. 左侧导航栏 ==========
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)
        
        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)
        
        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        nav_layout.addSpacing(10)
        
        nav_layout.addWidget(create_navigation_header("分析方法", font_size=11, parent=nav_panel))
        
        self.nav_btn_python = create_navigation_button("Python版本", font_size=13, parent=nav_panel)
        self.nav_btn_python.setChecked(True)
        nav_layout.addWidget(self.nav_btn_python)
        
        self.nav_btn_r = create_navigation_button("R版本", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_r)
        
        nav_layout.addStretch()
        
        main_layout.addWidget(nav_panel)
        
        # ========== 4. 右侧内容区 ==========
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # ---- 顶部栏（标题 + 音乐控制） ----
        title_panel, title_layout = create_styled_panel()
        top_layout = QHBoxLayout()
        
        title_label = QLabel("Python版本差异基因分析")
        title_label.setObjectName("diff_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)
        
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.diff_page, mod_instance)
        
        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')
        
        music_container_x = styles.get('music_container_x', 0.85)
        music_container_y = styles.get('music_container_y', 15)
        if isinstance(music_container_x, float):
            music_container_x = int(self.screen_width * music_container_x)
        music_container.move(music_container_x, music_container_y)
        
        top_layout.addWidget(music_container)
        
        top_layout.setStretch(0, 5)
        top_layout.setStretch(1, 1)
        
        title_layout.addLayout(top_layout)
        content_layout.addWidget(title_panel)
        
        # ---- 主内容区（左侧控制 + 右侧结果） ----
        inner_main_layout = QHBoxLayout()
        
        # ---- 左侧控制面板 ----
        left_panel, left_layout = create_styled_panel(fixed_width=380)
        
        # 【分组选择】
        group_label = create_styled_label("分组选择", font_size=12, bold=True)
        left_layout.addWidget(group_label)
        
        group_desc_label = create_styled_label("选择用于分组的注释列", font_size=9, bold=False)
        group_desc_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(group_desc_label)
        
        # 分组下拉框（选择注释列）
        self.diff_group_combo = create_styled_combo_box()
        left_layout.addWidget(self.diff_group_combo)
        
        left_layout.addSpacing(5)
        
        # 组别1选择框
        group1_label = create_styled_label("组别1（多选）", font_size=10, bold=True)
        left_layout.addWidget(group1_label)
        self.diff_group1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        left_layout.addWidget(self.diff_group1_list)
        
        # 组别2选择框
        group2_label = create_styled_label("组别2（多选）", font_size=10, bold=True)
        left_layout.addWidget(group2_label)
        self.diff_group2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        left_layout.addWidget(self.diff_group2_list)
        
        group_list_hint = create_styled_label("在两个列表中分别选择要比较的分组", font_size=9, bold=False)
        group_list_hint.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(group_list_hint)
        
        left_layout.addSpacing(10)
        
        # 【细胞筛选】
        filter_label = create_styled_label("细胞筛选", font_size=12, bold=True)
        left_layout.addWidget(filter_label)
        
        filter_desc_label = create_styled_label("可选：筛选特定细胞用于分析（多选）", font_size=9, bold=False)
        filter_desc_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(filter_desc_label)
        
        # 筛选条件1：列选择 + 多选列表
        filter1_col_label = create_styled_label("筛选条件1:", font_size=9, bold=True)
        left_layout.addWidget(filter1_col_label)
        self.diff_filter1_col = create_styled_combo_box()
        left_layout.addWidget(self.diff_filter1_col)
        self.diff_filter1_list = create_styled_list_widget(fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.diff_filter1_list)
        
        # 筛选条件2：列选择 + 多选列表
        filter2_col_label = create_styled_label("筛选条件2:", font_size=9, bold=True)
        left_layout.addWidget(filter2_col_label)
        self.diff_filter2_col = create_styled_combo_box()
        left_layout.addWidget(self.diff_filter2_col)
        self.diff_filter2_list = create_styled_list_widget(fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.diff_filter2_list)
        
        left_layout.addSpacing(10)
        
        # 【参数设置】
        param_label = create_styled_label("参数设置", font_size=12, bold=True)
        left_layout.addWidget(param_label)
        
        # 检验方法
        method_layout = QHBoxLayout()
        method_label = create_styled_label("检验方法", font_size=10, bold=False)
        self.diff_method_combo = create_styled_combo_box()
        self.diff_method_combo.addItems(["Mann-Whitney U检验"])
        self.diff_method_combo.setCurrentIndex(0)
        self.diff_method_combo.setEnabled(False)
        self.diff_method_help_btn = create_questions_button(
            "Mann-Whitney U 检验是非参数检验方法，适用于单细胞差异表达分析。\n"
            "该方法对数据分布假设要求较低，稳定性好，结果可靠。\n"
            "分析前会自动进行CP10K标准化和log1p转换。"
        )
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.diff_method_combo)
        method_layout.addWidget(self.diff_method_help_btn)
        left_layout.addLayout(method_layout)
        
        # 最小表达细胞数
        min_cells_layout = QHBoxLayout()
        min_cells_label = create_styled_label("最小表达细胞数", font_size=10, bold=False)
        self.diff_min_cells = create_styled_spinbox(min_value=1, max_value=1000, default_value=3)
        min_cells_layout.addWidget(min_cells_label)
        min_cells_layout.addWidget(self.diff_min_cells)
        left_layout.addLayout(min_cells_layout)
        
        # 最小表达量
        min_expr_layout = QHBoxLayout()
        min_expr_label = create_styled_label("最小表达量", font_size=10, bold=False)
        self.diff_min_expr = create_styled_spinbox(min_value=0, max_value=100, default_value=0)
        min_expr_layout.addWidget(min_expr_label)
        min_expr_layout.addWidget(self.diff_min_expr)
        left_layout.addLayout(min_expr_layout)
        
        # p值阈值
        pval_layout = QHBoxLayout()
        pval_label = create_styled_label("p值阈值", font_size=10, bold=False)
        self.diff_pval_spin = QDoubleSpinBox()
        self.diff_pval_spin.setFont(get_font_for_widget('label', 9))
        self.diff_pval_spin.setRange(0.001, 0.1)
        self.diff_pval_spin.setSingleStep(0.001)
        self.diff_pval_spin.setValue(0.05)
        self.diff_pval_spin.setStyleSheet(get_stylesheet_for_widget('spinbox'))
        pval_layout.addWidget(pval_label)
        pval_layout.addWidget(self.diff_pval_spin)
        left_layout.addLayout(pval_layout)
        
        # log2FC阈值
        logfc_layout = QHBoxLayout()
        logfc_label = create_styled_label("log2FC阈值", font_size=10, bold=False)
        self.diff_logfc_spin = QDoubleSpinBox()
        self.diff_logfc_spin.setFont(get_font_for_widget('label', 9))
        self.diff_logfc_spin.setRange(0, 2.0)
        self.diff_logfc_spin.setSingleStep(0.05)
        self.diff_logfc_spin.setValue(0.25)
        self.diff_logfc_spin.setStyleSheet(get_stylesheet_for_widget('spinbox'))
        logfc_layout.addWidget(logfc_label)
        logfc_layout.addWidget(self.diff_logfc_spin)
        left_layout.addLayout(logfc_layout)
        
        # 表达量百分比阈值
        pct_layout = QHBoxLayout()
        pct_label = create_styled_label("表达量百分比阈值", font_size=10, bold=False)
        self.diff_pct_spin = QDoubleSpinBox()
        self.diff_pct_spin.setFont(get_font_for_widget('label', 9))
        self.diff_pct_spin.setRange(0.0, 1.0)
        self.diff_pct_spin.setSingleStep(0.05)
        self.diff_pct_spin.setValue(0.1)
        self.diff_pct_spin.setStyleSheet(get_stylesheet_for_widget('spinbox'))
        pct_layout.addWidget(pct_label)
        pct_layout.addWidget(self.diff_pct_spin)
        left_layout.addLayout(pct_layout)
        
        # FDR校正
        self.diff_use_fdr = create_styled_checkbox("使用FDR校正")
        self.diff_use_fdr.setChecked(True)
        left_layout.addWidget(self.diff_use_fdr)
        
        # 日志面板
        self.diff_log = QTextEdit()
        self.diff_log.setReadOnly(True)
        self.diff_log.setMaximumHeight(80)
        self.diff_log.setFont(get_font_for_widget('label', 10))
        self.diff_log.setStyleSheet(get_stylesheet_for_widget('text_edit'))
        left_layout.addWidget(self.diff_log)
        
        left_layout.addStretch()
        
        inner_main_layout.addWidget(left_panel, 1)
        
        # ---- 右侧结果面板 ----
        right_panel, right_layout = create_styled_panel()
        
        # ===== 分析结果统计面板 =====
        stats_group = QWidget()
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(4)
        
        row1_layout = QHBoxLayout()
        self.diff_group1_cell_label = QLabel("组1细胞数: 0")
        self.diff_group1_cell_label.setFont(QFont("幼圆", 10))
        self.diff_group1_cell_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#98FB98')};")
        row1_layout.addWidget(self.diff_group1_cell_label)
        
        row1_layout.addStretch()
        
        self.diff_group2_cell_label = QLabel("组2细胞数: 0")
        self.diff_group2_cell_label.setFont(QFont("幼圆", 10))
        self.diff_group2_cell_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#FFB6C1')};")
        row1_layout.addWidget(self.diff_group2_cell_label)
        stats_layout.addLayout(row1_layout)
        
        row2_layout = QHBoxLayout()
        self.diff_up_label = QLabel("组1显著上调: 0")
        self.diff_up_label.setFont(QFont("幼圆", 10))
        self.diff_up_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#FF6B35')};")
        row2_layout.addWidget(self.diff_up_label)
        
        row2_layout.addStretch()
        
        self.diff_down_label = QLabel("组1显著下调: 0")
        self.diff_down_label.setFont(QFont("幼圆", 10))
        self.diff_down_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        row2_layout.addWidget(self.diff_down_label)
        stats_layout.addLayout(row2_layout)
        
        row3_layout = QHBoxLayout()
        self.diff_stable_label = QLabel("稳定基因: 0")
        self.diff_stable_label.setFont(QFont("幼圆", 10))
        self.diff_stable_label.setStyleSheet(f"color: {styles.get('sub_border_color', '#666666')};")
        row3_layout.addWidget(self.diff_stable_label)
        
        row3_layout.addStretch()
        
        self.diff_total_label = QLabel("总基因: 0")
        self.diff_total_label.setFont(QFont("幼圆", 10))
        self.diff_total_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        row3_layout.addWidget(self.diff_total_label)
        stats_layout.addLayout(row3_layout)
        
        right_layout.addWidget(stats_group)
        
        # 结果表格（使用标签页展示不同类型）
        result_label = create_styled_label("差异基因列表", font_size=12, bold=True)
        right_layout.addWidget(result_label)

        search_layout = QHBoxLayout()
        self.gene_search_input = create_styled_line_edit()
        self.gene_search_input.setPlaceholderText("输入基因名称搜索...")
        search_layout.addWidget(self.gene_search_input)
        self.gene_search_btn = create_styled_button("搜索", font_size=11)
        search_layout.addWidget(self.gene_search_btn)
        right_layout.addLayout(search_layout)
        
        # 创建标签页
        self.diff_result_tabs = create_styled_tab_widget()
        right_layout.addWidget(self.diff_result_tabs)
        
        # 总体差异分析列表
        self.diff_table_all_page, self.diff_table_all_layout = create_styled_tab_page(self.diff_result_tabs, "总体列表")
        self.diff_result_table = create_styled_table()
        self.diff_table_all_layout.addWidget(self.diff_result_table)
        self.diff_result_table.setColumnCount(10)
        self.diff_result_table.setHorizontalHeaderLabels([
            "基因", "mean_CP10K_group1", "mean_CP10K_group2", "log2FC",
            "pct_expr_group1", "pct_expr_group2", "p_val", "p_val_adj",
            "n_cells_group1", "n_cells_group2"
        ])
        
        # 显著上调基因
        self.diff_table_up_page, self.diff_table_up_layout = create_styled_tab_page(self.diff_result_tabs, "显著上调")
        self.diff_result_table_up = create_styled_table()
        self.diff_table_up_layout.addWidget(self.diff_result_table_up)
        self.diff_result_table_up.setColumnCount(10)
        self.diff_result_table_up.setHorizontalHeaderLabels([
            "基因", "mean_CP10K_group1", "mean_CP10K_group2", "log2FC",
            "pct_expr_group1", "pct_expr_group2", "p_val", "p_val_adj",
            "n_cells_group1", "n_cells_group2"
        ])
        
        # 显著下调基因
        self.diff_table_down_page, self.diff_table_down_layout = create_styled_tab_page(self.diff_result_tabs, "显著下调")
        self.diff_result_table_down = create_styled_table()
        self.diff_table_down_layout.addWidget(self.diff_result_table_down)
        self.diff_result_table_down.setColumnCount(10)
        self.diff_result_table_down.setHorizontalHeaderLabels([
            "基因", "mean_CP10K_group1", "mean_CP10K_group2", "log2FC",
            "pct_expr_group1", "pct_expr_group2", "p_val", "p_val_adj",
            "n_cells_group1", "n_cells_group2"
        ])
        
        # 火山图页
        self.diff_volcano_page, self.diff_volcano_layout = create_styled_tab_page(self.diff_result_tabs, "火山图")
        self.diff_volcano_label = QLabel()
        self.diff_volcano_label.setStyleSheet(f"border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; background: {styles.get('sub_fill_color', 'rgba(0,0,0,0.3)')};")
        self.diff_volcano_label.setAlignment(Qt.AlignCenter)
        self.diff_volcano_layout.addWidget(self.diff_volcano_label)
        
        inner_main_layout.addWidget(right_panel, 3)
        
        # ---- 最右侧运行区域 ----
        run_panel, run_layout = create_styled_panel(fixed_width=200)
        
        run_title = create_styled_label("运行区域", font_size=12, bold=True)
        run_layout.addWidget(run_title)
        
        run_layout.addSpacing(10)
        
        self.btn_run_diff = create_styled_button("▶ 执行差异分析", font_size=11, button_type='run')
        run_layout.addWidget(self.btn_run_diff)
        
        run_layout.addSpacing(10)
        
        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        run_layout.addWidget(export_title)
        
        run_layout.addSpacing(8)
        
        self.btn_export_csv = create_styled_button("导出Excel", font_size=10, button_type='export')
        run_layout.addWidget(self.btn_export_csv)
        
        self.btn_export_png = create_styled_button("导出火山图", font_size=10, button_type='export')
        run_layout.addWidget(self.btn_export_png)
        
        run_layout.addStretch()
        
        inner_main_layout.addWidget(run_panel)
        
        content_layout.addLayout(inner_main_layout)
        
        main_layout.addWidget(content_panel)
        
        # 初始化完成后立即应用样式
        self.update_styles()
