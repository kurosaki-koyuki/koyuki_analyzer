# -*- coding: utf-8 -*-
"""
scRNAseq Monocle目的基因分析子层UI布局脚本
负责创建控件、规划窗口布局、设置样式尺寸
完全不写按钮点击、触发逻辑
背景由主层容器统一管理，子层使用透明背景
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_label, create_styled_panel, create_styled_button,
    create_styled_text_edit, create_styled_combo_box, create_styled_tab_widget,
    create_styled_image_tab, create_zoomable_image_label
)
from script.mods_layer.mod_manager import global_mod_manager


class ScMonocleTargetgenePageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_monocle_targetgene_page = None
        self.create_page()

    def update_background(self):
        """更新背景图（子页面不处理，由主容器统一管理）"""
        pass

    def update_styles(self):
        """更新子层样式（mod切换时由主层递归调用）"""
        styles = get_mod_styles()

        title_label = self.sc_monocle_targetgene_page.findChild(QLabel, "sc_monocle_targetgene_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};"
            )

        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_monocle_targetgene_page.findChildren(QLabel):
            if child.objectName() != "sc_monocle_targetgene_title":
                child.setStyleSheet(label_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_monocle_targetgene_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        if hasattr(self, 'btn_run_plot'):
            self.btn_run_plot.setStyleSheet(get_stylesheet_for_widget('run_button'))

        primary_color = styles.get('sub_text_color', styles.get('text_color', '#87CEEB'))
        secondary_color = styles.get('sub_border_color', styles.get('border_color', '#1E3A5F'))
        dark_bg = styles.get('sub_fill_alt', styles.get('fill_alt', 'rgba(30, 58, 95, 0.6)'))
        hover_color = styles.get('sub_hover_color', styles.get('hover_color', 'rgba(30, 58, 95, 0.5)'))
        tab_selected_bg = styles.get('sub_active_color', styles.get('active_color', 'rgba(135, 206, 235, 0.2)'))
        tab_style = f"""
            QTabWidget::tab-bar {{
                alignment: left;
            }}
            QTabBar::tab {{
                color: {primary_color};
                background: {dark_bg};
                padding: 5px 15px;
                border: 1px solid {secondary_color};
                border-bottom: none;
            }}
            QTabBar::tab:hover {{
                background: {hover_color};
            }}
            QTabBar::tab:selected {{
                background: {tab_selected_bg};
            }}
            QTabWidget::pane {{
                border: 1px solid {secondary_color};
                background: rgba(0, 0, 0, 0.3);
            }}
        """
        if hasattr(self, 'plot_tabs'):
            self.plot_tabs.setStyleSheet(tab_style)

        self.update_background()

    def create_page(self):
        self.sc_monocle_targetgene_page = QWidget(self.parent)
        self.sc_monocle_targetgene_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()

        layout = QVBoxLayout(self.sc_monocle_targetgene_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== 顶部：标题 + 音乐控制器 ==========
        top_layout = QHBoxLayout()

        title_label = QLabel("Monocle目的基因分析")
        title_label.setObjectName("sc_monocle_targetgene_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.sc_monocle_targetgene_page, mod_instance)

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

        # ========== 主区域：左侧参数 + 右侧标签页 ==========
        main_layout = QHBoxLayout()

        # ========== 左侧参数面板 ==========
        left_panel, left_panel_layout = create_styled_panel(parent=self.sc_monocle_targetgene_page)
        left_panel.setMinimumWidth(400)
        left_panel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        left_panel_layout.addSpacing(15)

        gene_label = create_styled_label("目的基因列表（每行一个基因）", font_size=11, bold=True)
        left_panel_layout.addWidget(gene_label)

        self.gene_input_edit = create_styled_text_edit(read_only=False)
        self.gene_input_edit.setPlaceholderText("APOD\nGFAP\nS100B")
        self.gene_input_edit.setMaximumHeight(100)
        left_panel_layout.addWidget(self.gene_input_edit)

        left_panel_layout.addSpacing(10)

        yaxis_label = create_styled_label("Y轴数据格式", font_size=11, bold=True)
        left_panel_layout.addWidget(yaxis_label)

        self.yaxis_combo = create_styled_combo_box()
        self.yaxis_combo.addItem("count", "count")
        self.yaxis_combo.addItem("log2(count+1)", "log2")
        self.yaxis_combo.addItem("normalized", "normalized")
        left_panel_layout.addWidget(self.yaxis_combo)

        left_panel_layout.addSpacing(10)

        anno_label = create_styled_label("着色分组列（可选）", font_size=11, bold=True)
        left_panel_layout.addWidget(anno_label)

        self.anno_column_combo = create_styled_combo_box()
        self.anno_column_combo.addItem("不分组（按伪时间着色）", "")
        left_panel_layout.addWidget(self.anno_column_combo)

        left_panel_layout.addSpacing(20)

        self.btn_run_plot = create_styled_button("▶ 绘制伪时间趋势图", font_size=12, button_type='run')
        self.btn_run_plot.setEnabled(False)
        left_panel_layout.addWidget(self.btn_run_plot)

        left_panel_layout.addStretch()

        info_label = create_styled_label("数据信息", font_size=11, bold=True)
        left_panel_layout.addWidget(info_label)

        self.data_info_text = create_styled_text_edit(read_only=True)
        self.data_info_text.setMaximumHeight(60)
        left_panel_layout.addWidget(self.data_info_text)

        left_panel_layout.addSpacing(10)

        log_label = create_styled_label("运行日志", font_size=11, bold=True)
        left_panel_layout.addWidget(log_label)

        self.log_text_edit = create_styled_text_edit(read_only=True)
        self.log_text_edit.setMaximumHeight(100)
        left_panel_layout.addWidget(self.log_text_edit)

        main_layout.addWidget(left_panel)

        # ========== 右侧标签页区域 ==========
        right_panel, right_panel_layout = create_styled_panel(parent=self.sc_monocle_targetgene_page)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.plot_tabs = create_styled_tab_widget()

        self.plot_page, self.plot_image_label = create_styled_image_tab(
            self.plot_tabs, 
            "伪时间趋势图",
            parent=right_panel,
            default_text="请先加载CDS数据并输入基因名称",
            data_hint_template="数据: {dataset_name}\n请输入基因名称并点击「绘制伪时间趋势图」"
        )

        right_panel_layout.addWidget(self.plot_tabs, 1)

        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.sc_monocle_targetgene_page

    def update_anno_columns(self, columns):
        """更新注释列下拉框选项"""
        current_idx = self.anno_column_combo.currentIndex()
        self.anno_column_combo.clear()
        self.anno_column_combo.addItem("不分组（按伪时间着色）", "")
        for col in columns:
            self.anno_column_combo.addItem(col, col)
        self.anno_column_combo.setCurrentIndex(current_idx)