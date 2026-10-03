# -*- coding: utf-8 -*-
"""
空转差异分析页模块

SpatialDiffPageUI / SpatialDiffBind / SpatialDiffFunc

契约: `_d_spec_spatial_diff.md`（本页 = 单细胞 `py_diff` 的近似 1:1 复刻
+ 空转独有「样本多选驱动注释选项」）。
★ 页包必须能独立导入，且 UI / Bind 类必须定义在本页模块里
  （测试 `test_each_page_package_imports_and_exports_its_ui_bind_classes` 冻结此约定）。
★ 导出口径与兄弟页 `spatial_expression_layer/__init__.py` 逐字对齐
  （UI / Bind / Func 三件套一起导出）。
"""

from .ui_layout_spatial_diff import SpatialDiffPageUI
from .ui_bind_spatial_diff import SpatialDiffBind
from .ui_func_spatial_diff import SpatialDiffFunc

__all__ = ['SpatialDiffPageUI', 'SpatialDiffBind', 'SpatialDiffFunc']
