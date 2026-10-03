# -*- coding: utf-8 -*-
"""
scRNAseq 药物敏感性分析界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class ScGdscDrugSensitivityPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_gdsc_drug_sensitivity_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.sc_gdsc_drug_sensitivity_page.findChild(QLabel, "sc_gdsc_drug_sensitivity_bg")
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

        title_label = self.sc_gdsc_drug_sensitivity_page.findChild(QLabel, "sc_gdsc_drug_sensitivity_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        overlay = self.sc_gdsc_drug_sensitivity_page.findChild(QWidget, "sc_gdsc_drug_sensitivity_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    def create_page(self):
        self.sc_gdsc_drug_sensitivity_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.sc_gdsc_drug_sensitivity_page)
        bg_label.setObjectName("sc_gdsc_drug_sensitivity_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.sc_gdsc_drug_sensitivity_page)
        overlay.setObjectName("sc_gdsc_drug_sensitivity_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_sc_gdsc_drug_sensitivity = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_sc_gdsc_drug_sensitivity)

        title_label = QLabel("GDSC药物敏感性分析")
        title_label.setObjectName("sc_gdsc_drug_sensitivity_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.sc_gdsc_drug_sensitivity_page, mod_instance)

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

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)

        dev_label = QLabel("🚧 处于开发状态 🚧")
        dev_label.setFont(get_font_for_widget('button', 28, bold=True))
        dev_label.setStyleSheet(f"color: {styles.get('warning_color', '#FFA500')}; background: transparent;")
        dev_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(dev_label)

        info_label = QLabel("该功能正在开发中，敬请期待...")
        info_label.setFont(get_font_for_widget('label', 16))
        info_label.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')}; background: transparent;")
        info_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(info_label)

        layout.addWidget(center_widget)

        return self.sc_gdsc_drug_sensitivity_page