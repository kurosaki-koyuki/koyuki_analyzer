# -*- coding: utf-8 -*-
"""
bulk相关性分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_panel, create_styled_group_box,
    create_styled_tab_widget, create_styled_tab_page, create_styled_label,
    create_styled_line_edit, create_styled_combo_box
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class BulkCorredotPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_corredot_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_corredot_page.findChild(QLabel, "bulk_corredot_bg")
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

        title_label = self.bulk_corredot_page.findChild(QLabel, "bulk_corredot_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        overlay = self.bulk_corredot_page.findChild(QWidget, "bulk_corredot_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    def create_page(self):
        self.bulk_corredot_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.bulk_corredot_page)
        bg_label.setObjectName("bulk_corredot_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.bulk_corredot_page)
        overlay.setObjectName("bulk_corredot_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_bulk_corredot = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_bulk_corredot)

        title_label = QLabel("相关性散点图")
        title_label.setObjectName("bulk_corredot_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # 使用MusicController创建音乐控件
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.bulk_corredot_page, mod_instance)
        
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

        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0, 20, 0, 0)

        left_panel, left_layout = create_styled_panel()
        left_layout.setAlignment(Qt.AlignTop)
        
        self.btn_run_corredot = create_styled_button("运行", font_size=14, button_type='run')
        left_layout.addWidget(self.btn_run_corredot)
        
        left_layout.addStretch()
        center_layout.addWidget(left_panel, 1)

        params_panel, params_layout = create_styled_panel()
        params_layout.setAlignment(Qt.AlignTop)
        
        params_group = create_styled_group_box("参数设置")
        params_group_layout = QVBoxLayout(params_group)
        
        self.corredot_param1_label = create_styled_label("参数1")
        params_group_layout.addWidget(self.corredot_param1_label)
        self.corredot_param1_input = create_styled_line_edit()
        params_group_layout.addWidget(self.corredot_param1_input)
        
        params_group_layout.addSpacing(10)
        
        self.corredot_param2_label = create_styled_label("参数2")
        params_group_layout.addWidget(self.corredot_param2_label)
        self.corredot_param2_combo = create_styled_combo_box()
        params_group_layout.addWidget(self.corredot_param2_combo)
        
        params_group_layout.addStretch()
        params_layout.addWidget(params_group)
        
        params_layout.addStretch()
        center_layout.addWidget(params_panel, 1)

        right_panel, right_layout = create_styled_panel()
        
        self.corredot_tab_widget = create_styled_tab_widget(movable=True, document_mode=True)
        
        self.corredot_tab1_page, self.corredot_tab1_layout = create_styled_tab_page(self.corredot_tab_widget, "结果展示")
        self.corredot_tab1_label = create_styled_label("结果将显示在这里", font_size=14, bold=False)
        self.corredot_tab1_label.setAlignment(Qt.AlignCenter)
        self.corredot_tab1_layout.addWidget(self.corredot_tab1_label)
        
        self.corredot_tab2_page, self.corredot_tab2_layout = create_styled_tab_page(self.corredot_tab_widget, "数据表格")
        self.corredot_tab2_label = create_styled_label("数据表格将显示在这里", font_size=14, bold=False)
        self.corredot_tab2_label.setAlignment(Qt.AlignCenter)
        self.corredot_tab2_layout.addWidget(self.corredot_tab2_label)
        
        right_layout.addWidget(self.corredot_tab_widget)
        center_layout.addWidget(right_panel, 3)

        layout.addLayout(center_layout)

        return self.bulk_corredot_page