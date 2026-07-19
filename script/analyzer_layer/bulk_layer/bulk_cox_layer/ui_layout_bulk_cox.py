# -*- coding: utf-8 -*-
"""
bulk COX分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
参考WGCNA界面布局模式
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_tab_widget, create_styled_tab_page,
    create_styled_table, create_styled_text_edit,
    create_questions_button, create_labeled_param_with_help
)
from script.mods_layer.mod_manager import global_mod_manager


class BulkCoxPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_cox_page.findChild(QLabel, "bulk_cox_bg")
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

        title_label = self.bulk_cox_page.findChild(QLabel, "bulk_cox_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_cox_page.findChildren(QPushButton):
            if child == self.btn_run_cox or child == self.btn_export_csv:
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_run_cox'):
            self.btn_run_cox.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_csv'):
            self.btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_cox_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_cox_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_cox_page.findChildren(QLabel):
            if child.objectName() != "bulk_cox_title":
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_cox_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        table_style = get_stylesheet_for_widget('table')
        for child in self.bulk_cox_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_cox_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        spinbox_style = get_stylesheet_for_widget('spinbox')
        for child in self.bulk_cox_page.findChildren(QSpinBox):
            child.setStyleSheet(spinbox_style)
        for child in self.bulk_cox_page.findChildren(QDoubleSpinBox):
            child.setStyleSheet(spinbox_style)

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
        for child in self.bulk_cox_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_cox_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.bulk_cox_page.findChild(QWidget, "bulk_cox_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        if hasattr(self, 'r_version_label'):
            self.r_version_label.setStyleSheet(label_style)

    def create_page(self):
        self.bulk_cox_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.bulk_cox_page)
        bg_label.setObjectName("bulk_cox_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.bulk_cox_page)
        overlay.setObjectName("bulk_cox_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 顶部标题栏 ===
        top_layout = QHBoxLayout()

        self.btn_back = create_styled_button("← 返回bulk主页", font_size=12)
        top_layout.addWidget(self.btn_back)

        title_label = QLabel("COX回归分析")
        title_label.setObjectName("bulk_cox_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        self.r_version_label = create_styled_label("R版本: 检测中...", font_size=10, bold=False)
        top_layout.addWidget(self.r_version_label)

        top_layout.setStretch(0, 1)
        top_layout.setStretch(1, 3)
        top_layout.setStretch(2, 1)
        layout.addLayout(top_layout)

        # === 状态区域 ===
        status_layout = QHBoxLayout()
        self.bulk_cox_status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.bulk_cox_status_text.setMaximumHeight(80)
        status_layout.addWidget(self.bulk_cox_status_text)
        layout.addLayout(status_layout)

        # === 主内容区域（三栏） ===
        main_layout = QHBoxLayout()

        # ================ 左侧参数面板 ================
        left_panel, left_layout = create_styled_panel()
        left_panel.setMinimumWidth(280)
        left_panel.setMaximumWidth(320)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_content = QWidget()
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setContentsMargins(0, 0, 0, 0)

        # --- 分析模式设置 ---
        mode_group = QFrame()
        mode_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mode_group.setObjectName("styled_panel_mode")
        mode_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(8, 8, 8, 8)

        mode_title_row = QHBoxLayout()
        mode_title = create_styled_label("分析模式", font_size=12, bold=True)
        mode_title_row.addWidget(mode_title)
        self.bulk_cox_mode_help_btn = create_questions_button("""COX回归分析模式说明

【单因素COX回归】（推荐先做）
- 模型公式: Surv(time, event) ~ gene_expression_zscore
- 每个基因独立做一次COX回归，不考虑其他因素
- 用于全基因组筛选，找出与生存显著相关的基因
- 结果解读:
  - HR > 1: 高表达与不良预后相关（风险基因）
  - HR < 1: 高表达与良好预后相关（保护基因）

【多因素COX回归】（校正后验证）
- 模型公式: Surv(time, event) ~ gene_expression_zscore + 临床协变量
- 在单因素基础上加入临床协变量进行校正
- 用于验证单因素筛选出的基因是否独立于临床因素
- 协变量示例: 年龄、性别、IDH突变状态、MGMT甲基化状态等

注意：多因素模式下需要选择至少一个临床协变量""")
        mode_title_row.addWidget(self.bulk_cox_mode_help_btn)
        mode_layout.addLayout(mode_title_row)

        self.bulk_cox_mode_combo = create_styled_combo_box()
        self.bulk_cox_mode_combo.addItems(["单因素COX回归", "多因素COX回归"])
        mode_layout.addWidget(self.bulk_cox_mode_combo)

        left_content_layout.addWidget(mode_group)
        left_content_layout.addSpacing(8)

        # --- 临床协变量设置（多因素模式） ---
        covariate_group = QFrame()
        covariate_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        covariate_group.setObjectName("styled_panel_covariate")
        covariate_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        covariate_layout = QVBoxLayout(covariate_group)
        covariate_layout.setContentsMargins(8, 8, 8, 8)

        covariate_title_row = QHBoxLayout()
        covariate_title = create_styled_label("临床协变量（多因素模式）", font_size=12, bold=True)
        covariate_title_row.addWidget(covariate_title)
        self.bulk_cox_covariate_help_btn = create_questions_button("""临床协变量选择说明

功能：
- 在多因素COX回归中，选择需要校正的临床因素
- 协变量将被加入模型，控制混杂因素的影响

可选协变量（根据数据而定）：
- 连续变量: age（年龄）
- 分类变量: gender（性别）、grade（分级）、IDH_mutation_status（IDH状态）
             MGMTp_methylation_status（MGMT甲基化）等

选择示例：
- 如果想验证基因表达是否独立于年龄和性别
  选择: age, gender
- 如果想验证基因表达是否独立于分子亚型
  选择: IDH_mutation_status, 1p19q_codeletion_status

注意：
- 单因素模式下此选项不可用
- 建议先做单因素筛选，再用多因素验证""")
        covariate_title_row.addWidget(self.bulk_cox_covariate_help_btn)
        covariate_layout.addLayout(covariate_title_row)

        covariate_label = create_styled_label("协变量列选择", font_size=11, bold=False)
        covariate_layout.addWidget(covariate_label)

        self.bulk_cox_covariate_combo = create_styled_combo_box()
        self.bulk_cox_covariate_combo.setEnabled(False)
        covariate_layout.addWidget(self.bulk_cox_covariate_combo)

        self.bulk_cox_covariate_list_label = create_styled_label("协变量值（可多选）", font_size=11, bold=False)
        self.bulk_cox_covariate_list_label.hide()
        covariate_layout.addWidget(self.bulk_cox_covariate_list_label)

        self.bulk_cox_covariate_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_cox_covariate_list.setEnabled(False)
        self.bulk_cox_covariate_list.hide()
        covariate_layout.addWidget(self.bulk_cox_covariate_list)

        left_content_layout.addWidget(covariate_group)
        left_content_layout.addSpacing(8)

        # --- 基因筛选设置 ---
        gene_filter_group = QFrame()
        gene_filter_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        gene_filter_group.setObjectName("styled_panel_gene_filter")
        gene_filter_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        gene_filter_layout = QVBoxLayout(gene_filter_group)
        gene_filter_layout.setContentsMargins(8, 8, 8, 8)

        gene_filter_title_row = QHBoxLayout()
        gene_filter_title = create_styled_label("基因筛选设置", font_size=12, bold=True)
        gene_filter_title_row.addWidget(gene_filter_title)
        self.bulk_cox_gene_filter_help_btn = create_questions_button("""基因筛选设置说明

功能：
- 控制参与COX分析的基因范围

筛选模式：
1. 全部基因 - 使用表达矩阵中的所有基因进行分析
   - 适用于全基因组筛选
   - 注意：基因数量多时分析较慢

2. 前N个基因 - 按方差或均值筛选表达量最高的前N个基因
   - 推荐值: 5000
   - 目的：去除低表达噪声基因，提高分析效率

3. 自定义基因 - 只分析指定的基因
   - 适用于验证特定基因
   - 输入基因名称，用逗号分隔

注意：
- 调试时建议先用少量基因测试
- 正式分析建议使用前5000个基因或全部基因""")
        gene_filter_title_row.addWidget(self.bulk_cox_gene_filter_help_btn)
        gene_filter_layout.addLayout(gene_filter_title_row)

        gene_filter_mode_label = create_styled_label("筛选模式", font_size=11, bold=False)
        gene_filter_layout.addWidget(gene_filter_mode_label)

        self.bulk_cox_gene_filter_mode_combo = create_styled_combo_box()
        self.bulk_cox_gene_filter_mode_combo.addItems(["全部基因", "前N个基因", "自定义基因", "外部基因列表"])
        gene_filter_layout.addWidget(self.bulk_cox_gene_filter_mode_combo)

        gene_count_row = QHBoxLayout()
        gene_count_label = create_styled_label("基因数量", font_size=10, bold=False)
        gene_count_row.addWidget(gene_count_label)
        self.bulk_cox_gene_count_input = create_styled_line_edit()
        self.bulk_cox_gene_count_input.setText("5000")
        self.bulk_cox_gene_count_input.setMinimumWidth(80)
        self.bulk_cox_gene_count_input.setAlignment(Qt.AlignCenter)
        gene_count_row.addWidget(self.bulk_cox_gene_count_input)
        gene_filter_layout.addLayout(gene_count_row)

        custom_gene_row = QHBoxLayout()
        custom_gene_label = create_styled_label("自定义基因", font_size=10, bold=False)
        custom_gene_row.addWidget(custom_gene_label)
        self.bulk_cox_custom_gene_combo = create_styled_combo_box()
        custom_gene_row.addWidget(self.bulk_cox_custom_gene_combo)
        gene_filter_layout.addLayout(custom_gene_row)

        external_gene_row = QHBoxLayout()
        external_gene_label = create_styled_label("基因列表文件", font_size=10, bold=False)
        external_gene_row.addWidget(external_gene_label)
        self.bulk_cox_external_gene_combo = create_styled_combo_box()
        external_gene_row.addWidget(self.bulk_cox_external_gene_combo)
        self.btn_scan_gene_lists = create_styled_button("扫描", font_size=10)
        self.btn_scan_gene_lists.setMaximumWidth(60)
        external_gene_row.addWidget(self.btn_scan_gene_lists)
        gene_filter_layout.addLayout(external_gene_row)

        left_content_layout.addWidget(gene_filter_group)
        left_content_layout.addSpacing(8)

        # --- 显著性校正设置 ---
        fdr_group = QFrame()
        fdr_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        fdr_group.setObjectName("styled_panel_fdr")
        fdr_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        fdr_layout = QVBoxLayout(fdr_group)

        fdr_title_row = QHBoxLayout()
        fdr_title = create_styled_label("显著性校正设置", font_size=12, bold=True)
        fdr_title_row.addWidget(fdr_title)
        self.bulk_cox_fdr_help_btn = create_questions_button("""显著性校正设置

FDR（False Discovery Rate）校正：
- 用于控制多重检验中的假阳性率
- 当分析多个基因时，p值会产生多重检验问题
- FDR校正后的值更保守，但更可靠

使用方法：
- 选择"使用FDR校正"后，显著性判断基于FDR值
- 选择"使用原始p值"后，显著性判断基于原始p值
- 默认使用FDR校正，阈值为0.05

阈值调整：
- 0.05：标准阈值（推荐）
- 0.01：更严格，减少假阳性
- 0.10：更宽松，增加发现率

举例：
- 基因A原始p值=0.03，FDR=0.08
  → 使用FDR时：不显著（0.08>0.05）
  → 使用p值时：显著（0.03<0.05）""")
        fdr_title_row.addWidget(self.bulk_cox_fdr_help_btn)
        fdr_layout.addLayout(fdr_title_row)

        fdr_mode_label = create_styled_label("校正方式", font_size=11, bold=False)
        fdr_layout.addWidget(fdr_mode_label)

        self.bulk_cox_fdr_mode_combo = create_styled_combo_box()
        self.bulk_cox_fdr_mode_combo.addItems(["使用FDR校正", "使用原始p值"])
        fdr_layout.addWidget(self.bulk_cox_fdr_mode_combo)

        fdr_threshold_row = QHBoxLayout()
        fdr_threshold_label = create_styled_label("显著性阈值", font_size=10, bold=False)
        fdr_threshold_row.addWidget(fdr_threshold_label)
        self.bulk_cox_fdr_threshold_input = create_styled_line_edit()
        self.bulk_cox_fdr_threshold_input.setText("0.05")
        self.bulk_cox_fdr_threshold_input.setMinimumWidth(80)
        self.bulk_cox_fdr_threshold_input.setAlignment(Qt.AlignCenter)
        fdr_threshold_row.addWidget(self.bulk_cox_fdr_threshold_input)
        fdr_layout.addLayout(fdr_threshold_row)

        left_content_layout.addWidget(fdr_group)
        left_content_layout.addSpacing(8)

        # --- 样本筛选1 ---
        filter1_group = QFrame()
        filter1_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter1_group.setObjectName("styled_panel_filter1")
        filter1_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_group)

        filter1_header = QHBoxLayout()
        self.bulk_cox_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.bulk_cox_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.bulk_cox_filter1_combo = create_styled_combo_box()
        self.bulk_cox_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.bulk_cox_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.bulk_cox_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_cox_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.bulk_cox_filter1_list)

        left_content_layout.addWidget(filter1_group)
        left_content_layout.addSpacing(8)

        # --- 样本筛选2 ---
        filter2_group = QFrame()
        filter2_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter2_group.setObjectName("styled_panel_filter2")
        filter2_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_group)

        filter2_header = QHBoxLayout()
        self.bulk_cox_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.bulk_cox_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.bulk_cox_filter2_combo = create_styled_combo_box()
        self.bulk_cox_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.bulk_cox_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.bulk_cox_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_cox_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.bulk_cox_filter2_list)

        left_content_layout.addWidget(filter2_group)
        left_content_layout.addSpacing(8)

        left_content_layout.addStretch()

        left_scroll.setWidget(left_content)
        left_layout.addWidget(left_scroll)
        main_layout.addWidget(left_panel)

        # ================ 中间结果区域 ================
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)

        # --- 统计信息（标签页上方）---
        stats_bar = QFrame()
        stats_bar.setObjectName("styled_panel_stats_bar")
        stats_bar.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stats_bar_layout = QHBoxLayout(stats_bar)
        stats_bar_layout.setContentsMargins(10, 5, 10, 5)
        stats_bar_layout.setSpacing(20)

        self.bulk_cox_total_label = create_styled_label("总基因: -", font_size=11, bold=False)
        stats_bar_layout.addWidget(self.bulk_cox_total_label)

        self.bulk_cox_risk_label = create_styled_label("风险基因(HR>1): -", font_size=11, bold=False)
        stats_bar_layout.addWidget(self.bulk_cox_risk_label)

        self.bulk_cox_protective_label = create_styled_label("保护基因(HR<1): -", font_size=11, bold=False)
        stats_bar_layout.addWidget(self.bulk_cox_protective_label)

        self.bulk_cox_sig_label = create_styled_label("显著基因(p<0.05): -", font_size=11, bold=False)
        stats_bar_layout.addWidget(self.bulk_cox_sig_label)

        stats_bar_layout.addStretch()
        center_layout.addWidget(stats_bar)

        result_label = create_styled_label("COX分析结果", font_size=12, bold=True)
        center_layout.addWidget(result_label)

        search_layout = QHBoxLayout()
        self.gene_search_input = create_styled_line_edit()
        self.gene_search_input.setPlaceholderText("输入基因名称搜索...")
        search_layout.addWidget(self.gene_search_input)
        self.gene_search_btn = create_styled_button("搜索", font_size=11)
        search_layout.addWidget(self.gene_search_btn)
        center_layout.addLayout(search_layout)

        result_panel, result_layout = create_styled_panel()
        self.tab_widget = create_styled_tab_widget()

        # 总体列表
        overall_page, overall_layout = create_styled_tab_page(self.tab_widget, "总体列表")
        self.bulk_cox_overall_table = create_styled_table()
        self.bulk_cox_overall_table.setColumnCount(10)
        self.bulk_cox_overall_table.setHorizontalHeaderLabels([
            '基因', 'coef', 'HR', 'HR_lower95', 'HR_upper95', 'se', 'z', 'pvalue', 'FDR', '方向'
        ])
        overall_layout.addWidget(self.bulk_cox_overall_table)

        # 风险基因
        risk_page, risk_layout = create_styled_tab_page(self.tab_widget, "风险基因(HR>1)")
        self.bulk_cox_risk_table = create_styled_table()
        self.bulk_cox_risk_table.setColumnCount(10)
        self.bulk_cox_risk_table.setHorizontalHeaderLabels([
            '基因', 'coef', 'HR', 'HR_lower95', 'HR_upper95', 'se', 'z', 'pvalue', 'FDR', '方向'
        ])
        risk_layout.addWidget(self.bulk_cox_risk_table)

        # 保护基因
        protective_page, protective_layout = create_styled_tab_page(self.tab_widget, "保护基因(HR<1)")
        self.bulk_cox_protective_table = create_styled_table()
        self.bulk_cox_protective_table.setColumnCount(10)
        self.bulk_cox_protective_table.setHorizontalHeaderLabels([
            '基因', 'coef', 'HR', 'HR_lower95', 'HR_upper95', 'se', 'z', 'pvalue', 'FDR', '方向'
        ])
        protective_layout.addWidget(self.bulk_cox_protective_table)

        result_layout.addWidget(self.tab_widget)
        center_layout.addWidget(result_panel)
        main_layout.addWidget(center_panel)

        # ================ 右侧操作面板 ================
        right_panel, right_layout = create_styled_panel()
        right_panel.setMinimumWidth(180)
        right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.btn_run_cox = create_styled_button("运行COX分析", font_size=14, button_type='run')
        right_layout.addWidget(self.btn_run_cox)

        self.btn_export_csv = create_styled_button("导出结果", font_size=12, button_type='export')
        right_layout.addWidget(self.btn_export_csv)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.bulk_cox_page