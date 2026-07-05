# -*- coding: utf-8 -*-
"""
差异分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.scRNAseq_layer.diff_layer.diff_analysis import DiffAnalysis
from script.analyzer_layer.scRNAseq_layer.diff_layer.ui_func_diff import DiffFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect


class DiffBind:
    """差异分析功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, diff_ui):
        self.parent = parent_window
        self.diff_ui = diff_ui
        self.analysis = DiffAnalysis()
        self.func = DiffFunc(diff_ui, parent_window)
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_diff_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.diff_ui, 'btn_back_diff'):
            self.diff_ui.btn_back_diff.clicked.connect(lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page'))

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从单细胞分析主界面同步数据"""
        try:
            if single_cell_bind is None:
                single_cell_bind = getattr(self.parent, 'scRNAseq_top_bind', None)
            
            if single_cell_bind is None:
                return

            if hasattr(single_cell_bind, 'analysis') and single_cell_bind.analysis.adata is not None:
                self.analysis.set_adata(single_cell_bind.analysis.adata)
                self.load_groups()
            
            if hasattr(single_cell_bind, 'analysis') and single_cell_bind.analysis.dataset_output_dir is not None:
                self.analysis.set_dataset_output_dir(single_cell_bind.analysis.dataset_output_dir)

        except Exception as e:
            print(f"差异分析同步数据时出错: {str(e)}")

    def sync_data_from_analysis(self, analysis_bind=None):
        """从初步分析页面同步数据（兼容旧接口）"""
        self.sync_data_from_single_cell_main(analysis_bind)

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.diff_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.diff_ui.music_controller)

    def bind_diff_functions(self):
        """绑定差异分析功能信号"""
        log_widget = getattr(self.diff_ui, 'diff_log', None)

        if hasattr(self.diff_ui, 'btn_run_diff'):
            bind_button_with_sound(self.diff_ui.btn_run_diff, self.run_diff_analysis,
                                   log_widget, "差异分析完成", "差异分析失败")

        if hasattr(self.diff_ui, 'btn_export_csv'):
            bind_button_with_sound(self.diff_ui.btn_export_csv, self.export_csv,
                                   log_widget, "CSV导出完成", "CSV导出失败")

        if hasattr(self.diff_ui, 'btn_export_png'):
            bind_button_with_sound(self.diff_ui.btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        if hasattr(self.diff_ui, 'diff_group_combo'):
            self.diff_ui.diff_group_combo.currentIndexChanged.connect(self.on_group_combo_changed)

    # ---------- 分组加载 ----------

    def on_group_combo_changed(self):
        """分组下拉框变化时更新分组列表"""
        self.load_groups()

    def load_groups(self):
        """加载分组列表"""
        try:
            if self.analysis.adata is None:
                return

            groups = self.analysis.get_available_groups()
            if not groups:
                return

            self.func.set_combo_items(self.diff_ui.diff_group_combo, groups)

            current_group = self.diff_ui.diff_group_combo.currentText()
            if current_group:
                unique_vals = self.analysis.get_group_unique_vals(current_group)
                self.func.update_group_list(current_group, unique_vals)

            self.func.log(f"加载分组完成，共 {len(groups)} 个可选列")

        except Exception as e:
            self.func.alert_failure(f"加载分组失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    # ---------- 差异分析 ----------

    def run_diff_analysis(self):
        """执行差异分析"""
        try:
            group_col = self.diff_ui.diff_group_combo.currentText()
            selected_items = [item.text() for item in self.diff_ui.diff_group_list.selectedItems()]

            if not group_col:
                self.func.alert_error("请先选择分组列")
                return

            if len(selected_items) < 2:
                self.func.alert_error("请至少选择2个分组进行比较")
                return

            method_map = {0: "t", 1: "mannwhitney", 2: "logistic"}
            method = method_map.get(self.diff_ui.diff_method_combo.currentIndex(), "mannwhitney")
            min_cells = self.diff_ui.diff_min_cells.value()
            min_expr = self.diff_ui.diff_min_expr.value()
            use_fdr = self.diff_ui.diff_use_fdr.isChecked()

            self.func.log("开始差异分析...")
            self.func.log(f"分组: {group_col}")
            self.func.log(f"比较: {' vs '.join(selected_items)}")
            self.func.log(f"方法: {method}, min_cells={min_cells}")

            results_df = self.analysis.run_diff_analysis(
                group_col=group_col,
                selected_groups=selected_items,
                method=method,
                min_cells=min_cells,
                min_expr=min_expr,
                use_fdr=use_fdr
            )

            self.func.update_diff_stats(results_df, selected_items)
            self.func.fill_result_tables(
                results_df,
                results_df[results_df['change'] == 'up'],
                results_df[results_df['change'] == 'down']
            )
            self.func.render_volcano_plot(results_df, group_col, selected_items)

            self.func.log(f"找到 {len(results_df)} 个差异基因")

        except ValueError as e:
            self.func.alert_error(str(e))
        except Exception as e:
            self.func.alert_failure(f"差异分析失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    # ---------- 导出 ----------

    def export_csv(self):
        """导出结果为CSV"""
        if self.analysis.diff_gene_df is None or len(self.analysis.diff_gene_df) == 0:
            self.func.alert_error("请先执行差异分析")
            return

        default_name = f"diff_genes_{self.analysis.group_col}.csv"
        save_path = self.func.get_save_file_path("导出差异基因结果", default_name, "CSV文件 (*.csv)")

        if save_path:
            try:
                self.analysis.export_csv(save_path)
                self.func.alert_success(f"结果已保存到:\n{save_path}")
            except Exception as e:
                self.func.alert_failure(f"导出失败: {str(e)}")

    def export_png(self):
        """导出火山图为PNG"""
        if self.analysis.diff_gene_df is None or len(self.analysis.diff_gene_df) == 0:
            self.func.alert_error("请先执行差异分析")
            return

        default_name = f"volcano_plot_{self.analysis.group_col}.png"
        save_path = self.func.get_save_file_path("导出火山图", default_name, "PNG文件 (*.png)")

        if save_path:
            try:
                self.analysis.export_png(save_path)
                self.func.alert_success(f"火山图已保存到:\n{save_path}")
            except Exception as e:
                self.func.alert_failure(f"导出失败: {str(e)}")

    # ---------- 跨层桥接 ----------

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def set_adata(self, adata):
        """设置adata对象"""
        self.analysis.set_adata(adata)

    def set_dataset_output_dir(self, dataset_output_dir):
        """设置数据集输出目录"""
        self.analysis.set_dataset_output_dir(dataset_output_dir)
