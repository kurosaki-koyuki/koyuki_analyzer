# -*- coding: utf-8 -*-
"""
韦恩图界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.commontools_layer.vennplot_layer.vennplot_analysis import VennPlotAnalysis
from script.analyzer_layer.commontools_layer.vennplot_layer.ui_func_vennplot import VennPlotFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.page_intersect import page_intersect


class VennPlotBind:
    """韦恩图功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, vennplot_ui):
        self.parent = parent_window
        self.vennplot_ui = vennplot_ui
        self.analysis = VennPlotAnalysis()
        self.func = VennPlotFunc(vennplot_ui, parent_window)
        self._bindings_done = False
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        if self._bindings_done:
            return

        self.bind_music_controls()
        self.bind_vennplot_buttons()
        self.bind_table_events()
        self.bind_shortcuts()
        self.bind_navigation()

        self._bindings_done = True

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.vennplot_ui, 'btn_back_vennplot'):
            self.vennplot_ui.btn_back_vennplot.clicked.connect(page_intersect.go_to_home)

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.vennplot_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.vennplot_ui.music_controller)

    def bind_vennplot_buttons(self):
        """绑定韦恩图功能按钮"""
        self.vennplot_ui.btn_clear.clicked.connect(self.func.clear_table)
        self.vennplot_ui.btn_apply.clicked.connect(self.func.apply_table_params)
        self.vennplot_ui.btn_run.clicked.connect(self.run_venn_analysis)
        self.vennplot_ui.btn_export_gene_set.clicked.connect(self.export_gene_set_csv)
        self.vennplot_ui.btn_export_matrix.clicked.connect(self.export_intersection_matrix_csv)
        self.vennplot_ui.btn_export_pdf.clicked.connect(self.export_venn_pdf)
        self.vennplot_ui.btn_export_png.clicked.connect(self.export_venn_png)

    def bind_table_events(self):
        """绑定表格事件"""
        if hasattr(self.vennplot_ui, 'venn_table'):
            self.vennplot_ui.venn_table.set_key_press_handler(self.func.handle_key_press_event)

    def bind_shortcuts(self):
        """绑定快捷键"""
        if not hasattr(self.vennplot_ui, 'vennplot_page'):
            return

        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self.vennplot_ui.vennplot_page)
        copy_shortcut.activated.connect(self.func.copy_table)

        cut_shortcut = QShortcut(QKeySequence("Ctrl+X"), self.vennplot_ui.vennplot_page)
        cut_shortcut.activated.connect(self.func.cut_table)

        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self.vennplot_ui.vennplot_page)
        paste_shortcut.activated.connect(self.func.paste_table)

    def run_venn_analysis(self):
        """运行韦恩图分析"""
        try:
            sets_data = self.analysis.read_table_data(self.vennplot_ui.venn_table)

            if len(sets_data) < 2:
                self.func.log("[ERROR] 需要至少2个有内容的集合才能计算交集")
                self.func.alert_error("需要至少2个有内容的集合才能计算交集")
                return

            self.func.log(f"[INFO] 检测到 {len(sets_data)} 个集合，开始计算交集...")

            self.analysis.set_sets_data(sets_data)
            self.analysis.calculate_intersections()

            self.display_intersection_matrix(sets_data)

            plot_path_png, plot_path_pdf = self.analysis.draw_venn_diagram()
            if plot_path_png:
                self.display_venn_plot(plot_path_png)
                self.func.log("[INFO] 韦恩图已生成")
            else:
                self.func.log("[ERROR] 韦恩图生成失败")

        except Exception as e:
            self.func.log(f"[ERROR] 分析失败: {str(e)}")
            import traceback
            self.func.log(f"[ERROR] 详细错误: {traceback.format_exc()}")

    def display_intersection_matrix(self, sets_data):
        """显示交集矩阵"""
        intersection_results = self.analysis.get_intersection_results()
        header, matrix_data = self.analysis.get_intersection_matrix_data(intersection_results, sets_data)
        self.func.fill_intersection_matrix(header, matrix_data)

    def display_venn_plot(self, plot_path):
        """显示韦恩图"""
        if os.path.exists(plot_path):
            pixmap = QPixmap(plot_path)
            if hasattr(self.vennplot_ui.venn_plot_label, 'set_pixmap'):
                self.vennplot_ui.venn_plot_label.set_pixmap(pixmap)
            else:
                self.vennplot_ui.venn_plot_label.setPixmap(pixmap)

    def export_gene_set_csv(self):
        """导出基因集合CSV"""
        try:
            sets_data = self.analysis.read_table_data(self.vennplot_ui.venn_table)
            if not sets_data:
                self.func.log("[ERROR] 没有可导出的数据")
                return

            save_path = self.func.get_save_file_path("导出基因集合", "venn_gene_sets.csv", "CSV文件 (*.csv)")
            if save_path:
                self.analysis.export_gene_set_csv(sets_data, save_path)
                self.func.log(f"[INFO] 基因集合已导出到 {save_path}")
                self.func.alert_success("导出成功")
        except Exception as e:
            self.func.log(f"[ERROR] 导出失败: {str(e)}")

    def export_intersection_matrix_csv(self):
        """导出交集矩阵CSV"""
        try:
            sets_data = self.analysis.read_table_data(self.vennplot_ui.venn_table)
            if len(sets_data) < 2:
                self.func.log("[ERROR] 需要至少2个集合才能导出交集矩阵")
                return

            save_path = self.func.get_save_file_path("导出交集矩阵", "venn_intersection_matrix.csv", "CSV文件 (*.csv)")
            if save_path:
                self.analysis.calculate_intersections()
                intersection_results = self.analysis.get_intersection_results()
                self.analysis.export_intersection_matrix_csv(intersection_results, sets_data, save_path)
                self.func.log(f"[INFO] 交集矩阵已导出到 {save_path}")
                self.func.alert_success("导出成功")
        except Exception as e:
            self.func.log(f"[ERROR] 导出失败: {str(e)}")

    def export_venn_pdf(self):
        """导出韦恩图PDF"""
        try:
            sets_data = self.analysis.read_table_data(self.vennplot_ui.venn_table)
            if len(sets_data) < 2:
                self.func.log("[ERROR] 需要至少2个集合才能生成韦恩图")
                return

            save_path = self.func.get_save_file_path("导出韦恩图PDF", "venn_diagram.pdf", "PDF文件 (*.pdf)")
            if save_path:
                plot_path_png, plot_path_pdf = self.analysis.draw_venn_diagram()
                if plot_path_pdf:
                    success = self.analysis.export_venn_pdf(plot_path_pdf, save_path)
                    if success:
                        self.func.log(f"[INFO] 韦恩图PDF已导出到 {save_path}")
                        self.func.alert_success("导出成功")
                    else:
                        self.func.log("[ERROR] 导出失败")
        except Exception as e:
            self.func.log(f"[ERROR] 导出失败: {str(e)}")

    def export_venn_png(self):
        """导出韦恩图PNG"""
        try:
            sets_data = self.analysis.read_table_data(self.vennplot_ui.venn_table)
            if len(sets_data) < 2:
                self.func.log("[ERROR] 需要至少2个集合才能生成韦恩图")
                return

            save_path = self.func.get_save_file_path("导出韦恩图PNG", "venn_diagram.png", "PNG文件 (*.png)")
            if save_path:
                plot_path_png, plot_path_pdf = self.analysis.draw_venn_diagram()
                if plot_path_png:
                    from PIL import Image
                    img = Image.open(plot_path_png)
                    img.save(save_path, 'PNG')
                    self.func.log(f"[INFO] 韦恩图PNG已导出到 {save_path}")
                    self.func.alert_success("导出成功")
        except Exception as e:
            self.func.log(f"[ERROR] 导出失败: {str(e)}")

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)