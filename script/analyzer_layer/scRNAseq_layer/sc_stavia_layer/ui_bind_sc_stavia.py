# -*- coding: utf-8 -*-
"""
单细胞StaVIA分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

import os
import traceback
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QFileDialog
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect
from script.utils_layer.import_config import OUT_BASE
from script.analyzer_layer.scRNAseq_layer.sc_stavia_layer.sc_stavia_analysis import ScStaviaAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_stavia_layer.ui_func_sc_stavia import ScStaviaFunc
from script.analyzer_layer.scRNAseq_layer.sc_stavia_layer.sc_stavia_worker import StaviaWorker


class ScStaviaBind:
    def __init__(self, main_window, sc_stavia_ui):
        self.main_window = main_window
        self.sc_stavia_ui = sc_stavia_ui
        self.analysis = ScStaviaAnalysis()
        self.func = ScStaviaFunc(sc_stavia_ui)
        self._worker = None
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_analysis()
        self.bind_filters()
        self.bind_export()

    def bind_navigation(self):
        if hasattr(self.sc_stavia_ui, 'btn_back_sc_stavia'):
            self.sc_stavia_ui.btn_back_sc_stavia.clicked.connect(lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page'))

    def bind_analysis(self):
        if hasattr(self.sc_stavia_ui, 'btn_run_stavia'):
            self.sc_stavia_ui.btn_run_stavia.clicked.connect(self.run_stavia_analysis)

    def bind_filters(self):
        if hasattr(self.sc_stavia_ui, 'stavia_main_combo'):
            self.sc_stavia_ui.stavia_main_combo.currentTextChanged.connect(self.on_main_combo_changed)

        if hasattr(self.sc_stavia_ui, 'stavia_filter1_enable'):
            self.sc_stavia_ui.stavia_filter1_enable.stateChanged.connect(self.on_filter1_enable_changed)

        if hasattr(self.sc_stavia_ui, 'stavia_filter1_combo'):
            self.sc_stavia_ui.stavia_filter1_combo.currentTextChanged.connect(self.on_filter1_combo_changed)

        if hasattr(self.sc_stavia_ui, 'stavia_filter2_enable'):
            self.sc_stavia_ui.stavia_filter2_enable.stateChanged.connect(self.on_filter2_enable_changed)

        if hasattr(self.sc_stavia_ui, 'stavia_filter2_combo'):
            self.sc_stavia_ui.stavia_filter2_combo.currentTextChanged.connect(self.on_filter2_combo_changed)

    def on_main_combo_changed(self, text):
        if self.adata is None:
            return
        if text and text in self.adata.obs.columns:
            unique_vals = sorted(self.adata.obs[text].unique().tolist())
            self.func.update_main_list(text, unique_vals)

    def on_filter1_enable_changed(self, state):
        enabled = state == Qt.Checked
        if hasattr(self.sc_stavia_ui, 'stavia_filter1_combo'):
            self.sc_stavia_ui.stavia_filter1_combo.setEnabled(enabled)
        if hasattr(self.sc_stavia_ui, 'stavia_filter1_list'):
            self.sc_stavia_ui.stavia_filter1_list.setEnabled(enabled)

    def on_filter1_combo_changed(self, text):
        if self.adata is None:
            return
        if text and text in self.adata.obs.columns:
            unique_vals = sorted(self.adata.obs[text].unique().tolist())
            self.func.update_filter1_list(text, unique_vals)

    def on_filter2_enable_changed(self, state):
        enabled = state == Qt.Checked
        if hasattr(self.sc_stavia_ui, 'stavia_filter2_combo'):
            self.sc_stavia_ui.stavia_filter2_combo.setEnabled(enabled)
        if hasattr(self.sc_stavia_ui, 'stavia_filter2_list'):
            self.sc_stavia_ui.stavia_filter2_list.setEnabled(enabled)

    def on_filter2_combo_changed(self, text):
        if self.adata is None:
            return
        if text and text in self.adata.obs.columns:
            unique_vals = sorted(self.adata.obs[text].unique().tolist())
            self.func.update_filter2_list(text, unique_vals)

    def sync_data_from_single_cell_main(self, scRNAseq_top_bind):
        if not scRNAseq_top_bind or not scRNAseq_top_bind.analysis:
            return

        self.adata = scRNAseq_top_bind.analysis.adata
        self.dataset_name = scRNAseq_top_bind.analysis.dataset_name
        self.dataset_output_dir = scRNAseq_top_bind.analysis.dataset_output_dir

        if self.adata is not None:
            self.analysis.set_data(self.adata, self.dataset_name, self.dataset_output_dir)
            self.func.log(f"已从单细胞主页同步数据: {self.dataset_name}")
            self.update_dropdown_options()

    def update_dropdown_options(self):
        if self.adata is None:
            return

        obsm_keys = list(self.adata.obsm.keys())
        embedding_keys = [k for k in obsm_keys if k.startswith('X_')]

        categorical_cols = [col for col in self.adata.obs.columns 
                           if self.adata.obs[col].dtype.name == 'category' or 
                           len(self.adata.obs[col].unique()) < min(50, len(self.adata))]

        self.func.update_use_rep_options([k for k in obsm_keys if 'pca' in k.lower()] or ['X_pca'])
        self.func.update_basis_options(embedding_keys or ['X_umap'])

        if hasattr(self.sc_stavia_ui, 'stavia_main_combo'):
            self.sc_stavia_ui.stavia_main_combo.clear()
            self.sc_stavia_ui.stavia_main_combo.addItems(categorical_cols)

        if hasattr(self.sc_stavia_ui, 'stavia_filter1_combo'):
            self.sc_stavia_ui.stavia_filter1_combo.clear()
            self.sc_stavia_ui.stavia_filter1_combo.addItems(categorical_cols)

        if hasattr(self.sc_stavia_ui, 'stavia_filter2_combo'):
            self.sc_stavia_ui.stavia_filter2_combo.clear()
            self.sc_stavia_ui.stavia_filter2_combo.addItems(categorical_cols)

        if categorical_cols:
            basis_idx = self.sc_stavia_ui.cb_basis.findText('X_umap')
            if basis_idx >= 0:
                self.sc_stavia_ui.cb_basis.setCurrentIndex(basis_idx)

            rep_idx = self.sc_stavia_ui.cb_use_rep.findText('X_pca')
            if rep_idx >= 0:
                self.sc_stavia_ui.cb_use_rep.setCurrentIndex(rep_idx)

            main_idx = self.sc_stavia_ui.stavia_main_combo.findText('seurat_clusters')
            if main_idx >= 0:
                self.sc_stavia_ui.stavia_main_combo.setCurrentIndex(main_idx)
                self.on_main_combo_changed('seurat_clusters')

    def run_stavia_analysis(self):
        if self.adata is None:
            self.func.log("错误: 未加载数据，请先在单细胞主页加载数据")
            return

        if self._worker is not None and self._worker.is_running:
            self.func.log("正在运行中，请等待完成")
            return

        self.func.clear_log()
        self.func.clear_results()
        self.func.log("开始StaVIA轨迹分析...")

        ncomps = self.sc_stavia_ui.spin_ncomps.value()
        knn = self.sc_stavia_ui.spin_knn.value()
        try:
            resolution = float(self.sc_stavia_ui.spin_resolution.text())
        except ValueError:
            resolution = 1.5
        memory = self.sc_stavia_ui.spin_memory.value()
        use_rep = self.sc_stavia_ui.cb_use_rep.currentText()
        clusters = self.sc_stavia_ui.stavia_main_combo.currentText() if hasattr(self.sc_stavia_ui, 'stavia_main_combo') else 'seurat_clusters'
        basis = self.sc_stavia_ui.cb_basis.currentText()

        re_dim = self.sc_stavia_ui.chk_re_dim.isChecked() if hasattr(self.sc_stavia_ui, 'chk_re_dim') else False

        filter_params = self._get_filter_params()

        self.func.log(f"参数设置:")
        self.func.log(f"  - PCA成分数: {ncomps}")
        self.func.log(f"  - KNN邻居数: {knn}")
        self.func.log(f"  - 聚类分辨率: {resolution}")
        self.func.log(f"  - 内存参数: {memory}")
        self.func.log(f"  - 使用矩阵: {use_rep}")
        self.func.log(f"  - 主注释列: {clusters}")
        self.func.log(f"  - 嵌入空间: {basis}")
        self.func.log(f"  - 重新降维: {'是' if re_dim else '否'}")

        if filter_params['main_col'] or filter_params['filter1_enabled'] or filter_params['filter2_enabled']:
            self.func.log(f"  - 筛选设置:")
            if filter_params['main_col']:
                self.func.log(f"    * 主注释: {filter_params['main_col']}")
                self.func.log(f"    * 选择组别: {filter_params['main_selected']}")
            if filter_params['filter1_enabled']:
                self.func.log(f"    * 筛选1: {filter_params['filter1_col']} = {filter_params['filter1_selected']}")
            if filter_params['filter2_enabled']:
                self.func.log(f"    * 筛选2: {filter_params['filter2_col']} = {filter_params['filter2_selected']}")

        self._set_run_button_enabled(False)

        params = {
            'ncomps': ncomps,
            'knn': knn,
            'resolution': resolution,
            'memory': memory,
            'use_rep': use_rep,
            'clusters': clusters,
            'basis': basis,
            're_dim': re_dim,
            'filter_params': filter_params,
        }

        self._worker = StaviaWorker()
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.plots_ready.connect(self._on_plots_ready)

        QTimer.singleShot(100, lambda: self._worker.run_analysis(self.analysis, params))

    def _on_worker_progress(self, message):
        self.func.log(message)

    def _on_plots_ready(self, plots):
        self.func.display_all_plots(plots)

    def _on_analysis_finished(self, success, message, results):
        self._set_run_button_enabled(True)
        self._worker = None

        if success:
            if results:
                results['dataset_name'] = self.dataset_name
                self.func.show_info(results)
            self.func.log("\n分析完成！")
        else:
            self.func.log(message)

    def _set_run_button_enabled(self, enabled):
        if hasattr(self.sc_stavia_ui, 'btn_run_stavia'):
            self.sc_stavia_ui.btn_run_stavia.setEnabled(enabled)
            self.sc_stavia_ui.btn_run_stavia.setText("▶ 运行StaVIA分析" if enabled else "运行中...")

    def _get_filter_params(self):
        params = {
            'main_col': None,
            'main_selected': [],
            'filter1_enabled': False,
            'filter1_col': None,
            'filter1_selected': [],
            'filter2_enabled': False,
            'filter2_col': None,
            'filter2_selected': [],
        }

        if hasattr(self.sc_stavia_ui, 'stavia_main_combo'):
            params['main_col'] = self.sc_stavia_ui.stavia_main_combo.currentText()
        if hasattr(self.sc_stavia_ui, 'stavia_main_list'):
            params['main_selected'] = [item.text() for item in self.sc_stavia_ui.stavia_main_list.selectedItems()]

        if hasattr(self.sc_stavia_ui, 'stavia_filter1_enable'):
            params['filter1_enabled'] = self.sc_stavia_ui.stavia_filter1_enable.isChecked()
        if hasattr(self.sc_stavia_ui, 'stavia_filter1_combo'):
            params['filter1_col'] = self.sc_stavia_ui.stavia_filter1_combo.currentText()
        if hasattr(self.sc_stavia_ui, 'stavia_filter1_list'):
            params['filter1_selected'] = [item.text() for item in self.sc_stavia_ui.stavia_filter1_list.selectedItems()]

        if hasattr(self.sc_stavia_ui, 'stavia_filter2_enable'):
            params['filter2_enabled'] = self.sc_stavia_ui.stavia_filter2_enable.isChecked()
        if hasattr(self.sc_stavia_ui, 'stavia_filter2_combo'):
            params['filter2_col'] = self.sc_stavia_ui.stavia_filter2_combo.currentText()
        if hasattr(self.sc_stavia_ui, 'stavia_filter2_list'):
            params['filter2_selected'] = [item.text() for item in self.sc_stavia_ui.stavia_filter2_list.selectedItems()]

        return params

    def bind_export(self):
        if hasattr(self.sc_stavia_ui, 'btn_export_png'):
            self.sc_stavia_ui.btn_export_png.clicked.connect(lambda: self.export_current_image('png'))
        if hasattr(self.sc_stavia_ui, 'btn_export_pdf'):
            self.sc_stavia_ui.btn_export_pdf.clicked.connect(lambda: self.export_current_image('pdf'))
        if hasattr(self.sc_stavia_ui, 'btn_export_svg'):
            self.sc_stavia_ui.btn_export_svg.clicked.connect(lambda: self.export_current_image('svg'))

    def export_current_image(self, fmt='png'):
        if not hasattr(self.sc_stavia_ui, 'tab_widget'):
            self.func.log("错误: 未找到标签页")
            return

        current_tab_name = self.sc_stavia_ui.tab_widget.tabText(self.sc_stavia_ui.tab_widget.currentIndex())
        fig = self.func.get_current_figure(current_tab_name)

        if fig is None:
            self.func.log(f"错误: 当前标签页 '{current_tab_name}' 没有可导出的图片")
            return

        default_dir = os.path.join(OUT_BASE, 'stavia')
        os.makedirs(default_dir, exist_ok=True)
        default_name = f"{self.dataset_name or 'stavia'}_{current_tab_name}.{fmt}"
        default_path = os.path.join(default_dir, default_name)

        file_filter = f"{fmt.upper()} Files (*.{fmt})"
        file_path, _ = QFileDialog.getSaveFileName(
            self.sc_stavia_ui.sc_stavia_page,
            f"导出{fmt.upper()}",
            default_path,
            file_filter
        )

        if file_path:
            try:
                fig.savefig(file_path, format=fmt, dpi=300, bbox_inches='tight')
                self.func.log(f"✓ 已导出: {file_path}")
            except Exception as e:
                self.func.log(f"✗ 导出失败: {str(e)}")

    def export_all_images(self, fmt='png'):
        if not self.analysis.plot_figures:
            self.func.log("错误: 没有可导出的图片，请先运行分析")
            return

        default_dir = os.path.join(OUT_BASE, 'stavia')
        os.makedirs(default_dir, exist_ok=True)

        saved = self.analysis.save_all_figures(output_dir=default_dir, fmt=fmt, dpi=300)
        for key, path in saved.items():
            if path:
                self.func.log(f"✓ {key} 已导出: {path}")
            else:
                self.func.log(f"✗ {key} 导出失败")