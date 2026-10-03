# -*- coding: utf-8 -*-
"""
bulk差异分析界面功能绑定脚本 - Python版本
全权负责粘合内外，绑定信号 + 编排 analysis 与 func 的协作
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtCore import Qt


class BulkDiffPyBind:
    def __init__(self, main_window, bulk_diff_ui):
        self.main_window = main_window
        self.bulk_diff_ui = bulk_diff_ui
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_combo_boxes()

    def bind_navigation(self):
        if hasattr(self.bulk_diff_ui, 'btn_back_bulk_diff'):
            self.bulk_diff_ui.btn_back_bulk_diff.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('bulk_top_page')
            )

    def bind_combo_boxes(self):
        """绑定分组/筛选下拉框信号"""
        if hasattr(self.bulk_diff_ui, 'diff_group_combo'):
            self.bulk_diff_ui.diff_group_combo.currentIndexChanged.connect(self.on_group_col_changed)

        if hasattr(self.bulk_diff_ui, 'diff_filter1_col'):
            self.bulk_diff_ui.diff_filter1_col.currentIndexChanged.connect(self.on_filter1_col_changed)

        if hasattr(self.bulk_diff_ui, 'diff_filter2_col'):
            self.bulk_diff_ui.diff_filter2_col.currentIndexChanged.connect(self.on_filter2_col_changed)

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据，并填充分组/筛选下拉框"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return

        self.adata = bulk_top_bind.analysis.adata
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir

        if self.adata is None:
            return

        log_widget = getattr(self.bulk_diff_ui, 'diff_log', None)
        if log_widget is not None:
            log_widget.append(f"已从bulk主页同步数据: {self.dataset_name}")

        self._populate_group_columns()

    def _populate_group_columns(self):
        """填充分组列与筛选列下拉框"""
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
        """分组列改变时更新组别1/组别2列表"""
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
        """筛选条件1列改变时更新其取值列表"""
        self._update_filter_list('diff_filter1_col', 'diff_filter1_list')

    def on_filter2_col_changed(self):
        """筛选条件2列改变时更新其取值列表"""
        self._update_filter_list('diff_filter2_col', 'diff_filter2_list')

    def _update_filter_list(self, col_attr, list_attr):
        """更新筛选取值列表"""
        if self.adata is None:
            return

        col_widget = getattr(self.bulk_diff_ui, col_attr, None)
        list_widget = getattr(self.bulk_diff_ui, list_attr, None)

        if col_widget is None or list_widget is None:
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
