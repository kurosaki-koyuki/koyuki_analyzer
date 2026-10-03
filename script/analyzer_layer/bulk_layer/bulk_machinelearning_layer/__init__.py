# -*- coding: utf-8 -*-
"""
bulk 机器学习分析层模块 - 主层容器，管理数据加载类/差异训练类/生存训练类子层
（注：原「差异筛选类」空壳子层已移除，差异分析统一在差异训练类中完成训练+验证）
（注：原「生存筛选类」层已移除，生存分析统一在生存训练类中完成训练+评价+筛选）
"""

from .ui_layout_bulk_machinelearning import BulkMachineLearningPageUI
from .ui_bind_bulk_machinelearning import BulkMachineLearningBind
from .ui_func_bulk_machinelearning import BulkMachineLearningFunc
from .bulk_machinelearning_analysis import BulkMachineLearningAnalysis

from .bulk_machinelearning_loading_layer import (
    BulkMachineLearningLoadingPageUI,
    BulkMachineLearningLoadingBind,
    BulkMachineLearningLoadingFunc,
    BulkMachineLearningLoadingAnalysis,
)

from .bulk_machinelearning_diff_train_layer import (
    BulkMachineLearningDiffTrainPageUI,
    BulkMachineLearningDiffTrainBind,
    BulkMachineLearningDiffTrainFunc,
    BulkMachineLearningDiffTrainAnalysis,
)

from .bulk_machinelearning_surv_train_layer import (
    BulkMachineLearningSurvTrainPageUI,
    BulkMachineLearningSurvTrainBind,
    BulkMachineLearningSurvTrainFunc,
    BulkMachineLearningSurvTrainAnalysis,
)

__all__ = [
    # 主层容器
    'BulkMachineLearningPageUI',
    'BulkMachineLearningBind',
    'BulkMachineLearningFunc',
    'BulkMachineLearningAnalysis',
    # 数据加载类子层
    'BulkMachineLearningLoadingPageUI',
    'BulkMachineLearningLoadingBind',
    'BulkMachineLearningLoadingFunc',
    'BulkMachineLearningLoadingAnalysis',
    # 差异训练类子层
    'BulkMachineLearningDiffTrainPageUI',
    'BulkMachineLearningDiffTrainBind',
    'BulkMachineLearningDiffTrainFunc',
    'BulkMachineLearningDiffTrainAnalysis',
    # 生存训练类子层
    'BulkMachineLearningSurvTrainPageUI',
    'BulkMachineLearningSurvTrainBind',
    'BulkMachineLearningSurvTrainFunc',
    'BulkMachineLearningSurvTrainAnalysis',
]
