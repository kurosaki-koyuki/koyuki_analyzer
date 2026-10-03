# -*- coding: utf-8 -*-
"""
UMAP初步作图R版本前端功能脚本 - 纯前端显示操作
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScUmapInitialRFunc:
    def __init__(self, analysis_ui, parent_widget=None):
        self.analysis_ui = analysis_ui
        self.parent_widget = parent_widget

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
        combo_widget.blockSignals(False)

    def set_combo_index(self, combo_widget, index):
        combo_widget.blockSignals(True)
        combo_widget.setCurrentIndex(index)
        combo_widget.blockSignals(False)

    def update_data_info(self, info_dict):
        if not hasattr(self.analysis_ui, 'data_info_text'):
            return
        text_edit = self.analysis_ui.data_info_text
        text_edit.clear()
        text_edit.append(f"细胞数: {info_dict.get('cells', 0)}")
        text_edit.append(f"基因数: {info_dict.get('genes', 0)}")
        text_edit.append(f"UMAP: {'有' if info_dict.get('has_umap', False) else '无'}")
        text_edit.append(f"数据集: {info_dict.get('dataset', '')}")

    def display_image(self, image_path, label_name=None):
        if not image_path or not os.path.exists(image_path):
            return

        pixmap = QPixmap(image_path)
        
        if label_name:
            label = getattr(self.analysis_ui, label_name, None)
        else:
            label = getattr(self.analysis_ui, 'image_label', None)
        
        if label:
            if isinstance(label, ZoomableImageLabel):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap.scaled(
                    label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _stitch_images(self, image_paths):
        if not image_paths:
            return None
        
        pixmaps = []
        for path in image_paths:
            if os.path.exists(path):
                pixmaps.append(QPixmap(path))
        
        if not pixmaps:
            return None
        
        num_images = len(pixmaps)
        cols = 3
        rows = (num_images + 2) // 3
        
        max_width = max(p.width() for p in pixmaps)
        max_height = max(p.height() for p in pixmaps)
        
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
        
        return QPixmap.fromImage(result)

    def display_expression_images(self, image_paths):
        if not hasattr(self.analysis_ui, 'expression_layout'):
            return
        
        layout = self.analysis_ui.expression_layout
        
        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        if not image_paths:
            return
        
        stitched_pixmap = self._stitch_images(image_paths)
        if stitched_pixmap:
            label = ZoomableImageLabel()
            label.set_pixmap(stitched_pixmap)
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            return
        
        num_images = len(image_paths)
        rows = (num_images + 2) // 3
        
        for row in range(rows):
            row_layout = QHBoxLayout()
            for col in range(3):
                idx = row * 3 + col
                if idx >= num_images:
                    break
                
                image_path = image_paths[idx]
                if os.path.exists(image_path):
                    pixmap = QPixmap(image_path)
                    label = ZoomableImageLabel()
                    label.set_pixmap(pixmap)
                    label.setAlignment(Qt.AlignCenter)
                    row_layout.addWidget(label)
                else:
                    placeholder = QLabel(f"图片未找到: {os.path.basename(image_path)}")
                    placeholder.setStyleSheet(get_stylesheet_for_widget('label'))
                    placeholder.setAlignment(Qt.AlignCenter)
                    row_layout.addWidget(placeholder)
            
            layout.addLayout(row_layout)

    def get_current_pixmap(self):
        if not hasattr(self.analysis_ui, 'image_label'):
            return None
        return self.analysis_ui.image_label.pixmap()

    def log(self, message):
        if hasattr(self.analysis_ui, 'status_text'):
            self.analysis_ui.status_text.append(message)

    def clear_log(self):
        if hasattr(self.analysis_ui, 'status_text'):
            self.analysis_ui.status_text.clear()

    def get_save_file_path(self, title, default_name, filter_text):
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    def alert_no_image(self):
        attention(self.parent_widget, "当前没有显示图片")

    def alert_export_success(self, save_path):
        happy(self.parent_widget, f"图片已保存到:\n{save_path}")

    def alert_export_failed(self):
        attention(self.parent_widget, "保存图片失败")

    def alert_export_error(self, error_msg):
        wrong(self.parent_widget, f"导出失败: {str(error_msg)}")

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def export_expression_images_batch(self, image_paths, format='png'):
        if not image_paths or len(image_paths) == 0:
            self.alert_error("没有可导出的图片")
            return
        
        stitched_pixmap = self._stitch_images(image_paths)
        if not stitched_pixmap:
            self.alert_error("图片拼接失败")
            return
        
        default_name = f"{self.analysis_ui.dataset_name}_expression_batch.{format}" if hasattr(self.analysis_ui, 'dataset_name') else f"expression_batch.{format}"
        
        save_path = self.get_save_file_path(
            f"批量保存表达量图为{format.upper()}", 
            default_name, 
            f"{format.upper()}文件 (*.{format})"
        )
        
        if save_path:
            try:
                if not save_path.endswith(f'.{format}'):
                    save_path += f'.{format}'
                
                if format == 'png':
                    stitched_pixmap.save(save_path)
                elif format == 'pdf':
                    qimage = stitched_pixmap.toImage()
                    qimage.save(save_path)
                
                self.alert_export_success(save_path)
            except Exception as e:
                self.alert_export_error(str(e))