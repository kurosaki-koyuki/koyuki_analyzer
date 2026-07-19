# -*- coding: utf-8 -*-
"""
bulk差异分析模块 - 主层容器，管理Python/R版本切换
"""

from .ui_layout_bulk_diff import BulkDiffPageUI
from .ui_bind_bulk_diff import BulkDiffBind

from .py_diff import BulkDiffPyPageUI, BulkDiffPyBind, BulkDiffPyFunc, BulkDiffPyAnalysis
from .r_diff import BulkDiffRPageUI, BulkDiffRBind, BulkDiffRFunc, BulkDiffRAnalysis

__all__ = [
    'BulkDiffPageUI', 'BulkDiffBind',
    'BulkDiffPyPageUI', 'BulkDiffPyBind', 'BulkDiffPyFunc', 'BulkDiffPyAnalysis',
    'BulkDiffRPageUI', 'BulkDiffRBind', 'BulkDiffRFunc', 'BulkDiffRAnalysis'
]