# -*- coding: utf-8 -*-
"""
CellChat细胞通讯分析界面功能绑定脚本 - 主层容器，管理子层切换
负责：1) 初始化子层UI和Bind；2) 绑定导航栏按钮；3) 数据同步透传

子层顺序（与 content_stack 索引对应）：
    0 - 初步分析类 (sc_cellchat_primary_layer)
    1 - 数据加载类 (sc_cellchat_loading_layer)
"""

from script.utils_layer.page_intersect import page_intersect


class ScCellChatContainerBind:
    def __init__(self, main_window, sc_cellchat_ui):
        self.main_window = main_window
        self.sc_cellchat_ui = sc_cellchat_ui
        self.primary_bind = None  # 子层Bind实例（初步分析类）
        self.loading_bind = None  # 子层Bind实例（数据加载类）
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        """初始化所有子层（顺序与 content_stack 索引一致）"""
        self._init_primary_sub_layer()
        self._init_loading_sub_layer()

    def _init_primary_sub_layer(self):
        """初始化子层：初步分析类（索引0）"""
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_primary_layer.ui_layout_sc_cellchat_primary import ScCellChatPrimaryPageUI
            from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_primary_layer.ui_bind_sc_cellchat_primary import ScCellChatPrimaryBind

            primary_page = ScCellChatPrimaryPageUI(
                self.sc_cellchat_ui.primary_page_container,
                self.sc_cellchat_ui.screen_width - 220,
                self.sc_cellchat_ui.screen_height
            )
            self.sc_cellchat_ui.primary_page_layout.addWidget(primary_page.sc_cellchat_primary_page)
            self.sc_cellchat_ui.primary_ui = primary_page
            self.primary_bind = ScCellChatPrimaryBind(self.main_window, primary_page)
        except Exception as e:
            print(f"初始化初步分析类子层失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _init_loading_sub_layer(self):
        """初始化子层：数据加载类（索引1）"""
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_loading_layer.ui_layout_sc_cellchat_loading import ScCellChatLoadingPageUI
            from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_loading_layer.ui_bind_sc_cellchat_loading import ScCellChatLoadingBind

            loading_page = ScCellChatLoadingPageUI(
                self.sc_cellchat_ui.loading_page_container,
                self.sc_cellchat_ui.screen_width - 220,
                self.sc_cellchat_ui.screen_height
            )
            self.sc_cellchat_ui.loading_page_layout.addWidget(loading_page.sc_cellchat_loading_page)
            self.sc_cellchat_ui.loading_ui = loading_page
            self.loading_bind = ScCellChatLoadingBind(self.main_window, loading_page)
        except Exception as e:
            print(f"初始化数据加载类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_nav_buttons()

    def bind_navigation(self):
        if hasattr(self.sc_cellchat_ui, 'nav_btn_back'):
            self.sc_cellchat_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page')
            )

    def bind_nav_buttons(self):
        if hasattr(self.sc_cellchat_ui, 'nav_btn_primary'):
            self.sc_cellchat_ui.nav_btn_primary.clicked.connect(lambda: self.switch_to_primary())
        
        if hasattr(self.sc_cellchat_ui, 'nav_btn_loading'):
            self.sc_cellchat_ui.nav_btn_loading.clicked.connect(lambda: self.switch_to_loading())

    def _clear_all_nav_selections(self):
        """取消所有导航按钮的选中状态"""
        if hasattr(self.sc_cellchat_ui, 'nav_btn_primary'):
            self.sc_cellchat_ui.nav_btn_primary.setChecked(False)
        if hasattr(self.sc_cellchat_ui, 'nav_btn_loading'):
            self.sc_cellchat_ui.nav_btn_loading.setChecked(False)

    def switch_to_primary(self):
        """切换到初步分析类子层（索引0）"""
        if hasattr(self.sc_cellchat_ui, 'content_stack'):
            self.sc_cellchat_ui.content_stack.setCurrentIndex(0)
            self._clear_all_nav_selections()
            self.sc_cellchat_ui.nav_btn_primary.setChecked(True)

    def switch_to_loading(self):
        """切换到数据加载类子层（索引1）"""
        if hasattr(self.sc_cellchat_ui, 'content_stack'):
            self.sc_cellchat_ui.content_stack.setCurrentIndex(1)
            self._clear_all_nav_selections()
            self.sc_cellchat_ui.nav_btn_loading.setChecked(True)
    
    def on_page_activated(self):
        """页面激活回调"""
        # 根据当前显示的子层，通知对应的子层bind
        if hasattr(self.sc_cellchat_ui, 'content_stack'):
            current_index = self.sc_cellchat_ui.content_stack.currentIndex()
            if current_index == 0 and self.primary_bind:
                self.primary_bind.on_page_activated()
            elif current_index == 1 and self.loading_bind:
                self.loading_bind.on_page_activated()

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从scRNAseq主页同步数据（透传给所有子层）"""
        if self.primary_bind and hasattr(self.primary_bind, 'sync_data_from_single_cell_main'):
            self.primary_bind.sync_data_from_single_cell_main(single_cell_bind)
        if self.loading_bind and hasattr(self.loading_bind, 'sync_data_from_single_cell_main'):
            self.loading_bind.sync_data_from_single_cell_main(single_cell_bind)
    
    # ========== 数据共享接口 ==========
    
    def get_loading_analysis(self):
        """获取数据加载类的Analysis实例（供其他子层使用）"""
        if self.loading_bind and hasattr(self.loading_bind, 'func'):
            if hasattr(self.loading_bind.func, 'analysis'):
                return self.loading_bind.func.analysis
        return None
    
    def get_loaded_data(self):
        """获取已加载的数据信息"""
        analysis = self.get_loading_analysis()
        if analysis and analysis.is_loaded:
            return {
                'is_loaded': True,
                'dataset_name': analysis.dataset_name,
                'output_dir': analysis.output_dir,
                'rds_path': analysis.rds_path,
                'files': analysis.get_file_paths()
            }
        return {
            'is_loaded': False,
            'dataset_name': None,
            'output_dir': None,
            'rds_path': None,
            'files': None
        }
