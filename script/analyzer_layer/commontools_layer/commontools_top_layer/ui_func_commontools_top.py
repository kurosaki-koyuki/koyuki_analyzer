# -*- coding: utf-8 -*-
"""
小工具主页（hub）导航界面前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class CommonToolsTopFunc:
    """小工具主页导航界面前端功能类 - 纯前端显示操作"""

    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget

    def update_styles(self):
        """更新界面样式"""
        if hasattr(self.ui, 'update_styles'):
            self.ui.update_styles()

    def update_background(self):
        """更新背景图"""
        if hasattr(self.ui, 'update_background'):
            self.ui.update_background()

    def log(self, message):
        """在日志文本框中记录日志（hub 页无日志框时静默跳过）"""
        if hasattr(self.ui, 'commontools_log') and self.ui.commontools_log:
            self.ui.commontools_log.append(message)
