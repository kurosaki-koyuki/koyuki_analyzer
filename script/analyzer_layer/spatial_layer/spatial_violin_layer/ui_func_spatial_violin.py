# -*- coding: utf-8 -*-
"""空转「小提琴图」页面 func 层 —— v11（`_d_spec_v11_split_and_bubble.md` §1.2-C）

## 由来（整块搬移 + 一处必需的覆写）
本文件的小提琴**纯显示层** helper（`set_combo_items` / `fill_list_widget` /
`update_main_list` / `update_filter1_list` / `update_filter2_list` /
`_update_pairwise_list` / `display_violin_image` / `violin_log` / `get_export_size` /
`get_save_file_path` / `alert_error` / `alert_failure` / `alert_success` /
`update_styles` / `update_background` / 样本列 5 件）**逐字搬自**
`spatial_expression_layer/ui_func_spatial_expression.py:208-360`，
控件来源仍是 `self.ui.violin_*`（新页布局同名同形）⇒ 迁移**零语义改动**。

## ★★ 本类**必须**覆写 `log` / `clear_log`（D6 事故，§1.2-C 明令）
   父链的目标控件是**别的页的**日志框：
     · `SpatialExpressionFunc.log`   → `gene_log_text`（表达页的基因日志，本页没有）
     · `SpatialInitialFunc.log`      → `initial_log_text`（总览页的日志，本页也没有）
   ⇒ 若本类不覆写，`bind._log()` 的每一行都会**静默丢弃**（拿不到控件就 `return`），
     用户盯着的 `violin_log` 永远空白，而任何静态闸门都看不出来
     （这正是 D6 事故的形状）。所以这里把 `log` / `clear_log` **明确指向
     `violin_log`**，拿不到就 `print` 兜底（宁可打到控制台，也**绝不静默**）。

## 继承关系（为什么仍继承 `SpatialExpressionFunc`）
   样本列 5 件的显示实现（`sample_item_text` / `set_sample_items` /
   `get_selected_sample_ids` / `set_selected_count` / `refresh_selected_count`）、
   图片解码（`decode_full`）都在 `SpatialInitialFunc` 这一支上；
   `SpatialExpressionFunc` 又在其上加了一层日志覆写。
   本页**只多一层日志覆写**，不重写任何共享 helper（I6：一处实现，别抄两份）。
"""

import traceback

from script.utils_layer.import_config import *
# ★ 显式 import（不依赖 `import_config` 的通配导出清单 —— 本会话已多次踩这个坑）：
#   · `Qt`                  —— 贴图缩放常量
#   · `ZoomableImageLabel`  —— 三页签 label 的身份判定（`display_violin_image` 用）
#   · `itertools`           —— `_update_pairwise_list` 的两两组合
#   · `QFileDialog`         —— 保存对话框（走 import_config 的导出清单，这里不重复 import）
import itertools
from PyQt5.QtCore import Qt
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong

from script.analyzer_layer.spatial_layer.spatial_expression_layer.ui_func_spatial_expression import (
    SpatialExpressionFunc)


class SpatialViolinFunc(SpatialExpressionFunc):
    """「小提琴图」页面的 func：小提琴显示层 helper + **本页自己的日志控件**"""

    # ------------------------------------------------------------------
    # ★★ 日志：**必须覆写**父链（父链写的是 `gene_log_text` → `initial_log_text`，
    #    本页两个控件都没有 ⇒ 不覆写就整页日志静默丢失，见文件头 D6 说明）
    # ------------------------------------------------------------------
    def log(self, message):
        """在**本页**日志框（`violin_log`）追加一行（覆写父链，见文件头）"""
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
            # ★ 不静默（仓库纪律）：写不进去要看得见，但仍不往外抛
            traceback.print_exc()
            print("[SpatialViolin] %s" % message)

    def clear_log(self):
        """清空**本页**日志框（覆写父链；父链清的是别的页的控件）"""
        widget = getattr(self.ui, 'violin_log', None)
        if widget is None:
            return
        try:
            widget.clear()
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 小提琴图的**纯显示层 helper**（逐字搬自表达页 func `:208-360`）
    #   只 setText/setPixmap/填列表，不读数据、不调 R、不写盘；
    #   真正的取数/出图/导出归 bind 与 analysis。
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

        语义（冻结）：把**当前主注释分组**的所有组**两两组合**，
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
          免得把 bind 的绘制回调整个带崩。
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

        ★ 与 `log()` 语义**完全一致**（同一个控件 `violin_log`）——
          历史调用点两个名字都有（bind 走 `log`，小提琴编排走 `violin_log`），
          不必区分，谁调都一样。
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


__all__ = ['SpatialViolinFunc']
