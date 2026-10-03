# -*- coding: utf-8 -*-
"""
空转「自定义气泡图」前端功能层（纯显示）—— 单细胞
`sc_targetgene_bubble_layer/ui_func_sc_targetgene_bubble.py`（74 行）的**功能 1:1 复刻**，
只把宿主从 `targetgene_bubble_ui` 改成本页布局对象 `self.ui`（与兄弟页
`ui_func_spatial_diff.py` 同款），控件名换成**本页的 `spatial_targetgene_bubble_*`**。

## 本文件**只做**（规格 §0 的 I1：func 层 = 纯显示/日志/弹窗）
    `set_combo_items` / `fill_list_widget` / `display_image` / `log` / `clear_log` /
    `alert_error` / `alert_failure` / `alert_success` / `get_save_file_path` /
    `get_export_size`。
    ⛔ 不绑信号、不读数据、不调 R、不写盘、不实现导出——那是 W2（bind）与 W3（analysis）。

## ⛔ 相对单细胞**有意不照抄**的地方
1. **不写任何模板机制**（单细胞自定义气泡页的 `ui_func` 本来就没有，本页同样不引入
   ——规格 §2.8 缺陷 1 明令两页都不建模板控件、不写模板方法）。
2. **空控件守卫一律 `if widget is None:`**，⛔ 不写 `if not widget:`
   —— 空 `QListWidget` / 空 `QComboBox` 的 `bool()` 是 `False`
   （规格 §2.8 缺陷 5 点名的陷阱）。
3. **控件名多候选兜底**：布局归 W1、本文件归 W3b，两者并行施工 ⇒ 同一个控件可能有几种
   合法落地名。与 W2 的 `ui_bind_spatial_targetgene_bubble._widget(*names)` **同一套口径**
   （绑定侧也这么探），两边一起容忍，才不会出现「控件建成了但数据路径不通」这种
   只在运行期暴露的错位。候选顺序 = 「§2.3 冻结名」→「单细胞同款（去前缀）」。
   全部候选都没有时**留痕**（不静默）。
   `log` / `clear_log` **必须覆写**并指向**本页**的日志控件（候选名见 `LOG_ATTRS`），
   **绝不**写别的页的日志控件（项目 D6 事故：日志打到别的页）。
"""

from script.utils_layer.import_config import *          # QPixmap / Qt / QFileDialog / traceback …
from script.utils_layer.gui_styles import ZoomableImageLabel
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong

# 留痕前缀（与本层其它页一致）
_LOG_PREFIX = "[spatial_targetgene_bubble_func]"


def _warn(msg):
    """留痕（本层纪律：不许静默）"""
    print("%s %s" % (_LOG_PREFIX, msg))
    try:
        sys.stdout.flush()
    except Exception as e:                      # pragma: no cover - 极端环境
        print("%s flush failed: %r" % (_LOG_PREFIX, e))


class SpatialTargetgeneBubbleFunc:
    """自定义气泡图前端功能类 —— 纯前端显示操作"""

    # 本页的控件前缀（属性名逐字取自规格 §2.3 的冻结表）
    P = "spatial_targetgene_bubble"
    # 图片标签候选名（见模块 docstring 第 3 条；顺序即优先级）
    IMAGE_LABEL_ATTRS = ("spatial_targetgene_bubble_plot_image_label",
                         "spatial_targetgene_bubble_bubble_image_label",
                         "spatial_targetgene_bubble_image_label")
    # ★ 日志控件候选名：本文件**自己覆写** `log`/`clear_log` 指到这里，
    #   与 W2 绑定侧 `_log_widget()` 探的名字**逐个对齐**（含 §2.3 的"双 bubble"公式名、
    #   与单细胞同款名）；布局用哪个都不会把日志打丢。
    LOG_ATTRS = ("spatial_targetgene_bubble_bubble_log",
                 "spatial_targetgene_bubble_log")

    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget

    # ---------- 控件探测（与 W2 的 `_widget(*names)` 同口径）----------

    def _widget(self, *names):
        """按顺序取第一个存在的控件（都没有 ⇒ `None`；守卫一律 `is None`）

        ★ 不能写成 `if not widget:` —— 空 `QListWidget` / 空 `QComboBox` 的 `bool()`
          是 `False`，那样写会把**空控件**误判成"不存在"（规格 §2.8 缺陷 5）。
        """
        for name in names:
            widget = getattr(self.ui, name, None)
            if widget is not None:
                return widget
        return None

    def log_widget(self):
        """本页日志控件（供 bind / 探针读同一个真相源；都没有 ⇒ `None`）"""
        return self._widget(*self.LOG_ATTRS)

    # ---------- 下拉框 / 列表内容更新 ----------

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全地设置下拉框内容，可选保持当前选中项（**逐字照抄**单细胞同名方法）

        ★ `blockSignals(True)` 保证**重算选项本身不会触发** `currentIndexChanged`
          （否则"样本变化 → 重填分组 → 触发分组变化 → 重算注释值"会绕圈）；
          `keep_selection=True` + `saved_text in items` 实现"仍在列表里就保持"。
        """
        if combo_widget is None:
            _warn("set_combo_items: 下拉框为 None ⇒ 跳过（不静默）")
            return
        saved_text = combo_widget.currentText() if keep_selection else ""
        combo_widget.blockSignals(True)
        try:
            combo_widget.clear()
            combo_widget.addItems(list(items or []))
            if saved_text and saved_text in (items or []):
                combo_widget.setCurrentText(saved_text)
        finally:
            combo_widget.blockSignals(False)

    def fill_list_widget(self, list_widget, items, select_all=True):
        """填充列表控件并可选全选（**逐字照抄**单细胞同名方法）

        ★ 守卫用 `is None`：空 `QListWidget` 的 `bool()` 是 `False`
          （规格 §2.8 缺陷 5），写成 `if not list_widget:` 会让空列表永远填不上。
        """
        if list_widget is None:
            _warn("fill_list_widget: 列表控件为 None ⇒ 跳过（不静默）")
            return
        list_widget.clear()
        list_widget.addItems(list(items or []))
        if select_all:
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)

    # ---------- 图片显示 ----------

    def _image_label(self):
        """取本页的图片标签（多候选；都拿不到 ⇒ 留痕返回 None）"""
        label = self._widget(*self.IMAGE_LABEL_ATTRS)
        if label is None:
            _warn("找不到图片标签（已试 %s）⇒ 出图结果无处可贴（需要 W1 提供布局）"
                  % "/".join(self.IMAGE_LABEL_ATTRS))
        return label

    def display_image(self, fig_path):
        """将图片贴到本页的图标签（`ZoomableImageLabel` 走 `set_pixmap` 以保留缩放/拖动）

        ★ 图片路径坏 / 标签缺失 ⇒ **留痕但不抛**（返回 False），
          免得把 W2 的绘制回调整个带崩。
        """
        label = self._image_label()
        if label is None:
            return False
        try:
            pixmap = QPixmap(str(fig_path))
            if pixmap.isNull():
                _warn("display_image: 图片读取失败：%s" % fig_path)
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
            _warn("display_image: 贴图异常：%s" % fig_path)
            return False

    # ---------- 日志（★ **必须**覆写并指向本页自己的控件）----------

    def log(self, message):
        """在**本页**日志框（`spatial_targetgene_bubble_bubble_log` 等候选名）追加一行并滚到底部

        ★ 覆写理由（项目 D6 事故）：若沿用别的页的 `log()`，日志会打到**别的页**的
          控件（或因为本页没有那个属性而**静默丢弃**）。拿不到本页控件时 `print` 兜底
          —— 宁可打到控制台，也绝不静默。
        """
        widget = self.log_widget()
        if widget is None:
            _warn("日志控件缺失（已试 %s）⇒ 本条日志打到控制台：%s"
                  % ("/".join(self.LOG_ATTRS), message))
            return
        try:
            widget.append(str(message))
            bar = widget.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.maximum())
        except Exception:
            traceback.print_exc()
            _warn("%s" % message)

    def clear_log(self):
        """清空**本页**日志框（覆写理由同 `log`）"""
        widget = self.log_widget()
        if widget is None:
            _warn("日志控件缺失（已试 %s）⇒ clear_log 无处可清" % "/".join(self.LOG_ATTRS))
            return
        try:
            widget.clear()
        except Exception:
            traceback.print_exc()

    # ---------- 导出尺寸 ----------

    def get_export_size(self):
        """读导出宽高（英寸）：`spatial_targetgene_bubble_export_width` / `..._export_height`

        ★ 与单细胞不同：单细胞气泡页**没有**这个方法（导出尺寸写死），
          而空转两页的控件表（规格 §2.3）冻结了 `P_export_width` / `P_export_height`
          两个 spinbox ⇒ W2 的导出编排要读它们，故本页提供（拿不到就 `(None, None)`）。
        """
        width = None
        height = None
        widget = self._widget('%s_export_width' % self.P)
        if widget is not None:
            try:
                width = float(widget.value())
            except (TypeError, ValueError):
                traceback.print_exc()
                width = None
        widget = self._widget('%s_export_height' % self.P)
        if widget is not None:
            try:
                height = float(widget.value())
            except (TypeError, ValueError):
                traceback.print_exc()
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


__all__ = ['SpatialTargetgeneBubbleFunc']
