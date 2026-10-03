# -*- coding: utf-8 -*-
"""
bulk「基因集分析」共享内核 —— 表达量 / KM（py、R 双版）**唯一真相源**

## 背景（用户需求，2026-09）
原来 bulk 的表达量页与生存分析（KM）都只做**单基因**分析。现在要加「基因集分析」：
  · 输入一个**基因集合**（外部文件下拉 / 手动换行输入，二选一）；
  · 把这个集合聚合成**每个样本一个数值**（复合表达水平）；
  · 表达量页：拿这个复合值当"单基因表达量"去画箱线/小提琴（按临床分组）；
  · KM 页：拿这个复合值按中位数分高/低表达，画 KM 曲线（py 与 R 双版）。

## 聚合方法（用户选：做成下拉框）
  · `mean_zscore`：每个基因在样本间 z-score 标准化后，**按样本取均值**（基因集签名分，主流）。
  · `sum_zscore` ：每个基因 z-score 标准化后，**按样本求和**。
  · `mean_expr`  ：**平均原始表达**（不标准化，受高表达基因主导）。

## 为什么放共享模块（房规：一个真相源）
  表达量 / KM-py / KM-R 三处都要"读基因列表 + 算复合分"。若三份复制，
  将来改聚合公式/加方法必然漂移（本项目已因"两个真相源"栽过多次）。
  → 这里只放**纯数据函数**（无 Qt、无 matplotlib、无 R），三个 analysis 类都 import 它。

只读 `appdata/genelists`；**绝不写任何用户文件**。
"""
import os

from script.utils_layer.import_config import APPDATA_PATH, BASE_DIR

#: 聚合方法 id → 中文名（**顺序即下拉框顺序**，各处只读本表，不自行硬编码）
GENE_SET_METHODS = (
    ("mean_zscore", "平均 z-score"),
    ("sum_zscore", "求和 z-score"),
    ("mean_expr", "平均原始表达"),
)
GENE_SET_METHOD_IDS = tuple(k for k, _ in GENE_SET_METHODS)
DEFAULT_GENE_SET_METHOD = "mean_zscore"

#: 聚合方法的**英文**标签（只用于出图标题/坐标轴，不让图里出现中文）
GENE_SET_METHOD_LABELS_EN = {
    "mean_zscore": "Mean z-score",
    "sum_zscore": "Sum z-score",
    "mean_expr": "Mean expression",
}


def gene_set_method_label_en(method):
    """聚合方法英文名（出图用）；未知方法回退原 id。"""
    return GENE_SET_METHOD_LABELS_EN.get(method, str(method))

#: 「聚合方法」问号按钮的说明文字（三页统一，配合 `create_questions_button` 使用）
GENE_SET_METHOD_HELP = (
    "如何选聚合方法（取决于你的数据格式）：\n"
    "· 平均 z-score（推荐）：先把每个基因在样本间 z-score 标准化，再取均值。\n"
    "  适用于 count 原始计数（基因间量级差异大）与绝大多数场景，最能消除量级偏倚。\n"
    "· 求和 z-score：同样先 z-score，但按样本求和，信号会随基因数增多而放大。\n"
    "· 平均原始表达：直接取原始表达均值，不做标准化。\n"
    "  仅当数据已是可比尺度（如 TPM/CPM/log 标准化）时才考虑；\n"
    "  count 数据请勿用（会被高表达基因主导）。\n"
    "一句话：count 数据优先选「平均 z-score」；TPM 等标准化数据也可继续用 z-score 类方法。"
)

#: 外部基因列表目录（与 WGCNA 同一个 `appdata/genelists`）
_GENELIST_DIR_CANDIDATES = (
    os.path.join(APPDATA_PATH, "genelists"),
    os.path.join(BASE_DIR, "appdata", "genelists"),
)

#: 支持的外部列表扩展名
_GENE_LIST_EXTS = (".xlsx", ".xls", ".txt", ".csv")

#: 基因列表文件里"看起来是表头"的首行值（**冻结清单**，与 Circos 内核 / bulk 一致性分型同口径）。
#: 既有 4 个文件都是单列无表头，首格即基因名；但用户也可能存成带表头的表，
#: 那种文件的表头不能被当成基因（契约 §2 兼容性要求 b）。
GENE_HEADER_TOKENS = frozenset({
    "gene", "genes", "genename", "gene name", "gene_name", "gene symbol",
    "gene_symbol", "symbol", "symbols", "geneid", "gene_id", "id",
    "基因", "基因名", "基因名称", "基因符号", "名称",
})

#: 文本类基因列表的**显式**行内分隔符（绝不用 `sep=None` 让 pandas 嗅探）
_TEXT_SEPS = ("\t", ",", ";", "，")


def is_gene_list_header(value):
    """该值是否长得像基因列表表头（`gene` / `symbol` / `基因名` …）。"""
    try:
        return str(value).strip().strip('"').strip("'").strip().lower() in GENE_HEADER_TOKENS
    except Exception:  # noqa: BLE001
        return False


def drop_gene_header_token(genes):
    """跳过"首行是表头"的情形：只在**第一个**元素命中冻结清单时删掉它。

    只判断第一个元素（而不是全表过滤），这样列表中间真的叫 `ID` 的基因不会被误删。
    """
    seq = list(genes or [])
    if seq and is_gene_list_header(seq[0]):
        return seq[1:]
    return seq


def _read_text_first_column(path):
    """文本类列表：逐行读，**只在行内显式出现分隔符时**取第一段。

    ⚠️ 历史坑：`pd.read_csv(sep=None, engine="python")` 的分隔符嗅探器会把单列基因名
    （`C1orf61`、`H1-4`、`G00`）当分隔符切碎/并列，直接毁数据。
    """
    text = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as fh:
                text = fh.read()
            break
        except Exception:  # noqa: BLE001
            text = None
    if text is None:
        raise RuntimeError("无法解码文本文件：%s" % path)

    out = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        field = line
        for sep in _TEXT_SEPS:
            if sep in field:
                field = field.split(sep, 1)[0]
                break
        token = field.strip().strip('"').strip("'").strip()
        if token:
            out.append(token)
    return out


def read_gene_list_first_column(path):
    """读基因列表文件（xlsx/xls/csv/txt）→ **第一列**的字符串列表（去 NaN/空、保序）。

    · xlsx/xls → `header=None` 取第一列（**不是** `header=0`：既有文件无表头，
      默认表头会把第一个基因当列名吃掉，静默少 1 个 —— 契约 §0.3）；
    · csv      → `header=None` 取第一列；
    · txt 等   → 逐行读、显式分隔符取第一段（不用 `sep=None` 嗅探）。
    本函数**不**删表头行，需要时由调用方接 `drop_gene_header_token()`。
    """
    import pandas as pd

    low = str(path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, header=None)
    elif low.endswith(".csv"):
        df = pd.read_csv(path, header=None)
    else:
        return _read_text_first_column(path)

    if df is None or getattr(df, "shape", (0, 0))[1] < 1:
        return []
    values = df.iloc[:, 0].tolist()

    out = []
    for v in values:
        if v is None:
            continue
        try:
            if pd.isna(v):
                continue
        except (TypeError, ValueError):
            pass
        s = str(v).strip().strip('"').strip("'").strip()
        if s and s.lower() not in ("nan", "none", "na", "null"):
            out.append(s)
    return out


def gene_list_dir():
    """外部基因列表目录（取第一个实际存在的候选；都不存在返回 None）"""
    for d in _GENELIST_DIR_CANDIDATES:
        try:
            if os.path.isdir(d):
                return d
        except Exception:
            continue
    return None


def list_gene_set_files():
    """返回 `appdata/genelists` 下可用的基因列表文件名（排序，稳定顺序）。"""
    d = gene_list_dir()
    if not d:
        return []
    try:
        names = [f for f in os.listdir(d)
                 if os.path.isfile(os.path.join(d, f)) and f.lower().endswith(_GENE_LIST_EXTS)]
    except Exception:
        return []
    return sorted(names)


def gene_set_file_path(file_name):
    """基因列表文件绝对路径；文件名非法/目录不存在 → None"""
    if not file_name:
        return None
    d = gene_list_dir()
    if not d:
        return None
    p = os.path.join(d, str(file_name))
    return p if os.path.isfile(p) else None


def load_gene_set_from_file(file_name):
    """读外部基因列表文件，返回 `(gene_list, error)`。

    与 WGCNA / Circos / 一致性分型同一口径：**取第一列**（Excel / CSV / 文本），
    strip、去空、去重、保序；首格恰为 `gene`/`symbol` 等表头样值时跳过该行。
    """
    if not file_name:
        return [], "未选择基因列表文件"
    path = gene_set_file_path(file_name)
    if path is None:
        return [], "基因列表文件不存在：%s（请检查 appdata/genelists）" % file_name
    try:
        # ★ 无表头读法（见 read_gene_list_first_column：xlsx/csv header=None，txt 显式分隔）
        raw = drop_gene_header_token(read_gene_list_first_column(path))
    except Exception as e:  # noqa: BLE001
        # 兜底：当文本文件，逐行读（覆盖分隔符猜错 / 编码异常的情况）
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                raw = drop_gene_header_token([ln.strip() for ln in fh if ln.strip()])
        except Exception:
            return [], "读取基因列表文件失败：%s（%s）" % (file_name, e)
    if not raw:
        return [], "基因列表文件为空或没有列：%s" % file_name
    return _dedupe(raw), ""


def parse_gene_set_from_text(text):
    """手动输入 → 基因列表：按换行切分、strip、去空、去重、保序。"""
    if text is None:
        return []
    lines = [ln.strip() for ln in str(text).splitlines()]
    # 兼容用逗号/空格/制表符分隔（用户可能黏贴 "A B C" 或 "A,B,C"）
    tokens = []
    for ln in lines:
        if not ln:
            continue
        for tok in ln.replace(",", "\t").replace("，", "\t").split("\t"):
            t = tok.strip()
            if t:
                tokens.append(t)
    return _dedupe(tokens)


def _dedupe(items):
    out, seen = [], set()
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def resolve_gene_set(adata, gene_names):
    """把基因列表对到表达矩阵的 `var_names`，返回 `(valid, invalid)`（均保序）。"""
    available = set(adata.var_names) if adata is not None else set()
    valid, invalid = [], []
    for g in gene_names:
        if g in available:
            valid.append(g)
        else:
            invalid.append(g)
    return valid, invalid


def compute_gene_set_score(adata, gene_names, method=DEFAULT_GENE_SET_METHOD):
    """基因集合 → 每样本一个复合分（对齐 `adata.obs` 行序）。

    Args:
        adata: scanpy AnnData（`.X` 可为稠密或稀疏）。
        gene_names: 已匹配到 `var_names` 的基因列表（**本函数不再做匹配**，由调用方先 resolve）。
        method: 见 `GENE_SET_METHOD_IDS`。

    Returns:
        (scores: np.ndarray|None, note: str)
        scores 长度 == adata.n_obs；失败时 (None, 原因)。
    """
    import numpy as np
    from scipy import sparse

    if adata is None:
        return None, "未加载数据"
    if not gene_names:
        return None, "没有可用的基因"
    if method not in GENE_SET_METHOD_IDS:
        return None, "未知聚合方法：%s" % method

    try:
        sub = adata[:, gene_names].X
        if sparse.issparse(sub):
            dense = sub.toarray().astype(float)
        else:
            dense = np.asarray(sub, dtype=float)
    except Exception as e:  # noqa: BLE001
        return None, "提取基因表达失败：%s" % e

    if dense.shape[0] == 0 or dense.shape[1] == 0:
        return None, "表达矩阵为空"

    if method == "mean_expr":
        scores = np.nanmean(dense, axis=1)
    else:
        from scipy.stats import zscore
        z = zscore(dense, axis=0, ddof=1)      # 每列（基因）在样本间标准化
        z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
        if method == "sum_zscore":
            scores = z.sum(axis=1)
        else:                                   # mean_zscore
            scores = z.mean(axis=1)

    scores = np.asarray(scores, dtype=float).ravel()
    if scores.shape[0] != adata.n_obs:
        return None, "复合分长度与样本数不一致（%d vs %d）" % (scores.shape[0], adata.n_obs)
    return scores, ""


__all__ = [
    "GENE_SET_METHODS", "GENE_SET_METHOD_IDS", "DEFAULT_GENE_SET_METHOD",
    "GENE_SET_METHOD_HELP", "GENE_SET_METHOD_LABELS_EN", "gene_set_method_label_en",
    "gene_list_dir", "list_gene_set_files", "gene_set_file_path",
    "load_gene_set_from_file", "parse_gene_set_from_text",
    "resolve_gene_set", "compute_gene_set_score",
    "GENE_HEADER_TOKENS", "is_gene_list_header", "drop_gene_header_token",
    "read_gene_list_first_column",
]
