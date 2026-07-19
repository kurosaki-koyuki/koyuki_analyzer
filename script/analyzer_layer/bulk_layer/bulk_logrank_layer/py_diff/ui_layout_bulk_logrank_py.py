# -*- coding: utf-8 -*-
"""
bulk Log-rank分析界面UI布局脚本 - Python版本
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


class BulkLogrankPyPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_logrank_page = None
        self.create_page()

    def update_styles(self):
        styles = get_mod_styles()

        title_label = self.bulk_logrank_page.findChild(QLabel, "bulk_logrank_py_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_logrank_page.findChildren(QPushButton):
            if child == self.btn_run_logrank:
                continue
            elif child in [self.btn_export_csv]:
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_run_logrank'):
            self.btn_run_logrank.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_csv'):
            self.btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_logrank_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_logrank_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_logrank_page.findChildren(QLabel):
            if child.objectName() != "bulk_logrank_py_title":
                child.setStyleSheet(label_style)

        table_style = get_stylesheet_for_widget('table')
        for child in self.bulk_logrank_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_logrank_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_logrank_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

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
        for child in self.bulk_logrank_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_logrank_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    def create_page(self):
        self.bulk_logrank_page = QWidget(self.parent)

        styles = get_mod_styles()
        mod_instance = global_mod_manager.get_current_mod()

        layout = QVBoxLayout(self.bulk_logrank_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title_panel, title_layout = create_styled_panel()
        top_layout = QHBoxLayout()

        title_label = QLabel("Log-rank分析")
        title_label.setObjectName("bulk_logrank_py_title")
        title_label.setFont(get_font_for_widget('button', 28, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.bulk_logrank_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')

        top_layout.addWidget(music_container)
        top_layout.setStretch(0, 5)
        top_layout.setStretch(1, 1)
        title_layout.addLayout(top_layout)
        layout.addWidget(title_panel)

        inner_main_layout = QHBoxLayout()

        left_panel, left_layout = create_styled_panel(fixed_width=320)

        clinical_label = create_styled_label("分类列选择", font_size=12, bold=True)
        left_layout.addWidget(clinical_label)

        self.bulk_logrank_clinical_combo = create_styled_combo_box()
        self.bulk_logrank_clinical_combo.addItem("全部")
        left_layout.addWidget(self.bulk_logrank_clinical_combo)

        self.bulk_logrank_clinical_col_list_label = create_styled_label("分类列（可多选）", font_size=11, bold=False)
        self.bulk_logrank_clinical_col_list_label.hide()
        left_layout.addWidget(self.bulk_logrank_clinical_col_list_label)

        self.bulk_logrank_clinical_col_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_logrank_clinical_col_list.hide()
        left_layout.addWidget(self.bulk_logrank_clinical_col_list)

        self.bulk_logrank_group_list_label = create_styled_label("组别（可多选）", font_size=11, bold=False)
        self.bulk_logrank_group_list_label.hide()
        left_layout.addWidget(self.bulk_logrank_group_list_label)

        self.bulk_logrank_group_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_logrank_group_list.hide()
        left_layout.addWidget(self.bulk_logrank_group_list)

        filter1_frame = QFrame()
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.bulk_logrank_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.bulk_logrank_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.bulk_logrank_filter1_combo = create_styled_combo_box()
        self.bulk_logrank_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.bulk_logrank_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.bulk_logrank_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_logrank_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.bulk_logrank_filter1_list)

        left_layout.addWidget(filter1_frame)

        filter2_frame = QFrame()
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.bulk_logrank_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.bulk_logrank_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.bulk_logrank_filter2_combo = create_styled_combo_box()
        self.bulk_logrank_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.bulk_logrank_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.bulk_logrank_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_logrank_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.bulk_logrank_filter2_list)

        left_layout.addWidget(filter2_frame)

        left_layout.addSpacing(10)

        param_label = create_styled_label("参数设置", font_size=12, bold=True)
        left_layout.addWidget(param_label)

        pval_layout = QHBoxLayout()
        pval_label = create_styled_label("p值阈值", font_size=10, bold=False)
        self.bulk_logrank_pval_spin = QDoubleSpinBox()
        self.bulk_logrank_pval_spin.setFont(get_font_for_widget('label', 9))
        self.bulk_logrank_pval_spin.setRange(0.001, 0.1)
        self.bulk_logrank_pval_spin.setSingleStep(0.001)
        self.bulk_logrank_pval_spin.setValue(0.05)
        self.bulk_logrank_pval_spin.setStyleSheet(get_stylesheet_for_widget('spinbox'))
        pval_layout.addWidget(pval_label)
        pval_layout.addWidget(self.bulk_logrank_pval_spin)
        left_layout.addLayout(pval_layout)

        filter_col_label = create_styled_label("过滤依据", font_size=10, bold=False)
        left_layout.addWidget(filter_col_label)
        
        self.bulk_logrank_filter_col_combo = create_styled_combo_box()
        self.bulk_logrank_filter_col_combo.addItem("p值")
        self.bulk_logrank_filter_col_combo.addItem("p_adj值")
        self.bulk_logrank_filter_col_combo.setCurrentIndex(1)
        left_layout.addWidget(self.bulk_logrank_filter_col_combo)

        self.bulk_logrank_use_fdr = create_styled_checkbox("使用FDR校正")
        self.bulk_logrank_use_fdr.setChecked(True)
        left_layout.addWidget(self.bulk_logrank_use_fdr)

        self.bulk_logrank_log = QTextEdit()
        self.bulk_logrank_log.setReadOnly(True)
        self.bulk_logrank_log.setMaximumHeight(80)
        self.bulk_logrank_log.setFont(get_font_for_widget('label', 10))
        self.bulk_logrank_log.setStyleSheet(get_stylesheet_for_widget('text_edit'))
        left_layout.addWidget(self.bulk_logrank_log)

        left_layout.addStretch()
        inner_main_layout.addWidget(left_panel, 1)

        right_panel, right_layout = create_styled_panel()

        stats_group = QWidget()
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(4)

        row1_layout = QHBoxLayout()
        self.bulk_logrank_high_cell_label = QLabel("高表达组样本数: 0")
        self.bulk_logrank_high_cell_label.setFont(QFont("幼圆", 10))
        self.bulk_logrank_high_cell_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#98FB98')};")
        row1_layout.addWidget(self.bulk_logrank_high_cell_label)
        row1_layout.addStretch()
        self.bulk_logrank_low_cell_label = QLabel("低表达组样本数: 0")
        self.bulk_logrank_low_cell_label.setFont(QFont("幼圆", 10))
        self.bulk_logrank_low_cell_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#FFB6C1')};")
        row1_layout.addWidget(self.bulk_logrank_low_cell_label)
        stats_layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        self.bulk_logrank_favorable_label = QLabel("良好预后基因: 0")
        self.bulk_logrank_favorable_label.setFont(QFont("幼圆", 10))
        self.bulk_logrank_favorable_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#FF6B35')};")
        row2_layout.addWidget(self.bulk_logrank_favorable_label)
        row2_layout.addStretch()
        self.bulk_logrank_unfavorable_label = QLabel("不良预后基因: 0")
        self.bulk_logrank_unfavorable_label.setFont(QFont("幼圆", 10))
        self.bulk_logrank_unfavorable_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        row2_layout.addWidget(self.bulk_logrank_unfavorable_label)
        stats_layout.addLayout(row2_layout)

        row3_layout = QHBoxLayout()
        self.bulk_logrank_not_significant_label = QLabel("不显著基因: 0")
        self.bulk_logrank_not_significant_label.setFont(QFont("幼圆", 10))
        self.bulk_logrank_not_significant_label.setStyleSheet(f"color: {styles.get('sub_border_color', '#666666')};")
        row3_layout.addWidget(self.bulk_logrank_not_significant_label)
        row3_layout.addStretch()
        self.bulk_logrank_total_label = QLabel("总基因: 0")
        self.bulk_logrank_total_label.setFont(QFont("幼圆", 10))
        self.bulk_logrank_total_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        row3_layout.addWidget(self.bulk_logrank_total_label)
        stats_layout.addLayout(row3_layout)

        right_layout.addWidget(stats_group)

        result_label = create_styled_label("Log-rank分析结果", font_size=12, bold=True)
        right_layout.addWidget(result_label)

        search_layout = QHBoxLayout()
        self.gene_search_input = create_styled_line_edit()
        self.gene_search_input.setPlaceholderText("输入基因名称搜索...")
        search_layout.addWidget(self.gene_search_input)
        self.gene_search_btn = create_styled_button("搜索", font_size=11)
        search_layout.addWidget(self.gene_search_btn)
        right_layout.addLayout(search_layout)

        self.bulk_logrank_result_tabs = create_styled_tab_widget()
        right_layout.addWidget(self.bulk_logrank_result_tabs)

        self.bulk_logrank_table_all_page, self.bulk_logrank_table_all_layout = create_styled_tab_page(self.bulk_logrank_result_tabs, "总体列表")
        self.bulk_logrank_result_table = create_styled_table()
        self.bulk_logrank_table_all_layout.addWidget(self.bulk_logrank_result_table)
        self.bulk_logrank_result_table.setColumnCount(7)
        self.bulk_logrank_result_table.setHorizontalHeaderLabels([
            "基因", "median_high", "median_low", "HR", "p_val", "p_val_adj", "prognosis"
        ])

        self.bulk_logrank_table_favorable_page, self.bulk_logrank_table_favorable_layout = create_styled_tab_page(self.bulk_logrank_result_tabs, "良好预后")
        self.bulk_logrank_result_table_favorable = create_styled_table()
        self.bulk_logrank_table_favorable_layout.addWidget(self.bulk_logrank_result_table_favorable)
        self.bulk_logrank_result_table_favorable.setColumnCount(7)
        self.bulk_logrank_result_table_favorable.setHorizontalHeaderLabels([
            "基因", "median_high", "median_low", "HR", "p_val", "p_val_adj", "prognosis"
        ])

        self.bulk_logrank_table_unfavorable_page, self.bulk_logrank_table_unfavorable_layout = create_styled_tab_page(self.bulk_logrank_result_tabs, "不良预后")
        self.bulk_logrank_result_table_unfavorable = create_styled_table()
        self.bulk_logrank_table_unfavorable_layout.addWidget(self.bulk_logrank_result_table_unfavorable)
        self.bulk_logrank_result_table_unfavorable.setColumnCount(7)
        self.bulk_logrank_result_table_unfavorable.setHorizontalHeaderLabels([
            "基因", "median_high", "median_low", "HR", "p_val", "p_val_adj", "prognosis"
        ])

        inner_main_layout.addWidget(right_panel, 3)

        run_panel, run_layout = create_styled_panel(fixed_width=200)

        run_title = create_styled_label("运行区域", font_size=12, bold=True)
        run_layout.addWidget(run_title)

        run_layout.addSpacing(10)

        self.btn_run_logrank = create_styled_button("▶ 执行Log-rank分析", font_size=11, button_type='run')
        run_layout.addWidget(self.btn_run_logrank)

        run_layout.addSpacing(10)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        run_layout.addWidget(export_title)

        run_layout.addSpacing(8)

        self.btn_export_csv = create_styled_button("导出Excel", font_size=10, button_type='export')
        run_layout.addWidget(self.btn_export_csv)

        run_layout.addStretch()

        inner_main_layout.addWidget(run_panel)

        layout.addLayout(inner_main_layout)

        return self.bulk_logrank_page