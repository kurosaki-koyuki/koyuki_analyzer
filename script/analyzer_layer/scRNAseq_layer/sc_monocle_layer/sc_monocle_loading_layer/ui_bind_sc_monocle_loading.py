# -*- coding: utf-8 -*-
"""
scRNAseq Monocle数据加载子层功能绑定脚本
负责：1) 绑定音乐控制器；2) 绑定扫描/加载按钮；3) 加载后自动生成测试图
"""

from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_loading_layer.sc_monocle_loading_analysis import ScMonocleLoadingAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_loading_layer.ui_func_sc_monocle_loading import ScMonocleLoadingFunc


class ScMonocleLoadingBind:
    def __init__(self, main_window, loading_ui):
        self.parent = main_window
        self.sc_monocle_loading_ui = loading_ui
        self.analysis = ScMonocleLoadingAnalysis()
        self.func = ScMonocleLoadingFunc(loading_ui, main_window)
        self.bind_signals()

        # 绑定音乐控制器（按项目规则，确保全局同步函数能发现）
        if hasattr(self.sc_monocle_loading_ui, 'music_controller') and self.sc_monocle_loading_ui.music_controller:
            fix_music_controller_bindings(self, self.sc_monocle_loading_ui.music_controller)

    def bind_signals(self):
        self.bind_loading_buttons()

    def bind_loading_buttons(self):
        if hasattr(self.sc_monocle_loading_ui, 'btn_scan_rds'):
            self.sc_monocle_loading_ui.btn_scan_rds.clicked.connect(self.scan_rds_path)
        if hasattr(self.sc_monocle_loading_ui, 'btn_load_rds'):
            self.sc_monocle_loading_ui.btn_load_rds.clicked.connect(self.load_and_generate_test_plot)

    def set_volume(self, value):
        """设置音量（供 fix_music_controller_bindings 绑定音量滑块）"""
        from script.mods_layer.mod_manager import global_mod_manager
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)

    def scan_rds_path(self):
        """扫描pseudo_rds_data目录"""
        self.func.log("开始扫描伪时间rds数据路径...")

        success, rds_files, error = self.analysis.scan_pseudo_rds_folder()

        if not success:
            self.func.log(f"扫描失败: {error}")
            self.func.alert_error(error)
            # 清空下拉框并显示提示
            self.func.set_combo_items(self.sc_monocle_loading_ui.rds_combo, [])
            return

        self.func.log(f"扫描成功，找到 {len(rds_files)} 个rds文件")
        self.func.set_combo_items(self.sc_monocle_loading_ui.rds_combo, rds_files, keep_selection=False)
        self.func.log(f"已更新下拉框，共 {self.sc_monocle_loading_ui.rds_combo.count()} 项")

    def load_and_generate_test_plot(self):
        """加载rds文件并自动生成带轨迹的伪时间测试图"""
        selected_file = self.sc_monocle_loading_ui.rds_combo.currentText()

        if not selected_file or selected_file in ("请先扫描rds路径", "未找到rds文件"):
            self.func.alert_error("请先扫描rds路径并选择一个rds文件")
            return

        self.func.log(f"正在加载并生成测试图: {selected_file}...")

        success, result, is_error = self.analysis.generate_test_plot(selected_file)

        if not success:
            self.func.alert_failure(f"生成测试图失败: {result}")
            self.func.log(f"❌ {result}")
            return

        # result 是PNG路径
        png_path = result
        self.func.log(f"✓ 测试图生成完成: {png_path}")

        # 显示测试图
        self.func.display_test_image(png_path)

        # 切换到测试图标签页
        if hasattr(self.sc_monocle_loading_ui, 'loading_plot_tabs'):
            self.sc_monocle_loading_ui.loading_plot_tabs.setCurrentIndex(0)

        # 更新数据信息
        self.func.update_data_info({
            'dataset': self.analysis.dataset_name,
            'rds_path': self.analysis.cds_rds_path,
            'test_plot': png_path,
        })

        # 将CDS路径共享到main_window，供基因列表类/目的基因类使用
        # 仅共享路径字符串，不复制rds文件，不在其他位置存新的rds
        try:
            self.parent.shared_monocle_cds_rds_path = self.analysis.cds_rds_path
            self.parent.shared_monocle_dataset_name = self.analysis.dataset_name
            self.func.log(f"✓ 已共享CDS路径到主窗口: {self.analysis.dataset_name}")
        except Exception as e:
            print(f"[MonocleLoading] 共享CDS路径失败: {e}")

        self.func.alert_success(f"测试图生成完成\n数据集: {self.analysis.dataset_name}")

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        """从scRNAseq主页同步数据（数据加载类独立扫描，暂不依赖主页数据）"""
        try:
            if single_cell_bind is None:
                single_cell_bind = getattr(self.parent, 'scRNAseq_top_bind', None)

            if single_cell_bind is None:
                return

            # 数据加载类使用自己的扫描路径，不依赖主页seurat_path
            # 但保留接口以便后续可能需要同步dataset_name等
        except Exception as e:
            print(f"Monocle数据加载类同步数据时出错: {str(e)}")
