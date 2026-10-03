# -*- coding: utf-8 -*-
"""
scRNAseq Monocle基因列表类子层 - 前端功能层
负责：日志、表格填充、阈值筛选、基因搜索、提示框
"""

import os
from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_stylesheet_for_widget, TableSearcherMixin
)
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class ScMonocleGenelistsFunc(TableSearcherMixin):
    """基因列表类前端功能类 - 纯前端显示操作"""

    def __init__(self, ui_instance, parent_widget=None):
        self.sc_monocle_genelists_ui = ui_instance
        self.ui = ui_instance  # 兼容TableSearcherMixin的部分引用
        self.parent_widget = parent_widget if parent_widget else ui_instance.sc_monocle_genelists_page
        # 缓存原始结果DataFrame，供阈值筛选使用
        self._all_genes_df = None
        self._sig_genes_df = None

    # ---------- 日志 ----------

    def log(self, message):
        """追加日志消息"""
        if hasattr(self.ui, 'genelists_log'):
            current_text = self.ui.genelists_log.toPlainText()
            new_text = current_text + "\n" + message if current_text else message
            self.ui.genelists_log.setPlainText(new_text)
            self.ui.genelists_log.verticalScrollBar().setValue(
                self.ui.genelists_log.verticalScrollBar().maximum()
            )

    # ---------- 提示框 ----------

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    # ---------- 文件对话框 ----------

    def get_open_file_path(self, caption, filter_str):
        """弹出文件打开对话框，返回用户选择的路径"""
        if self.parent_widget:
            file_path, _ = QFileDialog.getOpenFileName(
                self.parent_widget, caption, "", filter_str)
            return file_path
        return ""

    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    # ---------- 表格填充 ----------

    def fill_all_genes_table(self, df):
        """填充所有基因列表表格"""
        self._all_genes_df = df
        if hasattr(self.ui, 'all_genes_table'):
            self._fill_table(self.ui.all_genes_table, df)

    def fill_significant_table(self, df):
        """填充显著基因列表表格"""
        self._sig_genes_df = df
        if hasattr(self.ui, 'sig_genes_table'):
            self._fill_table(self.ui.sig_genes_table, df)

    def fill_stage3_tables(self, result_dict):
        """填充阶段三的3个表格（总体 + 上调 + 下调）

        Args:
            result_dict: {
                'all': 总体DataFrame（含direction列）,
                'up': 上调DataFrame,
                'down': 下调DataFrame
            }
        """
        all_df = result_dict.get('all')
        up_df = result_dict.get('up')
        down_df = result_dict.get('down')

        if hasattr(self.ui, 'stage3_all_table'):
            self._fill_table(self.ui.stage3_all_table, all_df)
        if hasattr(self.ui, 'stage3_up_table'):
            self._fill_table(self.ui.stage3_up_table, up_df)
        if hasattr(self.ui, 'stage3_down_table'):
            self._fill_table(self.ui.stage3_down_table, down_df)

    def _fill_table(self, table_widget, df):
        """填充单个表格（参考差异分析的样式化填充）"""
        if df is None or len(df) == 0:
            table_widget.setRowCount(0)
            table_widget.setColumnCount(0)
            return

        styles = get_mod_styles()

        table_text_color = styles.get('sub_text_color', '#87CEEB')
        table_fill_color = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        table_fill_alt = styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')
        table_highlight_bg = styles.get('sub_mutant_color', 'rgba(255, 255, 200, 0.3)')

        def parse_color(color_str):
            if isinstance(color_str, QColor):
                return color_str
            if color_str.startswith('#'):
                return QColor(color_str)
            if color_str.startswith('rgba'):
                import re
                match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
                if match:
                    r, g, b, a = match.groups()
                    return QColor(int(r), int(g), int(b), int(float(a) * 255))
            return QColor(color_str)

        table_widget.setRowCount(len(df))
        table_widget.setColumnCount(len(df.columns))
        table_widget.setHorizontalHeaderLabels(list(df.columns))

        for i, row in enumerate(df.itertuples(index=False)):
            row_bg = table_fill_alt if (i % 2 == 0) else table_fill_color
            row_bg_color = parse_color(row_bg)

            for j, val in enumerate(row):
                col_name = df.columns[j]
                if pd is not None and isinstance(val, (float, int)) and not pd.isna(val):
                    # 数值格式化
                    if col_name in ("morans_I", "rho"):
                        val_str = f"{val:.4f}"
                    elif col_name in ("p_value", "q_value"):
                        val_str = f"{val:.6f}"
                    elif col_name == "morans_test_statistic":
                        val_str = f"{val:.4f}"
                    else:
                        val_str = str(val)
                elif pd is not None and pd.isna(val):
                    val_str = "NA"
                else:
                    val_str = str(val)

                item = QTableWidgetItem(val_str)
                item.setForeground(parse_color(table_text_color))
                item.setBackground(row_bg_color)

                # 显著性高亮：p或q < 0.05
                if col_name in ("p_value", "q_value"):
                    try:
                        if isinstance(val, (int, float)) and not pd.isna(val) and val < 0.05:
                            item.setBackground(parse_color(table_highlight_bg))
                    except Exception:
                        pass

                table_widget.setItem(i, j, item)

        table_widget.resizeColumnsToContents()
        table_widget.horizontalHeader().setStretchLastSection(True)

    # ---------- 基因搜索 ----------

    def setup_gene_search(self, tab_widget, tables, gene_col=0):
        """初始化基因搜索功能"""
        self._gene_search_tab_widget = tab_widget
        self._gene_search_tables = tables
        self._gene_search_col = gene_col

    def search_gene(self):
        """执行基因搜索（重写以适配本界面的ui属性名）"""
        ui = self.sc_monocle_genelists_ui
        if not hasattr(ui, 'gene_search_input'):
            return

        gene_name = ui.gene_search_input.text().strip()
        if not gene_name:
            self.alert_error("请输入基因名称")
            return

        table = self._get_current_search_table()
        if not table or table.rowCount() == 0:
            self.alert_error("当前表格无数据")
            return

        gene_col = getattr(self, '_gene_search_col', 0)
        gene_name_lower = gene_name.lower()
        found_row = -1

        # 精确匹配优先
        for row in range(table.rowCount()):
            item = table.item(row, gene_col)
            if item and item.text().lower() == gene_name_lower:
                found_row = row
                break

        # 模糊匹配兜底
        if found_row == -1:
            for row in range(table.rowCount()):
                item = table.item(row, gene_col)
                if item and gene_name_lower in item.text().lower():
                    found_row = row
                    break

        if found_row >= 0:
            table.selectRow(found_row)
            table.scrollToItem(table.item(found_row, gene_col), QAbstractItemView.PositionAtCenter)
        else:
            self.alert_error(f"未找到基因: {gene_name}")

    # ---------- 统计信息更新 ----------

    def update_stats_info(self, all_df, sig_df, stage3_df=None):
        """更新统计信息标签"""
        total_count = len(all_df) if all_df is not None else 0
        sig_count = len(sig_df) if sig_df is not None else 0
        
        up_count = 0
        down_count = 0
        if stage3_df is not None:
            up_count = len(stage3_df[stage3_df.get('direction') == 'up'])
            down_count = len(stage3_df[stage3_df.get('direction') == 'down'])

        if hasattr(self.ui, 'total_genes_label'):
            self.ui.total_genes_label.setText(f"总基因数: {total_count}")
        if hasattr(self.ui, 'sig_genes_label'):
            self.ui.sig_genes_label.setText(f"显著基因数: {sig_count}")
        if hasattr(self.ui, 'up_genes_label'):
            self.ui.up_genes_label.setText(f"上调基因数: {up_count}")
        if hasattr(self.ui, 'down_genes_label'):
            self.ui.down_genes_label.setText(f"下调基因数: {down_count}")

    # ---------- 按钮/控件状态管理 ----------

    def set_run_button_enabled(self, enabled):
        """启用/禁用运行按钮"""
        if hasattr(self.ui, 'btn_run_graph_test'):
            self.ui.btn_run_graph_test.setEnabled(enabled)

    def set_filter_button_enabled(self, enabled):
        """启用/禁用阈值筛选按钮"""
        if hasattr(self.ui, 'btn_apply_threshold'):
            self.ui.btn_apply_threshold.setEnabled(enabled)

    def set_stage3_button_enabled(self, enabled):
        """启用/禁用阶段三运行按钮"""
        if hasattr(self.ui, 'btn_run_stage3'):
            self.ui.btn_run_stage3.setEnabled(enabled)

    def set_run_button_enabled_stage3(self, enabled):
        """阶段三运行时禁用/启用运行按钮（同时禁用阶段一按钮避免冲突）"""
        if hasattr(self.ui, 'btn_run_stage3'):
            self.ui.btn_run_stage3.setEnabled(enabled)
        if hasattr(self.ui, 'btn_run_graph_test'):
            self.ui.btn_run_graph_test.setEnabled(enabled)

    def set_stage4_button_enabled(self, enabled):
        """启用/禁用阶段四运行按钮"""
        if hasattr(self.ui, 'btn_run_stage4'):
            self.ui.btn_run_stage4.setEnabled(enabled)

    def set_run_button_enabled_stage4(self, enabled):
        """阶段四运行时禁用/启用运行按钮"""
        if hasattr(self.ui, 'btn_run_stage4'):
            self.ui.btn_run_stage4.setEnabled(enabled)
        if hasattr(self.ui, 'btn_run_graph_test'):
            self.ui.btn_run_graph_test.setEnabled(enabled)
        if hasattr(self.ui, 'btn_run_stage3'):
            self.ui.btn_run_stage3.setEnabled(enabled)

    def set_export_button_enabled(self, enabled):
        """启用/禁用导出按钮"""
        if hasattr(self.ui, 'btn_export_xlsx'):
            self.ui.btn_export_xlsx.setEnabled(enabled)

    def set_progress_visible(self, visible):
        """显示/隐藏进度条"""
        if hasattr(self.ui, 'progress_bar'):
            self.ui.progress_bar.setVisible(visible)
            if visible:
                self.ui.progress_bar.setValue(0)

    def set_progress_value(self, value):
        """设置进度条值（0-100）"""
        if hasattr(self.ui, 'progress_bar'):
            self.ui.progress_bar.setValue(int(value))

    def update_data_info(self, info):
        """更新数据信息显示"""
        if hasattr(self.ui, 'data_info_text'):
            text = f"数据集: {info.get('dataset', '未知')}\n"
            text += f"rds路径: {info.get('rds_path', '未共享')}\n"
            text += f"筛选模式: {info.get('filter_mode', '未知')}"
            self.ui.data_info_text.setPlainText(text)

    def show_volcano_image(self, image_path):
        """在阶段四标签页显示火山图图片"""
        if hasattr(self.ui, 'stage4_volcano_label') and image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self.ui.stage4_volcano_label.setPixmap(pixmap)
                self.ui.stage4_volcano_label.setScaledContents(True)
                # 切换到火山图标签页（索引5）
                if hasattr(self.ui, 'genelists_tabs'):
                    self.ui.genelists_tabs.setCurrentIndex(5)
