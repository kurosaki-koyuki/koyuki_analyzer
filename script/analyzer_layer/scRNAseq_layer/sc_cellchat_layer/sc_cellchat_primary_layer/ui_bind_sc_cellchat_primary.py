# -*- coding: utf-8 -*-
"""
CellChat初步分析类界面功能绑定脚本
负责粘合内外，绑定信号，编排analysis与func的协作
包含数据同步、阶段一和阶段二按钮绑定
"""

import os
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_primary_layer.sc_cellchat_analysis import ScCellChatAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_primary_layer.ui_func_sc_cellchat_primary import ScCellChatPrimaryFunc


class ScCellChatPrimaryBind:
    def __init__(self, main_window, sc_cellchat_primary_ui):
        self.parent = main_window
        self.ui = sc_cellchat_primary_ui
        self.analysis = ScCellChatAnalysis()
        self.func = ScCellChatPrimaryFunc(sc_cellchat_primary_ui, main_window)
        self.func._analysis = self.analysis
        self._metadata_values = {}
        self.bind_signals()
        # 绑定音乐控制器
        if hasattr(self.ui, 'music_controller') and self.ui.music_controller:
            fix_music_controller_bindings(self, self.ui.music_controller)

    def bind_signals(self):
        self.bind_analysis_functions()

    def bind_analysis_functions(self):
        # 阶段一：按注释出图
        if hasattr(self.ui, 'btn_run_stage1'):
            self.ui.btn_run_stage1.clicked.connect(self.run_stage1)

        # 阶段二：执行筛选
        if hasattr(self.ui, 'btn_run_stage2'):
            self.ui.btn_run_stage2.clicked.connect(self.run_stage2)

        # 阶段一：注释列变化事件
        if hasattr(self.ui, 'combo_annotation'):
            self.ui.combo_annotation.currentIndexChanged.connect(self.on_annotation_changed)

        # 阶段二：主注释列变化事件
        if hasattr(self.ui, 'combo_main_annot'):
            self.ui.combo_main_annot.currentIndexChanged.connect(self.on_main_annot_changed)

        # 筛选条件1变化事件
        if hasattr(self.ui, 'combo_filter1'):
            self.ui.combo_filter1.currentIndexChanged.connect(self.on_filter1_changed)

        # 筛选条件2变化事件
        if hasattr(self.ui, 'combo_filter2'):
            self.ui.combo_filter2.currentIndexChanged.connect(self.on_filter2_changed)

        # 筛选后出图注释变化事件
        if hasattr(self.ui, 'combo_plot_annot'):
            self.ui.combo_plot_annot.currentIndexChanged.connect(self.on_plot_annot_changed)

        # 主注释分组选择变化时，自动勾选重新降维
        if hasattr(self.ui, 'list_main_groups'):
            self.ui.list_main_groups.itemSelectionChanged.connect(self.on_main_groups_selection_changed)

        # 筛选条件1列表选择变化
        if hasattr(self.ui, 'list_filter1'):
            self.ui.list_filter1.itemSelectionChanged.connect(self.on_filter1_selection_changed)

        # 筛选条件2列表选择变化
        if hasattr(self.ui, 'list_filter2'):
            self.ui.list_filter2.itemSelectionChanged.connect(self.on_filter2_selection_changed)

        # 阶段三：执行CellChat分析
        if hasattr(self.ui, 'btn_run_stage3'):
            self.ui.btn_run_stage3.clicked.connect(self.run_stage3)

        # 阶段四：生成亚组circle图
        if hasattr(self.ui, 'btn_run_stage4'):
            self.ui.btn_run_stage4.clicked.connect(self.run_stage4)

        # 阶段四：全选/取消全选
        if hasattr(self.ui, 'btn_select_all_subgroups'):
            self.ui.btn_select_all_subgroups.clicked.connect(self.select_all_subgroups)
        if hasattr(self.ui, 'btn_deselect_all_subgroups'):
            self.ui.btn_deselect_all_subgroups.clicked.connect(self.deselect_all_subgroups)

        # 阶段五：生成通路可视化图
        if hasattr(self.ui, 'btn_run_stage5'):
            self.ui.btn_run_stage5.clicked.connect(self.run_stage5)

        # 阶段五：配置分组
        if hasattr(self.ui, 'btn_config_groups'):
            self.ui.btn_config_groups.clicked.connect(self.config_celltype_groups)
        
        # 导出按钮
        if hasattr(self.ui, 'btn_export_rds'):
            self.ui.btn_export_rds.clicked.connect(self.export_cellchat_rds)
        if hasattr(self.ui, 'btn_export_pathway_info'):
            self.ui.btn_export_pathway_info.clicked.connect(self.export_pathway_info)

    def set_volume(self, value):
        """设置音量"""
        from script.mods_layer.mod_manager import global_mod_manager
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)
        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从scRNAseq主页同步数据"""
        try:
            if single_cell_bind is None:
                single_cell_bind = getattr(self.parent, 'scRNAseq_top_bind', None)

            if single_cell_bind is None:
                return

            if hasattr(single_cell_bind, 'analysis'):
                self.analysis.set_seurat_path(single_cell_bind.analysis.seurat_path)
                self.analysis.set_dataset_name(single_cell_bind.analysis.dataset_name)
                # 不使用主页的output_dir，CellChat使用自己的OUTPUT/cellchat/结构
                # self.analysis.set_dataset_output_dir(single_cell_bind.analysis.dataset_output_dir)

                if single_cell_bind.analysis.seurat_path is not None:
                    self.func.log(f"已从scRNAseq主页同步Seurat对象: {single_cell_bind.analysis.dataset_name}")
                    self.load_metadata_columns_from_main(single_cell_bind.analysis)
                    self.enable_stage1_button()

        except Exception as e:
            print(f"CellChat同步数据时出错: {str(e)}")

    def load_metadata_columns_from_main(self, main_analysis):
        """从主页加载元数据列"""
        try:
            metadata_cols = []
            if hasattr(main_analysis, 'seurat_metadata_columns') and main_analysis.seurat_metadata_columns:
                metadata_cols = main_analysis.seurat_metadata_columns

            # 阶段一：注释列选择
            if hasattr(self.ui, 'combo_annotation'):
                self.ui.combo_annotation.clear()
                self.ui.combo_annotation.addItem("选择注释列")
                for col in metadata_cols:
                    self.ui.combo_annotation.addItem(col)

            # 阶段二：主注释列
            if hasattr(self.ui, 'combo_main_annot'):
                self.ui.combo_main_annot.clear()
                self.ui.combo_main_annot.addItem("选择注释列")
                for col in metadata_cols:
                    self.ui.combo_main_annot.addItem(col)

            # 筛选条件1
            if hasattr(self.ui, 'combo_filter1'):
                self.ui.combo_filter1.clear()
                self.ui.combo_filter1.addItem("不筛选")
                for col in metadata_cols:
                    self.ui.combo_filter1.addItem(col)

            # 筛选条件2
            if hasattr(self.ui, 'combo_filter2'):
                self.ui.combo_filter2.clear()
                self.ui.combo_filter2.addItem("不筛选")
                for col in metadata_cols:
                    self.ui.combo_filter2.addItem(col)

            # 筛选后出图注释
            if hasattr(self.ui, 'combo_plot_annot'):
                self.ui.combo_plot_annot.clear()
                self.ui.combo_plot_annot.addItem("选择注释列")
                for col in metadata_cols:
                    self.ui.combo_plot_annot.addItem(col)

            # 阶段三：注释列选择
            if hasattr(self.ui, 'combo_stage3_annot'):
                self.ui.combo_stage3_annot.clear()
                self.ui.combo_stage3_annot.addItem("默认（使用阶段一）")
                for col in metadata_cols:
                    self.ui.combo_stage3_annot.addItem(col)

            # 元数据值
            self._metadata_values = {}
            if hasattr(main_analysis, 'seurat_metadata_values') and main_analysis.seurat_metadata_values:
                self._metadata_values = main_analysis.seurat_metadata_values

            self.func.log(f"已加载 {len(metadata_cols)} 个注释列")

        except Exception as e:
            print(f"加载注释列失败: {str(e)}")

    def enable_stage1_button(self):
        """启用阶段一按钮"""
        if hasattr(self.ui, 'btn_run_stage1'):
            self.ui.btn_run_stage1.setEnabled(True)

    def enable_stage2_button(self):
        """启用阶段二按钮"""
        if hasattr(self.ui, 'btn_run_stage2'):
            self.ui.btn_run_stage2.setEnabled(True)

    def enable_stage3_button(self):
        """启用阶段三按钮"""
        if hasattr(self.ui, 'btn_run_stage3'):
            self.ui.btn_run_stage3.setEnabled(True)

    def enable_stage4_button(self):
        """启用阶段四按钮"""
        if hasattr(self.ui, 'btn_run_stage4'):
            self.ui.btn_run_stage4.setEnabled(True)
        # 同时启用阶段五按钮
        self.enable_stage5_button()

    def enable_stage5_button(self):
        """启用阶段五按钮"""
        if hasattr(self.ui, 'btn_run_stage5'):
            self.ui.btn_run_stage5.setEnabled(True)
        # 同时启用导出按钮
        if hasattr(self.ui, 'btn_export_rds'):
            self.ui.btn_export_rds.setEnabled(True)
        if hasattr(self.ui, 'btn_export_pathway_info'):
            self.ui.btn_export_pathway_info.setEnabled(True)
    
    def export_cellchat_rds(self):
        """导出CellChat RDS文件"""
        if not self.analysis.dataset_name:
            self.func.alert_error("请先运行阶段三")
            return
        
        output_dir = self.analysis._get_output_dir()
        rds_file = os.path.join(output_dir, f"{self.analysis.dataset_name}_cellchat.rds")
        
        if not os.path.exists(rds_file):
            self.func.alert_error("CellChat RDS文件不存在，请先运行阶段三")
            return
        
        # 弹出文件保存对话框
        save_path = self.func.get_save_file_path(
            "导出CellChat RDS文件",
            f"{self.analysis.dataset_name}_cellchat.rds",
            "RDS文件 (*.rds)"
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(rds_file, save_path)
                self.func.log(f"CellChat RDS已导出: {save_path}")
                self.func.alert_success("CellChat RDS导出成功")
            except Exception as e:
                self.func.log(f"导出失败: {e}")
                self.func.alert_failure(f"导出失败: {e}")
    
    def export_pathway_info(self):
        """导出通路信息表"""
        output_dir = self.analysis._get_output_dir()
        info_file = os.path.join(output_dir, "pathway_info.csv")
        
        if not os.path.exists(info_file):
            self.func.alert_error("通路信息表不存在，请先运行阶段三")
            return
        
        # 弹出文件保存对话框
        save_path = self.func.get_save_file_path(
            "导出通路信息表",
            "pathway_info.csv",
            "CSV文件 (*.csv)"
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(info_file, save_path)
                self.func.log(f"通路信息表已导出: {save_path}")
                self.func.alert_success("通路信息表导出成功")
            except Exception as e:
                self.func.log(f"导出失败: {e}")
                self.func.alert_failure(f"导出失败: {e}")

    def select_all_subgroups(self):
        """全选所有亚组"""
        if hasattr(self.ui, 'list_subgroups'):
            self.ui.list_subgroups.selectAll()

    def deselect_all_subgroups(self):
        """取消全选"""
        if hasattr(self.ui, 'list_subgroups'):
            self.ui.list_subgroups.clearSelection()

    def on_annotation_changed(self):
        """阶段一：注释列变化时更新"""
        pass

    def on_main_annot_changed(self):
        """阶段二：主注释列变化时更新主注释分组列表"""
        if not hasattr(self.ui, 'list_main_groups'):
            return

        annot_col = self.ui.combo_main_annot.currentText()
        self.ui.list_main_groups.clear()

        if annot_col != "选择注释列" and annot_col in self._metadata_values:
            for value in self._metadata_values[annot_col]:
                from PyQt5.QtWidgets import QListWidgetItem
                item = QListWidgetItem(value)
                self.ui.list_main_groups.addItem(item)

            # 启用阶段二按钮
            self.enable_stage2_button()

    def on_filter1_changed(self):
        """筛选条件1变化时更新列表"""
        if not hasattr(self.ui, 'list_filter1'):
            return

        filter_col = self.ui.combo_filter1.currentText()
        self.ui.list_filter1.clear()

        if filter_col != "不筛选" and filter_col in self._metadata_values:
            for value in self._metadata_values[filter_col]:
                from PyQt5.QtWidgets import QListWidgetItem
                item = QListWidgetItem(value)
                self.ui.list_filter1.addItem(item)

    def on_filter2_changed(self):
        """筛选条件2变化时更新列表"""
        if not hasattr(self.ui, 'list_filter2'):
            return

        filter_col = self.ui.combo_filter2.currentText()
        self.ui.list_filter2.clear()

        if filter_col != "不筛选" and filter_col in self._metadata_values:
            for value in self._metadata_values[filter_col]:
                from PyQt5.QtWidgets import QListWidgetItem
                item = QListWidgetItem(value)
                self.ui.list_filter2.addItem(item)

    def on_plot_annot_changed(self):
        """筛选后出图注释变化时的处理"""
        pass

    def on_main_groups_selection_changed(self):
        """主注释分组选择变化时，自动勾选重新降维"""
        if not hasattr(self.ui, 'list_main_groups'):
            return

        selected_items = self.ui.list_main_groups.selectedItems()
        if selected_items:
            # 有选择时自动勾选重新降维
            if hasattr(self.ui, 'check_re_reduce'):
                self.ui.check_re_reduce.setChecked(True)

    def on_filter1_selection_changed(self):
        """筛选条件1列表选择变化"""
        pass

    def on_filter2_selection_changed(self):
        """筛选条件2列表选择变化"""
        pass

    def run_stage1(self):
        """运行阶段一：按注释出图"""
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return

        annotation_col = ""
        if hasattr(self.ui, 'combo_annotation'):
            annotation_col = self.ui.combo_annotation.currentText()

        if annotation_col == "选择注释列" or not annotation_col:
            self.func.alert_error("请先选择一个注释列")
            return

        self.func.log(f"正在按注释出图: {annotation_col}...")

        success, result = self.analysis.generate_umap_plot(annotation_col)

        if not success:
            self.func.alert_failure(f"出图失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"出图完成: {result}")
        self.func.display_stage1_image(result)
        self._stage1_image_path = result  # 保存阶段一图片路径
        self.func.alert_success(f"注释图 {annotation_col} 绘制完成")

        # 切换到数据集原始UMAP标签页
        if hasattr(self.ui, 'primary_tabs'):
            self.ui.primary_tabs.setCurrentIndex(0)

        # 启用阶段二按钮
        self.enable_stage2_button()

    def run_stage2(self):
        """运行阶段二：细胞筛选与重新降维"""
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return

        # 获取主注释列
        main_annot = ""
        if hasattr(self.ui, 'combo_main_annot'):
            main_annot = self.ui.combo_main_annot.currentText()

        # 获取主注释分组选择
        celltypes = []
        if hasattr(self.ui, 'list_main_groups'):
            for item in self.ui.list_main_groups.selectedItems():
                celltypes.append(item.text())

        # 如果没有选择主注释列或主注释分组，直接显示阶段一的图
        if main_annot == "选择注释列" or not main_annot or not celltypes:
            self.func.log("未选择筛选参数，直接显示原始UMAP图...")
            self.func.display_stage2_image(self._stage1_image_path if hasattr(self, '_stage1_image_path') else "")
            # 切换到筛选UMAP图标签页
            if hasattr(self.ui, 'primary_tabs'):
                self.ui.primary_tabs.setCurrentIndex(1)
            self.func.alert_success("已显示原始UMAP图（未筛选）")
            # 启用阶段三按钮
            self.enable_stage3_button()
            return

        # 获取筛选条件1
        filter1_col = ""
        filter1_values = []
        if hasattr(self.ui, 'combo_filter1'):
            filter1_col = self.ui.combo_filter1.currentText()
        if hasattr(self.ui, 'list_filter1') and filter1_col != "不筛选":
            for item in self.ui.list_filter1.selectedItems():
                filter1_values.append(item.text())

        # 获取筛选条件2
        filter2_col = ""
        filter2_values = []
        if hasattr(self.ui, 'combo_filter2'):
            filter2_col = self.ui.combo_filter2.currentText()
        if hasattr(self.ui, 'list_filter2') and filter2_col != "不筛选":
            for item in self.ui.list_filter2.selectedItems():
                filter2_values.append(item.text())

        # 获取重新降维选项
        re_reduce = False
        if hasattr(self.ui, 'check_re_reduce'):
            re_reduce = self.ui.check_re_reduce.isChecked()

        # 获取dim值
        dim_val = 30
        if hasattr(self.ui, 'input_dim_val'):
            try:
                dim_val = int(self.ui.input_dim_val.text())
            except:
                dim_val = 30

        # 获取筛选后出图注释
        plot_annot = ""
        if hasattr(self.ui, 'combo_plot_annot'):
            plot_annot = self.ui.combo_plot_annot.currentText()
            if plot_annot == "选择注释列":
                plot_annot = main_annot

        self.func.log(f"正在执行细胞筛选...")
        self.func.log(f"主注释列: {main_annot}")
        self.func.log(f"选择分组: {', '.join(celltypes)}")
        if filter1_col and filter1_values:
            self.func.log(f"筛选条件1: {filter1_col} = {', '.join(filter1_values)}")
        if filter2_col and filter2_values:
            self.func.log(f"筛选条件2: {filter2_col} = {', '.join(filter2_values)}")
        self.func.log(f"重新降维: {re_reduce}, dim: {dim_val}")

        # 构建筛选参数
        filter_params = {
            'main_annot': main_annot,
            'main_groups': celltypes,
            'filter1_col': filter1_col if filter1_col != "不筛选" else None,
            'filter1_values': filter1_values if filter1_col != "不筛选" else [],
            'filter2_col': filter2_col if filter2_col != "不筛选" else None,
            'filter2_values': filter2_values if filter2_col != "不筛选" else [],
        }

        success, result = self.analysis.filter_cells_and_reduce(
            celltypes, re_reduce, dim_val, plot_annot, filter_params
        )

        if not success:
            self.func.alert_failure(f"筛选失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"筛选完成")
        self.func.display_stage2_image(result)
        self.func.alert_success("阶段二分析完成")

        # 切换到筛选UMAP图标签页
        if hasattr(self.ui, 'primary_tabs'):
            self.ui.primary_tabs.setCurrentIndex(1)

        # 启用阶段三按钮
        self.enable_stage3_button()

    def run_stage3(self):
        """运行阶段三：CellChat通讯分析"""
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return

        # 获取阶段三的注释列
        stage3_annot = ""
        if hasattr(self.ui, 'combo_stage3_annot'):
            stage3_annot = self.ui.combo_stage3_annot.currentText()
        
        # 如果选的是"默认"，使用阶段一的注释列
        if stage3_annot == "默认（使用阶段一）" or not stage3_annot:
            if hasattr(self.ui, 'combo_annotation'):
                main_annot = self.ui.combo_annotation.currentText()
            else:
                main_annot = ""
        else:
            main_annot = stage3_annot
        
        if main_annot == "选择注释列" or not main_annot:
            self.func.alert_error("请先选择注释列（阶段一或阶段三）")
            return

        # 获取主注释分组选择（作为细胞类型筛选）
        celltypes = []
        if hasattr(self.ui, 'list_main_groups'):
            for item in self.ui.list_main_groups.selectedItems():
                celltypes.append(item.text())

        # 获取数据库类型
        db_type = "human"
        if hasattr(self.ui, 'combo_db_type'):
            db_type = self.ui.combo_db_type.currentText()

        # 获取数据库筛选
        db_search = "全部"
        if hasattr(self.ui, 'combo_db_search'):
            db_search = self.ui.combo_db_search.currentText()

        # 获取均值计算方法
        mean_method = "triMean"
        if hasattr(self.ui, 'combo_mean_method'):
            mean_method = self.ui.combo_mean_method.currentText()

        # 获取最少细胞数
        min_cells = 10
        if hasattr(self.ui, 'input_min_cells'):
            try:
                min_cells = int(self.ui.input_min_cells.text())
            except:
                min_cells = 10

        # 获取原始数据选项
        raw_use = True
        if hasattr(self.ui, 'check_raw_use'):
            raw_use = self.ui.check_raw_use.isChecked()

        self.func.log(f"正在执行CellChat通讯分析...")
        self.func.log(f"数据库: {db_type} - {db_search}")
        self.func.log(f"均值计算方法: {mean_method}")
        self.func.log(f"最少细胞数: {min_cells}")
        self.func.log(f"使用原始数据: {raw_use}")
        if celltypes:
            self.func.log(f"细胞类型筛选: {', '.join(celltypes)}")
        else:
            self.func.log("细胞类型筛选: 全部")

        self.func.log("分析可能需要几分钟，请耐心等待...")

        success, result = self.analysis.run_cellchat_analysis(
            main_annot, celltypes, db_type, db_search,
            mean_method, min_cells, raw_use
        )

        if not success:
            self.func.alert_failure(f"CellChat分析失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"CellChat分析完成")
        self.func.display_stage3_images(result['count'], result['weight'])
        
        # 读取并显示通路信息表
        self._load_and_display_pathway_info()
        
        self.func.alert_success("CellChat通讯分析完成")

        # 切换到通讯数量图标签页
        if hasattr(self.ui, 'primary_tabs'):
            self.ui.primary_tabs.setCurrentIndex(2)

        # 初始化亚组列表并启用阶段四
        self._init_subgroup_list()
        self._init_pathway_list()
        self.enable_stage4_button()
    
    def _load_and_display_pathway_info(self):
        """读取并显示通路信息表"""
        import pandas as pd
        
        output_dir = self.analysis._get_output_dir()
        info_file = os.path.join(output_dir, "pathway_info.csv")
        
        self.func.log(f"检查通路信息表: {info_file}")
        self.func.log(f"文件存在: {os.path.exists(info_file)}")
        
        if os.path.exists(info_file):
            try:
                info_data = pd.read_csv(info_file)
                self.func.log(f"读取成功: {len(info_data)} 行, {len(info_data.columns)} 列")
                self.func.log(f"列名: {list(info_data.columns)}")
                if len(info_data) > 0:
                    self.func.log(f"第一行数据: {info_data.iloc[0].tolist()}")
                self.func.display_pathway_info_table(info_data)
                self.func.log(f"通路信息表已加载: {len(info_data)} 条通路")
            except Exception as e:
                import traceback
                self.func.log(f"加载通路信息表失败: {e}")
                self.func.log(traceback.format_exc())
        else:
            self.func.log(f"未找到通路信息表，目录内容:")
            if os.path.exists(output_dir):
                for f in os.listdir(output_dir):
                    self.func.log(f"  - {f}")

    def _init_subgroup_list(self):
        """初始化亚组列表"""
        if not hasattr(self.ui, 'list_subgroups'):
            return

        self.ui.list_subgroups.clear()

        # 获取当前使用的注释列
        main_annot = ""
        if hasattr(self.ui, 'combo_stage3_annot'):
            annot = self.ui.combo_stage3_annot.currentText()
            if annot != "默认（使用阶段一）":
                main_annot = annot
            elif hasattr(self.ui, 'combo_annotation'):
                main_annot = self.ui.combo_annotation.currentText()
        
        if main_annot == "选择注释列" or not main_annot:
            main_annot = ""

        # 从metadata获取亚组
        subgroups = []
        if main_annot and self._metadata_values and main_annot in self._metadata_values:
            subgroups = list(set(self._metadata_values[main_annot]))
        
        if subgroups:
            from PyQt5.QtWidgets import QListWidgetItem
            for sg in sorted(subgroups):
                item = QListWidgetItem(sg)
                self.ui.list_subgroups.addItem(item)
            
            # 默认全选
            self.ui.list_subgroups.selectAll()
            self.func.log(f"已加载 {len(subgroups)} 个亚组")
        else:
            self.func.log("未找到可用的亚组，请先运行阶段三")

    def _init_pathway_list(self):
        """初始化信号通路列表"""
        if not hasattr(self.ui, 'list_pathways'):
            return

        self.ui.list_pathways.clear()

        # 尝试从CellChat对象获取通路列表
        try:
            import os
            import subprocess
            output_dir = self.analysis._get_output_dir()
            cellchat_rds_path = os.path.join(output_dir, f"{self.analysis.dataset_name}_cellchat.rds")
            
            if os.path.exists(cellchat_rds_path):
                # 创建临时R脚本获取通路列表
                temp_r_script = os.path.join(output_dir, "get_pathways_temp.R")
                rds_path_fixed = cellchat_rds_path.replace('\\', '/')
                
                r_code = f'''
library(CellChat)
cellchat <- readRDS("{rds_path_fixed}")
pathways <- cellchat@netP$pathways
cat(paste(pathways, collapse="\\n"))
'''
                with open(temp_r_script, 'w') as f:
                    f.write(r_code)
                
                # 运行R脚本
                r_script_path = "A:\\TOOLS\\R\\R-4.6.1\\bin\\Rscript.exe"
                result = subprocess.run(
                    [r_script_path, temp_r_script],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=60
                )
                
                # 解析通路列表
                if result.returncode == 0 and result.stdout.strip():
                    pathways = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                    from PyQt5.QtWidgets import QListWidgetItem
                    for pw in sorted(pathways):
                        item = QListWidgetItem(pw)
                        self.ui.list_pathways.addItem(item)
                    self.func.log(f"已加载 {len(pathways)} 个信号通路")
                else:
                    self.func.log("获取通路列表失败，将使用自动模式")
                
                # 删除临时文件
                try:
                    os.remove(temp_r_script)
                except:
                    pass
            else:
                self.func.log("CellChat对象不存在，请先运行阶段三")
        except Exception as e:
            self.func.log(f"获取通路列表失败: {str(e)}")

    def run_stage4(self):
        """运行阶段四：细分亚组circle图"""
        if not self.analysis.dataset_name:
            self.func.alert_error("请先运行阶段三")
            return

        # 获取选中的亚组
        subgroups = []
        if hasattr(self.ui, 'list_subgroups'):
            for item in self.ui.list_subgroups.selectedItems():
                subgroups.append(item.text())

        # 如果全不选，当作默认全选
        if not subgroups:
            if hasattr(self.ui, 'list_subgroups'):
                for i in range(self.ui.list_subgroups.count()):
                    subgroups.append(self.ui.list_subgroups.item(i).text())
            self.func.log("未选择亚组，默认全选")

        if not subgroups:
            self.func.alert_error("没有可用的亚组")
            return

        self.func.log(f"正在生成亚组circle图...")
        self.func.log(f"选择的亚组: {', '.join(subgroups)}")

        success, result = self.analysis.run_subgroup_analysis(subgroups)

        if not success:
            self.func.alert_failure(f"亚组分析失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"亚组circle图生成完成")
        self.func.display_stage4_image(result)
        self.func.alert_success("亚组circle图生成完成")

        # 切换到亚组circle图标签页（index=5）
        if hasattr(self.ui, 'primary_tabs'):
            self.ui.primary_tabs.setCurrentIndex(5)

    def run_stage5(self):
        """运行阶段五：信号通路可视化"""
        if not self.analysis.dataset_name:
            self.func.alert_error("请先运行阶段三")
            return

        # 获取模式
        is_auto_mode = self.ui.radio_auto_mode.isChecked()
        
        # 获取可视化类型
        viz_types = []
        if self.ui.check_hierarchy.isChecked():
            viz_types.append("hierarchy")
        if self.ui.check_circle.isChecked():
            viz_types.append("circle")
        if self.ui.check_chord.isChecked():
            viz_types.append("chord")
        if self.ui.check_heatmap.isChecked():
            viz_types.append("heatmap")
        
        if not viz_types:
            self.func.alert_error("请至少选择一种可视化类型")
            return

        if is_auto_mode:
            # 自动模式
            try:
                pval_threshold = float(self.ui.input_pval_threshold.text())
            except ValueError:
                self.func.alert_error("p值阈值格式错误")
                return
            
            try:
                pathway_count = int(self.ui.input_pathway_count.text())
            except ValueError:
                self.func.alert_error("选择数量格式错误")
                return
            
            self.func.log(f"自动模式: p值阈值={pval_threshold}, 数量={pathway_count}")
            pathways = "__AUTO__"
        else:
            # 手动模式
            pathways = []
            if hasattr(self.ui, 'list_pathways'):
                for item in self.ui.list_pathways.selectedItems():
                    pathways.append(item.text())
            
            if not pathways:
                self.func.alert_error("请选择至少一个信号通路")
                return
            
            self.func.log(f"手动模式: 选择通路 {len(pathways)} 个")

        self.func.log("正在生成通路可视化图...")
        
        success, result = self.analysis.run_pathway_visualization(
            pathways=pathways,
            pval_threshold=pval_threshold if is_auto_mode else 0.05,
            pathway_count=pathway_count if is_auto_mode else 5,
            viz_types=viz_types
        )

        if not success:
            self.func.alert_failure(f"通路可视化失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log("通路可视化图生成完成")
        
        # 处理新的返回格式
        if isinstance(result, dict):
            self.func.display_stage5_images(result.get('images', {}))
            # 显示通路信息表格
            if 'info_data' in result:
                self.func.display_pathway_info_table(result['info_data'])
        else:
            self.func.display_stage5_images(result)
            
        self.func.alert_success("通路可视化图生成完成")

        # 切换到第一个可视化标签页
        # 标签页索引: 0-原始UMAP, 1-筛选UMAP, 2-通讯数量图, 3-通讯强度图, 
        #            4-通路信息表, 5-亚组circle图, 6-层次结构图, 7-通路circle图, 8-通路弦图, 9-通路热图
        if hasattr(self.ui, 'primary_tabs') and viz_types:
            tab_map = {'hierarchy': 6, 'circle': 7, 'chord': 8, 'heatmap': 9}
            self.ui.primary_tabs.setCurrentIndex(tab_map.get(viz_types[0], 6))

    def config_celltype_groups(self):
        """配置细胞类型分组"""
        # TODO: 实现分组配置对话框
        self.func.log("分组配置功能开发中...")

    def on_page_activated(self):
        """页面激活时的回调"""
        # 页面激活时同步数据
        self.sync_data_from_single_cell_main()
