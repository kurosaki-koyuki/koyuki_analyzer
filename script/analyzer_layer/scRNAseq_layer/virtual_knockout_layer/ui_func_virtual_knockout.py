# -*- coding: utf-8 -*-
"""
scRNAseq 虚拟敲除界面前端功能层 - 负责前端显示、控件内容更新、图片渲染等

归属 W2：本文件**只做纯前端**（填下拉框、刷日志、推进度、填表、显示图片、弹窗），
不起线程、不调 R、不写业务算法（说明书 §3.1 四层分离铁律）。

控件名一律取 `_d_spec_virtual_knockout.md` §2 的冻结名（`vk_` 前缀）；
所有控件取用都为「缺失即静默跳过」（W1 布局未落盘时本文件也必须能 import 成功）。
"""

import os
import re
import traceback

from script.utils_layer.import_config import *
# ★ get_mod_styles 不在 import_config 的星号导出里，必须显式导入（否则 show_table 抛 NameError、
#   两张结果表静默为空 —— 2026-09-25 协调者离屏探针抓到）
from script.utils_layer.gui_styles import ZoomableImageLabel, get_mod_styles
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class VirtualKnockoutFunc:
    """虚拟敲除前端功能类 - 纯前端显示操作"""

    def __init__(self, ui_instance, parent_widget=None):
        # ★ 冻结签名：第一个参数是 virtual_knockout_ui（bind 里 `VirtualKnockoutFunc(virtual_knockout_ui)`）
        self.virtual_knockout_ui = ui_instance
        self.ui = ui_instance            # 兼容既有写法
        self.parent_widget = parent_widget if parent_widget else ui_instance
        # 缓存（供表头/日志用，不参与业务判定）
        self._last_group_columns = []
        self._last_warn_text = ""
        self._last_mem_text = ""

    # ================= 控件取用小工具 =================

    @staticmethod
    def _rgba(color_str, default="#87CEEB"):
        """把 'rgba(r,g,b,a)' / '#RRGGBB' / QColor 统一解析成 QColor

        虚拟敲除层是 W2 独立实现，不复用其它层的私有静态方法（房规：不许碰别的文件）；
        这里只做表格配色用，解析失败一律回退默认色。
        """
        try:
            if color_str is None:
                return QColor(default)
            if isinstance(color_str, QColor):
                return color_str
            text = str(color_str).strip()
            if text.startswith('#'):
                return QColor(text)
            match = re.match(r'rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)', text)
            if match:
                r, g, b, a = match.groups()
                return QColor(int(r), int(g), int(b), int(float(a) * 255))
            return QColor(text)
        except Exception:
            # 配色解析失败不能影响结果展示
            traceback.print_exc()
            return QColor(default)

    def _widget(self, name):
        """按冻结名取控件；不存在返回 None（绝不用 `if not widget` 判空）"""
        return getattr(self.ui, name, None)

    @staticmethod
    def _is_window(widget):
        """控件是否存在且不是 None（★ 本仓事故档案：空 QListWidget/QComboBox 的 bool() 为 False）"""
        return widget is not None

    def _warn_label(self):
        return self._widget('vk_warn_label')

    # ================= 日志 / 进度 / 警告 =================

    def log(self, message):
        """追加日志到 vk_log（自动滚到底）"""
        widget = self._widget('vk_log')
        if not self._is_window(widget):
            return
        try:
            text = "" if message is None else str(message)
            if hasattr(widget, 'setPlainText') and hasattr(widget, 'toPlainText'):
                # QTextEdit / QPlainTextEdit：照抄 monocle func 的写法（追加 + 自动滚到底）
                current_text = widget.toPlainText()
                new_text = current_text + "\n" + text if current_text else text
                widget.setPlainText(new_text)
                scrollbar = widget.verticalScrollBar() if hasattr(widget, 'verticalScrollBar') else None
                if scrollbar is not None:
                    scrollbar.setValue(scrollbar.maximum())
                return
            if hasattr(widget, 'addItem'):
                # QListWidget 兜底
                widget.addItem(text)
                scrollbar = widget.verticalScrollBar() if hasattr(widget, 'verticalScrollBar') else None
                if scrollbar is not None:
                    scrollbar.setValue(scrollbar.maximum())
        except Exception:
            traceback.print_exc()
            print(f"[VK] 写日志失败: {message}")

    def clear_log(self):
        """清空日志框（每次运行前置空，便于对结果）"""
        widget = self._widget('vk_log')
        if not self._is_window(widget):
            return
        try:
            if hasattr(widget, 'clear'):
                widget.clear()
        except Exception:
            traceback.print_exc()

    def set_progress(self, value):
        """设置进度条数值（0-100）——说明书 §4.2.2 冻结方法名"""
        widget = self._widget('vk_progress')
        if not self._is_window(widget):
            return
        try:
            widget.setValue(int(value))
        except Exception:
            traceback.print_exc()

    def set_progress_value(self, value):
        """`set_progress` 的别名（本仓既有页面用这个名，bind 两侧都调得通）"""
        self.set_progress(value)

    def set_progress_visible(self, visible):
        """显示/隐藏进度条；显示时归零"""
        widget = self._widget('vk_progress')
        if not self._is_window(widget):
            return
        try:
            widget.setVisible(bool(visible))
            if visible:
                widget.setValue(0)
        except Exception:
            traceback.print_exc()

    def set_run_button_enabled(self, enabled, busy_text="运行中…"):
        """启用/禁用运行按钮；运行时按钮文案改为「运行中…」，结束后恢复

        ★ 文案只在控件支持 setText 时改（QPushButton 支持），失败不影响启停。
        """
        widget = self._widget('vk_btn_run')
        if not self._is_window(widget):
            return
        try:
            if hasattr(widget, 'setEnabled'):
                widget.setEnabled(bool(enabled))
            if hasattr(widget, 'setText'):
                widget.setText("运行虚拟敲除" if enabled else busy_text)
        except Exception:
            traceback.print_exc()

    def set_warning(self, text):
        """在 vk_warn_label 上显示红字口径/出边警告（说明书 §5.5 / §8.8）

        `text` 为空串表示清除警告。
        """
        widget = self._warn_label()
        if not self._is_window(widget):
            return
        try:
            text = "" if text is None else str(text)
            self._last_warn_text = text
            widget.setText(text)
            widget.setVisible(True)
            # 红字：本仓「红字警告」既有做法就是直接给这一个告警 label 上色
            # （§9.1 的「不许手写样式」判据只约束 ui_layout 里**新建控件**的外观，不约束运行期告警态）
            widget.setStyleSheet("color: #FF4C4C; background: transparent;")
        except Exception:
            traceback.print_exc()

    def clear_warning(self):
        """清除红字警告"""
        self.set_warning("")

    def set_memory_estimate(self, text):
        """记录内存预估文本（**不再上屏**）。

        ★ 甲方 2026-09-25 界面意见：「现在前端有个预估内存，其实不用预估了，那个信息去掉…
          是在前端的运行按钮右边的，去掉那几个字，太碍事了」⇒ 布局侧已删除该标签控件。
        ★ 方法名**保留**：`ui_bind.refresh_memory_estimate()` 仍在调用它（跨文件调用契约 +
          接线探针 ⑧ 的 `self.<name>()` 判据），把它变成"记录但不显示"的 no-op，
          这样 bind 一个字都不用改。
        ★ 与它无关、**必须保留**的：`ui_bind._confirm_memory()` 的**内存确认框**
          （说明书 §8.8「内存预估超限」），它只用 `_estimate_memory_gb()`，不走本方法。
        """
        self._last_mem_text = "" if text is None else str(text)

    # ================= 弹窗（照抄 monocle func 的弹窗写法） =================

    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def confirm_question(self, title, message):
        """弹确认框（`QMessageBox.question`）；用户点「是」返回 True

        用于说明书 §8.8「内存预估超限」那一条。
        """
        try:
            answer = QMessageBox.question(
                self.parent_widget if self.parent_widget else None,
                str(title),
                str(message),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            return answer == QMessageBox.Yes
        except Exception:
            # 弹窗本身失败时不能吞——留痕并返回 False（保守：不继续）
            traceback.print_exc()
            self.log(f"❌ 确认框弹出失败: {traceback.format_exc()}")
            return False

    # ================= 下拉框 / 多选列表 =================

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全设置下拉框内容（blockSignals 很关键：否则填的过程中会反复触发联动）"""
        if not self._is_window(combo_widget):
            return
        try:
            items = list(items) if items else []
            saved_text = combo_widget.currentText() if keep_selection else ""
            combo_widget.blockSignals(True)
            combo_widget.clear()
            combo_widget.addItems([str(i) for i in items])
            if saved_text and saved_text in [str(i) for i in items]:
                combo_widget.setCurrentText(saved_text)
            combo_widget.blockSignals(False)
        except Exception:
            traceback.print_exc()
            self.log(f"❌ 填充下拉框失败: {traceback.format_exc()}")

    def set_combo_items_with_data(self, combo_widget, pairs, preferred_data=None):
        """安全设置带 userData 的下拉框（基因来源模式专用）

        Args:
            pairs: [(显示文本, userData), ...]
            preferred_data: 期望选中的 userData（取不到就选第一项）
        """
        if not self._is_window(combo_widget):
            return
        try:
            saved_data = combo_widget.currentData() if hasattr(combo_widget, 'currentData') else None
            target = preferred_data if preferred_data is not None else saved_data
            combo_widget.blockSignals(True)
            combo_widget.clear()
            for text, data in pairs:
                combo_widget.addItem(str(text), data)
            if target is not None:
                idx = combo_widget.findData(target)
                if idx >= 0:
                    combo_widget.setCurrentIndex(idx)
            combo_widget.blockSignals(False)
        except Exception:
            traceback.print_exc()
            self.log(f"❌ 填充基因来源下拉框失败: {traceback.format_exc()}")

    def fill_list_widget(self, list_widget, items, select_all=True):
        """填充多选列表；select_all=True 时全选（组别默认全选）"""
        if not self._is_window(list_widget):
            return
        try:
            items = [str(i) for i in items] if items else []
            list_widget.clear()
            list_widget.addItems(items)
            if select_all:
                for i in range(list_widget.count()):
                    list_widget.item(i).setSelected(True)
        except Exception:
            traceback.print_exc()
            self.log(f"❌ 填充多选列表失败: {traceback.format_exc()}")

    def fill_group_columns(self, columns, preferred=None):
        """填「分组选择」下拉框（保留首选列，取不到就用第一项）"""
        combo = self._widget('vk_group_combo')
        if not self._is_window(combo):
            return
        columns = [str(c) for c in (columns or [])]
        self._last_group_columns = columns
        self.set_combo_items(combo, columns, keep_selection=False)
        if preferred and preferred in columns:
            try:
                combo.setCurrentIndex(columns.index(preferred))
            except Exception:
                traceback.print_exc()
        self.log(f"已刷新分组列，共 {len(columns)} 个可选注释列")

    def fill_group_values(self, values):
        """填「组别（多选）」列表，默认全选（不选 = 全选）"""
        self.fill_list_widget(self._widget('vk_group_list'), values, select_all=True)

    def fill_filter_values(self, list_widget, values):
        """填筛选条件值列表（不做全选：不选 = 该筛选不生效）"""
        self.fill_list_widget(list_widget, values, select_all=False)

    def get_gene_lists_dir(self):
        """基因列表目录 = APPDATA_PATH/genelists（不存在则创建，供下拉框扫描）"""
        genelists_dir = os.path.join(APPDATA_PATH, "genelists")
        os.makedirs(genelists_dir, exist_ok=True)
        return genelists_dir

    def fill_gene_lists(self):
        """扫 APPDATA_PATH/genelists 填「基因列表文件」下拉框

        返回文件名列表（供 bind 记录），扩展名与排序照抄
        `bulk_machinelearning_diff_train_analysis.py:128-143` 的 `_scan_dir`。
        """
        combo = self._widget('vk_gene_list_combo')
        try:
            genelists_dir = self.get_gene_lists_dir()
            exts = ('.xlsx', '.xls', '.txt', '.csv')
            if not os.path.isdir(genelists_dir):
                files = []
            else:
                files = sorted([f for f in os.listdir(genelists_dir) if f.lower().endswith(exts)])
        except Exception:
            traceback.print_exc()
            self.log(f"❌ 扫描基因列表目录失败: {traceback.format_exc()}")
            files = []

        if self._is_window(combo):
            # 第一项固定为空 = 不使用外部列表（说明书 §5.2「留空或不选 = 不使用」）
            self.set_combo_items(combo, [""] + files, keep_selection=False)
        return files

    # ================= 基因来源模式显隐 =================

    def apply_gene_mode_visibility(self, mode):
        """按基因来源模式显隐（说明书 §5.2 联动 1/2/3）

        - `hvg`：显示 N，隐藏列表文件；
        - `list`：隐藏 N，显示列表文件；
        - `all`：N 与列表文件都隐藏。
        """
        mode = mode if mode else 'hvg'
        show_n = (mode == 'hvg')
        show_list = (mode == 'list')

        for name in ('vk_hvg_n_label', 'vk_hvg_n_spin', 'vk_hvg_n_hint'):
            widget = self._widget(name)
            if self._is_window(widget):
                widget.setVisible(show_n)

        for name in ('vk_gene_list_label', 'vk_gene_list_combo',
                     'vk_gene_list_path_label', 'vk_gene_list_hint'):
            widget = self._widget(name)
            if self._is_window(widget):
                widget.setVisible(show_list)

        # N 不在 hvg 模式下时置灰（双保险：即使布局只隐藏父容器，控件也是禁用的）
        spin = self._widget('vk_hvg_n_spin')
        if self._is_window(spin):
            spin.setEnabled(show_n)

    # ================= 结果表 / 结果图 =================

    def show_table(self, table_widget, df, columns=None):
        """把 DataFrame 填进结果表（显著基因 / 全部基因）

        - `df` 为空 ⇒ 清空表；
        - 表头取 `columns`（给定）否则取 df 的列；
        - 配色取自当前主题 `get_mod_styles()`，只做着色，不写控件外观样式。
        """
        if not self._is_window(table_widget):
            return
        try:
            if df is None or len(df) == 0:
                table_widget.setRowCount(0)
                table_widget.setColumnCount(0)
                return

            # 容错：analysis 万一回传 list/dict，也先转成 DataFrame 再填
            if pd is not None and not hasattr(df, 'columns'):
                df = pd.DataFrame(df)

            styles = get_mod_styles()
            text_color = self._rgba(styles.get('sub_text_color', '#87CEEB'))
            fill_color = self._rgba(styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)'))
            fill_alt = self._rgba(styles.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)'))

            if columns:
                col_list = [c for c in columns if c in df.columns]
                if not col_list:
                    col_list = list(df.columns)
            else:
                col_list = list(df.columns)

            sub = df[col_list]
            table_widget.setRowCount(len(sub))
            table_widget.setColumnCount(len(col_list))
            table_widget.setHorizontalHeaderLabels([str(c) for c in col_list])

            for i, row in enumerate(sub.itertuples(index=False)):
                row_bg = fill_alt if (i % 2 == 0) else fill_color
                for j, val in enumerate(row):
                    if isinstance(val, float):
                        # p / FDR / distance 这类统计量统一 6 位有效数字，避免 0.000000 丢信息
                        val_str = "NA" if (pd is not None and pd.isna(val)) else f"{val:.6g}"
                    elif pd is not None and val is not None and not isinstance(val, (int, str, bool)) and pd.isna(val):
                        val_str = "NA"
                    else:
                        val_str = str(val)

                    item = QTableWidgetItem(val_str)
                    item.setForeground(text_color)
                    item.setBackground(row_bg)
                    table_widget.setItem(i, j, item)

            table_widget.resizeColumnsToContents()
            if hasattr(table_widget, 'horizontalHeader'):
                table_widget.horizontalHeader().setStretchLastSection(True)
        except Exception:
            traceback.print_exc()
            self.log(f"❌ 填充结果表失败: {traceback.format_exc()}")

    def show_image(self, image_label, png_path):
        """把生成的 PNG 显示到可缩放图片控件（照抄 violin func 的 ZoomableImageLabel 判定）"""
        if not self._is_window(image_label):
            return
        try:
            if not png_path or not os.path.exists(str(png_path)):
                self.log(f"❌ 图片不存在，无法显示: {png_path}")
                return
            pixmap = QPixmap(str(png_path))
            if pixmap.isNull():
                self.log(f"❌ 图片读取失败（QPixmap 为空）: {png_path}")
                return
            if isinstance(image_label, ZoomableImageLabel):
                image_label.set_pixmap(pixmap)
            elif hasattr(image_label, 'setPixmap'):
                image_label.setPixmap(pixmap.scaled(
                    image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.log("❌ 图片控件不支持 setPixmap/set_pixmap，无法显示")
        except Exception:
            traceback.print_exc()
            self.log(f"❌ 显示图片失败: {traceback.format_exc()}")

    # ================= 运行期辅助（进度解析） =================

    @staticmethod
    def parse_step_progress(line):
        """解析 R 端 `[VK] STEP|i|n|描述` ⇒ (i, n, 描述) 或 None

        说明书 §8.9：STEP 行是进度条的唯一依据。
        """
        if not line:
            return None
        match = re.search(r'\[VK\]\s*STEP\|(\d+)\|(\d+)\|(.*)', str(line))
        if not match:
            return None
        try:
            return int(match.group(1)), int(match.group(2)), match.group(3).strip()
        except Exception:
            traceback.print_exc()
            return None

    def update_progress_from_line(self, line):
        """按 `[VK] STEP|i|n|描述` 推进度条；返回是否命中 STEP 行"""
        parsed = self.parse_step_progress(line)
        if parsed is None:
            return False
        i, n, desc = parsed
        if n > 0:
            self.set_progress(int(100 * i / n))
        self.log(f"▶ 步骤 {i}/{n}：{desc}")
        return True

    def handle_vk_outdeg_line(self, line):
        """解析 `[VK] OUTDEG|gko=|edges=` ⇒ edges=0 时红字警告（说明书 §8.8）

        ★ 红字文案**逐字**照说明书 §8.8：「该基因在网络中没有出边，结果仅为数值噪声」
        （靶基因名已在同一行的日志里，不缺可读性；甲方要求消息逐字）。
        返回 True 表示该行是 OUTDEG 行（bind 不再按普通日志重复处理）。
        """
        if not line:
            return False
        match = re.search(r'\[VK\]\s*OUTDEG\|([^|]*)\|edges=(\d+)', str(line))
        if not match:
            return False
        gko = match.group(1)
        edges = int(match.group(2))
        gko_name = gko.split('=', 1)[1] if '=' in gko else gko
        if edges == 0:
            self.set_warning("该基因在网络中没有出边，结果仅为数值噪声")
            self.log(f"⚠ [VK] OUTDEG|{gko}|edges=0")
        else:
            self.log(f"靶基因 {gko_name} 出边数: {edges}")
        return True

    def warn_out_of_edges(self):
        """直接出「无出边」红字（供结构化 diagnostics 的 no_out_edges 使用，文案同上逐字）"""
        self.set_warning("该基因在网络中没有出边，结果仅为数值噪声")
