# -*- coding: utf-8 -*-
"""
scRNAseq 虚拟敲除分析界面功能绑定脚本 - 负责粘合内外，绑定信号，编排analysis与func的协作

归属 W2。职责（说明书 §3.1 / §4.2.3）：
  1) 信号连接与联动（分组列 → 组别；筛选列 → 筛选值；基因来源模式 → 显隐/内存预估）；
  2) `collect_params()` 唯一取值出口（键名逐字照 `_d_spec_virtual_knockout.md` §3 / 说明书 §6）；
  3) `validate(params)` 只判「不拿数据就能判」的条目（说明书 §8.8）；
  4) `on_run_clicked()` 走 QThread 调 `analysis.run()`，回主线程填表/出图/刷日志；
  5) `sync_data_from_single_cell_main()` 取 Seurat `.rds` 路径与 meta.data 列/值（不需要 rpy2）；
  6) `on_page_entered()` 是 page_intersect 每次跳转都会调的回调（page_intersect.py:690）。

⛔ 本文件不建控件、不拼 R 命令（那是 layout 与 analysis 的事）。
"""

import inspect
import os
import time
import traceback

import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal, QObject

from script.utils_layer.page_intersect import page_intersect
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gene_list_export import ask_and_send, normalize_groups
from script.analyzer_layer.scRNAseq_layer.virtual_knockout_layer.virtual_knockout_analysis import VirtualKnockoutAnalysis
from script.analyzer_layer.scRNAseq_layer.virtual_knockout_layer.ui_func_virtual_knockout import VirtualKnockoutFunc


class VirtualKnockoutWorker(QObject):
    """虚拟敲除后台执行 Worker（在 QThread 中跑 analysis.run，照抄 monocle genelists 的 Worker 模式）

    线程里**只调 analysis**（不碰任何控件）：结果与错误都通过信号回主线程。
    """
    finished = pyqtSignal(bool, object)   # (success, 返回体或错误串)
    progress = pyqtSignal(str)            # 逐行进度 / 日志

    def __init__(self, analysis, params):
        super().__init__()
        self.analysis = analysis
        self.params = params
        self._running = True

    def stop(self):
        """请求停止（置位后进度回调不再转发）"""
        self._running = False

    def run(self):
        try:
            self.progress.emit("开始运行虚拟敲除（scTenifoldKnk）…")
            # 冻结签名：run(params, progress_callback=None) -> (bool, str)
            # 先探一次签名：避免 analysis 内部抛 TypeError 时被误判成「签名不符」而**跑第二遍 R**
            accepts_callback = True
            try:
                sig = inspect.signature(self.analysis.run)
                accepts_callback = 'progress_callback' in sig.parameters
            except (TypeError, ValueError):
                traceback.print_exc()
                accepts_callback = True

            if accepts_callback:
                success, result = self.analysis.run(
                    self.params, progress_callback=self._on_progress)
            else:
                self.progress.emit("⚠ analysis.run 未声明 progress_callback，按无进度回调调用")
                success, result = self.analysis.run(self.params)

            if success:
                self.progress.emit("虚拟敲除运行结束，正在整理结果…")
                self.finished.emit(True, result)
            else:
                self.progress.emit(f"虚拟敲除失败: {result}")
                self.finished.emit(False, result)
        except Exception as e:
            err_msg = f"虚拟敲除执行异常: {e}\n{traceback.format_exc()}"
            traceback.print_exc()
            try:
                self.progress.emit(err_msg)
            except Exception:
                traceback.print_exc()
            self.finished.emit(False, err_msg)
        finally:
            self._running = False

    def _on_progress(self, msg):
        """analysis 的 subprocess 进度回调（在工作线程里被调用）"""
        if not self._running:
            return
        try:
            self.progress.emit("" if msg is None else str(msg))
        except Exception:
            traceback.print_exc()


class VirtualKnockoutBind:
    """虚拟敲除功能绑定"""

    # ★ collect_params() 的完整键名（逐字照说明书 §6 参数总表 + 三个不暴露的固定参数）
    PARAM_KEYS = (
        'group_col', 'group_values',
        'filter1_col', 'filter1_values', 'filter2_col', 'filter2_values',
        'gene_mode', 'n_top_genes', 'gene_list_file', 'drop_mt', 'drop_ribo',
        'gko',
        'qc', 'qc_min_lib_size', 'qc_min_pct', 'qc_max_mt_ratio', 'qc_remove_outlier',
        'n_net', 'n_cells', 'n_comp', 'q',
        'scale_scores', 'symmetric', 'lambda',
        'td_k', 'td_max_iter', 'td_max_error', 'td_n_decimal', 'ma_ndim',
        'exclude_gko', 'fdr', 'empirical_null',
        'seed', 'n_cores',
        'out_dir', 'rds_path', 'dataset_name',
    )

    # 基因列表下拉里的「占位符」：布局可能写成字面量而非空串（W1 现状：「（不使用）」）
    GENE_LIST_PLACEHOLDERS = ('', '（不使用）', '(不使用)', '不使用',
                              '（未选择）', '(未选择)', '未选择', 'None', 'none')

    def __init__(self, main_window, virtual_knockout_ui):
        self.main_window = main_window
        self.parent = main_window          # 供音乐控制器修复函数取主窗口（本仓既有约定）
        #: 弹窗父控件（契约 §1：`ask_and_send(self.parent_widget, genes, prefix=...)`）
        self.parent_widget = main_window
        self.virtual_knockout_ui = virtual_knockout_ui
        self.analysis = VirtualKnockoutAnalysis()
        self.func = VirtualKnockoutFunc(virtual_knockout_ui, main_window)
        self._worker = None
        self._thread = None
        #: 最近一次运行的**显著基因表**（结果区「显著基因」页签填的同一份内存 DataFrame）
        self._last_sig_df = None
        # 已同步到的数据（Seurat .rds 绝对路径 / 数据集名 / meta.data 列与值）
        self._synced_rds_path = None
        self._synced_dataset_name = None
        self._meta_columns = []
        self._meta_values = {}
        self._run_start_time = None
        self.bind_signals()

        # 绑定音乐控制器（按项目规则，确保全局同步函数能发现）
        try:
            music_controller = getattr(virtual_knockout_ui, 'music_controller', None)
            if music_controller is not None:
                fix_music_controller_bindings(self, music_controller)
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 音乐控制器绑定失败: {traceback.format_exc()}")

    def set_volume(self, value):
        """设置音量（供 fix_music_controller_bindings 绑定音量滑块）"""
        try:
            from script.mods_layer.mod_manager import global_mod_manager
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_music_player'):
                mod_instance.global_music_player.set_volume(value / 100.0)
            if hasattr(self.main_window, '_sync_all_volume_sliders_from_subinterface'):
                self.main_window._sync_all_volume_sliders_from_subinterface(value)
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 设置音量失败: {traceback.format_exc()}")

    # ================= 信号绑定 =================

    def bind_signals(self):
        """绑定全部联动（等价于 bind_signals 的完整清单）"""
        self.bind_navigation()
        self.bind_cell_selection()
        self.bind_gene_selection()
        self.bind_run()
        self.bind_send_to_genelist()

    def bind_send_to_genelist(self):
        """「发送到列表文件夹」按钮（契约 §4.2：连接只在 bind 层）"""
        btn = getattr(self.virtual_knockout_ui, 'vk_btn_send_to_genelist', None)
        if btn is not None:
            btn.clicked.connect(self.on_send_to_genelist)

    def bind_navigation(self):
        """「← 返回上一页」→ scRNAseq_top_page"""
        ui = self.virtual_knockout_ui
        btn_back = getattr(ui, 'btn_back_virtual_knockout', None)
        if btn_back is not None:
            btn_back.clicked.connect(self.handle_back)

    def handle_back(self):
        """返回单细胞主页"""
        page_intersect.go_to_page_with_bind('scRNAseq_top_page')

    def bind_cell_selection(self):
        """分组列 + 两个筛选列的联动（照抄 diff 的 bind 侧）"""
        ui = self.virtual_knockout_ui

        group_combo = getattr(ui, 'vk_group_combo', None)
        if group_combo is not None:
            group_combo.currentIndexChanged.connect(self.on_group_changed)

        filter1_col = getattr(ui, 'vk_filter1_col', None)
        if filter1_col is not None:
            filter1_col.currentIndexChanged.connect(self.on_filter1_col_changed)

        filter2_col = getattr(ui, 'vk_filter2_col', None)
        if filter2_col is not None:
            filter2_col.currentIndexChanged.connect(self.on_filter2_col_changed)

    def bind_gene_selection(self):
        """基因来源模式联动 + 基因列表文件变化时更新路径 label"""
        ui = self.virtual_knockout_ui

        mode_combo = getattr(ui, 'vk_gene_mode_combo', None)
        if mode_combo is not None:
            mode_combo.currentIndexChanged.connect(self.on_gene_mode_changed)

        gene_list_combo = getattr(ui, 'vk_gene_list_combo', None)
        if gene_list_combo is not None:
            gene_list_combo.currentIndexChanged.connect(self.on_gene_list_changed)

        hvg_spin = getattr(ui, 'vk_hvg_n_spin', None)
        if hvg_spin is not None and hasattr(hvg_spin, 'valueChanged'):
            # ★ StyledNumberInput 没有 valueChanged，这里必须先 hasattr 判定
            hvg_spin.valueChanged.connect(self.on_hvg_n_changed)

    def bind_run(self):
        """运行按钮"""
        ui = self.virtual_knockout_ui
        btn_run = getattr(ui, 'vk_btn_run', None)
        if btn_run is not None:
            btn_run.clicked.connect(self.on_run_clicked)

    # ================= 联动槽 =================

    def on_group_changed(self):
        """分组列变 ⇒ 重填「组别（多选）」列表（默认全选）"""
        try:
            column = self._current_text('vk_group_combo')
            if not column:
                self.func.fill_group_values([])
                return
            values = self._get_column_values(column)
            self.func.fill_group_values(values)
            self.func.log(f"分组列切换为「{column}」，组别 {len(values)} 个（默认全选）")
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 分组列联动失败: {traceback.format_exc()}")

    def on_filter1_col_changed(self, *_ignored):
        """筛选条件1列变 ⇒ 重填该筛选的值列表（不选 = 该筛选不生效）

        ★ 与 `bind_signals` 里 connect 的方法名**逐字一致**（签收 2026-09-25 修：
        此前只有 `on_filter_col_changed`，导致构造期 AttributeError）。
        """
        try:
            column = self._current_text('vk_filter1_col')
            if not column:
                self.func.fill_filter_values(self._get_widget('vk_filter1_list'), [])
                return
            values = self._get_column_values(column)
            self.func.fill_filter_values(self._get_widget('vk_filter1_list'), values)
            self.func.log(f"筛选条件1 列切换为「{column}」，可选值 {len(values)} 个")
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 筛选条件1 联动失败: {traceback.format_exc()}")

    def on_filter2_col_changed(self, *_ignored):
        """筛选条件2 列变 ⇒ 重填值列表"""
        try:
            column = self._current_text('vk_filter2_col')
            if not column:
                self.func.fill_filter_values(self._get_widget('vk_filter2_list'), [])
                return
            values = self._get_column_values(column)
            self.func.fill_filter_values(self._get_widget('vk_filter2_list'), values)
            self.func.log(f"筛选条件2 列切换为「{column}」，可选值 {len(values)} 个")
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 筛选条件2 联动失败: {traceback.format_exc()}")

    def on_filter_col_changed(self, index=None):
        """筛选条件1 列变的旧名入口（兼容历史调用，内部转发到 on_filter1_col_changed）"""
        self.on_filter1_col_changed(index)

    def on_gene_mode_changed(self):
        """基因来源模式变 ⇒ 显隐（说明书 §5.2 联动 1/2/3）+ 刷新内存预估（联动 4）"""
        try:
            mode = self._current_data('vk_gene_mode_combo') or 'hvg'
            self.func.apply_gene_mode_visibility(mode)
            self.refresh_memory_estimate()
            mode_text = {'hvg': '高变基因前 N', 'all': '全部基因',
                         'list': '外部基因列表'}.get(mode, str(mode))
            self.func.log(f"基因来源模式：{mode_text}")
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 基因来源模式联动失败: {traceback.format_exc()}")

    def on_gene_list_changed(self, index=None):
        """基因列表文件下拉变化 ⇒ 更新路径 label（空/占位符 = 不使用外部列表）"""
        try:
            name = self._gene_list_name()
            label = self._get_widget('vk_gene_list_path_label')
            if label is not None:
                if name:
                    label.setText(os.path.join(self.func.get_gene_lists_dir(), name))
                else:
                    label.setText("（未选择，运行时按高变基因兜底）")
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 基因列表路径回显失败: {traceback.format_exc()}")

    def _gene_list_name(self):
        """取基因列表文件名（唯一取用口径）

        - 布局写的占位符（如「（不使用）」）一律当**空串**：绝不拿它去 genelists 目录找文件；
        - 万一布局给的是一整条绝对路径，只取 basename。
        """
        text = self._current_text('vk_gene_list_combo')
        if text in self.GENE_LIST_PLACEHOLDERS:
            return ""
        if text and (os.sep in text or '/' in text):
            return os.path.basename(text)
        return text

    def on_hvg_n_changed(self, value=None):
        """HVG 的 N 变化 ⇒ 刷新内存预估"""
        try:
            self.refresh_memory_estimate()
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 内存预估刷新失败: {traceback.format_exc()}")

    def refresh_memory_estimate(self):
        """按当前模式估算基因面板规模并回显（说明书 §5.2 联动 4 / §11）

        模型：内存 ≈ 0.5 GB × (基因数/1000)²（说明书 §11 甲方实测：
        1000 基因 ≈ 0.5 GB、5000 基因 ≈ 8.6 GB、10000 基因 ≈ 34 GB）。
        """
        try:
            mode = self._current_data('vk_gene_mode_combo') or 'hvg'
            n_genes = self._current_number('vk_hvg_n_spin', default=1000)
            n_genes = int(n_genes) if n_genes else 0
            if mode == 'hvg':
                text = (f"预估内存：约 {self._estimate_memory_gb(n_genes):.1f} GB"
                        f"（面板约 {n_genes} 基因）")
            elif mode == 'all':
                text = ("预估内存：全部基因——内存按基因数平方增长，"
                        "5000 基因约 8.6 GB、10000 基因约 34 GB（运行前会弹确认框）")
            else:
                text = "预估内存：外部基因列表——按列表实际基因数在运行前弹确认框"
            self.func.set_memory_estimate(text)
        except Exception:
            traceback.print_exc()

    # ================= 数据同步 =================

    def sync_data_from_single_cell_main(self, sc_top_bind=None):
        """从 scRNAseq 主页同步数据（page_intersect 的 sync_method 入口）

        照抄 `ui_bind_sc_hdwgcna.py:147-166`：直接用 scRNAseq 主页 analysis 上的
        字段，**不需要 rpy2**：
          - `seurat_path`：Seurat `.rds` 绝对路径（→ `--rds`）；
          - `dataset_name`：数据集名；
          - `dataset_output_dir`：输出目录基；
          - `seurat_metadata_columns`：meta.data 列名 list；
          - `seurat_metadata_values`：`{列名: [值, ...]}`。
        """
        if sc_top_bind is None:
            sc_top_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
        if sc_top_bind is None or not getattr(sc_top_bind, 'analysis', None):
            self.func.log("⚠ 未取得单细胞主页分析对象，暂不能同步数据")
            return

        try:
            src = sc_top_bind.analysis
            rds_path = getattr(src, 'seurat_path', None)
            dataset_name = getattr(src, 'dataset_name', None)
            dataset_output_dir = getattr(src, 'dataset_output_dir', None)
            meta_columns = list(getattr(src, 'seurat_metadata_columns', None) or [])
            meta_values = getattr(src, 'seurat_metadata_values', None) or {}

            self._synced_rds_path = rds_path
            self._synced_dataset_name = dataset_name
            self._meta_columns = meta_columns
            self._meta_values = dict(meta_values)

            # 交给 analysis（W3 的冻结方法名是 set_data_source；兼容分项 setter）
            if hasattr(self.analysis, 'set_data_source'):
                self.analysis.set_data_source(rds_path, dataset_name)
            else:
                if hasattr(self.analysis, 'set_seurat_path'):
                    self.analysis.set_seurat_path(rds_path)
                if hasattr(self.analysis, 'set_dataset_name'):
                    self.analysis.set_dataset_name(dataset_name)
                if hasattr(self.analysis, 'set_dataset_output_dir'):
                    self.analysis.set_dataset_output_dir(dataset_output_dir)

            if rds_path:
                self.func.log(f"✓ 已从单细胞主页同步数据：{dataset_name}")
                self.func.log(f"  Seurat rds：{rds_path}")
                self.func.log(f"  meta.data 列：{len(meta_columns)} 个")
            else:
                self.func.log("⚠ 单细胞主页尚未加载 Seurat 数据（seurat_path 为空）")
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 同步单细胞数据失败: {traceback.format_exc()}")

    def _refresh_group_columns(self):
        """刷新分组列下拉 + 组别列表（说明书 §12.3-2），并预载 meta 值缓存"""
        columns = []
        try:
            columns = list(self.analysis.get_meta_columns() or [])
        except Exception:
            traceback.print_exc()
            self.func.log("⚠ 取 meta.data 列失败，改用同步缓存")
        if not columns:
            columns = list(self._meta_columns or [])

        preferred = None
        try:
            preferred = getattr(self.analysis, 'DEFAULT_GROUPS', None)
            preferred = preferred[0] if preferred else None
        except Exception:
            traceback.print_exc()
            preferred = None
        if preferred is None:
            preferred = 'Celltype (major-lineage)'

        self.func.fill_group_columns(columns, preferred)

        group_col = self._current_text('vk_group_combo')
        if group_col:
            self.func.fill_group_values(self._get_column_values(group_col))

        for name in ('vk_filter1_col', 'vk_filter2_col'):
            combo = self._get_widget(name)
            if combo is not None:
                self.func.set_combo_items(combo, [''] + columns, keep_selection=True)

        self.on_filter1_col_changed()
        self.on_filter2_col_changed()

    def on_page_entered(self):
        """每次跳转进本页时由 page_intersect 调用（page_intersect.py:690）

        - 已同步到数据 ⇒ 刷新分组列下拉、组别列表与基因列表下拉（说明书 §12.3-2）；
        - 没有数据 ⇒ **只留痕不抛**（不弹窗、不打断跳转）。
        """
        try:
            self.func.log("—" * 30)
            self.func.log("进入「虚拟敲除」页面")

            # 基因列表下拉：与数据无关，恒刷新
            files = self.func.fill_gene_lists()
            self.on_gene_list_changed()
            self.func.apply_gene_mode_visibility(
                self._current_data('vk_gene_mode_combo') or 'hvg')
            self.refresh_memory_estimate()

            has_data = bool(self._synced_rds_path) or self._has_analysis_data()
            if has_data:
                self._refresh_group_columns()
                self.func.log(f"✓ 已按当前数据刷新分组列与基因列表（{len(files)} 个基因列表文件）")
            else:
                self.func.log("⚠ 尚未同步到 Seurat 数据：分组列与组别暂不可用")
                self.func.log("  请先在「单细胞分析」主页加载 .rds 数据集，再回到本页")
        except Exception:
            # 房规：不吞异常，但不许因为刷新失败打断页面跳转
            traceback.print_exc()
            self.func.log(f"❌ on_page_entered 刷新失败: {traceback.format_exc()}")

    def _has_analysis_data(self):
        """analysis 侧是否已有数据集（多写法兼容，避免绑死 W3 的字段名）"""
        try:
            if hasattr(self.analysis, 'has_shared_data') and callable(self.analysis.has_shared_data):
                return bool(self.analysis.has_shared_data())
            for attr in ('rds_path', 'seurat_path'):
                value = getattr(self.analysis, attr, None)
                if value:
                    return True
        except Exception:
            traceback.print_exc()
        return False

    # ================= 取值出口 =================

    def collect_params(self):
        """★ 唯一取值出口：返回直接交给 `analysis.run(params)` 的字典

        键名逐字照 `_d_spec_virtual_knockout.md` §3 / 说明书 §6「参数键名」列，
        另加三个不暴露的固定参数（`scale_scores/symmetric/lambda/td_max_iter/td_max_error/td_n_decimal`）。
        小数控件一律 `float(widget.value())`，整数控件一律 `int(widget.value())`。
        """
        params = {
            # ---- A 细胞选择 ----
            'group_col': self._current_text('vk_group_combo'),
            'group_values': self._selected_items('vk_group_list'),
            'filter1_col': self._current_text('vk_filter1_col'),
            'filter1_values': self._selected_items('vk_filter1_list'),
            'filter2_col': self._current_text('vk_filter2_col'),
            'filter2_values': self._selected_items('vk_filter2_list'),
            # ---- B 基因选择 ----
            'gene_mode': self._current_data('vk_gene_mode_combo') or 'hvg',
            'n_top_genes': int(self._current_number('vk_hvg_n_spin', default=1000)),
            'gene_list_file': self._gene_list_name(),
            'drop_mt': self._is_checked('vk_drop_mt_check', default=True),
            'drop_ribo': self._is_checked('vk_drop_ribo_check', default=True),
            # ---- C 靶基因 ----
            'gko': self._current_text('vk_gko_edit').strip(),
            # ---- D 质控 ----
            'qc': self._is_checked('vk_qc_check', default=True),
            'qc_min_lib_size': int(self._current_number('vk_qc_minlib_spin', default=1000)),
            'qc_min_pct': float(self._current_number('vk_qc_minpct_spin', default=0.05)),
            'qc_max_mt_ratio': float(self._current_number('vk_qc_mtratio_spin', default=0.1)),
            'qc_remove_outlier': self._is_checked('vk_qc_outlier_check', default=True),
            # ---- E 网络 / 主流程 ----
            'n_net': int(self._current_number('vk_nnet_spin', default=10)),
            'n_cells': int(self._current_number('vk_ncells_spin', default=500)),
            'n_comp': int(self._current_number('vk_ncomp_spin', default=3)),
            'q': float(self._current_number('vk_nq_spin', default=0.9)),
            # ---- F 固定不暴露参数（说明书 §6 C5/C6/C7/D3：也必须在 params 里传给 R）----
            'scale_scores': True,
            'symmetric': False,
            'lambda': 0,
            'td_max_iter': 1000,
            'td_max_error': 1e-05,
            'td_n_decimal': 3,
            # ---- G 张量 / 对齐 / 统计 ----
            'td_k': int(self._current_number('vk_tdk_spin', default=3)),
            'ma_ndim': int(self._current_number('vk_madim_spin', default=2)),
            'exclude_gko': self._is_checked('vk_exclude_gko_check', default=True),
            'fdr': float(self._current_number('vk_fdr_spin', default=0.05)),
            'empirical_null': self._is_checked('vk_empnull_check', default=False),
            # ---- H 随机与并行 ----
            'seed': int(self._current_number('vk_seed_spin', default=1)),
            'n_cores': int(self._current_number('vk_ncores_spin', default=4)),
            # ---- I 数据集与输出（由 analysis 定型/生成，本层只带过去）----
            'rds_path': self._synced_rds_path,
            'dataset_name': self._synced_dataset_name,
            'out_dir': None,
        }
        return params

    # ================= 校验（说明书 §8.8，只判不用数据的条目） =================

    def validate(self, params):
        """返回 (ok, message)；ok=False 时 bind 弹错误框并中止

        只做「不拿数据就能判」的条目；「细胞 < 30 / 靶基因不在矩阵 / 面板为空 / 出边=0」
        属于 R 端（W3）职责，本层只把 R 的 `[VK] ERROR|` 原样透出。
        """
        # 0) 数据集（说明书 §8.8「读不到数据集」的前置版）
        if not params.get('rds_path') and self._has_analysis_data():
            # 分析层侧已有数据集（可能由别的入口设过）：把路径补进参数，避免误判
            params['rds_path'] = (getattr(self.analysis, 'rds_path', None)
                                  or getattr(self.analysis, 'seurat_path', None))
            params['dataset_name'] = (params.get('dataset_name')
                                      or getattr(self.analysis, 'dataset_name', None))
        if not params.get('rds_path'):
            return False, ("尚未同步到 Seurat 数据集\n\n"
                           "请先在「单细胞分析」主页加载 .rds 文件，再回到本页")

        # 1) 靶基因必填
        if not params.get('gko'):
            return False, "靶基因必填\n\n请填写要虚拟敲除的基因名（如 SOX2）"

        # 2) FDR 越界（说明书 §8.8：fdr 0–1）
        fdr = params.get('fdr', 0.05)
        try:
            fdr = float(fdr)
        except (TypeError, ValueError):
            return False, f"FDR 阈值必须是数字（当前：{params.get('fdr')}）"
        if fdr <= 0 or fdr > 1:
            return False, f"FDR 阈值必须在 (0, 1] 之间（当前：{fdr}）"
        params['fdr'] = fdr

        # 3) 模式 = list 但文件为空 ⇒ 不报错，按 hvg 兜底并在日志说明（说明书 §5.2 联动 3）
        if params.get('gene_mode') == 'list' and not params.get('gene_list_file'):
            params['gene_mode'] = 'hvg'
            self.func.log("⚠ 基因来源选了「外部基因列表」但未选择列表文件："
                          "本次按「高变基因前 N」兜底（绝不静默变成全部基因）")
            self.func.log(f"  兜底 N = {params.get('n_top_genes')}")
        elif params.get('gene_mode') == 'list' and params.get('gene_list_file'):
            # 3.1) 文件存在性：只提示不中止（真正的判定在 R 端「基因面板为空」）
            try:
                list_path = os.path.join(self.func.get_gene_lists_dir(),
                                         params['gene_list_file'])
                if not os.path.exists(list_path):
                    self.func.log(f"⚠ 基因列表文件不存在：{list_path}"
                                  "（R 端可能会报「基因面板为空」）")
            except Exception:
                traceback.print_exc()
                self.func.log(f"⚠ 基因列表文件存在性检查失败: {traceback.format_exc()}")

        # 4) 经验零分布（说明书 §8.8：empirical_null=TRUE 但 locfdr 未装 ⇒ 中止）
        if params.get('empirical_null'):
            return False, ("经验零分布（Efron）需要 locfdr 包，当前环境未安装，"
                           "该选项不可用（请勿勾选）")

        # 5) 面板规模的内存预估 + 确认框（说明书 §5.2 联动 4 / §8.8「内存预估超限」）
        if not self._confirm_memory(params):
            return False, None

        return True, ""

    def _confirm_memory(self, params):
        """`all` 模式或 N > 2000 ⇒ 显示预估内存并弹确认框

        ★ 说明书要求「超可用内存时弹确认」；但**本仓无可靠的可用内存取值手段**
        （见交付回执「待确认」），因此这里**只显示预估内存并让用户确认**，
        绝不假装知道可用内存。
        """
        mode = params.get('gene_mode')
        n_genes = int(params.get('n_top_genes', 0) or 0)

        if mode == 'all':
            message = ("基因来源＝「全部基因」\n\n"
                       "内存按基因面板数的平方增长（5000 基因约 8.6 GB、10000 基因约 34 GB）。\n"
                       "本机可用内存无法自动读取，请自行确认后再继续。\n\n"
                       "确定要继续运行吗？")
        elif mode == 'hvg' and n_genes > 2000:
            message = (f"高变基因数 N = {n_genes}（> 2000）\n\n"
                       f"预估内存：约 {self._estimate_memory_gb(n_genes):.1f} GB。\n"
                       "本机可用内存无法自动读取，请自行确认后再继续。\n\n"
                       "确定要继续运行吗？")
        else:
            return True

        self.func.log("⚠ " + message.replace("\n\n", " ").replace("\n", " "))
        return self.func.confirm_question("内存预估确认", message)

    @staticmethod
    def _estimate_memory_gb(n_genes):
        """内存预估（GB）：0.5 GB × (n/1000)²（说明书 §11 甲方实测模型）"""
        try:
            n = max(int(n_genes), 0)
            return 0.5 * (n / 1000.0) ** 2
        except (TypeError, ValueError):
            return 0.0

    # ================= 运行 =================

    def on_run_clicked(self):
        """运行按钮：取值 → 校验 → QThread 跑 analysis.run → 回主线程回填结果"""
        try:
            # 每次点运行先同步一次数据（用户可能刚在主页换了数据集）
            self.sync_data_from_single_cell_main()

            if self._thread is not None and self._thread.isRunning():
                self.func.alert_error("虚拟敲除正在运行中，请等待本次运行结束")
                return

            # 本次运行的告警与日志先清掉（必须在取值/校验之前：
            # validate 的「按 hvg 兜底」说明也要留在日志里，说明书 §5.2 联动 3）
            self.func.clear_warning()
            self.func.clear_log()

            params = self.collect_params()
            ok, message = self.validate(params)
            if not ok:
                if message:
                    self.func.alert_error(message)
                    self.func.log(f"❌ 参数校验未通过：{message.splitlines()[0]}")
                else:
                    # 例如用户在内存预估确认框里点了「否」
                    self.func.log("⚠ 已取消本次运行（内存预估未确认）")
                return

            ui = self.virtual_knockout_ui
            mode_text = {'hvg': '高变基因前 N', 'all': '全部基因',
                         'list': '外部基因列表'}.get(params.get('gene_mode'), '未知')
            self.func.log("=" * 60)
            self.func.log("开始运行虚拟敲除")
            self.func.log(f"  数据集: {params.get('dataset_name')}")
            self.func.log(f"  Seurat rds: {params.get('rds_path')}")
            self.func.log(f"  靶基因: {params.get('gko')}")
            self.func.log(f"  分组列: {params.get('group_col')}  组别: {params.get('group_values')}")
            self.func.log(f"  筛选1: {params.get('filter1_col')} = {params.get('filter1_values')}")
            self.func.log(f"  筛选2: {params.get('filter2_col')} = {params.get('filter2_values')}")
            self.func.log(f"  基因来源: {mode_text}（N={params.get('n_top_genes')}，"
                          f"列表={params.get('gene_list_file') or '无'}）")
            self.func.log(f"  质控: {params.get('qc')}  minLib={params.get('qc_min_lib_size')} "
                          f"minPCT={params.get('qc_min_pct')} maxMT={params.get('qc_max_mt_ratio')}")
            self.func.log(f"  网络={params.get('n_net')} 每网络细胞={params.get('n_cells')} "
                          f"主成分={params.get('n_comp')} q={params.get('q')}")
            self.func.log(f"  排除靶基因校准: {params.get('exclude_gko')}  FDR={params.get('fdr')}")
            self.func.log("=" * 60)

            # ★ 说明书 §5.5：不排除靶基因 ⇒ 结果区红字口径提示
            if not params.get('exclude_gko'):
                self.func.set_warning("当前口径未排除靶基因：靶基因自身通常占据全部显著位。")

            # 运行中：禁按钮 + 显进度
            self.func.set_run_button_enabled(False)
            self.func.set_progress_visible(True)
            self.func.set_progress(0)
            # ★ 只用冻结名 vk_tabs（不做别名兜底，避免出现未冻结控件名）
            self.tabs = getattr(ui, 'vk_tabs', None)
            if self.tabs is not None:
                self.tabs.setCurrentIndex(0)

            self._run_start_time = time.time()

            # 建立 Worker + Thread（照抄 monocle genelists 的模式 1）
            self._worker = VirtualKnockoutWorker(self.analysis, params)
            self._thread = QThread()
            self._worker.moveToThread(self._thread)

            self._thread.started.connect(self._worker.run)
            self._worker.progress.connect(self._on_worker_progress)
            self._worker.finished.connect(self._on_worker_finished)
            self._worker.finished.connect(self._thread.quit)
            self._thread.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)

            self._thread.start()
        except Exception:
            # 房规：任何异常都要留痕，且必须把按钮/进度条恢复回来
            traceback.print_exc()
            self.func.log(f"❌ 启动虚拟敲除失败: {traceback.format_exc()}")
            self.func.alert_failure("启动虚拟敲除失败，详见日志")
            self.func.set_run_button_enabled(True)
            self.func.set_progress_visible(False)
            # 线程对象可能已经建了一半，清掉避免下次误判「正在运行」
            self._thread = None
            self._worker = None

    def _on_worker_progress(self, message):
        """工作线程进度回调（主线程执行；解析 [VK] 协议行）"""
        try:
            line = "" if message is None else str(message)

            # ★ 进度：`[VK] STEP|i|n|描述` ⇒ set_progress(int(100*i/n))
            if self.func.update_progress_from_line(line):
                return

            # ★ 出边自检：`[VK] OUTDEG|gko=…|edges=0` ⇒ 红字
            if self.func.handle_vk_outdeg_line(line):
                return

            # 其余 [VK] 行与普通行一律原样进日志
            self.func.log(line)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log(f"❌ 进度行处理失败: {traceback.format_exc()}")
            except Exception:
                traceback.print_exc()

    def _on_worker_finished(self, success, result):
        """运行结束（主线程）：恢复按钮/进度 → 填表/出图/写日志"""
        try:
            self.func.set_progress_visible(False)
            self.func.set_run_button_enabled(True)

            if not success:
                self.func.alert_failure(f"虚拟敲除执行失败:\n{result}")
                self.func.log(f"❌ 虚拟敲除失败: {result}")
                return

            self.func.set_progress(100)
            elapsed = None
            if self._run_start_time is not None:
                elapsed = time.time() - self._run_start_time

            self._fill_results(result, elapsed)
            self.func.alert_success("虚拟敲除完成！结果已写入输出目录，详见「日志」页签。")
        except Exception:
            traceback.print_exc()
            self.func.log(f"❌ 回填结果失败: {traceback.format_exc()}")
            self.func.alert_failure("回填结果失败，详见日志")
        finally:
            self._worker = None
            self._thread = None

    def _fill_results(self, result, elapsed):
        """把 analysis.run 的返回体（或 parse_outputs 的产物）填进界面"""
        ui = self.virtual_knockout_ui

        outputs = result
        # 冻结签名 `run(params, progress_callback) -> (bool, str)`：第二项是 out_dir 字符串
        # ⇒ 用 `parse_outputs(out_dir)` 展开成产物字典。
        # ★ 但若调用方**已经给了产物字典**（含 full_df/sig_df/fig_bar/diagnostics 等），就直接用它、
        #   **不再从磁盘重解析**：否则会（a）白读一遍 CSV/PNG，（b）把调用方在内存里注入的诊断
        #   （如 no_out_edges=True、missing=[...]）静默覆盖掉磁盘上的旧值。
        try:
            if hasattr(self.analysis, 'parse_outputs'):
                out_dir = None
                need_parse = False
                if isinstance(result, str):
                    if os.path.isdir(result):
                        out_dir = result
                        need_parse = True
                elif isinstance(result, dict):
                    out_dir = (result.get('out_dir') or result.get('output_dir')
                               or result.get('result_dir'))
                    has_products = any(k in result for k in (
                        'diagnostics', 'full_df', 'sig_df', 'full_csv', 'sig_csv',
                        'fig_bar', 'fig_scatter'))
                    need_parse = (not has_products) and bool(out_dir)
                if need_parse and out_dir:
                    parsed = self.analysis.parse_outputs(out_dir)
                    if isinstance(parsed, dict):
                        outputs = parsed
        except Exception:
            traceback.print_exc()
            self.func.log(f"⚠ 解析产物清单失败（改用 run 的返回体）: {traceback.format_exc()}")

        if not isinstance(outputs, dict):
            self.func.log(f"⚠ 未取得结构化产物清单，返回体类型: {type(outputs).__name__}")
            outputs = {}

        # ---- 两张表 ----
        full_df = self._pick(outputs, ('full_df', 'df_full', 'diff_full', 'all_genes_df'))
        sig_df = self._pick(outputs, ('sig_df', 'df_sig', 'diff_significant', 'sig_genes_df'))

        full_csv = self._pick(outputs, ('full_csv', 'full_csv_path', 'diff_full_csv'))
        sig_csv = self._pick(outputs, ('sig_csv', 'sig_csv_path', 'diff_sig_csv'))
        if full_df is None and full_csv and os.path.exists(str(full_csv)):
            full_df = pd.read_csv(full_csv)
        if sig_df is None and sig_csv and os.path.exists(str(sig_csv)):
            sig_df = pd.read_csv(sig_csv)

        # ★ 留一份**当前结果**的显著基因表给「发送到列表文件夹」用（契约 §3：不重算、不重跑）
        self._last_sig_df = sig_df

        # 两张表：列取 CSV/DataFrame 自身列序（`columns=None`）
        self.func.show_table(getattr(ui, 'vk_all_table', None), full_df, None)
        self.func.show_table(getattr(ui, 'vk_sig_table', None), sig_df, None)

        # ---- 两张图（W3 定稿键名：fig_bar / fig_scatter；保留旧别名兜底）----
        bar_png = self._pick(outputs, ('fig_bar', 'bar_png', 'fig1_bar', 'bar_path', 'img_bar'))
        scatter_png = self._pick(outputs, ('fig_scatter', 'scatter_png', 'fig2_scatter',
                                           'scatter_path', 'img_scatter'))
        self.func.show_image(getattr(ui, 'vk_img_bar', None), bar_png)
        self.func.show_image(getattr(ui, 'vk_img_scatter', None), scatter_png)

        # ---- 日志回显 ----
        out_dir = self._pick(outputs, ('out_dir', 'output_dir', 'result_dir'))
        if out_dir:
            self.func.log(f"输出目录: {out_dir}")
        if full_df is not None:
            self.func.log(f"全部基因表: {len(full_df)} 行")
        if sig_df is not None:
            self.func.log(f"显著基因表: {len(sig_df)} 行")

        # ★ 结构化 diagnostics 优先（比自己在日志里正则更稳；W3-b 已把 [VK] 行都解析好）
        #   键名口径：**W3-b `_parse_vk_lines` 写出的名字为主 + 本层旧名兜底**（取并集）。
        #   生产端/消费端键名对不上时界面不崩也不报错、只是数字静默不显示（⑨ 判据专治这个），
        #   所以两种写法都要认，绝不为了好看删兜底键。
        diag = self._pick(outputs, ('diagnostics',))
        if isinstance(diag, dict) and diag:
            # ★ 两端键名一致、已打通的诊断：无出边 ⇒ 红字（不要回归它）
            if diag.get('no_out_edges'):
                self.func.warn_out_of_edges()

            for key in ('genes', 'data_genes',                    # 矩阵规模
                        'cells', 'data_cells',
                        'after_filter', 'cells_after_filter',    # 过滤后细胞
                        'qc_genes', 'qc_cells',                  # 质控后规模（§10）
                        'panel_genes', 'panel_cells',
                        'nonzero_pct', 'panel_nonzero',          # ★ 非零占比
                        'target_gko',
                        'detected_cells', 'target_detected_cells',   # ★ 靶基因检出细胞数
                        'total_counts', 'target_total_counts',
                        'out_edges', 'out_degree',               # ★ 靶基因出边数
                        'share_of_target',                       # ★ 靶基因占 Σd²
                        'E_pkg', 'E_noKO',                       # 校准诊断（§8.9 E 行）
                        'calib_pkg', 'sig_calib_pkg',            # ★ 口径 A 显著数
                        'calib_noKO', 'sig_calib_noKO',          # ★ 口径 B 显著数
                        'fdr', 'sig_fdr',
                        'effective_ncells', 'n_cells_effective',
                        'out_dir', 'done_out_dir',
                        'no_out_edges',                          # ★ 出边=0（红字已在上面给出）
                        'notes', 'r_error'):                     # R 端 NOTE / ERROR 正文
                value = diag.get(key)
                if value is None:
                    continue
                if key == 'no_out_edges':
                    # 只有 edges=0 才有意义（红字已在上方给出，这里只是日志留痕）
                    if value:
                        self.func.log("  靶基因在网络中没有出边（已红字提示）")
                    continue
                if key == 'notes':
                    # R 端 NOTE（list，可能含「靶基因不在面板中，已强制加入」）逐条回显
                    if isinstance(value, (list, tuple)):
                        for note in value:
                            self.func.log(f"  注: {note}")
                    else:
                        self.func.log(f"  注: {value}")
                    continue
                if key == 'r_error':
                    self.func.log(f"  R 端错误: {value}")
                    continue
                self.func.log(f"  {key} = {value}")
        else:
            # 兜底：diagnostics 缺失时按扁平键回显能拿到的数字（同样取并集）
            for key in ('genes', 'data_genes', 'cells', 'data_cells',
                        'after_filter', 'cells_after_filter',
                        'qc_genes', 'qc_cells', 'panel_genes', 'panel_cells',
                        'nonzero_pct', 'panel_nonzero', 'target_gko',
                        'detected_cells', 'target_detected_cells',
                        'total_counts', 'target_total_counts',
                        'out_edges', 'out_degree', 'share_of_target',
                        'E_pkg', 'E_noKO',
                        'calib_pkg', 'sig_calib_pkg',
                        'calib_noKO', 'sig_calib_noKO',
                        'fdr', 'sig_fdr',
                        'effective_ncells', 'n_cells_effective',
                        'n_genes', 'n_cells', 'out_dir', 'done_out_dir'):
                value = self._pick(outputs, (key,))
                if value is not None:
                    self.func.log(f"  {key} = {value}")

        # 两张图尺寸（说明书 §12.2 要求宽高一致）
        size_bar = self._pick(outputs, ('fig_bar_size',))
        size_scatter = self._pick(outputs, ('fig_scatter_size',))
        if size_bar is not None or size_scatter is not None:
            self.func.log(f"  柱状图尺寸 = {size_bar}，散点图尺寸 = {size_scatter}")
            try:
                if (size_bar is not None and size_scatter is not None
                        and tuple(size_bar) != tuple(size_scatter)):
                    self.func.log("⚠ 两张图尺寸不一致（说明书 §12.2 要求宽高一致）")
            except Exception:
                traceback.print_exc()

        # 缺件清单（W3 的附加键）
        missing = self._pick(outputs, ('missing',))
        if missing:
            self.func.log(f"⚠ 缺件: {missing}")

        # W3 的其余附加键（元数据/完整性标记）：存在就回显
        # —— 避免"parse_outputs 返回了但界面从不取用"这类静默（⑨ 系列判据的同源风险）
        size_mismatch = self._pick(outputs, ('size_mismatch',))
        if size_mismatch:
            self.func.log("⚠ 两张图尺寸不一致（W3 的 size_mismatch 标记，"
                          "说明书 §12.2 要求宽高一致）")
        run_log = self._pick(outputs, ('run_log',))
        if run_log:
            self.func.log(f"  R 全量日志: {run_log}")
        summary = self._pick(outputs, ('summary',))
        if summary is not None:
            if isinstance(summary, dict):
                self.func.log(f"  运行摘要键: {list(summary.keys())}")
            else:
                self.func.log(f"  运行摘要: {summary}")
        params_out = self._pick(outputs, ('params',))
        if params_out:
            self.func.log(f"  参数指纹: {params_out}")
        rds_out = self._pick(outputs, ('rds',))
        if rds_out:
            self.func.log(f"  结果 rds: {rds_out}")

        if elapsed is not None:
            self.func.log(f"耗时: {elapsed:.1f} s")

    # ============ 「发送到列表文件夹」（契约 §3 v2：显著基因 + 正/负相关子集） ============

    #: 默认勾选的子集标签（契约 §3：虚拟敲除默认**全部**勾选 = 加子集功能前的旧口径）
    DEFAULT_SUBSET_LABEL = "显著基因"
    LOGFC_COLUMNS = ('logFC', 'log2FC', 'logfc')

    def _sig_df_gene_col(self):
        """显著基因表里的基因列名（缺失时退回第一列）"""
        df = self._last_sig_df
        return 'gene' if 'gene' in df.columns else df.columns[0]

    def collect_significant_genes(self):
        """取「当前结果的显著基因」

        口径 = 结果区「显著基因」页签填的那张表（`diffRegulation_significant.csv` 的 `gene` 列，
        R 端按 `exclude_gko`/FDR 口径选好的那批）—— 即 `_fill_results` 时留存的**同一份内存
        DataFrame**，**不重算、不重跑** R。
        """
        df = self._last_sig_df
        if df is None or len(df) == 0:
            return []
        try:
            return [str(g) for g in df[self._sig_df_gene_col()].tolist()]
        except Exception:
            traceback.print_exc()
            self.func.log(f"[WARN] 读取显著基因表失败: {traceback.format_exc()}")
            return []

    def collect_gene_subsets(self):
        """返回 `[(标签, 基因, 默认勾选), ...]`：显著基因（全部）/ 正相关 / 负相关

        - **显著基因（全部）**永远第一组：它等于「显著基因」页签那张表本身，**默认勾选**，
          因此不动手时发出的是**与加子集功能前逐字一致**的那批（顺序也一致）。
        - 正/负相关：**只有在显著表里确实带方向列（`logFC`/`log2FC`）时才给**——
          该列是页面自身散点图用的同一列，`logFC > 0` 记正相关、`< 0` 记负相关；
          `NaN` 的行只留在「显著基因」组里，**不硬塞进任何方向组**。
        - 没有方向列（例如调用方注入的简化表）⇒ **只给 1 个子集**，沿用旧口径（宁少勿假）。
        """
        df = self._last_sig_df
        if df is None or len(df) == 0:
            return []
        try:
            gene_col = df[self._sig_df_gene_col()]
            allg = [str(g) for g in gene_col.tolist()]
            groups = [(self.DEFAULT_SUBSET_LABEL, allg, True)]

            lfc_col = next((c for c in self.LOGFC_COLUMNS if c in df.columns), None)
            if lfc_col is not None:
                try:
                    lfc = pd.to_numeric(df[lfc_col], errors='coerce')
                except Exception:
                    traceback.print_exc()
                    lfc = None
                if lfc is not None and lfc.notna().any():
                    pos = [str(g) for g in gene_col[lfc > 0].tolist()]
                    neg = [str(g) for g in gene_col[lfc < 0].tolist()]
                    groups.append(("正相关（%s>0）" % lfc_col, pos, True))
                    groups.append(("负相关（%s<0）" % lfc_col, neg, True))
        except Exception:
            traceback.print_exc()
            self.func.log(f"[WARN] 读取显著基因子集失败: {traceback.format_exc()}")
            return []
        return groups

    def _default_union(self, groups):
        """默认勾选各集合的**并集并去重**（与共享工具 `selected_genes()` 同口径，保序）"""
        out, seen = [], set()
        for _label, genes, default in normalize_groups(groups):
            if not default:
                continue
            for g in genes:
                s = str(g).strip()
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)
        return out

    def on_send_to_genelist(self):
        """「发送到列表文件夹」：所选子集 → `appdata/genelists`（单列无表头 xlsx）

        契约 §1/§3/§4：
          · 子集 ≥2 个 ⇒ `multi=True` 弹窗勾选，发送 = **所选集合的并集并去重**；
          · 只剩 1 个可诚实给出的子集（显著表没有方向列）⇒ 沿用旧口径（不弹选择区）；
          · **默认全选** ⇒ 不动手时与加子集功能前**逐字一致**；
          · 未运行 / 结果为空 / 显著基因为 0 ⇒ 只提示，**绝不写空文件**。
        页面只负责「取子集 → 调 `ask_and_send` → 按 `r["ok"]` 打日志」，**不自己 to_excel**。
        """
        try:
            groups = self.collect_gene_subsets()
            default_genes = self._default_union(groups)
            if not default_genes:
                self.func.log("[WARN] 当前没有显著基因（尚未运行虚拟敲除，或结果显示 0 个显著）"
                              "——未发送任何文件")
                return

            if len(normalize_groups(groups)) >= 2:
                r = ask_and_send(self.parent_widget, groups=groups, multi=True,
                                 prefix="sc虚拟敲除显著基因")
            else:
                r = ask_and_send(self.parent_widget, default_genes,
                                 prefix="sc虚拟敲除显著基因")
            if r.get('ok'):
                self.func.log(f"[INFO] {r.get('message', '')}")
            elif r.get('cancelled'):
                self.func.log("[INFO] 已取消发送")
            else:
                self.func.log(f"[WARN] 发送失败：{r.get('message', '')}")
        except Exception:
            traceback.print_exc()
            self.func.log(f"[WARN] 发送到列表文件夹失败: {traceback.format_exc()}")

    @staticmethod
    def _pick(mapping, keys):
        """从产物字典里按候选键名取值（W3 的键名未冻结，多写法兼容）"""
        if not isinstance(mapping, dict):
            return None
        for key in keys:
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        return None

    # ================= 控件读取小工具（全部「缺失即默认值」） =================

    def _get_widget(self, name):
        return getattr(self.virtual_knockout_ui, name, None)

    def _current_text(self, name):
        """读下拉框/输入框文本；缺控件或空选 ⇒ ''（★ 不许用 bool(widget) 判空）"""
        widget = self._get_widget(name)
        if widget is None:
            return ""
        try:
            if hasattr(widget, 'currentText'):
                return str(widget.currentText() or '').strip()
            if hasattr(widget, 'text'):
                return str(widget.text() or '').strip()
        except Exception:
            traceback.print_exc()
        return ""

    def _current_data(self, name):
        """读下拉框 userData（基因来源模式用）"""
        widget = self._get_widget(name)
        if widget is None or not hasattr(widget, 'currentData'):
            return None
        try:
            return widget.currentData()
        except Exception:
            traceback.print_exc()
            return None

    def _current_number(self, name, default=0):
        """读数值控件：优先 `.value()`（StyledNumberInput/QSpinBox），否则解析 `.text()`"""
        widget = self._get_widget(name)
        if widget is None:
            return default
        try:
            if hasattr(widget, 'value'):
                value = widget.value()
                return default if value is None else value
            if hasattr(widget, 'text'):
                text = str(widget.text() or '').strip()
                if not text:
                    return default
                return float(text)
        except Exception:
            traceback.print_exc()
            self.func.log(f"⚠ 控件 {name} 取值失败，使用默认值 {default}")
        return default

    def _is_checked(self, name, default=False):
        """读勾选框状态；缺控件 ⇒ 默认值"""
        widget = self._get_widget(name)
        if widget is None or not hasattr(widget, 'isChecked'):
            return default
        try:
            return bool(widget.isChecked())
        except Exception:
            traceback.print_exc()
            return default

    def _selected_items(self, name):
        """读多选列表的选中项文本列表（空 = 全选/不生效，由 R 端语义决定）"""
        widget = self._get_widget(name)
        if widget is None or not hasattr(widget, 'selectedItems'):
            return []
        try:
            return [item.text() for item in widget.selectedItems()]
        except Exception:
            traceback.print_exc()
            return []

    def _get_column_values(self, column):
        """取某 meta.data 列的唯一值：先问 analysis（读缓存），取不到再用同步缓存"""
        if not column:
            return []
        try:
            if hasattr(self.analysis, 'get_meta_values'):
                values = self.analysis.get_meta_values(column)
                if values:
                    return [str(v) for v in values]
        except Exception:
            traceback.print_exc()
            self.func.log(f"⚠ 读取「{column}」取值失败，改用同步缓存")
        cached = (self._meta_values or {}).get(column)
        if cached:
            return [str(v) for v in cached]
        return []
