# -*- coding: utf-8 -*-
"""
Settings界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_label, create_styled_panel
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class SettingsPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.settings_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.settings_page.findChild(QLabel, "settings_bg")
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

        title_label = self.settings_page.findChild(QLabel, "settings_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        overlay = self.settings_page.findChild(QWidget, "settings_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    def create_page(self):
        self.settings_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.settings_page)
        bg_label.setObjectName("settings_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.settings_page)
        overlay.setObjectName("settings_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        # 顶部标题栏
        top_layout = QHBoxLayout()

        # 返回主页按钮 - 使用固定最小宽度
        self.btn_back_settings = create_styled_button("← 返回主页", font_size=12)
        self.btn_back_settings.setMinimumWidth(styles.get('back_button_min_width', 120))
        top_layout.addWidget(self.btn_back_settings)

        # 标题
        title_label = QLabel("设置选项")
        title_label.setObjectName("settings_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # 使用MusicController创建音乐控件
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.settings_page, mod_instance)
        
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

        # 主内容区域 - 使用水平布局，左侧R配置，右侧功能开发中
        main_layout = QHBoxLayout()
        
        # 左侧面板 - R配置
        left_panel, left_layout = create_styled_panel()
        left_layout.setContentsMargins(20, 20, 20, 20)
        
        # R配置标题
        r_config_title = create_styled_label("R配置", font_size=16, bold=True)
        left_layout.addWidget(r_config_title)
        
        left_layout.addSpacing(10)
        
        # R内核选择标签
        r_kernel_label = create_styled_label("R内核路径", font_size=12, bold=False)
        left_layout.addWidget(r_kernel_label)
        
        # 扫描R内核按钮
        self.btn_scan_r_kernel = create_styled_button("扫描R内核", font_size=11, variant='sub')
        left_layout.addWidget(self.btn_scan_r_kernel)
        
        left_layout.addSpacing(5)
        
        # R内核下拉框
        self.r_kernel_combo = create_styled_combo_box()
        self.r_kernel_combo.setMinimumWidth(350)
        left_layout.addWidget(self.r_kernel_combo)
        
        left_layout.addSpacing(5)
        
        # R内核提示信息
        r_tip_label = create_styled_label("提示：选择R内核后，点击确认按钮保存设置", font_size=10, bold=False)
        r_tip_label.setStyleSheet(f"color: {styles.get('sub_text_secondary', '#888888')};")
        left_layout.addWidget(r_tip_label)
        
        left_layout.addSpacing(15)
        
        # 确认设置按钮
        self.btn_confirm_r_kernel = create_styled_button("设置R内核", font_size=12, variant='sub')
        left_layout.addWidget(self.btn_confirm_r_kernel)
        
        left_layout.addSpacing(20)
        
        # 当前R状态
        r_status_title = create_styled_label("当前R状态", font_size=14, bold=True)
        left_layout.addWidget(r_status_title)
        
        self.r_status_text = create_styled_label("未设置", font_size=11, bold=False)
        left_layout.addWidget(self.r_status_text)
        
        left_layout.addStretch()
        
        # 右侧面板 - 功能开发中
        right_panel, right_layout = create_styled_panel()
        right_layout.setContentsMargins(20, 20, 20, 20)
        
        right_title = create_styled_label("更多功能", font_size= 16, bold=True)
        right_layout.addWidget(right_title)
        
        right_layout.addSpacing(20)
        
        right_tip = create_styled_label("功能开发中，敬请期待...", font_size=12, bold=False)
        right_tip.setStyleSheet(f"color: {styles.get('sub_text_secondary', '#888888')};")
        right_layout.addWidget(right_tip)
        
        right_layout.addStretch()
        
        # 添加到主布局
        main_layout.addWidget(left_panel, 1)
        main_layout.addSpacing(20)
        main_layout.addWidget(right_panel, 1)
        
        layout.addLayout(main_layout)
        
        # 保存stacked_widget引用
        self.stacked_widget = self.parent.stacked_widget if hasattr(self.parent, 'stacked_widget') else None
        
        return self.settings_page
