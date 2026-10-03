# -*- coding: utf-8 -*-
"""
bulk 机器学习分析界面UI布局脚本 - 主层容器，管理子层切换
背景图由主层统一管理，子层使用透明背景
参考：Monocle分析容器层结构 + log-rank左侧导航风格

子层顺序（与 content_stack 索引对应）：
    0 - 数据加载类 (bulk_machinelearning_loading_layer)
    1 - 差异训练类 (bulk_machinelearning_diff_train_layer)
    2 - 生存训练类 (bulk_machinelearning_surv_train_layer)
    （注：原「差异筛选类」空壳子层已移除，差异分析统一在差异训练类中完成训练+验证）
    （注：原「生存筛选类」层已移除，生存分析统一在生存训练类中完成训练+评价+筛选）
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_font_for_widget,
    create_styled_button, create_navigation_panel, create_navigation_button,
    create_navigation_divider, create_navigation_header
)
from script.mods_layer.mod_manager import global_mod_manager


class BulkMachineLearningPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.bulk_machinelearning_page = None
        self.loading_ui = None       # 子层UI实例（数据加载类）
        self.diff_train_ui = None    # 子层UI实例（差异训练类）
        self.surv_train_ui = None    # 子层UI实例（生存训练类）
        self.music_controller = None
        self.create_page()

    def update_background(self):
        """更新背景图（切换mod时调用）"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_machinelearning_page.findChild(QLabel, "bulk_machinelearning_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """更新覆盖层样式，并递归更新所有子页面样式"""
        styles = get_mod_styles()

        overlay = self.bulk_machinelearning_page.findChild(QWidget, "bulk_machinelearning_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        # 递归更新所有子层样式
        if self.loading_ui and hasattr(self.loading_ui, 'update_styles'):
            self.loading_ui.update_styles()
        if self.diff_train_ui and hasattr(self.diff_train_ui, 'update_styles'):
            self.diff_train_ui.update_styles()
        if self.surv_train_ui and hasattr(self.surv_train_ui, 'update_styles'):
            self.surv_train_ui.update_styles()

        self.update_background()

    def create_page(self):
        self.bulk_machinelearning_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        # 背景层
        bg_label = QLabel(self.bulk_machinelearning_page)
        bg_label.setObjectName("bulk_machinelearning_bg")
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
        overlay = QWidget(self.bulk_machinelearning_page)
        overlay.setObjectName("bulk_machinelearning_overlay")
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

        # 分析类别标题
        nav_layout.addWidget(create_navigation_header("分析类别", font_size=11, parent=nav_panel))

        # 数据加载类按钮（默认选中，索引0）
        self.nav_btn_loading = create_navigation_button("数据加载类", font_size=13, parent=nav_panel)
        self.nav_btn_loading.setChecked(True)
        nav_layout.addWidget(self.nav_btn_loading)

        # 差异训练类按钮（索引1）
        self.nav_btn_diff_train = create_navigation_button("差异训练类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_diff_train)

        # 生存训练类按钮（索引2）
        self.nav_btn_surv_train = create_navigation_button("生存训练类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_surv_train)

        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        # 右侧内容区域
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 音乐控制器（主层管理，子层共享，绝对定位放右上角，参考GDSC风格）
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.bulk_machinelearning_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')

        music_container_x = styles.get('music_container_x', 0.85)
        music_container_y = styles.get('music_container_y', 15)
        if isinstance(music_container_x, float):
            music_container_x = int(self.screen_width * music_container_x)
        music_container.move(music_container_x, music_container_y)

        # 子层内容栈（QStackedWidget便于后续扩展多个子层）
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: transparent;")

        # 子层容器：数据加载类（索引0）
        self.loading_page_container = QWidget()
        self.loading_page_container.setStyleSheet("background: transparent;")
        self.loading_page_layout = QVBoxLayout(self.loading_page_container)
        self.loading_page_layout.setContentsMargins(0, 0, 0, 0)
        self.content_stack.addWidget(self.loading_page_container)

        # 子层容器：差异训练类（索引1）
        self.diff_train_page_container = QWidget()
        self.diff_train_page_container.setStyleSheet("background: transparent;")
        self.diff_train_page_layout = QVBoxLayout(self.diff_train_page_container)
        self.diff_train_page_layout.setContentsMargins(0, 0, 0, 0)
        self.content_stack.addWidget(self.diff_train_page_container)

        # 子层容器：生存训练类（索引2）
        self.surv_train_page_container = QWidget()
        self.surv_train_page_container.setStyleSheet("background: transparent;")
        self.surv_train_page_layout = QVBoxLayout(self.surv_train_page_container)
        self.surv_train_page_layout.setContentsMargins(0, 0, 0, 0)
        self.content_stack.addWidget(self.surv_train_page_container)

        content_layout.addWidget(self.content_stack)

        main_layout.addWidget(content_panel)
        main_layout.setStretch(1, 1)

        return self.bulk_machinelearning_page
