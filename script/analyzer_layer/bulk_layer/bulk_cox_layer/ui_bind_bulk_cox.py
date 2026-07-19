# -*- coding: utf-8 -*-
"""
bulk COX分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.bulk_layer.bulk_cox_layer.bulk_cox_analysis import BulkCoxAnalysis
from script.analyzer_layer.bulk_layer.bulk_cox_layer.ui_func_bulk_cox import BulkCoxFunc
from script.analyzer_layer.bulk_layer.bulk_cox_layer.bulk_cox_worker import BulkCoxWorker
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from PyQt5.QtCore import QTimer


class BulkCoxBind:
    """bulk COX分析功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, bulk_cox_ui):
        self.parent = parent_window
        self.bulk_cox_ui = bulk_cox_ui
        self.analysis = BulkCoxAnalysis()
        self.func = BulkCoxFunc(bulk_cox_ui, parent_window)
        self.func.analysis = self.analysis
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self._worker = None
        self.init_bindings()
        self._init_page()

    def _init_page(self):
        """初始化页面"""
        self.func.update_r_version_label()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_cox_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.bulk_cox_ui, 'btn_back'):
            self.bulk_cox_ui.btn_back.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.bulk_cox_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.bulk_cox_ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def bind_cox_functions(self):
        """绑定COX分析功能信号"""

        # 运行COX分析按钮
        if hasattr(self.bulk_cox_ui, 'btn_run_cox'):
            bind_button_with_sound(self.bulk_cox_ui.btn_run_cox, self.run_cox_analysis)

        # 导出按钮
        if hasattr(self.bulk_cox_ui, 'btn_export_csv'):
            bind_button_with_sound(self.bulk_cox_ui.btn_export_csv, self.export_results)

        # 扫描基因列表按钮
        if hasattr(self.bulk_cox_ui, 'btn_scan_gene_lists'):
            bind_button_with_sound(self.bulk_cox_ui.btn_scan_gene_lists, self._load_external_gene_lists)

        # 分析模式切换
        if hasattr(self.bulk_cox_ui, 'bulk_cox_mode_combo'):
            self.bulk_cox_ui.bulk_cox_mode_combo.currentIndexChanged.connect(self.on_mode_changed)

        # 临床协变量下拉框
        if hasattr(self.bulk_cox_ui, 'bulk_cox_covariate_combo'):
            self.bulk_cox_ui.bulk_cox_covariate_combo.currentIndexChanged.connect(self.on_covariate_changed)

        # 筛选1启用复选框
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter1_enable'):
            self.bulk_cox_ui.bulk_cox_filter1_enable.stateChanged.connect(self.on_filter1_enabled)

        # 基因搜索功能
        if hasattr(self.bulk_cox_ui, 'gene_search_btn') and self.func:
            self.bulk_cox_ui.gene_search_btn.clicked.connect(self.func.search_gene)

        if hasattr(self.bulk_cox_ui, 'gene_search_input') and self.func:
            self.bulk_cox_ui.gene_search_input.returnPressed.connect(self.func.search_gene)

        # 筛选1下拉框
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter1_combo'):
            self.bulk_cox_ui.bulk_cox_filter1_combo.currentIndexChanged.connect(self.on_filter1_combo_changed)

        # 筛选2启用复选框
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter2_enable'):
            self.bulk_cox_ui.bulk_cox_filter2_enable.stateChanged.connect(self.on_filter2_enabled)

        # 筛选2下拉框
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter2_combo'):
            self.bulk_cox_ui.bulk_cox_filter2_combo.currentIndexChanged.connect(self.on_filter2_combo_changed)

        # 基因筛选模式切换
        if hasattr(self.bulk_cox_ui, 'bulk_cox_gene_filter_mode_combo'):
            self.bulk_cox_ui.bulk_cox_gene_filter_mode_combo.currentIndexChanged.connect(self.on_gene_filter_mode_changed)

    def on_mode_changed(self):
        """分析模式切换处理"""
        mode_idx = self.bulk_cox_ui.bulk_cox_mode_combo.currentIndex()
        is_adjusted = mode_idx == 1

        if hasattr(self.bulk_cox_ui, 'bulk_cox_covariate_combo'):
            self.bulk_cox_ui.bulk_cox_covariate_combo.setEnabled(is_adjusted)
        if hasattr(self.bulk_cox_ui, 'bulk_cox_covariate_list'):
            self.bulk_cox_ui.bulk_cox_covariate_list.setEnabled(is_adjusted)

    def on_covariate_changed(self):
        """临床协变量变化处理"""
        col_name = self.bulk_cox_ui.bulk_cox_covariate_combo.currentText()
        if col_name and self.adata and col_name in self.adata.obs.columns:
            unique_vals = self.analysis.get_obs_unique_values(col_name)
            if hasattr(self.bulk_cox_ui, 'bulk_cox_covariate_list'):
                self.func.fill_checkable_list_widget(self.bulk_cox_ui.bulk_cox_covariate_list, unique_vals)

    def on_filter1_enabled(self, state):
        """筛选1启用状态变化处理"""
        enabled = state == Qt.Checked
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter1_combo'):
            self.bulk_cox_ui.bulk_cox_filter1_combo.setEnabled(enabled)
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter1_list'):
            self.bulk_cox_ui.bulk_cox_filter1_list.setEnabled(enabled)

    def on_filter1_combo_changed(self):
        """筛选1下拉框变化处理"""
        col_name = self.bulk_cox_ui.bulk_cox_filter1_combo.currentText()
        if col_name and self.adata and col_name in self.adata.obs.columns:
            unique_vals = self.analysis.get_obs_unique_values(col_name)
            if hasattr(self.bulk_cox_ui, 'bulk_cox_filter1_list'):
                self.func.fill_checkable_list_widget(self.bulk_cox_ui.bulk_cox_filter1_list, unique_vals)

    def on_filter2_enabled(self, state):
        """筛选2启用状态变化处理"""
        enabled = state == Qt.Checked
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter2_combo'):
            self.bulk_cox_ui.bulk_cox_filter2_combo.setEnabled(enabled)
        if hasattr(self.bulk_cox_ui, 'bulk_cox_filter2_list'):
            self.bulk_cox_ui.bulk_cox_filter2_list.setEnabled(enabled)

    def on_filter2_combo_changed(self):
        """筛选2下拉框变化处理"""
        col_name = self.bulk_cox_ui.bulk_cox_filter2_combo.currentText()
        if col_name and self.adata and col_name in self.adata.obs.columns:
            unique_vals = self.analysis.get_obs_unique_values(col_name)
            if hasattr(self.bulk_cox_ui, 'bulk_cox_filter2_list'):
                self.func.fill_checkable_list_widget(self.bulk_cox_ui.bulk_cox_filter2_list, unique_vals)

    def on_gene_filter_mode_changed(self):
        """基因筛选模式切换"""
        mode_idx = self.bulk_cox_ui.bulk_cox_gene_filter_mode_combo.currentIndex()

        if hasattr(self.bulk_cox_ui, 'bulk_cox_gene_count_input'):
            self.bulk_cox_ui.bulk_cox_gene_count_input.setEnabled(mode_idx == 1)

        if hasattr(self.bulk_cox_ui, 'bulk_cox_custom_gene_combo'):
            self.bulk_cox_ui.bulk_cox_custom_gene_combo.setEnabled(mode_idx == 2)

        if hasattr(self.bulk_cox_ui, 'bulk_cox_external_gene_combo'):
            self.bulk_cox_ui.bulk_cox_external_gene_combo.setEnabled(mode_idx == 3)
            if mode_idx == 3:
                self._load_external_gene_lists()

    def _load_external_gene_lists(self):
        """加载外部基因列表文件"""
        if not hasattr(self.bulk_cox_ui, 'bulk_cox_external_gene_combo'):
            return

        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        gene_lists_dir = os.path.join(base_dir, 'appdata', 'genelists')

        self.bulk_cox_ui.bulk_cox_external_gene_combo.blockSignals(True)
        self.bulk_cox_ui.bulk_cox_external_gene_combo.clear()
        self.bulk_cox_ui.bulk_cox_external_gene_combo.addItem("请选择...")

        if os.path.exists(gene_lists_dir):
            gene_files = [f for f in os.listdir(gene_lists_dir) if f.endswith('.xlsx') or f.endswith('.txt')]
            for f in sorted(gene_files):
                self.bulk_cox_ui.bulk_cox_external_gene_combo.addItem(f)

        self.bulk_cox_ui.bulk_cox_external_gene_combo.blockSignals(False)
        self.func.log(f"已扫描基因列表目录: {gene_lists_dir}")

    def _load_genes_from_file(self, filename):
        """从xlsx或txt文件加载基因列表"""
        import os
        import pandas as pd

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        gene_list_path = os.path.join(base_dir, 'appdata', 'genelists', filename)

        if not os.path.exists(gene_list_path):
            self.func.log(f"文件不存在: {gene_list_path}")
            return None

        try:
            if filename.endswith('.xlsx'):
                gene_df = pd.read_excel(gene_list_path)
                gene_list = gene_df.iloc[:, 0].tolist()
            else:
                with open(gene_list_path, 'r', encoding='utf-8') as f:
                    gene_list = [line.strip() for line in f if line.strip()]

            gene_list = [str(g).strip() for g in gene_list if pd.notna(g) and str(g).strip()]

            if self.adata is not None:
                available_genes = set(self.adata.var_names)
                matched_genes = [g for g in gene_list if g in available_genes]
                self.func.log(f"基因列表: {len(gene_list)}个基因，匹配到 {len(matched_genes)} 个")
                return matched_genes

            return gene_list

        except Exception as e:
            self.func.log(f"加载基因列表失败: {str(e)}")
            return None

    def run_cox_analysis(self):
        """运行COX分析（异步）"""
        if self._worker is not None and self._worker._running:
            self.func.log("正在运行中，请等待完成")
            return

        self.func.clear_log()

        if not self.adata:
            self.func.log("错误: 未加载数据")
            return

        try:
            mode_idx = self.bulk_cox_ui.bulk_cox_mode_combo.currentIndex()
            adjusted = mode_idx == 1

            clinical_covariates = None
            if adjusted:
                col_name = self.bulk_cox_ui.bulk_cox_covariate_combo.currentText()
                if col_name:
                    clinical_covariates = [col_name]

            filter1_col = None
            filter1_groups = None
            if self.bulk_cox_ui.bulk_cox_filter1_enable.isChecked():
                filter1_col = self.bulk_cox_ui.bulk_cox_filter1_combo.currentText()
                filter1_groups = self.func.get_selected_items(self.bulk_cox_ui.bulk_cox_filter1_list)

            filter2_col = None
            filter2_groups = None
            if self.bulk_cox_ui.bulk_cox_filter2_enable.isChecked():
                filter2_col = self.bulk_cox_ui.bulk_cox_filter2_combo.currentText()
                filter2_groups = self.func.get_selected_items(self.bulk_cox_ui.bulk_cox_filter2_list)

            gene_filter_mode = self.bulk_cox_ui.bulk_cox_gene_filter_mode_combo.currentIndex()
            gene_names = None

            if gene_filter_mode == 0:
                gene_names = None
                self.func.log("使用全部基因进行分析")
            elif gene_filter_mode == 1:
                try:
                    gene_count = int(self.bulk_cox_ui.bulk_cox_gene_count_input.text())
                    gene_names = self.analysis.filter_genes_by_top_n(n=gene_count)
                    self.func.log(f"使用前{gene_count}个基因进行分析")
                except ValueError:
                    gene_names = None
                    self.func.log("基因数量输入无效，使用全部基因")
            elif gene_filter_mode == 2:
                custom_gene = self.bulk_cox_ui.bulk_cox_custom_gene_combo.currentText()
                if custom_gene:
                    gene_names = [custom_gene]
                    self.func.log(f"使用自定义基因: {custom_gene}")
                else:
                    gene_names = None
                    self.func.log("未选择自定义基因，使用全部基因")
            elif gene_filter_mode == 3:
                gene_file = self.bulk_cox_ui.bulk_cox_external_gene_combo.currentText()
                if gene_file and gene_file != "请选择...":
                    gene_names = self._load_genes_from_file(gene_file)
                    if gene_names:
                        self.func.log(f"从 {gene_file} 加载了 {len(gene_names)} 个基因")
                    else:
                        self.func.log(f"从 {gene_file} 加载基因失败，使用全部基因")
                        gene_names = None
                else:
                    self.func.log("未选择基因列表文件，使用全部基因")

            total_gene_count = len(gene_names) if gene_names else self.adata.shape[1]

            self.func.log(f"开始{'多因素' if adjusted else '单因素'}COX分析...")
            self.func.log(f"样本数: {self.adata.shape[0]}")
            self.func.log(f"基因数: {total_gene_count}")

            self._disable_run_button()

            self._worker = BulkCoxWorker()
            self._worker.finished.connect(self._on_cox_finished)
            self._worker.progress.connect(self._on_cox_progress)
            
            QTimer.singleShot(100, lambda: self._worker.run_cox_analysis(
                analysis=self.analysis,
                gene_names=gene_names,
                total_gene_count=total_gene_count,
                clinical_covariates=clinical_covariates,
                adjusted=adjusted,
                filter1_col=filter1_col,
                filter1_groups=filter1_groups,
                filter2_col=filter2_col,
                filter2_groups=filter2_groups
            ))

        except Exception as e:
            self.func.log(f"分析错误: {str(e)}")
            import traceback
            traceback.print_exc()

    def _on_cox_progress(self, message):
        """COX分析进度回调"""
        self.func.log(message)
        print(f"[COX进度] {message}")

    def _on_cox_finished(self, success, result_df):
        """COX分析完成回调"""
        self._enable_run_button()
        self._worker = None

        if success and result_df is not None and len(result_df) > 0:
            self.func.log(f"分析完成! 共 {len(result_df)} 个基因")

            use_fdr = self.bulk_cox_ui.bulk_cox_fdr_mode_combo.currentIndex() == 0
            try:
                threshold = float(self.bulk_cox_ui.bulk_cox_fdr_threshold_input.text())
            except ValueError:
                threshold = 0.05

            self.func.result_df = result_df
            self.func.update_stats(result_df, use_fdr=use_fdr, threshold=threshold)
            self.func.fill_overall_table(result_df)
            self.func.fill_risk_table(result_df, use_fdr=use_fdr, threshold=threshold)
            self.func.fill_protective_table(result_df, use_fdr=use_fdr, threshold=threshold)
        elif success:
            self.func.log("分析完成，但无结果")
        else:
            self.func.log("分析失败")

    def _disable_run_button(self):
        """禁用运行按钮"""
        if hasattr(self.bulk_cox_ui, 'btn_run_cox'):
            self.bulk_cox_ui.btn_run_cox.setEnabled(False)
            self.bulk_cox_ui.btn_run_cox.setText("分析中...")

    def _enable_run_button(self):
        """启用运行按钮"""
        if hasattr(self.bulk_cox_ui, 'btn_run_cox'):
            self.bulk_cox_ui.btn_run_cox.setEnabled(True)
            self.bulk_cox_ui.btn_run_cox.setText("运行COX分析")

    def export_results(self):
        """导出结果"""
        if self.func.result_df is None:
            self.func.log("错误: 没有可导出的结果")
            return

        if not self.dataset_output_dir:
            self.func.log("错误: 未设置输出目录")
            return

        output_dir = os.path.join(self.dataset_output_dir, "COX_results")
        success = self.func.export_results(self.func.result_df, output_dir)

        if success:
            self.func.log(f"结果已导出到: {output_dir}")
        else:
            self.func.log("导出失败")

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return

        adata = bulk_top_bind.analysis.adata
        if adata is None:
            self.func.log("bulk主页未加载数据")
            return

        self.adata = adata
        self.analysis.set_adata(adata)
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir

        self.analysis.set_dataset_name(self.dataset_name)
        self.analysis.set_dataset_output_dir(self.dataset_output_dir)

        obs_columns = self.analysis.get_obs_columns()

        self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")
        self.func.log(f"样本数: {adata.shape[0]}")
        self.func.log(f"基因数: {adata.shape[1]}")

        self.func.update_clinical_combo(obs_columns)
        self.func.update_filter1_combo(obs_columns)
        self.func.update_filter2_combo(obs_columns)

        self.func.update_r_version_label()

        if self.analysis.is_available():
            r_version = self.analysis.get_r_version()
            self.func.log(f"R环境: {r_version}")
        else:
            self.func.log("R环境不可用")