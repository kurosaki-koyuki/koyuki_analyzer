# -*- coding: utf-8 -*-
"""
上帝类型按钮样式模块 - 三种特殊功能按钮的样式定义

【重要设计原则】
编写健壮代码时，应该调用 emoji_trigger 内的函数而不是自己瞎捏弹窗！
所有弹窗都应该通过 happy() / attention() / wrong() 触发，而不是直接使用 QMessageBox！

三种上帝类型按钮：
1. import_gui_type  - 导入按钮（紫色半透明）
2. export_gui_type  - 导出按钮（绿色半透明）
3. run_gui_type      - 运行按钮（红色半透明）

这些按钮的共性：
- 绑定了 emoji_trigger，会检测成功与失败
- 成功时无弹窗，但会播放 happy 语音，并在进程框输出成功后+HAPPY emoji
- 失败时会弹出失败窗口，显示失败详情，并随机播放失败语音
- 中间如有提示，会通过 attention 系列触发

使用方式：
    from script.utils_layer.gui_god_type_style import (
        import_gui_type, export_gui_type, run_gui_type,
        GOD_BUTTON_STYLES
    )
"""

from script.utils_layer.import_config import QPushButton, QMessageBox, Qt, pyqtSignal, QFont

from script.mods_layer.emoji_function_for_mods import (
    happy, attention, wrong,
    trigger_happy, trigger_attention, trigger_wrong,
    shut_down_gui_window
)
from script.mods_layer.mod_manager import global_mod_manager


# ==================== 样式定义 ====================

# 导入按钮样式（紫色半透明）
IMPORT_BUTTON_STYLE = """
QPushButton {
    background-color: rgba(128, 0, 128, 0.6);
    color: white;
    border: 2px solid rgba(128, 0, 128, 0.8);
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: rgba(148, 0, 148, 0.7);
    border: 2px solid rgba(148, 0, 148, 0.9);
}
QPushButton:pressed {
    background-color: rgba(108, 0, 108, 0.8);
}
QPushButton:disabled {
    background-color: rgba(128, 0, 128, 0.3);
    color: rgba(255, 255, 255, 0.5);
}
"""

# 导出按钮样式（绿色半透明）
EXPORT_BUTTON_STYLE = """
QPushButton {
    background-color: rgba(0, 128, 0, 0.6);
    color: white;
    border: 2px solid rgba(0, 128, 0, 0.8);
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: rgba(0, 148, 0, 0.7);
    border: 2px solid rgba(0, 148, 0, 0.9);
}
QPushButton:pressed {
    background-color: rgba(0, 108, 0, 0.8);
}
QPushButton:disabled {
    background-color: rgba(0, 128, 0, 0.3);
    color: rgba(255, 255, 255, 0.5);
}
"""

# 运行按钮样式（红色半透明）
RUN_BUTTON_STYLE = """
QPushButton {
    background-color: rgba(200, 0, 0, 0.6);
    color: white;
    border: 2px solid rgba(200, 0, 0, 0.8);
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: rgba(220, 0, 0, 0.7);
    border: 2px solid rgba(220, 0, 0, 0.9);
}
QPushButton:pressed {
    background-color: rgba(180, 0, 0, 0.8);
}
QPushButton:disabled {
    background-color: rgba(200, 0, 0, 0.3);
    color: rgba(255, 255, 255, 0.5);
}
"""

# 样式字典
GOD_BUTTON_STYLES = {
    'import': IMPORT_BUTTON_STYLE,
    'export': EXPORT_BUTTON_STYLE,
    'run': RUN_BUTTON_STYLE
}


# ==================== 上帝类型按钮类 ====================

class _GodButtonMixin:
    """
    上帝类型按钮Mixin - 提供成功/失败检测和emoji触发机制
    
    【重要】
    所有弹窗都应该通过 emoji_trigger 的函数触发，不要直接使用 QMessageBox！
    
    共性行为：
    - 成功：播放 happy 语音，在进程框输出成功后+HAPPY emoji（无弹窗）
    - 失败：弹出失败窗口显示详情，随机播放失败语音
    - 提示：通过 attention 系列触发
    """
    
    # 信号定义
    success_signal = pyqtSignal(object)  # 成功信号，携带详情
    failure_signal = pyqtSignal(object)  # 失败信号，携带详情
    
    # 子类需要定义的属性
    button_type = 'god'  # 按钮类型：import/export/run
    success_emoji = '🎉'  # 成功时的emoji
    
    # 失败时的客套话（子类可覆盖）
    FAILURE_EXCUSE = "哎呀，操作失败了..."
    
    def _init_god_button(self):
        """初始化上帝按钮的实例变量（由子类在__init__中调用）"""
        self._log_widget = None  # 进程框
        self._detail_extractor = None  # 详情提取函数
    
    def set_log_widget(self, log_widget):
        """设置进程框（用于输出日志）"""
        self._log_widget = log_widget
    
    def set_detail_extractor(self, extractor):
        """
        设置详情提取函数
        
        Args:
            extractor: 一个函数，签名为 (exception) -> str
                      用于从异常中提取要显示的失败详情
        """
        self._detail_extractor = extractor
    
    def _log_success(self, message):
        """记录成功日志"""
        if self._log_widget:
            self._log_widget.append(f"{message} {self.success_emoji}")
        else:
            print(f"[{self.button_type.upper()}] 成功: {message}")
    
    def _log_failure(self, message):
        """记录失败日志"""
        if self._log_widget:
            self._log_widget.append(f"❌ {message}")
        else:
            print(f"[{self.button_type.upper()}] 失败: {message}")
    
    def _extract_detail(self, exception):
        """提取失败详情"""
        if self._detail_extractor:
            return self._detail_extractor(exception)
        return str(exception) if exception else "未知错误"
    
    def _emit_success(self, detail=None):
        """触发成功"""
        self._log_success(detail or "操作完成")
        trigger_happy()
        self.success_signal.emit(detail)
    
    def _emit_failure(self, exception=None, detail=None):
        """触发失败"""
        if detail is None and exception is not None:
            detail = self._extract_detail(exception)
        elif detail is None:
            detail = "未知错误"
        
        self._log_failure(detail)
        trigger_wrong()
        wrong(self.parent(), f"{self.FAILURE_EXCUSE}\n\n失败详情：\n{detail}")
        self.failure_signal.emit(detail)


class ImportGodButton(QPushButton, _GodButtonMixin):
    """
    导入上帝类型按钮
    
    用途：负责导入数据、加载文件等操作
    样式：紫色半透明
    成功：播放happy语音，进程框输出"导入成功" + HAPPY emoji
    失败：弹出失败窗口显示详情，播放失败语音
    """
    
    button_type = 'import'
    success_emoji = '🎉'
    FAILURE_EXCUSE = "哎呀，导入失败了..."
    
    def __init__(self, text="导入", parent=None):
        QPushButton.__init__(self, text, parent)
        _GodButtonMixin._init_god_button(self)
        self.setStyleSheet(IMPORT_BUTTON_STYLE)


class ExportGodButton(QPushButton, _GodButtonMixin):
    """
    导出上帝类型按钮
    
    用途：负责导出数据、保存文件等操作
    样式：绿色半透明
    成功：播放happy语音，进程框输出"导出成功" + HAPPY emoji
    失败：弹出失败窗口显示详情，播放失败语音
    """
    
    button_type = 'export'
    success_emoji = '🎉'
    FAILURE_EXCUSE = "哎呀，导出失败了..."
    
    def __init__(self, text="导出", parent=None):
        QPushButton.__init__(self, text, parent)
        _GodButtonMixin._init_god_button(self)
        self.setStyleSheet(EXPORT_BUTTON_STYLE)


class RunGodButton(QPushButton, _GodButtonMixin):
    """
    运行上帝类型按钮
    
    用途：负责运行绘图、处理数据等关键步骤（一般每个子界面只有一个）
    样式：红色半透明
    成功：播放happy语音，进程框输出"运行完成" + HAPPY emoji
    失败：弹出失败窗口显示详情，播放失败语音
    """
    
    button_type = 'run'
    success_emoji = '🎉'
    FAILURE_EXCUSE = "哎呀，运行失败了..."
    
    def __init__(self, text="运行", parent=None):
        QPushButton.__init__(self, text, parent)
        _GodButtonMixin._init_god_button(self)
        self.setStyleSheet(RUN_BUTTON_STYLE)


# ==================== 便捷函数 ====================

def create_import_button(text="导入", parent=None, log_widget=None):
    """
    创建导入按钮
    
    Args:
        text: 按钮文字
        parent: 父控件
        log_widget: 进程框（可选）
    
    Returns:
        ImportGodButton 实例
    """
    btn = ImportGodButton(text, parent)
    if log_widget:
        btn.set_log_widget(log_widget)
    return btn


def create_export_button(text="导出", parent=None, log_widget=None):
    """
    创建导出按钮
    
    Args:
        text: 按钮文字
        parent: 父控件
        log_widget: 进程框（可选）
    
    Returns:
        ExportGodButton 实例
    """
    btn = ExportGodButton(text, parent)
    if log_widget:
        btn.set_log_widget(log_widget)
    return btn


def create_run_button(text="运行", parent=None, log_widget=None):
    """
    创建运行按钮
    
    Args:
        text: 按钮文字
        parent: 父控件
        log_widget: 进程框（可选）
    
    Returns:
        RunGodButton 实例
    """
    btn = RunGodButton(text, parent)
    if log_widget:
        btn.set_log_widget(log_widget)
    return btn


def get_god_button_style(button_type):
    """
    获取指定类型的按钮样式
    
    Args:
        button_type: 'import' / 'export' / 'run'
    
    Returns:
        样式字符串，如果类型无效返回None
    """
    return GOD_BUTTON_STYLES.get(button_type)


def bind_god_button_handler(btn, handler):
    """
    将handler绑定到上帝类型按钮，自动处理成功/失败触发
    
    上帝按钮只管：样式 + 音效/弹窗风格
    成功/失败由try-except自动检测：
    - handler正常执行完（无异常）→ _emit_success()
    - handler抛出异常 → _emit_failure()
    
    注意：handler内部的业务逻辑（如QFileDialog）保持原样，
    不在这里做特殊处理。如果用户取消对话框导致路径为空，
    应该由handler内部判断并决定是否抛出异常。
    
    Args:
        btn: 上帝类型按钮实例
        handler: 要执行的handler函数
    
    Returns:
        包装后的handler函数
    """
    def wrapped_handler(*args, **kwargs):
        try:
            result = handler(*args, **kwargs)
            btn._emit_success()
            return result
        except Exception as e:
            btn._emit_failure(exception=e)
            raise
    return wrapped_handler


# ==================== 导出 ====================

__all__ = [
    # 样式定义
    'IMPORT_BUTTON_STYLE',
    'EXPORT_BUTTON_STYLE',
    'RUN_BUTTON_STYLE',
    'GOD_BUTTON_STYLES',
    # 按钮类
    'ImportGodButton',
    'ExportGodButton',
    'RunGodButton',
    # 便捷函数
    'create_import_button',
    'create_export_button',
    'create_run_button',
    'get_god_button_style',
    'bind_god_button_handler',
]
