# -*- coding: utf-8 -*-
"""
单细胞分析顶层导航界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
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


class ScRNAseqTopPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.scRNAseq_top_page.findChild(QLabel, "scRNAseq_top_bg")
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
        for child in self.scRNAseq_top_page.findChildren(QPushButton):
            if child in [self.btn_select_path, self.btn_load, self.btn_select_rds_path, self.btn_load_rds] and hasattr(self, 'btn_select_path'):
                continue
            nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
            if child in nav_buttons:
                continue
            child.setStyleSheet(button_style)
        
        if hasattr(self, 'btn_select_path'):
            self.btn_select_path.setStyleSheet(get_stylesheet_for_widget('import_button'))
            self.btn_load.setStyleSheet(get_stylesheet_for_widget('import_button'))
            self.btn_select_rds_path.setStyleSheet(get_stylesheet_for_widget('import_button'))
            self.btn_load_rds.setStyleSheet(get_stylesheet_for_widget('import_button'))
        
        label_style = get_stylesheet_for_widget('label')
        for child in self.scRNAseq_top_page.findChildren(QLabel):
            if child.objectName() == "scRNAseq_top_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)
        
        title_label = self.scRNAseq_top_page.findChild(QLabel, "scRNAseq_top_title")
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
        for child in self.scRNAseq_top_page.findChildren(QWidget):
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
        
        h5ad_section_title = QLabel("h5ad数据")
        h5ad_section_title.setFont(QFont(subtitle_font, 14, QFont.Bold))
        h5ad_section_title.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        h5ad_section_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(h5ad_section_title)
        
        self.btn_select_path = create_styled_button("扫描数据路径", font_size=14, button_type='import', parent=panel)
        layout.addWidget(self.btn_select_path, alignment=Qt.AlignCenter)
        
        layout.addSpacing(15)
        
        self.h5ad_combo = create_styled_combo_box(parent=panel)
        self.h5ad_combo.setMinimumWidth(300)
        layout.addWidget(self.h5ad_combo, alignment=Qt.AlignCenter)
        
        layout.addSpacing(15)
        
        self.btn_load = create_styled_button("加载数据集", font_size=14, button_type='import', parent=panel)
        layout.addWidget(self.btn_load, alignment=Qt.AlignCenter)
        
        layout.addSpacing(30)
        
        rds_section_title = QLabel("rds数据 (Seurat)")
        rds_section_title.setFont(QFont(subtitle_font, 14, QFont.Bold))
        rds_section_title.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        rds_section_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(rds_section_title)
        
        self.btn_select_rds_path = create_styled_button("扫描rds路径", font_size=14, button_type='import', parent=panel)
        layout.addWidget(self.btn_select_rds_path, alignment=Qt.AlignCenter)
        
        layout.addSpacing(15)
        
        self.rds_combo = create_styled_combo_box(parent=panel)
        self.rds_combo.setMinimumWidth(300)
        layout.addWidget(self.rds_combo, alignment=Qt.AlignCenter)
        
        layout.addSpacing(15)
        
        self.btn_load_rds = create_styled_button("加载Seurat对象", font_size=14, button_type='import', parent=panel)
        layout.addWidget(self.btn_load_rds, alignment=Qt.AlignCenter)
        
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
        
        title_label = QLabel("基础表达类")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(30)
        
        initial_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'initial_analysis_layer.png')
        violin_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'violin_layer.png')
        target_bubble_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'sc_targetgene_bubble_layer.png')
        genelist_bubble_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'sc_genelist_bubble_layer.png')
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        
        self.btn_initial_analysis = create_styled_image_button("UMAP初步作图", initial_image_path, parent=panel)
        columns_layout.addWidget(self.btn_initial_analysis, alignment=Qt.AlignCenter)
        
        self.btn_violin_plot = create_styled_image_button("自定义小提琴图", violin_image_path, parent=panel)
        columns_layout.addWidget(self.btn_violin_plot, alignment=Qt.AlignCenter)
        
        self.btn_bubble_plot = create_styled_image_button("自定义气泡图", target_bubble_image_path, parent=panel)
        columns_layout.addWidget(self.btn_bubble_plot, alignment=Qt.AlignCenter)
        
        self.btn_gene_bubble_plot = create_styled_image_button("基因集气泡图", genelist_bubble_image_path, parent=panel)
        columns_layout.addWidget(self.btn_gene_bubble_plot, alignment=Qt.AlignCenter)
        
        layout.addLayout(columns_layout)
        
        layout.addStretch()
        
        return panel

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
        
        diff_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'diff_layer.png')
        hdwgcna_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'sc_hdwgcna_layer.png')
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        
        self.btn_diff_analysis = create_styled_image_button("差异分析", diff_image_path, parent=panel)
        columns_layout.addWidget(self.btn_diff_analysis, alignment=Qt.AlignCenter)
        
        self.btn_hdwgcna = create_styled_image_button("hdWGCNA分析", hdwgcna_image_path, parent=panel)
        columns_layout.addWidget(self.btn_hdwgcna, alignment=Qt.AlignCenter)
        
        layout.addLayout(columns_layout)
        
        layout.addStretch()
        
        return panel

    def _create_trajectory_panel(self, parent):
        """创建轨迹类分析面板内容"""
        panel, layout = create_styled_panel(parent=parent)
        layout.setContentsMargins(20, 20, 20, 20)
        
        styles = get_mod_styles()
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 16)
        mutant_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
        
        title_label = QLabel("轨迹类分析")
        title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        title_label.setStyleSheet(f"color: {mutant_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(30)
        
        stavia_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'sc_stavia_layer.png')
        monocle_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'NULL.png')
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        
        self.btn_stavia = create_styled_image_button("StaVIA分析", stavia_image_path, parent=panel)
        columns_layout.addWidget(self.btn_stavia, alignment=Qt.AlignCenter)
        
        self.btn_monocle = create_styled_image_button("Monocle分析", monocle_image_path, parent=panel)
        columns_layout.addWidget(self.btn_monocle, alignment=Qt.AlignCenter)
        
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
        
        drug_sensitivity_image_path = os.path.join(APPDATA_PATH, 'elements', 'page_pics', 'NULL.png')
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        columns_layout.setContentsMargins(20, 0, 20, 0)
        
        self.btn_drug_sensitivity = create_styled_image_button("GDSC药物敏感性分析", drug_sensitivity_image_path, parent=panel)
        columns_layout.addWidget(self.btn_drug_sensitivity, alignment=Qt.AlignCenter)
        
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
        self.scRNAseq_top_page = QWidget(self.parent)
        
        styles = get_mod_styles()
        paths = get_mod_paths()
        
        bg_label = QLabel(self.scRNAseq_top_page)
        bg_label.setObjectName("scRNAseq_top_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height, 
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()
        
        overlay = QWidget(self.scRNAseq_top_page)
        overlay.setObjectName("scRNAseq_top_overlay")
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
        
        self.nav_btn_analysis = create_navigation_button("基础表达类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_analysis)
        
        self.nav_btn_genelist = create_navigation_button("基因列表类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_genelist)
        
        self.nav_btn_trajectory = create_navigation_button("轨迹分析类", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_trajectory)
        
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
        
        title_label = QLabel("单细胞分析")
        title_label.setObjectName("scRNAseq_top_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)
        
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.scRNAseq_top_page, mod_instance)
        
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
        self.trajectory_panel = self._create_trajectory_panel(panels_container)
        self.other_panel = self._create_other_panel(panels_container)
        
        self.panels = {
            'data': self.data_panel,
            'analysis': self.analysis_panel,
            'genelist': self.genelist_panel,
            'trajectory': self.trajectory_panel,
            'other': self.other_panel
        }
        
        panels_layout.addWidget(self.data_panel)
        panels_layout.addWidget(self.analysis_panel)
        panels_layout.addWidget(self.genelist_panel)
        panels_layout.addWidget(self.trajectory_panel)
        panels_layout.addWidget(self.other_panel)
        
        content_layout.addWidget(panels_container)
        
        main_layout.addWidget(content_panel)
        
        self.show_panel('data')
        
        self.update_styles()


__all__ = ['ScRNAseqTopPageUI']
