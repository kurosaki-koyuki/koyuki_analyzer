# -*- coding: utf-8 -*-
"""
初步分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.scRNAseq_layer.initial_analysis_layer.scRNAseq_analysis import ScRNAAnalysis
from script.analyzer_layer.scRNAseq_layer.initial_analysis_layer.ui_func_initial_analysis import InitialAnalysisFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class InitialAnalysisBind:
    """初步分析功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, analysis_ui):
        self.parent = parent_window
        self.analysis_ui = analysis_ui
        self.analysis = ScRNAAnalysis()
        self.func = InitialAnalysisFunc(analysis_ui, parent_window)
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_analysis_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.analysis_ui, 'btn_back_analysis'):
            self.analysis_ui.btn_back_analysis.clicked.connect(lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page'))

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.analysis_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.analysis_ui.music_controller)

    def bind_analysis_functions(self):
        """绑定生信分析功能信号"""
        log_widget = getattr(self.analysis_ui, 'status_text', None)

        if hasattr(self.analysis_ui, 'btn_query'):
            bind_button_with_sound(self.analysis_ui.btn_query, self.query_gene,
                                   log_widget, "查询完成", "查询失败")

        if hasattr(self.analysis_ui, 'source_combo'):
            self.analysis_ui.source_combo.currentIndexChanged.connect(self.switch_source)

        if hasattr(self.analysis_ui, 'plot_combo'):
            self.analysis_ui.plot_combo.currentIndexChanged.connect(self.switch_plot)

        if hasattr(self.analysis_ui, 'btn_export_png'):
            bind_button_with_sound(self.analysis_ui.btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        if hasattr(self.analysis_ui, 'btn_export_pdf'):
            bind_button_with_sound(self.analysis_ui.btn_export_pdf, self.export_pdf,
                                   log_widget, "PDF导出完成", "PDF导出失败")

    # ---------- 基因查询 / 切换 ----------

    def query_gene(self):
        """查询基因"""
        gene_name = self.analysis_ui.gene_input.text().strip()

        self.func.log(f"正在分析基因: {gene_name}")
        success, image_path, error = self.analysis.query_gene(gene_name)

        if not success:
            attention(self.parent, error)
            self.func.log(error)
            return

        self.func.display_image(image_path)
        self.func.log("分析完成")

    def switch_source(self):
        """切换显示类型"""
        if self.analysis.adata is None:
            attention(self.parent, "请先加载数据")
            self.func.set_combo_index(self.analysis_ui.source_combo, 0)
            return

        source_text = self.analysis_ui.source_combo.currentText()
        plot_items = self.analysis.get_plot_items_for_source(source_text)
        self.func.set_combo_items(self.analysis_ui.plot_combo, plot_items, keep_selection=False)

    def switch_plot(self):
        """切换绘图类型"""
        if self.analysis.adata is None:
            return

        source_text = self.analysis_ui.source_combo.currentText()
        plot_text = self.analysis_ui.plot_combo.currentText()

        image_path, error = self.analysis.get_plot_image_path(source_text, plot_text)
        if error:
            if error != "":
                wrong(self.parent, error)
            return

        if image_path:
            self.func.display_image(image_path)

    # ---------- 导出 ----------

    def export_png(self):
        """导出PNG"""
        pixmap = self.func.get_current_pixmap()
        if pixmap is None or pixmap.isNull():
            self.func.alert_no_image()
            return

        default_name = self.analysis.get_export_default_name(
            self.analysis_ui.source_combo.currentText(),
            self.analysis_ui.plot_combo.currentText(),
            "png"
        )
        save_path = self.func.get_save_file_path(
            self.parent, "保存图片为PNG", default_name, "PNG文件 (*.png)")

        if save_path:
            if self.analysis.save_pixmap_as_png(pixmap, save_path):
                self.func.alert_export_success(save_path)
            else:
                self.func.alert_export_failed()

    def export_pdf(self):
        """导出PDF"""
        pixmap = self.func.get_current_pixmap()
        if pixmap is None or pixmap.isNull():
            self.func.alert_no_image()
            return

        default_name = self.analysis.get_export_default_name(
            self.analysis_ui.source_combo.currentText(),
            self.analysis_ui.plot_combo.currentText(),
            "pdf"
        )
        save_path = self.func.get_save_file_path(
            self.parent, "保存图片为PDF", default_name, "PDF文件 (*.pdf)")

        if save_path:
            try:
                self.analysis.copy_or_convert_to_pdf(
                    pixmap,
                    self.analysis_ui.source_combo.currentText(),
                    self.analysis_ui.plot_combo.currentText(),
                    save_path
                )
                self.func.alert_export_success(save_path)
            except Exception as e:
                self.func.alert_export_error(str(e))

    # ---------- 跨层桥接 ----------

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从单细胞分析主界面同步数据"""
        try:
            if single_cell_bind is None:
                single_cell_bind = getattr(self.parent, 'scRNAseq_top_bind', None)
            
            if single_cell_bind is None:
                return

            if hasattr(single_cell_bind, 'analysis') and single_cell_bind.analysis.adata is not None:
                self.analysis.set_adata(single_cell_bind.analysis.adata)
                data_info = single_cell_bind.analysis.get_data_info()
                if data_info:
                    self.func.update_data_info(data_info)
                    self.func.set_combo_items(
                        self.analysis_ui.plot_combo,
                        ["表达量UMAP"] + data_info.get('valid_groups', []),
                        keep_selection=False
                    )
                    self.func.log("数据已从单细胞分析主界面同步")
            
            if hasattr(single_cell_bind, 'analysis') and single_cell_bind.analysis.dataset_output_dir is not None:
                self.analysis.set_dataset_output_dir(single_cell_bind.analysis.dataset_output_dir)

        except Exception as e:
            print(f"初步分析同步数据时出错: {str(e)}")

    def set_adata(self, adata):
        """设置adata对象"""
        self.analysis.set_adata(adata)

    def set_dataset_output_dir(self, dataset_output_dir):
        """设置数据集输出目录"""
        self.analysis.set_dataset_output_dir(dataset_output_dir)
