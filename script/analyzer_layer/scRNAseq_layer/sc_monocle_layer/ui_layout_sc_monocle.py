# -*- coding: utf-8 -*-
"""
scRNAseq Monocle分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_text_edit, create_styled_tab_widget, create_styled_image_tab,
    create_styled_web_tab, create_zoomable_image_label, create_styled_checkbox,
    create_questions_button
)
from script.mods_layer.mod_manager import global_mod_manager

class ScMonoclePageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_monocle_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.sc_monocle_page.findChild(QLabel, "sc_monocle_bg")
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

        title_label = self.sc_monocle_page.findChild(QLabel, "sc_monocle_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.sc_monocle_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_stage1'):
            self.btn_stage1.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_export_png'):
            self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'btn_export_pdf'):
            self.btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.sc_monocle_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.sc_monocle_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.sc_monocle_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_monocle_page.findChildren(QLabel):
            if child.objectName() != "sc_monocle_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_monocle_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.sc_monocle_page.findChild(QWidget, "sc_monocle_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    def create_page(self):
        self.sc_monocle_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.sc_monocle_page)
        bg_label.setObjectName("sc_monocle_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.sc_monocle_page)
        overlay.setObjectName("sc_monocle_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_sc_monocle = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_sc_monocle)

        title_label = QLabel("Monocle拟时序轨迹分析")
        title_label.setObjectName("sc_monocle_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.sc_monocle_page, mod_instance)

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

        self.monocle_log = create_styled_text_edit(read_only=True, variant='sub')
        self.monocle_log.setMaximumHeight(80)
        layout.addWidget(self.monocle_log)

        main_layout = QHBoxLayout()

        left_panel, left_panel_layout = create_styled_panel(parent=self.sc_monocle_page)
        left_panel.setMinimumWidth(340)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 0, 0)

        stage1_title = create_styled_label("阶段一：数据集加载与UMAP出图", font_size=14, bold=True)
        left_layout.addWidget(stage1_title)

        left_layout.addSpacing(8)

        stage1_note = create_styled_label("加载Seurat对象并按注释生成UMAP图", font_size=10, bold=False)
        stage1_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage1_note)

        left_layout.addSpacing(10)

        annotation_label = create_styled_label("注释列选择", font_size=10, bold=True)
        left_layout.addWidget(annotation_label)

        self.combo_annotation = create_styled_combo_box()
        self.combo_annotation.addItem("选择注释列")
        left_layout.addWidget(self.combo_annotation)

        left_layout.addSpacing(15)

        self.btn_stage1 = create_styled_button("▶ 按注释出图", font_size=12, button_type='run')
        left_layout.addWidget(self.btn_stage1)

        left_layout.addSpacing(20)

        left_layout.addWidget(create_styled_label("━" * 20, font_size=10))

        left_layout.addSpacing(10)

        stage2_title = create_styled_label("阶段二：细胞筛选与重新降维", font_size=14, bold=True)
        left_layout.addWidget(stage2_title)

        stage2_note = create_styled_label("筛选细胞群并可选重新降维", font_size=10, bold=False)
        stage2_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage2_note)

        left_layout.addSpacing(10)

        main_annot_label = create_styled_label("主注释列", font_size=10, bold=True)
        left_layout.addWidget(main_annot_label)
        self.combo_main_annot = create_styled_combo_box()
        self.combo_main_annot.addItem("选择注释列")
        left_layout.addWidget(self.combo_main_annot)

        main_group_label = create_styled_label("主注释分组（多选）", font_size=9, bold=True)
        left_layout.addWidget(main_group_label)
        self.list_main_groups = create_styled_list_widget(fixed_height=60, multi_selection=True)
        left_layout.addWidget(self.list_main_groups)

        left_layout.addSpacing(8)

        filter1_label = create_styled_label("筛选条件1", font_size=10, bold=True)
        left_layout.addWidget(filter1_label)
        self.combo_filter1 = create_styled_combo_box()
        self.combo_filter1.addItem("不筛选")
        left_layout.addWidget(self.combo_filter1)
        self.list_filter1 = create_styled_list_widget(fixed_height=40, multi_selection=True)
        left_layout.addWidget(self.list_filter1)

        left_layout.addSpacing(8)

        filter2_label = create_styled_label("筛选条件2", font_size=10, bold=True)
        left_layout.addWidget(filter2_label)
        self.combo_filter2 = create_styled_combo_box()
        self.combo_filter2.addItem("不筛选")
        left_layout.addWidget(self.combo_filter2)
        self.list_filter2 = create_styled_list_widget(fixed_height=40, multi_selection=True)
        left_layout.addWidget(self.list_filter2)

        left_layout.addSpacing(10)

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

        plot_annot_label = create_styled_label("筛选后出图注释", font_size=10, bold=True)
        left_layout.addWidget(plot_annot_label)
        self.combo_plot_annot = create_styled_combo_box()
        self.combo_plot_annot.addItem("选择注释列")
        left_layout.addWidget(self.combo_plot_annot)

        left_layout.addSpacing(15)

        self.btn_stage2 = create_styled_button("▶ 执行筛选", font_size=12, button_type='run')
        left_layout.addWidget(self.btn_stage2)

        left_layout.addSpacing(20)

        left_layout.addWidget(create_styled_label("━" * 20, font_size=10))

        left_layout.addSpacing(10)

        stage3_title = create_styled_label("阶段三：CDS创建与降维", font_size=14, bold=True)
        left_layout.addWidget(stage3_title)

        stage3_note = create_styled_label("创建CDS对象并进行数据预处理和降维", font_size=10, bold=False)
        stage3_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage3_note)

        left_layout.addSpacing(10)

        num_dim_layout = QHBoxLayout()
        num_dim_label = create_styled_label("num_dim:", font_size=10, bold=True)
        num_dim_layout.addWidget(num_dim_label)
        self.input_num_dim = create_styled_line_edit()
        self.input_num_dim.setText("50")
        self.input_num_dim.setFixedWidth(60)
        num_dim_layout.addWidget(self.input_num_dim)
        num_dim_help_btn = create_questions_button("""num_dim值说明

num_dim用于指定PCA降维时保留的主成分数量。

推荐值：
- 一般数据集：30-50
- 复杂数据集（细胞类型多）：50-100
- 简单数据集（细胞类型少）：20-30

选择原则：
1. 查看PCA累计方差贡献率
2. 通常选择解释80%-90%方差的PC数量
3. 值太小可能丢失重要信息
4. 值太大可能引入噪声""")
        num_dim_layout.addWidget(num_dim_help_btn)
        left_layout.addLayout(num_dim_layout)

        left_layout.addSpacing(8)

        alignment_label = create_styled_label("批次校正列", font_size=10, bold=True)
        left_layout.addWidget(alignment_label)
        self.combo_alignment = create_styled_combo_box()
        self.combo_alignment.addItem("不校正")
        left_layout.addWidget(self.combo_alignment)

        left_layout.addSpacing(8)

        traj_annot_label = create_styled_label("轨迹图注释", font_size=10, bold=True)
        left_layout.addWidget(traj_annot_label)
        self.combo_traj_annot = create_styled_combo_box()
        self.combo_traj_annot.addItem("选择注释列")
        left_layout.addWidget(self.combo_traj_annot)

        left_layout.addSpacing(8)

        coord_layout = QHBoxLayout()
        coord_label = create_styled_label("降维坐标模式:", font_size=10, bold=True)
        coord_layout.addWidget(coord_label)
        self.combo_coord_mode = create_styled_combo_box()
        self.combo_coord_mode.addItems(["UMAP", "CDS"])
        self.combo_coord_mode.setCurrentIndex(0)
        coord_layout.addWidget(self.combo_coord_mode)
        coord_help_btn = create_questions_button("""降维坐标模式说明

UMAP坐标（推荐）：
- 使用Seurat对象的UMAP降维结果
- 与前面阶段的图坐标一致
- 便于比较不同阶段的结果

CDS坐标：
- 使用Monocle3 CDS对象的降维结果
- 可能与UMAP坐标不同
- 适合查看Monocle3特有降维效果

建议：
- 通常选择UMAP坐标，保持图的一致性
- 如果需要查看Monocle3特有效果，选择CDS坐标""")
        coord_layout.addWidget(coord_help_btn)
        left_layout.addLayout(coord_layout)

        left_layout.addSpacing(15)

        self.btn_stage3 = create_styled_button("▶ 创建CDS", font_size=12, button_type='run')
        left_layout.addWidget(self.btn_stage3)

        left_layout.addSpacing(20)

        left_layout.addWidget(create_styled_label("━" * 20, font_size=10))

        left_layout.addSpacing(10)

        stage4_title = create_styled_label("阶段四：伪时间分析", font_size=14, bold=True)
        left_layout.addWidget(stage4_title)

        stage4_note = create_styled_label("选择根节点并计算伪时间", font_size=10, bold=False)
        stage4_note.setStyleSheet(f"color: {styles.get('sub_text_color', '#87CEEB')}; opacity: 0.7;")
        left_layout.addWidget(stage4_note)

        left_layout.addSpacing(10)

        node_mode_layout = QHBoxLayout()
        node_mode_label = create_styled_label("节点选择模式:", font_size=10, bold=True)
        node_mode_layout.addWidget(node_mode_label)
        self.combo_node_mode = create_styled_combo_box()
        self.combo_node_mode.addItems(["auto", "manual"])
        self.combo_node_mode.setCurrentIndex(0)
        node_mode_layout.addWidget(self.combo_node_mode)
        node_mode_help_btn = create_questions_button("""节点选择模式说明

自动模式（推荐）：
- 自动选择轨迹图中度数最高的节点作为根节点
- 适合大多数情况
- 无需人工干预

手动模式：
- 启动Shiny网页让用户手动选择根节点
- 适合需要精确定义发育起点的情况
- 需要在浏览器中点击选择后关闭继续""")
        node_mode_layout.addWidget(node_mode_help_btn)
        left_layout.addLayout(node_mode_layout)

        left_layout.addSpacing(15)

        self.btn_stage4 = create_styled_button("▶ 计算伪时间", font_size=12, button_type='run')
        left_layout.addWidget(self.btn_stage4)

        left_layout.addStretch()
        
        left_scroll.setWidget(left_content)
        left_panel_layout.addWidget(left_scroll)
        main_layout.addWidget(left_panel, 1)

        center_panel, center_layout = create_styled_panel(fixed_width=200)

        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        center_layout.addWidget(export_title)

        center_layout.addSpacing(8)

        self.btn_export_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        center_layout.addWidget(self.btn_export_png)

        self.btn_export_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        center_layout.addWidget(self.btn_export_pdf)

        center_layout.addSpacing(15)

        data_info_title = create_styled_label("数据信息", font_size=12, bold=True)
        center_layout.addWidget(data_info_title)

        self.data_info_text = create_styled_text_edit(read_only=True)
        self.data_info_text.setMaximumHeight(150)
        center_layout.addWidget(self.data_info_text)

        center_layout.addStretch()
        main_layout.addWidget(center_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.monocle_plot_tabs = create_styled_tab_widget()

        _, self.stage1_plot_label = create_styled_image_tab(self.monocle_plot_tabs, "数据集原始UMAP")

        _, self.stage2_plot_label = create_styled_image_tab(self.monocle_plot_tabs, "筛选UMAP图")

        _, self.stage3_traj_label = create_styled_image_tab(self.monocle_plot_tabs, "轨迹图")

        _, self.stage3_partition_label = create_styled_image_tab(self.monocle_plot_tabs, "分区图")

        _, self.stage4_web_view = create_styled_web_tab(self.monocle_plot_tabs, "节点选择(Shiny)")

        _, self.stage4_pseudotime_label = create_styled_image_tab(self.monocle_plot_tabs, "伪时间图")

        right_layout.addWidget(self.monocle_plot_tabs)
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.sc_monocle_page
