# -*- coding: utf-8 -*-
"""
CellChat初步分析类界面UI布局脚本
模仿基础表达类R版本风格：左侧固定面板 + 右侧标签页
只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_text_edit, create_styled_tab_widget, create_styled_image_tab,
    create_styled_checkbox, create_questions_button
)
from PyQt5.QtWidgets import QButtonGroup
from script.mods_layer.mod_manager import global_mod_manager


class ScCellChatPrimaryPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_cellchat_primary_page = None
        self.create_page()

    def update_background(self):
        """更新背景图（子页面不处理，由主容器统一管理）"""
        pass

    def update_styles(self):
        """更新子层样式（mod切换时由主层递归调用）"""
        styles = get_mod_styles()

        # 标题样式
        title_label = self.sc_cellchat_primary_page.findChild(QLabel, "sc_cellchat_primary_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};"
            )

        # 按钮样式
        button_style = get_stylesheet_for_widget('button')
        for child in self.sc_cellchat_primary_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        # 运行按钮样式
        if hasattr(self, 'btn_run_stage1'):
            self.btn_run_stage1.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_run_stage2'):
            self.btn_run_stage2.setStyleSheet(get_stylesheet_for_widget('run_button'))

        # 下拉框样式
        combo_style = get_stylesheet_for_widget('combo')
        for child in self.sc_cellchat_primary_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        # 输入框样式
        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.sc_cellchat_primary_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        # 文本编辑样式
        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.sc_cellchat_primary_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        # 标签样式
        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_cellchat_primary_page.findChildren(QLabel):
            if child.objectName() != "sc_cellchat_primary_title":
                child.setStyleSheet(label_style)

        # 面板样式
        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_cellchat_primary_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        self.update_background()

    def create_page(self):
        self.sc_cellchat_primary_page = QWidget(self.parent)
        self.sc_cellchat_primary_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()

        layout = QVBoxLayout(self.sc_cellchat_primary_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== 顶部：标题 + 音乐控制器 ==========
        top_layout = QHBoxLayout()

        title_label = QLabel("CellChat通讯分析")
        title_label.setObjectName("sc_cellchat_primary_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # music_controller（按项目规则保留，供全局同步函数发现）
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.sc_cellchat_primary_page, mod_instance)

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

        # ========== 状态日志区（顶部） ==========
        self.cellchat_log = create_styled_text_edit(read_only=True, variant='sub')
        self.cellchat_log.setMaximumHeight(80)
        layout.addWidget(self.cellchat_log)

        # ========== 主区域：左侧参数面板 + 右侧标签页 ==========
        main_layout = QHBoxLayout()

        # ========== 左侧参数面板（可滚动） ==========
        left_panel, left_panel_layout = create_styled_panel(parent=self.sc_cellchat_primary_page)
        left_panel.setMinimumWidth(340)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 数据信息区
        info_title = create_styled_label("数据信息", font_size=14, bold=True)
        left_layout.addWidget(info_title)

        self.data_info_text = create_styled_text_edit(read_only=True, variant='sub')
        self.data_info_text.setMaximumHeight(100)
        self.data_info_text.setPlaceholderText("数据未加载\n请从主页加载RDS文件")
        left_layout.addWidget(self.data_info_text)

        left_layout.addSpacing(15)

        # ========== 阶段一：数据加载与UMAP出图 ==========
        stage1_title = create_styled_label("阶段一：注释出图", font_size=14, bold=True)
        left_layout.addWidget(stage1_title)

        left_layout.addSpacing(8)

        # 注释列选择
        annotation_label = create_styled_label("注释列", font_size=10, bold=True)
        left_layout.addWidget(annotation_label)

        self.combo_annotation = create_styled_combo_box()
        self.combo_annotation.addItem("选择注释列")
        left_layout.addWidget(self.combo_annotation)

        left_layout.addSpacing(10)

        # 阶段一运行按钮
        self.btn_run_stage1 = create_styled_button("生成UMAP图", font_size=12, button_type='run')
        self.btn_run_stage1.setEnabled(False)
        left_layout.addWidget(self.btn_run_stage1)

        left_layout.addSpacing(15)

        # ========== 阶段二：细胞筛选与重新降维 ==========
        stage2_title = create_styled_label("阶段二：细胞筛选与重新降维", font_size=14, bold=True)
        left_layout.addWidget(stage2_title)

        stage2_note = create_styled_label("筛选细胞群并可选重新降维", font_size=10, bold=False)
        stage2_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage2_note)

        left_layout.addSpacing(10)

        # 主注释列
        main_annot_label = create_styled_label("主注释列", font_size=10, bold=True)
        left_layout.addWidget(main_annot_label)
        self.combo_main_annot = create_styled_combo_box()
        self.combo_main_annot.addItem("选择注释列")
        left_layout.addWidget(self.combo_main_annot)

        # 主注释分组（多选）
        main_group_label = create_styled_label("主注释分组（多选）", font_size=9, bold=True)
        left_layout.addWidget(main_group_label)
        self.list_main_groups = create_styled_list_widget(fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.list_main_groups)

        left_layout.addSpacing(8)

        # 筛选条件1
        filter1_label = create_styled_label("筛选条件1", font_size=10, bold=True)
        left_layout.addWidget(filter1_label)
        self.combo_filter1 = create_styled_combo_box()
        self.combo_filter1.addItem("不筛选")
        left_layout.addWidget(self.combo_filter1)
        self.list_filter1 = create_styled_list_widget(fixed_height=40, multi_selection=True)
        left_layout.addWidget(self.list_filter1)

        left_layout.addSpacing(8)

        # 筛选条件2
        filter2_label = create_styled_label("筛选条件2", font_size=10, bold=True)
        left_layout.addWidget(filter2_label)
        self.combo_filter2 = create_styled_combo_box()
        self.combo_filter2.addItem("不筛选")
        left_layout.addWidget(self.combo_filter2)
        self.list_filter2 = create_styled_list_widget(fixed_height=40, multi_selection=True)
        left_layout.addWidget(self.list_filter2)

        left_layout.addSpacing(10)

        # 重新降维选项
        re_reduce_layout = QHBoxLayout()
        self.check_re_reduce = create_styled_checkbox("重新降维")
        self.check_re_reduce.setChecked(False)
        re_reduce_layout.addWidget(self.check_re_reduce)
        
        dim_label = create_styled_label("dim:", font_size=9, bold=True)
        re_reduce_layout.addWidget(dim_label)
        
        self.input_dim_val = create_styled_line_edit()
        self.input_dim_val.setText("30")
        self.input_dim_val.setFixedWidth(50)
        re_reduce_layout.addWidget(self.input_dim_val)
        
        dim_help_btn = create_questions_button("""dim值说明

dim值用于指定PCA降维时保留的主成分数量，并非UMAP的维度。

推荐值：
- 一般数据集：20-50
- 复杂数据集（细胞类型多）：30-60
- 简单数据集（细胞类型少）：10-30

选择原则：
1. 查看PCA累计方差贡献率（Elbow Plot）
2. 通常选择解释80%-90%方差的PC数量
3. 对于后续UMAP可视化，30是常用的默认值
4. 值太小可能丢失重要信息
5. 值太大可能引入噪声

注意：
- 当主注释分组不全选时，自动勾选重新降维
- 重新降维会基于筛选后的细胞重新计算PCA和UMAP""")
        re_reduce_layout.addWidget(dim_help_btn)
        
        left_layout.addLayout(re_reduce_layout)

        left_layout.addSpacing(10)

        # 筛选后出图注释
        plot_annot_label = create_styled_label("筛选后出图注释", font_size=10, bold=True)
        left_layout.addWidget(plot_annot_label)
        self.combo_plot_annot = create_styled_combo_box()
        self.combo_plot_annot.addItem("选择注释列")
        left_layout.addWidget(self.combo_plot_annot)

        left_layout.addSpacing(15)

        # 阶段二运行按钮
        self.btn_run_stage2 = create_styled_button("▶ 执行筛选", font_size=12, button_type='run')
        self.btn_run_stage2.setEnabled(False)
        left_layout.addWidget(self.btn_run_stage2)

        left_layout.addSpacing(15)

        # ========== 阶段三：CellChat通讯分析 ==========
        stage3_title = create_styled_label("阶段三：CellChat通讯分析", font_size=14, bold=True)
        left_layout.addWidget(stage3_title)

        stage3_note = create_styled_label("创建CellChat对象并预测通讯网络", font_size=10, bold=False)
        stage3_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage3_note)

        left_layout.addSpacing(10)

        # --- 注释列选择 ---
        stage3_annot_layout = QHBoxLayout()
        stage3_annot_label = create_styled_label("注释列", font_size=10, bold=True)
        stage3_annot_layout.addWidget(stage3_annot_label)
        
        self.combo_stage3_annot = create_styled_combo_box()
        self.combo_stage3_annot.addItem("默认（使用阶段一）")
        stage3_annot_layout.addWidget(self.combo_stage3_annot)
        
        left_layout.addLayout(stage3_annot_layout)

        left_layout.addSpacing(8)

        # --- 数据库选择（步骤3）---
        db_layout = QHBoxLayout()
        db_label = create_styled_label("数据库类型", font_size=10, bold=True)
        db_layout.addWidget(db_label)
        
        self.combo_db_type = create_styled_combo_box()
        self.combo_db_type.addItems(["human", "mouse"])
        db_layout.addWidget(self.combo_db_type)
        
        db_help_btn = create_questions_button("""CellChat数据库说明

数据库类型选择：
- human：人类细胞通讯数据库（推荐用于人类样本）
- mouse：小鼠细胞通讯数据库（推荐用于小鼠样本）

数据库类别（search参数）：
- Secreted Signaling：分泌信号通路（如细胞因子、激素等）
- ECM-Receptor：细胞外基质-受体相互作用
- Cell-Cell Contact：细胞间直接接触信号

推荐配置：
1. 人类样本 + Secreted Signaling：最常用的配置，适用于大多数研究
2. 人类样本 + ECM-Receptor：适用于研究细胞-基质相互作用
3. 人类样本 + Cell-Cell Contact：适用于研究免疫细胞间的直接接触
4. 小鼠样本：根据样本来源选择mouse数据库

注意：可通过search参数过滤特定类别的相互作用，
减少分析范围，加快运行速度。""")
        db_layout.addWidget(db_help_btn)
        
        left_layout.addLayout(db_layout)

        # 数据库类别筛选
        db_search_layout = QHBoxLayout()
        db_search_label = create_styled_label("数据库筛选", font_size=9, bold=True)
        db_search_layout.addWidget(db_search_label)
        
        self.combo_db_search = create_styled_combo_box()
        self.combo_db_search.addItems(["全部", "Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact", "Regulatory"])
        db_search_layout.addWidget(self.combo_db_search)
        
        left_layout.addLayout(db_search_layout)

        left_layout.addSpacing(10)

        # --- 均值计算方法（步骤5）---
        mean_layout = QHBoxLayout()
        mean_label = create_styled_label("均值计算方法", font_size=10, bold=True)
        mean_layout.addWidget(mean_label)
        
        self.combo_mean_method = create_styled_combo_box()
        self.combo_mean_method.addItems(["triMean", "mean", "median"])
        mean_layout.addWidget(self.combo_mean_method)
        
        mean_help_btn = create_questions_button("""均值计算方法说明

CellChat计算基因表达均值时的方法选择：

1. triMean（推荐）
   - 截断均值（trimmed mean）
   - 去除最高和最低的5%值后计算均值
   - 优点：对异常值不敏感，结果更稳健
   - 适用：大多数场景的首选方法

2. mean
   - 算术平均值
   - 直接计算所有细胞的表达均值
   - 优点：简单直观
   - 缺点：容易受极端值影响

3. median
   - 中位数
   - 取所有细胞表达值的中位数
   - 优点：最稳健，不受异常值影响
   - 缺点：可能丢失部分信息

推荐：使用triMean作为默认方法，
它在稳定性和信息保留之间取得平衡。""")
        mean_layout.addWidget(mean_help_btn)
        
        left_layout.addLayout(mean_layout)

        left_layout.addSpacing(8)

        # 最少细胞数过滤（步骤5）
        min_cells_layout = QHBoxLayout()
        min_cells_label = create_styled_label("最少细胞数", font_size=10, bold=True)
        min_cells_layout.addWidget(min_cells_label)
        
        self.input_min_cells = create_styled_line_edit()
        self.input_min_cells.setText("10")
        self.input_min_cells.setFixedWidth(60)
        min_cells_layout.addWidget(self.input_min_cells)
        
        min_cells_help_btn = create_questions_button("""最少细胞数过滤说明

min.cells参数用于过滤掉细胞数过少的细胞类型间通讯：

推荐值：
- 10（默认）：适用于大多数数据集
- 5：如果细胞类型较小，可以降低阈值
- 20：如果数据集较大，可以提高阈值以获得更可靠的结果

说明：
- 该参数会过滤掉参与通讯的细胞数量少于min.cells的细胞类型对
- 值越小，保留的通讯越多，但可能包含假阳性
- 值越大，结果越可靠，但可能遗漏真实的低频率通讯""")
        min_cells_layout.addWidget(min_cells_help_btn)
        
        left_layout.addLayout(min_cells_layout)

        left_layout.addSpacing(10)

        # 原始数据选项
        raw_use_layout = QHBoxLayout()
        self.check_raw_use = create_styled_checkbox("使用原始数据")
        self.check_raw_use.setChecked(True)
        raw_use_layout.addWidget(self.check_raw_use)
        
        raw_help_btn = create_questions_button("""原始数据使用说明

raw.use参数控制CellChat计算时使用的数据类型：

- TRUE（推荐）：使用原始counts数据
  优点：更准确地反映基因表达水平
  适用于大多数场景

- FALSE：使用标准化后的数据
  优点：可能更稳定
  缺点：可能丢失部分信息

推荐：保持TRUE，使用原始counts数据进行计算。""")
        raw_use_layout.addWidget(raw_help_btn)
        
        left_layout.addLayout(raw_use_layout)

        left_layout.addSpacing(15)

        # 阶段三运行按钮
        self.btn_run_stage3 = create_styled_button("▶ 执行CellChat分析", font_size=12, button_type='run')
        self.btn_run_stage3.setEnabled(False)
        left_layout.addWidget(self.btn_run_stage3)

        left_layout.addSpacing(15)

        # ========== 阶段四：细分亚组分析 ==========
        stage4_title = create_styled_label("阶段四：细分亚组通讯图", font_size=14, bold=True)
        left_layout.addWidget(stage4_title)

        stage4_note = create_styled_label("选择细胞亚组生成细分circle图", font_size=10, bold=False)
        stage4_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage4_note)

        left_layout.addSpacing(10)

        # 亚组选择（多选，默认全选）
        subgroup_label = create_styled_label("细胞亚组选择", font_size=10, bold=True)
        left_layout.addWidget(subgroup_label)
        
        self.list_subgroups = create_styled_list_widget(fixed_height=80, multi_selection=True)
        left_layout.addWidget(self.list_subgroups)

        left_layout.addSpacing(8)
        
        # 全选/取消全选按钮
        subgroup_btn_layout = QHBoxLayout()
        self.btn_select_all_subgroups = create_styled_button("全选", font_size=9, button_type='normal')
        self.btn_deselect_all_subgroups = create_styled_button("取消全选", font_size=9, button_type='normal')
        subgroup_btn_layout.addWidget(self.btn_select_all_subgroups)
        subgroup_btn_layout.addWidget(self.btn_deselect_all_subgroups)
        subgroup_btn_layout.addStretch()
        left_layout.addLayout(subgroup_btn_layout)

        left_layout.addSpacing(10)

        # 阶段四运行按钮
        self.btn_run_stage4 = create_styled_button("▶ 生成亚组circle图", font_size=12, button_type='run')
        self.btn_run_stage4.setEnabled(False)
        left_layout.addWidget(self.btn_run_stage4)

        left_layout.addSpacing(15)

        # ========== 阶段五：信号通路可视化 ==========
        stage5_title = create_styled_label("阶段五：信号通路可视化", font_size=14, bold=True)
        left_layout.addWidget(stage5_title)

        stage5_note = create_styled_label("选择信号通路并生成多种可视化图", font_size=10, bold=False)
        stage5_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage5_note)

        left_layout.addSpacing(8)

        # 模式选择（使用QButtonGroup实现互斥）
        mode_label = create_styled_label("选择模式", font_size=10, bold=True)
        left_layout.addWidget(mode_label)
        
        mode_layout = QHBoxLayout()
        self.radio_auto_mode = create_styled_checkbox("自动模式")
        self.radio_auto_mode.setChecked(True)
        self.radio_manual_mode = create_styled_checkbox("手动模式")
        
        # 使用QButtonGroup确保互斥
        self.mode_button_group = QButtonGroup()
        self.mode_button_group.setExclusive(True)
        self.mode_button_group.addButton(self.radio_auto_mode, 0)
        self.mode_button_group.addButton(self.radio_manual_mode, 1)
        
        mode_layout.addWidget(self.radio_auto_mode)
        mode_layout.addWidget(self.radio_manual_mode)
        mode_layout.addStretch()
        left_layout.addLayout(mode_layout)

        left_layout.addSpacing(8)

        # 自动模式参数
        auto_params_layout = QVBoxLayout()
        auto_params_label = create_styled_label("自动模式参数", font_size=9, bold=True)
        auto_params_layout.addWidget(auto_params_label)
        
        # p值阈值
        pval_layout = QHBoxLayout()
        pval_label = create_styled_label("p值阈值:", font_size=9, bold=False)
        pval_layout.addWidget(pval_label)
        self.input_pval_threshold = create_styled_line_edit()
        self.input_pval_threshold.setText("0.05")
        self.input_pval_threshold.setFixedWidth(60)
        pval_layout.addWidget(self.input_pval_threshold)
        pval_layout.addStretch()
        auto_params_layout.addLayout(pval_layout)
        
        # 选择数量
        count_layout = QHBoxLayout()
        count_label = create_styled_label("选择数量:", font_size=9, bold=False)
        count_layout.addWidget(count_label)
        self.input_pathway_count = create_styled_line_edit()
        self.input_pathway_count.setText("5")
        self.input_pathway_count.setFixedWidth(60)
        count_layout.addWidget(self.input_pathway_count)
        count_layout.addStretch()
        auto_params_layout.addLayout(count_layout)
        
        left_layout.addLayout(auto_params_layout)

        left_layout.addSpacing(8)

        # 手动模式参数
        manual_label = create_styled_label("手动模式", font_size=9, bold=True)
        left_layout.addWidget(manual_label)
        
        # 搜索框
        search_layout = QHBoxLayout()
        self.input_pathway_search = create_styled_line_edit()
        self.input_pathway_search.setPlaceholderText("搜索通路名称...")
        search_layout.addWidget(self.input_pathway_search)
        left_layout.addLayout(search_layout)
        
        # 通路列表（多选）
        self.list_pathways = create_styled_list_widget(fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.list_pathways)

        left_layout.addSpacing(8)

        # 可视化类型选择
        viz_label = create_styled_label("可视化类型", font_size=10, bold=True)
        left_layout.addWidget(viz_label)
        
        viz_layout = QGridLayout()
        self.check_hierarchy = create_styled_checkbox("层次结构图")
        self.check_hierarchy.setChecked(True)
        self.check_circle = create_styled_checkbox("circle图")
        self.check_circle.setChecked(True)
        self.check_chord = create_styled_checkbox("弦图")
        self.check_heatmap = create_styled_checkbox("热图")
        self.check_heatmap.setChecked(True)
        
        viz_layout.addWidget(self.check_hierarchy, 0, 0)
        viz_layout.addWidget(self.check_circle, 0, 1)
        viz_layout.addWidget(self.check_chord, 1, 0)
        viz_layout.addWidget(self.check_heatmap, 1, 1)
        left_layout.addLayout(viz_layout)

        left_layout.addSpacing(8)

        # 分组设置
        group_label = create_styled_label("细胞类型分组（用于分组弦图）", font_size=10, bold=True)
        left_layout.addWidget(group_label)
        
        self.list_celltype_groups = create_styled_list_widget(fixed_height=60, multi_selection=False)
        left_layout.addWidget(self.list_celltype_groups)
        
        group_btn_layout = QHBoxLayout()
        self.btn_config_groups = create_styled_button("配置分组", font_size=9, button_type='normal')
        group_btn_layout.addWidget(self.btn_config_groups)
        group_btn_layout.addStretch()
        left_layout.addLayout(group_btn_layout)

        left_layout.addSpacing(10)

        # 阶段五运行按钮
        self.btn_run_stage5 = create_styled_button("▶ 生成通路可视化图", font_size=12, button_type='run')
        self.btn_run_stage5.setEnabled(False)
        left_layout.addWidget(self.btn_run_stage5)

        left_layout.addStretch()
        
        # 设置滚动区域
        left_scroll.setWidget(left_content)
        left_panel_layout.addWidget(left_scroll)
        main_layout.addWidget(left_panel, 1)
        
        # ========== 中间导出选项框 ==========
        middle_panel, middle_panel_layout = create_styled_panel(parent=self.sc_cellchat_primary_page)
        middle_panel.setFixedWidth(150)
        
        export_title = create_styled_label("导出选项", font_size=14, bold=True)
        middle_panel_layout.addWidget(export_title)

        # 导出CellChat RDS
        self.btn_export_rds = create_styled_button("导出CellChat RDS", font_size=11, button_type='export')
        self.btn_export_rds.setEnabled(False)
        middle_panel_layout.addWidget(self.btn_export_rds)
        
        # 导出通路信息表
        self.btn_export_pathway_info = create_styled_button("导出通路信息表", font_size=11, button_type='export')
        self.btn_export_pathway_info.setEnabled(False)
        middle_panel_layout.addWidget(self.btn_export_pathway_info)

        middle_panel_layout.addStretch()
        main_layout.addWidget(middle_panel)

        # ========== 右侧标签页区域 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.primary_tabs = create_styled_tab_widget()

        # 数据集原始UMAP标签页
        _, self.stage1_image_label = create_styled_image_tab(
            self.primary_tabs,
            "数据集原始UMAP",
            default_text="请加载RDS文件并选择注释列后生成UMAP图"
        )

        # 筛选后UMAP标签页
        _, self.stage2_image_label = create_styled_image_tab(
            self.primary_tabs,
            "筛选UMAP图",
            default_text="请执行筛选后生成筛选UMAP图"
        )

        # 阶段三标签页1：Number of interactions
        _, self.stage3_count_image_label = create_styled_image_tab(
            self.primary_tabs,
            "通讯数量图",
            default_text="请执行CellChat分析后生成通讯数量图\n(Number of interactions)"
        )

        # 阶段三标签页2：Interaction weights/strength
        _, self.stage3_weight_image_label = create_styled_image_tab(
            self.primary_tabs,
            "通讯强度图",
            default_text="请执行CellChat分析后生成通讯强度图\n(Interaction weights/strength)"
        )
        
        # 阶段三后：通路信息表格
        self.pathway_info_tab = QWidget()
        pathway_info_layout = QVBoxLayout(self.pathway_info_tab)
        pathway_info_label = create_styled_label("通路信息表格", font_size=12, bold=True)
        pathway_info_layout.addWidget(pathway_info_label)
        
        self.table_pathway_info = QTableWidget()
        self.table_pathway_info.setStyleSheet("""
            QTableWidget {
                gridline-color: #1E3A5F;
                background-color: rgba(30, 58, 95, 0.2);
                color: #87CEEB;
                border: 1px solid #1E3A5F;
            }
            QHeaderView::section {
                background-color: rgba(30, 58, 95, 0.5);
                color: #87CEEB;
                padding: 4px;
                border: 1px solid #1E3A5F;
            }
        """)
        self.table_pathway_info.setColumnCount(3)
        self.table_pathway_info.setHorizontalHeaderLabels(["通路", "p值", "通信强度"])
        self.table_pathway_info.horizontalHeader().setStretchLastSection(True)
        pathway_info_layout.addWidget(self.table_pathway_info)
        
        self.primary_tabs.addTab(self.pathway_info_tab, "通路信息表")

        # 阶段四标签页：细分亚组circle图
        _, self.stage4_subgroup_image_label = create_styled_image_tab(
            self.primary_tabs,
            "亚组circle图",
            default_text="请执行CellChat分析后选择亚组生成细分circle图"
        )

        # 阶段五标签页：层次结构图
        _, self.stage5_hierarchy_image_label = create_styled_image_tab(
            self.primary_tabs,
            "层次结构图",
            default_text="请执行CellChat分析后选择通路生成层次结构图"
        )

        # 阶段五标签页：circle图（通路水平）
        _, self.stage5_circle_image_label = create_styled_image_tab(
            self.primary_tabs,
            "通路circle图",
            default_text="请执行CellChat分析后选择通路生成circle图"
        )

        # 阶段五标签页：弦图
        _, self.stage5_chord_image_label = create_styled_image_tab(
            self.primary_tabs,
            "通路弦图",
            default_text="请执行CellChat分析后选择通路生成弦图"
        )

        # 阶段五标签页：热图
        _, self.stage5_heatmap_image_label = create_styled_image_tab(
            self.primary_tabs,
            "通路热图",
            default_text="请执行CellChat分析后选择通路生成热图"
        )

        right_layout.addWidget(self.primary_tabs)
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.sc_cellchat_primary_page
