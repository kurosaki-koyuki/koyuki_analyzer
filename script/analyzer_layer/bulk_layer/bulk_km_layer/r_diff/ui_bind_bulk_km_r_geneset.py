# -*- coding: utf-8 -*-
"""
bulk KM曲线 R模式 基因集分析 界面绑定脚本
近副本 ui_bind_bulk_km_r.py 的「单基因 R 链路」：读契约 §2 四控件 → 取基因列表 → resolve →
analysis.prepare_gene_set_km_data → filter → split_groups_simple(或 by_clinical) →
analysis.draw_km_plot_r(...) → display_image。复合分在 Python 端由 analysis 层算好（复用
bulk_gene_set_utils.compute_gene_set_score），R 脚本 bulk_km_r.R 不碰。

参考契约：docs/features/bulk_gene_set_analysis_contract.md §2 / §4c
"""

from script.utils_layer.import_config import os, traceback, pd
import re

from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.bulk_km_r_analysis import get_bulk_km_r_analysis
from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.ui_func_bulk_km_r import BulkKmRFunc
from script.analyzer_layer.bulk_layer.bulk_gene_set_utils import (
    GENE_SET_METHODS, GENE_SET_METHOD_IDS, DEFAULT_GENE_SET_METHOD,
    load_gene_set_from_file, parse_gene_set_from_text, resolve_gene_set,
)
from script.mods_layer.emoji_function_for_mods import happy, wrong
from script.utils_layer.page_intersect import page_intersect


class _GenesetUiAdapter:
    """把 bulk_km_geneset_* 控件名映射成 BulkKmRFunc 期望的 bulk_km_* 名。

    BulkKmRFunc（ui_func_bulk_km_r.py）内部全部通过 self.bulk_km_r_ui.bulk_km_xxx 访问控件；
    基因集页控件统一叫 bulk_km_geneset_xxx。本适配器只把前缀 bulk_km_ 重写为 bulk_km_geneset_，
    从而**原样复用** BulkKmRFunc（不复制其逻辑，单一真相源）。r_version_label 等同名属性原样透传。
    """

    def __init__(self, geneset_ui):
        object.__setattr__(self, '_ui', geneset_ui)

    def __getattr__(self, name):
        ui = object.__getattribute__(self, '_ui')
        if name.startswith('bulk_km_') and not name.startswith('bulk_km_geneset_'):
            mapped = 'bulk_km_geneset_' + name[len('bulk_km_'):]
            return getattr(ui, mapped)
        return getattr(ui, name)


class BulkKmRGeneSetBind:
    """bulk KM曲线 R模式 基因集分析绑定类"""

    def __init__(self, parent_widget, bulk_km_r_geneset_ui):
        self.parent = parent_widget
        self.bulk_km_r_ui = bulk_km_r_geneset_ui
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.analysis = get_bulk_km_r_analysis()
        self.func = BulkKmRFunc(_GenesetUiAdapter(bulk_km_r_geneset_ui), parent_widget)
        self.func.analysis = self.analysis  # 引用analysis到func
        self.current_km_fig_path = None
        self._last_km_df = None      # 最近一次成功出图后的分组 df（导出/复绘用）
        self._last_km_label = None   # 最近一次出图的标签（geneset(N genes)）
        self._bind_signals()
        self._init_page()

    def _bind_signals(self):
        """绑定按钮点击信号"""
        # 返回按钮（子页返回按钮已移除，统一走容器导航栏 nav_btn_back）
        if hasattr(self.bulk_km_r_ui, 'btn_back'):
            self.bulk_km_r_ui.btn_back.clicked.connect(self.on_back_clicked)

        # 生成KM曲线按钮
        self.bulk_km_r_ui.bulk_km_geneset_btn_plot.clicked.connect(self.generate_gene_set_km_plot)

        # 导出按钮
        self.bulk_km_r_ui.bulk_km_geneset_btn_export_png.clicked.connect(self.on_export_png)
        self.bulk_km_r_ui.bulk_km_geneset_btn_export_pdf.clicked.connect(self.on_export_pdf)
        self.bulk_km_r_ui.bulk_km_geneset_btn_export_svg.clicked.connect(self.on_export_svg)
        self.bulk_km_r_ui.bulk_km_geneset_btn_export_csv.clicked.connect(self.on_export_csv)

        # Debug按钮
        self.bulk_km_r_ui.bulk_km_geneset_debug_btn.clicked.connect(self.on_debug_clicked)

        # 基因集输入方式互斥（外部列表 / 手动输入）
        self.bulk_km_r_ui.bulk_km_geneset_input_mode_combo.currentIndexChanged.connect(
            self._on_gene_set_input_mode_changed)

        # 分类列选择变化
        self.bulk_km_r_ui.bulk_km_geneset_clinical_combo.currentIndexChanged.connect(self.on_clinical_combo_changed)

        # 筛选1启用
        self.bulk_km_r_ui.bulk_km_geneset_filter1_enable.stateChanged.connect(self.on_filter1_enable_changed)
        self.bulk_km_r_ui.bulk_km_geneset_filter1_combo.currentIndexChanged.connect(self.on_filter1_col_changed)

        # 筛选2启用
        self.bulk_km_r_ui.bulk_km_geneset_filter2_enable.stateChanged.connect(self.on_filter2_enable_changed)
        self.bulk_km_r_ui.bulk_km_geneset_filter2_combo.currentIndexChanged.connect(self.on_filter2_col_changed)

        # 组间比较启用
        self.bulk_km_r_ui.bulk_km_geneset_pairwise_enable.stateChanged.connect(self.on_pairwise_enable_changed)

        # 显示风险表格
        self.bulk_km_r_ui.bulk_km_geneset_show_table_check.stateChanged.connect(self.on_show_table_changed)

        # 尺寸同步
        self.bulk_km_r_ui.bulk_km_geneset_plot_width_input.textChanged.connect(self._sync_plot_width_to_export)
        self.bulk_km_r_ui.bulk_km_geneset_plot_height_input.textChanged.connect(self._sync_plot_height_to_export)
        self.bulk_km_r_ui.bulk_km_geneset_export_width.textChanged.connect(self._sync_export_width_to_plot)
        self.bulk_km_r_ui.bulk_km_geneset_export_height.textChanged.connect(self._sync_export_height_to_plot)

    def _init_page(self):
        """初始化页面"""
        self.func.log_set_default()
        self.func.update_r_version_label()
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()

        # 互斥状态：进页面也执行一次
        self._on_gene_set_input_mode_changed()

        # 设置默认字体大小
        if hasattr(self.bulk_km_r_ui, 'bulk_km_geneset_pvalsize_input'):
            self.bulk_km_r_ui.bulk_km_geneset_pvalsize_input.setText('5')
        if hasattr(self.bulk_km_r_ui, 'bulk_km_geneset_tablesize_input'):
            self.bulk_km_r_ui.bulk_km_geneset_tablesize_input.setText('5')
        if hasattr(self.bulk_km_r_ui, 'bulk_km_geneset_axissize_input'):
            self.bulk_km_r_ui.bulk_km_geneset_axissize_input.setText('14')

    # ---------- 基因集输入 ----------

    def _on_gene_set_input_mode_changed(self, index=None):
        """互斥：外部列表 ⇔ file 启用/manual 禁用；手动输入 ⇔ 反之（契约 §2 硬性要求）"""
        mode = self.bulk_km_r_ui.bulk_km_geneset_input_mode_combo.currentText()
        is_file = (mode == "外部列表")
        file_combo = self.bulk_km_r_ui.bulk_km_geneset_file_combo
        manual_input = self.bulk_km_r_ui.bulk_km_geneset_manual_input
        if is_file:
            file_combo.setEnabled(file_combo.count() > 0)
            manual_input.setEnabled(False)
        else:
            file_combo.setEnabled(False)
            manual_input.setEnabled(True)

    def _get_gene_set_input(self):
        """读 §2 四控件 → (gene_list, method_id, error)"""
        input_mode = self.bulk_km_r_ui.bulk_km_geneset_input_mode_combo.currentText()
        if input_mode == "手动输入":
            text = self.bulk_km_r_ui.bulk_km_geneset_manual_input.toPlainText()
            gene_list = parse_gene_set_from_text(text)
        else:
            file_name = self.bulk_km_r_ui.bulk_km_geneset_file_combo.currentText()
            gene_list, err = load_gene_set_from_file(file_name)
            if err:
                return [], DEFAULT_GENE_SET_METHOD, err

        if not gene_list:
            return [], DEFAULT_GENE_SET_METHOD, "基因列表为空，请先选择文件或输入基因"

        method_idx = self.bulk_km_r_ui.bulk_km_geneset_method_combo.currentIndex()
        if method_idx is None or method_idx < 0 or method_idx >= len(GENE_SET_METHOD_IDS):
            method = DEFAULT_GENE_SET_METHOD
        else:
            method = GENE_SET_METHOD_IDS[method_idx]
        return gene_list, method, ""

    # ---------- 主流程 ----------

    def generate_gene_set_km_plot(self):
        """生成基因集KM曲线（R模式）"""
        try:
            self.func.log("正在生成基因集KM曲线...")

            if self.adata is None:
                self.func.alert_error("数据未加载")
                return

            # 检查R环境
            if not self.analysis.is_available():
                r_version = self.analysis.get_r_version()
                self.func.alert_error(f"R环境不可用，无法生成曲线\n{r_version}")
                return

            self.func.log(f"R版本: {self.analysis.get_r_version()}")

            # 1. 读 §2 四控件，取基因列表
            gene_list, method, err = self._get_gene_set_input()
            if err:
                self.func.alert_error(err)
                return

            # 2. 解析到表达矩阵
            valid, invalid = resolve_gene_set(self.adata, gene_list)
            if not valid:
                self.func.alert_error("基因列表中没有任何基因存在于表达矩阵")
                return
            if invalid:
                self.func.log(f"以下基因不在表达矩阵中，已跳过（共 {len(invalid)} 个）: {', '.join(invalid)}")

            time_unit = self.func.get_time_unit()

            # 3. 准备基因集KM数据（复合分已在 Python 端算好，塞进 expression 列）
            df = self.analysis.prepare_gene_set_km_data(valid, method, time_unit)
            if df is None:
                self.func.alert_error("基因集KM数据准备失败（时间列缺失或有效样本数不足10）")
                return

            # 4. 筛选
            filter1_col = self.bulk_km_r_ui.bulk_km_geneset_filter1_combo.currentText() if self.bulk_km_r_ui.bulk_km_geneset_filter1_enable.isChecked() else None
            filter1_groups = self.func.get_filter1_groups() if filter1_col else None
            filter2_col = self.bulk_km_r_ui.bulk_km_geneset_filter2_combo.currentText() if self.bulk_km_r_ui.bulk_km_geneset_filter2_enable.isChecked() else None
            filter2_groups = self.func.get_filter2_groups() if filter2_col else None

            df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
            if df is None or len(df) < 10:
                self.func.alert_error("筛选后数据不足")
                return

            # 5. 分组
            clinical_col = self.func.get_clinical_col()
            if clinical_col != "全部":
                selected_groups = self.func.get_selected_groups()
                grouped_list = self.analysis.split_groups_by_clinical(df, clinical_col, selected_groups)
                if isinstance(grouped_list, list):
                    if len(grouped_list) == 0:
                        self.func.alert_error("分组后数据不足")
                        return
                    df = pd.concat(grouped_list, ignore_index=True)
                else:
                    df = grouped_list
                if not hasattr(df, 'columns') or 'group' not in df.columns:
                    self.func.alert_error("分组数据缺少group列")
                    return
            else:
                df, n_high, n_low = self.analysis.split_groups_simple(df)
                if df is None:
                    self.func.alert_error("数据分组失败")
                    return
                self.func.log(f"基因集复合分中位数分组: High={n_high}, Low={n_low}")

            # 6. 出图（自定义注释/标签默认 "genelist"，不用文件名/泛称）
            label_raw = ""
            if hasattr(self.bulk_km_r_ui, 'bulk_km_geneset_label_input'):
                label_raw = self.bulk_km_r_ui.bulk_km_geneset_label_input.text().strip()
            label = re.sub(r'[^\w.\-]+', '_', label_raw or "genelist").strip('_.') or "genelist"
            gene_name = label
            title = self.func.get_title(self.dataset_name)
            output_path = os.path.join(self.dataset_output_dir or ".", f"{label}_{self.dataset_name}_km.png")
            plot_params = self.func.get_plot_params()

            self.analysis.draw_km_plot_r(
                df, 'time', 'state', 'group', gene_name,
                output_path=output_path, title=title,
                show_risk_table=plot_params.get('show_table', True),
                plot_width=plot_params.get('plot_width', 6),
                plot_height=plot_params.get('plot_height', 8),
                pval_mode=plot_params.get('pval_mode', 0),
                title_font_size=plot_params.get('title_size', 14),
                axis_font_size=plot_params.get('axis_size', 12),
                legend_font_size=plot_params.get('legend_size', 12),
                pval_font_size=plot_params.get('pval_size', 5),
                risk_table_font_size=plot_params.get('table_size', 5),
                show_conf_int=plot_params.get('show_ci', False),
                show_n=plot_params.get('show_n', True),
                show_global_pval=plot_params.get('show_global_pval', True),
                show_pairwise=plot_params.get('show_pairwise', False),
                selected_pairwise=plot_params.get('selected_pairwise', [])
            )

            self.current_km_fig_path = output_path
            self._last_km_df = df
            self._last_km_label = gene_name
            self.func.display_image(self.bulk_km_r_ui.bulk_km_geneset_label, output_path)
            self.func.log(f"基因集({len(valid)} genes) KM曲线(R模式)生成成功")

        except Exception as e:
            self.func.log(f"R绘图失败: {str(e)}")
            debug_log = self.analysis.get_r_debug_log()
            if debug_log:
                self.func.log(f"[R_DEBUG] 当前已累计 {len(debug_log)} 个R交互错误:")
                for i, entry in enumerate(debug_log[-3:], max(1, len(debug_log) - 2)):
                    self.func.log(f"  错误{i}: {entry['operation']} -> {entry['error_type']}: {entry['error_message'][:80]}...")
            traceback.print_exc()
            self.func.alert_error(f"R绘图失败: {str(e)}")

    # ---------- 数据同步 ----------

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据（含 time/state 列校验）"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return

        adata = bulk_top_bind.analysis.adata
        if adata is None:
            self.func.log("bulk主页未加载数据")
            return

        # 校验 time/state 列
        obs_cols = set(adata.obs.columns)
        if 'state' not in obs_cols:
            self.func.log("错误: 数据缺少 state 列，无法进行KM分析")
            return
        if 'time' not in obs_cols and 'time (month)' not in obs_cols:
            self.func.log("错误: 数据缺少 time / time (month) 列，无法进行KM分析")
            return

        self.adata = adata
        self.analysis.set_adata(adata)
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir

        self.analysis.set_dataset_output_dir(self.dataset_output_dir)
        self.analysis.set_dataset_name(self.dataset_name)

        self.func.log_set_default()
        self.func.update_r_version_label()
        self.func.update_clinical_combo(self.analysis.get_obs_columns())
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()
        self._on_gene_set_input_mode_changed()

    def on_back_clicked(self):
        """返回主页"""
        page_intersect.go_to_page_with_bind('bulk_top_page')

    # ---------- 交互回调 ----------

    def on_clinical_combo_changed(self, index):
        """分类列选择变化"""
        clinical_col = self.bulk_km_r_ui.bulk_km_geneset_clinical_combo.currentText()

        if clinical_col == "全部":
            self.func.hide_group_list()
            self.func.enable_pairwise_controls(False)
            return

        unique_values = self.analysis.get_obs_unique_values(clinical_col)

        if not unique_values:
            self.func.hide_group_list()
            self.func.enable_pairwise_controls(False)
            return

        self.func.update_group_list(unique_values)
        self.func.enable_pairwise_controls(True)
        self.func.update_pairwise_list(unique_values)

    def on_filter1_enable_changed(self, state):
        enabled = (state == 2)
        self.func.on_filter1_enabled(enabled)

    def on_filter1_col_changed(self, index):
        if index < 0:
            return
        filter_col = self.bulk_km_r_ui.bulk_km_geneset_filter1_combo.currentText()
        if filter_col:
            unique_values = self.analysis.get_obs_unique_values(filter_col)
            self.func.update_filter_list(self.bulk_km_r_ui.bulk_km_geneset_filter1_list, unique_values)

    def on_filter2_enable_changed(self, state):
        enabled = (state == 2)
        self.func.on_filter2_enabled(enabled)

    def on_filter2_col_changed(self, index):
        if index < 0:
            return
        filter_col = self.bulk_km_r_ui.bulk_km_geneset_filter2_combo.currentText()
        if filter_col:
            unique_values = self.analysis.get_obs_unique_values(filter_col)
            self.func.update_filter_list(self.bulk_km_r_ui.bulk_km_geneset_filter2_list, unique_values)

    def on_pairwise_enable_changed(self, state):
        enabled = (state == 2)
        self.bulk_km_r_ui.bulk_km_geneset_pairwise_list.setEnabled(enabled)

    def on_show_table_changed(self, state):
        self.func.on_table_check_changed(state)

    def _sync_plot_width_to_export(self, text):
        try:
            width = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_geneset_export_width.setText(str(width))
        except Exception:
            pass

    def _sync_plot_height_to_export(self, text):
        try:
            height = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_geneset_export_height.setText(str(height))
        except Exception:
            pass

    def _sync_export_width_to_plot(self, text):
        try:
            width = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_geneset_plot_width_input.setText(str(width))
        except Exception:
            pass

    def _sync_export_height_to_plot(self, text):
        try:
            height = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_geneset_plot_height_input.setText(str(height))
        except Exception:
            pass

    def on_debug_clicked(self):
        """Debug按钮点击 - 检测基因集控件与R环境"""
        self.func.log("========== 基因集环境检测开始 ==========")
        for ctrl in ['bulk_km_geneset_input_mode_combo', 'bulk_km_geneset_file_combo',
                     'bulk_km_geneset_manual_input', 'bulk_km_geneset_method_combo',
                     'bulk_km_geneset_btn_plot', 'bulk_km_geneset_status_text',
                     'bulk_km_geneset_plot_tabs', 'bulk_km_geneset_label']:
            self.func.log(f"  {'✓' if hasattr(self.bulk_km_r_ui, ctrl) else '✗ 缺失'} {ctrl}")
        self.func.log(f"  self.adata: {'已设置' if self.adata is not None else 'None'}")
        self.func.log(f"  analysis.adata: {'已设置' if self.analysis.adata is not None else 'None'}")
        self.func.log(f"  analysis.is_available(): {self.analysis.is_available()}")
        self.func.log(f"  R版本: {self.analysis.get_r_version()}")
        self.func.log("========== 基因集环境检测完成 ==========")

    # ---------- 导出 ----------

    def on_export_png(self):
        if self.current_km_fig_path and os.path.exists(self.current_km_fig_path):
            self._export_image('png')
        else:
            self.func.alert_error("请先生成KM曲线")

    def on_export_pdf(self):
        if self._last_km_df is not None:
            self._replot_and_export('pdf')
        else:
            self.func.alert_error("请先生成KM曲线")

    def on_export_svg(self):
        if self._last_km_df is not None:
            self._replot_and_export('svg')
        else:
            self.func.alert_error("请先生成KM曲线")

    def on_export_csv(self):
        if self._last_km_df is not None:
            self._export_csv()
        else:
            self.func.alert_error("请先生成KM曲线")

    def _export_image(self, fmt):
        """导出图片"""
        try:
            width, height = self.func.get_export_size()
            if width is None or height is None:
                width, height = 8, 6

            label = self._last_km_label or "geneset"
            default_name = f"{label}_{self.dataset_name}_km.{fmt}"
            filter_text = f"{fmt.upper()} Files (*.{fmt})"

            save_path = self.func.get_save_file_path(f"导出{fmt.upper()}", default_name, filter_text)
            if not save_path:
                return

            if self.current_km_fig_path and os.path.exists(self.current_km_fig_path):
                from PIL import Image
                img = Image.open(self.current_km_fig_path)
                img.save(save_path)
                self.func.log(f"导出成功: {save_path}")
                happy(self.parent, "导出成功")
            else:
                self.func.alert_error("图片文件不存在")

        except Exception as e:
            self.func.log(f"导出失败: {str(e)}")
            traceback.print_exc()
            wrong(self.parent, "导出失败")

    def _replot_and_export(self, fmt):
        """重新绘制并导出为指定格式（PDF/SVG）"""
        try:
            if self._last_km_df is None:
                self.func.alert_error("请先生成KM曲线")
                return

            label = self._last_km_label or "geneset"
            plot_params = self.func.get_plot_params()
            width = plot_params.get('plot_width', 6)
            height = plot_params.get('plot_height', 8)

            default_name = f"{label}_{self.dataset_name}_km.{fmt}"
            filter_text = f"{fmt.upper()} Files (*.{fmt})"

            save_path = self.func.get_save_file_path(f"导出{fmt.upper()}", default_name, filter_text)
            if not save_path:
                return

            title = self.func.get_title(f"{label} {self.dataset_name}")

            self.analysis.draw_km_plot_r(
                self._last_km_df, 'time', 'state', 'group', label,
                output_path=save_path, title=title,
                show_risk_table=plot_params.get('show_table', True),
                plot_width=width,
                plot_height=height,
                pval_mode=plot_params.get('pval_mode', 0),
                title_font_size=plot_params.get('title_size', 14),
                axis_font_size=plot_params.get('axis_size', 12),
                legend_font_size=plot_params.get('legend_size', 12),
                pval_font_size=plot_params.get('pval_size', 5),
                risk_table_font_size=plot_params.get('table_size', 5),
                show_conf_int=plot_params.get('show_ci', False),
                show_n=plot_params.get('show_n', True),
                show_global_pval=plot_params.get('show_global_pval', True),
                show_pairwise=plot_params.get('show_pairwise', False),
                selected_pairwise=plot_params.get('selected_pairwise', [])
            )

            if os.path.exists(save_path):
                self.func.log(f"导出成功: {save_path}")
                happy(self.parent, "导出成功")
            else:
                self.func.alert_error("导出失败")

        except Exception as e:
            self.func.log(f"导出失败: {str(e)}")
            traceback.print_exc()
            wrong(self.parent, "导出失败")

    def _export_csv(self):
        """导出生存数据为CSV"""
        try:
            if self._last_km_df is None:
                self.func.alert_error("请先生成KM曲线")
                return

            label = self._last_km_label or "geneset"
            default_name = f"km_data_{label}_{self.dataset_name}.csv"
            filter_text = "CSV Files (*.csv)"

            save_path = self.func.get_save_file_path("导出CSV", default_name, filter_text)
            if not save_path:
                return

            self._last_km_df.to_csv(save_path, index=False, encoding='utf-8-sig')

            self.func.log(f"导出成功: {save_path}")
            happy(self.parent, "导出成功")

        except Exception as e:
            self.func.log(f"导出失败: {str(e)}")
            traceback.print_exc()
            wrong(self.parent, "导出失败")
