# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 数据加载类子层UI布局脚本
背景/导航/返回按钮由主层容器管理，本子层只负责内容区域，使用透明背景

两列布局（QHBoxLayout）：
    左侧 - 加载选项区域（扫描数据集 / 多选数据集 / 加载并运行PCA / 状态文本）
    右侧 - 4 个 PCA 图片标签页（不处理 / log2+1 / log2+1+scale / 仅scale）

规则：所有控件均从 gui_styles 模板函数创建，不硬编码
参考：KM曲线界面风格、差异筛选类界面风格
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_font_for_widget, get_stylesheet_for_widget,
    create_styled_panel, create_styled_tab_widget, create_styled_image_tab,
    create_styled_tab_page, create_styled_table,
    create_styled_label, create_styled_button, create_styled_list_widget,
    create_styled_text_edit, create_styled_progress_bar,
    create_styled_combo_box, create_labeled_param_with_help,
)


class BulkMachineLearningLoadingPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_machinelearning_loading_page = None
        # 控件引用
        self.option_panel = None          # 左侧加载选项区域
        self.btn_scan_datasets = None     # 扫描数据集按钮
        self.dataset_list = None          # 多选数据集列表
        self.btn_load_and_run = None      # 加载并运行PCA按钮
        self.progress_bar = None          # 运行进度条
        self.status_text = None           # 状态文本框
        self.preprocessing_combo = None   # 数据预处理类型下拉框（阶段二用）
        self.btn_run_combat = None        # 运行ComBat去批次按钮
        self.btn_run_clinical_sync = None # 运行阶段三：同步临床信息按钮
        self.tab_widget = None            # 右侧标签页
        self.raw_image_label = None           # 方法1：不处理 图片标签
        self.log2_image_label = None          # 方法2：log2+1 图片标签
        self.log2_scaled_image_label = None   # 方法3：log2+1+scale 图片标签
        self.scaled_image_label = None        # 方法4：仅scale 图片标签
        self.combat_image_label = None        # 去批次后PCA图片标签
        self.clinical_table = None            # 同步临床信息表格（阶段三结果）
        self.create_page()

    def update_background(self):
        """子层不管理背景，保持透明（背景由主层容器管理）"""
        pass

    def update_styles(self):
        """更新所有控件的样式（不修改控件尺寸）"""
        styles = get_mod_styles()

        title_label = self.bulk_machinelearning_loading_page.findChild(QLabel, "bulk_machinelearning_loading_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        # 更新label样式（排除标题和图片标签）
        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_machinelearning_loading_page.findChildren(QLabel):
            if child.objectName() != "bulk_machinelearning_loading_title" and not child.objectName().startswith("styled_image_label"):
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
        for child in self.bulk_machinelearning_loading_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        # 更新进度条样式
        if self.progress_bar is not None:
            from script.utils_layer.gui_styles import create_styled_progress_bar
            # 重新应用样式（通过重新创建一个临时进度条获取样式表）
            tmp = create_styled_progress_bar()
            self.progress_bar.setStyleSheet(tmp.styleSheet())
            tmp.deleteLater()

    def create_page(self):
        self.bulk_machinelearning_loading_page = QWidget(self.parent)
        self.bulk_machinelearning_loading_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()

        layout = QVBoxLayout(self.bulk_machinelearning_loading_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("机器学习分析 - 数据加载类")
        title_label.setObjectName("bulk_machinelearning_loading_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        # === 两列布局（QHBoxLayout） ===
        main_layout = QHBoxLayout()

        # ---- 左侧：加载选项区域 ----
        self.option_panel, option_layout = create_styled_panel(fixed_width=400)

        option_title = create_styled_label("加载选项", font_size=14, bold=True)
        option_layout.addWidget(option_title)

        option_layout.addSpacing(10)

        # 扫描数据集按钮
        self.btn_scan_datasets = create_styled_button("扫描数据集", font_size=12)
        option_layout.addWidget(self.btn_scan_datasets)

        option_layout.addSpacing(10)

        # 数据集列表标签
        dataset_list_label = create_styled_label("数据集列表（可多选）", font_size=11, bold=False)
        option_layout.addWidget(dataset_list_label)

        # 多选数据集列表
        self.dataset_list = create_styled_list_widget(
            multi_selection=True,
            fixed_height=150
        )
        option_layout.addWidget(self.dataset_list)

        option_layout.addSpacing(10)

        # 加载并运行PCA按钮
        self.btn_load_and_run = create_styled_button("加载并运行PCA", font_size=12, button_type='run')
        option_layout.addWidget(self.btn_load_and_run)

        option_layout.addSpacing(10)

        # 运行进度条（运行PCA时显示）
        self.progress_bar = create_styled_progress_bar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        option_layout.addWidget(self.progress_bar)

        option_layout.addSpacing(10)

        # 状态文本框
        self.status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.status_text.setMaximumHeight(80)
        self.status_text.setText("请先扫描数据集")
        option_layout.addWidget(self.status_text)

        option_layout.addSpacing(10)

        # ==== 阶段二：ComBat 去批次 ====
        # 数据预处理类型（带问号按钮）
        preprocessing_help = (
            "数据预处理方式说明：\n\n"
            "1. 不处理（原始TPM）：\n"
            "   直接使用原始表达值，保留数据的原始尺度。\n\n"
            "2. log2(x+1)（默认，推荐）：\n"
            "   对表达值做log2转换，压缩高表达基因的动态范围，\n"
            "   使数据分布更接近正态，是最常用的预处理方式。\n\n"
            "3. log2(x+1) + z-score：\n"
            "   在log2转换基础上再做z-score标准化，\n"
            "   消除基因间表达量量纲差异。\n\n"
            "4. 仅 z-score：\n"
            "   不做log2转换，仅做z-score标准化。\n\n"
            "【log2+scale 和 不加scale 两种方法都是优秀的解法，按需选取】\n"
            "   - 加 scale：强调基因的相对变化趋势\n"
            "   - 不加 scale：保留基因的绝对表达量差异"
        )
        preprocessing_label, preprocessing_q_btn = create_labeled_param_with_help(
            "数据预处理类型（阶段二）", preprocessing_help, font_size=12, bold=True
        )
        option_layout.addWidget(preprocessing_label)
        option_layout.addWidget(preprocessing_q_btn)

        # 数据预处理类型下拉框
        self.preprocessing_combo = create_styled_combo_box()
        self.preprocessing_combo.addItem("log2(x+1)", "log2")
        self.preprocessing_combo.addItem("不处理（原始TPM）", "raw")
        self.preprocessing_combo.addItem("log2(x+1) + z-score", "log2_scaled")
        self.preprocessing_combo.addItem("仅 z-score", "scaled")
        self.preprocessing_combo.setCurrentIndex(0)
        option_layout.addWidget(self.preprocessing_combo)

        option_layout.addSpacing(10)

        # 运行ComBat去批次按钮
        self.btn_run_combat = create_styled_button("运行阶段二：ComBat去批次", font_size=12, button_type='run')
        option_layout.addWidget(self.btn_run_combat)

        option_layout.addSpacing(10)

        # ==== 阶段三：同步临床信息 ====
        clinical_help = (
            "同步临床信息说明：\n\n"
            "1. 选择主注释数据集和临床列（如 IDH）\n"
            "2. 定义组别1/组别2（多选值映射，可自定义命名）\n"
            "3. 逐数据集映射临床列到组别1/组别2\n\n"
            "未分配到组别1/组别2 的样本将被丢弃。\n"
            "输出：组合版临床信息 txt（SampleID + 主注释列名）"
        )
        clinical_label, clinical_q_btn = create_labeled_param_with_help(
            "阶段三：同步临床信息", clinical_help, font_size=12, bold=True
        )
        option_layout.addWidget(clinical_label)
        option_layout.addWidget(clinical_q_btn)

        # 运行阶段三按钮
        self.btn_run_clinical_sync = create_styled_button("运行阶段三：同步临床信息", font_size=12, button_type='run')
        option_layout.addWidget(self.btn_run_clinical_sync)

        option_layout.addStretch()
        main_layout.addWidget(self.option_panel)

        # ---- 右侧：PCA 图片标签页区域 ----
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.tab_widget = create_styled_tab_widget()
        # 4 个 PCA 图片标签页
        _, self.raw_image_label = create_styled_image_tab(
            self.tab_widget, "不处理",
            default_text="请加载数据并运行 PCA"
        )
        _, self.log2_image_label = create_styled_image_tab(
            self.tab_widget, "log2+1",
            default_text="请加载数据并运行 PCA"
        )
        _, self.log2_scaled_image_label = create_styled_image_tab(
            self.tab_widget, "log2+1+scale",
            default_text="请加载数据并运行 PCA"
        )
        _, self.scaled_image_label = create_styled_image_tab(
            self.tab_widget, "仅scale",
            default_text="请加载数据并运行 PCA"
        )
        # 去批次后 PCA 图（阶段二）
        _, self.combat_image_label = create_styled_image_tab(
            self.tab_widget, "去批次后PCA",
            default_text="请运行阶段二进行ComBat去批次"
        )
        # 同步临床信息表格（阶段三）
        clinical_tab_page, clinical_tab_layout = create_styled_tab_page(self.tab_widget, "同步临床信息")
        self.clinical_table = create_styled_table()
        clinical_tab_layout.addWidget(self.clinical_table)

        right_layout.addWidget(self.tab_widget)
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        return self.bulk_machinelearning_loading_page
