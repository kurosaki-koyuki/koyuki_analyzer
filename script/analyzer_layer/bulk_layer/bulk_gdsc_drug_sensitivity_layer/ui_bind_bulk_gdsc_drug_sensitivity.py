# -*- coding: utf-8 -*-
"""
bulk GDSC药物敏感性分析界面功能绑定脚本 - 负责粘合内外，绑定信号，编排analysis与func的协作
"""

from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.bulk_layer.bulk_gdsc_drug_sensitivity_layer.bulk_gdsc_drug_sensitivity_analysis import BulkGdscDrugSensitivityAnalysis
from script.analyzer_layer.bulk_layer.bulk_gdsc_drug_sensitivity_layer.ui_func_bulk_gdsc_drug_sensitivity import BulkGdscDrugSensitivityFunc

class BulkGdscDrugSensitivityBind:
    def __init__(self, main_window, bulk_gdsc_drug_sensitivity_ui):
        self.main_window = main_window
        self.bulk_gdsc_drug_sensitivity_ui = bulk_gdsc_drug_sensitivity_ui
        self.analysis = BulkGdscDrugSensitivityAnalysis()
        self.func = BulkGdscDrugSensitivityFunc(bulk_gdsc_drug_sensitivity_ui)
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()

    def bind_navigation(self):
        if hasattr(self.bulk_gdsc_drug_sensitivity_ui, 'btn_back_bulk_gdsc_drug_sensitivity'):
            self.bulk_gdsc_drug_sensitivity_ui.btn_back_bulk_gdsc_drug_sensitivity.clicked.connect(self.handle_back)

    def handle_back(self):
        """返回bulk主页"""
        page_intersect.go_to_page_with_bind('bulk_top_page')