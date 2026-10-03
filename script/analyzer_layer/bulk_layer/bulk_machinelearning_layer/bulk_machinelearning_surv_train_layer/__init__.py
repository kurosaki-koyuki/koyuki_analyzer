# -*- coding: utf-8 -*-
"""
bulk_machinelearning_surv_train_layer - 机器学习生存训练类子层
"""

from .ui_layout_bulk_machinelearning_surv_train import BulkMachineLearningSurvTrainPageUI
from .ui_bind_bulk_machinelearning_surv_train import BulkMachineLearningSurvTrainBind
from .ui_func_bulk_machinelearning_surv_train import BulkMachineLearningSurvTrainFunc
from .bulk_machinelearning_surv_train_analysis import BulkMachineLearningSurvTrainAnalysis

__all__ = [
    'BulkMachineLearningSurvTrainPageUI',
    'BulkMachineLearningSurvTrainBind',
    'BulkMachineLearningSurvTrainFunc',
    'BulkMachineLearningSurvTrainAnalysis',
]
