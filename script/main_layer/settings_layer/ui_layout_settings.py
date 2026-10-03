# -*- coding: utf-8 -*-
"""
Settings界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_combo_box, create_styled_label, create_styled_panel,
    create_styled_checkbox, create_styled_setting_switch_row, create_styled_slider,
    SettingSliderSwitch
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.mod_config import get_startup_mod_name
from script.utils_layer.page_intersect import page_intersect

class SettingsPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.settings_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.settings_page.findChild(QLabel, "settings_bg")
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

        # 标题（突变色）
        title_label = self.settings_page.findChild(QLabel, "settings_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        # 半透明遮罩
        overlay = self.settings_page.findChild(QWidget, "settings_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        # 所有文字标签（含左侧大标题/小字/数值标签/开关行左侧字）统一用主题文字色
        label_style = get_stylesheet_for_widget('label')
        for child in self.settings_page.findChildren(QLabel):
            if child.objectName() == "settings_title":
                continue
            child.setStyleSheet(label_style)
        # 恢复标题专属颜色（避免被上面的 label 循环覆盖）
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        # 按钮（返回/扫描/确认/音乐按钮）
        button_style = get_stylesheet_for_widget('button')
        for child in self.settings_page.findChildren(QPushButton):
            child.setStyleSheet(button_style)

        # 下拉框（R内核 / 默认启动模组）
        combo_style = get_stylesheet_for_widget('combo')
        for child in self.settings_page.findChildren(QComboBox):
            child.setStyleSheet(combo_style)

        # 横向拉条（背景默认音量 / 按钮音效音量）
        slider_style = get_stylesheet_for_widget('slider')
        for child in self.settings_page.findChildren(QSlider):
            child.setStyleSheet(slider_style)

        # 面板（左右区域容器）
        panel_bg = styles.get('sub_panel_bg', 'rgba(30, 58, 95, 0.5)')
        panel_border = styles.get('sub_panel_border', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '8px')
        panel_style = f"background: {panel_bg}; border: 1px solid {panel_border}; border-radius: {panel_radius};"
        for child in self.settings_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

        # 滑块开关（自定义绘制）：重设三色
        for sw in self.settings_page.findChildren(SettingSliderSwitch):
            sw._on_color = QColor(styles.get('sub_mutant_color', '#FF6B35'))
            sw._off_color = QColor(styles.get('sub_border_color', '#1E3A5F'))
            sw._knob_color = QColor(styles.get('sub_text_color', '#87CEEB'))
            sw.update()

        # 顶部音乐控件容器（边框/底色）
        if hasattr(self, 'music_controller'):
            mc = self.music_controller
            container = getattr(mc, 'music_container', None)
            if container is not None:
                container.setStyleSheet(
                    f"background: {styles.get('sub_fill_color', 'rgba(50, 50, 80, 150)')}; border-radius: 5px;"
                )

        self.update_background()

    def create_page(self):
        self.settings_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.settings_page)
        bg_label.setObjectName("settings_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.settings_page)
        overlay.setObjectName("settings_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        # 顶部标题栏
        top_layout = QHBoxLayout()

        # 返回主页按钮 - 使用固定最小宽度
        self.btn_back_settings = create_styled_button("← 返回主页", font_size=12)
        self.btn_back_settings.setMinimumWidth(styles.get('back_button_min_width', 120))
        top_layout.addWidget(self.btn_back_settings)

        # 标题
        title_label = QLabel("设置选项")
        title_label.setObjectName("settings_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        # 使用MusicController创建音乐控件
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.settings_page, mod_instance)
        
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

        # 主内容区域 - 使用水平布局，左侧R配置，右侧功能开发中
        main_layout = QHBoxLayout()
        
        # 左侧面板 - R配置
        left_panel, left_layout = create_styled_panel()
        left_layout.setContentsMargins(20, 20, 20, 20)
        
        # R配置标题
        r_config_title = create_styled_label("R配置", font_size=16, bold=True)
        left_layout.addWidget(r_config_title)
        
        left_layout.addSpacing(10)
        
        # R内核选择标签
        r_kernel_label = create_styled_label("R内核路径", font_size=12, bold=False)
        left_layout.addWidget(r_kernel_label)
        
        # 扫描R内核按钮
        self.btn_scan_r_kernel = create_styled_button("扫描R内核", font_size=11, variant='sub')
        left_layout.addWidget(self.btn_scan_r_kernel)
        
        left_layout.addSpacing(5)
        
        # R内核下拉框
        self.r_kernel_combo = create_styled_combo_box()
        self.r_kernel_combo.setMinimumWidth(350)
        left_layout.addWidget(self.r_kernel_combo)
        
        left_layout.addSpacing(5)
        
        # R内核提示信息
        r_tip_label = create_styled_label("提示：选择R内核后，点击确认按钮保存设置", font_size=10, bold=False)
        r_tip_label.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        left_layout.addWidget(r_tip_label)
        
        left_layout.addSpacing(15)
        
        # 确认设置按钮
        self.btn_confirm_r_kernel = create_styled_button("设置R内核", font_size=12, variant='sub')
        left_layout.addWidget(self.btn_confirm_r_kernel)
        
        left_layout.addSpacing(20)
        
        # 当前R状态
        r_status_title = create_styled_label("当前R状态", font_size=14, bold=True)
        left_layout.addWidget(r_status_title)
        
        self.r_status_text = create_styled_label("未设置", font_size=11, bold=False)
        left_layout.addWidget(self.r_status_text)
        
        left_layout.addStretch()
        
        # 右侧面板 - 功能开发中
        right_panel, right_layout = create_styled_panel()
        right_layout.setContentsMargins(20, 20, 20, 20)
        
        right_title = create_styled_label("模组类设置", font_size= 16, bold=True)
        right_layout.addWidget(right_title)
        
        right_layout.addSpacing(20)
        
        # 全局音乐播放设置：启动时自动播放（滑块开关，右侧）
        music_setting_title = create_styled_label("全局音乐设置", font_size=13, bold=True)
        right_layout.addWidget(music_setting_title)
        
        right_layout.addSpacing(8)
        
        # 生成“文字 + 右侧滑块”设置行；row/slider 一并保存，便于绑定
        self.check_startup_music, self._startup_music_slider = create_styled_setting_switch_row(
            "背景音乐启动时自动播放",
            checked=False, parent=self.settings_page
        )
        right_layout.addWidget(self.check_startup_music)
        
        right_layout.addSpacing(6)
        
        music_hint = create_styled_label("关闭该选项后，程序启动时不会自动播放音乐", font_size=10, bold=False)
        music_hint.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(music_hint)
        
        right_layout.addSpacing(10)

        # 背景音乐默认音量（仿真音乐控件音量条的横向拉条）
        vol_label = create_styled_label("背景音乐默认音量", font_size=10, bold=False)
        vol_label.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(vol_label)

        right_layout.addSpacing(4)

        vol_row = QWidget(self.settings_page)
        vol_layout = QHBoxLayout(vol_row)
        vol_layout.setContentsMargins(0, 0, 0, 0)
        vol_layout.setSpacing(10)
        self.settings_volume_slider = create_styled_slider(Qt.Horizontal, vol_row, variant='sub')
        self.settings_volume_slider.setRange(0, 100)
        self.settings_volume_slider.setFixedWidth(180)
        vol_layout.addWidget(self.settings_volume_slider)
        self.settings_volume_label = create_styled_label("100", font_size=10, bold=False)
        self.settings_volume_label.setFixedWidth(28)
        self.settings_volume_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        vol_layout.addWidget(self.settings_volume_label)
        vol_layout.addStretch()
        right_layout.addWidget(vol_row)

        right_layout.addSpacing(6)

        vol_hint = create_styled_label("调节后立即同步到音乐音量，并作为下次启动的默认音量", font_size=10, bold=False)
        vol_hint.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(vol_hint)

        right_layout.addSpacing(10)

        # 点击音效开关（立即生效 + 重启生效）
        self.check_click_sound, self._click_sound_slider = create_styled_setting_switch_row(
            "点击音效",
            checked=False, parent=self.settings_page
        )
        right_layout.addWidget(self.check_click_sound)

        right_layout.addSpacing(6)

        click_hint = create_styled_label("开启后点击界面按钮会播放音效，立即生效", font_size=10, bold=False)
        click_hint.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(click_hint)

        right_layout.addSpacing(10)

        # 按钮音效音量（横向拉条，即时生效 + 重启生效）
        bvol_label = create_styled_label("按钮音效音量", font_size=10, bold=False)
        bvol_label.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(bvol_label)

        right_layout.addSpacing(4)

        bvol_row = QWidget(self.settings_page)
        bvol_layout = QHBoxLayout(bvol_row)
        bvol_layout.setContentsMargins(0, 0, 0, 0)
        bvol_layout.setSpacing(10)
        self.settings_click_volume_slider = create_styled_slider(Qt.Horizontal, bvol_row, variant='sub')
        self.settings_click_volume_slider.setRange(0, 100)
        self.settings_click_volume_slider.setFixedWidth(180)
        bvol_layout.addWidget(self.settings_click_volume_slider)
        self.settings_click_volume_label = create_styled_label("60", font_size=10, bold=False)
        self.settings_click_volume_label.setFixedWidth(28)
        self.settings_click_volume_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bvol_layout.addWidget(self.settings_click_volume_label)
        bvol_layout.addStretch()
        right_layout.addWidget(bvol_row)

        right_layout.addSpacing(6)

        bvol_hint = create_styled_label("调节后立即生效，并作为下次启动的按钮音效音量", font_size=10, bold=False)
        bvol_hint.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(bvol_hint)

        right_layout.addSpacing(10)

        # 角色音效开关（控制成功/警告/错误提示音，独立于点击音效）
        self.check_role_sound, self._role_sound_slider = create_styled_setting_switch_row(
            "角色音效",
            checked=False, parent=self.settings_page
        )
        right_layout.addWidget(self.check_role_sound)

        right_layout.addSpacing(6)

        role_hint = create_styled_label("开启后成功/警告/错误提示会播放角色音效，立即生效", font_size=10, bold=False)
        role_hint.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(role_hint)

        right_layout.addSpacing(10)

        # 角色音效音量（横向拉条，即时生效 + 重启生效）
        rvol_label = create_styled_label("角色音效音量", font_size=10, bold=False)
        rvol_label.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(rvol_label)

        right_layout.addSpacing(4)

        rvol_row = QWidget(self.settings_page)
        rvol_layout = QHBoxLayout(rvol_row)
        rvol_layout.setContentsMargins(0, 0, 0, 0)
        rvol_layout.setSpacing(10)
        self.settings_role_volume_slider = create_styled_slider(Qt.Horizontal, rvol_row, variant='sub')
        self.settings_role_volume_slider.setRange(0, 100)
        self.settings_role_volume_slider.setFixedWidth(180)
        rvol_layout.addWidget(self.settings_role_volume_slider)
        self.settings_role_volume_label = create_styled_label("100", font_size=10, bold=False)
        self.settings_role_volume_label.setFixedWidth(28)
        self.settings_role_volume_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rvol_layout.addWidget(self.settings_role_volume_label)
        rvol_layout.addStretch()
        right_layout.addWidget(rvol_row)

        right_layout.addSpacing(6)

        rvol_hint = create_styled_label("调节后立即生效，并作为下次启动的角色音效音量", font_size=10, bold=False)
        rvol_hint.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(rvol_hint)

        right_layout.addSpacing(22)
        
        # 默认启动模组设置：选择下次启动时默认加载的模组（不立即切换）
        mod_setting_title = create_styled_label("默认启动模组", font_size=13, bold=True)
        right_layout.addWidget(mod_setting_title)
        
        right_layout.addSpacing(8)
        
        mod_label = create_styled_label("启动时默认加载的模组：", font_size=10, bold=False)
        mod_label.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(mod_label)
        
        right_layout.addSpacing(4)
        
        self.startup_mod_combo = create_styled_combo_box(self.settings_page, variant='sub')
        self.startup_mod_combo.setFixedSize(220, 30)
        # 填充可用模组
        try:
            available_mods = global_mod_manager.get_available_mods()
        except Exception:
            available_mods = ["kurosaki_koyuki"]
        self.startup_mod_combo.addItems(available_mods)
        # 初始显示：当前配置的启动默认模组
        startup_mod = get_startup_mod_name("kurosaki_koyuki")
        idx = self.startup_mod_combo.findText(startup_mod)
        if idx >= 0:
            self.startup_mod_combo.setCurrentIndex(idx)
        right_layout.addWidget(self.startup_mod_combo)
        
        right_layout.addSpacing(6)
        
        mod_hint = create_styled_label("选择后不会立即切换，重启程序后生效", font_size=10, bold=False)
        mod_hint.setStyleSheet(f"color: {styles.get('sub_text_primary', '#87CEEB')};")
        right_layout.addWidget(mod_hint)
        
        right_layout.addStretch()
        
        # 添加到主布局
        main_layout.addWidget(left_panel, 1)
        main_layout.addSpacing(20)
        main_layout.addWidget(right_panel, 1)
        
        layout.addLayout(main_layout)
        
        # 保存stacked_widget引用
        self.stacked_widget = self.parent.stacked_widget if hasattr(self.parent, 'stacked_widget') else None
        
        return self.settings_page
