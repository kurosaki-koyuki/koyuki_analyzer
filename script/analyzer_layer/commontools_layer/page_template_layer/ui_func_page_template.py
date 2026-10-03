# -*- coding: utf-8 -*-
"""
页面模板前端功能脚本 - 只负责前端显示、控件内容更新等
不绑定信号，不写业务算法，不处理版本探测逻辑

仅提供 R / Python 自检结果的渲染与清空能力，所有数据由 analysis 层产出。
"""

from script.utils_layer.import_config import *


def _as_text(value, default="未知"):
    """把任意取值安全地转成展示文本（None / 空值统一回落到默认文案）"""
    if value is None:
        return default
    text = str(value)
    if text.strip() == "":
        return default
    return text


def _as_bool(value):
    """把任意取值安全地转成布尔值，无法判断时返回 None"""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "y", "是", "可用"):
            return True
        if lowered in ("false", "0", "no", "n", "否", "不可用"):
            return False
    return None


class PageTemplateFunc:
    """页面模板前端功能类 - 纯前端显示操作"""

    def __init__(self, page_template_ui, parent_window=None):
        self.page_template_ui = page_template_ui
        self.parent_window = parent_window
        self.parent_widget = parent_window

    def _get_log_widget(self, attr_name):
        """按属性名获取输出框控件，不存在时返回 None"""
        return getattr(self.page_template_ui, attr_name, None)

    def _render_lines(self, attr_name, lines):
        """把若干行文本渲染进指定输出框（整体替换 + 滚动到底部）"""
        log_widget = self._get_log_widget(attr_name)
        if log_widget is None:
            return
        try:
            log_widget.setPlainText("\n".join(lines))
            scroll_bar = log_widget.verticalScrollBar()
            if scroll_bar is not None:
                scroll_bar.setValue(scroll_bar.maximum())
        except Exception:
            pass

    def show_r_result(self, info: dict) -> None:
        """把 R 环境自检结果渲染进 r_log（容错：缺键/非dict/None 均不抛异常）"""
        data = info if isinstance(info, dict) else {}

        available = _as_bool(data.get('available'))
        if available is True:
            state_text = "可用"
        elif available is False:
            state_text = "不可用"
        else:
            state_text = "未知"

        lines = [
            "===== R 环境自检 =====",
            f"运行状态：{state_text}",
            f"版本号：{_as_text(data.get('version'))}",
            f"R_HOME：{_as_text(data.get('r_home'))}",
            "----- 详细信息 -----",
            _as_text(data.get('detail'), "（无详细信息）"),
        ]

        if not isinstance(info, dict):
            lines.append("")
            lines.append("提示：传入数据格式异常，已按空结果显示")

        self._render_lines('r_log', lines)

    def show_py_result(self, info: dict) -> None:
        """把 Python 内核自检结果渲染进 py_log（容错：缺键/非dict/None 均不抛异常）"""
        data = info if isinstance(info, dict) else {}

        lines = [
            "===== Python 内核自检 =====",
            f"版本号：{_as_text(data.get('version'))}",
            f"实现类型：{_as_text(data.get('implementation'))}",
            f"解释器路径：{_as_text(data.get('executable'))}",
            "----- 详细信息 -----",
            _as_text(data.get('detail'), "（无详细信息）"),
        ]

        if not isinstance(info, dict):
            lines.append("")
            lines.append("提示：传入数据格式异常，已按空结果显示")

        self._render_lines('py_log', lines)

    def clear_r_log(self) -> None:
        """清空 R 输出框"""
        log_widget = self._get_log_widget('r_log')
        if log_widget is None:
            return
        try:
            log_widget.clear()
        except Exception:
            pass

    def clear_py_log(self) -> None:
        """清空 Python 输出框"""
        log_widget = self._get_log_widget('py_log')
        if log_widget is None:
            return
        try:
            log_widget.clear()
        except Exception:
            pass


__all__ = ['PageTemplateFunc']
