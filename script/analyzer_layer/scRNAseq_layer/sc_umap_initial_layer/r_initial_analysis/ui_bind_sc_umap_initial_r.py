# -*- coding: utf-8 -*-
"""
UMAP初步作图R版本界面功能绑定脚本 - 子层
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.r_initial_analysis.sc_umap_initial_r_analysis import ScUmapInitialRAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.r_initial_analysis.ui_func_sc_umap_initial_r import ScUmapInitialRFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScUmapInitialRBind:
    def __init__(self, parent_window, analysis_ui):
        self.parent = parent_window
        self.analysis_ui = analysis_ui
        self.analysis = ScUmapInitialRAnalysis()
        self.func = ScUmapInitialRFunc(analysis_ui, parent_window)
        self._last_expression_paths = []
        self.init_bindings()

    def init_bindings(self):
        self.bind_music_controls()
        self.bind_analysis_functions()

    def bind_music_controls(self):
        if hasattr(self.analysis_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.analysis_ui.music_controller)

    def bind_analysis_functions(self):
        log_widget = getattr(self.analysis_ui, 'status_text', None)

        if hasattr(self.analysis_ui, 'btn_generate_annotations'):
            bind_button_with_sound(self.analysis_ui.btn_generate_annotations, self.generate_annotations,
                                   log_widget, "注释出图已生成", "注释出图生成失败")

        if hasattr(self.analysis_ui, 'btn_draw_expression'):
            bind_button_with_sound(self.analysis_ui.btn_draw_expression, self.draw_expression,
                                   log_widget, "表达量出图已完成", "表达量出图失败")

        if hasattr(self.analysis_ui, 'annotation_combo'):
            self.analysis_ui.annotation_combo.currentIndexChanged.connect(self.on_annotation_changed)

        if hasattr(self.analysis_ui, 'btn_export_png'):
            bind_button_with_sound(self.analysis_ui.btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        if hasattr(self.analysis_ui, 'btn_export_pdf'):
            bind_button_with_sound(self.analysis_ui.btn_export_pdf, self.export_pdf,
                                   log_widget, "PDF导出完成", "PDF导出失败")

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        try:
            if single_cell_bind is None:
                single_cell_bind = getattr(self.parent, 'scRNAseq_top_bind', None)

            if single_cell_bind is None:
                return

            if hasattr(single_cell_bind, 'analysis'):
                self.analysis.set_seurat_path(single_cell_bind.analysis.seurat_path)
                self.analysis.set_dataset_name(single_cell_bind.analysis.dataset_name)
                self.analysis.set_dataset_output_dir(single_cell_bind.analysis.dataset_output_dir)

                if single_cell_bind.analysis.seurat_path is not None:
                    self.func.log(f"已从scRNAseq主页同步Seurat对象: {single_cell_bind.analysis.dataset_name}")

        except Exception as e:
            print(f"R版本UMAP初步作图同步数据时出错: {str(e)}")

    def _load_metadata_lazy(self):
        if not self.analysis.seurat_path:
            return False, "请先加载RDS文件"
        
        try:
            seurat_info = self.analysis.get_seurat_info()
            if seurat_info:
                self.func.update_data_info(seurat_info)

            metadata_cols = self.analysis.get_metadata_columns()
            if metadata_cols:
                self.func.set_combo_items(
                    self.analysis_ui.annotation_combo,
                    ['seurat_clusters'] + metadata_cols,
                    keep_selection=False
                )
                self.func.log(f"已加载 {len(metadata_cols)} 个元数据列")
            
            return True, ""
        except Exception as e:
            print(f"加载元数据失败: {e}")
            return False, str(e)

    def generate_annotations(self):
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return

        self.func.log("正在加载元数据...")
        success, error = self._load_metadata_lazy()
        if not success:
            self.func.alert_failure(f"加载元数据失败: {error}")
            return

        self.func.log("正在生成注释出图...")

        success, result = self.analysis.generate_all_annotation_plots()

        if not success:
            self.func.alert_failure(f"生成失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"注释出图已保存到: {result}")

        if hasattr(self.analysis_ui, 'annotation_combo') and self.analysis_ui.annotation_combo.count() > 0:
            self.on_annotation_changed()

        self.func.alert_success("注释出图生成完成")

    def on_annotation_changed(self):
        if not self.analysis.seurat_path:
            return

        annotation_col = self.analysis_ui.annotation_combo.currentText()
        if not annotation_col:
            return

        image_path = self.analysis.get_annotation_plot_path(annotation_col)

        if image_path and os.path.exists(image_path):
            self.func.display_image(image_path, 'annotation_label')
            self.func.log(f"显示 {annotation_col} 注释图")
        else:
            self.func.log(f"{annotation_col} 注释图不存在，请点击'生成注释出图'按钮")

    def draw_expression(self):
        gene_text = self.analysis_ui.gene_input.toPlainText().strip()
        if not gene_text:
            self.func.alert_error("请输入基因名")
            return

        genes = [g.strip() for g in gene_text.split('\n') if g.strip()]
        if not genes:
            self.func.alert_error("请输入有效的基因名")
            return

        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return

        self.func.log(f"正在绘制表达量图: {', '.join(genes)}")

        success, result = self.analysis.generate_expression_plots(genes)

        if not success:
            self.func.alert_failure(f"绘制失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self._last_expression_paths = result
        self.func.display_expression_images(result)

        if self.analysis_ui.umap_plot_tabs.currentIndex() != 1:
            self.analysis_ui.umap_plot_tabs.setCurrentIndex(1)

        self.func.log(f"表达量出图完成，共 {len(result)} 张图片")
        self.func.alert_success("表达量出图完成")

    def export_png(self):
        current_tab = self.analysis_ui.umap_plot_tabs.currentIndex()

        if current_tab == 0:
            annotation_col = self.analysis_ui.annotation_combo.currentText()
            if not annotation_col:
                self.func.alert_no_image()
                return

            image_path = self.analysis.get_annotation_plot_path(annotation_col)
            if not image_path or not os.path.exists(image_path):
                self.func.alert_no_image()
                return

            default_name = f"{self.analysis.dataset_name}_{annotation_col}_umap.png"
            save_path = self.func.get_save_file_path("保存图片为PNG", default_name, "PNG文件 (*.png)")

            if save_path:
                try:
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        if not save_path.endswith('.png'):
                            save_path += '.png'
                        pixmap.save(save_path)
                        self.func.alert_export_success(save_path)
                    else:
                        self.func.alert_export_failed()
                except Exception as e:
                    self.func.alert_export_error(str(e))
        else:
            if self._last_expression_paths:
                self.func.export_expression_images_batch(self._last_expression_paths, format='png')
            else:
                self.func.alert_error("请先生成表达量图")

    def export_pdf(self):
        current_tab = self.analysis_ui.umap_plot_tabs.currentIndex()

        if current_tab == 0:
            annotation_col = self.analysis_ui.annotation_combo.currentText()
            if not annotation_col:
                self.func.alert_no_image()
                return

            image_path = self.analysis.get_annotation_plot_path(annotation_col)
            if not image_path:
                self.func.alert_no_image()
                return

            pdf_path = image_path.replace('.png', '.pdf')
            if os.path.exists(pdf_path):
                default_name = f"{self.analysis.dataset_name}_{annotation_col}_umap.pdf"
                save_path = self.func.get_save_file_path("保存图片为PDF", default_name, "PDF文件 (*.pdf)")

                if save_path:
                    try:
                        import shutil
                        if not save_path.endswith('.pdf'):
                            save_path += '.pdf'
                        shutil.copy2(pdf_path, save_path)
                        self.func.alert_export_success(save_path)
                    except Exception as e:
                        self.func.alert_export_error(str(e))
                return

            png_path = image_path
            default_name = f"{self.analysis.dataset_name}_{annotation_col}_umap.pdf"
            save_path = self.func.get_save_file_path("保存图片为PDF", default_name, "PDF文件 (*.pdf)")

            if save_path:
                try:
                    if not save_path.endswith('.pdf'):
                        save_path += '.pdf'

                    pixmap = QPixmap(png_path)
                    if not pixmap.isNull():
                        qimage = pixmap.toImage()
                        qimage.save(save_path)
                        self.func.alert_export_success(save_path)
                    else:
                        self.func.alert_export_failed()
                except Exception as e:
                    self.func.alert_export_error(str(e))
        else:
            if self._last_expression_paths:
                self.func.export_expression_images_batch(self._last_expression_paths, format='pdf')
            else:
                self.func.alert_error("请先生成表达量图")

    def set_volume(self, value):
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def set_seurat_path(self, seurat_path):
        self.analysis.set_seurat_path(seurat_path)

    def set_dataset_name(self, dataset_name):
        self.analysis.set_dataset_name(dataset_name)

    def set_dataset_output_dir(self, dataset_output_dir):
        self.analysis.set_dataset_output_dir(dataset_output_dir)