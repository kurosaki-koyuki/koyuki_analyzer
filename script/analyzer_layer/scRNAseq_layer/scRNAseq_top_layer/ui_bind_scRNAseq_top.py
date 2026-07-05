# -*- coding: utf-8 -*-
"""
单细胞分析顶层导航界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.scRNAseq_layer.scRNAseq_top_layer.ui_func_scRNAseq_top import ScRNAseqTopFunc
from script.analyzer_layer.scRNAseq_layer.scRNAseq_top_layer.scRNAseq_data_analysis import ScRNADataManager
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScRNAseqTopBind:
    """单细胞分析顶层导航界面功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, ui_instance):
        self.parent = parent_window
        self.ui = ui_instance
        self.func = ScRNAseqTopFunc(ui_instance, parent_window)
        self.analysis = ScRNADataManager()
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_data_loading()

    def bind_navigation(self):
        """绑定页面导航按钮"""
        if hasattr(self.ui, 'btn_back_single_cell'):
            self.ui.btn_back_single_cell.clicked.connect(page_intersect.go_to_home)

        if hasattr(self.ui, 'btn_initial_analysis'):
            self.ui.btn_initial_analysis.clicked.connect(lambda: page_intersect.go_to_page_with_bind('analysis_page'))

        if hasattr(self.ui, 'btn_violin_plot'):
            self.ui.btn_violin_plot.clicked.connect(lambda: page_intersect.go_to_page_with_bind('violin_page'))

        if hasattr(self.ui, 'btn_bubble_plot'):
            self.ui.btn_bubble_plot.clicked.connect(lambda: page_intersect.go_to_page_with_bind('sc_targetgene_bubble_page'))

        if hasattr(self.ui, 'btn_gene_bubble_plot'):
            self.ui.btn_gene_bubble_plot.clicked.connect(lambda: page_intersect.go_to_page_with_bind('sc_genelist_bubble_page'))

        if hasattr(self.ui, 'btn_diff_analysis'):
            self.ui.btn_diff_analysis.clicked.connect(lambda: page_intersect.go_to_page_with_bind('diff_page'))

    def bind_data_loading(self):
        """绑定数据加载相关控件"""
        print(f"[SingleCellMainBind] 检查控件是否存在:")
        print(f"  btn_select_path: {hasattr(self.ui, 'btn_select_path')}")
        print(f"  h5ad_combo: {hasattr(self.ui, 'h5ad_combo')}")
        print(f"  btn_load: {hasattr(self.ui, 'btn_load')}")
        print(f"  status_text: {hasattr(self.ui, 'status_text')}")
        
        if hasattr(self.ui, 'btn_select_path'):
            print(f"[SingleCellMainBind] 绑定 btn_select_path")
            self.ui.btn_select_path.clicked.connect(self.select_data_path)
        else:
            print(f"[SingleCellMainBind] btn_select_path 不存在!")
        
        if hasattr(self.ui, 'btn_load'):
            print(f"[SingleCellMainBind] 绑定 btn_load")
            self.ui.btn_load.clicked.connect(self.load_data)
        else:
            print(f"[SingleCellMainBind] btn_load 不存在!")

    def select_data_path(self):
        """扫描数据路径"""
        self.func.log(f"开始扫描数据路径...")
        self.func.log(f"SCAN_DATA_PATH: {SCAN_DATA_PATH}")
        self.func.log(f"路径是否存在: {os.path.exists(SCAN_DATA_PATH)}")
        
        success, files, error = self.analysis.scan_data_folder()
        if not success:
            self.func.log(f"扫描失败: {error}")
            attention(self.parent, error)
            return
        self.func.log(f"扫描成功，找到 {len(files)} 个文件")
        self.func.set_combo_items(self.ui.h5ad_combo, files, keep_selection=False)
        self.func.log(f"已更新下拉框，共 {self.ui.h5ad_combo.count()} 项")

    def load_data(self):
        """加载数据"""
        selected_file = self.ui.h5ad_combo.currentText()
        
        self.func.log("正在加载数据...")
        success, data_info, error = self.analysis.load_data(selected_file)
        
        if not success:
            attention(self.parent, error)
            self.func.log(error)
            return
        
        self.func.update_data_info(data_info)
        self.func.log("数据加载完成")

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.ui, 'music_controller'):
            fix_music_controller_bindings(self, self.ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)