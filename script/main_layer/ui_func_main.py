# -*- coding: utf-8 -*-
"""
主界面前端功能类 - 纯前端显示操作
负责主界面所有UI控件的显示更新、样式应用、图标同步等
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.mods_layer.emoji_function_for_mods import happy
from script.utils_layer.music_controller_fix import (
    sync_all_volume_sliders,
    sync_all_music_buttons
)
from script.utils_layer.gui_styles import get_main_gui_styles


class MainFunc:
    """主界面前端功能类 - 纯前端显示操作"""

    def __init__(self, main_ui):
        self.main_ui = main_ui

    # ---------- 模组样式应用 ----------

    def apply_mod_styles(self):
        """应用当前模组样式到主界面所有控件（纯显示，不处理音乐业务）"""
        new_styles = global_mod_manager.get_current_styles()
        main_styles = get_main_gui_styles()

        # 解构主界面样式
        primary_color = main_styles['primary_color']
        title_font = main_styles['title_font']
        label_font = main_styles['label_font']
        button_font = main_styles['button_font']
        button_stylesheet = main_styles['button_stylesheet']
        combo_stylesheet = main_styles['combo_stylesheet']
        slider_stylesheet = main_styles['slider_stylesheet']
        music_btn_stylesheet = main_styles['music_btn_stylesheet']

        self._update_window_title(new_styles.get('window_title', "小雪生信工具箱"))
        self._update_title_label(new_styles, primary_color, title_font)
        self._update_subtitle_labels(new_styles, label_font, primary_color)
        self._update_mod_controls(combo_stylesheet, new_styles, primary_color)
        self._update_music_controls_style(music_btn_stylesheet, slider_stylesheet)
        self._update_all_buttons(new_styles, button_font, button_stylesheet)
        self._update_donate_button(new_styles)

    def _update_window_title(self, title):
        """更新窗口标题"""
        self.main_ui.setWindowTitle(title)

    def _update_title_label(self, styles, primary_color, title_font):
        """更新主标题标签"""
        if not hasattr(self.main_ui, 'title_label'):
            return
        label = self.main_ui.title_label
        label.setText(styles.get('main_title', "生信工具一览"))
        label.setFont(QFont(title_font, styles.get('title_font_size', 20), QFont.Bold))
        label.setStyleSheet(f"color: {primary_color}; background: transparent;")
        label.setGeometry(
            int(self.main_ui.screen_width * styles.get('title_x', 0.65)),
            int(self.main_ui.screen_height * styles.get('title_y', 0.18)),
            int(self.main_ui.screen_width * styles.get('title_width', 0.3)),
            styles.get('title_height', 50)
        )

    def _update_subtitle_labels(self, styles, label_font, primary_color):
        """更新副标题标签"""
        subtitle_font = styles.get('subtitle_font', label_font)
        subtitle_font_size = styles.get('subtitle_font_size', 14)
        subtitle_color = styles.get('subtitle_color', primary_color)
        subtitle_background = styles.get('subtitle_background', 'transparent')
        subtitle_bold = styles.get('subtitle_bold', True)
        weight = QFont.Bold if subtitle_bold else QFont.Normal

        subtitle_configs = [
            ('left_title_label', 'single_cell_title', "单细胞分析",
             'left_title_x', 'left_title_y', 'left_title_width', 'left_title_height'),
            ('right_title_label', 'bulk_title', "bulk分析",
             'right_title_x', 'right_title_y', 'right_title_width', 'right_title_height'),
            ('tools_title_label', 'tools_title', "通用小工具",
             'tools_title_x', 'tools_title_y', 'tools_title_width', 'tools_title_height'),
        ]

        for attr, text_key, default_text, x_key, y_key, w_key, h_key in subtitle_configs:
            if not hasattr(self.main_ui, attr):
                continue
            label = getattr(self.main_ui, attr)
            label.setText(styles.get(text_key, default_text))
            label.setFont(QFont(subtitle_font, subtitle_font_size, weight))
            label.setStyleSheet(f"color: {subtitle_color}; background: {subtitle_background};")
            label.setGeometry(
                int(self.main_ui.screen_width * styles.get(x_key, 0.68 if 'left' in attr else 0.78 if 'right' in attr else 0.88)),
                int(self.main_ui.screen_height * styles.get(y_key, 0.28)),
                styles.get(w_key, 180),
                styles.get(h_key, 30)
            )

    def _update_mod_controls(self, combo_stylesheet, styles, primary_color):
        """更新模组选择控件样式"""
        if hasattr(self.main_ui, 'mod_combo'):
            self.main_ui.mod_combo.setStyleSheet(combo_stylesheet)

        if hasattr(self.main_ui, 'mod_label'):
            mod_label_color = styles.get('mod_label_color', primary_color)
            mod_label_bg = styles.get('mod_label_background', 'transparent')
            self.main_ui.mod_label.setStyleSheet(f"color: {mod_label_color}; background: {mod_label_bg};")

    def _update_music_controls_style(self, music_btn_stylesheet, slider_stylesheet):
        """更新音乐控件样式"""
        if hasattr(self.main_ui, 'music_btn'):
            self.main_ui.music_btn.setStyleSheet(music_btn_stylesheet)

        if hasattr(self.main_ui, 'volume_slider'):
            self.main_ui.volume_slider.setStyleSheet(slider_stylesheet)

    def _update_all_buttons(self, styles, button_font, button_stylesheet):
        """批量更新所有功能按钮的样式（位置更新委托给layout层）"""
        btn_font = QFont(button_font, styles.get('button_font_size', 16), QFont.Bold)
        
        buttons = [
            'btn_single_cell_main', 'btn_bulk_main', 'btn_venn'
        ]
        
        for btn_name in buttons:
            if not hasattr(self.main_ui, btn_name):
                continue
            btn = getattr(self.main_ui, btn_name)
            btn.setFont(btn_font)
            btn.setStyleSheet(button_stylesheet)
        
        if hasattr(self.main_ui, 'update_button_positions'):
            self.main_ui.update_button_positions(styles)

    def _update_donate_button(self, styles):
        """更新打赏按钮位置"""
        if not hasattr(self.main_ui, 'btn_donate'):
            return
        self.main_ui.btn_donate.move(
            int(self.main_ui.screen_width * styles.get('donate_button_x', 0.725)),
            int(self.main_ui.screen_height * styles.get('donate_button_y', 0.80))
        )

    # ---------- 视频背景 ----------

    def reload_video_background(self):
        """重新加载并播放视频背景（纯显示）"""
        if not hasattr(self.main_ui, 'video_bg'):
            return

        self.main_ui.video_bg.stop()
        new_paths = global_mod_manager.get_current_paths()
        VideoBackgroundClass = global_mod_manager.get_current_mod().get_video_background_class()
        self.main_ui.video_bg = VideoBackgroundClass(
            self.main_ui.home_page,
            self.main_ui.screen_width,
            self.main_ui.screen_height,
            startup_video=new_paths['STARTUP_VIDEO'],
            return_video=new_paths['STARTUP_RETURN_VIDEO'],
            remain_video=new_paths['STARTREMAIN_VIDEO']
        )
        self.main_ui.video_bg.set_label(self.main_ui.video_bg_label)
        self.main_ui.video_bg.play()

    # ---------- 子界面样式 ----------

    def update_subpage_styles(self):
        """更新所有子界面的样式和背景 - 自动检测所有以_ui结尾的属性"""
        for attr_name in dir(self.main_ui):
            if attr_name.endswith('_ui'):
                ui = getattr(self.main_ui, attr_name)
                if hasattr(ui, 'update_background'):
                    ui.update_background()
                if hasattr(ui, 'update_styles'):
                    ui.update_styles()

    # ---------- 音乐控件显示 ----------

    def update_music_icon(self, is_playing):
        """更新音乐按钮图标（纯显示）"""
        paths = global_mod_manager.get_current_paths()
        sync_all_music_buttons(self.main_ui, is_playing, paths)

    def sync_volume_sliders(self, value):
        """同步所有音量滑块（纯显示）"""
        sync_all_volume_sliders(self.main_ui, value)

    # ---------- 通用弹窗 ----------

    def show_donate_message(self):
        """显示打赏信息弹窗"""
        donate_message = """
        感谢您使用小雪生信工具箱！
        
        如果您觉得这个工具对您有帮助，
        可以考虑打赏作者以支持后续开发。
        
        您的每一份支持都是对开发者最大的鼓励！
        """
        happy(self.main_ui, donate_message)
