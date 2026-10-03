# -*- coding: utf-8 -*-
"""
CellChat数据加载类界面UI布局脚本
用于加载已有的CellChat RDS文件并查看相关结果
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_line_edit,
    create_styled_label, create_styled_panel, create_styled_list_widget,
    create_styled_text_edit, create_styled_tab_widget, create_styled_image_tab,
    create_styled_checkbox, create_questions_button
)
from script.mods_layer.mod_manager import global_mod_manager


class ScCellChatLoadingPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_cellchat_loading_page = None
        self.music_controller = None
        self.create_page()

    def update_styles(self):
        """更新样式"""
        styles = get_mod_styles()
        
        # 标题样式
        title_label = self.sc_cellchat_loading_page.findChild(QLabel, "sc_cellchat_loading_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};"
            )

    def create_page(self):
        self.sc_cellchat_loading_page = QWidget(self.parent)
        self.sc_cellchat_loading_page.setStyleSheet("background: transparent;")
        
        styles = get_mod_styles()

        layout = QVBoxLayout(self.sc_cellchat_loading_page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # ========== 顶部：标题 + 音乐控制器 ==========
        top_layout = QHBoxLayout()

        title_label = QLabel("CellChat数据加载")
        title_label.setObjectName("sc_cellchat_loading_title")
        title_label.setFont(get_font_for_widget('button', 28, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # music_controller
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.sc_cellchat_loading_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub'
        )

        music_container_x = styles.get('music_container_x', 0.85)
        music_container_y = styles.get('music_container_y', 15)
        if isinstance(music_container_x, float):
            music_container_x = int(self.screen_width * music_container_x)
        music_container.move(music_container_x, music_container_y)

        top_layout.addWidget(music_container)

        top_layout.setStretch(0, 3)
        top_layout.setStretch(1, 1)
        layout.addLayout(top_layout)
        
        # 主区域：左侧参数面板 + 右侧标签页
        main_layout = QHBoxLayout()
        
        # ========== 左侧参数面板 ==========
        left_panel, left_panel_layout = create_styled_panel(parent=self.sc_cellchat_loading_page)
        left_panel.setMinimumWidth(320)
        
        # 数据信息区
        info_title = create_styled_label("数据加载", font_size=14, bold=True)
        left_panel_layout.addWidget(info_title)
        
        self.data_info_text = create_styled_text_edit(read_only=True, variant='sub')
        self.data_info_text.setMaximumHeight(80)
        self.data_info_text.setPlaceholderText("请加载CellChat RDS文件")
        left_panel_layout.addWidget(self.data_info_text)
        
        left_panel_layout.addSpacing(10)
        
        # 扫描路径设置
        path_label = create_styled_label("扫描路径", font_size=10, bold=True)
        left_panel_layout.addWidget(path_label)
        
        self.input_scan_path = create_styled_line_edit()
        self.input_scan_path.setText(r"appdata\analyze_data\cellchat_rds_data")
        self.input_scan_path.setReadOnly(True)
        left_panel_layout.addWidget(self.input_scan_path)
        
        left_panel_layout.addSpacing(10)
        
        # 扫描按钮
        self.btn_scan = create_styled_button("▶ 扫描RDS文件", font_size=12, button_type='run')
        left_panel_layout.addWidget(self.btn_scan)
        
        left_panel_layout.addSpacing(10)
        
        # RDS文件列表
        rds_label = create_styled_label("可用RDS文件", font_size=10, bold=True)
        left_panel_layout.addWidget(rds_label)
        
        self.list_rds_files = create_styled_list_widget(fixed_height=150, multi_selection=False)
        left_panel_layout.addWidget(self.list_rds_files)
        
        left_panel_layout.addSpacing(10)
        
        # 加载按钮
        self.btn_load = create_styled_button("▶ 加载选中RDS", font_size=12, button_type='run')
        self.btn_load.setEnabled(False)
        left_panel_layout.addWidget(self.btn_load)
        
        left_panel_layout.addStretch()
        main_layout.addWidget(left_panel, 1)
        
        # ========== 右侧标签页区域 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.loading_tabs = create_styled_tab_widget()
        
        # 通讯数量图标签页
        _, self.loading_count_image_label = create_styled_image_tab(
            self.loading_tabs,
            "通讯数量图",
            default_text="请加载CellChat RDS文件后显示通讯数量图"
        )
        
        # 通讯强度图标签页
        _, self.loading_weight_image_label = create_styled_image_tab(
            self.loading_tabs,
            "通讯强度图",
            default_text="请加载CellChat RDS文件后显示通讯强度图"
        )
        
        # 通路信息表标签页
        self.loading_info_tab = QWidget()
        loading_info_layout = QVBoxLayout(self.loading_info_tab)
        loading_info_label = create_styled_label("通路信息表格", font_size=12, bold=True)
        loading_info_layout.addWidget(loading_info_label)
        
        self.table_loading_info = QTableWidget()
        self.table_loading_info.setStyleSheet("""
            QTableWidget {
                gridline-color: #1E3A5F;
                background-color: rgba(30, 58, 95, 0.2);
                color: #87CEEB;
                border: 1px solid #1E3A5F;
            }
            QHeaderView::section {
                background-color: rgba(30, 58, 95, 0.5);
                color: #87CEEB;
                padding: 4px;
                border: 1px solid #1E3A5F;
            }
        """)
        self.table_loading_info.setColumnCount(3)
        self.table_loading_info.setHorizontalHeaderLabels(["通路", "p值", "通信强度"])
        self.table_loading_info.horizontalHeader().setStretchLastSection(True)
        loading_info_layout.addWidget(self.table_loading_info)
        
        self.loading_tabs.addTab(self.loading_info_tab, "通路信息表")
        
        right_layout.addWidget(self.loading_tabs)
        main_layout.addWidget(right_panel, 1)
        
        layout.addLayout(main_layout)
        
        self.update_styles()
        
        return self.sc_cellchat_loading_page
