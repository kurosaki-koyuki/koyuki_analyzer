# -*- coding: utf-8 -*-
"""
bulk分析顶层导航界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑

采用左侧导航栏+右侧内容面板的布局风格
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


class BulkTopPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.bulk_top_page.findChild(QLabel, "bulk_top_bg")
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
        for child in self.bulk_top_page.findChildren(QPushButton):
            if child in [self.btn_select_path, self.btn_load] and hasattr(self, 'btn_select_path'):
                continue
            nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
            if child in nav_buttons:
                continue
            child.setStyleSheet(button_style)
        
        if hasattr(self, 'btn_select_path'):
            self.btn_select_path.setStyleSheet(get_stylesheet_for_widget('import_button'))
            self.btn_load.setStyleSheet(get_stylesheet_for_widget('import_button'))
        
        label_style = get_stylesheet_for_widget('label')
        for child in self.bulk_top_page.findChildren(QLabel):
            if child.objectName() == "bulk_top_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)
        
        title_label = self.bulk_top_page.findChild(QLabel, "bulk_top_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        
        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.bulk_top_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    def _create_data_load_panel(self, parent):
        """创建数据加载面板内容"""
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)
        
        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        subtitle_color = styles.get('sub_text_color', '#87CEEB')
        
        title_label = QLabel("数据加载")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(20)
        
        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
        
        status_title = QLabel("运行状态")
        status_title.setFont(QFont(subtitle_font, 14, QFont.Bold))
        status_title.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        status_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_title)
        
        self.status_text = create_styled_text_edit(read_only=True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setFont(get_font_for_widget('label', 10))
        self.status_text.setText("等待数据加载...")
        layout.addWidget(self.status_text)
        
        layout.addSpacing(30)
        
        self.btn_select_path = create_styled_button("扫描数据路径", font_size=14, button_type='import', parent=panel)
        layout.addWidget(self.btn_select_path, alignment=Qt.AlignCenter)
        
        layout.addSpacing(20)
        
        self.h5ad_combo = create_styled_combo_box(parent=panel)
        self.h5ad_combo.setMinimumWidth(300)
        layout.addWidget(self.h5ad_combo, alignment=Qt.AlignCenter)
        
        layout.addSpacing(20)
        
        self.btn_load = create_styled_button("加载数据集", font_size=14, button_type='import', parent=panel)
        layout.addWidget(self.btn_load, alignment=Qt.AlignCenter)
        
        layout.addStretch()
        
        return panel

    def _create_analysis_panel(self, parent):
        """创建分析方法面板内容"""
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)
        
        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
        
        title_label = QLabel("分析工具")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(30)
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)
        columns_layout.setContentsMargins(40, 0, 40, 0)
        
        btn_font_size = styles.get('button_font_size', 14)
        
        col1, col1_layout = create_styled_panel(variant='sub')
        col1_layout.setContentsMargins(15, 15, 15, 15)
        col1_layout.setSpacing(10)
        self.btn_expression = create_styled_button("表达量分析", font_size=btn_font_size, parent=col1)
        col1_layout.addWidget(self.btn_expression, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col1)
        
        col2, col2_layout = create_styled_panel(variant='sub')
        col2_layout.setContentsMargins(15, 15, 15, 15)
        col2_layout.setSpacing(10)
        self.btn_corre = create_styled_button("相关性分析", font_size=btn_font_size, parent=col2)
        col2_layout.addWidget(self.btn_corre, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col2)
        
        col3, col3_layout = create_styled_panel(variant='sub')
        col3_layout.setContentsMargins(15, 15, 15, 15)
        col3_layout.setSpacing(10)
        columns_layout.addWidget(col3)
        
        col4, col4_layout = create_styled_panel(variant='sub')
        col4_layout.setContentsMargins(15, 15, 15, 15)
        col4_layout.setSpacing(10)
        self.btn_km = create_styled_button("生存分析", font_size=btn_font_size, parent=col4)
        col4_layout.addWidget(self.btn_km, alignment=Qt.AlignCenter)
        self.btn_cluster = create_styled_button("一致性分析", font_size=btn_font_size, parent=col4)
        col4_layout.addWidget(self.btn_cluster, alignment=Qt.AlignCenter)
        self.btn_immune = create_styled_button("bulk免疫分析", font_size=btn_font_size, parent=col4)
        col4_layout.addWidget(self.btn_immune, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col4)
        
        layout.addLayout(columns_layout)
        
        layout.addStretch()
        
        return panel

    def _create_genelist_panel(self, parent):
        """创建基因列表类面板内容"""
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)
        
        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
        
        title_label = QLabel("基因列表类")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(30)
        
        btn_font_size = styles.get('button_font_size', 14)
        paths = get_mod_paths()
        pics_path = paths.get('PICS_PATH', 'appdata/elements/page_pics')
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        
        self.btn_cox = create_styled_image_button("Cox分析", os.path.join(pics_path, 'bulk_cox_layer.png'), parent=panel, font_size=btn_font_size)
        columns_layout.addWidget(self.btn_cox, alignment=Qt.AlignCenter)
        
        self.btn_diff = create_styled_image_button("差异分析", os.path.join(pics_path, 'bulk_diff_layer.png'), parent=panel, font_size=btn_font_size)
        columns_layout.addWidget(self.btn_diff, alignment=Qt.AlignCenter)
        
        self.btn_logrank = create_styled_image_button("Log-rank分析", os.path.join(pics_path, 'bulk_logrank_layer.png'), parent=panel, font_size=btn_font_size)
        columns_layout.addWidget(self.btn_logrank, alignment=Qt.AlignCenter)
        
        self.btn_wgcna = create_styled_image_button("WGCNA分析", os.path.join(pics_path, 'wgcna_layer.png'), parent=panel, font_size=btn_font_size)
        columns_layout.addWidget(self.btn_wgcna, alignment=Qt.AlignCenter)
        
        layout.addLayout(columns_layout)
        
        layout.addStretch()
        
        return panel

    def _create_other_panel(self, parent):
        """创建其他分析类面板内容"""
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)
        
        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
        
        title_label = QLabel("其他分析类")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(30)
        
        btn_font_size = styles.get('button_font_size', 14)
        
        col1, col1_layout = create_styled_panel(variant='sub')
        col1_layout.setContentsMargins(15, 15, 15, 15)
        col1_layout.setSpacing(10)
        self.btn_gdsc_drug_sensitivity = create_styled_button("GDSC药物敏感性分析", font_size=btn_font_size, parent=col1)
        col1_layout.addWidget(self.btn_gdsc_drug_sensitivity, alignment=Qt.AlignCenter)
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        columns_layout.addWidget(col1)
        
        layout.addLayout(columns_layout)
        
        layout.addStretch()
        
        return panel

    def show_panel(self, panel_name):
        """显示指定面板，隐藏其他面板（带淡入效果）"""
        for name, panel in self.panels.items():
            if name == panel_name:
                panel.show()
                panel.raise_()
                self._fade_in(panel)
            else:
                panel.hide()
        
        for attr in dir(self):
            if attr.startswith('nav_btn_'):
                btn = getattr(self, attr)
                btn.setChecked(attr == f'nav_btn_{panel_name}')

    def _fade_in(self, widget):
        """淡入动画效果"""
        widget.setWindowOpacity(1)
        widget.show()

    def create_page(self):
        self.bulk_top_page = QWidget(self.parent)
        
        styles = get_mod_styles()
        paths = get_mod_paths()
        
        bg_label = QLabel(self.bulk_top_page)
        bg_label.setObjectName("bulk_top_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height, 
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()
        
        overlay = QWidget(self.bulk_top_page)
        overlay.setObjectName("bulk_top_overlay")
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
        
        nav_layout.addWidget(create_navigation_header("数据管理", font_size=11, parent=nav_panel))
        
        self.nav_btn_data = create_navigation_button("加载数据", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_data)
        
        nav_layout.addSpacing(10)
        
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        
        nav_layout.addSpacing(10)
        
        nav_layout.addWidget(create_navigation_header("分析方法", font_size=11, parent=nav_panel))
        
        self.nav_btn_analysis = create_navigation_button("分析工具", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_analysis)
        
        self.nav_btn_genelist = create_navigation_button("基因列表类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_genelist)
        
        self.nav_btn_other = create_navigation_button("其他分析类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_other)
        
        nav_layout.addStretch()
        
        main_layout.addWidget(nav_panel)
        
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        top_bar, top_bar_layout = create_styled_panel(parent=content_panel)
        top_bar_layout.setContentsMargins(15, 8, 15, 8)
        
        title_row_layout = QHBoxLayout()
        
        title_label = QLabel("Bulk分析")
        title_label.setObjectName("bulk_top_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)
        
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.bulk_top_page, mod_instance)
        
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
        
        self.data_panel = self._create_data_load_panel(panels_container)
        self.analysis_panel = self._create_analysis_panel(panels_container)
        self.genelist_panel = self._create_genelist_panel(panels_container)
        self.other_panel = self._create_other_panel(panels_container)
        
        self.panels = {
            'data': self.data_panel,
            'analysis': self.analysis_panel,
            'genelist': self.genelist_panel,
            'other': self.other_panel
        }
        
        panels_layout.addWidget(self.data_panel)
        panels_layout.addWidget(self.analysis_panel)
        panels_layout.addWidget(self.genelist_panel)
        panels_layout.addWidget(self.other_panel)
        
        content_layout.addWidget(panels_container)
        
        main_layout.addWidget(content_panel)
        
        self.show_panel('data')
        
        self.update_styles()


__all__ = ['BulkTopPageUI']
