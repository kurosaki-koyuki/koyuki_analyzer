# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 差异训练类(diff_train)子层功能绑定脚本

职责：
1. 初始化下拉框（基因集文件 / 算法组合文件，扫描 APPDATA 目录）
2. 同步下拉框与参数控件选择到主层 Analysis
3. 绑定 5 个阶段运行按钮（QThread 后台执行，进度条/状态文本实时更新）
4. 从主层 Bind 获取共享 Analysis 实例
5. 各阶段完成后刷新对应标签页图片 / 文本结果
返回/导航由主层容器管理，本子层只负责自身业务逻辑
"""

from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_diff_train_layer.bulk_machinelearning_diff_train_analysis import BulkMachineLearningDiffTrainAnalysis
from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_diff_train_layer.ui_func_bulk_machinelearning_diff_train import BulkMachineLearningDiffTrainFunc
from script.utils_layer.import_config import os
from script.utils_layer.emoji_trigger import show_info, show_error, show_warning
from PyQt5.QtCore import QThread, pyqtSignal


class TrainStageWorker(QThread):
    """机器学习训练阶段后台运行线程

    信号:
        progress(stage, message): 进度消息
        finished_signal(stage, success, results, error): 完成信号
    """
    progress = pyqtSignal(str, str)
    finished_signal = pyqtSignal(str, bool, dict, str)

    def __init__(self, analysis, main_analysis, stage, label_col=None):
        super().__init__()
        self.analysis = analysis
        self.main_analysis = main_analysis
        self.stage = stage
        self.label_col = label_col

    def run(self):
        try:
            runner = {
                "stage1": lambda cb: self.analysis.run_stage1(
                    self.main_analysis, label_col=self.label_col, progress_callback=cb),
                "stage2": lambda cb: self.analysis.run_stage2(
                    self.main_analysis, label_col=self.label_col, progress_callback=cb),
                "stage3": lambda cb: self.analysis.run_stage3(
                    self.main_analysis, label_col=self.label_col, progress_callback=cb),
                "stage4": lambda cb: self.analysis.run_stage4(
                    self.main_analysis, label_col=self.label_col, progress_callback=cb),
                "stage5": lambda cb: self.analysis.run_stage5(
                    self.main_analysis, label_col=self.label_col, progress_callback=cb),
            }
            cb = lambda m, msg: self.progress.emit(m, msg)
            success, results, error = runner[self.stage](cb)
            self.finished_signal.emit(self.stage, success, results, error)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_signal.emit(self.stage, False, {}, str(e))


class BulkMachineLearningDiffTrainBind:
    """机器学习差异训练类绑定类"""

    def __init__(self, main_window, bulk_machinelearning_diff_train_ui):
        self.parent = main_window
        self.main_window = main_window
        self.bulk_machinelearning_diff_train_ui = bulk_machinelearning_diff_train_ui
        self.analysis = BulkMachineLearningDiffTrainAnalysis()
        self.func = BulkMachineLearningDiffTrainFunc(bulk_machinelearning_diff_train_ui)
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
        ui = self.bulk_machinelearning_diff_train_ui
        # 初始化下拉框（扫描 APPDATA 目录）
        self.func.fill_gene_combo(self.analysis.list_gene_files())
        methods_files = self.analysis.list_methods_files()
        self.func.fill_methods_combo(methods_files)
        # 默认选中方法文件：优先 30 算法集（用户指定默认识别），否则退回完整算法集
        if hasattr(ui, 'methods_combo') and ui.methods_combo is not None and methods_files:
            default_name = "methods_30.txt"
            if default_name not in methods_files or ui.methods_combo.findText(default_name) < 0:
                default_name = "methods_full.txt"
            if ui.methods_combo.findText(default_name) >= 0:
                ui.methods_combo.setCurrentText(default_name)
        # 绑定下拉框 / 参数控件变更信号 -> 同步到主层 Analysis
        if hasattr(ui, 'gene_file_combo') and ui.gene_file_combo is not None:
            ui.gene_file_combo.currentTextChanged.connect(self._sync_gene_file)
        if hasattr(ui, 'methods_combo') and ui.methods_combo is not None:
            ui.methods_combo.currentTextChanged.connect(self._sync_methods_file)
        # 阶段五筛选模式下拉框：同步 + 联动显隐条件输入框
        if hasattr(ui, 'filter_mode_combo') and ui.filter_mode_combo is not None:
            ui.filter_mode_combo.currentTextChanged.connect(self._on_filter_mode_changed)
        # 说明：max_genes_spin / seed_spin / filter_*_spin / auc_threshold_spin 为 StyledNumberInput（无 valueChanged 信号），
        # 其当前值在 run_stage 中实时读取同步，不做变更信号绑定（见 _sync_spin_values）。
        # 绑定 5 个阶段运行按钮
        for attr, stage in (
            ('btn_run_stage1', 'stage1'),
            ('btn_run_stage2', 'stage2'),
            ('btn_run_stage3', 'stage3'),
            ('btn_run_stage4', 'stage4'),
            ('btn_run_stage5', 'stage5'),
        ):
            if hasattr(ui, attr) and getattr(ui, attr) is not None:
                getattr(ui, attr).clicked.connect(
                    lambda _checked=False, s=stage: self.run_stage(s)
                )
        # 绑定 3 个导出按钮（需求6）
        self._bind_export_buttons()
        # 初始化筛选模式联动（默认复合模式显示全部输入框）
        self._apply_filter_mode_visibility()
        # 初始同步当前值到主层（默认值）
        self._sync_gene_file()
        self._sync_methods_file()
        self._sync_max_genes()
        self._sync_seed()
        self._sync_auc_threshold()
        self._sync_filter_params()

    # ============================================================
    # 下拉框 / 参数控件 -> 主层 Analysis 同步
    # ============================================================

    def _main_analysis_or_log(self):
        """获取主层 Analysis，失败时记录日志并返回 None"""
        main_analysis = self._get_main_analysis()
        if main_analysis is None:
            self.func.log("无法获取主层 Analysis 实例，请刷新页面")
        return main_analysis

    def _sync_gene_file(self, *_):
        """同步基因集文件下拉框选择到主层"""
        ui = self.bulk_machinelearning_diff_train_ui
        if not hasattr(ui, 'gene_file_combo') or ui.gene_file_combo is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.diff_train_gene_file = ui.gene_file_combo.currentText()

    def _sync_methods_file(self, *_):
        """同步算法组合文件下拉框选择到主层"""
        ui = self.bulk_machinelearning_diff_train_ui
        if not hasattr(ui, 'methods_combo') or ui.methods_combo is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.diff_train_methods_file = ui.methods_combo.currentText()

    def _sync_max_genes(self, *_):
        """同步高变异基因截断数到主层"""
        ui = self.bulk_machinelearning_diff_train_ui
        if not hasattr(ui, 'max_genes_spin') or ui.max_genes_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.diff_train_max_genes = ui.max_genes_spin.value()

    def _sync_seed(self, *_):
        """同步随机种子到主层"""
        ui = self.bulk_machinelearning_diff_train_ui
        if not hasattr(ui, 'seed_spin') or ui.seed_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.diff_train_seed = ui.seed_spin.value()

    def _sync_auc_threshold(self, *_):
        """同步阶段四/五 AUC 阈值筛选到主层"""
        ui = self.bulk_machinelearning_diff_train_ui
        if not hasattr(ui, 'auc_threshold_spin') or ui.auc_threshold_spin is None:
            return
        main_analysis = self._main_analysis_or_log()
        if main_analysis is not None:
            main_analysis.diff_train_auc_threshold = ui.auc_threshold_spin.value()

    # ============================================================
    # 阶段五筛选模式参数同步 + 联动
    # ============================================================

    # UI 展示名 -> R 脚本内部 mode 标识
    FILTER_MODE_MAP = {
        "复合模式": "composite",
        "基因排名 (Top N)": "gene_rank",
        "nModels 模式": "n_models",
        "AverageRank 模式": "avg_rank",
    }

    def _current_filter_mode(self):
        """获取当前筛选模式的内部标识（composite/gene_rank/n_models/avg_rank）"""
        ui = self.bulk_machinelearning_diff_train_ui
        if hasattr(ui, 'filter_mode_combo') and ui.filter_mode_combo is not None:
            text = ui.filter_mode_combo.currentText()
            return self.FILTER_MODE_MAP.get(text, "composite")
        return "composite"

    def _sync_filter_params(self, *_):
        """同步筛选模式与三个条件值到主层"""
        ui = self.bulk_machinelearning_diff_train_ui
        main_analysis = self._main_analysis_or_log()
        if main_analysis is None:
            return
        main_analysis.diff_train_filter_mode = self._current_filter_mode()
        main_analysis.diff_train_filter_top_n = ui.filter_top_n_spin.value()
        main_analysis.diff_train_filter_n_models = ui.filter_n_models_spin.value()
        main_analysis.diff_train_filter_avg_rank = ui.filter_avg_rank_spin.value()

    def _apply_filter_mode_visibility(self):
        """按当前筛选模式动态显隐三个条件输入框（及标签）

        交集阈值为通用基准（基因共识值），所有模式均显示：
        - 复合模式:    显示 TopN + 交集阈值 + 平均排名
        - 基因排名:    显示 TopN + 交集阈值
        - nModels:     仅显示 交集阈值
        - AverageRank: 显示 交集阈值 + 平均排名
        """
        ui = self.bulk_machinelearning_diff_train_ui
        mode = self._current_filter_mode()
        pairs = (
            ('filter_top_n_label', 'filter_top_n_spin'),
            ('filter_n_models_label', 'filter_n_models_spin'),
            ('filter_avg_rank_label', 'filter_avg_rank_spin'),
        )
        show_state = {'filter_top_n_label': False,
                      'filter_n_models_label': False,
                      'filter_avg_rank_label': False}
        # 交集阈值在所有模式下都作为基准显示（nModels 现为交集阈值，min=1）
        show_state['filter_n_models_label'] = True
        if mode == "composite":
            show_state['filter_top_n_label'] = True
            show_state['filter_avg_rank_label'] = True
        elif mode == "gene_rank":
            show_state['filter_top_n_label'] = True
        elif mode == "n_models":
            pass
        elif mode == "avg_rank":
            show_state['filter_avg_rank_label'] = True
        for attr, spin_attr in pairs:
            for a in (attr, spin_attr):
                if hasattr(ui, a) and getattr(ui, a) is not None:
                    getattr(ui, a).setVisible(show_state[attr])

    def _on_filter_mode_changed(self, *_):
        """筛选模式下拉框变更：同步到主层 + 联动显隐"""
        self._sync_filter_params()
        self._apply_filter_mode_visibility()
        self.func.log(f"已切换核心基因筛选模式: {self._current_filter_mode()}")

    def _validate_stage5_filter(self):
        """阶段五运行前校验：交集阈值(默认5)始终生效；TopN/AvgRank 可填0表示不限制

        Returns:
            (valid: bool, msg: str)
        """
        mode = self._current_filter_mode()
        if mode == "composite":
            ui = self.bulk_machinelearning_diff_train_ui
            top_n = ui.filter_top_n_spin.value()
            avg_r = ui.filter_avg_rank_spin.value()
            # 交集阈值(>=1)始终生效，因此必选非空；但 TopN/AvgRank 都填0时
            # 结果即整个交集池，功能仍可用，故仅做提示性校验。
            if max(top_n, avg_r) <= 0:
                return True, ""
        return True, ""

    # ============================================================
    # 导出按钮（需求6）
    # ============================================================

    def _bind_export_buttons(self):
        """绑定 3 个导出按钮到导出逻辑"""
        ui = self.bulk_machinelearning_diff_train_ui
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
        （= 第一个非空产物文件，施工前的行为，**与「导出基因列表 CSV」同一份输出文件**）。"""
        if self._is_running():
            self.func.log("任务正在运行中，请先等待完成再发送")
            return []
        return self.analysis.get_final_gene_names()

    def _collect_groups_for_send(self):
        """可选子集 `[(标签, 基因, 默认勾选), ...]`：阶段五**真实存在**的每个产物文件一组。

        宁少勿假：文件不在就不造这一层。默认勾选使得**默认并集 == 旧口径 payload**
        （即第一个非空产物文件；另一个文件若只是它的子集，勾上不改变并集，故默认勾上）。
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
        """把最终入选的特征基因发送到 `appdata/genelists`（契约 §3/§4，子集可选）。"""
        if self._is_running():
            self.func.log("[WARN] 任务正在运行中，请先等待完成再发送")
            return

        groups = [(l, g, d) for l, g, d in self._collect_groups_for_send() if g]
        defaults = [g for _l, g, d in groups if d]
        if not defaults:
            self.func.log("[WARN] 当前没有可发送的基因：请先运行阶段五（核心基因筛选）")
            show_warning(self.parent, "没有可发送的基因", "请先运行阶段五：核心基因筛选")
            return

        from script.utils_layer.gene_list_export import ask_and_send
        if len(groups) >= 2:
            r = ask_and_send(self.parent, groups=groups, multi=True, prefix="机器学习_差异特征")
        else:                                   # 只有 1 个子集 → 沿用旧口径（不弹选择区）
            r = ask_and_send(self.parent, defaults[0], prefix="机器学习_差异特征")
        if r.get("ok"):
            self.func.log("[INFO] " + str(r.get("message", "")))
            if r.get("selected_groups"):
                self.func.log("[INFO] 发送集合：" + "、".join(r["selected_groups"]))
        elif r.get("cancelled"):
            self.func.log("[INFO] 已取消发送")
        else:
            self.func.log("[WARN] " + str(r.get("message", "发送失败")))

    def _ask_save_path(self, default_name, file_filter):
        """弹出保存对话框，返回用户选择的路径；取消则返回 None"""
        from PyQt5.QtWidgets import QFileDialog
        out_dir = self.analysis.get_out_dir()
        start = os.path.join(out_dir, default_name)
        path, _ = QFileDialog.getSaveFileName(
            self.parent, "选择保存位置", start, file_filter)
        return path or None

    def _export_images(self, ext):
        """导出全部图片（png/pdf）为 zip"""
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
        """导出基因列表 csv"""
        if self._is_running():
            self.func.log("任务正在运行中，请先等待完成再导出")
            return
        save_path = self._ask_save_path("core_gene_list.csv", "CSV 文件 (*.csv)")
        if save_path is None:
            self.func.log("已取消导出")
            return
        ok, result, err = self.analysis.export_gene_list_csv(save_path=save_path)
        if ok:
            self.func.log(f"已导出基因列表 csv: {result}")
            show_info(self.parent, "导出成功", f"已导出基因列表到:\n{result}")
        else:
            self.func.log(f"导出基因列表失败: {err}")
            show_warning(self.parent, "导出失败", err)

    # ============================================================
    # 运行阶段
    # ============================================================

    def _is_running(self):
        return self.worker is not None and self.worker.isRunning()

    def _set_buttons_enabled(self, enabled):
        """统一启用/禁用所有阶段运行按钮、下拉框、参数控件与导出按钮"""
        ui = self.bulk_machinelearning_diff_train_ui
        for attr in ('gene_file_combo', 'methods_combo', 'max_genes_spin',
                     'seed_spin',
                     'filter_mode_combo', 'filter_top_n_spin',
                     'filter_n_models_spin', 'filter_avg_rank_spin',
                     'auc_threshold_spin',
                     'btn_run_stage1', 'btn_run_stage2', 'btn_run_stage3',
                     'btn_run_stage4', 'btn_run_stage5',
                     'btn_export_png', 'btn_export_pdf', 'btn_export_csv'):
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

        # 实时读取参数控件当前值并同步到主层（下拉框为变更信号，数值框为运行前读取）
        self._sync_gene_file()
        self._sync_methods_file()
        self._sync_max_genes()
        self._sync_seed()
        self._sync_auc_threshold()
        self._sync_filter_params()

        # 阶段五：复合模式校验（至少一个筛选条件非 0）
        if stage == "stage5":
            valid, msg = self._validate_stage5_filter()
            if not valid:
                self.func.log("阶段五未通过筛选参数校验")
                show_warning(self.parent, "参数不完整", msg)
                return

        stage_names = {
            "stage1": "阶段一：数据准备",
            "stage2": "阶段二：单模型",
            "stage3": "阶段三：批量建模",
            "stage4": "阶段四：AUC+热图",
            "stage5": "阶段五：核心基因筛选",
        }
        self.func.log(f"开始运行 {stage_names[stage]}...")
        self._set_buttons_enabled(False)
        self.func.set_progress(None, visible=True)

        self.worker = TrainStageWorker(self.analysis, main_analysis, stage)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_stage_finished)
        self.worker.start()

    def _on_progress(self, stage, message):
        """处理进度消息"""
        self.func.log(message)

    def _on_stage_finished(self, stage, success, results, error):
        """阶段运行完成回调"""
        stage_names = {
            "stage1": "阶段一：数据准备",
            "stage2": "阶段二：单模型",
            "stage3": "阶段三：批量建模",
            "stage4": "阶段四：AUC+热图",
            "stage5": "阶段五：核心基因筛选",
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
        """根据输出目录刷新对应标签页图片/文本"""
        ui = self.bulk_machinelearning_diff_train_ui
        out_dir = self.analysis.get_out_dir()

        if stage == "stage1":
            # 展示阶段一数据概要（确认已读取 loading 产物）
            txt_path = os.path.join(out_dir, "train_ready.txt")
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, encoding='utf-8', errors='replace') as f:
                        content = f.read()
                except Exception:
                    content = ""
                te = getattr(ui, 'stage1_data_text', None)
                if te is not None and content:
                    te.setPlainText("训练数据概要（已读取 loading 产物）:\n\n" + content)
                    self.func.log("阶段一数据概要已写入「阶段一：数据概要」标签页")
        elif stage == "stage2":
            file_map = [
                ('lasso_cv_label', 'lasso_cv_fit.png'),
                ('lasso_roc_label', 'lasso_roc.png'),
                ('rf_importance_label', 'rf_varImp.png'),
                ('rf_roc_label', 'rf_roc.png'),
                ('svm_roc_label', 'svm_roc.png'),
            ]
            for attr, fname in file_map:
                label = getattr(ui, attr, None)
                if label is not None:
                    self.func.set_image(label, os.path.join(out_dir, fname))
        elif stage == "stage4":
            # 展示 AUC 热图 PNG（由 Plot.Class.Heatmap 复刻参考脚本生成）
            png_path = os.path.join(out_dir, "Classification_AUC.png")
            label = getattr(ui, 'auc_heatmap_label', None)
            if label is not None:
                self.func.set_image(label, png_path)
            pdf_path = os.path.join(out_dir, "Classification_AUC.pdf")
            self.func.log(f"AUC 热图输出: {png_path} (PDF: {pdf_path})")
        elif stage == "stage5":
            oname = 'core_genes_image_label'
            imname = 'core_genes_top10_intersection.png'
            label = getattr(ui, oname, None)
            if label is not None:
                self.func.set_image(label, os.path.join(out_dir, imname))
            # 刷新基因列表表格（需求4/5：表格形式显示全部基因）
            all_txt = os.path.join(out_dir, "gene_all_list.txt")
            self.func.fill_gene_table(ui.core_genes_table, all_txt)
            filtered_txt = os.path.join(out_dir, "gene_filtered_result.txt")
            if os.path.exists(filtered_txt):
                self.func.log("阶段五筛选结果已保存 -> gene_filtered_result.txt")
                self.func.log(f"核心基因图输出: {os.path.join(out_dir, imname)}")

    # ============================================================
    # 主层透传入口
    # ============================================================

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        """从 bulk 主页同步数据（由主层容器透传调用，预留）"""
        pass
