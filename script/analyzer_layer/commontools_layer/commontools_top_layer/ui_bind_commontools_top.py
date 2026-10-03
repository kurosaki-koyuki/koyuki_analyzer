# -*- coding: utf-8 -*-
"""
小工具主页（hub）导航界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 导航跳转
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.commontools_layer.commontools_top_layer.ui_func_commontools_top import CommonToolsTopFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class CommonToolsTopBind:
    """小工具主页导航界面功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, ui_instance):
        self.parent = parent_window
        self.ui = ui_instance
        self.func = CommonToolsTopFunc(ui_instance, parent_window)
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_tool_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.ui, 'nav_btn_back'):
            self.ui.nav_btn_back.clicked.connect(page_intersect.go_to_home)

        if hasattr(self.ui, 'nav_btn_genelist'):
            self.ui.nav_btn_genelist.clicked.connect(lambda: self.ui.show_panel('genelist'))

        if hasattr(self.ui, 'nav_btn_misc'):
            self.ui.nav_btn_misc.clicked.connect(lambda: self.ui.show_panel('misc'))

    def bind_tool_navigation(self):
        """绑定小工具卡片按钮导航"""
        if hasattr(self.ui, 'btn_card_venn'):
            self.ui.btn_card_venn.clicked.connect(lambda: page_intersect.go_to_page_with_bind('venn_page'))

        if hasattr(self.ui, 'btn_card_circos'):
            self.ui.btn_card_circos.clicked.connect(lambda: page_intersect.go_to_page_with_bind('circos_page'))

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.ui, 'music_controller'):
            fix_music_controller_bindings(self, self.ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)
