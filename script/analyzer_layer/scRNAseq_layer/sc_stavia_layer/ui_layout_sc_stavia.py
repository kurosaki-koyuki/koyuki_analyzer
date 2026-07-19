# -*- coding: utf-8 -*-
"""
单细胞StaVIA分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_spinbox, create_styled_text_edit,
    create_styled_tab_widget, create_styled_image_tab, create_styled_table,
    create_questions_button, create_labeled_param_with_help
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class ScStaviaPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_stavia_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.sc_stavia_page.findChild(QLabel, "sc_stavia_bg")
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

        title_label = self.sc_stavia_page.findChild(QLabel, "sc_stavia_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.sc_stavia_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or
                                       isinstance(child, type(create_questions_button()))):
                continue
            child.setStyleSheet(button_style)

        run_button_style = get_stylesheet_for_widget('run_button')
        if hasattr(self, 'btn_run_stavia'):
            self.btn_run_stavia.setStyleSheet(run_button_style)

        export_button_style = get_stylesheet_for_widget('export_button')
        for btn_name in ['btn_export_png', 'btn_export_pdf', 'btn_export_svg']:
            if hasattr(self, btn_name):
                getattr(self, btn_name).setStyleSheet(export_button_style)

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.sc_stavia_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.sc_stavia_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.sc_stavia_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_stavia_page.findChildren(QLabel):
            if child.objectName() != "sc_stavia_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.sc_stavia_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_stavia_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.sc_stavia_page.findChild(QWidget, "sc_stavia_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

    def create_page(self):
        self.sc_stavia_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.sc_stavia_page)
        bg_label.setObjectName("sc_stavia_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.sc_stavia_page)
        overlay.setObjectName("sc_stavia_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_sc_stavia = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_sc_stavia)

        title_label = QLabel("StaVIA轨迹分析")
        title_label.setObjectName("sc_stavia_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.sc_stavia_page, mod_instance)

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

        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ================ 左侧参数面板 ================
        left_panel, left_panel_layout = create_styled_panel(parent=overlay)
        left_panel.setMinimumWidth(340)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        left_scroll = QScrollArea(left_panel)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setStyleSheet("background: transparent;")

        left_content = QWidget(left_scroll)
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setContentsMargins(8, 8, 8, 8)

        # --- 细胞筛选组 ---
        filter_group = QFrame(left_content)
        filter_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter_group.setObjectName("styled_panel_filter")
        filter_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setContentsMargins(8, 8, 8, 8)

        filter_title_row = QHBoxLayout()
        filter_title = create_styled_label("细胞筛选", font_size=12, bold=True)
        filter_title_row.addWidget(filter_title)
        self.filter_help_btn = create_questions_button("""细胞筛选说明

功能：
- 选择特定细胞亚群进行StaVIA轨迹分析
- 支持主注释筛选和两个附加筛选器
- 所有筛选条件取交集（AND逻辑）

主注释：
- 选择主要的细胞类型注释列
- 在列表中选择要分析的细胞类型（可多选）
- 未选择或全部选择时分析所有细胞

筛选器1/筛选器2：
- 勾选"启用筛选"后生效
- 选择筛选分类列和筛选组别
- 可用于进一步缩小分析范围

注意：
- 筛选后细胞数量过少可能导致分析失败
- 建议筛选后至少保留100个以上细胞
- 筛选后建议勾选"重新降维"以获得更准确的结果""")
        filter_title_row.addWidget(self.filter_help_btn)
        filter_layout.addLayout(filter_title_row)

        main_anno_label = create_styled_label("主注释（分组）", font_size=11, bold=False)
        filter_layout.addWidget(main_anno_label)
        self.stavia_main_combo = create_styled_combo_box()
        filter_layout.addWidget(self.stavia_main_combo)
        self.stavia_main_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        filter_layout.addWidget(self.stavia_main_list)

        filter1_frame = QFrame()
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)
        filter1_layout.setContentsMargins(8, 8, 8, 8)

        filter1_header = QHBoxLayout()
        self.stavia_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.stavia_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=10, bold=False)
        filter1_layout.addWidget(filter1_col_label)
        self.stavia_filter1_combo = create_styled_combo_box()
        self.stavia_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.stavia_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=10, bold=False)
        filter1_layout.addWidget(filter1_group_label)
        self.stavia_filter1_list = create_styled_list_widget(fixed_height=60, multi_selection=True)
        self.stavia_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.stavia_filter1_list)

        filter_layout.addWidget(filter1_frame)

        filter2_frame = QFrame()
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)
        filter2_layout.setContentsMargins(8, 8, 8, 8)

        filter2_header = QHBoxLayout()
        self.stavia_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.stavia_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=10, bold=False)
        filter2_layout.addWidget(filter2_col_label)
        self.stavia_filter2_combo = create_styled_combo_box()
        self.stavia_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.stavia_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=10, bold=False)
        filter2_layout.addWidget(filter2_group_label)
        self.stavia_filter2_list = create_styled_list_widget(fixed_height=60, multi_selection=True)
        self.stavia_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.stavia_filter2_list)

        filter_layout.addWidget(filter2_frame)

        re_dim_row = QHBoxLayout()
        re_dim_label, re_dim_help = create_labeled_param_with_help(
            "筛选后重新降维",
            "勾选后将使用筛选后的数据重新进行PCA和UMAP降维。\n建议筛选细胞后勾选此选项以获得更准确的轨迹分析结果。"
        )
        re_dim_row.addWidget(re_dim_label)
        re_dim_row.addWidget(re_dim_help)
        self.chk_re_dim = create_styled_checkbox("启用")
        re_dim_row.addWidget(self.chk_re_dim)
        filter_layout.addLayout(re_dim_row)

        left_content_layout.addWidget(filter_group)
        left_content_layout.addSpacing(8)

        # --- 分析参数组 ---
        param_group = QFrame(left_content)
        param_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        param_group.setObjectName("styled_panel_params")
        param_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        param_layout = QVBoxLayout(param_group)
        param_layout.setContentsMargins(8, 8, 8, 8)

        param_title_row = QHBoxLayout()
        param_title = create_styled_label("分析参数", font_size=12, bold=True)
        param_title_row.addWidget(param_title)
        self.stavia_help_btn = create_questions_button("""StaVIA轨迹分析参数说明

功能概述：
StaVIA（Single-cell Trajectory Analysis using VIA）是一种基于随机游走的单细胞轨迹分析方法，能够推断细胞分化的方向和伪时间。

核心参数：

【使用表达矩阵】
- 选择用于构建轨迹的表达矩阵
- 通常使用PCA降维后的结果（X_pca）
- 确保数据已进行预处理（标准化、归一化）

【PCA成分数】
- 使用的PCA主成分数量
- 默认30，值越大保留的信息越多，但计算时间越长
- 建议范围：10-50

【KNN邻居数】
- 构建K-NN图时使用的邻居数量
- 默认15，值越小图越稀疏，值越大图越密集
- 建议范围：5-50

【聚类分辨率】
- Leiden聚类的分辨率参数
- 默认1.5，值越大聚类越细，产生的cluster越多
- 建议范围：0.1-5.0

【内存参数】
- 随机游走的内存参数
- 默认10，值越大轨迹推断越平滑
- 建议范围：1-50

【主注释列】
- 选择主要的细胞类型注释列（obs中的列）
- 用于着色、注释和轨迹分析
- 同时作为筛选的主注释

【嵌入空间】
- 选择可视化的嵌入空间（UMAP/TSNE）
- 默认X_umap

运行要求：
- 需要先在scRNAseq主页加载数据
- 需要有PCA降维结果（X_pca）
- 需要有UMAP/TSNE嵌入（X_umap）
- 需要有细胞类型注释列

输出结果：
- 谱系饼图：展示各细胞类型在轨迹中的分布
- 伪时间图：展示细胞的伪时间值
- 轨迹曲线：展示推断的轨迹路径
- Atlas视图：展示轨迹的全局视图
- 轨迹箭头图：展示细胞分化方向（按cluster着色）
- 轨迹箭头图(PT)：展示细胞分化方向（按伪时间着色）""")
        param_title_row.addWidget(self.stavia_help_btn)
        param_layout.addLayout(param_title_row)

        row1 = QHBoxLayout()
        use_rep_label, use_rep_help = create_labeled_param_with_help(
            "使用表达矩阵",
            "选择用于构建轨迹的表达。\n通常选择'X_pca'，即PCA降维后的结果。"
        )
        row1.addWidget(use_rep_label)
        row1.addWidget(use_rep_help)
        self.cb_use_rep = create_styled_combo_box()
        self.cb_use_rep.addItems(['X_pca'])
        row1.addWidget(self.cb_use_rep)
        param_layout.addLayout(row1)

        row2 = QHBoxLayout()
        ncomps_label, ncomps_help = create_labeled_param_with_help(
            "PCA成分数",
            "使用的PCA主成分数量。\n默认30，值越大保留的信息越多，但计算时间越长。\n建议范围：10-50。"
        )
        row2.addWidget(ncomps_label)
        row2.addWidget(ncomps_help)
        self.spin_ncomps = create_styled_spinbox(min_value=5, max_value=100, default_value=30)
        row2.addWidget(self.spin_ncomps)
        param_layout.addLayout(row2)

        row3 = QHBoxLayout()
        knn_label, knn_help = create_labeled_param_with_help(
            "KNN邻居数",
            "构建K-NN图时使用的邻居数量。\n默认15，值越小图越稀疏，值越大图越密集。\n建议范围：5-50。"
        )
        row3.addWidget(knn_label)
        row3.addWidget(knn_help)
        self.spin_knn = create_styled_spinbox(min_value=5, max_value=100, default_value=15)
        row3.addWidget(self.spin_knn)
        param_layout.addLayout(row3)

        row4 = QHBoxLayout()
        resolution_label, resolution_help = create_labeled_param_with_help(
            "聚类分辨率",
            "Leiden聚类的分辨率参数。\n默认1.5，值越大聚类越细，产生的cluster越多。\n建议范围：0.1-5.0。"
        )
        row4.addWidget(resolution_label)
        row4.addWidget(resolution_help)
        self.spin_resolution = create_styled_line_edit()
        self.spin_resolution.setText("1.5")
        self.spin_resolution.setMinimumWidth(60)
        self.spin_resolution.setAlignment(Qt.AlignCenter)
        row4.addWidget(self.spin_resolution)
        param_layout.addLayout(row4)

        row5 = QHBoxLayout()
        memory_label, memory_help = create_labeled_param_with_help(
            "内存参数",
            "随机游走的内存参数。\n默认10，值越大轨迹推断越平滑。\n建议范围：1-50。"
        )
        row5.addWidget(memory_label)
        row5.addWidget(memory_help)
        self.spin_memory = create_styled_spinbox(min_value=1, max_value=50, default_value=10)
        row5.addWidget(self.spin_memory)
        param_layout.addLayout(row5)

        row6 = QHBoxLayout()
        basis_label, basis_help = create_labeled_param_with_help(
            "嵌入空间",
            "选择可视化的嵌入空间（UMAP/TSNE）。\n默认X_umap。\n需要先计算UMAP降维。"
        )
        row6.addWidget(basis_label)
        row6.addWidget(basis_help)
        self.cb_basis = create_styled_combo_box()
        self.cb_basis.addItems(['X_umap'])
        row6.addWidget(self.cb_basis)
        param_layout.addLayout(row6)

        left_content_layout.addWidget(param_group)
        left_content_layout.addStretch()

        left_scroll.setWidget(left_content)
        left_panel_layout.addWidget(left_scroll)

        main_layout.addWidget(left_panel)

        # ================ 中间结果面板 ================
        result_panel = QWidget()
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(0, 0, 0, 0)

        result_title = create_styled_label("分析结果", font_size=14, bold=True)
        result_layout.addWidget(result_title)

        self.tab_widget = create_styled_tab_widget()

        _, self.lbl_piechart = create_styled_image_tab(
            self.tab_widget, "谱系饼图",
            default_text="请运行StaVIA分析",
            data_hint_template="数据: {dataset_name}\n\n请设置参数并点击「运行StaVIA分析」"
        )

        _, self.lbl_pt = create_styled_image_tab(
            self.tab_widget, "伪时间图",
            default_text="请运行StaVIA分析",
            data_hint_template="数据: {dataset_name}\n\n请设置参数并点击「运行StaVIA分析」"
        )

        _, self.lbl_trajectory = create_styled_image_tab(
            self.tab_widget, "轨迹曲线",
            default_text="请运行StaVIA分析",
            data_hint_template="数据: {dataset_name}\n\n请设置参数并点击「运行StaVIA分析」"
        )

        _, self.lbl_atlas = create_styled_image_tab(
            self.tab_widget, "Atlas视图",
            default_text="请运行StaVIA分析",
            data_hint_template="数据: {dataset_name}\n\n请设置参数并点击「运行StaVIA分析」"
        )

        _, self.lbl_streamplot_cluster = create_styled_image_tab(
            self.tab_widget, "轨迹箭头图",
            default_text="请运行StaVIA分析",
            data_hint_template="数据: {dataset_name}\n\n请设置参数并点击「运行StaVIA分析」"
        )

        _, self.lbl_streamplot_pt = create_styled_image_tab(
            self.tab_widget, "轨迹箭头图(PT)",
            default_text="请运行StaVIA分析",
            data_hint_template="数据: {dataset_name}\n\n请设置参数并点击「运行StaVIA分析」"
        )

        result_layout.addWidget(self.tab_widget)

        main_layout.addWidget(result_panel)
        main_layout.setStretch(1, 1)

        # ================ 右侧运行+导出面板 ================
        right_panel, right_layout = create_styled_panel(parent=overlay)
        right_panel.setMinimumWidth(220)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        run_title = create_styled_label("运行区域", font_size=12, bold=True)
        right_layout.addWidget(run_title)

        right_layout.addSpacing(8)

        self.btn_run_stavia = create_styled_button("▶ 运行StaVIA分析", font_size=12, button_type='run')
        right_layout.addWidget(self.btn_run_stavia)

        right_layout.addSpacing(15)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        right_layout.addWidget(export_title)

        right_layout.addSpacing(8)

        self.btn_export_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        right_layout.addWidget(self.btn_export_png)

        right_layout.addSpacing(4)

        self.btn_export_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        right_layout.addWidget(self.btn_export_pdf)

        right_layout.addSpacing(4)

        self.btn_export_svg = create_styled_button("导出SVG", font_size=10, button_type='export')
        right_layout.addWidget(self.btn_export_svg)

        right_layout.addSpacing(15)

        log_title = create_styled_label("运行日志", font_size=12, bold=True)
        right_layout.addWidget(log_title)

        self.log_text = create_styled_text_edit(read_only=True)
        self.log_text.setFont(get_font_for_widget('label', 9))
        right_layout.addWidget(self.log_text)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        layout.addWidget(main_content)

        self.update_styles()

        return self.sc_stavia_page
