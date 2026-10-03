# -*- coding: utf-8 -*-
"""
bulk 机器学习分析界面功能绑定脚本 - 主层容器，管理子层切换
负责：1) 初始化子层UI和Bind；2) 绑定导航栏按钮；3) 数据同步透传
参考：Monocle容器绑定层结构

子层顺序（与 content_stack 索引对应）：
    0 - 数据加载类 (bulk_machinelearning_loading_layer)
    1 - 差异训练类 (bulk_machinelearning_diff_train_layer)
    2 - 生存训练类 (bulk_machinelearning_surv_train_layer)
    （注：原「差异筛选类」空壳子层已移除，差异分析统一在差异训练类中完成训练+验证）
    （注：原「生存筛选类」层已移除，生存分析统一在生存训练类中完成训练+评价+筛选）
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect
from script.utils_layer.music_controller_fix import fix_music_controller_bindings


class BulkMachineLearningBind:
    def __init__(self, main_window, bulk_machinelearning_ui):
        self.parent = main_window
        self.main_window = main_window
        self.bulk_machinelearning_ui = bulk_machinelearning_ui
        self.loading_bind = None      # 子层Bind实例（数据加载类）
        self.diff_train_bind = None    # 子层Bind实例（差异训练类）
        self.surv_train_bind = None    # 子层Bind实例（生存训练类）
        self._init_sub_layers()
        self.bind_signals()

    def _init_sub_layers(self):
        """初始化所有子层（顺序与 content_stack 索引一致）"""
        self._init_loading_sub_layer()
        self._init_diff_train_sub_layer()
        self._init_surv_train_sub_layer()

    def _init_loading_sub_layer(self):
        """初始化子层：数据加载类（索引0）"""
        try:
            from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_loading_layer.ui_layout_bulk_machinelearning_loading import BulkMachineLearningLoadingPageUI
            from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_loading_layer.ui_bind_bulk_machinelearning_loading import BulkMachineLearningLoadingBind

            loading_page = BulkMachineLearningLoadingPageUI(
                self.bulk_machinelearning_ui.loading_page_container,
                self.bulk_machinelearning_ui.screen_width - 220,
                self.bulk_machinelearning_ui.screen_height
            )
            self.bulk_machinelearning_ui.loading_page_layout.addWidget(loading_page.bulk_machinelearning_loading_page)
            self.bulk_machinelearning_ui.loading_ui = loading_page
            self.loading_bind = BulkMachineLearningLoadingBind(self.main_window, loading_page)
        except Exception as e:
            print(f"初始化数据加载类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def _init_diff_train_sub_layer(self):
        """初始化子层：差异训练类（索引1，基础骨架待扩展）"""
        try:
            from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_diff_train_layer.ui_layout_bulk_machinelearning_diff_train import BulkMachineLearningDiffTrainPageUI
            from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_diff_train_layer.ui_bind_bulk_machinelearning_diff_train import BulkMachineLearningDiffTrainBind

            diff_train_page = BulkMachineLearningDiffTrainPageUI(
                self.bulk_machinelearning_ui.diff_train_page_container,
                self.bulk_machinelearning_ui.screen_width - 220,
                self.bulk_machinelearning_ui.screen_height
            )
            self.bulk_machinelearning_ui.diff_train_page_layout.addWidget(diff_train_page.bulk_machinelearning_diff_train_page)
            self.bulk_machinelearning_ui.diff_train_ui = diff_train_page
            self.diff_train_bind = BulkMachineLearningDiffTrainBind(self.main_window, diff_train_page)
        except Exception as e:
            print(f"初始化差异训练类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def _init_surv_train_sub_layer(self):
        """初始化子层：生存训练类（索引2，基础骨架待扩展）"""
        try:
            from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_surv_train_layer.ui_layout_bulk_machinelearning_surv_train import BulkMachineLearningSurvTrainPageUI
            from script.analyzer_layer.bulk_layer.bulk_machinelearning_layer.bulk_machinelearning_surv_train_layer.ui_bind_bulk_machinelearning_surv_train import BulkMachineLearningSurvTrainBind

            surv_train_page = BulkMachineLearningSurvTrainPageUI(
                self.bulk_machinelearning_ui.surv_train_page_container,
                self.bulk_machinelearning_ui.screen_width - 220,
                self.bulk_machinelearning_ui.screen_height
            )
            self.bulk_machinelearning_ui.surv_train_page_layout.addWidget(surv_train_page.bulk_machinelearning_surv_train_page)
            self.bulk_machinelearning_ui.surv_train_ui = surv_train_page
            self.surv_train_bind = BulkMachineLearningSurvTrainBind(self.main_window, surv_train_page)
        except Exception as e:
            print(f"初始化生存训练类子层失败: {e}")
            import traceback
            traceback.print_exc()

    def bind_signals(self):
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_nav_buttons()

    def bind_music_controls(self):
        """绑定音乐控制（主层统一管理）"""
        if hasattr(self.bulk_machinelearning_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.bulk_machinelearning_ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def bind_navigation(self):
        """绑定返回主页按钮"""
        if hasattr(self.bulk_machinelearning_ui, 'nav_btn_back'):
            self.bulk_machinelearning_ui.nav_btn_back.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('bulk_top_page')
            )

    def bind_nav_buttons(self):
        """绑定子层切换导航按钮"""
        if hasattr(self.bulk_machinelearning_ui, 'nav_btn_loading'):
            self.bulk_machinelearning_ui.nav_btn_loading.clicked.connect(lambda: self.switch_to_loading())
        if hasattr(self.bulk_machinelearning_ui, 'nav_btn_diff_train'):
            self.bulk_machinelearning_ui.nav_btn_diff_train.clicked.connect(lambda: self.switch_to_diff_train())
        if hasattr(self.bulk_machinelearning_ui, 'nav_btn_surv_train'):
            self.bulk_machinelearning_ui.nav_btn_surv_train.clicked.connect(lambda: self.switch_to_surv_train())

    def _clear_all_nav_selections(self):
        """取消所有导航按钮的选中状态"""
        for attr in ('nav_btn_loading', 'nav_btn_diff_train', 'nav_btn_surv_train'):
            if hasattr(self.bulk_machinelearning_ui, attr):
                getattr(self.bulk_machinelearning_ui, attr).setChecked(False)

    def switch_to_loading(self):
        """切换到数据加载类子层（索引0）"""
        if hasattr(self.bulk_machinelearning_ui, 'content_stack'):
            self.bulk_machinelearning_ui.content_stack.setCurrentIndex(0)
            self._clear_all_nav_selections()
            self.bulk_machinelearning_ui.nav_btn_loading.setChecked(True)

            bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
            if self.loading_bind and hasattr(self.loading_bind, 'sync_data_from_bulk_main') and bulk_top_bind:
                self.loading_bind.sync_data_from_bulk_main(bulk_top_bind)

    def switch_to_diff_train(self):
        """切换到差异训练类子层（索引1）"""
        if hasattr(self.bulk_machinelearning_ui, 'content_stack'):
            self.bulk_machinelearning_ui.content_stack.setCurrentIndex(1)
            self._clear_all_nav_selections()
            self.bulk_machinelearning_ui.nav_btn_diff_train.setChecked(True)

            bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
            if self.diff_train_bind and hasattr(self.diff_train_bind, 'sync_data_from_bulk_main') and bulk_top_bind:
                self.diff_train_bind.sync_data_from_bulk_main(bulk_top_bind)

    def switch_to_surv_train(self):
        """切换到生存训练类子层（索引2）"""
        if hasattr(self.bulk_machinelearning_ui, 'content_stack'):
            self.bulk_machinelearning_ui.content_stack.setCurrentIndex(2)
            self._clear_all_nav_selections()
            self.bulk_machinelearning_ui.nav_btn_surv_train.setChecked(True)

            bulk_top_bind = getattr(self.main_window, 'bulk_top_bind', None)
            if self.surv_train_bind and hasattr(self.surv_train_bind, 'sync_data_from_bulk_main') and bulk_top_bind:
                self.surv_train_bind.sync_data_from_bulk_main(bulk_top_bind)

    def sync_data_from_bulk_main(self, bulk_top_bind=None):
        """从bulk主页同步数据（透传给当前激活的子层）"""
        current_idx = self.bulk_machinelearning_ui.content_stack.currentIndex() if hasattr(self.bulk_machinelearning_ui, 'content_stack') else 0
        if current_idx == 0 and self.loading_bind and hasattr(self.loading_bind, 'sync_data_from_bulk_main'):
            self.loading_bind.sync_data_from_bulk_main(bulk_top_bind)
        elif current_idx == 1 and self.diff_train_bind and hasattr(self.diff_train_bind, 'sync_data_from_bulk_main'):
            self.diff_train_bind.sync_data_from_bulk_main(bulk_top_bind)
        elif current_idx == 2 and self.surv_train_bind and hasattr(self.surv_train_bind, 'sync_data_from_bulk_main'):
            self.surv_train_bind.sync_data_from_bulk_main(bulk_top_bind)
