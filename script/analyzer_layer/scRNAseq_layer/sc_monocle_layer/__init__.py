# -*- coding: utf-8 -*-
"""
scRNAseq Monocle分析层 - 主层容器
左侧导航栏管理子层切换（初筛轨迹类、未来扩展的子层等）
背景图由主层统一管理，子层使用透明背景
"""

from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.ui_layout_sc_monocle import ScMonocleContainerPageUI
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.ui_bind_sc_monocle import ScMonocleContainerBind

# 子层模块（保留兼容性导出，外部若直接用子层类也可以访问）
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_initial_monocle_layer import (
    ScMonoclePageUI,
    ScMonocleBind,
    ScMonocleFunc,
    ScMonocleAnalysis,
)

__all__ = [
    # 主层容器类
    'ScMonocleContainerPageUI',
    'ScMonocleContainerBind',
    # 子层类（兼容性导出）
    'ScMonoclePageUI',
    'ScMonocleBind',
    'ScMonocleFunc',
    'ScMonocleAnalysis',
]
