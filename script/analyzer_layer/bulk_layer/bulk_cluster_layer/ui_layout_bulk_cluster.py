# -*- coding: utf-8 -*-
"""
bulk 一致性分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
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


class BulkClusterPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        """更新背景图"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_cluster_page.findChild(QLabel, "bulk_cluster_bg")
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

        title_label = self.bulk_cluster_page.findChild(QLabel, "bulk_cluster_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_cluster_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or
                                       child.objectName().startswith("number_input_btn_") or
                                       isinstance(child, type(create_questions_button()))):
                continue
            child.setStyleSheet(button_style)

        # 运行按钮和导出按钮特殊样式
        if hasattr(self, 'bulk_cluster_btn_stage1'):
            self.bulk_cluster_btn_stage1.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_cluster_btn_stage2'):
            self.bulk_cluster_btn_stage2.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_cluster_btn_stage3'):
            self.bulk_cluster_btn_stage3.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_cluster_btn_export_png'):
            self.bulk_cluster_btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_cluster_btn_export_pdf'):
            self.bulk_cluster_btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_cluster_btn_export_svg'):
            self.bulk_cluster_btn_export_svg.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_cluster_btn_export_csv'):
            self.bulk_cluster_btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_cluster_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_cluster_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_cluster_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_cluster_page.findChildren(QLabel):
            if child.objectName() != "bulk_cluster_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_cluster_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_cluster_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.bulk_cluster_page.findChild(QWidget, "bulk_cluster_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")
        if hasattr(self, 'r_version_label'):
            self.r_version_label.setStyleSheet(label_style)

    def create_page(self):
        self.bulk_cluster_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.bulk_cluster_page)
        bg_label.setObjectName("bulk_cluster_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.bulk_cluster_page)
        overlay.setObjectName("bulk_cluster_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 顶部标题栏 ===
        top_layout = QHBoxLayout()

        self.btn_back = create_styled_button("← 返回bulk主页", font_size=12)
        top_layout.addWidget(self.btn_back)

        title_label = QLabel("bulk 一致性分析")
        title_label.setObjectName("bulk_cluster_title")
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
        self.bulk_cluster_status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.bulk_cluster_status_text.setMaximumHeight(80)
        status_layout.addWidget(self.bulk_cluster_status_text)
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

        self.bulk_cluster_debug_btn = create_styled_button("检测环境对应", font_size=10)
        debug_layout.addWidget(self.bulk_cluster_debug_btn)

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

        # 分类列选择
        clinical_label = create_styled_label("分类列选择", font_size=11, bold=False)
        filter_group_layout.addWidget(clinical_label)

        self.bulk_cluster_clinical_combo = create_styled_combo_box()
        self.bulk_cluster_clinical_combo.addItem("全部")
        filter_group_layout.addWidget(self.bulk_cluster_clinical_combo)

        # 组别多选列表
        self.bulk_cluster_group_list_label = create_styled_label("组别（可多选）", font_size=11, bold=False)
        self.bulk_cluster_group_list_label.hide()
        filter_group_layout.addWidget(self.bulk_cluster_group_list_label)

        self.bulk_cluster_group_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_cluster_group_list.hide()
        filter_group_layout.addWidget(self.bulk_cluster_group_list)

        # 筛选1框架
        filter1_frame = QFrame()
        filter1_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.bulk_cluster_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.bulk_cluster_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.bulk_cluster_filter1_combo = create_styled_combo_box()
        self.bulk_cluster_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.bulk_cluster_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.bulk_cluster_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_cluster_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.bulk_cluster_filter1_list)

        filter_group_layout.addWidget(filter1_frame)

        # 筛选2框架
        filter2_frame = QFrame()
        filter2_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.bulk_cluster_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.bulk_cluster_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.bulk_cluster_filter2_combo = create_styled_combo_box()
        self.bulk_cluster_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.bulk_cluster_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.bulk_cluster_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_cluster_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.bulk_cluster_filter2_list)

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

        stage1_title = create_styled_label("阶段一参数（聚类计算）", font_size=12, bold=True)
        stage1_layout.addWidget(stage1_title)

        # MAD阈值
        mad_row = QHBoxLayout()
        mad_label, mad_help = create_labeled_param_with_help(
            "MAD阈值",
            "中位数绝对偏差阈值。\n从所有基因中选出MAD最高的前N个基因用于聚类。\n默认5000，值越大使用的基因越多，结果越精细但耗时越长。"
        )
        mad_row.addWidget(mad_label)
        mad_row.addWidget(mad_help)
        mad_row.addSpacing(8)
        self.bulk_cluster_mad_input = create_styled_line_edit()
        self.bulk_cluster_mad_input.setText("5000")
        self.bulk_cluster_mad_input.setMinimumWidth(60)
        self.bulk_cluster_mad_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        mad_row.addWidget(self.bulk_cluster_mad_input)
        stage1_layout.addLayout(mad_row)

        # reps抽样次数
        reps_row = QHBoxLayout()
        reps_label, reps_help = create_labeled_param_with_help(
            "reps抽样次数",
            "重抽样次数。\n每次迭代随机抽取部分样本和基因进行聚类，统计共聚类频率。\n默认1000，值越大结果越稳定但耗时越长。"
        )
        reps_row.addWidget(reps_label)
        reps_row.addWidget(reps_help)
        reps_row.addSpacing(8)
        self.bulk_cluster_reps_input = create_styled_line_edit()
        self.bulk_cluster_reps_input.setText("1000")
        self.bulk_cluster_reps_input.setMinimumWidth(60)
        self.bulk_cluster_reps_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        reps_row.addWidget(self.bulk_cluster_reps_input)
        stage1_layout.addLayout(reps_row)

        # clusterAlg聚类算法
        alg_row = QHBoxLayout()
        alg_label, alg_help = create_labeled_param_with_help(
            "聚类算法",
            "聚类算法类型。\nhc: 层次聚类（默认）\nkm: K均值聚类\npam: 围绕中心点划分"
        )
        alg_row.addWidget(alg_label)
        alg_row.addWidget(alg_help)
        alg_row.addSpacing(8)
        self.bulk_cluster_alg_combo = create_styled_combo_box()
        self.bulk_cluster_alg_combo.addItems(['hc', 'km', 'pam'])
        self.bulk_cluster_alg_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        alg_row.addWidget(self.bulk_cluster_alg_combo)
        stage1_layout.addLayout(alg_row)

        # distance距离度量
        dist_row = QHBoxLayout()
        dist_label, dist_help = create_labeled_param_with_help(
            "距离度量",
            "样本间距离计算方法。\npearson: 皮尔逊相关距离（默认）\neuclidean: 欧氏距离\nmanhattan: 曼哈顿距离\nmaximum: 最大距离\ncanberra: Canberra距离\nbinary: 二值距离\nminkowski: 闵可夫斯基距离\ncorrelation: 相关性距离"
        )
        dist_row.addWidget(dist_label)
        dist_row.addWidget(dist_help)
        dist_row.addSpacing(8)
        self.bulk_cluster_distance_combo = create_styled_combo_box()
        self.bulk_cluster_distance_combo.addItems(['pearson', 'euclidean', 'maximum', 'manhattan',
                                                    'canberra', 'binary', 'minkowski', 'correlation'])
        self.bulk_cluster_distance_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        dist_row.addWidget(self.bulk_cluster_distance_combo)
        stage1_layout.addLayout(dist_row)

        # pItem样本抽样比例
        pitem_row = QHBoxLayout()
        pitem_label, pitem_help = create_labeled_param_with_help(
            "pItem样本抽样比例",
            "样本抽样比例。\n每次迭代随机抽取该比例的样本进行聚类。\n默认0.8（即80%的样本），\n值越小结果越稳定但信息量少，\n值越大越接近不抽样，结果可能过拟合。"
        )
        pitem_row.addWidget(pitem_label)
        pitem_row.addWidget(pitem_help)
        pitem_row.addSpacing(8)
        self.bulk_cluster_pitem_input = create_styled_line_edit()
        self.bulk_cluster_pitem_input.setText("0.8")
        self.bulk_cluster_pitem_input.setMinimumWidth(50)
        self.bulk_cluster_pitem_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pitem_row.addWidget(self.bulk_cluster_pitem_input)
        stage1_layout.addLayout(pitem_row)

        # pFeature特征抽样比例
        pfeat_row = QHBoxLayout()
        pfeat_label, pfeat_help = create_labeled_param_with_help(
            "pFeature特征抽样比例",
            "特征（基因）抽样比例。\n每次迭代随机抽取该比例的基因进行聚类。\n默认1（即100%的基因），\n值越小引入更多随机性，结果更稳健但可能丢失信息。"
        )
        pfeat_row.addWidget(pfeat_label)
        pfeat_row.addWidget(pfeat_help)
        pfeat_row.addSpacing(8)
        self.bulk_cluster_pfeature_input = create_styled_line_edit()
        self.bulk_cluster_pfeature_input.setText("1")
        self.bulk_cluster_pfeature_input.setMinimumWidth(50)
        self.bulk_cluster_pfeature_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pfeat_row.addWidget(self.bulk_cluster_pfeature_input)
        stage1_layout.addLayout(pfeat_row)

        # k值区间
        krange_row = QHBoxLayout()
        krange_label, krange_help = create_labeled_param_with_help(
            "k值区间",
            "聚类数k的搜索范围。\n程序会对闭区间内的所有整数k值进行聚类计算。\n默认2~9，即计算k=2,3,4,5,6,7,8,9共8种聚类结果。"
        )
        krange_row.addWidget(krange_label)
        krange_row.addWidget(krange_help)
        krange_row.addSpacing(8)
        krange_inputs_container = QWidget()
        krange_inputs_layout = QHBoxLayout(krange_inputs_container)
        krange_inputs_layout.setContentsMargins(0, 0, 0, 0)
        krange_inputs_layout.setSpacing(4)
        self.bulk_cluster_min_k_input = create_styled_line_edit()
        self.bulk_cluster_min_k_input.setText("2")
        self.bulk_cluster_min_k_input.setMinimumWidth(30)
        self.bulk_cluster_min_k_input.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_min_k_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        krange_inputs_layout.addWidget(self.bulk_cluster_min_k_input)
        krange_inputs_layout.addWidget(create_styled_label("~", font_size=11))
        self.bulk_cluster_max_k_input = create_styled_line_edit()
        self.bulk_cluster_max_k_input.setText("9")
        self.bulk_cluster_max_k_input.setMinimumWidth(30)
        self.bulk_cluster_max_k_input.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_max_k_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        krange_inputs_layout.addWidget(self.bulk_cluster_max_k_input)
        krange_inputs_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        krange_row.addWidget(krange_inputs_container)
        stage1_layout.addLayout(krange_row)

        # plot输出格式
        plot_fmt_row = QHBoxLayout()
        plot_fmt_label, plot_fmt_help = create_labeled_param_with_help(
            "plot输出格式",
            "ConsensusClusterPlus内部诊断图的输出格式。\npng: 位图格式（默认）\npdf: 矢量格式\nps: PostScript格式\n影响R内部生成的诊断图格式。"
        )
        plot_fmt_row.addWidget(plot_fmt_label)
        plot_fmt_row.addWidget(plot_fmt_help)
        plot_fmt_row.addSpacing(8)
        self.bulk_cluster_plot_format_combo = create_styled_combo_box()
        self.bulk_cluster_plot_format_combo.addItems(['png', 'pdf', 'ps'])
        plot_fmt_row.addWidget(self.bulk_cluster_plot_format_combo)
        stage1_layout.addLayout(plot_fmt_row)

        left_content_layout.addWidget(stage1_group)
        left_content_layout.addSpacing(8)

        # --- 阶段二参数group_box（无参数，仅提示） ---
        stage2_group = QFrame()
        stage2_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage2_group.setObjectName("styled_panel_stage2")
        stage2_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage2_layout = QVBoxLayout(stage2_group)
        stage2_layout.setContentsMargins(8, 8, 8, 8)

        stage2_title = create_styled_label("阶段二参数（CDF+PAC曲线）", font_size=12, bold=True)
        stage2_layout.addWidget(stage2_title)

        stage2_hint = create_styled_label("此阶段无额外参数，\n直接运行即可生成CDF和PAC曲线", font_size=10, bold=False)
        stage2_layout.addWidget(stage2_hint)

        left_content_layout.addWidget(stage2_group)
        left_content_layout.addSpacing(8)

        # --- 阶段三参数group_box ---
        stage3_group = QFrame()
        stage3_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stage3_group.setObjectName("styled_panel_stage3")
        stage3_group.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        stage3_layout = QVBoxLayout(stage3_group)
        stage3_layout.setContentsMargins(8, 8, 8, 8)

        stage3_title = create_styled_label("阶段三参数（最终热图）", font_size=12, bold=True)
        stage3_layout.addWidget(stage3_title)

        # 选择最终k值
        k_row = QHBoxLayout()
        k_label, k_help = create_labeled_param_with_help(
            "选择最终k值",
            "从阶段一定义的k值区间内选择一个最终k值。\n建议根据阶段二的PAC曲线选择PAC值最小的k值作为最优k。"
        )
        k_row.addWidget(k_label)
        k_row.addWidget(k_help)
        k_row.addSpacing(8)
        self.bulk_cluster_final_k_combo = create_styled_combo_box()
        for k in range(2, 10):
            self.bulk_cluster_final_k_combo.addItem(str(k))
        self.bulk_cluster_final_k_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        k_row.addWidget(self.bulk_cluster_final_k_combo)
        stage3_layout.addLayout(k_row)

        # 输出模式
        mode_row = QHBoxLayout()
        mode_label, mode_help = create_labeled_param_with_help(
            "输出模式",
            "阶段三的输出内容选择：\n1. 只出一致性热图\n2. 热图+聚类树+样本表\n3. 热图+聚类树+ICL\n默认选1，可按需选择更详细的输出。"
        )
        mode_row.addWidget(mode_label)
        mode_row.addWidget(mode_help)
        mode_row.addSpacing(8)
        self.bulk_cluster_output_mode_combo = create_styled_combo_box()
        self.bulk_cluster_output_mode_combo.addItems(['1.只出热图', '2.热图+树+样本表', '3.热图+树+ICL'])
        self.bulk_cluster_output_mode_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        mode_row.addWidget(self.bulk_cluster_output_mode_combo)
        stage3_layout.addLayout(mode_row)

        # 出图尺寸
        size_row = QHBoxLayout()
        size_label, size_help = create_labeled_param_with_help(
            "出图尺寸",
            "最终热图的宽度和高度（英寸）。\n默认8×8，可根据样本数量调整。"
        )
        size_row.addWidget(size_label)
        size_row.addWidget(size_help)
        size_row.addSpacing(8)
        size_inputs_container = QWidget()
        size_inputs_layout = QHBoxLayout(size_inputs_container)
        size_inputs_layout.setContentsMargins(0, 0, 0, 0)
        size_inputs_layout.setSpacing(4)
        self.bulk_cluster_heatmap_width = create_styled_line_edit()
        self.bulk_cluster_heatmap_width.setText("8")
        self.bulk_cluster_heatmap_width.setMinimumWidth(30)
        self.bulk_cluster_heatmap_width.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_heatmap_width.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_inputs_layout.addWidget(self.bulk_cluster_heatmap_width)
        size_inputs_layout.addWidget(create_styled_label("×", font_size=11))
        self.bulk_cluster_heatmap_height = create_styled_line_edit()
        self.bulk_cluster_heatmap_height.setText("8")
        self.bulk_cluster_heatmap_height.setMinimumWidth(30)
        self.bulk_cluster_heatmap_height.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_heatmap_height.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_inputs_layout.addWidget(self.bulk_cluster_heatmap_height)
        size_inputs_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        size_row.addWidget(size_inputs_container)
        stage3_layout.addLayout(size_row)

        # 颜色方案
        color_row = QHBoxLayout()
        color_label, color_help = create_labeled_param_with_help(
            "颜色方案",
            "热图的颜色方案。\nblue: 白→钢蓝色（默认）\nred: 白→红色\ngreen: 白→绿色"
        )
        color_row.addWidget(color_label)
        color_row.addWidget(color_help)
        color_row.addSpacing(8)
        self.bulk_cluster_color_scheme_combo = create_styled_combo_box()
        self.bulk_cluster_color_scheme_combo.addItems(['blue', 'red', 'green'])
        self.bulk_cluster_color_scheme_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        color_row.addWidget(self.bulk_cluster_color_scheme_combo)
        stage3_layout.addLayout(color_row)

        # 标题字体大小
        title_size_row = QHBoxLayout()
        title_size_label, title_size_help = create_labeled_param_with_help(
            "标题字体大小",
            "热图标题的字体大小，默认14。"
        )
        title_size_row.addWidget(title_size_label)
        title_size_row.addWidget(title_size_help)
        title_size_row.addSpacing(8)
        self.bulk_cluster_title_font_size = create_styled_line_edit()
        self.bulk_cluster_title_font_size.setText("14")
        self.bulk_cluster_title_font_size.setMinimumWidth(40)
        self.bulk_cluster_title_font_size.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_title_font_size.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_size_row.addWidget(self.bulk_cluster_title_font_size)
        stage3_layout.addLayout(title_size_row)

        # 图例字体大小
        legend_size_row = QHBoxLayout()
        legend_size_label, legend_size_help = create_labeled_param_with_help(
            "图例字体大小",
            "热图图例和注释的字体大小，默认12。"
        )
        legend_size_row.addWidget(legend_size_label)
        legend_size_row.addWidget(legend_size_help)
        legend_size_row.addSpacing(8)
        self.bulk_cluster_legend_font_size = create_styled_line_edit()
        self.bulk_cluster_legend_font_size.setText("12")
        self.bulk_cluster_legend_font_size.setMinimumWidth(40)
        self.bulk_cluster_legend_font_size.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_legend_font_size.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        legend_size_row.addWidget(self.bulk_cluster_legend_font_size)
        stage3_layout.addLayout(legend_size_row)

        # 聚类方法
        clust_method_row = QHBoxLayout()
        clust_method_label, clust_method_help = create_labeled_param_with_help(
            "聚类方法",
            "层次聚类的连接方法。\naverage: 平均连接（默认）\ncomplete: 完全连接\nsingle: 单连接\nward.D: Ward方法\nmedian: 中位数连接\ncentroid: 重心连接"
        )
        clust_method_row.addWidget(clust_method_label)
        clust_method_row.addWidget(clust_method_help)
        clust_method_row.addSpacing(8)
        self.bulk_cluster_clust_method_combo = create_styled_combo_box()
        self.bulk_cluster_clust_method_combo.addItems(['average', 'complete', 'single', 'ward.D', 'median', 'centroid'])
        self.bulk_cluster_clust_method_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        clust_method_row.addWidget(self.bulk_cluster_clust_method_combo)
        stage3_layout.addLayout(clust_method_row)

        left_content_layout.addWidget(stage3_group)
        left_content_layout.addStretch()

        left_scroll.setWidget(left_content)
        left_layout.addWidget(left_scroll)
        main_layout.addWidget(left_panel)

        # ================ 中间图表区 ================
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)

        self.bulk_cluster_plot_tabs = create_styled_tab_widget()

        # 预创建所有Tab
        _, self.bulk_cluster_label_consensus = create_styled_image_tab(
            self.bulk_cluster_plot_tabs, "一致性矩阵",
            default_text="请运行阶段一聚类计算",
            data_hint_template="数据: {dataset_name}\n样本数: {n_samples}\n基因数: {n_genes}\n\n请设置参数并点击「阶段一：聚类计算」"
        )
        _, self.bulk_cluster_label_cdf = create_styled_image_tab(
            self.bulk_cluster_plot_tabs, "CDF曲线",
            default_text="请运行阶段二生成CDF+PAC曲线",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一，再点击「阶段二：CDF+PAC曲线」"
        )
        _, self.bulk_cluster_label_pac = create_styled_image_tab(
            self.bulk_cluster_plot_tabs, "PAC曲线",
            default_text="请运行阶段二生成CDF+PAC曲线",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一，再点击「阶段二：CDF+PAC曲线」"
        )
        _, self.bulk_cluster_label_heatmap = create_styled_image_tab(
            self.bulk_cluster_plot_tabs, "最终热图",
            default_text="请运行阶段三生成最终热图",
            data_hint_template="数据: {dataset_name}\n\n请先运行阶段一和阶段二，选择k值后点击「阶段三：生成最终热图」"
        )

        center_layout.addWidget(self.bulk_cluster_plot_tabs)
        main_layout.addWidget(center_panel, 1)

        # ================ 右侧运行+导出面板 ================
        right_panel, right_layout = create_styled_panel()
        right_panel.setMinimumWidth(220)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # 运行区域标题
        run_title = create_styled_label("运行区域", font_size=12, bold=True)
        right_layout.addWidget(run_title)

        # 阶段一运行按钮
        self.bulk_cluster_btn_stage1 = create_styled_button("▶ 阶段一：聚类计算", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_cluster_btn_stage1)

        # 阶段二运行按钮
        self.bulk_cluster_btn_stage2 = create_styled_button("▶ 阶段二：CDF+PAC曲线", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_cluster_btn_stage2)

        # 阶段三运行按钮
        self.bulk_cluster_btn_stage3 = create_styled_button("▶ 阶段三：生成最终热图", font_size=11, button_type='run')
        right_layout.addWidget(self.bulk_cluster_btn_stage3)

        right_layout.addSpacing(10)

        # 导出选项标题
        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        right_layout.addWidget(export_title)

        # 导出尺寸设置
        export_size_frame = QFrame()
        export_size_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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
        self.bulk_cluster_export_width = create_styled_line_edit()
        self.bulk_cluster_export_width.setText("8")
        self.bulk_cluster_export_width.setMinimumWidth(40)
        self.bulk_cluster_export_width.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_export_width.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        width_row.addWidget(self.bulk_cluster_export_width)
        export_size_layout.addLayout(width_row)

        # 高度行
        height_row = QHBoxLayout()
        height_row.addSpacing(5)
        height_label = create_styled_label("高度:", font_size=10, bold=False)
        height_row.addWidget(height_label)
        self.bulk_cluster_export_height = create_styled_line_edit()
        self.bulk_cluster_export_height.setText("6")
        self.bulk_cluster_export_height.setMinimumWidth(40)
        self.bulk_cluster_export_height.setAlignment(Qt.AlignCenter)
        self.bulk_cluster_export_height.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        height_row.addWidget(self.bulk_cluster_export_height)
        export_size_layout.addLayout(height_row)
        right_layout.addWidget(export_size_frame)

        right_layout.addSpacing(8)

        # 导出PNG按钮
        self.bulk_cluster_btn_export_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        right_layout.addWidget(self.bulk_cluster_btn_export_png)

        # 导出PDF按钮
        self.bulk_cluster_btn_export_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        right_layout.addWidget(self.bulk_cluster_btn_export_pdf)

        # 导出SVG按钮
        self.bulk_cluster_btn_export_svg = create_styled_button("导出SVG", font_size=10, button_type='export')
        right_layout.addWidget(self.bulk_cluster_btn_export_svg)

        # 导出CSV按钮
        self.bulk_cluster_btn_export_csv = create_styled_button("导出CSV", font_size=10, button_type='export')
        right_layout.addWidget(self.bulk_cluster_btn_export_csv)

        right_layout.addSpacing(8)

        # 导出h5ad按钮
        self.bulk_cluster_btn_export_h5ad = create_styled_button("导出h5ad", font_size=10, button_type='import')
        right_layout.addWidget(self.bulk_cluster_btn_export_h5ad)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.bulk_cluster_page
