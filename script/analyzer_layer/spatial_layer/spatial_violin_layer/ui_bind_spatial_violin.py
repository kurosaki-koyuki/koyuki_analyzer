# -*- coding: utf-8 -*-
"""空转「小提琴图」页面 bind —— v11（`_d_spec_v11_split_and_bubble.md` §1.2-B）

## 由来：从表达量页 bind **整块搬移**（不是重写）
用户 2026-09-25 拍板：小提琴图**从表达量分析页解离**成主页「初步分析类」的新页，
且**文件夹也解离**。本文件的全部内容 = 表达页 bind
（`spatial_expression_layer/ui_bind_spatial_expression.py`）里**属于小提琴的**那两段：

  A. **两页共用的基础设施**（照抄一份到本页，属性名/语义逐字不变）
     `_top_bind` / `_resolve_analysis` / `_dataset_name` / `_log` / `_ensure_analysis` /
     `_ensure_sample_catalog` / `_resolve_gene_paths`（本页只用它解析 rds 与输出根）/
     `on_page_entered` / `_fill_sample_list` / `_apply_sample_tooltips` /
     `_sample_ids` / `_current_selected_ids` / `_apply_selection` / `_refresh_count` /
     `_commit_selection` / `_process_selection_change` + 三个样本按钮（全选/高分/反选）。
  B. **小提琴编排**（`VIOLIN_NO_SAMPLE_MSG` / `_init_violin_analysis` / `_func_fallback` /
     `_alert` / `_violin_log` / `_violin_gene_input_text` / `_set_violin_combo_items` /
     `_violin_unique_vals` / `_update_violin_list` / `_update_pairwise_list` /
     `on_main_combo_changed` / `on_filter1|2_combo_changed` / `on_filter1|2_enable_changed` /
     `_violin_has_samples` / `_sync_violin_context` / `load_gene` / `draw_violin_plot` /
     `_display_violin_image` / `_get_save_file_path` / `_get_export_size` /
     `_default_violin_gene` / `_do_export` / `export_png|pdf|svg|plot_csv` / `bind_violin_mode`）。

  ⛔ **没搬**（有意）：`bind_mode_navigation` / `_on_switch_mode`（"两模式"已不存在）、
     基因表达段（`_GeneExpressionWorker` / `bind_gene_expression` / `_gene_*` /
     `bind_export` / `_collect_export_items` / `_on_export_clicked` —— 那些属**基础表达**，
     留在表达量页）；注释图段（`_anno_*` / `bind_annotation_figure`）同理留在表达页。

## 数据层共享（§1.4 决策 ③，**绝不重复读 rds**）
照既有约定 `getattr(self.parent, 'spatial_top_bind', None)` → `.analysis`
（表达页与差异页同款）⇒ 本页与 hub 共用**同一个** `SpatialDataManager`。
⛔ 本文件**任何地方都不 `load_data()`**、不扫目录、不写用户数据目录。
`SpatialViolinAnalysis` 只通过 `set_context(dataset, out_dir, rds_path, samples)` 拿上下文，
rds/输出根的解析复用 `_resolve_gene_paths()`（**唯一真相源**，不造第二套规则）。

## 返回
  `nav_btn_back` → `page_intersect.go_to_parent_page('spatial_violin_page')`
  （本页在 `page_intersect` 里登记的 `parent_page='spatial_top_page'`；
   与初始页/审查页/表达页同一风格，登记关系变了只需改 `page_intersect` 一处）。
"""

import itertools
import os
import traceback

from script.utils_layer.import_config import *
# ★ 显式 import：不依赖 import_config 的导出清单（本会话已多次踩这个坑）
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFileDialog
# ★ 小提琴三页签贴图要按 `ZoomableImageLabel` 分流（与单细胞 `ViolinFunc.display_image` 同款）
from script.utils_layer.gui_styles import ZoomableImageLabel

from script.analyzer_layer.spatial_layer.spatial_review_layer import spatial_review_analysis as RA
from script.analyzer_layer.spatial_layer.spatial_violin_layer.ui_func_spatial_violin import (
    SpatialViolinFunc)
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.page_intersect import page_intersect


class SpatialViolinBind:
    """「小提琴图」页面绑定类（从表达页 bind 的**小提琴段**整块搬移而来）

    ★ 本页与表达页**各自持有一份样本选择逻辑**（两份实现逐字相同）：
      两页的样本列表控件是各自的（`sample_list`），语义也各自独立
      （表达页选"画哪些样本的基因图"，本页选"小提琴按哪些样本池化"）。
    """

    # ★★ 小提琴的**空选守卫**文案（三个入口共用一句，保证逐字一致）。
    #   为什么必须拦：R 侧 `length == 0` 的语义是 **NULL = 全部样本** ⇒ 空列表交下去
    #   会**静默退化成"画全部"**（本项目已有 D 级教训）。
    VIOLIN_NO_SAMPLE_MSG = ("⚠ 请先在左侧选择样本（小提琴图按选中样本池化；"
                            "空选不会退化成全部样本）")

    def __init__(self, main_window, ui_instance):
        self.parent = main_window
        self.ui = ui_instance
        self.func = SpatialViolinFunc(ui_instance, main_window)
        self.analysis = None

        self.dataset = None
        self._filling = False            # 状态字段（勿与 _is_filling() 同名）
        self._selected = set()           # 当前选中的样本 id
        self._handling_selection = False  # 选择变化槽的重入守卫
        self._last_selection_ids = None   # 上次已处理的选中集合（去抖"空选择"中间态）
        self._selection_pending = False   # 是否已排队一次延后的选择处理
        # ★ 本页不做图集段 ⇒ `figures` 恒空（有方法会读它，给出确定的空值而不是缺失属性）
        self.figures = {}

        # ---- 小提琴图（§1.2-B）------------------------------------------
        self.violin_analysis = None       # SpatialViolinAnalysis（延迟 import 建，见下）
        self._violin_loaded = False       # 是否已成功加载过基因
        self._func_fallback_logged = set()  # 已留痕的"func 缺方法→bind 兜底"名字（防刷屏）

        self._init_violin_analysis()
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定（每个槽自带 try/except，防 PyQt5 对未捕获异常 qFatal）"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_sample_buttons()
        self.bind_sample_list()
        self.bind_violin_mode()

    # ==================================================================
    # 导航 / 音乐
    # ==================================================================
    def bind_navigation(self):
        """本页导航：只有「← 返回主页」（回 hub）"""
        try:
            if hasattr(self.ui, 'nav_btn_back'):
                self.ui.nav_btn_back.clicked.connect(self._on_back_clicked)
            else:
                self._log("⚠ 布局缺少控件 nav_btn_back → 返回主页未绑定（需要 W1 提供）")
        except Exception:
            traceback.print_exc()

    def _on_back_clicked(self):
        """回 hub（见文件头：走 `go_to_parent_page`，与初始页/审查页/表达页同款）"""
        try:
            page_intersect.go_to_parent_page('spatial_violin_page')
        except Exception:
            traceback.print_exc()

    def bind_music_controls(self):
        try:
            if hasattr(self.ui, 'music_controller'):
                fix_music_controller_bindings(self, self.ui.music_controller)
        except Exception:
            traceback.print_exc()

    def set_volume(self, value):
        """音乐音量回调（★ 必须存在：`fix_music_controller_bindings` 会连它）

        ★★ v11 协调者补：`fix_music_controller_bindings`
          （`script/utils_layer/music_controller_fix.py:43`）里写死了
          `volume_slider.valueChanged.connect(ui_bind_instance.set_volume)`
          ⇒ 本类**必须**有 `set_volume`，否则进页面时抛
          `AttributeError: 'SpatialViolinBind' object has no attribute 'set_volume'`，
          音量滑条**静默失效**（这条路径是解离搬家时漏掉的：空转**其余 8 个** bind
          —— top/review/initial/expression/region/diff/genelist_bubble/targetgene_bubble
          —— 每个都定义了它，只有本层漏了）。
        实现与 `ui_bind_spatial_expression.py:507` 逐字同形（同一真相源，不另写一套）。
        """
        try:
            from script.mods_layer.mod_manager import global_mod_manager
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_music_player'):
                mod_instance.global_music_player.set_volume(value / 100.0)
            if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
                self.parent._sync_all_volume_sliders_from_subinterface(value)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 数据层共享：hub 的 `spatial_top_bind.analysis`（**绝不自己加载数据集**）
    # ==================================================================
    def _top_bind(self):
        """取空转顶层 bind（`self.parent.spatial_top_bind`；**不是** scRNAseq_top_bind）"""
        try:
            return getattr(self.parent, 'spatial_top_bind', None)
        except Exception:
            traceback.print_exc()
            return None

    def _resolve_analysis(self):
        """解析数据层（顶层 bind 的 analysis 是**唯一**数据层）"""
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

    def _ensure_analysis(self):
        """确保 `self.analysis` 已解析（幂等）"""
        try:
            if self.analysis is None:
                self._resolve_analysis()
            return self.analysis
        except Exception:
            traceback.print_exc()
            return None

    def _dataset_name(self):
        """数据集名（先本页缓存的 analysis，再回顶层 bind 的 analysis）"""
        try:
            an = self.analysis
            if an is not None and getattr(an, 'dataset_name', None):
                return an.dataset_name
            top = self._top_bind()
            if top is not None:
                a2 = getattr(top, 'analysis', None)
                if a2 is not None:
                    return getattr(a2, 'dataset_name', None)
            return None
        except Exception:
            traceback.print_exc()
            return None

    def _log(self, msg):
        """写日志（`func.log` → 本页 `violin_log`；缺失时退回 print，**绝不静默**）"""
        try:
            if hasattr(self.func, 'log'):
                self.func.log(msg)
            else:
                print("[SpatialViolinBind] %s" % msg)
        except Exception:
            traceback.print_exc()

    def _is_filling(self):
        """是否正在程序化设值（防信号回环）

        ⚠ 检测方法名与状态字段名**刻意不同**（`_filling` vs `_is_filling`）——
          同名会让 `self._filling = True` 遮蔽掉方法。
        """
        try:
            return bool(self._filling)
        except Exception:
            return False

    def _resolve_gene_paths(self):
        """解析 `(rds_path, out_dir, 原因)` —— 任何一项取不到都给出可读原因

        ★ 逐字搬自表达页 bind（**唯一真相源**）：rds 优先用分析层的
          `artifact_info['path']`（同一套解析规则，避免第二个真相源），
          再退回 `appdata/spatial_main/<dataset>.rds`；out_dir 取
          `analysis.dataset_output_dir`，再退回 `OUT_BASE/<dataset>`。
        ★ 本页**只读**：不建目录、不写盘（写盘只经 R 脚本落到
          `OUTPUT/<ds>/08_GeneOnDemand/_violin/`，那是 W3 的事）。
        """
        try:
            if not self.dataset:
                return None, None, "尚未确定数据集（请先在主页加载）"
            an = self.analysis
            rds = ""
            info = getattr(an, 'artifact_info', None) if an is not None else None
            if isinstance(info, dict):
                rds = str(info.get('path') or "")
            if not rds or not os.path.isfile(rds):
                try:
                    from script.utils_layer.import_config import SPATIAL_SCAN_DATA_PATH
                    cand = os.path.join(SPATIAL_SCAN_DATA_PATH, "%s.rds" % self.dataset)
                except Exception:
                    cand = ""
                if cand and os.path.isfile(cand):
                    rds = cand
                elif rds and not os.path.isfile(rds):
                    rds = rds      # 保留原路径用于报错文案
            out_dir = ""
            if an is not None:
                out_dir = str(getattr(an, 'dataset_output_dir', '') or "")
            if not out_dir:
                try:
                    from script.utils_layer.import_config import OUT_BASE
                    out_dir = os.path.join(OUT_BASE, self.dataset)
                except Exception:
                    out_dir = ""
            if not rds or not os.path.isfile(rds):
                return None, out_dir or None, "找不到成品 .rds（%s）" % (rds or "未解析出路径")
            if not out_dir:
                return None, None, "无法解析数据集输出目录"
            if not os.access(rds, os.R_OK):
                return None, out_dir, "成品 .rds 不可读：%s" % rds
            return rds, out_dir, ""
        except Exception:
            traceback.print_exc()
            return None, None, "解析 rds/输出目录时异常（见日志）"

    # ==================================================================
    # 样本选择（照抄表达页/差异页那套：UI 为准 + 保住已选 + 默认全不选）
    # ==================================================================
    def bind_sample_buttons(self):
        """`btn_sample_all` / `btn_sample_high_score` / `btn_sample_invert`"""
        try:
            pairs = (('btn_sample_all', self._on_select_all_clicked),
                     ('btn_sample_high_score', self._on_select_high_score_clicked),
                     ('btn_sample_invert', self._on_select_invert_clicked))
            for attr, handler in pairs:
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(handler)
                else:
                    self._log("⚠ 布局缺少控件 %s → 该快捷选择未绑定" % attr)
        except Exception:
            traceback.print_exc()

    def bind_sample_list(self):
        """**样本选择信号（★ 必须 `itemSelectionChanged`）**

        ★★ D 系列事故（规格 §2.4 第 1 条）：`selectionChanged` 是
          `QAbstractItemView` 的**受保护槽** —— `hasattr` 为真、却**没有 `.connect`**、
          接上也**永不触发**（协调者离屏实测）。本项目既有两页
          （`ui_bind_spatial_expression.py:357-363`、`ui_bind_spatial_diff.py:251-264`）
          都是**先认 `itemSelectionChanged`**，`selectionChanged` 只在再查一次
          `.connect` 之后作兜底（防将来控件类型被换）。
        """
        try:
            lst = getattr(self.ui, 'sample_list', None)
            if lst is None:
                self._log("⚠ 布局缺少控件 sample_list → 样本选择未绑定（需要 W1 提供）")
                return
            if hasattr(lst, 'itemSelectionChanged'):
                lst.itemSelectionChanged.connect(self._on_sample_selection_changed)
            elif hasattr(lst, 'selectionChanged') and hasattr(lst.selectionChanged, 'connect'):
                lst.selectionChanged.connect(self._on_sample_selection_changed)
            else:
                self._log("⚠ sample_list 没有可用的选择信号 → 样本选择未绑定")
        except Exception:
            traceback.print_exc()

    def _sample_ids(self):
        """当前数据集的样本号列表（顺序稳定）

        ★ 本页从 hub 的 `analysis.samples` 取（**唯一数据源**，不自己扫目录）；
          `figures` 里若已缓存 `samples` 则优先用它（与表达页同源字段）。
        """
        try:
            cached = list((self.figures or {}).get("samples") or [])
            if cached:
                return cached
            self._ensure_analysis()
            an = self.analysis
            if an is None:
                return []
            rows = getattr(an, 'samples', None) or []
            ids = []
            for row in rows:
                if isinstance(row, dict):
                    sid = str(row.get('id', '') or '').strip()
                else:
                    sid = str(row or '').strip()
                if sid:
                    ids.append(sid)
            return ids
        except Exception:
            traceback.print_exc()
            return []

    def _sample_label(self, sid):
        """显示名的尾部（去掉开头样本号，避免与 sid 重复 —— 与审查页/表达页同一处理）"""
        try:
            raw = ""
            for s in (getattr(self.analysis, 'samples', None) or []):
                if isinstance(s, dict) and str(s.get('id')) == str(sid):
                    raw = str(s.get('label') or '')
                    break
            if not raw:
                return ""
            import re
            return re.sub(r'^\s*' + re.escape(str(sid)) + r'\s*[/\-|]?\s*', '', raw).strip()
        except Exception:
            return ""

    def _review_scores(self):
        """读该数据集的审查评分（用于「选已审查高分」与未审提示）"""
        try:
            if not self.dataset:
                return {}
            return RA.load_review_scores(self.dataset)
        except Exception:
            traceback.print_exc()
            return {}

    def _total_of(self, sid):
        try:
            entry = (self._review_scores().get("samples") or {}).get(str(sid)) or {}
            return int(entry.get("total") or 0)
        except Exception:
            return 0

    def _current_selected_ids(self):
        """从 UI 读当前选中（**以 UI 为准**，因为用户可能直接点列表）"""
        try:
            if hasattr(self.func, 'get_selected_sample_ids'):
                ids = self.func.get_selected_sample_ids()
                if ids is not None:
                    return [str(x) for x in ids]
        except Exception:
            traceback.print_exc()
        return sorted(self._selected)

    def _apply_selection(self):
        """把 `self._selected` 同步到 UI（逐个 setSelected，带 `_is_filling` 防回环）"""
        try:
            lst = getattr(self.ui, 'sample_list', None)
            if lst is None or not hasattr(lst, 'count'):
                return
            self._filling = True
            try:
                for i in range(lst.count()):
                    item = lst.item(i)
                    if item is None:
                        continue
                    sid = str(item.data(Qt.UserRole) or "")
                    if not sid:
                        continue
                    try:
                        item.setSelected(sid in self._selected)
                    except Exception:
                        traceback.print_exc()
            finally:
                self._filling = False
            self._refresh_count()
        except Exception:
            traceback.print_exc()

    def _refresh_count(self):
        """刷新「已选 N / M」计数（func 缺失时退化为自算 + 直接 setText）"""
        try:
            if hasattr(self.func, 'refresh_selected_count'):
                self.func.refresh_selected_count()
                return
            n = len(self._current_selected_ids())
            lbl = getattr(self.ui, 'sample_count_label', None)
            if lbl is not None and hasattr(lbl, 'setText'):
                lbl.setText("已选 %d 个样本" % n)
        except Exception:
            traceback.print_exc()

    def _on_select_all_clicked(self):
        try:
            self._selected = set(self._sample_ids())
            self._apply_selection()
            self._log("全选：%d 个样本" % len(self._selected))
            # ★ `_apply_selection()` 用 `_filling` 压掉了控件信号 ⇒ 必须显式走一次
            #   "选中已定稿"，否则下游（小提琴上下文）不会跟着更新。
            self._commit_selection(self._current_selected_ids(), "快捷选择：全选")
        except Exception:
            traceback.print_exc()

    def _on_select_high_score_clicked(self):
        """选「已审查且总分 ≥4★」的样本（用 `RA.reviewed_high_score_samples`）"""
        try:
            scores = self._review_scores()
            high = set(RA.reviewed_high_score_samples(scores, min_stars=4))
            self._selected = {s for s in self._sample_ids() if s in high}
            self._apply_selection()
            self._log("选已审查高分（≥4★）：%d 个 %s"
                      % (len(self._selected), sorted(self._selected)[:5]))
            if not self._selected:
                self._log("（没有 ≥4★ 的样本 —— 可先去审查模式打分）")
            self._commit_selection(self._current_selected_ids(), "快捷选择：已审查高分")
        except Exception:
            traceback.print_exc()

    def _on_select_invert_clicked(self):
        try:
            all_ids = set(self._sample_ids())
            cur = set(self._current_selected_ids())
            self._selected = all_ids - cur
            self._apply_selection()
            self._log("反选：%d 个样本" % len(self._selected))
            self._commit_selection(self._current_selected_ids(), "快捷选择：反选")
        except Exception:
            traceback.print_exc()

    def _on_sample_selection_changed(self):
        """用户在列表里直接点选 → **合并后**再处理（防 Qt 多次发信号）

        ⚠⚠ 为什么必须"延后合并"而不是"进入时比较集合"：
          `clearSelection()` 会**先发一次"空选择"信号**，随后 `setSelected()` 再发一次。
          若在进入时就跟 `_last_selection_ids` 比较并**丢弃**，
          "空选择"那次会把基线更新成空集 → 真正的选择那次被误判为"无变化"而**被吞掉**
          （表达页实测：改选样本后新增解码 = 0，图不跟随 —— 等于 bug 又回来了）。
          → 正解：用 `QTimer.singleShot(0, …)` 把处理推到事件循环下一轮，
            一次用户操作产生的多次信号会被**合并成一次**处理，
            且比较发生在"选择已经稳定"之后。
        """
        if self._is_filling() or self._handling_selection:
            return
        try:
            if getattr(self, '_selection_pending', False):
                return                      # 已排队，再来的信号直接丢（合并）
            self._selection_pending = True
            QTimer.singleShot(0, self._process_selection_change)
        except Exception:
            traceback.print_exc()

    def _process_selection_change(self):
        """真正处理一次"已稳定"的选择变化（由 `_on_sample_selection_changed` 延后调用）"""
        self._selection_pending = False
        if self._is_filling() or self._handling_selection:
            return
        self._handling_selection = True
        try:
            cur = set(self._current_selected_ids())
            if cur == getattr(self, '_last_selection_ids', None):
                return
            self._refresh_count()
            self._commit_selection(cur, "样本选择变化")
        except Exception:
            traceback.print_exc()
        finally:
            self._handling_selection = False

    def _commit_selection(self, cur, source=""):
        """一次"选中已定稿"的收口：**刷新计数 + 让小提琴上下文跟随新选择**

        ★ 表达页的同名方法是"让旧基因图/注释图失效"（本页没有那些产物）。
          本页对应要做的是：**把新选择同步进 `SpatialViolinAnalysis` 的上下文**，
          否则用户改选样本后，`load_gene`/`draw_violin_plot` 仍按**上一次**的样本池化
          （科研数据上这是危险的一类错：图与"当前左侧选择"不一致）。
        ★ 只在**真的变了**（`prev is not None and cur != prev`）时同步：
          首次观察（`prev is None`）与"没变"（进页面/主题刷新）都不该触发重算。

        Returns:
            bool: 选中集合是否**真的变了**
        """
        try:
            cur = set(str(x) for x in (cur or []))
            prev = getattr(self, '_last_selection_ids', None)
            changed = (prev is not None) and (cur != prev)
            self._last_selection_ids = set(cur)
            self._selected = cur
            if changed:
                self._log("样本选择已变（%s → %s）：小提琴样本池已更新"
                          % (self._fmt_samples(prev), self._fmt_samples(cur)))
                # ★ 只同步上下文，**不**在这里自动跑 R（用户点「加载基因」才跑）
                if self._violin_loaded and cur:
                    self._sync_violin_context(reason="样本选择变化")
            return changed
        except Exception:
            traceback.print_exc()
            return False

    @staticmethod
    def _fmt_samples(ids):
        """把样本集合打印成稳定、简短的一行（**排序后**，与 set 迭代顺序无关）"""
        try:
            s = sorted(str(x) for x in (ids or []))
        except Exception:
            return "?"
        if not s:
            return "（空）"
        if len(s) <= 3:
            return ",".join(s)
        return "%d 个：%s…" % (len(s), ",".join(s[:3]))

    def _fill_sample_list(self, selected_ids=None):
        """填充样本列表（**尽量保住用户已选样本**，见下）

        ## ★★ 为什么必须透传 `selected_ids`（这一条比"填得上"更要紧）
          func 的 `set_sample_items(samples)` 不带 `selected_ids` 时是**默认全不选**；
          若每次进页面都这样重建，"用户选好样本 → 回 hub → 再进来"选择就被清空，
          而 **R 侧把空列表当"全部样本"** ⇒ 会一次画满全部样本。

        ★ 本页不进 `list_all_figures`（那套图集清单是初始页/表达页的事）：
          样本清单直接取 hub 的 `analysis.samples`，**更轻、也没有第二个真相源**。
          因此本页不需要 `_ensure_sample_catalog`（它存在只为"清单为空时补填 figures"）。
        """
        try:
            if selected_ids is None:
                selected_ids = self._current_selected_ids()
            keep = [str(x) for x in (selected_ids or [])]
            samples = []
            scores = self._review_scores()
            for sid in self._sample_ids():
                label = self._sample_label(sid)
                try:
                    reviewed = RA.review_state(sid, scores) == "scored"
                except Exception:
                    traceback.print_exc()
                    reviewed = False
                samples.append({"id": sid, "label": label,
                                "reviewed": reviewed,
                                "total": self._total_of(sid)})
            if not samples:
                self._log("⚠ 样本清单为空（数据集未加载？）→ 样本列表保持为空")
                return
            try:
                self.func.set_sample_items(samples, keep)
            except TypeError:
                # 兜底：若 func 是**老签名**（只收 1 个参数）→ 退回不带选择的调用。
                #   真走到这里说明签名没跟上，**留痕**（代价是本次丢掉已选，故必须看得见）。
                traceback.print_exc()
                self.func.set_sample_items(samples)
            except Exception:
                traceback.print_exc()
                return
            self._log("样本清单: %d 条（保持已选 %d 条%s）"
                      % (len(samples), len(keep),
                         "；**未选任何样本时不会退化成全部**" if not keep else ""))
            # ★ 需求⑥：鼠标悬停样本 → 小框显示审查时写的备注。
            #   必须紧跟在 `set_sample_items` 之后：那只函数会 clear() 重建全部 item，
            #   任何在它之前设的 tooltip 都会被丢掉。这里也是**唯一**的重建路径，
            #   所以不会漏。
            self._apply_sample_tooltips()
        except Exception:
            traceback.print_exc()

    def _apply_sample_tooltips(self):
        """把「样本备注」挂到样本列表每一项的悬停提示上（需求⑥）

        ★ 备注为空 → **显式清空** tooltip。不清空的话，同一个 item 复用时会留着
          上一个样本的备注（`QListWidget.clear()` 会毁 item，但主题重刷路径不保证），
          显示错的备注比不显示更糟。
        ★ 备注是数据层（review.json → `samples[sid]['note']`）的唯一真相源，
          这里**只读不写**，绝不因为悬停/刷新而改动用户的备注。
        """
        try:
            widget = getattr(self.ui, 'sample_list', None)
            if widget is None:
                return
            shown = 0
            for i in range(widget.count()):
                item = widget.item(i)
                if item is None:
                    continue
                try:
                    sid = str(item.data(Qt.UserRole) or "")
                except Exception:
                    sid = ""
                note = ""
                if sid:
                    try:
                        note = RA.get_sample_note(sid, self.dataset) or ""
                    except Exception:
                        traceback.print_exc()
                        note = ""
                note = str(note).strip()
                if note:
                    item.setToolTip("审查备注：\n%s" % note)
                    shown += 1
                else:
                    item.setToolTip("")
            if shown:
                self._log("已为 %d 个样本挂上审查备注提示（悬停可见）" % shown)
        except Exception:
            traceback.print_exc()

    def _page_hint(self, msg):
        """把**首屏提示**同时写进本页日志控件（`violin_log`）与页面日志

        ★ 为什么单独一个方法：`_log()` 走 `func.log`（正常情况就是 `violin_log`），
          但它**可能落在别处**（func 方法缺失时退回 print）。首屏提示必须让用户
          **在页面上**看得见，所以这里显式再写一次控件，**拿不到就只留痕**（不静默）。
        """
        try:
            widget = getattr(self.ui, 'violin_log', None)
            if widget is not None and hasattr(widget, 'append'):
                try:
                    widget.append(str(msg))
                except Exception:
                    traceback.print_exc()
            self._log(msg)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # ★ 进页钩子（规格 I4：空转子页不用 data_source_page，改用本钩子自取上下文）
    # ==================================================================
    def on_page_entered(self):
        """每次跳转到本页时由 `page_intersect.go_to_page_with_bind` 调用（可选钩子）

        ## ★ 为什么必须有它
          page_intersect 进入页面后会按约定调用本钩子；**没有它** ⇒ 数据集在首次进页
          **之后**才加载时，样本列表永远空着（D8 事故同型）。本页做四件事：
            ① 从 hub 取数据集上下文（**只获取，不加载**）；
            ② 填样本列表（**保住上次选中**）；
            ③ 恢复上次选中的样本号（`_last_selection_ids` → 控件）；
            ④ 刷新计数。
        ★ **没有数据集时只留痕、不抛、不弹窗**（正常空状态）。
        """
        try:
            self._page_hint("【小提琴图】进入页面")
            an = self._ensure_analysis()
            ds = self._dataset_name()
            if not ds:
                self._page_hint("请先在主页加载数据集（小提琴页不会自己加载数据集）")
                return
            self.dataset = ds
            self._log("数据集: %s" % ds)
            # ② 样本列表（保住上次选中）
            self._fill_sample_list(self._current_selected_ids() or sorted(self._selected))
            # ③ 恢复上次选中的样本号（控件重建后按 id 重新勾选）
            if self._last_selection_ids:
                self._selected = set(self._last_selection_ids)
                self._apply_selection()
            # ④ 计数
            self._refresh_count()
            self._log("样本列表: %d 条，当前已选 %d 个"
                      % (len(self._sample_ids()), len(self._current_selected_ids())))
            if an is None:
                self._log("⚠ 顶层 bind 的 analysis 未就绪 → 小提琴取数将在点『加载基因』时再试")
            if not self._violin_loaded:
                self._page_hint("提示：先在左侧选样本（空选不会退化成全部样本），"
                                "再输入基因名点『加载基因』")
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 小提琴编排（§1.2-B：近乎一比一复刻 `violin_layer/ui_bind_violin.py`）
    #    数据来源 = W3 的 `SpatialViolinAnalysis`；本 bind **不写盘**
    # ==================================================================
    def _init_violin_analysis(self):
        """延迟 import 建 `SpatialViolinAnalysis`（避免 Qt 未就绪时拖入绘图栈）

        ★ 本页模块尚未落地/import 失败时**不抛**：置 None 并留痕，用户点按钮时会拿到
          明确提示 —— 既**不静默**，也**不假装可用**。
        ★ v11：import 路径已指向**本页自己的包** `spatial_violin_layer/`（解离后
          小提琴模块不再住在表达量页）。
        """
        try:
            from script.analyzer_layer.spatial_layer.spatial_violin_layer.spatial_violin_analysis import (  # noqa: E501
                SpatialViolinAnalysis)
            self.violin_analysis = SpatialViolinAnalysis()
            self._log("小提琴分析层就绪：SpatialViolinAnalysis")
        except Exception as e:
            traceback.print_exc()
            self.violin_analysis = None
            print("[spatial_violin] ⚠ 小提琴分析层不可用（SpatialViolinAnalysis）：%s: %s"
                  % (type(e).__name__, e))

    def _func_fallback(self, name):
        """记录一次"func 缺方法 → bind 用内置最小实现"（**只留痕一次**，不刷屏）

        ★ 为什么不静默跳过：本项目事故的根因就是"缺名字被 except 吞掉"。
          把降级路径写进日志，验收时一眼看得出 func 的方法有没有交齐。
        """
        try:
            tag = "func." + str(name)
            if tag in self._func_fallback_logged:
                return
            self._func_fallback_logged.add(tag)
            self._log("⚠ func 无 %s → 小提琴编排回退到 bind 内置最小实现" % tag)
        except Exception:
            traceback.print_exc()

    def _alert(self, kind, message):
        """弹窗提示（`alert_error` / `alert_failure` / `alert_success`）

        ★ 优先 func；缺失或弹窗抛异常时**退回日志/控制台**（绝不静默吞掉）。
        """
        try:
            fn = getattr(self.func, 'alert_%s' % kind, None)
            if callable(fn):
                try:
                    fn(message)
                    return
                except Exception:
                    traceback.print_exc()
            print("[spatial_violin][%s] %s" % (kind, message))
            self._violin_log("[%s] %s" % (kind, message))
        except Exception:
            traceback.print_exc()

    def _violin_log(self, msg):
        """写小提琴日志框 —— 优先 func 的 `violin_log`（拿不到就写本页日志框）"""
        try:
            fn = getattr(self.func, 'violin_log', None)
            if callable(fn):
                try:
                    fn(msg)
                    return
                except Exception:
                    traceback.print_exc()
            widget = getattr(self.ui, 'violin_log', None)
            if widget is None:
                self._log("[小提琴] %s" % msg)
                return
            self._func_fallback('violin_log')
            widget.append(str(msg))
        except Exception:
            traceback.print_exc()

    def _violin_gene_input_text(self):
        """读小提琴基因输入框（控件缺失返回空串，**不抛**）"""
        try:
            w = getattr(self.ui, 'violin_gene_input', None)
            if w is None:
                return ""
            if hasattr(w, 'text'):
                return str(w.text()).strip()
            if hasattr(w, 'toPlainText'):
                return str(w.toPlainText()).strip()
            return ""
        except Exception:
            traceback.print_exc()
            return ""

    def _set_violin_combo_items(self, combo, items):
        """把分组列填进下拉框 —— 优先 `func.set_combo_items`，否则内置最小实现"""
        try:
            vals = [str(x) for x in (items or [])]
            fn = getattr(self.func, 'set_combo_items', None)
            if callable(fn):
                try:
                    fn(combo, vals)
                    return
                except Exception:
                    traceback.print_exc()
            if combo is None or not hasattr(combo, 'addItems'):
                self._log("⚠ 小提琴下拉框缺失 → %d 个选项无法填入" % len(vals))
                return
            self._func_fallback('set_combo_items')
            saved = combo.currentText() if hasattr(combo, 'currentText') else ""
            try:
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(vals)
                if saved and saved in vals:
                    combo.setCurrentText(saved)
            finally:
                combo.blockSignals(False)
        except Exception:
            traceback.print_exc()

    def _violin_unique_vals(self, group):
        """`analysis.get_group_unique_vals(col)`（分析层为唯一真相源）"""
        try:
            an = self.violin_analysis
            if an is None or not group:
                return []
            return [str(v) for v in (an.get_group_unique_vals(group) or [])]
        except Exception:
            traceback.print_exc()
            return []

    def _update_violin_list(self, kind, group, unique_vals):
        """填 `violin_main_list` / `violin_filter1_list` / `violin_filter2_list`

        ★ 单细胞同序：`func.update_main_list(group, vals)`（它内部顺带刷 pairwise 列表）；
          缺失时用内置最小实现（clear+addItems+全选），**并留痕**。
        """
        try:
            fn = getattr(self.func, 'update_%s_list' % kind, None)
            if callable(fn):
                try:
                    fn(group, list(unique_vals or []))
                    return
                except Exception:
                    traceback.print_exc()
            widget = getattr(self.ui, 'violin_%s_list' % kind, None)
            if widget is None:
                self._log("⚠ 布局未提供 violin_%s_list → 该列表无法填充" % kind)
                return
            self._func_fallback('update_%s_list' % kind)
            widget.clear()
            widget.addItems([str(x) for x in (unique_vals or [])])
            for i in range(widget.count()):
                it = widget.item(i)
                if it is not None:
                    it.setSelected(True)
        except Exception:
            traceback.print_exc()

    def _update_pairwise_list(self, unique_vals):
        """填 `violin_pairwise_list` = 所有组两两组合 `"A vs B"`

        ★ 优先 func 的同名 helper（单细胞 `ViolinFunc._update_pairwise_list`）；
          缺失时用 `itertools.combinations` 在 bind 内做（规则逐字一致）+ 留痕。
        """
        try:
            vals = [str(v) for v in (unique_vals or [])]
            fn = getattr(self.func, '_update_pairwise_list', None)
            if callable(fn):
                try:
                    fn(vals)
                    return
                except Exception:
                    traceback.print_exc()
            widget = getattr(self.ui, 'violin_pairwise_list', None)
            if widget is None:
                self._log("⚠ 布局未提供 violin_pairwise_list → 组间比较列表无法填充")
                return
            self._func_fallback('_update_pairwise_list')
            widget.clear()
            for a, b in itertools.combinations(vals, 2):
                widget.addItem("%s vs %s" % (a, b))
            for i in range(widget.count()):
                it = widget.item(i)
                if it is not None:
                    it.setSelected(True)
        except Exception:
            traceback.print_exc()

    def on_main_combo_changed(self, *args):
        """主注释下拉框变化 → 刷 `violin_main_list`（+ pairwise 列表）"""
        try:
            combo = getattr(self.ui, 'violin_main_combo', None)
            if combo is None:
                return
            group = combo.currentText()
            vals = self._violin_unique_vals(group)
            # ★ `func.update_main_list` 内部已顺带刷 pairwise；这里再显式刷一次是
            #   **幂等**的（单细胞同序，且 func 缺失时由内置实现兜底）。
            self._update_violin_list('main', group, vals)
            self._update_pairwise_list(vals)
        except Exception:
            traceback.print_exc()

    def on_filter1_combo_changed(self, *args):
        """筛选1下拉框变化 → 刷 `violin_filter1_list`"""
        try:
            if getattr(self.ui, 'violin_filter1_combo', None) is None:
                return
            group = self.ui.violin_filter1_combo.currentText()
            if group:
                self._update_violin_list('filter1', group, self._violin_unique_vals(group))
        except Exception:
            traceback.print_exc()

    def on_filter2_combo_changed(self, *args):
        """筛选2下拉框变化 → 刷 `violin_filter2_list`"""
        try:
            if getattr(self.ui, 'violin_filter2_combo', None) is None:
                return
            group = self.ui.violin_filter2_combo.currentText()
            if group:
                self._update_violin_list('filter2', group, self._violin_unique_vals(group))
        except Exception:
            traceback.print_exc()

    def on_filter1_enable_changed(self, state):
        """启用/禁用筛选1 的 combo + list（复刻单细胞 `on_filter1_enable_changed`）"""
        try:
            enabled = (state == Qt.Checked)
            for name in ('violin_filter1_combo', 'violin_filter1_list'):
                w = getattr(self.ui, name, None)
                if w is not None and hasattr(w, 'setEnabled'):
                    w.setEnabled(enabled)
        except Exception:
            traceback.print_exc()

    def on_filter2_enable_changed(self, state):
        """启用/禁用筛选2 的 combo + list（复刻单细胞 `on_filter2_enable_changed`）"""
        try:
            enabled = (state == Qt.Checked)
            for name in ('violin_filter2_combo', 'violin_filter2_list'):
                w = getattr(self.ui, name, None)
                if w is not None and hasattr(w, 'setEnabled'):
                    w.setEnabled(enabled)
        except Exception:
            traceback.print_exc()

    def _violin_has_samples(self):
        """小提琴的**空选守卫**：没有选中样本 ⇒ 拒绝执行（**绝不把空列表交给 R**）

        ★ R 侧空列表 = `NULL` = **全部样本** ⇒ 空选会静默退化成"画全部"。
          三个入口（加载基因 / 出图 / 上下文同步）共用本方法，
          保证提示文案与行为逐字一致（文案见类常量 `VIOLIN_NO_SAMPLE_MSG`）。

        Returns:
            list[str]: 当前选中的样本 id；**为空 = 调用方必须 return**（本方法已写日志）。
        """
        try:
            sel = [str(x) for x in self._current_selected_ids()]
            if not sel:
                self._violin_log(self.VIOLIN_NO_SAMPLE_MSG)
                self._log("小提琴图：左侧没有选中样本 → 已拒绝执行"
                          "（空选不会退化成全部样本）")
            return sel
        except Exception:
            traceback.print_exc()
            self._violin_log(self.VIOLIN_NO_SAMPLE_MSG)
            return []

    def _sync_violin_context(self, reason=""):
        """把 `(dataset, out_dir, rds_path, samples)` 喂给 `SpatialViolinAnalysis.set_context`

        ★ rds/out_dir 的解析**复用 `_resolve_gene_paths()`**（唯一真相源），
          本方法不再造第二套解析规则。
        ★ 取不到就**留痕返回 False**（不抛）：真正加载基因时会再同步一次。
        """
        try:
            an = self.violin_analysis
            if an is None:
                return False
            setter = getattr(an, 'set_context', None)
            if not callable(setter):
                self._log("⚠ SpatialViolinAnalysis 无 set_context → 小提琴上下文未同步")
                return False
            ds = self.dataset or self._dataset_name()
            if not ds:
                self._violin_log("⚠ 尚未确定数据集（请先在主页加载）→ 小提琴上下文未同步")
                return False
            self.dataset = ds
            self._ensure_analysis()
            rds, out_dir, perr = self._resolve_gene_paths()
            if not out_dir:
                self._violin_log("⚠ 解析输出目录失败：%s" % (perr or "未知原因"))
                return False
            samples = [str(x) for x in self._current_selected_ids()]
            if not samples:
                # ★ 双保险：任何调用点漏了守卫，这里也**不**把空列表交给 R
                #   （分析层的 `set_context` 把空当 NULL = 全部样本）。绝不静默。
                self._violin_log(self.VIOLIN_NO_SAMPLE_MSG)
                return False
            setter(ds, out_dir, rds or "", samples)
            if perr:
                self._violin_log("⚠ rds 未解析成功（%s）—— 加载基因时可能失败" % perr)
            if reason:
                self._log("小提琴上下文已同步（%s）：dataset=%s，样本 %d 个，rds=%s"
                          % (reason, ds, len(samples), rds or "（未解析）"))
            return True
        except Exception:
            traceback.print_exc()
            self._violin_log("⚠ 同步小提琴上下文时异常（见控制台 traceback）")
            return False

    def load_gene(self):
        """加载基因（第一步）：`analysis.load_gene` → 3 个 combo → main_list → 日志

        ★ **空选守卫**：一个样本都没选 ⇒ 直接拒绝（空列表交给 R = 全部样本）。
        """
        try:
            # ★ 先查样本池（它是 load_gene 的语义前提：小提琴按选中样本池化）
            if not self._violin_has_samples():
                return
            gene = self._violin_gene_input_text()
            if not gene:
                self._violin_log("请输入基因名再点『加载基因』")
                self._alert('error', "请输入基因名")
                return
            an = self.violin_analysis
            if an is None:
                self._violin_log("⚠ 小提琴分析层不可用（SpatialViolinAnalysis 未就绪，见控制台）")
                self._alert('failure', "小提琴分析层不可用")
                return
            self._sync_violin_context(reason="加载基因前")

            groups, n = an.load_gene(gene)
            groups = [str(g) for g in (groups or [])]

            for name in ('violin_main_combo', 'violin_filter1_combo', 'violin_filter2_combo'):
                self._set_violin_combo_items(getattr(self.ui, name, None), groups)

            self.on_main_combo_changed()
            self.on_filter1_combo_changed()
            self.on_filter2_combo_changed()

            self._violin_loaded = True
            self._violin_log("加载 %s 完成" % gene)
            self._violin_log("   行数(spot): %s" % n)
            self._violin_log("   可用注释: %d" % len(groups))
            self._violin_log("   分组列: %s" % (", ".join(groups) or "（无）"))
            self._log("【小提琴图】加载 %s：行数 %s，可用注释 %d 个（%s）"
                      % (gene, n, len(groups), ", ".join(groups) or "无"))
        except ValueError as e:
            traceback.print_exc()
            self._violin_log("❌ %s" % e)
            self._alert('error', str(e))
        except Exception as e:
            traceback.print_exc()
            self._violin_log("❌ 加载失败：%s: %s" % (type(e).__name__, e))
            self._alert('failure', "加载失败: %s" % e)

    def draw_violin_plot(self):
        """生成结果图：按单细胞同序读 16 个参数 → 三张图分别上屏

        ★ 入参形态与单细胞**逐字一致**：2 个位置参 + 13 个关键字（契约冻结）。
        ★ **空选守卫**：一个样本都没选 ⇒ 直接拒绝（`load_gene` 那条池化前提同样适用）。
        """
        try:
            # ★ 先查样本池（与 load_gene 同一守卫，文案共用 VIOLIN_NO_SAMPLE_MSG）
            if not self._violin_has_samples():
                return
            an = self.violin_analysis
            if an is None:
                self._violin_log("⚠ 小提琴分析层不可用（SpatialViolinAnalysis 未就绪）")
                self._alert('failure', "小提琴分析层不可用")
                return
            ui = self.ui
            main_combo = getattr(ui, 'violin_main_combo', None)
            if main_combo is None:
                self._violin_log("⚠ 布局未提供 violin_main_combo → 无法出图")
                self._alert('failure', "界面缺少主注释下拉框")
                return
            main_col = main_combo.currentText()
            main_list = getattr(ui, 'violin_main_list', None)
            selected_items = ([it.text() for it in main_list.selectedItems()]
                              if main_list is not None else [])

            filter1_col = None
            filter1_selected = []
            f1e = getattr(ui, 'violin_filter1_enable', None)
            if f1e is not None and f1e.isChecked():
                f1c = getattr(ui, 'violin_filter1_combo', None)
                f1l = getattr(ui, 'violin_filter1_list', None)
                filter1_col = f1c.currentText() if f1c is not None else None
                filter1_selected = ([it.text() for it in f1l.selectedItems()]
                                    if f1l is not None else [])

            filter2_col = None
            filter2_selected = []
            f2e = getattr(ui, 'violin_filter2_enable', None)
            if f2e is not None and f2e.isChecked():
                f2c = getattr(ui, 'violin_filter2_combo', None)
                f2l = getattr(ui, 'violin_filter2_list', None)
                filter2_col = f2c.currentText() if f2c is not None else None
                filter2_selected = ([it.text() for it in f2l.selectedItems()]
                                    if f2l is not None else [])

            tn = getattr(ui, 'violin_title_name', None)
            title_name = tn.text().strip() if tn is not None else None
            ts = getattr(ui, 'violin_title_size', None)
            title_size = ts.value() if ts is not None else 16
            yn = getattr(ui, 'violin_ylabel_name', None)
            ylabel_name = yn.text().strip() if yn is not None else None
            axs = getattr(ui, 'violin_axis_size', None)
            axis_size = axs.value() if axs is not None else 12
            pe = getattr(ui, 'violin_pairwise_enable', None)
            pairwise_enable = pe.isChecked() if pe is not None else True
            ps = getattr(ui, 'violin_pairwise_size', None)
            pairwise_size = ps.value() if ps is not None else 11

            pairwise_selected_pairs = []
            pl = getattr(ui, 'violin_pairwise_list', None)
            if pl is not None and pairwise_enable:
                pairwise_selected_pairs = [it.text() for it in pl.selectedItems()]

            pv = getattr(ui, 'violin_pvalue_mode', None)
            pvalue_mode = pv.currentIndex() if pv is not None else 0
            op = getattr(ui, 'violin_overall_pvalue', None)
            overall_pvalue = op.isChecked() if op is not None else False

            n, p1, p2, p3 = an.draw_violin_plot(
                main_col, selected_items,
                filter1_col=filter1_col, filter1_selected=filter1_selected,
                filter2_col=filter2_col, filter2_selected=filter2_selected,
                title_name=title_name,
                title_size=title_size,
                ylabel_name=ylabel_name,
                axis_size=axis_size,
                pairwise_enable=pairwise_enable,
                pairwise_size=pairwise_size,
                pairwise_selected_pairs=pairwise_selected_pairs,
                pvalue_mode=pvalue_mode,
                overall_pvalue=overall_pvalue)

            self._violin_log("筛选后 spot 数: %s" % n)
            self._display_violin_image(p1, 'violin_box')
            self._display_violin_image(p2, 'box')
            self._display_violin_image(p3, 'violin')
            self._violin_log("绘图完成")
            self._log("【小提琴图】筛选后 spot 数 %s → 三张图已上屏" % n)
        except ValueError as e:
            traceback.print_exc()
            self._violin_log("❌ %s" % e)
            self._alert('error', str(e))
        except Exception as e:
            traceback.print_exc()
            self._violin_log("❌ 绘图失败：%s: %s" % (type(e).__name__, e))
            self._alert('failure', "绘图失败: %s" % e)

    def _display_violin_image(self, fig_path, fig_type='violin_box'):
        """把图贴到对应小提琴页签 —— 优先 func 的 `display_violin_image`

        ★ 三个图型 → 三个 label 的映射与冻结顺序一致：
          `violin_box`→`violin_box_label` / `box`→`violin_box_only_label`
          / `violin`→`violin_only_label`。
        """
        try:
            fn = getattr(self.func, 'display_violin_image', None)
            if callable(fn):
                try:
                    fn(fig_path, fig_type)
                    return
                except Exception:
                    traceback.print_exc()
            label_map = {'violin_box': 'violin_box_label',
                         'box': 'violin_box_only_label',
                         'violin': 'violin_only_label'}
            label = getattr(self.ui, label_map.get(fig_type, ''), None)
            if label is None:
                self._log("⚠ 布局未提供 %s → %s 图无法上屏"
                          % (label_map.get(fig_type, fig_type), fig_type))
                return
            self._func_fallback('display_violin_image')
            pixmap = QPixmap(str(fig_path))
            if isinstance(label, ZoomableImageLabel):
                label.set_pixmap(pixmap)
            elif hasattr(label, 'setPixmap'):
                label.setPixmap(pixmap.scaled(label.size(), Qt.KeepAspectRatio,
                                              Qt.SmoothTransformation))
        except Exception:
            traceback.print_exc()

    # ---- 导出（照搬单细胞 `_do_export` / `export_plot_csv`）----------------
    def _get_save_file_path(self, title, default_name, filter_text):
        """保存对话框 —— 优先 func 的 `get_save_file_path`"""
        try:
            fn = getattr(self.func, 'get_save_file_path', None)
            if callable(fn):
                try:
                    return fn(title, default_name, filter_text)
                except Exception:
                    traceback.print_exc()
            self._func_fallback('get_save_file_path')
            path, _ = QFileDialog.getSaveFileName(self.parent, title, default_name, filter_text)
            return path or ""
        except Exception:
            traceback.print_exc()
            return ""

    def _get_export_size(self):
        """导出宽高 —— 优先 func 的 `get_export_size`，否则读两个 spinbox"""
        try:
            fn = getattr(self.func, 'get_export_size', None)
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    traceback.print_exc()
            self._func_fallback('get_export_size')
            w = getattr(self.ui, 'violin_export_width', None)
            h = getattr(self.ui, 'violin_export_height', None)
            return (float(w.value()) if w is not None else None,
                    float(h.value()) if h is not None else None)
        except Exception:
            traceback.print_exc()
            return None, None

    def _default_violin_gene(self):
        """导出默认名里的基因名（分析层的 `violin_gene` → 输入框 → 兜底 "violin"）"""
        try:
            gene = getattr(self.violin_analysis, 'violin_gene', None)
            if gene:
                return str(gene)
            gene = self._violin_gene_input_text()
            return gene or "violin"
        except Exception:
            traceback.print_exc()
            return "violin"

    def _do_export(self, ext, export_method):
        """通用导出（照搬单细胞：先判 `current_figs` 空 → 提示「请先绘图」）"""
        try:
            if not getattr(self.violin_analysis, 'current_figs', None):
                self._violin_log("请先绘图（当前没有任何小提琴图可导出）")
                self._alert('error', "请先绘图")
                return
            tabs = getattr(self.ui, 'violin_plot_tabs', None)
            current_tab = tabs.currentIndex() if tabs is not None else 0
            fig_type = {0: 'violin_box', 1: 'box', 2: 'violin'}.get(int(current_tab), 'violin_box')
            if not callable(export_method):
                self._violin_log("⚠ 分析层不支持导出 %s（export_%s 缺失）" % (ext.upper(), ext))
                self._alert('failure', "分析层不支持导出 %s" % ext.upper())
                return
            default_name = "%s_自定义小提琴图.%s" % (self._default_violin_gene(), ext)
            save_path = self._get_save_file_path("保存图片为%s" % ext.upper(), default_name,
                                                 "%s文件 (*.%s)" % (ext.upper(), ext))
            if not save_path:
                self._violin_log("已取消导出 %s（用户没有选择保存路径）" % ext.upper())
                return
            width, height = self._get_export_size()
            export_method(save_path, width, height, fig_type)
            self._violin_log("已导出 %s：%s（图型 %s，尺寸 %sx%s）"
                             % (ext.upper(), save_path, fig_type, width, height))
            self._alert('success', "图片已保存到:\n%s" % save_path)
        except Exception as e:
            traceback.print_exc()
            self._violin_log("❌ 导出 %s 失败：%s: %s" % (str(ext).upper(), type(e).__name__, e))
            self._alert('failure', "导出失败: %s" % e)

    def export_png(self):
        """导出PNG"""
        self._do_export('png', getattr(self.violin_analysis, 'export_png', None))

    def export_pdf(self):
        """导出PDF"""
        self._do_export('pdf', getattr(self.violin_analysis, 'export_pdf', None))

    def export_svg(self):
        """导出SVG"""
        self._do_export('svg', getattr(self.violin_analysis, 'export_svg', None))

    def export_plot_csv(self):
        """导出绘图CSV（先判 `filtered_df` 空；默认名 `<gene>_绘图数据.csv`）"""
        try:
            an = self.violin_analysis
            if an is None or getattr(an, 'filtered_df', None) is None:
                self._violin_log("请先绘图（还没有可导出的绘图数据）")
                self._alert('error', "请先绘图")
                return
            default_name = "%s_绘图数据.csv" % self._default_violin_gene()
            save_path = self._get_save_file_path("导出绘图数据为CSV", default_name,
                                                 "CSV文件 (*.csv)")
            if not save_path:
                self._violin_log("已取消导出绘图CSV（用户没有选择保存路径）")
                return
            fn = getattr(an, 'export_plot_csv', None)
            if not callable(fn):
                self._violin_log("⚠ 分析层无 export_plot_csv → 绘图数据未导出")
                self._alert('failure', "分析层不支持导出绘图CSV")
                return
            fn(save_path)
            self._violin_log("绘图数据已保存：%s" % save_path)
            self._alert('success', "绘图数据已保存到:\n%s" % save_path)
        except Exception as e:
            traceback.print_exc()
            self._violin_log("❌ 导出绘图CSV 失败：%s: %s" % (type(e).__name__, e))
            self._alert('failure', "导出失败: %s" % e)

    def bind_violin_mode(self):
        """小提琴**全部信号**（顺序与 `ui_bind_violin.py` 一致）

        ★ 控件缺失**不静默**：逐个列进日志（否则"某按钮点了没反应"查不出原因）。
        ★ 本方法名沿用表达页的历史命名（`bind_violin_mode`）；v11 之后本页**就是**
          小提琴页，"模式"二字只剩历史含义，方法名不改以免破坏既有调用点。
        """
        try:
            ui = self.ui
            frozen = ('violin_gene_input', 'btn_load_gene', 'violin_main_combo',
                      'violin_main_list', 'violin_filter1_enable', 'violin_filter1_combo',
                      'violin_filter1_list', 'violin_filter2_enable', 'violin_filter2_combo',
                      'violin_filter2_list', 'violin_log', 'violin_title_name',
                      'violin_title_size', 'violin_ylabel_name', 'violin_axis_size',
                      'violin_pairwise_size', 'violin_pairwise_enable', 'violin_pairwise_list',
                      'violin_overall_pvalue', 'violin_pvalue_mode', 'btn_draw_violin',
                      'violin_export_width', 'violin_export_height', 'btn_export_violin_png',
                      'btn_export_violin_pdf', 'btn_export_violin_svg',
                      'btn_export_violin_plot_csv', 'violin_plot_tabs', 'violin_box_label',
                      'violin_box_only_label', 'violin_only_label')
            missing = [n for n in frozen if getattr(ui, n, None) is None]
            if missing:
                self._log("⚠ 布局未提供 %d 个小提琴控件：%s（对应功能不可用）"
                          % (len(missing), ", ".join(missing)))

            for attr, slot in (('btn_load_gene', self.load_gene),
                               ('btn_draw_violin', self.draw_violin_plot),
                               ('btn_export_violin_png', self.export_png),
                               ('btn_export_violin_pdf', self.export_pdf),
                               ('btn_export_violin_svg', self.export_svg),
                               ('btn_export_violin_plot_csv', self.export_plot_csv)):
                w = getattr(ui, attr, None)
                if w is not None and hasattr(w, 'clicked'):
                    w.clicked.connect(slot)

            for attr, slot in (('violin_main_combo', self.on_main_combo_changed),
                               ('violin_filter1_combo', self.on_filter1_combo_changed),
                               ('violin_filter2_combo', self.on_filter2_combo_changed)):
                w = getattr(ui, attr, None)
                if w is not None and hasattr(w, 'currentIndexChanged'):
                    w.currentIndexChanged.connect(slot)

            for attr, slot in (('violin_filter1_enable', self.on_filter1_enable_changed),
                               ('violin_filter2_enable', self.on_filter2_enable_changed)):
                w = getattr(ui, attr, None)
                if w is not None and hasattr(w, 'stateChanged'):
                    w.stateChanged.connect(slot)

            # ★ 复刻单细胞 `bind_violin_functions` 末尾的三次初始刷新（此刻还没数据 ⇒ 空列表）
            self.on_main_combo_changed()
            self.on_filter1_combo_changed()
            self.on_filter2_combo_changed()
        except Exception:
            traceback.print_exc()


__all__ = ['SpatialViolinBind']
