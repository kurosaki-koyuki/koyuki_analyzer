# -*- coding: utf-8 -*-
"""
Emoji触发器 - 统一管理弹窗和进程框输出
用于在成功/警告/错误时显示emoji并播放对应语音

【重要】此模块优先级最高，所有弹窗都必须通过此模块触发
禁止在子界面脚本中直接使用 QMessageBox
"""

from script.utils_layer.import_config import QMessageBox, QWidget, QApplication, QIcon, QPixmap, Qt, QEvent, os, sys, random


# ========================================
# 全局变量
# ========================================
_current_paths = None
_current_styles = None
_mod_instance = None
_log_widget = None  # 进程框（QTextEdit或类似控件）
_is_shut_down = False  # 弹窗拦截开关
_parent_window = None  # 父窗口引用
_dialog_triggered = False  # 追踪是否触发了attention/wrong弹窗


def init_emoji_trigger(paths, styles, mod_instance, log_widget=None, parent_window=None):
    """
    初始化emoji触发器
    
    Args:
        paths: 模组路径字典
        styles: 模组样式字典
        mod_instance: 模组实例
        log_widget: 进程框控件（可选，用于在进程框中显示emoji）
        parent_window: 主窗口引用（用于获取父窗口）
    """
    global _current_paths, _current_styles, _mod_instance, _log_widget, _parent_window
    _current_paths = paths
    _current_styles = styles
    _mod_instance = mod_instance
    _log_widget = log_widget
    _parent_window = parent_window


def shut_down_gui_window(enable=True):
    """
    【核心函数】关闭/开启全局弹窗拦截
    
    调用此函数后，所有直接使用 QMessageBox 的弹窗都会被拦截
    只有通过 happy() / attention() / wrong() 触发的弹窗才会正常显示
    
    Args:
        enable: True=开启拦截（阻止非emoji弹窗）, False=关闭拦截
    
    Example:
        # 开启拦截
        shut_down_gui_window(True)
        
        # 关闭拦截（恢复原始行为）
        shut_down_gui_window(False)
    """
    global _is_shut_down
    _is_shut_down = enable
    
    if enable:
        # 安装事件过滤器
        app = QApplication.instance()
        if app:
            app.installEventFilter(_EmojiEventFilter.instance())


def is_shut_down():
    """检查弹窗是否被拦截"""
    return _is_shut_down


def _get_mod_base():
    """获取当前模组的基目录"""
    # 首先尝试从全局变量获取
    if _current_paths:
        # 尝试从paths中获取mod_base
        if 'mod_base' in _current_paths:
            return _current_paths['mod_base']
        # 如果没有，尝试从BASE_DIR推断
        if 'BG_IMAGE_PATH' in _current_paths:
            # BG_IMAGE_PATH格式: .../mods/xxx/background/bg.png
            bg_path = _current_paths['BG_IMAGE_PATH']
            # 向上三级到达mods目录
            mods_dir = os.path.dirname(os.path.dirname(os.path.dirname(bg_path)))
            # 获取当前模组名
            mod_name = os.path.basename(os.path.dirname(os.path.dirname(bg_path)))
            return os.path.join(mods_dir, mod_name)
    
    # 如果全局变量未初始化，尝试从global_mod_manager获取
    try:
        from script.mods_layer.mod_manager import global_mod_manager
        paths = global_mod_manager.get_current_paths()
        if paths and 'BG_IMAGE_PATH' in paths:
            bg_path = paths['BG_IMAGE_PATH']
            # 向上三级到达mods目录
            mods_dir = os.path.dirname(os.path.dirname(os.path.dirname(bg_path)))
            # 获取当前模组名
            mod_name = os.path.basename(os.path.dirname(os.path.dirname(bg_path)))
            return os.path.join(mods_dir, mod_name)
    except:
        pass
    
    return ''


def _get_emoji_path(emoji_name):
    """获取emoji图片路径"""
    mod_base = _get_mod_base()
    if mod_base and emoji_name:
        emoji_dir = os.path.join(mod_base, 'emoji')
        emoji_file = f"{emoji_name}.png"
        full_path = os.path.join(emoji_dir, emoji_file)
        if os.path.exists(full_path):
            return full_path
    return None


def _get_sound_paths(sound_type):
    """获取指定类型的所有语音文件路径"""
    mod_base = _get_mod_base()
    if mod_base and sound_type:
        sound_dir = os.path.join(mod_base, 'sound', sound_type)
        if os.path.exists(sound_dir):
            files = [f for f in os.listdir(sound_dir) if f.endswith(('.ogg', '.wav'))]
            full_paths = [os.path.join(sound_dir, f) for f in files]
            return full_paths
    return []


def _play_random_sound(sound_type):
    """随机播放一个语音文件"""
    if _mod_instance and hasattr(_mod_instance, 'global_sound_player'):
        sound_paths = _get_sound_paths(sound_type)
        if sound_paths:
            selected = random.choice(sound_paths)
            try:
                _mod_instance.global_sound_player.load_sound(selected, f"emoji_{sound_type}")
                _mod_instance.global_sound_player.play_sound(f"emoji_{sound_type}", volume=0.8)
            except Exception as e:
                print(f"播放emoji语音失败: {e}")


def _get_parent():
    """获取父窗口"""
    if _parent_window:
        return _parent_window
    try:
        from script.mods_layer.mod_manager import global_mod_manager
        instance = global_mod_manager.get_current_mod()
        if instance and hasattr(instance, '_parent_window'):
            return instance._parent_window
    except:
        pass
    return None


def get_and_reset_dialog_triggered():
    """
    获取并重置弹窗触发标志
    
    Returns:
        True if a dialog was triggered since last reset, False otherwise
    """
    global _dialog_triggered
    result = _dialog_triggered
    _dialog_triggered = False
    return result


# ========================================
# 事件过滤器 - 拦截所有非emoji弹窗
# ========================================

class _EmojiEventFilter(QApplication):
    """
    全局事件过滤器
    用于拦截所有 QMessageBox 弹窗
    """
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def eventFilter(self, obj, event):
        # 拦截 QMessageBox 的显示事件
        if event.type() == QEvent.Show and isinstance(obj, QMessageBox):
            # 检查是否是emoji_trigger触发的弹窗
            if hasattr(obj, '_is_emoji_triggered') and obj._is_emoji_triggered:
                return super().eventFilter(obj, event)
            
            # 如果开启了拦截，阻止弹窗显示
            if _is_shut_down:
                # 打印警告信息到控制台
                msg = obj.text() if hasattr(obj, 'text') else "拦截到弹窗"
                print(f"[Emoji Trigger] 弹窗被拦截: {msg}")
                print(f"[Emoji Trigger] 请使用 happy() / attention() / wrong() 触发弹窗")
                obj.hide()
                obj.deleteLater()
                return True
        
        return super().eventFilter(obj, event)


# ========================================
# 核心触发函数
# ========================================

def trigger_happy(parent=None, message="操作成功！", use_dialog=True, append_to_log=True):
    """
    触发成功emoji和语音
    
    Args:
        parent: 父窗口
        message: 成功信息
        use_dialog: 是否使用弹窗
        append_to_log: 是否追加到进程框
    
    Returns:
        弹窗的返回值（如果使用了弹窗）
    """
    emoji_path = _get_emoji_path('happy')
    
    # 播放happy语音
    _play_random_sound('happy')
    
    result = None
    
    if use_dialog:
        if parent is None:
            parent = _get_parent()
        
        # 创建带emoji的弹窗
        msg_box = QMessageBox(parent)
        msg_box._is_emoji_triggered = True  # 标记为emoji触发的弹窗
        msg_box.setWindowTitle("成功")
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Information)
        
        # 设置emoji图标
        if emoji_path:
            msg_box.setWindowIcon(QIcon(emoji_path))
            # 在消息前添加emoji
            pixmap = QPixmap(emoji_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                msg_box.setIconPixmap(scaled_pixmap)
        
        msg_box.setStandardButtons(QMessageBox.Ok)
        result = msg_box.exec_()
    
    # 追加到进程框
    if append_to_log and _log_widget:
        emoji_html = f'<img src="{emoji_path}" width="20" height="20"/>' if emoji_path else "✓"
        _log_widget.append(f'<span style="color: green;">{emoji_html} {message}</span>')
    
    return result


def trigger_attention(parent=None, message="请注意！", use_dialog=True, append_to_log=True):
    """
    触发警告emoji和语音
    
    Args:
        parent: 父窗口
        message: 警告信息
        use_dialog: 是否使用弹窗
        append_to_log: 是否追加到进程框
    
    Returns:
        弹窗的返回值（如果使用了弹窗）
    """
    global _dialog_triggered
    _dialog_triggered = True
    
    emoji_path = _get_emoji_path('attention')
    
    # 播放attention语音
    _play_random_sound('attention')
    
    result = None
    
    if use_dialog:
        if parent is None:
            parent = _get_parent()
        
        # 创建带emoji的弹窗
        msg_box = QMessageBox(parent)
        msg_box._is_emoji_triggered = True  # 标记为emoji触发的弹窗
        msg_box.setWindowTitle("注意")
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Warning)
        
        # 设置emoji图标
        if emoji_path:
            msg_box.setWindowIcon(QIcon(emoji_path))
            pixmap = QPixmap(emoji_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                msg_box.setIconPixmap(scaled_pixmap)
        
        msg_box.setStandardButtons(QMessageBox.Ok)
        result = msg_box.exec_()
    
    # 追加到进程框
    if append_to_log and _log_widget:
        emoji_html = f'<img src="{emoji_path}" width="20" height="20"/>' if emoji_path else "⚠"
        _log_widget.append(f'<span style="color: orange;">{emoji_html} {message}</span>')
    
    return result


def trigger_wrong(parent=None, message="发生错误！", use_dialog=True, append_to_log=True):
    """
    触发错误emoji和语音
    
    Args:
        parent: 父窗口
        message: 错误信息
        use_dialog: 是否使用弹窗
        append_to_log: 是否追加到进程框
    
    Returns:
        弹窗的返回值（如果使用了弹窗）
    """
    global _dialog_triggered
    _dialog_triggered = True
    
    emoji_path = _get_emoji_path('wrong')
    
    # 播放wrong语音
    _play_random_sound('wrong')
    
    result = None
    
    if use_dialog:
        if parent is None:
            parent = _get_parent()
        
        # 创建带emoji的弹窗
        msg_box = QMessageBox(parent)
        msg_box._is_emoji_triggered = True  # 标记为emoji触发的弹窗
        msg_box.setWindowTitle("错误")
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Critical)
        
        # 设置emoji图标
        if emoji_path:
            msg_box.setWindowIcon(QIcon(emoji_path))
            pixmap = QPixmap(emoji_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                msg_box.setIconPixmap(scaled_pixmap)
        
        msg_box.setStandardButtons(QMessageBox.Ok)
        result = msg_box.exec_()
    
    # 追加到进程框
    if append_to_log and _log_widget:
        emoji_html = f'<img src="{emoji_path}" width="20" height="20"/>' if emoji_path else "✗"
        _log_widget.append(f'<span style="color: red;">{emoji_html} {message}</span>')
    
    return result


# ========================================
# 进程框日志函数（无弹窗版本）
# ========================================

def log_success(message):
    """仅在进程框记录成功信息（带emoji）"""
    emoji_path = _get_emoji_path('happy')
    _play_random_sound('happy')
    
    if _log_widget:
        emoji_html = f'<img src="{emoji_path}" width="16" height="16"/>' if emoji_path else "✓"
        _log_widget.append(f'<span style="color: green;">{emoji_html} {message}</span>')


def log_warning(message):
    """仅在进程框记录警告信息（带emoji）"""
    emoji_path = _get_emoji_path('attention')
    _play_random_sound('attention')
    
    if _log_widget:
        emoji_html = f'<img src="{emoji_path}" width="16" height="16"/>' if emoji_path else "⚠"
        _log_widget.append(f'<span style="color: orange;">{emoji_html} {message}</span>')


def log_error(message):
    """仅在进程框记录错误信息（带emoji）"""
    emoji_path = _get_emoji_path('wrong')
    _play_random_sound('wrong')
    
    if _log_widget:
        emoji_html = f'<img src="{emoji_path}" width="16" height="16"/>' if emoji_path else "✗"
        _log_widget.append(f'<span style="color: red;">{emoji_html} {message}</span>')


def log_info(message):
    """仅在进程框记录普通信息"""
    if _log_widget:
        _log_widget.append(f'<span style="color: gray;">{message}</span>')


# ========================================
# 便捷的QMessageBox替换函数
# ========================================

def show_info(parent, title, message):
    """显示信息弹窗（替代QMessageBox.information）"""
    return trigger_happy(parent, message, use_dialog=True, append_to_log=False)


def show_warning(parent, title, message):
    """显示警告弹窗（替代QMessageBox.warning）"""
    return trigger_attention(parent, message, use_dialog=True, append_to_log=False)


def show_error(parent, title, message):
    """显示错误弹窗（替代QMessageBox.critical）"""
    return trigger_wrong(parent, message, use_dialog=True, append_to_log=False)


__all__ = [
    # 初始化
    'init_emoji_trigger',
    # 核心开关
    'shut_down_gui_window',
    'is_shut_down',
    # 核心触发函数（带弹窗）
    'trigger_happy',
    'trigger_attention',
    'trigger_wrong',
    # 便捷的QMessageBox替换
    'show_info',
    'show_warning',
    'show_error',
    # 仅日志版本
    'log_success',
    'log_warning',
    'log_error',
    'log_info'
]
