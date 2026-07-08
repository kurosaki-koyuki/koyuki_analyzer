# -*- coding: utf-8 -*-
"""
bulk WGCNA分析界面UI绑定脚本 - 只负责绑定信号和槽、实现按钮点击逻辑、调用分析层API
完全不写R代码，不负责UI布局
"""

from script.utils_layer.import_config import os, traceback, QApplication, Qt, QFileDialog, shutil
from script.utils_layer.gui_styles import get_mod_styles, get_stylesheet_for_widget
from script.utils_layer.page_intersect import page_intersect
from script.utils_layer.emoji_trigger import show_info, show_error

from script.analyzer_layer.bulk_layer.wgcna_layer.wgcna_analysis import get_wgcna_analysis
from script.analyzer_layer.bulk_layer.wgcna_layer.ui_func_bulk_wgcna import BulkWgcnaFunc


class BulkWgcnaPageBind:
    def __init__(self, parent_widget, wgcna_ui):
        self.parent = parent_widget
        self.ui = wgcna_ui
        self.wgcna_analysis = get_wgcna_analysis()
        self.func = BulkWgcnaFunc(wgcna_ui, parent_widget)
        self._setup_signals()
        self._update_r_version()

    def _setup_signals(self):
        self.ui.btn_back.clicked.connect(self.go_back_to_bulk_top)

        self.ui.bulk_wgcna_clinical_combo.currentIndexChanged.connect(self._on_clinical_combo_changed)
        self.ui.bulk_wgcna_filter1_enable.stateChanged.connect(self._on_filter1_enable_changed)
        self.ui.bulk_wgcna_filter1_combo.currentIndexChanged.connect(self._on_filter1_combo_changed)
        self.ui.bulk_wgcna_filter2_enable.stateChanged.connect(self._on_filter2_enable_changed)
        self.ui.bulk_wgcna_filter2_combo.currentIndexChanged.connect(self._on_filter2_combo_changed)

        self.ui.bulk_wgcna_debug_btn.clicked.connect(self._debug_check_environment)

        self.ui.bulk_wgcna_btn_stage1.clicked.connect(self.run_stage1)
        self.ui.bulk_wgcna_btn_stage2.clicked.connect(self.run_stage2)
        self.ui.bulk_wgcna_btn_stage3.clicked.connect(self.run_stage3)
        self.ui.bulk_wgcna_btn_stage4.clicked.connect(self.run_stage4)
        self.ui.bulk_wgcna_btn_stage5.clicked.connect(self.run_stage5)
        self.ui.bulk_wgcna_btn_stage6.clicked.connect(self.run_stage6)

        self.ui.bulk_wgcna_btn_export_png.clicked.connect(lambda: self._export_current_plot('png'))
        self.ui.bulk_wgcna_btn_export_pdf.clicked.connect(lambda: self._export_current_plot('pdf'))
        self.ui.bulk_wgcna_btn_export_svg.clicked.connect(lambda: self._export_current_plot('svg'))

    def go_back_to_bulk_top(self):
        page_intersect.go_to_page_with_bind('bulk_top_page')

    def sync_data_from_bulk_main(self, bulk_top_bind):
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return

        self.wgcna_analysis.set_adata(bulk_top_bind.analysis.adata)
        self.wgcna_analysis.set_dataset_name(bulk_top_bind.analysis.dataset_name)
        self.wgcna_analysis.set_dataset_output_dir(bulk_top_bind.analysis.dataset_output_dir)

        if bulk_top_bind.analysis.adata is not None:
            self._populate_clinical_combo()
            self._populate_filter_combos()
            n_samples, n_genes = self.wgcna_analysis.get_adata_shape()
            self._update_status_text(f"数据已加载: {bulk_top_bind.analysis.dataset_name}\n维度: {n_samples} 样本 × {n_genes} 基因")

    def _populate_clinical_combo(self):
        obs_cols = self.wgcna_analysis.get_obs_columns()
        self.ui.bulk_wgcna_clinical_combo.clear()
        self.ui.bulk_wgcna_clinical_combo.addItem("全部")
        self.ui.bulk_wgcna_clinical_combo.addItems(obs_cols)

    def _populate_filter_combos(self):
        obs_cols = self.wgcna_analysis.get_obs_columns()
        self.ui.bulk_wgcna_filter1_combo.clear()
        self.ui.bulk_wgcna_filter1_combo.addItems(obs_cols)
        self.ui.bulk_wgcna_filter2_combo.clear()
        self.ui.bulk_wgcna_filter2_combo.addItems(obs_cols)
        
        if hasattr(self.ui, 'bulk_wgcna_trait_list'):
            self.ui.bulk_wgcna_trait_list.clear()
            self.ui.bulk_wgcna_trait_list.addItems(obs_cols)
        
        if hasattr(self.ui, 'bulk_wgcna_external_gene_combo'):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            for _ in range(4):
                base_dir = os.path.dirname(base_dir)
            gene_lists_dir = os.path.join(base_dir, 'appdata', 'genelists')
            if os.path.exists(gene_lists_dir):
                gene_files = [f for f in os.listdir(gene_lists_dir) if f.endswith('.xlsx') or f.endswith('.txt')]
                self.ui.bulk_wgcna_external_gene_combo.clear()
                self.ui.bulk_wgcna_external_gene_combo.addItems(gene_files)
            else:
                self.ui.bulk_wgcna_external_gene_combo.clear()

    def _on_clinical_combo_changed(self, index):
        col_name = self.ui.bulk_wgcna_clinical_combo.itemText(index)
        if col_name == "全部":
            self.ui.bulk_wgcna_group_list_label.hide()
            self.ui.bulk_wgcna_group_list.hide()
        else:
            unique_vals = self.wgcna_analysis.get_obs_unique_values(col_name)
            self.ui.bulk_wgcna_group_list.clear()
            self.ui.bulk_wgcna_group_list.addItems(unique_vals)
            self.ui.bulk_wgcna_group_list_label.show()
            self.ui.bulk_wgcna_group_list.show()

    def _on_filter1_enable_changed(self, state):
        enabled = state == Qt.Checked
        self.ui.bulk_wgcna_filter1_combo.setEnabled(enabled)
        self.ui.bulk_wgcna_filter1_list.setEnabled(enabled)

    def _on_filter1_combo_changed(self, index):
        col_name = self.ui.bulk_wgcna_filter1_combo.itemText(index)
        unique_vals = self.wgcna_analysis.get_obs_unique_values(col_name)
        self.ui.bulk_wgcna_filter1_list.clear()
        self.ui.bulk_wgcna_filter1_list.addItems(unique_vals)

    def _on_filter2_enable_changed(self, state):
        enabled = state == Qt.Checked
        self.ui.bulk_wgcna_filter2_combo.setEnabled(enabled)
        self.ui.bulk_wgcna_filter2_list.setEnabled(enabled)

    def _on_filter2_combo_changed(self, index):
        col_name = self.ui.bulk_wgcna_filter2_combo.itemText(index)
        unique_vals = self.wgcna_analysis.get_obs_unique_values(col_name)
        self.ui.bulk_wgcna_filter2_list.clear()
        self.ui.bulk_wgcna_filter2_list.addItems(unique_vals)

    def _update_status_text(self, text):
        self.ui.bulk_wgcna_status_text.setPlainText(text)

    def _update_r_version(self):
        version = self.wgcna_analysis.get_r_version()
        self.ui.r_version_label.setText(f"R版本: {version}")

    def _debug_check_environment(self):
        self._update_status_text("正在检测R环境...")
        QApplication.processEvents()
        try:
            if self.wgcna_analysis.is_available():
                version = self.wgcna_analysis.get_r_version()
                self._update_status_text(f"R环境检测成功!\n版本: {version}\n脚本路径: {self.wgcna_analysis.R_SCRIPT_PATH}")
            else:
                self._update_status_text("R环境检测失败!\n请检查R路径配置")
        except Exception as e:
            self._update_status_text(f"环境检测异常: {str(e)}")

    def _get_selected_groups(self, list_widget):
        selected_items = list_widget.selectedItems()
        return [item.text() for item in selected_items]

    def run_stage1(self):
        self._update_status_text("正在运行阶段一：数据准备+基因筛选...")
        QApplication.processEvents()

        try:
            filter_mode = self.ui.bulk_wgcna_filter_mode_combo.currentText()
            
            mad_threshold = int(self.ui.bulk_wgcna_mad_input.text()) if filter_mode == 'MAD筛选' else None
            
            external_gene_file = None
            if filter_mode == '外部基因列表':
                external_gene_file = self.ui.bulk_wgcna_external_gene_combo.currentText()
                if not external_gene_file:
                    raise ValueError("请选择外部基因列表文件")

            clinical_col = None
            clinical_groups = None
            if self.ui.bulk_wgcna_clinical_combo.currentText() != "全部":
                clinical_col = self.ui.bulk_wgcna_clinical_combo.currentText()
                clinical_groups = self._get_selected_groups(self.ui.bulk_wgcna_group_list)

            filter1_col = None
            filter1_groups = None
            if self.ui.bulk_wgcna_filter1_enable.isChecked():
                filter1_col = self.ui.bulk_wgcna_filter1_combo.currentText()
                filter1_groups = self._get_selected_groups(self.ui.bulk_wgcna_filter1_list)

            filter2_col = None
            filter2_groups = None
            if self.ui.bulk_wgcna_filter2_enable.isChecked():
                filter2_col = self.ui.bulk_wgcna_filter2_combo.currentText()
                filter2_groups = self._get_selected_groups(self.ui.bulk_wgcna_filter2_list)

            success = self.wgcna_analysis.run_stage1_gene_filter(
                filter_mode=filter_mode,
                mad_threshold=mad_threshold,
                external_gene_file=external_gene_file,
                clinical_col=clinical_col,
                clinical_groups=clinical_groups,
                filter1_col=filter1_col,
                filter1_groups=filter1_groups,
                filter2_col=filter2_col,
                filter2_groups=filter2_groups
            )

            if success:
                self._update_status_text("阶段一完成!\n已生成样本聚类树")
                self._load_sample_dendrogram()
            else:
                self._update_status_text("阶段一失败")

        except Exception as e:
            self._update_status_text(f"阶段一运行失败: {str(e)}")

    def run_stage2(self):
        self._update_status_text("正在运行阶段二：软阈值选择...")
        QApplication.processEvents()

        try:
            network_type = self.ui.bulk_wgcna_network_type_combo.currentText()
            rsquared_cut = float(self.ui.bulk_wgcna_rsquared_input.text())
            
            manual_power = None
            manual_power_text = self.ui.bulk_wgcna_manual_power_input.text().strip()
            if manual_power_text:
                manual_power = int(manual_power_text)

            power_estimate = self.wgcna_analysis.run_stage2_soft_threshold(
                network_type=network_type,
                rsquared_cut=rsquared_cut,
                manual_power=manual_power
            )

            self._update_status_text(f"阶段二完成!\n推荐软阈值: {power_estimate}")
            self.ui.bulk_wgcna_power_estimate_label.setText(f"推荐软阈值: {power_estimate}")
            if power_estimate:
                self.ui.bulk_wgcna_power_input.setText(power_estimate)
            self._load_soft_threshold_plot()

        except Exception as e:
            self._update_status_text(f"阶段二运行失败: {str(e)}")

    def run_stage3(self):
        self._update_status_text("正在运行阶段三：网络构建+模块识别...")
        QApplication.processEvents()

        try:
            power = int(self.ui.bulk_wgcna_power_input.text())
            min_module_size = int(self.ui.bulk_wgcna_min_module_input.text())
            merge_cut_height = float(self.ui.bulk_wgcna_merge_cut_input.text())
            
            stage3_width = int(self.ui.bulk_wgcna_stage3_width_input.text())
            stage3_height = int(self.ui.bulk_wgcna_stage3_height_input.text())

            success = self.wgcna_analysis.run_stage3_network_construction(
                power=power,
                min_module_size=min_module_size,
                merge_cut_height=merge_cut_height,
                stage3_width=stage3_width,
                stage3_height=stage3_height
            )

            if success:
                self._update_status_text("阶段三完成!\n已完成网络构建和模块识别")
                self._load_gene_dendrogram()
                self._load_module_merge_plots()
                self._populate_module_list()
            else:
                self._update_status_text("阶段三失败")

        except Exception as e:
            self._update_status_text(f"阶段三运行失败: {str(e)}")
            show_error(self.parent, "错误", f"阶段三运行失败:\n{str(e)}")

    def run_stage4(self):
        self._update_status_text("正在运行阶段四：模块-性状关联...")
        QApplication.processEvents()

        try:
            trait_cols = self._get_selected_trait_cols()
            
            stage4_width = int(self.ui.bulk_wgcna_stage4_width_input.text())
            stage4_height = int(self.ui.bulk_wgcna_stage4_height_input.text())
            cell_width = int(self.ui.bulk_wgcna_stage4_cell_width_input.text())
            cell_height = int(self.ui.bulk_wgcna_stage4_cell_height_input.text())
            show_significance = self.ui.bulk_wgcna_stage4_significance_checkbox.isChecked()
            
            success = self.wgcna_analysis.run_stage4_module_trait(trait_cols=trait_cols, stage4_width=stage4_width, stage4_height=stage4_height, cell_width=cell_width, cell_height=cell_height, show_significance=show_significance)

            if success:
                self._update_status_text("阶段四完成!\n已生成模块-性状关联图")
                self._load_module_trait_plots()
            else:
                self._update_status_text("阶段四失败")

        except Exception as e:
            self._update_status_text(f"阶段四运行失败: {str(e)}")
    
    def _get_selected_trait_cols(self):
        trait_cols = []
        if hasattr(self.ui, 'bulk_wgcna_trait_list'):
            selected_items = self.ui.bulk_wgcna_trait_list.selectedItems()
            trait_cols = [item.text() for item in selected_items]
        
        if not trait_cols and hasattr(self.ui, 'bulk_wgcna_clinical_combo'):
            clinical_col = self.ui.bulk_wgcna_clinical_combo.currentText()
            if clinical_col != "全部":
                trait_cols = [clinical_col]
        
        return trait_cols if trait_cols else None

    def run_stage5(self):
        self._update_status_text("正在运行阶段五：GO/KEGG富集分析...")
        QApplication.processEvents()

        try:
            selected_modules = self._get_selected_modules_go()
            
            if not selected_modules:
                self._update_status_text("请先选择要分析的模块")
                return

            organism = "hsa"
            if hasattr(self.ui, 'bulk_wgcna_organism_combo'):
                organism = self.ui.bulk_wgcna_organism_combo.currentText()

            go_padj_cutoff = 0.05
            if hasattr(self.ui, 'bulk_wgcna_go_padj_spin'):
                go_padj_cutoff = self.ui.bulk_wgcna_go_padj_spin.value()

            kegg_padj_cutoff = 0.05
            if hasattr(self.ui, 'bulk_wgcna_kegg_padj_spin'):
                kegg_padj_cutoff = self.ui.bulk_wgcna_kegg_padj_spin.value()

            go_top_n = 15
            if hasattr(self.ui, 'bulk_wgcna_go_topn_spin'):
                go_top_n = self.ui.bulk_wgcna_go_topn_spin.value()

            kegg_top_n = 15
            if hasattr(self.ui, 'bulk_wgcna_kegg_topn_spin'):
                kegg_top_n = self.ui.bulk_wgcna_kegg_topn_spin.value()

            QApplication.processEvents()

            success = self.wgcna_analysis.run_stage5_go_kegg(
                selected_modules=selected_modules,
                organism=organism,
                go_padj_cutoff=go_padj_cutoff,
                kegg_padj_cutoff=kegg_padj_cutoff,
                go_top_n=go_top_n,
                kegg_top_n=kegg_top_n
            )

            QApplication.processEvents()

            if success:
                self._update_status_text(f"阶段五完成!\nGO和KEGG富集分析已完成")
                
                output_dir = self.wgcna_analysis.dataset_output_dir or self.wgcna_analysis._temp_dir
                
                if selected_modules:
                    self._load_go_kegg_charts(output_dir, selected_modules)
                
                if hasattr(self.ui, 'bulk_wgcna_plot_tabs'):
                    self.ui.bulk_wgcna_plot_tabs.setCurrentIndex(9)
                    
            else:
                self._update_status_text("阶段五失败")

        except Exception as e:
            self._update_status_text(f"阶段五运行失败: {str(e)}")
            traceback.print_exc()

    def _load_go_kegg_charts(self, output_dir, modules):
        if isinstance(modules, str):
            modules = [modules]
        
        go_bubble_paths = [os.path.join(output_dir, f"GO_bubble_{mod}.png") for mod in modules]
        go_bar_paths = [os.path.join(output_dir, f"GO_bar_{mod}.png") for mod in modules]
        kegg_bubble_paths = [os.path.join(output_dir, f"KEGG_bubble_{mod}.png") for mod in modules]
        kegg_bar_paths = [os.path.join(output_dir, f"KEGG_bar_{mod}.png") for mod in modules]
        
        go_bubble_paths = [p for p in go_bubble_paths if os.path.exists(p)]
        go_bar_paths = [p for p in go_bar_paths if os.path.exists(p)]
        kegg_bubble_paths = [p for p in kegg_bubble_paths if os.path.exists(p)]
        kegg_bar_paths = [p for p in kegg_bar_paths if os.path.exists(p)]
        
        if hasattr(self.ui, 'bulk_wgcna_label_go_bubble') and go_bubble_paths:
            combined_pixmap = self._combine_images(go_bubble_paths)
            if combined_pixmap:
                self._load_image_to_pixmap(combined_pixmap, self.ui.bulk_wgcna_label_go_bubble)
        
        if hasattr(self.ui, 'bulk_wgcna_label_go_bar') and go_bar_paths:
            combined_pixmap = self._combine_images(go_bar_paths)
            if combined_pixmap:
                self._load_image_to_pixmap(combined_pixmap, self.ui.bulk_wgcna_label_go_bar)
        
        if hasattr(self.ui, 'bulk_wgcna_label_kegg_bubble') and kegg_bubble_paths:
            combined_pixmap = self._combine_images(kegg_bubble_paths)
            if combined_pixmap:
                self._load_image_to_pixmap(combined_pixmap, self.ui.bulk_wgcna_label_kegg_bubble)
        
        if hasattr(self.ui, 'bulk_wgcna_label_kegg_bar') and kegg_bar_paths:
            combined_pixmap = self._combine_images(kegg_bar_paths)
            if combined_pixmap:
                self._load_image_to_pixmap(combined_pixmap, self.ui.bulk_wgcna_label_kegg_bar)

    def _combine_images(self, image_paths):
        from PyQt5.QtGui import QPixmap, QImage
        from PIL import Image
        import io
        
        if len(image_paths) == 1:
            pixmap = QPixmap(image_paths[0])
            return pixmap
        
        images = []
        for path in image_paths:
            img = Image.open(path).convert('RGB')
            images.append(img)
        
        widths, heights = zip(*(img.size for img in images))
        
        max_width = max(widths)
        total_height = sum(heights)
        
        combined = Image.new('RGB', (max_width, total_height))
        
        y_offset = 0
        for img in images:
            combined.paste(img, (0, y_offset))
            y_offset += img.height
        
        buf = io.BytesIO()
        combined.save(buf, format='PNG')
        buf.seek(0)
        
        qimage = QImage.fromData(buf.read())
        return QPixmap.fromImage(qimage)

    def _load_image_to_pixmap(self, pixmap, label_widget):
        if hasattr(label_widget, 'set_pixmap'):
            label_widget.set_pixmap(pixmap)
        else:
            label_widget.setPixmap(pixmap.scaled(
                label_widget.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
            label_widget.setAlignment(Qt.AlignCenter)

    def _load_image_to_label(self, image_path, label_widget):
        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            if hasattr(label_widget, 'set_pixmap'):
                label_widget.set_pixmap(pixmap)
            else:
                label_widget.setPixmap(pixmap.scaled(
                    label_widget.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
                label_widget.setAlignment(Qt.AlignCenter)

    def run_stage6(self):
        self._update_status_text("正在运行阶段六：导出基因集合...")
        QApplication.processEvents()

        try:
            selected_modules = self._get_selected_modules()
            
            if not selected_modules:
                self._update_status_text("请先选择要导出的模块")
                return

            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(None, "保存基因列表", "", "Excel文件 (*.xlsx)")
            if not file_path:
                self._update_status_text("取消导出")
                return

            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'

            save_dir = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            merge_modules = False
            if hasattr(self.ui, 'bulk_wgcna_merge_checkbox'):
                merge_modules = self.ui.bulk_wgcna_merge_checkbox.isChecked()

            export_go_kegg = False
            if hasattr(self.ui, 'bulk_wgcna_export_go_kegg_checkbox'):
                export_go_kegg = self.ui.bulk_wgcna_export_go_kegg_checkbox.isChecked()

            success = self.wgcna_analysis.run_stage6_export_genes(selected_modules=selected_modules, save_path=save_dir, base_name=base_name, merge_modules=merge_modules, export_go_kegg=export_go_kegg)

            if success:
                self._update_status_text(f"阶段六完成!\n已导出基因列表到: {save_dir}")
            else:
                self._update_status_text("阶段六失败")

        except Exception as e:
            self._update_status_text(f"阶段六运行失败: {str(e)}")

    def _export_genes_dialog(self):
        from PyQt5.QtWidgets import QFileDialog
        
        selected_modules = self._get_selected_modules()
        if not selected_modules:
            self._update_status_text("请先选择要导出的模块")
            return

        file_path, _ = QFileDialog.getSaveFileName(None, "保存基因列表", "", "Excel文件 (*.xlsx)")
        if not file_path:
            return

        if not file_path.endswith('.xlsx'):
            file_path += '.xlsx'

        save_dir = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        merge_modules = False
        if hasattr(self.ui, 'bulk_wgcna_merge_checkbox'):
            merge_modules = self.ui.bulk_wgcna_merge_checkbox.isChecked()

        self._update_status_text("正在导出基因列表...")
        QApplication.processEvents()

        try:
            success = self.wgcna_analysis.run_stage5_export_genes(selected_modules=selected_modules, save_path=save_dir, base_name=base_name, merge_modules=merge_modules)

            if success:
                self._update_status_text(f"导出完成!\n已导出基因列表到: {save_dir}")
            else:
                self._update_status_text("导出失败")

        except Exception as e:
            self._update_status_text(f"导出失败: {str(e)}")

    def _get_selected_modules(self):
        modules = []
        if hasattr(self.ui, 'bulk_wgcna_module_list'):
            selected_items = self.ui.bulk_wgcna_module_list.selectedItems()
            modules = [item.text() for item in selected_items]
        return modules if modules else None

    def _get_selected_modules_go(self):
        modules = []
        if hasattr(self.ui, 'bulk_wgcna_module_list_go'):
            selected_items = self.ui.bulk_wgcna_module_list_go.selectedItems()
            modules = [item.text() for item in selected_items]
        return modules if modules else None

    def _populate_module_list(self):
        try:
            modules = self.wgcna_analysis.get_modules()
            if modules:
                if hasattr(self.ui, 'bulk_wgcna_module_list'):
                    self.ui.bulk_wgcna_module_list.clear()
                    self.ui.bulk_wgcna_module_list.addItems(modules)
                if hasattr(self.ui, 'bulk_wgcna_module_list_go'):
                    self.ui.bulk_wgcna_module_list_go.clear()
                    self.ui.bulk_wgcna_module_list_go.addItems(modules)
        except Exception as e:
            print(f"[获取模块列表失败: {e}")

    def _load_sample_dendrogram(self):
        output_dir = self.wgcna_analysis.dataset_output_dir or self.wgcna_analysis._temp_dir
        plot_path = os.path.join(output_dir, "sample_dendrogram.png")
        if os.path.exists(plot_path):
            self.func.display_image(self.ui.bulk_wgcna_label_sample_dendro, plot_path)
            self.ui.bulk_wgcna_plot_tabs.setCurrentWidget(
                self.ui.bulk_wgcna_plot_tabs.widget(0)
            )

    def _load_soft_threshold_plot(self):
        output_dir = self.wgcna_analysis.dataset_output_dir or self.wgcna_analysis._temp_dir
        plot_path = os.path.join(output_dir, "soft_threshold.png")
        if os.path.exists(plot_path):
            self.func.display_image(self.ui.bulk_wgcna_label_soft_threshold, plot_path)
            self.ui.bulk_wgcna_plot_tabs.setCurrentWidget(
                self.ui.bulk_wgcna_plot_tabs.widget(1)
            )

    def _load_gene_dendrogram(self):
        output_dir = self.wgcna_analysis.dataset_output_dir or self.wgcna_analysis._temp_dir
        plot_path = os.path.join(output_dir, "gene_dendrogram_with_modules.png")
        if os.path.exists(plot_path):
            self.func.display_image(self.ui.bulk_wgcna_label_gene_dendro, plot_path)
            self.ui.bulk_wgcna_plot_tabs.setCurrentWidget(
                self.ui.bulk_wgcna_plot_tabs.widget(2)
            )

    def _load_module_merge_plots(self):
        output_dir = self.wgcna_analysis.dataset_output_dir or self.wgcna_analysis._temp_dir
        
        merge_path = os.path.join(output_dir, "module_merge_analysis.png")
        if os.path.exists(merge_path):
            self.func.display_image(self.ui.bulk_wgcna_label_module_merge, merge_path)
        
        comparison_path = os.path.join(output_dir, "module_colors_comparison.png")
        if os.path.exists(comparison_path):
            self.func.display_image(self.ui.bulk_wgcna_label_module_comparison, comparison_path)

    def _load_module_trait_plots(self):
        output_dir = self.wgcna_analysis.dataset_output_dir or self.wgcna_analysis._temp_dir

        module_trait_path = os.path.join(output_dir, "module_trait_heatmap.png")
        if os.path.exists(module_trait_path):
            self.func.display_image(self.ui.bulk_wgcna_label_module_trait, module_trait_path)

        me_boxplot_path = os.path.join(output_dir, "module_me_boxplot.png")
        if os.path.exists(me_boxplot_path):
            self.func.display_image(self.ui.bulk_wgcna_label_me_boxplot, me_boxplot_path)

        module_cluster_path = os.path.join(output_dir, "module_cluster_heatmap.png")
        if os.path.exists(module_cluster_path):
            self.func.display_image(self.ui.bulk_wgcna_label_module_cluster, module_cluster_path)

        gene_significance_path = os.path.join(output_dir, "gene_significance_scatter.png")
        if os.path.exists(gene_significance_path):
            self.func.display_image(self.ui.bulk_wgcna_label_gene_significance, gene_significance_path)

        self.ui.bulk_wgcna_plot_tabs.setCurrentWidget(
            self.ui.bulk_wgcna_plot_tabs.widget(5)
        )

    def _export_current_plot(self, format_type):
        current_index = self.ui.bulk_wgcna_plot_tabs.currentIndex()
        tab_label = self.ui.bulk_wgcna_plot_tabs.tabText(current_index)

        output_dir = self.wgcna_analysis.dataset_output_dir or self.wgcna_analysis._temp_dir
        
        go_kegg_patterns = {
            9: ("GO_bubble_", "GO富集气泡图"),
            10: ("GO_bar_", "GO富集条图"),
            11: ("KEGG_bubble_", "KEGG富集气泡图"),
            12: ("KEGG_bar_", "KEGG富集条图"),
        }

        if current_index in go_kegg_patterns:
            pattern_prefix, desc = go_kegg_patterns[current_index]
            import glob
            from PyQt5.QtWidgets import QFileDialog
            ext = 'pdf' if format_type == 'pdf' else 'png'
            search_pattern = os.path.join(output_dir, f"{pattern_prefix}*.{ext}")
            source_files = glob.glob(search_pattern)
            
            if not source_files:
                self._update_status_text(f"{desc}尚未生成")
                return
            
            save_dir = QFileDialog.getExistingDirectory(self.parent, f"导出{desc}", "")
            if not save_dir:
                return
            
            for src_path in source_files:
                file_name = os.path.basename(src_path)
                dst_path = os.path.join(save_dir, file_name)
                shutil.copy(src_path, dst_path)
            
            show_info(self.parent, "成功", f"已导出{len(source_files)}个{desc}文件到:\n{save_dir}")
            return

        png_file_map = {
            0: os.path.join(output_dir, "sample_dendrogram.png"),
            1: os.path.join(output_dir, "soft_threshold.png"),
            2: os.path.join(output_dir, "gene_dendrogram_with_modules.png"),
            3: os.path.join(output_dir, "module_merge_analysis.png"),
            4: os.path.join(output_dir, "module_colors_comparison.png"),
            5: os.path.join(output_dir, "module_trait_heatmap.png"),
            6: os.path.join(output_dir, "module_me_boxplot.png"),
            7: os.path.join(output_dir, "module_cluster_heatmap.png"),
            8: os.path.join(output_dir, "gene_significance_scatter.png"),
        }
        pdf_file_map = {
            0: os.path.join(output_dir, "sample_dendrogram.pdf"),
            1: os.path.join(output_dir, "soft_threshold.pdf"),
            2: os.path.join(output_dir, "gene_dendrogram_with_modules.pdf"),
            3: os.path.join(output_dir, "module_merge_analysis.pdf"),
            4: os.path.join(output_dir, "module_colors_comparison.pdf"),
            5: os.path.join(output_dir, "module_trait_heatmap.pdf"),
            6: os.path.join(output_dir, "module_me_boxplot.pdf"),
            7: os.path.join(output_dir, "module_cluster_heatmap.pdf"),
            8: os.path.join(output_dir, "gene_significance_scatter.pdf"),
        }

        png_path = png_file_map.get(current_index)
        pdf_path = pdf_file_map.get(current_index)
        
        if format_type == 'pdf':
            source_path = pdf_path
        else:
            source_path = png_path
        
        if not source_path or not os.path.exists(source_path):
            print(f"[导出调试] 当前索引: {current_index}")
            print(f"[导出调试] 当前标签: {tab_label}")
            print(f"[导出调试] PNG路径: {png_path}, 存在: {os.path.exists(png_path) if png_path else False}")
            print(f"[导出调试] PDF路径: {pdf_path}, 存在: {os.path.exists(pdf_path) if pdf_path else False}")
            print(f"[导出调试] 输出目录: {output_dir}, 存在: {os.path.exists(output_dir)}")
            if output_dir and os.path.exists(output_dir):
                print(f"[导出调试] 目录内容: {os.listdir(output_dir)}")
            self._update_status_text("当前图表尚未生成")
            return

        if format_type == 'pdf':
            save_path = self.func.get_save_file_path(
                f"导出{tab_label}",
                f"{tab_label}.pdf",
                "PDF文件 (*.pdf)"
            )
        elif format_type == 'png':
            save_path = self.func.get_save_file_path(
                f"导出{tab_label}",
                f"{tab_label}.png",
                "PNG文件 (*.png)"
            )
        elif format_type == 'svg':
            save_path = self.func.get_save_file_path(
                f"导出{tab_label}",
                f"{tab_label}.svg",
                "SVG文件 (*.svg)"
            )
        else:
            return

        if save_path:
            try:
                if format_type == 'pdf':
                    shutil.copy(source_path, save_path)
                elif format_type == 'png':
                    shutil.copy(source_path, save_path)
                elif format_type == 'svg':
                    shutil.copy(pdf_path.replace('.pdf', '.png'), save_path)
                
                show_info(self.parent, "成功", f"已导出到:\n{save_path}")
            except Exception as e:
                import traceback
                print(f"[导出错误] {traceback.format_exc()}")
                show_error(self.parent, "错误", f"导出失败:\n{str(e)}")