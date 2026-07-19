# -*- coding: utf-8 -*-
"""
scRNAseq hdWGCNA分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
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


class ScHdWgcnaPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_hdwgcna_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.sc_hdwgcna_page.findChild(QLabel, "sc_hdwgcna_bg")
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

        title_label = self.sc_hdwgcna_page.findChild(QLabel, "sc_hdwgcna_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.sc_hdwgcna_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or
                                       isinstance(child, type(create_questions_button()))):
                continue
            child.setStyleSheet(button_style)

        run_button_style = get_stylesheet_for_widget('run_button')
        for i in range(1, 11):
            btn_name = f'sc_hdwgcna_btn_stage{i}'
            if hasattr(self, btn_name):
                getattr(self, btn_name).setStyleSheet(run_button_style)

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.sc_hdwgcna_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.sc_hdwgcna_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.sc_hdwgcna_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_hdwgcna_page.findChildren(QLabel):
            if child.objectName() != "sc_hdwgcna_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.sc_hdwgcna_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_hdwgcna_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        if hasattr(self, 'r_version_label'):
            self.r_version_label.setStyleSheet(label_style)

    def create_page(self):
        self.sc_hdwgcna_page = QWidget(self.parent)
        self.sc_hdwgcna_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()
        mod_instance = global_mod_manager.get_current_mod()

        layout = QVBoxLayout(self.sc_hdwgcna_page)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        title_label = QLabel("scRNAseq hdWGCNA分析")
        title_label.setObjectName("sc_hdwgcna_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        self.r_version_label = create_styled_label("R版本: 检测中...", font_size=10, bold=False)
        top_layout.addWidget(self.r_version_label)

        top_layout.setStretch(0, 3)
        top_layout.setStretch(1, 1)
        layout.addLayout(top_layout)

        status_layout = QHBoxLayout()
        self.sc_hdwgcna_status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.sc_hdwgcna_status_text.setMaximumHeight(80)
        status_layout.addWidget(self.sc_hdwgcna_status_text)
        layout.addLayout(status_layout)

        main_layout = QHBoxLayout()

        # ================ 左侧参数面板 ================
        left_panel, left_layout = create_styled_panel(parent=self.sc_hdwgcna_page)
        left_panel.setMinimumWidth(340)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_scroll = QScrollArea(left_panel)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_content = QWidget(left_scroll)
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setContentsMargins(0, 0, 0, 0)

        # --- 阶段一参数 ---
        stage1_group = QFrame(left_content)
        stage1_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage1_group.setObjectName("styled_panel_stage1")
        stage1_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage1_layout = QVBoxLayout(stage1_group)
        stage1_layout.setContentsMargins(8, 8, 8, 8)

        stage1_title_row = QHBoxLayout()
        stage1_title = create_styled_label("阶段一参数（加载Seurat对象+基因选择+重新降维）", font_size=12, bold=True)
        stage1_title_row.addWidget(stage1_title)
        self.sc_hdwgcna_stage1_help_btn = create_questions_button("""阶段一：加载Seurat对象+基因选择+重新降维

功能：
- 加载主页已导入的Seurat对象
- 使用RNA assay的data层（logNormalized数据）
- 选择基因进行分析（三种模式可选）
- 选择分析分组列（细胞类型注释列）
- 选择样本列（用于批次校正）
- 选择目标细胞类型进行分析
- 筛选后重新进行PCA和UMAP降维

基因选择模式：
- fraction（最常用，推荐）：按比例随机选择基因，默认0.4（40%）
- custom（自定义基因列表）：使用指定的基因列表，放在appdata/genelists目录
- 高变基因：使用高变基因，默认3000个

注意：
- Seurat对象需先在scRNAseq主页加载
- 分析分组列应为分类变量
- 样本列用于Harmony批次校正
- 如果选择了目标细胞类型，会自动重新降维
- fraction模式是最常用的默认分析方法""")
        stage1_title_row.addWidget(self.sc_hdwgcna_stage1_help_btn)
        stage1_layout.addLayout(stage1_title_row)

        self.sc_hdwgcna_btn_fetch_metadata = create_styled_button("获取注释列表", font_size=11, button_type='import')
        stage1_layout.addWidget(self.sc_hdwgcna_btn_fetch_metadata)

        self.sc_hdwgcna_seurat_status = create_styled_label("Seurat对象: 未加载", font_size=11, bold=False)
        stage1_layout.addWidget(self.sc_hdwgcna_seurat_status)

        analyze_group_label = create_styled_label("分析分组列（细胞类型）", font_size=11, bold=False)
        stage1_layout.addWidget(analyze_group_label)
        self.sc_hdwgcna_analyze_group_combo = create_styled_combo_box()
        self.sc_hdwgcna_analyze_group_combo.addItem("Celltype (major-lineage)")
        stage1_layout.addWidget(self.sc_hdwgcna_analyze_group_combo)

        target_cell_label = create_styled_label("目标细胞类型（可选）", font_size=11, bold=False)
        stage1_layout.addWidget(target_cell_label)
        self.sc_hdwgcna_target_cell_combo = create_styled_combo_box()
        self.sc_hdwgcna_target_cell_combo.addItem("全部")
        stage1_layout.addWidget(self.sc_hdwgcna_target_cell_combo)

        filter_frame = QFrame()
        filter_frame.setObjectName("styled_panel_filter")
        filter_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter_layout = QVBoxLayout(filter_frame)
        filter_layout.setContentsMargins(8, 8, 8, 8)

        filter_header = QHBoxLayout()
        self.sc_hdwgcna_filter_enable = create_styled_checkbox("启用筛选")
        filter_header.addWidget(self.sc_hdwgcna_filter_enable)
        filter_layout.addLayout(filter_header)

        filter_col_label = create_styled_label("筛选分类列", font_size=10, bold=False)
        filter_layout.addWidget(filter_col_label)

        self.sc_hdwgcna_filter_combo = create_styled_combo_box()
        self.sc_hdwgcna_filter_combo.setEnabled(False)
        filter_layout.addWidget(self.sc_hdwgcna_filter_combo)

        filter_group_label = create_styled_label("筛选组别（可多选）", font_size=10, bold=False)
        filter_layout.addWidget(filter_group_label)

        self.sc_hdwgcna_filter_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.sc_hdwgcna_filter_list.setEnabled(False)
        filter_layout.addWidget(self.sc_hdwgcna_filter_list)

        stage1_layout.addWidget(filter_frame)

        sample_group_label = create_styled_label("样本列（批次校正）", font_size=11, bold=False)
        stage1_layout.addWidget(sample_group_label)
        self.sc_hdwgcna_sample_group_combo = create_styled_combo_box()
        self.sc_hdwgcna_sample_group_combo.addItem("Sample")
        stage1_layout.addWidget(self.sc_hdwgcna_sample_group_combo)

        self.sc_hdwgcna_recluster_checkbox = create_styled_checkbox("筛选后重新降维")
        self.sc_hdwgcna_recluster_checkbox.setChecked(True)
        stage1_layout.addWidget(self.sc_hdwgcna_recluster_checkbox)

        dims_row = QHBoxLayout()
        dims_label, dims_help = create_labeled_param_with_help(
            "降维维度数",
            "PCA和UMAP降维使用的维度数。\n默认30，值越大保留的信息越多，但计算时间越长。"
        )
        dims_row.addWidget(dims_label)
        dims_row.addWidget(dims_help)
        dims_row.addSpacing(8)
        self.sc_hdwgcna_dims_input = create_styled_line_edit()
        self.sc_hdwgcna_dims_input.setText("30")
        self.sc_hdwgcna_dims_input.setMinimumWidth(40)
        self.sc_hdwgcna_dims_input.setAlignment(Qt.AlignCenter)
        dims_row.addWidget(self.sc_hdwgcna_dims_input)
        stage1_layout.addLayout(dims_row)

        gene_select_title_row = QHBoxLayout()
        gene_select_label = create_styled_label("基因选择模式", font_size=11, bold=True)
        gene_select_title_row.addWidget(gene_select_label)
        self.sc_hdwgcna_gene_select_help_btn = create_questions_button("""基因选择模式说明

【fraction模式】（最常用，推荐）
- 按比例随机选择基因进行分析
- 常规分析：fraction = 0.05（5%），能过滤掉极稀有转录本，避免噪声主导相关性
- 纳入基因过少（< 2,000）：可放宽至 0.03（3%），以保留更多基因用于网络构建
- 追求更严格/聚焦：可适当提高至 0.07–0.10（7–10%），但可能会丢失低丰度但生物学上相关的基因
- 不想手动设 fraction：可改用"高变基因"模式，直接使用Seurat已计算的高变基因

【custom模式】（自定义基因集合）
- 使用指定的基因列表进行分析
- 基因列表放在 appdata/genelists 目录下
- 支持xlsx格式，第一列为基因名（无表头）
- 适用场景：已知关注的基因集合时

【高变基因模式】
- 使用Seurat已计算的高变基因（VariableFeatures）
- 默认值：3000个高变基因
- 适用场景：不想手动设fraction时可直接使用

注意：
- fraction模式是最常用的默认分析方法
- 知道基因集合时优选custom模式
- 一般不建议使用全部基因（计算量大且可能引入噪音）""")
        gene_select_title_row.addWidget(self.sc_hdwgcna_gene_select_help_btn)
        gene_select_title_row.addStretch()
        stage1_layout.addLayout(gene_select_title_row)

        gene_select_mode_row = QHBoxLayout()
        gene_select_mode_label = create_styled_label("选择模式", font_size=11, bold=False)
        gene_select_mode_row.addWidget(gene_select_mode_label)
        gene_select_mode_row.addSpacing(8)
        self.sc_hdwgcna_gene_select_mode_combo = create_styled_combo_box()
        self.sc_hdwgcna_gene_select_mode_combo.addItem("fraction（比例）")
        self.sc_hdwgcna_gene_select_mode_combo.addItem("custom（自定义基因列表）")
        self.sc_hdwgcna_gene_select_mode_combo.addItem("高变基因")
        self.sc_hdwgcna_gene_select_mode_combo.setMinimumWidth(180)
        gene_select_mode_row.addWidget(self.sc_hdwgcna_gene_select_mode_combo)
        gene_select_mode_row.addStretch()
        stage1_layout.addLayout(gene_select_mode_row)

        fraction_row = QHBoxLayout()
        fraction_label, fraction_help = create_labeled_param_with_help(
            "fraction值",
            "随机选择基因的比例。\n常规0.05（5%），范围0-1。\n基因过少可降至0.03，聚焦可提高至0.07-0.10。"
        )
        fraction_row.addWidget(fraction_label)
        fraction_row.addWidget(fraction_help)
        fraction_row.addSpacing(8)
        self.sc_hdwgcna_fraction_input = create_styled_line_edit()
        self.sc_hdwgcna_fraction_input.setText("0.05")
        self.sc_hdwgcna_fraction_input.setMinimumWidth(60)
        self.sc_hdwgcna_fraction_input.setAlignment(Qt.AlignCenter)
        fraction_row.addWidget(self.sc_hdwgcna_fraction_input)
        fraction_row.addStretch()
        stage1_layout.addLayout(fraction_row)

        custom_gene_row = QHBoxLayout()
        custom_gene_label, custom_gene_help = create_labeled_param_with_help(
            "基因列表",
            "从 appdata/genelists 目录选择基因列表。\n支持xlsx格式，第一列为基因名（无表头）。"
        )
        custom_gene_row.addWidget(custom_gene_label)
        custom_gene_row.addWidget(custom_gene_help)
        custom_gene_row.addSpacing(8)
        self.sc_hdwgcna_custom_gene_combo = create_styled_combo_box()
        self.sc_hdwgcna_custom_gene_combo.setMinimumWidth(180)
        custom_gene_row.addWidget(self.sc_hdwgcna_custom_gene_combo)
        custom_gene_row.addStretch()
        stage1_layout.addLayout(custom_gene_row)

        variable_gene_row = QHBoxLayout()
        variable_gene_label, variable_gene_help = create_labeled_param_with_help(
            "高变基因数量",
            "选择高变基因的数量。\n默认3000个。\n值越大基因越多，计算越慢。"
        )
        variable_gene_row.addWidget(variable_gene_label)
        variable_gene_row.addWidget(variable_gene_help)
        variable_gene_row.addSpacing(8)
        self.sc_hdwgcna_variable_gene_input = create_styled_line_edit()
        self.sc_hdwgcna_variable_gene_input.setText("3000")
        self.sc_hdwgcna_variable_gene_input.setMinimumWidth(60)
        self.sc_hdwgcna_variable_gene_input.setAlignment(Qt.AlignCenter)
        variable_gene_row.addWidget(self.sc_hdwgcna_variable_gene_input)
        variable_gene_row.addStretch()
        stage1_layout.addLayout(variable_gene_row)

        left_content_layout.addWidget(stage1_group)
        left_content_layout.addSpacing(8)

        # --- 阶段二参数 ---
        stage2_group = QFrame(left_content)
        stage2_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage2_group.setObjectName("styled_panel_stage2")
        stage2_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage2_layout = QVBoxLayout(stage2_group)
        stage2_layout.setContentsMargins(8, 8, 8, 8)

        stage2_title_row = QHBoxLayout()
        stage2_title = create_styled_label("阶段二参数（SetupForWGCNA+Metacell构建）", font_size=12, bold=True)
        stage2_title_row.addWidget(stage2_title)
        self.sc_hdwgcna_stage2_help_btn = create_questions_button("""阶段二：SetupForWGCNA+Metacell构建

功能：
- 设置hdWGCNA分析所需的数据结构
- 运行Harmony批次校正
- 构建Metacell（细胞聚合）
- 对Metacell进行归一化

参数说明：
- k: Metacell近邻数，默认25
- max_shared: Metacell共享细胞数，默认10
- min_cells: 最小细胞数，默认80

注意：
- 需要先运行阶段一""")
        stage2_title_row.addWidget(self.sc_hdwgcna_stage2_help_btn)
        stage2_layout.addLayout(stage2_title_row)

        k_row = QHBoxLayout()
        k_label, k_help = create_labeled_param_with_help(
            "k值",
            "Metacell近邻数。\n默认25，值越大Metacell越大，细胞聚合程度越高。"
        )
        k_row.addWidget(k_label)
        k_row.addWidget(k_help)
        k_row.addSpacing(8)
        self.sc_hdwgcna_k_input = create_styled_line_edit()
        self.sc_hdwgcna_k_input.setText("25")
        self.sc_hdwgcna_k_input.setMinimumWidth(40)
        self.sc_hdwgcna_k_input.setAlignment(Qt.AlignCenter)
        k_row.addWidget(self.sc_hdwgcna_k_input)
        stage2_layout.addLayout(k_row)

        max_shared_row = QHBoxLayout()
        max_shared_label, max_shared_help = create_labeled_param_with_help(
            "max_shared",
            "Metacell共享细胞数。\n默认10，一个细胞最多属于多少个Metacell。"
        )
        max_shared_row.addWidget(max_shared_label)
        max_shared_row.addWidget(max_shared_help)
        max_shared_row.addSpacing(8)
        self.sc_hdwgcna_max_shared_input = create_styled_line_edit()
        self.sc_hdwgcna_max_shared_input.setText("10")
        self.sc_hdwgcna_max_shared_input.setMinimumWidth(40)
        self.sc_hdwgcna_max_shared_input.setAlignment(Qt.AlignCenter)
        max_shared_row.addWidget(self.sc_hdwgcna_max_shared_input)
        stage2_layout.addLayout(max_shared_row)

        min_cells_row = QHBoxLayout()
        min_cells_label, min_cells_help = create_labeled_param_with_help(
            "min_cells",
            "最小细胞数。\n默认80，细胞数少于此值的分组将被跳过。"
        )
        min_cells_row.addWidget(min_cells_label)
        min_cells_row.addWidget(min_cells_help)
        min_cells_row.addSpacing(8)
        self.sc_hdwgcna_min_cells_input = create_styled_line_edit()
        self.sc_hdwgcna_min_cells_input.setText("80")
        self.sc_hdwgcna_min_cells_input.setMinimumWidth(40)
        self.sc_hdwgcna_min_cells_input.setAlignment(Qt.AlignCenter)
        min_cells_row.addWidget(self.sc_hdwgcna_min_cells_input)
        stage2_layout.addLayout(min_cells_row)

        left_content_layout.addWidget(stage2_group)
        left_content_layout.addSpacing(8)

        # --- 阶段三参数 ---
        stage3_group = QFrame(left_content)
        stage3_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage3_group.setObjectName("styled_panel_stage3")
        stage3_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage3_layout = QVBoxLayout(stage3_group)
        stage3_layout.setContentsMargins(8, 8, 8, 8)

        stage3_title_row = QHBoxLayout()
        stage3_title = create_styled_label("阶段三参数（软阈值选择）", font_size=12, bold=True)
        stage3_title_row.addWidget(stage3_title)
        self.sc_hdwgcna_stage3_help_btn = create_questions_button("""阶段三：软阈值选择

功能：
- 设置表达矩阵用于网络构建
- 测试不同power值的无标度网络拟合度
- 自动推荐最优软阈值

参数说明：
- 网络类型：unsigned（无符号）或signed（有符号）

注意：
- 需要先运行阶段一和阶段二""")
        stage3_title_row.addWidget(self.sc_hdwgcna_stage3_help_btn)
        stage3_layout.addLayout(stage3_title_row)

        network_type_row = QHBoxLayout()
        network_type_label, network_type_help = create_labeled_param_with_help(
            "网络类型",
            "网络构建的相关性类型。\n\nUnsigned: power范围6-12，不区分正负相关，通常需要较低power\nSigned: power范围9-18，区分正负相关，通常需要较高power（推荐用于单细胞）"
        )
        network_type_row.addWidget(network_type_label)
        network_type_row.addWidget(network_type_help)
        network_type_row.addSpacing(8)
        self.sc_hdwgcna_network_type_combo = create_styled_combo_box()
        self.sc_hdwgcna_network_type_combo.addItems(['signed', 'unsigned'])
        self.sc_hdwgcna_network_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        network_type_row.addWidget(self.sc_hdwgcna_network_type_combo)
        stage3_layout.addLayout(network_type_row)

        manual_power_row = QHBoxLayout()
        manual_power_label, manual_power_help = create_labeled_param_with_help(
            "手动软阈值",
            "如果不希望使用自动推荐的软阈值，可在此手动输入。\n留空则使用自动推荐值。\n通常取值范围为1-20。"
        )
        manual_power_row.addWidget(manual_power_label)
        manual_power_row.addWidget(manual_power_help)
        manual_power_row.addSpacing(8)
        self.sc_hdwgcna_manual_power_input = create_styled_line_edit()
        self.sc_hdwgcna_manual_power_input.setPlaceholderText("自动推荐")
        self.sc_hdwgcna_manual_power_input.setMinimumWidth(40)
        self.sc_hdwgcna_manual_power_input.setAlignment(Qt.AlignCenter)
        manual_power_row.addWidget(self.sc_hdwgcna_manual_power_input)
        stage3_layout.addLayout(manual_power_row)

        self.sc_hdwgcna_power_estimate_label = create_styled_label("推荐软阈值: -", font_size=10, bold=False)
        stage3_layout.addWidget(self.sc_hdwgcna_power_estimate_label)

        left_content_layout.addWidget(stage3_group)
        left_content_layout.addSpacing(8)

        # --- 阶段四参数 ---
        stage4_group = QFrame(left_content)
        stage4_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage4_group.setObjectName("styled_panel_stage4")
        stage4_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage4_layout = QVBoxLayout(stage4_group)
        stage4_layout.setContentsMargins(8, 8, 8, 8)

        stage4_title_row = QHBoxLayout()
        stage4_title = create_styled_label("阶段四参数（网络构建）", font_size=12, bold=True)
        stage4_title_row.addWidget(stage4_title)
        self.sc_hdwgcna_stage4_help_btn = create_questions_button("""阶段四：网络构建(ConstructNetwork)

功能：
- 使用选定的软阈值构建共表达网络
- 计算基因间的拓扑重叠矩阵(TOM)
- 进行层次聚类识别模块

参数说明：
- 软阈值power值：建议使用阶段三推荐的值
- 最小模块大小：默认30

注意：
- 模块数量会影响后续分析的分辨率
- 太小的模块可能噪声较大""")
        stage4_title_row.addWidget(self.sc_hdwgcna_stage4_help_btn)
        stage4_layout.addLayout(stage4_title_row)

        power_row = QHBoxLayout()
        power_label, power_help = create_labeled_param_with_help(
            "软阈值power值",
            "软阈值幂次。\n用于将相关性矩阵转换为邻接矩阵，使网络近似服从无标度分布。\n建议使用阶段三推荐的值。"
        )
        power_row.addWidget(power_label)
        power_row.addWidget(power_help)
        power_row.addSpacing(8)
        self.sc_hdwgcna_power_input = create_styled_line_edit()
        self.sc_hdwgcna_power_input.setText("6")
        self.sc_hdwgcna_power_input.setMinimumWidth(40)
        self.sc_hdwgcna_power_input.setAlignment(Qt.AlignCenter)
        power_row.addWidget(self.sc_hdwgcna_power_input)
        stage4_layout.addLayout(power_row)

        min_module_row = QHBoxLayout()
        min_module_label, min_module_help = create_labeled_param_with_help(
            "最小模块大小",
            "识别的模块中基因的最小数量。\n默认30，值越小产生的模块越多，值越大产生的模块越少。"
        )
        min_module_row.addWidget(min_module_label)
        min_module_row.addWidget(min_module_help)
        min_module_row.addSpacing(8)
        self.sc_hdwgcna_min_module_input = create_styled_line_edit()
        self.sc_hdwgcna_min_module_input.setText("30")
        self.sc_hdwgcna_min_module_input.setMinimumWidth(40)
        self.sc_hdwgcna_min_module_input.setAlignment(Qt.AlignCenter)
        min_module_row.addWidget(self.sc_hdwgcna_min_module_input)
        stage4_layout.addLayout(min_module_row)

        merge_threshold_row = QHBoxLayout()
        merge_threshold_label, merge_threshold_help = create_labeled_param_with_help(
            "模块合并阈值",
            "模块特征基因(MEs)之间的相似性阈值。\n高于此阈值的模块将被合并。\n默认0.25，值越大合并的模块越少。"
        )
        merge_threshold_row.addWidget(merge_threshold_label)
        merge_threshold_row.addWidget(merge_threshold_help)
        merge_threshold_row.addSpacing(8)
        self.sc_hdwgcna_merge_threshold_input = create_styled_line_edit()
        self.sc_hdwgcna_merge_threshold_input.setText("0.25")
        self.sc_hdwgcna_merge_threshold_input.setMinimumWidth(40)
        self.sc_hdwgcna_merge_threshold_input.setAlignment(Qt.AlignCenter)
        merge_threshold_row.addWidget(self.sc_hdwgcna_merge_threshold_input)
        stage4_layout.addLayout(merge_threshold_row)

        left_content_layout.addWidget(stage4_group)
        left_content_layout.addSpacing(8)

        # --- 图表设置 ---
        plot_settings_group = QFrame(left_content)
        plot_settings_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        plot_settings_group.setObjectName("styled_panel_plot_settings")
        plot_settings_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        plot_settings_layout = QVBoxLayout(plot_settings_group)
        plot_settings_layout.setContentsMargins(8, 8, 8, 8)

        plot_settings_title = create_styled_label("图表设置", font_size=12, bold=True)
        plot_settings_layout.addWidget(plot_settings_title)

        plot_width_row = QHBoxLayout()
        plot_width_label, plot_width_help = create_labeled_param_with_help(
            "图表宽度",
            "生成图表的宽度（像素）。\n默认1200，值越大图表越宽。"
        )
        plot_width_row.addWidget(plot_width_label)
        plot_width_row.addWidget(plot_width_help)
        plot_width_row.addSpacing(8)
        self.sc_hdwgcna_plot_width_input = create_styled_line_edit()
        self.sc_hdwgcna_plot_width_input.setText("1200")
        self.sc_hdwgcna_plot_width_input.setMinimumWidth(60)
        self.sc_hdwgcna_plot_width_input.setAlignment(Qt.AlignCenter)
        plot_width_row.addWidget(self.sc_hdwgcna_plot_width_input)
        plot_settings_layout.addLayout(plot_width_row)

        plot_height_row = QHBoxLayout()
        plot_height_label, plot_height_help = create_labeled_param_with_help(
            "图表高度",
            "生成图表的高度（像素）。\n默认800，值越大图表越高。"
        )
        plot_height_row.addWidget(plot_height_label)
        plot_height_row.addWidget(plot_height_help)
        plot_height_row.addSpacing(8)
        self.sc_hdwgcna_plot_height_input = create_styled_line_edit()
        self.sc_hdwgcna_plot_height_input.setText("800")
        self.sc_hdwgcna_plot_height_input.setMinimumWidth(60)
        self.sc_hdwgcna_plot_height_input.setAlignment(Qt.AlignCenter)
        plot_height_row.addWidget(self.sc_hdwgcna_plot_height_input)
        plot_settings_layout.addLayout(plot_height_row)

        left_content_layout.addWidget(plot_settings_group)
        left_content_layout.addSpacing(8)

        # --- 阶段五参数 ---
        stage5_group = QFrame(left_content)
        stage5_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage5_group.setObjectName("styled_panel_stage5")
        stage5_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage5_layout = QVBoxLayout(stage5_group)
        stage5_layout.setContentsMargins(8, 8, 8, 8)

        stage5_title_row = QHBoxLayout()
        stage5_title = create_styled_label("阶段五（模块可视化）", font_size=12, bold=True)
        stage5_title_row.addWidget(stage5_title)
        self.sc_hdwgcna_stage5_help_btn = create_questions_button("""阶段五：模块可视化(Dendrogram+KMEs)

功能：
- 计算模块特征基因(MEs)
- 计算基于特征基因的连接性(kME)
- 绘制每个模块按kME排序的基因
- 重命名模块

注意：
- 需要先运行阶段四""")
        stage5_title_row.addWidget(self.sc_hdwgcna_stage5_help_btn)
        stage5_layout.addLayout(stage5_title_row)

        left_content_layout.addWidget(stage5_group)
        left_content_layout.addSpacing(8)

        # --- 阶段六参数 ---
        stage6_group = QFrame(left_content)
        stage6_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage6_group.setObjectName("styled_panel_stage6")
        stage6_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage6_layout = QVBoxLayout(stage6_group)
        stage6_layout.setContentsMargins(8, 8, 8, 8)

        stage6_title_row = QHBoxLayout()
        stage6_title = create_styled_label("阶段六（模块特征图）", font_size=12, bold=True)
        stage6_title_row.addWidget(stage6_title)
        self.sc_hdwgcna_stage6_help_btn = create_questions_button("""阶段六：模块特征图(hMEs)

功能：
- 计算模块表达分数(ModuleExprScore)
- 绘制每个模块hMEs的特征图
- 保存每个模块的单独特征图

注意：
- 需要先运行阶段五""")
        stage6_title_row.addWidget(self.sc_hdwgcna_stage6_help_btn)
        stage6_layout.addLayout(stage6_title_row)

        left_content_layout.addWidget(stage6_group)
        left_content_layout.addSpacing(8)

        # --- 阶段七参数 ---
        stage7_group = QFrame(left_content)
        stage7_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage7_group.setObjectName("styled_panel_stage7")
        stage7_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage7_layout = QVBoxLayout(stage7_group)
        stage7_layout.setContentsMargins(8, 8, 8, 8)

        stage7_title_row = QHBoxLayout()
        stage7_title = create_styled_label("阶段七（相关图）", font_size=12, bold=True)
        stage7_title_row.addWidget(stage7_title)
        self.sc_hdwgcna_stage7_help_btn = create_questions_button("""阶段七：相关图

功能：
- 绘制模块相关图(Correlogram)
- 绘制模块点图(DotPlot)
- 绘制模块网络图(ModuleNetworkPlot)
- 分析模块特征基因之间的相关性

注意：
- 需要先运行阶段六""")
        stage7_title_row.addWidget(self.sc_hdwgcna_stage7_help_btn)
        stage7_layout.addLayout(stage7_title_row)

        left_content_layout.addWidget(stage7_group)
        left_content_layout.addSpacing(8)

        # --- 阶段八参数 ---
        stage8_group = QFrame()
        stage8_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage8_group.setObjectName("styled_panel_stage8")
        stage8_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage8_layout = QVBoxLayout(stage8_group)
        stage8_layout.setContentsMargins(8, 8, 8, 8)

        stage8_title_row = QHBoxLayout()
        stage8_title = create_styled_label("阶段八（ModuleUMAP）", font_size=12, bold=True)
        stage8_title_row.addWidget(stage8_title)
        self.sc_hdwgcna_stage8_help_btn = create_questions_button("""阶段八：ModuleUMAP

功能：
- 基于枢纽基因运行UMAP降维
- 绘制Module UMAP图

注意：
- 需要先运行阶段七""")
        stage8_title_row.addWidget(self.sc_hdwgcna_stage8_help_btn)
        stage8_layout.addLayout(stage8_title_row)

        left_content_layout.addWidget(stage8_group)
        left_content_layout.addSpacing(8)

        # --- 阶段九参数 ---
        stage9_group = QFrame()
        stage9_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage9_group.setObjectName("styled_panel_stage9")
        stage9_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage9_layout = QVBoxLayout(stage9_group)
        stage9_layout.setContentsMargins(8, 8, 8, 8)

        stage9_title_row = QHBoxLayout()
        stage9_title = create_styled_label("阶段九参数（GO和KEGG富集分析）", font_size=12, bold=True)
        stage9_title_row.addWidget(stage9_title)
        self.sc_hdwgcna_stage9_help_btn = create_questions_button("""阶段九：GO和KEGG富集分析

注意：此步骤运行较慢且需要联网

功能：
- 使用clusterProfiler对每个模块进行GO富集分析（BP/MF/CC）
- 使用clusterProfiler对每个模块进行KEGG通路富集分析
- 生成气泡图和条形图展示富集结果
- 导出富集分析结果表格

参数说明：
- 物种：选择分析的物种（默认人类hsa）
- GO校正p值阈值：筛选显著GO条目的阈值
- KEGG校正p值阈值：筛选显著KEGG条目的阈值
- GO展示条目数：每个模块展示的GO条目数量
- KEGG展示条目数：每个模块展示的KEGG条目数量

注意：
- 需要先运行阶段四（网络构建）
- 需要安装clusterProfiler和对应物种的注释包""")
        stage9_title_row.addWidget(self.sc_hdwgcna_stage9_help_btn)
        stage9_layout.addLayout(stage9_title_row)

        organism_row = QHBoxLayout()
        organism_label = create_styled_label("物种", font_size=10, bold=False)
        organism_row.addWidget(organism_label)
        self.sc_hdwgcna_organism_combo = create_styled_combo_box()
        self.sc_hdwgcna_organism_combo.addItems(["hsa", "mmu", "rno", "dme"])
        self.sc_hdwgcna_organism_combo.setCurrentText("hsa")
        organism_row.addWidget(self.sc_hdwgcna_organism_combo)
        stage9_layout.addLayout(organism_row)

        module_label = create_styled_label("模块选择（可多选）", font_size=11, bold=False)
        stage9_layout.addWidget(module_label)

        self.sc_hdwgcna_module_list_go = create_styled_list_widget(fixed_height=100, multi_selection=True)
        stage9_layout.addWidget(self.sc_hdwgcna_module_list_go)

        go_padj_row = QHBoxLayout()
        go_padj_label, go_padj_help = create_labeled_param_with_help(
            "GO校正p值阈值",
            "GO富集分析的校正p值阈值。\n默认0.05，值越小筛选越严格。"
        )
        go_padj_row.addWidget(go_padj_label)
        go_padj_row.addWidget(go_padj_help)
        go_padj_row.addSpacing(8)
        self.sc_hdwgcna_go_padj_input = create_styled_line_edit()
        self.sc_hdwgcna_go_padj_input.setText("0.05")
        self.sc_hdwgcna_go_padj_input.setMinimumWidth(60)
        self.sc_hdwgcna_go_padj_input.setAlignment(Qt.AlignCenter)
        go_padj_row.addWidget(self.sc_hdwgcna_go_padj_input)
        stage9_layout.addLayout(go_padj_row)

        kegg_padj_row = QHBoxLayout()
        kegg_padj_label, kegg_padj_help = create_labeled_param_with_help(
            "KEGG校正p值阈值",
            "KEGG富集分析的校正p值阈值。\n默认0.05，值越小筛选越严格。"
        )
        kegg_padj_row.addWidget(kegg_padj_label)
        kegg_padj_row.addWidget(kegg_padj_help)
        kegg_padj_row.addSpacing(8)
        self.sc_hdwgcna_kegg_padj_input = create_styled_line_edit()
        self.sc_hdwgcna_kegg_padj_input.setText("0.05")
        self.sc_hdwgcna_kegg_padj_input.setMinimumWidth(60)
        self.sc_hdwgcna_kegg_padj_input.setAlignment(Qt.AlignCenter)
        kegg_padj_row.addWidget(self.sc_hdwgcna_kegg_padj_input)
        stage9_layout.addLayout(kegg_padj_row)

        go_top_n_row = QHBoxLayout()
        go_top_n_label, go_top_n_help = create_labeled_param_with_help(
            "GO展示条目数",
            "每个模块展示的GO条目数量。\n默认15，值越大展示越多条目。"
        )
        go_top_n_row.addWidget(go_top_n_label)
        go_top_n_row.addWidget(go_top_n_help)
        go_top_n_row.addSpacing(8)
        self.sc_hdwgcna_go_top_n_input = create_styled_line_edit()
        self.sc_hdwgcna_go_top_n_input.setText("15")
        self.sc_hdwgcna_go_top_n_input.setMinimumWidth(40)
        self.sc_hdwgcna_go_top_n_input.setAlignment(Qt.AlignCenter)
        go_top_n_row.addWidget(self.sc_hdwgcna_go_top_n_input)
        stage9_layout.addLayout(go_top_n_row)

        kegg_top_n_row = QHBoxLayout()
        kegg_top_n_label, kegg_top_n_help = create_labeled_param_with_help(
            "KEGG展示条目数",
            "每个模块展示的KEGG条目数量。\n默认15，值越大展示越多条目。"
        )
        kegg_top_n_row.addWidget(kegg_top_n_label)
        kegg_top_n_row.addWidget(kegg_top_n_help)
        kegg_top_n_row.addSpacing(8)
        self.sc_hdwgcna_kegg_top_n_input = create_styled_line_edit()
        self.sc_hdwgcna_kegg_top_n_input.setText("15")
        self.sc_hdwgcna_kegg_top_n_input.setMinimumWidth(40)
        self.sc_hdwgcna_kegg_top_n_input.setAlignment(Qt.AlignCenter)
        kegg_top_n_row.addWidget(self.sc_hdwgcna_kegg_top_n_input)
        stage9_layout.addLayout(kegg_top_n_row)

        left_content_layout.addWidget(stage9_group)
        left_content_layout.addSpacing(8)

        # --- 阶段十参数 ---
        stage10_group = QFrame()
        stage10_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage10_group.setObjectName("styled_panel_stage10")
        stage10_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage10_layout = QVBoxLayout(stage10_group)
        stage10_layout.setContentsMargins(8, 8, 8, 8)

        stage10_title_row = QHBoxLayout()
        stage10_title = create_styled_label("阶段十（导出基因集合）", font_size=12, bold=True)
        stage10_title_row.addWidget(stage10_title)
        self.sc_hdwgcna_stage10_help_btn = create_questions_button("""阶段十：导出基因集合

功能：
- 将每个模块中的基因列表导出为xlsx文件
- 导出枢纽基因表
- 导出完整模块信息表

注意：
- 需要先运行阶段四""")
        stage10_title_row.addWidget(self.sc_hdwgcna_stage10_help_btn)
        stage10_layout.addLayout(stage10_title_row)

        left_content_layout.addWidget(stage10_group)
        left_content_layout.addStretch()

        left_scroll.setWidget(left_content)
        left_layout.addWidget(left_scroll)
        main_layout.addWidget(left_panel)

        # ================ 中间图表区 ================
        center_panel = QWidget(self.sc_hdwgcna_page)
        center_layout = QVBoxLayout(center_panel)

        self.sc_hdwgcna_plot_tabs = create_styled_tab_widget(parent=center_panel)

        _, self.sc_hdwgcna_label_umap = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "UMAP图",
            default_text="请运行阶段一",
            data_hint_template="数据: {dataset_name}\n\n请设置参数并点击「阶段一：加载Seurat对象+重新降维」"
        )
        _, self.sc_hdwgcna_label_soft_threshold = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "软阈值选择图",
            default_text="请运行阶段三",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一和阶段二"
        )
        _, self.sc_hdwgcna_label_gene_dendro = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "基因聚类树+模块色条",
            default_text="请运行阶段四",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段三"
        )
        _, self.sc_hdwgcna_label_kme = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "kME得分图",
            default_text="请运行阶段五",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段四"
        )
        _, self.sc_hdwgcna_label_hme = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "模块特征图(hMEs)",
            default_text="请运行阶段六",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段五"
        )
        _, self.sc_hdwgcna_label_correlogram = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "模块相关图",
            default_text="请运行阶段七",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段六"
        )
        _, self.sc_hdwgcna_label_dotplot = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "模块点图",
            default_text="请运行阶段七",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段六"
        )
        _, self.sc_hdwgcna_label_module_umap = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "模块UMAP图",
            default_text="请运行阶段八",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段七"
        )
        _, self.sc_hdwgcna_label_go_bubble = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "GO气泡图",
            default_text="请运行阶段九",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段四，并选择模块进行GO/KEGG分析"
        )
        _, self.sc_hdwgcna_label_go_bar = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "GO条形图",
            default_text="请运行阶段九",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段四，并选择模块进行GO/KEGG分析"
        )
        _, self.sc_hdwgcna_label_kegg_bar = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "KEGG条形图",
            default_text="请运行阶段九",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段四，并选择模块进行GO/KEGG分析"
        )
        _, self.sc_hdwgcna_label_kegg_bubble = create_styled_image_tab(
            self.sc_hdwgcna_plot_tabs, "KEGG气泡图",
            default_text="请运行阶段九",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一至阶段四，并选择模块进行GO/KEGG分析"
        )

        center_layout.addWidget(self.sc_hdwgcna_plot_tabs)
        main_layout.addWidget(center_panel, 1)

        # ================ 右侧运行+导出面板 ================
        right_panel, right_layout = create_styled_panel(parent=self.sc_hdwgcna_page)
        right_panel.setMinimumWidth(220)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        run_title = create_styled_label("运行区域", font_size=12, bold=True)
        right_layout.addWidget(run_title)

        self.sc_hdwgcna_btn_stage1 = create_styled_button("▶ 阶段一：加载Seurat对象", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage1)

        self.sc_hdwgcna_btn_stage2 = create_styled_button("▶ 阶段二：Metacell构建", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage2)

        self.sc_hdwgcna_btn_stage3 = create_styled_button("▶ 阶段三：软阈值选择", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage3)

        self.sc_hdwgcna_btn_stage4 = create_styled_button("▶ 阶段四：网络构建", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage4)

        self.sc_hdwgcna_btn_stage5 = create_styled_button("▶ 阶段五：模块可视化", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage5)

        self.sc_hdwgcna_btn_stage6 = create_styled_button("▶ 阶段六：模块特征图", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage6)

        self.sc_hdwgcna_btn_stage7 = create_styled_button("▶ 阶段七：相关图", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage7)

        self.sc_hdwgcna_btn_stage8 = create_styled_button("▶ 阶段八：ModuleUMAP", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage8)

        self.sc_hdwgcna_btn_stage9 = create_styled_button("▶ 阶段九：GO/KEGG分析", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage9)

        self.sc_hdwgcna_btn_stage10 = create_styled_button("▶ 阶段十：导出基因集合", font_size=11, button_type='run')
        right_layout.addWidget(self.sc_hdwgcna_btn_stage10)

        right_layout.addSpacing(10)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        right_layout.addWidget(export_title)

        right_layout.addSpacing(8)

        self.sc_hdwgcna_btn_export_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        right_layout.addWidget(self.sc_hdwgcna_btn_export_png)

        self.sc_hdwgcna_btn_export_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        right_layout.addWidget(self.sc_hdwgcna_btn_export_pdf)

        self.sc_hdwgcna_btn_export_svg = create_styled_button("导出SVG", font_size=10, button_type='export')
        right_layout.addWidget(self.sc_hdwgcna_btn_export_svg)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.sc_hdwgcna_page