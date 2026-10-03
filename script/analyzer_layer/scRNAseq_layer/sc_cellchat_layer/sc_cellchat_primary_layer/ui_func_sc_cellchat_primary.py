# -*- coding: utf-8 -*-
"""
CellChat初步分析类前端功能层
负责前端显示、控件内容更新、图片渲染等
包含日志显示、图片显示、弹窗提示等功能
"""

import os
from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScCellChatPrimaryFunc:
    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget if parent_widget else ui_instance.sc_cellchat_primary_page
        self._stage1_plot_paths = []
        self._stage2_plot_paths = []

    def log(self, message):
        """记录日志"""
        if hasattr(self.ui, 'cellchat_log'):
            current_text = self.ui.cellchat_log.toPlainText()
            new_text = current_text + "\n" + message if current_text else message
            self.ui.cellchat_log.setPlainText(new_text)
            self.ui.cellchat_log.verticalScrollBar().setValue(
                self.ui.cellchat_log.verticalScrollBar().maximum()
            )

    def display_stage1_image(self, image_path):
        """显示阶段一UMAP图"""
        self._stage1_plot_paths = [image_path]
        if not hasattr(self.ui, 'stage1_image_label'):
            return

        label = self.ui.stage1_image_label

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

    def display_stage2_image(self, image_path):
        """显示阶段二筛选后UMAP图"""
        self._stage2_plot_paths = [image_path]
        if not hasattr(self.ui, 'stage2_image_label'):
            return

        label = self.ui.stage2_image_label

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

    def display_image(self, image_path):
        """显示图片到样板标签页（通用方法）"""
        if not hasattr(self.ui, 'sample_image_label'):
            return

        label = self.ui.sample_image_label

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

    def display_stage3_images(self, count_path, weight_path):
        """显示阶段三CellChat分析图片"""
        # 显示通讯数量图
        if hasattr(self.ui, 'stage3_count_image_label'):
            label = self.ui.stage3_count_image_label
            if count_path and os.path.exists(count_path):
                pixmap = QPixmap(count_path)
                if hasattr(label, 'set_pixmap'):
                    label.set_pixmap(pixmap)
                else:
                    label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignCenter)
        
        # 显示通讯强度图
        if hasattr(self.ui, 'stage3_weight_image_label'):
            label = self.ui.stage3_weight_image_label
            if weight_path and os.path.exists(weight_path):
                pixmap = QPixmap(weight_path)
                if hasattr(label, 'set_pixmap'):
                    label.set_pixmap(pixmap)
                else:
                    label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignCenter)

    def display_stage4_image(self, image_path):
        """显示阶段四亚组circle图"""
        if not hasattr(self.ui, 'stage4_subgroup_image_label'):
            return

        label = self.ui.stage4_subgroup_image_label

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

    def display_stage5_images(self, images_dict):
        """显示阶段五信号通路可视化图片
        images_dict格式: {viz_type: image_path}
        viz_type: hierarchy, circle, chord, heatmap
        """
        viz_label_map = {
            'hierarchy': 'stage5_hierarchy_image_label',
            'circle': 'stage5_circle_image_label',
            'chord': 'stage5_chord_image_label',
            'heatmap': 'stage5_heatmap_image_label'
        }
        
        for viz_type, attr_name in viz_label_map.items():
            if hasattr(self.ui, attr_name):
                label = getattr(self.ui, attr_name)
                image_path = images_dict.get(viz_type)
                
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

    def display_pathway_info_table(self, info_data):
        """显示通路信息表格"""
        if hasattr(self.ui, 'table_pathway_info'):
            table = self.ui.table_pathway_info
            if info_data is not None and len(info_data) > 0:
                # 清空表格
                table.setRowCount(0)
                table.setColumnCount(len(info_data.columns))
                table.setHorizontalHeaderLabels(info_data.columns.tolist())
                
                # 填充数据
                for row_idx in range(len(info_data)):
                    table.insertRow(row_idx)
                    for col_idx in range(len(info_data.columns)):
                        value = str(info_data.iloc[row_idx, col_idx])
                        item = QTableWidgetItem(value)
                        item.setTextAlignment(Qt.AlignCenter)
                        table.setItem(row_idx, col_idx, item)
                
                # 调整列宽
                table.resizeColumnsToContents()
            else:
                table.setRowCount(0)
                table.setColumnCount(1)
                table.setHorizontalHeaderLabels(["提示"])
                table.insertRow(0)
                table.setItem(0, 0, QTableWidgetItem("暂无通路信息"))
    
    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))
