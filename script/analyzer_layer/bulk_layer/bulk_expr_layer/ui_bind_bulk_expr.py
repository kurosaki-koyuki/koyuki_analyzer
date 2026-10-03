# -*- coding: utf-8 -*-
"""
bulk表达量分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.bulk_layer.bulk_expr_layer.bulk_expr_analysis import BulkExprAnalysis
from script.analyzer_layer.bulk_layer.bulk_expr_layer.ui_func_bulk_expr import BulkExprFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.bulk_layer.bulk_gene_set_utils import (
    GENE_SET_METHODS, GENE_SET_METHOD_IDS,
    load_gene_set_from_file, parse_gene_set_from_text,
    resolve_gene_set,
)


class BulkExprBind:
    """bulk表达量分析功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, bulk_expr_ui):
        self.parent = parent_window
        self.bulk_expr_ui = bulk_expr_ui
        self.analysis = BulkExprAnalysis()
        self.func = BulkExprFunc(bulk_expr_ui, parent_window)
        self.func.analysis = self.analysis  # 引用analysis到func
        self.data_folder = None
        self.adata = None
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_bulk_expr_functions()
        self.bind_geneset_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.bulk_expr_ui, 'nav_btn_back'):
            self.bulk_expr_ui.nav_btn_back.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

        if hasattr(self.bulk_expr_ui, 'nav_btn_single'):
            self.bulk_expr_ui.nav_btn_single.clicked.connect(lambda: self.switch_to_single())
        if hasattr(self.bulk_expr_ui, 'nav_btn_geneset'):
            self.bulk_expr_ui.nav_btn_geneset.clicked.connect(lambda: self.switch_to_geneset())

    def switch_to_single(self):
        """切到单基因分析页"""
        ui = self.bulk_expr_ui
        if hasattr(ui, 'content_stack'):
            ui.content_stack.setCurrentIndex(0)
        if hasattr(ui, 'nav_btn_single'):
            ui.nav_btn_single.setChecked(True)
        if hasattr(ui, 'nav_btn_geneset'):
            ui.nav_btn_geneset.setChecked(False)

    def switch_to_geneset(self):
        """切到基因集分析页"""
        ui = self.bulk_expr_ui
        if hasattr(ui, 'content_stack'):
            ui.content_stack.setCurrentIndex(1)
        if hasattr(ui, 'nav_btn_geneset'):
            ui.nav_btn_geneset.setChecked(True)
        if hasattr(ui, 'nav_btn_single'):
            ui.nav_btn_single.setChecked(False)
        self._on_gene_set_input_mode_changed()

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.bulk_expr_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.bulk_expr_ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def bind_bulk_expr_functions(self):
        """绑定bulk表达量分析功能信号"""
        log_widget = getattr(self.bulk_expr_ui, 'bulk_status_text', None)

        # 分类列选择下拉框
        if hasattr(self.bulk_expr_ui, 'bulk_clinical_combo'):
            self.bulk_expr_ui.bulk_clinical_combo.currentIndexChanged.connect(self.on_clinical_changed)

        # 筛选1启用复选框
        if hasattr(self.bulk_expr_ui, 'bulk_filter1_enable'):
            self.bulk_expr_ui.bulk_filter1_enable.stateChanged.connect(self.on_filter1_enabled)

        # 筛选1下拉框
        if hasattr(self.bulk_expr_ui, 'bulk_filter1_combo'):
            self.bulk_expr_ui.bulk_filter1_combo.currentIndexChanged.connect(self.on_filter1_combo_changed)

        # 筛选2启用复选框
        if hasattr(self.bulk_expr_ui, 'bulk_filter2_enable'):
            self.bulk_expr_ui.bulk_filter2_enable.stateChanged.connect(self.on_filter2_enabled)

        # 筛选2下拉框
        if hasattr(self.bulk_expr_ui, 'bulk_filter2_combo'):
            self.bulk_expr_ui.bulk_filter2_combo.currentIndexChanged.connect(self.on_filter2_combo_changed)

        # 生成结果图按钮
        if hasattr(self.bulk_expr_ui, 'bulk_btn_plot'):
            bind_button_with_sound(self.bulk_expr_ui.bulk_btn_plot, self.generate_plots,
                                   log_widget, "绘图完成", "绘图失败")

        # 导出CSV按钮
        if hasattr(self.bulk_expr_ui, 'bulk_btn_export_csv'):
            bind_button_with_sound(self.bulk_expr_ui.bulk_btn_export_csv, self.export_csv,
                                   log_widget, "CSV导出完成", "CSV导出失败")

        # 导出PNG按钮
        if hasattr(self.bulk_expr_ui, 'bulk_btn_export_png'):
            bind_button_with_sound(self.bulk_expr_ui.bulk_btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        # 导出PDF按钮
        if hasattr(self.bulk_expr_ui, 'bulk_btn_export_pdf'):
            bind_button_with_sound(self.bulk_expr_ui.bulk_btn_export_pdf, self.export_pdf,
                                   log_widget, "PDF导出完成", "PDF导出失败")

    def bind_geneset_functions(self):
        """绑定基因集分析页功能信号"""
        log_widget = getattr(self.bulk_expr_ui, 'bulk_status_text', None)
        ui = self.bulk_expr_ui

        # 输入模式互斥
        if hasattr(ui, 'bulk_geneset_input_mode_combo'):
            ui.bulk_geneset_input_mode_combo.currentIndexChanged.connect(self._on_gene_set_input_mode_changed)

        # 分类列选择下拉框
        if hasattr(ui, 'bulk_geneset_clinical_combo'):
            ui.bulk_geneset_clinical_combo.currentIndexChanged.connect(self.on_geneset_clinical_changed)

        # 筛选1启用复选框
        if hasattr(ui, 'bulk_geneset_filter1_enable'):
            ui.bulk_geneset_filter1_enable.stateChanged.connect(self.on_geneset_filter1_enabled)

        # 筛选1下拉框
        if hasattr(ui, 'bulk_geneset_filter1_combo'):
            ui.bulk_geneset_filter1_combo.currentIndexChanged.connect(self.on_geneset_filter1_combo_changed)

        # 筛选2启用复选框
        if hasattr(ui, 'bulk_geneset_filter2_enable'):
            ui.bulk_geneset_filter2_enable.stateChanged.connect(self.on_geneset_filter2_enabled)

        # 筛选2下拉框
        if hasattr(ui, 'bulk_geneset_filter2_combo'):
            ui.bulk_geneset_filter2_combo.currentIndexChanged.connect(self.on_geneset_filter2_combo_changed)

        # 生成结果图按钮
        if hasattr(ui, 'bulk_geneset_btn_plot'):
            bind_button_with_sound(ui.bulk_geneset_btn_plot, self.generate_plots,
                                   log_widget, "绘图完成", "绘图失败")

        # 导出CSV按钮
        if hasattr(ui, 'bulk_geneset_btn_export_csv'):
            bind_button_with_sound(ui.bulk_geneset_btn_export_csv, self.export_geneset_csv,
                                   log_widget, "CSV导出完成", "CSV导出失败")

        # 导出PNG按钮
        if hasattr(ui, 'bulk_geneset_btn_export_png'):
            bind_button_with_sound(ui.bulk_geneset_btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        # 导出PDF按钮
        if hasattr(ui, 'bulk_geneset_btn_export_pdf'):
            bind_button_with_sound(ui.bulk_geneset_btn_export_pdf, self.export_pdf,
                                   log_widget, "PDF导出完成", "PDF导出失败")

        # 进页面/构造时执行一次互斥状态
        self._on_gene_set_input_mode_changed()

    def _on_gene_set_input_mode_changed(self):
        """基因集输入模式互斥：外部列表 ↔ 手动输入"""
        ui = self.bulk_expr_ui
        if not hasattr(ui, 'bulk_geneset_input_mode_combo'):
            return

        manual_mode = ui.bulk_geneset_input_mode_combo.currentText() == "手动输入"

        if hasattr(ui, 'bulk_geneset_file_combo'):
            ui.bulk_geneset_file_combo.setEnabled(not manual_mode)
        if hasattr(ui, 'bulk_geneset_manual_input'):
            ui.bulk_geneset_manual_input.setEnabled(manual_mode)

    def _populate_geneset_controls(self, columns):
        """数据加载后填充基因集页的分类列/筛选下拉框"""
        ui = self.bulk_expr_ui
        # ★ 挑一个"低基数分类列"作默认（2~25 个组），**排除生存列**与高基数列：
        #   直接 setCurrentIndex(1) 会默认选到第一列 `time`（几百个唯一值）→
        #   `itertools.combinations` 生成几万对 → 卡死（用户实机报的 bug）。
        default_col = None
        if self.adata is not None:
            for c in columns:
                if c in ("time", "time (month)", "state"):
                    continue
                try:
                    n = int(self.adata.obs[c].nunique())
                except Exception:
                    n = 0
                if 2 <= n <= 25:
                    default_col = c
                    break
        if hasattr(ui, 'bulk_geneset_clinical_combo'):
            self.func.set_combo_items(ui.bulk_geneset_clinical_combo, ["全部"] + list(columns))
            # 基因集页不支持「全部」（=跨所有列出组合图）；有低基数列就默认选中它，
            # 没有则停在「全部」（由 generate_gene_set_plots 弹"请选择具体分类列"）。
            if default_col is not None:
                try:
                    idx = list(columns).index(default_col) + 1   # +1 因为前面插了「全部」
                    ui.bulk_geneset_clinical_combo.setCurrentIndex(idx)
                except (ValueError, IndexError):
                    pass
        if hasattr(ui, 'bulk_geneset_filter1_combo'):
            self.func.set_combo_items(ui.bulk_geneset_filter1_combo, list(columns))
        if hasattr(ui, 'bulk_geneset_filter2_combo'):
            self.func.set_combo_items(ui.bulk_geneset_filter2_combo, list(columns))

    # ---------- 数据加载 ----------

    def scan_data_path(self):
        """扫描bulk数据路径"""
        folder_path = BULK_SCAN_DATA_PATH

        if not os.path.exists(folder_path):
            self.func.alert_error(f"扫描路径不存在: {folder_path}")
            return

        h5ad_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.h5ad')])

        if not h5ad_files:
            self.func.alert_error(f"{folder_path} 中没有找到h5ad文件")
            return

        self.data_folder = folder_path
        self.func.set_combo_items(self.bulk_expr_ui.bulk_h5ad_combo, h5ad_files)

        self.func.log(f"已扫描数据路径: {folder_path}")
        self.func.log(f"找到 {len(h5ad_files)} 个h5ad文件")

    def load_data(self):
        """加载bulk数据"""
        if not self.data_folder:
            self.func.alert_error("请先扫描数据路径")
            return

        selected_file = self.bulk_expr_ui.bulk_h5ad_combo.currentText()
        if not selected_file:
            self.func.alert_error("请选择要加载的h5ad文件")
            return

        self.clear_data()

        data_path = os.path.join(self.data_folder, selected_file)

        try:
            self.func.log("正在加载数据...")

            import scanpy as sc
            self.adata = sc.read_h5ad(data_path)
            self.analysis.set_adata(self.adata)

            self.dataset_name = os.path.splitext(selected_file)[0]
            self.dataset_output_dir = os.path.join(OUT_BASE, "bulk", self.dataset_name)
            os.makedirs(self.dataset_output_dir, exist_ok=True)
            self.analysis.set_dataset_output_dir(self.dataset_output_dir)

            n_samples, n_genes = self.adata.shape
            obs_columns = self.analysis.get_obs_columns()



            self.func.update_data_info(self.dataset_name, n_samples, n_genes, len(obs_columns))
            self.func.update_hint_text(self.dataset_name, n_samples, n_genes)
            self.func.update_clinical_combo(obs_columns)

            self.func.load_clinical_columns_to_filter1()
            self.func.load_clinical_columns_to_filter2()
            self._populate_geneset_controls(obs_columns)

            self.func.alert_success("数据加载完成")

        except Exception as e:
            self.func.log(f"加载失败: {str(e)}")
            self.func.alert_failure(f"加载失败: {str(e)}")
            traceback.print_exc()

    def clear_data(self):
        """清空已加载的数据"""
        self.adata = None
        self.analysis.set_adata(None)
        self.dataset_name = None
        self.dataset_output_dir = None

        self.func.log_clear()
        self.func.log_set_default()
        self.func.clear_image(self.bulk_expr_ui.bulk_violin_box_label)
        self.func.clear_image(self.bulk_expr_ui.bulk_box_label)
        self.func.clear_image(self.bulk_expr_ui.bulk_violin_label)

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return
        
        adata = bulk_top_bind.analysis.adata
        if adata is None:
            self.func.log("bulk主页未加载数据")
            return
        
        self.adata = adata
        self.analysis.set_adata(adata)
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir
        
        n_samples = adata.shape[0]
        n_genes = adata.shape[1]
        obs_columns = list(adata.obs.columns)
        
        self.func.update_data_info(self.dataset_name, n_samples, n_genes, len(obs_columns))
        self.func.update_hint_text(self.dataset_name, n_samples, n_genes)
        self.func.update_clinical_combo(obs_columns)
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()
        self._populate_geneset_controls(obs_columns)
        
        self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")
        self.func.log(f"样本数: {n_samples}, 基因数: {n_genes}")

    # ---------- 分类列选择 ----------

    def on_clinical_changed(self):
        """分类列选择改变"""
        selected_col = self.bulk_expr_ui.bulk_clinical_combo.currentText()

        self.bulk_expr_ui.bulk_pairwise_list.clear()

        if self.adata is None:
            self.func.show_clinical_col_list(False)
            self.func.enable_pairwise_controls(False)
            return

        if selected_col == "全部":
            self.func.show_clinical_col_list(True)
            self.func.enable_pairwise_controls(False)

            columns = self.analysis.get_obs_columns()
            print(f"[DEBUG] get_obs_columns returned: {columns}")
            self.func.update_clinical_col_list(columns)
        else:
            self.func.show_clinical_col_list(False)
            self.func.enable_pairwise_controls(True)

            groups = self.analysis.get_obs_unique_values(selected_col)
            self.func.update_group_list(groups)

            # ★ 组数过多时不生成两两组合（`time` 这类列几百个组 → combinations 几万对 → 卡死）
            if len(groups) > 25:
                self.func.update_pairwise_list([])
                self.func.log("列「%s」有 %d 个组，过多，已跳过组间比较" % (selected_col, len(groups)))
            else:
                pairs = list(itertools.combinations(groups, 2))
                self.func.update_pairwise_list(pairs)

    # ---------- 筛选控件 ----------

    def on_filter1_enabled(self, state):
        """筛选1启用状态改变"""
        enabled = state == Qt.Checked
        self.func.on_filter1_enabled(enabled)

    def on_filter1_combo_changed(self):
        """筛选1下拉框改变"""
        filter1_col = self.bulk_expr_ui.bulk_filter1_combo.currentText()
        if filter1_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter1_col)
            self.func.update_filter_list(self.bulk_expr_ui.bulk_filter1_list, groups)

    def on_filter2_enabled(self, state):
        """筛选2启用状态改变"""
        enabled = state == Qt.Checked
        self.func.on_filter2_enabled(enabled)

    def on_filter2_combo_changed(self):
        """筛选2下拉框改变"""
        filter2_col = self.bulk_expr_ui.bulk_filter2_combo.currentText()
        if filter2_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter2_col)
            self.func.update_filter_list(self.bulk_expr_ui.bulk_filter2_list, groups)

    # ---------- 基因集页分类列/筛选 ----------

    def on_geneset_clinical_changed(self):
        """基因集页分类列选择改变"""
        ui = self.bulk_expr_ui
        selected_col = ui.bulk_geneset_clinical_combo.currentText()

        if hasattr(ui, 'bulk_geneset_pairwise_list'):
            ui.bulk_geneset_pairwise_list.clear()

        if self.adata is None:
            return

        if selected_col == "全部":
            if hasattr(ui, 'bulk_geneset_group_list_label'):
                ui.bulk_geneset_group_list_label.hide()
            if hasattr(ui, 'bulk_geneset_group_list'):
                ui.bulk_geneset_group_list.hide()
            if hasattr(ui, 'bulk_geneset_pairwise_enable'):
                ui.bulk_geneset_pairwise_enable.setChecked(False)
            return

        if hasattr(ui, 'bulk_geneset_group_list_label'):
            ui.bulk_geneset_group_list_label.show()
        if hasattr(ui, 'bulk_geneset_group_list'):
            ui.bulk_geneset_group_list.show()

        groups = self.analysis.get_obs_unique_values(selected_col)
        self.func.fill_list_widget(ui.bulk_geneset_group_list, groups)

        # ★ 组数过多时不生成两两组合（`time` 这类列几百个组 → combinations 几万对 → 卡死）
        if len(groups) > 25:
            ui.bulk_geneset_pairwise_list.clear()
            self.func.log("列「%s」有 %d 个组，过多，已跳过组间比较" % (selected_col, len(groups)))
            return
        pairs = list(itertools.combinations(groups, 2))
        for pair in pairs:
            ui.bulk_geneset_pairwise_list.addItem(f"{pair[0]} vs {pair[1]}")
        for i in range(ui.bulk_geneset_pairwise_list.count()):
            ui.bulk_geneset_pairwise_list.item(i).setSelected(True)

    def on_geneset_filter1_enabled(self, state):
        """基因集页筛选1启用状态改变"""
        enabled = state == Qt.Checked
        ui = self.bulk_expr_ui
        if hasattr(ui, 'bulk_geneset_filter1_combo'):
            ui.bulk_geneset_filter1_combo.setEnabled(enabled)
        if hasattr(ui, 'bulk_geneset_filter1_list'):
            ui.bulk_geneset_filter1_list.setEnabled(enabled)

    def on_geneset_filter1_combo_changed(self):
        """基因集页筛选1下拉框改变"""
        ui = self.bulk_expr_ui
        filter1_col = ui.bulk_geneset_filter1_combo.currentText()
        if filter1_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter1_col)
            self.func.fill_list_widget(ui.bulk_geneset_filter1_list, groups)

    def on_geneset_filter2_enabled(self, state):
        """基因集页筛选2启用状态改变"""
        enabled = state == Qt.Checked
        ui = self.bulk_expr_ui
        if hasattr(ui, 'bulk_geneset_filter2_combo'):
            ui.bulk_geneset_filter2_combo.setEnabled(enabled)
        if hasattr(ui, 'bulk_geneset_filter2_list'):
            ui.bulk_geneset_filter2_list.setEnabled(enabled)

    def on_geneset_filter2_combo_changed(self):
        """基因集页筛选2下拉框改变"""
        ui = self.bulk_expr_ui
        filter2_col = ui.bulk_geneset_filter2_combo.currentText()
        if filter2_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter2_col)
            self.func.fill_list_widget(ui.bulk_geneset_filter2_list, groups)

    # ---------- 绘图 ----------

    def generate_plots(self):
        """生成表达量分析图表（按当前页分派单基因/基因集）"""
        if hasattr(self.bulk_expr_ui, 'content_stack') and self.bulk_expr_ui.content_stack.currentIndex() == 1:
            return self.generate_gene_set_plots()

        if self.adata is None:
            self.func.alert_error("请先加载数据")
            return

        multi_gene_text = self.bulk_expr_ui.bulk_multi_gene_input.toPlainText().strip()
        multi_gene_mode = False
        multi_gene_list = []

        if multi_gene_text:
            lines = [line.strip() for line in multi_gene_text.split('\n') if line.strip()]
            if lines:
                valid_genes, invalid_genes = self.analysis.get_multiple_genes_expression(lines)

                if not valid_genes:
                    self.func.alert_error(f"所有输入的基因都不存在于数据集中:\n{', '.join(invalid_genes)}")
                    return

                if invalid_genes:
                    self.func.alert_error(f"以下基因不存在于数据集中，已跳过:\n{', '.join(invalid_genes)}")

                multi_gene_list = valid_genes
                multi_gene_mode = True

        gene_name = self.bulk_expr_ui.bulk_gene_input.text().strip()

        if not multi_gene_mode and not gene_name:
            self.func.alert_error("请输入基因名称或在多基因测定区域输入基因")
            return

        if not multi_gene_mode and not self.analysis.get_gene_exists(gene_name):
            self.func.alert_error(f"基因 {gene_name} 不存在于数据集中")
            return

        clinical_col = self.bulk_expr_ui.bulk_clinical_combo.currentText()

        if multi_gene_mode and clinical_col == "全部":
            self.func.alert_error("多基因测定模式必须在分类列选择中选择具体分类列（不能选择'全部'）")
            return

        title_name = self.bulk_expr_ui.bulk_title_name.text().strip()
        title_size = self.bulk_expr_ui.bulk_title_size.value()
        ylabel_name = self.bulk_expr_ui.bulk_ylabel_name.text().strip()
        axis_size = self.bulk_expr_ui.bulk_axis_size.value()
        pairwise_size = self.bulk_expr_ui.bulk_pairwise_size.value()
        global_size = self.bulk_expr_ui.bulk_global_size.value()
        show_global = self.bulk_expr_ui.bulk_global_check.isChecked()
        show_insig = self.bulk_expr_ui.bulk_show_insig.isChecked()
        ns_replace = self.bulk_expr_ui.bulk_ns_replace.isChecked()
        star_replace = self.bulk_expr_ui.bulk_star_replace.isChecked()

        self.analysis.set_significance_options(show_insig, ns_replace, star_replace)

        if clinical_col == "全部":
            clinical_cols = self.analysis.all_clinical_columns.copy()
            print(f"[DEBUG] 使用analysis层的分类列列表: {clinical_cols}")
            selected_groups = []
            pairwise_groups = []
        else:
            clinical_cols = [clinical_col]
            selected_groups = []
            for i in range(self.bulk_expr_ui.bulk_group_list.count()):
                item = self.bulk_expr_ui.bulk_group_list.item(i)
                if item.isSelected():
                    selected_groups.append(item.text())
            if not selected_groups:
                self.func.alert_error("请在组别多选列表中至少选择一个组别")
                return

            pairwise_groups = []
            if self.bulk_expr_ui.bulk_pairwise_enable.isChecked():
                for item in self.bulk_expr_ui.bulk_pairwise_list.selectedItems():
                    pairwise_groups.append(item.text())

        filter1_col = None
        filter1_groups = []
        if self.bulk_expr_ui.bulk_filter1_enable.isChecked():
            filter1_col = self.bulk_expr_ui.bulk_filter1_combo.currentText()
            for i in range(self.bulk_expr_ui.bulk_filter1_list.count()):
                item = self.bulk_expr_ui.bulk_filter1_list.item(i)
                if item.isSelected():
                    filter1_groups.append(item.text())

        filter2_col = None
        filter2_groups = []
        if self.bulk_expr_ui.bulk_filter2_enable.isChecked():
            filter2_col = self.bulk_expr_ui.bulk_filter2_combo.currentText()
            for i in range(self.bulk_expr_ui.bulk_filter2_list.count()):
                item = self.bulk_expr_ui.bulk_filter2_list.item(i)
                if item.isSelected():
                    filter2_groups.append(item.text())

        try:
            genes_to_plot = multi_gene_list if multi_gene_mode else [gene_name]

            # 根据是否选择"全部"来决定绘图方式
            is_all_clinical = (clinical_col == "全部")

            if multi_gene_mode and is_all_clinical:
                self.func.alert_error("多基因测定模式必须在分类列选择中选择具体分类列（不能选择'全部'）")
                return

            self.func.log(f"正在处理 {len(genes_to_plot)} 个基因")

            # 根据是否选择"全部"来决定绘图方式
            if is_all_clinical:
                # 选择"全部"时，使用组合出图方法
                # 组合出图只支持单个基因
                if len(genes_to_plot) > 1:
                    self.func.alert_error("多基因测定模式必须在分类列选择中选择具体分类列（不能选择'全部'）")
                    return

                gene = genes_to_plot[0]
                self.func.log(f"正在处理基因: {gene}")

                figs = self.analysis.generate_combined_plots(
                    gene, clinical_cols, selected_groups,
                    title_name=None,  # 默认标题为基因名
                    title_size=title_size,
                    ylabel_name=ylabel_name,
                    axis_size=axis_size,
                    pairwise_size=pairwise_size,
                    global_size=global_size,
                    show_global=show_global,
                    pairwise_groups=pairwise_groups,
                    filter1_col=filter1_col if filter1_col else None,
                    filter1_groups=filter1_groups if filter1_groups else None,
                    filter2_col=filter2_col if filter2_col else None,
                    filter2_groups=filter2_groups if filter2_groups else None
                )

                # 检查是否有有效图表
                if not figs:
                    self.func.log(f"错误：未找到有效数据，请检查筛选条件")
                    self.func.alert_error("未找到有效数据，请检查筛选条件")
                    return

                # 显示组合图表
                if figs.get('violin_box'):
                    self.func.display_image(self.bulk_expr_ui.bulk_violin_box_label, figs['violin_box'])
                    self.func.log(f"  箱线小提琴图已生成")

                if figs.get('box'):
                    self.func.display_image(self.bulk_expr_ui.bulk_box_label, figs['box'])
                    self.func.log(f"  箱线图已生成")

                if figs.get('violin'):
                    self.func.display_image(self.bulk_expr_ui.bulk_violin_label, figs['violin'])
                    self.func.log(f"  小提琴图已生成")

            elif multi_gene_mode and len(genes_to_plot) > 1:
                # 多基因模式：使用多基因组合出图
                self.func.log(f"多基因组合出图模式，共 {len(genes_to_plot)} 个基因")

                # 生成三种多基因组合图
                for plot_type in ['violin_box', 'box', 'violin']:
                    result = self.analysis.generate_multi_gene_plots(
                        genes_to_plot, clinical_col, plot_type=plot_type,
                        title_size=title_size,
                        ylabel_name=ylabel_name,
                        axis_size=axis_size,
                        pairwise_size=pairwise_size,
                        global_size=global_size,
                        show_global=show_global,
                        pairwise_groups=pairwise_groups,
                        filter1_col=filter1_col if filter1_col else None,
                        filter1_groups=filter1_groups if filter1_groups else None,
                        filter2_col=filter2_col if filter2_col else None,
                        filter2_groups=filter2_groups if filter2_groups else None
                    )

                    if result and result.get('fig'):
                        if plot_type == 'violin_box':
                            self.func.display_image(self.bulk_expr_ui.bulk_violin_box_label, result['fig'])
                        elif plot_type == 'box':
                            self.func.display_image(self.bulk_expr_ui.bulk_box_label, result['fig'])
                        elif plot_type == 'violin':
                            self.func.display_image(self.bulk_expr_ui.bulk_violin_label, result['fig'])

                self.func.log(f"  多基因组合图已生成（{len(genes_to_plot)}个基因）")

            else:
                # 单基因模式：使用单独出图方法
                for gene in genes_to_plot:
                    self.func.log(f"正在处理基因: {gene}")

                    for col in clinical_cols:
                        fig = self.analysis.generate_violin_box_plot(
                            gene, col, selected_groups,
                            title_name=None,  # 默认标题为基因名
                            title_size=title_size,
                            ylabel_name=ylabel_name if len(genes_to_plot) == 1 else None,
                            axis_size=axis_size,
                            pairwise_size=pairwise_size,
                            pairwise_groups=pairwise_groups,
                            show_global=show_global,
                            global_size=global_size,
                            filter1_col=filter1_col if filter1_col else None,
                            filter1_groups=filter1_groups if filter1_groups else None,
                            filter2_col=filter2_col if filter2_col else None,
                            filter2_groups=filter2_groups if filter2_groups else None
                        )

                        if fig:
                            self.func.display_image(self.bulk_expr_ui.bulk_violin_box_label, fig)
                            self.func.log(f"  箱线小提琴图已生成: {gene}_{col}")

                    box_fig = self.analysis.generate_box_plot(
                        gene, clinical_col,
                        selected_groups,
                        title_name=None,  # 默认标题为基因名
                        title_size=title_size,
                        ylabel_name=ylabel_name if len(genes_to_plot) == 1 else None,
                        axis_size=axis_size,
                        pairwise_size=pairwise_size,
                        pairwise_groups=pairwise_groups,
                        show_global=show_global,
                        global_size=global_size,
                        filter1_col=filter1_col if filter1_col else None,
                        filter1_groups=filter1_groups if filter1_groups else None,
                        filter2_col=filter2_col if filter2_col else None,
                        filter2_groups=filter2_groups if filter2_groups else None
                    )

                    if box_fig:
                        self.func.display_image(self.bulk_expr_ui.bulk_box_label, box_fig)
                        self.func.log(f"  箱线图已生成: {gene}_{clinical_col}")

                    violin_fig = self.analysis.generate_violin_plot(
                        gene, clinical_col,
                        selected_groups,
                        title_name=None,  # 默认标题为基因名
                        title_size=title_size,
                        ylabel_name=ylabel_name if len(genes_to_plot) == 1 else None,
                        axis_size=axis_size,
                        pairwise_size=pairwise_size,
                        pairwise_groups=pairwise_groups,
                        show_global=show_global,
                        global_size=global_size,
                        filter1_col=filter1_col if filter1_col else None,
                        filter1_groups=filter1_groups if filter1_groups else None,
                        filter2_col=filter2_col if filter2_col else None,
                        filter2_groups=filter2_groups if filter2_groups else None
                    )

                    if violin_fig:
                        self.func.display_image(self.bulk_expr_ui.bulk_violin_label, violin_fig)
                        self.func.log(f"  小提琴图已生成: {gene}_{clinical_col}")

            self.func.log("绘图完成")
            self.func.alert_success("绘图完成")

        except ValueError as e:
            self.func.alert_error(str(e))
        except Exception as e:
            self.func.alert_failure(f"绘图失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")
            traceback.print_exc()

    def generate_gene_set_plots(self):
        """基因集分析出图"""
        if self.adata is None:
            self.func.alert_error("请先加载数据")
            return

        ui = self.bulk_expr_ui

        # 读 §2 四控件 → 取基因列表
        input_mode = ui.bulk_geneset_input_mode_combo.currentText()
        if input_mode == "手动输入":
            gene_list = parse_gene_set_from_text(ui.bulk_geneset_manual_input.toPlainText())
        else:
            gene_list, err = load_gene_set_from_file(ui.bulk_geneset_file_combo.currentText())
            if err:
                self.func.alert_error(err)
                return

        if not gene_list:
            self.func.alert_error("基因列表为空，请先输入或选择基因")
            return

        valid, invalid = resolve_gene_set(self.adata, gene_list)
        if not valid:
            self.func.alert_error("基因列表中没有任何基因存在于表达矩阵")
            return
        if invalid:
            self.func.log(f"以下 {len(invalid)} 个基因不存在于表达矩阵，已跳过: {', '.join(invalid)}")

        # 聚合方法 id
        method_idx = ui.bulk_geneset_method_combo.currentIndex()
        if 0 <= method_idx < len(GENE_SET_METHOD_IDS):
            method = GENE_SET_METHOD_IDS[method_idx]
        else:
            method = GENE_SET_METHOD_IDS[0]

        # 临床列 / 筛选 / 标题等参数（读 bulk_geneset_* 控件）
        clinical_col = ui.bulk_geneset_clinical_combo.currentText()
        if clinical_col == "全部":
            self.func.alert_error("基因集分析请选择具体分类列（不能选择'全部'）")
            return

        title_name = ui.bulk_geneset_title_name.text().strip()
        title_size = ui.bulk_geneset_title_size.value()
        ylabel_name = ui.bulk_geneset_ylabel_name.text().strip()
        axis_size = ui.bulk_geneset_axis_size.value()
        pairwise_size = ui.bulk_geneset_pairwise_size.value()
        global_size = ui.bulk_geneset_global_size.value()
        show_global = ui.bulk_geneset_global_check.isChecked()
        show_insig = ui.bulk_geneset_show_insig.isChecked()
        ns_replace = ui.bulk_geneset_ns_replace.isChecked()
        star_replace = ui.bulk_geneset_star_replace.isChecked()

        self.analysis.set_significance_options(show_insig, ns_replace, star_replace)

        selected_groups = []
        for i in range(ui.bulk_geneset_group_list.count()):
            item = ui.bulk_geneset_group_list.item(i)
            if item.isSelected():
                selected_groups.append(item.text())
        if not selected_groups:
            self.func.alert_error("请在组别多选列表中至少选择一个组别")
            return

        pairwise_groups = []
        if ui.bulk_geneset_pairwise_enable.isChecked():
            for item in ui.bulk_geneset_pairwise_list.selectedItems():
                pairwise_groups.append(item.text())

        filter1_col = None
        filter1_groups = []
        if ui.bulk_geneset_filter1_enable.isChecked():
            filter1_col = ui.bulk_geneset_filter1_combo.currentText()
            for i in range(ui.bulk_geneset_filter1_list.count()):
                item = ui.bulk_geneset_filter1_list.item(i)
                if item.isSelected():
                    filter1_groups.append(item.text())

        filter2_col = None
        filter2_groups = []
        if ui.bulk_geneset_filter2_enable.isChecked():
            filter2_col = ui.bulk_geneset_filter2_combo.currentText()
            for i in range(ui.bulk_geneset_filter2_list.count()):
                item = ui.bulk_geneset_filter2_list.item(i)
                if item.isSelected():
                    filter2_groups.append(item.text())

        try:
            self.func.log(f"基因集分析：{len(valid)} 个有效基因，聚合方法 {method}，分类列 {clinical_col}")

            figs = self.analysis.generate_gene_set_plots(
                valid, method, clinical_col,
                selected_groups=selected_groups,
                title_name=title_name or None,
                title_size=title_size,
                ylabel_name=ylabel_name or None,
                axis_size=axis_size,
                pairwise_size=pairwise_size,
                global_size=global_size,
                show_global=show_global,
                pairwise_groups=pairwise_groups,
                filter1_col=filter1_col if filter1_col else None,
                filter1_groups=filter1_groups if filter1_groups else None,
                filter2_col=filter2_col if filter2_col else None,
                filter2_groups=filter2_groups if filter2_groups else None
            )

            if not figs:
                self.func.log("错误：未找到有效数据，请检查筛选条件")
                self.func.alert_error("未找到有效数据，请检查筛选条件")
                return

            if figs.get('violin_box'):
                self.func.display_image(ui.bulk_geneset_violin_box_label, figs['violin_box'])
                self.func.log("  箱线小提琴图已生成")
            if figs.get('box'):
                self.func.display_image(ui.bulk_geneset_box_label, figs['box'])
                self.func.log("  箱线图已生成")
            if figs.get('violin'):
                self.func.display_image(ui.bulk_geneset_violin_label, figs['violin'])
                self.func.log("  小提琴图已生成")

            # 记录最近一次基因集数据，供CSV导出使用
            data_key = f"geneset_{method}_{clinical_col}_violin_box"
            if data_key in self.analysis.saved_data:
                self._geneset_export_data = self.analysis.saved_data[data_key]

            self.func.log("绘图完成")
            self.func.alert_success("绘图完成")

        except ValueError as e:
            self.func.alert_error(str(e))
        except RuntimeError as e:
            self.func.alert_error(str(e))
        except Exception as e:
            self.func.alert_failure(f"绘图失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")
            traceback.print_exc()

    def export_geneset_csv(self):
        """导出基因集分析数据CSV"""
        if self.adata is None:
            self.func.alert_error("请先加载数据")
            return

        df = getattr(self, '_geneset_export_data', None)
        if df is None or (hasattr(df, 'empty') and df.empty):
            self.func.alert_error("没有可导出的基因集数据，请先生成图表")
            return

        default_filename = f"{self.dataset_name}_geneset_data.csv" if hasattr(self, 'dataset_name') and self.dataset_name else "geneset_data.csv"
        file_path = self.func.get_save_file_path("导出CSV数据", default_filename, "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            df.to_csv(file_path, index=False)
            self.func.log(f"CSV已导出: {os.path.basename(file_path)}")
            self.func.alert_success(f"CSV导出完成\n{file_path}")
        except Exception as e:
            self.func.alert_failure(f"CSV导出失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    # ---------- 导出 ----------

    def export_csv(self):
        """导出CSV数据"""
        if self.adata is None:
            self.func.alert_error("请先加载数据")
            return

        gene_name = self.bulk_expr_ui.bulk_gene_input.text().strip()
        if not gene_name:
            self.func.alert_error("请输入基因名称")
            return

        clinical_col = self.bulk_expr_ui.bulk_clinical_combo.currentText()
        if clinical_col == "全部":
            clinical_col = self.analysis.get_obs_columns()[0] if self.analysis.get_obs_columns() else None

        if not clinical_col:
            self.func.alert_error("没有可用的分类列")
            return

        default_filename = f"{self.dataset_name}_{gene_name}_single_data.csv" if hasattr(self, 'dataset_name') and self.dataset_name else f"{gene_name}_{clinical_col}_data.csv"

        file_path = self.func.get_save_file_path("导出CSV数据", default_filename, "CSV Files (*.csv)")

        if not file_path:
            return

        try:
            csv_path = self.analysis.export_plot_data_csv(
                gene_name, clinical_col,
                save_path=file_path,
                filter1_col=self.bulk_expr_ui.bulk_filter1_combo.currentText() if self.bulk_expr_ui.bulk_filter1_enable.isChecked() else None,
                filter1_groups=[item.text() for item in self.bulk_expr_ui.bulk_filter1_list.selectedItems()] if self.bulk_expr_ui.bulk_filter1_enable.isChecked() else None,
                filter2_col=self.bulk_expr_ui.bulk_filter2_combo.currentText() if self.bulk_expr_ui.bulk_filter2_enable.isChecked() else None,
                filter2_groups=[item.text() for item in self.bulk_expr_ui.bulk_filter2_list.selectedItems()] if self.bulk_expr_ui.bulk_filter2_enable.isChecked() else None
            )

            if csv_path:
                self.func.log(f"CSV已导出: {os.path.basename(csv_path)}")
                self.func.alert_success(f"CSV导出完成\n{csv_path}")

        except Exception as e:
            self.func.alert_failure(f"CSV导出失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")

    def export_png(self):
        """导出PNG图片"""
        if not self.analysis.saved_figs:
            self.func.alert_error("没有可导出的图表，请先生成图表")
            return

        # 让用户选择保存路径
        default_filename = self.analysis.generate_default_filename('png')
        file_path = self.func.get_save_file_path("导出PNG图片", default_filename, "PNG Files (*.png)")

        if not file_path:
            return

        try:
            # 导出PNG
            saved_path = self.analysis.export_to_png(file_path)
            self.func.log(f"PNG已导出: {saved_path}")
            self.func.alert_success("PNG导出成功")
        except Exception as e:
            self.func.alert_failure(f"PNG导出失败: {str(e)}")
            self.func.log(f"❌ PNG导出失败: {str(e)}")

    def export_pdf(self):
        """导出PDF图片"""
        if not self.analysis.saved_figs:
            self.func.alert_error("没有可导出的图表，请先生成图表")
            return

        # 让用户选择保存路径
        default_filename = self.analysis.generate_default_filename('pdf')
        file_path = self.func.get_save_file_path("导出PDF图片", default_filename, "PDF Files (*.pdf)")

        if not file_path:
            return

        try:
            # 导出PDF
            saved_path = self.analysis.export_to_pdf(file_path)
            self.func.log(f"PDF已导出: {saved_path}")
            self.func.alert_success("PDF导出成功")
        except Exception as e:
            self.func.alert_failure(f"PDF导出失败: {str(e)}")
            self.func.log(f"❌ PDF导出失败: {str(e)}")
