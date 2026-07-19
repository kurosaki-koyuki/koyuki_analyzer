# -*- coding: utf-8 -*-
"""
bulk KM曲线 R模式界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
继承bulk_km_layer的样式模板，控件命名与原KM界面保持一致
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_checkbox, create_styled_spinbox, create_styled_text_edit,
    create_styled_tab_widget, create_styled_image_tab
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class BulkKmRPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        """更新背景图（子页面不处理，由主容器处理）"""
        pass

    def update_styles(self):
        """更新所有控件的样式（不修改控件尺寸）"""
        styles = get_mod_styles()

        title_label = self.bulk_km_r_page.findChild(QLabel, "bulk_km_r_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_km_r_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'bulk_km_btn_plot'):
            self.bulk_km_btn_plot.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'bulk_km_btn_export_png'):
            self.bulk_km_btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_km_btn_export_pdf'):
            self.bulk_km_btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_km_btn_export_svg'):
            self.bulk_km_btn_export_svg.setStyleSheet(get_stylesheet_for_widget('export_button'))
        if hasattr(self, 'bulk_km_btn_export_csv'):
            self.bulk_km_btn_export_csv.setStyleSheet(get_stylesheet_for_widget('export_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_km_r_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_km_r_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_km_r_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_km_r_page.findChildren(QLabel):
            if child.objectName() != "bulk_km_r_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_km_r_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_km_r_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        if hasattr(self, 'r_version_label'):
            self.r_version_label.setStyleSheet(label_style)

    def create_page(self):
        self.bulk_km_r_page = QWidget(self.parent)
        self.bulk_km_r_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()
        mod_instance = global_mod_manager.get_current_mod()

        layout = QVBoxLayout(self.bulk_km_r_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # 顶部标题栏
        top_layout = QHBoxLayout()

        self.btn_back = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back)

        title_label = QLabel("bulk KM曲线 (R版本)")
        title_label.setObjectName("bulk_km_r_title")
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

        # 状态区域
        status_layout = QHBoxLayout()
        self.bulk_km_status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.bulk_km_status_text.setMaximumHeight(80)
        status_layout.addWidget(self.bulk_km_status_text)
        layout.addLayout(status_layout)

        # 主内容区域
        main_layout = QHBoxLayout()

        # 左侧控制面板
        left_panel, left_layout = create_styled_panel(fixed_width=320)

        # Debug区域
        debug_frame = QFrame()
        debug_frame.setObjectName("styled_panel_debug")
        debug_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        debug_layout = QVBoxLayout(debug_frame)
        debug_layout.setContentsMargins(5, 5, 5, 5)

        debug_title = create_styled_label("Debug区域", font_size=11, bold=True)
        debug_layout.addWidget(debug_title)

        self.bulk_km_debug_btn = create_styled_button("检测环境对应", font_size=10)
        debug_layout.addWidget(self.bulk_km_debug_btn)

        left_layout.addWidget(debug_frame)

        left_layout.addSpacing(8)

        # 基因输入
        gene_label = create_styled_label("基因名称", font_size=12, bold=True)
        left_layout.addWidget(gene_label)

        self.bulk_km_gene_input = create_styled_line_edit()
        left_layout.addWidget(self.bulk_km_gene_input)

        # 分类选择下拉框
        clinical_label = create_styled_label("分类列选择", font_size=12, bold=True)
        left_layout.addWidget(clinical_label)

        self.bulk_km_clinical_combo = create_styled_combo_box()
        self.bulk_km_clinical_combo.addItem("全部")
        left_layout.addWidget(self.bulk_km_clinical_combo)

        # 分类列多选列表
        self.bulk_km_clinical_col_list_label = create_styled_label("分类列（可多选）", font_size=11, bold=False)
        self.bulk_km_clinical_col_list_label.hide()
        left_layout.addWidget(self.bulk_km_clinical_col_list_label)

        self.bulk_km_clinical_col_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_km_clinical_col_list.hide()
        left_layout.addWidget(self.bulk_km_clinical_col_list)

        # 组别多选列表
        self.bulk_km_group_list_label = create_styled_label("组别（可多选）", font_size=11, bold=False)
        self.bulk_km_group_list_label.hide()
        left_layout.addWidget(self.bulk_km_group_list_label)

        self.bulk_km_group_list = create_styled_list_widget(fixed_height=100, multi_selection=True)
        self.bulk_km_group_list.hide()
        left_layout.addWidget(self.bulk_km_group_list)

        # 筛选1框架
        filter1_frame = QFrame()
        filter1_frame.setObjectName("styled_panel_filter1")
        filter1_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter1_layout = QVBoxLayout(filter1_frame)

        filter1_header = QHBoxLayout()
        self.bulk_km_filter1_enable = create_styled_checkbox("启用筛选1")
        filter1_header.addWidget(self.bulk_km_filter1_enable)
        filter1_layout.addLayout(filter1_header)

        filter1_col_label = create_styled_label("筛选分类列1", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_col_label)

        self.bulk_km_filter1_combo = create_styled_combo_box()
        self.bulk_km_filter1_combo.setEnabled(False)
        filter1_layout.addWidget(self.bulk_km_filter1_combo)

        filter1_group_label = create_styled_label("筛选组别1（可多选）", font_size=11, bold=False)
        filter1_layout.addWidget(filter1_group_label)

        self.bulk_km_filter1_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_km_filter1_list.setEnabled(False)
        filter1_layout.addWidget(self.bulk_km_filter1_list)

        left_layout.addWidget(filter1_frame)

        # 筛选2框架
        filter2_frame = QFrame()
        filter2_frame.setObjectName("styled_panel_filter2")
        filter2_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px;")
        filter2_layout = QVBoxLayout(filter2_frame)

        filter2_header = QHBoxLayout()
        self.bulk_km_filter2_enable = create_styled_checkbox("启用筛选2")
        filter2_header.addWidget(self.bulk_km_filter2_enable)
        filter2_layout.addLayout(filter2_header)

        filter2_col_label = create_styled_label("筛选分类列2", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_col_label)

        self.bulk_km_filter2_combo = create_styled_combo_box()
        self.bulk_km_filter2_combo.setEnabled(False)
        filter2_layout.addWidget(self.bulk_km_filter2_combo)

        filter2_group_label = create_styled_label("筛选组别2（可多选）", font_size=11, bold=False)
        filter2_layout.addWidget(filter2_group_label)

        self.bulk_km_filter2_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_km_filter2_list.setEnabled(False)
        filter2_layout.addWidget(self.bulk_km_filter2_list)

        left_layout.addWidget(filter2_frame)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # 中间参数调整面板
        center_panel, center_layout = create_styled_panel(fixed_width=280)

        # 多基因输入区域
        multi_gene_frame = QFrame()
        multi_gene_frame.setObjectName("styled_panel_multigene")
        multi_gene_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        multi_gene_layout = QVBoxLayout(multi_gene_frame)
        multi_gene_layout.setContentsMargins(5, 5, 5, 5)

        multi_gene_label = create_styled_label("多基因测定（每列一个基因）", font_size=11, bold=True)
        multi_gene_layout.addWidget(multi_gene_label)

        multi_gene_hint = create_styled_label("每输入一个基因请另起一行", font_size=9, bold=False)
        multi_gene_layout.addWidget(multi_gene_hint)

        self.bulk_km_multi_gene_input = create_styled_text_edit(variant='sub')
        self.bulk_km_multi_gene_input.setMaximumHeight(60)
        multi_gene_layout.addWidget(self.bulk_km_multi_gene_input)

        center_layout.addWidget(multi_gene_frame)
        center_layout.addSpacing(8)

        param_title = create_styled_label("参数调整", font_size=14, bold=True)
        center_layout.addWidget(param_title)

        # 标题名称
        title_name_layout = QHBoxLayout()
        title_name_label = create_styled_label("标题名称", font_size=10, bold=False)
        title_name_layout.addWidget(title_name_label)
        self.bulk_km_title_input = create_styled_line_edit(fixed_width=160)
        title_name_layout.addWidget(self.bulk_km_title_input)
        center_layout.addLayout(title_name_layout)
        center_layout.addSpacing(5)

        # 标题字体大小
        title_size_layout = QHBoxLayout()
        title_size_label = create_styled_label("标题字体大小", font_size=10, bold=False)
        title_size_layout.addWidget(title_size_label)
        self.bulk_km_titlesize_input = create_styled_line_edit(fixed_width=160)
        self.bulk_km_titlesize_input.setText("18")
        title_size_layout.addWidget(self.bulk_km_titlesize_input)
        center_layout.addLayout(title_size_layout)
        center_layout.addSpacing(5)

        # 显示风险表格
        self.bulk_km_show_table_check = create_styled_checkbox("显示风险表格")
        self.bulk_km_show_table_check.setChecked(True)
        center_layout.addWidget(self.bulk_km_show_table_check)

        # 出图尺寸
        plot_size_layout = QHBoxLayout()
        plot_size_label = create_styled_label("出图尺寸", font_size=10, bold=False)
        plot_size_layout.addWidget(plot_size_label)
        self.bulk_km_plot_width_input = create_styled_line_edit(fixed_width=60)
        self.bulk_km_plot_width_input.setText("6")
        plot_size_layout.addWidget(self.bulk_km_plot_width_input)
        plot_size_layout.addWidget(create_styled_label("×", font_size=10))
        self.bulk_km_plot_height_input = create_styled_line_edit(fixed_width=60)
        self.bulk_km_plot_height_input.setText("8")
        plot_size_layout.addWidget(self.bulk_km_plot_height_input)
        center_layout.addLayout(plot_size_layout)

        # 添加置信区间
        self.bulk_km_show_ci_check = create_styled_checkbox("添加置信区间")
        self.bulk_km_show_ci_check.setChecked(True)
        center_layout.addWidget(self.bulk_km_show_ci_check)

        # 显示n值
        self.bulk_km_show_n_check = create_styled_checkbox("显示n值")
        self.bulk_km_show_n_check.setChecked(True)
        center_layout.addWidget(self.bulk_km_show_n_check)

        center_layout.addSpacing(5)

        # 表格字体大小
        table_size_layout = QHBoxLayout()
        table_size_label = create_styled_label("表格字体大小", font_size=10, bold=False)
        table_size_layout.addWidget(table_size_label)
        self.bulk_km_tablesize_input = create_styled_line_edit(fixed_width=160)
        self.bulk_km_tablesize_input.setText("10")
        table_size_layout.addWidget(self.bulk_km_tablesize_input)
        center_layout.addLayout(table_size_layout)
        center_layout.addSpacing(5)

        # 注释字体大小
        legend_size_layout = QHBoxLayout()
        legend_size_label = create_styled_label("注释字体大小", font_size=10, bold=False)
        legend_size_layout.addWidget(legend_size_label)
        self.bulk_km_legendsize_input = create_styled_line_edit(fixed_width=160)
        self.bulk_km_legendsize_input.setText("12")
        legend_size_layout.addWidget(self.bulk_km_legendsize_input)
        center_layout.addLayout(legend_size_layout)
        center_layout.addSpacing(5)

        # 坐标轴字体大小
        axis_size_layout = QHBoxLayout()
        axis_size_label = create_styled_label("坐标字体大小", font_size=10, bold=False)
        axis_size_layout.addWidget(axis_size_label)
        self.bulk_km_axissize_input = create_styled_line_edit(fixed_width=160)
        self.bulk_km_axissize_input.setText("16")
        axis_size_layout.addWidget(self.bulk_km_axissize_input)
        center_layout.addLayout(axis_size_layout)
        center_layout.addSpacing(5)

        # 显著性字体大小
        pval_size_layout = QHBoxLayout()
        pval_size_label = create_styled_label("显著性字体大小", font_size=10, bold=False)
        pval_size_layout.addWidget(pval_size_label)
        self.bulk_km_pvalsize_input = create_styled_line_edit(fixed_width=160)
        self.bulk_km_pvalsize_input.setText("14")
        pval_size_layout.addWidget(self.bulk_km_pvalsize_input)
        center_layout.addLayout(pval_size_layout)
        center_layout.addSpacing(5)

        # p值显示模式
        pval_mode_layout = QHBoxLayout()
        pval_mode_label = create_styled_label("p值显示", font_size=10, bold=False)
        pval_mode_layout.addWidget(pval_mode_label)
        self.bulk_km_pval_mode_combo = create_styled_combo_box()
        self.bulk_km_pval_mode_combo.addItems(['具体值', '模糊值', '模糊值+具体值'])
        self.bulk_km_pval_mode_combo.setCurrentIndex(0)
        pval_mode_layout.addWidget(self.bulk_km_pval_mode_combo)
        center_layout.addLayout(pval_mode_layout)

        center_layout.addSpacing(5)

        # 时间单位
        time_unit_layout = QHBoxLayout()
        time_unit_label = create_styled_label("时间单位", font_size=10, bold=False)
        time_unit_layout.addWidget(time_unit_label)
        self.bulk_km_time_unit_combo = create_styled_combo_box()
        self.bulk_km_time_unit_combo.addItems(['days', 'month'])
        self.bulk_km_time_unit_combo.setCurrentIndex(1)
        time_unit_layout.addWidget(self.bulk_km_time_unit_combo)
        center_layout.addLayout(time_unit_layout)

        center_layout.addSpacing(5)

        # 显示总体p值
        self.bulk_km_show_global_check = create_styled_checkbox("显示总体p值")
        self.bulk_km_show_global_check.setChecked(True)
        center_layout.addWidget(self.bulk_km_show_global_check)

        center_layout.addSpacing(8)

        # 组间比较框架
        pairwise_frame = QFrame()
        pairwise_frame.setObjectName("styled_panel_pairwise")
        pairwise_frame.setStyleSheet(f"background: {styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')}; border: 1px solid {styles.get('sub_border_color', '#1E3A5F')}; border-radius: 5px; padding: 5px;")
        pairwise_layout = QVBoxLayout(pairwise_frame)
        pairwise_layout.setContentsMargins(5, 5, 5, 5)

        pairwise_header = QHBoxLayout()
        self.bulk_km_pairwise_enable = create_styled_checkbox("启用组间比较")
        pairwise_header.addWidget(self.bulk_km_pairwise_enable)
        pairwise_layout.addLayout(pairwise_header)

        self.bulk_km_pairwise_list = create_styled_list_widget(fixed_height=80, multi_selection=True)
        self.bulk_km_pairwise_list.setEnabled(False)
        pairwise_layout.addWidget(self.bulk_km_pairwise_list)

        pairwise_select_all_btn = create_styled_button("全选", font_size=9)
        pairwise_select_all_btn.setEnabled(False)
        pairwise_layout.addWidget(pairwise_select_all_btn)

        center_layout.addWidget(pairwise_frame)

        center_layout.addSpacing(8)

        center_layout.addStretch()
        main_layout.addWidget(center_panel)

        # 导出面板
        export_panel, export_layout = create_styled_panel(fixed_width=220)

        # 运行区域标题
        run_title = create_styled_label("运行区域", font_size=12, bold=True)
        export_layout.addWidget(run_title)

        # 生成KM曲线按钮
        self.bulk_km_btn_plot = create_styled_button("▶ 生成KM曲线", font_size=12, button_type='run')
        export_layout.addWidget(self.bulk_km_btn_plot)

        export_layout.addSpacing(10)

        # 导出选项标题
        export_title = create_styled_label("导出选项", font_size=12, bold=True)
        export_layout.addWidget(export_title)

        # 导出尺寸设置
        export_size_frame = QFrame()
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
        self.bulk_km_export_width = create_styled_line_edit(fixed_width=70)
        self.bulk_km_export_width.setText("8")
        width_row.addWidget(self.bulk_km_export_width)
        width_row.addStretch()
        export_size_layout.addLayout(width_row)

        # 高度行
        height_row = QHBoxLayout()
        height_row.addSpacing(5)
        height_label = create_styled_label("高度:", font_size=10, bold=False)
        height_row.addWidget(height_label)
        self.bulk_km_export_height = create_styled_line_edit(fixed_width=70)
        self.bulk_km_export_height.setText("6")
        height_row.addWidget(self.bulk_km_export_height)
        height_row.addStretch()
        export_size_layout.addLayout(height_row)
        export_layout.addWidget(export_size_frame)

        export_layout.addSpacing(8)

        # 导出PNG按钮
        self.bulk_km_btn_export_png = create_styled_button("导出PNG", font_size=10, button_type='export')
        export_layout.addWidget(self.bulk_km_btn_export_png)

        # 导出PDF按钮
        self.bulk_km_btn_export_pdf = create_styled_button("导出PDF", font_size=10, button_type='export')
        export_layout.addWidget(self.bulk_km_btn_export_pdf)

        # 导出SVG按钮
        self.bulk_km_btn_export_svg = create_styled_button("导出SVG", font_size=10, button_type='export')
        export_layout.addWidget(self.bulk_km_btn_export_svg)

        # 导出CSV按钮
        self.bulk_km_btn_export_csv = create_styled_button("导出CSV", font_size=10, button_type='export')
        export_layout.addWidget(self.bulk_km_btn_export_csv)

        export_layout.addStretch()
        main_layout.addWidget(export_panel)

        # 右侧图表区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.bulk_km_plot_tabs = create_styled_tab_widget()

        _, self.bulk_km_label = create_styled_image_tab(self.bulk_km_plot_tabs, "KM出图")

        right_layout.addWidget(self.bulk_km_plot_tabs)
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.bulk_km_r_page


class ScalableLabel(QLabel):
    """可缩放的标签控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap = None

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        super().setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled)
