# -*- coding: utf-8 -*-
"""
scRNAseq Monocle分析界面前端功能层 - 负责前端显示、控件内容更新、图片渲染等
"""

import os
from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, get_font_for_widget
)
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScMonocleFunc:
    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget if parent_widget else ui_instance.sc_monocle_page
        self._stage1_plot_paths = []
        self._stage2_plot_paths = []

    def log(self, message):
        if hasattr(self.ui, 'monocle_log'):
            current_text = self.ui.monocle_log.toPlainText()
            new_text = current_text + "\n" + message if current_text else message
            self.ui.monocle_log.setPlainText(new_text)
            self.ui.monocle_log.verticalScrollBar().setValue(
                self.ui.monocle_log.verticalScrollBar().maximum()
            )

    def update_data_info(self, info):
        if hasattr(self.ui, 'data_info_text'):
            text = f"数据集: {info.get('dataset', '未知')}\n"
            text += f"细胞数: {info.get('cells', 0)}\n"
            text += f"基因数: {info.get('genes', 0)}\n"
            text += f"有UMAP: {'是' if info.get('has_umap') else '否'}"
            self.ui.data_info_text.setPlainText(text)

    def display_stage1_images(self, image_paths):
        self._stage1_plot_paths = image_paths
        if not hasattr(self.ui, 'stage1_plot_label'):
            return
        
        label = self.ui.stage1_plot_label
        
        if image_paths and len(image_paths) > 0:
            pixmaps = []
            for path in image_paths:
                if os.path.exists(path):
                    pixmaps.append(QPixmap(path))
            
            if pixmaps:
                if len(pixmaps) == 1:
                    final_pixmap = pixmaps[0]
                else:
                    max_width = max(p.width() for p in pixmaps)
                    max_height = max(p.height() for p in pixmaps)
                    cols = 2
                    rows = (len(pixmaps) + cols - 1) // cols
                    
                    total_width = max_width * cols
                    total_height = max_height * rows
                    
                    result = QImage(total_width, total_height, QImage.Format_ARGB32)
                    result.fill(Qt.white)
                    
                    painter = QPainter(result)
                    for i, pixmap in enumerate(pixmaps):
                        row = i // cols
                        col = i % cols
                        x = col * max_width
                        y = row * max_height
                        painter.drawPixmap(x, y, pixmap)
                    
                    painter.end()
                    
                    final_pixmap = QPixmap.fromImage(result)
                
                if hasattr(label, 'set_pixmap'):
                    label.set_pixmap(final_pixmap)
                else:
                    label.setPixmap(final_pixmap)
                    label.setAlignment(Qt.AlignCenter)
        else:
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(None)
            else:
                label.clear()

    def display_stage2_images(self, image_paths):
        self._stage2_plot_paths = image_paths
        if not hasattr(self.ui, 'stage2_plot_label'):
            return
        
        label = self.ui.stage2_plot_label
        
        if image_paths and len(image_paths) > 0:
            pixmaps = []
            for path in image_paths:
                if os.path.exists(path):
                    pixmaps.append(QPixmap(path))
            
            if pixmaps:
                if len(pixmaps) == 1:
                    final_pixmap = pixmaps[0]
                else:
                    max_width = max(p.width() for p in pixmaps)
                    max_height = max(p.height() for p in pixmaps)
                    cols = 2
                    rows = (len(pixmaps) + cols - 1) // cols
                    
                    total_width = max_width * cols
                    total_height = max_height * rows
                    
                    result = QImage(total_width, total_height, QImage.Format_ARGB32)
                    result.fill(Qt.white)
                    
                    painter = QPainter(result)
                    for i, pixmap in enumerate(pixmaps):
                        row = i // cols
                        col = i % cols
                        x = col * max_width
                        y = row * max_height
                        painter.drawPixmap(x, y, pixmap)
                    
                    painter.end()
                    
                    final_pixmap = QPixmap.fromImage(result)
            
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(final_pixmap)
            else:
                label.setPixmap(final_pixmap)
                label.setAlignment(Qt.AlignCenter)
        else:
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(None)
            else:
                label.clear()

    def display_stage3_traj_image(self, image_path):
        self._stage3_traj_path = image_path
        if not hasattr(self.ui, 'stage3_traj_label'):
            return
        
        label = self.ui.stage3_traj_label
        
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignCenter)
        else:
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(None)
            else:
                label.clear()

    def display_stage3_partition_image(self, image_path):
        self._stage3_partition_path = image_path
        if not hasattr(self.ui, 'stage3_partition_label'):
            return
        
        label = self.ui.stage3_partition_label
        
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignCenter)
        else:
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(None)
            else:
                label.clear()

    def display_stage4_pseudotime_image(self, image_path):
        self._stage4_pseudotime_path = image_path
        if not hasattr(self.ui, 'stage4_pseudotime_label'):
            return
        
        label = self.ui.stage4_pseudotime_label
        
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignCenter)
        else:
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(None)
            else:
                label.clear()

    def get_save_file_path(self, caption, default_name, filter_str):
        return QFileDialog.getSaveFileName(
            self.parent_widget,
            caption,
            default_name,
            filter_str
        )[0]

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def alert_no_image(self):
        self.alert_error("当前没有可显示的图片")

    def alert_export_success(self, path):
        self.alert_success(f"导出成功！\n{path}")

    def alert_export_failed(self):
        self.alert_failure("导出失败")

    def alert_export_error(self, message):
        self.alert_failure(f"导出错误: {message}")

    def export_stage1_png(self, output_dir):
        if not self._stage1_plot_paths:
            self.alert_no_image()
            return
        
        default_name = "monocle_stage1_plots.png"
        save_path = self.get_save_file_path("保存阶段一图为PNG", default_name, "PNG文件 (*.png)")
        
        if save_path:
            try:
                if not save_path.endswith('.png'):
                    save_path += '.png'
                
                pixmaps = []
                for path in self._stage1_plot_paths:
                    if os.path.exists(path):
                        pixmaps.append(QPixmap(path))
                
                if pixmaps:
                    max_width = max(p.width() for p in pixmaps)
                    max_height = max(p.height() for p in pixmaps)
                    cols = 2
                    rows = (len(pixmaps) + cols - 1) // cols
                    
                    total_width = max_width * cols
                    total_height = max_height * rows
                    
                    result = QImage(total_width, total_height, QImage.Format_ARGB32)
                    result.fill(Qt.white)
                    
                    painter = QPainter(result)
                    for i, pixmap in enumerate(pixmaps):
                        row = i // cols
                        col = i % cols
                        x = col * max_width
                        y = row * max_height
                        painter.drawPixmap(x, y, pixmap)
                    
                    painter.end()
                    
                    QPixmap.fromImage(result).save(save_path)
                    self.alert_export_success(save_path)
                else:
                    self.alert_export_failed()
            except Exception as e:
                self.alert_export_error(str(e))

    def export_stage1_pdf(self, output_dir):
        if not self._stage1_plot_paths:
            self.alert_no_image()
            return
        
        default_name = "monocle_stage1_plots.pdf"
        save_path = self.get_save_file_path("保存阶段一图为PDF", default_name, "PDF文件 (*.pdf)")
        
        if save_path:
            try:
                if not save_path.endswith('.pdf'):
                    save_path += '.pdf'
                
                pixmaps = []
                for path in self._stage1_plot_paths:
                    if os.path.exists(path):
                        pixmaps.append(QPixmap(path))
                
                if pixmaps:
                    max_width = max(p.width() for p in pixmaps)
                    max_height = max(p.height() for p in pixmaps)
                    cols = 2
                    rows = (len(pixmaps) + cols - 1) // cols
                    
                    total_width = max_width * cols
                    total_height = max_height * rows
                    
                    result = QImage(total_width, total_height, QImage.Format_ARGB32)
                    result.fill(Qt.white)
                    
                    painter = QPainter(result)
                    for i, pixmap in enumerate(pixmaps):
                        row = i // cols
                        col = i % cols
                        x = col * max_width
                        y = row * max_height
                        painter.drawPixmap(x, y, pixmap)
                    
                    painter.end()
                    
                    QPixmap.fromImage(result).toImage().save(save_path)
                    self.alert_export_success(save_path)
                else:
                    self.alert_export_failed()
            except Exception as e:
                self.alert_export_error(str(e))