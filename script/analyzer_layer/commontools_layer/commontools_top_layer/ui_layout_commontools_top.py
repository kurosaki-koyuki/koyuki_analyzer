# -*- coding: utf-8 -*-
"""
小工具主页（hub）导航界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑

采用左侧导航栏+右侧内容面板的布局风格（同构于单细胞主页 scRNAseq_top_layer）
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_panel, create_styled_text_edit,
    create_navigation_panel, create_navigation_button, create_navigation_divider, create_navigation_header,
    create_styled_image_button
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect


class CommonToolsTopPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.commontools_top_page.findChild(QLabel, "commontools_top_bg")
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
        
        button_style = get_stylesheet_for_widget('button')
        for child in self.commontools_top_page.findChildren(QPushButton):
            if child in [self.btn_card_venn, self.btn_card_circos] and hasattr(self, 'btn_card_venn'):
                continue
            nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
            if child in nav_buttons:
                continue
            child.setStyleSheet(button_style)
        
        if hasattr(self, 'btn_card_venn'):
            self.btn_card_venn.setStyleSheet(get_stylesheet_for_widget('button'))
            self.btn_card_circos.setStyleSheet(get_stylesheet_for_widget('button'))
        
        label_style = get_stylesheet_for_widget('label')
        for child in self.commontools_top_page.findChildren(QLabel):
            if child.objectName() == "commontools_top_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)
        
        title_label = self.commontools_top_page.findChild(QLabel, "commontools_top_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        
        panel_bg = styles.get('sub_panel_bg', 'rgba(30, 58, 95, 0.5)')
        panel_border = styles.get('sub_panel_border', '#1E3A5F')
        panel_radius = styles.get('panel_border_radius', '8px')
        
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.commontools_top_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    def _create_genelist_panel(self, parent):
        """创建基因列表类分析面板内容"""
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)
        
        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
        
        title_label = QLabel("基因列表类分析")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(30)
        
        venn_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'vennplot_layer.png')
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        
        self.btn_card_venn = create_styled_image_button("韦恩图交集", venn_image_path, parent=panel)
        columns_layout.addWidget(self.btn_card_venn, alignment=Qt.AlignCenter)
        
        layout.addLayout(columns_layout)
        
        layout.addStretch()
        
        return panel

    def _create_misc_panel(self, parent):
        """创建杂项分析类面板内容"""
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)
        
        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
        
        title_label = QLabel("杂项分析类")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(30)
        
        circos_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'circos_layer.png')
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        
        self.btn_card_circos = create_styled_image_button("Circos 染色体定位", circos_image_path, parent=panel)
        columns_layout.addWidget(self.btn_card_circos, alignment=Qt.AlignCenter)
        
        layout.addLayout(columns_layout)
        
        layout.addStretch()
        
        return panel

    def show_panel(self, panel_name):
        """显示指定面板，隐藏其他面板"""
        for name, panel in self.panels.items():
            if name == panel_name:
                panel.show()
                panel.raise_()
            else:
                panel.hide()
        
        for attr in dir(self):
            if attr.startswith('nav_btn_'):
                btn = getattr(self, attr)
                btn.setChecked(attr == f'nav_btn_{panel_name}')

    def create_page(self):
        self.commontools_top_page = QWidget(self.parent)
        
        styles = get_mod_styles()
        paths = get_mod_paths()
        
        bg_label = QLabel(self.commontools_top_page)
        bg_label.setObjectName("commontools_top_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height, 
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()
        
        overlay = QWidget(self.commontools_top_page)
        overlay.setObjectName("commontools_top_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")
        
        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)
        
        self.nav_btn_back = create_navigation_button("← 返回主界面", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)
        
        nav_layout.addSpacing(10)
        
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        
        nav_layout.addSpacing(10)
        
        nav_layout.addWidget(create_navigation_header("分析工具", font_size=11, parent=nav_panel))
        
        self.nav_btn_genelist = create_navigation_button("基因列表类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_genelist)
        
        self.nav_btn_misc = create_navigation_button("杂项分析类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_misc)
        
        nav_layout.addStretch()
        
        main_layout.addWidget(nav_panel)
        
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        top_bar, top_bar_layout = create_styled_panel(parent=content_panel)
        top_bar_layout.setContentsMargins(15, 8, 15, 8)
        
        title_row_layout = QHBoxLayout()
        
        title_label = QLabel("小工具")
        title_label.setObjectName("commontools_top_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)
        
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.commontools_top_page, mod_instance)
        
        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')
        
        title_row_layout.addWidget(music_container)
        
        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)
        
        top_bar_layout.addLayout(title_row_layout)
        
        content_layout.addWidget(top_bar)
        
        panels_container = QWidget(content_panel)
        panels_layout = QVBoxLayout(panels_container)
        panels_layout.setContentsMargins(20, 20, 20, 20)
        
        self.genelist_panel = self._create_genelist_panel(panels_container)
        self.misc_panel = self._create_misc_panel(panels_container)
        
        self.panels = {
            'genelist': self.genelist_panel,
            'misc': self.misc_panel
        }
        
        panels_layout.addWidget(self.genelist_panel)
        panels_layout.addWidget(self.misc_panel)
        
        content_layout.addWidget(panels_container)
        
        main_layout.addWidget(content_panel)
        
        self.show_panel('genelist')
        
        self.update_styles()


__all__ = ['CommonToolsTopPageUI']
