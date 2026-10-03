# -*- coding: utf-8 -*-
"""
scRNAseq Monocle界面功能绑定脚本 - 主层容器，管理子层切换
负责：1) 初始化子层UI和Bind；2) 绑定导航栏按钮；3) 数据同步透传

子层顺序（与 content_stack 索引对应）：
    0 - 初筛轨迹类 (sc_initial_monocle_layer)
    1 - 数据加载类 (sc_monocle_loading_layer)
    2 - 基因列表类 (sc_monocle_genelists_layer)
    3 - 目的基因类 (sc_monocle_targetgene_layer)
"""

from script.utils_layer.page_intersect import page_intersect


class ScMonocleContainerBind:
    def __init__(self, main_window, sc_monocle_ui):
        self.main_window = main_window
        self.sc_monocle_ui = sc_monocle_ui
        self.initial_bind = None  # 子层Bind实例（初筛轨迹类）
        self.loading_bind = None  # 子层Bind实例（数据加载类）
        self.genelists_bind = None  # 子层Bind实例（基因列表类）
        self.targetgene_bind = None  # 子层Bind实例（目的基因类）
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        """初始化所有子层（顺序与 content_stack 索引一致）"""
        self._init_initial_sub_layer()
        self._init_loading_sub_layer()
        self._init_genelists_sub_layer()
        self._init_targetgene_sub_layer()

    def _init_initial_sub_layer(self):
        """初始化子层：初筛轨迹类（索引0）"""
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_initial_monocle_layer.ui_layout_sc_monocle import ScMonoclePageUI
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_initial_monocle_layer.ui_bind_sc_monocle import ScMonocleBind

            initial_page = ScMonoclePageUI(
                self.sc_monocle_ui.initial_page_container,
                self.sc_monocle_ui.screen_width - 220,
                self.sc_monocle_ui.screen_height
            )
            self.sc_monocle_ui.initial_page_layout.addWidget(initial_page.sc_monocle_page)
            self.sc_monocle_ui.initial_ui = initial_page
            self.initial_bind = ScMonocleBind(self.main_window, initial_page)
        except Exception as e:
            print(f"初始化初筛轨迹类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def _init_loading_sub_layer(self):
        """初始化子层：数据加载类（索引1，基础骨架待扩展）"""
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_loading_layer.ui_layout_sc_monocle_loading import ScMonocleLoadingPageUI
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_loading_layer.ui_bind_sc_monocle_loading import ScMonocleLoadingBind

            loading_page = ScMonocleLoadingPageUI(
                self.sc_monocle_ui.loading_page_container,
                self.sc_monocle_ui.screen_width - 220,
                self.sc_monocle_ui.screen_height
            )
            self.sc_monocle_ui.loading_page_layout.addWidget(loading_page.sc_monocle_loading_page)
            self.sc_monocle_ui.loading_ui = loading_page
            self.loading_bind = ScMonocleLoadingBind(self.main_window, loading_page)
        except Exception as e:
            print(f"初始化数据加载类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def _init_genelists_sub_layer(self):
        """初始化子层：基因列表类（索引2，基础骨架待扩展）"""
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_genelists_layer.ui_layout_sc_monocle_genelists import ScMonocleGenelistsPageUI
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_genelists_layer.ui_bind_sc_monocle_genelists import ScMonocleGenelistsBind

            genelists_page = ScMonocleGenelistsPageUI(
                self.sc_monocle_ui.genelists_page_container,
                self.sc_monocle_ui.screen_width - 220,
                self.sc_monocle_ui.screen_height
            )
            self.sc_monocle_ui.genelists_page_layout.addWidget(genelists_page.sc_monocle_genelists_page)
            self.sc_monocle_ui.genelists_ui = genelists_page
            self.genelists_bind = ScMonocleGenelistsBind(self.main_window, genelists_page)
        except Exception as e:
            print(f"初始化基因列表类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def _init_targetgene_sub_layer(self):
        """初始化子层：目的基因类（索引3，基础骨架待扩展）"""
        try:
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_targetgene_layer.ui_layout_sc_monocle_targetgene import ScMonocleTargetgenePageUI
            from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_targetgene_layer.ui_bind_sc_monocle_targetgene import ScMonocleTargetgeneBind

            targetgene_page = ScMonocleTargetgenePageUI(
                self.sc_monocle_ui.targetgene_page_container,
                self.sc_monocle_ui.screen_width - 220,
                self.sc_monocle_ui.screen_height
            )
            self.sc_monocle_ui.targetgene_page_layout.addWidget(targetgene_page.sc_monocle_targetgene_page)
            self.sc_monocle_ui.targetgene_ui = targetgene_page
            self.targetgene_bind = ScMonocleTargetgeneBind(self.main_window, targetgene_page)
        except Exception as e:
            print(f"初始化目的基因类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_nav_buttons()

    def bind_navigation(self):
        if hasattr(self.sc_monocle_ui, 'nav_btn_back'):
            self.sc_monocle_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page')
            )

    def bind_nav_buttons(self):
        if hasattr(self.sc_monocle_ui, 'nav_btn_initial'):
            self.sc_monocle_ui.nav_btn_initial.clicked.connect(lambda: self.switch_to_initial())
        if hasattr(self.sc_monocle_ui, 'nav_btn_loading'):
            self.sc_monocle_ui.nav_btn_loading.clicked.connect(lambda: self.switch_to_loading())
        if hasattr(self.sc_monocle_ui, 'nav_btn_genelists'):
            self.sc_monocle_ui.nav_btn_genelists.clicked.connect(lambda: self.switch_to_genelists())
        if hasattr(self.sc_monocle_ui, 'nav_btn_targetgene'):
            self.sc_monocle_ui.nav_btn_targetgene.clicked.connect(lambda: self.switch_to_targetgene())

    def _clear_all_nav_selections(self):
        """取消所有导航按钮的选中状态"""
        for attr in ('nav_btn_initial', 'nav_btn_loading', 'nav_btn_genelists', 'nav_btn_targetgene'):
            if hasattr(self.sc_monocle_ui, attr):
                getattr(self.sc_monocle_ui, attr).setChecked(False)

    def switch_to_initial(self):
        """切换到初筛轨迹类子层（索引0）"""
        if hasattr(self.sc_monocle_ui, 'content_stack'):
            self.sc_monocle_ui.content_stack.setCurrentIndex(0)
            self._clear_all_nav_selections()
            self.sc_monocle_ui.nav_btn_initial.setChecked(True)

            sc_top_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
            if self.initial_bind and hasattr(self.initial_bind, 'sync_data_from_single_cell_main') and sc_top_bind:
                self.initial_bind.sync_data_from_single_cell_main(sc_top_bind)

    def switch_to_loading(self):
        """切换到数据加载类子层（索引1）"""
        if hasattr(self.sc_monocle_ui, 'content_stack'):
            self.sc_monocle_ui.content_stack.setCurrentIndex(1)
            self._clear_all_nav_selections()
            self.sc_monocle_ui.nav_btn_loading.setChecked(True)

            sc_top_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
            if self.loading_bind and hasattr(self.loading_bind, 'sync_data_from_single_cell_main') and sc_top_bind:
                self.loading_bind.sync_data_from_single_cell_main(sc_top_bind)

    def switch_to_genelists(self):
        """切换到基因列表类子层（索引2）"""
        if hasattr(self.sc_monocle_ui, 'content_stack'):
            self.sc_monocle_ui.content_stack.setCurrentIndex(2)
            self._clear_all_nav_selections()
            self.sc_monocle_ui.nav_btn_genelists.setChecked(True)

            # 调用页面激活钩子（同步共享数据并更新数据信息显示）
            if self.genelists_bind and hasattr(self.genelists_bind, 'on_page_activated'):
                self.genelists_bind.on_page_activated()

            sc_top_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
            if self.genelists_bind and hasattr(self.genelists_bind, 'sync_data_from_single_cell_main') and sc_top_bind:
                self.genelists_bind.sync_data_from_single_cell_main(sc_top_bind)

    def switch_to_targetgene(self):
        """切换到目的基因类子层（索引3）"""
        if hasattr(self.sc_monocle_ui, 'content_stack'):
            self.sc_monocle_ui.content_stack.setCurrentIndex(3)
            self._clear_all_nav_selections()
            self.sc_monocle_ui.nav_btn_targetgene.setChecked(True)

            sc_top_bind = getattr(self.main_window, 'scRNAseq_top_bind', None)
            if self.targetgene_bind and hasattr(self.targetgene_bind, 'sync_data_from_single_cell_main') and sc_top_bind:
                self.targetgene_bind.sync_data_from_single_cell_main(sc_top_bind)

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从scRNAseq主页同步数据（透传给所有子层）"""
        for bind_attr in ('initial_bind', 'loading_bind', 'genelists_bind', 'targetgene_bind'):
            bind_instance = getattr(self, bind_attr, None)
            if bind_instance and hasattr(bind_instance, 'sync_data_from_single_cell_main'):
                bind_instance.sync_data_from_single_cell_main(single_cell_bind)
