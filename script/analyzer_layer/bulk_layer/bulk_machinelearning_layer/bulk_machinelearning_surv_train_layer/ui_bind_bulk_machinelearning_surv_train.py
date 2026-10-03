# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 生存训练类(surv_train)子层功能绑定脚本

职责：
1. 初始化下拉框（基因集文件 / 算法组合文件，扫描 APPDATA 目录）
2. 同步下拉框与参数控件选择到主层 Analysis
3. 绑定 4 个阶段运行按钮（QThread 后台执行，进度条/状态文本实时更新）
4. 从主层 Bind 获取共享 Analysis 实例
5. 各阶段完成后刷新对应标签页图片 / 表格结果
返回/导航由主层容器管理。
"""

from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_surv_train_layer.bulk_machinelearning_surv_train_analysis import BulkMachineLearningSurvTrainAnalysis
from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_surv_train_layer.ui_func_bulk_machinelearning_surv_train import BulkMachineLearningSurvTrainFunc
from script.utils_layer.import_config import os
from script.utils_layer.emoji_trigger import show_info, show_error, show_warning
from PyQt5.QtCore import QThread, pyqtSignal


class SurvTrainStageWorker(QThread):
    """生存训练阶段后台运行线程

    信号:
        progress(stage, message): 进度消息
        finished_signal(stage, success, results, error): 完成信号
    """
    progress = pyqtSignal(str, str)
    finished_signal = pyqtSignal(str, bool, dict, str)

    def __init__(self, analysis, main_analysis, stage):
        super().__init__()
        self.analysis = analysis
        self.main_analysis = main_analysis
        self.stage = stage

    def run(self):
        try:
            runner = {
                "stage1": lambda cb: self.analysis.run_stage1(self.main_analysis, progress_callback=cb),
                "stage2": lambda cb: self.analysis.run_stage2(self.main_analysis, progress_callback=cb),
                "stage3": lambda cb: self.analysis.run_stage3(self.main_analysis, progress_callback=cb),
                "stage4": lambda cb: self.analysis.run_stage4(self.main_analysis, progress_callback=cb),
            }
            cb = lambda m, msg: self.progress.emit(m, msg)
            success, results, error = runner[self.stage](cb)
            self.finished_signal.emit(self.stage, success, results, error)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_signal.emit(self.stage, False, {}, str(e))


class BulkMachineLearningSurvTrainBind:
    """机器学习生存训练类绑定类"""

    def __init__(self, main_window, bulk_machinelearning_surv_train_ui):
        self.parent = main_window
        self.main_window = main_window
        self.bulk_machinelearning_surv_train_ui = bulk_machinelearning_surv_train_ui
        self.analysis = BulkMachineLearningSurvTrainAnalysis()
        self.func = BulkMachineLearningSurvTrainFunc(bulk_machinelearning_surv_train_ui)
        # 主层 Analysis 实例（懒加载）
        self.main_analysis = None
        # 后台线程引用
        self.worker = None
        self.bind_signals()

    # ============================================================
    # 主层 Analysis 实例获取（懒加载）
    # ============================================================

    def _get_main_analysis(self):
        """获取主层 Analysis 实例（从主层 Bind 获取或创建）"""
        if self.main_analysis is not None:
            return self.main_analysis
        main_bind = getattr(self.main_window, 'bulk_machinelearning_bind', None)
        if main_bind is not None and hasattr(main_bind, 'analysis') and main_bind.analysis is not None:
            self.main_analysis = main_bind.analysis
            return self.main_analysis
        try:
            from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_analysis import BulkMachineLearningAnalysis
            self.main_analysis = BulkMachineLearningAnalysis()
            if main_bind is not None:
                main_bind.analysis = self.main_analysis
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.main_analysis = None
        return self.main_analysis

    # ============================================================
    # 信号绑定
    # ============================================================

    def bind_signals(self):
        ui = self.bulk_machinelearning_surv_train_ui
        # 初始化下拉框（扫描 APPDATA 目录）
        self.func.fill_gene_combo(self.analysis.list_gene_files())
        methods_files = self.analysis.list_methods_files()
        self.func.fill_methods_combo(methods_files)
        # 默认选中方法文件（优先完整算法，展示全部算法；缺失则回退 30 算法）
        if hasattr(ui, 'methods_combo') and ui.methods_combo is not None and methods_files:
            default_name = "methods_full.txt"
            if default_name not in methods_files or ui.methods_combo.findText(default_name) < 0:
                default_name = "methods_30.txt"
            if ui.methods_combo.findText(default_name) >= 0:
                ui.methods_combo.setCurrentText(default_name)
        # 绑定下拉框变更信号 -> 同步到主层 Analysis
        if hasattr(ui, 'gene_file_combo') and ui.gene_file_combo is not None:
            ui.gene_file_combo.currentTextChanged.connect(self._sync_gene_file)
        if hasattr(ui, 'methods_combo') and ui.methods_combo is not None:
            ui.methods_combo.currentTextChanged.connect(self._sync_methods_file)
        # 绑定 4 个阶段运行按钮
        for attr, stage in (
            ('btn_run_stage1', 'stage1'),
            ('btn_run_stage2', 'stage2'),
            ('btn_run_stage3', 'stage3'),
            ('btn_run_stage4', 'stage4'),
        ):
            if hasattr(ui, attr) and getattr(ui, attr) is not None:
                getattr(ui, attr).clicked.connect(
                    lambda _checked=False, s=stage: self.run_stage(s)
                )
        # 绑定 3 个导出按钮
        self._bind_export_buttons()
        # 初始同步当前值到主层（默认值）
        self._sync_gene_file(); self._sync_methods_file()
        self._sync_max_genes(); self._sync_seed()
        self._sync_max_features(); self._sync_top_frac()
        self._sync_plot_width_cm(); self._sync_plot_height_cm()

    # ============================================================
    # 参数控件 -> 主层 Analysis 同步
    # ============================================================

    def _main_analysis_or_log(self):
        """获取主层 Analysis，失败时记录日志并返回 None"""
        main_analysis = self._get_main_analysis()
        if main_analysis is None:
            self.func.log("无法获取主层 Analysis 实例，请刷新页面")
        return main_analysis

    def _sync_gene_file(self, *_):
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'gene_file_combo') or ui.gene_file_combo is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.surv_train_gene_file = ui.gene_file_combo.currentText()

    def _sync_methods_file(self, *_):
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'methods_combo') or ui.methods_combo is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.surv_train_methods_file = ui.methods_combo.currentText()

    def _sync_max_genes(self, *_):
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'max_genes_spin') or ui.max_genes_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.surv_train_max_genes = ui.max_genes_spin.value()

    def _sync_seed(self, *_):
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'seed_spin') or ui.seed_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.surv_train_seed = ui.seed_spin.value()

    def _sync_max_features(self, *_):
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'max_features_spin') or ui.max_features_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.surv_train_max_features = ui.max_features_spin.value()

    def _sync_top_frac(self, *_):
        """同步重要性 Top-N 比例（UI 用百分比整数，store 为 0-1 小数）"""
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'top_frac_spin') or ui.top_frac_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            pct = ui.top_frac_spin.value()
            main_analysis.surv_train_top_frac = round(max(5, min(100, pct)) / 100.0, 4)

    def _sync_plot_width_cm(self, *_):
        """同步热图画布宽度(cm)"""
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'plot_width_spin') or ui.plot_width_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.surv_train_plot_width_cm = float(ui.plot_width_spin.value())

    def _sync_plot_height_cm(self, *_):
        """同步热图画布高度(cm)"""
        ui = self.bulk_machinelearning_surv_train_ui
        if not hasattr(ui, 'plot_height_spin') or ui.plot_height_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.surv_train_plot_height_cm = float(ui.plot_height_spin.value())

    # ============================================================
    # 导出按钮
    # ============================================================

    def _bind_export_buttons(self):
        ui = self.bulk_machinelearning_surv_train_ui
        if hasattr(ui, 'btn_export_png') and ui.btn_export_png is not None:
            ui.btn_export_png.clicked.connect(lambda _=False: self._export_images('png'))
        if hasattr(ui, 'btn_export_pdf') and ui.btn_export_pdf is not None:
            ui.btn_export_pdf.clicked.connect(lambda _=False: self._export_images('pdf'))
        if hasattr(ui, 'btn_export_csv') and ui.btn_export_csv is not None:
            ui.btn_export_csv.clicked.connect(lambda _=False: self._export_gene_csv())
        if hasattr(ui, 'btn_send_to_genelist') and ui.btn_send_to_genelist is not None:
            ui.btn_send_to_genelist.clicked.connect(lambda _=False: self.send_to_gene_list_folder())

    def _collect_genes_for_send(self):
        """旧口径 payload = `self.analysis.get_final_gene_names()`
        （= 第一个非空产物文件，施工前的行为，**与「导出最优基因 CSV」同一份输出文件**）。"""
        if self._is_running():
            self.func.log("任务正在运行中，请先等待完成再发送")
            return []
        return self.analysis.get_final_gene_names()

    def _collect_groups_for_send(self):
        """可选子集 `[(标签, 基因, 默认勾选), ...]`：阶段四**真实存在**的每个产物文件一组
        （`surv_best_gene_list.txt` 一组，各 `best_method_genes_<方法>.txt` 各一组）。

        宁少勿假：文件不在就不造这一层。默认勾选使得**默认并集 == 旧口径 payload**
        （即第一个非空产物文件；其余文件若只是它的子集，勾上不改变并集，故默认勾上）。
        """
        if self._is_running():
            return []
        subsets = self.analysis.list_gene_subsets()
        covered = set(self._collect_genes_for_send())
        groups = []
        for label, genes in subsets:
            default = all(g in covered for g in genes)
            groups.append((label, list(genes), default))
        return groups

    def send_to_gene_list_folder(self):
        """把最终入选的最优特征基因发送到 `appdata/genelists`（契约 §3/§4，子集可选）。"""
        if self._is_running():
            self.func.log("[WARN] 任务正在运行中，请先等待完成再发送")
            return

        groups = [(l, g, d) for l, g, d in self._collect_groups_for_send() if g]
        defaults = [g for _l, g, d in groups if d]
        if not defaults:
            self.func.log("[WARN] 当前没有可发送的基因：请先运行阶段四（最优基因）")
            show_warning(self.parent, "没有可发送的基因", "请先运行阶段四：最优基因")
            return

        from script.utils_layer.gene_list_export import ask_and_send
        if len(groups) >= 2:
            r = ask_and_send(self.parent, groups=groups, multi=True, prefix="机器学习_生存特征")
        else:                                   # 只有 1 个子集 → 沿用旧口径（不弹选择区）
            r = ask_and_send(self.parent, defaults[0], prefix="机器学习_生存特征")
        if r.get("ok"):
            self.func.log("[INFO] " + str(r.get("message", "")))
            if r.get("selected_groups"):
                self.func.log("[INFO] 发送集合：" + "、".join(r["selected_groups"]))
        elif r.get("cancelled"):
            self.func.log("[INFO] 已取消发送")
        else:
            self.func.log("[WARN] " + str(r.get("message", "发送失败")))

    def _ask_save_path(self, default_name, file_filter):
        from PyQt5.QtWidgets import QFileDialog
        out_dir = self.analysis.get_out_dir()
        start = os.path.join(out_dir, default_name)
        path, _ = QFileDialog.getSaveFileName(self.parent, "选择保存位置", start, file_filter)
        return path or None

    def _export_images(self, ext):
        if self._is_running():
            self.func.log("任务正在运行中，请先等待完成再导出")
            return
        fmts = {"png": ("全部图片 PNG (*.zip)", "all_images_png.zip"),
                "pdf": ("全部图片 PDF (*.zip)", "all_images_pdf.zip")}
        file_filter, default_name = fmts.get(ext, fmts["png"])
        save_path = self._ask_save_path(default_name, file_filter)
        if save_path is None:
            self.func.log("已取消导出")
            return
        ok, result, err = self.analysis.export_images_zip(ext=ext, save_path=save_path)
        if ok:
            self.func.log(f"已导出 {ext.upper()} 图片并打包: {result}")
            show_info(self.parent, "导出成功", f"已导出全部 {ext.upper()} 图片到:\n{result}")
        else:
            self.func.log(f"导出 {ext.upper()} 失败: {err}")
            show_warning(self.parent, "导出失败", err)

    def _export_gene_csv(self):
        if self._is_running():
            self.func.log("任务正在运行中，请先等待完成再导出")
            return
        save_path = self._ask_save_path("surv_best_genes.csv", "CSV 文件 (*.csv)")
        if save_path is None:
            self.func.log("已取消导出")
            return
        ok, result, err = self.analysis.export_gene_list_csv(save_path=save_path)
        if ok:
            self.func.log(f"已导出最优基因 csv: {result}")
            show_info(self.parent, "导出成功", f"已导出最优基因到:\n{result}")
        else:
            self.func.log(f"导出最优基因失败: {err}")
            show_warning(self.parent, "导出失败", err)

    # ============================================================
    # 运行阶段
    # ============================================================

    def _is_running(self):
        return self.worker is not None and self.worker.isRunning()

    def _set_buttons_enabled(self, enabled):
        ui = self.bulk_machinelearning_surv_train_ui
        for attr in ('gene_file_combo', 'methods_combo', 'max_genes_spin',
                     'seed_spin', 'max_features_spin', 'top_frac_spin',
                     'plot_width_spin', 'plot_height_spin',
                     'btn_run_stage1', 'btn_run_stage2', 'btn_run_stage3',
                     'btn_run_stage4', 'btn_export_png', 'btn_export_pdf',
                     'btn_export_csv'):
            widget = getattr(ui, attr, None)
            if hasattr(ui, attr) and widget is not None:
                widget.setEnabled(enabled)

    def run_stage(self, stage):
        """运行指定训练阶段（后台线程执行）"""
        if self._is_running():
            self.func.log("任务正在运行中，请稍候...")
            return
        if not self.analysis.is_r_available():
            self.func.log("R 环境不可用，请检查 R 内核配置")
            return
        main_analysis = self._get_main_analysis()
        if main_analysis is None:
            self.func.log("无法获取主层 Analysis 实例")
            return

        # 实时读取参数控件当前值并同步到主层
        self._sync_gene_file(); self._sync_methods_file()
        self._sync_max_genes(); self._sync_seed()
        self._sync_max_features(); self._sync_top_frac()
        self._sync_plot_width_cm(); self._sync_plot_height_cm()

        stage_names = {
            "stage1": "阶段一：数据准备",
            "stage2": "阶段二：批量建模(算法选基因)",
            "stage3": "阶段三：生存分析+iAUC热图",
            "stage4": "阶段四：最优基因",
        }
        self.func.log(f"开始运行 {stage_names[stage]}...")
        self._set_buttons_enabled(False)
        self.func.set_progress(None, visible=True)

        self.worker = SurvTrainStageWorker(self.analysis, main_analysis, stage)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_stage_finished)
        self.worker.start()

    def _on_progress(self, stage, message):
        self.func.log(message)

    def _on_stage_finished(self, stage, success, results, error):
        stage_names = {
            "stage1": "阶段一：数据准备",
            "stage2": "阶段二：批量建模(算法选基因)",
            "stage3": "阶段三：生存分析+iAUC热图",
            "stage4": "阶段四：最优基因",
        }
        self.func.set_progress(0, visible=False)
        self._set_buttons_enabled(True)

        if not success:
            self.func.log(f"{stage_names[stage]} 失败: {error}")
            show_error(self.parent, "错误", f"{stage_names[stage]} 失败:\n{error}")
            return

        self.func.log(f"{stage_names[stage]} 完成！")
        self._refresh_result_tabs(stage)
        show_info(self.parent, "成功", f"{stage_names[stage]} 完成！")

    # ============================================================
    # 结果刷新
    # ============================================================

    def _refresh_result_tabs(self, stage):
        ui = self.bulk_machinelearning_surv_train_ui
        out_dir = self.analysis.get_out_dir()

        if stage == "stage1":
            txt_path = os.path.join(out_dir, "train_ready.txt")
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, encoding='utf-8', errors='replace') as f:
                        content = f.read()
                except Exception:
                    content = ""
                te = getattr(ui, 'stage1_data_text', None)
                if te is not None and content:
                    te.setPlainText("训练数据概要（含提取的生存信息）:\n\n" + content)
                    self.func.log("阶段一数据概要已写入「阶段一：数据概要」标签页")
            # 同时展示提取到的生存元数据信息
        elif stage == "stage3":
            png_path = os.path.join(out_dir, "surv_iAUC_heatmap.png")
            label = getattr(ui, 'iauc_heatmap_label', None)
            if label is not None:
                self.func.set_image(label, png_path)
            pdf_path = os.path.join(out_dir, "surv_iAUC_heatmap.pdf")
            self.func.log(f"iAUC 热图输出: {png_path} (PDF: {pdf_path})")
            # 算法性能表
            method_txt = os.path.join(out_dir, "method_performance.txt")
            self.func.fill_method_table(getattr(ui, 'method_table', None), method_txt)
            self.func.log("算法性能排序表已刷新")
        elif stage == "stage4":
            gene_txt = os.path.join(out_dir, "surv_best_gene_list.txt")
            import glob as _glob
            if not os.path.exists(gene_txt):
                cand = sorted(_glob.glob(os.path.join(out_dir, "best_method_genes_*.txt")))
                if cand:
                    gene_txt = cand[0]
            self.func.fill_gene_table(getattr(ui, 'best_gene_table', None), gene_txt)
            self.func.log(f"最优基因表输出: {gene_txt}")

    # ============================================================
    # 主层透传入口
    # ============================================================

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        """从 bulk 主页同步数据（由主层容器透传调用）"""
        pass
