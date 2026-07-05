# -*- coding: utf-8 -*-
"""
bulk相关性气泡图界面功能绑定脚本
"""

from script.utils_layer.import_config import os, traceback
from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.bulk_layer.bulk_corre_layer.bulk_correbubble_layer.bulk_correbubble_analysis import get_bulk_correbubble_analysis
from script.analyzer_layer.bulk_layer.bulk_corre_layer.bulk_correbubble_layer.ui_func_bulk_correbubble import BulkCorreBubbleFunc


class BulkCorrebubbleBind:
    """bulk相关性气泡图绑定类"""

    def __init__(self, main_window, bulk_correbubble_ui):
        self.parent = main_window
        self.bulk_correbubble_ui = bulk_correbubble_ui
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.analysis = get_bulk_correbubble_analysis()
        self.func = BulkCorreBubbleFunc(bulk_correbubble_ui, main_window)
        self.current_fig_path = None
        self._bind_signals()
        self._init_page()

    def _bind_signals(self):
        """绑定按钮点击信号"""
        # 返回按钮
        if hasattr(self.bulk_correbubble_ui, 'btn_back_bulk_correbubble'):
            self.bulk_correbubble_ui.btn_back_bulk_correbubble.clicked.connect(self.on_back_clicked)

        # 运行按钮
        if hasattr(self.bulk_correbubble_ui, 'btn_run_correbubble'):
            self.bulk_correbubble_ui.btn_run_correbubble.clicked.connect(self.on_run_clicked)

    def _init_page(self):
        """初始化页面"""
        self.func.log_set_default()

    def on_back_clicked(self):
        """返回相关性分析页面"""
        page_intersect.go_to_parent_page('bulk_correbubble_page')

    def on_run_clicked(self):
        """运行相关性气泡图分析"""
        try:
            self.func.log("========== 开始相关性气泡图分析 ==========")

            if self.adata is None:
                self.func.alert_error("数据未加载，请从相关性分析页面跳转")
                return

            # 获取基因列表
            gene_list = self.func.get_gene_list()
            if not gene_list:
                self.func.alert_error("请输入至少2个基因名称")
                return
            if len(gene_list) < 2:
                self.func.alert_error("相关性分析需要至少2个基因")
                return

            self.func.log(f"输入的基因列表 ({len(gene_list)}个): {', '.join(gene_list)}")

            # 检查基因是否存在
            valid_genes = []
            invalid_genes = []
            for gene in gene_list:
                if self.analysis.get_gene_exists(gene):
                    valid_genes.append(gene)
                else:
                    invalid_genes.append(gene)

            if invalid_genes:
                self.func.log(f"跳过不存在的基因: {', '.join(invalid_genes)}")

            if len(valid_genes) < 2:
                self.func.alert_error("有效基因少于2个，无法进行相关性分析")
                return

            self.func.log(f"有效基因列表 ({len(valid_genes)}个): {', '.join(valid_genes)}")

            # 检查R环境
            if not self.analysis.is_available():
                self.func.alert_error(f"R环境不可用，无法生成图表\n{self.analysis.get_r_version()}")
                return

            self.func.log(f"R版本: {self.analysis.get_r_version()}")

            # 生成输出路径
            output_dir = self.dataset_output_dir or "."
            output_path = os.path.join(output_dir, f"correlation_bubble_{self.dataset_name}.png")

            # 绘制图表
            self._plot_with_r(valid_genes, output_path)

        except Exception as e:
            self.func.log(f"错误: {str(e)}")
            traceback.print_exc()

    def _plot_with_r(self, gene_list, output_path):
        """使用R绘制相关性气泡图"""
        try:
            # 从UI读取所有参数
            title = self.func.get_plot_title()
            title_size = self.func.get_title_size()
            axis_text_size = self.func.get_axis_text_size()
            width_ratio = self.func.get_width_ratio()
            height_ratio = self.func.get_height_ratio()
            show_sig = self.func.get_show_sig()
            anno_size = self.func.get_anno_size()
            legend_size = self.func.get_legend_size()

            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            self.func.log(f"参数: 标题={title}, 标题大小={title_size}")
            self.func.log(f"参数: 基因名字体={axis_text_size}, 宽高比={width_ratio:.2f}:{height_ratio:.2f}")
            self.func.log(f"参数: 显示显著性={show_sig}, 注释大小={anno_size:.1f}, 图例大小={legend_size:.1f}")

            self.analysis.draw_correlation_bubble_r(
                gene_list=gene_list,
                output_path=output_path,
                title=title,
                title_size=title_size,
                axis_text_size=axis_text_size,
                width_ratio=width_ratio,
                height_ratio=height_ratio,
                show_sig=show_sig,
                anno_size=anno_size,
                legend_key_width=legend_size,
                legend_key_height=legend_size,
                base_size=8.0
            )

            self.current_fig_path = output_path

            # 显示图片（使用ZoomableImageLabel）
            if hasattr(self.bulk_correbubble_ui, 'correbubble_plot_label'):
                self.func.display_image(self.bulk_correbubble_ui.correbubble_plot_label, output_path)

            self.func.log(f"相关性气泡图生成成功: {output_path}")
            self.func.alert_success("图表生成成功")

        except Exception as e:
            self.func.log(f"R绘图失败: {str(e)}")
            debug_log = self.analysis.get_r_debug_log()
            if debug_log:
                self.func.log(f"[R_DEBUG] 共 {len(debug_log)} 个错误")
                for entry in debug_log[-3:]:
                    self.func.log(f"  {entry['operation']}: {entry['error_message'][:80]}")
            self.func.alert_failure(f"图表生成失败: {str(e)}")

    def sync_data_from_corre(self, corre_bind=None):
        """从相关性分析页面同步数据"""
        try:
            if corre_bind is None:
                corre_bind = getattr(self.parent, 'bulk_corre_bind', None)

            if corre_bind is None:
                self.func.log("警告: 无法从相关性分析页面同步数据（bind对象为空）")
                return

            # 获取数据
            self.adata = corre_bind.adata
            self.dataset_name = getattr(corre_bind, 'dataset_name', None)
            self.dataset_output_dir = getattr(corre_bind, 'dataset_output_dir', None)

            if self.adata is None:
                self.func.log("警告: 相关性分析页面数据为空")
                return

            # 设置到analysis层
            self.analysis.set_adata(self.adata)
            self.analysis.set_dataset_name(self.dataset_name)
            self.analysis.set_dataset_output_dir(self.dataset_output_dir)

            # 更新界面提示
            self.func.update_hint_text(
                self.dataset_name or "Unknown",
                self.adata.n_obs,
                self.adata.n_vars
            )

            self.func.log(f"已从相关性分析页面同步数据: {self.dataset_name}")
            self.func.log(f"样本数: {self.adata.n_obs}, 基因数: {self.adata.n_vars}")

        except Exception as e:
            self.func.log(f"同步数据时出错: {str(e)}")
            traceback.print_exc()
