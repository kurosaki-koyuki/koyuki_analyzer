# -*- coding: utf-8 -*-
"""
Settings界面功能函数脚本 - 存放具体业务逻辑函数
"""

from script.utils_layer.import_config import *


class SettingsFunc:
    """Settings界面功能函数类"""

    def __init__(self, bind_instance):
        self.bind = bind_instance
