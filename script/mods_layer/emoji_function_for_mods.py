# -*- coding: utf-8 -*-
"""
Emoji功能模块 - 为各mod提供emoji触发功能
包含四个核心函数：happy, attention, wrong, compromise_for_emoji
以及全局弹窗拦截：shut_down_gui_window
"""

from script.utils_layer.emoji_trigger import (
    trigger_happy,
    trigger_attention,
    trigger_wrong,
    shut_down_gui_window,
    is_shut_down,
    show_info,
    show_warning,
    show_error,
    log_success,
    log_warning,
    log_error,
    log_info
)


# ========================================
# 成功/警告/错误 触发函数
# ========================================

def happy(parent=None, message="操作成功！", use_dialog=True, append_to_log=True):
    """
    成功触发函数
    
    触发场景：
    - 文件导入成功
    - 文件导出成功
    - 图表绘制成功
    
    Args:
        parent: 父窗口
        message: 成功信息
        use_dialog: 是否使用弹窗
        append_to_log: 是否追加到进程框
    
    Returns:
        弹窗返回值（如果使用了弹窗）
    """
    return trigger_happy(parent, message, use_dialog, append_to_log)


def attention(parent=None, message="请注意！", use_dialog=True, append_to_log=True):
    """
    警告触发函数
    
    触发场景：
    - 黄色感叹号提示框出现时
    
    Args:
        parent: 父窗口
        message: 警告信息
        use_dialog: 是否使用弹窗
        append_to_log: 是否追加到进程框
    
    Returns:
        弹窗返回值（如果使用了弹窗）
    """
    return trigger_attention(parent, message, use_dialog, append_to_log)


def wrong(parent=None, message="发生错误！", use_dialog=True, append_to_log=True):
    """
    错误触发函数
    
    触发场景：
    - 红色错误提示框出现时
    
    Args:
        parent: 父窗口
        message: 错误信息
        use_dialog: 是否使用弹窗
        append_to_log: 是否追加到进程框
    
    Returns:
        弹窗返回值（如果使用了弹窗）
    """
    return trigger_wrong(parent, message, use_dialog, append_to_log)


# ========================================
# 妥协函数 - 容错处理
# ========================================

def compromise_for_emoji(mod_instance, paths, styles):
    """
    妥协函数 - 用于校正容错
    
    当没有读取到当前模组有全套的信息时，
    尽可能地放能运行的部分，
    没有的成分就假装无事发生防止系统卡死或者疯狂连续报错。
    
    使用方法：
    在mod_script.py的Mod类初始化时调用此函数，
    它会初始化emoji_trigger模块，确保即使资源缺失也能正常运行。
    
    Args:
        mod_instance: 模组实例
        paths: 模组路径字典
        styles: 模组样式字典
    
    Returns:
        bool: 是否成功初始化（True即使部分资源缺失也返回True）
    """
    from script.utils_layer.emoji_trigger import init_emoji_trigger
    
    try:
        # 尝试初始化emoji触发器
        init_emoji_trigger(paths, styles, mod_instance, log_widget=None)
        return True
    except Exception as e:
        # 出错也返回True，只是打印警告
        print(f"[Emoji] 初始化emoji功能时出现非致命错误: {e}")
        return True


# ========================================
# 便捷函数 - 仅日志版本
# ========================================

def log_happy(message):
    """
    仅在进程框记录成功（不弹窗）
    
    适用于：
    - 进程框已有成功提示，只需要在旁边加emoji和小语音
    """
    log_success(message)


def log_attention(message):
    """
    仅在进程框记录警告（不弹窗）
    
    适用于：
    - 进程框已有警告提示，只需要在旁边加emoji和小语音
    """
    log_warning(message)


def log_wrong(message):
    """
    仅在进程框记录错误（不弹窗）
    
    适用于：
    - 进程框已有错误提示，只需要在旁边加emoji和小语音
    """
    log_error(message)


# ========================================
# 导出所有函数
# ========================================

__all__ = [
    # 核心触发函数（带弹窗）
    'happy',
    'attention', 
    'wrong',
    # 妥协函数
    'compromise_for_emoji',
    # 全局弹窗拦截
    'shut_down_gui_window',
    'is_shut_down',
    # 便捷的QMessageBox替换
    'show_info',
    'show_warning',
    'show_error',
    # 仅日志版本
    'log_happy',
    'log_attention',
    'log_wrong',
]
