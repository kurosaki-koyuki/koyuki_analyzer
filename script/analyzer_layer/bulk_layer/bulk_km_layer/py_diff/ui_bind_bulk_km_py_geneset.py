# -*- coding: utf-8 -*-
"""
bulk KM曲线基因集分析界面功能绑定脚本（Python版） - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
是 ui_bind_bulk_km_py.py 单基因链路的「基因集」近副本：核心 generate_gene_set_km_plot()
读 §2 四控件 → 取基因列表 → resolve → prepare_gene_set_km_data → split_groups → draw_km_plot。
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.bulk_layer.bulk_km_layer.py_diff.bulk_km_py_analysis import BulkKmPyAnalysis
from script.analyzer_layer.bulk_layer.bulk_km_layer.py_diff.ui_func_bulk_km_py import BulkKmPyFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.bulk_layer.bulk_gene_set_utils import (
    GENE_SET_METHODS,
    load_gene_set_from_file, parse_gene_set_from_text, resolve_gene_set,
)
import re


class _GeneSetUIAlias:
    """把 BulkKmPyFunc 硬编码的 bulk_km_* 属性名映射到基因集页的 bulk_km_geneset_*。

    BulkKmPyFunc 内部写死 self.bulk_km_ui.bulk_km_XXX；基因集页控件都叫
    bulk_km_geneset_XXX。这里做一层只读映射即可 100% 复用（不改 ui_func_bulk_km_py.py）。
    """
    def __init__(self, ui):
        object.__setattr__(self, '_ui', ui)

    def _map(self, name):
        if name.startswith('bulk_km_') and not name.startswith('bulk_km_geneset_'):
            return 'bulk_km_geneset_' + name[len('bulk_km_'):]
        return name

    def __getattr__(self, name):
        ui = object.__getattribute__(self, '_ui')
        return getattr(ui, self._map(name))

    def __setattr__(self, name, value):
        ui = object.__getattribute__(self, '_ui')
        setattr(ui, self._map(name), value)


class BulkKmPyGeneSetFunc(BulkKmPyFunc):
    """基因集页前端功能类：复用 BulkKmPyFunc，仅把 bulk_km_* 属性映射到 bulk_km_geneset_*。"""
    def __init__(self, bulk_km_ui, parent_widget=None):
        super().__init__(_GeneSetUIAlias(bulk_km_ui), parent_widget)


class BulkKmPyGeneSetBind:
    """bulk KM曲线基因集分析功能绑定类"""

    def __init__(self, parent_window, bulk_km_ui):
        self.parent = parent_window
        self.bulk_km_ui = bulk_km_ui
        self.analysis = BulkKmPyAnalysis()
        self.func = BulkKmPyGeneSetFunc(bulk_km_ui, parent_window)
        self.func.analysis = self.analysis  # 引用analysis到func
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.all_fig_paths = []
        self.all_km_data = []
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_bulk_km_functions()
        self.bind_navigation()
        self._on_gene_set_input_mode_changed()  # 进页面时执行一次互斥状态

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.bulk_km_ui, 'btn_back_bulk_km_geneset'):
            self.bulk_km_ui.btn_back_bulk_km_geneset.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.bulk_km_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.bulk_km_ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def bind_bulk_km_functions(self):
        """绑定bulk KM基因集功能信号"""
        log_widget = getattr(self.bulk_km_ui, 'bulk_km_geneset_status_text', None)

        # 基因集输入模式互斥
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_input_mode_combo'):
            self.bulk_km_ui.bulk_km_geneset_input_mode_combo.currentIndexChanged.connect(self._on_gene_set_input_mode_changed)

        # 分类列选择下拉框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_clinical_combo'):
            self.bulk_km_ui.bulk_km_geneset_clinical_combo.currentIndexChanged.connect(self.on_clinical_changed)

        # 筛选1启用复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_filter1_enable'):
            self.bulk_km_ui.bulk_km_geneset_filter1_enable.stateChanged.connect(self.on_filter1_enabled)

        # 筛选1下拉框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_filter1_combo'):
            self.bulk_km_ui.bulk_km_geneset_filter1_combo.currentIndexChanged.connect(self.on_filter1_combo_changed)

        # 筛选2启用复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_filter2_enable'):
            self.bulk_km_ui.bulk_km_geneset_filter2_enable.stateChanged.connect(self.on_filter2_enabled)

        # 筛选2下拉框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_filter2_combo'):
            self.bulk_km_ui.bulk_km_geneset_filter2_combo.currentIndexChanged.connect(self.on_filter2_combo_changed)

        # 显示风险表格复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_show_table_check'):
            self.bulk_km_ui.bulk_km_geneset_show_table_check.stateChanged.connect(self.on_table_check_changed)

        # 出图尺寸输入框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_plot_width_input'):
            self.bulk_km_ui.bulk_km_geneset_plot_width_input.textChanged.connect(self.on_plot_size_changed)
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_plot_height_input'):
            self.bulk_km_ui.bulk_km_geneset_plot_height_input.textChanged.connect(self.on_plot_size_changed)

        # 导出尺寸输入框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_export_width'):
            self.bulk_km_ui.bulk_km_geneset_export_width.textChanged.connect(self.on_export_size_changed)
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_export_height'):
            self.bulk_km_ui.bulk_km_geneset_export_height.textChanged.connect(self.on_export_size_changed)

        # 两两比较启用复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_pairwise_enable'):
            self.bulk_km_ui.bulk_km_geneset_pairwise_enable.stateChanged.connect(self.on_pairwise_enable_changed)

        # 生成KM曲线按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_btn_plot'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_geneset_btn_plot, self.generate_gene_set_km_plot,
                                   log_widget, "绘图完成", "绘图失败")

        # 导出PNG按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_btn_export_png'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_geneset_btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        # 导出PDF按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_btn_export_pdf'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_geneset_btn_export_pdf, self.export_pdf,
                                   log_widget, "PDF导出完成", "PDF导出失败")

        # 导出SVG按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_btn_export_svg'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_geneset_btn_export_svg, self.export_svg,
                                   log_widget, "SVG导出完成", "SVG导出失败")

        # 导出CSV按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_btn_export_csv'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_geneset_btn_export_csv, self.export_csv,
                                   log_widget, "CSV导出完成", "CSV导出失败")

    # ---------- 基因集输入模式互斥（§2） ----------

    def _on_gene_set_input_mode_changed(self):
        """输入模式切换互斥：外部列表 ⇔ 手动输入"""
        mode = self.bulk_km_ui.bulk_km_geneset_input_mode_combo.currentText()
        if mode == "手动输入":
            self.bulk_km_ui.bulk_km_geneset_file_combo.setEnabled(False)
            self.bulk_km_ui.bulk_km_geneset_manual_input.setEnabled(True)
        else:
            # 外部列表：有文件才启用（空则保持禁用，见 §2「空则禁用」）
            has_files = self.bulk_km_ui.bulk_km_geneset_file_combo.count() > 0
            self.bulk_km_ui.bulk_km_geneset_file_combo.setEnabled(has_files)
            self.bulk_km_ui.bulk_km_geneset_manual_input.setEnabled(False)

    # ---------- 页面导航 ----------

    def go_to_home(self):
        """返回主页"""
        page_intersect.go_to_home()

    # ---------- 数据加载 ----------

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

        self.analysis.set_dataset_output_dir(self.dataset_output_dir)
        self.analysis.set_dataset_name(self.dataset_name)

        if 'time' not in self.adata.obs.columns and 'time (month)' not in self.adata.obs.columns:
            self.adata = None
            self.analysis.set_adata(None)
            self.func.log("这个数据集不能做生存曲线，因为缺少time或time (month)列")
            return

        n_samples, n_genes = adata.shape
        obs_columns = self.analysis.get_obs_columns()

        self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")
        self.func.log(f"样本数: {n_samples}")
        self.func.log(f"基因数: {n_genes}")
        self.func.log(f"可用注释列: {len(obs_columns)} 个")

        self.func.update_clinical_combo(obs_columns)
        self.func.update_hint_text(self.dataset_name, n_samples, n_genes)
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()

    # ---------- 分类列选择 ----------

    def on_clinical_changed(self):
        """分类列选择改变"""
        selected_col = self.bulk_km_ui.bulk_km_geneset_clinical_combo.currentText()

        self.bulk_km_ui.bulk_km_geneset_pairwise_list.clear()

        if self.adata is None:
            self.func.hide_group_list()
            self.func.enable_pairwise_controls(False)
            return

        if selected_col == "全部":
            self.bulk_km_ui.bulk_km_geneset_show_global_check.setChecked(True)
            self.bulk_km_ui.bulk_km_geneset_pairwise_enable.setChecked(False)
            self.bulk_km_ui.bulk_km_geneset_pairwise_list.clear()
            self.bulk_km_ui.bulk_km_geneset_pairwise_list.addItem("High vs Low")
            self.bulk_km_ui.bulk_km_geneset_pairwise_list.selectAll()

            self.func.show_clinical_col_list(False)
            self.func.enable_pairwise_controls(False)
        else:
            self.bulk_km_ui.bulk_km_geneset_show_global_check.setChecked(False)
            self.bulk_km_ui.bulk_km_geneset_pairwise_enable.setChecked(True)

            groups = self.analysis.get_obs_unique_values(selected_col)
            self.func.update_group_list(groups)

            self.bulk_km_ui.bulk_km_geneset_pairwise_list.clear()
            for g in groups:
                self.bulk_km_ui.bulk_km_geneset_pairwise_list.addItem(f"{g} High vs Low")
            self.bulk_km_ui.bulk_km_geneset_pairwise_list.selectAll()

    # ---------- 筛选控件 ----------

    def on_filter1_enabled(self, state):
        """筛选1启用状态改变"""
        enabled = state == Qt.Checked
        self.func.on_filter1_enabled(enabled)

        if enabled and self.adata is not None:
            columns = self.analysis.get_obs_columns()
            self.func.update_filter_combo(self.bulk_km_ui.bulk_km_geneset_filter1_combo, columns)

    def on_filter1_combo_changed(self):
        """筛选1下拉框改变"""
        filter1_col = self.bulk_km_ui.bulk_km_geneset_filter1_combo.currentText()
        if filter1_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter1_col)
            self.func.update_filter_list(self.bulk_km_ui.bulk_km_geneset_filter1_list, groups)

    def on_filter2_enabled(self, state):
        """筛选2启用状态改变"""
        enabled = state == Qt.Checked
        self.func.on_filter2_enabled(enabled)

        if enabled and self.adata is not None:
            columns = self.analysis.get_obs_columns()
            self.func.update_filter_combo(self.bulk_km_ui.bulk_km_geneset_filter2_combo, columns)

    def on_filter2_combo_changed(self):
        """筛选2下拉框改变"""
        filter2_col = self.bulk_km_ui.bulk_km_geneset_filter2_combo.currentText()
        if filter2_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter2_col)
            self.func.update_filter_list(self.bulk_km_ui.bulk_km_geneset_filter2_list, groups)

    def on_table_check_changed(self, state):
        """显示风险表格选项变化时更新出图尺寸"""
        self.func.on_table_check_changed(state)

    def on_plot_size_changed(self):
        """出图尺寸变化时同步到导出尺寸"""
        plot_width = self.bulk_km_ui.bulk_km_geneset_plot_width_input.text().strip()
        plot_height = self.bulk_km_ui.bulk_km_geneset_plot_height_input.text().strip()
        if plot_width and plot_width.replace('.', '').isdigit():
            self.func.sync_plot_size_to_export(float(plot_width), float(plot_height) if plot_height.replace('.', '').isdigit() else 6)

    def on_export_size_changed(self):
        """导出尺寸变化时同步到出图尺寸"""
        export_width = self.bulk_km_ui.bulk_km_geneset_export_width.text().strip()
        export_height = self.bulk_km_ui.bulk_km_geneset_export_height.text().strip()
        if export_width and export_width.replace('.', '').isdigit():
            self.func.sync_export_size_to_plot(float(export_width), float(export_height) if export_height.replace('.', '').isdigit() else 6)

    def on_pairwise_enable_changed(self, state):
        """两两比较启用状态改变"""
        enabled = state == Qt.Checked
        self.bulk_km_ui.bulk_km_geneset_pairwise_list.setEnabled(enabled)

    # ---------- 基因集KM绘图 ----------

    def generate_gene_set_km_plot(self):
        """生成基因集KM曲线"""
        if self.adata is None:
            self.func.alert_error("请先加载数据")
            return

        # 1. 读 §2 四控件取基因列表
        mode = self.bulk_km_ui.bulk_km_geneset_input_mode_combo.currentText()
        if mode == "手动输入":
            text = self.bulk_km_ui.bulk_km_geneset_manual_input.toPlainText()
            gene_list = parse_gene_set_from_text(text)
        else:
            file_name = self.bulk_km_ui.bulk_km_geneset_file_combo.currentText()
            gene_list, err = load_gene_set_from_file(file_name)
            if err:
                self.func.alert_error(err)
                return

        # ★ 自定义注释/标签：默认 "genelist"，**不用文件名**（用户要求 2026-09）。
        #   该标签作为出图图例标题（`{label} expression level`）与输出文件名前缀。
        label_raw = ""
        if hasattr(self.bulk_km_ui, 'bulk_km_geneset_label_input'):
            label_raw = self.bulk_km_ui.bulk_km_geneset_label_input.text().strip()
        label = re.sub(r'[^\w.\-]+', '_', label_raw or "genelist").strip('_.') or "genelist"

        if not gene_list:
            self.func.alert_error("基因列表为空，请选择外部列表文件或手动输入基因")
            return

        # 聚合方法（currentIndex 对齐 GENE_SET_METHODS 顺序）
        method_idx = self.bulk_km_ui.bulk_km_geneset_method_combo.currentIndex()
        if method_idx < 0 or method_idx >= len(GENE_SET_METHODS):
            self.func.alert_error("请选择聚合方法")
            return
        method = GENE_SET_METHODS[method_idx][0]

        # 2. resolve 到矩阵
        valid, invalid = resolve_gene_set(self.adata, gene_list)
        if not valid:
            self.func.alert_error("基因列表中没有任何基因存在于表达矩阵")
            return
        self.func.log(f"基因集匹配: {len(valid)}/{len(gene_list)} 个基因可用")
        if invalid:
            self.func.log(f"以下基因不存在于数据集中，已跳过 ({len(invalid)} 个): {', '.join(invalid[:20])}")

        gs_ident = label

        # 3. 时间单位 + 参数
        time_unit = self.func.get_time_unit()
        params = self.func.get_plot_params()
        time_label = 'Time (months)' if time_unit == 'month' else 'Time (days)'

        self.func.log("正在生成基因集KM曲线...")

        try:
            # 4. 准备基因集数据
            df = self.analysis.prepare_gene_set_km_data(valid, method, time_unit)
            if df is None:
                self.func.alert_error("基因集数据准备失败（有效样本数不足或缺少生存列）")
                return

            # 5. 筛选
            filter1_col = None
            filter1_groups = []
            if self.bulk_km_ui.bulk_km_geneset_filter1_enable.isChecked():
                filter1_col = self.bulk_km_ui.bulk_km_geneset_filter1_combo.currentText()
                filter1_groups = self.func.get_filter1_groups()

            filter2_col = None
            filter2_groups = []
            if self.bulk_km_ui.bulk_km_geneset_filter2_enable.isChecked():
                filter2_col = self.bulk_km_ui.bulk_km_geneset_filter2_combo.currentText()
                filter2_groups = self.func.get_filter2_groups()

            df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
            if df is None or len(df) < 10:
                self.func.alert_error("筛选后样本数太少，无法分析")
                return

            # 6. 分组
            clinical_col = self.func.get_clinical_col()
            if clinical_col == "全部":
                df, n_high, n_low = self.analysis.split_groups_simple(df)
                self.func.log(f"  样本数: {len(df)}, High: {n_high}, Low: {n_low}")
            else:
                selected_groups = self.func.get_selected_groups()
                df = self.analysis.split_groups_by_clinical(df, clinical_col, selected_groups)
                if len(df) == 0:
                    self.func.alert_error("没有足够的样本进行分析")
                    return
                for g in sorted(df['group'].unique()):
                    self.func.log(f"  - {g}: {len(df[df['group'] == g])}")

            # 7. 标题 + 画图（用户要求：只写数据集名）
            title = self.func.get_title(self.dataset_name)
            self.analysis.current_km_df = df

            fig_path = self.analysis.draw_km_plot(
                df,
                time_label=time_label,
                title=title,
                title_size=params['title_size'],
                legend_size=params['legend_size'],
                axis_size=params['axis_size'],
                pval_size=params['pval_size'],
                show_table=params['show_table'],
                table_size=params['table_size'],
                show_ci=params['show_ci'],
                show_n=params['show_n'],
                pval_mode=params['pval_mode'],
                show_global_pval=params['show_global_pval'],
                show_pairwise=params['show_pairwise'],
                selected_pairwise=params['selected_pairwise'],
                gene_name=gs_ident,
                export_width=params['plot_width'],
                export_height=params['plot_height']
            )

            self.all_fig_paths = [fig_path]
            self.all_km_data = [(gs_ident, df.copy())]

            self.func.display_image(self.bulk_km_ui.bulk_km_geneset_label, fig_path)
            self.func.log("基因集KM曲线生成完成")

        except Exception as e:
            self.func.log(f"绘图失败: {str(e)}")
            self.func.alert_failure(f"绘图失败: {str(e)}")
            traceback.print_exc()

    # ---------- 导出 ----------

    def export_png(self):
        """导出PNG"""
        if not self.all_fig_paths:
            self.func.alert_error("请先生成KM曲线")
            return

        gene_name = self.all_km_data[0][0] if self.all_km_data else self.dataset_name
        save_path = self.func.get_save_file_path(
            "导出PNG",
            f"{gene_name}_{self.dataset_name}_km.png",
            "PNG Files (*.png)"
        )

        if save_path:
            result = self.analysis.export_png(save_path)
            if result:
                self.func.alert_success(f"PNG导出成功: {result}")
            else:
                self.func.alert_failure("PNG导出失败")

    def export_pdf(self):
        """导出PDF"""
        if not self.all_fig_paths:
            self.func.alert_error("请先生成KM曲线")
            return

        gene_name = self.all_km_data[0][0] if self.all_km_data else self.dataset_name
        save_path = self.func.get_save_file_path(
            "导出PDF",
            f"{gene_name}_{self.dataset_name}_km.pdf",
            "PDF Files (*.pdf)"
        )

        if save_path:
            result = self.analysis.export_pdf(save_path)
            if result:
                self.func.alert_success(f"PDF导出成功: {result}")
            else:
                self.func.alert_failure("PDF导出失败")

    def export_svg(self):
        """导出SVG"""
        if not self.all_fig_paths:
            self.func.alert_error("请先生成KM曲线")
            return

        gene_name = self.all_km_data[0][0] if self.all_km_data else self.dataset_name
        save_path = self.func.get_save_file_path(
            "导出SVG",
            f"{gene_name}_{self.dataset_name}_km.svg",
            "SVG Files (*.svg)"
        )

        if save_path:
            result = self.analysis.export_svg(save_path)
            if result:
                self.func.alert_success(f"SVG导出成功: {result}")
            else:
                self.func.alert_failure("SVG导出失败")

    def export_csv(self):
        """导出CSV"""
        if not self.all_km_data:
            self.func.alert_error("请先生成KM曲线")
            return

        gene_name = self.all_km_data[0][0] if self.all_km_data else self.dataset_name
        save_path = self.func.get_save_file_path(
            "导出CSV",
            f"{gene_name}_{self.dataset_name}_km_data.csv",
            "CSV Files (*.csv)"
        )

        if save_path:
            result = self.analysis.export_csv(save_path)
            if result:
                self.func.alert_success(f"CSV导出成功: {result}")
            else:
                self.func.alert_failure("CSV导出失败")
