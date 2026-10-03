# -*- coding: utf-8 -*-
"""
空转「小提琴图」分析层（纯逻辑，无 UI）—— 继承单细胞 `ViolinAnalysis` 的**全部**绘图/显著性/导出。

设计要点（契约 `_d_spec_expr_two_modes.md` §4.2 / §5 / §8）：
  · **绘图/显著性/导出一律继承**，本文件**不复制**任何一个 `plot_*` / `add_significance_marks` /
    `export_*` 的实现（复制必然漂移）。已 AST 核对：那批方法只依赖
    `self.violin_df` / `self.current_figs` / `self.current_axes` / `self.violin_gene` / `self.filtered_df`，
    **不碰 `self.adata`** —— 所以空间版只需要把 `violin_df` / `violin_gene` 喂好。
  · 与单细胞唯一的差别在"数据从哪来"：空间数据不在 adata 里，而是
      ① R dump 出逐 spot 表达量 CSV（`spatial_violin_dump.R`，与表达量图**同一 data 层**）；
      ② 再与 `_region_workbench/spots.csv`（原始 cell_type）和每样本
         `_region_workbench/region_labels_<sid>.csv`（绘图模式新注释）逐 spot 合并。
  · **绝不写 appdata/**；本模块只读 appdata 的 .rds 与 OUTPUT/<ds>/_region_workbench/，
    以及 §6 新增的 `appdata/spatial_main/<ds>.regions.json`（**只读**，派生 group_graphed 列），
    新增写盘只经过 R 脚本落到 `OUTPUT/<ds>/08_GeneOnDemand/_violin/<gene>.csv`。

★ 两条必须守住的继承契约（漏了会静默 KeyError，来自协调者实测）：
  1. `self.violin_gene` 必须设成**用户输入的基因名原串**（继承的 plot_* 用它取 y 值、拼产物路径）；
  2. `self.violin_df` 里必须有一列**名字恰好等于该基因名** —— R dump 写的列名是 `expr`，
     所以合并时必须 `rename(columns={"expr": gene})`。**不做大小写/别名变换**（R 侧已负责匹配）。

★ 异常纪律（契约 §8）：一切 except 都留痕（`print`），**不许静默**；
  对外失败一律抛 `ValueError("<可读原因>")`，绝不吞掉（W2 会 alert + 写日志）。

导入风格：本模块**有意只用标准库 + pandas**（与 `spatial_gene_expression_analysis` 同一条理由：
不把 scanpy 等重依赖拖进后台线程）。R 侧定位/子进程纪律**复用同目录的
`spatial_gene_expression_analysis`**（同一真相源：`find_rscript` / `_decode` / `is_ascii_path`），
只 import 该模块本身，不重复实现。
"""

import os
import subprocess
import sys
import traceback

import pandas as pd

from script.analyzer_layer.scRNAseq_layer.violin_layer.violin_analysis import ViolinAnalysis
from script.analyzer_layer.spatial_layer.spatial_expression_layer import spatial_gene_expression_analysis as GEA
# ★ §6：`group_graphed` 列的真相源 = 区域内部字段（`anno_label`），所以必须取区域层。
#   本模块**只读**它（`load_regions` / `get_sample_regions` / `group_graphed_labels` / `load_spots`），
#   一个字都不写回 appdata。
from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as SREG


# R 结果行的前缀（与 spatial_violin_dump.R 严格一致）
RESULT_MARKER = "##SPATIAL_VIOLIN_RESULT##"

# 按需目录（与 GEA / R 脚本一致）
ON_DEMAND_SUBDIR = "08_GeneOnDemand"
VIOLIN_SUBDIR = "_violin"

# 合并后可用的分组列候选顺序（契约 §4.2：存在者才给）
# ★ §6（`_d_spec_region_naming_v2.md`）：`group_graphed` 追加在 `region_label` **之后**（顺序冻结）
# ★ v11（`_d_spec_v11_split_and_bubble.md` §3.3）：**唯一真相源已下沉到区域层**
#   （`SREG.ANNOTATION_CANDIDATES`）。本模块改为**再导出同一个对象**：
#     · 既有探针 `_d_verify_region_naming.py:411-414` 读 `SVA.ANNOTATION_CANDIDATES` 继续有效；
#     · 文档锚点（契约 §20.6 / §6）继续有效；
#     · ⛔ 绝不在这里再写第二份字面量（抄了就会漂移 —— 这正是 v11 要消灭的东西）。
ANNOTATION_CANDIDATES = SREG.ANNOTATION_CANDIDATES

# 冻结的 violin_df 列顺序（契约 §4.2；§6：`group_graphed` 插在 `region_label` 与 `group` **之间**）
FROZEN_COLUMNS = ("spot", "sample", "cluster", "cell_type", "region_label", "group_graphed", "group")

# 分组列的 nunique 判据（复刻单细胞 load_gene：1 < nunique < 60）
MIN_GROUP_NUNIQUE = 1
MAX_GROUP_NUNIQUE = 60

# 子进程超时（与 GEA 一致：900 s）
DEFAULT_TIMEOUT = 900

_HERE = os.path.dirname(os.path.abspath(__file__))
_DUMP_R_REL = "spatial_violin_dump.R"


def resolve_dump_r_script():
    """定位 `spatial_violin_dump.R`（**相对本文件**；找不到返回 `''`）

    ★ v11（`_d_spec_v11_split_and_bubble.md` §1.1）：本函数从「实例方法」提为
      **模块级函数**，实例方法改为委托（`return resolve_dump_r_script()`）。
      理由：架构冻结断言
      `tests/test_spatial_top_smoke.py::test_page_r_scripts_are_located_next_to_their_own_page_module`
      用 `getattr(module, 'resolve_dump_r_script')` 取**模块属性**并实测返回值
      ⇒ 每页的 `.R` 必须与本页 analysis 模块**同目录**、且靠这个函数定位
      （写法逐字照 `spatial_diff_layer/spatial_diff_analysis.py:102-113`）。

    ★ `_HERE` / `_DUMP_R_REL` 本来就是"按本文件目录 + 同目录相对名"定位
      ⇒ 整块搬家（`spatial_expression_layer/` → `spatial_violin_layer/`）后**自动成立**，
      路径常量一个字都不用改。

    只做 `os.path.isfile` ⇒ 只读、不跑 R、不写文件。
    """
    p = os.path.normpath(os.path.join(_HERE, _DUMP_R_REL))
    return p if os.path.isfile(p) else ""


def _warn(msg):
    """留痕（契约 §8：不许静默）。统一前缀，方便在整合日志里 grep。"""
    print("[spatial_violin] %s" % msg)
    try:
        sys.stdout.flush()
    except Exception as e:                      # pragma: no cover - 极端环境
        print("[spatial_violin] flush failed: %r" % (e,))


class SpatialViolinAnalysis(ViolinAnalysis):
    """空间版小提琴图分析：数据来自 R dump + 注释逐 spot 合并；绘图/显著性/导出**全部继承**。"""

    def __init__(self):
        super().__init__()
        # ---- 空间上下文（set_context 填）----
        self.dataset = None
        self.out_dir = None                 # 数据集输出根（调用方给 OUTPUT/<ds>）
        self.rds_path = None
        self.samples = []
        # R dump / 出图的落盘根。**默认 = out_dir**（生产路径）；探针/自检可单独指向临时目录，
        # 好让"注释仍从真实 OUTPUT/<ds>/_region_workbench 读、dump 落临时盘"两件事解耦。
        self.dump_out_dir = None
        # ---- dump / 合并产物（load_gene 填，便于排障与复算）----
        self.dump_result = None             # R 侧 JSON（原样保存）
        self.spot_annotations = None        # spots.csv + region_labels 合并后的逐 spot 注释
        self.region_label_map = {}          # {sample_id: {spot: label}}
        # §6：{sample_id: {spot: anno_label}}（只读区域层派生；**只含非空值**）。
        # 与 region_label_map 同一形态 ⇒ load_gene 用**同一套查表代码**对齐（不会各写一套）。
        self.group_graphed_map = {}
        self.spots_csv_path = ""            # 实际使用的 spots.csv
        self.annotation_notes = []          # 降级说明（缺文件/缺列等），供 UI/日志回显

    # -------------------------------------------------------------------------
    # 上下文与路径定位
    # -------------------------------------------------------------------------
    def resolve_dump_r_script(self):
        """定位 spatial_violin_dump.R（相对本文件；找不到返回 ''）。

        ★ v11（§1.1）：实例方法**委托**模块级同名函数（`spatial_diff_analysis.py` 同款），
          保证「实例调用」与「模块属性取用」永远是**同一份实现**（不会各写一套）。
        """
        return resolve_dump_r_script()

    def find_rscript(self):
        """Rscript 定位：**复用** spatial_gene_expression_analysis.find_rscript()（同一真相源）。

        包一层是为了「同一真相源 + 可被覆写测试」两个目标同时成立：
        R_HOME → PATH → 本机开发兜底 的优先级与 4 条不变量仍由 GEA 实现决定。
        """
        return GEA.find_rscript()

    def set_context(self, dataset, out_dir, rds_path, samples):
        """记住上下文。

        参数：
          dataset  : 数据集名（= 输出目录名，如 GSE237183）
          out_dir  : **数据集输出根**（= OUTPUT/<dataset>）。`self.dataset_output_dir` 会被设成
                     `<out_dir>/08_GeneOnDemand`，好让**继承的** `draw_violin_plot` 把三张图落到
                     `<out_dir>/08_GeneOnDemand/<gene>/`（契约 §6）。
          rds_path : 成品 .rds 绝对路径（必须全 ASCII；R 侧也会断言）
          samples  : 选中的样本名列表（None/空 = 全部样本）
        """
        self.dataset = dataset
        self.out_dir = out_dir
        self.rds_path = rds_path
        # dump 落盘根默认跟随 out_dir；显式设过 dump_out_dir（自检/探针）时不覆盖
        self.dump_out_dir = self.dump_out_dir or out_dir
        if samples is None:
            self.samples = []
        elif isinstance(samples, str):
            clean, err = GEA.sanitize_samples(samples)
            if err:
                _warn("set_context: samples 解析失败：%s" % err)
                clean = []
            self.samples = clean
        else:
            clean, err = GEA.sanitize_samples(list(samples))
            if err:
                _warn("set_context: samples 解析失败：%s" % err)
                clean = []
            self.samples = clean

        # 继承的 draw_violin_plot 会 os.path.join(self.dataset_output_dir, self.violin_gene)
        self.dataset_output_dir = os.path.join(out_dir, ON_DEMAND_SUBDIR) if out_dir else None
        _warn("set_context: dataset=%s | out_dir=%s | samples=%s | dataset_output_dir=%s"
              % (dataset, out_dir, self.samples or "(all)", self.dataset_output_dir))

    def annotation_sources(self):
        """返回实际存在的分组列（按 ANNOTATION_CANDIDATES 顺序；violin_df 为空则返回 []）"""
        if self.violin_df is None:
            return []
        cols = list(self.violin_df.columns)
        return [c for c in ANNOTATION_CANDIDATES if c in cols]

    def _dump_root(self):
        """dump 落盘根（= out_dir，除非探针显式设过 dump_out_dir）"""
        return self.dump_out_dir or self.out_dir or ""

    def get_annotation_notes(self):
        """返回所有降级/异常说明（供 UI 日志回显；不会抛）"""
        return list(self.annotation_notes)

    # -------------------------------------------------------------------------
    # 读注释（spots.csv + region_labels_<sid>.csv）
    # -------------------------------------------------------------------------
    def _workbench_dir(self):
        if not self.out_dir:
            return ""
        return os.path.join(self.out_dir, "_region_workbench")

    def _load_spots_annotations(self, spot_series):
        """
        读 `_region_workbench/spots.csv`（列 `spot,sample,x,y,cluster,cell_type`），返回
        与 spot_series 对齐的 (sample, cluster, cell_type) 三个 list。

        降级策略（契约 §5 / §8：缺文件缺列一律降级 + 留痕，不许崩）：
          · spots.csv 找不到 / 读失败 / 缺 spot 列 → 三列全用**空串**，写日志；
          · 某 spot 不在 spots.csv 里 → 该行补空串（**绝不丢弃该 spot**，否则小提琴的 n 会莫名变少）；
          · spots.csv 的 cell_type 为空/NA 时，保留 R dump 里给出的 cell_type（若有）。
        """
        n = len(spot_series)
        wb = self._workbench_dir()
        cand = [os.path.join(wb, "spots.csv"),
                os.path.join(self.out_dir or "", "07_CellTypeAnno", "spots.csv")]
        path = next((p for p in cand if p and os.path.isfile(p)), "")

        if not path:
            self.annotation_notes.append("spots.csv 未找到（尝试：%s）⇒ sample/cluster/cell_type 用空串"
                                         % "; ".join([p for p in cand if p]))
            _warn("spots.csv 未找到，注释列降级为空串（尝试路径：%s）" % "; ".join([p for p in cand if p]))
            return [""] * n, [""] * n, [""] * n

        try:
            df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
        except Exception as e:
            self.annotation_notes.append("spots.csv 读取失败（%s）⇒ 注释列用空串" % e)
            _warn("spots.csv 读取失败：%s ⇒ 注释列降级为空串" % e)
            return [""] * n, [""] * n, [""] * n

        self.spots_csv_path = path
        cols = set(df.columns)
        if "spot" not in cols:
            self.annotation_notes.append("spots.csv 缺 spot 列（实际列：%s）⇒ 注释列用空串" % list(df.columns))
            _warn("spots.csv 缺 spot 列（实际列：%s）⇒ 注释列降级为空串" % list(df.columns))
            return [""] * n, [""] * n, [""] * n

        for col in ("sample", "cluster", "cell_type"):
            if col not in cols:
                self.annotation_notes.append("spots.csv 缺 %s 列 ⇒ 该列用空串" % col)
                _warn("spots.csv 缺 %s 列 ⇒ 该列降级为空串（文件：%s）" % (col, path))
                df[col] = ""

        df = df[["spot", "sample", "cluster", "cell_type"]]
        # 极端情况：重复 spot 行（不该有，硬要求不许改 spots.csv ⇒ 这里只留第一行并留痕）
        if df["spot"].duplicated().any():
            dup = int(df["spot"].duplicated().sum())
            self.annotation_notes.append("spots.csv 有 %d 个重复 spot，已保留首行" % dup)
            _warn("spots.csv 有 %d 个重复 spot（保留首行）：%s" % (dup, path))
            df = df.drop_duplicates(subset="spot", keep="first")

        mapped = df.set_index("spot")
        keys = spot_series.astype(str)
        sample = keys.map(mapped["sample"]).fillna("").astype(str).tolist()
        cluster = keys.map(mapped["cluster"]).fillna("").astype(str).tolist()
        cell_type = keys.map(mapped["cell_type"]).fillna("").astype(str).tolist()
        hit = int(sum(1 for v in sample if v))
        _warn("spots.csv 命中 %d/%d 个 spot（%s）" % (hit, n, path))
        return sample, cluster, cell_type

    def _load_all_region_labels(self, sample_ids):
        """
        读每样本 `_region_workbench/region_labels_<sid>.csv`（列 `spot,label`）。

        返回 {sample_id: {spot: label}}；**只有读成功的样本才会出现在字典里**（契约 §5：
        没有 region_labels 的样本 ⇒ region_label 全空、group 全等于 cell_type）。
        缺文件不是错误（绝大多数样本本来就没进过绘图模式），但要留痕。
        """
        wb = self._workbench_dir()
        out = {}
        for sid in sample_ids:
            if not sid:
                continue
            path = os.path.join(wb, "region_labels_%s.csv" % sid)
            if not os.path.isfile(path):
                _warn("样本 %s 无 region_labels_%s.csv ⇒ 该样本 region_label 全空、group 回退 cell_type"
                      % (sid, sid))
                continue
            try:
                df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
            except Exception as e:
                self.annotation_notes.append("region_labels_%s.csv 读取失败（%s）⇒ 该样本回退原始注释"
                                             % (sid, e))
                _warn("region_labels_%s.csv 读取失败：%s ⇒ 该样本 region_label 全空" % (sid, e))
                continue
            if "spot" not in df.columns or "label" not in df.columns:
                self.annotation_notes.append("region_labels_%s.csv 缺 spot/label 列（实际：%s）"
                                             % (sid, list(df.columns)))
                _warn("region_labels_%s.csv 缺 spot/label 列（实际：%s）⇒ 该样本回退原始注释"
                      % (sid, list(df.columns)))
                continue
            m = {}
            for s, lb in zip(df["spot"].astype(str).tolist(), df["label"].astype(str).tolist()):
                if s:
                    m[s] = (lb or "").strip()
            out[sid] = m
            n_nonempty = sum(1 for v in m.values() if v)
            _warn("region_labels_%s.csv: %d 行，其中非空 label %d 个" % (sid, len(m), n_nonempty))
        return out

    # -------------------------------------------------------------------------
    # §6：读区域层（只读）→ 逐 spot 的 `group_graphed` 注释值
    # -------------------------------------------------------------------------
    def _sample_spot_rows(self, sample_id):
        """某样本的 spots（**含 x/y**，供"落在哪个区域里"判定）；取不到 → `[]`（已留痕）

        为什么单独读一次：`_load_spots_annotations` 只带出 `sample/cluster/cell_type`
        （没有坐标），而逐 spot 的 `group_graphed` 必须靠坐标 + 区域多边形判定。

        读法（**只读，不写盘**）：
          ① 首选本类的 `_workbench_dir()/spots.csv`（与注释同一份文件、同一个 out_dir 口径）；
          ② 读不到 / 缺 `spot,x,y` / 解析失败 ⇒ 退回 `SREG.load_spots(dataset, sid)`（同文件另一读路径）；
          ③ 两条都不行 ⇒ `[]` + 留痕（调用方据此把**整样本**降级为空，绝不错位）。
        """
        wb = self._workbench_dir()
        path = os.path.join(wb, "spots.csv") if wb else ""
        if path and os.path.isfile(path):
            try:
                df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
                cols = set(df.columns)
                if {"spot", "x", "y"} <= cols:
                    if sample_id and "sample" in cols:
                        df = df[df["sample"].astype(str) == str(sample_id)]
                    rows = []
                    n_bad = 0
                    for rec in df.to_dict("records"):
                        try:
                            rows.append({"spot": str(rec.get("spot") or ""),
                                         "x": float(rec.get("x")),
                                         "y": float(rec.get("y"))})
                        except (TypeError, ValueError):
                            n_bad += 1
                    if n_bad:
                        _warn("样本 %s 有 %d 行坐标无法解析（已跳过，不参与区域判定）" % (sample_id, n_bad))
                    return rows
                _warn("spots.csv 缺 spot/x/y 列（实际：%s）⇒ 退回 SREG.load_spots" % list(df.columns))
            except Exception as e:
                _warn("读 spots.csv 坐标失败：%s ⇒ 退回 SREG.load_spots" % e)
        else:
            _warn("未见 spots.csv（%s）⇒ 退回 SREG.load_spots" % (path or "(out_dir 为空)"))
        try:
            rows, err = SREG.load_spots(self.dataset, sample_id)
            if err:
                self.annotation_notes.append("样本 %s 取不到 spot 坐标（%s）⇒ group_graphed 空"
                                             % (sample_id, err))
                _warn("SREG.load_spots(%s) 未取到坐标：%s" % (sample_id, err))
                return []
            return list(rows or [])
        except Exception as e:
            traceback.print_exc()
            _warn("SREG.load_spots(%s) 异常：%s ⇒ 该样本 group_graphed 空" % (sample_id, e))
            return []

    def _load_group_graphed_map(self, sample_ids):
        """逐样本（**只读** `appdata/<ds>.regions.json`）→ `{spot: anno_label}`

        Returns:
            dict: `{sample_id: {spot: 非空 anno_label}}`；**只有非空注释值才进字典**
                  （与 `region_label_map` 同一形态，`load_gene` 因此能用**同一套查表代码**对齐）

        纪律（§6 / 模块 §8）：
          · **按样本切 regions**（`SREG.get_sample_regions`）⇒ 跨样本**结构上不可能错位**；
          · 用 `SREG.group_graphed_labels(该样本的 spots, 该样本的 regions)` —— 与 `assign_labels`
            同一套"后画赢 + 有效区域"语义，只是取 `anno_label` 且非空才生效；
          · 标签数 ≠ spot 数、或拿不到坐标 ⇒ **整个样本**降级为空串 + 留痕（**绝不错位**）；
          · 旧式区域（`anno_label` 空）/ 没有 regions 的样本 ⇒ 该样本全空 + 留痕（**正常情况**）。
        """
        out = {}
        try:
            data = SREG.load_regions(self.dataset)
        except Exception as e:
            traceback.print_exc()
            self.annotation_notes.append("regions.json 读取异常（%s）⇒ group_graphed 全空" % e)
            _warn("SREG.load_regions(%s) 异常：%s ⇒ group_graphed 全空" % (self.dataset, e))
            return out

        issues = list(data.get("_issues") or [])
        if issues:
            _warn("regions.json 读取有说明（不阻断）：%s" % "; ".join(str(x) for x in issues))

        for sid in sample_ids:
            if not sid:
                continue
            try:
                regs = SREG.get_sample_regions(data, sid)
                if not regs:
                    _warn("样本 %s 无区域（regions.json）⇒ group_graphed 全空" % sid)
                    continue
                if not SREG.sample_has_group_graphed(regs):
                    # ★ 这是**用户现有数据的正常形态**（区域名都是旧的自由文本，没有 anno_label）
                    _warn("样本 %s 的区域都是旧式/无注释值（anno_label 全空）⇒ group_graphed 全空" % sid)
                    continue
                rows = self._sample_spot_rows(sid)
                if not rows:
                    self.annotation_notes.append("样本 %s 取不到 spot 坐标 ⇒ group_graphed 全空" % sid)
                    _warn("样本 %s 取不到 spot 坐标 ⇒ group_graphed 全空（不许错位，故整样本降级）" % sid)
                    continue
                labels = SREG.group_graphed_labels(rows, regs)
                if len(labels) != len(rows):
                    self.annotation_notes.append(
                        "样本 %s 的 group_graphed 标签数(%d)与 spot 数(%d)不一致 ⇒ 整样本降级为空"
                        % (sid, len(labels), len(rows)))
                    _warn("样本 %s group_graphed 标签数 %d != spot 数 %d ⇒ 整样本降级为空（绝不错位）"
                          % (sid, len(labels), len(rows)))
                    continue
                m = {}
                for row, lb in zip(rows, labels):
                    key = str(row.get("spot") or "")
                    val = str(lb or "").strip()
                    if key and val:
                        m[key] = val
                out[sid] = m
                _warn("样本 %s: regions=%d | group_graphed 非空 spot=%d/%d"
                      % (sid, len(regs), len(m), len(rows)))
            except Exception as e:
                # 单样本异常 ⇒ 只丢该样本（其余样本的映射是**逐样本自洽**的，不会连带错位）
                traceback.print_exc()
                self.annotation_notes.append("样本 %s 的 group_graphed 计算异常（%s）⇒ 该样本为空" % (sid, e))
                _warn("样本 %s 的 group_graphed 计算异常：%s ⇒ 该样本为空" % (sid, e))
                out.pop(sid, None)
        return out

    # -------------------------------------------------------------------------
    # 调 R dump
    # -------------------------------------------------------------------------
    @staticmethod
    def _parse_result_line(stdout):
        """从子进程 stdout 取**最后一条** ##SPATIAL_VIOLIN_RESULT## JSON（找不到返回 None）"""
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
                import json
                found = json.loads(payload)
            except ValueError as e:
                _warn("解析 R 结果行失败（忽略该行）：%s" % e)
                continue
        return found if isinstance(found, dict) else None

    @staticmethod
    def _as_list(v):
        """把可能是标量的字段强制成 list（R 侧 auto_unbox 会把长度 1 的向量脱成标量）"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]

    def run_dump(self, gene, timeout=DEFAULT_TIMEOUT):
        """
        调 `spatial_violin_dump.R` 把单个基因 dump 成 CSV。

        返回 (ok: bool, result: dict, error: str)。**绝不抛异常**（与 GEA.run_gene_expression 同纪律）；
        调用方（load_gene）负责把 error 转成 ValueError 并留痕。

        子进程纪律（逐条照抄 GEA.run_gene_expression）：
          · 基因清单走**临时文件**（不靠 argv 传长列表）；
          · `stdin=DEVNULL` + `timeout`（默认 900 s）+ `cwd=` 已断言为 ASCII 的目录；
          · stdout/stderr 全捕获、`GEA._decode` 逐级退化解码（本机 R console 可能是 GBK）；
          · 结果行找不到 / ok=false ⇒ 返回 (False, {}, 可读原因)，把 stderr 尾巴带上。
        """
        if not gene or not isinstance(gene, str):
            return False, {}, "基因名为空"
        gene = gene.strip()
        if not GEA._is_safe_gene(gene):
            return False, {}, "基因名含非法字符（只允许 [A-Za-z0-9_.-]，且首字符为字母或数字）：%r" % gene

        if not self.out_dir or not self.rds_path or not self.dataset:
            return False, {}, "上下文不完整：请先调用 set_context(dataset, out_dir, rds_path, samples)"
        if not GEA.is_ascii_path(self.rds_path):
            return False, {}, "rds_path 含非 ASCII 字符，已拒绝：%s" % self.rds_path
        if not GEA.is_ascii_path(self._dump_root()):
            return False, {}, "dump 落盘根含非 ASCII 字符，已拒绝：%s" % self._dump_root()
        if not GEA.is_ascii_path(self.dataset):
            return False, {}, "dataset 含非 ASCII 字符，已拒绝：%s" % self.dataset
        if not os.path.isfile(self.rds_path):
            return False, {}, "成品 .rds 不存在：%s" % self.rds_path

        r_script = self.resolve_dump_r_script()
        if not r_script:
            return False, {}, "找不到 R 脚本 %s（期望位置：%s）" % \
                              (_DUMP_R_REL, os.path.normpath(os.path.join(_HERE, _DUMP_R_REL)))

        try:
            timeout_val = int(timeout)
        except (TypeError, ValueError):
            return False, {}, "timeout 不是整数：%r" % (timeout,)
        if timeout_val <= 0:
            return False, {}, "timeout 必须为正数：%d" % timeout_val

        # 基因清单临时文件（放在 ASCII 的按需目录下，与 GEA 同款）
        on_demand_root = os.path.join(self._dump_root(), ON_DEMAND_SUBDIR)
        genes_file = ""
        try:
            os.makedirs(on_demand_root, exist_ok=True)
            if not os.path.isdir(on_demand_root):
                return False, {}, "无法创建按需出图目录：%s" % on_demand_root
            import tempfile
            fd, genes_file = tempfile.mkstemp(prefix="_violin_gene_", suffix=".txt", dir=on_demand_root)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(gene + "\n")
        except OSError as e:
            return False, {}, "准备基因清单失败：%s" % e

        cmd = [self.find_rscript(), r_script, self.rds_path, self._dump_root(),
               self.dataset, genes_file]
        if self.samples:
            cmd += ["--samples", ",".join(self.samples)]
        _warn("run_dump: gene=%s | cmd=%s" % (gene, " ".join(cmd)))
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,      # ★ 绝不给 R 任何交互机会
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_val,
                cwd=on_demand_root,            # cwd 也放在已断言为 ASCII 的目录里
            )
        except subprocess.TimeoutExpired:
            GEA._safe_unlink(genes_file)
            return False, {}, ("R dump 超时（>%ds）：gene=%s。按实测约 6 s 载入 + 每基因 <1 s，"
                               "可提高 timeout。" % (timeout_val, gene))
        except OSError as e:
            GEA._safe_unlink(genes_file)
            return False, {}, "无法启动 R 子进程（%s）：%s" % (cmd[0], e)

        GEA._safe_unlink(genes_file)

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

        # 归一化"应该是数组"的字段（防 R 侧漏加 I()；与 GEA._normalize_result 同一理由）
        for key in ("genes", "cached", "samples_used", "samples_missing", "not_found",
                    "written", "dropped_unsafe_genes", "samples_requested"):
            result[key] = self._as_list(result.get(key))

        miss = [str(s) for s in result.get("samples_missing", [])]
        if miss:
            # 契约要求：缺失样本**不硬失败**，但必须留痕（用户选的样本没出现，调用方要能看见）
            _warn("run_dump: 请求的样本在数据里不存在（已跳过，不失败）：%s" % ", ".join(miss))
        return True, result, ""

    # -------------------------------------------------------------------------
    # 主入口：load_gene
    # -------------------------------------------------------------------------
    def load_gene(self, gene_name):
        """
        加载一个基因 → 建好 `self.violin_df` / `self.violin_gene`，返回 (groups, n_spots)。

        流程（契约 §4.2 + §6）：
          ① 调 R dump（`spatial_violin_dump.R`）→ `08_GeneOnDemand/_violin/<gene>.csv`
             （列 **逐字** `spot,sample,cluster,cell_type,expr`）；
          ② 读 spots.csv + 每样本 region_labels_<sid>.csv，逐 spot 合成注释（§5 规则）；
          ②' §6：读 `appdata/<ds>.regions.json`（**只读**）→ 每样本 `anno_label` → 逐 spot `group_graphed`
             （与 region_label 同一套 spot 对齐；对齐不上 ⇒ 空串 + 留痕，**绝不错位**）；
          ③ `expr` 列**改名成基因名**（继承的 plot_* 用 `df[self.violin_gene]` 取 y 值）；
          ④ 列冻结为 `spot, sample, cluster, cell_type, region_label, group_graphed, group, <gene>`；
          ⑤ `groups = [c for c in df.columns if 1 < df[c].nunique() < 60]`（复刻单细胞判据）。

        失败一律抛 `ValueError("<可读原因>")`（W2 会 alert_failure + 写日志），且此前已 print 留痕。
        """
        if not gene_name or not str(gene_name).strip():
            raise ValueError("请输入基因名")
        gene = str(gene_name).strip()

        # ---- ① R dump ----
        ok, result, err = self.run_dump(gene)
        if not ok:
            _warn("load_gene: R dump 失败，gene=%s，原因：%s" % (gene, err))
            raise ValueError("加载基因 %s 失败：%s" % (gene, err))
        self.dump_result = result
        for s in result.get("samples_missing", []):
            self.annotation_notes.append("样本 %s 在数据里不存在（R dump 已跳过）" % s)

        files = result.get("files") or {}
        csv_path = ""
        if isinstance(files, dict):
            csv_path = files.get(gene) or ""
        if not csv_path:
            csv_path = os.path.join(self._dump_root(), ON_DEMAND_SUBDIR, VIOLIN_SUBDIR, "%s.csv" % gene)
        if not os.path.isfile(csv_path):
            _warn("load_gene: R 未产出 CSV，gene=%s，期望路径：%s（not_found=%s）"
                  % (gene, csv_path, result.get("not_found")))
            not_found = [str(g) for g in (result.get("not_found") or [])]
            if gene in not_found:
                raise ValueError("基因 %s 不存在于表达矩阵中（可选基因 %s 个）"
                                 % (gene, result.get("available_genes_n", "?")))
            raise ValueError("加载基因 %s 失败：未找到 dump CSV %s" % (gene, csv_path))

        try:
            expr_df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
        except Exception as e:
            _warn("load_gene: 读 dump CSV 失败：%s（%s）" % (e, csv_path))
            raise ValueError("读取 %s 失败：%s" % (os.path.basename(csv_path), e))

        if "spot" not in expr_df.columns or "expr" not in expr_df.columns:
            _warn("load_gene: dump CSV 缺 spot/expr 列（实际：%s，文件：%s）"
                  % (list(expr_df.columns), csv_path))
            raise ValueError("dump CSV 表头异常（缺 spot/expr）：%s" % list(expr_df.columns))

        # ---- ② 注释合成 ----
        spots = expr_df["spot"].astype(str)
        sample_from_csv = (expr_df["sample"].astype(str).tolist()
                           if "sample" in expr_df.columns else [""] * len(expr_df))
        cluster_from_csv = (expr_df["cluster"].astype(str).tolist()
                            if "cluster" in expr_df.columns else [""] * len(expr_df))
        celltype_from_csv = (expr_df["cell_type"].astype(str).tolist()
                             if "cell_type" in expr_df.columns else [""] * len(expr_df))

        s_sample, s_cluster, s_celltype = self._load_spots_annotations(spots)

        def _prefer(primary, fallback):
            """spots.csv 有值就用它；为空则回退 R dump 的同名列（R 侧 NA 已写成空串）"""
            return [p if (p or "").strip() else (f or "") for p, f in zip(primary, fallback)]

        sample = _prefer(s_sample, sample_from_csv)
        cluster = _prefer(s_cluster, cluster_from_csv)
        cell_type = _prefer(s_celltype, celltype_from_csv)

        # region_labels：按 spot 所属样本取对应文件
        sample_ids = sorted({s for s in sample if s})
        self.region_label_map = self._load_all_region_labels(sample_ids)
        region_label = []
        n_override = 0
        for spot, sid in zip(spots.tolist(), sample):
            lb = self.region_label_map.get(sid, {}).get(spot, "") or ""
            if lb:
                n_override += 1
            region_label.append(lb)
        _warn("注释合成：%d 个 spot 中 %d 个有非空 region_label（覆盖样本 %d 个，有 region_labels 文件的样本 %d 个）"
              % (len(spots), n_override, len(sample_ids), len(self.region_label_map)))

        # §6：group_graphed 逐 spot 派生（区域层 anno_label；**与 region_label 同一套对齐代码**）
        self.group_graphed_map = self._load_group_graphed_map(sample_ids)
        group_graphed = []
        n_gg = 0
        for spot, sid in zip(spots.tolist(), sample):
            gg = self.group_graphed_map.get(sid, {}).get(spot, "") or ""
            if gg:
                n_gg += 1
            group_graphed.append(gg)
        _warn("注释合成：%d 个 spot 中 %d 个有非空 group_graphed（有 anno_label 的样本 %d 个）"
              % (len(spots), n_gg, len(self.group_graphed_map)))

        # ---- ③④ 冻结列（expr → 基因名；group = region_label or cell_type）----
        try:
            expr_vals = pd.to_numeric(expr_df["expr"], errors="coerce")
        except Exception as e:
            _warn("load_gene: expr 列转数值失败：%s" % e)
            raise ValueError("expr 列无法转为数值：%s" % e)
        n_bad_expr = int(expr_vals.isna().sum())
        if n_bad_expr:
            _warn("load_gene: %d 个 expr 值无法解析为数值，已按 0 处理（gene=%s）" % (n_bad_expr, gene))
            expr_vals = expr_vals.fillna(0.0)

        # group = region_label if region_label else cell_type（§5 规则 3）
        group = [(lb if (lb or "").strip() else (ct or "")) for lb, ct in zip(region_label, cell_type)]

        self.violin_df = pd.DataFrame({
            "spot": spots.tolist(),
            "sample": sample,
            "cluster": cluster,
            "cell_type": cell_type,
            "region_label": region_label,
            "group_graphed": group_graphed,    # ★ §6：区域层 anno_label（空 = 旧式/未覆盖）
            "group": group,
            gene: expr_vals.tolist(),          # ★ 列名**恰好等于基因名**（继承的 plot_* 依赖它）
        }, columns=list(FROZEN_COLUMNS) + [gene])

        # ★ 继承契约 1：violin_gene 必须是原串（拼产物路径 / 取 y 值都用它）
        self.violin_gene = gene

        if len(self.violin_df) == 0:
            _warn("load_gene: 合并后 0 行（gene=%s）" % gene)
            raise ValueError("基因 %s 没有可用的 spot 数据" % gene)

        # ---- ⑤ 分组列候选 ----
        groups = [c for c in self.violin_df.columns
                  if MIN_GROUP_NUNIQUE < self.violin_df[c].nunique() < MAX_GROUP_NUNIQUE]
        _warn("load_gene: gene=%s | rows=%d | groups=%s | cell_type_nunique=%d | region_label_nonempty=%d | group_graphed_nonempty=%d"
              % (gene, len(self.violin_df), groups,
                 self.violin_df["cell_type"].nunique(),
                 int((self.violin_df["region_label"].astype(str).str.strip() != "").sum()),
                 int((self.violin_df["group_graphed"].astype(str).str.strip() != "").sum())))
        return groups, len(self.violin_df)


__all__ = ["SpatialViolinAnalysis", "ANNOTATION_CANDIDATES", "FROZEN_COLUMNS"]
