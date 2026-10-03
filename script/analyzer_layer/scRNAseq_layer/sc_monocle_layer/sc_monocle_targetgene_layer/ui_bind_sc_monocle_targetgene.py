# -*- coding: utf-8 -*-
"""
scRNAseq Monocle目的基因分析子层功能绑定脚本
负责按钮点击、数据同步、R脚本调用等逻辑
"""

import os

from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_targetgene_layer.sc_monocle_targetgene_analysis import ScMonocleTargetgeneAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_targetgene_layer.ui_func_sc_monocle_targetgene import ScMonocleTargetgeneFunc


class ScMonocleTargetgeneBind:
    def __init__(self, main_window, targetgene_ui):
        self.parent = main_window
        self.sc_monocle_targetgene_ui = targetgene_ui
        
        self.analysis = ScMonocleTargetgeneAnalysis()
        self.func = ScMonocleTargetgeneFunc(targetgene_ui, main_window)
        
        self.bind_signals()

        if hasattr(self.sc_monocle_targetgene_ui, 'music_controller') and self.sc_monocle_targetgene_ui.music_controller:
            fix_music_controller_bindings(self, self.sc_monocle_targetgene_ui.music_controller)

    def bind_signals(self):
        """绑定控件信号"""
        ui = self.sc_monocle_targetgene_ui
        
        if hasattr(ui, 'btn_run_plot'):
            ui.btn_run_plot.clicked.connect(self.run_pseudotime_plot)

    def set_volume(self, value):
        """设置音量"""
        from script.mods_layer.mod_manager import global_mod_manager
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def _sync_shared_data_from_main_window(self):
        """从main_window读取共享的cds_rds_path和dataset_name"""
        try:
            shared_path = getattr(self.parent, 'shared_monocle_cds_rds_path', None)
            shared_dataset = getattr(self.parent, 'shared_monocle_dataset_name', None)

            if shared_path and shared_dataset:
                self.analysis.set_cds_rds_path(shared_path, shared_dataset)
                self.func.log(f"✓ 已同步CDS路径: {shared_dataset}")
                
                self._update_anno_columns()
                
                self.func.update_data_info({
                    'dataset': self.analysis.dataset_name,
                    'rds_path': self.analysis.cds_rds_path
                })
                
                self.func.set_run_button_enabled(True)
        except Exception as e:
            self.func.log(f"同步共享数据失败: {e}")

    def _update_anno_columns(self):
        """从CDS中获取注释列并更新下拉框"""
        try:
            import rpy2.robjects as robjects
            from rpy2.robjects import pandas2ri
            
            r_script = f"""
                library(monocle3)
                cds <- readRDS("{self.analysis.cds_rds_path}")
                colnames(colData(cds))
            """
            
            pandas2ri.activate()
            columns = robjects.r(r_script)
            pandas2ri.deactivate()
            
            column_list = [str(c) for c in columns]
            
            exclude_cols = ['orig.ident', 'Size_Factor']
            filtered_cols = [c for c in column_list if c not in exclude_cols]
            
            self.sc_monocle_targetgene_ui.update_anno_columns(filtered_cols)
            self.func.log(f"✓ 已加载 {len(filtered_cols)} 个注释列")
            
        except Exception as e:
            self.func.log(f"获取注释列失败: {e}")

    def run_pseudotime_plot(self):
        """运行伪时间趋势图绘制"""
        self._sync_shared_data_from_main_window()
        
        if not self.analysis.has_shared_data():
            self.func.alert_error("请先在数据加载类页面加载CDS RDS文件")
            return
        
        gene_list = self.func.get_gene_list_from_input()
        if not gene_list:
            self.func.alert_error("请输入至少一个基因名称")
            return
        
        anno_column = self.sc_monocle_targetgene_ui.anno_column_combo.currentData()
        if anno_column == "":
            anno_column = None
        
        yaxis_format = self.sc_monocle_targetgene_ui.yaxis_combo.currentData()
        
        self.func.log(f"开始绘制伪时间趋势图...")
        self.func.log(f"基因列表: {', '.join(gene_list)}")
        self.func.log(f"Y轴格式: {yaxis_format}")
        if anno_column:
            self.func.log(f"着色分组列: {anno_column}")
        
        self.func.set_run_button_enabled(False)
        
        try:
            success, result, is_error = self.analysis.run_pseudotime_plot(
                gene_list=gene_list,
                anno_column=anno_column,
                yaxis_format=yaxis_format,
                progress_callback=self.func.log
            )
            
            if success:
                self.func.show_plot_image(result)
                self.func.alert_success(f"伪时间趋势图绘制完成!\n\n图片路径: {result}")
                self.func.log(f"✓ 绘制完成: {result}")
            else:
                self.func.alert_failure(f"绘制失败: {result}")
                self.func.log(f"❌ 绘制失败: {result}")
        except Exception as e:
            self.func.alert_failure(f"绘制异常: {str(e)}")
            self.func.log(f"❌ 绘制异常: {e}")
        finally:
            self.func.set_run_button_enabled(True)

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从scRNAseq主页同步数据"""
        try:
            self._sync_shared_data_from_main_window()
        except Exception as e:
            self.func.log(f"同步数据时出错: {str(e)}")

    def on_page_activated(self):
        """页面激活时调用"""
        self._sync_shared_data_from_main_window()