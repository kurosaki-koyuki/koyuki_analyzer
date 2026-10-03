# -*- coding: utf-8 -*-
"""
scRNAseq Monocle基因列表分析子层UI布局脚本
左侧：基因筛选模式 + 阈值控件 + 运行按钮 + 日志区
右侧：基因搜索框 + 标签页（所有基因列表 + 显著基因列表）+ 统计信息
背景由主层容器统一管理，子层使用透明背景
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_label,
    create_styled_panel, create_styled_text_edit, create_styled_tab_widget,
    create_styled_tab_page, create_styled_table, create_styled_line_edit,
    create_styled_spinbox, create_questions_button, create_styled_progress_bar,
    create_zoomable_image_label
)
from script.mods_layer.mod_manager import global_mod_manager


class ScMonocleGenelistsPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_monocle_genelists_page = None
        self.create_page()

    def update_background(self):
        """更新背景图（子页面不处理，由主容器统一管理）"""
        pass

    def update_styles(self):
        """更新子层样式（mod切换时由主层递归调用）"""
        styles = get_mod_styles()

        title_label = self.sc_monocle_genelists_page.findChild(QLabel, "sc_monocle_genelists_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};"
            )

        button_style = get_stylesheet_for_widget('button')
        for child in self.sc_monocle_genelists_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_run_graph_test'):
            self.btn_run_graph_test.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_import_gene_list'):
            self.btn_import_gene_list.setStyleSheet(get_stylesheet_for_widget('import_button'))
        if hasattr(self, 'btn_apply_threshold'):
            self.btn_apply_threshold.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_run_stage3'):
            self.btn_run_stage3.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_run_stage4'):
            self.btn_run_stage4.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_xlsx'):
            self.btn_export_xlsx.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.sc_monocle_genelists_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.sc_monocle_genelists_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.sc_monocle_genelists_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_monocle_genelists_page.findChildren(QLabel):
            if child.objectName() != "sc_monocle_genelists_title":
                child.setStyleSheet(label_style)

        # 表格样式（style模板已修复 color:black 问题，文字颜色由 _fill_table 的 setForeground 控制）
        table_style = get_stylesheet_for_widget('table')
        for child in self.sc_monocle_genelists_page.findChildren(QTableWidget):
            child.setStyleSheet(table_style)

        # 进度条样式（mod切换时刷新颜色）
        progress_bg = styles.get('sub_slider_bg', 'rgba(30, 58, 95, 0.4)')
        progress_chunk = styles.get('sub_slider_handle', styles.get('sub_active_color', '#1E3A5F'))
        progress_border = styles.get('sub_border_default', '#1E3A5F')
        progress_text = styles.get('sub_text_color', '#87CEEB')
        progress_radius = styles.get('sub_radius_sm', '3px')
        progress_style = f"""
            QProgressBar {{
                color: {progress_text};
                background: {progress_bg};
                border: 1px solid {progress_border};
                border-radius: {progress_radius};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {progress_chunk};
                border-radius: {progress_radius};
            }}
        """
        for child in self.sc_monocle_genelists_page.findChildren(QProgressBar):
            child.setStyleSheet(progress_style)

        # 标签页样式
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
        for child in self.sc_monocle_genelists_page.findChildren(QTabWidget):
            child.setStyleSheet(tab_style)

        # 统计标签着色
        if hasattr(self, 'total_genes_label'):
            self.total_genes_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        if hasattr(self, 'sig_genes_label'):
            self.sig_genes_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#FF6B35')};")

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_monocle_genelists_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        self.update_background()

    def create_page(self):
        self.sc_monocle_genelists_page = QWidget(self.parent)
        self.sc_monocle_genelists_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()

        layout = QVBoxLayout(self.sc_monocle_genelists_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== 顶部：标题 + 音乐控制器 ==========
        top_layout = QHBoxLayout()

        title_label = QLabel("Monocle基因列表分析")
        title_label.setObjectName("sc_monocle_genelists_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # music_controller（按项目规则保留，供全局同步函数发现）
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.sc_monocle_genelists_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub'
        )

        music_container_x = styles.get('music_container_x', 0.85)
        music_container_y = styles.get('music_container_y', 15)
        if isinstance(music_container_x, float):
            music_container_x = int(self.screen_width * music_container_x)
        music_container.move(music_container_x, music_container_y)

        top_layout.addWidget(music_container)

        top_layout.setStretch(0, 3)
        top_layout.setStretch(1, 1)
        layout.addLayout(top_layout)

        # ========== 主区域：左侧参数 + 右侧表格 ==========
        main_layout = QHBoxLayout()

        # ========== 左侧参数面板 ==========
        left_panel, left_panel_outer_layout = create_styled_panel(parent=self.sc_monocle_genelists_page)
        left_panel.setMinimumWidth(400)
        left_panel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        # 可滚动区域（参考初筛界面，阶段一/二/三控件较多需要滚动）
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_content = QWidget()
        left_panel_layout = QVBoxLayout(left_content)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)

        # 总标题 + questions_btn
        param_title_layout = QHBoxLayout()
        param_title = create_styled_label("graph_test分析参数", font_size=14, bold=True)
        param_title_layout.addWidget(param_title)

        param_hint_btn = create_questions_button("""graph_test分析说明

功能：
对CDS对象运行monocle3的graph_test(Moran's I检验)，
检测沿轨迹显著变化的基因。

输出字段：
- gene_id: 基因名
- morans_I: Moran's I统计量(范围-1到1)
- morans_test_statistic: 检验统计量
- p_value: 原始p值
- q_value: BH-FDR校正后的q值

基因独立性（重要）：
- graph_test对每个基因独立计算Moran's I
- morans_I / morans_test_statistic / p_value 完全独立
  选部分基因 vs 全部基因，每个基因这三个值完全一致
- 唯一例外：q_value (BH-FDR)受参与基因数影响
  因为FDR校正是基于参与基因的p值分布计算的
  选不同基因集合时，同一基因的q_value会略有波动

阶段一：基因筛选模式
1. 全部基因: 对CDS中所有基因计算(最完整但最慢)
2. 高变基因前N个: 使用CDS的ordering_genes，
   默认N=2000(调试推荐，速度快10倍)
3. 外部基因列表: 从txt/xlsx文件加载基因名

阶段二：显著基因筛选
- 从阶段一缓存的DataFrame中按p/q阈值筛选
- 不重跑R脚本，可反复调整阈值

数据来源：
- 自动从数据加载类页面共享CDS rds路径
- 若未共享，请先在数据加载类页面加载rds文件

注意：
- 本步骤仅做显著性判断，不涉及上下调
- 不输出CSV文件，结果仅显示在表格中""")
        param_title_layout.addWidget(param_hint_btn)
        left_panel_layout.addLayout(param_title_layout)

        left_panel_layout.addSpacing(20)
        left_panel_layout.addWidget(create_styled_label("━" * 20, font_size=10))
        left_panel_layout.addSpacing(10)

        # ========== 阶段一：graph_test分析 ==========
        stage1_title = create_styled_label("阶段一：graph_test分析", font_size=14, bold=True)
        left_panel_layout.addWidget(stage1_title)

        left_panel_layout.addSpacing(8)

        stage1_note = create_styled_label("运行Moran's I检验，检测沿轨迹显著变化的基因", font_size=10, bold=False)
        stage1_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_panel_layout.addWidget(stage1_note)

        left_panel_layout.addSpacing(10)

        # 基因筛选模式
        filter_mode_label = create_styled_label("基因筛选模式", font_size=10, bold=True)
        left_panel_layout.addWidget(filter_mode_label)
        self.gene_filter_combo = create_styled_combo_box()
        self.gene_filter_combo.addItem("全部基因", "all")
        self.gene_filter_combo.addItem("高变基因前N个", "hvg")
        self.gene_filter_combo.addItem("外部基因列表", "list")
        self.gene_filter_combo.setCurrentIndex(1)
        left_panel_layout.addWidget(self.gene_filter_combo)

        left_panel_layout.addSpacing(8)

        # 高变基因数N（仅hvg模式可见）
        self.hvg_n_label = create_styled_label("高变基因数N", font_size=10, bold=True)
        left_panel_layout.addWidget(self.hvg_n_label)
        self.hvg_n_spinbox = create_styled_spinbox(
            min_value=100, max_value=50000, default_value=2000
        )
        left_panel_layout.addWidget(self.hvg_n_spinbox)

        left_panel_layout.addSpacing(8)

        # 外部基因列表导入（仅list模式可见）
        self.gene_list_label = create_styled_label("外部基因列表文件", font_size=10, bold=True)
        left_panel_layout.addWidget(self.gene_list_label)

        gene_list_btn_layout = QHBoxLayout()
        self.btn_import_gene_list = create_styled_button("导入基因列表", font_size=10, button_type='import')
        gene_list_btn_layout.addWidget(self.btn_import_gene_list)
        self.gene_list_path_label = create_styled_label("未选择文件", font_size=9, bold=False)
        self.gene_list_path_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        gene_list_btn_layout.addWidget(self.gene_list_path_label)
        left_panel_layout.addLayout(gene_list_btn_layout)

        # 根据默认选中的模式显示/隐藏控件
        current_mode = self.gene_filter_combo.currentData()
        if current_mode == 'hvg':
            self.hvg_n_label.setVisible(True)
            self.hvg_n_spinbox.setVisible(True)
            self.gene_list_label.setVisible(False)
            self.btn_import_gene_list.setVisible(False)
            self.gene_list_path_label.setVisible(False)
        elif current_mode == 'list':
            self.hvg_n_label.setVisible(False)
            self.hvg_n_spinbox.setVisible(False)
            self.gene_list_label.setVisible(True)
            self.btn_import_gene_list.setVisible(True)
            self.gene_list_path_label.setVisible(True)
        else:
            self.hvg_n_label.setVisible(False)
            self.hvg_n_spinbox.setVisible(False)
            self.gene_list_label.setVisible(False)
            self.btn_import_gene_list.setVisible(False)
            self.gene_list_path_label.setVisible(False)

        left_panel_layout.addSpacing(15)

        # 阶段一运行按钮
        self.btn_run_graph_test = create_styled_button("▶ 运行graph_test", font_size=12, button_type='run')
        left_panel_layout.addWidget(self.btn_run_graph_test)

        left_panel_layout.addSpacing(20)
        left_panel_layout.addWidget(create_styled_label("━" * 20, font_size=10))
        left_panel_layout.addSpacing(10)

        # ========== 阶段二：显著基因筛选 ==========
        stage2_title = create_styled_label("阶段二：显著基因筛选", font_size=14, bold=True)
        left_panel_layout.addWidget(stage2_title)

        left_panel_layout.addSpacing(8)

        stage2_note = create_styled_label("从阶段一结果中按p/q阈值筛显著基因", font_size=10, bold=False)
        stage2_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_panel_layout.addWidget(stage2_note)

        left_panel_layout.addSpacing(10)

        # 阈值字段
        threshold_field_label = create_styled_label("阈值字段", font_size=10, bold=True)
        left_panel_layout.addWidget(threshold_field_label)
        self.threshold_field_combo = create_styled_combo_box()
        self.threshold_field_combo.addItem("p_value (原始p值)", "p_value")
        self.threshold_field_combo.addItem("q_value (FDR校正q值)", "q_value")
        self.threshold_field_combo.setCurrentIndex(0)
        left_panel_layout.addWidget(self.threshold_field_combo)

        left_panel_layout.addSpacing(8)

        # 阈值
        threshold_value_label = create_styled_label("阈值", font_size=10, bold=True)
        left_panel_layout.addWidget(threshold_value_label)
        self.threshold_value_edit = create_styled_line_edit()
        self.threshold_value_edit.setText("0.05")
        left_panel_layout.addWidget(self.threshold_value_edit)

        left_panel_layout.addSpacing(15)

        # 阶段二筛选按钮
        self.btn_apply_threshold = create_styled_button("▶ 筛选显著基因", font_size=12, button_type='run')
        self.btn_apply_threshold.setEnabled(False)
        left_panel_layout.addWidget(self.btn_apply_threshold)

        left_panel_layout.addSpacing(20)
        left_panel_layout.addWidget(create_styled_label("━" * 20, font_size=10))
        left_panel_layout.addSpacing(10)

        # ========== 阶段三：上下调分类 ==========
        stage3_title_layout = QHBoxLayout()
        stage3_title = create_styled_label("阶段三：上下调分类", font_size=14, bold=True)
        stage3_title_layout.addWidget(stage3_title)
        
        # 算法说明按钮
        algo_help_btn = create_questions_button("""阶段三算法说明

三种算法用于分析基因表达随伪时间的变化趋势：

1. Spearman秩相关（推荐）
   - 原理：计算表达量与伪时间的秩相关系数
   - 特点：速度最快，检测线性趋势，对异常值不敏感
   - 适用：初步筛选，快速预览，大数据集
   - rho范围：-1到1（正=上调，负=下调）

2. LOESS局部加权回归（精准）
   - 原理：拟合表达量随伪时间变化的平滑曲线
   - 特点：捕捉非线性关系，结果最可靠，但计算最慢
   - 适用：基因表达模式复杂时，如波浪形、周期性变化
   - 注意：对大量基因（>1000）建议先筛显著基因

3. Wilcoxon检验（早期vs晚期）
   - 原理：按伪时间中位数划分早期/晚期细胞，比较两组表达差异
   - 特点：忽略中间过渡，只看两端差异，速度较快
   - 适用：关注轨迹起点和终点的显著变化

分类规则：
- rho > 0 且 p/q < 阈值 → 上调(up)
- rho < 0 且 p/q < 阈值 → 下调(down)
- 其他 → 不显著(not_significant)

推荐流程：
1. 先用Spearman快速筛选显著基因
2. 对关键基因用LOESS做精准验证
3. Wilcoxon作为补充验证手段""")
        stage3_title_layout.addWidget(algo_help_btn)
        left_panel_layout.addLayout(stage3_title_layout)

        left_panel_layout.addSpacing(8)

        stage3_note = create_styled_label("计算基因表达量与伪时间的相关性", font_size=10, bold=False)
        stage3_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_panel_layout.addWidget(stage3_note)

        left_panel_layout.addSpacing(10)

        # 算法选择
        algorithm_label = create_styled_label("分析算法", font_size=10, bold=True)
        left_panel_layout.addWidget(algorithm_label)
        self.stage3_algorithm_combo = create_styled_combo_box()
        self.stage3_algorithm_combo.addItem("Spearman秩相关（推荐）", "spearman")
        self.stage3_algorithm_combo.addItem("LOESS局部加权回归（精准）", "loess")
        self.stage3_algorithm_combo.addItem("Wilcoxon检验（早期vs晚期）", "wilcoxon")
        self.stage3_algorithm_combo.setCurrentIndex(0)
        left_panel_layout.addWidget(self.stage3_algorithm_combo)

        left_panel_layout.addSpacing(8)

        # 计算范围
        calc_scope_label = create_styled_label("计算范围", font_size=10, bold=True)
        left_panel_layout.addWidget(calc_scope_label)
        self.calc_scope_combo = create_styled_combo_box()
        self.calc_scope_combo.addItem("显著基因（推荐）", "sig")
        self.calc_scope_combo.addItem("全部基因", "all")
        self.calc_scope_combo.setCurrentIndex(0)
        left_panel_layout.addWidget(self.calc_scope_combo)

        left_panel_layout.addSpacing(8)

        # 阶段三阈值字段
        stage3_threshold_field_label = create_styled_label("分类阈值字段", font_size=10, bold=True)
        left_panel_layout.addWidget(stage3_threshold_field_label)
        self.stage3_threshold_field_combo = create_styled_combo_box()
        self.stage3_threshold_field_combo.addItem("p_value (原始p值)", "p_value")
        self.stage3_threshold_field_combo.addItem("q_value (FDR校正q值)", "q_value")
        self.stage3_threshold_field_combo.setCurrentIndex(0)
        left_panel_layout.addWidget(self.stage3_threshold_field_combo)

        left_panel_layout.addSpacing(8)

        # 阶段三阈值
        stage3_threshold_value_label = create_styled_label("分类阈值", font_size=10, bold=True)
        left_panel_layout.addWidget(stage3_threshold_value_label)
        self.stage3_threshold_value_edit = create_styled_line_edit()
        self.stage3_threshold_value_edit.setText("0.05")
        left_panel_layout.addWidget(self.stage3_threshold_value_edit)

        left_panel_layout.addSpacing(15)

        # 阶段三运行按钮
        self.btn_run_stage3 = create_styled_button("▶ 运行上下调分析", font_size=12, button_type='run')
        self.btn_run_stage3.setEnabled(False)
        left_panel_layout.addWidget(self.btn_run_stage3)

        left_panel_layout.addSpacing(20)
        left_panel_layout.addWidget(create_styled_label("━" * 20, font_size=10))
        left_panel_layout.addSpacing(10)

        # ========== 阶段四：火山图可视化 ==========
        stage4_title = create_styled_label("阶段四：火山图可视化", font_size=14, bold=True)
        left_panel_layout.addWidget(stage4_title)

        left_panel_layout.addSpacing(8)

        stage4_note = create_styled_label("基于阶段三结果绘制火山图，标记显著上下调基因", font_size=10, bold=False)
        stage4_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_panel_layout.addWidget(stage4_note)

        left_panel_layout.addSpacing(10)

        # X轴指标
        x_axis_label = create_styled_label("X轴指标", font_size=10, bold=True)
        left_panel_layout.addWidget(x_axis_label)
        self.stage4_x_axis_combo = create_styled_combo_box()
        self.stage4_x_axis_combo.addItem("rho (Spearman相关系数)", "rho")
        self.stage4_x_axis_combo.addItem("log2FC (晚期/早期表达比值)", "log2fc")
        self.stage4_x_axis_combo.setCurrentIndex(1)
        left_panel_layout.addWidget(self.stage4_x_axis_combo)

        left_panel_layout.addSpacing(8)

        # Y轴指标
        y_axis_label = create_styled_label("Y轴指标", font_size=10, bold=True)
        left_panel_layout.addWidget(y_axis_label)
        self.stage4_y_axis_combo = create_styled_combo_box()
        self.stage4_y_axis_combo.addItem("p_value (原始p值)", "p_value")
        self.stage4_y_axis_combo.addItem("q_value (FDR校正q值)", "q_value")
        self.stage4_y_axis_combo.setCurrentIndex(0)
        left_panel_layout.addWidget(self.stage4_y_axis_combo)

        left_panel_layout.addSpacing(8)

        # FC阈值
        fc_threshold_label = create_styled_label("FC阈值", font_size=10, bold=True)
        left_panel_layout.addWidget(fc_threshold_label)
        self.stage4_fc_threshold_edit = create_styled_line_edit()
        self.stage4_fc_threshold_edit.setText("1.0")
        left_panel_layout.addWidget(self.stage4_fc_threshold_edit)

        left_panel_layout.addSpacing(8)

        # p值阈值
        p_threshold_label = create_styled_label("p/q值阈值", font_size=10, bold=True)
        left_panel_layout.addWidget(p_threshold_label)
        self.stage4_p_threshold_edit = create_styled_line_edit()
        self.stage4_p_threshold_edit.setText("0.05")
        left_panel_layout.addWidget(self.stage4_p_threshold_edit)

        left_panel_layout.addSpacing(8)

        # 标记基因数量
        top_n_label = create_styled_label("标记基因数量", font_size=10, bold=True)
        left_panel_layout.addWidget(top_n_label)
        self.stage4_top_n_spinbox = create_styled_spinbox(
            min_value=1, max_value=50, default_value=10
        )
        left_panel_layout.addWidget(self.stage4_top_n_spinbox)

        left_panel_layout.addSpacing(15)

        # 阶段四运行按钮
        self.btn_run_stage4 = create_styled_button("▶ 绘制火山图", font_size=12, button_type='run')
        self.btn_run_stage4.setEnabled(False)
        left_panel_layout.addWidget(self.btn_run_stage4)

        left_panel_layout.addSpacing(20)
        left_panel_layout.addWidget(create_styled_label("━" * 20, font_size=10))
        left_panel_layout.addSpacing(10)

        left_panel_layout.addStretch()

        # 设置滚动区域
        left_scroll.setWidget(left_content)
        left_panel_outer_layout.addWidget(left_scroll)
        main_layout.addWidget(left_panel, 1)

        # ========== 中间面板：运行日志 + 数据信息 ==========
        middle_panel, middle_panel_layout = create_styled_panel(parent=self.sc_monocle_genelists_page)
        middle_panel.setMinimumWidth(260)
        middle_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 进度条（使用 style 模板）
        progress_title = create_styled_label("运行进度", font_size=12, bold=True)
        middle_panel_layout.addWidget(progress_title)

        self.progress_bar = create_styled_progress_bar(parent=self.sc_monocle_genelists_page)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        middle_panel_layout.addWidget(self.progress_bar)

        middle_panel_layout.addSpacing(10)

        # 日志区
        log_title = create_styled_label("运行日志", font_size=12, bold=True)
        middle_panel_layout.addWidget(log_title)

        self.genelists_log = create_styled_text_edit(read_only=True, variant='sub')
        middle_panel_layout.addWidget(self.genelists_log)

        middle_panel_layout.addSpacing(10)

        # 数据信息区
        data_info_title = create_styled_label("数据信息", font_size=12, bold=True)
        middle_panel_layout.addWidget(data_info_title)

        self.data_info_text = create_styled_text_edit(read_only=True)
        self.data_info_text.setMaximumHeight(80)
        middle_panel_layout.addWidget(self.data_info_text)

        middle_panel_layout.addSpacing(10)

        # 导出Excel按钮（放在运行信息面板下面）
        self.btn_export_xlsx = create_styled_button("导出Excel", font_size=12, button_type='export')
        self.btn_export_xlsx.setEnabled(False)
        middle_panel_layout.addWidget(self.btn_export_xlsx)

        middle_panel_layout.addStretch()
        main_layout.addWidget(middle_panel, 1)

        # ========== 右侧表格区 ==========
        right_panel = QWidget()
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(right_panel)

        # 统计标签
        stats_layout = QHBoxLayout()
        self.total_genes_label = create_styled_label("总基因数: 0", font_size=11, bold=True)
        self.total_genes_label.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')};")
        stats_layout.addWidget(self.total_genes_label)

        self.sig_genes_label = create_styled_label("显著基因数: 0", font_size=11, bold=True)
        self.sig_genes_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#FF6B35')};")
        stats_layout.addWidget(self.sig_genes_label)

        stats_layout.addStretch()
        right_layout.addLayout(stats_layout)

        # 上下调基因数标签
        stats_layout2 = QHBoxLayout()
        self.up_genes_label = create_styled_label("上调基因数: 0", font_size=11, bold=True)
        self.up_genes_label.setStyleSheet("color: #E74C3C;")
        stats_layout2.addWidget(self.up_genes_label)

        self.down_genes_label = create_styled_label("下调基因数: 0", font_size=11, bold=True)
        self.down_genes_label.setStyleSheet("color: #3498DB;")
        stats_layout2.addWidget(self.down_genes_label)

        stats_layout2.addStretch()
        right_layout.addLayout(stats_layout2)

        # 基因搜索框
        search_layout = QHBoxLayout()
        self.gene_search_input = create_styled_line_edit()
        self.gene_search_input.setPlaceholderText("输入基因名称搜索...")
        search_layout.addWidget(self.gene_search_input)
        self.gene_search_btn = create_styled_button("搜索", font_size=11)
        search_layout.addWidget(self.gene_search_btn)
        right_layout.addLayout(search_layout)

        # 标签页：所有基因列表 + 显著基因列表
        self.genelists_tabs = create_styled_tab_widget()

        # 所有基因列表页
        all_table_page, all_table_layout = create_styled_tab_page(self.genelists_tabs, "所有基因列表")
        self.all_genes_table = create_styled_table()
        all_table_layout.addWidget(self.all_genes_table)
        self.all_genes_table.setColumnCount(5)
        self.all_genes_table.setHorizontalHeaderLabels([
            "gene_id", "morans_I", "morans_test_statistic",
            "p_value", "q_value"
        ])

        # 显著基因列表页
        sig_table_page, sig_table_layout = create_styled_tab_page(self.genelists_tabs, "显著基因列表")
        self.sig_genes_table = create_styled_table()
        sig_table_layout.addWidget(self.sig_genes_table)
        self.sig_genes_table.setColumnCount(5)
        self.sig_genes_table.setHorizontalHeaderLabels([
            "gene_id", "morans_I", "morans_test_statistic",
            "p_value", "q_value"
        ])

        # ========== 阶段三标签页（3个） ==========
        # 上下调总体表格页（含direction列）
        stage3_all_page, stage3_all_layout = create_styled_tab_page(self.genelists_tabs, "上下调总体")
        self.stage3_all_table = create_styled_table()
        stage3_all_layout.addWidget(self.stage3_all_table)
        self.stage3_all_table.setColumnCount(5)
        self.stage3_all_table.setHorizontalHeaderLabels([
            "gene_id", "rho", "p_value", "q_value", "direction"
        ])

        # 上调基因表格页
        stage3_up_page, stage3_up_layout = create_styled_tab_page(self.genelists_tabs, "上调基因")
        self.stage3_up_table = create_styled_table()
        stage3_up_layout.addWidget(self.stage3_up_table)
        self.stage3_up_table.setColumnCount(5)
        self.stage3_up_table.setHorizontalHeaderLabels([
            "gene_id", "rho", "p_value", "q_value", "direction"
        ])

        # 下调基因表格页
        stage3_down_page, stage3_down_layout = create_styled_tab_page(self.genelists_tabs, "下调基因")
        self.stage3_down_table = create_styled_table()
        stage3_down_layout.addWidget(self.stage3_down_table)
        self.stage3_down_table.setColumnCount(5)
        self.stage3_down_table.setHorizontalHeaderLabels([
            "gene_id", "rho", "p_value", "q_value", "direction"
        ])

        # ========== 阶段四标签页：火山图 ==========
        stage4_volcano_page, stage4_volcano_layout = create_styled_tab_page(self.genelists_tabs, "火山图")
        self.stage4_volcano_label = create_zoomable_image_label()
        stage4_volcano_layout.addWidget(self.stage4_volcano_label)

        right_layout.addWidget(self.genelists_tabs)

        main_layout.addWidget(right_panel, 3)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.sc_monocle_genelists_page
