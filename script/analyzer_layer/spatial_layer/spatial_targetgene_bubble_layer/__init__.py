# -*- coding: utf-8 -*-
"""
空转「自定义气泡图」页模块

SpatialTargetgeneBubblePageUI / SpatialTargetgeneBubbleBind / SpatialTargetgeneBubbleFunc

契约: `_d_spec_v11_split_and_bubble.md` §2（本页 = 单细胞
`sc_targetgene_bubble_layer` 的近似 1:1 复刻 + 空转独有「样本多选驱动注释选项」，
取数/注释选项语义**继承** `SpatialDiffAnalysis`，与差异分析页逐位同源）。

★ 页包必须能独立导入，且 UI / Bind 类必须定义在本页模块里
  （测试 `test_each_page_package_imports_and_exports_its_ui_bind_classes` 冻结此约定）。
★ 导出口径与兄弟页 `spatial_diff_layer/__init__.py` 逐字对齐
  （UI / Bind / Func 三件套一起导出）。
★ 单细胞 `sc_targetgene_bubble_layer/` 缺 `__init__.py` 是缺陷（规格 §2.8 缺陷 3），
  **不照抄** —— 两页都建。
"""

from .ui_layout_spatial_targetgene_bubble import SpatialTargetgeneBubblePageUI
from .ui_bind_spatial_targetgene_bubble import SpatialTargetgeneBubbleBind
from .ui_func_spatial_targetgene_bubble import SpatialTargetgeneBubbleFunc

__all__ = ['SpatialTargetgeneBubblePageUI', 'SpatialTargetgeneBubbleBind',
           'SpatialTargetgeneBubbleFunc']
