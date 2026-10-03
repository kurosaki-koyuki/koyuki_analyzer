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
from script.utils_layer.gene_list_export import ask_and_send                       # noqa: F401
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
            self.vennplot_ui.btn_back_vennplot.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('commontools_top_page'))

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
        # ★ 「发送到列表文件夹」（契约 §1/§4）：**直接** `clicked.connect`。
        #   ⚠ 与左边的「导出基因集合」语义不同（那个走 QFileDialog 存用户自选路径）；
        #      本按钮把**当前选中的交集基因集合**写进 `appdata/genelists`。
        #   ⛔ 不套 `bind_button_with_sound`：多余音效/✓ 日志会盖掉契约 §4.4 要求的
        #      「[INFO] 已发送 xxx.xlsx：写入 N 个基因」。
        if hasattr(self.vennplot_ui, 'btn_send_to_genelist'):
            self.vennplot_ui.btn_send_to_genelist.clicked.connect(self.send_gene_list_to_folder)
        else:
            self.func.log("[WARN] 布局缺少控件 btn_send_to_genelist → 发送到列表文件夹未绑定")
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
            self.display_intersection_genes()

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

    def display_intersection_genes(self):
        """显示各交集基因宽表"""
        intersection_results = self.analysis.get_intersection_results()
        headers, gene_rows = self.analysis.build_intersection_gene_matrix(intersection_results)
        self.func.fill_intersection_genes_table(headers, gene_rows)

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

    # ------------------------------------------------------------------
    # ★ 「发送到列表文件夹」（契约 `docs/features/gene_list_send_contract.md` §1/§3/§4）
    # ------------------------------------------------------------------
    def send_gene_list_to_folder(self):
        """把**当前交集结果**按子集发送到 `appdata/genelists`（★ v2：子集可选）

        ## 子集（契约 §3 表：韦恩图）
          **每个交集组合一组**（标签直接用页面已有的交集标签，即
          `get_intersection_results()` 的 key，如 `A ∩ B`；显示时由弹窗统一补成
          `组合名（N 个）`）+「全部交集并集」；**默认全选**
          ⇒ 发送内容 = 全部交集基因的并集去重 = **与"加子集可选之前"逐字一致**。
        ## 取数来源（契约 §3「子集来自当前结果、不重算不重跑」+ 协调者重申）
          · 集合来源 = `VennPlotAnalysis.read_table_data(self.vennplot_ui.venn_table)`
            （= `export_gene_set_csv` 用的那一份，只读**表头被勾选**的列）；
          · 与「运行」同口径：`set_sets_data()` + `calculate_intersections()`
            （**纯内存、不写盘、每个子集不各跑一次**），子集只是把
            `get_intersection_results()` 的**每个组合**拆成一组。
          ⛔ 绝不另起筛选、绝不重新读文件、绝不重跑分析。
        ⛔ 集合不足 2 个 / 结果为空时：只写 `[WARN]` 日志 + 可读提示，**绝不写空文件**（§3 末条）。
        ⛔ 落盘**只**走共享工具 `ask_and_send`，本页**不自己 `to_excel`**（§1）。
        """
        try:
            groups, flat = self._build_send_groups()
            if not groups:
                msg = "需要至少2个有内容的集合才能发送交集基因（请先在表格中填入并勾选列）"
                self.func.log("[WARN] %s" % msg)
                self.func.alert_error(msg)
                return None
            labels = ", ".join("%s(%d)" % (l, len(g)) for l, g, _d in groups)
            self.func.log("[INFO] 可发送子集: %s（并集去重后 %d 个基因）" % (labels, len(flat)))
            if len(groups) > 1:
                r = ask_and_send(self.parent, groups=groups, multi=True, prefix="交集基因")
            else:
                # 只有 1 个交集组合（2 个集合）⇒ 旧口径，不弹选择区（契约 §3 末条"宁少勿假"）
                r = ask_and_send(self.parent, flat, groups=groups, prefix="交集基因")
            self._report_gene_list_send(r)
            return r
        except Exception as e:            # 槽内**绝不抛**（PyQt5 对未捕获异常会 qFatal）
            import traceback
            self.func.log("[WARN] 发送到列表文件夹失败: %s" % e)
            self.func.log("[WARN] 详细错误:\n%s" % traceback.format_exc())
            return None

    def _build_send_groups(self):
        """构造发送子集 `[(标签, 基因, 默认勾选), ...]`；同时返回并集扁平列表

        · 标签 = 页面已有的交集组合名（`get_intersection_results()` 的 key，**不另起命名**）；
          "（N 个）"由共享工具的弹窗统一补，页面**不**自己拼。
        · 默认勾选：**全 True**（复现旧行为）；「全部交集并集」也是 True。
        · 返回 `([], [])` 表示当前无可发送结果（调用方给提示，不落盘）。
        """
        sets_data = self.analysis.read_table_data(self.vennplot_ui.venn_table)
        if len(sets_data) < 2:
            return [], []
        # ★ 与「运行」同口径：把当前表数据同步进分析层，再算交集（**纯内存、只算一次**）
        self.analysis.set_sets_data(sets_data)
        self.analysis.calculate_intersections()
        intersection_results = self.analysis.get_intersection_results() or {}
        groups = []
        # 组合顺序 = 「各交集基因」宽表同款（`build_intersection_gene_matrix` 用 sorted(keys)）
        for key in sorted(intersection_results.keys()):
            genes = [str(g).strip() for g in (intersection_results[key] or [])]
            genes = [g for g in genes if g]
            if genes:
                groups.append((str(key), genes, True))      # 标签 = 已有交集标签
        if not groups:
            return [], []
        flat_seen, flat = set(), []
        for _label, genes, _default in groups:
            for g in genes:
                if g not in flat_seen:
                    flat_seen.add(g)
                    flat.append(g)
        if len(groups) > 1:
            groups.append(("全部交集并集", list(flat), True))
        return groups, flat

    def _report_gene_list_send(self, r):
        """按 `r["ok"]` 用页面既有日志接口打 `[INFO]`/`[WARN]`（契约 §4.4）"""
        try:
            r = r or {}
            if r.get('cancelled'):
                self.func.log("[INFO] 已取消发送")
            elif r.get('ok'):
                self.func.log("[INFO] %s" % r.get('message', '已发送'))
                self.func.alert_success(r.get('message', '已发送'))
            else:
                msg = r.get('message') or "发送失败"
                self.func.log("[WARN] %s" % msg)
                self.func.alert_error(msg)
        except Exception as e:
            self.func.log("[WARN] 发送结果日志写入失败: %s" % e)

    def export_intersection_matrix_csv(self):
        """导出交集结果（xlsx 多sheet）：交集矩阵统计 + 各交集基因明细/宽表"""
        try:
            sets_data = self.analysis.read_table_data(self.vennplot_ui.venn_table)
            if len(sets_data) < 2:
                self.func.log("[ERROR] 需要至少2个集合才能导出交集结果")
                return

            save_path = self.func.get_save_file_path("导出交集结果", "venn_intersection_result.xlsx", "Excel文件 (*.xlsx)")
            if save_path:
                if not save_path.lower().endswith('.xlsx'):
                    save_path += '.xlsx'
                self.analysis.set_sets_data(sets_data)
                self.analysis.calculate_intersections()
                intersection_results = self.analysis.get_intersection_results()
                self.analysis.export_intersection_result_xlsx(intersection_results, sets_data, save_path)
                self.func.log(f"[INFO] 交集结果已导出到 {save_path}")
                self.func.alert_success("导出成功")
        except Exception as e:
            self.func.log(f"[ERROR] 导出失败: {str(e)}")
            import traceback
            self.func.log(f"[ERROR] 详细错误: {traceback.format_exc()}")

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