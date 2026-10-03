# -*- coding: utf-8 -*-
"""
scRNAseq hdWGCNA分析界面功能层脚本 - 负责前端显示、控件更新、图像显示等UI相关功能
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget
)
from script.mods_layer.mod_manager import global_mod_manager


class ScHdWgcnaFunc:
    def __init__(self, main_window, sc_hdwgcna_ui):
        self.main_window = main_window
        self.sc_hdwgcna_ui = sc_hdwgcna_ui

    def log(self, message):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_status_text'):
            current_text = self.sc_hdwgcna_ui.sc_hdwgcna_status_text.toPlainText()
            new_text = current_text + "\n" + message if current_text else message
            self.sc_hdwgcna_ui.sc_hdwgcna_status_text.setPlainText(new_text)
            self.sc_hdwgcna_ui.sc_hdwgcna_status_text.verticalScrollBar().setValue(
                self.sc_hdwgcna_ui.sc_hdwgcna_status_text.verticalScrollBar().maximum()
            )

    def update_r_version(self, version):
        if hasattr(self.sc_hdwgcna_ui, 'r_version_label'):
            self.sc_hdwgcna_ui.r_version_label.setText(f"R版本: {version}")

    def show_image(self, image_path, image_title="分析结果"):
        if not hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_plot_tabs'):
            return False

        try:
            if not os.path.exists(image_path):
                self.log(f"图像文件不存在: {image_path}")
                return False

            if hasattr(self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs, 'addTab'):
                from script.utils_layer.gui_styles import create_styled_image_tab
                _, label = create_styled_image_tab(
                    self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs, 
                    image_title,
                    default_text="",
                    data_hint_template=""
                )
                label.load_image(image_path)
                return True
            else:
                self.log("图像标签页不支持addTab方法")
                return False
        except Exception as e:
            self.log(f"显示图像失败: {str(e)}")
            return False

    def clear_images(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_plot_tabs'):
            while self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.count() > 0:
                self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.removeTab(0)

    def update_seurat_status(self, status_text):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_seurat_status'):
            self.sc_hdwgcna_ui.sc_hdwgcna_seurat_status.setText(status_text)

    def update_seurat_info(self, info_text):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_seurat_info_text'):
            self.sc_hdwgcna_ui.sc_hdwgcna_seurat_info_text.setPlainText(info_text)

    def update_analyze_group_combo(self, columns):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_analyze_group_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_analyze_group_combo.clear()
            for col in columns:
                self.sc_hdwgcna_ui.sc_hdwgcna_analyze_group_combo.addItem(col)
            
            preferred_cols = ['Celltype (major-lineage)', 'Celltype', 'celltype', 'MajorLineage', 'major_lineage']
            for preferred in preferred_cols:
                idx = self.sc_hdwgcna_ui.sc_hdwgcna_analyze_group_combo.findText(preferred)
                if idx >= 0:
                    self.sc_hdwgcna_ui.sc_hdwgcna_analyze_group_combo.setCurrentIndex(idx)
                    return

    def update_sample_group_combo(self, columns):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_sample_group_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_sample_group_combo.clear()
            for col in columns:
                self.sc_hdwgcna_ui.sc_hdwgcna_sample_group_combo.addItem(col)

    def update_target_cell_combo(self, cell_types):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_target_cell_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_target_cell_combo.clear()
            self.sc_hdwgcna_ui.sc_hdwgcna_target_cell_combo.addItem("全部")
            for cell_type in cell_types:
                self.sc_hdwgcna_ui.sc_hdwgcna_target_cell_combo.addItem(cell_type)

    def get_selected_analyze_group(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_analyze_group_combo'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_analyze_group_combo.currentText()
        return "Celltype (major-lineage)"

    def get_selected_sample_group(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_sample_group_combo'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_sample_group_combo.currentText()
        return "Sample"

    def get_selected_target_cell(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_target_cell_combo'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_target_cell_combo.currentText()
        return "全部"

    def get_n_genes(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_n_genes_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_n_genes_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return None

    def get_gene_select_mode(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_gene_select_mode_combo'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_gene_select_mode_combo.currentText()
            if 'fraction' in text:
                return 'fraction'
            elif 'custom' in text:
                return 'custom'
            elif '高变' in text:
                return 'variable'
        return 'fraction'

    def get_fraction_value(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_fraction_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_fraction_input.text().strip()
            if text:
                try:
                    val = float(text)
                    if 0 < val <= 1:
                        return val
                except ValueError:
                    pass
        return 0.05

    def get_custom_gene_list_name(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_custom_gene_combo'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_custom_gene_combo.currentText()
        return ""

    def get_variable_gene_count(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_variable_gene_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_variable_gene_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 3000

    def _get_genelists_dir(self):
        from script.utils_layer.import_config import BASE_DIR
        return os.path.join(BASE_DIR, 'appdata', 'genelists')

    def load_gene_list_files(self):
        genelists_dir = self._get_genelists_dir()
        if not os.path.exists(genelists_dir):
            os.makedirs(genelists_dir, exist_ok=True)
            return []
        
        xlsx_files = []
        for f in os.listdir(genelists_dir):
            if f.lower().endswith('.xlsx') or f.lower().endswith('.xls'):
                xlsx_files.append(f)
        return xlsx_files

    def update_custom_gene_combo(self):
        gene_files = self.load_gene_list_files()
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_custom_gene_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_custom_gene_combo.clear()
            for f in gene_files:
                self.sc_hdwgcna_ui.sc_hdwgcna_custom_gene_combo.addItem(f)

    def get_custom_gene_list_path(self):
        gene_list_name = self.get_custom_gene_list_name()
        if not gene_list_name:
            return None
        gene_list_path = os.path.join(self._get_genelists_dir(), gene_list_name)
        return gene_list_path if os.path.exists(gene_list_path) else None

    def get_recluster(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_recluster_checkbox'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_recluster_checkbox.isChecked()
        return True

    def get_dims(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_dims_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_dims_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 30

    def update_filter_combo(self, columns):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_filter_combo.clear()
            for col in columns:
                self.sc_hdwgcna_ui.sc_hdwgcna_filter_combo.addItem(col)

    def update_filter_list(self, values):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_list'):
            self.sc_hdwgcna_ui.sc_hdwgcna_filter_list.clear()
            for val in values:
                self.sc_hdwgcna_ui.sc_hdwgcna_filter_list.addItem(val)

    def is_filter_enabled(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_enable'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_filter_enable.isChecked()
        return False

    def get_selected_filter_col(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_combo'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_filter_combo.currentText()
        return ""

    def get_selected_filter_groups(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_list'):
            selected_items = self.sc_hdwgcna_ui.sc_hdwgcna_filter_list.selectedItems()
            return [item.text() for item in selected_items]
        return []

    def get_k_value(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_k_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_k_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 25

    def get_max_shared_value(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_max_shared_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_max_shared_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 10

    def get_min_cells_value(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_min_cells_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_min_cells_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 80

    def get_network_type(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_network_type_combo'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_network_type_combo.currentText()
        return 'unsigned'

    def get_manual_power(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_manual_power_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_manual_power_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return None

    def update_power_estimate(self, power):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_power_estimate_label'):
            self.sc_hdwgcna_ui.sc_hdwgcna_power_estimate_label.setText(f"推荐软阈值: {power}")

    def update_umap_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_umap'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_umap.set_pixmap(pixmap)

    def update_soft_threshold_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_soft_threshold'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_soft_threshold.set_pixmap(pixmap)

    def update_gene_dendro_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_gene_dendro'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_gene_dendro.set_pixmap(pixmap)

    def update_module_heatmap_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_module_heatmap'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_module_heatmap.set_pixmap(pixmap)

    def update_go_bubble_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_go_bubble'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_go_bubble.set_pixmap(pixmap)

    def update_module_list(self, modules):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_module_list_go'):
            self.sc_hdwgcna_ui.sc_hdwgcna_module_list_go.clear()
            for module in modules:
                self.sc_hdwgcna_ui.sc_hdwgcna_module_list_go.addItem(module)

    def update_trait_list(self, columns):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_trait_list'):
            self.sc_hdwgcna_ui.sc_hdwgcna_trait_list.clear()
            for col in columns:
                self.sc_hdwgcna_ui.sc_hdwgcna_trait_list.addItem(col)

    def get_selected_trait_cols(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_trait_list'):
            selected_items = self.sc_hdwgcna_ui.sc_hdwgcna_trait_list.selectedItems()
            return [item.text() for item in selected_items]
        return []

    def get_selected_modules(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_module_list_go'):
            selected_items = self.sc_hdwgcna_ui.sc_hdwgcna_module_list_go.selectedItems()
            return [item.text() for item in selected_items]
        return []

    def get_organism(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_organism_combo'):
            return self.sc_hdwgcna_ui.sc_hdwgcna_organism_combo.currentText()
        return 'hsa'

    def get_go_padj_cutoff(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_go_padj_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_go_padj_input.text().strip()
            if text:
                try:
                    return float(text)
                except ValueError:
                    pass
        return 0.05

    def get_kegg_padj_cutoff(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_kegg_padj_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_kegg_padj_input.text().strip()
            if text:
                try:
                    return float(text)
                except ValueError:
                    pass
        return 0.05

    def get_go_top_n(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_go_top_n_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_go_top_n_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 15

    def get_kegg_top_n(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_kegg_top_n_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_kegg_top_n_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 15

    def get_power(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_power_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_power_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return None

    def get_min_module_size(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_min_module_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_min_module_input.text().strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        return 30

    def get_merge_threshold(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_merge_threshold_input'):
            text = self.sc_hdwgcna_ui.sc_hdwgcna_merge_threshold_input.text().strip()
            if text:
                try:
                    return float(text)
                except ValueError:
                    pass
        return 0.25

    def update_kme_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_kme'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_kme.set_pixmap(pixmap)

    def update_hme_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_hme'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_hme.set_pixmap(pixmap)

    def update_correlogram_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_correlogram'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_correlogram.set_pixmap(pixmap)

    def update_dotplot_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_dotplot'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_dotplot.set_pixmap(pixmap)

    def update_module_umap_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_module_umap'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_module_umap.set_pixmap(pixmap)

    def update_go_bubble_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_go_bubble'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_go_bubble.set_pixmap(pixmap)

    def update_go_bar_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_go_bar'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_go_bar.set_pixmap(pixmap)

    def update_kegg_bar_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_kegg_bar'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_kegg_bar.set_pixmap(pixmap)

    def update_kegg_bubble_plot(self, image_path):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_label_kegg_bubble'):
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            self.sc_hdwgcna_ui.sc_hdwgcna_label_kegg_bubble.set_pixmap(pixmap)

    def switch_to_tab(self, tab_name):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_plot_tabs'):
            for i in range(self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.count()):
                if self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.tabText(i) == tab_name:
                    self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.setCurrentIndex(i)
                    return True
        return False

    def export_current_plot(self, format_type):
        current_tab_index = self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.currentIndex()
        if current_tab_index < 0:
            self.log("请先选择一个图表标签页")
            return

        from PyQt5.QtWidgets import QFileDialog
        
        current_tab_text = self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.tabText(current_tab_index)
        default_filename = f"hdWGCNA_{current_tab_text}.{format_type}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            f"导出{format_type.upper()}文件",
            default_filename,
            f"{format_type.upper()}文件 (*.{format_type})"
        )
        
        if file_path:
            try:
                import shutil
                image_label = self.sc_hdwgcna_ui.sc_hdwgcna_plot_tabs.widget(current_tab_index).findChild(QLabel)
                if image_label and image_label.pixmap():
                    pixmap = image_label.pixmap()
                    if format_type == 'png':
                        pixmap.save(file_path, 'PNG')
                    elif format_type == 'pdf':
                        pixmap.save(file_path, 'PDF')
                    elif format_type == 'svg':
                        pixmap.save(file_path, 'SVG')
                    self.log(f"图表已导出到: {file_path}")
                else:
                    self.log("当前标签页没有可导出的图像")
            except Exception as e:
                self.log(f"导出失败: {str(e)}")