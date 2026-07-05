# -*- coding: utf-8 -*-
"""
主界面功能绑定脚本 - 全权负责粘合内外
只包含主界面相关的功能绑定（视频播放、页面导航、打赏等）
音乐控制完全由模组的MusicController处理
支持动态切换模组，从模组管理器获取当前模组的资源和功能
"""

from script.utils_layer.import_config import *
from script.main_layer import MainWindowUI
from script.main_layer.ui_func_main import MainFunc
from script.mods_layer.mod_manager import global_mod_manager
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong
from script.utils_layer.music_controller_fix import (
    sync_all_volume_sliders,
    get_all_music_controllers,
    update_music_button_icon,
    validate_music_controller_state,
    sync_all_music_buttons,
    fix_music_controller_bindings
)
from script.utils_layer.page_intersect import page_intersect


# ========================================
# 主窗口功能绑定类
# ========================================
class MainWindowBind(MainWindowUI):
    """主窗口功能绑定类 - 负责绑定主界面GUI控件与功能"""

    def __init__(self):
        super().__init__()
        self.func = MainFunc(self)
        self.init_bindings()
        self.init_variables()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_mod_selection()
        self.bind_page_navigation()
        self.bind_general_tools()

        # 初始化音量与音乐播放
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player') and hasattr(self, 'volume_slider'):
            initial_volume = self.volume_slider.value()
            mod_instance.global_music_player.set_volume(initial_volume / 100.0)
            mod_instance.on_load(auto_play=True)
            self.func.update_music_icon(True)

        mod_instance = global_mod_manager.get_current_mod()
        ClickFilterClass = mod_instance.get_click_filter_class()
        self.click_filter = ClickFilterClass(mod_instance.global_sound_player)
        self.installEventFilter(self.click_filter)
        self._install_click_filter_recursively(self)

    def _install_click_filter_recursively(self, widget):
        """递归安装点击音效过滤器到所有子控件"""
        try:
            if widget and hasattr(widget, 'installEventFilter'):
                widget.installEventFilter(self.click_filter)
            if hasattr(widget, 'children'):
                for child in widget.children():
                    self._install_click_filter_recursively(child)
        except Exception as e:
            print(f"安装点击音效过滤器失败: {e}")

    def init_variables(self):
        """初始化变量"""
        paths = global_mod_manager.get_current_paths()
        VideoBackgroundClass = global_mod_manager.get_current_mod().get_video_background_class()
        self.video_bg = VideoBackgroundClass(
            self.home_page,
            self.screen_width,
            self.screen_height,
            startup_video=paths['STARTUP_VIDEO'],
            return_video=paths['STARTUP_RETURN_VIDEO'],
            remain_video=paths['STARTREMAIN_VIDEO']
        )

        QTimer.singleShot(100, self.init_video_background)

    def bind_mod_selection(self):
        """绑定模组选择"""
        if hasattr(self, 'mod_combo'):
            self.mod_combo.currentTextChanged.connect(self.switch_mod)

    def switch_mod(self, mod_name):
        """切换模组"""
        try:
            # 保存当前音乐播放状态
            old_mod_instance = global_mod_manager.get_current_mod()
            old_music_playing = False
            old_music_volume = 1.0
            if hasattr(old_mod_instance, 'global_music_player'):
                old_music_playing = old_mod_instance.global_music_player.is_playing
                old_music_volume = old_mod_instance.global_music_player.get_volume()

            if global_mod_manager.set_current_mod(mod_name):
                print(f"已切换到模组: {mod_name}")
                self.reload_mod_resources(old_music_playing, old_music_volume)
            else:
                print(f"切换模组失败: {mod_name}")
        except Exception as e:
            print(f"切换模组异常: {e}")

    def reload_mod_resources(self, old_music_playing=False, old_music_volume=1.0):
        """重新加载模组资源 - 业务编排：调用func更新UI + 处理音乐业务"""
        try:
            new_paths = global_mod_manager.get_current_paths()

            # 1. 应用UI样式（委托给func层）
            self.func.apply_mod_styles()

            # 2. 重新加载视频背景（委托给func层）
            self.func.reload_video_background()

            # 3. 更新子界面样式（委托给func层）
            self.func.update_subpage_styles()

            # 4. 更新音效资源和点击过滤器（业务层）
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_sound_player'):
                click_sound = new_paths.get('UI_CLICK_SOUND')
                if os.path.exists(click_sound):
                    mod_instance.global_sound_player.load_sound(click_sound, "click")

                # 重新创建点击过滤器
                ClickFilterClass = mod_instance.get_click_filter_class()
                self.click_filter = ClickFilterClass(mod_instance.global_sound_player)
                self.installEventFilter(self.click_filter)
                self._install_click_filter_recursively(self)

            # 5. 音乐播放状态恢复（业务层）
            if hasattr(mod_instance, 'global_music_player'):
                # 加载新模组的音乐资源但不自动播放
                mod_instance.on_load(auto_play=False)

                # 恢复之前的音乐播放状态
                if old_music_playing:
                    mod_instance.global_music_player.play()
                    self.func.update_music_icon(True)
                else:
                    self.func.update_music_icon(False)

                # 恢复之前的音量
                mod_instance.global_music_player.set_volume(old_music_volume)

            print("模组资源重新加载完成")
        except Exception as e:
            print(f"重新加载模组资源失败: {e}")

    def bind_page_navigation(self):
        """绑定页面导航"""
        print("[UI_Bind] 开始绑定页面导航按钮")
        
        if hasattr(self, 'btn_single_cell_main'):
            print(f"[UI_Bind] btn_single_cell_main 存在，尝试绑定...")
            self.btn_single_cell_main.clicked.connect(lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page'))
            print(f"[UI_Bind] btn_single_cell_main 绑定成功")
        else:
            print(f"[UI_Bind] btn_single_cell_main 不存在")

        if hasattr(self, 'btn_bulk_main'):
            print(f"[UI_Bind] btn_bulk_main 存在，尝试绑定...")
            self.btn_bulk_main.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))
            print(f"[UI_Bind] btn_bulk_main 绑定成功")
        else:
            print(f"[UI_Bind] btn_bulk_main 不存在")

        if hasattr(self, 'btn_venn'):
            print(f"[UI_Bind] btn_venn 存在，尝试绑定...")
            self.btn_venn.clicked.connect(lambda: page_intersect.go_to_page_with_bind('venn_page'))
            print(f"[UI_Bind] btn_venn 绑定成功")
        else:
            print(f"[UI_Bind] btn_venn 不存在")

        if hasattr(self, 'settings_btn'):
            print(f"[UI_Bind] settings_btn 存在，尝试绑定...")
            self.settings_btn.clicked.connect(lambda: page_intersect.go_to_page_with_bind('settings_page'))
            print(f"[UI_Bind] settings_btn 绑定成功")
        else:
            print(f"[UI_Bind] settings_btn 不存在")
        
        print("[UI_Bind] 页面导航按钮绑定完成")

    def bind_general_tools(self):
        """绑定通用工具"""
        if hasattr(self, 'btn_donate'):
            self.btn_donate.clicked.connect(self.show_donate_message)

        self.bind_music_controls()

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self, 'music_btn'):
            self.music_btn.clicked.connect(self.toggle_music)

        if hasattr(self, 'volume_slider'):
            self.volume_slider.valueChanged.connect(self.set_volume)

    def toggle_music(self):
        """切换音乐播放状态"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            is_playing = mod_instance.global_music_player.toggle()
            # 同步所有音乐按钮的图标状态（委托给func层）
            self.func.update_music_icon(is_playing)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        # 更新子界面的音量滑块（委托给func层）
        self.func.sync_volume_sliders(value)

    # 从子界面同步音量滑块的外部接口
    _sync_all_volume_sliders_from_subinterface = lambda self, value: self.func.sync_volume_sliders(value)

    # ========================================
    # 视频背景相关方法
    # ========================================
    def init_video_background(self):
        """初始化视频背景"""
        self.video_bg.set_label(self.video_bg_label)
        self.video_bg.play()

    # ========================================
    # 页面导航方法
    # ========================================
    def go_to_home_page(self):
        """返回主页"""
        try:
            page_intersect.go_to_home()
            if hasattr(self, 'video_bg'):
                self.video_bg.play_return()
        except Exception as e:
            print(f"返回主页失败: {e}")

    # ========================================
    # 通用工具方法
    # ========================================
    def show_donate_message(self):
        """显示打赏信息（委托给func层）"""
        self.func.show_donate_message()
