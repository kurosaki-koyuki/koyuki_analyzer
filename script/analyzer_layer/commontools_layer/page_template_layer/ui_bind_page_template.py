# -*- coding: utf-8 -*-
"""
页面模板界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作

职责边界（四层分离）：
- 本层（bind）只做信号绑定与流程编排，是“粘合内外”的唯一场所；
- 不直接操作数据、不写业务算法（版本探测在 analysis 层，日志/结果显示在 func 层）。
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.commontools_layer.page_template_layer.page_template_analysis import PageTemplateAnalysis
from script.analyzer_layer.commontools_layer.page_template_layer.ui_func_page_template import PageTemplateFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect


class PageTemplateBind:
    """页面模板功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, page_template_ui):
        # 主窗口引用：fix_music_controller_bindings 与音量同步都依赖 self.parent
        self.parent = parent_window
        self.page_template_ui = page_template_ui
        # analysis 层：只提供数据/算法能力，不做界面操作
        self.analysis = PageTemplateAnalysis()
        # func 层：只提供界面显示能力，不绑定信号、不做算法
        self.func = PageTemplateFunc(page_template_ui, parent_window)
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定（顺序固定：音乐控件 → 功能按钮 → 页面导航）"""
        self.bind_music_controls()
        self.bind_page_template_functions()
        self.bind_navigation()

    # ---------- 绑定区 ----------

    def bind_music_controls(self):
        """绑定音乐控制（照参照页做法，交给全局修复函数统一处理，避免信号重复绑定）"""
        if hasattr(self.page_template_ui, 'music_controller') and self.page_template_ui.music_controller:
            fix_music_controller_bindings(self, self.page_template_ui.music_controller)

    def bind_page_template_functions(self):
        """绑定模板页的功能按钮

        本仓库对“功能按钮”的惯例是 bind_button_with_sound：
        由 gui_styles.bind_button_with_sound 统一包裹 handler，自动处理成功/失败音效与日志，
        因此这里按惯例绑定 self.on_test_r_clicked / self.on_test_py_clicked。
        """
        # 日志控件仅用于音效绑定的结果提示；缺失时传 None（bind_button_with_sound 内部会跳过写入）
        r_log_widget = getattr(self.page_template_ui, 'r_log', None)
        py_log_widget = getattr(self.page_template_ui, 'py_log', None)

        # R 环境检测按钮
        if hasattr(self.page_template_ui, 'btn_test_r'):
            bind_button_with_sound(self.page_template_ui.btn_test_r, self.on_test_r_clicked,
                                   r_log_widget, "R 环境检测完成", "R 环境检测失败")

        # Python 环境检测按钮
        if hasattr(self.page_template_ui, 'btn_test_py'):
            bind_button_with_sound(self.page_template_ui.btn_test_py, self.on_test_py_clicked,
                                   py_log_widget, "Python 环境检测完成", "Python 环境检测失败")

    def bind_navigation(self):
        """绑定页面导航按钮（返回父页面 bulk_top_page）"""
        if hasattr(self.page_template_ui, 'btn_back_page_template'):
            # 用 lambda 吞掉 clicked 自带的 checked 参数，避免其被当作 page_name 传入
            self.page_template_ui.btn_back_page_template.clicked.connect(
                lambda: page_intersect.go_to_parent_page('page_template_page'))

    # ---------- 音乐控制辅助 ----------

    def set_volume(self, value):
        """设置音量（供 fix_music_controller_bindings 绑定音量滑块）"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    # ---------- 功能按钮处理（编排：清日志 → 提示 → analysis 取数 → func 显示） ----------

    def _write_hint(self, log_attr_name, message):
        """向指定日志控件写入一行提示（控件缺失时静默跳过，不影响主流程）"""
        log_widget = getattr(self.page_template_ui, log_attr_name, None)
        if log_widget is not None and hasattr(log_widget, 'append'):
            log_widget.append(message)

    def on_test_r_clicked(self):
        """检测 R 环境：清空日志 → 写入提示 → 取版本 → 显示结果（全过程异常兜底）"""
        try:
            self.func.clear_r_log()
            self._write_hint('r_log', "[INFO] 正在检测 R 环境…")
            # 探测会同步拉起子进程，先刷新一次界面，避免看起来像卡死
            QApplication.processEvents()

            info = self.analysis.get_r_version()
            self.func.show_r_result(info)

        except Exception as e:
            # 任何异常都落到结果展示中，保证按钮点击不会把主界面打崩
            self.func.show_r_result({
                'available': False,
                'version': '未知',
                'r_home': '',
                'detail': str(e)
            })

    def on_test_py_clicked(self):
        """检测 Python 环境：清空日志 → 写入提示 → 取版本 → 显示结果（全过程异常兜底）"""
        try:
            self.func.clear_py_log()
            self._write_hint('py_log', "[INFO] 正在检测 Python 环境…")
            # 探测会同步拉起子进程，先刷新一次界面，避免看起来像卡死
            QApplication.processEvents()

            info = self.analysis.get_py_version()
            self.func.show_py_result(info)

        except Exception as e:
            # 任何异常都落到结果展示中，保证按钮点击不会把主界面打崩
            self.func.show_py_result({
                'version': '未知',
                'implementation': '未知',
                'executable': '',
                'detail': str(e)
            })
