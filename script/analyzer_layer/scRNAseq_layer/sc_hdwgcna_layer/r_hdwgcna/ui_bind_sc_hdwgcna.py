# -*- coding: utf-8 -*-
"""
scRNAseq hdWGCNA分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.scRNAseq_layer.sc_hdwgcna_layer.r_hdwgcna.sc_hdwgcna_analysis import get_sc_hdwgcna_analysis
from script.analyzer_layer.scRNAseq_layer.sc_hdwgcna_layer.r_hdwgcna.ui_func_sc_hdwgcna import ScHdWgcnaFunc
from script.analyzer_layer.scRNAseq_layer.sc_hdwgcna_layer.r_hdwgcna.sc_hdwgcna_worker import HdWgcnaWorker
from PyQt5.QtCore import QThread, QTimer


class ScHdWgcnaBind:
    def __init__(self, main_window, sc_hdwgcna_ui):
        self.main_window = main_window
        self.sc_hdwgcna_ui = sc_hdwgcna_ui
        self.analysis = get_sc_hdwgcna_analysis()
        self.func = ScHdWgcnaFunc(main_window, sc_hdwgcna_ui)
        self.bind_signals()
        self._update_r_version()
        self._worker_thread = None
        self._worker = None

    def bind_signals(self):
        self.bind_stage1()
        self.bind_stage2()
        self.bind_stage3()
        self.bind_stage4()
        self.bind_stage5()
        self.bind_stage6()
        self.bind_stage7()
        self.bind_stage8()
        self.bind_stage9()
        self.bind_stage10()
        self.bind_metadata_fetch()
        self.bind_analyze_group_change()
        self.bind_filter()
        self.bind_exports()
        self.bind_gene_select_mode()
        self._init_gene_select_mode()

    def bind_gene_select_mode(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_gene_select_mode_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_gene_select_mode_combo.currentIndexChanged.connect(self.on_gene_select_mode_changed)

    def _init_gene_select_mode(self):
        self.func.update_custom_gene_combo()
        self._update_gene_select_controls()

    def on_gene_select_mode_changed(self):
        self._update_gene_select_controls()

    def _update_gene_select_controls(self):
        mode = self.func.get_gene_select_mode()
        
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_fraction_input'):
            self.sc_hdwgcna_ui.sc_hdwgcna_fraction_input.setEnabled(mode == 'fraction')
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_custom_gene_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_custom_gene_combo.setEnabled(mode == 'custom')
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_variable_gene_input'):
            self.sc_hdwgcna_ui.sc_hdwgcna_variable_gene_input.setEnabled(mode == 'variable')

    def bind_stage1(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage1'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage1.clicked.connect(self.run_stage1)

    def bind_stage2(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage2'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage2.clicked.connect(self.run_stage2)

    def bind_stage3(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage3'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage3.clicked.connect(self.run_stage3)

    def bind_stage4(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage4'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage4.clicked.connect(self.run_stage4)

    def bind_stage5(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage5'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage5.clicked.connect(self.run_stage5)

    def bind_stage6(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage6'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage6.clicked.connect(self.run_stage6)

    def bind_stage7(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage7'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage7.clicked.connect(self.run_stage7)

    def bind_stage8(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage8'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage8.clicked.connect(self.run_stage8)

    def bind_stage9(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage9'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage9.clicked.connect(self.run_stage9)

    def bind_stage10(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_stage10'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_stage10.clicked.connect(self.run_stage10)

    def bind_metadata_fetch(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_fetch_metadata'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_fetch_metadata.clicked.connect(self.fetch_metadata)

    def bind_analyze_group_change(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_analyze_group_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_analyze_group_combo.currentIndexChanged.connect(self.on_analyze_group_changed)

    def bind_filter(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_enable'):
            self.sc_hdwgcna_ui.sc_hdwgcna_filter_enable.stateChanged.connect(self.on_filter_enable_changed)
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_filter_combo.currentIndexChanged.connect(self.on_filter_col_changed)

    def on_filter_enable_changed(self, state):
        enabled = state == 2
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_combo'):
            self.sc_hdwgcna_ui.sc_hdwgcna_filter_combo.setEnabled(enabled)
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_filter_list'):
            self.sc_hdwgcna_ui.sc_hdwgcna_filter_list.setEnabled(enabled)

    def on_filter_col_changed(self, index):
        filter_col = self.func.get_selected_filter_col()
        if filter_col:
            try:
                values = self.analysis.get_seurat_column_values(filter_col)
                self.func.update_filter_list(values)
            except Exception as e:
                self.func.log(f"更新筛选组别失败: {str(e)}")

    def bind_exports(self):
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_export_png'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_export_png.clicked.connect(lambda: self.func.export_current_plot('png'))
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_export_pdf'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_export_pdf.clicked.connect(lambda: self.func.export_current_plot('pdf'))
        if hasattr(self.sc_hdwgcna_ui, 'sc_hdwgcna_btn_export_svg'):
            self.sc_hdwgcna_ui.sc_hdwgcna_btn_export_svg.clicked.connect(lambda: self.func.export_current_plot('svg'))

    def _update_r_version(self):
        r_version = self.analysis.get_r_version()
        self.func.update_r_version(r_version)

    def sync_data_from_scrna_main(self, scrna_top_bind):
        if not scrna_top_bind or not scrna_top_bind.analysis:
            return

        self.seurat_path = scrna_top_bind.analysis.seurat_path
        self.dataset_name = scrna_top_bind.analysis.dataset_name
        self.dataset_output_dir = scrna_top_bind.analysis.dataset_output_dir

        if self.seurat_path is not None:
            self.func.log(f"已从scRNAseq主页同步数据: {self.dataset_name}")
            self.func.update_seurat_status(f"Seurat对象: {self.dataset_name}")

            self.analysis.set_seurat_path(self.seurat_path)
            self.analysis.set_dataset_name(self.dataset_name)
            self.analysis.set_dataset_output_dir(self.dataset_output_dir)
            
            self._preload_metadata()

    def sync_data_from_single_cell_main(self, scrna_top_bind):
        self.sync_data_from_scrna_main(scrna_top_bind)

    def _preload_metadata(self):
        try:
            colnames = self.analysis.get_seurat_metadata_columns()
            if colnames:
                self.func.log("正在预加载元数据列...")
                self.func.update_analyze_group_combo(colnames)
                self.func.update_sample_group_combo(colnames)
                self.func.update_filter_combo(colnames)
                self.func.update_trait_list(colnames)
                if 'Sample' in colnames:
                    idx = self.sc_hdwgcna_ui.sc_hdwgcna_sample_group_combo.findText('Sample')
                    self.sc_hdwgcna_ui.sc_hdwgcna_sample_group_combo.setCurrentIndex(idx)
                
                for col in colnames:
                    try:
                        self.analysis.get_seurat_column_values(col)
                    except Exception:
                        pass
                self.func.log(f"预加载完成，共 {len(colnames)} 个元数据列")
                
                analyze_group = self.func.get_selected_analyze_group()
                if analyze_group:
                    self.update_cell_types(analyze_group)
        except Exception as e:
            self.func.log(f"预加载元数据失败: {str(e)}")

    def fetch_metadata(self):
        self.func.log("正在获取Seurat元数据...")
        try:
            colnames = self.analysis.get_seurat_metadata_columns()
            if colnames:
                self.func.update_analyze_group_combo(colnames)
                self.func.update_sample_group_combo(colnames)
                self.func.update_filter_combo(colnames)
                if 'Sample' in colnames:
                    idx = self.sc_hdwgcna_ui.sc_hdwgcna_sample_group_combo.findText('Sample')
                    self.sc_hdwgcna_ui.sc_hdwgcna_sample_group_combo.setCurrentIndex(idx)
                self.func.log(f"成功获取 {len(colnames)} 个元数据列")

                analyze_group = self.func.get_selected_analyze_group()
                self.update_cell_types(analyze_group)
            else:
                self.func.log("未获取到元数据列")
        except Exception as e:
            self.func.log(f"获取元数据失败: {str(e)}")

    def on_analyze_group_changed(self):
        analyze_group = self.func.get_selected_analyze_group()
        self.update_cell_types(analyze_group)

    def update_cell_types(self, analyze_group):
        try:
            cell_types = self.analysis.get_seurat_column_values(analyze_group)
            self.func.update_target_cell_combo(cell_types)
            self.func.log(f"已更新 {analyze_group} 的细胞类型")
        except Exception as e:
            self.func.log(f"更新细胞类型失败: {str(e)}")

    def run_stage1(self):
        analyze_group = self.func.get_selected_analyze_group()
        sample_group = self.func.get_selected_sample_group()
        target_cell = self.func.get_selected_target_cell()
        gene_select_mode = self.func.get_gene_select_mode()
        fraction_value = self.func.get_fraction_value()
        variable_gene_count = self.func.get_variable_gene_count()
        custom_gene_list_path = self.func.get_custom_gene_list_path()
        recluster = self.func.get_recluster()
        dims = self.func.get_dims()
        filter_enabled = self.func.is_filter_enabled()
        filter_col = self.func.get_selected_filter_col()
        filter_groups = self.func.get_selected_filter_groups()

        self.func.log(f"开始运行阶段一: 分析分组={analyze_group}, 样本列={sample_group}, 目标细胞={target_cell}, 基因选择模式={gene_select_mode}, 重新降维={recluster}, 维度数={dims}, 筛选={filter_enabled}")

        try:
            if target_cell == "全部":
                target_cell = None

            success = self.analysis.run_stage1_load_seurat(
                seurat_path=self.seurat_path,
                analyze_group=analyze_group,
                sample_group=sample_group,
                target_cell_type=target_cell,
                gene_select_mode=gene_select_mode,
                fraction_value=fraction_value,
                variable_gene_count=variable_gene_count,
                custom_gene_list_path=custom_gene_list_path,
                recluster=recluster,
                dims=dims,
                filter_enabled=filter_enabled,
                filter_col=filter_col,
                filter_groups=filter_groups
            )

            if success:
                self.func.log("阶段一运行成功")
                result = self.analysis.get_stage1_result()
                if result:
                    self.func.log(result)
                umap_path = self.analysis.get_stage1_umap_path()
                if umap_path:
                    self.func.update_umap_plot(umap_path)
                    self.func.switch_to_tab("UMAP图")
        except Exception as e:
            self.func.log(f"阶段一运行失败: {str(e)}")

    def run_stage2(self):
        k = self.func.get_k_value()
        max_shared = self.func.get_max_shared_value()
        min_cells = self.func.get_min_cells_value()

        self.func.log(f"开始运行阶段二: k={k}, max_shared={max_shared}, min_cells={min_cells}")

        try:
            success = self.analysis.run_stage2_metacell(
                k=k,
                max_shared=max_shared,
                min_cells=min_cells
            )

            if success:
                self.func.log("阶段二运行成功")
                result = self.analysis.get_stage2_result()
                if result:
                    self.func.log(result)
        except Exception as e:
            self.func.log(f"阶段二运行失败: {str(e)}")

    def run_stage3(self):
        if self._worker is not None and self._worker._running:
            self.func.log("正在运行中，请等待完成")
            return
        
        network_type = self.func.get_network_type()
        manual_power = self.func.get_manual_power()

        self.func.log(f"开始运行阶段三: 网络类型={network_type}, 手动软阈值={manual_power}")

        self._disable_stage_buttons([3, 4])

        self._worker = HdWgcnaWorker()
        self._worker.finished.connect(self._on_stage3_finished)
        self._worker.progress.connect(self._on_worker_progress)
        
        QTimer.singleShot(100, lambda: self._worker.run_stage3(
            analysis=self.analysis,
            network_type=network_type,
            manual_power=manual_power
        ))

    def _on_stage3_finished(self, success, result):
        self._enable_stage_buttons([3, 4])
        self._worker = None
        
        if success:
            self.func.log("阶段三运行成功")
            power_estimate = self.analysis.get_power_estimate()
            if power_estimate:
                self.func.update_power_estimate(power_estimate)
                self.func.log(f"推荐软阈值: {power_estimate}")
            soft_threshold_plot_path = self.analysis.get_stage3_soft_threshold_plot_path()
            if soft_threshold_plot_path:
                self.func.update_soft_threshold_plot(soft_threshold_plot_path)
                self.func.switch_to_tab("软阈值选择图")
        else:
            self.func.log(f"阶段三运行失败: {result}")

    def _on_worker_progress(self, message):
        self.func.log(message)

    def run_stage4(self):
        if self._worker is not None and self._worker._running:
            self.func.log("正在运行中，请等待完成")
            return
        
        power = self.func.get_power()
        min_module_size = self.func.get_min_module_size()
        merge_threshold = self.func.get_merge_threshold()

        self.func.log(f"开始运行阶段四: 网络构建, power={power}, min_module_size={min_module_size}, merge_threshold={merge_threshold}")

        self._disable_stage_buttons([3, 4])

        self._worker = HdWgcnaWorker()
        self._worker.finished.connect(self._on_stage4_finished)
        self._worker.progress.connect(self._on_worker_progress)
        
        QTimer.singleShot(100, lambda: self._worker.run_stage4(
            analysis=self.analysis,
            power=power,
            min_module_size=min_module_size,
            merge_threshold=merge_threshold
        ))

    def _on_stage4_finished(self, success, result):
        self._enable_stage_buttons([3, 4])
        self._worker = None
        
        if success:
            self.func.log("阶段四运行成功")
            gene_dendro_path = self.analysis.get_stage4_gene_dendro_path()
            if gene_dendro_path:
                self.func.update_gene_dendro_plot(gene_dendro_path)
                self.func.switch_to_tab("基因聚类树+模块色条")
            
            modules = self.analysis.get_modules()
            print(f"[阶段四完成] 获取到模块列表: {modules}")
            if modules:
                print(f"[阶段四完成] 更新模块列表到UI")
                self.func.update_module_list(modules)
            else:
                print(f"[阶段四完成] 模块列表为空，尝试重新获取...")
                modules = self.analysis.get_modules()
                print(f"[阶段四完成] 重新获取模块列表: {modules}")
                if modules:
                    self.func.update_module_list(modules)
        else:
            self.func.log(f"阶段四运行失败: {result}")

    def _disable_stage_buttons(self, stages):
        for stage in stages:
            btn_name = f'sc_hdwgcna_btn_stage{stage}'
            if hasattr(self.sc_hdwgcna_ui, btn_name):
                getattr(self.sc_hdwgcna_ui, btn_name).setEnabled(False)

    def _enable_stage_buttons(self, stages):
        for stage in stages:
            btn_name = f'sc_hdwgcna_btn_stage{stage}'
            if hasattr(self.sc_hdwgcna_ui, btn_name):
                getattr(self.sc_hdwgcna_ui, btn_name).setEnabled(True)

    def run_stage5(self):
        self.func.log("开始运行阶段五: 模块可视化(Dendrogram+KMEs)")

        try:
            success = self.analysis.run_stage5_module_visualization()

            if success:
                self.func.log("阶段五运行成功")
                kme_plot_path = self.analysis.get_stage5_kme_plot_path()
                if kme_plot_path:
                    self.func.update_kme_plot(kme_plot_path)
                    self.func.switch_to_tab("kME得分图")
        except Exception as e:
            self.func.log(f"阶段五运行失败: {str(e)}")

    def run_stage6(self):
        self.func.log("开始运行阶段六: 模块特征图(hMEs)")

        try:
            success = self.analysis.run_stage6_hme_plots()

            if success:
                self.func.log("阶段六运行成功")
                hme_plot_path = self.analysis.get_stage6_hme_plot_path()
                if hme_plot_path:
                    self.func.update_hme_plot(hme_plot_path)
                    self.func.switch_to_tab("模块特征图(hMEs)")
        except Exception as e:
            self.func.log(f"阶段六运行失败: {str(e)}")

    def run_stage7(self):
        self.func.log("开始运行阶段七: 相关图(Correlogram+DotPlot)")

        try:
            success = self.analysis.run_stage7_correlogram_and_dotplot()

            if success:
                self.func.log("阶段七运行成功")
                correlogram_path = self.analysis.get_stage7_correlogram_path()
                if correlogram_path:
                    self.func.update_correlogram_plot(correlogram_path)
                    self.func.switch_to_tab("模块相关图")
                dotplot_path = self.analysis.get_stage7_dotplot_path()
                if dotplot_path:
                    self.func.update_dotplot_plot(dotplot_path)
        except Exception as e:
            self.func.log(f"阶段七运行失败: {str(e)}")

    def run_stage8(self):
        self.func.log("开始运行阶段八: ModuleUMAP")

        try:
            success = self.analysis.run_stage8_module_umap()

            if success:
                self.func.log("阶段八运行成功")
                module_umap_path = self.analysis.get_stage8_module_umap_path()
                if module_umap_path:
                    self.func.update_module_umap_plot(module_umap_path)
                    self.func.switch_to_tab("模块UMAP图")
        except Exception as e:
            self.func.log(f"阶段八运行失败: {str(e)}")

    def run_stage9(self):
        organism = self.func.get_organism()
        selected_modules = self.func.get_selected_modules()
        go_padj_cutoff = self.func.get_go_padj_cutoff()
        kegg_padj_cutoff = self.func.get_kegg_padj_cutoff()
        go_top_n = self.func.get_go_top_n()
        kegg_top_n = self.func.get_kegg_top_n()

        self.func.log(f"开始运行阶段九: GO和KEGG富集分析, 物种={organism}, 模块={selected_modules}, GO校正p值={go_padj_cutoff}, KEGG校正p值={kegg_padj_cutoff}, GO展示数={go_top_n}, KEGG展示数={kegg_top_n}")

        try:
            success = self.analysis.run_stage9_go_kegg_enrichment(
                organism=organism,
                selected_modules=selected_modules,
                go_padj_cutoff=go_padj_cutoff,
                kegg_padj_cutoff=kegg_padj_cutoff,
                go_top_n=go_top_n,
                kegg_top_n=kegg_top_n
            )

            if success:
                self.func.log("阶段九运行成功")
                
                target_modules = selected_modules if selected_modules and len(selected_modules) > 0 else self.analysis.get_modules()
                
                if target_modules and len(target_modules) > 0:
                    self.func.log(f"正在处理 {len(target_modules)} 个模块的图片...")
                    
                    go_bubble_path = self.analysis.get_stage9_combined_image(target_modules, 'go_bubble')
                    if go_bubble_path:
                        self.func.update_go_bubble_plot(go_bubble_path)
                        self.func.log(f"GO气泡图已更新: {go_bubble_path}")
                    else:
                        self.func.log("未找到GO气泡图")
                    
                    go_bar_path = self.analysis.get_stage9_combined_image(target_modules, 'go_bar')
                    if go_bar_path:
                        self.func.update_go_bar_plot(go_bar_path)
                        self.func.log(f"GO条形图已更新: {go_bar_path}")
                    else:
                        self.func.log("未找到GO条形图")
                    
                    kegg_bar_path = self.analysis.get_stage9_combined_image(target_modules, 'kegg_bar')
                    if kegg_bar_path:
                        self.func.update_kegg_bar_plot(kegg_bar_path)
                        self.func.log(f"KEGG条形图已更新: {kegg_bar_path}")
                    else:
                        self.func.log("未找到KEGG条形图")
                    
                    kegg_bubble_path = self.analysis.get_stage9_combined_image(target_modules, 'kegg_bubble')
                    if kegg_bubble_path:
                        self.func.update_kegg_bubble_plot(kegg_bubble_path)
                        self.func.log(f"KEGG气泡图已更新: {kegg_bubble_path}")
                    else:
                        self.func.log("未找到KEGG气泡图")
                    
                    self.func.switch_to_tab("GO气泡图")
                else:
                    self.func.log("未找到有效模块")
        except Exception as e:
            self.func.log(f"阶段九运行失败: {str(e)}")

    def run_stage10(self):
        self.func.log("开始运行阶段十: 导出基因集合")

        try:
            success = self.analysis.run_stage10_export_modules()

            if success:
                self.func.log("阶段十运行成功")
                export_path = self.analysis.get_stage10_export_path()
                if export_path:
                    self.func.log(f"基因集合已导出到: {export_path}")
        except Exception as e:
            self.func.log(f"阶段十运行失败: {str(e)}")
