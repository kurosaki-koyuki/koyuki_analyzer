# -*- coding: utf-8 -*-
"""
bulk 一致性分析界面绑定脚本 - 绑定按钮信号、调用业务逻辑层、驱动analysis层
"""

from script.utils_layer.import_config import os, traceback, np, pd, plt, FigureCanvas, QFileDialog, QMessageBox, QApplication, QListWidgetItem

from script.analyzer_layer.bulk_layer.bulk_cluster_layer.bulk_cluster_analysis import get_bulk_cluster_analysis
from script.analyzer_layer.bulk_layer.bulk_cluster_layer.ui_func_bulk_cluster import BulkClusterFunc
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong
from script.utils_layer.page_intersect import page_intersect


class BulkClusterBind:
    """bulk 一致性分析绑定类"""

    def __init__(self, parent_widget, bulk_cluster_ui):
        self.parent = parent_widget
        self.bulk_cluster_ui = bulk_cluster_ui
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.analysis = get_bulk_cluster_analysis()
        self.func = BulkClusterFunc(bulk_cluster_ui, parent_widget)
        self.func.analysis = self.analysis
        self.current_consensus_path = None
        self.current_cdf_pac_path = None
        self.current_heatmap_path = None
        self.optimal_k = None
        self._bind_signals()
        self._init_page()

    def _bind_signals(self):
        """绑定按钮点击信号"""
        # 返回按钮
        self.bulk_cluster_ui.btn_back.clicked.connect(self.on_back_clicked)

        # 运行按钮（阶段一~四）
        self.bulk_cluster_ui.bulk_cluster_btn_stage1.clicked.connect(self.on_stage1_clicked)
        self.bulk_cluster_ui.bulk_cluster_btn_stage2.clicked.connect(self.on_stage2_clicked)
        self.bulk_cluster_ui.bulk_cluster_btn_stage3.clicked.connect(self.on_stage3_clicked)
        self.bulk_cluster_ui.bulk_cluster_btn_stage4.clicked.connect(self.on_stage4_clicked)

        # 分析模式切换 / 列表内MAD勾选（两者共用 on_mode_changed，幂等刷新显隐）
        self.bulk_cluster_ui.bulk_cluster_mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.bulk_cluster_ui.bulk_cluster_mad_filter_check.stateChanged.connect(self.on_mode_changed)

        # 固定k勾选
        self.bulk_cluster_ui.bulk_cluster_fix_k_check.stateChanged.connect(self.on_fix_k_changed)

        # 导出按钮
        self.bulk_cluster_ui.bulk_cluster_btn_export_png.clicked.connect(self.on_export_png)
        self.bulk_cluster_ui.bulk_cluster_btn_export_pdf.clicked.connect(self.on_export_pdf)
        self.bulk_cluster_ui.bulk_cluster_btn_export_svg.clicked.connect(self.on_export_svg)
        self.bulk_cluster_ui.bulk_cluster_btn_export_csv.clicked.connect(self.on_export_csv)
        self.bulk_cluster_ui.bulk_cluster_btn_export_h5ad.clicked.connect(self.on_export_h5ad)

        # Debug按钮
        self.bulk_cluster_ui.bulk_cluster_debug_btn.clicked.connect(self.on_debug_clicked)

        # 分类列选择变化
        self.bulk_cluster_ui.bulk_cluster_clinical_combo.currentIndexChanged.connect(self.on_clinical_combo_changed)

        # 筛选1启用
        self.bulk_cluster_ui.bulk_cluster_filter1_enable.stateChanged.connect(self.on_filter1_enable_changed)
        self.bulk_cluster_ui.bulk_cluster_filter1_combo.currentIndexChanged.connect(self.on_filter1_col_changed)

        # 筛选2启用
        self.bulk_cluster_ui.bulk_cluster_filter2_enable.stateChanged.connect(self.on_filter2_enable_changed)
        self.bulk_cluster_ui.bulk_cluster_filter2_combo.currentIndexChanged.connect(self.on_filter2_col_changed)

        # 初始禁用阶段二、三、四按钮
        self.bulk_cluster_ui.bulk_cluster_btn_stage2.setEnabled(False)
        self.bulk_cluster_ui.bulk_cluster_btn_stage3.setEnabled(False)
        self.bulk_cluster_ui.bulk_cluster_btn_stage4.setEnabled(False)

    def _init_page(self):
        """初始化页面"""
        self.func.log_set_default()
        self.func.update_r_version_label()
        self.func.load_clinical_columns_to_filter1()
        self.func.load_clinical_columns_to_filter2()

        # 基因列表 / 分析模式 / 固定k / 参考分组列 的初始状态（契约 §6.2）
        self.func.set_gene_list_items(self.analysis.scan_gene_lists())
        self.func.apply_mode_visibility(self.func.get_analysis_mode())
        self.func.apply_fix_k_state(False)
        self.func.update_eval_ref_combo([])      # 同步数据前先清空

    # ============ 导航 ============

    def on_back_clicked(self):
        """返回bulk主页"""
        page_intersect.go_to_page_with_bind('bulk_top_page')

    # ============ 数据同步 ============

    def sync_data_from_bulk_main(self, bulk_top_bind):
        """从bulk主页同步数据"""
        if not bulk_top_bind or not bulk_top_bind.analysis:
            return

        self.adata = bulk_top_bind.analysis.adata
        self.dataset_name = bulk_top_bind.analysis.dataset_name
        self.dataset_output_dir = bulk_top_bind.analysis.dataset_output_dir

        self.analysis.set_adata(self.adata)
        self.analysis.set_dataset_name(self.dataset_name)
        self.analysis.set_dataset_output_dir(self.dataset_output_dir)

        if self.adata is not None:
            self.func.log(f"已从bulk主页同步数据: {self.dataset_name}")
            n_samples, n_genes = self.analysis.get_adata_shape()
            self.func.log(f"样本数: {n_samples}, 基因数: {n_genes}")

            # 更新分类列下拉框
            obs_cols = self.analysis.get_obs_columns()
            self.func.update_clinical_combo(obs_cols)
            self.func.load_clinical_columns_to_filter1()
            self.func.load_clinical_columns_to_filter2()

            # 同步数据后刷新基因列表选项与参考分组列（契约 §6.3）
            self.func.set_gene_list_items(self.analysis.scan_gene_lists())
            self.func.update_eval_ref_combo(self.analysis.get_obs_columns())

    # ============ 筛选控件 ============

    def on_clinical_combo_changed(self):
        """分类列选择变化"""
        clinical_col = self.func.get_clinical_col()
        if clinical_col == "全部":
            self.func.hide_group_list()
        else:
            groups = self.analysis.get_obs_unique_values(clinical_col)
            self.func.update_group_list(groups)

    def on_filter1_enable_changed(self, state):
        """筛选1启用状态变化"""
        enabled = state == 2  # Qt.Checked
        self.func.on_filter1_enabled(enabled)
        if enabled:
            self._update_filter_list(self.bulk_cluster_ui.bulk_cluster_filter1_combo,
                                     self.bulk_cluster_ui.bulk_cluster_filter1_list)

    def on_filter2_enable_changed(self, state):
        """筛选2启用状态变化"""
        enabled = state == 2
        self.func.on_filter2_enabled(enabled)
        if enabled:
            self._update_filter_list(self.bulk_cluster_ui.bulk_cluster_filter2_combo,
                                     self.bulk_cluster_ui.bulk_cluster_filter2_list)

    def on_filter1_col_changed(self):
        """筛选1分类列变化"""
        if self.bulk_cluster_ui.bulk_cluster_filter1_enable.isChecked():
            self._update_filter_list(self.bulk_cluster_ui.bulk_cluster_filter1_combo,
                                     self.bulk_cluster_ui.bulk_cluster_filter1_list)

    def on_filter2_col_changed(self):
        """筛选2分类列变化"""
        if self.bulk_cluster_ui.bulk_cluster_filter2_enable.isChecked():
            self._update_filter_list(self.bulk_cluster_ui.bulk_cluster_filter2_combo,
                                     self.bulk_cluster_ui.bulk_cluster_filter2_list)

    def _update_filter_list(self, combo, list_widget):
        """更新筛选列表内容"""
        col_name = combo.currentText()
        if col_name and col_name != "全部":
            values = self.analysis.get_obs_unique_values(col_name)
            self.func.update_filter_list(list_widget, values)

    # ============ 模式联动 ============

    def on_mode_changed(self):
        """分析模式切换 / 列表内MAD勾选变化：统一刷新显隐（幂等）"""
        self.func.apply_mode_visibility(self.func.get_analysis_mode())

    def on_fix_k_changed(self):
        """固定k勾选变化：启用/禁用固定k输入框"""
        self.func.apply_fix_k_state(self.bulk_cluster_ui.bulk_cluster_fix_k_check.isChecked())

    # ============ 三阶段运行 ============

    def on_stage1_clicked(self):
        """阶段一：聚类计算"""
        if self.adata is None:
            self.func.alert_error("请先从bulk主页加载数据")
            return

        if not self.analysis.is_available():
            self.func.alert_error("R环境不可用，请检查R安装")
            return

        # 获取参数
        params = self.func.get_stage1_params()

        # 获取筛选条件
        clinical_col = self.func.get_clinical_col()
        clinical_groups = self.func.get_selected_groups() if clinical_col != "全部" else None

        filter1_col = None
        filter1_groups = None
        if self.bulk_cluster_ui.bulk_cluster_filter1_enable.isChecked():
            filter1_col = self.bulk_cluster_ui.bulk_cluster_filter1_combo.currentText()
            filter1_groups = self.func.get_filter1_groups()

        filter2_col = None
        filter2_groups = None
        if self.bulk_cluster_ui.bulk_cluster_filter2_enable.isChecked():
            filter2_col = self.bulk_cluster_ui.bulk_cluster_filter2_combo.currentText()
            filter2_groups = self.func.get_filter2_groups()

        # 参数验证
        if params['min_k'] >= params['max_k']:
            self.func.alert_error("min_k 必须小于 max_k")
            return

        if params['p_item'] <= 0 or params['p_item'] > 1:
            self.func.alert_error("pItem 必须在 (0, 1] 范围内")
            return

        if params['p_feature'] <= 0 or params['p_feature'] > 1:
            self.func.alert_error("pFeature 必须在 (0, 1] 范围内")
            return

        # 契约 §6.6：基因列表分型模式必须先选列表文件
        # 四个新键统一用带默认值的取法（W1 未就绪或缺键时也不会抛异常终止程序）
        mode = params.get('mode', 'traditional')
        gene_list_file = params.get('gene_list_file', '')
        mad_filter_in_list = params.get('mad_filter_in_list', False)
        seed = params.get('seed', 123456)
        if mode == 'signature' and not gene_list_file:
            self.func.alert_error("基因列表分型模式需要先选择基因列表文件")
            return

        # 契约 §6.6：小基因列表 + Pearson 距离仅提示、不阻断（预估失败则静默跳过）
        small_gene_list_hint = False
        if mode == 'signature' and params['distance'] == 'pearson':
            try:
                gene_list = self.analysis.read_gene_list_file(gene_list_file)
                match_info = self.analysis.match_gene_list(gene_list, self.adata.var_names)
                small_gene_list_hint = match_info.get('n_matched', 0) < 200
            except Exception:
                small_gene_list_hint = False

        # 执行
        self.func.log_clear()
        self.func.log(f"========== 阶段一：聚类计算 ==========")
        self.func.log(f"参数: MAD={params['mad_threshold']}, reps={params['reps']}")
        self.func.log(f"聚类算法: {params['cluster_alg']}, 距离: {params['distance']}")
        self.func.log(f"pItem={params['p_item']}, pFeature={params['p_feature']}")
        self.func.log(f"k值区间: {params['min_k']}~{params['max_k']}")
        self.func.log(f"分析模式: {'基因列表分型' if mode == 'signature' else '传统一致性聚类'}")
        if mode == 'signature':
            self.func.log(f"基因列表文件: {gene_list_file}")
        self.func.log(f"随机种子: {seed}")

        if small_gene_list_hint:
            self.func.log("[提示] 基因数较少时 Pearson 距离受单个基因影响较大，建议改用 spearman/euclidean")

        # 打印筛选信息
        n_total = self.analysis.get_adata_shape()[0]
        self.func.log(f"总样本数: {n_total}")

        filter_info = []
        if clinical_col and clinical_groups:
            filter_info.append(f"分类列: {clinical_col}, 选中: {len(clinical_groups)}组")
        if filter1_col and filter1_groups:
            filter_info.append(f"筛选1: {filter1_col}, 选中: {len(filter1_groups)}组")
        if filter2_col and filter2_groups:
            filter_info.append(f"筛选2: {filter2_col}, 选中: {len(filter2_groups)}组")

        if filter_info:
            self.func.log("筛选条件: " + "; ".join(filter_info))
        else:
            self.func.log("筛选条件: 无（使用全部样本）")

        self.func.log("开始聚类计算，请耐心等待...")

        QApplication.processEvents()

        try:
            success = self.analysis.run_stage1_cluster(
                mad_threshold=params['mad_threshold'],
                reps=params['reps'],
                cluster_alg=params['cluster_alg'],
                distance=params['distance'],
                p_item=params['p_item'],
                p_feature=params['p_feature'],
                min_k=params['min_k'],
                max_k=params['max_k'],
                plot_format=params['plot_format'],
                filter1_col=filter1_col, filter1_groups=filter1_groups,
                filter2_col=filter2_col, filter2_groups=filter2_groups,
                clinical_col=clinical_col if clinical_col != "全部" else None,
                clinical_groups=clinical_groups,
                mode=mode,
                gene_list_file=gene_list_file,
                mad_filter_in_list=mad_filter_in_list,
                seed=seed,
            )

            if success:
                self.func.log("阶段一聚类计算完成！")
                self.func.alert_success("聚类计算完成！\n可进行阶段二：CDF+PAC曲线")

                # 启用阶段二、三、四按钮
                self.bulk_cluster_ui.bulk_cluster_btn_stage2.setEnabled(True)
                self.bulk_cluster_ui.bulk_cluster_btn_stage3.setEnabled(True)
                self.bulk_cluster_ui.bulk_cluster_btn_stage4.setEnabled(True)

                # 更新阶段三k值下拉框选项
                self._update_final_k_combo(params['min_k'], params['max_k'])

                # 显示一致性矩阵图（从临时目录读取）
                self._display_consensus_images()

        except Exception as e:
            self.func.log(f"阶段一失败: {str(e)}")
            self.func.alert_failure(f"阶段一失败: {str(e)}")

    def on_stage2_clicked(self):
        """阶段二：CDF+PAC曲线"""
        if not self.analysis.get_stage_status()['stage1']:
            self.func.alert_error("请先运行阶段一聚类计算")
            return

        params = self.func.get_stage1_params()

        # 固定k参数（契约 §6.7）
        fix_k_params = self.func.get_fix_k_params()

        # 导出尺寸
        export_width, export_height = self.func.get_export_size()
        if export_width is None or export_height is None:
            export_width, export_height = 10, 6

        # 输出路径（临时文件）
        temp_path = os.path.join(self.analysis._temp_dir or ".",
                                 f"{self.dataset_name}_cdf_pac.png")

        self.func.log(f"\n========== 阶段二：CDF+PAC曲线 ==========")
        if fix_k_params['fix_k_enable']:
            self.func.log(f"固定k: {fix_k_params['fixed_k']}（跳过 PAC 自动选）")
        QApplication.processEvents()

        try:
            result = self.analysis.run_stage2_cdf_pac(
                min_k=params['min_k'],
                max_k=params['max_k'],
                output_path=temp_path,
                plot_width=export_width,
                plot_height=export_height,
                fix_k_enable=fix_k_params['fix_k_enable'],
                fixed_k=fix_k_params['fixed_k']
            )

            if isinstance(result, tuple):
                output_path, opt_k = result
            else:
                output_path = result
                opt_k = None

            self.current_cdf_pac_path = output_path
            self.optimal_k = opt_k

            # 显示CDF+PAC图
            self.func.display_image(self.bulk_cluster_ui.bulk_cluster_label_cdf, output_path)
            self.func.display_image(self.bulk_cluster_ui.bulk_cluster_label_pac, output_path)

            self.func.log(f"CDF+PAC曲线生成完成！")
            if opt_k:
                self.func.log(f"建议最优k值: {opt_k}")
                self.func.alert_success(f"CDF+PAC曲线生成完成！\n建议最优k值: {opt_k}")
            else:
                self.func.alert_success("CDF+PAC曲线生成完成！")

        except Exception as e:
            self.func.log(f"阶段二失败: {str(e)}")
            self.func.alert_failure(f"阶段二失败: {str(e)}")

    def on_stage3_clicked(self):
        """阶段三：生成最终热图"""
        if not self.analysis.get_stage_status()['stage1']:
            self.func.alert_error("请先运行阶段一聚类计算")
            return

        params = self.func.get_stage3_params()

        # 输出路径（临时文件）
        temp_path = os.path.join(self.analysis._temp_dir or ".",
                                 f"{self.dataset_name}_heatmap_k{params['final_k']}.png")

        self.func.log(f"\n========== 阶段三：生成最终热图 ==========")
        self.func.log(f"最终k值: {params['final_k']}")
        self.func.log(f"输出模式: {params['output_mode']}")
        QApplication.processEvents()

        try:
            output_path = self.analysis.run_stage3_heatmap(
                final_k=params['final_k'],
                output_mode=params['output_mode'],
                output_path=temp_path,
                heatmap_width=params['heatmap_width'],
                heatmap_height=params['heatmap_height'],
                color_scheme=params['color_scheme'],
                title_font_size=params['title_font_size'],
                legend_font_size=params['legend_font_size'],
                clustering_method=params['clustering_method']
            )

            self.current_heatmap_path = output_path

            # 显示热图
            self.func.display_image(self.bulk_cluster_ui.bulk_cluster_label_heatmap, output_path)

            # 将聚类结果写入adata.obs
            is_filtered = self.func.is_filtered()
            col_name = self.analysis.save_consensus_to_adata(
                final_k=params['final_k'],
                is_filtered=is_filtered
            )
            self.func.log(f"聚类结果已写入adata.obs['{col_name}']")
            self.func.log(f"其他分析界面（KM、Cox等）同步数据后可在分类下拉框中选择此列")

            # 更新本界面下拉框
            obs_cols = self.analysis.get_obs_columns()
            self.func.update_clinical_combo(obs_cols)
            self.func.load_clinical_columns_to_filter1()
            self.func.load_clinical_columns_to_filter2()

            self.func.log(f"最终热图(k={params['final_k']})生成完成！")
            self.func.log(f"final_cluster_k 已保存到R内存")
            self.func.alert_success(f"最终热图生成完成！\n聚类结果已存入adata.obs[{col_name}]")

        except Exception as e:
            self.func.log(f"阶段三失败: {str(e)}")
            self.func.alert_failure(f"阶段三失败: {str(e)}")

    def on_stage4_clicked(self):
        """阶段四：分型评估 + 基因×样本表达热图"""
        # 1. 前置检查：阶段一必须已完成
        if not self.analysis.get_stage_status()['stage1']:
            self.func.alert_error("请先运行阶段一聚类计算")
            return

        # 2. 取三组参数
        stage1 = self.func.get_stage1_params()
        stage3 = self.func.get_stage3_params()
        s4 = self.func.get_stage4_params()

        min_k = stage1['min_k']
        max_k = stage1['max_k']
        final_k = stage3['final_k']

        # 3. 两项校验
        if final_k < min_k or final_k > max_k:
            self.func.alert_error(f"选定 k={final_k} 不在 K 范围 {min_k}~{max_k} 内")
            return

        if (s4['eval_ref_col'] == '不使用'
                and not s4['silhouette_enable']
                and not s4['gene_heatmap_enable']):
            self.func.alert_error("请至少选择一项评估内容：参考分组列 / 轮廓系数 / 基因表达热图")
            return

        # 4. 三个输出路径（临时文件）
        base = self.analysis._temp_dir or "."
        eval_plot_path = os.path.join(base, f"{self.dataset_name}_eval.png")
        gene_heatmap_path = os.path.join(base, f"{self.dataset_name}_gene_heatmap.png")
        eval_text_path = os.path.join(base, f"{self.dataset_name}_eval.txt")

        self.func.log(f"\n========== 阶段四：分型评估 ==========")
        self.func.log(f"最终k值: {final_k}（K 范围 {min_k}~{max_k}）")
        self.func.log(f"参考分组列: {s4['eval_ref_col']}")
        self.func.log(f"轮廓系数: {'开' if s4['silhouette_enable'] else '关'}, "
                      f"基因热图: {'开' if s4['gene_heatmap_enable'] else '关'}")
        QApplication.processEvents()

        try:
            # 5. 参考分组标签（与表达矩阵列对齐）
            ref_labels = self.analysis.get_ref_labels(s4['eval_ref_col'])

            # 6. 调用 analysis 层
            res = self.analysis.run_stage4_eval(
                min_k=min_k,
                max_k=max_k,
                final_k=final_k,
                eval_ref_col=s4['eval_ref_col'],
                silhouette_enable=s4['silhouette_enable'],
                gene_heatmap_enable=s4['gene_heatmap_enable'],
                gene_heatmap_max=s4['gene_heatmap_max'],
                eval_plot_path=eval_plot_path,
                gene_heatmap_path=gene_heatmap_path,
                eval_text_path=eval_text_path,
                color_scheme=stage3['color_scheme'],
                heatmap_width=stage3['heatmap_width'],
                heatmap_height=stage3['heatmap_height'],
                title_font_size=stage3['title_font_size'],
                legend_font_size=stage3['legend_font_size'],
                clustering_method=stage3['clustering_method'],
                ref_labels=ref_labels
            )

            # 7. 回显三处结果
            if res.get('eval_plot'):
                self.func.display_image(self.bulk_cluster_ui.bulk_cluster_label_eval_plot,
                                        res['eval_plot'])
            if res.get('eval_text'):
                self.func.display_text(self.bulk_cluster_ui.bulk_cluster_text_eval,
                                       res['eval_text'])
            if res.get('gene_heatmap'):
                self.func.display_image(self.bulk_cluster_ui.bulk_cluster_label_gene_heatmap,
                                        res['gene_heatmap'])
            else:
                self.func.log("未生成基因热图（未勾选或模式不适用）")

            # 8. 成功提示
            self.func.log("阶段四完成：分型评估已生成")
            self.func.alert_success("阶段四完成：分型评估已生成")

        except Exception as e:
            self.func.log(f"阶段四失败: {str(e)}")
            self.func.alert_failure(f"阶段四运行失败: {e}")

    # ============ 辅助方法 ============

    def _update_final_k_combo(self, min_k, max_k):
        """更新阶段三k值下拉框选项"""
        self.bulk_cluster_ui.bulk_cluster_final_k_combo.blockSignals(True)
        self.bulk_cluster_ui.bulk_cluster_final_k_combo.clear()
        for k in range(min_k, max_k + 1):
            self.bulk_cluster_ui.bulk_cluster_final_k_combo.addItem(str(k))
        # 如果有最优k，默认选中
        if self.optimal_k:
            idx = self.optimal_k - min_k
            if 0 <= idx < self.bulk_cluster_ui.bulk_cluster_final_k_combo.count():
                self.bulk_cluster_ui.bulk_cluster_final_k_combo.setCurrentIndex(idx)
        self.bulk_cluster_ui.bulk_cluster_final_k_combo.blockSignals(False)

    def _display_consensus_images(self):
        """显示一致性矩阵图（从临时目录读取）"""
        if not self.analysis._temp_dir or not os.path.exists(self.analysis._temp_dir):
            return

        # 查找临时目录中的热图文件
        png_files = [f for f in os.listdir(self.analysis._temp_dir) if f.endswith('.png')]
        if png_files:
            # 显示第一张作为预览
            first_img = os.path.join(self.analysis._temp_dir, sorted(png_files)[0])
            self.func.display_image(self.bulk_cluster_ui.bulk_cluster_label_consensus, first_img)
            self.current_consensus_path = first_img
            self.func.log(f"已加载 {len(png_files)} 张一致性矩阵图")

    # ============ 导出 ============

    def on_export_png(self):
        """导出PNG"""
        self._export_image('png')

    def on_export_pdf(self):
        """导出PDF"""
        self._export_image('pdf')

    def on_export_svg(self):
        """导出SVG"""
        self._export_image('svg')

    def on_export_csv(self):
        """导出CSV"""
        if not self.analysis.get_stage_status()['stage1']:
            self.func.alert_error("请先运行阶段一聚类计算")
            return

        params = self.func.get_stage3_params()

        default_name = f"{self.dataset_name}_cluster_k{params['final_k']}.csv"
        save_path = self.func.get_save_file_path(
            "导出CSV文件", default_name, "CSV文件 (*.csv)"
        )

        if not save_path:
            return

        try:
            self.analysis.export_csv(params['final_k'], save_path)
            self.func.log(f"CSV导出成功: {save_path}")
            self.func.alert_success(f"CSV导出成功:\n{save_path}")
        except Exception as e:
            self.func.log(f"CSV导出失败: {str(e)}")
            self.func.alert_failure(f"CSV导出失败: {str(e)}")

    def on_export_h5ad(self):
        """导出h5ad（带聚类结果）"""
        if self.adata is None:
            self.func.alert_error("未加载数据")
            return

        default_name = f"{self.dataset_name}_with_clusters.h5ad"
        save_path = self.func.get_save_file_path(
            "导出h5ad文件", default_name, "h5ad文件 (*.h5ad)"
        )

        if not save_path:
            return

        try:
            self.analysis.export_h5ad(save_path)
            self.func.log(f"h5ad导出成功: {save_path}")
            self.func.alert_success(f"h5ad导出成功:\n{save_path}")
        except Exception as e:
            self.func.log(f"h5ad导出失败: {str(e)}")
            self.func.alert_failure(f"h5ad导出失败: {str(e)}")

    def _export_image(self, format_type):
        """导出图片的通用方法"""
        if not self.analysis.get_stage_status()['stage1']:
            self.func.alert_error("请先运行阶段一聚类计算")
            return

        # 获取当前Tab页对应的图片路径
        current_tab = self.bulk_cluster_ui.bulk_cluster_plot_tabs.currentIndex()
        tab_names = ['一致性矩阵', 'CDF曲线', 'PAC曲线', '最终热图']
        current_path = None

        if current_tab == 0:
            current_path = self.current_consensus_path
        elif current_tab == 1 or current_tab == 2:
            current_path = self.current_cdf_pac_path
        elif current_tab == 3:
            current_path = self.current_heatmap_path

        if not current_path or not os.path.exists(current_path):
            self.func.alert_error(f"当前Tab（{tab_names[current_tab]}）没有可导出的图片")
            return

        # 获取导出尺寸
        export_width, export_height = self.func.get_export_size()
        if export_width is None or export_height is None:
            export_width, export_height = 8, 6

        default_name = f"{self.dataset_name}_{tab_names[current_tab]}.{format_type}"
        save_path = self.func.get_save_file_path(
            f"导出{format_type.upper()}文件", default_name,
            f"{format_type.upper()}文件 (*.{format_type})"
        )

        if not save_path:
            return

        try:
            # 重新调用R生成指定格式的图
            params = self.func.get_stage3_params()
            current_k = params['final_k']

            if current_tab == 3:
                # 最终热图：重新生成指定格式
                output_path = self.analysis.run_stage3_heatmap(
                    final_k=current_k,
                    output_mode=params['output_mode'],
                    output_path=save_path,
                    heatmap_width=export_width,
                    heatmap_height=export_height,
                    color_scheme=params['color_scheme'],
                    title_font_size=params['title_font_size'],
                    legend_font_size=params['legend_font_size'],
                    clustering_method=params['clustering_method']
                )
            else:
                # 其他图：直接复制临时文件
                import shutil
                shutil.copy2(current_path, save_path)

            self.func.log(f"{format_type.upper()}导出成功: {save_path}")
            self.func.alert_success(f"{format_type.upper()}导出成功:\n{save_path}")
        except Exception as e:
            self.func.log(f"{format_type.upper()}导出失败: {str(e)}")
            self.func.alert_failure(f"{format_type.upper()}导出失败: {str(e)}")

    # ============ Debug ============

    def on_debug_clicked(self):
        """Debug按钮点击 - 检测环境对应关系"""
        self.func.log("========== 环境检测开始 ==========")

        # 1. UI控件检测
        self.func.log("\n【1. UI控件检测】")
        ui_controls = [
            'btn_back', 'bulk_cluster_btn_stage1', 'bulk_cluster_btn_stage2',
            'bulk_cluster_btn_stage3', 'bulk_cluster_btn_export_png',
            'bulk_cluster_btn_export_pdf', 'bulk_cluster_btn_export_svg',
            'bulk_cluster_btn_export_csv', 'bulk_cluster_debug_btn',
            'bulk_cluster_clinical_combo', 'bulk_cluster_mad_input',
            'bulk_cluster_reps_input', 'bulk_cluster_final_k_combo'
        ]
        for ctrl_name in ui_controls:
            exists = hasattr(self.bulk_cluster_ui, ctrl_name)
            self.func.log(f"  {ctrl_name}: {'✓' if exists else '✗'}")

        # 2. 数据状态检测
        self.func.log("\n【2. 数据状态检测】")
        self.func.log(f"  adata: {'已加载' if self.adata is not None else '未加载'}")
        self.func.log(f"  dataset_name: {self.dataset_name or '未设置'}")
        if self.adata is not None:
            n_samples, n_genes = self.analysis.get_adata_shape()
            self.func.log(f"  样本数: {n_samples}, 基因数: {n_genes}")

        # 3. R环境检测
        self.func.log("\n【3. R环境检测】")
        r_version = self.analysis.get_r_version()
        self.func.log(f"  R版本: {r_version}")
        self.func.log(f"  R可用: {'是' if self.analysis.is_available() else '否'}")
        self.func.log(f"  R脚本路径: {self.analysis.R_SCRIPT_PATH}")
        self.func.log(f"  R脚本存在: {'是' if os.path.exists(self.analysis.R_SCRIPT_PATH) else '否'}")

        # 4. 阶段状态检测
        self.func.log("\n【4. 阶段状态检测】")
        stage_status = self.analysis.get_stage_status()
        for stage, status in stage_status.items():
            self.func.log(f"  {stage}: {'已完成' if status else '未完成'}")

        # 5. R错误日志
        self.func.log("\n【5. R错误日志】")
        debug_log = self.analysis.get_r_debug_log()
        if debug_log:
            for i, entry in enumerate(debug_log[-5:]):  # 最近5条
                self.func.log(f"  [{i+1}] {entry['operation']}: {entry['error_type']}")
                self.func.log(f"      {entry['error_message'][:100]}")
        else:
            self.func.log("  无错误记录")

        self.func.log("\n========== 环境检测结束 ==========")
