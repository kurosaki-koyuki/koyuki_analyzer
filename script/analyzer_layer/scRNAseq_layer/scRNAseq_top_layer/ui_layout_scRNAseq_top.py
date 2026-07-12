# -*- coding: utf-8 -*-
"""
单细胞分析顶层导航界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑

仿作主界面GUI，风格追溯到style和mod_manage
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget, create_styled_button, create_styled_combo_box, create_styled_slider, create_styled_panel, create_styled_text_edit
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
            if child in [self.btn_select_path, self.btn_load, self.btn_select_rds_path, self.btn_load_rds]:
                continue
            child.setStyleSheet(button_style)
        
        self.btn_select_path.setStyleSheet(get_stylesheet_for_widget('import_button'))
        self.btn_load.setStyleSheet(get_stylesheet_for_widget('import_button'))
        if hasattr(self, 'btn_select_rds_path'):
            self.btn_select_rds_path.setStyleSheet(get_stylesheet_for_widget('import_button'))
        if hasattr(self, 'btn_load_rds'):
            self.btn_load_rds.setStyleSheet(get_stylesheet_for_widget('import_button'))
        
        slider_style = get_stylesheet_for_widget('slider')
        for child in self.scRNAseq_top_page.findChildren(QSlider):
            child.setStyleSheet(slider_style)
        
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
        
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title_panel, title_layout = create_styled_panel()
        top_layout = QHBoxLayout()
        
        self.btn_back_single_cell = create_styled_button("← 返回主页", font_size=12)
        top_layout.addWidget(self.btn_back_single_cell)
        
        title_label = QLabel("单细胞分析")
        title_label.setObjectName("scRNAseq_top_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)
        
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.scRNAseq_top_page, mod_instance)
        
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
        
        title_layout.addLayout(top_layout)
        layout.addWidget(title_panel)
        
        main_content_layout = QHBoxLayout()
        
        left_panel, left_layout = create_styled_panel(fixed_width=220)
        
        subtitle_font = styles.get('sub_text_font', '幼圆')
        subtitle_font_size = styles.get('subtitle_font_size', 14)
        subtitle_color = styles.get('sub_text_color', '#87CEEB')
        
        data_title = QLabel("数据加载")
        data_title.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        data_title.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        data_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(data_title)
        
        h5ad_section_title = QLabel("h5ad数据")
        h5ad_section_title.setFont(QFont(subtitle_font, 11, QFont.Bold))
        h5ad_section_title.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        left_layout.addWidget(h5ad_section_title)
        
        self.btn_select_path = create_styled_button("扫描数据路径", font_size=12, button_type='import', parent=left_panel)
        left_layout.addWidget(self.btn_select_path)
        
        self.h5ad_combo = create_styled_combo_box(parent=left_panel)
        self.h5ad_combo.setMinimumWidth(180)
        left_layout.addWidget(self.h5ad_combo)
        
        self.btn_load = create_styled_button("加载数据集", font_size=12, button_type='import', parent=left_panel)
        left_layout.addWidget(self.btn_load)
        
        left_layout.addSpacing(15)
        
        rds_section_title = QLabel("rds数据 (Seurat)")
        rds_section_title.setFont(QFont(subtitle_font, 11, QFont.Bold))
        rds_section_title.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        left_layout.addWidget(rds_section_title)
        
        self.btn_select_rds_path = create_styled_button("扫描rds路径", font_size=12, button_type='import', parent=left_panel)
        left_layout.addWidget(self.btn_select_rds_path)
        
        self.rds_combo = create_styled_combo_box(parent=left_panel)
        self.rds_combo.setMinimumWidth(180)
        left_layout.addWidget(self.rds_combo)
        
        self.btn_load_rds = create_styled_button("加载Seurat对象", font_size=12, button_type='import', parent=left_panel)
        left_layout.addWidget(self.btn_load_rds)
        
        left_layout.addSpacing(15)
        
        status_title = QLabel("运行状态")
        status_title.setFont(QFont(subtitle_font, 12, QFont.Bold))
        status_title.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        status_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(status_title)
        
        self.status_text = create_styled_text_edit(read_only=True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setFont(get_font_for_widget('label', 10))
        self.status_text.setText("等待数据加载...")
        left_layout.addWidget(self.status_text)
        
        left_layout.addStretch()
        main_content_layout.addWidget(left_panel)
        
        analysis_panel, analysis_layout = create_styled_panel()
        analysis_layout.setContentsMargins(8, 8, 8, 8)
        analysis_layout.setSpacing(5)
        
        analysis_title = QLabel("分析工具")
        analysis_title.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold))
        analysis_title.setStyleSheet(f"color: {subtitle_color}; background: transparent;")
        analysis_title.setAlignment(Qt.AlignCenter)
        analysis_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        analysis_layout.addWidget(analysis_title)
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(10)
        
        btn_font_size = styles.get('button_font_size', 14)
        
        col1, col1_layout = create_styled_panel(variant='sub')
        col1_layout.setContentsMargins(8, 8, 8, 8)
        col1_layout.setSpacing(5)
        self.btn_initial_analysis = create_styled_button("初步分析", font_size=btn_font_size, parent=col1)
        col1_layout.addWidget(self.btn_initial_analysis, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col1)
        
        col2, col2_layout = create_styled_panel(variant='sub')
        col2_layout.setContentsMargins(8, 8, 8, 8)
        col2_layout.setSpacing(5)
        self.btn_violin_plot = create_styled_button("自定义小提琴图", font_size=btn_font_size, parent=col2)
        col2_layout.addWidget(self.btn_violin_plot, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col2)
        
        col3, col3_layout = create_styled_panel(variant='sub')
        col3_layout.setContentsMargins(8, 8, 8, 8)
        col3_layout.setSpacing(5)
        self.btn_bubble_plot = create_styled_button("自定义气泡图", font_size=btn_font_size, parent=col3)
        col3_layout.addWidget(self.btn_bubble_plot, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col3)
        
        col4, col4_layout = create_styled_panel(variant='sub')
        col4_layout.setContentsMargins(8, 8, 8, 8)
        col4_layout.setSpacing(5)
        self.btn_gene_bubble_plot = create_styled_button("基因集气泡图", font_size=btn_font_size, parent=col4)
        col4_layout.addWidget(self.btn_gene_bubble_plot, alignment=Qt.AlignCenter)
        self.btn_diff_analysis = create_styled_button("差异分析", font_size=btn_font_size, parent=col4)
        col4_layout.addWidget(self.btn_diff_analysis, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col4)
        
        col5, col5_layout = create_styled_panel(variant='sub')
        col5_layout.setContentsMargins(8, 8, 8, 8)
        col5_layout.setSpacing(5)
        self.btn_hdwgcna = create_styled_button("hdWGCNA分析", font_size=btn_font_size, parent=col5)
        col5_layout.addWidget(self.btn_hdwgcna, alignment=Qt.AlignCenter)
        columns_layout.addWidget(col5)
        
        analysis_layout.addLayout(columns_layout)
        
        main_content_layout.addWidget(analysis_panel)
        
        layout.addLayout(main_content_layout)
        
        self.update_styles()