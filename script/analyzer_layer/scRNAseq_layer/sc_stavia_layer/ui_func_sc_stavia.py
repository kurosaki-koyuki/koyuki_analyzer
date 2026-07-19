# -*- coding: utf-8 -*-
"""
单细胞StaVIA分析界面前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

import os
import io
from script.utils_layer.import_config import *


class ScStaviaFunc:
    """单细胞StaVIA分析界面前端功能类 - 纯前端显示操作"""

    def __init__(self, ui):
        self.ui = ui
        self.current_image_paths = {}
        self.current_image_figures = {}

    def log(self, message):
        if hasattr(self.ui, 'log_text'):
            self.ui.log_text.append(message)
            self.ui.log_text.verticalScrollBar().setValue(
                self.ui.log_text.verticalScrollBar().maximum()
            )

    def clear_log(self):
        if hasattr(self.ui, 'log_text'):
            self.ui.log_text.clear()



    def update_use_rep_options(self, obsm_keys):
        if hasattr(self.ui, 'cb_use_rep'):
            self.ui.cb_use_rep.clear()
            self.ui.cb_use_rep.addItems(obsm_keys)

    def update_basis_options(self, embedding_keys):
        if hasattr(self.ui, 'cb_basis'):
            self.ui.cb_basis.clear()
            self.ui.cb_basis.addItems(embedding_keys)

    def update_main_list(self, group, unique_vals):
        if hasattr(self.ui, 'stavia_main_list'):
            self.fill_list_widget(self.ui.stavia_main_list, unique_vals)

    def update_filter1_list(self, group, unique_vals):
        if hasattr(self.ui, 'stavia_filter1_list'):
            self.fill_list_widget(self.ui.stavia_filter1_list, unique_vals)

    def update_filter2_list(self, group, unique_vals):
        if hasattr(self.ui, 'stavia_filter2_list'):
            self.fill_list_widget(self.ui.stavia_filter2_list, unique_vals)

    def fill_list_widget(self, list_widget, items):
        list_widget.clear()
        for item in items:
            list_widget.addItem(str(item))
            list_widget.item(list_widget.count() - 1).setSelected(True)

    def show_info(self, results):
        pass

    def display_image(self, image_key, image_figure=None):
        label_map = {
            'piechart': 'lbl_piechart',
            'pt_via': 'lbl_pt',
            'trajectory': 'lbl_trajectory',
            'atlas': 'lbl_atlas',
            'streamplot_cluster': 'lbl_streamplot_cluster',
            'streamplot_pt': 'lbl_streamplot_pt',
        }

        label_name = label_map.get(image_key)
        if not label_name:
            return

        label = getattr(self.ui, label_name, None)
        if not label:
            return

        if image_figure is not None:
            buf = io.BytesIO()
            image_figure.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(pixmap)
            else:
                scaled_pixmap = pixmap.scaled(
                    label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                label.setPixmap(scaled_pixmap)
            self.current_image_figures[image_key] = image_figure
        else:
            if hasattr(label, 'set_pixmap'):
                label.set_pixmap(None)
            else:
                label.clear()
            self.current_image_figures[image_key] = None

    def display_all_plots(self, plots):
        for key, fig in plots.items():
            self.display_image(key, fig)

    def clear_results(self):
        if hasattr(self.ui, 'info_text'):
            self.ui.info_text.clear()

        labels = ['lbl_piechart', 'lbl_pt', 'lbl_trajectory', 'lbl_atlas', 
                  'lbl_streamplot_cluster', 'lbl_streamplot_pt']
        for label_name in labels:
            label = getattr(self.ui, label_name, None)
            if label:
                if hasattr(label, 'set_pixmap'):
                    label.set_pixmap(None)
                else:
                    label.clear()

        self.current_image_paths = {}
        self.current_image_figures = {}

    def get_current_figure(self, tab_name):
        tab_map = {
            '谱系饼图': 'piechart',
            '伪时间图': 'pt_via',
            '轨迹曲线': 'trajectory',
            'Atlas视图': 'atlas',
            '轨迹箭头图': 'streamplot_cluster',
            '轨迹箭头图(PT)': 'streamplot_pt',
        }
        key = tab_map.get(tab_name)
        if key and key in self.current_image_figures:
            return self.current_image_figures[key]
        return None