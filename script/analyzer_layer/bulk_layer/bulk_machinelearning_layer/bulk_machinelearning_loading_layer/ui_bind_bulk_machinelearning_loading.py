# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 数据加载类子层功能绑定脚本

职责：
1. 绑定「扫描数据集」「加载并运行PCA」「运行阶段二：ComBat去批次」按钮信号
2. 编排 analysis 与 func 的协作
3. 从主层 Bind 获取/创建主层 Analysis 实例（共享数据容器）
4. 使用 QThread 后台运行 PCA 与 ComBat 去批次，避免阻塞 UI，通过进度条显示运行状态
"""

from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_loading_layer.bulk_machinelearning_loading_analysis import BulkMachineLearningLoadingAnalysis
from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_loading_layer.ui_func_bulk_machinelearning_loading import BulkMachineLearningLoadingFunc
from script.utils_layer.import_config import os, OUT_BASE
from script.utils_layer.emoji_trigger import show_info, show_error, show_warning
from PyQt5.QtCore import QThread, pyqtSignal


class PcaWorker(QThread):
    """PCA 后台运行线程

    信号:
        progress(method, message): 进度消息
        finished_signal(success, results, error): 完成信号
    """
    progress = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, analysis, main_analysis):
        super().__init__()
        self.analysis = analysis
        self.main_analysis = main_analysis

    def run(self):
        try:
            success, results, error = self.analysis.run_pca_analysis(
                self.main_analysis,
                progress_callback=lambda m, msg: self.progress.emit(m, msg)
            )
            self.finished_signal.emit(success, results, error)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_signal.emit(False, {}, str(e))


class ComBatWorker(QThread):
    """ComBat 去批次后台运行线程（阶段二）

    信号:
        progress(method, message): 进度消息
        finished_signal(success, results, error): 完成信号
    """
    progress = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, analysis, main_analysis, preprocessing_method):
        super().__init__()
        self.analysis = analysis
        self.main_analysis = main_analysis
        self.preprocessing_method = preprocessing_method

    def run(self):
        try:
            success, results, error = self.analysis.run_stage2_combat(
                self.main_analysis,
                preprocessing_method=self.preprocessing_method,
                progress_callback=lambda m, msg: self.progress.emit(m, msg)
            )
            self.finished_signal.emit(success, results, error)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_signal.emit(False, {}, str(e))


class BulkMachineLearningLoadingBind:
    """机器学习数据加载类绑定类"""

    # PCA 方法 -> UI 图片标签属性名 映射
    METHOD_TO_LABEL_ATTR = {
        'raw': 'raw_image_label',
        'log2': 'log2_image_label',
        'log2_scaled': 'log2_scaled_image_label',
        'scaled': 'scaled_image_label',
    }

    def __init__(self, main_window, bulk_machinelearning_loading_ui):
        self.parent = main_window
        self.main_window = main_window
        self.bulk_machinelearning_loading_ui = bulk_machinelearning_loading_ui
        self.analysis = BulkMachineLearningLoadingAnalysis()
        self.func = BulkMachineLearningLoadingFunc(bulk_machinelearning_loading_ui)
        # 主层 Analysis 实例（从主层 Bind 获取，懒加载）
        self.main_analysis = None
        # PCA 后台线程引用
        self.pca_worker = None
        # ComBat 后台线程引用（阶段二）
        self.combat_worker = None
        self.bind_signals()

    def bind_signals(self):
        ui = self.bulk_machinelearning_loading_ui
        if hasattr(ui, 'btn_scan_datasets') and ui.btn_scan_datasets is not None:
            ui.btn_scan_datasets.clicked.connect(self.scan_datasets)
        if hasattr(ui, 'btn_load_and_run') and ui.btn_load_and_run is not None:
            ui.btn_load_and_run.clicked.connect(self.load_and_run_pca)
        if hasattr(ui, 'btn_run_combat') and ui.btn_run_combat is not None:
            ui.btn_run_combat.clicked.connect(self.run_stage2_combat)
        if hasattr(ui, 'btn_run_clinical_sync') and ui.btn_run_clinical_sync is not None:
            ui.btn_run_clinical_sync.clicked.connect(self.run_stage3_clinical_sync)

    # ============================================================
    # 主层 Analysis 实例获取（懒加载）
    # ============================================================

    def _get_main_analysis(self):
        """获取主层 Analysis 实例

        主层 Bind（BulkMachineLearningBind）目前可能没有 analysis 属性，
        本方法负责：先尝试获取，没有则创建并赋值给主层 Bind。
        """
        if self.main_analysis is not None:
            return self.main_analysis

        main_bind = getattr(self.main_window, 'bulk_machinelearning_bind', None)
        if main_bind is not None and hasattr(main_bind, 'analysis') and main_bind.analysis is not None:
            self.main_analysis = main_bind.analysis
            return self.main_analysis

        # 主层 Bind 没有 analysis，创建一个并赋值给主层 Bind
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
    # 业务槽函数
    # ============================================================

    def scan_datasets(self):
        """扫描数据集"""
        self.func.log("开始扫描数据集...")
        success, files, error = self.analysis.scan_datasets()
        if not success:
            self.func.log(f"扫描失败: {error}")
            show_error(self.parent, "错误", f"扫描失败:\n{error}")
            return
        self.func.log(f"扫描成功，找到 {len(files)} 个 h5ad 文件")
        self.func.set_dataset_list(files, keep_selection=True)
        show_info(self.parent, "成功", f"扫描成功，找到 {len(files)} 个 h5ad 文件")

    def load_and_run_pca(self):
        """加载数据并运行 PCA（后台线程执行，避免阻塞 UI）"""
        # 防止重复运行
        if self._is_running():
            self.func.log("任务正在运行中，请稍候...")
            return

        selected = self.func.get_selected_datasets()
        if not selected:
            self.func.log("请先选择至少一个数据集")
            return
        if not self.analysis.is_r_available():
            self.func.log("R 环境不可用，请检查 R 内核配置")
            return

        main_analysis = self._get_main_analysis()
        if main_analysis is None:
            self.func.log("无法获取主层 Analysis 实例")
            return

        # 1. 加载并合并数据（主线程执行，速度较快）
        self.func.log(f"正在加载 {len(selected)} 个数据集...")
        self.func.set_progress(None, visible=True)  # 不确定模式
        success, info, error = self.analysis.load_and_merge_datasets(selected, main_analysis)
        if not success:
            self.func.log(f"加载失败: {error}")
            self.func.set_progress(0, visible=False)
            show_error(self.parent, "错误", f"加载数据集失败:\n{error}")
            return
        self.func.log(
            f"合并完成: {info['samples']}样本, {info['genes']}基因(交集), "
            f"数据集: {', '.join(info['datasets'])}"
        )

        # 2. 禁用运行按钮，后台运行 PCA
        self._set_buttons_enabled(False)
        self.func.log("正在运行 PCA 分析...")
        self.func.set_progress(None, visible=True)  # 不确定模式（忙碌指示器）

        # 创建后台线程
        self.pca_worker = PcaWorker(self.analysis, main_analysis)
        self.pca_worker.progress.connect(self._on_pca_progress)
        self.pca_worker.finished_signal.connect(self._on_pca_finished)
        self.pca_worker.start()

    def _on_pca_progress(self, method, message):
        """PCA 运行进度回调"""
        self.func.log(f"[{method}] {message}")

    def _on_pca_finished(self, success, results, error):
        """PCA 运行完成回调"""
        # 恢复运行按钮
        self._set_buttons_enabled(True)

        if not success:
            self.func.log(f"PCA 分析失败: {error}")
            self.func.set_progress(0, visible=False)
            show_error(self.parent, "错误", f"PCA 分析失败:\n{error}")
            return

        # 显示图片到对应标签页
        ui = self.bulk_machinelearning_loading_ui
        for method, label_attr in self.METHOD_TO_LABEL_ATTR.items():
            if method in results and hasattr(ui, label_attr):
                self.func.set_image(getattr(ui, label_attr), results[method]['plot_path'])
        self.func.log("PCA 分析完成！")
        self.func.set_progress(100, visible=False)
        show_info(self.parent, "成功", "PCA 分析完成！")

    # ============================================================
    # 阶段二：ComBat 去批次 + 去批次后 PCA
    # ============================================================

    def run_stage2_combat(self):
        """运行阶段二：ComBat 去批次 + 去批次后 PCA（后台线程执行）"""
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

        # 检查合并数据是否已就绪
        merged_dir = getattr(main_analysis, 'merged_output_dir', None) or os.path.join(
            OUT_BASE, self.analysis.MERGED_DIR_NAME
        )
        expr_path = os.path.join(merged_dir, self.analysis.EXPR_FILE_NAME)
        if not os.path.exists(expr_path):
            self.func.log("合并数据不存在，请先加载数据集并运行 PCA")
            return

        # 获取选中的预处理方法
        preprocessing = self.func.get_preprocessing_method()
        self.func.log(f"阶段二开始（ComBat 去批次，预处理: {preprocessing}）...")
        self.func.set_progress(None, visible=True)

        # 禁用按钮
        self._set_buttons_enabled(False)

        # 创建后台线程
        self.combat_worker = ComBatWorker(self.analysis, main_analysis, preprocessing)
        self.combat_worker.progress.connect(self._on_combat_progress)
        self.combat_worker.finished_signal.connect(self._on_combat_finished)
        self.combat_worker.start()

    def _on_combat_progress(self, method, message):
        """ComBat 运行进度回调"""
        self.func.log(f"[{method}] {message}")

    def _on_combat_finished(self, success, result, error):
        """ComBat 运行完成回调"""
        self._set_buttons_enabled(True)

        if not success:
            self.func.log(f"阶段二失败: {error}")
            self.func.set_progress(0, visible=False)
            show_error(self.parent, "错误", f"阶段二 ComBat 去批次失败:\n{error}")
            return

        ui = self.bulk_machinelearning_loading_ui
        if hasattr(ui, 'combat_image_label'):
            self.func.set_image(ui.combat_image_label, result.get('plot_path', ''))
            # 自动跳转到「去批次后PCA」标签页
            if hasattr(ui, 'tab_widget') and ui.tab_widget is not None:
                combat_tab_idx = ui.tab_widget.indexOf(ui.combat_image_label.parentWidget())
                if combat_tab_idx >= 0:
                    ui.tab_widget.setCurrentIndex(combat_tab_idx)
        self.func.log("阶段二完成！去批次后表达矩阵已保存到 loading 目录。")
        self.func.set_progress(100, visible=False)
        show_info(self.parent, "成功", "阶段二完成！去批次后表达矩阵已保存到 loading 目录。")

    # ============================================================
    # 通用辅助
    # ============================================================

    def _is_running(self):
        """检查是否有任务正在运行（PCA 或 ComBat）"""
        if self.pca_worker is not None and self.pca_worker.isRunning():
            return True
        if self.combat_worker is not None and self.combat_worker.isRunning():
            return True
        return False

    def _set_buttons_enabled(self, enabled):
        """统一启用/禁用所有运行按钮"""
        ui = self.bulk_machinelearning_loading_ui
        for attr in ('btn_scan_datasets', 'btn_load_and_run', 'btn_run_combat', 'btn_run_clinical_sync'):
            if hasattr(ui, attr) and getattr(ui, attr) is not None:
                getattr(ui, attr).setEnabled(enabled)

    # ============================================================
    # 阶段三：同步临床信息
    # ============================================================

    def run_stage3_clinical_sync(self):
        """运行阶段三：同步临床信息（弹窗向导，主线程交互）"""
        if self._is_running():
            self.func.log("任务正在运行中，请稍候...")
            return

        main_analysis = self._get_main_analysis()
        if main_analysis is None:
            self.func.log("无法获取主层 Analysis 实例")
            return

        # 检查合并数据是否已就绪（阶段一必须已完成）
        if not getattr(main_analysis, 'is_data_loaded', lambda: False)():
            self.func.log("请先加载数据集并运行阶段一")
            return

        # 获取已加载的数据集文件列表
        dataset_names = getattr(main_analysis, 'dataset_names', [])
        if not dataset_names:
            self.func.log("未找到已加载的数据集列表")
            return

        # 从数据集名还原文件名
        import os as _os
        from script.utils_layer.import_config import BULK_SCAN_DATA_PATH
        selected_files = []
        for name in dataset_names:
            for fname in _os.listdir(BULK_SCAN_DATA_PATH):
                if fname.endswith('.h5ad') and _os.path.splitext(fname)[0] == name:
                    selected_files.append(fname)
                    break
        if not selected_files:
            self.func.log("无法从数据集名还原 h5ad 文件列表")
            return

        # 1. 读取每个数据集的 obs
        self.func.log("正在读取临床信息...")
        success, dataset_obs_dict, error = self.analysis.load_dataset_obs(selected_files)
        if not success:
            self.func.log(f"读取临床信息失败: {error}")
            show_error(self.parent, "错误", f"读取临床信息失败:\n{error}")
            return
        self.func.log(f"已读取 {len(dataset_obs_dict)} 个数据集的临床信息")

        # 2. 弹出向导弹窗
        from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_loading_layer.bulk_machinelearning_loading_clinical_dialog import ClinicalSyncDialog
        dialog = ClinicalSyncDialog(self.main_window, dataset_obs_dict)
        dialog.exec_()
        result = dialog.get_result()

        if result is None:
            self.func.log("阶段三已取消")
            show_warning(self.parent, "注意", "阶段三已取消")
            return

        # 3. 根据向导结果构建组合临床信息
        self.func.log("正在构建组合临床信息...")
        success, clinical_df, error = self.analysis.build_clinical_df(result, main_analysis)
        if not success:
            self.func.log(f"构建临床信息失败: {error}")
            show_error(self.parent, "错误", f"构建临床信息失败:\n{error}")
            return

        column_name = result['column_name']
        synced_col_name = f"{column_name}_synced"
        group_names = {'group1': result['group1_name'], 'group2': result['group2_name']}
        self.func.log(
            f"组合临床信息构建完成: {len(clinical_df)} 样本, "
            f"组别1({group_names['group1']}) / 组别2({group_names['group2']})"
        )

        # 4. 保存为 txt
        success, file_path, error = self.analysis.save_clinical_txt(clinical_df, synced_col_name, main_analysis)
        if not success:
            self.func.log(f"保存临床信息失败: {error}")
            show_error(self.parent, "错误", f"保存临床信息失败:\n{error}")
            return
        self.func.log(f"临床信息已保存: {file_path}")

        # 5. 存储到 main_analysis
        if hasattr(main_analysis, 'set_clinical_data'):
            main_analysis.set_clinical_data(clinical_df, synced_col_name, group_names)

        # 6. 更新表格标签页
        self.func.set_clinical_table(clinical_df)

        # 7. 自动跳转到「同步临床信息」标签页
        ui = self.bulk_machinelearning_loading_ui
        if hasattr(ui, 'tab_widget') and ui.tab_widget is not None and hasattr(ui, 'clinical_table'):
            clinical_tab_idx = ui.tab_widget.indexOf(ui.clinical_table.parentWidget())
            if clinical_tab_idx >= 0:
                ui.tab_widget.setCurrentIndex(clinical_tab_idx)

        self.func.log("阶段三完成！")
        show_info(self.parent, "成功", f"阶段三完成！\n临床信息已保存: {file_path}")

    # ============================================================
    # 主层透传入口
    # ============================================================

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        """从 bulk 主页同步数据（预留，由主层容器透传调用）"""
        pass
