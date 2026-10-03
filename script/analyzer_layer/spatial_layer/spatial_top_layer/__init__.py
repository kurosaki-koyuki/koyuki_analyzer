# -*- coding: utf-8 -*-
"""
空转分析**主页（hub）+ 数据集层**模块

迁移 2026-09-23：原来 22 个页脚本 + 5 个 R 平铺在 spatial_top_layer/，现在**每页一个文件夹**
（对齐 scRNAseq_layer / bulk_layer 的传统布局）：
  · spatial_top_layer/        主页 hub + 数据集层（data_analysis / manifest / 建库 R）
  · spatial_review_layer/     审查页（评分 / 星标 / 图集登记）
  · spatial_initial_layer/    总览页（图集浏览 + 一键批量导出）
  · spatial_expression_layer/ 表达量页
  · spatial_region_layer/     绘制区域页

★ 公开面**刻意保持与迁移前逐字一致（8 项）**：
  原扁平 __init__.py 就 re-export 了审查页 / 总览页的 UI+Func（M2a/M3 时为方便调用方加的），
  测试 `test_init_exports_frozen_all` / `test_init_exports_are_importable` 把它当冻结契约。
  迁移只改**文件位置**，不该顺手缩公开 API ⇒ 这里改为从**新页包**导入同样 4 个名字。
  （若要收缩成"只导出本页 4 项"——那是 bulk_top_layer 的做法——必须同时改契约与用例，
    属于单独的决策，见 docs/features/spatial_m2m3_contract.md §18.9。）
"""

from .spatial_data_analysis import SpatialDataManager
from .ui_layout_spatial_top import SpatialTopPageUI
from .ui_bind_spatial_top import SpatialTopBind
from .ui_func_spatial_top import SpatialTopFunc

# ---- 兼容再导出（位置变了，名字没变）----
from script.analyzer_layer.spatial_layer.spatial_review_layer.ui_layout_spatial_review import (
    SpatialReviewPageUI)
from script.analyzer_layer.spatial_layer.spatial_review_layer.ui_func_spatial_review import (
    SpatialReviewFunc)
from script.analyzer_layer.spatial_layer.spatial_initial_layer.ui_layout_spatial_initial import (
    SpatialInitialPageUI)
from script.analyzer_layer.spatial_layer.spatial_initial_layer.ui_func_spatial_initial import (
    SpatialInitialFunc)

__all__ = [
    'SpatialDataManager',
    'SpatialTopPageUI', 'SpatialTopBind', 'SpatialTopFunc',
    'SpatialReviewPageUI', 'SpatialReviewFunc',
    'SpatialInitialPageUI', 'SpatialInitialFunc',
]
