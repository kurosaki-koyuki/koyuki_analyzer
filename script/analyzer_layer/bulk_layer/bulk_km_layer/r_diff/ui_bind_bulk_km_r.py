# -*- coding: utf-8 -*-
"""
bulk KM曲线 R模式界面绑定脚本 - 绑定按钮信号、调用业务逻辑层、驱动analysis层
"""

from script.utils_layer.import_config import os, traceback, np, pd, plt, gridspec, FigureCanvas, QFileDialog, QMessageBox, QApplication, QListWidgetItem

from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.bulk_km_r_analysis import get_bulk_km_r_analysis
from script.analyzer_layer.bulk_layer.bulk_km_layer.r_diff.ui_func_bulk_km_r import BulkKmRFunc
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong
from script.utils_layer.page_intersect import page_intersect


class BulkKmRBind:
    """bulk KM曲线 R模式绑定类"""

    def __init__(self, parent_widget, bulk_km_r_ui):
        self.parent = parent_widget
        self.bulk_km_r_ui = bulk_km_r_ui
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.data_folder = None
        self.analysis = get_bulk_km_r_analysis()
        self.func = BulkKmRFunc(bulk_km_r_ui, parent_widget)
        self.func.analysis = self.analysis  # 引用analysis到func
        self.current_km_fig_path = None
        self.all_fig_paths = []  # 多基因模式：所有单图路径
        self.all_km_data = []    # 多基因模式：所有KM数据
        self.combined_fig_path = None  # 多基因模式：组合图路径
        self._bind_signals()
        self._init_page()

    def _bind_signals(self):
        """绑定按钮点击信号"""
        # 返回按钮
        self.bulk_km_r_ui.btn_back.clicked.connect(self.on_back_clicked)

        # 生成KM曲线按钮
        self.bulk_km_r_ui.bulk_km_btn_plot.clicked.connect(self.on_plot_clicked)

        # 导出按钮
        self.bulk_km_r_ui.bulk_km_btn_export_png.clicked.connect(self.on_export_png)
        self.bulk_km_r_ui.bulk_km_btn_export_pdf.clicked.connect(self.on_export_pdf)
        self.bulk_km_r_ui.bulk_km_btn_export_svg.clicked.connect(self.on_export_svg)
        self.bulk_km_r_ui.bulk_km_btn_export_csv.clicked.connect(self.on_export_csv)

        # Debug按钮
        self.bulk_km_r_ui.bulk_km_debug_btn.clicked.connect(self.on_debug_clicked)

        # 分类列选择变化
        self.bulk_km_r_ui.bulk_km_clinical_combo.currentIndexChanged.connect(self.on_clinical_combo_changed)

        # 筛选1启用
        self.bulk_km_r_ui.bulk_km_filter1_enable.stateChanged.connect(self.on_filter1_enable_changed)
        self.bulk_km_r_ui.bulk_km_filter1_combo.currentIndexChanged.connect(self.on_filter1_col_changed)

        # 筛选2启用
        self.bulk_km_r_ui.bulk_km_filter2_enable.stateChanged.connect(self.on_filter2_enable_changed)
        self.bulk_km_r_ui.bulk_km_filter2_combo.currentIndexChanged.connect(self.on_filter2_col_changed)

        # 组间比较启用
        self.bulk_km_r_ui.bulk_km_pairwise_enable.stateChanged.connect(self.on_pairwise_enable_changed)

        # 显示风险表格
        self.bulk_km_r_ui.bulk_km_show_table_check.stateChanged.connect(self.on_show_table_changed)

        # 尺寸同步
        self.bulk_km_r_ui.bulk_km_plot_width_input.textChanged.connect(self._sync_plot_width_to_export)
        self.bulk_km_r_ui.bulk_km_plot_height_input.textChanged.connect(self._sync_plot_height_to_export)
        self.bulk_km_r_ui.bulk_km_export_width.textChanged.connect(self._sync_export_width_to_plot)
        self.bulk_km_r_ui.bulk_km_export_height.textChanged.connect(self._sync_export_height_to_plot)

    def _init_page(self):
        """初始化页面"""
        self.func.log_set_default()
        self.func.update_r_version_label()
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()

        # 设置默认字体大小
        if hasattr(self.bulk_km_r_ui, 'bulk_km_pvalsize_input'):
            self.bulk_km_r_ui.bulk_km_pvalsize_input.setText('5')
        if hasattr(self.bulk_km_r_ui, 'bulk_km_tablesize_input'):
            self.bulk_km_r_ui.bulk_km_tablesize_input.setText('5')
        if hasattr(self.bulk_km_r_ui, 'bulk_km_axissize_input'):
            self.bulk_km_r_ui.bulk_km_axissize_input.setText('14')

    def on_debug_clicked(self):
        """Debug按钮点击 - 检测环境对应关系"""
        self.func.log("========== 环境检测开始 ==========")

        # 1. 检测UI控件是否存在
        self.func.log("\n【1. UI控件检测】")
        ui_controls = [
            'btn_back', 'bulk_km_btn_plot',
            'bulk_km_btn_export_png', 'bulk_km_btn_export_pdf',
            'bulk_km_btn_export_svg', 'bulk_km_btn_export_csv',
            'bulk_km_debug_btn',
            'bulk_km_gene_input', 'bulk_km_clinical_combo',
            'bulk_km_group_list', 'bulk_km_clinical_col_list',
            'bulk_km_filter1_enable', 'bulk_km_filter1_combo', 'bulk_km_filter1_list',
            'bulk_km_filter2_enable', 'bulk_km_filter2_combo', 'bulk_km_filter2_list',
            'bulk_km_pairwise_enable', 'bulk_km_pairwise_list',
            'bulk_km_show_table_check', 'bulk_km_show_ci_check', 'bulk_km_show_n_check',
            'bulk_km_plot_width_input', 'bulk_km_plot_height_input',
            'bulk_km_export_width', 'bulk_km_export_height',
            'bulk_km_titlesize_input', 'bulk_km_legendsize_input',
            'bulk_km_axissize_input', 'bulk_km_pvalsize_input', 'bulk_km_tablesize_input',
            'bulk_km_pval_mode_combo', 'bulk_km_time_unit_combo',
            'bulk_km_title_input', 'bulk_km_multi_gene_input',
            'bulk_km_show_global_check',
            'bulk_km_plot_tabs', 'bulk_km_label',
            'bulk_km_status_text', 'r_version_label'
        ]

        missing_ui = []
        for ctrl_name in ui_controls:
            if hasattr(self.bulk_km_r_ui, ctrl_name):
                self.func.log(f"  ✓ {ctrl_name}")
            else:
                self.func.log(f"  ✗ {ctrl_name} - 缺失!")
                missing_ui.append(ctrl_name)

        if missing_ui:
            self.func.log(f"\n缺失UI控件: {', '.join(missing_ui)}")

        # 2. 检测数据状态
        self.func.log("\n【2. 数据状态检测】")
        self.func.log(f"  self.adata: {'已设置' if self.adata is not None else 'None'}")
        self.func.log(f"  self.dataset_name: {self.dataset_name}")
        self.func.log(f"  self.dataset_output_dir: {self.dataset_output_dir}")
        self.func.log(f"  analysis.adata: {'已设置' if self.analysis.adata is not None else 'None'}")

        if self.adata is not None:
            self.func.log(f"  adata.shape: {self.adata.shape}")
        else:
            self.func.log("  ⚠ 数据未加载，请先在KM模式加载数据")

        # 3. 检测父对象关系
        self.func.log("\n【3. 父对象关系检测】")
        self.func.log(f"  hasattr(parent, 'bulk_km_bind'): {hasattr(self.parent, 'bulk_km_bind')}")
        if hasattr(self.parent, 'bulk_km_bind'):
            km_bind = self.parent.bulk_km_bind
            self.func.log(f"  parent.bulk_km_bind is None: {km_bind is None}")
            if km_bind is not None:
                self.func.log(f"  parent.bulk_km_bind.adata: {'已设置' if km_bind.adata is not None else 'None'}")

        # 4. 检测R环境
        self.func.log("\n【4. R环境检测】")
        self.func.log(f"  analysis.is_available(): {self.analysis.is_available()}")
        self.func.log(f"  R版本: {self.analysis.get_r_version()}")

        # 5. 检测func层引用
        self.func.log("\n【5. Func层引用检测】")
        self.func.log(f"  func.analysis: {hasattr(self.func, 'analysis')}")
        if hasattr(self.func, 'analysis'):
            self.func.log(f"  func.analysis.adata: {'已设置' if self.func.analysis.adata is not None else 'None'}")

        # 6. R交互错误日志
        self.func.log("\n【6. R交互错误日志】")
        debug_log = self.analysis.get_r_debug_log()
        if not debug_log:
            self.func.log("  没有记录到R相关错误")
        else:
            self.func.log(f"  共记录 {len(debug_log)} 个R相关错误:")
            for i, entry in enumerate(debug_log, 1):
                self.func.log(f"  --- 错误 {i} ---")
                self.func.log(f"    时间: {entry['timestamp']}")
                self.func.log(f"    操作: {entry['operation']}")
                self.func.log(f"    类型: {entry['error_type']}")
                self.func.log(f"    消息: {entry['error_message']}")

        # 总结
        self.func.log("\n========== 环境检测完成 ==========")

    def sync_data_from_km(self, km_bind=None):
        """从KM页面同步数据"""
        try:
            if km_bind is None:
                km_bind = getattr(self.parent, 'bulk_km_bind', None)
            
            if km_bind is None:
                self.func.log("错误: 无法从KM模式同步数据（KM bind对象为空）")
                return

            # 获取数据
            self.adata = km_bind.adata
            self.dataset_name = getattr(km_bind, 'dataset_name', None)
            self.dataset_output_dir = getattr(km_bind, 'dataset_output_dir', None)
            self.data_folder = getattr(km_bind, 'data_folder', None)

            if self.adata is None:
                self.func.log("错误: KM模式adata为空，请先加载数据")
                return

            # 设置到analysis层
            self.analysis.set_adata(self.adata)
            self.analysis.set_dataset_name(self.dataset_name)
            self.analysis.set_dataset_output_dir(self.dataset_output_dir)

            # 更新界面
            obs_columns = self.analysis.get_obs_columns()
            self.func.update_clinical_combo(obs_columns)
            self.func.load_clinical_columns_to_filter1()
            self.func.load_clinical_columns_to_filter2()

            self.func.update_hint_text(
                self.dataset_name or "Unknown",
                self.adata.n_obs,
                self.adata.n_vars
            )

            self.func.log(f"已从KM模式同步数据: {self.dataset_name}")
            self.func.log(f"样本数: {self.adata.n_obs}, 基因数: {self.adata.n_vars}")

        except Exception as e:
            self.func.log(f"同步数据时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_back_clicked(self):
        """返回主页"""
        page_intersect.go_to_page_with_bind('bulk_top_page')

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
        
        self.func.log_set_default()
        self.func.update_r_version_label()
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()

    def on_clinical_combo_changed(self, index):
        """分类列选择变化"""
        clinical_col = self.bulk_km_r_ui.bulk_km_clinical_combo.currentText()

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
        """筛选1启用状态变化"""
        enabled = (state == 2)
        self.func.on_filter1_enabled(enabled)

    def on_filter1_col_changed(self, index):
        """筛选1分类列变化"""
        if index < 0:
            return
        filter_col = self.bulk_km_r_ui.bulk_km_filter1_combo.currentText()
        if filter_col:
            unique_values = self.analysis.get_obs_unique_values(filter_col)
            self.func.update_filter_list(self.bulk_km_r_ui.bulk_km_filter1_list, unique_values)

    def on_filter2_enable_changed(self, state):
        """筛选2启用状态变化"""
        enabled = (state == 2)
        self.func.on_filter2_enabled(enabled)

    def on_filter2_col_changed(self, index):
        """筛选2分类列变化"""
        if index < 0:
            return
        filter_col = self.bulk_km_r_ui.bulk_km_filter2_combo.currentText()
        if filter_col:
            unique_values = self.analysis.get_obs_unique_values(filter_col)
            self.func.update_filter_list(self.bulk_km_r_ui.bulk_km_filter2_list, unique_values)

    def on_pairwise_enable_changed(self, state):
        """组间比较启用状态变化"""
        enabled = (state == 2)
        self.bulk_km_r_ui.bulk_km_pairwise_list.setEnabled(enabled)

    def on_show_table_changed(self, state):
        """显示风险表格变化"""
        self.func.on_table_check_changed(state)

    def _sync_plot_width_to_export(self, text):
        """同步出图宽度到导出"""
        try:
            width = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_export_width.setText(str(width))
        except:
            pass

    def _sync_plot_height_to_export(self, text):
        """同步出图高度到导出"""
        try:
            height = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_export_height.setText(str(height))
        except:
            pass

    def _sync_export_width_to_plot(self, text):
        """同步导出宽度到出图"""
        try:
            width = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_plot_width_input.setText(str(width))
        except:
            pass

    def _sync_export_height_to_plot(self, text):
        """同步导出高度到出图"""
        try:
            height = float(text) if text.replace('.', '').isdigit() else 6
            self.bulk_km_r_ui.bulk_km_plot_height_input.setText(str(height))
        except:
            pass

    def on_plot_clicked(self):
        """生成KM曲线"""
        try:
            self.func.log("正在生成KM曲线...")

            if self.adata is None:
                self.func.alert_error("数据未加载")
                return

            # 检查R环境
            if not self.analysis.is_available():
                r_version = self.analysis.get_r_version()
                self.func.alert_error(f"R环境不可用，无法生成曲线\n{r_version}")
                return

            self.func.log(f"R版本: {self.analysis.get_r_version()}")
            self._plot_with_r()

        except Exception as e:
            self.func.log(f"错误: {str(e)}")
            traceback.print_exc()

    def _plot_with_python(self):
        """使用Python绘制KM曲线"""
        multi_gene_text = self.func.get_multi_gene_list()
        gene_name = self.func.get_gene_name()
        time_unit = self.func.get_time_unit()
        plot_params = self.func.get_plot_params()

        if multi_gene_text:
            genes = [g.strip() for g in multi_gene_text.split('\n') if g.strip()]
            self._plot_multi_gene_python(genes, time_unit, plot_params)
        elif gene_name:
            self._plot_single_gene_python(gene_name, time_unit, plot_params)
        else:
            self.func.alert_error("请输入基因名称")

    def _plot_single_gene_python(self, gene_name, time_unit, plot_params):
        """绘制单基因KM曲线（Python版本）"""
        df = self.analysis.prepare_km_data(gene_name, time_unit)
        if df is None:
            self.func.alert_error(f"基因 {gene_name} 不存在或数据无效")
            return

        clinical_col = self.func.get_clinical_col()
        filter1_col = self.bulk_km_r_ui.bulk_km_filter1_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter1_enable.isChecked() else None
        filter1_groups = self.func.get_filter1_groups() if filter1_col else None
        filter2_col = self.bulk_km_r_ui.bulk_km_filter2_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter2_enable.isChecked() else None
        filter2_groups = self.func.get_filter2_groups() if filter2_col else None

        df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
        if df is None or len(df) < 10:
            self.func.alert_error("筛选后数据不足")
            return

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
            self.func.log(f"[DEBUG] Clinical grouped df columns: {df.columns.tolist()}, shape: {df.shape}")
        else:
            df, n_high, n_low = self.analysis.split_groups_simple(df)
            if df is None:
                self.func.alert_error("数据分组失败")
                return

        title = self.func.get_title(f"{gene_name} {self.dataset_name}")
        self._render_km_plot(df, gene_name, title, plot_params)
        self.func.log(f"基因 {gene_name} KM曲线生成成功")

    def _plot_multi_gene_python(self, genes, time_unit, plot_params):
        """绘制多基因KM曲线（Python版本）"""
        n_genes = len(genes)
        self.func.log(f"开始绘制 {n_genes} 个基因的KM曲线")

        valid_genes = []
        invalid_genes = []
        gene_data = {}

        for gene_name in genes:
            df = self.analysis.prepare_km_data(gene_name, time_unit)
            if df is None:
                invalid_genes.append(gene_name)
                continue

            clinical_col = self.func.get_clinical_col()
            filter1_col = self.bulk_km_r_ui.bulk_km_filter1_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter1_enable.isChecked() else None
            filter1_groups = self.func.get_filter1_groups() if filter1_col else None
            filter2_col = self.bulk_km_r_ui.bulk_km_filter2_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter2_enable.isChecked() else None
            filter2_groups = self.func.get_filter2_groups() if filter2_col else None

            df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
            if df is None or len(df) < 10:
                invalid_genes.append(gene_name)
                continue

            if clinical_col != "全部":
                selected_groups = self.func.get_selected_groups()
                grouped_list = self.analysis.split_groups_by_clinical(df, clinical_col, selected_groups)
                if isinstance(grouped_list, list):
                    if len(grouped_list) == 0:
                        invalid_genes.append(gene_name)
                        continue
                    df = pd.concat(grouped_list, ignore_index=True)
                else:
                    df = grouped_list
                if not hasattr(df, 'columns') or 'group' not in df.columns:
                    invalid_genes.append(gene_name)
                    continue
            else:
                df, n_high, n_low = self.analysis.split_groups_simple(df)
                if df is None:
                    invalid_genes.append(gene_name)
                    continue

            gene_data[gene_name] = df
            valid_genes.append(gene_name)

        if invalid_genes:
            self.func.log(f"跳过无效基因: {', '.join(invalid_genes)}")

        if not valid_genes:
            self.func.alert_error("没有有效基因可以绘图")
            return

        if len(valid_genes) == 1:
            gene_name = valid_genes[0]
            title = self.func.get_title(f"{gene_name} {self.dataset_name}")
            self._render_km_plot(gene_data[gene_name], gene_name, title, plot_params)
            self.func.log(f"基因 {gene_name} KM曲线生成成功")
        else:
            self._render_multi_km_plot(gene_data, plot_params)
            self.func.log(f"多基因组合KM曲线生成成功")

    def _render_km_plot(self, df, gene_name, title, plot_params):
        """渲染KM曲线"""
        import lifelines
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test

        fig = plt.figure(figsize=(plot_params['plot_width'], plot_params['plot_height']))
        ax = fig.add_subplot(111)

        groups = df['group'].unique()
        colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']

        for i, group in enumerate(sorted(groups)):
            group_df = df[df['group'] == group]
            kmf = KaplanMeierFitter()
            kmf.fit(group_df['time'], group_df['state'], label=group)

            color = colors[i % len(colors)]
            ci_show = plot_params['show_ci'] if 'show_ci' in plot_params else True
            kmf.plot_survival_function(ax=ax, color=color, ci_show=ci_show)

        ax.set_title(title, fontsize=plot_params.get('title_size', 18))
        ax.set_xlabel('Time', fontsize=plot_params.get('axis_size', 16))
        ax.set_ylabel('Survival Probability', fontsize=plot_params.get('axis_size', 16))
        ax.legend(loc='best', fontsize=plot_params.get('legend_size', 12))
        ax.grid(True, alpha=0.3)

        if plot_params.get('show_global_pval', True) and len(groups) >= 2:
            group_list = [df[df['group'] == g]['time'] for g in sorted(groups)]
            event_list = [df[df['group'] == g]['state'] for g in sorted(groups)]
            if len(group_list) == 2:
                results = logrank_test(group_list[0], group_list[1], event_list[0], event_list[1])
                pval = results.p_value
            else:
                from lifelines.statistics import multivariate_logrank_test
                results = multivariate_logrank_test(df['time'], df['group'], df['state'])
                pval = results.p_value

            pval_mode = plot_params.get('pval_mode', 0)
            if pval_mode == 0:
                pval_text = f"p = {pval:.4f}"
            elif pval_mode == 1:
                if pval < 0.001:
                    pval_text = "p < 0.001"
                elif pval < 0.01:
                    pval_text = "p < 0.01"
                elif pval < 0.05:
                    pval_text = "p < 0.05"
                else:
                    pval_text = "p >= 0.05"
            else:
                if pval < 0.001:
                    pval_text = f"p < 0.001 ({pval:.2e})"
                elif pval < 0.01:
                    pval_text = f"p < 0.01 ({pval:.4f})"
                elif pval < 0.05:
                    pval_text = f"p < 0.05 ({pval:.4f})"
                else:
                    pval_text = f"p >= 0.05 ({pval:.4f})"

            ax.text(0.5, 0.1, pval_text, transform=ax.transAxes,
                    fontsize=plot_params.get('pval_size', 5), ha='center')

        fig.tight_layout()

        temp_path = os.path.join(self.dataset_output_dir or ".", f"km_temp_{gene_name}.png")
        fig.savefig(temp_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        self.current_km_fig_path = temp_path
        self.func.display_image(self.bulk_km_r_ui.bulk_km_label, temp_path)

    def _render_multi_km_plot(self, gene_data, plot_params):
        """渲染多基因组合KM曲线"""
        n_genes = len(gene_data)
        n_cols = min(3, n_genes)
        n_rows = (n_genes + n_cols - 1) // n_cols

        fig_width = plot_params['plot_width'] * n_cols
        fig_height = plot_params['plot_height'] * n_rows

        fig = plt.figure(figsize=(fig_width, fig_height))
        gs = gridspec.GridSpec(n_rows, n_cols, wspace=0.3, hspace=0.3)

        genes = list(gene_data.keys())
        for idx, gene_name in enumerate(genes):
            row = idx // n_cols
            col = idx % n_cols
            ax = fig.add_subplot(gs[row, col])

            df = gene_data[gene_name]
            self._render_single_km_subplot(ax, df, gene_name, plot_params)

        for idx in range(n_genes, n_rows * n_cols):
            row = idx // n_cols
            col = idx % n_cols
            fig.add_subplot(gs[row, col]).axis('off')

        fig.tight_layout()

        temp_path = os.path.join(self.dataset_output_dir or ".", "km_multi_temp.png")
        fig.savefig(temp_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        self.current_km_fig_path = temp_path
        self.func.display_image(self.bulk_km_r_ui.bulk_km_label, temp_path)

    def _render_single_km_subplot(self, ax, df, gene_name, plot_params):
        """渲染单个KM子图"""
        import lifelines
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test, multivariate_logrank_test

        groups = df['group'].unique()
        colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']

        for i, group in enumerate(sorted(groups)):
            group_df = df[df['group'] == group]
            kmf = KaplanMeierFitter()
            kmf.fit(group_df['time'], group_df['state'], label=group)

            color = colors[i % len(colors)]
            ci_show = plot_params.get('show_ci', True)
            kmf.plot_survival_function(ax=ax, color=color, ci_show=ci_show)

        ax.set_title(gene_name, fontsize=plot_params.get('title_size', 14))
        ax.set_xlabel('Time', fontsize=plot_params.get('axis_size', 12))
        ax.set_ylabel('Survival', fontsize=plot_params.get('axis_size', 12))
        ax.legend(loc='best', fontsize=plot_params.get('legend_size', 10))
        ax.grid(True, alpha=0.3)

        if plot_params.get('show_global_pval', True) and len(groups) >= 2:
            group_list = [df[df['group'] == g]['time'] for g in sorted(groups)]
            event_list = [df[df['group'] == g]['state'] for g in sorted(groups)]
            if len(group_list) == 2:
                results = logrank_test(group_list[0], group_list[1], event_list[0], event_list[1])
                pval = results.p_value
            else:
                results = multivariate_logrank_test(df['time'], df['group'], df['state'])
                pval = results.p_value

            pval_mode = plot_params.get('pval_mode', 0)
            if pval_mode == 0:
                pval_text = f"p = {pval:.4f}"
            elif pval_mode == 1:
                if pval < 0.001:
                    pval_text = "p < 0.001"
                elif pval < 0.01:
                    pval_text = "p < 0.01"
                elif pval < 0.05:
                    pval_text = "p < 0.05"
                else:
                    pval_text = "p >= 0.05"
            else:
                if pval < 0.001:
                    pval_text = f"p < 0.001 ({pval:.2e})"
                elif pval < 0.01:
                    pval_text = f"p < 0.01 ({pval:.4f})"
                elif pval < 0.05:
                    pval_text = f"p < 0.05 ({pval:.4f})"
                else:
                    pval_text = f"p >= 0.05 ({pval:.4f})"

            ax.text(0.5, 0.1, pval_text, transform=ax.transAxes,
                    fontsize=plot_params.get('pval_size', 5), ha='center')

    def _plot_with_r(self):
        """使用R绘制KM曲线"""
        multi_gene_text = self.func.get_multi_gene_list()
        gene_name = self.func.get_gene_name()
        time_unit = self.func.get_time_unit()
        plot_params = self.func.get_plot_params()

        if multi_gene_text:
            genes = [g.strip() for g in multi_gene_text.split('\n') if g.strip()]
            self._plot_multi_gene_r(genes, time_unit, plot_params)
        elif gene_name:
            self._plot_single_gene_r(gene_name, time_unit, plot_params)
        else:
            self.func.alert_error("请输入基因名称")

    def _plot_single_gene_r(self, gene_name, time_unit, plot_params):
        """绘制单基因KM曲线（R版本）"""
        try:
            df = self.analysis.prepare_km_data(gene_name, time_unit)
            if df is None:
                self.func.alert_error(f"基因 {gene_name} 不存在或数据无效")
                return

            clinical_col = self.func.get_clinical_col()
            filter1_col = self.bulk_km_r_ui.bulk_km_filter1_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter1_enable.isChecked() else None
            filter1_groups = self.func.get_filter1_groups() if filter1_col else None
            filter2_col = self.bulk_km_r_ui.bulk_km_filter2_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter2_enable.isChecked() else None
            filter2_groups = self.func.get_filter2_groups() if filter2_col else None

            df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
            if df is None or len(df) < 10:
                self.func.alert_error("筛选后数据不足")
                return

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
                if not hasattr(df, 'columns') or 'group' not in df.columns:
                    self.func.alert_error("分组数据缺少group列")
                    return

            title = self.func.get_title(f"{gene_name} {self.dataset_name}")
            output_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.png")

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
            self.func.display_image(self.bulk_km_r_ui.bulk_km_label, output_path)
            self.func.log(f"基因 {gene_name} KM曲线(R模式)生成成功")

        except Exception as e:
            self.func.log(f"R绘图失败: {str(e)}")
            debug_log = self.analysis.get_r_debug_log()
            if debug_log:
                self.func.log(f"[R_DEBUG] 当前已累计 {len(debug_log)} 个R交互错误:")
                for i, entry in enumerate(debug_log[-3:], max(1, len(debug_log)-2)):
                    self.func.log(f"  错误{i}: {entry['operation']} -> {entry['error_type']}: {entry['error_message'][:80]}...")
            traceback.print_exc()
            self.func.alert_error(f"R绘图失败: {str(e)}")

    def _plot_multi_gene_r(self, genes, time_unit, plot_params):
        """绘制多基因KM曲线（R版本）"""
        try:
            clinical_col = self.func.get_clinical_col()
            filter1_col = self.bulk_km_r_ui.bulk_km_filter1_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter1_enable.isChecked() else None
            filter1_groups = self.func.get_filter1_groups() if filter1_col else None
            filter2_col = self.bulk_km_r_ui.bulk_km_filter2_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter2_enable.isChecked() else None
            filter2_groups = self.func.get_filter2_groups() if filter2_col else None

            time_label = 'Time (months)' if time_unit == 'month' else 'Time (days)'

            # 重置存储列表
            self.all_fig_paths = []
            self.all_km_data = []

            # 逐个基因绘制KM曲线
            for i, gene_name in enumerate(genes):
                self.func.log(f"正在处理基因 {i+1}/{len(genes)}: {gene_name}")

                df = self.analysis.prepare_km_data(gene_name, time_unit)
                if df is None:
                    self.func.log(f"基因 {gene_name} 数据准备失败，跳过")
                    continue

                df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
                if df is None or len(df) < 10:
                    self.func.log(f"基因 {gene_name} 筛选后样本数太少，跳过")
                    continue

                if clinical_col != "全部":
                    selected_groups = self.func.get_selected_groups()
                    grouped_list = self.analysis.split_groups_by_clinical(df, clinical_col, selected_groups)
                    if isinstance(grouped_list, list):
                        if len(grouped_list) == 0:
                            self.func.log(f"基因 {gene_name} 没有足够的样本进行分析，跳过")
                            continue
                        df = pd.concat(grouped_list, ignore_index=True)
                    else:
                        df = grouped_list
                    if not hasattr(df, 'columns') or 'group' not in df.columns:
                        self.func.log(f"基因 {gene_name} 分组数据缺少group列，跳过")
                        continue
                else:
                    df, n_high, n_low = self.analysis.split_groups_simple(df)
                    if df is None:
                        self.func.log(f"基因 {gene_name} 数据分组失败，跳过")
                        continue
                    if 'group' not in df.columns:
                        self.func.log(f"基因 {gene_name} 分组数据缺少group列，跳过")
                        continue

                self.func.log(f"  样本数: {len(df)}")

                title = self.func.get_title(f"{gene_name} {self.dataset_name}")
                output_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.png")

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

                # 保存单图路径和数据
                if os.path.exists(output_path):
                    self.all_fig_paths.append(output_path)
                    self.all_km_data.append((gene_name, df.copy()))
                    self.func.log(f"  基因 {gene_name} KM曲线生成成功")

            # 多基因模式下生成组合图
            if len(self.all_km_data) > 0:
                combined_fig_path = self._draw_combined_km_plot(
                    self.all_km_data,
                    time_label=time_label,
                    title_size=plot_params.get('title_size', 14),
                    legend_size=plot_params.get('legend_size', 12),
                    axis_size=plot_params.get('axis_size', 12),
                    pval_size=plot_params.get('pval_size', 5),
                    show_table=plot_params.get('show_table', True),
                    table_size=plot_params.get('table_size', 5),
                    pval_mode=plot_params.get('pval_mode', 0),
                    show_global_pval=plot_params.get('show_global_pval', True),
                    show_pairwise=plot_params.get('show_pairwise', False),
                    selected_pairwise=plot_params.get('selected_pairwise', []),
                    show_ci=plot_params.get('show_ci', False),
                    show_n=plot_params.get('show_n', True),
                    export_width=plot_params.get('plot_width', 6),
                    export_height=plot_params.get('plot_height', 8)
                )
                self.all_fig_paths.insert(0, combined_fig_path)
                self.combined_fig_path = combined_fig_path
                self.current_km_fig_path = combined_fig_path

                # 显示组合图
                self.func.display_image(self.bulk_km_r_ui.bulk_km_label, combined_fig_path)
                self.func.log(f"多基因模式处理完成，共处理 {len(self.all_km_data)} 个基因")
            else:
                self.func.alert_error("没有基因成功生成KM曲线")

        except Exception as e:
            self.func.log(f"R模式多基因绘图失败: {str(e)}")
            traceback.print_exc()
            self.func.alert_error(f"R模式多基因绘图失败: {str(e)}")

    def _draw_combined_km_plot(self, all_km_data, time_label='Time (days)',
                               title_size=14, legend_size=12, axis_size=12, pval_size=5,
                               show_table=True, table_size=5, pval_mode=0,
                               show_global_pval=True, show_pairwise=False, selected_pairwise=None,
                               show_ci=False, show_n=True, export_width=6, export_height=8,
                               fmt='png'):
        """组合多基因KM图片（支持PNG/PDF/SVG矢量格式）"""
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg

        if not all_km_data:
            return None

        n_plots = len(all_km_data)
        if n_plots == 0:
            return None

        n_cols = min(3, n_plots)
        n_rows = (n_plots + n_cols - 1) // n_cols

        if fmt == 'png':
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * export_width, n_rows * export_height))

            if n_plots == 1:
                axes = [axes]
            else:
                axes = axes.flatten()

            for i, (gene_name, df) in enumerate(all_km_data):
                ax = axes[i]

                fig_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.png")
                if os.path.exists(fig_path):
                    img = mpimg.imread(fig_path)
                    ax.imshow(img)

                ax.axis('off')

            for i in range(n_plots, len(axes)):
                axes[i].axis('off')

            plt.tight_layout()

            output_path = os.path.join(self.dataset_output_dir or ".", f"{self.dataset_name}_combined_km.{fmt}")
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close(fig)

            return output_path
        elif fmt == 'svg':
            return self._combine_svg_vectors(all_km_data, n_cols, n_rows, export_width, export_height)
        else:
            return None

    def _combine_svg_vectors(self, all_km_data, n_cols, n_rows, export_width, export_height):
        """使用<g transform>组合矢量图，修复clip-path ID冲突"""
        from lxml import etree
        import os
        import re

        n_plots = len(all_km_data)
        if n_plots == 0:
            return None

        svg_files = []
        
        for gene_name, df in all_km_data:
            svg_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.svg")
            if os.path.exists(svg_path):
                svg_files.append((gene_name, svg_path))

        if not svg_files:
            return None

        if n_plots == 1:
            output_path = os.path.join(self.dataset_output_dir or ".", f"{self.dataset_name}_combined_km.svg")
            import shutil
            shutil.copy(svg_files[0][1], output_path)
            return output_path

        first_tree = etree.parse(svg_files[0][1])
        first_root = first_tree.getroot()
        first_vb = first_root.get('viewBox', '0 0 432 576').split()
        base_width = int(float(first_vb[2])) if len(first_vb) >= 4 else 432
        base_height = int(float(first_vb[3])) if len(first_vb) >= 4 else 576

        total_width = base_width * n_cols
        total_height = base_height * n_rows

        ns = 'http://www.w3.org/2000/svg'
        new_root = etree.Element(f'{{{ns}}}svg', 
                                 width=f'{total_width}pt', 
                                 height=f'{total_height}pt',
                                 viewBox=f'0 0 {total_width} {total_height}',
                                 xmlns=ns)

        defs_element = etree.SubElement(new_root, f'{{{ns}}}defs')

        for i, (gene_name, svg_path) in enumerate(svg_files):
            tree = etree.parse(svg_path)
            root = tree.getroot()
            
            row = i // n_cols
            col = i % n_cols
            x = col * base_width
            y = row * base_height

            prefix = f'{gene_name.replace(" ", "_")}_'
            id_map = {}

            g = etree.SubElement(new_root, f'{{{ns}}}g', transform=f'translate({x},{y})')

            for child in root:
                if child.tag == f'{{{ns}}}defs':
                    for def_item in child:
                        def_id = def_item.get('id', '')
                        if def_id:
                            new_id = prefix + def_id
                            id_map[def_id] = new_id
                            def_item.set('id', new_id)
                            for attr_name, attr_value in list(def_item.attrib.items()):
                                if isinstance(attr_value, str) and 'url(' in attr_value:
                                    new_value = re.sub(r'url\(#([^)]+)\)', lambda m, d=id_map: f'url(#{d.get(m.group(1), m.group(1))})', attr_value)
                                    def_item.set(attr_name, new_value)
                            defs_element.append(def_item)
                else:
                    new_child = etree.Element(child.tag)
                    for attr_name, attr_value in child.attrib.items():
                        if isinstance(attr_value, str) and 'url(' in attr_value:
                            new_value = re.sub(r'url\(#([^)]+)\)', lambda m, d=id_map: f'url(#{d.get(m.group(1), m.group(1))})', attr_value)
                            new_child.set(attr_name, new_value)
                        else:
                            new_child.set(attr_name, attr_value)
                    for sub_child in child:
                        new_sub = etree.Element(sub_child.tag)
                        for sub_attr_name, sub_attr_value in sub_child.attrib.items():
                            if isinstance(sub_attr_value, str) and 'url(' in sub_attr_value:
                                new_sub_value = re.sub(r'url\(#([^)]+)\)', lambda m, d=id_map: f'url(#{d.get(m.group(1), m.group(1))})', sub_attr_value)
                                new_sub.set(sub_attr_name, new_sub_value)
                            else:
                                new_sub.set(sub_attr_name, sub_attr_value)
                        new_child.append(new_sub)
                    g.append(new_child)

        tree = etree.ElementTree(new_root)
        output_path = os.path.join(self.dataset_output_dir or ".", f"{self.dataset_name}_combined_km.svg")
        tree.write(output_path, pretty_print=True, xml_declaration=True, encoding='utf-8')

        return output_path

    def on_export_png(self):
        """导出PNG（多基因模式打包为ZIP）"""
        if not self.all_fig_paths:
            if self.current_km_fig_path and os.path.exists(self.current_km_fig_path):
                self._export_image('png')
            else:
                self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_km_data) > 1:
            # 多基因模式：导出ZIP
            save_path = self.func.get_save_file_path(
                "导出PNG（ZIP）",
                f"{self.dataset_name}_km.zip",
                "ZIP Files (*.zip)"
            )

            if save_path:
                try:
                    import zipfile
                    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for fig_path in self.all_fig_paths:
                            if os.path.exists(fig_path):
                                zipf.write(fig_path, os.path.basename(fig_path))
                    self.func.alert_success(f"PNG打包导出成功: {save_path}")
                except Exception as e:
                    self.func.alert_failure(f"PNG打包导出失败: {str(e)}")
        else:
            # 单基因导出
            self._export_image('png')

    def on_export_pdf(self):
        """导出PDF（多基因模式打包为ZIP）"""
        if not self.all_fig_paths:
            if self.adata is not None:
                self._replot_and_export('pdf')
            else:
                self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_km_data) > 1:
            # 多基因模式：R生成SVG→Python组合→svglib转PDF→打包成ZIP
            save_path = self.func.get_save_file_path(
                "导出PDF（ZIP）",
                f"{self.dataset_name}_km.zip",
                "ZIP Files (*.zip)"
            )

            if save_path:
                try:
                    import zipfile
                    plot_params = self.func.get_plot_params()
                    width = plot_params.get('plot_width', 6)
                    height = plot_params.get('plot_height', 8)
                    
                    # 生成每个基因的PDF
                    for gene_name, df in self.all_km_data:
                        pdf_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.pdf")
                        
                        title = self.func.get_title(f"{gene_name} {self.dataset_name}")
                        self.analysis.draw_km_plot_r(
                            df, 'time', 'state', 'group', gene_name,
                            output_path=pdf_path, title=title,
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
                    
                    # 打包单图PDF到ZIP
                    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for gene_name, df in self.all_km_data:
                            pdf_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.pdf")
                            if os.path.exists(pdf_path):
                                zipf.write(pdf_path, os.path.basename(pdf_path))
                    
                    self.func.alert_success(f"PDF打包导出成功: {save_path}")
                except Exception as e:
                    self.func.log(f"PDF打包导出失败: {str(e)}")
                    traceback.print_exc()
                    self.func.alert_failure(f"PDF打包导出失败: {str(e)}")
        else:
            # 单基因导出
            self._replot_and_export('pdf')

    def on_export_svg(self):
        """导出SVG（多基因模式打包为ZIP）"""
        if not self.all_fig_paths:
            if self.adata is not None:
                self._replot_and_export('svg')
            else:
                self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_km_data) > 1:
            # 多基因模式：R生成SVG→Python用lxml组合→打包成ZIP
            save_path = self.func.get_save_file_path(
                "导出SVG（ZIP）",
                f"{self.dataset_name}_km.zip",
                "ZIP Files (*.zip)"
            )

            if save_path:
                try:
                    import zipfile
                    plot_params = self.func.get_plot_params()
                    width = plot_params.get('plot_width', 6)
                    height = plot_params.get('plot_height', 8)
                    
                    # 第一步：R生成每个基因的矢量SVG
                    for gene_name, df in self.all_km_data:
                        svg_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.svg")
                        
                        title = self.func.get_title(f"{gene_name} {self.dataset_name}")
                        self.analysis.draw_km_plot_r(
                            df, 'time', 'state', 'group', gene_name,
                            output_path=svg_path, title=title,
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
                    
                    # 第二步：Python用lxml组合矢量SVG成网格布局组合图
                    combined_svg_path = self._draw_combined_km_plot(
                        self.all_km_data,
                        export_width=width,
                        export_height=height,
                        fmt='svg'
                    )
                    
                    # 第三步：打包成ZIP（包含组合图和所有单图）
                    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        if combined_svg_path and os.path.exists(combined_svg_path):
                            zipf.write(combined_svg_path, os.path.basename(combined_svg_path))
                        
                        for gene_name, df in self.all_km_data:
                            svg_path = os.path.join(self.dataset_output_dir or ".", f"{gene_name}_{self.dataset_name}_km.svg")
                            if os.path.exists(svg_path):
                                zipf.write(svg_path, os.path.basename(svg_path))
                    
                    self.func.alert_success(f"SVG打包导出成功: {save_path}")
                except Exception as e:
                    self.func.log(f"SVG打包导出失败: {str(e)}")
                    traceback.print_exc()
                    self.func.alert_failure(f"SVG打包导出失败: {str(e)}")
        else:
            # 单基因导出
            self._replot_and_export('svg')

    def on_export_csv(self):
        """导出CSV（多基因模式合并为单表）"""
        if not self.all_km_data:
            if self.adata is not None:
                self._export_csv()
            else:
                self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_km_data) > 1:
            # 多基因模式：合并所有数据到一个CSV
            save_path = self.func.get_save_file_path(
                "导出CSV（多基因合并）",
                f"{self.dataset_name}_km_merged.csv",
                "CSV Files (*.csv)"
            )

            if save_path:
                try:
                    import pandas as pd
                    all_dfs = []
                    for gene_name, df in self.all_km_data:
                        df_copy = df.copy()
                        df_copy['gene'] = gene_name
                        all_dfs.append(df_copy)
                    merged_df = pd.concat(all_dfs, ignore_index=True)
                    merged_df.to_csv(save_path, index=False, encoding='utf-8-sig')
                    self.func.alert_success(f"CSV合并导出成功: {save_path}")
                except Exception as e:
                    self.func.alert_failure(f"CSV合并导出失败: {str(e)}")
        else:
            # 单基因导出
            self._export_csv()

    def _export_image(self, fmt):
        """导出图片"""
        try:
            width, height = self.func.get_export_size()
            if width is None or height is None:
                width, height = 8, 6

            gene_name = self.func.get_gene_name() or ""
            if gene_name:
                default_name = f"{gene_name}_{self.dataset_name}_km.{fmt}"
            else:
                default_name = f"{self.dataset_name}_km.{fmt}"

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
            gene_name = self.func.get_gene_name()
            time_unit = self.func.get_time_unit()
            plot_params = self.func.get_plot_params()

            if not gene_name:
                self.func.alert_error("请输入基因名称")
                return

            width = plot_params.get('plot_width', 6)
            height = plot_params.get('plot_height', 8)

            # 单基因导出时带上基因名
            if gene_name:
                default_name = f"{gene_name}_{self.dataset_name}_km.{fmt}"
            else:
                default_name = f"{self.dataset_name}_km.{fmt}"

            filter_text = f"{fmt.upper()} Files (*.{fmt})"

            save_path = self.func.get_save_file_path(f"导出{fmt.upper()}", default_name, filter_text)
            if not save_path:
                return

            df = self.analysis.prepare_km_data(gene_name, time_unit)
            if df is None:
                self.func.alert_error(f"基因 {gene_name} 不存在或数据无效")
                return

            clinical_col = self.func.get_clinical_col()
            filter1_col = self.bulk_km_r_ui.bulk_km_filter1_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter1_enable.isChecked() else None
            filter1_groups = self.func.get_filter1_groups() if filter1_col else None
            filter2_col = self.bulk_km_r_ui.bulk_km_filter2_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter2_enable.isChecked() else None
            filter2_groups = self.func.get_filter2_groups() if filter2_col else None

            df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
            if df is None or len(df) < 10:
                self.func.alert_error("筛选后数据不足")
                return

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
                if not hasattr(df, 'columns') or 'group' not in df.columns:
                    self.func.alert_error("分组数据缺少group列")
                    return

            title = self.func.get_title(f"{gene_name} {self.dataset_name}")

            self.analysis.draw_km_plot_r(
                df, 'time', 'state', 'group', gene_name,
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
            gene_name = self.func.get_gene_name()
            time_unit = self.func.get_time_unit()

            if not gene_name:
                self.func.alert_error("请输入基因名称")
                return

            df = self.analysis.prepare_km_data(gene_name, time_unit)
            if df is None:
                self.func.alert_error(f"基因 {gene_name} 不存在或数据无效")
                return

            clinical_col = self.func.get_clinical_col()
            filter1_col = self.bulk_km_r_ui.bulk_km_filter1_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter1_enable.isChecked() else None
            filter1_groups = self.func.get_filter1_groups() if filter1_col else None
            filter2_col = self.bulk_km_r_ui.bulk_km_filter2_combo.currentText() if self.bulk_km_r_ui.bulk_km_filter2_enable.isChecked() else None
            filter2_groups = self.func.get_filter2_groups() if filter2_col else None

            df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
            if df is None or len(df) < 10:
                self.func.alert_error("筛选后数据不足")
                return

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

            # 单基因导出时带上基因名
            if gene_name:
                default_name = f"km_data_{gene_name}_{self.dataset_name}.csv"
            else:
                default_name = f"km_data_{self.dataset_name}.csv"
            filter_text = "CSV Files (*.csv)"

            save_path = self.func.get_save_file_path("导出CSV", default_name, filter_text)
            if not save_path:
                return

            df.to_csv(save_path, index=False, encoding='utf-8-sig')

            self.func.log(f"导出成功: {save_path}")
            happy(self.parent, "导出成功")

        except Exception as e:
            self.func.log(f"导出失败: {str(e)}")
            traceback.print_exc()
            wrong(self.parent, "导出失败")
