# -*- coding: utf-8 -*-
"""
初步分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget, create_styled_button, create_styled_combo_box, create_styled_line_edit, create_styled_label, create_styled_panel
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class InitialAnalysisPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()
    
    def update_background(self):
        """更新背景图"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.analysis_page.findChild(QLabel, "analysis_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height, 
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
    
    def update_styles(self):
        """更新所有控件的样式"""
        styles = get_mod_styles()
        primary_color = styles.get('sub_text_color', styles.get('text_color', '#87CEEB'))
        secondary_color = styles.get('sub_border_color', styles.get('border_color', '#1E3A5F'))
        slider_bg = styles.get('sub_slider_bg', styles.get('slider_background', 'rgba(30, 58, 95, 0.4)'))
        slider_handle = styles.get('sub_slider_handle', styles.get('slider_handle', '#1E3A5F'))
        slider_handle_hover = styles.get('sub_slider_handle_hover', styles.get('slider_handle_hover', '#2E4A6F'))
        
        # 更新标题样式
        title_label = self.analysis_page.findChild(QLabel, "analysis_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        
        # 更新按钮样式
        button_style = get_stylesheet_for_widget('button')
        for child in self.analysis_page.findChildren(QPushButton):
            # 特殊按钮保持自己的样式
            if child == self.btn_query:
                continue  # 运行按钮保持run_button样式
            elif child in [self.btn_export_png, self.btn_export_pdf]:
                continue  # 导出按钮保持export_button样式
            child.setStyleSheet(button_style)
        
        # 重新应用特殊按钮样式
        self.btn_query.setStyleSheet(get_stylesheet_for_widget('run_button'))
        self.btn_export_png.setStyleSheet(get_stylesheet_for_widget('export_button'))
        self.btn_export_pdf.setStyleSheet(get_stylesheet_for_widget('export_button'))
        
        # 更新下拉框样式
        combo_style = get_stylesheet_for_widget('combo')
        for child in self.analysis_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)
        
        # 更新输入框样式
        line_edit_style = get_stylesheet_for_widget('line_edit')
        for child in self.analysis_page.findChildren(QLineEdit):
            child.setStyleSheet(line_edit_style)
        
        # 更新文本编辑框样式
        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.analysis_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)
        
        # 更新标签样式
        label_style = get_stylesheet_for_widget('label')
        for child in self.analysis_page.findChildren(QLabel):
            if child.objectName() != "analysis_title":
                child.setStyleSheet(label_style)
        
        # 更新音量条样式
        slider_style = f"""
            QSlider {{
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {secondary_color};
                height: 8px;
                background: {slider_bg};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {slider_handle};
                border: 1px solid {secondary_color};
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {slider_handle_hover};
            }}
        """
        for child in self.analysis_page.findChildren(QSlider):
            child.setStyleSheet(slider_style)
        
        # 更新面板样式
        panel_bg = styles.get('sub_panel_bg', styles.get('panel_background', 'rgba(30, 58, 95, 0.5)'))
        panel_border = styles.get('sub_panel_border', styles.get('panel_border_color', '#1E3A5F'))
        panel_radius = styles.get('panel_border_radius', '8px')
        
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.analysis_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)
        
        # 更新overlay样式
        overlay = self.analysis_page.findChild(QWidget, "analysis_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")
    
    def create_page(self):
        self.analysis_page = QWidget(self.parent)
        
        styles = get_mod_styles()
        paths = get_mod_paths()
        
        primary_color = styles.get('primary_color', '#87CEEB')
        secondary_color = styles.get('secondary_color', '#1E3A5F')
        
        bg_label = QLabel(self.analysis_page)
        bg_label.setObjectName("analysis_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height, 
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()
        
        overlay = QWidget(self.analysis_page)
        overlay.setObjectName("analysis_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")
        
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title_panel, title_layout = create_styled_panel()
        top_layout = QHBoxLayout()
        
        self.btn_back_analysis = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_analysis)
        
        title_label = QLabel("初步分析")
        title_label.setObjectName("analysis_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)
        
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.analysis_page, mod_instance)
        
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
        
        title_layout.addLayout(top_layout)
        layout.addWidget(title_panel)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(80)
        self.status_text.setFont(get_font_for_widget('label', 10))
        self.status_text.setStyleSheet(get_stylesheet_for_widget('text_edit'))
        layout.addWidget(self.status_text)
        
        main_layout = QHBoxLayout()
        
        left_panel, left_layout = create_styled_panel(fixed_width=280)
        
        info_title = QLabel("数据信息")
        info_title.setFont(get_font_for_widget('label', 14, bold=True))
        info_title.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(info_title)
        
        self.data_info_text = QTextEdit()
        self.data_info_text.setReadOnly(True)
        self.data_info_text.setMaximumHeight(120)
        self.data_info_text.setFont(get_font_for_widget('label', 10))
        self.data_info_text.setStyleSheet(get_stylesheet_for_widget('text_edit'))
        self.data_info_text.setText("数据未加载\n请点击下方按钮加载数据")
        left_layout.addWidget(self.data_info_text)
        
        left_layout.addSpacing(15)
        
        gene_label = QLabel("基因名")
        gene_label.setFont(get_font_for_widget('label', 12, bold=True))
        gene_label.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(gene_label)
        
        self.gene_input = create_styled_line_edit()
        left_layout.addWidget(self.gene_input)
        
        self.btn_query = create_styled_button("查询基因", font_size=12, button_type='run')
        left_layout.addWidget(self.btn_query)
        
        left_layout.addSpacing(15)
        
        source_label = QLabel("显示类型")
        source_label.setFont(get_font_for_widget('label', 12, bold=True))
        source_label.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(source_label)
        
        self.source_combo = create_styled_combo_box()
        self.source_combo.addItems(["基因表达量", "注释"])
        left_layout.addWidget(self.source_combo)
        
        plot_label = QLabel("注释类型")
        plot_label.setFont(get_font_for_widget('label', 12, bold=True))
        plot_label.setStyleSheet(get_stylesheet_for_widget('label'))
        left_layout.addWidget(plot_label)
        
        self.plot_combo = create_styled_combo_box()
        left_layout.addWidget(self.plot_combo)
        
        left_layout.addSpacing(5)
        
        self.btn_export_png = create_styled_button("导出当前图片png", font_size=12, button_type='export')
        left_layout.addWidget(self.btn_export_png)
        
        self.btn_export_pdf = create_styled_button("导出当前图片pdf", font_size=12, button_type='export')
        left_layout.addWidget(self.btn_export_pdf)
        
        left_layout.addStretch()
        main_layout.addWidget(left_panel)
        
        right_panel, right_layout = create_styled_panel()
        
        self.image_label = QLabel()
        self.image_label.setStyleSheet(get_stylesheet_for_widget('image_label'))
        self.image_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.image_label)
        
        main_layout.addWidget(right_panel)
        layout.addLayout(main_layout)
        
        # 初始化完成后立即应用样式
        self.update_styles()