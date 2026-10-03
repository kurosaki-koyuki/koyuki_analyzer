# -*- coding: utf-8 -*-
"""空转「表达量分析」子页面的 func 层 —— 2026-09-20 从 `ui_func_spatial_initial.py` 拆出

## 为什么是**子类**
  基因专属的 6 个方法（`set_gene_status` / `gene_log` / `clear_gene_results` /
  `add_gene_result` / `gene_input_text` / `set_gene_busy`）搬到本文件；
  **共享 helper（log / 样本条目 / 图位 / 空状态 / 未审提示…）留在 `SpatialInitialFunc`
  原处**，由本类**继承**拿到 —— 符合"共享 helper 留在原处被两边 import"的要求，
  也避免把那些方法复制成两份（复制会让以后改一处漏一处）。
"""

import os
import traceback

from script.utils_layer.import_config import *
# ★★ 必须**显式** import（**不要**图省事写 `from ... import *`：那会让"缺名字"更难查）：
#   `add_gene_result()` 里用到 `create_styled_image_tab` / `create_styled_label` /
#   `Qt` / `os`，而拆页时**只搬了方法、忘了搬这几个名字** ⇒ 一进去就 `NameError`，
#   又被方法内的裸 `except` 吞掉 ⇒ **静默返回 False、一个页签都不加**
#   （用户真跑完基因图会看到"结果页永远空白"，日志里连线索都没有）。
#   本会话同类坑第 N 次："语法闸门过 ≠ 运行期有名字"，故这里逐个写清来源。
from PyQt5.QtCore import Qt
from script.utils_layer.gui_styles import (
    create_styled_image_tab, create_styled_label, ZoomableImageLabel)
# ★ 提示气泡（`alert_*` 用）与单细胞 `ui_func_violin.py` 同一套：
#   本页原来是靠父类 import 带进来的，但这里**显式**再写明来源（缺名字好查）。
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong

from script.analyzer_layer.spatial_layer.spatial_initial_layer.ui_func_spatial_initial import (
    SpatialInitialFunc)


class SpatialExpressionFunc(SpatialInitialFunc):
    """表达量分析页的 func：共享 helper 全部继承，只多这 6 个基因专属方法

    ★ v5（2026-09-23，W1 新增）：本类**再追加**一组小提琴图的**纯显示层** helper
      （`set_combo_items`/`fill_list_widget`/`update_main_list`/`update_filter1_list`/
       `update_filter2_list`/`_update_pairwise_list`/`display_violin_image`/`violin_log`/
       `get_export_size`/`get_save_file_path`/`alert_error`/`alert_failure`/`alert_success`），
      实现照抄单细胞 `violin_layer/ui_func_violin.py`，只把控件来源改成本页 `self.ui.violin_*`；
      上面 6 个基因方法**一个字都没动**。
    """

    # ------------------------------------------------------------------
    # ★★ 日志：**必须覆写父类**（父类写的是 `initial_log_text`，本页没有那个控件）
    # ------------------------------------------------------------------
    # 事故（协调者跨页依赖扫描抓到，离屏决定性复现）：
    #   `SpatialExpressionFunc` 继承父类的 `log()` ⇒ 它写
    #   `getattr(self.ui,'initial_log_text',None)` ⇒ 表达页该控件**不存在**
    #   ⇒ 拿到 None 就 `return` ⇒ **本页所有日志静默丢弃**（"绘制中/取数失败/导出结果"
    #   这些反馈全没了，日志框永远空白），而且**任何一道静态闸门都看不出来**。
    # ⇒ 覆写 `log()` / `clear_log()`，目标控件改为本页自己的 `gene_log_text`；
    #   拿不到就 `print` 兜底（宁可打到控制台，也**绝不静默**）。
    #   `gene_log()` 与 `log()` 语义**完全一致**（同一个控件）—— 历史调用点两处名字都有，
    #   不必区分，谁调都一样。
    def log(self, message):
        """在**本页**日志框（`gene_log_text`）追加一行（覆写父类，见上面的说明）"""
        widget = getattr(self.ui, 'gene_log_text', None)
        if widget is None:
            print("[SpatialExpression] %s" % message)
            return
        try:
            widget.append(str(message))
            bar = widget.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.maximum())
        except Exception:
            print("[SpatialExpression] %s" % message)

    def clear_log(self):
        """清空**本页**日志框（覆写父类；父类清的是 `initial_log_text`）"""
        widget = getattr(self.ui, 'gene_log_text', None)
        if widget is None:
            return
        try:
            widget.clear()
        except Exception:
            pass

    def set_gene_status(self, text):
        """写「基因状态/成本提示」标签"""
        label = getattr(self.ui, 'gene_status_label', None)
        if label is not None:
            label.setText(str(text) if text else "")

    def gene_log(self, msg):
        """向基因日志框追加一行（并滚到底部）"""
        widget = getattr(self.ui, 'gene_log_text', None)
        if widget is None:
            return
        try:
            widget.append(str(msg))
            bar = widget.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.maximum())
        except Exception:
            pass

    def clear_gene_results(self):
        """清空基因结果页签 —— ★ **页签条保持常驻可见**，并让空提示回来。

        ★ 本方法在真实路径上很关键：W2 的 bind **每次点「绘制表达量图」都会先调它**
          （`ui_bind_spatial_initial.py:1295-1303`）。所以这里**绝不能** `setVisible(False)` ——
          否则一旦这次绘制失败/超时/没出图，右列会整个塌掉：图没了、连空提示也没有
          （正是用户第三轮要消灭的"下方弹出来/不美观"现象）。
          历史事故：这里曾残留一句 `tabs.setVisible(False)`，静态检查与"构造后可见"都测不出来，
          只有**真调一次本方法**才暴露 —— 故本方法必须保持"只清内容、不动显隐"。
        """
        tabs = getattr(self.ui, 'gene_result_tabs', None)
        if tabs is not None:
            try:
                tabs.clear()
            except Exception:
                # ★ 不静默（照仓库纪律）：清失败要看得见，但仍然不往外抛
                #   （本方法在"点绘制"路径上被调用，抛出去会把整个回调带崩）
                traceback.print_exc()
        # 空提示回来（容错：拿不到就跳过）
        hint = getattr(self.ui, 'gene_result_empty_hint', None)
        if hint is not None:
            try:
                hint.setVisible(True)
            except Exception:
                pass

    def add_gene_result(self, title, image_path):
        """新增一个基因结果页签，并在其中放一张图。

        Args:
            title: 页签标题（例如 "EGFR 空间表达"）
            image_path: 图片路径（不存在/损坏则只显示提示，不抛）
        Returns:
            bool: 是否成功贴上图
        ★ 容错：页签容器缺失 / 路径不存在 / 图片损坏一律不抛。
        """
        tabs = getattr(self.ui, 'gene_result_tabs', None)
        if tabs is None:
            return False
        image_label = None
        try:
            # ★ 老样式（用户第 4 轮实测要求）：结果页也走 `create_styled_image_tab`
            #   —— 与 24 图集页签同一个"老样式图片页"真相源；它内部已 `addTab`。
            page, image_label = create_styled_image_tab(
                tabs, str(title), default_text="该图尚未生成")
            image_label.setAlignment(Qt.AlignCenter)

            note_label = create_styled_label(str(title), font_size=10, bold=False, parent=page)
            note_label.setAlignment(Qt.AlignCenter)
            page.layout().addWidget(note_label)

            tabs.setVisible(True)          # 无害（它本就常驻），但保持幂等
            tabs.setCurrentIndex(tabs.count() - 1)
        except Exception:
            # ★★ **不许静默**（本会话纪律）：这里原来只有 `return False`，
            #   于是"少了导入名"这种致命问题被完全吞掉、页签一个都不加而日志空白。
            #   仍然**不往外抛**（R 出图失败时把整个回调带崩更糟），但必须留痕。
            traceback.print_exc()
            return False
        # ★ 有图了 → 空提示必须让位（容错：拿不到就跳过）
        hint = getattr(self.ui, 'gene_result_empty_hint', None)
        if hint is not None:
            try:
                hint.setVisible(False)
            except Exception:
                pass
        if image_label is None:
            return False

        path = str(image_path) if image_path else ""
        if not path or not os.path.exists(path):
            image_label.setText("该图尚未生成")
            return False
        # ★ 一律全分辨率（用户实测：基因图同样糊）；ZoomableImageLabel 会自行缩小适配
        pixmap = self.decode_full(path)
        if pixmap is None:
            image_label.setText("图片读取失败")
            return False
        image_label.set_pixmap(pixmap)
        return True

    def gene_input_text(self):
        """取基因输入框全文（★ 只读控件，不做任何解析/校验）"""
        widget = getattr(self.ui, 'gene_input', None)
        if widget is None:
            return ""
        try:
            return widget.toPlainText()
        except Exception:
            return ""

    def set_gene_busy(self, busy):
        """运行期间禁用/恢复「绘制表达量图」（+ 输入框）"""
        flag = not bool(busy)
        for name in ('btn_draw_expression', 'gene_input'):
            widget = getattr(self.ui, name, None)
            if widget is not None:
                try:
                    widget.setEnabled(flag)
                except Exception:
                    pass

    # ==================================================================
    # 小提琴图（§3）的**纯显示层 helper** —— 2026-09-23 W1 新增
    #   来源：单细胞 `scRNAseq_layer/violin_layer/ui_func_violin.py` 的对应实现，
    #   只把 `self.violin_ui.violin_*` 改成**本页控件** `self.ui.violin_*`。
    #   ★ 与上面 6 个基因方法**同层**：只 setText/setPixmap/填列表，不读数据、
    #     不调 R、不写盘；真正的取数/出图/导出归 W2（bind）与 W3（analysis）。
    # ==================================================================
    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全地设置下拉框内容，可选保持当前选中项（照抄单细胞同名方法）"""
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        combo_widget.clear()
        combo_widget.addItems(items)
        if saved_text and saved_text in items:
            combo_widget.setCurrentText(saved_text)
        combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        """填充列表控件并可选全选（照抄单细胞同名方法）"""
        list_widget.clear()
        list_widget.addItems(items)
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    def update_main_list(self, group, vals):
        """更新「主注释（分组）」列表，并同步重建组间两两比较列表"""
        self.fill_list_widget(self.ui.violin_main_list, vals)
        self._update_pairwise_list(vals)

    def update_filter1_list(self, group, vals):
        """更新筛选1的组别列表"""
        widget = getattr(self.ui, 'violin_filter1_list', None)
        if widget is not None:
            self.fill_list_widget(widget, vals)

    def update_filter2_list(self, group, vals):
        """更新筛选2的组别列表"""
        widget = getattr(self.ui, 'violin_filter2_list', None)
        if widget is not None:
            self.fill_list_widget(widget, vals)

    def _update_pairwise_list(self, unique_vals):
        """重建「组间比较」列表

        语义（§3.2/§7 冻结）：把**当前主注释分组**的所有组**两两组合**，
        生成 `"A vs B"` 字符串；组数 < 2 时列表为空（`itertools.combinations`
        天然给出空序列）。生成后默认全选。
        """
        widget = getattr(self.ui, 'violin_pairwise_list', None)
        if widget is None:
            return
        pairs = list(itertools.combinations(list(unique_vals), 2))
        widget.clear()
        for pair in pairs:
            widget.addItem("%s vs %s" % (pair[0], pair[1]))
        for i in range(widget.count()):
            widget.item(i).setSelected(True)

    def display_violin_image(self, fig_path, fig_type='violin_box'):
        """把小提琴结果图贴到对应页签（`violin_box`/`box`/`violin` 三选一）

        ★ `label_map` 的键与单细胞 `ui_func_violin.display_image` **逐字一致**
          （`violin_box` → `violin_box_label`、`box` → `violin_box_only_label`、
           `violin` → `violin_only_label`）；
          `ZoomableImageLabel` 走 `set_pixmap`（保留滚轮缩放/拖动），否则退回缩放 setPixmap。
        ★ 图片路径坏 / 页签缺失 → **留痕但不抛**（返回 False），
          免得把 W2 的绘制回调整个带崩。
        """
        try:
            label_map = {
                'violin_box': getattr(self.ui, 'violin_box_label', None),
                'box': getattr(self.ui, 'violin_box_only_label', None),
                'violin': getattr(self.ui, 'violin_only_label', None),
            }
            label = label_map.get(fig_type)
            if label is None:
                print("[SpatialViolin] 找不到页签控件: fig_type=%s" % fig_type)
                return False
            pixmap = QPixmap(str(fig_path))
            if pixmap.isNull():
                print("[SpatialViolin] 图片读取失败: %s" % fig_path)
                return False
            if isinstance(label, ZoomableImageLabel):
                label.set_pixmap(pixmap)
            else:
                label.setPixmap(pixmap.scaled(
                    label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            return True
        except Exception:
            # ★ 不静默（仓库纪律）：贴图失败要看得见，但不往外抛
            traceback.print_exc()
            return False

    def violin_log(self, message):
        """向小提琴日志框追加一行（并滚到底部）

        ★ 与 `gene_log()` 同语义，只是目标控件是本页新增的 `violin_log`
          （同名属性是 QTextEdit；本方法是 func 上的方法，互不冲突）。
        """
        widget = getattr(self.ui, 'violin_log', None)
        if widget is None:
            print("[SpatialViolin] %s" % message)
            return
        try:
            widget.append(str(message))
            bar = widget.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.maximum())
        except Exception:
            traceback.print_exc()
            print("[SpatialViolin] %s" % message)

    def get_export_size(self):
        """读导出宽高（英寸）：`violin_export_width` / `violin_export_height`"""
        width = None
        height = None

        widget = getattr(self.ui, 'violin_export_width', None)
        if widget is not None:
            try:
                width = float(widget.value())
            except (TypeError, ValueError):
                width = None

        widget = getattr(self.ui, 'violin_export_height', None)
        if widget is not None:
            try:
                height = float(widget.value())
            except (TypeError, ValueError):
                height = None

        return width, height

    # ---------- 前端提示信息（照抄单细胞同名方法）----------

    def alert_error(self, message):
        """显示错误提示"""
        if self.parent_widget:
            attention(self.parent_widget, str(message))

    def alert_failure(self, message):
        """显示失败提示"""
        if self.parent_widget:
            wrong(self.parent_widget, str(message))

    def alert_success(self, message):
        """显示成功提示"""
        if self.parent_widget:
            happy(self.parent_widget, str(message))

    # ---------- 文件对话框（照抄单细胞同名方法）----------

    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框，返回用户选择的路径（取消则空串）"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""


__all__ = ['SpatialExpressionFunc']
