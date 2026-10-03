# -*- coding: utf-8 -*-
"""
bulk Log-rank分析界面UI布局脚本 - Python版本
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_font_for_widget,
    create_styled_button, create_navigation_panel, create_navigation_button,
    create_navigation_divider, create_navigation_header
)
from script.mods_layer.mod_manager import global_mod_manager


class BulkLogrankPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_logrank_page = None
        self.py_ui = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_logrank_page.findChild(QLabel, "bulk_logrank_bg")
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

        overlay = self.bulk_logrank_page.findChild(QWidget, "bulk_logrank_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        if self.py_ui and hasattr(self.py_ui, 'update_styles'):
            self.py_ui.update_styles()

        self.update_background()

    def create_page(self):
        self.bulk_logrank_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.bulk_logrank_page)
        bg_label.setObjectName("bulk_logrank_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.bulk_logrank_page)
        overlay.setObjectName("bulk_logrank_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(20, 20, 20, 20)

        self.py_page_container = QWidget()
        self.py_page_layout = QVBoxLayout(self.py_page_container)
        self.py_page_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.addWidget(self.py_page_container)

        main_layout.addWidget(content_panel)
        main_layout.setStretch(1, 1)

        return self.bulk_logrank_page