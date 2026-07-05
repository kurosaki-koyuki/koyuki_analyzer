# -*- coding: utf-8 -*-
"""
bulk KM曲线界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.bulk_layer.bulk_km_layer.bulk_km_analysis import BulkKmAnalysis
from script.analyzer_layer.bulk_layer.bulk_km_layer.ui_func_bulk_km import BulkKmFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect


class BulkKmBind:
    """bulk KM曲线功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, bulk_km_ui):
        self.parent = parent_window
        self.bulk_km_ui = bulk_km_ui
        self.analysis = BulkKmAnalysis()
        self.func = BulkKmFunc(bulk_km_ui, parent_window)
        self.func.analysis = self.analysis  # 引用analysis到func
        self.data_folder = None
        self.adata = None
        self.all_fig_paths = []
        self.all_km_data = []
        self.combined_fig_path = None
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_bulk_km_functions()
        self.bind_navigation()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.bulk_km_ui, 'btn_back_bulk_km'):
            self.bulk_km_ui.btn_back_bulk_km.clicked.connect(lambda: page_intersect.go_to_page_with_bind('bulk_top_page'))

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
        """绑定bulk KM曲线功能信号"""
        log_widget = getattr(self.bulk_km_ui, 'bulk_km_status_text', None)

        # 进入R模式按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_r_mode_btn'):
            self.bulk_km_ui.bulk_km_r_mode_btn.clicked.connect(self.go_to_km_r_page)

        # 分类列选择下拉框
        if hasattr(self.bulk_km_ui, 'bulk_km_clinical_combo'):
            self.bulk_km_ui.bulk_km_clinical_combo.currentIndexChanged.connect(self.on_clinical_changed)

        # 筛选1启用复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_filter1_enable'):
            self.bulk_km_ui.bulk_km_filter1_enable.stateChanged.connect(self.on_filter1_enabled)

        # 筛选1下拉框
        if hasattr(self.bulk_km_ui, 'bulk_km_filter1_combo'):
            self.bulk_km_ui.bulk_km_filter1_combo.currentIndexChanged.connect(self.on_filter1_combo_changed)

        # 筛选2启用复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_filter2_enable'):
            self.bulk_km_ui.bulk_km_filter2_enable.stateChanged.connect(self.on_filter2_enabled)

        # 筛选2下拉框
        if hasattr(self.bulk_km_ui, 'bulk_km_filter2_combo'):
            self.bulk_km_ui.bulk_km_filter2_combo.currentIndexChanged.connect(self.on_filter2_combo_changed)

        # 显示风险表格复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_show_table_check'):
            self.bulk_km_ui.bulk_km_show_table_check.stateChanged.connect(self.on_table_check_changed)

        # 出图尺寸输入框
        if hasattr(self.bulk_km_ui, 'bulk_km_plot_width_input'):
            self.bulk_km_ui.bulk_km_plot_width_input.textChanged.connect(self.on_plot_size_changed)
        if hasattr(self.bulk_km_ui, 'bulk_km_plot_height_input'):
            self.bulk_km_ui.bulk_km_plot_height_input.textChanged.connect(self.on_plot_size_changed)

        # 导出尺寸输入框
        if hasattr(self.bulk_km_ui, 'bulk_km_export_width'):
            self.bulk_km_ui.bulk_km_export_width.textChanged.connect(self.on_export_size_changed)
        if hasattr(self.bulk_km_ui, 'bulk_km_export_height'):
            self.bulk_km_ui.bulk_km_export_height.textChanged.connect(self.on_export_size_changed)

        # 两两比较启用复选框
        if hasattr(self.bulk_km_ui, 'bulk_km_pairwise_enable'):
            self.bulk_km_ui.bulk_km_pairwise_enable.stateChanged.connect(self.on_pairwise_enable_changed)

        # 生成KM曲线按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_btn_plot'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_btn_plot, self.generate_km_plot,
                                   log_widget, "绘图完成", "绘图失败")

        # 导出PNG按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_btn_export_png'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_btn_export_png, self.export_png,
                                   log_widget, "PNG导出完成", "PNG导出失败")

        # 导出PDF按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_btn_export_pdf'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_btn_export_pdf, self.export_pdf,
                                   log_widget, "PDF导出完成", "PDF导出失败")

        # 导出SVG按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_btn_export_svg'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_btn_export_svg, self.export_svg,
                                   log_widget, "SVG导出完成", "SVG导出失败")

        # 导出CSV按钮
        if hasattr(self.bulk_km_ui, 'bulk_km_btn_export_csv'):
            bind_button_with_sound(self.bulk_km_ui.bulk_km_btn_export_csv, self.export_csv,
                                   log_widget, "CSV导出完成", "CSV导出失败")

    # ---------- 页面导航 ----------

    def go_to_home(self):
        """返回主页"""
        page_intersect.go_to_home()

    def go_to_km_r_page(self):
        """进入R模式页面"""
        page_intersect.go_to_page_with_bind('bulk_km_r_page', self)

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
        self.func.set_combo_items(self.bulk_km_ui.bulk_km_h5ad_combo, h5ad_files)

        self.func.log(f"已扫描数据路径: {folder_path}")
        self.func.log(f"找到 {len(h5ad_files)} 个h5ad文件")

    def load_data(self):
        """加载bulk数据"""
        if not self.data_folder:
            self.func.alert_error("请先扫描数据路径")
            return

        selected_file = self.bulk_km_ui.bulk_km_h5ad_combo.currentText()
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

            # 检查是否有生存数据列
            if 'time' not in self.adata.obs.columns or 'time (month)' not in self.adata.obs.columns:
                self.adata = None
                self.analysis.set_adata(None)
                self.func.alert_error("这个数据集不能做生存曲线，因为缺少time或time (month)列")
                return

            self.dataset_name = os.path.splitext(selected_file)[0]
            self.dataset_output_dir = os.path.join(OUT_BASE, "bulk_km", self.dataset_name)
            os.makedirs(self.dataset_output_dir, exist_ok=True)
            self.analysis.set_dataset_output_dir(self.dataset_output_dir)
            self.analysis.set_dataset_name(self.dataset_name)

            n_samples, n_genes = self.adata.shape
            obs_columns = self.analysis.get_obs_columns()

            self.func.log(f"样本数: {n_samples}")
            self.func.log(f"基因数: {n_genes}")
            self.func.log(f"数据集: {self.dataset_name}")
            self.func.log(f"可用注释列: {len(obs_columns)} 个")

            # 更新分类列下拉框
            self.func.update_clinical_combo(obs_columns)

            # 更新提示文本
            self.func.update_hint_text(self.dataset_name, n_samples, n_genes)

            # 加载筛选下拉框内容
            self.func.load_clinical_columns_to_filter1()
            self.func.load_clinical_columns_to_filter2()

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
        if hasattr(self.bulk_km_ui, 'bulk_km_label'):
            self.func.clear_image(self.bulk_km_ui.bulk_km_label)

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
        selected_col = self.bulk_km_ui.bulk_km_clinical_combo.currentText()

        self.bulk_km_ui.bulk_km_pairwise_list.clear()

        if self.adata is None:
            self.func.hide_group_list()
            self.func.enable_pairwise_controls(False)
            return

        if selected_col == "全部":
            self.bulk_km_ui.bulk_km_show_global_check.setChecked(True)
            self.bulk_km_ui.bulk_km_pairwise_enable.setChecked(False)
            self.bulk_km_ui.bulk_km_pairwise_list.clear()
            self.bulk_km_ui.bulk_km_pairwise_list.addItem("High vs Low")
            self.bulk_km_ui.bulk_km_pairwise_list.selectAll()

            self.func.show_clinical_col_list(False)
            self.func.enable_pairwise_controls(False)
        else:
            self.bulk_km_ui.bulk_km_show_global_check.setChecked(False)
            self.bulk_km_ui.bulk_km_pairwise_enable.setChecked(True)

            groups = self.analysis.get_obs_unique_values(selected_col)
            self.func.update_group_list(groups)

            self.bulk_km_ui.bulk_km_pairwise_list.clear()
            for g in groups:
                self.bulk_km_ui.bulk_km_pairwise_list.addItem(f"{g} High vs Low")
            self.bulk_km_ui.bulk_km_pairwise_list.selectAll()

    # ---------- 筛选控件 ----------

    def on_filter1_enabled(self, state):
        """筛选1启用状态改变"""
        enabled = state == Qt.Checked
        self.func.on_filter1_enabled(enabled)

        if enabled and self.adata is not None:
            columns = self.analysis.get_obs_columns()
            self.func.update_filter_combo(self.bulk_km_ui.bulk_km_filter1_combo, columns)

    def on_filter1_combo_changed(self):
        """筛选1下拉框改变"""
        filter1_col = self.bulk_km_ui.bulk_km_filter1_combo.currentText()
        if filter1_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter1_col)
            self.func.update_filter_list(self.bulk_km_ui.bulk_km_filter1_list, groups)

    def on_filter2_enabled(self, state):
        """筛选2启用状态改变"""
        enabled = state == Qt.Checked
        self.func.on_filter2_enabled(enabled)

        if enabled and self.adata is not None:
            columns = self.analysis.get_obs_columns()
            self.func.update_filter_combo(self.bulk_km_ui.bulk_km_filter2_combo, columns)

    def on_filter2_combo_changed(self):
        """筛选2下拉框改变"""
        filter2_col = self.bulk_km_ui.bulk_km_filter2_combo.currentText()
        if filter2_col and self.adata is not None:
            groups = self.analysis.get_obs_unique_values(filter2_col)
            self.func.update_filter_list(self.bulk_km_ui.bulk_km_filter2_list, groups)

    def on_table_check_changed(self, state):
        """显示风险表格选项变化时更新出图尺寸"""
        self.func.on_table_check_changed(state)

    def on_plot_size_changed(self):
        """出图尺寸变化时同步到导出尺寸"""
        plot_width = self.bulk_km_ui.bulk_km_plot_width_input.text().strip()
        plot_height = self.bulk_km_ui.bulk_km_plot_height_input.text().strip()
        if plot_width and plot_width.replace('.', '').isdigit():
            self.func.sync_plot_size_to_export(float(plot_width), float(plot_height) if plot_height.replace('.', '').isdigit() else 6)

    def on_export_size_changed(self):
        """导出尺寸变化时同步到出图尺寸"""
        export_width = self.bulk_km_ui.bulk_km_export_width.text().strip()
        export_height = self.bulk_km_ui.bulk_km_export_height.text().strip()
        if export_width and export_width.replace('.', '').isdigit():
            self.func.sync_export_size_to_plot(float(export_width), float(export_height) if export_height.replace('.', '').isdigit() else 6)

    def on_pairwise_enable_changed(self, state):
        """两两比较启用状态改变"""
        enabled = state == Qt.Checked
        self.bulk_km_ui.bulk_km_pairwise_list.setEnabled(enabled)

    # ---------- KM绘图 ----------

    def generate_km_plot(self):
        """生成KM曲线"""
        multi_gene_text = self.func.get_multi_gene_list()
        multi_gene_mode = False
        multi_gene_list = []

        if multi_gene_text:
            lines = [line.strip() for line in multi_gene_text.split('\n') if line.strip()]
            if lines:
                valid_genes = []
                invalid_genes = []
                for gene in lines:
                    if self.analysis.get_gene_exists(gene):
                        valid_genes.append(gene)
                    else:
                        invalid_genes.append(gene)

                if not valid_genes:
                    self.func.alert_error(f"所有输入的基因都不存在于数据集中:\n{', '.join(invalid_genes)}")
                    return

                if invalid_genes:
                    self.func.log(f"以下基因不存在于数据集中，已跳过:\n{', '.join(invalid_genes)}")

                multi_gene_list = valid_genes
                multi_gene_mode = True

        gene_name = self.func.get_gene_name()

        if not multi_gene_mode and not gene_name:
            self.func.alert_error("请输入基因名称或在多基因测定区域输入基因")
            return

        if self.adata is None:
            self.func.alert_error("请先加载数据")
            return

        if not multi_gene_mode and not self.analysis.get_gene_exists(gene_name):
            self.func.alert_error(f"基因 {gene_name} 不存在于数据集中")
            return

        self.func.log("正在生成KM曲线...")

        try:
            time_unit = self.func.get_time_unit()
            params = self.func.get_plot_params()

            # 确定要绘图的基因列表
            if multi_gene_mode:
                genes_to_plot = multi_gene_list
                self.func.log(f"多基因模式: 准备处理 {len(genes_to_plot)} 个基因")
            else:
                genes_to_plot = [gene_name]

            # 重置存储列表
            self.all_fig_paths = []
            self.all_km_data = []
            self.combined_fig_path = None

            time_label = 'Time (months)' if time_unit == 'month' else 'Time (days)'

            # 确定要绘图的基因列表
            if multi_gene_mode:
                genes_to_plot = multi_gene_list
                self.func.log(f"多基因模式: 准备处理 {len(genes_to_plot)} 个基因")
            else:
                genes_to_plot = [gene_name]

            # 重置存储列表
            self.all_fig_paths = []
            self.all_km_data = []
            self.combined_fig_path = None

            # 获取筛选参数
            filter1_col = None
            filter1_groups = []
            if self.bulk_km_ui.bulk_km_filter1_enable.isChecked():
                filter1_col = self.bulk_km_ui.bulk_km_filter1_combo.currentText()
                filter1_groups = self.func.get_filter1_groups()

            filter2_col = None
            filter2_groups = []
            if self.bulk_km_ui.bulk_km_filter2_enable.isChecked():
                filter2_col = self.bulk_km_ui.bulk_km_filter2_combo.currentText()
                filter2_groups = self.func.get_filter2_groups()

            clinical_col = self.func.get_clinical_col()

            # 逐个基因绘制KM曲线
            for i, current_gene in enumerate(genes_to_plot):
                if multi_gene_mode:
                    self.func.log(f"正在处理基因 {i+1}/{len(genes_to_plot)}: {current_gene}")

                # 准备单个基因的数据
                df = self.analysis.prepare_km_data(current_gene, time_unit)
                if df is None:
                    if multi_gene_mode:
                        self.func.log(f"基因 {current_gene} 数据准备失败，跳过")
                        continue
                    else:
                        self.func.alert_error(f"基因 {current_gene} 数据准备失败")
                        return

                # 应用筛选条件
                df = self.analysis.filter_data(df, filter1_col, filter1_groups, filter2_col, filter2_groups)
                if df is None or len(df) < 10:
                    if multi_gene_mode:
                        self.func.log(f"基因 {current_gene} 筛选后样本数太少，跳过")
                        continue
                    else:
                        self.func.alert_error("筛选后样本数太少，无法分析")
                        return

                # 分组
                if clinical_col == "全部":
                    df, n_high, n_low = self.analysis.split_groups_simple(df)
                    self.func.log(f"  样本数: {len(df)}, High: {n_high}, Low: {n_low}")
                else:
                    selected_groups = self.func.get_selected_groups()
                    df = self.analysis.split_groups_by_clinical(df, clinical_col, selected_groups)
                    if len(df) == 0:
                        if multi_gene_mode:
                            self.func.log(f"基因 {current_gene} 没有足够的样本进行分析，跳过")
                            continue
                        else:
                            self.func.alert_error("没有足够的样本进行分析")
                            return
                    for g in sorted(df['group'].unique()):
                        self.func.log(f"  - {g}: {len(df[df['group'] == g])}")

                # 确定标题
                title = self.func.get_title(f"{current_gene} {self.dataset_name}")

                # 绘制KM曲线
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
                    gene_name=current_gene,
                    export_width=params['plot_width'],
                    export_height=params['plot_height']
                )

                # 保存单图路径和数据
                self.all_fig_paths.append(fig_path)
                self.all_km_data.append((current_gene, df.copy()))

            # 多基因模式下生成组合图
            if multi_gene_mode and len(self.all_km_data) > 0:
                combined_fig_path = self.analysis.draw_combined_km_plot(
                    self.all_km_data,
                    time_label=time_label,
                    title_size=params['title_size'],
                    legend_size=params['legend_size'],
                    axis_size=params['axis_size'],
                    pval_size=params['pval_size'],
                    show_table=params['show_table'],
                    table_size=params['table_size'],
                    pval_mode=params['pval_mode'],
                    show_global_pval=params['show_global_pval'],
                    show_pairwise=params['show_pairwise'],
                    selected_pairwise=params['selected_pairwise'],
                    show_ci=params['show_ci'],
                    show_n=params['show_n'],
                    export_width=params['plot_width'],
                    export_height=params['plot_height'],
                    dataset_name=self.dataset_name
                )
                self.all_fig_paths.insert(0, combined_fig_path)
                self.combined_fig_path = combined_fig_path

                # 显示组合图
                self.func.display_image(self.bulk_km_ui.bulk_km_label, combined_fig_path)
            else:
                # 单基因模式显示最后一张图
                if self.all_fig_paths:
                    self.func.display_image(self.bulk_km_ui.bulk_km_label, self.all_fig_paths[-1])

            if multi_gene_mode:
                self.func.log(f"多基因模式处理完成，共处理 {len(genes_to_plot)} 个基因")
            else:
                self.func.log("KM曲线生成完成")

        except Exception as e:
            self.func.log(f"绘图失败: {str(e)}")
            self.func.alert_failure(f"绘图失败: {str(e)}")
            traceback.print_exc()

    # ---------- 导出 ----------

    def export_png(self):
        """导出PNG（多基因模式打包为ZIP）"""
        if not self.all_fig_paths:
            self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_fig_paths) > 1:
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
            # 单基因导出，文件名带上基因名
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
        """导出PDF（多基因模式打包为ZIP）"""
        if not self.all_fig_paths:
            self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_fig_paths) > 1:
            save_path = self.func.get_save_file_path(
                "导出PDF（ZIP）",
                f"{self.dataset_name}_km.zip",
                "ZIP Files (*.zip)"
            )

            if save_path:
                try:
                    import zipfile
                    from PIL import Image
                    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for fig_path in self.all_fig_paths:
                            if os.path.exists(fig_path):
                                base_name = os.path.splitext(os.path.basename(fig_path))[0]
                                pdf_path = os.path.join(self.analysis.dataset_output_dir, f"{base_name}.pdf")
                                img = Image.open(fig_path)
                                img = img.convert('RGB')
                                img.save(pdf_path, 'PDF', resolution=150)
                                zipf.write(pdf_path, os.path.basename(pdf_path))
                    self.func.alert_success(f"PDF打包导出成功: {save_path}")
                except ImportError:
                    self.func.alert_failure("需要安装PIL库来导出PDF")
                except Exception as e:
                    self.func.alert_failure(f"PDF打包导出失败: {str(e)}")
        else:
            # 单基因导出，文件名带上基因名
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
        """导出SVG（多基因模式打包为ZIP）"""
        if not self.all_fig_paths:
            self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_fig_paths) > 1:
            save_path = self.func.get_save_file_path(
                "导出SVG（ZIP）",
                f"{self.dataset_name}_km.zip",
                "ZIP Files (*.zip)"
            )

            if save_path:
                try:
                    import zipfile
                    with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for fig_path in self.all_fig_paths:
                            if os.path.exists(fig_path):
                                base_name = os.path.splitext(os.path.basename(fig_path))[0]
                                svg_path = os.path.join(self.analysis.dataset_output_dir, f"{base_name}.svg")
                                self.analysis.export_svg(svg_path)
                                if os.path.exists(svg_path):
                                    zipf.write(svg_path, os.path.basename(svg_path))
                    self.func.alert_success(f"SVG打包导出成功: {save_path}")
                except Exception as e:
                    self.func.alert_failure(f"SVG打包导出失败: {str(e)}")
        else:
            # 单基因导出，文件名带上基因名
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
        """导出CSV（多基因模式合并为单表）"""
        if not self.all_km_data:
            self.func.alert_error("请先生成KM曲线")
            return

        if len(self.all_km_data) > 1:
            merged_df = None
            for gene_name, df in self.all_km_data:
                gene_df = df[['time', 'state']].copy()
                gene_df[f'{gene_name}_group'] = df['group']
                if merged_df is None:
                    merged_df = gene_df
                else:
                    merged_df = merged_df.merge(gene_df, on=['time', 'state'], how='outer')

            if merged_df is not None:
                save_path = self.func.get_save_file_path(
                    "导出CSV",
                    f"{self.dataset_name}_km_data.csv",
                    "CSV Files (*.csv)"
                )

                if save_path:
                    merged_df.to_csv(save_path, index=False)
                    self.func.alert_success(f"CSV导出成功: {save_path}")
                else:
                    self.func.alert_failure("CSV导出失败")
            else:
                self.func.alert_failure("CSV导出失败：无数据")
        else:
            # 单基因导出，文件名带上基因名
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