# -*- coding: utf-8 -*-
"""
自定义小提琴图界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.scRNAseq_layer.violin_layer.violin_analysis import ViolinAnalysis
from script.analyzer_layer.scRNAseq_layer.violin_layer.ui_func_violin import ViolinFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect


class ViolinBind:
    """小提琴图功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, violin_ui):
        self.parent = parent_window
        self.violin_ui = violin_ui
        self.analysis = ViolinAnalysis()
        self.func = ViolinFunc(violin_ui, parent_window)
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_violin_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.violin_ui, 'btn_back_violin'):
            self.violin_ui.btn_back_violin.clicked.connect(lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page'))

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从单细胞分析主界面同步数据"""
        try:
            if single_cell_bind is None:
                single_cell_bind = getattr(self.parent, 'scRNAseq_top_bind', None)
            
            if single_cell_bind is None:
                return

            if hasattr(single_cell_bind, 'analysis') and single_cell_bind.analysis.adata is not None:
                self.analysis.set_adata(single_cell_bind.analysis.adata)
            
            if hasattr(single_cell_bind, 'analysis') and single_cell_bind.analysis.dataset_output_dir is not None:
                self.analysis.set_dataset_output_dir(single_cell_bind.analysis.dataset_output_dir)

        except Exception as e:
            print(f"小提琴图同步数据时出错: {str(e)}")

    def sync_data_from_analysis(self, analysis_bind=None):
        """从初步分析页面同步数据（兼容旧接口）"""
        self.sync_data_from_single_cell_main(analysis_bind)

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.violin_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.violin_ui.music_controller)

    def bind_violin_functions(self):
        """绑定小提琴图功能信号"""
        log_widget = getattr(self.violin_ui, 'violin_log', None)

        if hasattr(self.violin_ui, 'btn_load_gene'):
            bind_button_with_sound(self.violin_ui.btn_load_gene, self.load_gene,
                                   log_widget, "基因加载完成", "基因加载失败")

        if hasattr(self.violin_ui, 'violin_main_combo'):
            self.violin_ui.violin_main_combo.currentIndexChanged.connect(self.on_main_combo_changed)

        if hasattr(self.violin_ui, 'violin_filter1_combo'):
            self.violin_ui.violin_filter1_combo.currentIndexChanged.connect(self.on_filter1_combo_changed)

        if hasattr(self.violin_ui, 'violin_filter2_combo'):
            self.violin_ui.violin_filter2_combo.currentIndexChanged.connect(self.on_filter2_combo_changed)

        if hasattr(self.violin_ui, 'violin_filter1_enable'):
            self.violin_ui.violin_filter1_enable.stateChanged.connect(self.on_filter1_enable_changed)

        if hasattr(self.violin_ui, 'violin_filter2_enable'):
            self.violin_ui.violin_filter2_enable.stateChanged.connect(self.on_filter2_enable_changed)

        if hasattr(self.violin_ui, 'btn_draw_violin'):
            bind_button_with_sound(self.violin_ui.btn_draw_violin, self.draw_violin_plot,
                                   log_widget, "绘图完成", "绘图失败")

        if hasattr(self.violin_ui, 'btn_export_violin_png'):
            bind_button_with_sound(self.violin_ui.btn_export_violin_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        if hasattr(self.violin_ui, 'btn_export_violin_pdf'):
            bind_button_with_sound(self.violin_ui.btn_export_violin_pdf, self.export_pdf,
                                   log_widget, "PDF导出完成", "PDF导出失败")

        if hasattr(self.violin_ui, 'btn_export_violin_svg'):
            bind_button_with_sound(self.violin_ui.btn_export_violin_svg, self.export_svg,
                                   log_widget, "SVG导出完成", "SVG导出失败")

        if hasattr(self.violin_ui, 'btn_export_violin_plot_csv'):
            bind_button_with_sound(self.violin_ui.btn_export_violin_plot_csv, self.export_plot_csv,
                                   log_widget, "CSV导出完成", "CSV导出失败")

        self.on_main_combo_changed()
        self.on_filter1_combo_changed()
        self.on_filter2_combo_changed()

    def on_main_combo_changed(self):
        """主注释下拉框变化"""
        group = self.violin_ui.violin_main_combo.currentText()
        unique_vals = self.analysis.get_group_unique_vals(group)
        self.func.update_main_list(group, unique_vals)

    def on_filter1_combo_changed(self):
        """筛选1下拉框变化"""
        if not hasattr(self.violin_ui, 'violin_filter1_combo') or not hasattr(self.violin_ui, 'violin_filter1_list'):
            return
        group = self.violin_ui.violin_filter1_combo.currentText()
        if group:
            unique_vals = self.analysis.get_group_unique_vals(group)
            self.func.update_filter1_list(group, unique_vals)

    def on_filter2_combo_changed(self):
        """筛选2下拉框变化"""
        if not hasattr(self.violin_ui, 'violin_filter2_combo') or not hasattr(self.violin_ui, 'violin_filter2_list'):
            return
        group = self.violin_ui.violin_filter2_combo.currentText()
        if group:
            unique_vals = self.analysis.get_group_unique_vals(group)
            self.func.update_filter2_list(group, unique_vals)

    def on_filter1_enable_changed(self, state):
        """筛选1启用/禁用"""
        enabled = state == Qt.Checked
        if hasattr(self.violin_ui, 'violin_filter1_combo'):
            self.violin_ui.violin_filter1_combo.setEnabled(enabled)
        if hasattr(self.violin_ui, 'violin_filter1_list'):
            self.violin_ui.violin_filter1_list.setEnabled(enabled)

    def on_filter2_enable_changed(self, state):
        """筛选2启用/禁用"""
        enabled = state == Qt.Checked
        if hasattr(self.violin_ui, 'violin_filter2_combo'):
            self.violin_ui.violin_filter2_combo.setEnabled(enabled)
        if hasattr(self.violin_ui, 'violin_filter2_list'):
            self.violin_ui.violin_filter2_list.setEnabled(enabled)

    def load_gene(self):
        """加载基因数据"""
        gene_name = self.violin_ui.violin_gene_input.text().strip()

        try:
            groups, cell_count = self.analysis.load_gene(gene_name)

            self.func.set_combo_items(self.violin_ui.violin_main_combo, groups)
            if hasattr(self.violin_ui, 'violin_filter1_combo'):
                self.func.set_combo_items(self.violin_ui.violin_filter1_combo, groups)
            if hasattr(self.violin_ui, 'violin_filter2_combo'):
                self.func.set_combo_items(self.violin_ui.violin_filter2_combo, groups)

            self.on_main_combo_changed()
            self.on_filter1_combo_changed()
            self.on_filter2_combo_changed()

            self.func.log(f"加载 {gene_name} 完成")
            self.func.log(f"   细胞数: {cell_count}")
            self.func.log(f"   可用注释: {len(groups)}")

        except ValueError as e:
            self.func.alert_error(str(e))
        except Exception as e:
            self.func.alert_failure(f"加载失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    def draw_violin_plot(self):
        """绘制小提琴图（三种类型）"""
        try:
            main_col = self.violin_ui.violin_main_combo.currentText()
            selected_items = [item.text() for item in self.violin_ui.violin_main_list.selectedItems()]

            filter1_col = None
            filter1_selected = []
            if hasattr(self.violin_ui, 'violin_filter1_enable') and self.violin_ui.violin_filter1_enable.isChecked():
                filter1_col = self.violin_ui.violin_filter1_combo.currentText()
                filter1_selected = [item.text() for item in self.violin_ui.violin_filter1_list.selectedItems()]

            filter2_col = None
            filter2_selected = []
            if hasattr(self.violin_ui, 'violin_filter2_enable') and self.violin_ui.violin_filter2_enable.isChecked():
                filter2_col = self.violin_ui.violin_filter2_combo.currentText()
                filter2_selected = [item.text() for item in self.violin_ui.violin_filter2_list.selectedItems()]

            title_name = self.violin_ui.violin_title_name.text().strip() if hasattr(self.violin_ui, 'violin_title_name') else None
            title_size = self.violin_ui.violin_title_size.value() if hasattr(self.violin_ui, 'violin_title_size') else 16
            ylabel_name = self.violin_ui.violin_ylabel_name.text().strip() if hasattr(self.violin_ui, 'violin_ylabel_name') else None
            axis_size = self.violin_ui.violin_axis_size.value() if hasattr(self.violin_ui, 'violin_axis_size') else 12
            pairwise_enable = self.violin_ui.violin_pairwise_enable.isChecked() if hasattr(self.violin_ui, 'violin_pairwise_enable') else True
            pairwise_size = self.violin_ui.violin_pairwise_size.value() if hasattr(self.violin_ui, 'violin_pairwise_size') else 11

            pairwise_selected_pairs = []
            if hasattr(self.violin_ui, 'violin_pairwise_list') and pairwise_enable:
                pairwise_selected_pairs = [item.text() for item in self.violin_ui.violin_pairwise_list.selectedItems()]

            pvalue_mode = self.violin_ui.violin_pvalue_mode.currentIndex() if hasattr(self.violin_ui, 'violin_pvalue_mode') else 0
            overall_pvalue = self.violin_ui.violin_overall_pvalue.isChecked() if hasattr(self.violin_ui, 'violin_overall_pvalue') else False

            cell_count, violin_box_path, box_path, violin_path = self.analysis.draw_violin_plot(
                main_col, selected_items,
                filter1_col=filter1_col, filter1_selected=filter1_selected,
                filter2_col=filter2_col, filter2_selected=filter2_selected,
                title_name=title_name,
                title_size=title_size,
                ylabel_name=ylabel_name,
                axis_size=axis_size,
                pairwise_enable=pairwise_enable,
                pairwise_size=pairwise_size,
                pairwise_selected_pairs=pairwise_selected_pairs,
                pvalue_mode=pvalue_mode,
                overall_pvalue=overall_pvalue
            )

            self.func.log(f"筛选后细胞数: {cell_count}")
            self.func.display_image(violin_box_path, 'violin_box')
            self.func.display_image(box_path, 'box')
            self.func.display_image(violin_path, 'violin')
            self.func.log("绘图完成")

        except ValueError as e:
            self.func.alert_error(str(e))
        except Exception as e:
            self.func.alert_failure(f"绘图失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    def export_png(self):
        """导出PNG"""
        self._do_export('png', self.analysis.export_png)

    def export_pdf(self):
        """导出PDF"""
        self._do_export('pdf', self.analysis.export_pdf)

    def export_svg(self):
        """导出SVG"""
        self._do_export('svg', self.analysis.export_svg)

    def export_plot_csv(self):
        """导出绘图CSV"""
        if self.analysis.filtered_df is None:
            self.func.alert_error("请先绘图")
            return

        default_name = f"{self.analysis.violin_gene}_绘图数据.csv"
        save_path = self.func.get_save_file_path("导出绘图数据为CSV", default_name, "CSV文件 (*.csv)")

        if save_path:
            try:
                self.analysis.export_plot_csv(save_path)
                self.func.alert_success(f"绘图数据已保存到:\n{save_path}")
            except Exception as e:
                self.func.alert_failure(f"导出失败: {str(e)}")

    def _do_export(self, ext, export_method):
        """通用导出逻辑"""
        if not self.analysis.current_figs:
            self.func.alert_error("请先绘图")
            return

        current_tab = self.violin_ui.violin_plot_tabs.currentIndex()
        fig_type_map = {0: 'violin_box', 1: 'box', 2: 'violin'}
        fig_type = fig_type_map.get(current_tab, 'violin_box')

        default_name = f"{self.analysis.violin_gene}_自定义小提琴图.{ext}"
        save_path = self.func.get_save_file_path(f"保存图片为{ext.upper()}", default_name, f"{ext.upper()}文件 (*.{ext})")

        if save_path:
            try:
                width, height = self.func.get_export_size()
                export_method(save_path, width, height, fig_type)
                self.func.alert_success(f"图片已保存到:\n{save_path}")
            except Exception as e:
                self.func.alert_failure(f"导出失败: {str(e)}")

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