# -*- coding: utf-8 -*-
"""
bulk相关性分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_label, create_styled_panel,
    create_styled_text_edit, create_styled_group_box
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class BulkCorrePageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_corre_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_corre_page.findChild(QLabel, "bulk_corre_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """更新所有控件的样式（不修改控件尺寸）"""
        styles = get_mod_styles()

        title_label = self.bulk_corre_page.findChild(QLabel, "bulk_corre_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        button_style = get_stylesheet_for_widget('button')
        for child in self.bulk_corre_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)
# 重新应用特殊按钮样式（确保不被通用样式覆盖）
        if hasattr(self, 'btn_corredot'):
            self.btn_corredot.setStyleSheet(get_stylesheet_for_widget('run_button'))
        if hasattr(self, 'btn_correbubble'):
            self.btn_correbubble.setStyleSheet(get_stylesheet_for_widget('run_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.bulk_corre_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.bulk_corre_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_corre_page.findChildren(QLabel):
            if child.objectName() != "bulk_corre_title":
                child.setStyleSheet(label_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')

        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_corre_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        overlay = self.bulk_corre_page.findChild(QWidget, "bulk_corre_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    def create_page(self):
        self.bulk_corre_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.bulk_corre_page)
        bg_label.setObjectName("bulk_corre_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.bulk_corre_page)
        overlay.setObjectName("bulk_corre_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_bulk_corre = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_bulk_corre)

        title_label = QLabel("bulk相关性分析")
        title_label.setObjectName("bulk_corre_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # 使用MusicController创建音乐控件
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.bulk_corre_page, mod_instance)
        
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

        main_layout = QHBoxLayout()

        left_panel, left_layout = create_styled_panel(fixed_width=320)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        right_panel, right_layout = create_styled_panel()

        self.bulk_corre_status_text = create_styled_text_edit(read_only=True)
        self.bulk_corre_status_text.setMaximumHeight(80)
        right_layout.addWidget(self.bulk_corre_status_text)

        right_layout.addSpacing(20)

        button_group = create_styled_group_box("相关性分析工具")
        button_layout = QVBoxLayout(button_group)

        self.btn_corredot = create_styled_button("相关性散点图", font_size=14)
        button_layout.addWidget(self.btn_corredot)

        self.btn_correbubble = create_styled_button("相关性气泡图（基因）", font_size=14)
        button_layout.addWidget(self.btn_correbubble)

        right_layout.addWidget(button_group)

        right_layout.addStretch()
        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.bulk_corre_page