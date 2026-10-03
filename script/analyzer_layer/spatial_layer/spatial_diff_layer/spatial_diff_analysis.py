# -*- coding: utf-8 -*-
"""
空转「差异分析」分析层（纯逻辑，无 UI）—— 继承单细胞 `DiffAnalysis` 的**全部统计**，
只替换两件事：**数据从哪来**（R dump + 逐 spot 注释合并 → 真 `anndata.AnnData`）
与**有哪些分组/注释值可选**（按所选样本取并集，契约 §4.2）。

契约：`_d_spec_spatial_diff.md`（v10）。本文件对应其 §6.1 / §11 与 §4.2。

## 一句话设计
    `SpatialDiffAnalysis(DiffAnalysis)`：
      · **白拿（不覆写）**：`bh_fdr` / `_run_mannwhitney_analysis` / `get_results` /
        `export_csv` / `export_png` —— 统计一行都不重写（复制的实现必然漂移）；
      · **覆写**：`get_available_groups()` / `get_group_unique_vals(col)`（只换判据，
        返回类型仍是 `list[str]`）、`run_diff_analysis(...)`（**签名与原型逐字一致**；
        内部只做"取参与样本 → R dump → 装 AnnData → 原样转发给 `super()`"）；
      · **新增**（W2 会按这些名字调用，**名字冻结**，契约 §6.1）：
        `set_context(dataset, samples, …)` / `available_group_columns()` /
        `group_unique_values(col)` / `participating_samples(col)` / **`prepare() -> bool`**。
      · `set_context` **廉价**（只记元数据）；真正昂贵的数据装配在 `prepare()` 里，
        且**幂等**（同一 `(dataset, samples)` 已装配过就不再跑 R dump）。
        bind 的"细胞筛选掩码"必须在 `get_filter_mask()` **之前** `prepare()`，
        否则首次运行时用户勾的筛选会被静默忽略（W2 已在掩码前存在性安全地调用）。

## 为什么必须走 R（而不是读 h5ad）
    空转成品的 `X` 是 **LogNormalize 之后的表达**，而差异分析的原型契约要求
    **原始 counts**（基类自己做 CP10K + log1p）。成品 `.rds` 的 `Spatial` assay 有
    `counts`/`data` 两层且**语义不同**（`docs/features/spatial_algo_design_w3.md:233`）
    ⇒ 只能在 R 侧显式取 `counts`（见 `spatial_diff_dump.R`，本文件只调用它）。

## 数据流（全部只读；写盘只发生在 `_diff/`）
    ① `SREG.load_spots(dataset, sid)`         → 逐 spot `spot/sample/cluster/cell_type`（+x/y）
    ② `region_labels_<sid>.csv`（若有）        → 逐 spot `region_label`
    ③ `appdata/<ds>.regions.json`（只读）      → 逐 spot `group_graphed`（区域 `anno_label`）
    ④ `spatial_diff_dump.R`（一次 readRDS）    → 每样本 `counts` 稀疏矩阵 + 逐 spot obs
    ⑤ 逐 spot 左连接 ①~④ → `adata.obs`；`adata.X` = 原始 counts（CSR）；
       `adata.var.index` = 基因名（R 侧 `genes.txt` 的顺序）
    ★ `spots.csv` **不含** `region_label` / `group_graphed` / `group` 三列 ⇒
      它们必须在 Python 侧 join（这正是 `anndata.obs` 的来源）。
    ★ **绝不**用"产物是否存在"反推注释资格（`09_RegionOverride/*.png` /
      `_figure_manifest.csv`）：资格的唯一真相源是 `SREG.sample_has_group_graphed`
      （= 存在 `anno_label` 非空的有效区域）—— 见测试
      `tests/test_spatial_top_smoke.py:6404-6406` 的明文反例锚点。

## `adata.obs` 索引（★ 跨样本唯一性）
    索引 = **合成 uid `"<sample>|<spot>"`**，`spot` 原串另存一列 `obs["spot"]`。
    理由：Visium barcode 是**逐切片**的（不同切片会出现同一个 `AAACAAGTATCTCCCA-1`），
    而 Seurat `merge()` 是否给 colnames 加样本前缀**不由本页控制**；基类的
    `all_cells.index(cell)` 取的是**第一个匹配**，一旦重复就是**静默错配**（统计错而不报错）。
    合成 uid 是确定性的、结构上不可能重复（并在装配时**断言**唯一；万一撞了，
    追加序号 + 留痕，**绝不静默**）。代价：`obs.index` 不再等于 barcode ——
    调用方构造 `filter_mask`（原型是 `pd.Series(..., index=adata.obs.index)`）时
    **必须用 `adata.obs.index`**，不要自己拼 barcode。

## 异常纪律（契约 §7.4）
    · 任何 `except` 都 `traceback.print_exc()` + `print("[spatial_diff] …")`，**不许静默**；
    · 所有降级（缺 spots.csv / 缺 region_labels / regions.json 坏 / R 少了样本）都进
      `self.annotation_notes`，UI 可以 `get_annotation_notes()` 原样回显；
    · 对外失败一律 `raise ValueError("<可读原因>")`（W2 会 alert + 写日志）。
"""

import json
import os
import subprocess
import sys
import traceback

from script.utils_layer.import_config import *          # os / sys / traceback / np / pd / OUT_BASE …
# ★ `anndata` **不在** import_config.__all__ 里（它只 import 了、没导出）
#   ⇒ 必须显式 import，否则 `from … import *` 拿不到。
import anndata
from scipy.io import mmread
from scipy.sparse import vstack as sparse_vstack

from script.analyzer_layer.scRNAseq_layer.diff_layer.py_diff.diff_analysis import DiffAnalysis
# ★ R 子进程纪律（`find_rscript` / `_decode` / `is_ascii_path` / `sanitize_samples` /
#   `_safe_unlink`）**复用同一真相源**，不在这里再写第二套（与 SpatialViolinAnalysis 同款）。
from script.analyzer_layer.spatial_layer.spatial_expression_layer import (
    spatial_gene_expression_analysis as GEA)
# ★ v11（`_d_spec_v11_split_and_bubble.md` §3.3）：分组候选白名单与 `group_graphed` 列的
#   真相源**统一到区域层**（该模块零项目内 import ⇒ 不会与任何页产生循环）。
#   ⛔ 此前是从 `spatial_expression_layer.spatial_violin_analysis` 取 —— 小提琴页 v11 已
#      搬去 `spatial_violin_layer/`，且两个新气泡页也要用同一份白名单 ⇒ 下沉到 `SREG`。
#      本文件**不再**import 小提琴模块（否则"页面解离"就白做了）。
from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as SREG


# -----------------------------------------------------------------------------
# 常量
# -----------------------------------------------------------------------------
# 与 spatial_diff_dump.R 严格一致的结果行前缀
RESULT_MARKER = "##SPATIAL_DIFF_RESULT##"

# 按需目录（与 GEA / 小提琴一致）＋本页新增子目录（契约 §7.3 / §7.7）
ON_DEMAND_SUBDIR = "08_GeneOnDemand"
DIFF_SUBDIR = "_diff"

# R 脚本与本文件同目录
_HERE = os.path.dirname(os.path.abspath(__file__))
_DUMP_R_REL = "spatial_diff_dump.R"


def spot_libsize(x):
    """逐 spot 的**总 counts**（CP10K 的分母；下限 1.0 防除零）

    Args:
        x: counts 矩阵（`self.adata.X`；稀疏/稠密均可）
    Returns:
        `np.ndarray[float64]`，长度 = spot 数

    ★★ v11 口径真相源（`_d_spec_v11_split_and_bubble.md` §2.6）：
      空转 dump 出来的是 **counts 层**（`spatial_diff_dump.R` 明文只取 counts、
      还带"非负 + 整数"完整性检查）⇒ `self.adata.X` **是原始 counts**，
      **不是** LogNormalize 之后的表达。
      ⛔ 千万不要拿原始 counts 直接算"平均表达"：每个 spot 的测序深度不同，
         depth 大的 spot 对**所有**基因都会显得"高表达"⇒ 色标变成文库大小的伪影。
      ⇒ 与差异分析**报的同一个量**对齐：差异页的均值列就叫 `mean_CP10K`
        （`diff_analysis.py:162-174` 内部自己算 CP10K + log1p）。
        气泡图的颜色也必须用 **CP10K**，否则同一次取数在两个页面上口径不一致。

    ★ 逐位同源：分母下限 `max(libsize, 1)` 与 `diff_analysis.py:166-167` 一致。
    """
    ls = np.asarray(x.sum(axis=1)).ravel().astype(float)
    return np.maximum(ls, 1.0)


def resolve_dump_r_script():
    """定位 `spatial_diff_dump.R`（相对本文件；找不到返回 `''`）

    ★ **模块级函数**（不是实例方法）：架构冻结断言
      `tests/test_spatial_top_smoke.py::test_page_r_scripts_are_located_next_to_their_own_page_module`
      用 `getattr(module, 'resolve_dump_r_script')` 取**模块属性**并实测返回值
      ⇒ 每页的 `.R` 必须与本页 analysis 模块**同目录**、且靠这个函数定位
      （同 `spatial_violin_analysis.resolve_dump_r_script` / `spatial_region_analysis.resolve_*_r_script`）。
    只做 `os.path.isfile` ⇒ 只读、不跑 R、不写文件。
    """
    p = os.path.normpath(os.path.join(_HERE, _DUMP_R_REL))
    return p if os.path.isfile(p) else ""

# `group_graphed` 的列名：真相源 = 区域层模块（`"group_graphed"`）
GROUP_GRAPHED = SREG.GROUP_GRAPHED

# ⭐ 判据白名单 = 区域层的 `ANNOTATION_CANDIDATES`（**唯一真相源**，不许本地再抄；
#   v11 由小提琴模块**下沉**到 `SREG`，见文件头 import 处的说明）
#   顺序即下拉框顺序：group, cell_type, cluster, sample, region_label, group_graphed
ANNOTATION_CANDIDATES = SREG.ANNOTATION_CANDIDATES
CANDIDATE_COLUMNS = tuple(ANNOTATION_CANDIDATES)

# `adata.obs` 的列顺序（冻结；`spot` 是原串 barcode，索引另用合成 uid）
FROZEN_OBS_COLUMNS = ("spot", "sample", "cluster", "cell_type",
                      "region_label", GROUP_GRAPHED, "group")

# R dump 的默认超时：一次 readRDS（实测 ≈5.5 s）+ 逐样本写稀疏矩阵
# （每样本 59–127 MB 量级，19 样本合计约 1.19 GB —— 与原始 10x `.mtx` 同量级，
#  见 `docs/features/spatial_data_storage_recon_ledger.md` §3 的 19 个 `.mtx` 台账）。
# 小提琴 dump 用 900 s 是"一个基因"的口径；本脚本一次要写全部参与样本
# ⇒ 默认放宽到 1800 s（仍可被调用方覆写）。
DEFAULT_TIMEOUT = 1800


def _warn(msg):
    """留痕（契约 §7.4：不许静默）。统一前缀，方便在整合日志里 grep。"""
    print("[spatial_diff] %s" % msg)
    try:
        sys.stdout.flush()
    except Exception as e:                      # pragma: no cover - 极端环境
        print("[spatial_diff] flush failed: %r" % (e,))


class SpatialDiffAnalysis(DiffAnalysis):
    """空间版差异分析：统计**全部继承**，只换"取数据 + 选项枚举"。"""

    # -------------------------------------------------------------------------
    # 构造 / 上下文
    # -------------------------------------------------------------------------
    def __init__(self):
        super().__init__()
        # ---- 空间上下文（`set_context` 填）----
        self.dataset = None
        self.samples = []                   # 所选样本（保序、去重、已清洗）
        self.out_dir = None                 # 数据集输出根（= OUTPUT/<dataset>）
        self.rds_path = None                # 成品 .rds 绝对路径（必须 ASCII）
        self.timeout = DEFAULT_TIMEOUT      # R 子进程超时（可覆写）
        # 探针/自检可显式注入（契约 §6.1 的可选入参；生产路径由本层自行解析）
        self._supplied_spots = None         # {sample_id: [spot_row, …]}
        self._supplied_regions = None       # {sample_id: [region, …]}
        # ---- dump / 装配产物（便于排障；**不写盘**）----
        self.dump_result = None             # R 侧 JSON 原样保存
        self.dump_dir = ""                  # 实际使用的 `_diff/` 目录
        self.loaded_samples = []            # 真正装进 adata 的样本（= R 的 samples_used）
        self.last_load_info = {}            # 装配摘要（行数/基因数/降级计数）
        self.last_prepare_error = ""        # `prepare()` 最近一次失败原因（供调用方转文案）
        self.annotation_notes = []          # 降级说明（缺文件/缺列/错位…），供 UI 回显
        # ★ `prepare()` 的幂等标记：`(dataset, tuple(请求的样本))` ——
        #   同一上下文已装配过 ⇒ 直接返回 True，**不再跑 R dump**（readRDS 很贵）。
        self._prepared_key = None
        # 中间产物（`.mtx`/`obs.csv`/`genes.txt`）装完 adata 后是否保留。
        # ★ 默认**删除**：每样本 59–127 MB、19 样本 ≈1.19 GB，留着会持续吃盘；
        #   W5/自检需要留证时把它设 True 即可（删除动作一律留痕）。
        self.keep_dump_files = False
        # ---- 只读缓存（`clear_cache()` / `set_context()` 清空；重算不写盘）----
        self._spots_cache = {}              # {sid: [spot_row, …]}
        self._has_graph_cache = {}          # {sid: bool}
        self._anno_rows_cache = {}          # {sid: [ann_row, …]}
        self._regions_raw_cache = None      # `SREG.load_regions(dataset)` 的结果

    def set_context(self, dataset, samples=None, spots_by_sample=None,
                    regions_by_sample=None, out_dir=None, rds_path=None):
        """记住上下文（**冻结签名**：前两位是 `dataset, samples`）。

        Args:
            dataset: 数据集名（= `OUTPUT/<dataset>` 的目录名，也是 `.rds` 主名）。
            samples: **所选样本**（`list[str]` / 逗号串 / None）。
                     None 或空 = **没有选择**（本页**不会**退化成"全部样本"：
                     空选时分组/注释值全为空，`run_diff_analysis` 直接给可读错误）。
            spots_by_sample: 可选。`{sample_id: [spot_row, …]}`；给了就**不再读**
                     `spots.csv`（契约 §6.1 的入参形态，供探针注入夹具）。
            regions_by_sample: 可选。`{sample_id: [region, …]}`；给了就**不再读**
                     `regions.json`。
            out_dir: 可选。数据集输出根；None ⇒ `OUT_BASE/<dataset>`。
            rds_path: 可选。成品 `.rds`；None ⇒ `SPATIAL_SCAN_DATA_PATH/<dataset>.rds`。

        ★ 解析口径与 `ui_bind_spatial_expression._resolve_gene_paths()` **同源**
          （`OUT_BASE` / `SPATIAL_SCAN_DATA_PATH`），不造第二套规则。
        ★ 本方法**只记上下文**（廉价：不读盘、不写盘、不跑 R、不抛）——装配在 `prepare()`
          里发生；`available_group_columns()` / `group_unique_values()` /
          `participating_samples()` 只依赖这里记下的元数据。
        ★ 幂等：**同一 `(dataset, samples)`** 再调一次 ⇒ 保留 `prepare()` 的已装配标记
          （不会因为 bind 每次进页重同步上下文而白跑一次 R dump）；上下文真变了 ⇒
          标记作废、`self.adata` 置 None（避免调用方拿着**上一个数据集**的 adata 建筛选掩码）。
        """
        old_key = self._prepared_key
        self.dataset = str(dataset or "").strip() or None

        # ---- 样本清洗（唯一真相源：GEA.sanitize_samples；含逗号会被当分隔符，同小提琴口径）----
        raw_samples = samples
        if raw_samples is None:
            raw_samples = []
        if isinstance(raw_samples, str):
            clean, err = GEA.sanitize_samples(raw_samples)
        else:
            try:
                clean, err = GEA.sanitize_samples(list(raw_samples))
            except TypeError as e:
                traceback.print_exc()
                clean, err = [], "samples 类型不支持：%r（%s）" % (type(raw_samples).__name__, e)
        if err:
            _warn("set_context: samples 解析失败，按**空选**处理（不静默）：%s" % err)
            self.annotation_notes.append("样本列表解析失败（已按空选处理）：%s" % err)
            clean = []
        self.samples = [str(s) for s in (clean or [])]

        # ---- 输出根 / rds 路径 ----
        if out_dir:
            self.out_dir = str(out_dir)
        else:
            base = str(OUT_BASE or "")
            self.out_dir = os.path.join(base, self.dataset) if (base and self.dataset) else None
        if rds_path:
            self.rds_path = str(rds_path)
        else:
            scan = str(SPATIAL_SCAN_DATA_PATH or "")
            self.rds_path = (os.path.join(scan, "%s.rds" % self.dataset)
                             if (scan and self.dataset) else None)

        # 基类 `export_png` 会对 `dataset_output_dir` 做 makedirs ⇒ 指向本页新增子目录（契约 §7.7）
        self.dataset_output_dir = self._diff_dir() or None

        # ---- 注入的夹具（探针用；生产路径恒为 None）----
        self._supplied_spots = dict(spots_by_sample) if isinstance(spots_by_sample, dict) else None
        self._supplied_regions = (dict(regions_by_sample)
                                  if isinstance(regions_by_sample, dict) else None)

        self.clear_cache()

        # ---- 幂等标记（见 docstring：同一上下文保标记；真变了就作废并把 adata 置空）----
        same_ctx = (old_key is not None
                    and old_key[0] == self.dataset
                    and list(old_key[1]) == list(self.samples))
        if same_ctx:
            self._prepared_key = old_key
        else:
            self._prepared_key = None
            if self.adata is not None:
                _warn("set_context: 上下文已变化 ⇒ 丢弃上一次装配的 adata（防止用旧数据建筛选掩码）")
                self.adata = None
                self.loaded_samples = []
        _warn("set_context: dataset=%s | samples=%s | out_dir=%s | rds=%s"
              % (self.dataset or "(未定)", self.samples or "(空选)",
                 self.out_dir or "(未解析)", self.rds_path or "(未解析)"))
        return True

    def clear_cache(self):
        """清空**只读缓存**（换上下文 / 区域被外部改动后调用）

        ★ 只清内存里的 spots/regions 缓存，**不碰** `adata` 与 `prepare()` 的幂等标记：
          需要"连 adata 一起重装"时，正确做法是重新 `set_context(dataset, samples)`
          （它会作废标记并按需重跑一次 dump）。
        """
        self._spots_cache = {}
        self._has_graph_cache = {}
        self._anno_rows_cache = {}
        self._regions_raw_cache = None

    def set_rds_path(self, rds_path):
        """显式指定成品 `.rds`（W2 若能拿到 `artifact_info['path']` 就优先给它）"""
        self.rds_path = str(rds_path) if rds_path else None

    def get_annotation_notes(self):
        """所有降级/异常说明（供 UI 日志原样回显；**不会抛**）"""
        return list(self.annotation_notes)

    def _note(self, msg):
        """降级说明：既进 notes（UI 可见），也 print（控制台可见）——**不静默**"""
        self.annotation_notes.append(str(msg))
        _warn(msg)

    # -------------------------------------------------------------------------
    # 路径
    # -------------------------------------------------------------------------
    def _diff_dir(self):
        """本页唯一允许写盘的目录：`OUTPUT/<ds>/08_GeneOnDemand/_diff/`（契约 §7.7）"""
        if not self.out_dir or not self.dataset:
            return ""
        return os.path.join(str(self.out_dir), ON_DEMAND_SUBDIR, DIFF_SUBDIR)

    def resolve_dump_r_script(self):
        """定位 `spatial_diff_dump.R`（委托给**模块级**同名函数；找不到返回 `''`）"""
        return resolve_dump_r_script()

    def find_rscript(self):
        """Rscript 定位：复用 `GEA.find_rscript()`（R_HOME → PATH → 本机兜底）"""
        return GEA.find_rscript()

    # -------------------------------------------------------------------------
    # 只读数据供给：逐 spot 注释行（候选列的**唯一数据源**）
    # -------------------------------------------------------------------------
    def _sample_spots(self, sample_id):
        """某样本的 spots 行（含 x/y）——`SREG.load_spots`（或注入夹具）；取不到 → `[]`

        `SREG.load_spots` 已经给出 `{spot, sample, x, y, cluster, cell_type}`，
        这里只做**归一化**（键缺失补空串、spot 为空的行剔除并留痕），不改判据。
        """
        sid = str(sample_id or "")
        if not sid:
            return []
        if sid in self._spots_cache:
            return self._spots_cache[sid]

        rows = None
        if self._supplied_spots is not None and sid in self._supplied_spots:
            _v = self._supplied_spots.get(sid)
            if isinstance(_v, (list, tuple)):
                rows = list(_v)
                _warn("样本 %s：使用**注入夹具**的 spots（%d 行），未读 spots.csv" % (sid, len(rows)))
            else:
                self._note("注入的 spots_by_sample[%s] 不是 list（%s）⇒ 忽略夹具，回退读 spots.csv"
                           % (sid, type(_v).__name__))
        if rows is None:
            if not self.dataset:
                self._note("尚未确定数据集 ⇒ 样本 %s 的 spots 为空" % sid)
                rows = []
            else:
                try:
                    rows, err = SREG.load_spots(self.dataset, sid)
                except Exception as e:
                    traceback.print_exc()
                    self._note("SREG.load_spots(%s, %s) 异常（%s）⇒ 该样本 spots 为空"
                               % (self.dataset, sid, e))
                    rows = []
                else:
                    if err:
                        # ★ 缺文件/缺样本不是异常（W3 可能还没导出坐标表）⇒ 降级 + 留痕
                        self._note("样本 %s 取不到 spots：%s" % (sid, err))
                        rows = []

        clean, n_bad = [], 0
        for r in (rows or []):
            if not isinstance(r, dict):
                n_bad += 1
                continue
            spot = str(r.get("spot") or "").strip()
            if not spot:
                n_bad += 1
                continue
            clean.append({
                "spot": spot,
                "sample": str(r.get("sample") or "").strip() or sid,
                "x": r.get("x"), "y": r.get("y"),
                "cluster": str(r.get("cluster") or "").strip(),
                "cell_type": str(r.get("cell_type") or "").strip(),
            })
        if n_bad:
            self._note("样本 %s 有 %d 行 spot 无法解析/缺 spot（已剔除，不参与任何分组统计）"
                       % (sid, n_bad))
        if not clean:
            self._note("样本 %s 没有任何可用 spot 行 ⇒ 该样本不参与分组并集" % sid)
        self._spots_cache[sid] = clean
        return clean

    def _sample_regions(self, sample_id):
        """某样本的区域列表（**只读**）：注入夹具优先，否则 `regions.json`（经 `get_sample_regions`）"""
        sid = str(sample_id or "")
        if not sid:
            return []
        if self._supplied_regions is not None:
            try:
                regs = self._supplied_regions.get(sid)
                # 两种注入形态都接受：`[区域, …]` 或 `{"regions": [区域, …]}`
                # （后者与 `regions.json` 的每样本结构一致，探针不必先拆包）
                if isinstance(regs, dict):
                    inner = regs.get("regions")
                    return list(inner) if isinstance(inner, list) else []
                return list(regs) if isinstance(regs, (list, tuple)) else []
            except Exception:
                traceback.print_exc()
                return []
        if not self.dataset:
            return []
        if self._regions_raw_cache is None:
            try:
                data = SREG.load_regions(self.dataset)
            except Exception as e:
                traceback.print_exc()
                self._note("regions.json 读取异常（%s）⇒ 所有样本的 %s 视为空"
                           % (e, GROUP_GRAPHED))
                data = {}
            issues = list((data or {}).get("_issues") or [])
            if issues:
                self._note("regions.json 读取有说明（不阻断）：%s" % "; ".join(str(x) for x in issues))
            self._regions_raw_cache = data
        try:
            return list(SREG.get_sample_regions(self._regions_raw_cache, sid) or [])
        except Exception as e:
            traceback.print_exc()
            self._note("取样本 %s 的区域时异常（%s）⇒ 该样本区域为空" % (sid, e))
            return []

    def _sample_has_graph(self, sample_id):
        """该样本是否"画了图/有 graph 注释"（**唯一判据**：`SREG.sample_has_group_graphed`）

        ⛔ 绝不用 `09_RegionOverride/*.png` / `_figure_manifest.csv` 等**产物存在性**反推
           （测试 `test_spatial_top_smoke.py:6404-6406` 明文锚定该反例）。
        """
        sid = str(sample_id or "")
        if not sid:
            return False
        if sid not in self._has_graph_cache:
            regs = self._sample_regions(sid)
            try:
                self._has_graph_cache[sid] = bool(SREG.sample_has_group_graphed(regs))
            except Exception as e:
                traceback.print_exc()
                self._note("SREG.sample_has_group_graphed(%s) 异常（%s）⇒ 该样本按**无** graph 处理"
                           % (sid, e))
                self._has_graph_cache[sid] = False
        return self._has_graph_cache[sid]

    def _sample_region_labels(self, sample_id):
        """某样本的 `{spot: region_label}`（读 `region_labels_<sid>.csv`；缺文件 ⇒ `{}`）

        读法与小提琴一致：**缺文件不是错误**（绝大多数样本本来就没进过绘图模式），
        但要留痕；`region_labels_<sid>.csv` 的真相源路径 = `SREG.labels_csv_path_for`。
        """
        sid = str(sample_id or "")
        if not sid:
            return {}
        cands = []
        if self.out_dir and self.dataset:
            cands.append(os.path.join(str(self.out_dir), SREG.WORKBENCH_DIR,
                                      "region_labels_%s.csv" % sid))
        try:
            p = SREG.labels_csv_path_for(self.dataset, sid)
            if p:
                cands.append(p)
        except Exception:
            traceback.print_exc()
        path = next((p for p in cands if p and os.path.isfile(p)), "")
        if not path:
            _warn("样本 %s 无 region_labels_%s.csv ⇒ 该样本 region_label 全空（group 回退 cell_type）"
                  % (sid, sid))
            return {}
        try:
            df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
        except Exception as e:
            traceback.print_exc()
            self._note("region_labels_%s.csv 读取失败（%s）⇒ 该样本 region_label 全空" % (sid, e))
            return {}
        if "spot" not in df.columns or "label" not in df.columns:
            self._note("region_labels_%s.csv 缺 spot/label 列（实际：%s）⇒ 该样本 region_label 全空"
                       % (sid, list(df.columns)))
            return {}
        m = {}
        for s, lb in zip(df["spot"].astype(str).tolist(), df["label"].astype(str).tolist()):
            s = str(s or "").strip()
            if s:
                m[s] = str(lb or "").strip()
        _warn("region_labels_%s.csv: %d 行，其中非空 label %d 个（%s）"
              % (sid, len(m), sum(1 for v in m.values() if v), path))
        return m

    def _sample_graphed_map(self, sample_id):
        """某样本的 `{spot: group_graphed}`（区域 `anno_label`，**只含非空值**）

        · 没有 graph 注释（`sample_has_group_graphed` 假）⇒ `{}`（**正常情况**）；
        · 标签数与 spot 数不一致 / 取不到坐标 ⇒ **整样本降级为空**（**绝不错位**）。
        """
        sid = str(sample_id or "")
        if not sid or not self._sample_has_graph(sid):
            return {}
        rows = self._sample_spots(sid)
        if not rows:
            self._note("样本 %s 有 graph 注释但取不到 spot 坐标 ⇒ %s 全空（不错位，整样本降级）"
                       % (sid, GROUP_GRAPHED))
            return {}
        regs = self._sample_regions(sid)
        try:
            labels = SREG.group_graphed_labels(rows, regs)
        except Exception as e:
            traceback.print_exc()
            self._note("样本 %s 的 group_graphed 计算异常（%s）⇒ 该样本为空" % (sid, e))
            return {}
        if len(labels) != len(rows):
            self._note("样本 %s 的 %s 标签数(%d)与 spot 数(%d)不一致 ⇒ 整样本降级为空（绝不错位）"
                       % (sid, GROUP_GRAPHED, len(labels), len(rows)))
            return {}
        m = {}
        for row, lb in zip(rows, labels):
            key = str(row.get("spot") or "")
            val = str(lb or "").strip()
            if key and val:
                m[key] = val
        _warn("样本 %s: regions=%d | %s 非空 spot=%d/%d"
              % (sid, len(regs), GROUP_GRAPHED, len(m), len(rows)))
        return m

    def _sample_annotation_rows(self, sample_id):
        """★ 候选列的**唯一数据源**：逐 spot 一行、带全部 6 个候选列的 dict 列表

        返回的每行键 = `spot,sample,cluster,cell_type,region_label,group_graphed,group`
        （`group` = `region_label` 非空则取它，否则取 `cell_type` —— 与小提琴 `load_gene`
         的 `group` 同规则）。

        ★ 为什么做成"逐 spot 行"：这样 §4.2 的并集口径可以对**任何**候选列复用
          `SREG.anno_values_from_spots(rows, col)` 同一个函数（区域层与注释层不会各写一套），
          并且 `available_group_columns` / `group_unique_values` / `adata.obs` 三处
          **共用同一份数据**（口径不可能漂移）。
        """
        sid = str(sample_id or "")
        if not sid:
            return []
        if sid in self._anno_rows_cache:
            return self._anno_rows_cache[sid]
        spots = self._sample_spots(sid)
        if not spots:
            self._anno_rows_cache[sid] = []
            return []
        rmap = self._sample_region_labels(sid)
        gmap = self._sample_graphed_map(sid)
        out = []
        for r in spots:
            spot = r.get("spot") or ""
            ct = str(r.get("cell_type") or "").strip()
            lb = str(rmap.get(spot) or "").strip()
            gg = str(gmap.get(spot) or "").strip()
            out.append({
                "spot": spot,
                "sample": str(r.get("sample") or "").strip() or sid,
                "cluster": str(r.get("cluster") or "").strip(),
                "cell_type": ct,
                "region_label": lb,
                GROUP_GRAPHED: gg,
                "group": lb if lb else ct,
                # 坐标保留：`group_graphed` 的逐 spot 判定要用（`_sample_spots` 已带过来）
                "x": r.get("x"), "y": r.get("y"),
            })
        self._anno_rows_cache[sid] = out
        return out

    # -------------------------------------------------------------------------
    # §4.2 判据：可用分组 / 注释值 / 参与样本
    #   ★ v11（`_d_spec_v11_split_and_bubble.md` §3.3）：真正的**并集口径**已下沉到
    #     `SREG.anno_union_values` / `SREG.participating_samples_for_col`（纯函数）。
    #     本类的三个方法**公共名字与返回类型一字不改**，只负责：
    #       ① 按 `self.samples` 装配 `rows_by_sample` / `has_graph_by_sample`（含逐样本容错+留痕）；
    #       ② 调纯函数；
    #       ③ 留痕日志。
    #     ⇒ 两个新气泡页**继承**本类即自动获得逐位相同的选项语义（用户硬要求）。
    # -------------------------------------------------------------------------
    def _anno_rows_by_sample(self):
        """`{sid: [ann_row, …]}`（顺序 = `self.samples`；逐样本异常 ⇒ 该样本记 `[]` + 留痕）

        ★ 容错与留痕留在**本层**（纯函数不吞异常）；`_sample_annotation_rows` 自身有缓存。
        """
        out = {}
        for sid in self.samples:
            try:
                out[sid] = self._sample_annotation_rows(sid)
            except Exception as e:
                traceback.print_exc()
                self._note("取样本 %s 的注释行时异常（%s）⇒ 该样本不贡献任何注释值" % (sid, e))
                out[sid] = []
        return out

    def _has_graph_by_sample(self):
        """`{sid: bool}`（判据 = `sample_has_group_graphed`；异常 ⇒ 按**无** graph 处理 + 留痕）"""
        out = {}
        for sid in self.samples:
            try:
                out[sid] = bool(self._sample_has_graph(sid))
            except Exception as e:
                traceback.print_exc()
                self._note("判定样本 %s 有无 graph 注释时异常（%s）⇒ 按**无**处理" % (sid, e))
                out[sid] = False
        return out

    def available_group_columns(self):
        """§4.2.1 **可用分组列**（`list[str]`，顺序 = `ANNOTATION_CANDIDATES`）：

        白名单 `ANNOTATION_CANDIDATES` ∩ 「该列在**所选样本的并集**里有非空值」。
        · `group_graphed` 的并集**只统计"有 graph 注释"的样本**（`sample_has_group_graphed`
          为假的样本一律不计入）⇒ 全为假时该分组**完全不出现**；
        · `S` 为空 ⇒ `[]`（§4.2.4 边界，不崩）；
        · **不**加 `nunique ≥ 2` 过滤（基础类有，本页按 §4.2.1 冻结口径**不加**：
          只剩一个取值的分组仍要出现，运行按钮/日志侧提示"无法比较"）。
        ★ 判据只看 `self.samples`（**不看 dataset**）：spots/regions 可以由
          `set_context(..., spots_by_sample=…, regions_by_sample=…)` 注入夹具 ⇒
          纯函数级探针不需要真数据集、也不会碰盘。
        """
        if not self.samples:
            return []
        rows_by_sample = self._anno_rows_by_sample()
        has_graph = self._has_graph_by_sample()
        cols = []
        for col in CANDIDATE_COLUMNS:
            try:
                if SREG.anno_union_values(rows_by_sample, col, has_graph):
                    cols.append(col)
            except Exception as e:
                traceback.print_exc()
                self._note("枚举分组列 %s 时异常（%s）⇒ 该列不出现" % (col, e))
        _warn("available_group_columns: %s（所选样本 %d 个）"
              % (cols or "（无）", len(self.samples)))
        return cols

    def group_unique_values(self, col):
        """§4.2.2 **某分组的注释值列表**（`list[str]`）：

        `⋃_{s∈S} anno_values_from_spots(rows(s), col)` → 去重去空 → **`sorted(...)`**
        （排序口径与单细胞 `get_group_unique_vals()` 的 `sorted(unique 值)` 一致 ——
         这是 1:1 复刻的一部分；`anno_values_from_spots` 的"保序"是小提琴页的口径，不用于本页）。

        · `col == group_graphed` 时，**只**统计 `sample_has_group_graphed` 为真的样本；
        · `S` 为空 / 列不存在 / 无任何非空值 ⇒ `[]`（不崩）。
        ★ 判据只看 `self.samples`（不看 dataset）—— 见 `available_group_columns` 的说明。
        """
        if not col:
            return []
        col = str(col)
        if not self.samples:
            return []
        try:
            # ★ 并集口径的唯一实现（`sorted` 也在里面）—— 见 `SREG.anno_union_values`
            return SREG.anno_union_values(self._anno_rows_by_sample(), col,
                                          self._has_graph_by_sample())
        except Exception as e:
            traceback.print_exc()
            self._note("枚举分组 %s 的取值并集时异常（%s）⇒ 返回空列表" % (col, e))
            return []

    def participating_samples(self, col):
        """§4.2.3 **实际参与分析的样本**（保序 = 所选样本顺序）：

        · `col == group_graphed` ⇒ 只保留 `sample_has_group_graphed(regions(s))` 为真的样本
          （用户原话：**只分析带 graph 注释的那个样本**）；
        · 其它列 ⇒ 保留"该列在该样本里有非空值"的样本；
        · 参与集合与**被排除**的样本都写进日志（§4.2.3 明令，不许静默）。
        ★ 判据只看 `self.samples`（不看 dataset）—— 见 `available_group_columns` 的说明。
        """
        if not self.samples or not col:
            return []
        col = str(col)
        try:
            # ★ 参与判据的唯一实现 —— 见 `SREG.participating_samples_for_col`
            used = SREG.participating_samples_for_col(
                self.samples, self._anno_rows_by_sample(), col,
                self._has_graph_by_sample())
        except Exception as e:
            traceback.print_exc()
            self._note("判定参与分组 %s 的样本时异常（%s）⇒ 无样本参与" % (col, e))
            used = []
        # 「被排除」由调用方求差（纯函数只回"参与"）—— §4.2.3 明令两者都要留痕
        used_set = set(used)
        excluded = [sid for sid in self.samples if sid not in used_set]
        _warn("participating_samples(%s): 参与=%s | 排除=%s"
              % (col, used or "（无）", excluded or "（无）"))
        return used

    # -------------------------------------------------------------------------
    # 基类契约的两个覆写（**只换判据，返回类型不变**）
    # -------------------------------------------------------------------------
    def get_available_groups(self):
        """覆写：返回 §4.2.1 的分组列（`list[str]`），不再用 obs 的 `2 ≤ nunique ≤ 100`"""
        return self.available_group_columns()

    def get_group_unique_vals(self, group_col):
        """覆写：返回 §4.2.2 的注释值（`list[str]`），不再直接取 obs 的 unique"""
        return self.group_unique_values(group_col)

    # -------------------------------------------------------------------------
    # R dump（子进程纪律逐条照抄 `SpatialViolinAnalysis.run_dump`）
    # -------------------------------------------------------------------------
    @staticmethod
    def _parse_result_line(stdout):
        """从子进程 stdout 取**最后一条** `##SPATIAL_DIFF_RESULT##` JSON（找不到 ⇒ `None`）"""
        if not stdout:
            return None
        found = None
        for line in str(stdout).splitlines():
            idx = line.find(RESULT_MARKER)
            if idx < 0:
                continue
            payload = line[idx + len(RESULT_MARKER):].strip()
            if not payload:
                continue
            try:
                found = json.loads(payload)
            except ValueError as e:
                _warn("解析 R 结果行失败（忽略该行）：%s" % e)
                continue
        return found if isinstance(found, dict) else None

    @staticmethod
    def _as_list(v):
        """把可能是标量的字段强制成 list（R 侧 `auto_unbox` 会把长度 1 的向量脱成标量）"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]

    @staticmethod
    def _as_dict(v):
        """把可能是空数组（`[]`）的字段强制成 dict（R 侧空 named list 可能序列化成 `[]`）"""
        if isinstance(v, dict):
            return v
        if isinstance(v, list):
            out = {}
            for i, item in enumerate(v):
                out[str(i)] = item
            return out
        return {}

    def run_dump(self, samples, timeout=None):
        """调 `spatial_diff_dump.R`：**一次 readRDS**，把参与样本的 counts + obs 落 `_diff/`

        Returns:
            `(ok: bool, result: dict, error: str)` —— **绝不抛**（与 `GEA.run_gene_expression`
            同纪律）；调用方（`load_expression`）负责把 error 转成 `ValueError` 并留痕。

        子进程纪律（逐条照抄小提琴/表达量图）：
          · `stdin=DEVNULL`（绝不给 R 交互机会）+ `timeout` + `cwd=` 已断言为 ASCII 的目录；
          · stdout/stderr 全捕获、`GEA._decode` 逐级退化解码（本机 R console 可能是 GBK）；
          · 找不到结果行 / `ok=false` ⇒ `(False, {}, 可读原因)`，把 stderr 尾巴带上。
        """
        clean_samples = [str(s) for s in (samples or []) if str(s or "").strip()]
        if not clean_samples:
            return False, {}, "参与分析的样本为空（请先选择样本）"
        if not self.dataset:
            return False, {}, "尚未确定数据集（请先在主页加载）"
        if not self.out_dir or not self.rds_path:
            return False, {}, "上下文不完整：dataset/out_dir/rds_path 有一项没解析出来"
        if not GEA.is_ascii_path(self.rds_path):
            return False, {}, ("rds_path 含非 ASCII 字符，已拒绝：%s（非 ASCII 路径会让 R 弹交互式"
                               "目录菜单，在 rpy2 下会变成无限循环）" % self.rds_path)
        if not GEA.is_ascii_path(self.out_dir):
            return False, {}, "out_dir 含非 ASCII 字符，已拒绝：%s" % self.out_dir
        if not GEA.is_ascii_path(self.dataset):
            return False, {}, "dataset 含非 ASCII 字符，已拒绝：%s" % self.dataset
        if not os.path.isfile(self.rds_path):
            return False, {}, "成品 .rds 不存在：%s" % self.rds_path

        r_script = self.resolve_dump_r_script()
        if not r_script:
            return False, {}, ("找不到 R 脚本 %s（期望位置：%s）"
                               % (_DUMP_R_REL, os.path.normpath(os.path.join(_HERE, _DUMP_R_REL))))

        try:
            timeout_val = int(timeout if timeout is not None else self.timeout)
        except (TypeError, ValueError):
            return False, {}, "timeout 不是整数：%r" % (timeout,)
        if timeout_val <= 0:
            return False, {}, "timeout 必须为正数：%d" % timeout_val

        diff_dir = self._diff_dir()
        if not diff_dir:
            return False, {}, "无法解析 `_diff/` 目录（out_dir/dataset 缺失）"
        try:
            os.makedirs(diff_dir, exist_ok=True)
        except OSError as e:
            return False, {}, "无法创建 `_diff/` 目录（%s）：%s" % (diff_dir, e)
        if not os.path.isdir(diff_dir):
            return False, {}, "无法创建 `_diff/` 目录：%s" % diff_dir

        cmd = [self.find_rscript(), r_script, self.rds_path, str(self.out_dir),
               str(self.dataset), "--samples", ",".join(clean_samples)]
        _warn("run_dump: cmd=%s" % " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,      # ★ 绝不给 R 任何交互机会
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_val,
                cwd=diff_dir,                  # cwd 也放在已断言为 ASCII 的目录里
            )
        except subprocess.TimeoutExpired:
            return False, {}, ("R dump 超时（>%ds）：样本 %d 个。一次 readRDS≈5.5 s + 逐样本写稀疏矩阵"
                               "（每样本 59–127 MB 量级），可提高 timeout 或减少样本。"
                               % (timeout_val, len(clean_samples)))
        except OSError as e:
            return False, {}, "无法启动 R 子进程（%s）：%s" % (cmd[0], e)

        stdout = GEA._decode(proc.stdout)
        stderr = GEA._decode(proc.stderr)
        result = self._parse_result_line(stdout)

        if result is None:
            reason = (stderr or stdout or "").strip()
            if len(reason) > 800:
                reason = reason[-800:]
            return False, {}, ("R 子进程未产出可解析结果（returncode=%s）：%s"
                               % (proc.returncode, reason or "无任何输出"))
        if not result.get("ok"):
            return False, {}, "R 报告失败：%s" % result.get("error", "未知原因")
        if proc.returncode != 0:
            result["r_returncode"] = proc.returncode
            _warn("run_dump: R 退出码 %s 但 ok=true（如实记录，不掩盖）" % proc.returncode)
        if stderr:
            result["stderr_tail"] = stderr[-800:]
            _warn("run_dump: R stderr 尾巴（不掩盖）：%s" % stderr[-300:].replace("\n", " | "))

        # 归一化"应该是数组/对象"的字段（防 R 侧漏加 I()；与 GEA._normalize_result 同一理由）
        for key in ("samples_used", "samples_missing", "samples_requested", "samples_empty",
                    "assays_available"):
            result[key] = self._as_list(result.get(key))
        out_files = self._as_dict(result.get("out_files"))
        for key in ("obs_csv", "mtx", "nnz_per_sample", "spots_per_sample"):
            out_files[key] = self._as_dict(out_files.get(key))
        result["out_files"] = out_files

        miss = [str(s) for s in result.get("samples_missing", [])]
        if miss:
            # 缺失样本**不硬失败**（与小提琴 dump 同口径），但必须留痕
            self._note("请求的样本在数据里不存在（R 已跳过，不失败）：%s" % ", ".join(miss))
        empty = [str(s) for s in result.get("samples_empty", [])]
        if empty:
            self._note("R 侧这些样本 QC 后**没有任何 spot**（已跳过）：%s" % ", ".join(empty))
        failed = self._as_dict(result.get("failed_samples"))
        if failed:
            # 逐样本失败**不中断整批**（照 E4 精神），但必须让用户看见少了哪些样本
            self._note("R 侧这些样本 dump **失败**（已跳过，整批继续）：%s"
                       % "; ".join("%s: %s" % (k, v) for k, v in failed.items()))
        return True, result, ""

    # -------------------------------------------------------------------------
    # 装配 AnnData（本层唯一的"新数据供给层"）
    # -------------------------------------------------------------------------
    def _adata_ready(self):
        """当前 `adata` 是否正好对应 `(dataset, 当前所选样本)`（`prepare()` 的幂等判据）"""
        if self.adata is None or self._prepared_key is None:
            return False
        return (self._prepared_key[0] == self.dataset
                and list(self._prepared_key[1]) == list(self.samples))

    def prepare(self):
        """★ 冻结接口：按当前 `set_context` 的 `(dataset, samples)` 装配 `self.adata`

        Returns:
            bool：True = `adata` 就绪（可安全地 `adata.obs.index` 建筛选掩码 / 直接跑统计）；
                  False = 无上下文或装配失败（**已留痕**，原因见 `self.last_prepare_error`
                  与 `get_annotation_notes()`）。

        ★ 为什么需要它：bind 的"细胞筛选掩码"必须用 `adata.obs.index` 构造（照原型），
          而**首次运行**时若 adata 还没装配，用户勾的筛选就会被静默忽略
          ⇒ 调用方应在 `get_filter_mask()` **之前**调本方法。
        ★ **幂等**：同一 `(dataset, samples)` 已装配过 ⇒ 直接 True，**不再跑 R dump**
          （一次 readRDS ≈5.5 s + 逐样本写稀疏矩阵，重复跑纯属浪费）。
        ★ **绝不抛**：一切异常 → `traceback.print_exc()` + 留痕 + False。
        """
        self.last_prepare_error = ""
        try:
            if not self.dataset or not self.samples:
                msg = "尚无上下文（dataset/samples 为空）——请先 set_context(dataset, samples)"
                self._note("prepare: %s" % msg)
                self.last_prepare_error = msg
                return False
            if self._adata_ready():
                _warn("prepare: 命中幂等缓存（dataset=%s，样本 %d 个）⇒ 不重复 dump"
                      % (self.dataset, len(self.samples)))
                return True
            self.load_expression(self.samples)
            return True
        except ValueError as e:
            # `load_expression` 内部已留痕；这里只补一层"调用方视角"的说明
            traceback.print_exc()
            self._note("prepare: 装配失败（ValueError）：%s" % e)
            self.last_prepare_error = str(e)
            return False
        except Exception as e:
            traceback.print_exc()
            self._note("prepare: 装配失败（%s）：%s" % (type(e).__name__, e))
            self.last_prepare_error = "%s: %s" % (type(e).__name__, e)
            return False

    def load_expression(self, samples=None, timeout=None):
        """① 调 R dump → ② 逐 spot join 注释 → ③ 装 `anndata.AnnData` → ④ `set_adata()`

        Args:
            samples: 参与的样本（None ⇒ 用 `self.samples`）
            timeout: R 子进程超时（None ⇒ `self.timeout`）
        Returns:
            `anndata.AnnData`：`.obs` 索引 = 合成 uid `"<sample>|<spot>"`，
            `.obs` 列 = `spot,sample,cluster,cell_type,region_label,group_graphed,group`，
            `.var.index` = 基因名（R 侧 `genes.txt` 顺序），`.X` = **原始 counts**（CSR, float32）。
        Raises:
            `ValueError("<可读原因>")`（此前已 `traceback.print_exc()` 或 `_note()` 留痕）
        """
        use = [str(s) for s in (samples if samples is not None else self.samples) or []]
        if not use:
            raise ValueError("请先选择样本（空选不会退化成全部样本）")
        if not self.dataset:
            raise ValueError("尚未确定数据集，请先在主页加载数据集")

        # ---- ① R dump（一次 readRDS，只 dump 参与样本）----
        ok, result, err = self.run_dump(use, timeout=timeout)
        if not ok:
            _warn("load_expression: R dump 失败：%s" % err)
            raise ValueError("空转差异分析取数失败：%s" % err)
        self.dump_result = result
        diff_dir = str(result.get("diff_dir") or self._diff_dir() or "")
        self.dump_dir = diff_dir
        samples_used = [str(s) for s in self._as_list(result.get("samples_used"))]
        if not samples_used:
            raise ValueError("R dump 报告没有任何可用样本（samples_used 为空）")
        genes_n_r = result.get("genes_n")
        layer_used = str(result.get("layer_used") or "")
        _warn("load_expression: R dump 完成：samples_used=%s | genes_n=%s | spots_n=%s | layer=%s"
              % (samples_used, genes_n_r, result.get("spots_n"), layer_used))

        # ---- ①' 基因顺序（`genes.txt`）----
        out_files = self._as_dict(result.get("out_files"))
        f_genes = str(out_files.get("genes_txt") or "") or os.path.join(diff_dir, "genes.txt")
        genes = self._read_genes(f_genes, genes_n_r)

        # ---- ② 逐样本读稀疏矩阵 + obs.csv，逐 spot join 注释 ----
        obs_maps = self._as_dict(out_files.get("obs_csv"))
        mtx_maps = self._as_dict(out_files.get("mtx"))
        nnz_map = self._as_dict(out_files.get("nnz_per_sample"))
        blocks, uids, load_info = [], [], {}
        # 冻结列顺序的"列名 → list"容器（装配完直接交给 pd.DataFrame，不再二次整理）
        obs_cols = {k: [] for k in FROZEN_OBS_COLUMNS}
        n_join_miss = 0
        for sid in samples_used:
            x_csr, n_spots = self._read_sample_matrix(
                str(mtx_maps.get(sid) or "") or os.path.join(diff_dir, "%s.mtx" % sid),
                sid, len(genes))
            odf = self._read_sample_obs(
                str(obs_maps.get(sid) or "") or os.path.join(diff_dir, "%s.obs.csv" % sid), sid)
            if len(odf) != n_spots:
                msg = ("样本 %s 的 obs.csv 行数(%d) != 矩阵列数(%d) —— 拒绝装配（宁可失败也不错位）"
                       % (sid, len(odf), n_spots))
                _warn("load_expression: %s" % msg)
                raise ValueError(msg)

            anno = {r["spot"]: r for r in self._sample_annotation_rows(sid)}
            for spot, r_ct, r_cl in zip(odf["spot"].tolist(),
                                        odf["cell_type"].tolist(),
                                        odf["cluster"].tolist()):
                spot = str(spot or "").strip()
                row = anno.get(spot)
                if row is None:
                    n_join_miss += 1
                ct_spots = str((row or {}).get("cell_type") or "").strip()
                cl_spots = str((row or {}).get("cluster") or "").strip()
                # 与 `spots.csv` 同口径：spots.csv 有值就用它，为空再回退 R dump 的同名列
                cell_type = ct_spots or str(r_ct or "").strip()
                cluster = cl_spots or str(r_cl or "").strip()
                rl = str((row or {}).get("region_label") or "").strip()
                gg = str((row or {}).get(GROUP_GRAPHED) or "").strip()
                obs_cols["spot"].append(spot)
                obs_cols["sample"].append(sid)
                obs_cols["cluster"].append(cluster)
                obs_cols["cell_type"].append(cell_type)
                obs_cols["region_label"].append(rl)
                obs_cols[GROUP_GRAPHED].append(gg)
                obs_cols["group"].append(rl if rl else cell_type)
                uids.append("%s|%s" % (sid, spot))
            blocks.append(x_csr)
            load_info[sid] = {"spots": int(n_spots),
                              "nnz": self._as_int_or(nnz_map.get(sid), -1)}
            _warn("load_expression: 样本 %s 装配完成：spots=%d（矩阵 %s）"
                  % (sid, n_spots, "x".join(str(d) for d in x_csr.shape)))

        if not blocks:
            raise ValueError("没有任何样本被装配进 AnnData（samples_used=%s）" % samples_used)
        if n_join_miss:
            self._note("%d 个 spot 在 spots.csv 里找不到对应行（注释按空串处理，**绝不丢弃该 spot**）"
                       % n_join_miss)

        # ---- ③ 索引唯一性（★ 跨样本 barcode 可能重复 ⇒ 合成 uid，并**断言**唯一）----
        uids = self._ensure_unique_index(uids)
        obs_df = pd.DataFrame(obs_cols, columns=list(FROZEN_OBS_COLUMNS))
        obs_df.index = pd.Index(uids, name="spot_uid")

        X = sparse_vstack(blocks, format="csr")
        if X.shape != (len(obs_df), len(genes)):
            msg = ("装配后的 X 形状 %s 与 obs(%d) × genes(%d) 不符 —— 拒绝交付（宁可失败也不错位）"
                   % (tuple(X.shape), len(obs_df), len(genes)))
            _warn("load_expression: %s" % msg)
            raise ValueError(msg)
        # 计数：整数计数用 float32 足够（1e7 以内精确），且省一半内存（原型的 X 也是 float32）
        X = X.astype(np.float32)

        adata = anndata.AnnData(X=X, obs=obs_df,
                                var=pd.DataFrame(index=pd.Index(genes, name=None)))
        self.set_adata(adata)
        self.loaded_samples = list(samples_used)
        # ★ 幂等标记按**请求的**样本记（不是 R 实际命中的 samples_used）：
        #   否则 R 少报一个样本就会导致每次调用都重跑 dump。
        self._prepared_key = (self.dataset, tuple(use))
        self.last_prepare_error = ""
        self.last_load_info = {
            "samples_used": list(samples_used),
            "samples_requested": list(use),
            "obs_n": int(adata.n_obs),
            "genes_n": int(adata.n_vars),
            "nnz": int(X.nnz),
            "dtype": str(X.dtype),
            "layer_used": layer_used,
            "diff_dir": diff_dir,
            "per_sample": load_info,
            "obs_join_miss": int(n_join_miss),
        }
        _warn("load_expression: AnnData 就绪：obs=%d × genes=%d | nnz=%d | dtype=%s | 索引首例=%s"
              % (adata.n_obs, adata.n_vars, X.nnz, X.dtype, uids[0] if uids else "(空)"))

        # ---- 清理中间产物（默认删；每样本 59–127 MB，留着会持续吃盘）----
        self._cleanup_dump_files(result, diff_dir)
        return adata

    # —— load_expression 的小工具（全部只读 / 全部留痕）——
    def _read_genes(self, path, genes_n_r):
        """读 `genes.txt`（**保序、不去重**：行序 = 每个 `.mtx` 的行序）"""
        if not path or not os.path.isfile(path):
            msg = "R 未产出 genes.txt（期望 %s）" % (path or "(空路径)")
            _warn("load_expression: %s" % msg)
            raise ValueError(msg)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                genes = [ln.rstrip("\r\n") for ln in f]
        except OSError as e:
            traceback.print_exc()
            raise ValueError("读取 genes.txt 失败（%s）：%s" % (path, e))
        genes = [g for g in genes if g.strip()]
        if not genes:
            raise ValueError("genes.txt 为空：%s" % path)
        if len(set(genes)) != len(genes):
            # 基因名重复本身不致命（原型也照抄 var.index），但会与 R 侧行数对不上时必须炸
            self._note("genes.txt 有重复基因名（%d/%d）——按原样保留（不去重，保持与矩阵行对齐）"
                       % (len(genes) - len(set(genes)), len(genes)))
        try:
            n_r = int(genes_n_r)
        except (TypeError, ValueError):
            n_r = -1
        if n_r > 0 and n_r != len(genes):
            msg = ("genes.txt 行数(%d) 与 R 报告的 genes_n(%d) 不一致 —— 拒绝装配（宁可失败也不错位）"
                   % (len(genes), n_r))
            _warn("load_expression: %s" % msg)
            raise ValueError(msg)
        return genes

    def _read_sample_matrix(self, path, sid, n_genes):
        """读某样本的 `.mtx`（MatrixMarket：**行=基因、列=spot**）→ `csr_matrix`（spot × 基因）"""
        if not path or not os.path.isfile(path):
            msg = "样本 %s 的 .mtx 不存在：%s" % (sid, path or "(空路径)")
            _warn("load_expression: %s" % msg)
            raise ValueError(msg)
        try:
            coo = mmread(path)
        except Exception as e:
            traceback.print_exc()
            raise ValueError("读取样本 %s 的 .mtx 失败（%s）：%s: %s" % (sid, path, type(e).__name__, e))
        if int(coo.shape[0]) != int(n_genes) or int(coo.shape[1]) <= 0:
            msg = ("样本 %s 的 .mtx 形状 %s 与 genes(%d) 不符（行必须是基因、列必须是 spot）"
                   " —— 拒绝装配（宁可失败也不错位）" % (sid, tuple(coo.shape), int(n_genes)))
            _warn("load_expression: %s" % msg)
            raise ValueError(msg)
        if coo.nnz and float(coo.data.min()) < 0:
            msg = "样本 %s 的 counts 出现负值（最小 %r）—— 不是原始 counts，拒绝装配" % (sid, float(coo.data.min()))
            _warn("load_expression: %s" % msg)
            raise ValueError(msg)
        # 转置成 spot × gene（coo.T 只是交换 row/col 数组，成本极低）
        return coo.T.tocsr(), int(coo.shape[1])

    def _read_sample_obs(self, path, sid):
        """读某样本的 `obs.csv`（列**至少**含 `spot`；可含 `sample,cluster,cell_type`）"""
        if not path or not os.path.isfile(path):
            msg = "样本 %s 的 obs.csv 不存在：%s" % (sid, path or "(空路径)")
            _warn("load_expression: %s" % msg)
            raise ValueError(msg)
        try:
            df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
        except Exception as e:
            traceback.print_exc()
            raise ValueError("读取样本 %s 的 obs.csv 失败（%s）：%s" % (sid, path, e))
        if "spot" not in df.columns:
            raise ValueError("样本 %s 的 obs.csv 缺 spot 列（实际：%s）" % (sid, list(df.columns)))
        for c in ("sample", "cluster", "cell_type"):
            if c not in df.columns:
                self._note("样本 %s 的 obs.csv 缺 %s 列 ⇒ 该列用空串" % (sid, c))
                df[c] = ""
        return df

    @staticmethod
    def _as_int_or(v, default):
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _ensure_unique_index(self, uids):
        """★ 断言 `obs` 索引唯一；万一撞了 ⇒ 追加序号 + **留痕**（绝不静默）"""
        if len(set(uids)) == len(uids):
            return uids
        seen, out, n_dup = {}, [], 0
        for u in uids:
            if u in seen:
                seen[u] += 1
                n_dup += 1
                out.append("%s#%d" % (u, seen[u]))
            else:
                seen[u] = 0
                out.append(u)
        self._note("合成 uid 出现 %d 个重复（样本名/spot 里含 `|` 的极端情形）⇒ 已追加序号；"
                   "obs 索引保持唯一" % n_dup)
        return out

    def _cleanup_dump_files(self, result, diff_dir):
        """装完 adata 后删除中间产物（默认行为；`keep_dump_files=True` 时保留）——**一律留痕**"""
        if self.keep_dump_files:
            _warn("keep_dump_files=True ⇒ 保留中间产物于 %s" % diff_dir)
            return
        out_files = self._as_dict(result.get("out_files"))
        paths = [str(out_files.get("genes_txt") or "")]
        for key in ("obs_csv", "mtx"):
            paths += [str(p) for p in self._as_dict(out_files.get(key)).values()]
        n_ok, n_fail = 0, 0
        for p in paths:
            if not p:
                continue
            try:
                if os.path.isfile(p):
                    os.remove(p)
                    n_ok += 1
            except OSError as e:
                n_fail += 1
                _warn("删除中间产物失败（忽略，不影响结果）：%s：%s" % (p, e))
        _warn("已删除中间产物 %d 个（失败 %d 个）；`_diff/` 目录保留：%s"
              % (n_ok, n_fail, diff_dir))

    # -------------------------------------------------------------------------
    # 主入口（★ 签名与原型逐字一致）
    # -------------------------------------------------------------------------
    def run_diff_analysis(self, group_col, selected_groups, method="mannwhitney",
                          min_cells=3, min_expr=0, use_fdr=True,
                          pval_threshold=0.05, logfc_threshold=1.0, pct_threshold=0.1,
                          filter_mask=None):
        """执行差异分析（空转版：只换数据供给层，统计 100% 走 `super()`）

        流程（契约 §6.1 / §4.2.3）：
          ① `samples = self.participating_samples(group_col)`
             —— `group_graphed` 时**只分析带 graph 注释的样本**，其它列取"该列有非空值"的样本；
          ② `self.prepare()` 装配 `anndata.AnnData`（**幂等**：已装配过就复用，不重复 dump；
             调用方若已提前 prepare（为了建 `filter_mask`），这里零成本）；
             ★ 装配的是**全部所选样本**，而统计只取两个组别的 `isin` 命中行 ⇒
               未参与样本的该分组列**必然全空**，结构上不可能混进组1/组2（不影响任何统计量），
               同时保证 `filter_mask`（按 `adata.obs.index` 构造）与这里用的是**同一份** adata；
          ③ `super().run_diff_analysis(...)` **原样转发全部参数**（含 `filter_mask`）。

        ⚠ 与原型一致的口径（契约 §6.2 / §7.8，**必须如实告知用户**）：
          · 以 **spot 为独立观测**做 Mann-Whitney U，**未做 pseudobulk**
            （同一样本内 spot 空间自相关 ⇒ p 值偏乐观）；这是**对原型的忠实复刻**；
          · `min_expr` 与 `pct_threshold` / `method` 在原型的 Mann-Whitney 分支里
            **收下但不用**（原型即如此）⇒ 本页照此，不新增过滤。

        Raises:
            `ValueError`：空选样本 / 该分组在所选样本里没有取值 / 取数失败 /
            基类的"细胞数不足"等（文案与原型逐字一致的那条由基类给出）。
        """
        if not self.samples:
            raise ValueError("请先选择样本（空选不会退化成全部样本）")
        samples = self.participating_samples(group_col)
        if not samples:
            raise ValueError("分组 %s 在所选样本里没有任何可用取值（请换分组或换样本）"
                             % (group_col or "(空)"))
        _warn("run_diff_analysis: group_col=%s | selected_groups=%s | 参与样本=%s | min_cells=%s"
              % (group_col, selected_groups, samples, min_cells))

        # ② 取数并装配（`prepare()` 内部已 set_adata；失败一律 ValueError + 留痕）
        if not self.prepare():
            raise ValueError("空转差异分析取数失败：%s"
                             % (self.last_prepare_error or "未知原因（见控制台 traceback/日志）"))

        # ③ 统计部分**一个字都不重写**，原样转发全部参数
        return super().run_diff_analysis(
            group_col, selected_groups,
            method=method, min_cells=min_cells, min_expr=min_expr, use_fdr=use_fdr,
            pval_threshold=pval_threshold, logfc_threshold=logfc_threshold,
            pct_threshold=pct_threshold, filter_mask=filter_mask)


__all__ = ["SpatialDiffAnalysis", "RESULT_MARKER", "CANDIDATE_COLUMNS",
           "FROZEN_OBS_COLUMNS", "GROUP_GRAPHED", "ON_DEMAND_SUBDIR", "DIFF_SUBDIR",
           # v11：CP10K 分母的共享实现（两个气泡页都要用它，见函数 docstring 的口径说明）
           "spot_libsize", "resolve_dump_r_script"]
