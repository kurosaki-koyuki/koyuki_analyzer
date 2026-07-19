# -*- coding: utf-8 -*-
"""
bulk差异分析界面功能绑定脚本 - R版本
全权负责粘合内外，绑定信号 + 编排 analysis 与 func 的协作
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect
from script.utils_layer.import_config import *


class BulkDiffRBind:
    def __init__(self, main_window, bulk_diff_ui):
        self.main_window = main_window
        self.bulk_diff_ui = bulk_diff_ui
        self.adata = None
        self.analysis = None
        self.func = None
        self._init_analysis()
        self._init_func()
        self.bind_signals()

    def _init_analysis(self):
        """初始化分析器"""
        try:
            from script.analyzer_layer.bulk_layer.bulk_diff_layer.r_diff.bulk_diff_r_analysis import BulkDiffRAnalysis
            self.analysis = BulkDiffRAnalysis()
        except Exception as e:
            print(f"[DiffR] 初始化分析器失败: {e}")
            import traceback
            traceback.print_exc()

    def _init_func(self):
        """初始化功能层"""
        try:
            from script.analyzer_layer.bulk_layer.bulk_diff_layer.r_diff.ui_func_bulk_diff_r import BulkDiffRFunc
            self.func = BulkDiffRFunc(self.bulk_diff_ui, self.main_window)
        except Exception as e:
            print(f"[DiffR] 初始化功能层失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_buttons()
        self.bind_combo_boxes()

    def bind_buttons(self):
        """绑定按钮信号"""
        if hasattr(self.bulk_diff_ui, 'btn_run_diff') and self.func:
            self.bulk_diff_ui.btn_run_diff.clicked.connect(self.run_diff_analysis)

        if hasattr(self.bulk_diff_ui, 'btn_export_csv') and self.func:
            self.bulk_diff_ui.btn_export_csv.clicked.connect(self.export_results)

        if hasattr(self.bulk_diff_ui, 'gene_search_btn') and self.func:
            self.bulk_diff_ui.gene_search_btn.clicked.connect(self.func.search_gene)

        if hasattr(self.bulk_diff_ui, 'gene_search_input') and self.func:
            self.bulk_diff_ui.gene_search_input.returnPressed.connect(self.func.search_gene)

    def bind_combo_boxes(self):
        """绑定下拉框信号"""
        if hasattr(self.bulk_diff_ui, 'diff_group_combo'):
            self.bulk_diff_ui.diff_group_combo.currentIndexChanged.connect(self.on_group_col_changed)

        if hasattr(self.bulk_diff_ui, 'diff_filter1_col'):
            self.bulk_diff_ui.diff_filter1_col.currentIndexChanged.connect(self.on_filter1_col_changed)

        if hasattr(self.bulk_diff_ui, 'diff_filter2_col'):
            self.bulk_diff_ui.diff_filter2_col.currentIndexChanged.connect(self.on_filter2_col_changed)

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return

        self.adata = bulk_top_bind.analysis.adata
        dataset_name = bulk_top_bind.analysis.dataset_name
        dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir

        if self.analysis:
            self.analysis.set_adata(self.adata, dataset_name, dataset_output_dir)

        if self.func:
            self.func.log(f"已从bulk主页同步数据: {dataset_name}")

        self._populate_group_columns()

    def _populate_group_columns(self):
        """填充分组列下拉框"""
        if self.adata is None:
            return

        obs_cols = self.adata.obs.columns.tolist()

        if hasattr(self.bulk_diff_ui, 'diff_group_combo'):
            self.bulk_diff_ui.diff_group_combo.blockSignals(True)
            self.bulk_diff_ui.diff_group_combo.clear()
            for col in obs_cols:
                unique_vals = self.adata.obs[col].dropna().unique()
                if 2 <= len(unique_vals) <= 50:
                    self.bulk_diff_ui.diff_group_combo.addItem(col)
            self.bulk_diff_ui.diff_group_combo.blockSignals(False)

            if self.bulk_diff_ui.diff_group_combo.count() > 0:
                self.on_group_col_changed()

        if hasattr(self.bulk_diff_ui, 'diff_filter1_col'):
            self.bulk_diff_ui.diff_filter1_col.blockSignals(True)
            self.bulk_diff_ui.diff_filter1_col.clear()
            self.bulk_diff_ui.diff_filter1_col.addItem("不筛选")
            for col in obs_cols:
                self.bulk_diff_ui.diff_filter1_col.addItem(col)
            self.bulk_diff_ui.diff_filter1_col.blockSignals(False)

        if hasattr(self.bulk_diff_ui, 'diff_filter2_col'):
            self.bulk_diff_ui.diff_filter2_col.blockSignals(True)
            self.bulk_diff_ui.diff_filter2_col.clear()
            self.bulk_diff_ui.diff_filter2_col.addItem("不筛选")
            for col in obs_cols:
                self.bulk_diff_ui.diff_filter2_col.addItem(col)
            self.bulk_diff_ui.diff_filter2_col.blockSignals(False)

    def on_group_col_changed(self):
        """分组列改变时更新组别列表"""
        if self.adata is None:
            return

        col = self.bulk_diff_ui.diff_group_combo.currentText()
        if not col or col not in self.adata.obs.columns:
            return

        unique_vals = self.adata.obs[col].dropna().unique().tolist()
        unique_vals = [str(v) for v in unique_vals]

        self._fill_checkable_list(self.bulk_diff_ui.diff_group1_list, unique_vals)
        self._fill_checkable_list(self.bulk_diff_ui.diff_group2_list, unique_vals)

    def on_filter1_col_changed(self):
        """筛选条件1列改变时"""
        self._update_filter_list('diff_filter1_col', 'diff_filter1_list')

    def on_filter2_col_changed(self):
        """筛选条件2列改变时"""
        self._update_filter_list('diff_filter2_col', 'diff_filter2_list')

    def _update_filter_list(self, col_attr, list_attr):
        """更新筛选列表"""
        if self.adata is None:
            return

        col_widget = getattr(self.bulk_diff_ui, col_attr, None)
        list_widget = getattr(self.bulk_diff_ui, list_attr, None)

        if not col_widget or not list_widget:
            return

        col = col_widget.currentText()
        if not col or col == "不筛选" or col not in self.adata.obs.columns:
            list_widget.clear()
            list_widget.setEnabled(False)
            return

        list_widget.setEnabled(True)
        unique_vals = self.adata.obs[col].dropna().unique().tolist()
        unique_vals = [str(v) for v in unique_vals]
        self._fill_checkable_list(list_widget, unique_vals)

    def _fill_checkable_list(self, list_widget, items):
        """填充可勾选列表"""
        list_widget.clear()
        for item_text in items:
            item = QListWidgetItem(str(item_text))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            list_widget.addItem(item)

    def run_diff_analysis(self):
        """运行差异分析"""
        if not self.analysis or not self.func:
            return

        if self.adata is None:
            self.func.log("请先加载数据")
            return

        group_col = self.bulk_diff_ui.diff_group_combo.currentText()
        if not group_col:
            self.func.log("请选择分组列")
            return

        group1_list = self.func.get_selected_items(self.bulk_diff_ui.diff_group1_list)
        group2_list = self.func.get_selected_items(self.bulk_diff_ui.diff_group2_list)

        if not group1_list:
            self.func.log("请选择组1的组别")
            return
        if not group2_list:
            self.func.log("请选择组2的组别")
            return

        method_idx = self.bulk_diff_ui.diff_method_combo.currentIndex()
        method = "limma" if method_idx == 0 else "edger"

        pval_threshold = self.bulk_diff_ui.diff_pval_spin.value()
        logfc_threshold = self.bulk_diff_ui.diff_logfc_spin.value()

        filter1_col = None
        filter1_groups = None
        if hasattr(self.bulk_diff_ui, 'diff_filter1_col'):
            f1_col = self.bulk_diff_ui.diff_filter1_col.currentText()
            if f1_col and f1_col != "不筛选":
                filter1_col = f1_col
                filter1_groups = self.func.get_selected_items(self.bulk_diff_ui.diff_filter1_list)

        filter2_col = None
        filter2_groups = None
        if hasattr(self.bulk_diff_ui, 'diff_filter2_col'):
            f2_col = self.bulk_diff_ui.diff_filter2_col.currentText()
            if f2_col and f2_col != "不筛选":
                filter2_col = f2_col
                filter2_groups = self.func.get_selected_items(self.bulk_diff_ui.diff_filter2_list)

        self.func.log(f"开始差异分析 ({method})...")
        self.func.log(f"分组列: {group_col}")
        self.func.log(f"组1: {group1_list}")
        self.func.log(f"组2: {group2_list}")

        try:
            result_df = self.analysis.run_diff_analysis(
                group_col=group_col,
                group1_list=group1_list,
                group2_list=group2_list,
                method=method,
                filter1_col=filter1_col,
                filter1_groups=filter1_groups,
                filter2_col=filter2_col,
                filter2_groups=filter2_groups
            )

            if result_df is not None and len(result_df) > 0:
                summary = self.analysis.get_diff_summary(
                    pval_threshold=pval_threshold,
                    logfc_threshold=logfc_threshold
                )

                self.func.update_stats(summary)
                self.func.fill_result_table(
                    result_df,
                    pval_threshold=pval_threshold,
                    logfc_threshold=logfc_threshold
                )

                # 更新样本数
                group1_count = sum(1 for v in self.adata.obs[group_col].astype(str) if v in group1_list)
                group2_count = sum(1 for v in self.adata.obs[group_col].astype(str) if v in group2_list)
                self.func.update_group_counts(group1_count, group2_count)

                self.func.log(f"分析完成! 总基因: {summary['total']}, 上调: {summary['up']}, 下调: {summary['down']}")
            else:
                self.func.log("分析完成，但无结果")

        except Exception as e:
            self.func.log(f"分析失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def export_results(self):
        """导出结果"""
        if not self.analysis or self.analysis.result_df is None:
            self.func.alert_error("没有可导出的数据，请先执行分析")
            return

        import os

        if self.analysis and self.analysis.dataset_name:
            default_filename = f"{self.analysis.dataset_name}_diff_result.xlsx"
        else:
            default_filename = "diff_result.xlsx"

        file_path = self.func.get_save_file_path("导出Excel", default_filename, "Excel Files (*.xlsx)")
        if not file_path:
            return

        try:
            pval_threshold = self.bulk_diff_ui.diff_pval_spin.value()
            logfc_threshold = self.bulk_diff_ui.diff_logfc_spin.value()
            self.analysis.export_to_excel(file_path, pval_threshold=pval_threshold, logfc_threshold=logfc_threshold)
            self.func.log(f"Excel已导出: {os.path.basename(file_path)}")
            self.func.alert_success(f"Excel导出完成\n{file_path}")
        except Exception as e:
            self.func.alert_failure(f"Excel导出失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")
            import traceback
            traceback.print_exc()
