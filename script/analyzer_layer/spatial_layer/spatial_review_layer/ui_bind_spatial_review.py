# -*- coding: utf-8 -*-
"""
空转「审查模式」子页面 —— 逻辑与编排绑定脚本

职责（M2a/M3 契约 §4 + W1 冻结控件清单）：
  · 读 `list_review_figures()`，把 PNG 路径 **setPixmap** 进 W1 建好的图控件；填图注
  · 控制 `figure_tabs` ↔ `figure_empty_hint` 显隐
  · 连信号、读写评分、刷样本名颜色
  · 图集 id 变化时显示 ⚠ 警示 + 「按旧评分继续」/「清空重审」
  · 未审样本：灰色 + ⚠未审 角标 + **每个未审集合只弹一次**

★ 本文件**不创建任何控件**（契约/协调者明确）：不 import 工厂、不 addTab、不 QLabel、不 create_*。
  只用 W1 已建好的控件：`figure_views` / `figure_notes` / `figure_tabs` / `figure_empty_hint` /
  `figure_caption_label` / `review_sample_list` / `review_progress_label` / `sample_total_stars` /
  `sample_color_swatch` / `dimension_stars` / `atlas_warning_panel`。

★ 三条硬要求（协调者冻结）：
  1. **逐格分只写记录**；**只有样本总分（star_size=28）的 `rating_changed` 才连到刷颜色**
     （W1 §7.3 / 契约 R2）。
  2. 跨页传参走 **C1**：读 `spatial_top_bind.pending_review_sample`，**读后即清**；不改 `page_intersect.py`。
  3. **图集 id 变化必须显示警示**，绝不静默沿用、绝不静默清空。

⚠ 命名纪律（本轮踩过的坑，见 `ui_bind_spatial_top.py` 同名注释）：
  状态字段不要与检测方法同名 —— `self.x = True` 会**遮蔽**类上的 `def x(self)`。
  本文件用 `self._filling` 做状态、`self._is_filling()` 做检测，刻意分开。

⚠ Qt 回调纪律（协调者警告 ③）：PyQt5 对槽里未捕获的 Python 异常调 `qFatal()` →
  **进程直接 abort、无 traceback**。因此**每一个槽函数体都自带 try/except + traceback.print_exc()**。

⚠ 解码成本（协调者实测）：逐样本 6 型 × 19 = 114 张，设了 `setScaledSize` 仍要完整 zlib 解压，
  **约 212 ms/张 ≈ 24 秒**。故：**只解码当前页签那一型（19 张），切页签才解码该型**，
  绝不一次性解码整组；并在日志里如实告知"正在解码"。
"""

import os
import time

from script.utils_layer.import_config import *
# ★ 显式 import：不依赖 import_config 的导出清单（本轮已第二次强调该踩坑面）
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from script.analyzer_layer.spatial_layer.spatial_review_layer import spatial_review_analysis as RA
from script.analyzer_layer.spatial_layer.spatial_review_layer.ui_func_spatial_review import SpatialReviewFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.page_intersect import page_intersect
# 样本 id 解析唯一实现处（契约修订 R1 的取 id 侧；**禁止**再写 GSM 专属正则）
from script.utils_layer.sample_id_utils import sample_id_from_item


class SpatialReviewBind:
    """审查模式子页面绑定类 - 全权负责粘合内外"""

    def __init__(self, main_window, ui_instance):
        self.parent = main_window
        self.ui = ui_instance
        self.func = SpatialReviewFunc(ui_instance, main_window)
        self.analysis = None            # SpatialDataManager（从顶层 bind 取）

        self.dataset = None
        self.figures = {}               # list_review_figures() 的返回
        self.scores = {}                # 评分（含 figure_set_id）
        self.current_sample = None
        self.current_figure_type = None
        self._filling = False           # 状态字段（勿与 _is_filling() 同名）
        self._warned_unreviewed = set()  # 未审弹窗去重（每个未审集合只弹一次）
        self._decoded_pages = set()     # 已解码过图的 page 索引（防重复解码）
        self._atlas_conflict = False    # 当前是否处于"图集不符"状态
        self._dirty = False             # 评分是否有未落盘改动
        self._entered_key = None        # on_page_entered 的幂等键 (dataset, figure_set_id)

        self.init_bindings()
        self.refresh_all(reason="进入页面")

    # ==================================================================
    # 绑定
    # ==================================================================
    def init_bindings(self):
        """初始化所有绑定（每个槽都自带 try/except，防 PyQt5 abort）"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_sample_list()
        self.bind_scoring()
        self.bind_figure_tabs()
        self.bind_atlas_actions()

    def bind_music_controls(self):
        try:
            if hasattr(self.ui, 'music_controller'):
                fix_music_controller_bindings(self, self.ui.music_controller)
        except Exception:
            traceback.print_exc()

    def bind_navigation(self):
        """返回按钮 → 顶层页（hub）

        ⏱ 2026-09-20 第二轮拍板：「绘制区域」入口**已从审查页退休** ——
          绘区域现在是 hub 的独立入口（`btn_card_region`），审查页那个按钮
          W1 已删，所以这里连同 `_on_goto_region_clicked` 的接线一并删除
          （不留死代码；`_on_goto_region_clicked` 也已随之删除）。
        """
        try:
            if hasattr(self.ui, 'nav_btn_back'):
                self.ui.nav_btn_back.clicked.connect(self._on_back_clicked)
        except Exception:
            traceback.print_exc()

    def bind_sample_list(self):
        try:
            if hasattr(self.ui, 'review_sample_list') and \
                    hasattr(self.ui.review_sample_list, 'itemSelectionChanged'):
                self.ui.review_sample_list.itemSelectionChanged.connect(
                    self._on_sample_selection_changed)
        except Exception:
            traceback.print_exc()

    def bind_scoring(self):
        """★ 两层打分的接线是**故意不同**的（契约 R2 / W1 §7.3）

        · 逐格 5 维（`dimension_stars[*]`，star_size=16）→ 只写记录，**不刷颜色**
        · 样本总分（`sample_total_stars`，star_size=28）→ **唯一**刷颜色的入口
        """
        try:
            # 样本总分：唯一染色源
            if hasattr(self.ui, 'sample_total_stars'):
                sig = getattr(self.ui.sample_total_stars, 'rating_changed', None)
                if sig is not None:
                    sig.connect(self._on_total_rating_changed)
                # 注入颜色回调：每次重绘/重刷都由 W1 重新调用（房规 2：不得缓存创建时的色）
                if hasattr(self.ui.sample_total_stars, 'set_color_provider'):
                    self.ui.sample_total_stars.set_color_provider(
                        lambda stars: RA.color_for_stars(stars))

            # 逐格 5 维：只记录
            dims = getattr(self.ui, 'dimension_stars', None)
            if isinstance(dims, dict):
                for dim_key, star_widget in dims.items():
                    sig = getattr(star_widget, 'rating_changed', None)
                    if sig is None:
                        continue
                    sig.connect(self._make_dimension_handler(dim_key))
                    # 逐格星用中性色（W1 §4.2.3 手段 3），不给分数色 provider

            for attr in ('btn_review_save', 'btn_review_skip'):
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(getattr(self, '_on_' + attr.replace('btn_review_', '') + '_clicked'))
        except Exception:
            traceback.print_exc()

    def bind_figure_tabs(self):
        """页签切换 → 只填充该型（惰性解码，防 24 秒一次性解码）"""
        try:
            tabs = getattr(self.ui, 'figure_tabs', None)
            if tabs is not None and hasattr(tabs, 'currentChanged'):
                tabs.currentChanged.connect(self._on_tab_changed)
        except Exception:
            traceback.print_exc()

    def bind_atlas_actions(self):
        try:
            for attr, handler in (('btn_keep_old_scores', self._on_keep_old_scores_clicked),
                                  ('btn_clear_scores', self._on_clear_scores_clicked)):
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(handler)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 取数据（契约：从 main_window.spatial_top_bind.analysis 读，getattr 守卫）
    # ==================================================================
    def _top_bind(self):
        """取顶层 bind（能进本页的前提就是先经过顶层页，但**仍加守卫**）"""
        try:
            return getattr(self.parent, 'spatial_top_bind', None)
        except Exception:
            traceback.print_exc()
            return None

    def _resolve_analysis(self):
        """解析 SpatialDataManager；取不到**如实报错、不抛**"""
        try:
            top = self._top_bind()
            if top is None:
                self._log("无法获取空转顶层 bind（spatial_top_bind 不存在）")
                return None
            an = getattr(top, 'analysis', None)
            if an is None:
                self._log("顶层 bind 上没有 analysis 实例")
                return None
            self.analysis = an
            return an
        except Exception:
            traceback.print_exc()
            return None

    def _dataset_name(self):
        try:
            an = self.analysis
            if an is not None and getattr(an, 'dataset_name', None):
                return an.dataset_name
            top = self._top_bind()
            if top is not None:
                an = getattr(top, 'analysis', None)
                if an is not None:
                    return getattr(an, 'dataset_name', None)
            return None
        except Exception:
            traceback.print_exc()
            return None

    def _consume_pending_sample(self):
        """契约 C1：读 `pending_review_sample` 并**读后即清**"""
        try:
            top = self._top_bind()
            if top is None:
                return None
            sid = getattr(top, 'pending_review_sample', None)
            if sid:
                top.pending_review_sample = None      # 读后即清
                return sid
            return None
        except Exception:
            traceback.print_exc()
            return None

    # ==================================================================
    # 进入页面的钩子（page_intersect 在 go_to_page_with_bind 末尾调用）
    # ==================================================================
    def on_page_entered(self):
        """每次跳转到本页时由 `page_intersect` 调用（可选钩子，`:577-591`）

        ★ **为什么必须有**（协调者端到端实测的根因）：
          `page_intersect._preload_all_bind_modules()` 在**应用启动时**就为每个页面建好了
          bind 实例（`:408-411` 的 `if hasattr(...): continue`），于是
          ① 本类 `__init__` 里那次 `refresh_all()` 发生在**用户还没加载数据集**的时刻；
          ② 之后 `go_to_page_with_bind` 看到 bind 已存在 → **复用、不再创建**，
             也没有任何"进入时刷新"的回调。
          ⇒ 真实流程（先加载数据集 → 再点「审查模式」）**永远拿不到刷新**，页面恒为空。
          实测到的现象：`figures.ok = None`、样本列表 0 条、图控件 0/6。

        ★ **幂等键**：`(dataset, figure_set_id, review_version)`
          —— 三者都没变就直接 return。审查页重填代价虽小于初步分析页，
             但同样会白刷一遍颜色/列表并重置选中项，**且用户会看到选中被我改掉**。

        ★★ 第三项 `review_version` 是**需求④**加的（2026-09，用户第二轮实测报的 bug）：
          · 原键只有 `(dataset, figure_set_id)`，而 **`figure_set_id` 只反映图集**，
            评分/备注的变化**完全不在键里**。
          · 症状：在审查页保存 → 回初步分析页 → 键没变 → 跳过刷新 →
            徽标/备注/进度还是旧的 → **只有重启才更新**。
          · `review_version` = `RA.review_version(dataset)` = `(mtime_ns, size)`；
            `save_review_scores` 走 `os.replace` 原子替换 ⇒ 每次保存 mtime 必变。
          · 本页保存后也走这条路：保存 → `_persist_scores` → 下次进页面键已变 → 重读。
        ★ 幂等性**没有退化**：文件没被动过时 `review_version` 不变 ⇒ 键不变 ⇒ 直接 return，
          **一张图都不重解**（用户明确要求保住这条）。
        """
        try:
            dataset = self._dataset_name()
            if not dataset:
                # 未加载数据集：走提示分支，**不抛**
                self._log("【审查模式】进入页面，但顶层页尚未加载数据集 → 请先回主页加载")
                self.func.show_empty_state("请先在主页加载数据集")
                self._show_tabs_or_hint(False)
                self._entered_key = None
                return

            current_id = RA.figure_set_id(dataset)
            rv = RA.review_version(dataset)
            key = (dataset, current_id, rv)
            if key == getattr(self, '_entered_key', None):
                self._log("【审查模式】进入页面（%s / %s / 评分版本 %s 均未变，跳过刷新）"
                          % (dataset, current_id, rv))
                return
            self._log("【审查模式】进入页面：%s（图集 %s，评分版本 %s）"
                      % ("幂等键变化 → 刷新" if getattr(self, '_entered_key', None) else "首次",
                         current_id, rv))
            self._entered_key = key
            self.refresh_all(reason="进入页面（on_page_entered）")
        except Exception:
            traceback.print_exc()   # 内部兜底：抛了会被 page_intersect 吞掉且跳转照常

    # ==================================================================
    # 主刷新
    # ==================================================================
    def refresh_all(self, reason=""):
        """整页刷新：取数 → 图型核对 → 样本列表 → 当前样本 → 图集核对"""
        try:
            self._log("=" * 40)
            self._log("【审查模式】%s" % (reason or "刷新"))

            an = self._resolve_analysis()
            if an is None:
                self.func.show_empty_state("无法获取空转数据（顶层页未就绪）")
                self._show_tabs_or_hint(False)
                return

            dataset = self._dataset_name()
            if not dataset:
                self._log("顶层页尚未加载数据集 → 请先回主页加载数据集")
                self.func.show_empty_state("请先在主页加载数据集")
                self._show_tabs_or_hint(False)
                return
            self.dataset = dataset
            self._log("数据集: %s" % dataset)

            # ① 图清单
            self.figures = RA.list_review_figures(dataset)
            if not self.figures.get("ok"):
                self._log("读取图清单失败: %s" % self.figures.get("reason"))
                self.func.show_empty_state("读不到图清单：%s"
                                           % (self.figures.get("reason") or "未知原因"))
                self._show_tabs_or_hint(False)
                return

            # ② 图型一致性核对（**差异由我打日志，绝不静默**）
            types = list(self.figures.get("figure_types") or [])
            try:
                # ★ W1 冻结签名：verify_figure_types(list) -> (matched: bool, extra: list, missing: list)
                #   `matched` 是**布尔**不是列表（本轮踩过：写 len(matched) 会 TypeError）
                checked = self.func.verify_figure_types(types)
                if isinstance(checked, tuple) and len(checked) == 3:
                    matched, extra, missing = checked
                    if extra or missing:
                        self._log("⚠ 图型不一致：多出 %s / 缺少 %s" % (list(extra), list(missing)))
                    else:
                        self._log("图型核对通过：%s（数据 %d 个图型，matched=%s）"
                                  % ("一致" if matched else "?", len(types), matched))
                else:
                    self._log("⚠ verify_figure_types 返回形状异常: %r" % (checked,))
            except Exception:
                traceback.print_exc()

            # ③ 样本差异（read 返回里已给出）
            diff = self.figures.get("sample_diff") or {}
            if diff.get("extra_in_figures"):
                self._log("⚠ 图里有、清单没有的样本: %s" % diff["extra_in_figures"])
            if diff.get("missing_in_figures"):
                self._log("⚠ 清单有、图里没有的样本: %s" % diff["missing_in_figures"])
            for ft, items in (self.figures.get("unmatched") or {}).items():
                if items:
                    self._log("⚠ 图型 %s 有无法归属的图: %s" % (ft, items[:5]))

            # ④ 评分 + 图集核对
            self.scores = RA.load_review_scores(dataset)
            for iss in (self.scores.get("_issues") or []):
                self._log("评分文件提示: %s" % iss)
            self._check_atlas()

            # ⑤ 样本列表 + 未审软阻断
            self._fill_sample_list()

            # ⑥ 进入时的初始样本：C1 传参优先
            pending = self._consume_pending_sample()
            if pending:
                self._log("从其他页面带入待审查样本: %s" % pending)
                self._select_sample_in_list(pending)
            self._sync_current_sample()

            # ⑦ 图区
            self._refresh_figure_area()
        except Exception:
            traceback.print_exc()

    def _show_tabs_or_hint(self, has_figures):
        """`figure_tabs` ↔ `figure_empty_hint` 显隐联动（协调者明确归我）"""
        try:
            tabs = getattr(self.ui, 'figure_tabs', None)
            hint = getattr(self.ui, 'figure_empty_hint', None)
            if tabs is not None:
                tabs.setVisible(bool(has_figures))
            if hint is not None:
                hint.setVisible(not has_figures)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 样本列表
    # ==================================================================
    def _item_text(self, sid, label=None, reviewed=None, stars=None):
        """**列表项文本的唯一生成处**（填表、重写、刷新都必须调它，否则两处写法会不一致）

        实测修掉的两个用户可见 bug：
          bug1 **样本号重复两次**：W1 的 `set_sample_items` 已是 `"%s %s" % (sample_id, label)`，
               而 `label` 若自带样本号（manifest 的 label 形如 `"GSM7596587 / mgh258"`）
               ⇒ 就变成 `GSM7596587 GSM7596587 / mgh258`。
               → 本函数：**label 已含 sid 就不再前置 sid**（由 `_sample_label` 先剥掉开头样本号，
                 这里再兜一次底）。
          bug2 **被选中项丢掉 `⚠未审` 角标**：选中项文本被另一条路径重写却没带角标。
               → 本函数统一带上角标；`_restamp_sample_items()` 用它重写**每一项**（含选中项）。

        ★★ 星串 = **固定 5 个字符**（协调者裁决，2026-09）
          格式（与 `ui_func_spatial_initial.sample_item_text` **同形**，两边观感必须一致）：
              未审：`⚠未审  <body>`
              已审：`★★★★☆  <body>`      ← 实心 = 总分、空心 = 5−总分
          为什么改掉旧写法 `"★" * stars`：
            · 看不出满分是 5（`★★★★` 到底缺不缺一颗？）；
            · `stars=0 且已审` 时星串**整段消失**，只剩裸 body —— 那是显示缺陷
              （已审但没打分也是"已审"状态，必须看得出"0/5"）。
          `stars` 为 None / 非数字 → 一律当 0，**不抛**；越界夹到 0..5。
        """
        try:
            sid = str(sid or "").strip()
            lab = str(label or "").strip()
            if lab and sid and sid in lab:
                body = lab                       # label 已含样本号 → 不重复
            elif lab:
                body = ("%s %s" % (sid, lab)).strip()
            else:
                body = sid
            if reviewed is None:
                reviewed = (RA.review_state(sid, self.scores) == "scored")
            if not reviewed:
                return "⚠未审  " + body          # 契约 R5：未审**始终**带角标，不给星串
            try:
                n = int(stars or 0)
            except (TypeError, ValueError):
                n = 0
            n = max(0, min(5, n))
            return ("★" * n + "☆" * (5 - n)) + "  " + body
        except Exception:
            traceback.print_exc()
            return str(sid or label or "")

    def _fill_sample_list(self):
        """把样本清单交给 func 渲染（含 reviewed 标记与总分），并刷颜色"""
        try:
            samples = []
            for sid in (self.figures.get("samples") or []):
                entry = (self.scores.get("samples") or {}).get(sid) or {}
                total = entry.get("total")
                try:
                    total = int(total) if total is not None else 0
                except Exception:
                    total = 0
                reviewed = (RA.review_state(sid, self.scores) == "scored")
                # ★ 统一文本：label 已含 sid 时不重复前置；未审始终带角标
                label = self._item_text(sid, self._sample_label(sid),
                                        reviewed=reviewed, stars=total)
                samples.append({"id": sid, "label": label,
                                "reviewed": reviewed, "total": total})
            try:
                self.func.set_sample_items(samples)
            except Exception:
                traceback.print_exc()
            # W1 的 set_sample_items 会自己再前置一次 sid → 这里统一重写成权威文本
            self._restamp_sample_items()
            self.refresh_sample_colors()
            self._refresh_progress()
        except Exception:
            traceback.print_exc()

    def restamp_sample_item(self, sid):
        """重写**单个**样本项的文本（含 `⚠未审` 角标与总星星标）

        ★ 这是 bug④ 的修复件：`_on_total_rating_changed` 只刷了颜色与进度，
          **没重写文本** → `⚠未审` 角标留在界面上，用户以为"没保存成功"
          （实际 `review.json` 已写对，重启后自然正确）。
        ★ 文本一律由 `_item_text()` 生成（单一来源），保证角标与星标不会两处写法不一致。
        """
        try:
            lst = getattr(self.ui, 'review_sample_list', None)
            if lst is None or not hasattr(lst, 'count') or not sid:
                return False
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                if str(self._sample_id_from_item(item)) != str(sid):
                    continue
                entry = (self.scores.get("samples") or {}).get(str(sid)) or {}
                try:
                    total = int(entry.get("total") or 0)
                except Exception:
                    total = 0
                reviewed = (RA.review_state(sid, self.scores) == "scored")
                item.setText(self._item_text(sid, self._sample_label(sid),
                                             reviewed=reviewed, stars=total))
                return True
            return False
        except Exception:
            traceback.print_exc()
            return False

    def _restamp_sample_items(self):
        """用 `_item_text` 统一重写每一项文本（消除 W1 的二次拼接；角标对选中项也保留）"""
        try:
            lst = getattr(self.ui, 'review_sample_list', None)
            if lst is None or not hasattr(lst, 'count'):
                return
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                sid = self._sample_id_from_item(item)
                if not sid:
                    continue
                entry = (self.scores.get("samples") or {}).get(str(sid)) or {}
                try:
                    total = int(entry.get("total") or 0)
                except Exception:
                    total = 0
                reviewed = (RA.review_state(sid, self.scores) == "scored")
                try:
                    item.setText(self._item_text(sid, self._sample_label(sid),
                                                 reviewed=reviewed, stars=total))
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()

    def _sample_label(self, sid):
        """样本显示名的**尾部**（去掉开头的样本号，避免与 sid 重复）

        manifest 的 `label` 形如 `"GSM7596587 / mgh258"` —— **自带样本号**。
        这里把开头的 `GSM\\d+` 去掉，只保留 `"/ mgh258"` → `"mgh258"`，
        交给 `_item_text` 组出 `GSM7596587 mgh258`（号只出现一次）。
        取不到 label 时返回 ""（由 `_item_text` 只用 sid）。
        """
        try:
            raw = ""
            an = self.analysis
            for s in (getattr(an, 'samples', None) or []):
                if isinstance(s, dict) and str(s.get('id')) == str(sid):
                    raw = str(s.get('label') or '')
                    break
            if not raw:
                return ""
            import re
            # 去掉开头的样本号（可能后跟 '/' 或空格）
            stripped = re.sub(r'^\s*' + re.escape(str(sid)) + r'\s*[/\-|]?\s*', '', raw).strip()
            return stripped
        except Exception:
            traceback.print_exc()
            return ""

    def refresh_sample_colors(self):
        """★ 唯一染色入口：**只读样本总分**（逐格分不参与），颜色每次现算

        W1 §4.2.4：对每个列表项 `setForeground(color_for_stars(total))`；
        未打分（0）→ 中性色（`color_for_stars(0)` 已内置该语义），**不是 1 分色**。
        """
        try:
            lst = getattr(self.ui, 'review_sample_list', None)
            if lst is None or not hasattr(lst, 'count'):
                return
            reviewed_with_score = 0
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                sid = item.data(Qt.UserRole) if hasattr(item, 'data') else None
                if not sid:
                    sid = self._sample_id_from_item(item)
                entry = (self.scores.get("samples") or {}).get(str(sid)) or {}
                try:
                    total = int(entry.get("total") or 0)
                except Exception:
                    total = 0
                if total > 0:
                    reviewed_with_score += 1
                color = RA.color_for_stars(total)
                try:
                    item.setForeground(color)
                except Exception:
                    traceback.print_exc()
                # 底衬：把"四层合成"降为"两层合成"（W1 §6.3.6），QListWidgetItem 支持
                try:
                    if hasattr(item, 'setBackground'):
                        item.setBackground(RA.chip_color_for_stars(total))
                except Exception:
                    pass
            self._log("已按总分刷新 %d 个样本名颜色（其中已打分 %d 个）"
                      % (lst.count(), reviewed_with_score))
        except Exception:
            traceback.print_exc()

    def _sample_id_from_item(self, item):
        """从列表项取样本 id（**唯一口径**：`sample_id_utils.sample_id_from_item`）

        W1 的 `set_sample_items` 会写成：
          · 未审：`⚠未审  UKF241_C_ST UKF241_C_ST`
          · 已审：`★★★★☆  GSM7596587 mgh258`（星串固定 5 字符，见 `_item_text`）
        并写入 `setData(Qt.UserRole, sample_id)` ⇒ 先读 UserRole（权威），
        读不到再按**已知样本清单**从文本里认（清单来自 `figures['samples']`）。

        ★★ 真 bug 的根因（用户 2026-09 报"审查页 Dryad 各样本各页签都不出图"）：
            这里原来写死 `re.search(r'(GSM\\d+)', txt)` —— 只认 GEO 的 `GSM*` 编号。
            Dryad_UKF 的 id 是 `UKF241_C_ST` ⇒ **每一项都返回 None** ⇒
            `_select_sample_in_list` 选不中任何样本 ⇒ `current_sample` 恒为 None ⇒
            `_fill_figure_page` 拿不到 sid ⇒ 全部逐样本页签一律走"该格尚未生成"。
            （GSE237183 是 `GSM7596587`，恰好命中 ⇒ 该数据集一直正常，掩盖了这个硬编码。）
          契约依据：**契约修订 R1** 已把样本 id 判据放宽为
            `^[A-Za-z][A-Za-z0-9_.\\-]*$`（GEO 之外没有 GSM 编号）——
            取 id 这一侧必须跟上同一条判据。
        """
        try:
            return sample_id_from_item(item, self.figures.get("samples") or [])
        except Exception:
            traceback.print_exc()
            return None

    def _refresh_progress(self):
        try:
            total = len(self.figures.get("samples") or [])
            done = 0
            for sid in (self.figures.get("samples") or []):
                if RA.review_state(sid, self.scores) == "scored":
                    done += 1
            self.func.set_progress_text("已审 %d / %d 个样本" % (done, total))
        except Exception:
            traceback.print_exc()

    def _select_sample_in_list(self, sid):
        """在列表里选中指定样本（找不到则记日志，不静默）"""
        try:
            lst = getattr(self.ui, 'review_sample_list', None)
            if lst is None or not hasattr(lst, 'count'):
                return
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                if str(self._sample_id_from_item(item)) == str(sid):
                    lst.setCurrentItem(item)
                    return
            self._log("列表里没有找到样本 %s（清单与图集可能不一致）" % sid)
        except Exception:
            traceback.print_exc()

    def _sync_current_sample(self):
        """把当前选中样本同步到右栏（总分星、逐格星、颜色预览、图注）"""
        try:
            sid = self.current_sample
            entry = (self.scores.get("samples") or {}).get(str(sid)) if sid else None
            entry = entry if isinstance(entry, dict) else {}
            try:
                total = int(entry.get("total") or 0)
            except Exception:
                total = 0
            self._filling = True
            try:
                if hasattr(self.ui, 'sample_total_stars') and \
                        hasattr(self.ui.sample_total_stars, 'set_rating'):
                    self.ui.sample_total_stars.set_rating(total, emit=False)
                if hasattr(self.ui, 'sample_total_value_label') and \
                        hasattr(self.ui.sample_total_value_label, 'setText'):
                    self.ui.sample_total_value_label.setText(
                        "%d / 5%s" % (total, "" if total else "（未打分）"))
                dims = (entry.get("cells") or {})
                star_map = getattr(self.ui, 'dimension_stars', None)
                if isinstance(star_map, dict):
                    for dim_key, w_ in star_map.items():
                        v = dims.get(dim_key)
                        try:
                            v = int(v) if v is not None else 0
                        except Exception:
                            v = 0
                        if hasattr(w_, 'set_rating'):
                            w_.set_rating(v, emit=False)
                if hasattr(self.ui, 'dimension_summary_label') and \
                        hasattr(self.ui.dimension_summary_label, 'setText'):
                    self.ui.dimension_summary_label.setText(
                        "本图 %s（逐格均值，不决定颜色）" % self._dimension_summary(dims))
                if hasattr(self.func, 'set_total_score'):
                    self.func.set_total_score(total)
            finally:
                self._filling = False
            # ⚠ ⑤（用户上机实测）：W1 已删掉 `sample_color_swatch` /
            #   `sample_color_value_label` 两个控件 ⇒ 不再调 `func.set_color_preview`。
            #   颜色的实际落点是**样本列表项前景色**（`refresh_sample_colors`），
            #   那里才是"颜色随总分变"的可见位置。
        except Exception:
            traceback.print_exc()

    def _dimension_summary(self, dims):
        try:
            vals = []
            for k, _ in getattr(self.ui, 'DIMENSIONS', []) or []:
                v = (dims or {}).get(k)
                if v:
                    vals.append(float(v))
            if not vals:
                return "未评"
            return "%.1f" % (sum(vals) / len(vals))
        except Exception:
            return "未评"

    # ==================================================================
    # 图区
    # ==================================================================
    def _refresh_figure_area(self):
        """只在"当前页签"上填图（惰性解码，绝不一次性解码整组）"""
        try:
            order = list(self.figures.get("figure_types") or [])
            if not order:
                self._show_tabs_or_hint(False)
                return
            self._show_tabs_or_hint(True)
            tabs = getattr(self.ui, 'figure_tabs', None)
            idx = tabs.currentIndex() if (tabs is not None and hasattr(tabs, 'currentIndex')) else 0
            if idx < 0 or idx >= len(order):
                idx = 0
            self.current_figure_type = order[idx]
            self._fill_figure_page(self.current_figure_type)

            # 未选样本时给一行提示，但**不阻塞**（契约 Q2'）
            if not self.current_sample:
                try:
                    self.func.show_empty_state("请先在左侧选择一个样本")
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()

    def _fill_figure_page(self, ftype):
        """填充某一图型：当前选中样本的图 → 对应图控件；无图则清空并提示

        解码成本实测 ≈212 ms/张 → **只解码当前样本这一张**（而不是该型 19 张），
        用户切样本/切页签时才解码下一张。日志如实告知。
        """
        try:
            if not ftype:
                return
            view = None
            note = None
            views = getattr(self.ui, 'figure_views', None)
            notes = getattr(self.ui, 'figure_notes', None)
            if isinstance(views, dict):
                view = views.get(ftype)
            if isinstance(notes, dict):
                note = notes.get(ftype)

            sid = self.current_sample
            path = None
            if sid:
                cell = ((self.figures.get("matrix") or {}).get(sid) or {}).get(ftype) or {}
                path = cell.get("png")
                pdf = cell.get("pdf")
            else:
                pdf = None

            if path:
                # ⚠ 文案要与初步分析页区分：审查页是**全尺寸**解码（要看细节），
                #   初步分析页才是缩略图。这里不能写"缩略图"。
                self._log("正在解码图像…（%s / %s）" % (sid, ftype))
                ok = False
                try:
                    ok = bool(self.func.show_figure(ftype, path))
                except Exception:
                    traceback.print_exc()
                if not ok:
                    self._log("图显示失败（文件可能已被重跑覆盖）: %s" % path)
                    try:
                        self.func.show_empty_state("该图读取失败，可能已被重新运行覆盖")
                    except Exception:
                        pass
                if note is not None and hasattr(note, 'setText'):
                    note.setText("%s · %s" % (sid, ftype))
                try:
                    self.func.set_caption("%s（%s）" % (self._ftype_label(ftype), sid))
                except Exception:
                    pass
            else:
                # 缺图：**如实表达**，不补空串假装有（契约 §4.2）
                try:
                    if isinstance(views, dict) and view is not None and hasattr(view, 'set_pixmap'):
                        view.set_pixmap(None)
                except Exception:
                    pass
                is_raw = (ftype == getattr(RA, 'RAW_TISSUE_TYPE_ID', 'tissue_raw'))
                if note is not None and hasattr(note, 'setText'):
                    note.setText("该样本原始数据里没有组织切片图"
                                 if is_raw else "该格尚未生成")
                try:
                    if is_raw:
                        # ★ 原始组织切片**不归"重跑图集"管**：图集重跑一百遍也变不出原图。
                        #   所以这里绝不能沿用"去初步分析运行"那句 —— 那是错误引导。
                        self.func.show_empty_state(
                            "样本 %s 的原始数据里没有组织切片图（hires / lowres 都没有）"
                            "—— 与图集运行无关，请回数据管理页核对 raw_root"
                            % (sid or "（未选样本）"))
                    else:
                        self.func.show_empty_state(
                            "「%s」在样本 %s 上还没有图 —— 可点下面按钮去初步分析运行"
                            % (self._ftype_label(ftype), sid or "（未选样本）"))
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()

    def _ftype_label(self, ftype):
        try:
            labels = getattr(self.ui, 'FIGURE_TYPE_LABELS', None) or {}
            return labels.get(ftype, ftype)
        except Exception:
            return ftype

    # ==================================================================
    # 槽函数（**每个都自带 try/except**，防 PyQt5 对未捕获异常 qFatal）
    # ==================================================================
    def _on_back_clicked(self):
        try:
            self.flush_scores(reason="离开审查页")
            page_intersect.go_to_parent_page('spatial_review_page')
        except Exception:
            traceback.print_exc()

    def _on_sample_selection_changed(self):
        """样本选中变化：同步右栏 + 换图 + 未审软阻断（去重弹窗）

        ⚠ 这个槽会被频繁触发（包括我用 setCurrentItem 程序设值时）→ 用 `_is_filling()` 防重入，
          否则程序设值会再触发一轮。
        """
        if self._is_filling():
            return
        try:
            lst = getattr(self.ui, 'review_sample_list', None)
            item = lst.currentItem() if (lst is not None and hasattr(lst, 'currentItem')) else None
            sid = self._sample_id_from_item(item) if item is not None else None
            if not sid:
                return
            self.current_sample = sid
            self._sync_current_sample()
            self._load_note_into_edit(sid)          # ⑥ 备注框随样本切换
            self._fill_figure_page(self.current_figure_type)
            self._note_unreviewed(sid)
        except Exception:
            traceback.print_exc()

    def _on_tab_changed(self, idx):
        """页签切换：只解该型的当前样本一张（惰性，不整组解码）"""
        if self._is_filling():
            return
        try:
            order = list(self.figures.get("figure_types") or [])
            if 0 <= int(idx) < len(order):
                self.current_figure_type = order[int(idx)]
                self._log("切到图型: %s（%s）"
                          % (self._ftype_label(self.current_figure_type), self.current_figure_type))
                self._fill_figure_page(self.current_figure_type)
        except Exception:
            traceback.print_exc()

    def _on_total_rating_changed(self, stars, max_stars=5):
        """★ 样本总分变化 —— **唯一刷颜色**的入口（契约 R2 / W1 §7.3）"""
        if self._is_filling():
            return
        try:
            sid = self.current_sample
            if not sid:
                self._log("尚未选择样本，总分未记录")
                return
            entry = (self.scores.setdefault("samples", {})).setdefault(str(sid), {})
            entry.setdefault("cells", {})
            entry["total"] = int(stars)
            self._dirty = True
            self._log("样本 %s 总分 = %d 星" % (sid, int(stars)))
            self.refresh_sample_colors()          # ← 刷颜色（唯一入口）
            # ★★ bug④ 根因修复：列表项**文本**必须跟着重写，否则 `⚠未审` 角标会一直留着
            #   （用户报"保存并下一个以后显示的还是未审，重启后才生效"——
            #     落盘一直是对的，缺的就是这一步"会话内重算文本"）。
            self.restamp_sample_item(sid)
            self._refresh_progress()
            # ⚠ ⑤：不再调 `func.set_color_preview`（W1 已删那两个控件）；
            #   颜色由上面的 `refresh_sample_colors()` 落到列表项前景色。
            # 已打分 → 从未审集合里摘掉
            if int(stars) > 0:
                self._warned_unreviewed.discard(str(sid))
            self._persist_scores(reason="总分变更")
        except Exception:
            traceback.print_exc()

    def _make_dimension_handler(self, dim_key):
        """逐格分（5 维）—— **只写记录，绝不刷颜色**"""
        def _handler(stars, max_stars=5):
            if self._is_filling():
                return
            try:
                sid = self.current_sample
                if not sid:
                    return
                entry = (self.scores.setdefault("samples", {})).setdefault(str(sid), {})
                cells = entry.setdefault("cells", {})
                cells[dim_key] = int(stars)
                self._dirty = True
                self._log("逐格分 %s / %s = %d（记录用，不决定颜色）"
                          % (sid, dim_key, int(stars)))
                try:
                    self.func.set_dimension_scores(cells)
                    self.func.set_dimension_summary(
                        "本图 %s（逐格均值，不决定颜色）" % self._dimension_summary(cells))
                except Exception:
                    pass
                self._persist_scores(reason="逐格分变更")
            except Exception:
                traceback.print_exc()
        return _handler

    def _on_save_clicked(self):
        """"保存并下一个"

        ★ bug④ 验收三条（用户上机实测要求，**不重启就要立刻生效**）：
          ① 该样本列表项文本重写 → `⚠未审` 角标**消失**（`restamp_sample_item`）
          ② 进度计数 `已审查 N / 19` 的 N **+1**（`_refresh_progress` 从内存 scores 重算）
          ③ 「下一个」跳到**下一个未审样本**（不是简单的"下一行"）
        另：保存当前样本的备注（⑥）与评分**同一时机**落盘（不每敲一字就写盘）。
        """
        try:
            sid = self.current_sample
            self._note_current_sample_note(sid)          # ⑥ 备注与评分同时机落盘
            self._persist_scores(reason="手动保存", force=True)
            if sid:
                self.restamp_sample_item(sid)            # ① 角标立刻消失
            self._refresh_progress()                     # ② 进度立刻 +1
            self._goto_next_unreviewed_sample()          # ③ 跳下一个**未审**样本
        except Exception:
            traceback.print_exc()

    def _on_skip_clicked(self):
        """"跳过"：不改分数，但**备注也要落盘**（⑥ 与评分同一时机）"""
        try:
            self._log("跳过当前样本（不改分数）")
            self._note_current_sample_note(self.current_sample)
            self._persist_scores(reason="跳过", force=True)
            self._goto_next_unreviewed_sample()
        except Exception:
            traceback.print_exc()

    def _goto_next_unreviewed_sample(self):
        """跳到**下一个未审样本**（从当前行之后找；找不到就如实提示）

        ★ 用户验收第③条明确要求"「下一个未审」从这个新样本之后跳"，
          所以不能沿用"简单下一行"（那会跳到已审样本上，用户还得再点）。
        """
        try:
            lst = getattr(self.ui, 'review_sample_list', None)
            if lst is None or not hasattr(lst, 'count') or lst.count() == 0:
                return
            cur = lst.currentRow() if hasattr(lst, 'currentRow') else 0
            n = lst.count()
            for step in range(1, n + 1):
                i = (cur + step) % n
                item = lst.item(i)
                sid = self._sample_id_from_item(item) if item is not None else None
                if sid and RA.review_state(sid, self.scores) != "scored":
                    lst.setCurrentRow(i)
                    self._log("已跳到下一个未审样本: %s" % sid)
                    return
            self._log("没有更多未审样本了（已全部审查）")
        except Exception:
            traceback.print_exc()

    def _note_current_sample_note(self, sid):
        """把备注框当前内容收进内存 scores（⑥；由 `_persist_scores` 统一落盘）"""
        try:
            if not sid:
                return
            edit = getattr(self.ui, 'sample_note_edit', None)
            if edit is None:
                return
            text = ""
            if hasattr(edit, 'toPlainText'):
                text = edit.toPlainText()
            elif hasattr(edit, 'text'):
                try:
                    text = edit.text()
                except Exception:
                    text = ""
            entry = (self.scores.setdefault("samples", {})).setdefault(str(sid), {})
            if (entry.get("note") or "") != (text or ""):
                entry["note"] = text or ""
                self._dirty = True
        except Exception:
            traceback.print_exc()

    def _load_note_into_edit(self, sid):
        """把该样本的备注读进备注框（切样本时调用）"""
        try:
            edit = getattr(self.ui, 'sample_note_edit', None)
            if edit is None:
                return
            entry = (self.scores.get("samples") or {}).get(str(sid)) or {} if sid else {}
            note = entry.get("note") or ""
            if hasattr(edit, 'setPlainText'):
                edit.setPlainText(note)
            elif hasattr(edit, 'setText'):
                edit.setText(note)
        except Exception:
            traceback.print_exc()

    def _goto_next_sample(self):
        """（保留）简单跳到下一行；主要流程已改用 `_goto_next_unreviewed_sample`"""
        try:
            lst = getattr(self.ui, 'review_sample_list', None)
            if lst is None or not hasattr(lst, 'count') or lst.count() == 0:
                return
            cur = lst.currentRow() if hasattr(lst, 'currentRow') else 0
            nxt = cur + 1
            if nxt >= lst.count():
                self._log("已经是最后一个样本")
                return
            lst.setCurrentRow(nxt)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 未审样本：**仅视觉标记，不弹窗**（契约 R5 已改）
    # ==================================================================
    def _note_unreviewed(self, sid):
        """未审样本只**记一行日志**（视觉标记由 `_item_text` 的 `⚠未审` 角标承担）

        ★ 用户上机实测后明确要求（问题⑦）：
          「我们在审查模式下点击未审核的样本就不要弹出告诉我们还需要审查的弹窗了好吧」
          ⇒ **去掉那个模态提示**。未审的视觉标记保留三处：
             ① 列表项文本的 `⚠未审` 角标（`_item_text`）
             ② 未打分时星色为中性色（`color_for_stars(0)`）
             ③ 左侧进度 `已审查 N / 19`
        ★ 本路径（点未审样本）**不再有任何模态**。
          `_can_show_modal()` 仍在，但只剩一个调用方：「清空重审」那句不可逆确认
          （见 `_on_clear_scores_clicked`）—— 那里是**必须**问一次的破坏性操作。
        """
        try:
            if RA.review_state(sid, self.scores) == "scored":
                return
            if str(sid) in self._warned_unreviewed:
                return
            self._warned_unreviewed.add(str(sid))
            self._log("样本 %s 尚未审查（仅视觉标记，不弹窗）" % sid)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 图集核对（契约 R1）—— 绝不静默沿用、绝不静默清空
    # ==================================================================
    def _check_atlas(self):
        """当前图集 id vs 评分里记录的 id；不符则显示警示面板"""
        try:
            cur = self.figures.get("figure_set_id") or ""
            old = self.scores.get("figure_set_id") or ""
            has_scores = bool(self.scores.get("samples"))
            if not cur:
                self._log("⚠ 无法取得当前图集 id（figure_set_id 为空），无法核对")
                self._set_atlas_warning(False)
                return
            self._log("当前图集 id: %s" % cur)
            if not old:
                self._log("评分文件未记录图集 id（可能是首次审查或旧版本文件）")
                self._set_atlas_warning(False)
                return
            self._log("评分记录的图集 id: %s" % old)
            if old != cur and has_scores:
                # ★★ L2：先判"旧 id 是不是当前 CSV 的**字节前缀**"。
                #   命中 ⇒ 当前图集是在被评分的那份之上**纯追加**（用户评过的每一行
                #   都还在原位置、一个字节没动）⇒ **同一图集**，不弹面板、不置冲突。
                #   实测动机：W3 只补了 7 个 `.pdf` 孪生文件（6×gene_spatial + 1×gene_panel），
                #   297 行→304 行，既有 53681 字节逐字节未变，却会逼用户在
                #   「按旧评分继续」（写他的评分文件）/「清空重审」（不可逆）之间二选一。
                #   ⚠ 命中时**绝不写 review.json**：用户什么都不用做，文件一个字节都不变。
                if RA.figure_set_id_is_append_prefix(old, self.dataset):
                    _info = RA.LAST_PREFIX_CHECK or {}
                    _msg = ("★ 评分图集 %s 是当前图集 %s 的字节前缀"
                            "（前 %s 字节 sha256 一致 = 仅追加、既有行零改动）"
                            "→ 判定为同一图集，不弹警示"
                            % (old, cur, _info.get("n_bytes")))
                    self._log(_msg)
                    # 契约不许静默：就算 `func.log` 已经写进控件，也**照打一遍 stdout**
                    print("[SpatialReview] %s" % _msg)
                    self._atlas_conflict = False
                    self._set_atlas_warning(False)
                    return
                self._atlas_conflict = True
                self._log("⚠ 当前评分对应的是旧图集（%s），当前图集 %s" % (old, cur))
                self._log("   ★ 已暂停沿用旧评分：请选择「按旧评分继续」或「清空重审」")
                try:
                    self.func.show_atlas_mismatch(old, cur)
                except Exception:
                    traceback.print_exc()
                self._set_atlas_warning(True)
            else:
                self._atlas_conflict = False
                self._set_atlas_warning(False)
        except Exception:
            traceback.print_exc()

    def _set_atlas_warning(self, visible):
        try:
            panel = getattr(self.ui, 'atlas_warning_panel', None)
            if panel is not None and hasattr(panel, 'setVisible'):
                panel.setVisible(bool(visible))
            if not visible:
                try:
                    self.func.hide_atlas_mismatch()
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()

    def _on_keep_old_scores_clicked(self):
        """按旧评分继续：把记录的 id 更新为当前 id（用户明确知情后接受）"""
        try:
            cur = self.figures.get("figure_set_id") or ""
            self.scores["figure_set_id"] = cur
            self._atlas_conflict = False
            self._dirty = True
            self._log("用户选择：按旧评分继续（已把评分绑定到当前图集 %s）" % cur)
            self._set_atlas_warning(False)
            self._persist_scores(reason="按旧评分继续", force=True)
            self._fill_sample_list()
        except Exception:
            traceback.print_exc()

    def _can_show_modal(self):
        """当前是否能安全弹模态框。

        ⚠ 为什么必须问这个问题：离屏平台（`QT_QPA_PLATFORM=offscreen` / `minimal`）下
          **模态 `exec_()` 会让进程原生崩溃**（实测 `exit=0xC0000005`，且**没有 Python
          traceback**，看起来像"程序自己没了"）。所以任何模态都必须先过这道闸。
        """
        try:
            plat = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
            if plat in ("offscreen", "minimal"):
                return False
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                return False
            if str(app.platformName() or "").strip().lower() in ("offscreen", "minimal"):
                return False
            return True
        except Exception:
            traceback.print_exc()
            return False

    def _on_clear_scores_clicked(self):
        """清空重审：**先确认**（这是不可逆操作），用户确认后清空并落盘

        ★ 这是**唯一**一处保留模态的路径：不可逆的破坏性操作必须问一次。
          离屏（测试）下弹不了模态 → **拒绝执行**而不是自动放行：宁可测试里清不掉，
          也不能在没有人类确认的情况下把用户几十分钟的人工打分抹掉。
          测试要覆盖这条路径请显式设 `bind._auto_confirm_clear = True`。
        """
        try:
            override = getattr(self, "_auto_confirm_clear", None)
            if override is None:
                if not self._can_show_modal():
                    self._log("当前平台无法弹出确认框（离屏/测试环境）→ 为安全起见未清空")
                    return
                from PyQt5.QtWidgets import QMessageBox
                r = QMessageBox.question(
                    self.parent, "确认清空",
                    "将清空该数据集的所有审查评分，且不可撤销。\n确定要清空重审吗？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if r != QMessageBox.Yes:
                    self._log("已取消清空")
                    return
            elif not override:
                self._log("已取消清空（测试覆盖）")
                return
            self.scores = {"schema": 1, "dataset": self.dataset,
                           "figure_set_id": self.figures.get("figure_set_id") or "",
                           "samples": {}}
            self._warned_unreviewed.clear()
            self._atlas_conflict = False
            self._dirty = True
            self._log("用户选择：清空重审（评分已清空）")
            self._set_atlas_warning(False)
            self._persist_scores(reason="清空重审", force=True)
            self._fill_sample_list()
            self._sync_current_sample()
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 落盘
    # ==================================================================
    def _persist_scores(self, reason="", force=False):
        """落盘评分（原子写）。**图集冲突未解决时不写**，避免把旧评分绑到新图集上"""
        try:
            if not self.dataset:
                return False
            if self._atlas_conflict:
                self._log("图集冲突未解决 → 暂不落盘（%s）" % reason)
                return False
            if not (self._dirty or force):
                return False
            # ★ 落盘前把 figure_set_id 钉成**当前图集 id**（取自 list_review_figures）。
            #   为什么必须在这里做：`load_review_scores` 首次读不到文件时返回的是
            #   `figure_set_id=""` 的空结构；若直接存下去，文件里就是空 id →
            #   下次进来 `!=` 当前 id → **永远误报"旧图集"**（协调者实测指出的同一类事故）。
            try:
                cur = (self.figures or {}).get("figure_set_id") or ""
                if cur and self.scores.get("figure_set_id") != cur:
                    self.scores["figure_set_id"] = cur
                if not self.scores.get("dataset"):
                    self.scores["dataset"] = self.dataset
            except Exception:
                traceback.print_exc()
            ok = RA.save_review_scores(self.dataset, self.scores)
            if ok:
                self._dirty = False
                self._log("评分已保存（%s）" % reason)
                self._sync_entered_key_review_version()
            else:
                self._log("⚠ 评分保存失败（%s）—— 请检查 appdata 目录权限" % reason)
            return ok
        except Exception:
            traceback.print_exc()
            return False

    def _sync_entered_key_review_version(self):
        """自己刚保存完 → 把幂等键里的**评分版本**同步成当前值

        ★ 为什么需要（否则 ④ 的修法会带来一个新毛病）：
          幂等键加了 `review_version` 之后，「保存 → 离开 → 再进本页」会因为
          **本页自己写的那次改动**判定"键变了" → 白刷一遍 `refresh_all`，
          代价是重置当前样本/颜色（用户会看到选中被改掉）。
          刚刚落盘的内容本来就是内存里这份，没有任何需要重读的东西 ⇒ 直接把键对齐。
        ★ 只更新第三项：`figure_set_id` 沿用**键里已校验过的**那个值，或退化用
          `self.figures['figure_set_id']`（本页刷新时已经拿到，**不重算**——
          重算要再读一遍 53 KB 的 `_figure_manifest.csv`）。
        ★ 键还不存在时（例如 bind 是被直接构造、没经过 `page_intersect` 的
          `on_page_entered`）**就地建立**它：本页此刻的 dataset 与图集 id 都是已知的，
          建出来的键与 `on_page_entered` 会建的完全同形。这样"保存后要不要自刷自己"
          这件事**不依赖 bind 的创建方式**。
        ★ 幂等性不因此退化：下一次真有别的改动（新的保存）时 mtime 又变 → 照常刷新。
        """
        try:
            if not self.dataset:
                return
            old = getattr(self, '_entered_key', None)
            rv = RA.review_version(self.dataset)
            if old and old[0] == self.dataset:
                self._entered_key = (old[0], old[1], rv)
            else:
                fid = (self.figures or {}).get("figure_set_id") or ""
                if not fid:
                    # 还没刷新过、连图集 id 都不知道 → 这次不动键（下次进页面会正常刷新）
                    return
                self._entered_key = (self.dataset, fid, rv)
            self._log("幂等键已同步为本页保存后的评分版本 %s" % (self._entered_key[2],))
        except Exception:
            traceback.print_exc()

    def flush_scores(self, reason="退出"):
        """对外：强制落盘（离开页面/切数据集前调用）"""
        try:
            return self._persist_scores(reason=reason, force=True)
        except Exception:
            traceback.print_exc()
            return False

    # ==================================================================
    # 小工具
    # ==================================================================
    def _is_filling(self):
        """是否正在程序化设值（防信号回环）。

        ⚠ 检测方法名与状态字段名**刻意不同**（`_filling` vs `_is_filling`）：
          同名会让 `self._filling = True` 遮蔽掉方法（本轮已踩过一次）。
        """
        try:
            return bool(self._filling)
        except Exception:
            return False

    def _log(self, msg):
        try:
            if hasattr(self.func, 'log'):
                self.func.log(msg)
            else:
                print("[SpatialReview] %s" % msg)
        except Exception:
            traceback.print_exc()

    def set_volume(self, value):
        """设置音量（与其它顶层/子页同形，供 fix_music_controller_bindings 调用）"""
        try:
            from script.mods_layer.mod_manager import global_mod_manager
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_music_player'):
                mod_instance.global_music_player.set_volume(value / 100.0)
            if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
                self.parent._sync_all_volume_sliders_from_subinterface(value)
        except Exception:
            traceback.print_exc()


__all__ = ['SpatialReviewBind']
