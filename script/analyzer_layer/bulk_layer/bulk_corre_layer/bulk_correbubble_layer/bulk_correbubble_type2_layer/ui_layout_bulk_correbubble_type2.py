# -*- coding: utf-8 -*-
"""
bulk相关性气泡图界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_panel, create_styled_group_box,
    create_styled_tab_widget, create_styled_image_tab, create_styled_label,
    create_styled_line_edit, create_styled_combo_box, create_styled_text_edit,
    create_styled_checkbox, create_styled_spinbox
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class BulkCorrebubblePageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_correbubble_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_correbubble_page.findChild(QLabel, "bulk_correbubble_bg")
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

        title_label = self.bulk_correbubble_page.findChild(QLabel, "bulk_correbubble_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        overlay = self.bulk_correbubble_page.findChild(QWidget, "bulk_correbubble_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        # 更新按钮样式
        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_correbubble_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_run_correbubble'):
            self.btn_run_correbubble.setStyleSheet(get_stylesheet_for_widget('run_button'))

        # 更新输入框样式
        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.bulk_correbubble_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_correbubble_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        # 更新复选框样式
        checkbox_style = get_stylesheet_for_widget('checkbox')
        for child in self.bulk_correbubble_page.findChildren(QCheckBox):
            child.setStyleSheet(checkbox_style)

        # 更新面板样式
        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_correbubble_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        self.update_background()

    def create_page(self):
        self.bulk_correbubble_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.bulk_correbubble_page)
        bg_label.setObjectName("bulk_correbubble_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.bulk_correbubble_page)
        overlay.setObjectName("bulk_correbubble_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 顶部标题栏 ===
        top_layout = QHBoxLayout()

        self.btn_back_bulk_correbubble = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_bulk_correbubble)

        title_label = QLabel("相关性气泡图（基因）")
        title_label.setObjectName("bulk_correbubble_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.bulk_correbubble_page, mod_instance)
        
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

        # === 状态日志区域 ===
        self.correbubble_status_text = create_styled_text_edit(read_only=True, variant='sub')
        self.correbubble_status_text.setMaximumHeight(60)
        layout.addWidget(self.correbubble_status_text)

        # === 主体三列布局 ===
        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0, 10, 0, 0)

        # --- 左侧：基因输入 + 运行按钮 ---
        left_panel, left_layout = create_styled_panel()
        left_layout.setAlignment(Qt.AlignTop)
        
        # 基因集合输入区域
        gene_set_group = create_styled_group_box("基因集合")
        gene_set_layout = QVBoxLayout(gene_set_group)
        
        gene_hint = create_styled_label("每行输入一个基因名称", font_size=9, bold=False)
        gene_set_layout.addWidget(gene_hint)
        
        self.correbubble_gene_input = create_styled_text_edit(variant='sub')
        self.correbubble_gene_input.setMaximumHeight(120)
        gene_set_layout.addWidget(self.correbubble_gene_input)
        
        left_layout.addWidget(gene_set_group)
        
        # 运行按钮
        self.btn_run_correbubble = create_styled_button("运行", font_size=14, button_type='run')
        left_layout.addWidget(self.btn_run_correbubble)
        
        left_layout.addStretch()
        center_layout.addWidget(left_panel, 1)

        # --- 中间：参数设置 ---
        params_panel, params_layout = create_styled_panel()
        params_layout.setAlignment(Qt.AlignTop)
        
        params_group = create_styled_group_box("参数设置")
        params_group_layout = QVBoxLayout(params_group)
        params_group_layout.setSpacing(8)
        
        # 1. 标题名称
        row_title = QHBoxLayout()
        lbl_title = create_styled_label("标题名称", font_size=10, bold=False)
        row_title.addWidget(lbl_title)
        self.correbubble_title_input = create_styled_line_edit(fixed_width=150)
        self.correbubble_title_input.setPlaceholderText("Gene Correlation")
        row_title.addWidget(self.correbubble_title_input)
        params_group_layout.addLayout(row_title)
        
        # 2. 标题字体大小
        row_title_size = QHBoxLayout()
        lbl_title_size = create_styled_label("标题字体大小", font_size=10, bold=False)
        row_title_size.addWidget(lbl_title_size)
        self.correbubble_title_size = create_styled_spinbox(min_value=8, max_value=40, default_value=14)
        row_title_size.addWidget(self.correbubble_title_size)
        params_group_layout.addLayout(row_title_size)
        
        # 3. 基因名字体大小
        row_axis_size = QHBoxLayout()
        lbl_axis_size = create_styled_label("基因名字体大小", font_size=10, bold=False)
        row_axis_size.addWidget(lbl_axis_size)
        self.correbubble_axis_size = create_styled_spinbox(min_value=8, max_value=30, default_value=10)
        row_axis_size.addWidget(self.correbubble_axis_size)
        params_group_layout.addLayout(row_axis_size)
        
        # 4. 宽高比例设置
        ratio_group = create_styled_group_box("宽高比例设置")
        ratio_layout = QVBoxLayout(ratio_group)
        
        row_width = QHBoxLayout()
        lbl_width = create_styled_label("宽度比例", font_size=10, bold=False)
        row_width.addWidget(lbl_width)
        self.correbubble_width_ratio = create_styled_spinbox(min_value=0, max_value=100, default_value=100)
        row_width.addWidget(self.correbubble_width_ratio)
        lbl_width_unit = create_styled_label("%", font_size=10, bold=False)
        row_width.addWidget(lbl_width_unit)
        ratio_layout.addLayout(row_width)
        
        row_height = QHBoxLayout()
        lbl_height = create_styled_label("高度比例", font_size=10, bold=False)
        row_height.addWidget(lbl_height)
        self.correbubble_height_ratio = create_styled_spinbox(min_value=0, max_value=100, default_value=100)
        row_height.addWidget(self.correbubble_height_ratio)
        lbl_height_unit = create_styled_label("%", font_size=10, bold=False)
        row_height.addWidget(lbl_height_unit)
        ratio_layout.addLayout(row_height)
        
        params_group_layout.addWidget(ratio_group)
        
        # 5. 显著性是否显示
        self.correbubble_show_sig = create_styled_checkbox("显示显著性星号(*,**,***)")
        self.correbubble_show_sig.setChecked(True)
        params_group_layout.addWidget(self.correbubble_show_sig)
        
        # 6. 注释大小
        row_anno = QHBoxLayout()
        lbl_anno = create_styled_label("注释大小", font_size=10, bold=False)
        row_anno.addWidget(lbl_anno)
        self.correbubble_anno_size = create_styled_spinbox(min_value=1, max_value=20, default_value=45)
        row_anno.addWidget(self.correbubble_anno_size)
        lbl_anno_unit = create_styled_label("x", font_size=10, bold=False)
        row_anno.addWidget(lbl_anno_unit)
        params_group_layout.addLayout(row_anno)
        
        # 7. 注释条大小
        row_legend = QHBoxLayout()
        lbl_legend = create_styled_label("图例条大小", font_size=10, bold=False)
        row_legend.addWidget(lbl_legend)
        self.correbubble_legend_size = create_styled_spinbox(min_value=1, max_value=20, default_value=5)
        row_legend.addWidget(self.correbubble_legend_size)
        lbl_legend_unit = create_styled_label("x", font_size=10, bold=False)
        row_legend.addWidget(lbl_legend_unit)
        params_group_layout.addLayout(row_legend)
        
        params_group_layout.addStretch()
        params_layout.addWidget(params_group)
        
        params_layout.addStretch()
        center_layout.addWidget(params_panel, 1)

        # --- 右侧：标签页（可拖动） ---
        right_panel, right_layout = create_styled_panel()
        
        self.correbubble_plot_tabs = create_styled_tab_widget(movable=True, document_mode=True)
        
        # 使用create_styled_image_tab创建标签页（可缩放图片）
        _, self.correbubble_plot_label = create_styled_image_tab(self.correbubble_plot_tabs, "结果展示")
        
        _, self.correbubble_data_label = create_styled_image_tab(self.correbubble_plot_tabs, "数据表格")
        
        right_layout.addWidget(self.correbubble_plot_tabs)
        center_layout.addWidget(right_panel, 3)

        layout.addLayout(center_layout)

        self.update_styles()
        return self.bulk_correbubble_page
