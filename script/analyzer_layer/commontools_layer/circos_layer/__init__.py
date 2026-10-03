# -*- coding: utf-8 -*-
"""circos_layer —— 小工具主页「杂项分析类」里的 Circos 圈图页

分层（与项目其它页一致）：
  · `circos_analysis.py`  —— `CircosAnalysis` 绘图内核（纯 Python + matplotlib + pycirclize，**无 R**）
  · `ui_layout_circos.py` —— `CircosPageUI` 页面布局（本包由 UI worker 补齐）
  · `ui_func_circos.py`   —— `CircosFunc` 页面级工具（日志/样式转发）
  · `ui_bind_circos.py`   —— `CircosBind` 交互绑定

本 `__init__.py` **故意不做任何 import**：`page_intersect` 会在启动时按模块路径导入
各页面文件，若这里提前 import 尚未就绪的 UI 模块，会连带把整个页面注册表拖崩。
内核请显式导入：

    from script.analyzer_layer.commontools_layer.circos_layer.circos_analysis import CircosAnalysis

数据目录：`appdata/circos_data`（**只读**）；输出：`OUT_BASE/circos/<时间戳>/`。
"""
