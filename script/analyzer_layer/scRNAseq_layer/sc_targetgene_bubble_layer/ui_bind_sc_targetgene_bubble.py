# -*- coding: utf-8 -*-
"""
自定义气泡图界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.scRNAseq_layer.sc_targetgene_bubble_layer.sc_targetgene_bubble_analysis import ScTargetgeneBubbleAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_targetgene_bubble_layer.ui_func_sc_targetgene_bubble import ScTargetgeneBubbleFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect


class ScTargetgeneBubbleBind:
    """自定义气泡图功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, targetgene_bubble_ui):
        self.parent = parent_window
        self.targetgene_bubble_ui = targetgene_bubble_ui
        self.analysis = ScTargetgeneBubbleAnalysis()
        self.func = ScTargetgeneBubbleFunc(targetgene_bubble_ui, parent_window)
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_bubble_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.targetgene_bubble_ui, 'btn_back_bubble'):
            self.targetgene_bubble_ui.btn_back_bubble.clicked.connect(lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page'))

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
            print(f"自定义气泡图同步数据时出错: {str(e)}")

    def sync_data_from_analysis(self, analysis_bind=None):
        """从初步分析页面同步数据（兼容旧接口）"""
        self.sync_data_from_single_cell_main(analysis_bind)

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.targetgene_bubble_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.targetgene_bubble_ui.music_controller)

    def bind_bubble_functions(self):
        """绑定自定义气泡图功能信号"""
        log_widget = getattr(self.targetgene_bubble_ui, 'targetgene_bubble_log', None)

        if hasattr(self.targetgene_bubble_ui, 'btn_load_gene_set'):
            bind_button_with_sound(self.targetgene_bubble_ui.btn_load_gene_set, self.load_gene_set_data,
                                   log_widget, "基因加载完成", "基因加载失败")

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_x_combo'):
            self.targetgene_bubble_ui.targetgene_bubble_x_combo.currentIndexChanged.connect(lambda: self.on_x_combo_changed())

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_y_combo'):
            self.targetgene_bubble_ui.targetgene_bubble_y_combo.currentIndexChanged.connect(lambda: self.on_y_combo_changed())

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_filter1_enable'):
            self.targetgene_bubble_ui.targetgene_bubble_filter1_enable.stateChanged.connect(self.on_filter1_enable_changed)

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_filter1_combo'):
            self.targetgene_bubble_ui.targetgene_bubble_filter1_combo.currentIndexChanged.connect(lambda: self.on_filter1_combo_changed())

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_filter2_enable'):
            self.targetgene_bubble_ui.targetgene_bubble_filter2_enable.stateChanged.connect(self.on_filter2_enable_changed)

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_filter2_combo'):
            self.targetgene_bubble_ui.targetgene_bubble_filter2_combo.currentIndexChanged.connect(lambda: self.on_filter2_combo_changed())

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_fig_width') and hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_export_width'):
            self.targetgene_bubble_ui.targetgene_bubble_fig_width.line_edit.editingFinished.connect(self.sync_width_to_export)
            self.targetgene_bubble_ui.targetgene_bubble_export_width.line_edit.editingFinished.connect(self.sync_export_width_to_param)

        if hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_fig_height') and hasattr(self.targetgene_bubble_ui, 'targetgene_bubble_export_height'):
            self.targetgene_bubble_ui.targetgene_bubble_fig_height.line_edit.editingFinished.connect(self.sync_height_to_export)
            self.targetgene_bubble_ui.targetgene_bubble_export_height.line_edit.editingFinished.connect(self.sync_export_height_to_param)

        if hasattr(self.targetgene_bubble_ui, 'btn_draw_bubble'):
            bind_button_with_sound(self.targetgene_bubble_ui.btn_draw_bubble, self.draw_target_gene_bubble_plot,
                                   log_widget, "绘图完成", "绘图失败")

        if hasattr(self.targetgene_bubble_ui, 'btn_export_png'):
            bind_button_with_sound(self.targetgene_bubble_ui.btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        if hasattr(self.targetgene_bubble_ui, 'btn_export_pdf'):
            bind_button_with_sound(self.targetgene_bubble_ui.btn_export_pdf, lambda: self.export_other('pdf'),
                                   log_widget, "PDF导出完成", "PDF导出失败")

        if hasattr(self.targetgene_bubble_ui, 'btn_export_svg'):
            bind_button_with_sound(self.targetgene_bubble_ui.btn_export_svg, lambda: self.export_other('svg'),
                                   log_widget, "SVG导出完成", "SVG导出失败")

        if hasattr(self.targetgene_bubble_ui, 'btn_export_eps'):
            bind_button_with_sound(self.targetgene_bubble_ui.btn_export_eps, lambda: self.export_other('eps'),
                                   log_widget, "EPS导出完成", "EPS导出失败")

        if hasattr(self.targetgene_bubble_ui, 'btn_export_csv'):
            bind_button_with_sound(self.targetgene_bubble_ui.btn_export_csv, self.export_csv,
                                   log_widget, "CSV导出完成", "CSV导出失败")

    def on_x_combo_changed(self):
        """X轴注释下拉框变化"""
        group = self.targetgene_bubble_ui.targetgene_bubble_x_combo.currentText()
        unique_vals = self.analysis.get_group_unique_vals(group)
        self.func.fill_list_widget(self.targetgene_bubble_ui.targetgene_bubble_x_list, unique_vals)

    def on_y_combo_changed(self):
        """Y轴注释下拉框变化"""
        group = self.targetgene_bubble_ui.targetgene_bubble_y_combo.currentText()
        unique_vals = self.analysis.get_group_unique_vals(group)
        self.func.fill_list_widget(self.targetgene_bubble_ui.targetgene_bubble_y_list, unique_vals)

    def on_filter1_enable_changed(self, state):
        """筛选1启用/禁用"""
        enabled = state == Qt.Checked
        self.targetgene_bubble_ui.targetgene_bubble_filter1_combo.setEnabled(enabled)
        self.targetgene_bubble_ui.targetgene_bubble_filter1_list.setEnabled(enabled)

    def on_filter1_combo_changed(self):
        """筛选1下拉框变化"""
        group = self.targetgene_bubble_ui.targetgene_bubble_filter1_combo.currentText()
        unique_vals = self.analysis.get_group_unique_vals(group)
        self.func.fill_list_widget(self.targetgene_bubble_ui.targetgene_bubble_filter1_list, unique_vals)

    def on_filter2_enable_changed(self, state):
        """筛选2启用/禁用"""
        enabled = state == Qt.Checked
        self.targetgene_bubble_ui.targetgene_bubble_filter2_combo.setEnabled(enabled)
        self.targetgene_bubble_ui.targetgene_bubble_filter2_list.setEnabled(enabled)

    def on_filter2_combo_changed(self):
        """筛选2下拉框变化"""
        group = self.targetgene_bubble_ui.targetgene_bubble_filter2_combo.currentText()
        unique_vals = self.analysis.get_group_unique_vals(group)
        self.func.fill_list_widget(self.targetgene_bubble_ui.targetgene_bubble_filter2_list, unique_vals)

    def sync_width_to_export(self):
        """同步参数面板宽度到导出宽度"""
        value = self.targetgene_bubble_ui.targetgene_bubble_fig_width.value()
        self.targetgene_bubble_ui.targetgene_bubble_export_width.setValue(value)

    def sync_export_width_to_param(self):
        """同步导出宽度到参数面板宽度"""
        value = self.targetgene_bubble_ui.targetgene_bubble_export_width.value()
        self.targetgene_bubble_ui.targetgene_bubble_fig_width.setValue(value)

    def sync_height_to_export(self):
        """同步参数面板高度到导出高度"""
        value = self.targetgene_bubble_ui.targetgene_bubble_fig_height.value()
        self.targetgene_bubble_ui.targetgene_bubble_export_height.setValue(value)

    def sync_export_height_to_param(self):
        """同步导出高度到参数面板高度"""
        value = self.targetgene_bubble_ui.targetgene_bubble_export_height.value()
        self.targetgene_bubble_ui.targetgene_bubble_fig_height.setValue(value)

    def load_gene_set_data(self):
        """加载基因数据"""
        gene_text = self.targetgene_bubble_ui.targetgene_text_input.toPlainText().strip()

        try:
            valid_genes, lost_genes, valid_groups, cell_count = self.analysis.load_target_genes(gene_text)

            self.func.set_combo_items(self.targetgene_bubble_ui.targetgene_bubble_x_combo, valid_groups)
            self.func.set_combo_items(self.targetgene_bubble_ui.targetgene_bubble_y_combo, valid_groups)
            self.func.set_combo_items(self.targetgene_bubble_ui.targetgene_bubble_filter1_combo, [''] + valid_groups)
            self.func.set_combo_items(self.targetgene_bubble_ui.targetgene_bubble_filter2_combo, [''] + valid_groups)

            if valid_groups:
                self.targetgene_bubble_ui.targetgene_bubble_x_combo.setCurrentIndex(0)
                self.targetgene_bubble_ui.targetgene_bubble_y_combo.setCurrentIndex(0)

            self.on_x_combo_changed()
            self.on_y_combo_changed()
            self.on_filter1_combo_changed()
            self.on_filter2_combo_changed()

            self.func.log(f"基因加载完成，有效基因数：{len(valid_genes)}，总细胞数：{cell_count}")
            if lost_genes:
                self.func.log(f"未找到基因：{','.join(lost_genes[:5])}{'...' if len(lost_genes)>5 else ''}")

        except ValueError as e:
            self.func.alert_error(str(e))
        except Exception as e:
            self.func.alert_failure(f"加载失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    def draw_target_gene_bubble_plot(self):
        """绘制自定义气泡图"""
        try:
            x_col = self.targetgene_bubble_ui.targetgene_bubble_x_combo.currentText()
            x_sel = [item.text() for item in self.targetgene_bubble_ui.targetgene_bubble_x_list.selectedItems()]

            y_col = self.targetgene_bubble_ui.targetgene_bubble_y_combo.currentText()
            y_sel = [item.text() for item in self.targetgene_bubble_ui.targetgene_bubble_y_list.selectedItems()]

            f1_col = None
            f1_sel = []
            if self.targetgene_bubble_ui.targetgene_bubble_filter1_enable.isChecked():
                f1_col = self.targetgene_bubble_ui.targetgene_bubble_filter1_combo.currentText()
                f1_sel = [item.text() for item in self.targetgene_bubble_ui.targetgene_bubble_filter1_list.selectedItems()]

            f2_col = None
            f2_sel = []
            if self.targetgene_bubble_ui.targetgene_bubble_filter2_enable.isChecked():
                f2_col = self.targetgene_bubble_ui.targetgene_bubble_filter2_combo.currentText()
                f2_sel = [item.text() for item in self.targetgene_bubble_ui.targetgene_bubble_filter2_list.selectedItems()]

            main_title = self.targetgene_bubble_ui.targetgene_bubble_main_title.text().strip()
            fig_width = self.targetgene_bubble_ui.targetgene_bubble_fig_width.value()
            fig_height = self.targetgene_bubble_ui.targetgene_bubble_fig_height.value()
            scale_factor = self.targetgene_bubble_ui.targetgene_bubble_scale_factor.value()
            legend_scale = self.targetgene_bubble_ui.targetgene_bubble_legend_scale.value() / 10.0
            main_right_ratio = self.targetgene_bubble_ui.targetgene_bubble_main_right_ratio.value() / 100.0
            title_fontsize = self.targetgene_bubble_ui.targetgene_bubble_title_fontsize.value()
            x_label_fontsize = self.targetgene_bubble_ui.targetgene_bubble_x_label_fontsize.value()
            y_label_fontsize = self.targetgene_bubble_ui.targetgene_bubble_y_label_fontsize.value()
            label_spacing = self.targetgene_bubble_ui.targetgene_bubble_label_spacing.value() / 10.0
            legend_title_fontsize = self.targetgene_bubble_ui.targetgene_bubble_legend_label_fontsize.value()
            cbar_label_fontsize = self.targetgene_bubble_ui.targetgene_bubble_cbar_label_fontsize.value()
            cbar_label_text = self.targetgene_bubble_ui.targetgene_bubble_cbar_label.text().strip()

            cell_count, fig_path = self.analysis.draw_target_gene_bubble_plot(
                x_col, x_sel, y_col, y_sel,
                f1_col=f1_col, f1_sel=f1_sel, f2_col=f2_col, f2_sel=f2_sel,
                main_title=main_title, scale_factor=scale_factor, legend_scale=legend_scale,
                main_right_ratio=main_right_ratio, title_fontsize=title_fontsize,
                x_label_fontsize=x_label_fontsize, y_label_fontsize=y_label_fontsize,
                label_spacing=label_spacing, legend_title_fontsize=legend_title_fontsize,
                cbar_label_fontsize=cbar_label_fontsize, cbar_label_text=cbar_label_text,
                collapsed=False, fig_width=fig_width, fig_height=fig_height
            )

            self.func.log(f"筛选后细胞数: {cell_count}")
            self.func.display_image(fig_path)
            self.func.log("绘图完成")

        except ValueError as e:
            self.func.alert_error(str(e))
        except Exception as e:
            self.func.alert_failure(f"绘图失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    def export_png(self):
        """导出PNG"""
        if self.analysis.current_fig_path is None:
            self.func.alert_error("请先绘图")
            return

        default_name = "target_gene_bubble.png"
        save_path = self.func.get_save_file_path("保存图片为PNG", default_name, "PNG文件 (*.png)")

        if save_path:
            try:
                self.analysis.export_png(save_path)
                self.func.alert_success(f"图片已保存到:\n{save_path}")
            except Exception as e:
                self.func.alert_failure(f"导出失败: {str(e)}")

    def export_csv(self):
        """导出CSV"""
        if self.analysis.target_gene_final_df is None:
            self.func.alert_error("请先绘图")
            return

        default_name = "target_gene_bubble_data.csv"
        save_path = self.func.get_save_file_path("保存数据为CSV", default_name, "CSV文件 (*.csv)")

        if save_path:
            try:
                self.analysis.export_csv(save_path)
                self.func.alert_success(f"数据已保存到:\n{save_path}")
            except Exception as e:
                self.func.alert_failure(f"导出失败: {str(e)}")

    def export_other(self, fmt):
        """导出其他格式"""
        if self.analysis.target_gene_final_df is None:
            self.func.alert_error("请先绘图")
            return

        default_name = f"自定义气泡图.{fmt}"
        save_path = self.func.get_save_file_path(f"保存图片为{fmt.upper()}", default_name, f"{fmt.upper()}文件 (*.{fmt})")

        if save_path:
            try:
                self.analysis.export_other(save_path, fmt)
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