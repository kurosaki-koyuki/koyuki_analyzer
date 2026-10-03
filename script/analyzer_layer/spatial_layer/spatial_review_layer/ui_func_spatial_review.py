# -*- coding: utf-8 -*-
"""
空转审查模式页面前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑

★ 硬约束：本文件不读数据、不扫目录；所有数据由 bind 传入。
   全部方法**容错**：info 为 None / 非 dict / 缺键都不得抛异常。
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class SpatialReviewFunc:
    """审查模式页面前端功能类 - 纯前端显示操作"""

    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget

    # ------------------------------------------------------------------
    # 样式 / 背景（与主页 func 同构）
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
    # 日志出口（§16.3 L3：审查页**此前没有 log**，所有日志只进 stdout ⇒ 界面看不见）
    # ------------------------------------------------------------------
    def log(self, msg):
        """向审查页日志框 `review_log_text` 追加一行

        ★ 为什么必须补这个方法：`SpatialReviewBind._log` 是
          `if hasattr(self.func, 'log'): self.func.log(msg) else: print(...)` ——
          本类原来**没有** `log`，于是审查页的日志（未审样本提示、图集冲突、
          保存结果…）**全部只进 stdout、用户在界面上一个字都看不到**。
          W1/W2 都报过这一条，§16.3 的 L3 冻结了修法。
        ★ 控件不存在时：**退回 stdout 并留一行前缀**，绝不抛、也不静默丢。
        """
        widget = getattr(self.ui, 'review_log_text', None)
        if widget is None:
            print("[SpatialReview] %s" % msg)
            return
        try:
            if hasattr(widget, 'append'):
                widget.append(str(msg))
                bar = widget.verticalScrollBar()
                if bar is not None:
                    bar.setValue(bar.maximum())
            elif hasattr(widget, 'setText'):
                widget.setText(str(msg))
        except Exception:
            # 显示失败不该把调用方（bind 的每个槽）拖垮
            try:
                print("[SpatialReview] %s" % msg)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 空状态：没有图集时页面必须能正常显示，而不是报错或空白
    # ------------------------------------------------------------------
    def show_empty_state(self, message="尚未载入图集，请先在「初步分析」里运行出图。"):
        """显示空状态提示（不删页签容器，只提示）"""
        if hasattr(self.ui, 'figure_empty_hint') and self.ui.figure_empty_hint is not None:
            self.ui.figure_empty_hint.setText(message)
            self.ui.figure_empty_hint.setVisible(True)
        if hasattr(self.ui, 'figure_caption_label') and self.ui.figure_caption_label is not None:
            self.ui.figure_caption_label.setText("")

    def hide_empty_state(self):
        """隐藏空状态提示"""
        if hasattr(self.ui, 'figure_empty_hint') and self.ui.figure_empty_hint is not None:
            self.ui.figure_empty_hint.setVisible(False)

    # ------------------------------------------------------------------
    # 样本列表
    # ------------------------------------------------------------------
    def set_sample_items(self, samples):
        """填充样本列表。

        Args:
            samples: list[dict]，每项至少含 'id'；可选 'label' / 'reviewed'(bool) / 'total'(int)
        ★ 容错：None / 非 list / 元素非 dict 一律忽略，不抛异常。
        """
        widget = getattr(self.ui, 'review_sample_list', None)
        if widget is None:
            return
        try:
            widget.clear()
        except Exception:
            return
        if not samples:
            self.set_progress_text("尚未载入样本")
            return
        items = samples if isinstance(samples, (list, tuple)) else []
        reviewed = 0
        for entry in items:
            if not isinstance(entry, dict):
                continue
            sample_id = str(entry.get('id', '')) or "（未知样本）"
            label = str(entry.get('label', '') or '')
            is_reviewed = bool(entry.get('reviewed', False))
            if is_reviewed:
                reviewed += 1
            text = "%s %s" % (sample_id, label)
            item = QListWidgetItem(text)
            # ★ 权威样本 id 落进 UserRole —— 绑定侧首选读取路径
            #   （文本解析只是兼容兜底；写死 `GSM\d+` 的解析在 Dryad_UKF 上恒返回 None，
            #    正是"审查页各样本各页签都不出图"的根因，见 ui_bind_spatial_review
            #    `_sample_id_from_item` 与 `sample_id_utils` 模块说明）
            try:
                item.setData(Qt.UserRole, sample_id)
            except Exception:
                traceback.print_exc()
            if not is_reviewed:
                # 未审：灰色文字 + ⚠未审 角标（软阻断，仍可点击）
                item.setText("⚠未审  " + text)
                if hasattr(self.ui, '_empty_color'):
                    item.setForeground(self.ui._empty_color)
            widget.addItem(item)
        self.set_progress_text("已审查 %d / %d" % (reviewed, len(items)))

    def set_progress_text(self, text):
        """更新左侧进度文案"""
        label = getattr(self.ui, 'review_progress_label', None)
        if label is not None:
            label.setText(str(text))

    # ------------------------------------------------------------------
    # 图类型页签（页签在图布局期已静态建好；本层只做"比对/选中/显示"）
    # ★ 本层**不建任何控件**，只 setPixmap / setText / setVisible
    # ------------------------------------------------------------------
    def verify_figure_types(self, figure_types):
        """比对数据里的图型与布局里已建好的页签（6 个图集逐样本型 + 1 个原始组织切片）；
        只报差异，不建控件。

        Args:
            figure_types: list[str]（来自 W2 的 list_review_figures），可为 None
        Returns:
            (matched: bool, extra: list, missing: list)
              matched  = 数据里的图型集合与布局的页签**完全一致**
              extra    = 数据里有、但布局页签里没有的（图集新增了类型）
              missing  = 布局页签里有、但数据里没有的（该类型本次缺图）
        ★ 容错：None / 非 list 一律当空清单，不抛异常。
        """
        order = list(getattr(self.ui, 'figure_type_order', None)
                     or getattr(self.ui, 'figure_views', {}).keys())
        if not figure_types or not isinstance(figure_types, (list, tuple)):
            given = []
        else:
            given = [str(t) for t in figure_types]
        extra = [t for t in given if t not in order]
        missing = [t for t in order if t not in given]
        matched = (not extra) and (not missing)

        # 缺图的页签给出文字提示（只 setText，不建控件）
        notes = getattr(self.ui, 'figure_notes', None)
        if isinstance(notes, dict):
            for type_id in order:
                note = notes.get(type_id)
                if note is None:
                    continue
                note.setText("" if type_id in given else "该图类型尚未生成")

        # 选中第一个"本次有图"的页签
        tabs = getattr(self.ui, 'figure_tabs', None)
        available = [t for t in order if t in given]
        if tabs is not None and available:
            try:
                tabs.setCurrentIndex(order.index(available[0]))
            except Exception:
                pass
        return matched, extra, missing

    def show_figure(self, type_id, image_path):
        """把某图类型的图片显示到对应页签（只 setPixmap/setText，不建控件）。

        ★ 容错：路径不存在 / 页签未建 / 图片损坏都只提示，不抛异常。
        """
        views = getattr(self.ui, 'figure_views', None)
        if not isinstance(views, dict):
            return False
        label = views.get(str(type_id))
        if label is None:
            return False
        path = str(image_path) if image_path else ""
        if not path or not os.path.exists(path):
            label.set_pixmap(None)
            label.setText("该图尚未生成")
            return False
        pixmap = QPixmap(path)
        if pixmap.isNull():
            label.set_pixmap(None)
            label.setText("图片读取失败")
            return False
        label.set_pixmap(pixmap)
        return True

    def set_figure_note(self, type_id, text):
        """更新某图类型页签里的说明标签"""
        notes = getattr(self.ui, 'figure_notes', None)
        if not isinstance(notes, dict):
            return
        note = notes.get(str(type_id))
        if note is not None:
            note.setText(str(text) if text else "")

    def set_caption(self, text):
        """更新图注"""
        label = getattr(self.ui, 'figure_caption_label', None)
        if label is not None:
            label.setText(str(text) if text else "")

    # ------------------------------------------------------------------
    # 打分显示
    # ------------------------------------------------------------------
    def set_total_score(self, stars):
        """刷新「样本总分」显示（★ 不改颜色：颜色由 bind 经 color_provider 统一注入）"""
        stars = stars if isinstance(stars, int) else 0
        star_widget = getattr(self.ui, 'sample_total_stars', None)
        if star_widget is not None:
            star_widget.set_rating(stars)
        label = getattr(self.ui, 'sample_total_value_label', None)
        if label is not None:
            label.setText("%d / 5" % stars if stars else "未打分")

    def set_dimension_scores(self, scores):
        """按维度刷新逐格星级（只作记录）。

        Args:
            scores: dict，key 为维度 key（structure/noise/cluster/color/usability）
        ★ 容错：None / 非 dict / 缺键一律按 0 处理。
        """
        widgets = getattr(self.ui, 'dimension_stars', None)
        if not isinstance(widgets, dict):
            return
        data = scores if isinstance(scores, dict) else {}
        for key, widget in widgets.items():
            try:
                widget.set_rating(int(data.get(key, 0) or 0))
            except Exception:
                continue

    def set_dimension_summary(self, text):
        """更新逐格汇总小字"""
        label = getattr(self.ui, 'dimension_summary_label', None)
        if label is not None:
            label.setText(str(text) if text else "")

    def set_color_preview(self, color):
        """刷新颜色预览（不透明色块 + 色值文字）。

        Args:
            color: QColor 或 '#RRGGBB' 字符串
        ★ 只做显示；颜色语义（分数→颜色）由 bind 用同一份 provider 计算。
        """
        swatch = getattr(self.ui, 'sample_color_swatch', None)
        value_label = getattr(self.ui, 'sample_color_value_label', None)
        try:
            qcolor = color if isinstance(color, QColor) else QColor(str(color))
        except Exception:
            return
        if not qcolor.isValid():
            return
        name = qcolor.name()
        if swatch is not None:
            swatch.setStyleSheet(
                "background: %s; border: 1px solid #1E3A5F; border-radius: 3px;" % name)
        if value_label is not None:
            value_label.setText(name)

    # ------------------------------------------------------------------
    # 图集版本提示（绝不静默沿用 / 绝不静默清空）
    # ------------------------------------------------------------------
    def show_atlas_mismatch(self, old_id=None, new_id=None):
        """显示「当前评分对应的是旧图集」提示条（是否沿用/清空由用户点按钮决定）"""
        panel = getattr(self.ui, 'atlas_warning_panel', None)
        label = getattr(self.ui, 'atlas_warning_label', None)
        if label is not None:
            old_text = str(old_id) if old_id else "未知"
            new_text = str(new_id) if new_id else "未知"
            label.setText("⚠ 当前评分对应的是旧图集（%s），当前图集 %s" % (old_text, new_text))
        if panel is not None:
            panel.setVisible(True)

    def hide_atlas_mismatch(self):
        """隐藏图集版本提示条"""
        panel = getattr(self.ui, 'atlas_warning_panel', None)
        if panel is not None:
            panel.setVisible(False)
