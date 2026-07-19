# -*- coding: utf-8 -*-
"""
scRNAseq 药物敏感性分析界面功能绑定脚本 - 负责粘合内外，绑定信号，编排analysis与func的协作
"""

from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.scRNAseq_layer.sc_gdsc_drug_sensitivity_layer.sc_gdsc_drug_sensitivity_analysis import ScGdscDrugSensitivityAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_gdsc_drug_sensitivity_layer.ui_func_sc_gdsc_drug_sensitivity import ScGdscDrugSensitivityFunc

class ScGdscDrugSensitivityBind:
    def __init__(self, main_window, sc_gdsc_drug_sensitivity_ui):
        self.main_window = main_window
        self.sc_gdsc_drug_sensitivity_ui = sc_gdsc_drug_sensitivity_ui
        self.analysis = ScGdscDrugSensitivityAnalysis()
        self.func = ScGdscDrugSensitivityFunc(sc_gdsc_drug_sensitivity_ui)
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()

    def bind_navigation(self):
        if hasattr(self.sc_gdsc_drug_sensitivity_ui, 'btn_back_sc_gdsc_drug_sensitivity'):
            self.sc_gdsc_drug_sensitivity_ui.btn_back_sc_gdsc_drug_sensitivity.clicked.connect(self.handle_back)

    def handle_back(self):
        """返回单细胞主页"""
        page_intersect.go_to_page_with_bind('scRNAseq_top_page')