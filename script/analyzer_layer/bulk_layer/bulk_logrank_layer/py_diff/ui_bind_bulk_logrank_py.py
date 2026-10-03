# -*- coding: utf-8 -*-
"""
bulk Log-rank分析界面功能绑定脚本 - Python版本
全权负责粘合内外，绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.bulk_layer.bulk_logrank_layer.py_diff.bulk_logrank_py_analysis import BulkLogrankPyAnalysis
from script.analyzer_layer.bulk_layer.bulk_logrank_layer.py_diff.ui_func_bulk_logrank_py import BulkLogrankPyFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect

GENE_LIST_DEFAULT_TEXT = "全部基因（默认）"


class BulkLogrankPyBind:
    def __init__(self, parent, bulk_logrank_ui):
        self.parent = parent
        self.bulk_logrank_ui = bulk_logrank_ui
        self.analysis = BulkLogrankPyAnalysis()
        self.func = BulkLogrankPyFunc(bulk_logrank_ui, parent)
        self.func.analysis = self.analysis
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.bind_signals()

    def bind_signals(self):
        self.bind_music_controls()
        self.bind_logrank_functions()

    def bind_music_controls(self):
        if hasattr(self.bulk_logrank_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.bulk_logrank_ui.music_controller)

    def set_volume(self, value):
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def bind_logrank_functions(self):
        log_widget = getattr(self.bulk_logrank_ui, 'bulk_logrank_log', None)

        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_clinical_combo'):
            self.bulk_logrank_ui.bulk_logrank_clinical_combo.currentIndexChanged.connect(self.on_clinical_changed)

        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter1_enable'):
            self.bulk_logrank_ui.bulk_logrank_filter1_enable.stateChanged.connect(self.on_filter1_enabled)

        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter1_combo'):
            self.bulk_logrank_ui.bulk_logrank_filter1_combo.currentIndexChanged.connect(self.on_filter1_combo_changed)

        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter2_enable'):
            self.bulk_logrank_ui.bulk_logrank_filter2_enable.stateChanged.connect(self.on_filter2_enabled)

        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter2_combo'):
            self.bulk_logrank_ui.bulk_logrank_filter2_combo.currentIndexChanged.connect(self.on_filter2_combo_changed)

        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_use_fdr'):
            self.bulk_logrank_ui.bulk_logrank_use_fdr.stateChanged.connect(self.on_fdr_changed)

        if hasattr(self.bulk_logrank_ui, 'btn_run_logrank'):
            bind_button_with_sound(self.bulk_logrank_ui.btn_run_logrank, self.run_logrank_analysis,
                                   log_widget, "Log-rank分析完成", "Log-rank分析失败")

        if hasattr(self.bulk_logrank_ui, 'btn_export_csv'):
            bind_button_with_sound(self.bulk_logrank_ui.btn_export_csv, self.export_csv,
                                   log_widget, "Excel导出完成", "Excel导出失败")

        if hasattr(self.bulk_logrank_ui, 'btn_send_to_genelist'):
            bind_button_with_sound(self.bulk_logrank_ui.btn_send_to_genelist,
                                   self.send_to_gene_list_folder,
                                   log_widget, "已发送到基因列表文件夹", "发送到基因列表文件夹失败")

        if hasattr(self.bulk_logrank_ui, 'gene_search_btn') and self.func:
            self.bulk_logrank_ui.gene_search_btn.clicked.connect(self.func.search_gene)

        if hasattr(self.bulk_logrank_ui, 'gene_search_input') and self.func:
            self.bulk_logrank_ui.gene_search_input.returnPressed.connect(self.func.search_gene)

    def _get_gene_lists_dir(self):
        """基因列表目录（与WGCNA外部基因列表一致：项目根/appdata/genelists）"""
        return os.path.join(BASE_DIR, 'appdata', 'genelists')

    def _populate_gene_list_combo(self):
        """填充基因列表下拉框：默认全部基因 + appdata/genelists 下的 xlsx/txt 文件"""
        combo = getattr(self.bulk_logrank_ui, 'bulk_logrank_gene_list_combo', None)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()
        combo.addItem(GENE_LIST_DEFAULT_TEXT)

        gene_lists_dir = self._get_gene_lists_dir()
        if os.path.exists(gene_lists_dir):
            gene_files = sorted(f for f in os.listdir(gene_lists_dir)
                                if f.endswith('.xlsx') or f.endswith('.txt'))
            combo.addItems(gene_files)

        combo.blockSignals(False)

    def sync_data_from_bulk_main(self, bulk_top_bind):
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

        self.analysis.set_dataset_output_dir(self.dataset_output_dir)
        self.analysis.set_dataset_name(self.dataset_name)

        if 'time' not in self.adata.obs.columns and 'time (month)' not in self.adata.obs.columns:
            self.adata = None
            self.analysis.set_adata(None)
            self.func.log("这个数据集不能做生存分析，因为缺少time或time (month)列")
            return

        n_samples, n_genes = adata.shape
        obs_columns = self.analysis.get_obs_columns()

        self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")
        self.func.log(f"样本数: {n_samples}")
        self.func.log(f"基因数: {n_genes}")
        self.func.log(f"可用注释列: {len(obs_columns)} 个")

        self.func.update_clinical_combo(obs_columns)
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()
        self._populate_gene_list_combo()

    def on_clinical_changed(self):
        selected_col = self.bulk_logrank_ui.bulk_logrank_clinical_combo.currentText()

        if self.adata is None:
            self.func.hide_group_list()
            return

        if selected_col == "全部":
            self.func.show_clinical_col_list(False)
            self.bulk_logrank_ui.bulk_logrank_group_list.clear()
            self.bulk_logrank_ui.bulk_logrank_group_list.addItem("High vs Low")
            self.bulk_logrank_ui.bulk_logrank_group_list.selectAll()
        else:
            groups = self.analysis.get_obs_unique_values(selected_col)
            self.func.update_group_list(groups)

    def on_filter1_enabled(self, state):
        enabled = state == Qt.Checked
        self.func.on_filter1_enabled(enabled)

        if enabled and self.adata is not None:
            columns = self.analysis.get_obs_columns()
            survival_cols = ['time', 'time (month)', 'state']
            valid_cols = [col for col in columns if col not in survival_cols]
            self.func.update_filter_combo(self.bulk_logrank_ui.bulk_logrank_filter1_combo, valid_cols)

    def on_filter1_combo_changed(self):
        filter1_col = self.bulk_logrank_ui.bulk_logrank_filter1_combo.currentText()
        if filter1_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter1_col)
            self.func.update_filter_list(self.bulk_logrank_ui.bulk_logrank_filter1_list, groups)

    def on_filter2_enabled(self, state):
        enabled = state == Qt.Checked
        self.func.on_filter2_enabled(enabled)

        if enabled and self.adata is not None:
            columns = self.analysis.get_obs_columns()
            survival_cols = ['time', 'time (month)', 'state']
            valid_cols = [col for col in columns if col not in survival_cols]
            self.func.update_filter_combo(self.bulk_logrank_ui.bulk_logrank_filter2_combo, valid_cols)

    def on_filter2_combo_changed(self):
        filter2_col = self.bulk_logrank_ui.bulk_logrank_filter2_combo.currentText()
        if filter2_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter2_col)
            self.func.update_filter_list(self.bulk_logrank_ui.bulk_logrank_filter2_list, groups)

    def on_fdr_changed(self, state):
        fdr_enabled = state == Qt.Checked
        
        if hasattr(self.bulk_logrank_ui, 'bulk_logrank_filter_col_combo'):
            combo = self.bulk_logrank_ui.bulk_logrank_filter_col_combo
            
            if fdr_enabled:
                combo.setItemData(0, True, Qt.UserRole)
                combo.setItemData(1, True, Qt.UserRole)
            else:
                combo.setItemData(0, True, Qt.UserRole)
                combo.setItemData(1, False, Qt.UserRole)
                
                if combo.currentText() == "p_adj值":
                    combo.setCurrentIndex(0)

    def run_logrank_analysis(self):
        try:
            if self.adata is None:
                self.func.alert_error("请先加载数据")
                self.func.log("错误: self.adata为None")
                return

            clinical_col = self.func.get_clinical_col()
            if clinical_col == "全部":
                group_col = None
            else:
                group_col = clinical_col

            pval_threshold = self.bulk_logrank_ui.bulk_logrank_pval_spin.value()
            use_fdr = self.bulk_logrank_ui.bulk_logrank_use_fdr.isChecked()
            
            filter_col = self.bulk_logrank_ui.bulk_logrank_filter_col_combo.currentText()
            filter_col_type = 'p_val' if filter_col == "p值" else 'p_val_adj'

            filter1_col = None
            filter1_groups = []
            if self.bulk_logrank_ui.bulk_logrank_filter1_enable.isChecked():
                filter1_col = self.bulk_logrank_ui.bulk_logrank_filter1_combo.currentText()
                filter1_groups = self.func.get_filter1_groups()

            filter2_col = None
            filter2_groups = []
            if self.bulk_logrank_ui.bulk_logrank_filter2_enable.isChecked():
                filter2_col = self.bulk_logrank_ui.bulk_logrank_filter2_combo.currentText()
                filter2_groups = self.func.get_filter2_groups()

            # 基因范围：默认全部基因；选择列表文件则只分析列表中匹配的基因
            gene_list_file = None
            gene_list_text = GENE_LIST_DEFAULT_TEXT
            if hasattr(self.bulk_logrank_ui, 'bulk_logrank_gene_list_combo'):
                combo_text = self.bulk_logrank_ui.bulk_logrank_gene_list_combo.currentText()
                if combo_text and combo_text != GENE_LIST_DEFAULT_TEXT:
                    gene_list_text = combo_text
                    gene_list_file = os.path.join(BASE_DIR, 'appdata', 'genelists', combo_text)

            self.func.log("正在执行Log-rank分析...")
            self.func.log(f"基因总数: {len(self.adata.var_names)}")
            self.func.log(f"基因列表: {gene_list_text}")
            self.func.log(f"分组列: {group_col}")
            self.func.log(f"p值阈值: {pval_threshold}")
            self.func.log(f"过滤依据: {filter_col}")
            self.func.log(f"使用FDR校正: {use_fdr}")
            self.func.log(f"筛选1: {filter1_col} - {filter1_groups}")
            self.func.log(f"筛选2: {filter2_col} - {filter2_groups}")

            result = self.analysis.run_logrank_analysis(
                group_col=group_col,
                pval_threshold=pval_threshold,
                use_fdr=use_fdr,
                filter_col=filter_col_type,
                filter1_col=filter1_col,
                filter1_groups=filter1_groups,
                filter2_col=filter2_col,
                filter2_groups=filter2_groups,
                gene_list_file=gene_list_file
            )

            if result is None:
                self.func.alert_error("分析失败")
                self.func.log("错误: analysis.run_logrank_analysis返回None")
                return

            self.func.log(f"分析完成，结果基因数: {len(result)}")
            
            self.func.log("正在更新统计信息...")
            self.func.update_stats(result)
            
            self.func.log("正在显示结果...")
            self.func.display_results(result)

            self.func.alert_success("Log-rank分析完成")

        except Exception as e:
            self.func.alert_failure(f"Log-rank分析失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")
            import traceback
            traceback.print_exc()

    def _logrank_subsets(self):
        """→ `(favorable, unfavorable, all_genes)`（同一份内存结果 `analysis.result_df`）。

        与 `export_to_excel` 的三张工作表完全同源：
        `all_genes = favorable + unfavorable`（= 施工前的发送内容，保持这个顺序）。
        """
        df = getattr(self.analysis, 'result_df', None)
        if df is None or len(df) == 0 or 'gene' not in df.columns or 'prognosis' not in df.columns:
            return [], [], []

        favorable = df[df['prognosis'] == 'favorable']['gene'].tolist()
        unfavorable = df[df['prognosis'] == 'unfavorable']['gene'].tolist()
        return favorable, unfavorable, favorable + unfavorable

    def _collect_genes_for_send(self):
        """旧口径 payload（良好 + 不良合并）。"""
        _fav, _unf, all_genes = self._logrank_subsets()
        return all_genes

    def _collect_groups_for_send(self):
        """可选子集；默认**仅「全部」**（= 旧行为）。"""
        favorable, unfavorable, all_genes = self._logrank_subsets()
        return [("良好预后", favorable, False), ("不良预后", unfavorable, False),
                ("全部", all_genes, True)]

    def send_to_gene_list_folder(self):
        """把当前结果的预后相关基因发送到 `appdata/genelists`（契约 §3/§4，子集可选）。"""
        groups = [(l, g, d) for l, g, d in self._collect_groups_for_send() if g]
        defaults = [g for _l, g, d in groups if d]
        if not defaults:
            self.func.log("[WARN] 当前没有可发送的基因：请先执行Log-rank分析（或放宽p值阈值）")
            self.func.alert_error("当前没有可发送的基因，请先执行Log-rank分析")
            return

        parent_widget = getattr(self.func, 'parent_widget', None) or self.parent
        from script.utils_layer.gene_list_export import ask_and_send
        if len(groups) >= 2:
            r = ask_and_send(parent_widget, groups=groups, multi=True, prefix="Log-rank预后基因")
        else:                                   # 只有 1 个子集 → 沿用旧口径（不弹选择区）
            r = ask_and_send(parent_widget, defaults[0], prefix="Log-rank预后基因")
        if r.get("ok"):
            self.func.log("[INFO] " + str(r.get("message", "")))
            if r.get("selected_groups"):
                self.func.log("[INFO] 发送集合：" + "、".join(r["selected_groups"]))
        elif r.get("cancelled"):
            self.func.log("[INFO] 已取消发送")
        else:
            self.func.log("[WARN] " + str(r.get("message", "发送失败")))

    def export_csv(self):
        if self.analysis.result_df is None:
            self.func.alert_error("没有可导出的数据，请先执行分析")
            return

        default_filename = f"{self.dataset_name}_logrank_result.xlsx" if self.dataset_name else "logrank_result.xlsx"

        file_path = self.func.get_save_file_path("导出Excel", default_filename, "Excel Files (*.xlsx)")
        if not file_path:
            return

        try:
            self.analysis.export_to_excel(file_path)
            self.func.log(f"Excel已导出: {os.path.basename(file_path)}")
            self.func.alert_success(f"Excel导出完成\n{file_path}")
        except Exception as e:
            self.func.alert_failure(f"Excel导出失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")