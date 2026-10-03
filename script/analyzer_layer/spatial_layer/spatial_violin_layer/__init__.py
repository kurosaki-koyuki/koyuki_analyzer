# -*- coding: utf-8 -*-
"""
空转「小提琴图」页模块（v11 从表达量分析页**整块解离**而来）

SpatialViolinPageUI / SpatialViolinBind / SpatialViolinFunc

契约: `_d_spec_v11_split_and_bubble.md` §1
  · 新页 `spatial_violin_page`（`attr_name` **逐字等于** `name`），
    目录 `script/analyzer_layer/spatial_layer/spatial_violin_layer/`，
    `parent_page = 'spatial_top_page'`（页内「← 返回主页」一律回 hub）；
  · 迁入文件**冻结 6 个**：`__init__.py` / `ui_layout_spatial_violin.py` /
    `ui_func_spatial_violin.py` / `ui_bind_spatial_violin.py` /
    `spatial_violin_analysis.py` / `spatial_violin_dump.R`（`.R` 与 analysis **同目录**，
    靠 `spatial_violin_analysis.resolve_dump_r_script()` 定位）；
  · 31 个小提琴控件属性名**逐字不变**（值可原样复用 `_EXPR_VIOLIN_FROZEN_ATTRS`）。

★ 页包必须能独立导入，且 UI / Bind 类必须定义在**本页模块**里
  （测试 `test_each_page_package_imports_and_exports_its_ui_bind_classes` 冻结此约定）。
★ 导出口径与兄弟页 `spatial_diff_layer/__init__.py` 逐字对齐（UI / Bind / Func 三件套一起导出）。
"""

from .ui_layout_spatial_violin import SpatialViolinPageUI
from .ui_bind_spatial_violin import SpatialViolinBind
from .ui_func_spatial_violin import SpatialViolinFunc

__all__ = ['SpatialViolinPageUI', 'SpatialViolinBind', 'SpatialViolinFunc']
