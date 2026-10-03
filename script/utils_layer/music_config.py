# -*- coding: utf-8 -*-
"""
全局音乐配置模块 - 管理“启动时是否自动播放背景音乐”的设置

存储位置：appdata/mods/kurosaki_koyuki/config/music_config.txt
内容格式：一行，例如 autoplay=1 或 autoplay=0
  - 1 表示开启：程序启动时自动播放背景音乐
  - 0 表示关闭：程序启动时保持静默（用户可手动点播放）

供设置界面（写入）与主窗口启动流程（读取）共用，保持一致。
"""

import os
from script.utils_layer.import_config import APPDATA_PATH

_CONFIG_FILE_NAME = "music_config.txt"
_DEFAULT_ENABLED = True   # 首次运行（无配置文件）默认开启，与历史行为一致

# —— 点击音效开关 ——
_CLICK_FILE_NAME = "click_sound.txt"
_DEFAULT_CLICK = True     # 首次默认开启点击音效

# —— 默认音量（0-100）——
_VOLUME_FILE_NAME = "volume.txt"
_DEFAULT_VOLUME = 100     # 首次默认音量 100

# —— 按钮音效音量（0-100）——
_CLICK_VOLUME_FILE_NAME = "click_volume.txt"
_DEFAULT_CLICK_VOLUME = 60   # 首次默认按钮音效音量 60

# —— 角色音效开关（成功/警告/错误提示音）——
_ROLE_FILE_NAME = "role_sound.txt"
_DEFAULT_ROLE_ENABLED = True   # 首次默认开启角色音效

# —— 角色音效音量（0-100）——
_ROLE_VOLUME_FILE_NAME = "role_volume.txt"
_DEFAULT_ROLE_VOLUME = 100   # 首次默认角色音效音量 100


def _config_dir():
    """配置目录（存放各全局音乐设置）"""
    return os.path.join(APPDATA_PATH, "mods", "kurosaki_koyuki", "config")


def get_music_config_path():
    """获取音乐配置文件的完整路径（autoplay）"""
    return os.path.join(_config_dir(), _CONFIG_FILE_NAME)


def is_startup_music_enabled():
    """读取“启动时自动播放音乐”开关，返回 True/False"""
    try:
        cfg_path = get_music_config_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                line = f.read().strip()
            if '=' in line:
                val = line.split('=', 1)[1].strip()
                return val == '1'
    except Exception as e:
        print(f"读取音乐配置失败: {e}")
    return _DEFAULT_ENABLED


def set_startup_music_enabled(enabled):
    """保存“启动时自动播放音乐”开关，enabled 为 True/False"""
    try:
        cfg_path = get_music_config_path()
        cfg_dir = os.path.dirname(cfg_path)
        os.makedirs(cfg_dir, exist_ok=True)
        with open(cfg_path, 'w', encoding='utf-8') as f:
            f.write("autoplay=" + ("1" if enabled else "0"))
        print(f"音乐配置已保存: autoplay={'1' if enabled else '0'} -> {cfg_path}")
        return True
    except Exception as e:
        print(f"保存音乐配置失败: {e}")
        return False


# ---------- 点击音效开关 ----------

def get_click_sound_path():
    """获取点击音效配置文件的完整路径"""
    return os.path.join(_config_dir(), _CLICK_FILE_NAME)


def is_click_sound_enabled():
    """读取“点击音效是否开启”，返回 True/False"""
    try:
        cfg_path = get_click_sound_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                line = f.read().strip()
            if '=' in line:
                return line.split('=', 1)[1].strip() == '1'
    except Exception as e:
        print(f"读取点击音效配置失败: {e}")
    return _DEFAULT_CLICK


def set_click_sound_enabled(enabled):
    """保存“点击音效是否开启”，enabled 为 True/False"""
    try:
        cfg_dir = _config_dir()
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, _CLICK_FILE_NAME), 'w', encoding='utf-8') as f:
            f.write("enabled=" + ("1" if enabled else "0"))
        print(f"点击音效配置已保存: enabled={'1' if enabled else '0'}")
        return True
    except Exception as e:
        print(f"保存点击音效配置失败: {e}")
        return False


# ---------- 默认音量 ----------

def get_volume_path():
    """获取默认音量配置文件的完整路径"""
    return os.path.join(_config_dir(), _VOLUME_FILE_NAME)


def get_default_volume():
    """读取“默认音量”（0-100），未配置时返回 100"""
    try:
        cfg_path = get_volume_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                line = f.read().strip()
            if '=' in line:
                val = float(line.split('=', 1)[1].strip())
                return int(max(0, min(100, val)))
    except Exception as e:
        print(f"读取默认音量配置失败: {e}")
    return _DEFAULT_VOLUME


def set_default_volume(volume):
    """保存“默认音量”（0-100）"""
    try:
        cfg_dir = _config_dir()
        os.makedirs(cfg_dir, exist_ok=True)
        v = int(max(0, min(100, volume)))
        with open(os.path.join(cfg_dir, _VOLUME_FILE_NAME), 'w', encoding='utf-8') as f:
            f.write(f"volume={v}")
        print(f"默认音量配置已保存: volume={v}")
        return True
    except Exception as e:
        print(f"保存默认音量配置失败: {e}")
        return False


# ---------- 按钮音效音量 ----------

def get_click_volume_path():
    """获取按钮音效音量配置文件的完整路径"""
    return os.path.join(_config_dir(), _CLICK_VOLUME_FILE_NAME)


def get_click_volume():
    """读取“按钮音效音量”（0-100），未配置时返回 60"""
    try:
        cfg_path = get_click_volume_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                line = f.read().strip()
            if '=' in line:
                val = float(line.split('=', 1)[1].strip())
                return int(max(0, min(100, val)))
    except Exception as e:
        print(f"读取按钮音效音量配置失败: {e}")
    return _DEFAULT_CLICK_VOLUME


def set_click_volume(volume):
    """保存“按钮音效音量”（0-100）"""
    try:
        cfg_dir = _config_dir()
        os.makedirs(cfg_dir, exist_ok=True)
        v = int(max(0, min(100, volume)))
        with open(os.path.join(cfg_dir, _CLICK_VOLUME_FILE_NAME), 'w', encoding='utf-8') as f:
            f.write(f"volume={v}")
        print(f"按钮音效音量配置已保存: volume={v}")
        return True
    except Exception as e:
        print(f"保存按钮音效音量配置失败: {e}")
        return False


# ---------- 角色音效开关（成功/警告/错误提示音） ----------

def get_role_sound_path():
    """获取角色音效配置文件路径"""
    return os.path.join(_config_dir(), _ROLE_FILE_NAME)


def is_role_sound_enabled():
    """读取“角色音效是否开启”，返回 True/False"""
    try:
        cfg_path = get_role_sound_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                line = f.read().strip()
            if '=' in line:
                return line.split('=', 1)[1].strip() == '1'
    except Exception as e:
        print(f"读取角色音效配置失败: {e}")
    return _DEFAULT_ROLE_ENABLED


def set_role_sound_enabled(enabled):
    """保存“角色音效是否开启”，enabled 为 True/False"""
    try:
        cfg_dir = _config_dir()
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, _ROLE_FILE_NAME), 'w', encoding='utf-8') as f:
            f.write("enabled=" + ("1" if enabled else "0"))
        print(f"角色音效配置已保存: enabled={'1' if enabled else '0'}")
        return True
    except Exception as e:
        print(f"保存角色音效配置失败: {e}")
        return False


# ---------- 角色音效音量（0-100） ----------

def get_role_volume_path():
    """获取角色音效音量配置文件路径"""
    return os.path.join(_config_dir(), _ROLE_VOLUME_FILE_NAME)


def get_role_volume():
    """读取“角色音效音量”（0-100），未配置时返回 100"""
    try:
        cfg_path = get_role_volume_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                line = f.read().strip()
            if '=' in line:
                val = float(line.split('=', 1)[1].strip())
                return int(max(0, min(100, val)))
    except Exception as e:
        print(f"读取角色音效音量配置失败: {e}")
    return _DEFAULT_ROLE_VOLUME


def set_role_volume(volume):
    """保存“角色音效音量”（0-100）"""
    try:
        cfg_dir = _config_dir()
        os.makedirs(cfg_dir, exist_ok=True)
        v = int(max(0, min(100, volume)))
        with open(os.path.join(cfg_dir, _ROLE_VOLUME_FILE_NAME), 'w', encoding='utf-8') as f:
            f.write(f"volume={v}")
        print(f"角色音效音量配置已保存: volume={v}")
        return True
    except Exception as e:
        print(f"保存角色音效音量配置失败: {e}")
        return False
