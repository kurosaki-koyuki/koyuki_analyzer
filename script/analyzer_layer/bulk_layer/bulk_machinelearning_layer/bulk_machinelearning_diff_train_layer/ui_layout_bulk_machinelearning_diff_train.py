# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 差异训练类(diff_train)子层UI布局脚本
背景/导航/返回按钮由主层容器管理，本子层只负责内容区域，使用透明背景

三列布局（QHBoxLayout）：
    左侧 - 参数区域框（基因集文件选择）
    中间 - 结果标签页（阶段二单模型 / 阶段四AUC热图 / 阶段五核心基因）
    右侧 - 运行选项框（5 个阶段运行按钮 + 进度条 + 状态文本）

规则：所有控件均从 gui_styles 模板函数创建，不硬编码
参考：数据加载类(PCA)界面风格
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_font_for_widget, get_stylesheet_for_widget,
    create_styled_panel, create_styled_tab_widget, create_styled_image_tab,
    create_styled_tab_page, create_styled_text_edit,
    create_styled_label, create_styled_button, create_styled_progress_bar,
    create_styled_combo_box, create_styled_spinbox,
    create_styled_table,
    create_labeled_param_with_help,
)


def _make_table_item(text, color=None):
    """构建一个 QTableWidgetItem，用于表格填充（带前景色设置）"""
    from PyQt5.QtWidgets import QTableWidgetItem
    from PyQt5.QtGui import QColor
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(int(Qt.AlignLeft | Qt.AlignVCenter))
    if color is not None:
        try:
            item.setForeground(QColor(color))
        except Exception:
            pass
    return item


class BulkMachineLearningDiffTrainPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_machinelearning_diff_train_page = None
        # 三列控件引用
        self.param_panel = None            # 左侧参数区域
        self.gene_file_combo = None        # 基因集文件下拉框
        self.methods_combo = None          # 算法组合文件下拉框
        self.max_genes_spin = None         # 高变异基因截断数
        self.seed_spin = None              # 随机种子
        self.tab_widget = None             # 中间标签页
        # 阶段二：单模型标签
        self.lasso_roc_label = None        # Lasso ROC
        self.lasso_cv_label = None         # Lasso 交叉验证
        self.rf_roc_label = None           # RF ROC
        self.rf_importance_label = None    # RF 变量重要性
        self.svm_roc_label = None          # SVM ROC
        # 阶段四：AUC 热图标签
        self.auc_heatmap_label = None
        # 阶段一：数据准备概要文本
        self.stage1_data_text = None
        # 阶段五：核心基因结果
        self.core_genes_image_label = None
        self.core_genes_text = None        # 基因筛选文本(平铺旧控件, 预留)
        self.core_genes_table = None       # 核心基因表格(需求4: 表格模板显示)
        # 阶段五：筛选模式与条件控件
        self.filter_mode_combo = None      # 筛选模式下拉框
        self.filter_top_n_label = None     # Top N 基因数标签
        self.filter_n_models_label = None  # 至少 N 个模型标签
        self.filter_avg_rank_label = None  # 平均排名前 N 标签
        self.filter_top_n_spin = None      # Top N 输入框
        self.filter_n_models_spin = None   # nModels 输入框
        self.filter_avg_rank_spin = None   # AverageRank 输入框
        # 阶段四：AUC 阈值筛选
        self.auc_threshold_label = None    # AUC 阈值标签
        self.auc_threshold_spin = None     # AUC 阈值输入框(0=不筛选, 0.5-1 筛选)
        # 右侧运行选项
        self.run_option_panel = None       # 右侧运行选项区域
        self.btn_run_stage1 = None         # 阶段一：数据准备
        self.btn_run_stage2 = None         # 阶段二：单模型
        self.btn_run_stage3 = None         # 阶段三：批量建模
        self.btn_run_stage4 = None         # 阶段四：AUC+热图
        self.btn_run_stage5 = None         # 阶段五：核心基因
        # 导出按钮(需求6)
        self.btn_export_png = None         # 导出全部图片 png -> zip
        self.btn_export_pdf = None         # 导出全部图片 pdf -> zip
        self.btn_export_csv = None         # 导出基因列表 csv
        self.progress_bar = None           # 运行进度条
        self.status_text = None            # 状态文本框
        self.create_page()

    def update_background(self):
        """子层不管理背景，保持透明（背景由主层容器管理）"""
        pass

    def update_styles(self):
        """更新所有控件的样式（不修改控件尺寸）"""
        styles = get_mod_styles()

        title_label = self.bulk_machinelearning_diff_train_page.findChild(QLabel, "bulk_machinelearning_diff_train_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        # 更新label样式（排除标题和图片标签）
        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_machinelearning_diff_train_page.findChildren(QLabel):
            if child.objectName() != "bulk_machinelearning_diff_train_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        # 更新panel样式
        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_machinelearning_diff_train_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        # 更新进度条样式
        if self.progress_bar is not None:
            tmp = create_styled_progress_bar()
            self.progress_bar.setStyleSheet(tmp.styleSheet())
            tmp.deleteLater()

    def _init_core_table_default(self):
        """基因列表表格初始提示（运行阶段五前显示占位说明）"""
        if self.core_genes_table is None:
            return
        styles = get_mod_styles()
        text_color = styles.get('sub_text_color', '#87CEEB')
        self.core_genes_table.setRowCount(1)
        placeholder = "运行阶段五后在此显示全部核心基因列表（表格形式）。"
        self.core_genes_table.setItem(
            0, 0, _make_table_item(placeholder, text_color)
        )
        self.core_genes_table.setSpan(0, 0, 1, 4)

    def create_page(self):
        self.bulk_machinelearning_diff_train_page = QWidget(self.parent)
        self.bulk_machinelearning_diff_train_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()

        layout = QVBoxLayout(self.bulk_machinelearning_diff_train_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("机器学习分析 - 差异训练类")
        title_label.setObjectName("bulk_machinelearning_diff_train_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        # === 三列布局（QHBoxLayout） ===
        main_layout = QHBoxLayout()

        # ---- 左侧：参数区域框 ----
        self.param_panel, param_layout = create_styled_panel(fixed_width=380)

        param_title = create_styled_label("参数区域", font_size=14, bold=True)
        param_layout.addWidget(param_title)

        param_layout.addSpacing(10)

        # ======================= 阶段一：数据准备参数 =======================
        stage1_group_title = create_styled_label("▎阶段一 · 数据准备", font_size=12, bold=True)
        stage1_group_title.setStyleSheet("color: #F48FB1;")
        param_layout.addWidget(stage1_group_title)
        param_layout.addSpacing(8)

        # ============ 参数区：基因集文件（下拉框，来自 APPDATA/genelists 扫描） ============
        gene_help = (
            "基因集文件选择说明：\n\n"
            "基因集文件位于程序 appdata/genelists 目录内，\n"
            "请先将基因列表文件（xlsx/xls/txt/csv）放入该目录。\n\n"
            "1. 下拉框中会自动枚举该目录下的所有基因集文件。\n\n"
            "2. 用于限定机器学习建模的输入基因范围，\n"
            "   分析与表达矩阵取交集后使用。\n\n"
            "3. 选择「不使用基因集」：\n"
            "   则使用所有加载基因的全体交集，不额外筛选。\n\n"
            "4. 选择后点击「阶段一：数据准备」应用。"
        )
        gene_label, gene_q_btn = create_labeled_param_with_help(
            "基因集文件（APPDATA/genelists）", gene_help, font_size=12, bold=True
        )
        param_layout.addWidget(gene_label)
        param_layout.addWidget(gene_q_btn)

        self.gene_file_combo = create_styled_combo_box(fixed_height=26)
        self.gene_file_combo.addItem("不使用基因集")
        param_layout.addWidget(self.gene_file_combo)

        param_layout.addSpacing(12)

        # ============ 参数区：高变异基因截断数（默认1000） ============
        maxgenes_help = (
            "高变异基因截断数说明：\n\n"
            "批量建模中部分算法（如 Stepglm/glmBoost）基于全特征公式，\n"
            "无法处理数万基因，且超多特征会显著拖慢运行。\n\n"
            "此处限制取表达量变异度最高的前 N 个基因参与建模\n"
            "（参考量级约 771 基因）。\n\n"
            "若已指定基因集且基因数较少，则不触发该截断。"
        )
        maxgenes_label, maxgenes_q_btn = create_labeled_param_with_help(
            "高变异基因截断数", maxgenes_help, font_size=12, bold=True
        )
        param_layout.addWidget(maxgenes_label)
        param_layout.addWidget(maxgenes_q_btn)

        self.max_genes_spin = create_styled_spinbox(
            fixed_height=26, min_value=50, max_value=20000, default_value=1000
        )
        param_layout.addWidget(self.max_genes_spin)

        param_layout.addSpacing(12)

        # ============ 参数区：随机种子（默认1234，参考脚本一致） ============
        seed_help = (
            "随机种子说明：\n\n"
            "用于固定模型训练与交叉验证的随机过程，\n"
            "保证多次运行结果可复现。\n\n"
            "默认 1234，与参考脚本「成功测试脚本.R」中的 set.seed(1234) 一致。\n"
            "可自行修改为其他整数。"
        )
        seed_label, seed_q_btn = create_labeled_param_with_help(
            "随机种子", seed_help, font_size=12, bold=True
        )
        param_layout.addWidget(seed_label)
        param_layout.addWidget(seed_q_btn)

        self.seed_spin = create_styled_spinbox(
            fixed_height=26, min_value=1, max_value=999999, default_value=1234
        )
        param_layout.addWidget(self.seed_spin)

        param_layout.addSpacing(14)

        # ======================= 阶段三：批量建模参数 =======================
        stage3_group_title = create_styled_label("▎阶段三 · 批量建模", font_size=12, bold=True)
        stage3_group_title.setStyleSheet("color: #81C784;")
        param_layout.addWidget(stage3_group_title)
        param_layout.addSpacing(8)

        # ============ 参数区：算法组合文件（下拉框，来自 APPDATA/machinelearning 扫描） ============
        methods_help = (
            "算法组合选择说明：\n\n"
            "算法组合文件位于程序 appdata/machinelearning 目录内。\n\n"
            "1. 简易算法集（methods_simple.txt）：\n"
            "   少量常用模型（Lasso/RF/SVM/Enet/GBM/XGBoost 等），\n"
            "   运行快，适合快速验证。推荐先使用。\n\n"
            "2. 完整算法集（methods_full.txt）：\n"
            "   113 种算法组合，运行时间较长。\n\n"
            "3. 可在 appdata/machinelearning 内自由添加自定义\n"
            "   算法列表 txt 文件，每行一个算法组合。\n\n"
            "格式示例（每行一个）：\n"
            "   Lasso\n"
            "   RF + Enet [alpha=0.1]\n"
            "   Stepglm [forward] + XGBoost"
        )
        methods_label, methods_q_btn = create_labeled_param_with_help(
            "算法组合文件（APPDATA/machinelearning）", methods_help, font_size=12, bold=True
        )
        param_layout.addWidget(methods_label)
        param_layout.addWidget(methods_q_btn)

        self.methods_combo = create_styled_combo_box(fixed_height=26)
        param_layout.addWidget(self.methods_combo)

        param_layout.addSpacing(14)

        # ======================= 阶段四：AUC 阈值筛选 =======================
        stage4_group_title = create_styled_label("▎阶段四 · AUC 阈值筛选", font_size=12, bold=True)
        stage4_group_title.setStyleSheet("color: #FFB74D;")
        param_layout.addWidget(stage4_group_title)
        param_layout.addSpacing(8)

        auc_help = (
            "AUC 阈值筛选（阶段四/阶段五）：\n\n"
            "输入 0（默认）为不筛选，全部算法均纳入阶段四五。\n"
            "输入 0.5-1 之间的数字时，仅保留平均 AUC 高于等于\n"
            "该阈值的算法，用于后续阶段四出图与阶段五基因计数；\n"
            "被筛选掉的算法不纳入阶段五计数。"
        )
        auc_label, auc_q_btn = create_labeled_param_with_help(
            "AUC 阈值筛选（0=不筛选）", auc_help, font_size=11, bold=False
        )
        param_layout.addWidget(auc_label)
        param_layout.addWidget(auc_q_btn)

        self.auc_threshold_spin = create_styled_spinbox(
            fixed_height=26, min_value=0, max_value=1, default_value=0, step=0.05
        )
        param_layout.addWidget(self.auc_threshold_spin)

        param_layout.addSpacing(14)

        # ======================= 阶段五：核心基因筛选参数 =======================
        stage5_group_title = create_styled_label("▎阶段五 · 核心基因筛选", font_size=12, bold=True)
        stage5_group_title.setStyleSheet("color: #64B5F6;")
        param_layout.addWidget(stage5_group_title)
        param_layout.addSpacing(8)

        # ---- 筛选模式下拉框 ----
        mode_help = (
            "核心基因筛选模式说明（基于参考脚本的交集法）：\n\n"
            "交集法：取平均AUC最高的 Top10 个模型，\n"
            "统计每个基因被这 Top10 模型纳入的次数，\n"
            "基因须出现 ≥ 交集阈值(N) 次才入选（N 默认 5，参考默认）。\n\n"
            "1. 基因排名（Top N）：\n"
            "   在交集池内按综合排名取前 N 个核心基因（默认 30）。\n\n"
            "2. nModels 模式：\n"
            "   直接输出交集池全部基因（出现 ≥ 阈值 次，默认 5）。\n\n"
            "3. AverageRank 模式：\n"
            "   在交集池内再按平均排名前 N 筛选（默认 100）。\n\n"
            "4. 复合模式（默认）：\n"
            "   同时应用上面 3 个条件，Top 默认 30，\n"
            "   交集阈值默认 5，AverageRank 可填 0 表示不限制\n"
            "   （至少需一个条件生效才可运行阶段五）。"
        )
        mode_label, mode_q_btn = create_labeled_param_with_help(
            "核心基因筛选模式", mode_help, font_size=12, bold=True
        )
        param_layout.addWidget(mode_label)
        param_layout.addWidget(mode_q_btn)

        self.filter_mode_combo = create_styled_combo_box(fixed_height=26)
        self.filter_mode_combo.addItems(["复合模式", "基因排名 (Top N)", "nModels 模式", "AverageRank 模式"])
        param_layout.addWidget(self.filter_mode_combo)

        param_layout.addSpacing(8)

        # ---- 条件输入框（随模式动态显隐） ----
        # 子容器：为便于整组显隐，使用三个独立 spin，各自附带简短标签
        self.filter_top_n_spin = create_styled_spinbox(
            fixed_height=26, min_value=0, max_value=5000, default_value=30
        )
        self.filter_n_models_spin = create_styled_spinbox(
            fixed_height=26, min_value=1, max_value=10, default_value=5
        )
        self.filter_avg_rank_spin = create_styled_spinbox(
            fixed_height=26, min_value=0, max_value=5000, default_value=0
        )

        self.filter_top_n_label = create_styled_label("Top N 基因数", font_size=11, bold=False)
        self.filter_n_models_label = create_styled_label("交集阈值 (Top10 模型内出现≥N)", font_size=11, bold=False)
        self.filter_avg_rank_label = create_styled_label("平均排名前 N", font_size=11, bold=False)

        param_layout.addWidget(self.filter_top_n_label)
        param_layout.addWidget(self.filter_top_n_spin)
        param_layout.addSpacing(6)
        param_layout.addWidget(self.filter_n_models_label)
        param_layout.addWidget(self.filter_n_models_spin)
        param_layout.addSpacing(6)
        param_layout.addWidget(self.filter_avg_rank_label)
        param_layout.addWidget(self.filter_avg_rank_spin)

        param_layout.addSpacing(10)
        param_layout.addStretch()
        main_layout.addWidget(self.param_panel)

        # ---- 中间：结果标签页区域 ----
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)

        self.tab_widget = create_styled_tab_widget()

        # 阶段一：数据准备概要文本标签页
        stage1_page, stage1_layout = create_styled_tab_page(self.tab_widget, "阶段一：数据概要")
        self.stage1_data_text = create_styled_text_edit(read_only=True, variant='sub')
        self.stage1_data_text.setPlainText("运行阶段一后显示读取的训练数据概要（基因数/样本数/分组分布）")
        stage1_layout.addWidget(self.stage1_data_text)

        # 阶段二：单模型标签页（各模型图为平级标签页）
        _, self.lasso_cv_label = create_styled_image_tab(
            self.tab_widget, "Lasso 交叉验证", default_text="请运行阶段二生成 Lasso 交叉验证图"
        )
        _, self.lasso_roc_label = create_styled_image_tab(
            self.tab_widget, "Lasso ROC", default_text="请运行阶段二生成 Lasso ROC 曲线"
        )
        _, self.rf_importance_label = create_styled_image_tab(
            self.tab_widget, "RF 变量重要性", default_text="请运行阶段二生成随机森林重要性图"
        )
        _, self.rf_roc_label = create_styled_image_tab(
            self.tab_widget, "RF ROC", default_text="请运行阶段二生成随机森林 ROC 曲线"
        )
        _, self.svm_roc_label = create_styled_image_tab(
            self.tab_widget, "SVM ROC", default_text="请运行阶段二生成 SVM ROC 曲线"
        )

        # 阶段四：AUC 热图标签页
        _, self.auc_heatmap_label = create_styled_image_tab(
            self.tab_widget, "AUC 热图", default_text="请运行阶段四生成 AUC 热图"
        )

        # 阶段五：核心基因标签页
        _, self.core_genes_image_label = create_styled_image_tab(
            self.tab_widget, "核心基因图", default_text="请运行阶段五生成核心基因图"
        )
        # 基因列表标签页：使用表格模板显示全部基因(需求4/5)
        core_table_page, core_table_layout = create_styled_tab_page(self.tab_widget, "基因列表")
        self.core_genes_table = create_styled_table()
        self.core_genes_table.setColumnCount(4)
        self.core_genes_table.setHorizontalHeaderLabels(
            ["基因名 (Gene)", "纳入模型数 (NModels)", "频率 (Frequency)", "平均排名 (AvgRank)"]
        )
        self.core_genes_table.horizontalHeader().setStretchLastSection(True)
        self.core_genes_table.verticalHeader().setDefaultSectionSize(24)
        self._init_core_table_default()
        core_table_layout.addWidget(self.core_genes_table)

        center_layout.addWidget(self.tab_widget)
        main_layout.addWidget(center_panel, 1)

        # ---- 右侧：运行选项框区域 ----
        self.run_option_panel, run_layout = create_styled_panel(fixed_width=300)

        run_title = create_styled_label("运行选项", font_size=14, bold=True)
        run_layout.addWidget(run_title)

        run_layout.addSpacing(10)
        run_layout.addWidget(create_styled_label("机器学习流程（仅训练）", font_size=11, bold=False))
        run_layout.addSpacing(6)

        # 5 个阶段按钮
        self.btn_run_stage1 = create_styled_button("阶段一：数据准备", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage1)

        self.btn_run_stage2 = create_styled_button("阶段二：单模型(Lasso/RF/SVM)", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage2)

        self.btn_run_stage3 = create_styled_button("阶段三：批量建模(113算法)", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage3)

        self.btn_run_stage4 = create_styled_button("阶段四：AUC计算+热图", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage4)

        self.btn_run_stage5 = create_styled_button("阶段五：核心基因筛选", font_size=12, button_type='run')
        run_layout.addWidget(self.btn_run_stage5)

        run_layout.addSpacing(12)

        # ---- 导出按钮区(需求6) ----
        run_layout.addWidget(create_styled_label("导出结果", font_size=12, bold=True))
        run_layout.addSpacing(4)

        self.btn_export_png = create_styled_button("导出全部图片 PNG → zip", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_export_png)

        self.btn_export_pdf = create_styled_button("导出全部图片 PDF → zip", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_export_pdf)

        self.btn_export_csv = create_styled_button("导出基因列表 CSV", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_export_csv)

        # 发送最终入选的特征基因（阶段五核心基因列表）到 appdata/genelists
        # （控件只在这里创建；信号连接与落盘逻辑在 ui_bind_bulk_machinelearning_diff_train）
        self.btn_send_to_genelist = create_styled_button("发送到列表文件夹", font_size=11, button_type='export')
        run_layout.addWidget(self.btn_send_to_genelist)

        run_layout.addSpacing(10)

        # 进度条
        self.progress_bar = create_styled_progress_bar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        run_layout.addWidget(self.progress_bar)

        run_layout.addSpacing(10)

        # 状态文本框
        self.status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.status_text.setMaximumHeight(120)
        self.status_text.setText("请先完成「数据加载类」(去批次+同步临床信息)，再运行阶段一")
        run_layout.addWidget(self.status_text)

        run_layout.addStretch()
        main_layout.addWidget(self.run_option_panel)

        layout.addLayout(main_layout)

        return self.bulk_machinelearning_diff_train_page
