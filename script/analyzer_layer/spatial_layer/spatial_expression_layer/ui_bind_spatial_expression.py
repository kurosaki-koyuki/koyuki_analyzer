# -*- coding: utf-8 -*-
"""空转「表达量分析」子页面 bind —— 2026-09-20 用户拍板**从「初步分析」页真拆出来**

## 这个文件是什么
  · 从 `ui_bind_spatial_initial.py` **机械搬迁**来的"表达分析类"逻辑：
    基因输入/绘制（`GEA.run_gene_expression`）、结果页签填充与空状态、
    `gene_status_label`/`gene_log_text` 的日志、基因图导出 PNG/PDF，
    以及**本页自己的样本选择**（样本列表填充、全选/选高分/反选、计数）。
  · 搬迁时**方法名与实现逐字保留**（机械搬迁，没有顺手重构）。
  · 本页**没有**大类切换、**没有** `pending_initial_category`（已退休）、
    **没有**图集页签逻辑（那是初始页的事）。

## 数据层共享，绝不重复加载 rds
  照既有约定 `getattr(self.parent, 'spatial_top_bind', None)` → `.analysis`
  （`ui_bind_spatial_initial.py:844` 附近是范例）；拿不到时**留痕不抛**。
  ⇒ 两页共用顶层 bind 那一个 `SpatialDataManager`，**不会再读一次 .rds**。

## 返回
  `nav_btn_back` → **回 hub**。二选一我选了 **`page_intersect.go_to_parent_page(
  'spatial_expression_page')`**：本页在 `page_intersect` 里登记的就是
  `parent_page='spatial_top_page'`（协调者已登记）⇒ 走"按登记关系回父页"这条，
  与初始页/审查页的既有风格一致；若哪天登记关系变了，只需改 `page_intersect` 一处。
  （另一条 `go_to_page_with_bind('spatial_top_page')` 是硬编码路由名，**未采用**。）
## v11 解离（2026-09-25）
  第二个模式已**解离**为独立子页（`spatial_layer/` 下另立同名新目录），
  本页**只留基础表达**：模式导航（`expression_stack` 与两个 `nav_btn_*`）及
  该模式的**全部**方法/常量已删除；下列通用件**保留**（有测试冻结）：
  `_on_gene_done` / `_render_result_tabs` / `gene_result_tabs` /
  `bind_annotation_figure` 与 `_anno_*` / `on_draw_anno_figure_clicked` /
  `bind_gene_expression` / `bind_export` / 两个 `@staticmethod`（`_gene_title` / `_fmt_samples`）。
"""

import os
import time
import traceback

from script.utils_layer.import_config import *
# ★ 显式 import：不依赖 import_config 的导出清单（本会话已多次踩这个坑）
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QFileDialog

from script.analyzer_layer.spatial_layer.spatial_review_layer import spatial_review_analysis as RA
from script.analyzer_layer.spatial_layer.spatial_expression_layer import spatial_gene_expression_analysis as GEA
from script.analyzer_layer.spatial_layer.spatial_initial_layer import spatial_export_analysis as SEA
from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as SREG
from script.analyzer_layer.spatial_layer.spatial_expression_layer.ui_func_spatial_expression import (
    SpatialExpressionFunc)
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.page_intersect import page_intersect
# 样本 id 解析唯一实现处（契约修订 R1 的取 id 侧；**禁止**再写 GSM 专属正则）
from script.utils_layer.sample_id_utils import sample_id_from_item

# =============================================================================
# ② 基因表达按需出图的成本估算常数（**单独成常量，便于按实测更新**）
# =============================================================================
# 来源：W3 实测 —— **几何改成"每面板 6×5 英寸、每行 ≤3 列"之后**的系数：
#   readRDS ≈ 5.6 s（固定）；单基因的**空间图**耗时/体积**随样本数线性增长**：
#     3 样本 → 2.51 s / 6.36 MB ; 19 样本 → 14.32 s / 35.2 MB
#   UMAP 单图 ≈ 1.0 s / 0.2 MB（与样本数无关）
#   基因集评分图（N基因 ≥ 2 时才出）≈ 9.0 s
# ★ 旧版只按"基因数"估（8.8 s / 16 MB）是**19 样本旧几何**的数字，对 3 样本会高估 3 倍、
#   对 19 样本又偏小（现在 35.2 MB）——已作废，改为 `gene_cost_estimate()`。
# 这是**估算**，只用于"点击前的成本预告"；真实耗时以 R 侧进度文件为准。
GENE_SEC_LOAD = 5.6
GENE_UMAP_SEC = 1.0
GENE_UMAP_MB = 0.2
GENE_SCORE_SEC = 9.0
# ⚠ 基因集评分图的**体积**不写成常数：它和别的空间图是同一套面板几何（每面板 6×5 in），
#   所以体积随样本数变。**实测依据**（本轮 3 样本 × 2 基因那次真跑）：
#     _geneset/GSE237183_geneset_score_spatial.png = 6,660,458 B = 6.35 MB
#     EGFR_spatial.png = 6.36 MB、TP53_spatial.png = 6.29 MB  → 三者同一量级
#   若按"恒定 16.6 MB"估，对 3 样本会**高估 2.6 倍**（正是本轮要消灭的那类错）。
#   ⇒ 体积项用 `spatial_mb`（同一公式），耗时项仍用常数 `GENE_SCORE_SEC`
#     （那 9 s 主要是 AddModuleScore 的计算，与面板数关系弱）。
#   校验：2 基因 × 3 样本 → 预估 19.3 MB vs 实测 19.2 MB（误差 0.5%）；
#         2 基因 × 3 样本 → 预估 21.6 s vs 实测 21.3 s（误差 1.4%）。
# 空间图对样本数的线性拟合（两点定线：3→2.51 s / 6.36 MB、19→14.32 s / 35.2 MB）
_SPATIAL_SEC_SLOPE, _SPATIAL_SEC_BASE = 0.738, 0.30
_SPATIAL_MB_SLOPE, _SPATIAL_MB_BASE = 1.803, 0.95


def gene_cost_estimate(n_genes, n_samples):
    """返回 (预计秒数, 预计 MB) —— **同时含基因数与样本数**（旧版只按基因数，已作废）"""
    try:
        n_genes = max(1, int(n_genes))
        n_samples = max(1, int(n_samples))
    except Exception:
        return 0.0, 0.0
    spatial_sec = _SPATIAL_SEC_SLOPE * n_samples + _SPATIAL_SEC_BASE
    spatial_mb = _SPATIAL_MB_SLOPE * n_samples + _SPATIAL_MB_BASE
    sec = GENE_SEC_LOAD + (spatial_sec + GENE_UMAP_SEC) * n_genes
    mb = (spatial_mb + GENE_UMAP_MB) * n_genes
    if n_genes >= 2:            # ≥2 基因才有基因集评分图
        sec += GENE_SCORE_SEC
        mb += spatial_mb        # ★ 与空间图同一套面板几何（见上面的实测依据）
    return sec, mb


# 进度轮询周期（W3 的 stdout 是全量缓冲的，**只能靠进度文件**）
GENE_PROGRESS_INTERVAL_MS = 500

# =============================================================================
# ③ 基础表达「注释图」的**分组 → 预渲染产物**映射（契约 `_d_spec_region_naming_v2.md` §5.2）
# -----------------------------------------------------------------------------
#   · 一页签一张图、**逐张判**；
#   · Q2-A（用户拍板）：**不新增 R 渲染** —— 没有预渲染产物的分组只写日志（为将来留口子）；
#   · 默认分组 = `group_graphed`（绘图模式产物的真相源 = 区域层 `anno_label`，
#     判据走 W3 的 `SREG.sample_has_group_graphed`，本文件**不自己再判一套**）。
ANNO_GROUP_GRAPHED = "group_graphed"
#: `group_graphed` 的两张产物（区域层 R 渲染，**逐张判**）
ANNO_GRAPHED_SPOTS = os.path.join("09_RegionOverride", "Spatial_%s.png")
ANNO_GRAPHED_NOSPOTS = os.path.join("09_RegionOverride", "SpatialNoSpots_%s.png")
#: 其余分组的 (子目录, 文件名模板, 页签标题模板) —— 用**图集已有产物**做映射
ANNO_GROUP_PRODUCTS = {
    "cell_type": (os.path.join("07_CellTypeAnno", "06_Spatial_per_sample"),
                  "Spatial_%s.png", "%s cell_type"),
    "cluster": (os.path.join("05_SpatialViz", "02_Spatial_Cluster"),
                "Spatial_Cluster_%s.png", "%s cluster"),
}

# ⏱ 原 `ui_bind_spatial_initial.py` 里的 `ANNO_*` / `OVERRIDE_AWARE_TYPES` 常量
#   **没有**搬到本文件：它们属于"图集/注释段"，按 2026-09-20 的拆分**留在初始页**。
#   （搬迁教训：只搬方法、常量没跟着搬，会在**运行期**抛 NameError，`py_compile` 看不出来
#     —— 所以本页凡是用到图集的地方一律走"空实现"，不引用那些常量。）


class _GeneExpressionWorker(QThread):
    """在**后台线程**里跑 `GEA.run_gene_expression`（subprocess + Rscript）

    ★ 为什么可以放线程：`run_gene_expression` 走的是 **`subprocess` + `Rscript`，完全不碰 rpy2**
      （契约 §9.1.1 就是为了这个才选子进程）—— 所以没有"M1 的 rpy2 只能在主线程用"的限制。
      若直接在按钮槽里调它，181 s 的 R 跑动会把整个界面冻死（连"取消/关闭"都点不动）。

    ★ 为什么用 `QThread` 而不是 `threading.Thread`：结果必须回到**主线程**改控件。
      QThread 的 `finished`/自定义信号会投递到接收者所在线程的事件队列里，
      接收者是 bind（主线程）⇒ 槽函数天然在主线程执行，不需要自己写 marshal。

    ★★ 线程里**绝不碰任何 Qt 控件**（也不读 `self.ui`）：只 emit 信号。
      这是 Qt 的硬规则，违反的症状是随机崩溃/卡死，且**没有 Python traceback**。
    """

    # 进度由**主线程**的 QTimer 轮询进度文件得到，所以这里不需要进度信号
    done_ok = pyqtSignal(object)     # result dict
    done_fail = pyqtSignal(str)      # 失败原因

    def __init__(self, rds_path, out_dir, dataset_id, genes, timeout,
                 samples=None, parent=None):
        super(_GeneExpressionWorker, self).__init__(parent)
        # ★ 只存**纯数据**（字符串/列表/数字），不存 QWidget、不存 bind 引用
        self._rds_path = rds_path
        self._out_dir = out_dir
        self._dataset_id = dataset_id
        self._genes = list(genes)
        self._timeout = timeout
        # ★ 只画这些样本（用户第二轮实测报的 bug：以前画了全部 19 个）。
        #   ⚠ 空列表的语义在 R 侧是 **NULL = 全部样本**，所以**调用方必须保证非空**。
        self._samples = [str(x) for x in (samples or [])]

    def run(self):
        """QThread 入口（**在工作线程**执行）"""
        try:
            ok, result, err = GEA.run_gene_expression(
                self._rds_path, self._out_dir, self._dataset_id,
                self._genes, timeout=self._timeout, samples=self._samples)
        except Exception as e:
            # run_gene_expression 自身承诺不抛；真抛了也要让主线程收到，
            # 否则界面会永远停在"绘制中"（这是"卡死"最常见的来源）
            import traceback as _tb
            _tb.print_exc()
            self.done_fail.emit("后台线程异常：%s: %s" % (type(e).__name__, e))
            return
        if ok:
            self.done_ok.emit(result)
        else:
            self.done_fail.emit(err or "未知原因")


class SpatialExpressionBind:
    """「表达量分析」子页面绑定类（从初始页 bind 机械搬迁而来）

    ★ 本页与初始页**各自持有一份样本选择逻辑**（两份实现逐字相同）：
      因为两页的样本列表控件是各自的（`sample_list`），语义也各自独立
      （初始页选"看哪些样本的图集"，本页选"画哪些样本的基因图"）。
    """

    def __init__(self, main_window, ui_instance):
        self.parent = main_window
        self.ui = ui_instance
        self.func = SpatialExpressionFunc(ui_instance, main_window)
        self.analysis = None

        self.dataset = None
        self._filling = False            # 状态字段（勿与 _is_filling() 同名）
        self._selected = set()           # 当前选中的样本 id
        self._repr_is_fallback = False    # 逐样本组的代表样本是否是"未选样本时的回退"
        self._handling_selection = False  # 选择变化槽的重入守卫
        self._last_selection_ids = None   # 上次已处理的选中集合（去抖"空选择"中间态）
        self._selection_pending = False   # 是否已排队一次延后的选择处理

        # ---- ② 基因表达按需出图 ----
        self._gene_worker = None
        self._gene_timer = None
        self._gene_out_dir = None
        self._gene_stale_ids = set()
        self._gene_genes = []
        self._gene_seen_progress = 0
        self._gene_t0 = 0.0
        self._gene_entries = []           # [(标题, 路径)] 基因结果段（**只含 PNG**）
        self._gene_pdf_entries = []       # [(标题, pdf 路径)]（只给导出用）
        self._gene_samples = []           # 这批基因图是用哪几个样本画的
        self._anno_cache = []             # [(标题, 路径)] 注释段（本页也会显示图集现成图）
        self._tabs_signature = None       # (anno, gene) 元组：内容没变就不重画
        # ★ 本页没有图集页签 ⇒ `figures` 恒空（有方法会读它，给出确定的空值而不是缺失属性）
        self.figures = {}

        # ---- ③ 绘图模式注释图（2026-09-23 §2）----------------------------
        # ★ `_anno_entries_list` 是注释段的**唯一真相源**：按钮算出来 → `_anno_entries()`
        #   读它 → `_render_result_tabs()` 按 [注释段][基因段] 重画（不另写建页签代码）。
        self._anno_entries_list = []      # [(标题, 路径)]

        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定（每个槽自带 try/except，防 PyQt5 对未捕获异常 qFatal）"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_sample_buttons()
        self.bind_sample_list()
        self.bind_gene_expression()
        self.bind_export()
        # ---- 2026-09-23 新增：绘图模式注释图（v11 起第二个模式已解离为独立页）----
        self.bind_annotation_figure()

    def bind_navigation(self):
        """本页导航：返回 hub + 基因导出（**没有**大类切换、没有图集页签）"""
        try:
            if hasattr(self.ui, 'nav_btn_back'):
                self.ui.nav_btn_back.clicked.connect(self._on_back_clicked)
        except Exception:
            traceback.print_exc()

    def _on_back_clicked(self):
        """回 hub（见文件头：二选一我选了 `go_to_parent_page`）"""
        try:
            page_intersect.go_to_parent_page('spatial_expression_page')
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 本页**不做**"注释/总览段"与图集页签 —— 那部分归初始页
    # ==================================================================
    # ★ 判断留痕（协调者可推翻）：`_render_result_tabs` / `_collect_export_items` /
    #   `_per_sample_types` 这些从初始页搬来的方法，内部会引用初始页的**图集机制**
    #   （`_anno_sources` / `_anno_entries` / `_figure_types` / `_is_per_sample_type` /
    #   `_decode_index` / `_sync_hint` / `self.figures`）。
    #   按用户 2026-09-20 的拆分："图集/注释"归初始页、"基因结果"归本页
    #   ⇒ 本页的注释段**恒为空**，故给出**最小空实现**，而不把整套图集解码
    #   （23 张全分辨率图）也拖进本页 —— 否则本页一打开就重解一遍图。
    #   ⚠ 若协调者裁定本页也要显示注释段：把初始页那几个取源方法**原样复制**过来即可，
    #     `_render_result_tabs` 本身已是"两段通用"的写法，不用改。
    def _anno_sources(self):
        return []

    def _anno_entries(self):
        """注释段页签清单 = 按钮 `on_draw_anno_figure_clicked()` 算出的 `_anno_entries_list`

        ★ 2026-09-23（§2）：本页的注释段**不再是恒空** —— 「绘图模式注释图」按钮
          把 `[(标题, 路径), ...]` 存进 `self._anno_entries_list`，这里只读它。
        ★ `_render_result_tabs()` 会把注释段排在基因段**之前**，不用另写一套顺序逻辑。
        ★ 返回的是**副本**（调用方 tuple 化后与 `_tabs_signature` 比较，不允许被就地改）。
        """
        try:
            return [tuple(x) for x in (self._anno_entries_list or [])]
        except Exception:
            traceback.print_exc()
            return []

    def _figure_types(self):
        return []

    def _is_per_sample_type(self, ft):
        return False

    def _decode_index(self, idx):
        return None

    def _sync_hint(self):
        return None

    @staticmethod
    def _image_size(path):
        """读图片真实像素尺寸（**只读文件头**，不解码全图）；失败返回 (0, 0)

        ★ 逐字复制自 `ui_bind_spatial_initial.py`（搬迁纪律：小工具优先复制最小实现，
          不反向 import 那个模块）。
        """
        try:
            from PyQt5.QtGui import QImageReader
            r = QImageReader(str(path))
            s = r.size()
            return (int(s.width()), int(s.height())) if s.isValid() else (0, 0)
        except Exception:
            return (0, 0)

    def bind_gene_expression(self):
        """② 「绘制表达量图」按钮 → 后台线程跑 Rscript

        ★ 控件名按契约冻结：`gene_input` / `btn_draw_expression` / `gene_status_label` /
          `gene_log_text` / `gene_result_tabs`；func 侧 `set_gene_status` / `gene_log` /
          `clear_gene_results` / `add_gene_result` / `gene_input_text` / `set_gene_busy`。
        ★ 控件**不存在时不报错、不建控件**，但**绝不静默**：写一行日志说明缺哪个控件
          （本会话教训：W1 曾因一个未定义方法名让 23 个图位全空，而三道闸门全过 ——
            所以"缺失"必须留下痕迹，不能靠 hasattr 悄悄跳过）。
        """
        try:
            btn = getattr(self.ui, 'btn_draw_expression', None)
            if btn is not None and hasattr(btn, 'clicked'):
                btn.clicked.connect(self._on_draw_expression_clicked)
            else:
                self._log("⚠ 布局未提供 btn_draw_expression → ② 基因表达出图按钮未绑定")
            for attr in ('gene_input', 'gene_status_label', 'gene_log_text',
                         'gene_result_tabs'):
                if getattr(self.ui, attr, None) is None:
                    self._log("⚠ 布局未提供 %s（② 的一部分界面会缺）" % attr)
        except Exception:
            traceback.print_exc()

    def bind_music_controls(self):
        try:
            if hasattr(self.ui, 'music_controller'):
                fix_music_controller_bindings(self, self.ui.music_controller)
        except Exception:
            traceback.print_exc()

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

    def bind_export(self):
        """`btn_gene_export_*` → 一键导出**本页的基因图**

        ★ 2026-09-20 拆页后：本页**只有**基因那两对按钮；
          `btn_export_all_*`（图集那批）留在初始页 —— 所以这里不再绑它们，
          也不会打出"布局未提供 btn_export_all_*"的假告警。
        """
        try:
            pairs = (('btn_gene_export_png', 'gene', 'png'),
                     ('btn_gene_export_pdf', 'gene', 'pdf'))
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

        · `scope='gene'`（本页）= **基因段**：png 取 `_gene_entries`，
          pdf 取 `_gene_pdf_entries`（两者同批产生、语义前提都是 `_gene_samples`）。
        · 其它 scope ⇒ **不收集**并留痕（图集那批在初始页，不在本页）。
        ★ 只收集路径，**不看文件在不在** —— 存在性判断与"跳过/失败"的账
          统一由 `SEA.batch_export` 记（一处记账，别两处各记一份）。
        """
        items = []
        try:
            key = 'pdf' if str(fmt).lower() == 'pdf' else 'png'
            # ★ 本页**只导出基因段**（`scope='gene'`）。"图集/注释"那批（`scope='all'`）
            #   留在初始页 ⇒ 这里**不再**引用 `self.figures` / `_anno_sources()` /
            #   `ANNO_*` 那套图集常量（拆页时只搬方法没搬常量 ⇒ 运行期 NameError，
            #   `py_compile` 看不出来；这里是替代实现）。
            if scope != 'gene':
                self._log("表达量页只导出基因段（收到 scope=%r）→ 本次不收集" % (scope,))
                return items
            # 基因段：png 用 `_gene_entries`，pdf 用 `_gene_pdf_entries`
            src = (self._gene_entries or []) if key == 'png' else (self._gene_pdf_entries or [])
            for title, p in src:
                items.append((title, p))
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

    def _log(self, msg):
        try:
            if hasattr(self.func, 'log'):
                self.func.log(msg)
            else:
                print("[SpatialInitial] %s" % msg)
        except Exception:
            traceback.print_exc()

    def _is_filling(self):
        """是否正在程序化设值（防信号回环）

        ⚠ 检测方法名与状态字段名**刻意不同**（`_filling` vs `_is_filling`）——
          同名会让 `self._filling = True` 遮蔽掉方法（本轮已踩过一次）。
        """
        try:
            return bool(self._filling)
        except Exception:
            return False

    # ⏱ 原 `_set_empty_hint` 已删（2026-09-20 拆页后清理）：
    #   它写 `self.ui.initial_empty_hint`（**本页没有这个控件**：那是总览页图集区的），
    #   且搬迁后本文件**没有任何调用点** ⇒ 纯死代码。
    #   本页的空状态走 `gene_result_empty_hint`（由 `_render_result_tabs` /
    #   `func.clear_gene_results` 负责），不需要这个方法。
    #   （初始页那份 `_set_empty_hint` 有 5 处调用、控件存在，**保留在那边**。）

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

    def _sample_ids(self):
        try:
            return list(self.figures.get("samples") or [])
        except Exception:
            return []

    def on_page_entered(self):
        """每次跳转到本页时由 `page_intersect.go_to_page_with_bind` 调用（可选钩子）

        ## ★ 为什么必须有它（用户报的 bug：表达页样本列表同步不出来）
          `page_intersect` 进入页面后会按约定调用本钩子；**本页拆出来时漏了它**
          ⇒ 全文件**没有任何地方**给 `self.figures` 赋值（`__init__` 里是 `{}`）
          ⇒ `_sample_ids()` 永远读到 `[]` ⇒ **样本列表 0 条**
          （其他页都正常，因为它们各有 `refresh_all` 负责这件事。）

        ## ★ 为什么这里只做两件事，**不抄初始页的 `refresh_all`**
          本页**刻意不做图集段**（24 个图集页签与解码归初始页）⇒ 这里只：
            ① 取图清单 `RA.list_all_figures(dataset)` —— **与初始页同一个真相源**，
               它是"清单读取"、很轻，每次进页面调没问题；
            ② 重填样本列表（并在重填时**保住用户已选样本**，见 `_fill_sample_list`）。

        ★ 拿不到数据集 ⇒ **只留痕并返回**（不抛、不崩）：与初始页同一套守卫语义。
        """
        try:
            ds = self._dataset_name()
            if not ds:
                self._log("请先在主页加载数据集")
                return
            self.dataset = ds
            self.figures = RA.list_all_figures(ds) or {}
            self._log("【表达量分析】进入页面：%s（图集清单 ok=%s，样本 %d 条）"
                      % (ds, (self.figures or {}).get("ok"), len(self._sample_ids())))
            self._fill_sample_list()
        except Exception:
            traceback.print_exc()

    def _fill_sample_list(self, selected_ids=None):
        """填充样本列表（**尽量保住用户已选样本**，见下）

        ## ★★ 为什么必须透传 `selected_ids`（这一条比"填得上"更要紧）
          W1 的 `set_sample_items(samples)` 不带 `selected_ids` 时是**默认全不选**；
          若每次进页面都这样重建，"用户选好样本 → 回 hub → 再进来"选择就被清空，
          而 **R 侧把空列表当"全部样本"** ⇒ 会一次画满 19 个
          （这正是用户以前亲自报过的 bug）。
          ⇒ 默认 `selected_ids=None` 时**取当前选择**：`_current_selected_ids()`
            读 UI（列表控件在页面常驻、重填前仍持有上次的选择），拿不到才退回 `self._selected`。
        """
        try:
            if selected_ids is None:
                selected_ids = self._current_selected_ids()
            keep = [str(x) for x in (selected_ids or [])]
            samples = []
            for sid in self._sample_ids():
                label = self._sample_label(sid)
                samples.append({"id": sid, "label": label,
                                "reviewed": RA.review_state(sid, self._review_scores()) == "scored",
                                "total": self._total_of(sid)})
            try:
                self.func.set_sample_items(samples, keep)
            except TypeError:
                # 兜底：若 func 是**老签名**（只收 1 个参数）→ 退回不带选择的调用。
                #   真走到这里说明签名没跟上，**留痕**（代价是本次丢掉已选，故必须看得见）。
                traceback.print_exc()
                self.func.set_sample_items(samples)
            except Exception:
                traceback.print_exc()
            self._log("样本清单: %d 条（保持已选 %d 条%s）"
                      % (len(samples), len(keep),
                         "；**未选任何样本时不会退化成全部**" if not keep else ""))
            # ★ 需求⑥：鼠标悬停样本 → 小框显示审查时写的备注。
            #   必须紧跟在 set_sample_items 之后：那只函数会 clear() 重建全部 item，
            #   任何在它之前设的 tooltip 都会被丢掉。这里也是**唯一**的重建路径
            #   （on_page_entered / 主题刷新都走 _fill_sample_list），所以不会漏。
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
                    # ★ 统一口径：先读 UserRole（初始页 W1 建列表时已写真实 id），
                    #   再按已知样本清单解析文本。旧写法 `re.search(r'(GSM\d+)', text)`
                    #   只认 GEO 编号，Dryad_UKF 的 `UKF*` 恒取不到 ⇒ 勾选同步静默失效。
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

        ## 为什么必须在这里让基因段失效（协调者实测发现的缺陷）
          基因表达图是**按某几个样本**画出来的，**选中集是它的语义前提**。
          之前 `_gene_entries` 只在"绘制前清空 / 收图后赋值"两处变过，
          **从不因选择变化而失效** ⇒ 用户改选样本后，注释段跟着变了，
          基因段**却还挂在旧样本上，标题仍写"EGFR 空间表达"，没有任何陈旧标记**。
          科研数据上这是最危险的一类错：用户会拿它去下结论、去写文章。

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
            if changed and (self._gene_entries or []):
                n_gene = len(self._gene_entries)
                old_samples = list(getattr(self, '_gene_samples', []) or [])
                self._gene_entries = []
                self._gene_pdf_entries = []     # PDF 与 PNG 同批失效（同一语义前提）
                self._log("⚠ 样本选择已变（原 %s → 现 %s）：已清掉旧样本的基因表达图"
                          "（%d 张%s），请重新绘制"
                          % (self._fmt_samples(prev), self._fmt_samples(cur), n_gene,
                             ("，它们属于 %s" % self._fmt_samples(old_samples))
                             if old_samples else ""))
            # ★ 注释段（「绘图模式注释图」）**同样按样本出图**，选择一变就必须作废 ——
            #   否则用户改选样本后，结果区还挂着**旧样本**的注释图，且标题只写 sid，
            #   一眼看不出与当前选择不一致（与上面基因段同一条纪律，只是来源不同）。
            #   这里**只清注释段**：`_gene_entries` 的既有失效逻辑一个字都没动。
            #   force=True 是为了立刻把注释段摘掉；其后的 `_render_result_tabs` 会因
            #   签名一致而直接 return（幂等，不重复解码）。
            if changed and (self._anno_entries_list or []):
                n_anno = len(self._anno_entries_list)
                self._anno_entries_list = []
                self._render_result_tabs(force=True, reason="样本选择已变，注释段作废")
                self._gene_log("样本选择已变：『绘图模式注释图』页签已清空（原 %d 张），"
                               "请重新点一次出图" % n_anno)
            # 内容没变时 `_render_result_tabs` 内部会直接 return（幂等，不重解图）
            self._render_result_tabs(reason=source or "选中已定稿")
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

    def _gene_input_text(self):
        """读基因输入框的原文

        ★ 优先用 W1 func 的 `gene_input_text()`；拿不到就直接读控件。
          两条路都拿不到 → 返回 `None`（**与"用户输入了空字符串"区分开**：
          前者是"界面没接上"，后者是"用户没填"，报错文案不一样）。
        """
        try:
            getter = getattr(self.func, 'gene_input_text', None)
            if callable(getter):
                try:
                    v = getter()
                    if v is not None:
                        return str(v)
                except Exception:
                    traceback.print_exc()
            widget = getattr(self.ui, 'gene_input', None)
            if widget is None:
                return None
            if hasattr(widget, 'toPlainText'):
                return str(widget.toPlainText())
            if hasattr(widget, 'text'):
                return str(widget.text())
            return None
        except Exception:
            traceback.print_exc()
            return None

    def _gene_status(self, msg):
        """写状态栏（缺失时退回日志，不静默）"""
        try:
            setter = getattr(self.func, 'set_gene_status', None)
            if callable(setter):
                setter(msg)
                return
            self._log("[基因表达] %s" % msg)
        except Exception:
            traceback.print_exc()

    def _gene_log(self, msg):
        """写**基因日志框**（`gene_log_text`）

        ⚠ 为什么不能只用 `self._log`：`_log` 走的是 `func.log` → 本页的
          **页面日志框** `initial_log_text`，而契约给 ② 单独留了 `gene_log_text`。
          如果出图细节只写进页面日志，用户盯着的那个"基因日志"框会一直停在
          "等待操作..." —— 正是"构造通过 ≠ 数据路径通过"那种假绿。
        """
        try:
            logger = getattr(self.func, 'gene_log', None)
            if callable(logger):
                logger(msg)
                return
            self._log("[基因] %s" % msg)
        except Exception:
            traceback.print_exc()

    def _gene_busy(self, busy):
        """置忙：禁/启用按钮（缺失时退回日志）"""
        try:
            setter = getattr(self.func, 'set_gene_busy', None)
            if callable(setter):
                setter(bool(busy))
        except Exception:
            traceback.print_exc()

    def _gene_result_files(self, result):
        """把 R 侧结果摊平成 [(标题, 路径), ...]（**顺序稳定**：先逐基因，再基因集评分）

        ★ 一个文件一个页签（与 ①"平铺 23"同一思路）。
        ★ `files` 已被 W3 归一化成 list（R 的 `auto_unbox` 会把长度 1 的向量脱成标量，
          W3 在 `_normalize_result` 里补过一层），这里仍然按"可能是标量"防御。
        """
        out = []
        try:
            per_gene = (result or {}).get("per_gene") or {}
            for gene, rec in per_gene.items():
                if not isinstance(rec, dict):
                    continue
                files = rec.get("files")
                if not isinstance(files, (list, tuple)):
                    files = [files] if files else []
                for p in files:
                    if not p:
                        continue
                    out.append((self._gene_title(str(gene), str(p)), str(p)))
            gs = (result or {}).get("gene_set_score") or {}
            for p in (gs.get("files") or []):
                if p:
                    out.append(("基因集评分", str(p)))
        except Exception as e:
            traceback.print_exc()
            # ★ 不许静默（2026-09-23 事故：`_gene_title` 漏 `@staticmethod` ⇒ 这里 TypeError
            #   被吞掉 ⇒ `out=[]` ⇒ 结果区**0 个页签且界面毫无提示**，用户只看到"出不了图"。
            #   现在把原因写进基因日志，下次同类问题一眼可见。）
            try:
                self._gene_log("⚠ 摊平基因结果失败：%s: %s（结果区可能为空，详见控制台）"
                               % (type(e).__name__, e))
            except Exception:
                # ★ 再兜一层：`self.func` 不存在时日志通道自己会抛（W5 复核实测）
                #   ⇒ 那就 print，绝不出现"连一行字都没有"的静默。
                print("[spatial_expression] ⚠ 摊平基因结果失败：%s: %s" % (type(e).__name__, e))
        return out

    def _gene_pdf_files(self, result):
        """把 R 侧新字段 `pdf_files` 摊平成 `[(标题, pdf路径), ...]`（**只给导出用**）

        ★ 第 5 轮：W3 让每张基因图同时产出 PDF，放在 `per_gene[g]['pdf_files']` 与
          `gene_set['pdf_files']`（与 `files` 并列的新字段）。
        ★ **绝不进 `_gene_entries`**：`files` 的语义与顺序保持不变（仍是 PNG 页签），
          PDF 混进去会让每个基因多出一个重复页签（契约 §12.2 硬约束）。
        ★ 字段还没落地（W3 未交付 / 旧结果文件）时返回 `[]`，**不报错、不影响页签**。
          标题沿用 `_gene_title`（同一套命名规则），便于与 PNG 页签对照。
        """
        out = []
        try:
            per_gene = (result or {}).get("per_gene") or {}
            for gene, rec in per_gene.items():
                if not isinstance(rec, dict):
                    continue
                files = rec.get("pdf_files")
                if not isinstance(files, (list, tuple)):
                    files = [files] if files else []
                for p in files:
                    if not p:
                        continue
                    out.append((self._gene_title(str(gene), str(p)), str(p)))
            gs = (result or {}).get("gene_set_score") or {}
            gs_files = gs.get("pdf_files")
            if not isinstance(gs_files, (list, tuple)):
                gs_files = [gs_files] if gs_files else []
            for p in gs_files:
                if p:
                    out.append(("基因集评分", str(p)))
        except Exception as e:
            traceback.print_exc()
            # ★ 同上：不许静默（否则「导出全部PDF」少文件却查不到原因）
            try:
                self._gene_log("⚠ 摊平 PDF 结果失败：%s: %s（导出可能缺文件，详见控制台）"
                               % (type(e).__name__, e))
            except Exception:
                # ★ 同上一处：日志通道不可用也要 print 兜底（绝不静默）
                print("[spatial_expression] ⚠ 摊平 PDF 结果失败：%s: %s" % (type(e).__name__, e))
        return out

    @staticmethod
    def _gene_title(gene, path):
        """按**文件名**给页签起标题（`<基因> 空间表达` / `<基因> UMAP`）

        ★ 为什么不按"files 的第 0 个就是空间图"来猜：那是**位置约定**，R 侧一改顺序
          就会把 UMAP 标成空间图。用文件名判断是自证的（R 侧命名见 W3 的脚本）。
        """
        low = str(path).lower()
        if "umap" in low:
            return "%s UMAP" % gene
        if "geneset" in low or "score" in low:
            return "%s 基因集评分" % gene
        return "%s 空间表达" % gene

    def _resolve_gene_paths(self):
        """解析 (rds_path, out_dir) —— 任何一项取不到都返回 (None, None, 原因)

        rds 优先用 **W3 自己的 `artifact_info['path']`**（同一套解析规则，避免第二个真相源），
        再退回 `appdata/spatial_main/<dataset>.rds`。
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

    def _on_draw_expression_clicked(self):
        """「绘制表达量图」：解析 → 成本预告 → **后台线程**跑 R → 主线程收结果"""
        try:
            if self._gene_worker is not None:
                self._gene_status("已有一次绘制在进行中，请等它结束")
                self._gene_log("忽略重复点击：上一次绘制还没结束")
                return

            raw = self._gene_input_text()
            if raw is None:
                self._gene_status("界面未接上基因输入框（见日志）")
                self._gene_log("⚠ 取不到基因输入框（func.gene_input_text / ui.gene_input 都没有）")
                return

            # ★ 解析用 W3 的 `sanitize_genes`（**唯一真相源**）：切分/去空/去重保序/
            #   上限 20/非法字符——全部一套规则，不在 bind 里再写一份。
            clean, dropped, err = GEA.sanitize_genes(raw)
            if err:
                self._gene_status("输入有误：%s" % err)
                self._gene_log("未开始绘制：%s（原始输入=%r）" % (err, raw))
                return
            if dropped:
                # 如实列出被拒项，**不静默丢**
                self._gene_log("⚠ 以下基因名含非法字符（会被当作目录名），已跳过：%s"
                               % ", ".join(dropped))

            rds, out_dir, perr = self._resolve_gene_paths()
            if perr:
                self._gene_status(perr)
                self._gene_log("未开始绘制：%s" % perr)
                return

            # ★ 只画**左侧选中的样本**（用户第二轮实测报的 bug：以前画了全部 19 个）
            #   ⚠ 绝不能把空列表传下去：R 侧 `length==0` 的语义是 **NULL = 全部样本**
            #     ⇒ 空选必须**在这里**就拦住，否则会静默退化成"画全部"，正是用户报的现象。
            sel = self._current_selected_ids()
            if not sel:
                self._gene_status("请先在左侧选择样本（可点「全选」）；本功能只画你选中的样本")
                self._gene_log("未开始绘制：一个样本都没选 —— 本功能只画你选中的样本"
                               "（**不会退化成全部 19 个**）")
                return

            n = len(clean)
            est, est_mb = gene_cost_estimate(n, len(sel))
            cost = ("将绘制 %d 个基因 × %d 个样本：预计约 %.0f 秒（约 %d 分 %d 秒），磁盘约 %.0f MB"
                    % (n, len(sel), est, int(est // 60), int(est % 60), est_mb))
            # ★ 成本预告必须**在整个运行期间都留在状态栏上**。
            #   实测教训：先前"先写预告、紧接着写『正在绘制 0/N』"会把预告**立刻冲掉**，
            #   用户根本没机会看到估算。所以预告拼进每一次进度更新里。
            self._gene_cost = cost
            self._gene_status(cost)
            self._log("=" * 40)
            self._log("【基因表达按需出图】%s" % cost)
            self._gene_log(cost)
            self._gene_log("基因：%s" % ", ".join(clean))
            self._gene_log("样本：%d 个 —— %s（**只画这些**）" % (len(sel), ", ".join(sel)))
            self._gene_log("rds = %s" % rds)
            self._gene_log("输出目录 = %s（子目录 %s，**不动图集**）"
                           % (out_dir, GEA.ON_DEMAND_SUBDIR))
            # ★ 协调者点名：注释/总览那几个页签取自**图集现成文件**，
            #   不跑 R、不新增磁盘、不增加耗时 ⇒ **不计入上面的成本预告**。
            self._gene_log("（注：结果区里的『总UMAP』『总UMAP·细胞注释』『注释空间·样本』"
                           "来自图集现成图，不跑 R、不计入本次预估）")

            # ★★ 只清**基因段**，注释/总览段必须留着（第 4 轮的核心要求）。
            #    这里**不再调 `func.clear_gene_results()`** —— 它内部是 `tabs.clear()`，
            #    会把整条 strip 清空（注释段一起没）。改成把基因段置空后重画：
            #    重画会按 [注释段][基因段] 的顺序重建，注释段仍在最前面。
            self._gene_entries = []
            self._gene_pdf_entries = []     # PDF 与 PNG 同批失效（否则会导出上一批的 PDF）
            self._gene_samples = list(sel)      # 记下这批图属于哪几个样本（语义前提）
            self._render_result_tabs(reason="开始绘制前清空基因段")

            self._gene_genes = list(clean)
            self._gene_seen_progress = 0
            self._gene_out_dir = out_dir
            # 开跑前记下进度文件里"已存在"的 run_id（陈旧集）——见 `__init__` 的说明
            try:
                self._gene_stale_ids = set(
                    str(r.get('run_id')) for r in GEA.read_progress(out_dir) if r.get('run_id'))
            except Exception:
                traceback.print_exc()
                self._gene_stale_ids = set()
            self._gene_t0 = time.time()

            self._gene_busy(True)
            self._gene_status("正在绘制 0/%d …（%s）｜%s" % (n, ", ".join(clean), cost))

            # timeout：给足余量（**样本感知**的估算值 ×3，且不低于 W3 的默认 900 s）
            timeout = max(900, int(est * 3))
            worker = _GeneExpressionWorker(rds, out_dir, self.dataset, clean, timeout,
                                           samples=sel)
            worker.done_ok.connect(self._on_gene_done)
            worker.done_fail.connect(self._on_gene_failed)
            worker.finished.connect(self._on_gene_thread_finished)
            self._gene_worker = worker
            worker.start()
            self._start_gene_progress_timer()
        except Exception as e:
            traceback.print_exc()
            self._gene_busy(False)
            # ★ 兜底也要**带上异常类型与原文**：只写"见日志"会让"功能整块坏掉"
            #   看起来像"优雅处理"（本轮真踩过：一个常量名打错 → NameError →
            #   被这里吞成一句提示，界面上完全看不出是代码 bug）。
            self._gene_status("启动绘制时异常：%s: %s" % (type(e).__name__, e))
            self._gene_log("❌ 启动绘制时异常：%s: %s" % (type(e).__name__, e))

    def _start_gene_progress_timer(self):
        """主线程 QTimer 轮询进度文件（W3 的 stdout 全量缓冲，只能靠进度文件）"""
        try:
            self._stop_gene_progress_timer()
            timer = QTimer()
            timer.setInterval(GENE_PROGRESS_INTERVAL_MS)
            timer.timeout.connect(self._poll_gene_progress)
            self._gene_timer = timer
            timer.start()
        except Exception:
            traceback.print_exc()

    def _stop_gene_progress_timer(self):
        try:
            if self._gene_timer is not None:
                self._gene_timer.stop()
                self._gene_timer = None
        except Exception:
            traceback.print_exc()

    def _poll_gene_progress(self):
        """读进度文件，把**新增**的行写进日志/状态栏（不重复刷同一行）"""
        try:
            out_dir = getattr(self, '_gene_out_dir', None)
            if not out_dir:
                return
            stale = getattr(self, '_gene_stale_ids', set()) or set()
            rows = [r for r in GEA.read_progress(out_dir)
                    if str(r.get('run_id')) not in stale]
            if not rows:
                return
            total = len(self._gene_genes) or 0
            for rec in rows[self._gene_seen_progress:]:
                i = rec.get('i')
                n = rec.get('n') or total
                gene = rec.get('gene') or ''
                status = rec.get('status') or ''
                el = rec.get('elapsed')
                line = "进度 %s/%s：%s %s" % (i, n, gene, status)
                if el not in (None, ""):
                    line += "（%.1f s）" % float(el)
                self._gene_log(line)
                self._gene_status("正在绘制 %s/%s …（%s）｜%s"
                                  % (i, n, gene, getattr(self, '_gene_cost', '')))
            self._gene_seen_progress = len(rows)
        except Exception:
            traceback.print_exc()

    def _on_gene_done(self, result):
        """**主线程**槽：结果到齐 → 一个文件一个页签"""
        try:
            # ★ 先把进度文件里剩下的行读完，**再**写完成摘要。
            #   为什么：`done_ok` 比 `finished` 先投递，而 R 的最后一条进度行往往
            #   与进程退出几乎同时落盘（单基因实测：进度行只比退出早约 0.2 s）。
            #   若把这次补读放在 `_on_gene_thread_finished` 里，日志就会出现
            #   "绘制完成…" 之后又冒出一行 "进度 1/1" 的**倒序**，读起来像 bug。
            self._poll_gene_progress()
            self._gene_log("R 子进程返回 ok=True，开始收图")
            result = result if isinstance(result, dict) else {}
            pairs = self._gene_result_files(result)
            # ★ 第 4 轮：基因结果**不再直接往控件里追加**，而是交给"结果区唯一真相源"
            #   `_gene_entries` + `_render_result_tabs()` 统一重画 ——
            #   这样注释/总览段永远排在最前面、基因段永远在后面，且顺序确定。
            for title, path in pairs:
                self._gene_log("基因图：%s → %s（%dx%d px）"
                               % (title, path, *self._image_size(path)))

            # ★★ 边界（协调者点名要明确结论）：**绘制进行中用户改了选择**
            #    出图是在后台线程跑的，R 用的是**开工那一刻**的样本集。
            #    若这期间用户改了选择，这批图就**不属于当前选择** ——
            #    既不能假装它是当前的（科研数据），也不能直接丢掉（用户等了十几秒）。
            #    采取的做法：**留着，但打上明确标记**，标题里带上它实际属于几个样本，
            #    日志里写全名单 + 一句"要当前选择的图请重新绘制"。
            drawn = [str(x) for x in (getattr(self, '_gene_samples', []) or [])]
            cur_sel = [str(x) for x in self._current_selected_ids()]
            stale = (set(drawn) != set(cur_sel))
            if stale:
                suffix = "（样本 %d 个）" % len(drawn) if drawn else "（无样本）"
                pairs = [(str(t) + suffix, p) for t, p in pairs]
                self._gene_log("⚠ 这次出图用的是开工时的样本 %s，但当前选中的是 %s"
                               % (self._fmt_samples(drawn), self._fmt_samples(cur_sel)))
                self._gene_log("⚠ 因此这批图已标注「%s」；要**当前选择**的图请重新点一次绘制"
                               % suffix)
                self._log("⚠ 基因表达图与当前选中样本不一致（出图样本 %s / 当前 %s）"
                          % (self._fmt_samples(drawn), self._fmt_samples(cur_sel)))

            self._gene_entries = [tuple(x) for x in pairs]
            # ★ PDF 另存一份（只给导出；**不进页签**）。字段未落地时是空列表。
            self._gene_pdf_entries = [tuple(x) for x in self._gene_pdf_files(result)]
            if self._gene_pdf_entries:
                self._gene_log("同时收到 %d 个 PDF（供「导出全部PDF」使用，不额外占页签）"
                               % len(self._gene_pdf_entries))
            self._render_result_tabs(reason="基因结果就绪")
            # 真正"上屏成功"的基因页签数 = 结果条总数 − 注释段数
            # （`add_gene_result` 返回 False 表示没贴上，这类项仍然在 `pairs` 里，
            #   所以不能直接拿 `len(pairs)` 当"已上屏"，否则日志会虚报。）
            added = len(pairs)
            try:
                tabs = getattr(self.ui, 'gene_result_tabs', None)
                if tabs is not None and hasattr(tabs, 'count'):
                    added = max(0, int(tabs.count()) - len(self._anno_cache or []))
            except Exception:
                traceback.print_exc()

            # ★★ 样本子集**闭环回显**（需求③）：我们在 Python 侧拦住了"空选择"，
            #    但真正决定画几个面板的是 R 侧。必须把"请求了什么 / R 实际用了什么"
            #    摊在日志里，并在两者不一致时**大声报**——
            #    否则"用户选了 3 个却出了 19 个面板"这类退化只会表现为"图变大了"，
            #    没人能一眼看出是选择没生效。（W3 已实测：不存在的样本名会硬失败，
            #    但"传了空列表 → NULL → 全部样本"这条退化路径必须在两侧都堵。）
            s_req = [str(x) for x in (result.get("samples_requested") or [])]
            s_used = [str(x) for x in (result.get("samples_used") or [])]
            n_panels = result.get("n_panels")
            s_missing = [str(x) for x in (result.get("samples_missing") or [])]
            if s_req or s_used:
                self._gene_log("R 回显：请求样本 %d 个 → 实际使用 %d 个%s"
                               % (len(s_req), len(s_used),
                                  ("，面板数 %s" % n_panels) if n_panels is not None else ""))
                self._gene_log("R 实际使用：%s" % (", ".join(s_used) or "（空）"))
                if s_req and set(s_req) != set(s_used):
                    self._gene_log("⚠ 请求样本与实际使用样本**不一致**！请求=%s 实际=%s"
                                   % (", ".join(s_req), ", ".join(s_used)))
            if s_missing:
                self._gene_log("⚠ R 报告缺失样本（请求了但数据里没有）：%s"
                               % ", ".join(s_missing))

            # ★ not_found **必须如实显示**（W3 实测能列出未找到的基因；
            #   单细胞 R 版没有这个能力 —— 这是本页要显式用上的）
            not_found = result.get("not_found") or []
            if not_found:
                self._gene_log("⚠ 数据集中找不到这些基因，未出图：%s"
                               % ", ".join(str(g) for g in not_found))
            avail = result.get("available_genes") or []
            if not_found and avail:
                preview = ", ".join(str(g) for g in avail[:15])
                self._gene_log("（数据集中可用基因示例：%s%s）"
                               % (preview, " …" if len(avail) > 15 else ""))
            failed_genes = [str(g) for g, rec in (result.get("per_gene") or {}).items()
                            if isinstance(rec, dict) and rec.get("status") not in (None, "ok")]
            if failed_genes:
                self._gene_log("⚠ 这些基因出图状态非 ok：%s" % ", ".join(failed_genes))
            dropped = result.get("dropped_genes") or []
            if dropped:
                self._gene_log("⚠ 被拒的基因名：%s" % ", ".join(str(x) for x in dropped))
            if result.get("stderr_tail"):
                self._gene_log("R stderr 末尾：%s" % str(result.get("stderr_tail"))[-300:])

            dt = time.time() - self._gene_t0 if self._gene_t0 else 0.0
            summary = ("绘制完成：%d 个基因 → %d 张图 / %d 个页签，实际耗时 %.1f 秒"
                       % (len(self._gene_genes), len(pairs), added, dt))
            if s_used:
                summary += "；样本 %d 个" % len(s_used)
            elif s_req:
                summary += "；请求样本 %d 个（R 未回显）" % len(s_req)
            if not_found:
                summary += "；%d 个基因未找到" % len(not_found)
            self._log(summary)
            self._gene_log(summary)
            self._gene_status(summary)
        except Exception:
            traceback.print_exc()
            self._gene_status("收图时异常（见日志）")

    def _on_gene_failed(self, reason):
        """**主线程**槽：失败一律如实报（不抛、不静默、不假装成功）"""
        try:
            dt = time.time() - self._gene_t0 if self._gene_t0 else 0.0
            msg = "绘制失败（%.1f 秒）：%s" % (dt, reason)
            self._log("❌ %s" % msg)
            self._gene_log("❌ %s" % msg)
            self._gene_status(msg)
        except Exception:
            traceback.print_exc()

    def _on_gene_thread_finished(self):
        """线程收尾：停表、复位忙标记（**无论成功失败都必须执行**，否则按钮永久禁用）"""
        try:
            self._stop_gene_progress_timer()
            # 最后再读一次进度，避免漏掉 R 写完后、进程退出前的最后几行
            self._poll_gene_progress()
            self._gene_worker = None
            self._gene_busy(False)
        except Exception:
            traceback.print_exc()

    def _render_result_tabs(self, force=False, reason=""):
        """按「注释段 + 基因段」重画结果页签条（**顺序由这两份列表决定**）

        ★ 为什么是"重画"而不是"往控件里追加"：页签必须满足
          `[注释段][基因段]` 且注释段随样本选择变化 —— 只靠 `addTab` 追加做不到
          "把新注释段插到前面"。以两份列表为唯一真相源重画，顺序天然正确。
        ★ 内容没变 → **直接返回，一张图都不重解**（关键：进页面/切大类都会走到这里）。
        ★ 只在**注释段变了**时才需要连基因段一起重画；若 `WrappingTabStrip` 提供了
          `removeTab`，则"注释段没变、只有基因段变"时走**外科式**只删基因段，
          注释段一张图都不用重解（W1 交付 `removeTab` 后自动生效，无需再改）。
        ★ 本函数**绝不改 `gene_result_tabs` 的显隐**（③ 的硬约束：它常驻可见）。
        """
        try:
            tabs = getattr(self.ui, 'gene_result_tabs', None)
            if tabs is None or not hasattr(tabs, 'addTab'):
                return
            anno = [tuple(x) for x in self._anno_entries()]
            gene = [tuple(x) for x in (self._gene_entries or [])]
            sig = (tuple(anno), tuple(gene))
            try:
                cur = int(tabs.count())
            except Exception:
                cur = -1
            if (not force) and sig == self._tabs_signature and cur == len(anno) + len(gene):
                return

            adder = getattr(self.func, 'add_gene_result', None)
            # `add_gene_result` 是 W1 func 里"建一个图片页签"的唯一入口。
            # bind 不建控件，所以注释图和基因图都走它（只是标题不同）。
            if not callable(adder):
                self._log("⚠ func 无 add_gene_result → %d 个结果页签无法上屏"
                          % (len(anno) + len(gene)))
                self._tabs_signature = sig
                return

            old_anno = tuple(t for t, _ in (self._anno_cache or []))
            remover = getattr(tabs, 'removeTab', None)
            anno_same = (old_anno == tuple(t for t, _ in anno))
            if callable(remover) and anno_same and cur >= len(anno):
                # 外科式：只删基因段（从后往前），注释段原样保留、**不重解**
                for i in range(cur - 1, len(anno) - 1, -1):
                    try:
                        remover(i)
                    except Exception:
                        traceback.print_exc()
            else:
                try:
                    tabs.clear()
                except Exception:
                    traceback.print_exc()
                for title, p in anno:
                    if adder(title, p) is False:
                        self._log("⚠ 注释/总览页签未贴上图：%s（%s）" % (title, p))
            for title, p in gene:
                if adder(title, p) is False:
                    self._log("⚠ 基因页签未贴上图：%s（%s）" % (title, p))

            self._tabs_signature = sig
            self._anno_cache = list(anno)
            titles = []
            for i in range(int(tabs.count())):
                try:
                    titles.append(str(tabs.tabText(i)))
                except Exception:
                    titles.append("<?>")
            self._log("结果区页签（%d 个%s）：%s"
                      % (len(titles), ("，%s" % reason) if reason else "",
                         " | ".join(titles) or "（空）"))
            self._update_gene_result_hint()
        except Exception:
            traceback.print_exc()

    def _update_gene_result_hint(self):
        """**基因段为空** → 显示 `gene_result_empty_hint`；否则隐藏

        ★ 用户第三轮原话：「表达分析类的图标签页能不能放在右侧并且一直存在？
          现在属于是输入基因后它才能在下方弹出来，这样非常不美观」
          ⇒ W1 已把 `gene_result_tabs` 改成**常驻可见**，并新增 `gene_result_empty_hint`。
             **空/非空这个显隐判断归 bind**（本函数），布局只提供控件与文案。
        ★★ 第 4 轮**修正判据**：原来是 `tabs.count() == 0`，现在结果区里**永远**有
           注释/总览段（至少 2 个页签）⇒ 那个判据会让提示**永远不出现**，
           等于把 W1 的空状态文案废掉。
           提示的原文是"尚未绘制**任何基因**…"，说的是**基因**结果，
           所以判据改成 **`_gene_entries` 是否为空**（基因段的唯一真相源）。
           这样：注释段在、但没画过基因 → 提示照样显示（文案与实际相符）。
        ★ 只切**提示**的显隐：`gene_result_tabs` 自身的显隐仍由 W1 的 func 管 ——
          **不在这里重复一份**，否则就是"两个真相源"，本会话已经因此栽过两次。
        """
        try:
            hint = getattr(self.ui, 'gene_result_empty_hint', None)
            if hint is None or not hasattr(hint, 'setVisible'):
                return
            hint.setVisible(len(self._gene_entries or []) == 0)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # ③ 基础表达：「绘图模式注释图」（§2）—— 逐张判、一个页签只放一张图
    # ==================================================================
    def bind_annotation_figure(self):
        """`btn_draw_anno_figure` → 逐样本产出注释图页签 + `anno_group_combo` → 切分组作废

        ★ v2（`_d_spec_region_naming_v2.md` §5.1/§5.2）：「注释图」多了「注释分组」选择器
          （`anno_group_combo`，items 由 W1 冻结为 `[group_graphed, cell_type, cluster]`，
          默认 index 0 = `group_graphed`）。**切分组 ⇒ 注释段作废**（与"样本选择变了
          就作废"同一条纪律，见 `_commit_selection`）——否则用户切了分组，
          结果区还挂着**上一个分组**出的图，标题一模一样，一眼看不出不一致。
        """
        try:
            btn = getattr(self.ui, 'btn_draw_anno_figure', None)
            if btn is not None and hasattr(btn, 'clicked'):
                btn.clicked.connect(self.on_draw_anno_figure_clicked)
            else:
                self._log("⚠ 布局未提供 btn_draw_anno_figure → 「绘图模式注释图」未绑定")
            combo = getattr(self.ui, 'anno_group_combo', None)
            if combo is None:
                self._log("⚠ 布局未提供 anno_group_combo → 「注释分组」不可选"
                          "（一律按默认 %s 出图）" % ANNO_GROUP_GRAPHED)
            else:
                sig = getattr(combo, 'currentIndexChanged', None)
                if sig is not None and hasattr(sig, 'connect'):
                    sig.connect(self._on_anno_group_combo_changed)
                else:
                    self._log("⚠ anno_group_combo 上没有 currentIndexChanged → "
                              "切换注释分组不会作废已出的注释图页签")
        except Exception:
            traceback.print_exc()

    def _current_anno_group(self):
        """读「注释分组」（`anno_group_combo.currentText()`）；控件缺失 → 默认分组 + 留痕"""
        try:
            combo = getattr(self.ui, 'anno_group_combo', None)
            if combo is not None:
                fn = getattr(combo, 'currentText', None)
                if callable(fn):
                    t = str(fn() or "").strip()
                    if t:
                        return t
        except Exception:
            traceback.print_exc()
        self._log("⚠ 取不到「注释分组」（anno_group_combo 缺失或为空）→ 按默认 %s 出图"
                  % ANNO_GROUP_GRAPHED)
        return ANNO_GROUP_GRAPHED

    def _on_anno_group_combo_changed(self, *args):
        """切换注释分组 ⇒ **注释段作废**：清 `_anno_entries_list` + 重画页签 + 留痕（§5.2）

        ★ `force=True` 才会立刻把旧分组的页签从结果区摘掉；随后的 `_render_result_tabs`
          会因为签名一致而直接 return（幂等，不重复解码）。
        """
        try:
            group = self._current_anno_group()
            n_anno = len(self._anno_entries_list or [])
            self._anno_entries_list = []
            self._render_result_tabs(force=True, reason="注释分组已切换")
            self._gene_log("注释分组已切到 %s：注释图页签已清空，请重新点一次出图" % group)
            self._log("注释分组已切到 %s：注释图页签已清空（原 %d 张），请重新点一次出图"
                      % (group, n_anno))
        except Exception:
            traceback.print_exc()

    def _anno_group_product(self, sid, out_dir, group):
        """按分组拼出该样本的预渲染产物 `(png 路径, 页签标题)`；该分组无产物 → `(None, None)`"""
        try:
            spec = ANNO_GROUP_PRODUCTS.get(str(group or "").strip())
            if not spec:
                return None, None
            sub, fn_tpl, title_tpl = spec
            return os.path.join(out_dir, sub, fn_tpl % sid), title_tpl % sid
        except Exception:
            traceback.print_exc()
            return None, None

    def _anno_sample_regions(self, regions_data, sid):
        """只读取某样本的 `regions`（`get_sample_regions` 永远返回 list；异常留痕不抛）"""
        try:
            return SREG.get_sample_regions(regions_data, sid)
        except Exception:
            traceback.print_exc()
            return []

    @staticmethod
    def _anno_has_group_graphed(regions):
        """`SREG.sample_has_group_graphed(regions)`（缺失/异常 → False + 留痕，绝不抛）"""
        try:
            fn = getattr(SREG, 'sample_has_group_graphed', None)
            if not callable(fn):
                print("[spatial_expression] ⚠ SREG.sample_has_group_graphed() 不存在 → "
                      "该样本按『没有绘图模式注释』处理（需要 W3 补）")
                return False
            return bool(fn(regions))
        except Exception:
            traceback.print_exc()
            return False

    def _anno_figure_paths(self, sid, out_dir):
        """【历史兼容】拼出该样本的三张候选图路径（**只拼路径，不判存在**）

        ★ v2 起「注释图」按 `anno_group_combo` **分流**（`_anno_group_product` +
          `group_graphed` 的两张），本方法**不再被主流程使用**。
          保留它是因为历史探针/文档按这个名字引用；**不要**在这里再挂分流逻辑
          （否则就是第二份"取图口径"）。
        """
        return (os.path.join(out_dir, ANNO_GRAPHED_SPOTS % sid),
                os.path.join(out_dir, ANNO_GRAPHED_NOSPOTS % sid),
                os.path.join(out_dir, "07_CellTypeAnno", "06_Spatial_per_sample",
                              "Spatial_%s.png" % sid))

    def _anno_output_dir(self):
        """解析 `OUTPUT/<ds>`（优先 `analysis.dataset_output_dir`，其次 `OUT_BASE/<ds>`）

        Returns:
            (out_dir, 原因)：取不到时 out_dir 为空串、原因非空（**不抛**）。
        """
        try:
            an = self.analysis
            out_dir = str(getattr(an, 'dataset_output_dir', '') or "") if an is not None else ""
            if out_dir:
                return out_dir, ""
            ds = self.dataset or self._dataset_name()
            if not ds:
                return "", "尚未确定数据集（请先在主页加载）"
            try:
                from script.utils_layer.import_config import OUT_BASE
            except Exception:
                traceback.print_exc()
                return "", "无法解析输出根目录（import_config.OUT_BASE 取不到）"
            return os.path.join(OUT_BASE, ds), ""
        except Exception:
            traceback.print_exc()
            return "", "解析输出目录时异常（见控制台 traceback）"

    def on_draw_anno_figure_clicked(self):
        """「注释图」：按 `anno_group_combo` 的**所选分组**逐样本取产物、各自成页签（§5.2）

        ## 分组 → 产物（**一页签一张图、逐张判**）
          | 选中分组 | 每样本产物 | 页签标题 | 缺产物 |
          |---|---|---|---|
          | `group_graphed`（默认） | `09_RegionOverride/Spatial_<sid>.png` /
            `SpatialNoSpots_<sid>.png` | `<sid> 带点` / `<sid> 不带点` |
            **`sample_has_group_graphed` 为假 ⇒ 跳过**（该样本没有绘图模式注释）；
            为真但图缺 ⇒ 跳过 + 日志（写期望路径，提示回「绘制区域」重绘） |
          | `cell_type` | `07_CellTypeAnno/06_Spatial_per_sample/Spatial_<sid>.png` |
            `<sid> cell_type` | 跳过 + 日志（写期望路径） |
          | `cluster` | `05_SpatialViz/02_Spatial_Cluster/Spatial_Cluster_<sid>.png` |
            `<sid> cluster` | 跳过 + 日志（写期望路径） |
          | 其它（将来） | — | 跳过 + 日志「该分组暂无预渲染产物（待补齐）」 |

        ## 硬纪律（一条都不许破）
          · **空选择不退化成"全部样本"**（与「绘制表达量图」同一条守卫）；
          · 页签一律走 `func.add_gene_result`（`_render_result_tabs` 里已有的唯一入口），
            本方法**不写任何建页签代码**；
          · 缺图**只写日志，绝不抛、绝不建空页签**；
          · 样本级 `regions` **只读**（`SREG.load_regions` + `SREG.get_sample_regions`，
            缺失/损坏返回空骨架，不抛）。
        """
        try:
            sel = self._current_selected_ids()
            if not sel:
                # 页面若没走过 `on_page_entered`（离屏构造/探针）清单会是空的 ⇒ 先补一次再读。
                self._ensure_sample_catalog("注释图前补清单")
                sel = self._current_selected_ids()
            if not sel:
                self._gene_log("请先在左侧选择样本，再点『绘图模式注释图』"
                               "（一个都没选时**不会**退化成全部样本）")
                self._log("未生成注释图：左侧没有选中任何样本")
                return

            self._ensure_analysis()
            out_dir, perr = self._anno_output_dir()
            if not out_dir:
                self._gene_log("未生成注释图：%s" % (perr or "无法解析输出目录"))
                self._log("未生成注释图：%s" % (perr or "无法解析输出目录"))
                return

            group = self._current_anno_group()
            # `group_graphed` 需要"该样本有没有绘图模式注释" ⇒ 只读载入 regions.json 骨架
            regions_all = None
            if group == ANNO_GROUP_GRAPHED:
                try:
                    regions_all = SREG.load_regions(self.dataset or self._dataset_name())
                except Exception:
                    traceback.print_exc()
                    regions_all = {}
                if not isinstance(regions_all, dict) or not regions_all.get('samples'):
                    self._log("⚠ 读不到 regions.json（或该数据集没有样本）→ "
                              "group_graphed 一律按空处理（本批各样本都会按规则跳过）")
                    if not isinstance(regions_all, dict):
                        regions_all = {}

            entries = []
            n_used = 0                 # 用到了产物的样本数
            n_skip_no_anno = 0         # 跳过：该样本没有绘图模式注释
            n_skip_missing = 0         # 跳过：有资格但产物缺失
            n_unknown_group = 0        # 跳过：该分组暂无预渲染产物
            for sid in [str(x) for x in sel]:
                if group == ANNO_GROUP_GRAPHED:
                    regs = self._anno_sample_regions(regions_all, sid)
                    if not self._anno_has_group_graphed(regs):
                        n_skip_no_anno += 1
                        self._gene_log("%s 没有绘图模式注释（group_graphed 为空）⇒ 按规则跳过"
                                       % sid)
                        continue
                    p_spots = os.path.join(out_dir, ANNO_GRAPHED_SPOTS % sid)
                    p_nospots = os.path.join(out_dir, ANNO_GRAPHED_NOSPOTS % sid)
                    got = 0
                    if os.path.isfile(p_spots):
                        entries.append(("%s 带点" % sid, p_spots))
                        got += 1
                    if os.path.isfile(p_nospots):
                        entries.append(("%s 不带点" % sid, p_nospots))
                        got += 1
                    if got:
                        n_used += 1
                    else:
                        n_skip_missing += 1
                        self._gene_log("%s 的绘图模式产物缺失（期望 %s / %s）⇒ "
                                       "请回「绘制区域」确认并重绘"
                                       % (sid, p_spots, p_nospots))
                    continue
                # ---- 其它分组：用图集已有产物做映射（**只读**）----
                p, title = self._anno_group_product(sid, out_dir, group)
                if p is None:
                    n_unknown_group += 1
                    continue
                if os.path.isfile(p):
                    entries.append((title, p))
                    n_used += 1
                else:
                    n_skip_missing += 1
                    self._gene_log("%s 的 %s 注释图不存在（期望 %s）⇒ 跳过"
                                   % (sid, group, p))

            if n_unknown_group:
                self._gene_log("注释分组『%s』：该分组暂无预渲染产物（待补齐）⇒ "
                               "本批 %d 个样本全部跳过" % (group, n_unknown_group))

            self._anno_entries_list = [tuple(x) for x in entries]
            # ★ 复用既有结果区（[注释段][基因段] 语义），**不另写建页签代码**
            self._render_result_tabs(force=True, reason="注释图（分组=%s）" % group)
            summary = ("注释图（分组=%s）：本批 %d 个样本 → %d 个页签；"
                       "用产物 %d 个样本，跳过 %d 个（「无绘图模式注释/无该分组产物」%d、"
                       "「产物缺失」%d%s）"
                       % (group, len(sel), len(entries), n_used,
                          n_skip_no_anno + n_skip_missing + n_unknown_group,
                          n_skip_no_anno + n_unknown_group, n_skip_missing,
                          ("、「分组暂无预渲染产物」%d" % n_unknown_group) if n_unknown_group else ""))
            self._gene_log(summary)
            self._log(summary)
        except Exception as e:
            traceback.print_exc()
            try:
                self._gene_log("❌ 生成注释图时异常：%s: %s（见控制台 traceback）"
                               % (type(e).__name__, e))
            except Exception:
                print("[spatial_expression] ❌ 生成注释图时异常：%s: %s"
                      % (type(e).__name__, e))

    # ==================================================================
    # ④ 样本清单按需补填（与 `on_page_entered` 同一真相源，幂等、只读）
    # ==================================================================
    def _ensure_sample_catalog(self, reason=""):
        """清单为空时按需补填一次左侧样本列表（**只读清单，不新增写盘**）

        Returns:
            bool: 补填后清单是否非空。
        """
        try:
            lst = getattr(self.ui, 'sample_list', None)
            if lst is not None and hasattr(lst, 'count') and lst.count() > 0:
                return True
            ds = self.dataset or self._dataset_name()
            if not ds:
                return False
            self.dataset = ds
            if not (self.figures or {}):
                self.figures = RA.list_all_figures(ds) or {}
            self._fill_sample_list()
            n = lst.count() if (lst is not None and hasattr(lst, 'count')) else 0
            if reason:
                self._log("样本清单按需补填（%s）：%d 条" % (reason, n))
            return bool(n)
        except Exception:
            traceback.print_exc()
            return False

    def _ensure_analysis(self):
        """确保 `self.analysis` 已解析（顶层 bind 的 analysis 是唯一数据层）"""
        try:
            if self.analysis is None:
                self._resolve_analysis()
            return self.analysis
        except Exception:
            traceback.print_exc()
            return None


__all__ = ['SpatialExpressionBind']
