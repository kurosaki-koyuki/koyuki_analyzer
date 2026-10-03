# -*- coding: utf-8 -*-
"""
CellChat细胞通讯分析界面UI布局脚本 - 主层容器，管理子层切换（初步分析类等）
背景图由主层统一管理，子层使用透明背景
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_font_for_widget,
    create_styled_button, create_navigation_panel, create_navigation_button,
    create_navigation_divider, create_navigation_header
)
from script.mods_layer.mod_manager import global_mod_manager


class ScCellChatContainerPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_cellchat_page = None
        self.primary_ui = None  # 子层UI实例（初步分析类）
        self.loading_ui = None  # 子层UI实例（数据加载类）
        self.create_page()

    def update_background(self):
        """更新背景图（切换mod时调用）"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.sc_cellchat_page.findChild(QLabel, "sc_cellchat_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """更新覆盖层样式，并递归更新子页面样式"""
        styles = get_mod_styles()

        overlay = self.sc_cellchat_page.findChild(QWidget, "sc_cellchat_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        if self.primary_ui and hasattr(self.primary_ui, 'update_styles'):
            self.primary_ui.update_styles()
        
        if self.loading_ui and hasattr(self.loading_ui, 'update_styles'):
            self.loading_ui.update_styles()

        self.update_background()

    def create_page(self):
        self.sc_cellchat_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()

        # 背景层
        bg_label = QLabel(self.sc_cellchat_page)
        bg_label.setObjectName("sc_cellchat_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        # 覆盖层（统一暗化）
        overlay = QWidget(self.sc_cellchat_page)
        overlay.setObjectName("sc_cellchat_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        # 主布局：左侧导航栏 + 右侧内容栈
        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航栏
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        # 返回主页按钮
        self.nav_btn_back = create_navigation_button("← 返回主页", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        nav_layout.addSpacing(10)

        # 分析模式标题
        nav_layout.addWidget(create_navigation_header("分析类别", font_size=11, parent=nav_panel))

        # 初步分析类按钮（默认选中）
        self.nav_btn_primary = create_navigation_button("初步分析类", font_size=13, parent=nav_panel)
        self.nav_btn_primary.setChecked(True)
        nav_layout.addWidget(self.nav_btn_primary)
        
        # 数据加载类按钮
        self.nav_btn_loading = create_navigation_button("数据加载类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_loading)

        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        # 右侧内容栈
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(20, 20, 20, 20)

        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background: transparent;")

        # 子层容器：初步分析类
        self.primary_page_container = QWidget()
        self.primary_page_layout = QVBoxLayout(self.primary_page_container)
        self.primary_page_layout.setContentsMargins(0, 0, 0, 0)

        self.content_stack.addWidget(self.primary_page_container)
        
        # 子层容器：数据加载类
        self.loading_page_container = QWidget()
        self.loading_page_layout = QVBoxLayout(self.loading_page_container)
        self.loading_page_layout.setContentsMargins(0, 0, 0, 0)

        self.content_stack.addWidget(self.loading_page_container)

        content_layout.addWidget(self.content_stack)

        main_layout.addWidget(content_panel)
        main_layout.setStretch(1, 1)

        return self.sc_cellchat_page
