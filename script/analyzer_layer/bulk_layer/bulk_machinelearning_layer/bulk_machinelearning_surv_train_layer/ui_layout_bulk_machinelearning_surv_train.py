# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 生存训练类(surv_train)子层UI布局脚本
背景/导航/返回按钮由主层容器管理，本子层只负责内容区域，使用透明背景

三列布局（QHBoxLayout）：
    左侧 - 参数区域框（基因集/算法组合/高变异基因/种子/每算法基因数/重要性比例）
    中间 - 结果标签页（数据概要 / iAUC热图 / 算法性能 / 最优基因）
    右侧 - 运行选项框（4 个阶段运行按钮 + 导出 + 进度条 + 状态文本）

规则：所有控件均从 gui_styles 模板函数创建，不硬编码
参考：差异训练类界面风格
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_font_for_widget, get_stylesheet_for_widget,
    create_styled_panel, create_styled_tab_widget, create_styled_image_tab,
    create_styled_tab_page, create_styled_text_edit,
    create_styled_label, create_styled_button, create_styled_progress_bar,
    create_styled_combo_box, create_styled_spinbox, create_styled_table,
    create_labeled_param_with_help,
)


class BulkMachineLearningSurvTrainPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_machinelearning_surv_train_page = None
        # 三列控件引用
        self.param_panel = None            # 左侧参数区域
        self.gene_file_combo = None        # 基因集文件下拉框
        self.methods_combo = None          # 算法组合文件下拉框
        self.max_genes_spin = None         # 高变异基因截断数
        self.seed_spin = None              # 随机种子
        self.max_features_spin = None      # 每算法基因数上限
        self.top_frac_spin = None          # 重要性Top-N比例
        self.plot_width_spin = None        # 热图设备宽度(cm)
        self.plot_height_spin = None       # 热图设备高度(cm)
        self.tab_widget = None             # 中间标签页
        self.stage1_data_text = None       # 阶段一数据概要
        self.iauc_heatmap_label = None     # 阶段三 iAUC 热图
        self.method_table = None           # 算法性能表
        self.best_genes_image_label = None # 最优基因图（预告留白）
        self.best_gene_table = None        # 最优基因表
        # 右侧运行选项
        self.run_option_panel = None
        self.btn_run_stage1 = None
        self.btn_run_stage2 = None
        self.btn_run_stage3 = None
        self.btn_run_stage4 = None
        self.btn_export_png = None
        self.btn_export_pdf = None
        self.btn_export_csv = None
        self.progress_bar = None
        self.status_text = None
        self.create_page()

    def update_background(self):
        """子层不管理背景，保持透明"""
        pass

    def update_styles(self):
        """更新所有控件的样式（不修改控件尺寸）"""
        styles = get_mod_styles()

        title_label = self.bulk_machinelearning_surv_train_page.findChild(QLabel, "bulk_machinelearning_surv_train_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_machinelearning_surv_train_page.findChildren(QLabel):
            if child.objectName() != "bulk_machinelearning_surv_train_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_machinelearning_surv_train_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        if self.progress_bar is not None:
            tmp = create_styled_progress_bar()
            self.progress_bar.setStyleSheet(tmp.styleSheet())
            tmp.deleteLater()

    def create_page(self):
        self.bulk_machinelearning_surv_train_page = QWidget(self.parent)
        self.bulk_machinelearning_surv_train_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()

        layout = QVBoxLayout(self.bulk_machinelearning_surv_train_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("机器学习分析 - 生存训练类")
        title_label.setObjectName("bulk_machinelearning_surv_train_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        # === 三列布局 ===
        main_layout = QHBoxLayout()

        # ---- 左侧：参数区域框 ----
        self.param_panel, param_layout = create_styled_panel(fixed_width=380)
        param_title = create_styled_label("参数区域", font_size=14, bold=True)
        param_layout.addWidget(param_title)
        param_layout.addSpacing(10)

        # ============ 阶段一：数据准备参数 ============
        s1 = create_styled_label("▎阶段一 · 数据准备", font_size=12, bold=True)
        s1.setStyleSheet("color: #F48FB1;")
        param_layout.addWidget(s1)
        param_layout.addSpacing(8)

        gene_help = (
            "基因集文件选择说明：\n\n"
            "基因集文件位于 appdata/genelists 目录内。\n"
            "用于限定生存分析的输入基因范围，与表达矩阵取交集后使用。\n"
            "选择「不使用基因集」则使用所有共同基因。\n\n"
            "示例：衰老相关核心基因.xlsx"
        )
        gene_label, gene_q = create_labeled_param_with_help("基因集文件（APPDATA/genelists）", gene_help, font_size=12, bold=True)
        param_layout.addWidget(gene_label)
        param_layout.addWidget(gene_q)
        self.gene_file_combo = create_styled_combo_box(fixed_height=26)
        self.gene_file_combo.addItem("不使用基因集")
        param_layout.addWidget(self.gene_file_combo)
        param_layout.addSpacing(12)

        maxgenes_help = (
            "高变异基因截断数：\n\n"
            "批量建模中部分算法(如glmBoost/Stepglm)基于全特征公式，\n"
            "无法处理数万基因。此处限制取变异度最高的前 N 个基因\n"
            "参与特征空间（参考量级约 1000）。"
        )
        maxgenes_label, maxgenes_q = create_labeled_param_with_help("高变异基因截断数", maxgenes_help, font_size=12, bold=True)
        param_layout.addWidget(maxgenes_label)
        param_layout.addWidget(maxgenes_q)
        self.max_genes_spin = create_styled_spinbox(fixed_height=26, min_value=50, max_value=5000, default_value=1000)
        param_layout.addWidget(self.max_genes_spin)
        param_layout.addSpacing(12)

        seed_help = (
            "随机种子：\n\n用于固定算法训练与基因划分的随机过程，\n"
            "保证多次运行可复现。默认 1234。"
        )
        seed_label, seed_q = create_labeled_param_with_help("随机种子", seed_help, font_size=12, bold=True)
        param_layout.addWidget(seed_label)
        param_layout.addWidget(seed_q)
        self.seed_spin = create_styled_spinbox(fixed_height=26, min_value=1, max_value=999999, default_value=1234)
        param_layout.addWidget(self.seed_spin)
        param_layout.addSpacing(14)

        # ============ 阶段二：批量建模参数 ============
        s2 = create_styled_label("▎阶段二 · 批量建模", font_size=12, bold=True)
        s2.setStyleSheet("color: #81C784;")
        param_layout.addWidget(s2)
        param_layout.addSpacing(8)

        methods_help = (
            "算法组合选择说明：\n\n"
            "文件位于 appdata/machinelearning 目录内。\n\n"
            "1. methods_simple.txt：少量常用模型，运行快\n"
            "2. methods_full.txt：完整算法，运行时间较长\n"
            "3. 可自定义添加算法列表 txt，每行一个算法组合。"
        )
        methods_label, methods_q = create_labeled_param_with_help("算法组合文件（APPDATA/machinelearning）", methods_help, font_size=12, bold=True)
        param_layout.addWidget(methods_label)
        param_layout.addWidget(methods_q)
        self.methods_combo = create_styled_combo_box(fixed_height=26)
        param_layout.addWidget(self.methods_combo)
        param_layout.addSpacing(12)

        mf_help = (
            "每算法提取基因数上限：\n\n"
            "对每个算法用重要性Top-N比例法提取选中基因后，\n"
            "若仍超过该上限，则按其训练集方差最高的前 N 个截断，\n"
            "避免无重要性算法(SVM径向核/KNN)返回海量特征。默认 50。"
        )
        mf_label, mf_q = create_labeled_param_with_help("每算法提取基因数上限", mf_help, font_size=12, bold=True)
        param_layout.addWidget(mf_label)
        param_layout.addWidget(mf_q)
        self.max_features_spin = create_styled_spinbox(fixed_height=26, min_value=3, max_value=500, default_value=50)
        param_layout.addWidget(self.max_features_spin)
        param_layout.addSpacing(12)

        tf_help = (
            "重要性Top-N比例：\n\n"
            "按算法输出重要性分数，保留前该比例(0.3=前30%)的基因\n"
            "作为该算法的纳入基因。默认 0.3。"
        )
        tf_label, tf_q = create_labeled_param_with_help("重要性Top-N比例", tf_help, font_size=12, bold=True)
        param_layout.addWidget(tf_label)
        param_layout.addWidget(tf_q)
        self.top_frac_spin = create_styled_spinbox(fixed_height=26, min_value=5, max_value=100, default_value=30, step=5)
        param_layout.addWidget(self.top_frac_spin)
        top_frac_note = create_styled_label("（此处填整数百分比，如 30 = 前30%）", font_size=10, bold=False)
        param_layout.addWidget(top_frac_note)

        param_layout.addSpacing(14)

        # ============ 阶段三：iAUC 热图尺寸参数 ============
        s3 = create_styled_label("▎阶段三 · iAUC 热图尺寸", font_size=12, bold=True)
        s3.setStyleSheet("color: #4FC3F7;")
        param_layout.addWidget(s3)
        param_layout.addSpacing(8)

        pwh_help = (
            "热图设备画布尺寸（单位 cm）：\n\n"
            "控制 heatmap 输出 PDF/PNG 的画布宽高。\n"
            "算法/队列较多时适当调大，太少时调小，可在页面右侧\n"
            "表格中看到效果后按需微调。"
        )
        pw_label, pw_q = create_labeled_param_with_help("热图画布宽度(cm)", pwh_help, font_size=12, bold=True)
        param_layout.addWidget(pw_label)
        param_layout.addWidget(pw_q)
        self.plot_width_spin = create_styled_spinbox(fixed_height=26, min_value=6, max_value=60, default_value=12)
        param_layout.addWidget(self.plot_width_spin)
        param_layout.addSpacing(10)

        ph_label, ph_q = create_labeled_param_with_help("热图画布高度(cm)", pwh_help, font_size=12, bold=True)
        param_layout.addWidget(ph_label)
        param_layout.addWidget(ph_q)
        self.plot_height_spin = create_styled_spinbox(fixed_height=26, min_value=4, max_value=60, default_value=8)
        param_layout.addWidget(self.plot_height_spin)

        param_layout.addSpacing(10)
        param_layout.addStretch()
        main_layout.addWidget(self.param_panel)

        # ---- 中间：结果标签页区域 ----
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)

        self.tab_widget = create_styled_tab_widget()

        # 阶段一：数据概要
        s1_page, s1_layout = create_styled_tab_page(self.tab_widget, "阶段一：数据概要")
        self.stage1_data_text = create_styled_text_edit(read_only=True, variant='sub')
        self.stage1_data_text.setPlainText("运行阶段一后显示训练数据概要（基因数/样本数/数据集/生存事件数）")
        s1_layout.addWidget(self.stage1_data_text)

        # 阶段三：iAUC 热图
        _, self.iauc_heatmap_label = create_styled_image_tab(
            self.tab_widget, "生存 iAUC 热图", default_text="请运行阶段三生成 iAUC 热图"
        )

        # 阶段三：算法性能表
        method_page, method_layout = create_styled_tab_page(self.tab_widget, "算法性能")
        self.method_table = create_styled_table()
        self.method_table.setColumnCount(1)
        self.method_table.setHorizontalHeaderLabels(["提示"])
        self.method_table.horizontalHeader().setStretchLastSection(True)
        self.method_table.verticalHeader().setDefaultSectionSize(24)
        method_layout.addWidget(self.method_table)

        # 阶段四：最优基因图（仅 iAUC 相关，R 中未强制出图，展示基因表）
        # 简化：只提供「最优基因表」
        gene_page, gene_layout = create_styled_tab_page(self.tab_widget, "最优基因表")
        self.best_gene_table = create_styled_table()
        self.best_gene_table.setColumnCount(1)
        self.best_gene_table.setHorizontalHeaderLabels(["提示"])
        self.best_gene_table.horizontalHeader().setStretchLastSection(True)
        self.best_gene_table.verticalHeader().setDefaultSectionSize(24)
        gene_layout.addWidget(self.best_gene_table)

        center_layout.addWidget(self.tab_widget)
        main_layout.addWidget(center_panel, 1)

        # ---- 右侧：运行选项框区域 ----
        self.run_option_panel, run_layout = create_styled_panel(fixed_width=300)
        run_title = create_styled_label("运行选项", font_size=14, bold=True)
        run_layout.addWidget(run_title)
        run_layout.addSpacing(10)
        run_layout.addWidget(create_styled_label("生存分析流程（4 阶段）", font_size=11, bold=False))
        run_layout.addSpacing(6)

        self.btn_run_stage1 = create_styled_button("阶段一：数据准备", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage1)

        self.btn_run_stage2 = create_styled_button("阶段二：批量建模(算法选基因)", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage2)

        self.btn_run_stage3 = create_styled_button("阶段三：生存分析+iAUC热图", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage3)

        self.btn_run_stage4 = create_styled_button("阶段四：最优基因", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage4)

        run_layout.addSpacing(12)
        run_layout.addWidget(create_styled_label("导出结果", font_size=12, bold=True))
        run_layout.addSpacing(4)

        self.btn_export_png = create_styled_button("导出全部图片 PNG → zip", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_export_png)

        self.btn_export_pdf = create_styled_button("导出全部图片 PDF → zip", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_export_pdf)

        self.btn_export_csv = create_styled_button("导出最优基因 CSV", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_export_csv)

        # 发送最终入选的最优特征基因（阶段四最优基因）到 appdata/genelists
        # （控件只在这里创建；信号连接与落盘逻辑在 ui_bind_bulk_machinelearning_surv_train）
        self.btn_send_to_genelist = create_styled_button("发送到列表文件夹", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_send_to_genelist)

        run_layout.addSpacing(10)
        self.progress_bar = create_styled_progress_bar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        run_layout.addWidget(self.progress_bar)

        run_layout.addSpacing(10)
        self.status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.status_text.setMaximumHeight(120)
        self.status_text.setText("请先完成「数据加载类」(去批次+同步临床信息)，再运行阶段一")
        run_layout.addWidget(self.status_text)

        run_layout.addStretch()
        main_layout.addWidget(self.run_option_panel)

        layout.addLayout(main_layout)

        return self.bulk_machinelearning_surv_train_page
