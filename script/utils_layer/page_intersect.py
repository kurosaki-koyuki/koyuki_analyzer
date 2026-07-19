# -*- coding: utf-8 -*-
"""
页面路由管理器 - 全权管理页面注册和跳转
提供统一的页面跳转接口，自动处理bind层初始化
"""

import importlib

class PageIntersect:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.pages = {}
            cls._instance.stacked_widget = None
            cls._instance.main_window = None
            cls._instance.page_configs = [
                {
                    'name': 'scRNAseq_top_page',
                    'ui_class': 'ScRNAseqTopPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.scRNAseq_top_layer.ui_layout_scRNAseq_top',
                    'bind_class': 'ScRNAseqTopBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.scRNAseq_top_layer.ui_bind_scRNAseq_top',
                    'attr_name': 'scRNAseq_top_page'
                },
                {
                    'name': 'sc_umap_initial_page',
                    'ui_class': 'ScUmapInitialPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.ui_layout_sc_umap_initial',
                    'bind_class': 'ScUmapInitialBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.sc_umap_initial_layer.ui_bind_sc_umap_initial',
                    'attr_name': 'sc_umap_initial_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'violin_page',
                    'ui_class': 'ViolinPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.violin_layer.ui_layout_violin',
                    'bind_class': 'ViolinBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.violin_layer.ui_bind_violin',
                    'attr_name': 'violin_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {'name': 'diff_page',
                    'ui_class': 'DiffPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.diff_layer.py_diff.ui_layout_diff',
                    'bind_class': 'DiffBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.diff_layer.py_diff.ui_bind_diff',
                    'attr_name': 'diff_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'scRNAseq_r_diff_page',
                    'ui_class': 'RDiffPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.diff_layer.r_diff.ui_layout_r_diff',
                    'bind_class': 'RDiffBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.diff_layer.r_diff.ui_bind_r_diff',
                    'attr_name': 'r_diff_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'sc_genelist_bubble_page',
                    'ui_class': 'ScGenelistBubblePageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.sc_genelist_bubble_layer.ui_layout_sc_genelist_bubble',
                    'bind_class': 'ScGenelistBubbleBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.sc_genelist_bubble_layer.ui_bind_sc_genelist_bubble',
                    'attr_name': 'genelist_bubble_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'sc_targetgene_bubble_page',
                    'ui_class': 'ScTargetgeneBubblePageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.sc_targetgene_bubble_layer.ui_layout_sc_targetgene_bubble',
                    'bind_class': 'ScTargetgeneBubbleBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.sc_targetgene_bubble_layer.ui_bind_sc_targetgene_bubble',
                    'attr_name': 'targetgene_bubble_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'sc_hdwgcna_page',
                    'ui_class': 'ScHdWgcnaPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.sc_hdwgcna_layer.ui_layout_sc_hdwgcna',
                    'bind_class': 'ScHdWgcnaBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.sc_hdwgcna_layer.ui_bind_sc_hdwgcna',
                    'attr_name': 'sc_hdwgcna_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'sc_stavia_page',
                    'ui_class': 'ScStaviaPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.sc_stavia_layer.ui_layout_sc_stavia',
                    'bind_class': 'ScStaviaBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.sc_stavia_layer.ui_bind_sc_stavia',
                    'attr_name': 'sc_stavia_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'sc_monocle_page',
                    'ui_class': 'ScMonoclePageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.ui_layout_sc_monocle',
                    'bind_class': 'ScMonocleBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.ui_bind_sc_monocle',
                    'attr_name': 'sc_monocle_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'sc_gdsc_drug_sensitivity_page',
                    'ui_class': 'ScGdscDrugSensitivityPageUI',
                    'ui_module': 'script.analyzer_layer.scRNAseq_layer.sc_gdsc_drug_sensitivity_layer.ui_layout_sc_gdsc_drug_sensitivity',
                    'bind_class': 'ScGdscDrugSensitivityBind',
                    'bind_module': 'script.analyzer_layer.scRNAseq_layer.sc_gdsc_drug_sensitivity_layer.ui_bind_sc_gdsc_drug_sensitivity',
                    'attr_name': 'sc_gdsc_drug_sensitivity_page',
                    'data_source_page': 'scRNAseq_top_page',
                    'sync_method': 'sync_data_from_single_cell_main'
                },
                {
                    'name': 'bulk_top_page',
                    'ui_class': 'BulkTopPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_top_layer.ui_layout_bulk_top',
                    'bind_class': 'BulkTopBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_top_layer.ui_bind_bulk_top',
                    'attr_name': 'bulk_top_page'
                },
                {
                    'name': 'bulk_expr_page',
                    'ui_class': 'BulkExprPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_expr_layer.ui_layout_bulk_expr',
                    'bind_class': 'BulkExprBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_expr_layer.ui_bind_bulk_expr',
                    'attr_name': 'bulk_expr_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_cox_page',
                    'ui_class': 'BulkCoxPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_cox_layer.ui_layout_bulk_cox',
                    'bind_class': 'BulkCoxBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_cox_layer.ui_bind_bulk_cox',
                    'attr_name': 'bulk_cox_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_diff_page',
                    'ui_class': 'BulkDiffPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_diff_layer.ui_layout_bulk_diff',
                    'bind_class': 'BulkDiffBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_diff_layer.ui_bind_bulk_diff',
                    'attr_name': 'bulk_diff_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_logrank_page',
                    'ui_class': 'BulkLogrankPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_logrank_layer.ui_layout_bulk_logrank',
                    'bind_class': 'BulkLogrankBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_logrank_layer.ui_bind_bulk_logrank',
                    'attr_name': 'bulk_logrank_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_cluster_page',
                    'ui_class': 'BulkClusterPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_cluster_layer.ui_layout_bulk_cluster',
                    'bind_class': 'BulkClusterBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_cluster_layer.ui_bind_bulk_cluster',
                    'attr_name': 'bulk_cluster_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_corre_page',
                    'ui_class': 'BulkCorrePageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_corre_layer.ui_layout_bulk_corre',
                    'bind_class': 'BulkCorreBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_corre_layer.ui_bind_bulk_corre',
                    'attr_name': 'bulk_corre_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_corredot_page',
                    'ui_class': 'BulkCorredotPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_corre_layer.bulk_corredot_layer.ui_layout_bulk_corredot',
                    'bind_class': 'BulkCorredotBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_corre_layer.bulk_corredot_layer.ui_bind_bulk_corredot',
                    'attr_name': 'bulk_corredot_page',
                    'parent_page': 'bulk_corre_page',
                    'data_source_page': 'bulk_corre_page',
                    'sync_method': 'sync_data_from_corre'
                },
                {
                    'name': 'bulk_correbubble_page',
                    'ui_class': 'BulkCorrebubblePageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_corre_layer.bulk_correbubble_layer.ui_layout_bulk_correbubble',
                    'bind_class': 'BulkCorrebubbleBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_corre_layer.bulk_correbubble_layer.ui_bind_bulk_correbubble',
                    'attr_name': 'bulk_correbubble_page',
                    'parent_page': 'bulk_corre_page',
                    'data_source_page': 'bulk_corre_page',
                    'sync_method': 'sync_data_from_corre'
                },
                {
                    'name': 'bulk_km_page',
                    'ui_class': 'BulkKmPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_km_layer.ui_layout_bulk_km',
                    'bind_class': 'BulkKmBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_km_layer.ui_bind_bulk_km',
                    'attr_name': 'bulk_km_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_wgcna_page',
                    'ui_class': 'BulkWgcnaPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.wgcna_layer.ui_layout_bulk_wgcna',
                    'bind_class': 'BulkWgcnaPageBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.wgcna_layer.ui_bind_bulk_wgcna',
                    'attr_name': 'bulk_wgcna_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_gdsc_drug_sensitivity_page',
                    'ui_class': 'BulkGdscDrugSensitivityPageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.bulk_gdsc_drug_sensitivity_layer.ui_layout_bulk_gdsc_drug_sensitivity',
                    'bind_class': 'BulkGdscDrugSensitivityBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.bulk_gdsc_drug_sensitivity_layer.ui_bind_bulk_gdsc_drug_sensitivity',
                    'attr_name': 'bulk_gdsc_drug_sensitivity_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'bulk_immune_estimate_page',
                    'ui_class': 'BulkImmuneEstimatePageUI',
                    'ui_module': 'script.analyzer_layer.bulk_layer.immune_top_layer.bulk_immune_estimate_layer.ui_layout_bulk_immune_estimate',
                    'bind_class': 'BulkImmuneEstimateBind',
                    'bind_module': 'script.analyzer_layer.bulk_layer.immune_top_layer.bulk_immune_estimate_layer.ui_bind_bulk_immune_estimate',
                    'attr_name': 'bulk_immune_estimate_page',
                    'data_source_page': 'bulk_top_page',
                    'sync_method': 'sync_data_from_bulk_main'
                },
                {
                    'name': 'venn_page',
                    'ui_class': 'VennPlotPageUI',
                    'ui_module': 'script.analyzer_layer.commontools_layer.vennplot_layer.ui_layout_vennplot',
                    'bind_class': 'VennPlotBind',
                    'bind_module': 'script.analyzer_layer.commontools_layer.vennplot_layer.ui_bind_vennplot',
                    'attr_name': 'vennplot_page'
                },
                {
                    'name': 'settings_page',
                    'ui_class': 'SettingsPageUI',
                    'ui_module': 'script.main_layer.settings_layer.ui_layout_settings',
                    'bind_class': 'SettingsBind',
                    'bind_module': 'script.main_layer.settings_layer.ui_bind_settings',
                    'attr_name': 'settings_page'
                }
            ]
        return cls._instance
    
    def set_main_window(self, main_window):
        self.main_window = main_window
    
    def set_stacked_widget(self, stacked_widget):
        self.stacked_widget = stacked_widget
    
    def register_page(self, page_name, page_widget):
        self.pages[page_name] = page_widget
    
    def get_page(self, page_name):
        return self.pages.get(page_name)
    
    def go_to_home(self):
        result = self.go_to_page_with_bind('home_page')
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'video_bg'):
            self.main_window.video_bg.play_return()
        return result
    
    def init_all_pages(self, main_window, stacked_widget):
        """
        初始化所有页面 - 动态创建并注册所有分析页面
        home_page 需要由主界面自己创建并手动注册
        
        Args:
            main_window: 主窗口对象，需要包含 screen_width 和 screen_height 属性
            stacked_widget: QStackedWidget 对象
        """
        self.main_window = main_window
        self.stacked_widget = stacked_widget
        
        print(f"[PageIntersect] 开始初始化所有页面，共 {len(self.page_configs)} 个页面")
        
        for config in self.page_configs:
            print(f"[PageIntersect] 正在初始化页面: {config['name']}")
            print(f"[PageIntersect]   UI模块: {config['ui_module']}")
            print(f"[PageIntersect]   UI类: {config['ui_class']}")
            print(f"[PageIntersect]   属性名: {config['attr_name']}")
            
            try:
                print(f"[PageIntersect]   尝试导入UI模块: {config['ui_module']}")
                ui_module = importlib.import_module(config['ui_module'])
                print(f"[PageIntersect]   UI模块导入成功")
                
                print(f"[PageIntersect]   尝试获取UI类: {config['ui_class']}")
                ui_class = getattr(ui_module, config['ui_class'])
                print(f"[PageIntersect]   UI类获取成功")
                
                print(f"[PageIntersect]   尝试创建UI实例")
                page_width = getattr(main_window, 'base_width', main_window.screen_width)
                page_height = getattr(main_window, 'base_height', main_window.screen_height)
                ui_instance = ui_class(main_window, page_width, page_height)
                print(f"[PageIntersect]   UI实例创建成功")
                
                print(f"[PageIntersect]   尝试获取页面控件: {config['attr_name']}")
                page_widget = getattr(ui_instance, config['attr_name'])
                print(f"[PageIntersect]   页面控件获取成功")
                
                stacked_widget.addWidget(page_widget)
                self.register_page(config['name'], page_widget)
                
                ui_attr_name = f"{config['name'].replace('_page', '_ui')}"
                setattr(main_window, ui_attr_name, ui_instance)
                setattr(main_window, config['name'], page_widget)
                
                print(f"[PageIntersect] 页面 {config['name']} UI初始化成功")
                
            except Exception as e:
                print(f"[PageIntersect] 初始化页面 {config['name']} 失败: {e}")
                import traceback
                traceback.print_exc()
                
        self._preload_all_bind_modules()
        
    def _preload_all_bind_modules(self):
        """
        预加载所有bind模块，避免运行时动态导入失败
        在PyInstaller打包环境中，动态导入需要模块在打包时被包含
        预加载确保所有bind模块在应用启动时就被加载到内存中
        """
        print(f"[PageIntersect] 开始预加载所有bind模块")
        
        for config in self.page_configs:
            bind_module_name = config.get('bind_module')
            if not bind_module_name:
                continue
                
            bind_attr_name = f"{config['name'].replace('_page', '_bind')}"
            if hasattr(self.main_window, bind_attr_name):
                print(f"[PageIntersect] bind模块 {bind_module_name} 已加载")
                continue
                
            print(f"[PageIntersect] 预加载bind模块: {bind_module_name}")
            
            try:
                bind_module = importlib.import_module(bind_module_name)
                print(f"[PageIntersect]   bind模块导入成功")
                
                bind_class_name = config.get('bind_class')
                if bind_class_name:
                    bind_class = getattr(bind_module, bind_class_name)
                    print(f"[PageIntersect]   bind类 {bind_class_name} 获取成功")
                    
                    ui_attr_name = f"{config['name'].replace('_page', '_ui')}"
                    if hasattr(self.main_window, ui_attr_name):
                        ui_instance = getattr(self.main_window, ui_attr_name)
                        bind_instance = bind_class(self.main_window, ui_instance)
                        setattr(self.main_window, bind_attr_name, bind_instance)
                        print(f"[PageIntersect]   bind实例创建成功")
                
                print(f"[PageIntersect] bind模块 {bind_module_name} 预加载完成")
                
            except Exception as e:
                print(f"[PageIntersect] 预加载bind模块 {bind_module_name} 失败: {e}")
                import traceback
                traceback.print_exc()
                
        print(f"[PageIntersect] 所有bind模块预加载完成")
    
    def get_page_config(self, page_name):
        """
        获取指定页面的配置信息
        
        Args:
            page_name: 页面名称
            
        Returns:
            dict: 页面配置字典，如果未找到返回None
        """
        for config in self.page_configs:
            if config['name'] == page_name:
                return config
        return None
    
    def go_to_page_with_bind(self, page_name, parent_bind=None):
        """
        跳转到指定页面并自动初始化bind层（如果尚未初始化）
        bind层已在应用启动时预加载，这里只需要获取已存在的bind实例
        
        Args:
            page_name: 目标页面名称
            parent_bind: 父页面的bind对象（用于数据同步等操作）
            
        Returns:
            bool: 是否跳转成功
        """
        print(f"[PageIntersect] 尝试跳转到页面: {page_name}")
        
        if not self.stacked_widget:
            print(f"[PageIntersect] 错误: stacked_widget 为空")
            return False
        
        if page_name not in self.pages:
            print(f"[PageIntersect] 错误: 页面 {page_name} 未注册")
            print(f"[PageIntersect] 已注册页面: {list(self.pages.keys())}")
            return False
        
        print(f"[PageIntersect] 页面 {page_name} 已注册，准备切换")
        self.stacked_widget.setCurrentWidget(self.pages[page_name])
        print(f"[PageIntersect] 页面切换成功")
        
        config = self.get_page_config(page_name)
        if not config:
            print(f"[PageIntersect] 错误: 未找到页面 {page_name} 的配置")
            return False
        
        bind_attr_name = f"{page_name.replace('_page', '_bind')}"
        bind_instance = None
        
        if hasattr(self.main_window, bind_attr_name):
            print(f"[PageIntersect] bind层已存在: {bind_attr_name}")
            bind_instance = getattr(self.main_window, bind_attr_name)
        else:
            print(f"[PageIntersect] bind层不存在，尝试动态导入（预加载可能失败）")
            print(f"[PageIntersect]   Bind模块: {config['bind_module']}")
            print(f"[PageIntersect]   Bind类: {config['bind_class']}")
            
            try:
                print(f"[PageIntersect]   尝试导入Bind模块: {config['bind_module']}")
                bind_module = importlib.import_module(config['bind_module'])
                print(f"[PageIntersect]   Bind模块导入成功")
                
                print(f"[PageIntersect]   尝试获取Bind类: {config['bind_class']}")
                bind_class = getattr(bind_module, config['bind_class'])
                print(f"[PageIntersect]   Bind类获取成功")
                
                ui_attr_name = f"{page_name.replace('_page', '_ui')}"
                print(f"[PageIntersect]   尝试获取UI实例: {ui_attr_name}")
                ui_instance = getattr(self.main_window, ui_attr_name)
                print(f"[PageIntersect]   UI实例获取成功")
                
                print(f"[PageIntersect]   尝试创建Bind实例")
                bind_instance = bind_class(self.main_window, ui_instance)
                setattr(self.main_window, bind_attr_name, bind_instance)
                print(f"[PageIntersect]   Bind实例创建成功")
                
            except Exception as e:
                print(f"[PageIntersect] 初始化页面 {page_name} 的bind层失败: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        if config.get('sync_method'):
            print(f"[PageIntersect] 需要同步数据，方法: {config['sync_method']}")
            if parent_bind:
                sync_method = getattr(bind_instance, config['sync_method'], None)
                if sync_method:
                    sync_method(parent_bind)
                    print(f"[PageIntersect] 数据同步成功（使用parent_bind）")
                else:
                    print(f"[PageIntersect] 警告: 未找到同步方法 {config['sync_method']}")
            elif config.get('data_source_page'):
                source_bind_attr = f"{config['data_source_page'].replace('_page', '_bind')}"
                if hasattr(self.main_window, source_bind_attr):
                    source_bind = getattr(self.main_window, source_bind_attr)
                    sync_method = getattr(bind_instance, config['sync_method'], None)
                    if sync_method:
                        sync_method(source_bind)
                        print(f"[PageIntersect] 数据同步成功（使用data_source_page）")
                    else:
                        print(f"[PageIntersect] 警告: 未找到同步方法 {config['sync_method']}")
                else:
                    print(f"[PageIntersect] 警告: 数据来源页面 {config['data_source_page']} 的bind层未初始化")
        
        print(f"[PageIntersect] 跳转到页面 {page_name} 成功")
        return True
    
    def bind_page_button(self, button, page_name, parent_bind=None):
        """
        绑定按钮点击事件到指定页面跳转
        
        Args:
            button: QPushButton对象
            page_name: 目标页面名称
            parent_bind: 父页面的bind对象（用于数据同步）
        """
        button.clicked.connect(lambda: self.go_to_page_with_bind(page_name, parent_bind))
    
    def go_to_parent_page(self, page_name):
        """
        跳转到指定页面的父页面
        
        Args:
            page_name: 当前页面名称
            
        Returns:
            bool: 是否跳转成功
        """
        config = self.get_page_config(page_name)
        if config and config.get('parent_page'):
            return self.go_to_page_with_bind(config['parent_page'])
        return False

page_intersect = PageIntersect()
