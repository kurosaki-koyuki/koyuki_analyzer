# -*- coding: utf-8 -*-
"""
全局模组配置模块 - 管理“程序启动时默认加载的模组”设置

存储位置：appdata/mods/kurosaki_koyuki/config/startup_mod.txt
内容格式：一行，例如 kurosaki_koyuki
说明：
  - 该配置决定“下次启动程序时默认运行的模组”，并非实时切换当前模组
  - 供设置界面（写入）与模组管理器启动流程（读取）共用

用法：
  - get_startup_mod_name(fallback="kurosaki_koyuki")：读取启动默认模组
  - set_startup_mod_name(name)：保存启动默认模组
"""

import os
from script.utils_layer.import_config import APPDATA_PATH

_CONFIG_FILE_NAME = "startup_mod.txt"
_DEFAULT_MOD = "kurosaki_koyuki"


def _config_dir():
    """配置目录（与音乐配置同目录）"""
    return os.path.join(APPDATA_PATH, "mods", "kurosaki_koyuki", "config")


def get_startup_mod_path():
    """获取启动默认模组配置文件的完整路径"""
    return os.path.join(_config_dir(), _CONFIG_FILE_NAME)


def get_startup_mod_name(fallback=None):
    """读取“启动时默认加载的模组”，返回模组名；未配置或读取失败时返回 fallback"""
    if fallback is None:
        fallback = _DEFAULT_MOD
    try:
        cfg_path = get_startup_mod_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                name = f.read().strip()
            if name:
                return name
    except Exception as e:
        print(f"读取启动模组配置失败: {e}")
    return fallback


def set_startup_mod_name(mod_name):
    """保存“启动时默认加载的模组”"""
    if not mod_name:
        return False
    try:
        cfg_dir = _config_dir()
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, _CONFIG_FILE_NAME), 'w', encoding='utf-8') as f:
            f.write(str(mod_name).strip())
        print(f"启动默认模组已保存: {mod_name} -> {get_startup_mod_path()}")
        return True
    except Exception as e:
        print(f"保存启动模组配置失败: {e}")
        return False
