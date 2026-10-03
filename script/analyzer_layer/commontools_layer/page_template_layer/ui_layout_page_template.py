# -*- coding: utf-8 -*-
"""
页面模板界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输出框、设置样式尺寸
完全不写按钮点击、触发逻辑

顶端控件（返回按钮 / 标题 / 音乐控件）的排布、字号与配色逐行对齐 GDSC 子页面
（ui_layout_bulk_gdsc_drug_sensitivity.py 的 create_page）；下方左右两栏：
左栏为「R测试」按钮与其正下方的 R 环境自检输出框，右栏为「py测试」按钮与其正下方的
Python 内核自检输出框，两侧互不影响。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_text_edit, create_styled_panel
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class PageTemplateUI:
    def __init__(self, parent_window, page_width, page_height):
        self.parent = parent_window
        self.page_width = page_width
        self.page_height = page_height
        self.screen_width = page_width
        self.screen_height = page_height
        self.page_template_page = None
        self.create_page()

    def update_background(self):
        """刷新背景图（主题/尺寸变化时调用）"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.page_template_page.findChild(QLabel, "page_template_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """更新主题相关样式（照 GDSC 子页面写法：只刷标题配色与遮罩）

        注意：这里**不遍历子控件**。所有控件都由 gui_styles 工厂函数创建并已注册主题回调，
        主题切换时由 refresh_all_themed_widgets() 统一重刷；若在此对 findChildren(QPushButton)
        套通用按钮样式，会把音乐控制器内部的按钮一并改样式，破坏顶端观感。
        """
        styles = get_mod_styles()

        title_label = self.page_template_page.findChild(QLabel, "page_template_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")

        overlay = self.page_template_page.findChild(QWidget, "page_template_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    def _create_test_column(self, column_width, column_height):
        """创建一个测试栏（按钮在上、只读输出框在正下方），返回列容器与内部布局"""
        column, column_layout = create_styled_panel(fixed_width=column_width)
        column.setFixedHeight(column_height)
        column_layout.setContentsMargins(15, 15, 15, 15)
        column_layout.setSpacing(20)
        return column, column_layout

    def create_page(self):
        self.page_template_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.page_template_page)
        bg_label.setObjectName("page_template_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.page_template_page)
        overlay.setObjectName("page_template_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_page_template = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_page_template)

        title_label = QLabel("页面模板")
        title_label.setObjectName("page_template_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.page_template_page, mod_instance)

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

        # ---------------- 左右两栏：左 R测试 / 右 py测试 ----------------
        # 照 GDSC 用居中容器承载下方内容区
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)

        columns_layout = QHBoxLayout()
        columns_layout.setContentsMargins(40, 0, 40, 0)
        columns_layout.setSpacing(60)

        column_width = 600
        button_height = 60
        log_width = 600
        log_height = 420

        columns_layout.addStretch()

        # 左栏：R测试
        left_column, left_layout = self._create_test_column(column_width, button_height + log_height + 50)

        self.btn_test_r = create_styled_button("R测试", font_size=14, parent=left_column)
        self.btn_test_r.setFixedSize(column_width - 30, button_height)
        left_layout.addWidget(self.btn_test_r, alignment=Qt.AlignCenter)

        self.r_log = create_styled_text_edit(parent=left_column, read_only=True)
        self.r_log.setFixedSize(log_width - 30, log_height)
        left_layout.addWidget(self.r_log, alignment=Qt.AlignCenter)

        columns_layout.addWidget(left_column)

        # 右栏：py测试
        right_column, right_layout = self._create_test_column(column_width, button_height + log_height + 50)

        self.btn_test_py = create_styled_button("py测试", font_size=14, parent=right_column)
        self.btn_test_py.setFixedSize(column_width - 30, button_height)
        right_layout.addWidget(self.btn_test_py, alignment=Qt.AlignCenter)

        self.py_log = create_styled_text_edit(parent=right_column, read_only=True)
        self.py_log.setFixedSize(log_width - 30, log_height)
        right_layout.addWidget(self.py_log, alignment=Qt.AlignCenter)

        columns_layout.addWidget(right_column)

        columns_layout.addStretch()

        center_layout.addLayout(columns_layout)
        layout.addWidget(center_widget)

        return self.page_template_page


__all__ = ['PageTemplateUI']
