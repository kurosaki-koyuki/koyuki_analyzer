# -*- coding: utf-8 -*-
"""
空转初步分析页面前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑

★ 硬约束：本文件不读数据、不扫目录；所有数据由 bind 传入。
   全部方法**容错**：None / 非 dict / 缺键都不得抛异常。
   ★ 本层**不建任何控件**，只做 setText / setPixmap / setVisible / setTabVisible。
"""

from script.utils_layer.import_config import *
# ★ 必须显式 import：QImageReader 不在 import_config 的导出清单里
#   （该文件 QtGui 只导出 QFont/QPixmap/QIcon/QImage/QColor/QKeySequence/QPainter/QBrush/QPen）
#   这是本会话第 3 次同类坑（前两次：QPolygonF 导致无 traceback 的进程级崩溃）。
from PyQt5.QtGui import QImageReader
from script.utils_layer.gui_styles import (
    create_zoomable_image_label, create_styled_label, create_styled_image_tab)
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class SpatialInitialFunc:
    """初步分析页面前端功能类 - 纯前端显示操作"""

    # 缩略图边长（按需解码，不展开全尺寸）
    THUMB_SIZE = 320
    # 星级渲染上限（与审查页一致：5 星制）
    MAX_STARS = 5
    # "看大图"同时只保留 1 张全尺寸 QPixmap（最大单张约 96 MB，可接受）
    LARGE_KEEP = 1

    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget
        self._large_kept = []      # 最近用过的全尺寸 pixmap（LRU，只留 LARGE_KEEP 张）

    # ------------------------------------------------------------------
    # 样式 / 背景
    # ------------------------------------------------------------------
    def update_styles(self):
        """更新界面样式"""
        if hasattr(self.ui, 'update_styles'):
            self.ui.update_styles()

    def update_background(self):
        """更新背景图"""
        if hasattr(self.ui, 'update_background'):
            self.ui.update_background()

    # ------------------------------------------------------------------
    # 日志（M1 的 ui_func_spatial_top 没有 log，本页自带一个）
    # ------------------------------------------------------------------
    def log(self, message):
        """在状态框里追加一行（只写控件，不读数据）"""
        widget = getattr(self.ui, 'initial_log_text', None)
        if widget is None:
            return
        try:
            widget.append(str(message))
            bar = widget.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.maximum())
        except Exception:
            pass

    def clear_log(self):
        """清空日志框"""
        widget = getattr(self.ui, 'initial_log_text', None)
        if widget is not None:
            try:
                widget.clear()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 样本多选列表
    # ------------------------------------------------------------------
    def _stars_text(self, total):
        """把样本总分渲染成**固定 5 个字符**的星串：实心 = total、空心 = 5−total。

        例：total=4 → `★★★★☆`；total=0 → `☆☆☆☆☆`（或未审时不显示星串）。
        ★ 容错：total 非数字 / 越界一律夹到 0..MAX_STARS。
        """
        try:
            n = int(total or 0)
        except (TypeError, ValueError):
            n = 0
        n = max(0, min(self.MAX_STARS, n))
        return "★" * n + "☆" * (self.MAX_STARS - n)

    def sample_item_text(self, sample_id, label="", reviewed=False, total=0):
        """**列表项文本的唯一生成处**（★ 别在 bind 里再写一份，本会话已因"两处各写一份"出过 bug）

        格式（与审查页 `ui_bind_spatial_review._item_text` 同形）：
            未审：`⚠未审  <样本号> <标签>`
            已审：`★★★★☆  <样本号> <标签>`      （星串固定 5 字符）

        ★ 防重复：manifest 的 label 形如 `"GSM7596587 / mgh258"` 时**自带样本号**，
          若无条件 `"%s %s" % (sid, label)` 会变成 `GSM7596587 GSM7596587 / mgh258`
          （审查 bind 的注释里记着这个真实 bug）。故 label 已含 sid 时不再前置 sid。
        """
        sid = str(sample_id or "").strip()
        lab = str(label or "").strip()
        if lab and sid and sid in lab:
            body = lab                       # label 已含样本号 → 不重复
        elif lab:
            body = ("%s %s" % (sid, lab)).strip()
        else:
            body = sid
        if not reviewed:
            return "⚠未审  " + body
        return "%s  %s" % (self._stars_text(total), body)

    def set_sample_items(self, samples, selected_ids=None):
        """填充样本多选列表。

        Args:
            samples: list[dict]，每项至少含 'id'；可选 'label' / 'reviewed'(bool) / 'total'(int)
            selected_ids: 需要置为已选的样本 id 集合（默认空 = ★ 默认全不选，契约 Q2）
        ★ 容错：None / 非 list / 元素非 dict 一律忽略，不抛异常。
        """
        widget = getattr(self.ui, 'sample_list', None)
        if widget is None:
            return
        try:
            widget.clear()
        except Exception:
            return
        items = samples if isinstance(samples, (list, tuple)) else []
        chosen = set()
        if isinstance(selected_ids, (list, tuple, set)):
            chosen = {str(x) for x in selected_ids}
        added = 0
        for entry in items:
            if not isinstance(entry, dict):
                continue
            sample_id = str(entry.get('id', '')) or "（未知样本）"
            label = str(entry.get('label', '') or '')
            is_reviewed = bool(entry.get('reviewed', False))
            total = entry.get('total', 0)
            # ★ 文本走唯一生成处（① 星标：此前声明了 total 却从未渲染）
            text = self.sample_item_text(sample_id, label, is_reviewed, total)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, sample_id)
            if not is_reviewed and hasattr(self.ui, '_empty_color'):
                item.setForeground(self.ui._empty_color)
            widget.addItem(item)
            if sample_id in chosen:
                item.setSelected(True)
            added += 1
        self.set_selected_count(widget.selectedItems() if added else [], added)

    def get_selected_sample_ids(self):
        """读取当前选中的样本 id 列表（★ 只读控件，不查分）"""
        widget = getattr(self.ui, 'sample_list', None)
        if widget is None:
            return []
        try:
            return [it.data(Qt.UserRole) for it in widget.selectedItems()]
        except Exception:
            return []

    def set_selected_count(self, selected_items, total=None):
        """更新「已选 N / M」计数"""
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
        label.setText("已选 %d / %d" % (selected, total))

    def refresh_selected_count(self):
        """按当前控件状态刷新计数（供 bind 在选中变化后调用）"""
        widget = getattr(self.ui, 'sample_list', None)
        if widget is None:
            return
        try:
            self.set_selected_count(widget.selectedItems(), widget.count())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 图片解码（★ 网格项一律缩略图；全尺寸只允许"看大图"那一处，且同时只留 1 张）
    # ------------------------------------------------------------------
    def decode_thumbnail(self, path, box=None):
        """用 QImageReader.setScaledSize 做**按需缩放解码**，不展开全尺寸。

        Returns: QPixmap 或 None
        ★ 容错：路径不存在 / 读失败 / 损坏一律返回 None，不抛异常。
        """
        target = box if box else QSize(self.THUMB_SIZE, self.THUMB_SIZE)
        path = str(path) if path else ""
        if not path or not os.path.exists(path):
            return None
        try:
            reader = QImageReader(path)
            reader.setAutoTransform(True)
            size = reader.size()                      # 只读头部，不解码像素
            if size.isValid() and size.width() > 0 and size.height() > 0:
                scaled = QSize(size)
                scaled.scale(target, Qt.KeepAspectRatio)
                reader.setScaledSize(scaled)
            image = reader.read()
            if image is None or image.isNull():
                return None
            return QPixmap.fromImage(image)
        except Exception:
            return None

    def decode_full(self, path):
        """全尺寸解码（**只用于"看大图"**；结果按 LRU 只保留 LARGE_KEEP 张）"""
        path = str(path) if path else ""
        if not path or not os.path.exists(path):
            return None
        # 命中缓存
        for kept_path, kept_pixmap in self._large_kept:
            if kept_path == path:
                return kept_pixmap
        try:
            pixmap = QPixmap(path)
        except Exception:
            return None
        if pixmap.isNull():
            return None
        self._large_kept.append((path, pixmap))
        while len(self._large_kept) > self.LARGE_KEEP:
            self._large_kept.pop(0)
        return pixmap

    # ------------------------------------------------------------------
    # 图集显示（布局期已建好图位；本层只填图/显隐）
    # ------------------------------------------------------------------
    def show_figure(self, figure_type, image_path, thumbnail=None):
        """把某图型的图片填进对应图位（只 setPixmap/setText，不建控件）。

        ★ 一律**全分辨率解码**（用户第二轮实测：「都是非常模糊的小图，字都看不清」）。
          原因：`ZoomableImageLabel.reset_view` 的 `scale_factor = min(..., 1.0)` **封顶 1.0、不放大**，
          所以 320px 的缩略图只会以 320px 画在 ~1372px 的区域里 → 又小又糊。
          全分辨率下 `scale_factor < 1.0`（自动缩小适配），图填满区域且滚轮放大用的是真实像素。
        ★ `thumbnail` 参数**保留但已弃用**（W2 传 `thumbnail=True` 也照样全分辨率）——
          为的是**不改 bind 一行**。`decode_thumbnail` 仍保留给将来真正的小预览用，本页不再调用。

        Args:
            figure_type: 图型 id
            image_path: 图片路径
            thumbnail: 已弃用（忽略；兼容旧调用）
        ★ 容错：图位未建 / 路径不存在 / 图片损坏都只提示，不抛异常。
        """
        view = self._view_of(figure_type)
        if view is None:
            return False
        if not image_path or not os.path.exists(str(image_path)):
            view.set_pixmap(None)
            view.setText("该图尚未生成")
            return False
        pixmap = self.decode_full(image_path)
        if pixmap is None:
            view.set_pixmap(None)
            view.setText("图片读取失败")
            return False
        view.set_pixmap(pixmap)
        return True

    def clear_slot(self, figure_type):
        """清空某个图位的图片（释放其 QPixmap 引用）"""
        view = self._view_of(figure_type)
        if view is not None:
            view.set_pixmap(None)

    def release_other_figures(self, keep_figure_type):
        """释放除 `keep_figure_type` 之外**已加载**的全尺寸 pixmap（把常驻张数压到 1 张）。

        ⚠ **故意不自动调用**（不在 show_figure 里自动触发），原因见下 —— 这是本轮的实测结论：
            W2 的 bind 用 `_decoded_types` 做缓存（`ui_bind_spatial_initial.py:725-729`）：
                already = ft in self._decoded_types
                if already and (not is_ps or was_repr == cur_repr):
                    return          # ← 直接跳过，不重填
            所以**由本层静默清掉某页的 pixmap 后，切回该页时 bind 会跳过重填 → 出现空白页**。
            ⇒ 正确做法是**由 bind 在切页签时调用本方法，并把被清的那个 ft 从 `_decoded_types` 移除**。
            需要 W2 加的一行（在 `_on_tab_changed` / `_decode_index` 里）：
                self.func.release_other_figures(ft)
                self._decoded_types.discard(<被释放的那个 ft>)
            —— 我没有替他改（文件所有权），故本方法先备好并自测。

        Args:
            keep_figure_type: 要保留的图型 id（其余全部释放）
        Returns:
            int: 实际释放的张数
        """
        views = getattr(self.ui, 'figure_views', None)
        if not isinstance(views, dict):
            return 0
        keep = str(keep_figure_type)
        released = 0
        for ft, label in views.items():
            if str(ft) == keep or label is None:
                continue
            try:
                if getattr(label, '_original_pixmap', None) is not None:
                    label.set_pixmap(None)
                    released += 1
            except Exception:
                continue
        return released

    def _view_of(self, figure_type):
        """按 figure_type 取图控件（平铺一层：figure_views[figure_type]）"""
        views = getattr(self.ui, 'figure_views', None)
        if not isinstance(views, dict):
            return None
        return views.get(str(figure_type))

    def _note_of(self, figure_type):
        """按 figure_type 取说明标签（平铺一层：figure_notes[figure_type]）"""
        notes = getattr(self.ui, 'figure_notes', None)
        if not isinstance(notes, dict):
            return None
        return notes.get(str(figure_type))

    def _tab_index_of(self, figure_type):
        """按 figure_type 取页签索引（顺序真相源 = figure_type_order）"""
        order = getattr(self.ui, 'figure_type_order', None)
        if not isinstance(order, (list, tuple)):
            return -1
        key = str(figure_type)
        try:
            return list(order).index(key)
        except ValueError:
            return -1

    def set_slot_visible(self, figure_type, visible):
        """显隐某个图型（连它的说明标签 + 它的页签一起）

        ★ 隐藏页签用 `setTabVisible(False)`：该页**不参与折行排布**（不留空洞）。
        """
        view = self._view_of(figure_type)
        if view is not None:
            view.setVisible(bool(visible))
        note = self._note_of(figure_type)
        if note is not None:
            note.setVisible(bool(visible))
        tabs = getattr(self.ui, 'initial_tabs', None)
        idx = self._tab_index_of(figure_type)
        if tabs is not None and idx >= 0:
            try:
                tabs.setTabVisible(idx, bool(visible))
            except Exception:
                pass

    def set_slot_note(self, figure_type, text):
        """更新某图型的说明文字"""
        note = self._note_of(figure_type)
        if note is not None:
            note.setText(str(text) if text else "")

    def verify_figure_types(self, figure_types):
        """比对数据里的图型与布局里已建好的页签；只报差异，不建控件。

        Args:
            figure_types: list[str]（来自 bind 读到的图集清单），可为 None
        Returns:
            (matched: bool, extra: list, missing: list)
              extra   = 数据里有、但布局页签里没有的（图集新增了类型 → 由 bind 打日志）
              missing = 布局页签里有、但数据里没有的（该图型本次未产出 → 隐藏页签）
        ★ 容错：None / 非 list 一律当空清单。
        """
        order = getattr(self.ui, 'figure_type_order', None)
        known = [str(t) for t in order] if isinstance(order, (list, tuple)) else []
        if not figure_types or not isinstance(figure_types, (list, tuple)):
            given = []
        else:
            given = [str(t) for t in figure_types]
        extra = [t for t in given if t not in known]
        missing = [t for t in known if t not in given]
        matched = (not extra) and (not missing)

        # 未产出的图型：隐藏其页签（不删控件，避免索引错位）
        for figure_type in missing:
            self.set_slot_visible(figure_type, False)
        for figure_type in given:
            if figure_type in known:
                self.set_slot_visible(figure_type, True)
        return matched, extra, missing

    def set_tab_visible(self, figure_type, visible):
        """按 figure_type 显隐页签（等价于 set_slot_visible 的页签部分）"""
        tabs = getattr(self.ui, 'initial_tabs', None)
        idx = self._tab_index_of(figure_type)
        if tabs is None or idx < 0:
            return
        try:
            tabs.setTabVisible(idx, bool(visible))
        except Exception:
            pass

    def show_empty_state(self, message="尚未载入图集，请先在主页「加载数据」后再运行出图。"):
        """显示空状态提示"""
        label = getattr(self.ui, 'initial_empty_hint', None)
        if label is not None:
            label.setText(message)
            label.setVisible(True)

    def hide_empty_state(self):
        """隐藏空状态提示"""
        label = getattr(self.ui, 'initial_empty_hint', None)
        if label is not None:
            label.setVisible(False)

    # ------------------------------------------------------------------
    # 未审样本提示条（软阻断：提示但不禁止使用）
    # ------------------------------------------------------------------
    def show_unreviewed_notice(self, sample_ids=None, text=None):
        """显示未审样本提示（不禁止继续使用）"""
        panel = getattr(self.ui, 'unreviewed_notice_panel', None)
        label = getattr(self.ui, 'unreviewed_notice_label', None)
        if label is not None:
            if text:
                label.setText(str(text))
            else:
                ids = [str(x) for x in (sample_ids or [])]
                label.setText("⚠ 本次选择的样本中有 %d 个尚未审查：%s"
                              % (len(ids), "、".join(ids) if ids else "—"))
        if panel is not None:
            panel.setVisible(True)

    def hide_unreviewed_notice(self):
        """隐藏未审样本提示"""
        panel = getattr(self.ui, 'unreviewed_notice_panel', None)
        if panel is not None:
            panel.setVisible(False)

    # ------------------------------------------------------------------
    # 按需基因表达量图（②）—— 名字冻结，W2 按这些名字接
    # ★ 本层不建"新控件类型"以外的逻辑：add_gene_result 需要新建一个页签
    #   （页签内容随结果数量增长，不可能在布局期预建），故这一处由 func 建控件。
    # ★ 本层不写任何 R / subprocess / 文件读写（出图全归 W2/W3）。
    # ------------------------------------------------------------------





