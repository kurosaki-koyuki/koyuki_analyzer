# -*- coding: utf-8 -*-
"""
空转「初步分析」子页面 —— 逻辑与编排绑定脚本

职责（M2a/M3 契约 §2 Q2/Q2' + W1 冻结控件清单）：
  · **默认全不选（0 个样本）**（契约 Q2）：默认全选会每次进页面触发分钟级重算，与"秒开"冲突
  · 三个快捷按钮：`全选` / `选已审查高分（总分≥4★）` / `反选`
  · 读 `list_all_figures()`（**23 个图型**，不是审查页那 6 个）并核对
  · **只读现有图，不接 R 内核、不触发重跑**（那是 M2b）
  · 图不存在 → 一行提示 + 「去初步分析运行」按钮，**不阻塞、不报错、不空白**（契约 Q2'）

★ 本文件**不创建任何控件**：只用 W1 建好的 `sample_list` / `btn_sample_*` / `figure_views` /
  `figure_notes` / `figure_type_order` / `initial_tabs` / `initial_empty_hint` /
  `unreviewed_notice_panel` / `btn_initial_run` / `btn_initial_from_review` /
  `initial_log_text` / `sample_count_label`。

★★ 图位接口：**平铺 23 型**（方案 X，协调者裁决，无兼容别名）
  ```
  INITIAL_FIGURE_TYPES = [(figure_type, 中文名), ...]   # 23 项，布局类常量
  figure_views         : {figure_type: ZoomableImageLabel}   # 23 项
  figure_notes         : {figure_type: QLabel}               # 23 项
  figure_type_order    : [figure_type, ...]                  # 23 个 id，顺序 = 页签顺序
  ```
  **已删除**：`figure_slots` / `figure_slot_notes` / `INITIAL_FIGURE_GROUPS` / `SLOTS_PER_GROUP`。

  ★ 唯一真相源 = **`self.ui.figure_type_order`**（页签 i ↔ `figure_type_order[i]`，一一对应）。
    不用 manifest 的 `panel`/`panel_label` 去匹配 —— 两边是两套作者定义
    （manifest 按 panel 分 **9 组**，布局是**平铺 23 型**），用 panel_label 匹配会全错配。
  ★ 为什么不留"分组别名"：本会话已经因为"两个真相源"栽过两次
    （`figure_set_id` 两条计算路径 → 页面永远误报旧图集；`per_sample` 挂错位置 → 6 个图型全对不上）。
    **嵌套一层变平铺一层是化简，不是改造。**

★ 解码成本（协调者/W1 实测）：缩略图内存收益 351.6×，但**解码时间只省约 12%**
  （`setScaledSize(320)` 211.8 ms vs 全尺寸 241.3 ms —— Qt 的 PNG 解码仍要完整 zlib 解压）。
  逐样本 6 型 × 19 = 114 张 ≈ **24 秒**。
  ⇒ **按可见性触发**：`initial_tabs` 切到哪个页签就解**那一个**图型（惰性粒度 = 1 型 = 1 张），
    日志如实写"正在解码缩略图…"，**绝不一次性解码整页 23 张**。

★ `on_page_entered()`（协调者加在 `page_intersect.go_to_page_with_bind` 末尾的钩子）：
  **必须幂等** —— 记住 `(dataset, figure_set_id)`，没变就直接 return；
  否则每次进页面重解 114 张 ≈ 24 秒。
"""

import os
import time

from script.utils_layer.import_config import *
# ★ 显式 import：不依赖 import_config 的导出清单（本轮已第 3 次强调该踩坑面）
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
# ★ 显式 import：不依赖 import_config 的导出清单（本轮已第 3 次强调该踩坑面）
from PyQt5.QtWidgets import QFileDialog

from script.analyzer_layer.spatial_layer.spatial_review_layer import spatial_review_analysis as RA
from script.analyzer_layer.spatial_layer.spatial_initial_layer import spatial_export_analysis as SEA
from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as SREG
from script.analyzer_layer.spatial_layer.spatial_initial_layer.ui_func_spatial_initial import SpatialInitialFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.page_intersect import page_intersect
# 样本 id 解析唯一实现处（契约修订 R1 的取 id 侧；**禁止**再写 GSM 专属正则）
from script.utils_layer.sample_id_utils import extract_sample_id, sample_id_from_item


# =============================================================================
# 第 4 轮：结果区的「注释 / 总览」段 —— **全部取自图集现成文件**
# =============================================================================
# 用户第 4 轮原话要的三种图，图集里**都已经有了**（协调者逐行核对过
# `OUTPUT/GSE237183/_figure_manifest.csv`），所以这一段：
#   · **不跑 R**、**不产生新磁盘**、**不增加耗时**；
#   · 只读，**绝不写 `_figure_manifest.csv`**；
#   · 因此 `gene_cost_estimate()` 的预告里**绝不能把它们的体积/时间算进去**
#     （否则就是"预告一个用户根本不会付的代价"）。
ANNO_TOTAL_UMAP = "umap_sample_cluster"                  # 02_Clustering/02_UMAP_Sample_Cluster.png
ANNO_CELLTYPE_UMAP = "celltype_umap"                     # 07_CellTypeAnno/03_UMAP_celltype.png
ANNO_CELLTYPE_SPATIAL_PS = "celltype_spatial_persample"  # 07_CellTypeAnno/06_Spatial_per_sample/Spatial_<样本>.png
ANNO_TOTAL_UMAP_TITLE = "总UMAP（所有样本）"
ANNO_CELLTYPE_UMAP_TITLE = "总UMAP·细胞注释"
# ★ §15.5 的**第 24 个图型**：不是图集里的类型，而是「绘制区域」的产物（不带 spot 点）。
#   W1 会把它追加到 `INITIAL_FIGURE_TYPES`（23 → 24）；
#   而图集清单（`list_all_figures`）里**没有**它 ⇒ 它是**虚拟型**：
#   `figure_type_info[ft]` 与 `paths[ft]` 都查不到，路径要自己从 `09_RegionOverride/` 拼。
ANNO_CELLTYPE_NOSPOT = SREG.CELLTYPE_SPATIAL_NOSPOT
ANNO_CELLTYPE_NOSPOT_TITLE = "逐样本空间图（细胞类型·无点）"
# 「按样本取图 + 会被 override 替换」的那些型 —— 缓存令牌要多带一维"区域版本"，
# 否则区域变了这些页签不刷新（§14.3 v2 / §15.5 都要求跟着变）。
OVERRIDE_AWARE_TYPES = (ANNO_CELLTYPE_SPATIAL_PS, ANNO_CELLTYPE_NOSPOT)
# 结果区一条 strip 的两段（**顺序冻结**：注释段永远在前，基因段永远追加在后）
#   [总UMAP, 总UMAP·注释, 注释空间·样本1, 注释空间·样本2, …] + [基因结果…]
# 这样"点绘制表达量图"时只替换后一段，**前一段不会被清掉**。


class SpatialInitialBind:
    """初步分析子页面绑定类 - 全权负责粘合内外"""

    def __init__(self, main_window, ui_instance):
        self.parent = main_window
        self.ui = ui_instance
        self.func = SpatialInitialFunc(ui_instance, main_window)
        self.analysis = None

        self.dataset = None
        self.figures = {}                # list_all_figures() 的返回
        self._filling = False            # 状态字段（勿与 _is_filling() 同名）
        self._entered_key = None         # on_page_entered 幂等键 (dataset, figure_set_id)
        self._decoded_types = set()      # 已解码过的图型（惰性：1 型只解一次）
        # ① 修"图模糊"后每张都是**全分辨率**（实测最大 6000×3900 ≈ 89 MB），
        #    所以必须限制常驻张数（见 `_remember_full`）；2 = 当前 + 上一张。
        self._FULL_KEEP = 2
        self._full_resident = []         # 当前仍占着全尺寸 pixmap 的图型（LRU，最旧在前）
        self._selected = set()           # 当前选中的样本 id
        self._repr_is_fallback = False    # 逐样本组的代表样本是否是"未选样本时的回退"
        self._handling_selection = False  # 选择变化槽的重入守卫（Qt 会多次发 itemSelectionChanged）
        self._last_selection_ids = None   # 上次已处理的选中集合（用于去抖"空选择"中间态）
        self._selection_pending = False   # 是否已排队一次延后的选择处理（合并多次信号）

        # ⏱ 原「② 基因表达按需出图」的 8 个状态字段（`_gene_worker`/`_gene_timer`/
        #   `_gene_out_dir`/`_gene_stale_ids`/`_gene_genes`/`_gene_seen_progress`/
        #   `_gene_t0`）与「结果区两段式」的 5 个字段（`_gene_entries`/
        #   `_gene_pdf_entries`/`_gene_samples`/`_anno_cache`/`_tabs_signature`）
        #   **已随表达量页搬走（2026-09-20 第二轮拆页）**，本页不再有这些状态。

        self.init_bindings()
        self.refresh_all(reason="构造")

    # ==================================================================
    # 绑定
    # ==================================================================
    def init_bindings(self):
        """初始化所有绑定（每个槽自带 try/except，防 PyQt5 对未捕获异常 qFatal）"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_sample_buttons()
        self.bind_sample_list()
        self.bind_tabs()


    def bind_music_controls(self):
        try:
            if hasattr(self.ui, 'music_controller'):
                fix_music_controller_bindings(self, self.ui.music_controller)
        except Exception:
            traceback.print_exc()

    def bind_navigation(self):
        try:
            if hasattr(self.ui, 'nav_btn_back'):
                self.ui.nav_btn_back.clicked.connect(self._on_back_clicked)
            # 「去初步分析运行」→ 本页就是初步分析页；该按钮实际是**触发运行**（M2b 才接 R）
            if hasattr(self.ui, 'btn_initial_run'):
                self.ui.btn_initial_run.clicked.connect(self._on_run_clicked)
            if hasattr(self.ui, 'btn_initial_from_review'):
                self.ui.btn_initial_from_review.clicked.connect(self._on_from_review_clicked)
            self.bind_export()
        except Exception:
            traceback.print_exc()

    # ------------------------------------------------------------------
    # 第 5 轮：一键批量导出（4 个按钮；**复制逻辑全在 SEA，本层只管收集与报数**）
    # ------------------------------------------------------------------
    def bind_export(self):
        """`btn_export_all_*` → 一键导出本页（图集）全部图

        契约 §12.2 冻结的 4 个按钮名里，**基因那两对已随表达量页搬走**；
        按钮不存在时**留痕**（本会话纪律）。
        """
        try:
            # ★ 2026-09-20 拆页后：本页**只**导出"全部"（图集那批）；
            #   基因图的两对按钮（`btn_gene_export_*`）已随表达量页搬走。
            pairs = (('btn_export_all_png', 'all', 'png'),
                     ('btn_export_all_pdf', 'all', 'pdf'))
            for attr, scope, fmt in pairs:
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(
                        lambda _=False, s=scope, f=fmt: self._on_export_clicked(s, f))
                else:
                    self._log("⚠ 布局未提供 %s → 该导出入口未绑定" % attr)
        except Exception:
            traceback.print_exc()

    def _collect_export_items(self, scope, fmt):
        """收集要导出的 `[(显示名, 路径)]`（顺序 = 页签顺序，便于对照）

        · `scope='all'`（本页）= **当前图集 23 个图型的该格式全部文件**；
          逐样本型**含每个样本**（19 个样本就是 19 张/型）。
        · ⏱ `scope='gene'`（注释/总览段 + 基因段）**已随表达量页搬走**（2026-09-20 拆页）；
          本页收到其它 scope 时**留痕**并只返回已收集的部分。
        ★ 只收集路径，**不看文件在不在** —— 存在性判断与"跳过/失败"的账
          统一由 `SEA.batch_export` 记（一处记账，别两处各记一份）。
        ★★ §14.4：`scope='all'` 时，**有不过期 override** 的样本，其
          `celltype_spatial_persample` 一项**导出 override 文件**，显示名加 `（自定义分区）`
          ⇒ **用户导出的就是他看到的那一版**（页面显示与导出必须是同一版，
          否则用户拿到的图和屏幕上看到的不是一张，这在科研数据上不可接受）。
          判定同样只走 `SREG.override_png_for`（不写第二份规则）。
        """
        items = []
        try:
            key = 'pdf' if str(fmt).lower() == 'pdf' else 'png'
            figs = self.figures or {}
            paths = figs.get("paths") or {}
            ps_paths = figs.get("per_sample_paths") or {}
            info = figs.get("figure_type_info") or {}
            regions = self._regions_data_cached() if scope == 'all' else {}

            if scope == 'all':
                for ft in self._figure_types():
                    label = (info.get(ft) or {}).get("label") or ft
                    if ft == ANNO_CELLTYPE_NOSPOT:
                        # ★ §15.5：第 24 型是**虚拟型**（图集里没有），每个样本一张
                        #   `SpatialNoSpots_<样本>.png`；**只有 override 有效时才有文件**，
                        #   没有就跳过并留痕（`batch_export` 也会把"没有该格式路径"记进 skipped）。
                        wanted = 0
                        for sid in self._sample_ids():
                            ns_png, state = SREG.override_nospot_png_for(
                                self.dataset, sid, regions_data=regions)
                            if state != "ok":
                                continue
                            want = ns_png
                            if key == 'pdf':
                                ns_pdf = os.path.splitext(ns_png)[0] + ".pdf"
                                want = ns_pdf if os.path.isfile(ns_pdf) else ""
                            if want:
                                wanted += 1
                                items.append(("%s[%s·%s]%s" % (label, ft, sid,
                                                               SREG.OVERRIDE_SUFFIX_OK), want))
                        if wanted == 0:
                            self._log("导出：%s 一个可用的自定义分区都没有 → 跳过这一类"
                                      "（第 24 型只有画过并确认过的样本才有图）" % ft)
                        continue
                    p = (paths.get(ft) or {}).get(key)
                    if p:
                        items.append(("%s[%s]" % (label, ft), p))
                    # 逐样本型：**每个样本**都要
                    for sid, cell in (ps_paths.get(ft) or {}).items():
                        pp = (cell or {}).get(key)
                        name = "%s[%s·%s]" % (label, ft, sid)
                        if ft == ANNO_CELLTYPE_SPATIAL_PS:
                            ov_png, state = SREG.override_png_for(
                                self.dataset, sid, regions_data=regions)
                            if state == "ok":
                                if key == 'png':
                                    pp = ov_png
                                else:
                                    ov_pdf = os.path.splitext(ov_png)[0] + ".pdf"
                                    pp = ov_pdf if os.path.isfile(ov_pdf) else pp
                                name += SREG.OVERRIDE_SUFFIX_OK
                        if pp:
                            items.append((name, pp))
            else:
                # ⏱ `scope='gene'`（基因段）已随表达量页搬走 ⇒ 本页只处理 `'all'`。
                #   真收到别的 scope：**留痕**（不静默），返回已收集的部分。
                self._log("本页只导出图集全部（scope='all'），收到 scope=%r → 本次不收集"
                          % (scope,))
        except Exception:
            traceback.print_exc()
        return items

    def _on_export_clicked(self, scope, fmt):
        """选目录 → 批量复制 → **在日志里报数**（无图可导时如实提示，不静默）"""
        try:
            title = "导出全部%s" % str(fmt).upper()
            dest = ""
            try:
                dest = QFileDialog.getExistingDirectory(self.parent, title, "")
            except Exception:
                traceback.print_exc()
                self._log("⚠ 无法打开目录选择框（%s）" % title)
                return
            if not dest:
                self._log("已取消导出（%s）：用户没有选择目录" % title)
                return

            items = self._collect_export_items(scope, fmt)
            want_ext = "." + str(fmt).lower()
            usable = [x for x in items if str(x[1] or "").lower().endswith(want_ext)]
            self._log("=" * 40)
            self._log("【一键导出 · %s】候选 %d 项，其中 %s 格式 %d 项 → %s"
                      % (title, len(items), str(fmt).upper(), len(usable), dest))
            if not items:
                self._log("没有可导出的图：%s 里一张 %s 都没有（**没有静默跳过**）"
                          % ("当前图集清单" if scope == 'all' else "结果区（注释段+基因段）",
                             str(fmt).upper()))
                return
            if not usable:
                self._log("候选里没有任何 %s 文件（该格式这一批都没出）——未复制任何文件"
                          % str(fmt).upper())
                return

            res = SEA.batch_export(items, dest, fmt)
            summary, details = SEA.format_report(res)
            self._log(summary)
            for ln in details:
                self._log(ln)
            if not res.get("ok"):
                self._log("⚠ 导出未完成：%s" % (res.get("reason") or "未知原因"))
        except Exception:
            traceback.print_exc()
            self._log("⚠ 导出时异常（见日志）")

    # ------------------------------------------------------------------
    # ⏱ 原「② 大类切换（左侧导航按钮 → content_stack）」整段已**退休**
    #   （2026-09-20 第二轮拍板：「表达量分析」真拆成独立页面后，初始页不再有
    #    大类切换 —— `bind_category_nav` / `switch_category` / `_consume_pending_category`
    #    三个方法与其接线全部删除，别再照着这段注释去找它们）。
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # ③ + 第 4 轮 结果区：两段式（注释/总览段在前，基因段追加在后）
    # ------------------------------------------------------------------
    def _sorted_selected_ids(self):
        """当前选中的样本，按**样本号**排序（确定性）

        ★ 为什么必须排序：`_current_selected_ids()` 来自控件，而集合的迭代顺序
          在别处是不确定的；页签顺序若跟着 set 走，用户每次看到的顺序都可能不同。
          这里按 **manifest 顺序**（= 样本号顺序，GSM 号等宽）作主键，同名再按字符串。
        """
        try:
            sel = [str(x) for x in self._current_selected_ids()]
            rank = {sid: i for i, sid in enumerate(self._sample_ids())}
            return sorted(sel, key=lambda s: (rank.get(s, 10 ** 6), s))
        except Exception:
            traceback.print_exc()
            return []

    def _anno_missing(self, ft, title, path):
        """缺图**必须留痕**（本会话纪律：绝不静默跳过）"""
        if path:
            self._log("⚠ 注释/总览页签『%s』的图读不到：%s" % (title, path))
        else:
            self._log("⚠ 注释/总览页签『%s』缺少 figure_type『%s』（图集清单里没有它的 png）"
                      % (title, ft))

    def _anno_sources(self):
        """注释/总览段的**完整来源**：`[(标题, {'png':…, 'pdf':…}), ...]`

        顺序冻结：总UMAP → 总UMAP·注释 → 注释空间·样本1 → …

        ★ 这是注释段路径的**唯一计算处**；`_anno_entries()` 从它派生（只取 png），
          导出也用它（png 与 pdf 都要）—— 避免"页签一份逻辑、导出一份逻辑"，
          那种"两个真相源"本会话已经栽过两次。

        ★ 路径只从 `self.figures`（= `list_all_figures()` 的返回）里取：
            · 非逐样本型走 `paths[ft]['png'|'pdf']`；
            · 逐样本型走 `per_sample_paths[ft][样本号]['png'|'pdf']`（**已按样本号索引**，
              比"从文件名里切"稳得多），并用**已知样本清单**从文件名**交叉校验**一次
              （`sample_id_utils.extract_sample_id`，清单最长优先 + 词边界；
               旧写法 `GSM\\d+` 只认 GEO 编号，Dryad_UKF 的 `UKF*` 恒解析失败 ⇒
               这条交叉校验等于没有），不一致就报（防"路径与键错配"这种静默错图）。
        ★ 逐样本那段**只出当前选中的样本**；一个都没选 → 这段为空，
          **绝不退化成 19 个**（用户原话就是"选中的那几个样本"）。
        ★ 判定"有没有这张图"以 **png 为准**（页签要上屏的是 png）；
          pdf 只是**顺带记下来给导出用**，缺 pdf 不算这张图缺失
          （W3 的每基因 PDF 是新增能力，旧图集未必有）。
        """
        out = []
        try:
            figs = self.figures or {}
            paths = figs.get("paths") or {}
            ps_paths = figs.get("per_sample_paths") or {}
            import re

            def _cell(src):
                """取一项的 {png, pdf}（png 必须真实存在才算"有这张图"）"""
                png = (src or {}).get("png")
                pdf = (src or {}).get("pdf")
                if not (png and os.path.isfile(png)):
                    return None
                return {"png": png,
                        "pdf": pdf if (pdf and os.path.isfile(pdf)) else ""}

            # ① 总UMAP（所有样本）
            cell = _cell(paths.get(ANNO_TOTAL_UMAP))
            if cell:
                out.append((ANNO_TOTAL_UMAP_TITLE, cell))
            else:
                self._anno_missing(ANNO_TOTAL_UMAP, ANNO_TOTAL_UMAP_TITLE,
                                   (paths.get(ANNO_TOTAL_UMAP) or {}).get("png"))

            # ② 总UMAP·细胞注释
            cell = _cell(paths.get(ANNO_CELLTYPE_UMAP))
            if cell:
                out.append((ANNO_CELLTYPE_UMAP_TITLE, cell))
            else:
                self._anno_missing(ANNO_CELLTYPE_UMAP, ANNO_CELLTYPE_UMAP_TITLE,
                                   (paths.get(ANNO_CELLTYPE_UMAP) or {}).get("png"))

            # ③ 注释空间·<样本>（**只对选中的样本**）
            #    ★ §14.3：该样本有"不过期的自定义分区" ⇒ **优先显示 override**，
            #      并在标题里带后缀（`add_gene_result` 的说明行就用这个标题，
            #      W1 的签名没有单独的 note 参数）—— **绝不静默替换**。
            sel = self._sorted_selected_ids()
            d = ps_paths.get(ANNO_CELLTYPE_SPATIAL_PS) or {}
            if not sel:
                self._log("注释空间段为空：当前没有选中样本 → 只出两个『总』页签"
                          "（**不退化成 19 个**）")
            for sid in sel:
                atlas_cell = _cell(d.get(sid))
                cell, suffix = self._apply_override(sid, atlas_cell, reason="注释空间段")
                title = "注释空间·%s%s" % (sid, suffix)
                if not cell:
                    self._anno_missing(ANNO_CELLTYPE_SPATIAL_PS, title,
                                       (d.get(sid) or {}).get("png"))
                    continue
                # ★ 交叉校验用**统一解析**（已知样本清单最长优先），不再写死 `GSM\d+`：
                #   Dryad_UKF 的 `UKF*` 样本号在旧写法下恒解析失败 ⇒ 这条校验形同没有。
                found = extract_sample_id(os.path.basename(str(cell["png"])),
                                          self._sample_ids())
                if found and found != str(sid) and cell.get("source") != "override":
                    self._log("⚠ 注释空间图路径里的样本号(%s)与键(%s)不一致：%s"
                              % (found, sid, cell["png"]))
                out.append((title, cell))
        except Exception:
            traceback.print_exc()
        return out

    def _regions_data_cached(self):
        """缓存一份 `load_regions()`（同一页面生命周期内多次调用只读一次）

        ★ 为什么要缓存：§14.3 的判定会被"每个注释空间页签 × 每次重画"调用，
          每次都读一遍 JSON 是白费 I/O。缓存键 = `regions_version`（§14.3 第 4 条），
          所以**文件一变缓存自动失效**（不会读到旧的）。
        """
        try:
            if not self.dataset:
                return {}
            ver = SREG.regions_version(self.dataset)
            if getattr(self, '_regions_ver_cache', None) == ver and \
                    getattr(self, '_regions_cache', None) is not None:
                return self._regions_cache
            data = SREG.load_regions(self.dataset)
            self._regions_cache = data
            self._regions_ver_cache = ver
            return data
        except Exception:
            traceback.print_exc()
            return {}

    def _apply_override(self, sid, atlas_cell, reason="", nospot=False):
        """§14.3 / §15.5 的**唯一应用点**：返回 `(cell, suffix)`

        · `state == "ok"` → 用 override 的 png（pdf 也一起换），suffix = `（自定义分区）`
        · `state == "stale"/"expired"` → **图集版** + `（自定义分区尚未生成或已过期，…）`
        · `state == "no_regions"` → 图集版、**无后缀**
        · override 的 png 存在但 pdf 缺 → pdf 退回图集版（缺 pdf 不算"这张图没有"）
        · `nospot=True`（§15.5 第 24 型）→ 用**不带点**那张的判定；
          它**没有图集版可退**（所以调用方传 `{}` 当 atlas_cell），
          非 `ok` 时返回空 cell ⇒ 调用方显示"该图尚未生成"，**绝不拿带点版冒充**。
        ★ 判定规则**只在 `SREG` 里实现一次**，这里不再写第二份。
        """
        try:
            cache = self._regions_data_cached()
            if nospot:
                ov_png, state = SREG.override_nospot_png_for(self.dataset, sid,
                                                            regions_data=cache)
            else:
                ov_png, state = SREG.override_png_for(self.dataset, sid, regions_data=cache)
            suffix = SREG.override_note_suffix(state)
            if state == "ok":
                ov_pdf = os.path.splitext(ov_png)[0] + ".pdf"
                cell = {"png": ov_png,
                        "pdf": ov_pdf if os.path.isfile(ov_pdf) else ((atlas_cell or {}).get("pdf") or ""),
                        "source": "override"}
                self._log("%s：样本 %s 显示**自定义分区**图（%s）"
                          % (reason or "override", sid, ov_png))
                return cell, suffix
            if suffix:
                self._log("⚠ %s：样本 %s 有区域但自定义分区不可用（%s）→ %s，并加后缀提示"
                          % (reason or "override", sid, state,
                             "该页签显示『该图尚未生成』" if nospot else "**显示图集版**"))
            return ({} if nospot else atlas_cell), suffix
        except Exception:
            traceback.print_exc()
            return ({} if nospot else atlas_cell), ""

    def _anno_entries(self):
        """注释/总览段页签用的 `[(标题, png路径)]`（从 `_anno_sources()` 派生）

        ★ 保持这个**形状不变**：页签渲染、注释段比对、导出之外的地方都读它。
        """
        try:
            return [(t, d.get("png")) for t, d in self._anno_sources() if d.get("png")]
        except Exception:
            traceback.print_exc()
            return []



    def bind_sample_buttons(self):
        try:
            pairs = (('btn_sample_all', self._on_select_all_clicked),
                     ('btn_sample_high_score', self._on_select_high_score_clicked),
                     ('btn_sample_invert', self._on_select_invert_clicked))
            for attr, handler in pairs:
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(handler)
        except Exception:
            traceback.print_exc()

    def bind_sample_list(self):
        try:
            lst = getattr(self.ui, 'sample_list', None)
            if lst is not None and hasattr(lst, 'itemSelectionChanged'):
                lst.itemSelectionChanged.connect(self._on_sample_selection_changed)
        except Exception:
            traceback.print_exc()

    def bind_tabs(self):
        """页签切换 → 该**图型**首次可见时才解码（惰性，绝不一次解 23 张）

        ⚠ W1 的 `WrappingTabStrip` 对外暴露 QTabWidget 的那一小撮 API
          （`currentChanged` / `currentIndex` / `count` / `setCurrentIndex` …），
          所以这里按 QTabWidget 的用法连信号是安全的。
        ⚠ `setCurrentIndex(i)` 会**发 `currentChanged`**（Qt 语义）—— 我们没有任何
          地方在 `_on_tab_changed` / `_decode_index` 里回写 `setCurrentIndex`，
          且 `_is_filling()` 守卫盖住了"程序化填表"那条路，不会回环。
        """
        try:
            tabs = getattr(self.ui, 'initial_tabs', None)
            if tabs is not None and hasattr(tabs, 'currentChanged'):
                tabs.currentChanged.connect(self._on_tab_changed)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 取数（契约：从 main_window.spatial_top_bind.analysis 读，getattr 守卫）
    # ==================================================================
    def _top_bind(self):
        try:
            return getattr(self.parent, 'spatial_top_bind', None)
        except Exception:
            traceback.print_exc()
            return None

    def _resolve_analysis(self):
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
                a2 = getattr(top, 'analysis', None)
                if a2 is not None:
                    return getattr(a2, 'dataset_name', None)
            return None
        except Exception:
            traceback.print_exc()
            return None

    # ==================================================================
    # 进入页面的钩子（page_intersect 在 go_to_page_with_bind 末尾调用）
    # ==================================================================

    def on_page_entered(self):
        """每次跳转到本页时由 `page_intersect` 调用（可选钩子）

        ★ **必须幂等**：幂等键 = `(dataset, figure_set_id, review_version)`。
          本页一次刷新可能要解码 23 张全分辨率图，不幂等会让用户每次进页面都等十几秒。

        ★★ 第三项 `review_version` 是**需求④**加的（2026-09，用户第二轮实测报的 bug）：
          · 原键只有 `(dataset, figure_set_id)`，而 **`figure_set_id` 只反映图集**，
            评分/备注的变化**完全不在键里**。
          · 症状（用户原话「我在审查页面更新的审查结果没法实时同步到初步分析里…
            只有在我退出程序重启后才更新」）：审查页打分 → 回本页 → 键没变 →
            跳过刷新 → `⚠未审` 角标 / `已审查 N/19` / ⑥ 的备注悬停提示**全是旧的**。
          · `review_version` = `RA.review_version(dataset)` = `(mtime_ns, size)`；
            `save_review_scores` 走 `os.replace` 原子替换 ⇒ 每次保存 mtime 必变。
        ★ 幂等性**没有退化**（用户明确要求保住）：没人动过 review.json 时
          `review_version` 不变 ⇒ 键不变 ⇒ 直接 return，**一张图都不重解**。
        """
        try:
            dataset = self._dataset_name()
            if not dataset:
                self._log("【初步分析】进入页面，但顶层页尚未加载数据集 → 请先回主页加载")
                if hasattr(self.func, 'log'):
                    self.func.log("请先在主页加载数据集")
                return
            current_id = RA.figure_set_id(dataset)
            rv = RA.review_version(dataset)
            # ★ §14.3 第 4 条：把 `regions.json` 的 `(mtime_ns, size)` **并入既有幂等键**。
            #   为什么必须：改了区域（或刚确认出 override）后回本页，
            #   若键不变就会跳过刷新 → 概览页 still 显示图集版/旧 override。
            #   为什么放**第 4 位**：前三位 `(dataset, figure_set_id, review_version)`
            #   的形状与语义保持不变（别的代码/测试按索引读它们）。
            rv_regions = SREG.regions_version(dataset)
            key = (dataset, current_id, rv, rv_regions)
            if key == getattr(self, '_entered_key', None):
                self._log("【初步分析】进入页面（%s / %s / 评分版本 %s / 区域版本 %s 均未变，"
                          "跳过刷新，不重新解码）" % (dataset, current_id, rv, rv_regions))
                return
            self._log("【初步分析】进入页面：%s（图集 %s，评分版本 %s，区域版本 %s）"
                      % ("幂等键变化 → 刷新" if getattr(self, '_entered_key', None) else "首次",
                         current_id, rv, rv_regions))
            self._entered_key = key
            self.refresh_all(reason="进入页面（on_page_entered）")
        except Exception:
            traceback.print_exc()   # 内部兜底，绝不外抛

    # ==================================================================
    # 主刷新
    # ==================================================================
    def refresh_all(self, reason=""):
        try:
            self._log("=" * 40)
            self._log("【初步分析】%s" % (reason or "刷新"))

            an = self._resolve_analysis()
            if an is None:
                self._set_empty_hint("无法获取空转数据（顶层页未就绪）")
                return
            dataset = self._dataset_name()
            if not dataset:
                self._log("顶层页尚未加载数据集 → 请先回主页加载数据集")
                self._set_empty_hint("请先在主页加载数据集")
                return
            self.dataset = dataset
            self._log("数据集: %s" % dataset)

            # ① 全量图清单（23 个图型）
            self.figures = RA.list_all_figures(dataset)
            if not self.figures.get("ok"):
                self._log("读取图清单失败: %s" % self.figures.get("reason"))
                self._set_empty_hint("读不到图清单：%s" % (self.figures.get("reason") or "未知"))
                return
            types = list(self.figures.get("figure_types") or [])
            # ★ §15.5：布局里现在是 **24** 个页签（图集 23 + 虚拟型 `celltype_spatial_nospot`）。
            #   而 `list_all_figures()` 只能给出图集的 23 个 ⇒ 若直接把 23 交给
            #   `verify_figure_types`，W1 的 func 会把第 24 个当成"数据里没有"→
            #   **`set_slot_visible(..., False)` 把第 24 页签藏掉**（契约明确要它显示）。
            #   ⇒ 这里把虚拟型**显式声明为"有"**（它的可用性不依赖图集，永远存在）。
            declared = types + ([] if ANNO_CELLTYPE_NOSPOT in types else [ANNO_CELLTYPE_NOSPOT])
            self._log("图型：图集 %d 个 + 虚拟型 %s = 声明 %d 个（初步分析页期望 24 个页签）"
                      % (len(types),
                         "1 个" if ANNO_CELLTYPE_NOSPOT in declared else "0 个",
                         len(declared)))

            # ② 图型核对（**差异由我打日志，绝不静默**）
            try:
                checked = self.func.verify_figure_types(declared)
                if isinstance(checked, tuple) and len(checked) == 3:
                    matched, extra, missing = checked
                    if extra or missing:
                        self._log("⚠ 图型不一致：多出 %s / 缺少 %s" % (list(extra), list(missing)))
                    else:
                        self._log("图型核对通过：一致（%d 个）" % len(declared))
                else:
                    self._log("⚠ verify_figure_types 返回形状异常: %r" % (checked,))
            except Exception:
                traceback.print_exc()

            # ③ 样本列表（**默认全不选**，契约 Q2）
            self._fill_sample_list()
            self._apply_selection()

            # ④ 图：只解码**当前页签那组**
            self._decode_current_group()
            self._sync_hint()
            # ⑤ 结果区：注释/总览段 + 基因段（第 4 轮）
            #    ★ 刷新时机之一 —— 数据集加载后 / 进页面时；**不等基因绘制**
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 样本选择
    # ==================================================================
    def _sample_ids(self):
        try:
            return list(self.figures.get("samples") or [])
        except Exception:
            return []

    def _fill_sample_list(self):
        """填充样本列表；**默认全不选**（契约 Q2）"""
        try:
            samples = []
            for sid in self._sample_ids():
                label = self._sample_label(sid)
                samples.append({"id": sid, "label": label,
                                "reviewed": RA.review_state(sid, self._review_scores()) == "scored",
                                "total": self._total_of(sid)})
            try:
                # selected_ids 不传 → W1 的 func 按"默认全不选"处理
                self.func.set_sample_items(samples)
            except TypeError:
                self.func.set_sample_items(samples, [])
            except Exception:
                traceback.print_exc()
            self._log("样本清单: %d 条（默认全不选）" % len(samples))
            # ★ 需求⑥：鼠标悬停样本 → 小框显示审查时写的备注。
            #   必须紧跟在 set_sample_items 之后：那只函数会 clear() 重建全部 item，
            #   任何在它之前设的 tooltip 都会被丢掉。这里也是**唯一**的重建路径
            #   （refresh_all / 主题刷新都走 _fill_sample_list），所以不会漏。
            self._apply_sample_tooltips()
        except Exception:
            traceback.print_exc()

    def _apply_sample_tooltips(self):
        """把「样本备注」挂到样本列表每一项的悬停提示上（需求⑥）

        ★ 备注为空 → **显式清空** tooltip。不清空的话，同一个 item 复用时会留着
          上一个样本的备注（QListWidget.clear() 会毁 item，但主题重刷路径不保证），
          显示错的备注比不显示更糟。
        ★ 备注是 W2 数据层（review.json → samples[sid]['note']）的唯一真相源，
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

    def _sample_label(self, sid):
        """显示名的尾部（去掉开头样本号，避免与 sid 重复 —— 与审查页同一处理）"""
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

    def _on_select_all_clicked(self):
        try:
            self._selected = set(self._sample_ids())
            self._apply_selection()
            self._log("全选：%d 个样本" % len(self._selected))
            # ★ 第 4 轮补漏：`_apply_selection()` 用 `_filling` 压掉了控件信号，
            #   所以**必须显式**走一次"选中已定稿" —— 否则注释空间段不会跟着变成 19 个。
            self._commit_selection(self._current_selected_ids(), "快捷选择：全选")
        except Exception:
            traceback.print_exc()

    def _on_select_high_score_clicked(self):
        """选「已审查且总分 ≥4★」的样本（用 RA.reviewed_high_score_samples）"""
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
        """把 `self._selected` 同步到 UI（逐个 setSelected，带 _is_filling 防回环）"""
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
                    # ★ 统一口径：先读 UserRole（W1 建列表时已写真实 id），再按清单解析文本。
                    #   旧写法 `re.search(r'(GSM\d+)', item.text())` 只认 GEO 编号，
                    #   Dryad_UKF 的 `UKF*` 恒取不到 ⇒ 勾选状态同步静默失效。
                    sid = sample_id_from_item(item, self._sample_ids())
                    if not sid:
                        continue
                    try:
                        item.setSelected(sid in self._selected)
                    except Exception:
                        pass
            finally:
                self._filling = False
            self._refresh_count()
        except Exception:
            traceback.print_exc()

    def _refresh_count(self):
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

    def _per_sample_types(self):
        """返回**逐样本型**的 figure_type 集合（**自动判定，不硬编码那 6 个字符串**）

        判据：该 `figure_type` 在 `list_all_figures()['figure_type_info']` 里
        `per_sample=True`（该布尔来自 `artifacts[].per_sample`，不是硬编码名单 ——
        实测 `per_sample` 挂在 `artifacts[]` 上，写错位置会让你以为 6 个图型全对不上）。

        平铺 23 型之后，判定的粒度自然从"哪些**组**含逐样本图"变成"哪些**图型**是逐样本型"。
        """
        try:
            info = (self.figures or {}).get("figure_type_info") or {}
            return set(t for t in self._figure_types() if self._is_per_sample_type(t))
        except Exception:
            traceback.print_exc()
            return set()

    def _repr_sample(self, selected_ids=None):
        """逐样本组出图用的"代表样本"

        取值顺序：
          ① 选中集合里按 **manifest 顺序**的第一个（稳定、确定）；
          ② ★ **一个都没选时回退为 manifest 的第一个样本**（`self._sample_ids()[0]`）。
             为什么必须回退：契约 Q2 定了"**默认全不选**"，若这里返回 None，
             逐样本组 6 个图位会全空并显示"该格尚未生成"——**
             把"我还没输入"说成了"数据没有"**，用户第一眼会以为图没出/报 bug
             （而这 6 张其实都在 `per_sample_paths` 里）。
             回退后首次进入就有 6 张可看，**并置 `self._repr_is_fallback` 以便如实标注**。
        ⚠ 一致性要求：`_fill_type` 与失效判定**必须同源**调本函数，
          否则会出现"失效判定认为变了、取图却仍取旧样本"的脱节。
        """
        try:
            ids = list(selected_ids) if selected_ids is not None else list(self._current_selected_ids())
            chosen = set(ids)
            order = self._sample_ids()
            for sid in order:
                if sid in chosen:
                    self._repr_is_fallback = False
                    return sid
            # 未选任何样本 → 回退 manifest 第一个，并记标记
            fallback = order[0] if order else None
            self._repr_is_fallback = bool(fallback)
            return fallback
        except Exception:
            traceback.print_exc()
            return None

    def _on_sample_selection_changed(self):
        """用户在列表里直接点选 → **合并后**再处理（防 Qt 多次发信号）

        ⚠⚠ 为什么必须"延后合并"而不是"进入时比较集合"：
          `clearSelection()` 会**先发一次"空选择"信号**，随后 `setSelected()` 再发一次。
          若在进入时就跟 `_last_selection_ids` 比较并**丢弃**，
          "空选择"那次会把基线更新成空集 → 真正的选择那次被误判为"无变化"而**被吞掉**
          （实测：改选样本后新增解码 = 0，图不跟随 —— 等于 bug 又回来了）。
          → 正解：用 `QTimer.singleShot(0, …)` 把处理**推到事件循环下一轮**，
            这样一次用户操作产生的多次信号会被**合并成一次**处理，
            且比较发生在"选择已经稳定"之后。
        """
        if self._is_filling() or self._handling_selection:
            return
        try:
            from PyQt5.QtCore import QTimer
            if getattr(self, '_selection_pending', False):
                return                      # 已排队，再来的信号直接丢（合并）
            self._selection_pending = True
            QTimer.singleShot(0, self._process_selection_change)
        except Exception:
            traceback.print_exc()

    def _commit_selection(self, cur, source=""):
        """一次"选中已定稿"的收口：**陈旧基因图失效** + 重画结果区

        Returns:
            bool: 选中集合是否**真的变了**（`prev is None` 的首次观察算"没变"）

        ## ⏱ 原来这里还有一段"选择变了 ⇒ 让**基因段**失效"的逻辑
          （2026-09-20 拆页前的缺陷修复：基因图按某几个样本画出，选中集是它的语义前提，
           旧实现只在"绘制前清空 / 收图后赋值"两处变过 ⇒ 改选样本后基因段还挂在旧样本上）。
          **该失效逻辑现在归「表达量分析」页**（它自己的 `_process_selection_change` 负责），
          本页已无基因段可失效 —— 保留这段 ⏱ 说明是为了不让后来者以为漏了这条边界。

        ## 三条边界（都不能误清）
          1. `prev is None`（首次观察，例如进页面首次填充）→ **不清**：
             那是"从无到有"，不是"用户改了选择"。
          2. `cur == prev`（进页面 / 切大类 / `refresh_all` / 主题刷新）→ **不清**：
             这些路径都会走到这里，但它们没有改变选择。
          3. 只有 `prev is not None and cur != prev` → 清，**并且必须留痕**：
             静默清空会让用户以为"图丢了是 bug"。
        """
        try:
            cur = set(str(x) for x in (cur or []))
            prev = getattr(self, '_last_selection_ids', None)
            changed = (prev is not None) and (cur != prev)
            self._last_selection_ids = set(cur)
            self._selected = cur
            # ⏱ 原来这里还有一段"样本选择变了 ⇒ 清掉旧基因图"的逻辑：
            #   基因图现在归**表达量页**（那边的 `_process_selection_change` 自己会清），
            #   本页没有基因图可作废。
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
            # ★ 不再手工"失效 + 判断代表样本是否变" —— 直接让**自校验缓存**决定：
            #   `_decode_index` 会比对"该图型解码时用的代表样本"与"当前代表样本"，
            #   一致则跳过、不一致则重解。这样与信号时序彻底解耦。
            try:
                tabs = getattr(self.ui, 'initial_tabs', None)
                idx = tabs.currentIndex() if (tabs is not None
                                              and hasattr(tabs, 'currentIndex')) else -1
                if idx >= 0:
                    self._decode_index(idx)
            except Exception:
                traceback.print_exc()
            self._sync_hint()
            # ★ 刷新时机之二 —— **样本选择变化后**重建注释/总览段
            #   （用户第 4 轮：注释空间图"就是选中的那几个样本"），
            #   并让"给旧样本画的基因图"失效（`_commit_selection` 的三条边界见其 docstring）。
            self._commit_selection(cur, "样本选择变化")
        except Exception:
            traceback.print_exc()
        finally:
            self._handling_selection = False

    # ==================================================================
    # 图：惰性按图型解码（平铺 23 型）
    # ==================================================================
    def _figure_types(self):
        """★ **唯一真相源 = `self.ui.figure_type_order`**（页签 i ↔ order[i]，一一对应）

        实测两边是两套作者定义：manifest 按 `panel` 分 **9 组**，W1 布局是**平铺 23 型**
        → 用 `panel_label` 匹配会**23 个图位全错配**，所以只认布局自己暴露的顺序表。

        为什么不用 `figure_views.keys()`：dict 的键顺序虽然在新版 Python 里是插入序，
        但**契约里的顺序真相源就是 `figure_type_order`**（= `INITIAL_FIGURE_TYPES` 的
        figure_type 列 = 页签顺序）。用 keys() 是"碰巧也对"，属于第二个真相源。
        """
        try:
            order = getattr(self.ui, 'figure_type_order', None)
            if isinstance(order, (list, tuple)) and len(order):
                return [str(t) for t in order]
            views = getattr(self.ui, 'figure_views', None)
            self._log("⚠ 布局未暴露 figure_type_order（figure_views 有 %d 项），无法按页签取图型"
                      % (len(views) if isinstance(views, dict) else 0))
            return []
        except Exception:
            traceback.print_exc()
            return []

    def _on_tab_changed(self, idx):
        if self._is_filling():
            return
        try:
            self._decode_index(int(idx))
        except Exception:
            traceback.print_exc()

    def _decode_current_group(self):
        try:
            tabs = getattr(self.ui, 'initial_tabs', None)
            idx = tabs.currentIndex() if (tabs is not None and hasattr(tabs, 'currentIndex')) else 0
            self._decode_index(max(0, idx))
        except Exception:
            traceback.print_exc()

    def _decode_index(self, idx):
        """只解码第 idx 个页签那**一个图型**（**首次可见时解**；逐样本型在代表样本变化时重解）

        ★★ **自校验缓存**（取代早先"靠信号失效"的写法）：
          记录 `_decoded_repr[figure_type] = 该图型解码时用的代表样本`。
          判定"能否复用"时**同时**看：
            ① 该图型是否解过；② 若它是逐样本型，则**当时用的代表样本是否等于当前代表样本**。
          不等就重解（并更新记录）。
          好处：**不依赖 `itemSelectionChanged` 的信号时序**——无论选择是通过
          `setSelected` / `setCurrentRow` / 程序化 `_apply_selection` 哪条路改的、
          中间发了几次信号，只要代表样本不一致就一定会重解。
          这是本轮反复踩"选择改了但图没变"之后采取的做法：**把正确性放在缓存判定里，
          而不是放在信号链上**。

        ★ 平铺 23 型后**惰性粒度 = 1 型 = 1 张**（旧布局里 6 个逐样本型挤在同一个"逐样本"组，
          改选样本要重解 6 张；现在只看可见的那一个页签，切到别的逐样本页签时按同样的
          判定各自重解）。这比"一次重解 6 张"更省，且**正确性不变**：
          旧的 `_decoded_repr` 判定原封不动地搬到了 per-figure_type 这一层。
        """
        try:
            order = self._figure_types()
            if not order or idx < 0 or idx >= len(order):
                return
            ft = order[idx]
            is_ps = self._is_per_sample_type(ft)
            cur_repr = self._repr_sample() if is_ps else None
            # ★ 缓存令牌：**逐样本型多加一维"区域版本"**（§14.3 第 4 条）
            #   为什么必须：`celltype_spatial_persample` 这张图会被 override **替换掉**。
            #   若缓存只认"代表样本"，那么"区域没变、图却该换了"就永远不触发
            #   → 用户画完区域回概览页还是看到图集版（§14.1 缺口 2 复发）。
            cur_token = self._decode_token(ft, cur_repr)
            was_repr = (getattr(self, '_decoded_repr', {}) or {}).get(ft, "__NEVER__")
            already = ft in self._decoded_types
            if already and (not is_ps or was_repr == cur_token):
                self._log("图型『%s』已解码过且令牌未变（%s），跳过（不重复解码）"
                          % (ft, cur_token if is_ps else "非逐样本"))
                return
            if already and is_ps:
                self._log("图型『%s』令牌 %s → %s，按新选择/新区域重解"
                          % (ft, was_repr, cur_token))
            self._fill_type(ft)
            self._decoded_types.add(ft)
            if not hasattr(self, '_decoded_repr') or self._decoded_repr is None:
                self._decoded_repr = {}
            self._decoded_repr[ft] = cur_token if is_ps else "__STATIC__"
            self._remember_full(ft)
        except Exception:
            traceback.print_exc()

    def _is_per_sample_type(self, ft):
        """该图型是否"按样本取图"

        ★ §15.5 的第 24 型（`celltype_spatial_nospot`）是**虚拟型**：
          `figure_type_info` 里没有它，所以不能只靠 `per_sample` 布尔判断 ——
          但它**确实是逐样本的**（每个样本一张 `SpatialNoSpots_<样本>.png`）。
          漏掉这一条 ⇒ `_fill_type` 会走"非逐样本"分支去查 `paths[ft]` → 永远 None
          ⇒ 第 24 页签永远是"该格尚未生成"（正是契约要求"没有 override 才显示未生成"之外的情况）。
        """
        try:
            if ft in OVERRIDE_AWARE_TYPES:
                return True
            info = (self.figures or {}).get("figure_type_info") or {}
            return bool((info.get(ft) or {}).get("per_sample"))
        except Exception:
            traceback.print_exc()
            return False

    def _decode_token(self, ft, cur_repr):
        """逐样本型的**缓存令牌**：一般就是代表样本；会被 override 替换的型再加区域版本

        ★ 只有"会被 override 替换的那几个型"需要多这一维，其余保持原样
          （令牌越窄，无谓重解越少）。§15.5 的虚拟型也要带上，否则区域变了它不刷新。
        """
        try:
            if ft in OVERRIDE_AWARE_TYPES:
                return (cur_repr, SREG.regions_version(self.dataset)
                        if self.dataset else ("none", 0))
            return cur_repr
        except Exception:
            traceback.print_exc()
            return cur_repr

    def _remember_full(self, ft):
        """记下"这个图型现在还占着一张**全尺寸** pixmap"，并把常驻张数压到 ≤ `_FULL_KEEP`

        ★ 为什么必须做：① 修好之后每张图都是**全分辨率**（最大实测 6000×3900 ≈ 89 MB），
          23 个页签全解一遍就是 2 GB 级常驻。用户机器再大也不该这么吃。
        ★ 为什么"清 slot"必须和"清 `_decoded_types`"**成对**：
          `_decode_index` 的跳过条件是 `already = ft in self._decoded_types`。
          只清 slot 不清记录 → 切回去时判定"已解码过、代表样本没变" → **跳过填充** →
          图位是空的（用户看到黑图）。所以这里两个一起清，切回去会老老实实重解。
        ★ 保留 `_FULL_KEEP` 张而不是 1 张：来回切一次不用重解，解码一次约 0.24 s。
        """
        try:
            keep = getattr(self, '_FULL_KEEP', 2)
            lst = getattr(self, '_full_resident', None)
            if lst is None:
                lst = []
                self._full_resident = lst
            if ft in lst:
                lst.remove(ft)
            lst.append(ft)
            while len(lst) > keep:
                old = lst.pop(0)
                if old == ft:
                    continue
                try:
                    self.func.clear_slot(old)
                except Exception:
                    traceback.print_exc()
                self._decoded_types.discard(old)
                if getattr(self, '_decoded_repr', None):
                    self._decoded_repr.pop(old, None)
                self._log("释放上一张全尺寸图（%s）—— 常驻全尺寸 ≤ %d 张" % (old, keep))
        except Exception:
            traceback.print_exc()

    def _fill_type(self, ft):
        """填充**一个**图型对应的图位（**全分辨率**；缺图如实提示）

        ★ 为什么是 `thumbnail=False`（用户第二轮实测报的"图模糊"）：
          `SpatialInitialFunc.THUMB_SIZE = 320`，缩略图走 `QImageReader.setScaledSize(320)`；
          而 `ZoomableImageLabel.scale_factor = min(scale_x, scale_y, **1.0**)`
          —— **只缩不放**。于是 320 px 的位图被摆在约 1372 px 的图位里，
          既小又糊（源图其实是 3000×3750 ~ 6000×3900，白白丢掉一个数量级的像素）。
          ⇒ 初步分析页的图位是"单张铺满"的，必须按**原始分辨率**解码。
        ★ 全尺寸的内存由 `_remember_full()` 压到常驻 ≤ `_FULL_KEEP`（=2）张。
        ★ 页面级日志里不再写"缩略图"（那是旧行为的措辞，留着会误导排障）。
        """
        try:
            views = getattr(self.ui, 'figure_views', None) or {}
            notes = getattr(self.ui, 'figure_notes', None) or {}
            view = views.get(ft)
            note = notes.get(ft)
            if view is None:
                self._log("⚠ 图型『%s』在布局里没有对应图位（figure_views 里没有这个 id）" % ft)
                return
            paths = self.figures.get("paths") or {}
            ps_paths = self.figures.get("per_sample_paths") or {}
            info = self.figures.get("figure_type_info") or {}

            meta = info.get(ft) or {}
            is_ps = self._is_per_sample_type(ft)
            self._log("正在解码图像…（图型『%s』，全分辨率）—— 逐张惰性，绝不整页预解" % ft)

            # 代表样本只取一次（`_fill_type` 与失效判定必须同源调 `_repr_sample()`，
            # 否则会出现"失效判定认为变了、取图却仍取旧样本"的脱节）
            repr_sid = self._repr_sample() if is_ps else None
            is_fallback = bool(getattr(self, '_repr_is_fallback', False))
            if is_ps:
                if is_fallback:
                    self._log("（未选样本，暂显示 %s；在左侧选中样本后按你的选择显示）" % repr_sid)
                else:
                    self._log("逐样本图型代表样本 = %s" % repr_sid)

            # ★ §14.3 / §15.5：这两个"按样本 + 会被 override 替换"的型要**优先显示自定义分区**
            #   （否则用户画完区域、回概览页却看到图集版 ⇒ 与"注释空间图直接跟着
            #     我画的区域走"不符）。说明行 = `figure_notes[ft]`，后缀走**说明行**，
            #   页签标题保持不动（这里与注释空间段不同：那边没有独立的说明控件）。
            override_suffix = ""
            is_nospot = (ft == ANNO_CELLTYPE_NOSPOT)
            if is_nospot:
                # ★ 虚拟型（§15.5）：**没有图集版可退**，只有 override 那一张。
                #   所以"没有 override ⇒ 该图尚未生成"，**绝不拿带点版冒充**。
                cell, override_suffix = self._apply_override(
                    repr_sid, {}, reason="概览页『%s』" % ft, nospot=True)
                p = (cell or {}).get("png")
            elif is_ps:
                atlas_cell = ((ps_paths.get(ft) or {}).get(repr_sid) or {}) if repr_sid else {}
                cell, override_suffix = self._apply_override(repr_sid, atlas_cell,
                                                            reason="概览页『%s』" % ft)
                p = (cell or {}).get("png")
            else:
                p = (paths.get(ft) or {}).get("png")

            if p:
                try:
                    # ★ 全分辨率（用户第二轮实测报"图模糊"）：缩略图 320px 在只缩不放的
                    #   ZoomableImageLabel 里会又小又糊。见本方法 docstring。
                    ok = bool(self.func.show_figure(ft, p, thumbnail=False))
                except Exception:
                    traceback.print_exc()
                    ok = False
                if ok:
                    self._log("图型『%s』完成：1/1 有图%s"
                              % (ft, ("（代表样本 %s%s%s）" % (
                                  repr_sid,
                                  "，未选样本时的回退" if is_fallback else "",
                                  ("，%s" % override_suffix.strip("（）")) if override_suffix else ""))
                                 if is_ps else ""))
                    # 说明行：有后缀就写后缀（**绝不静默替换**），没有就清空
                    if note is not None and hasattr(note, 'setText'):
                        note.setText(override_suffix)
                else:
                    try:
                        self.func.clear_slot(ft)
                    except Exception:
                        pass
                    if note is not None and hasattr(note, 'setText'):
                        note.setText("该图读取失败")
            else:
                try:
                    self.func.clear_slot(ft)
                except Exception:
                    pass
                if note is not None and hasattr(note, 'setText'):
                    # ★ 文案必须按情况区分：**不能把"我还没输入"说成"数据没有"**
                    #   （契约 Q2 默认全不选；若无回退，这里会写"尚未生成"，
                    #     而这些图其实都在 per_sample_paths 里 → 用户会以为图没出）
                    if is_nospot:
                        # §15.5：第 24 型**没有图集版可退** ⇒ 就是"尚未生成"，
                        # 并把 §14.3 的后缀带上（有区域但过期时用户要知道去哪重做）
                        note.setText("该图尚未生成" + override_suffix)
                    elif is_ps and not repr_sid:
                        note.setText("请先在左侧选择样本")
                    elif is_ps:
                        note.setText("该样本的此图尚未生成")
                    else:
                        note.setText("该格尚未生成")
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 提示
    # ==================================================================
    def _sync_hint(self):
        """未审提示：选了未审样本 → 顶部一行提示，**不禁止使用**（契约 R5）"""
        try:
            scores = self._review_scores()
            unreviewed = [s for s in self._current_selected_ids()
                          if RA.review_state(s, scores) != "scored"]
            if unreviewed:
                self._log("提示：选中的 %d 个样本里有 %d 个尚未审查（仍可使用）"
                          % (len(self._current_selected_ids()), len(unreviewed)))
                try:
                    if hasattr(self.func, 'show_unreviewed_notice'):
                        self.func.show_unreviewed_notice()
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()

    def _set_empty_hint(self, msg):
        try:
            if hasattr(self.func, 'log'):
                self.func.log(msg)
            hint = getattr(self.ui, 'initial_empty_hint', None)
            if hint is not None and hasattr(hint, 'setText'):
                hint.setText(msg)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 槽函数
    # ==================================================================
    def _on_back_clicked(self):
        try:
            page_intersect.go_to_parent_page('spatial_initial_page')
        except Exception:
            traceback.print_exc()

    def _on_run_clicked(self):
        """「运行初步分析」——**本阶段不接 R 内核**（M2b 才做），如实告知"""
        try:
            n = len(self._current_selected_ids())
            if n == 0:
                self._log("请先选择至少一个样本（默认全不选是有意的，见契约 Q2）")
                return
            self._log("已选 %d 个样本；本阶段（M2a）只读现有图，"
                      "不触发重跑（应用内 rpy2 重跑属 M2b）" % n)
        except Exception:
            traceback.print_exc()

    def _on_from_review_clicked(self):
        try:
            page_intersect.go_to_page_with_bind('spatial_review_page')
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # ② 基因表达按需出图（后台线程 + 进度文件轮询）
    # ==================================================================






    @staticmethod









    @staticmethod
    def _image_size(path):
        """读图片真实像素尺寸（**只读文件头**，不解码全图）；失败返回 (0, 0)"""
        try:
            from PyQt5.QtGui import QImageReader
            r = QImageReader(str(path))
            s = r.size()
            return (int(s.width()), int(s.height())) if s.isValid() else (0, 0)
        except Exception:
            return (0, 0)

    # ==================================================================
    # 小工具
    # ==================================================================
    def _is_filling(self):
        """是否正在程序化设值（防信号回环）

        ⚠ 检测方法名与状态字段名**刻意不同**（`_filling` vs `_is_filling`）——
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
                print("[SpatialInitial] %s" % msg)
        except Exception:
            traceback.print_exc()

    def set_volume(self, value):
        try:
            from script.mods_layer.mod_manager import global_mod_manager
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_music_player'):
                mod_instance.global_music_player.set_volume(value / 100.0)
            if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
                self.parent._sync_all_volume_sliders_from_subinterface(value)
        except Exception:
            traceback.print_exc()


__all__ = ['SpatialInitialBind']
