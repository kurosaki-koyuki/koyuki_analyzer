# -*- coding: utf-8 -*-
"""
bulk WGCNA分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
继承bulk层的样式模板
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_spinbox, create_styled_text_edit,
    create_styled_tab_widget, create_styled_image_tab,
    create_questions_button, create_labeled_param_with_help
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class BulkWgcnaPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_wgcna_page.findChild(QLabel, "bulk_wgcna_bg")
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

        title_label = self.bulk_wgcna_page.findChild(QLabel, "bulk_wgcna_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_wgcna_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or
                                       isinstance(child, type(create_questions_button()))):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'bulk_wgcna_btn_stage1'):
            self.bulk_wgcna_btn_stage1.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_wgcna_btn_stage2'):
            self.bulk_wgcna_btn_stage2.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_wgcna_btn_stage3'):
            self.bulk_wgcna_btn_stage3.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_wgcna_btn_stage4'):
            self.bulk_wgcna_btn_stage4.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_wgcna_btn_stage5'):
            self.bulk_wgcna_btn_stage5.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_wgcna_btn_stage6'):
            self.bulk_wgcna_btn_stage6.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_wgcna_btn_export_png'):
            self.bulk_wgcna_btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_wgcna_btn_export_pdf'):
            self.bulk_wgcna_btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_wgcna_btn_export_svg'):
            self.bulk_wgcna_btn_export_svg.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_wgcna_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_wgcna_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_wgcna_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_wgcna_page.findChildren(QLabel):
            if child.objectName() != "bulk_wgcna_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_wgcna_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_wgcna_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.bulk_wgcna_page.findChild(QWidget, "bulk_wgcna_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")
        if hasattr(self, 'r_version_label'):
            self.r_version_label.setStyleSheet(label_style)

    def create_page(self):
        self.bulk_wgcna_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.bulk_wgcna_page)
        bg_label.setObjectName("bulk_wgcna_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.bulk_wgcna_page)
        overlay.setObjectName("bulk_wgcna_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 顶部标题栏 ===
        top_layout = QHBoxLayout()

        self.btn_back = create_styled_button("← 返回bulk主页", font_size=12)
        top_layout.addWidget(self.btn_back)

        title_label = QLabel("bulk WGCNA分析")
        title_label.setObjectName("bulk_wgcna_title")
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
        self.bulk_wgcna_status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.bulk_wgcna_status_text.setMaximumHeight(80)
        status_layout.addWidget(self.bulk_wgcna_status_text)
        layout.addLayout(status_layout)

        # === 主内容区域（三栏） ===
        main_layout = QHBoxLayout()

        # ================ 左侧参数面板 ================
        left_panel, left_layout = create_styled_panel()
        left_panel.setMinimumWidth(340)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_content = QWidget()
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setContentsMargins(0, 0, 0, 0)

        # --- Debug区域 ---
        debug_frame = QFrame()
        debug_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        debug_frame.setObjectName("styled_panel_debug")
        debug_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        debug_layout = QVBoxLayout(debug_frame)
        debug_layout.setContentsMargins(5, 5, 5, 5)

        debug_title = create_styled_label("Debug区域", font_size=11, bold=True)
        debug_layout.addWidget(debug_title)

        self.bulk_wgcna_debug_btn = create_styled_button("检测环境对应", font_size=10)
        debug_layout.addWidget(self.bulk_wgcna_debug_btn)

        left_content_layout.addWidget(debug_frame)
        left_content_layout.addSpacing(8)

        # --- 数据筛选group_box ---
        filter_group = QFrame()
        filter_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter_group.setObjectName("styled_panel_filter")
        filter_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter_group_layout = QVBoxLayout(filter_group)
        filter_group_layout.setContentsMargins(8, 8, 8, 8)

        filter_group_title = create_styled_label("数据筛选", font_size=12, bold=True)
        filter_group_layout.addWidget(filter_group_title)

        clinical_label = create_styled_label("分类列选择", font_size=11, bold=False)
        filter_group_layout.addWidget(clinical_label)

        self.bulk_wgcna_clinical_combo = create_styled_combo_box()
        self.bulk_wgcna_clinical_combo.addItem("全部")
        filter_group_layout.addWidget(self.bulk_wgcna_clinical_combo)

        self.bulk_wgcna_group_list_label = create_styled_label("组别（可多选）", font_size=11, bold=False)
        self.bulk_wgcna_group_list_label.hide()
        filter_group_layout.addWidget(self.bulk_wgcna_group_list_label)

        self.bulk_wgcna_group_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_wgcna_group_list.hide()
        filter_group_layout.addWidget(self.bulk_wgcna_group_list)

        filter1_frame = QFrame()
        filter1_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.bulk_wgcna_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.bulk_wgcna_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.bulk_wgcna_filter1_combo = create_styled_combo_box()
        self.bulk_wgcna_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.bulk_wgcna_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.bulk_wgcna_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_wgcna_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.bulk_wgcna_filter1_list)

        filter_group_layout.addWidget(filter1_frame)

        filter2_frame = QFrame()
        filter2_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.bulk_wgcna_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.bulk_wgcna_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.bulk_wgcna_filter2_combo = create_styled_combo_box()
        self.bulk_wgcna_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.bulk_wgcna_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.bulk_wgcna_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_wgcna_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.bulk_wgcna_filter2_list)

        filter_group_layout.addWidget(filter2_frame)
        left_content_layout.addWidget(filter_group)
        left_content_layout.addSpacing(8)

        # --- 阶段一参数group_box ---
        stage1_group = QFrame()
        stage1_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage1_group.setObjectName("styled_panel_stage1")
        stage1_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage1_layout = QVBoxLayout(stage1_group)
        stage1_layout.setContentsMargins(8, 8, 8, 8)

        stage1_title_row = QHBoxLayout()
        stage1_title = create_styled_label("阶段一参数（数据准备+基因筛选）", font_size=12, bold=True)
        stage1_title_row.addWidget(stage1_title)
        self.bulk_wgcna_stage1_help_btn = create_questions_button("""阶段一：数据准备+基因筛选

功能：
- 从表达矩阵中筛选基因用于构建网络
- 支持两种方式：MAD筛选或外部基因列表导入
- 生成样本聚类树

参数说明：
- 筛选方式：MAD筛选或外部基因列表
- MAD阈值：默认5000，值越大使用的基因越多
- 外部基因列表：从appdata/genelists目录导入预定义的基因列表

注意：
- 如果选择了外部基因列表，将跳过MAD筛选
- 建议根据数据集中基因总数调整MAD阈值
- 基因数太多会导致后续分析耗时显著增加
- 基因数太少会丢失重要信息""")
        stage1_title_row.addWidget(self.bulk_wgcna_stage1_help_btn)
        stage1_layout.addLayout(stage1_title_row)

        filter_mode_row = QHBoxLayout()
        filter_mode_label, filter_mode_help = create_labeled_param_with_help(
            "筛选方式",
            "选择基因筛选方式。\nMAD筛选：使用中位数绝对偏差筛选变异最大的基因\n外部基因列表：从预定义的基因列表文件中导入基因\n\n如果选择了外部基因列表，MAD阈值将被忽略。"
        )
        filter_mode_row.addWidget(filter_mode_label)
        filter_mode_row.addWidget(filter_mode_help)
        filter_mode_row.addSpacing(8)
        self.bulk_wgcna_filter_mode_combo = create_styled_combo_box()
        self.bulk_wgcna_filter_mode_combo.addItems(['MAD筛选', '外部基因列表'])
        self.bulk_wgcna_filter_mode_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_mode_row.addWidget(self.bulk_wgcna_filter_mode_combo)
        stage1_layout.addLayout(filter_mode_row)

        mad_row = QHBoxLayout()
        mad_label, mad_help = create_labeled_param_with_help(
            "MAD阈值",
            "中位数绝对偏差阈值。\n从所有基因中选出MAD最高的前N个基因用于构建网络。\n默认5000，值越大使用的基因越多，结果越精细但耗时越长。\n建议根据基因总数调整，通常取3000-10000。"
        )
        mad_row.addWidget(mad_label)
        mad_row.addWidget(mad_help)
        mad_row.addSpacing(8)
        self.bulk_wgcna_mad_input = create_styled_line_edit()
        self.bulk_wgcna_mad_input.setText("5000")
        self.bulk_wgcna_mad_input.setMinimumWidth(60)
        self.bulk_wgcna_mad_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        mad_row.addWidget(self.bulk_wgcna_mad_input)
        stage1_layout.addLayout(mad_row)

        external_gene_row = QHBoxLayout()
        external_gene_label, external_gene_help = create_labeled_param_with_help(
            "外部基因列表",
            "选择预定义的基因列表文件。\n文件位于appdata/genelists目录下。\n选择后将使用该文件中的基因进行分析，跳过MAD筛选。"
        )
        external_gene_row.addWidget(external_gene_label)
        external_gene_row.addWidget(external_gene_help)
        external_gene_row.addSpacing(8)
        self.bulk_wgcna_external_gene_combo = create_styled_combo_box()
        self.bulk_wgcna_external_gene_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        external_gene_row.addWidget(self.bulk_wgcna_external_gene_combo)
        stage1_layout.addLayout(external_gene_row)

        left_content_layout.addWidget(stage1_group)
        left_content_layout.addSpacing(8)

        # --- 阶段二参数group_box ---
        stage2_group = QFrame()
        stage2_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage2_group.setObjectName("styled_panel_stage2")
        stage2_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage2_layout = QVBoxLayout(stage2_group)
        stage2_layout.setContentsMargins(8, 8, 8, 8)

        stage2_title_row = QHBoxLayout()
        stage2_title = create_styled_label("阶段二参数（软阈值选择）", font_size=12, bold=True)
        stage2_title_row.addWidget(stage2_title)
        self.bulk_wgcna_stage2_help_btn = create_questions_button("""阶段二：软阈值选择

功能：
- 计算不同power值下的无标度网络拟合度
- 绘制Scale Free Topology曲线和平均连通性曲线
- 自动推荐最优软阈值

参数说明：
- 网络类型：unsigned（无符号）或signed（有符号）

注意：
- 最优软阈值是使Scale Free Topology R^2达到0.85的最小power值
- 如果自动推荐失败，需要根据曲线手动选择
- 推荐值会自动填入阶段三的power参数""")
        stage2_title_row.addWidget(self.bulk_wgcna_stage2_help_btn)
        stage2_layout.addLayout(stage2_title_row)

        network_type_row = QHBoxLayout()
        network_type_label, network_type_help = create_labeled_param_with_help(
            "网络类型",
            "网络构建的相关性类型。\nunsigned: 无符号网络（默认）\nsigned: 有符号网络\n\n无符号网络同时考虑正相关和负相关，适合共表达网络分析。\n有符号网络只考虑正相关，适合基因表达趋势相似的模块发现。"
        )
        network_type_row.addWidget(network_type_label)
        network_type_row.addWidget(network_type_help)
        network_type_row.addSpacing(8)
        self.bulk_wgcna_network_type_combo = create_styled_combo_box()
        self.bulk_wgcna_network_type_combo.addItems(['unsigned', 'signed'])
        self.bulk_wgcna_network_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        network_type_row.addWidget(self.bulk_wgcna_network_type_combo)
        stage2_layout.addLayout(network_type_row)

        rsquared_row = QHBoxLayout()
        rsquared_label, rsquared_help = create_labeled_param_with_help(
            "Scale Free R²阈值",
            "用于确定最优软阈值的拟合度阈值。\n默认0.9，值越高要求网络越接近无标度分布。\n如果推荐失败，可适当降低此值。"
        )
        rsquared_row.addWidget(rsquared_label)
        rsquared_row.addWidget(rsquared_help)
        rsquared_row.addSpacing(8)
        self.bulk_wgcna_rsquared_input = create_styled_line_edit()
        self.bulk_wgcna_rsquared_input.setText("0.9")
        self.bulk_wgcna_rsquared_input.setMinimumWidth(50)
        self.bulk_wgcna_rsquared_input.setAlignment(Qt.AlignCenter)
        rsquared_row.addWidget(self.bulk_wgcna_rsquared_input)
        stage2_layout.addLayout(rsquared_row)

        manual_power_row = QHBoxLayout()
        manual_power_label, manual_power_help = create_labeled_param_with_help(
            "手动软阈值",
            "如果不希望使用自动推荐的软阈值，可在此手动输入。\n留空则使用自动推荐值。\n通常取值范围为1-20。"
        )
        manual_power_row.addWidget(manual_power_label)
        manual_power_row.addWidget(manual_power_help)
        manual_power_row.addSpacing(8)
        self.bulk_wgcna_manual_power_input = create_styled_line_edit()
        self.bulk_wgcna_manual_power_input.setPlaceholderText("自动推荐")
        self.bulk_wgcna_manual_power_input.setMinimumWidth(40)
        self.bulk_wgcna_manual_power_input.setAlignment(Qt.AlignCenter)
        manual_power_row.addWidget(self.bulk_wgcna_manual_power_input)
        stage2_layout.addLayout(manual_power_row)

        self.bulk_wgcna_power_estimate_label = create_styled_label("推荐软阈值: -", font_size=10, bold=False)
        stage2_layout.addWidget(self.bulk_wgcna_power_estimate_label)

        left_content_layout.addWidget(stage2_group)
        left_content_layout.addSpacing(8)

        # --- 阶段三参数group_box ---
        stage3_group = QFrame()
        stage3_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage3_group.setObjectName("styled_panel_stage3")
        stage3_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage3_layout = QVBoxLayout(stage3_group)
        stage3_layout.setContentsMargins(8, 8, 8, 8)

        stage3_title_row = QHBoxLayout()
        stage3_title = create_styled_label("阶段三参数（网络构建+模块识别）", font_size=12, bold=True)
        stage3_title_row.addWidget(stage3_title)
        self.bulk_wgcna_stage3_help_btn = create_questions_button("""阶段三：网络构建+模块识别

功能：
- 使用选定的软阈值构建共表达网络
- 计算基因间的拓扑重叠矩阵(TOM)
- 进行层次聚类识别模块
- 合并相似的模块

参数说明：
- 软阈值power值：建议使用阶段二推荐的值
- 最小模块大小：默认30
- 模块合并阈值：默认0.25

注意：
- 模块数量会影响后续分析的分辨率
- 太小的模块可能噪声较大""")
        stage3_title_row.addWidget(self.bulk_wgcna_stage3_help_btn)
        stage3_layout.addLayout(stage3_title_row)

        power_row = QHBoxLayout()
        power_label, power_help = create_labeled_param_with_help(
            "软阈值power值",
            "软阈值幂次。\n用于将相关性矩阵转换为邻接矩阵，使网络近似服从无标度分布。\n建议使用阶段二推荐的值，默认7。\n若阶段二未推荐，可根据Scale Free Topology曲线手动选择。"
        )
        power_row.addWidget(power_label)
        power_row.addWidget(power_help)
        power_row.addSpacing(8)
        self.bulk_wgcna_power_input = create_styled_line_edit()
        self.bulk_wgcna_power_input.setText("7")
        self.bulk_wgcna_power_input.setMinimumWidth(40)
        self.bulk_wgcna_power_input.setAlignment(Qt.AlignCenter)
        self.bulk_wgcna_power_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        power_row.addWidget(self.bulk_wgcna_power_input)
        stage3_layout.addLayout(power_row)

        min_module_row = QHBoxLayout()
        min_module_label, min_module_help = create_labeled_param_with_help(
            "最小模块大小",
            "识别的模块中基因的最小数量。\n默认30，值越小产生的模块越多，值越大产生的模块越少。\n建议根据数据集大小调整，通常取20-50。"
        )
        min_module_row.addWidget(min_module_label)
        min_module_row.addWidget(min_module_help)
        min_module_row.addSpacing(8)
        self.bulk_wgcna_min_module_input = create_styled_line_edit()
        self.bulk_wgcna_min_module_input.setText("30")
        self.bulk_wgcna_min_module_input.setMinimumWidth(40)
        self.bulk_wgcna_min_module_input.setAlignment(Qt.AlignCenter)
        self.bulk_wgcna_min_module_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        min_module_row.addWidget(self.bulk_wgcna_min_module_input)
        stage3_layout.addLayout(min_module_row)

        merge_cut_row = QHBoxLayout()
        merge_cut_label, merge_cut_help = create_labeled_param_with_help(
            "模块合并阈值",
            "模块特征基因(ME)之间的相关性阈值。\n\n融合过程：\n1. 首先使用动态切树算法识别初始模块\n2. 计算所有模块特征基因之间的相关性\n3. 将相关性大于此阈值的模块合并\n4. 生成模块融合分析图和合并前后对比图\n\n默认0.25，值越小合并越少(模块数越多)，值越大合并越多(模块数越少)。\n建议取0.15-0.30。\n\n注意：如果所有模块相关性都低于此阈值，则不会合并任何模块。"
        )
        merge_cut_row.addWidget(merge_cut_label)
        merge_cut_row.addWidget(merge_cut_help)
        merge_cut_row.addSpacing(8)
        self.bulk_wgcna_merge_cut_input = create_styled_line_edit()
        self.bulk_wgcna_merge_cut_input.setText("0.25")
        self.bulk_wgcna_merge_cut_input.setMinimumWidth(40)
        self.bulk_wgcna_merge_cut_input.setAlignment(Qt.AlignCenter)
        self.bulk_wgcna_merge_cut_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        merge_cut_row.addWidget(self.bulk_wgcna_merge_cut_input)
        stage3_layout.addLayout(merge_cut_row)

        stage3_width_row = QHBoxLayout()
        stage3_width_label = create_styled_label("出图宽度", font_size=11, bold=False)
        stage3_width_row.addWidget(stage3_width_label)
        self.bulk_wgcna_stage3_width_input = create_styled_line_edit()
        self.bulk_wgcna_stage3_width_input.setText("1200")
        self.bulk_wgcna_stage3_width_input.setMinimumWidth(60)
        self.bulk_wgcna_stage3_width_input.setAlignment(Qt.AlignCenter)
        stage3_width_row.addWidget(self.bulk_wgcna_stage3_width_input)
        stage3_width_row.addSpacing(8)
        stage3_height_label = create_styled_label("出图高度", font_size=11, bold=False)
        stage3_width_row.addWidget(stage3_height_label)
        self.bulk_wgcna_stage3_height_input = create_styled_line_edit()
        self.bulk_wgcna_stage3_height_input.setText("1200")
        self.bulk_wgcna_stage3_height_input.setMinimumWidth(60)
        self.bulk_wgcna_stage3_height_input.setAlignment(Qt.AlignCenter)
        stage3_width_row.addWidget(self.bulk_wgcna_stage3_height_input)
        stage3_layout.addLayout(stage3_width_row)

        left_content_layout.addWidget(stage3_group)
        left_content_layout.addSpacing(8)

        # --- 阶段四参数group_box ---
        stage4_group = QFrame()
        stage4_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage4_group.setObjectName("styled_panel_stage4")
        stage4_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage4_layout = QVBoxLayout(stage4_group)
        stage4_layout.setContentsMargins(8, 8, 8, 8)

        stage4_title_row = QHBoxLayout()
        stage4_title = create_styled_label("阶段四参数（模块-性状关联）", font_size=12, bold=True)
        stage4_title_row.addWidget(stage4_title)
        self.bulk_wgcna_stage4_help_btn = create_questions_button("""阶段四：模块-性状关联

功能：
- 计算每个模块的特征基因(ME)
- 分析模块特征基因与临床性状的相关性
- 生成模块-性状关联热图
- 生成模块特征基因表达箱线图
- 生成模块聚类热图

参数说明：
- 性状列选择：选择一个或多个分类列作为性状进行关联分析
- 可同时分析多个性状，在热图中会分别显示每个性状的相关性

注意：
- 相关性越高的模块越可能与该性状相关
- 选择多个性状可以比较不同分类对模块的影响""")
        stage4_title_row.addWidget(self.bulk_wgcna_stage4_help_btn)
        stage4_layout.addLayout(stage4_title_row)

        trait_label = create_styled_label("性状列选择（可多选）", font_size=11, bold=False)
        stage4_layout.addWidget(trait_label)

        self.bulk_wgcna_trait_list = create_styled_list_widget(fixed_height=120, multi_selection=True)
        stage4_layout.addWidget(self.bulk_wgcna_trait_list)

        stage4_width_row = QHBoxLayout()
        stage4_width_label = create_styled_label("出图宽度", font_size=11, bold=False)
        stage4_width_row.addWidget(stage4_width_label)
        self.bulk_wgcna_stage4_width_input = create_styled_line_edit()
        self.bulk_wgcna_stage4_width_input.setText("1200")
        self.bulk_wgcna_stage4_width_input.setMinimumWidth(60)
        self.bulk_wgcna_stage4_width_input.setAlignment(Qt.AlignCenter)
        stage4_width_row.addWidget(self.bulk_wgcna_stage4_width_input)
        stage4_width_row.addSpacing(8)
        stage4_height_label = create_styled_label("出图高度", font_size=11, bold=False)
        stage4_width_row.addWidget(stage4_height_label)
        self.bulk_wgcna_stage4_height_input = create_styled_line_edit()
        self.bulk_wgcna_stage4_height_input.setText("1000")
        self.bulk_wgcna_stage4_height_input.setMinimumWidth(60)
        self.bulk_wgcna_stage4_height_input.setAlignment(Qt.AlignCenter)
        stage4_width_row.addWidget(self.bulk_wgcna_stage4_height_input)
        stage4_layout.addLayout(stage4_width_row)

        stage4_cell_row = QHBoxLayout()
        stage4_cell_width_label = create_styled_label("热图单元格宽度", font_size=11, bold=False)
        stage4_cell_row.addWidget(stage4_cell_width_label)
        self.bulk_wgcna_stage4_cell_width_input = create_styled_line_edit()
        self.bulk_wgcna_stage4_cell_width_input.setText("80")
        self.bulk_wgcna_stage4_cell_width_input.setMinimumWidth(60)
        self.bulk_wgcna_stage4_cell_width_input.setAlignment(Qt.AlignCenter)
        stage4_cell_row.addWidget(self.bulk_wgcna_stage4_cell_width_input)
        stage4_cell_row.addSpacing(8)
        stage4_cell_height_label = create_styled_label("热图单元格高度", font_size=11, bold=False)
        stage4_cell_row.addWidget(stage4_cell_height_label)
        self.bulk_wgcna_stage4_cell_height_input = create_styled_line_edit()
        self.bulk_wgcna_stage4_cell_height_input.setText("80")
        self.bulk_wgcna_stage4_cell_height_input.setMinimumWidth(60)
        self.bulk_wgcna_stage4_cell_height_input.setAlignment(Qt.AlignCenter)
        stage4_cell_row.addWidget(self.bulk_wgcna_stage4_cell_height_input)
        stage4_layout.addLayout(stage4_cell_row)

        self.bulk_wgcna_stage4_significance_checkbox = create_styled_checkbox("显示箱线图显著性标记")
        self.bulk_wgcna_stage4_significance_checkbox.setChecked(True)
        stage4_layout.addWidget(self.bulk_wgcna_stage4_significance_checkbox)

        left_content_layout.addWidget(stage4_group)

        stage5_group = QFrame()
        stage5_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage5_group.setObjectName("styled_panel_stage5")
        stage5_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage5_layout = QVBoxLayout(stage5_group)
        stage5_layout.setContentsMargins(8, 8, 8, 8)

        stage5_title_row = QHBoxLayout()
        stage5_title = create_styled_label("阶段五参数（GO/KEGG富集分析）", font_size=12, bold=True)
        stage5_title_row.addWidget(stage5_title)
        self.bulk_wgcna_stage5_help_btn = create_questions_button("""阶段五：GO和KEGG富集分析

注意：此步骤运行较慢且需要联网（最好是VPN）

功能：
- 对每个选中的模块进行GO生物学过程(BP)富集分析
- 对每个选中的模块进行KEGG通路富集分析
- 生成气泡图、条图和环形图展示富集结果

参数说明：
- 模块选择：选择一个或多个模块进行富集分析
- 物种：选择分析的物种（默认人类hsa）
- GO校正p值阈值：GO富集结果的校正p值筛选阈值
- KEGG校正p值阈值：KEGG富集结果的校正p值筛选阈值
- GO展示条目数：GO结果图中展示的条目数量
- KEGG展示条目数：KEGG结果图中展示的条目数量

注意：
- 需要先运行阶段三完成模块识别
- 模块基因数少于10个将跳过分析
- 结果保存在当前数据集的output目录下""")
        stage5_title_row.addWidget(self.bulk_wgcna_stage5_help_btn)
        stage5_layout.addLayout(stage5_title_row)

        module_label = create_styled_label("选择模块（可多选）", font_size=11, bold=False)
        stage5_layout.addWidget(module_label)

        self.bulk_wgcna_module_list_go = create_styled_list_widget(fixed_height=100, multi_selection=True)
        stage5_layout.addWidget(self.bulk_wgcna_module_list_go)

        organism_row = QHBoxLayout()
        organism_label = create_styled_label("物种", font_size=10, bold=False)
        organism_row.addWidget(organism_label)
        self.bulk_wgcna_organism_combo = create_styled_combo_box()
        self.bulk_wgcna_organism_combo.addItems(["hsa", "mmu", "rno", "dme"])
        self.bulk_wgcna_organism_combo.setCurrentText("hsa")
        organism_row.addWidget(self.bulk_wgcna_organism_combo)
        stage5_layout.addLayout(organism_row)

        go_padj_row = QHBoxLayout()
        go_padj_label = create_styled_label("GO校正p值阈值", font_size=10, bold=False)
        go_padj_row.addWidget(go_padj_label)
        self.bulk_wgcna_go_padj_spin = create_styled_spinbox(min_value=0.01, max_value=1.0, default_value=0.05)
        go_padj_row.addWidget(self.bulk_wgcna_go_padj_spin)
        stage5_layout.addLayout(go_padj_row)

        kegg_padj_row = QHBoxLayout()
        kegg_padj_label = create_styled_label("KEGG校正p值阈值", font_size=10, bold=False)
        kegg_padj_row.addWidget(kegg_padj_label)
        self.bulk_wgcna_kegg_padj_spin = create_styled_spinbox(min_value=0.01, max_value=1.0, default_value=0.05)
        kegg_padj_row.addWidget(self.bulk_wgcna_kegg_padj_spin)
        stage5_layout.addLayout(kegg_padj_row)

        go_topn_row = QHBoxLayout()
        go_topn_label = create_styled_label("GO展示条目数", font_size=10, bold=False)
        go_topn_row.addWidget(go_topn_label)
        self.bulk_wgcna_go_topn_spin = create_styled_spinbox(min_value=5, max_value=50, default_value=15)
        go_topn_row.addWidget(self.bulk_wgcna_go_topn_spin)
        stage5_layout.addLayout(go_topn_row)

        kegg_topn_row = QHBoxLayout()
        kegg_topn_label = create_styled_label("KEGG展示条目数", font_size=10, bold=False)
        kegg_topn_row.addWidget(kegg_topn_label)
        self.bulk_wgcna_kegg_topn_spin = create_styled_spinbox(min_value=5, max_value=50, default_value=15)
        kegg_topn_row.addWidget(self.bulk_wgcna_kegg_topn_spin)
        stage5_layout.addLayout(kegg_topn_row)

        left_content_layout.addWidget(stage5_group)

        stage6_group = QFrame()
        stage6_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage6_group.setObjectName("styled_panel_stage6")
        stage6_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage6_layout = QVBoxLayout(stage6_group)
        stage6_layout.setContentsMargins(8, 8, 8, 8)

        stage6_title_row = QHBoxLayout()
        stage6_title = create_styled_label("阶段六参数（导出基因集合）", font_size=12, bold=True)
        stage6_title_row.addWidget(stage6_title)
        self.bulk_wgcna_stage6_help_btn = create_questions_button("""阶段六：导出基因集合

功能：
- 选择需要导出的模块
- 将选中模块中的基因列表导出为xlsx文件
- 每个模块导出一个独立的文件
- 文件格式：第一列是基因名，无列名和行名

参数说明：
- 模块选择：选择一个或多个模块导出基因列表
- 导出格式：xlsx格式，第一列是基因名

注意：
- 需要先运行阶段三完成模块识别
- 导出文件保存在当前数据集的output目录下""")
        stage6_title_row.addWidget(self.bulk_wgcna_stage6_help_btn)
        stage6_layout.addLayout(stage6_title_row)

        module_label = create_styled_label("选择模块（可多选）", font_size=11, bold=False)
        stage6_layout.addWidget(module_label)

        self.bulk_wgcna_module_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        stage6_layout.addWidget(self.bulk_wgcna_module_list)

        self.bulk_wgcna_merge_checkbox = QCheckBox("合并到一个表格（按模块分组）")
        self.bulk_wgcna_merge_checkbox.setStyleSheet(f"color: {styles.get('text_color', '#FFFFFF')};")
        self.bulk_wgcna_merge_checkbox.setChecked(True)
        stage6_layout.addWidget(self.bulk_wgcna_merge_checkbox)

        self.bulk_wgcna_export_go_kegg_checkbox = QCheckBox("同时导出GO和KEGG分析结果")
        self.bulk_wgcna_export_go_kegg_checkbox.setStyleSheet(f"color: {styles.get('text_color', '#FFFFFF')};")
        self.bulk_wgcna_export_go_kegg_checkbox.setChecked(False)
        stage6_layout.addWidget(self.bulk_wgcna_export_go_kegg_checkbox)

        left_content_layout.addWidget(stage6_group)
        left_content_layout.addStretch()

        left_scroll.setWidget(left_content)
        left_layout.addWidget(left_scroll)
        main_layout.addWidget(left_panel)

        # ================ 中间图表区 ================
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)

        self.bulk_wgcna_plot_tabs = create_styled_tab_widget()

        _, self.bulk_wgcna_label_sample_dendro = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "样本聚类树",
            default_text="请运行阶段一",
            data_hint_template="数据: {dataset_name}\n样本数: {n_samples}\n基因数: {n_genes}\n\n请设置参数并点击「阶段一：数据准备+MAD筛选」"
        )
        _, self.bulk_wgcna_label_soft_threshold = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "软阈值选择图",
            default_text="请运行阶段二",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一，再点击「阶段二：软阈值选择」"
        )
        _, self.bulk_wgcna_label_gene_dendro = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "基因聚类树+模块色条",
            default_text="请运行阶段三",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一和阶段二，再点击「阶段三：网络构建+模块识别」"
        )
        _, self.bulk_wgcna_label_module_merge = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "模块融合分析图",
            default_text="请运行阶段三",
            data_hint_template="数据: {dataset_name}\n\n模块融合分析图显示模块特征基因的聚类关系"
        )
        _, self.bulk_wgcna_label_module_comparison = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "合并前后对比图",
            default_text="请运行阶段三",
            data_hint_template="数据: {dataset_name}\n\n显示模块合并前后的颜色分配对比"
        )
        _, self.bulk_wgcna_label_module_trait = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "模块-性状关联图",
            default_text="请运行阶段四",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段四：模块-性状关联」"
        )
        _, self.bulk_wgcna_label_me_boxplot = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "模块特征基因箱线图",
            default_text="请运行阶段四",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段四：模块-性状关联」"
        )
        _, self.bulk_wgcna_label_module_cluster = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "模块聚类热图",
            default_text="请运行阶段四",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段四：模块-性状关联」"
        )
        _, self.bulk_wgcna_label_gene_significance = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "基因显著性散点图",
            default_text="请运行阶段四",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段四：模块-性状关联」"
        )
        _, self.bulk_wgcna_label_go_bubble = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "GO富集气泡图",
            default_text="请运行阶段五",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段五：GO/KEGG富集分析」"
        )
        _, self.bulk_wgcna_label_go_bar = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "GO富集条图",
            default_text="请运行阶段五",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段五：GO/KEGG富集分析」"
        )
        _, self.bulk_wgcna_label_kegg_bubble = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "KEGG富集气泡图",
            default_text="请运行阶段五",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段五：GO/KEGG富集分析」"
        )
        _, self.bulk_wgcna_label_kegg_bar = create_styled_image_tab(
            self.bulk_wgcna_plot_tabs, "KEGG富集条图",
            default_text="请运行阶段五",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三，再点击「阶段五：GO/KEGG富集分析」"
        )

        center_layout.addWidget(self.bulk_wgcna_plot_tabs)
        main_layout.addWidget(center_panel, 1)

        # ================ 右侧运行+导出面板 ================
        right_panel, right_layout = create_styled_panel()
        right_panel.setMinimumWidth(220)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        run_title = create_styled_label("运行区域", font_size=12, bold=True)
        right_layout.addWidget(run_title)

        self.bulk_wgcna_btn_stage1 = create_styled_button("▶ 阶段一：数据准备+MAD筛选", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_wgcna_btn_stage1)

        self.bulk_wgcna_btn_stage2 = create_styled_button("▶ 阶段二：软阈值选择", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_wgcna_btn_stage2)

        self.bulk_wgcna_btn_stage3 = create_styled_button("▶ 阶段三：网络构建+模块识别", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_wgcna_btn_stage3)

        self.bulk_wgcna_btn_stage4 = create_styled_button("▶ 阶段四：模块-性状关联", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_wgcna_btn_stage4)

        self.bulk_wgcna_btn_stage5 = create_styled_button("▶ 阶段五：GO/KEGG富集分析", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_wgcna_btn_stage5)

        self.bulk_wgcna_btn_stage6 = create_styled_button("▶ 阶段六：导出基因集合", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_wgcna_btn_stage6)

        right_layout.addSpacing(10)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        right_layout.addWidget(export_title)

        right_layout.addSpacing(8)

        self.bulk_wgcna_btn_export_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        right_layout.addWidget(self.bulk_wgcna_btn_export_png)

        self.bulk_wgcna_btn_export_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        right_layout.addWidget(self.bulk_wgcna_btn_export_pdf)

        self.bulk_wgcna_btn_export_svg = create_styled_button("导出SVG", font_size=10, button_type='export')
        right_layout.addWidget(self.bulk_wgcna_btn_export_svg)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.bulk_wgcna_page