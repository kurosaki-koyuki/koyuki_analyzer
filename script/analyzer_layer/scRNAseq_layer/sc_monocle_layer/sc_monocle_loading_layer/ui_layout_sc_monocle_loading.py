# -*- coding: utf-8 -*-
"""
scRNAseq Monocle数据加载子层UI布局脚本
左侧：扫描+下拉框+加载控件套装，上方标题处加questions_btn提示
右侧：标签页出图区域，加载后自动生成带轨迹的伪时间测试图
背景由主层容器统一管理，子层使用透明背景
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_label,
    create_styled_panel, create_styled_text_edit, create_styled_tab_widget,
    create_styled_image_tab, create_questions_button
)
from script.mods_layer.mod_manager import global_mod_manager


class ScMonocleLoadingPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.sc_monocle_loading_page = None
        self.create_page()

    def update_background(self):
        """更新背景图（子页面不处理，由主容器统一管理）"""
        pass

    def update_styles(self):
        """更新子层样式（mod切换时由主层递归调用）"""
        styles = get_mod_styles()

        title_label = self.sc_monocle_loading_page.findChild(QLabel, "sc_monocle_loading_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};"
            )

        button_style = get_stylesheet_for_widget('button')
        for child in self.sc_monocle_loading_page.findChildren(QPushButton):
            if child.objectName() and (child.objectName().startswith("styled_btn_") or child.objectName().startswith("number_input_btn_")):
                continue
            child.setStyleSheet(button_style)

        if hasattr(self, 'btn_scan_rds'):
            self.btn_scan_rds.setStyleSheet(get_stylesheet_for_widget('import_button'))
        if hasattr(self, 'btn_load_rds'):
            self.btn_load_rds.setStyleSheet(get_stylesheet_for_widget('import_button'))

        combo_style = get_stylesheet_for_widget('combo')
        for child in self.sc_monocle_loading_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        text_edit_style = get_stylesheet_for_widget('text_edit')
        for child in self.sc_monocle_loading_page.findChildren(QTextEdit):
            child.setStyleSheet(text_edit_style)

        label_style = get_stylesheet_for_widget('label')
        for child in self.sc_monocle_loading_page.findChildren(QLabel):
            if child.objectName() != "sc_monocle_loading_title" and not child.objectName().startswith("styled_image_label"):
                child.setStyleSheet(label_style)

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.sc_monocle_loading_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        self.update_background()

    def create_page(self):
        self.sc_monocle_loading_page = QWidget(self.parent)
        self.sc_monocle_loading_page.setStyleSheet("background: transparent;")

        styles = get_mod_styles()

        layout = QVBoxLayout(self.sc_monocle_loading_page)
        layout.setContentsMargins(20, 20, 20, 20)

        # 顶部布局：标题 + 音乐控制器
        top_layout = QHBoxLayout()

        title_label = QLabel("Monocle数据加载")
        title_label.setObjectName("sc_monocle_loading_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # music_controller（按项目规则保留，供全局同步函数发现）
        MusicControllerClass = global_mod_manager.get_current_mod().get_music_controller_class()
        mod_instance = global_mod_manager.get_current_mod()
        self.music_controller = MusicControllerClass(self.sc_monocle_loading_page, mod_instance)

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

        # 主区域：左侧加载控件 + 右侧标签页
        main_layout = QHBoxLayout()

        # 左侧加载控件面板
        left_panel, left_panel_layout = create_styled_panel(parent=self.sc_monocle_loading_page)
        left_panel.setMinimumWidth(340)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # 加载区标题 + questions_btn 提示
        loading_title_layout = QHBoxLayout()
        loading_title = create_styled_label("加载伪时间CDS对象", font_size=14, bold=True)
        loading_title_layout.addWidget(loading_title)

        # questions_btn：强调rds文件应放在正确的相对路径下
        scan_path_hint = create_questions_button("""伪时间rds文件存放路径说明

请将初筛轨迹类阶段四导出的CDS对象（带伪时间）rds文件
存放到以下相对路径下：

    appdata\\analyze_data\\pseudo_rds_data\\

文件命名建议：
    {数据集名}_cds_with_pseudotime.rds

操作流程：
1. 点击"扫描rds路径"按钮扫描上述目录
2. 从下拉框选择要加载的rds文件
3. 点击"加载并生成测试图"按钮
4. 程序会自动调用R脚本生成带轨迹的伪时间测试图
5. 测试图保存路径：
   OUTPUT\\monocle3\\loading_test\\{数据集名}\\

注意：
- rds文件必须来自初筛轨迹类阶段四的导出
- rds文件中必须包含有效的伪时间数据
- 如果文件不在指定路径下，扫描将提示路径不存在""")
        loading_title_layout.addWidget(scan_path_hint)

        left_panel_layout.addLayout(loading_title_layout)

        left_panel_layout.addSpacing(10)

        # 扫描按钮
        self.btn_scan_rds = create_styled_button("扫描rds路径", font_size=12, button_type='import')
        left_panel_layout.addWidget(self.btn_scan_rds)

        left_panel_layout.addSpacing(8)

        # 下拉框
        rds_combo_label = create_styled_label("选择rds文件", font_size=10, bold=True)
        left_panel_layout.addWidget(rds_combo_label)
        self.rds_combo = create_styled_combo_box()
        self.rds_combo.setMinimumWidth(300)
        self.rds_combo.addItem("请先扫描rds路径")
        left_panel_layout.addWidget(self.rds_combo)

        left_panel_layout.addSpacing(15)

        # 加载按钮
        self.btn_load_rds = create_styled_button("▶ 加载并生成测试图", font_size=12, button_type='run')
        left_panel_layout.addWidget(self.btn_load_rds)

        left_panel_layout.addSpacing(20)

        left_panel_layout.addWidget(create_styled_label("━" * 20, font_size=10))

        left_panel_layout.addSpacing(10)

        # 日志区
        log_title = create_styled_label("运行日志", font_size=12, bold=True)
        left_panel_layout.addWidget(log_title)

        self.loading_log = create_styled_text_edit(read_only=True, variant='sub')
        self.loading_log.setMaximumHeight(120)
        left_panel_layout.addWidget(self.loading_log)

        left_panel_layout.addSpacing(10)

        # 数据信息区
        data_info_title = create_styled_label("数据信息", font_size=12, bold=True)
        left_panel_layout.addWidget(data_info_title)

        self.data_info_text = create_styled_text_edit(read_only=True)
        self.data_info_text.setMaximumHeight(100)
        left_panel_layout.addWidget(self.data_info_text)

        left_panel_layout.addStretch()

        main_layout.addWidget(left_panel, 1)

        # 右侧标签页出图区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.loading_plot_tabs = create_styled_tab_widget()

        # 测试图标签页（带轨迹的伪时间图）
        _, self.test_plot_label = create_styled_image_tab(
            self.loading_plot_tabs,
            "伪时间测试图(带轨迹)",
            default_text="请加载rds文件后自动生成测试图"
        )

        right_layout.addWidget(self.loading_plot_tabs)
        main_layout.addWidget(right_panel, 2)

        layout.addLayout(main_layout)

        self.update_styles()

        return self.sc_monocle_loading_page
