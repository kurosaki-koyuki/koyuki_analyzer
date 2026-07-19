# -*- coding: utf-8 -*-
"""
bulk差异分析界面UI布局脚本 - R版本
只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_spinbox, create_styled_tab_widget,
    create_styled_tab_page, create_styled_table, create_questions_button
)
from script.mods_layer.mod_manager import global_mod_manager


class BulkDiffRPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_diff_page = None
        self.create_page()

    def update_styles(self):
        styles = get_mod_styles()

        title_label = self.bulk_diff_page.findChild(QLabel, "bulk_diff_r_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_diff_page.findChildren(QPushButton):
            if child == self.btn_run_diff:
                continue
            elif child in [self.btn_export_csv, self.btn_export_png]:
                continue
            child.setStyleSheet(button_style)

        self.btn_run_diff.setStyleSheet(get_stylesheet_for_widget('run_button'))
        self.btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))
        self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_diff_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_diff_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_diff_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_diff_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_diff_page.findChildren(QLabel):
            if child.objectName() != "bulk_diff_r_title":
                child.setStyleSheet(label_style)

        table_style = get_stylesheet_for_widget('table')
        for child in self.bulk_diff_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)

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
        for child in self.bulk_diff_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_style)

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
            self.diff_total_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")

        panel_bg = styles.get('sub_panel_bg', styles.get('panel_background', 'rgba(30, 58, 95, 0.5)'))
        panel_border = styles.get('sub_panel_border', styles.get('panel_border_color', '#1E3A5F'))
        panel_radius = styles.get('panel_border_radius', '8px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_diff_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    def create_page(self):
        self.bulk_diff_page = QWidget(self.parent)

        styles = get_mod_styles()
        mod_instance = global_mod_manager.get_current_mod()

        layout = QVBoxLayout(self.bulk_diff_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title_panel, title_layout = create_styled_panel()
        top_layout = QHBoxLayout()

        title_label = QLabel("R版本差异分析")
        title_label.setObjectName("bulk_diff_r_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.bulk_diff_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')

        top_layout.addWidget(music_container)

        top_layout.setStretch(0, 5)
        top_layout.setStretch(1, 1)

        title_layout.addLayout(top_layout)
        layout.addWidget(title_panel)

        inner_main_layout = QHBoxLayout()

        left_panel, left_layout = create_styled_panel(fixed_width=380)

        group_label = create_styled_label("分组选择", font_size=12, bold=True)
        left_layout.addWidget(group_label)

        group_desc_label = create_styled_label("选择用于分组的注释列", font_size=9, bold=False)
        group_desc_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(group_desc_label)

        self.diff_group_combo = create_styled_combo_box()
        left_layout.addWidget(self.diff_group_combo)

        left_layout.addSpacing(5)

        group1_label = create_styled_label("组别1（多选）", font_size=10, bold=True)
        left_layout.addWidget(group1_label)
        self.diff_group1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        left_layout.addWidget(self.diff_group1_list)

        group2_label = create_styled_label("组别2（多选）", font_size=10, bold=True)
        left_layout.addWidget(group2_label)
        self.diff_group2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        left_layout.addWidget(self.diff_group2_list)

        group_list_hint = create_styled_label("在两个列表中分别选择要比较的分组", font_size=9, bold=False)
        group_list_hint.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(group_list_hint)

        left_layout.addSpacing(10)

        filter_label = create_styled_label("样本筛选", font_size=12, bold=True)
        left_layout.addWidget(filter_label)

        filter_desc_label = create_styled_label("可选：筛选特定样本用于分析（多选）", font_size=9, bold=False)
        filter_desc_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(filter_desc_label)

        filter1_col_label = create_styled_label("筛选条件1:", font_size=9, bold=True)
        left_layout.addWidget(filter1_col_label)
        self.diff_filter1_col = create_styled_combo_box()
        left_layout.addWidget(self.diff_filter1_col)
        self.diff_filter1_list = create_styled_list_widget(fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.diff_filter1_list)

        filter2_col_label = create_styled_label("筛选条件2:", font_size=9, bold=True)
        left_layout.addWidget(filter2_col_label)
        self.diff_filter2_col = create_styled_combo_box()
        left_layout.addWidget(self.diff_filter2_col)
        self.diff_filter2_list = create_styled_list_widget(fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.diff_filter2_list)

        left_layout.addSpacing(10)

        param_label = create_styled_label("参数设置", font_size=12, bold=True)
        left_layout.addWidget(param_label)

        method_layout = QHBoxLayout()
        method_label = create_styled_label("检验方法", font_size=10, bold=False)
        self.diff_method_combo = create_styled_combo_box()
        self.diff_method_combo.addItems(["limma t检验", "edgeR"])
        self.diff_method_combo.setCurrentIndex(0)
        self.diff_method_help_btn = create_questions_button(
            "limma适用于微阵列和RNA-seq数据，使用经验贝叶斯方法提高检验效能。\n"
            "edgeR基于负二项分布模型，适用于RNA-seq计数数据。\n"
            "分析前会自动进行标准化处理。"
        )
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.diff_method_combo)
        method_layout.addWidget(self.diff_method_help_btn)
        left_layout.addLayout(method_layout)

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

        self.diff_log = QTextEdit()
        self.diff_log.setReadOnly(True)
        self.diff_log.setMaximumHeight(80)
        self.diff_log.setFont(get_font_for_widget('label', 10))
        self.diff_log.setStyleSheet(get_stylesheet_for_widget('text_edit'))
        left_layout.addWidget(self.diff_log)

        left_layout.addStretch()

        inner_main_layout.addWidget(left_panel, 1)

        right_panel, right_layout = create_styled_panel()

        stats_group = QWidget()
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(4)

        row1_layout = QHBoxLayout()
        self.diff_group1_cell_label = QLabel("组1样本数: 0")
        self.diff_group1_cell_label.setFont(QFont("幼圆", 10))
        self.diff_group1_cell_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#98FB98')};")
        row1_layout.addWidget(self.diff_group1_cell_label)

        row1_layout.addStretch()

        self.diff_group2_cell_label = QLabel("组2样本数: 0")
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

        result_label = create_styled_label("差异基因列表", font_size=12, bold=True)
        right_layout.addWidget(result_label)

        search_layout = QHBoxLayout()
        self.gene_search_input = create_styled_line_edit()
        self.gene_search_input.setPlaceholderText("输入基因名称搜索...")
        search_layout.addWidget(self.gene_search_input)
        self.gene_search_btn = create_styled_button("搜索", font_size=11)
        search_layout.addWidget(self.gene_search_btn)
        right_layout.addLayout(search_layout)

        self.diff_result_tabs = create_styled_tab_widget()
        right_layout.addWidget(self.diff_result_tabs)

        self.diff_table_all_page, self.diff_table_all_layout = create_styled_tab_page(self.diff_result_tabs, "总体列表")
        self.diff_result_table = create_styled_table()
        self.diff_table_all_layout.addWidget(self.diff_result_table)
        self.diff_result_table.setColumnCount(8)
        self.diff_result_table.setHorizontalHeaderLabels([
            "gene", "mean_group1", "mean_group2", "log2FC",
            "p_val", "adj_p_val", "significant", "direction"
        ])

        self.diff_table_up_page, self.diff_table_up_layout = create_styled_tab_page(self.diff_result_tabs, "显著上调")
        self.diff_result_table_up = create_styled_table()
        self.diff_table_up_layout.addWidget(self.diff_result_table_up)
        self.diff_result_table_up.setColumnCount(8)
        self.diff_result_table_up.setHorizontalHeaderLabels([
            "gene", "mean_group1", "mean_group2", "log2FC",
            "p_val", "adj_p_val", "significant", "direction"
        ])

        self.diff_table_down_page, self.diff_table_down_layout = create_styled_tab_page(self.diff_result_tabs, "显著下调")
        self.diff_result_table_down = create_styled_table()
        self.diff_table_down_layout.addWidget(self.diff_result_table_down)
        self.diff_result_table_down.setColumnCount(8)
        self.diff_result_table_down.setHorizontalHeaderLabels([
            "gene", "mean_group1", "mean_group2", "log2FC",
            "p_val", "adj_p_val", "significant", "direction"
        ])

        self.diff_volcano_page, self.diff_volcano_layout = create_styled_tab_page(self.diff_result_tabs, "火山图")
        self.diff_volcano_label = QLabel()
        self.diff_volcano_label.setStyleSheet(f"border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; background: {styles.get('sub_fill_color', 'rgba(0,0,0,0.3)')};")
        self.diff_volcano_label.setAlignment(Qt.AlignCenter)
        self.diff_volcano_layout.addWidget(self.diff_volcano_label)

        inner_main_layout.addWidget(right_panel, 3)

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

        layout.addLayout(inner_main_layout)

        self.update_styles()

        return self.bulk_diff_page