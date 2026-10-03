# -*- coding: utf-8 -*-
"""
空转差异分析前端功能脚本 - 只负责前端显示、控件内容更新、表格填充、火山图渲染等
不绑定信号，不写业务算法，不处理导出逻辑

## 复刻来源（**近似 1:1**）
`script/analyzer_layer/scRNAseq_layer/diff_layer/py_diff/ui_func_diff.py`（303 行）。
本文件与它的差别**只有两处**，其余逐字照抄：

1. **`log` / `_collect_log`**：原型只 `append` 到 `diff_log`；本页把**同一份文本**收进
   `self._log_lines`，好让 bind 侧「参与分析的样本 / 被排除的样本」（规格 §4.2.3）能
   **真的写进日志**、并在控件缺失时仍能留痕（`get_collected_log`）。追加语义不变。
2. **控件名**：`self.diff_ui` 换成 `self.ui`（本页的布局对象名，与其它空转子页一致）。
   全部属性名与原型**逐字一致**（规格 §5.1 冻结）：`diff_log` / `diff_group_combo` /
   `diff_group1_list` / `diff_group2_list` / `diff_filter1_col` / `diff_filter1_list` /
   `diff_filter2_col` / `diff_filter2_list` / `diff_group1_cell_label` /
   `diff_group2_cell_label` / `diff_up_label` / `diff_down_label` / `diff_stable_label` /
   `diff_total_label` / `diff_result_tabs` / `diff_result_table` / `diff_result_table_up` /
   `diff_result_table_down` / `diff_volcano_label` / `gene_search_input` / `gene_search_btn`。

## ⛔ 本文件**不做**的事
- 不写盘、不落盘任何中间产物（导出归 bind 的文件对话框，中间产物归 W3 的 `_diff/`）；
- 不调分析层（那是 bind 的职责）；
- 不自己实现基因搜索（走既有 `TableSearcherMixin.setup_gene_search`）。
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_styles, TableSearcherMixin
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class SpatialDiffFunc(TableSearcherMixin):
    """空转差异分析前端功能类 - 纯前端显示操作"""

    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget
        # 已写入日志的文本快照（追加语义；供 bind 在控件缺失时仍能读回，见 `_collect_log`）
        self._log_lines = []
        self._setup_gene_search()

    # ---------- 下拉框/列表内容更新 ----------

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全地设置下拉框内容，可选保持当前选中项（**逐字照抄**原型 `ui_func_diff.py:22-30`）

        ★ 本页的关键语义（规格 §4.3）：`blockSignals(True)` 保证**重算选项本身不会触发**
          `currentIndexChanged`（否则"样本变化 → 重填分组 → 触发分组变化 → 重算注释值"
          会绕圈）；`keep_selection=True` + `saved_text in items` 实现"仍在列表里就保持"。
        """
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
        combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        """填充列表控件并可选全选（**逐字照抄**原型 `ui_func_diff.py:32-38`）

        ★ 本页两个「注释值」列表一律走 `select_all=False`（规格 §4.3：**不自动勾选**，
          交由用户点）——筛选值列表同样 `False`（与原型 `:142/:146` 一致）。
        """
        list_widget.clear()
        list_widget.addItems(items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def update_group_list(self, group_col, unique_vals):
        """更新分组列表（旧版兼容，**逐字照抄**原型）"""
        self.update_group_lists(group_col, unique_vals)

    def update_group_lists(self, group_col, unique_vals):
        """更新两个组别列表（**逐字照抄**原型 `ui_func_diff.py:44-49`）

        ★ 一律 `select_all=False`：**绝不自动勾选**任何注释值（规格 §4.3/§4.5）。
        """
        if hasattr(self.ui, 'diff_group1_list'):
            self.fill_list_widget(self.ui.diff_group1_list, unique_vals, select_all=False)
        if hasattr(self.ui, 'diff_group2_list'):
            self.fill_list_widget(self.ui.diff_group2_list, unique_vals, select_all=False)

    # ---------- 统计标签更新 ----------

    def update_diff_stats(self, df, group1_items, group2_items=None):
        """更新差异分析统计结果显示（**逐字照抄**原型 `ui_func_diff.py:53-84`）

        ★ 6 个标签全部按**组名**改写（不是写死"组1/组2"）；
          页签 1/2 改名为 `{组1名}显著上调` / `{组1名}显著下调`（**页签 0/3 不动**）。

        Args:
            df: 差异分析结果 DataFrame（需含 `change` / `n_cells_group1` / `n_cells_group2`）
            group1_items: 组别1 的分组列表（可多选 → 组名用 `"+"` 连接）
            group2_items: 组别2 的分组列表（可多选）
        """
        if group2_items is None:
            group2_items = []

        group1_name = "+".join(group1_items) if len(group1_items) > 1 else (group1_items[0] if group1_items else "组1")
        group2_name = "+".join(group2_items) if len(group2_items) > 1 else (group2_items[0] if group2_items else "组2")

        total_count = len(df)
        up_count = len(df[df['change'] == 'up'])
        down_count = len(df[df['change'] == 'down'])
        stable_count = len(df[df['change'] == 'stable'])

        group1_cells = df['n_cells_group1'].iloc[0] if len(df) > 0 else 0
        group2_cells = df['n_cells_group2'].iloc[0] if len(df) > 0 else 0

        self.ui.diff_group1_cell_label.setText(f"{group1_name}细胞数: {group1_cells}")
        self.ui.diff_group2_cell_label.setText(f"{group2_name}细胞数: {group2_cells}")
        self.ui.diff_up_label.setText(f"{group1_name}显著上调: {up_count}")
        self.ui.diff_down_label.setText(f"{group1_name}显著下调: {down_count}")
        self.ui.diff_stable_label.setText(f"稳定基因: {stable_count}")
        self.ui.diff_total_label.setText(f"总基因: {total_count}")

        if hasattr(self.ui, 'diff_result_tabs'):
            self.ui.diff_result_tabs.setTabText(1, f"{group1_name}显著上调")
            self.ui.diff_result_tabs.setTabText(2, f"{group1_name}显著下调")

    # ---------- 表格填充 ----------

    def fill_result_tables(self, df, df_up, df_down):
        """填充三个结果表格（**逐字照抄**原型 `ui_func_diff.py:88-93`）"""
        self._fill_table(self.ui.diff_result_table, df)
        self._fill_table(self.ui.diff_result_table_up, df_up)
        self._fill_table(self.ui.diff_result_table_down, df_down)
        self.update_stats_info(df, df_up, df_down)

    def update_stats_info(self, df, df_up, df_down):
        """更新统计信息显示（**逐字照抄**原型 `ui_func_diff.py:95-113`）

        ⚠ 原型里它是 `fill_result_tables` 的最后一跳、且在 `update_diff_stats` **之后**
          执行 ⇒ 标签文本会被**这一版**（写死"组1/组2"）覆盖。这是原型的**既有行为**，
          本页**照抄不改**（规格 §5.1「近似 1:1 复刻」）。
        """
        if not hasattr(self.ui, 'diff_group1_cell_label'):
            return

        n_cells_group1 = int(df['n_cells_group1'].iloc[0]) if len(df) > 0 and 'n_cells_group1' in df.columns else 0
        n_cells_group2 = int(df['n_cells_group2'].iloc[0]) if len(df) > 0 and 'n_cells_group2' in df.columns else 0

        up_count = len(df_up) if df_up is not None else 0
        down_count = len(df_down) if df_down is not None else 0
        stable_count = len(df) - up_count - down_count if df is not None else 0
        total_count = len(df) if df is not None else 0

        self.ui.diff_group1_cell_label.setText(f"组1细胞数: {n_cells_group1}")
        self.ui.diff_group2_cell_label.setText(f"组2细胞数: {n_cells_group2}")
        self.ui.diff_up_label.setText(f"组1显著上调: {up_count}")
        self.ui.diff_down_label.setText(f"组1显著下调: {down_count}")
        self.ui.diff_stable_label.setText(f"稳定基因: {stable_count}")
        self.ui.diff_total_label.setText(f"总基因: {total_count}")

    def _fill_table(self, table_widget, df):
        """填充单个表格（**逐字照抄**原型 `ui_func_diff.py:115-173`）

        ## ★ 表头列数：**布局层写死 10 列**，本方法按 DataFrame 实际列填充 ⇒ 12 列
          规格 §5.3 明确要求：「表格表头在原型里是"建页时写死 10 列"（不含
          `significant`/`change`），三张表各写一次；复刻照此（并在 docstring 注明
          数据层有 12 列）」。
          ⇒ 10 列写在 **W1 的布局**里；而这里的 `setColumnCount(len(df.columns))` 是
            原型行为（运行时扩成 12 列，因为结果 DataFrame 带 `significant`/`change`）。
            若真要"界面只显示 10 列"，就必须在这里截列 —— 那会**偏离原型**、
            且让「显著性/上下调」在表里不可见，故**照抄不截**，如实记录在此。
        """
        styles = get_mod_styles()

        table_text_color = styles.get('sub_text_color', '#87CEEB')
        table_fill_color = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        table_fill_alt = styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')
        table_highlight_bg = styles.get('sub_mutant_color', 'rgba(255, 255, 200, 0.3)')
        table_log2fc_up = styles.get('sub_mutant_color', '#FF6B35')
        table_log2fc_down = styles.get('sub_text_color', '#87CEEB')

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
                if isinstance(val, float):
                    if df.columns[j] in ["log2FC", "p_val", "p_val_adj"]:
                        val_str = f"{val:.4f}"
                    else:
                        val_str = f"{val:.2f}"
                else:
                    val_str = str(val)

                item = QTableWidgetItem(val_str)
                item.setForeground(parse_color(table_text_color))
                item.setBackground(row_bg_color)

                if df.columns[j] == "p_val_adj" and isinstance(val, float) and val < 0.05:
                    item.setBackground(parse_color(table_highlight_bg))
                    item.setForeground(parse_color(table_text_color))
                elif df.columns[j] == "log2FC":
                    if isinstance(val, float):
                        if val > 1:
                            item.setForeground(parse_color(table_log2fc_up))
                        elif val < -1:
                            item.setForeground(parse_color(table_log2fc_down))

                table_widget.setItem(i, j, item)

        table_widget.resizeColumnsToContents()
        table_widget.horizontalHeader().setStretchLastSection(True)

    # ---------- 火山图渲染 ----------

    def render_volcano_plot(self, df, group_col, selected_groups):
        """渲染火山图到 QLabel（**逐字照抄**原型 `ui_func_diff.py:177-257`）

        ★ 着色走结果的 `change` 列（= 分析层按 `p_val_adj` / `log2FC` 判出的 up/down/stable）；
          虚线与阈值提示**写死** `y=-log10(0.05)`、`x=±1`（规格 §5.3：**不跟随 UI 微调框**）。
        ★ matplotlib 用 `FigureCanvasQTAgg` 现画 → `canvas.grab()` 贴到 `diff_volcano_label`；
          失败**只追加日志**（原型 `:255-257`），绝不抛。

        Args:
            df: 差异分析结果 DataFrame
            group_col: 分组列名（原型未使用，仅保留签名）
            selected_groups: `[[组别1项…], [组别2项…]]`（原型未使用，仅保留签名）
        """
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            import numpy as np

            styles = get_mod_styles()

            volcano_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
            volcano_text = styles.get('sub_text_color', '#87CEEB')
            volcano_mutant = styles.get('sub_mutant_color', '#FF6B35')
            volcano_stable = styles.get('sub_border_color', '#666666')

            def convert_to_hex(rgba_str):
                import re
                if rgba_str.startswith('#'):
                    return rgba_str
                match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*[\d.]+\)', rgba_str)
                if match:
                    r, g, b = match.groups()
                    return f'#{int(r):02x}{int(g):02x}{int(b):02x}'
                return rgba_str

            volcano_text_hex = convert_to_hex(volcano_text)
            volcano_mutant_hex = convert_to_hex(volcano_mutant)
            volcano_stable_hex = convert_to_hex(volcano_stable)

            fig = Figure(figsize=(8, 6), dpi=100)
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)

            df_plot = df.copy()
            df_plot['-log10(p值)'] = -np.log10(df_plot['p_val'] + 1e-300)

            ax.set_facecolor(volcano_bg)
            fig.patch.set_alpha(0)

            ax.scatter(df_plot[df_plot['change'] != 'up']['log2FC'],
                       df_plot[df_plot['change'] != 'up']['-log10(p值)'],
                       c=volcano_stable_hex, alpha=0.5, s=20, label='Not significant')
            ax.scatter(df_plot[df_plot['change'] == 'up']['log2FC'],
                       df_plot[df_plot['change'] == 'up']['-log10(p值)'],
                       c=volcano_mutant_hex, alpha=0.7, s=30, label='Up')
            ax.scatter(df_plot[df_plot['change'] == 'down']['log2FC'],
                       df_plot[df_plot['change'] == 'down']['-log10(p值)'],
                       c=volcano_text_hex, alpha=0.7, s=30, label='Down')

            ax.set_xlabel('log2 Fold Change', fontsize=12, color=volcano_text_hex)
            ax.set_ylabel('-log10(p-value)', fontsize=12, color=volcano_text_hex)
            ax.set_title('Differential Expression', fontsize=14, color=volcano_text_hex)
            ax.legend()

            ax.axhline(y=-np.log10(0.05), color=volcano_stable_hex, linestyle='--', alpha=0.5)
            ax.axvline(x=1, color=volcano_stable_hex, linestyle='--', alpha=0.5)
            ax.axvline(x=-1, color=volcano_stable_hex, linestyle='--', alpha=0.5)

            ax.tick_params(axis='x', colors=volcano_text_hex)
            ax.tick_params(axis='y', colors=volcano_text_hex)
            ax.spines['bottom'].set_color(volcano_stable_hex)
            ax.spines['top'].set_color(volcano_stable_hex)
            ax.spines['left'].set_color(volcano_stable_hex)
            ax.spines['right'].set_color(volcano_stable_hex)

            fig.tight_layout()

            canvas.draw()
            pixmap = canvas.grab()
            self.ui.diff_volcano_label.setPixmap(pixmap)

            import matplotlib.pyplot as plt
            plt.close(fig)
        except Exception as e:
            if hasattr(self.ui, 'diff_log'):
                self.ui.diff_log.append(f"火山图绘制失败: {str(e)}")

    # ---------- 日志 ----------

    def log(self, message):
        """追加日志消息（原型 `ui_func_diff.py:261-264` + 本页的**快照留痕**）

        ★ 追加语义不变；额外把同一份文本收进 `self._log_lines`，供 bind 在
          `diff_log` 缺失时仍能留下"参与/被排除样本"的痕迹（规格 §4.2.3「不许静默」）。
        """
        self._collect_log(message)
        if hasattr(self.ui, 'diff_log'):
            self.ui.diff_log.append(message)

    def _collect_log(self, message):
        """把日志文本收进快照（**只记文本，不碰控件**；任何异常都只留痕）"""
        try:
            self._log_lines.append(str(message))
        except Exception:
            traceback.print_exc()

    def get_collected_log(self):
        """返回本次会话已写入日志的文本列表（只读副本）"""
        try:
            return list(self._log_lines)
        except Exception:
            traceback.print_exc()
            return []

    # ---------- 前端提示信息 ----------

    def alert_error(self, message):
        """显示错误提示（**逐字照抄**原型）"""
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def alert_failure(self, message):
        """显示失败提示（**逐字照抄**原型）"""
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_success(self, message):
        """显示成功提示（**逐字照抄**原型）"""
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    # ---------- 文件对话框 ----------

    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径（**逐字照抄**原型）

        ★ 本页**绝不自动落盘到 OUTPUT**（规格 §7.7）：导出 xlsx/png 一律经用户选路径。
        """
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""

    # ---------- 样本列表（★ 空转新增控件，规格 §5.2；**尽量保住已选**） ----------

    def set_sample_items(self, samples, selected_ids=None):
        """填充样本多选列表（`sample_list`）

        ## ★★ 为什么必须透传 `selected_ids`（比"填得上"更要紧）
          `page_intersect` 每次进页都会调 `on_page_entered()` ⇒ 本方法会被反复调用；
          若默认清空选择，"用户选好样本 → 回 hub → 再进来"就丢选择（D8 型事故）。
          故 `selected_ids=None` 时**读当前 UI 选择**保住它（列表控件在页面常驻）。

        Args:
            samples: list[dict]，每项至少含 `'id'`；可选 `'label'`
            selected_ids: 需要置为已选的样本 id 集合（None = 读当前选择）
        ★ 容错：None / 非 list / 元素非 dict 一律忽略，**不抛异常**。
        """
        widget = getattr(self.ui, 'sample_list', None)
        if widget is None:
            self._collect_log("⚠ 布局缺少控件 sample_list → 样本列表无法填充（需要 W1 提供）")
            return
        try:
            widget.clear()
        except Exception:
            traceback.print_exc()
            return

        if selected_ids is None:
            selected_ids = self.get_selected_sample_ids()
        chosen = set()
        if isinstance(selected_ids, (list, tuple, set)):
            chosen = {str(x) for x in selected_ids}

        items = samples if isinstance(samples, (list, tuple)) else []
        added = 0
        for entry in items:
            if not isinstance(entry, dict):
                continue
            sample_id = str(entry.get('id', '')) or "（未知样本）"
            label = str(entry.get('label', '') or '')
            # ★ 文本口径照初始页 `sample_item_text`（label 已含样本号时不重复）
            if label and sample_id and sample_id in label:
                text = label
            elif label:
                text = ("%s %s" % (sample_id, label)).strip()
            else:
                text = sample_id
            try:
                item = QListWidgetItem(text)
                # ★★ 必须写 UserRole：绑定侧靠它取**真实样本 id**（照初始页 :143）
                item.setData(Qt.UserRole, sample_id)
                widget.addItem(item)
                if sample_id in chosen:
                    item.setSelected(True)
                added += 1
            except Exception:
                traceback.print_exc()

        self.set_selected_count(widget.selectedItems() if added else [], added)

    def get_selected_sample_ids(self):
        """读取当前选中的样本 id 列表（★ **只读控件**，不查分、不写盘；照初始页 :152-160）"""
        widget = getattr(self.ui, 'sample_list', None)
        if widget is None:
            return []
        try:
            return [it.data(Qt.UserRole) for it in widget.selectedItems()]
        except Exception:
            traceback.print_exc()
            return []

    def set_selected_count(self, selected_items, total=None):
        """更新「已选 N / M」计数（照初始页 :162-174）"""
        label = getattr(self.ui, 'sample_count_label', None)
        if label is None:
            return
        try:
            selected = len(selected_items) if selected_items else 0
        except Exception:
            selected = 0
        if total is None:
            widget = getattr(self.ui, 'sample_list', None)
            total = widget.count() if widget is not None else 0
        try:
            label.setText("已选 %d / %d" % (selected, total))
        except Exception:
            traceback.print_exc()

    def refresh_selected_count(self):
        """按当前控件状态刷新计数（供 bind 在选中变化后调用）"""
        widget = getattr(self.ui, 'sample_list', None)
        if widget is None:
            return
        try:
            self.set_selected_count(widget.selectedItems(), widget.count())
        except Exception:
            traceback.print_exc()

    # ---------- 基因搜索 ----------

    def _setup_gene_search(self):
        """初始化基因搜索功能（**逐字照抄**原型 `ui_func_diff.py:293-303`）

        ★ 必须走既有 `TableSearcherMixin.setup_gene_search`
          ⇒ **页签 index 0/1/2 = 总体列表 / 显著上调 / 显著下调**，
             **火山图必须留在 index 3**（规格 §5.3：表格顺序不许动）。
        """
        if not hasattr(self.ui, 'diff_result_tabs'):
            return
        tables = [
            getattr(self.ui, 'diff_result_table', None),
            getattr(self.ui, 'diff_result_table_up', None),
            getattr(self.ui, 'diff_result_table_down', None),
        ]
        tables = [t for t in tables if t is not None]
        self.setup_gene_search(self.ui.diff_result_tabs, tables, gene_col=0)


__all__ = ['SpatialDiffFunc']
