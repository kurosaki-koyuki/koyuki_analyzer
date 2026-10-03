# -*- coding: utf-8 -*-
"""circos_analysis.py —— Circos 圈图绘图内核（commontools 层 / 契约 §1-B、§7）

纯 Python + matplotlib + pycirclize，**不涉及 R / rpy2**，不引入任何新依赖。
数据源固定为只读目录 `appdata/circos_data/`（`karyotype_/cytoband_/gene_coords_/
gene_density_<N>Mb/gc_<N>Mb`，N ∈ {1,2,5,10,20}），**绝不往该目录写任何东西**。

绘图逻辑照搬本轮视觉验收过的试跑脚本 `Circos图绘制参考/脚本/02_绘制circos.py`
（环半径、配色语言、GC 分段、切片色阶、标签分层、布局引擎全部沿用），
只是把数据来源从试跑文件夹的 `数据/` 换成 `appdata/circos_data/`。

────────────────────────────────────────────────────────────────────────────
⚠️ 本文件有三个**必须先看**的副作用/环境约束（都是踩过的坑）
────────────────────────────────────────────────────────────────────────────

1) `import pycirclize` 会在**导入时全局**改写 3 个 matplotlib rcParams
   （见 site-packages/pycirclize/config.py:107-114）：

       savefig.bbox        None  -> "tight"
       savefig.pad_inches  0.1   -> 0.5
       svg.fonttype        path  -> none

   这是**进程级**改动，会污染 App 里其它所有图的导出（保存被裁边、留白变大）。
   所以本模块在 import pycirclize **之前**存下这 3 个键，import **之后立刻还原**
   （见下面 `_RC_GUARDED` 那段）；此外在每次 savefig 时再用
   `matplotlib.rc_context` 局部强制 `savefig.bbox="standard"`，
   双重保证导出尺寸严格等于 `figsize * dpi`。
   注意：本模块**只还原自己导入造成的污染**；若别的模块在本模块之前就 import 过
   pycirclize，那污染在更早处发生，不归这里管。

2) **禁止**在本文件里调用 `matplotlib.use(...)`（试跑脚本里有，这里必须没有）。
   App 通过 `import_config` 以 Qt5Agg 画布长驻运行；`matplotlib.use` 是**全局**切后端，
   内核一旦切到 Agg，App 里所有 Qt 画布图都会失效。无界面自测请用环境变量
   `MPLBACKEND=Agg` 隔离，而不是改后端。

3) `savefig` 之后必须 `plt.close(fig)`：GUI 是长驻进程，反复出图不关会持续泄漏 figure。

其它保留的关键细节（漏一个就出问题）：
  · `fig.set_layout_engine("none")` + 手工 `set_position`，导出严格 figsize*dpi 正方形；
  · 染色体号在 r=110（超出 0~100 绘图半径）→ 轴框高度必须 ≤0.80，否则顶部号码被标题压住；
  · GC 纵轴范围按**该档实测极值**算（1 Mb 档到 ~59%，写死 56 直接抛 ValueError），
    `fill_between` 的基线必须落在 [vmin, vmax] 内；GC 表含 NaN（装配缺口）→ 按连续有效段分段画；
  · 密度 heatmap 与柱状用**该染色体自身色阶**（白→深色），全图"一条染色体一个颜色"；
  · 基因名水平书写（不传 `adjust_rotation`），按左右半圈设 `ha`；角度相近的标签换半径层
    （60/51）防叠字；超过 `max_labels` 的只画点不标名；
  · matplotlib ≥3.9 用 `matplotlib.colormaps[...]`（`cm.get_cmap` 已移除）；
  · 图中一律英文（用户要求），中文只出现在日志里；
  · 基因列表文件解析：**逐行按首个字段取**，绝不用 `pd.read_csv(sep=None)` 嗅探
    （嗅探器会把单列基因名切碎，历史坑）。

输出约定（契约 §8）：`OUT_BASE/circos/<YYYYmmdd_HHMMSS>/circos_genes.png|svg|pdf`。
"""

import io
import math
import os
import re
import time
import urllib.parse
import urllib.request

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib import font_manager as font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# ---------------------------------------------------------------------------
# 路径常量：OUT_BASE / APPDATA_PATH 来自全项目唯一的配置模块
# ---------------------------------------------------------------------------
try:
    from script.utils_layer.import_config import APPDATA_PATH, OUT_BASE
except Exception:  # pragma: no cover - 仅在脱离项目结构独立自测时兜底
    _HERE_DIR = os.path.dirname(os.path.abspath(__file__))
    _BASE_DIR = os.path.abspath(os.path.join(_HERE_DIR, "..", "..", "..", ".."))
    APPDATA_PATH = os.path.join(_BASE_DIR, "appdata")
    OUT_BASE = os.path.join(_BASE_DIR, "OUTPUT")

#: Circos 恒定参考数据目录（**只读**，禁止写入）
CIRCOS_DATA_DIR = os.path.join(APPDATA_PATH, "circos_data")
#: 外部基因列表目录（与 WGCNA / bulk 基因集同一处）
GENELIST_DIR = os.path.join(APPDATA_PATH, "genelists")

# ---------------------------------------------------------------------------
# 全 App 统一的"基因列表文件"口径：目录扫描与文件名→路径解析复用 bulk 模块，
# 保证"appdata/genelists 在哪、有哪些文件"只有一处实现。
# ---------------------------------------------------------------------------
try:
    from script.analyzer_layer.bulk_layer.bulk_gene_set_utils import (
        _dedupe as _bulk_dedupe,
        gene_list_dir as _bulk_gene_list_dir,
        gene_set_file_path as _bulk_gene_set_file_path,
        list_gene_set_files as _bulk_list_gene_set_files,
    )
    _BULK_GENESET_IMPORT_ERROR = None
except Exception as _bulk_err:  # pragma: no cover
    _bulk_dedupe = None
    _bulk_gene_list_dir = None
    _bulk_gene_set_file_path = None
    _bulk_list_gene_set_files = None
    _BULK_GENESET_IMPORT_ERROR = _bulk_err

# ---------------------------------------------------------------------------
# ⚠️ rcParams 存-还（本内核最重要的副作用，见文件头 1)）
# ---------------------------------------------------------------------------
_RC_GUARDED = ("savefig.bbox", "savefig.pad_inches", "svg.fonttype")
_RC_SNAPSHOT = {}
for _k in _RC_GUARDED:
    try:
        _RC_SNAPSHOT[_k] = matplotlib.rcParams[_k]
    except Exception:
        pass

try:
    from pycirclize import Circos
    _PYCIRCLIZE_IMPORT_ERROR = None
except Exception as _pcc_err:  # pragma: no cover - pycirclize 1.10.1 已装
    Circos = None
    _PYCIRCLIZE_IMPORT_ERROR = _pcc_err
finally:
    for _k, _v in _RC_SNAPSHOT.items():
        try:
            matplotlib.rcParams[_k] = _v
        except Exception:
            pass

# ---------------------------------------------------------------------------
# 环半径分层（照抄试跑脚本，已验证）
# ---------------------------------------------------------------------------
R_NUM = 110.0                      # 染色体号（超出 0~100 绘图半径 → 轴高必须 ≤0.80）
R_IDEO = (95.0, 100.0)             # R1 核型条带
R_GC = (88.0, 92.5)                # R2 GC 含量
R_HEAT = (83.0, 87.0)              # R3 基因密度 heatmap
R_HIST = (75.5, 81.5)              # R4 基因密度柱状
R_LOCUS = (70.0, 73.5)             # R5 输入基因散点
R_LABEL, R_LABEL_ALT = 60.0, 51.0  # 基因名两层半径（第 1 层 60，每向内一层减 9）
LABEL_RADII = (R_LABEL, R_LABEL_ALT)
LABEL_MIN_SEP = 10.0               # 同层标签最小角距（度）
R_LINK = 45.0                      # 连线附着半径：**仅在所有环都关时**作为回退锚点

# ---------------------------------------------------------------------------
# 契约 §14.1：连线/牵引线的锚点 =「最内圈可见环的内缘」（由内向外取第一个可见环）
# ---------------------------------------------------------------------------
#: 所有环都关时的回退锚点半径（契约 §14.1）
LINK_FALLBACK_R = 45.0
#: 判定顺序（由内向外）：(环名, 内缘半径)。内缘一律取该环**真实的** `r_lim[0]`
#: （单一真相源，不和绘图常量各写一份）：核型带即 `R_IDEO[0] = 95`。
#: 契约 §14.1 原写 `R_IDEO=(94,100)`，与已验收的绘图常量 `(95,100)` 不一致；
#: 协调者 2026-10-03 裁决：**绘图与锚点都用 95**（弦端与色带内缘零间隙，且不动已验收的画面），
#: 门禁与契约同步改为 95。
RING_ANCHOR_ORDER = (
    ("loci", R_LOCUS[0]),
    ("bars", R_HIST[0]),
    ("heatmap", R_HEAT[0]),
    ("gc", R_GC[0]),
    ("ideogram", R_IDEO[0]),
)
#: 弦最深点 ≈ r_anchor * 该比例（契约 §14.1 建议 0.35），避免锚点外移后弦挤在圆心
LINK_DEPTH_RATIO = 0.35
#: pycirclize 的绘图最大半径（`height_ratio` 相对它定义，见 pycirclize/patches.py:282）
LINK_MAX_R = 100.0

# ---------------------------------------------------------------------------
# 契约 §14.2：标签三个参数（取值范围同时用于内核钳制）
# ---------------------------------------------------------------------------
LABEL_FONTSIZE_RANGE = (4.0, 16.0)
LABEL_LAYERS_RANGE = (1, 4)
LABEL_MIN_SEP_RANGE = (2.0, 30.0)
#: 每向内一层，标签半径减少的量（第 1 层 60 → 51 → 42 → 33）
LABEL_LAYER_STEP = 9.0
#: 标签半径下限（契约 §14.2：最小不小于 20）
LABEL_R_MIN = 20.0

#: 轴框位置：高度 0.80，给 r=110 的染色体号留出上方空间（否则被标题压住/出画布）
AX_POSITION = [0.03, 0.10, 0.94, 0.80]

#: 出图字体：用 `rc_context` 局部设置，**不动全局 rcParams**。
#: 为什么必须这样做：App 的 `import_config` 把 `font.sans-serif` 设成 `['SimHei','Microsoft YaHei']`，
#: 而 `SimHei` 只有单一字重（无 bold 字面）→ matplotlib 命中第一个 family 后就回退 400，
#: 日志刷 `findfont: Failed to find font weight bold, now using 400`，标题/染色体号/正中物种名
#: 全都不粗（与用户已验收的试跑图不一致）。
#: 这里让**必然存在**且**有真粗体**的 DejaVu Sans（matplotlib 自带）优先，
#: 中文字形交给系统里的中文字体兜底。
#:
#: ⚠️ 两个实测坑（都验证过，别改回去）：
#: 1) `font.family` 必须写成**显式列表**（不能只写 'sans-serif'）：matplotlib 的字体回退链是
#:    由 `font.family` 生成的，`font.family='sans-serif'` 时回退链只有 1 个字体
#:    （`font.sans-serif` 只用来解析泛名，不进回退链）→ 中文标题变"豆腐块"
#:    （Glyph 26579 missing from font(s) DejaVu Sans）。
#: 2) 回退链里**不能混入"无粗体字面"的中文字体**（本机 `SimHei` 只有 weight=400）：
#:    实测每有一个 `fontweight="bold"` 的文本就刷一条 `Failed to find font weight bold` 警告
#:    （本内核有标题/染色体号/正中物种名 3 处粗体 ⇒ 3 条）。所以本机取 `Microsoft YaHei`
#:    （有 msyhbd.ttc 粗体字面，且 gui_styles.py 自己也在用它做中文 UI 字体）。
_CJK_FONT_CANDIDATES = ("Microsoft YaHei", "SimHei")


def _pick_cjk_fallbacks():
    """挑中文字体进绘图回退链（模块导入时算一次）。

    优先"有真粗体字面"的中文字体；都没有时才退回第一个存在的（中文能显示，
    代价是粗体文本会刷警告，属无法两全的降级）。查 `fontManager.ttflist` 而不用
    `findfont()`：后者在字体缺失时会自己往日志写 "Font family ... not found"。
    """
    try:
        weights = {}
        for entry in font_manager.fontManager.ttflist:
            name = getattr(entry, "name", None)
            if not name:
                continue
            try:
                weight = int(getattr(entry, "weight", 400))
            except Exception:
                weight = 400
            weights.setdefault(name, []).append(weight)
        for cand in _CJK_FONT_CANDIDATES:
            if cand in weights and any(w >= 600 for w in weights[cand]):
                return [cand]
        for cand in _CJK_FONT_CANDIDATES:
            if cand in weights:
                return [cand]
    except Exception:
        pass
    return ["Microsoft YaHei"]


_FONT_RC = {
    "font.family": ["DejaVu Sans"] + _pick_cjk_fallbacks(),
    "font.sans-serif": ["DejaVu Sans"] + _pick_cjk_fallbacks(),
    "axes.unicode_minus": False,
}

# ---------------------------------------------------------------------------
# 图例自适应（"量-调"循环）
# ---------------------------------------------------------------------------
#: 默认列数与字号（= 用户已验收的 10 英寸图：一行三项）
LEGEND_NCOL_DEFAULT = 3
LEGEND_FONTSIZE_DEFAULT = 9.5
#: 图例允许占用的最大画布宽度比例（两侧各留 2% 安全边）
LEGEND_WIDTH_FRACTION = 0.96
#: 字号下限（再小就没法读了）
LEGEND_MIN_FONTSIZE = 6.0
#: "量-调"迭代上限
LEGEND_MAX_ITER = 5

DEFAULT_GC_VMIN, DEFAULT_GC_VMAX = 30.0, 56.0

#: 一条染色体一个专属颜色（贯穿 R1~R5 与染色体号，同基色不同明度）
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860",
           "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD", "#2E5A88", "#E07B54",
           "#3E8E5A", "#A83C40", "#6A5FA0", "#7A6652", "#C070AE", "#6E6E6E",
           "#B8A45C", "#4A9CB5", "#8FB8DE", "#F0B27A", "#9CCB9C", "#E39A9C"]

#: Giemsa 条带配色（照抄试跑脚本）
CYTO_CMAP = {"gneg": "#FFFFFFB3", "gpos25": "#D9D9D9B3", "gpos50": "#A6A6A6B3",
             "gpos75": "#666666B3", "gpos100": "#1A1A1AB3", "acen": "#C00000CC",
             "gvar": "#BFBFBFB3", "stalk": "#808080B3"}

#: TSV 表头首列黑名单（各表表头首列不同，统一在这里列全）
_HEADER_FIRST = {"chrom", "symbol", "genea", "gene"}
#: 基因列表文件里"看起来是表头"的首行值
_GENE_HEADER_TOKENS = {"gene", "genes", "genename", "gene name", "gene_name", "gene symbol",
                       "gene_symbol", "symbol", "symbols", "geneid", "gene_id", "id",
                       "基因", "基因名", "基因名称", "基因符号", "名称", "gene symbol"}

_SUPPORTED_FORMATS = ("png", "svg", "pdf")
_GENE_LIST_EXTS = (".xlsx", ".xls", ".txt", ".csv")

#: assembly → 圈中心显示的版本名（用户已视觉验收的版本显示 GRCh38）
_ASSEMBLY_LABELS = {"hg38": "GRCh38", "hg19": "GRCh37", "grch38": "GRCh38", "mm10": "GRCm38"}
#: assembly → STRING 物种号（仅 hg38/hg19 有人类数据；非人类物种回退 9606）
_STRING_SPECIES = {"hg38": 9606, "hg19": 9606, "grch38": 9606, "mm10": 10090, "mm39": 10090}


# ===========================================================================
# 模块级小工具
# ===========================================================================
def _shade(hex_color, factor):
    """同一基色的明暗变体：factor<1 变深，factor>1 变浅（照抄试跑脚本）。"""
    r, g, b = mcolors.to_rgb(hex_color)
    if factor <= 1:
        rgb = (r * factor, g * factor, b * factor)
    else:
        k = factor - 1.0
        rgb = (r + (1 - r) * k, g + (1 - g) * k, b + (1 - b) * k)
    return mcolors.to_hex(rgb)


def _blend(h1, h2, t):
    """两色线性插值（t=0 取 h1，t=1 取 h2）。"""
    a, b = mcolors.to_rgb(h1), mcolors.to_rgb(h2)
    return mcolors.to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def _as_bool_flag(value):
    """把 '0'/'1'/'yes'/'no' 等列值统一成 bool。"""
    try:
        s = str(value).strip().lower()
    except Exception:
        return False
    if s in ("1", "1.0", "y", "yes", "true", "t"):
        return True
    try:
        return float(s) != 0.0
    except Exception:
        return False


def _iter_tsv(path, ncol=1, header_first=None):
    """按行读 TSV：跳过空行 / `#` 注释行 / 表头行（首列命中 header_first）。

    不返回 DataFrame —— 这几张固定参考表用纯文本逐行读最稳，也避免"嗅探"类坑。
    """
    rows = []
    if not path or not os.path.isfile(path):
        return rows
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                parts = s.split("\t")
                first = parts[0].strip().lower()
                if header_first and first in header_first:
                    continue
                if len(parts) < ncol:
                    continue
                rows.append([p.strip() for p in parts])
    except Exception:
        return rows
    return rows


def _read_text_genes(path):
    """文本类基因列表：**逐行取首个字段**。

    ⚠️ 历史坑：绝不能用 `pd.read_csv(sep=None, engine="python")` 让 pandas 嗅探分隔符
    —— 单列基因名（如 `H1-4`、`C1orf61`）会被嗅探器切碎/并列，直接毁数据。
    这里只在行内**显式**出现分隔符时才取第一段，否则整行即基因名。
    """
    genes = []
    text = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            with io.open(path, "r", encoding=enc, errors="strict") as fh:
                text = fh.read()
            break
        except Exception:
            text = None
    if text is None:
        return genes
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        field = line
        for sep in ("\t", ",", ";", "，"):
            if sep in field:
                field = field.split(sep, 1)[0]
                break
        token = field.strip().strip('"').strip("'").strip()
        if token:
            genes.append(token)
    return genes


def _read_excel_genes(path):
    """xlsx/xls 基因列表：**无表头**取第一列（header=None）。

    ⚠️ 这里必须 `header=None`：`appdata/genelists` 的全部 xlsx 都是**无表头**的，
    若用默认 `header=0`，第一行的基因名会被 pandas 当成列名吃掉（静默丢一个基因）。
    """
    import pandas as pd
    df = pd.read_excel(path, header=None, dtype=str)
    if df is None or getattr(df, "shape", (0, 0))[1] < 1:
        return []
    genes = []
    for value in df.iloc[:, 0].tolist():
        if value is None:
            continue
        try:
            if value != value:      # NaN（空单元格）
                continue
        except Exception:
            pass
        token = str(value).strip().strip('"').strip("'").strip()
        if token and token.lower() not in ("nan", "none", "na", "null"):
            genes.append(token)
    return genes


def _drop_header_token(genes):
    """去掉"首行是表头"的情况（只在第一个元素命中白名单时删）。"""
    if genes and genes[0].strip().lower() in _GENE_HEADER_TOKENS:
        return genes[1:]
    return genes


def _pick_color(chrom_order, prefer, mapping):
    """取某个染色体颜色；该染色体不存在时退回中间的染色体（保证图例不崩）。"""
    for name in prefer:
        if name in mapping:
            return mapping[name]
    if not chrom_order:
        return "#4C72B0"
    return mapping[chrom_order[len(chrom_order) // 2]]


def _clamp_float(value, value_range, default):
    """把脏值/越界值钳到 `value_range`；无法解析时取 default。"""
    low, high = value_range
    try:
        v = float(value)
    except Exception:
        return float(default)
    if v != v:                      # NaN
        return float(default)
    return float(min(max(v, low), high))


def _clamp_int(value, value_range, default):
    """整数版钳制（用于层数）。"""
    low, high = value_range
    try:
        v = int(round(float(value)))
    except Exception:
        return int(default)
    return int(min(max(v, low), high))


def _label_radii(layers):
    """契约 §14.2：第 1 层半径 60，每多一层向内推 9，半径下限 20。

    返回长度 == layers 的半径列表（严格递减）：1→[60]、2→[60,51]、3→[60,51,42]、4→[60,51,42,33]。
    """
    count = max(1, int(layers))
    radii = []
    for i in range(count):
        radius = R_LABEL - LABEL_LAYER_STEP * i
        if radius < LABEL_R_MIN:
            radius = LABEL_R_MIN
        if radii and radius >= radii[-1]:
            # 触底后仍要求"严格递减"（契约 §14.4-20 会断言递减），逐层再降 1
            radius = radii[-1] - 1.0
        radii.append(float(radius))
    return radii


# ===========================================================================
# 内核
# ===========================================================================
class CircosAnalysis:
    """Circos 圈图内核（纯 Python）。API 见契约 §7，签名已冻结。"""

    def __init__(self, log_callback=None):
        """log_callback(str) 可选；内核所有日志统一走 self.log()。"""
        self.log_callback = log_callback
        self._last_out_dir = None        # 最近一次输出目录
        self._last_render = None         # 最近一次 render 的参数（export_current 用）
        self._karyotype_cache = {}       # assembly -> (sizes, order)
        self._coords_cache = {}          # assembly -> (by_symbol, upper_map)
        self._band_cache = {}            # assembly -> {chrom: [(s, e, name)]}
        self._density_cache = {}         # (assembly, tier) -> {chrom: [(s, e, n)]}
        self._gc_cache = {}              # (assembly, tier) -> {chrom: [(s, e, v)]}

    # ------------------------------------------------------------ 日志
    def log(self, message):
        """统一日志出口：优先 log_callback，其次 stdout（无回调时便于独立自测）。"""
        text = str(message)
        callback = self.log_callback
        if callable(callback):
            try:
                callback(text)
                return
            except Exception:
                pass
        try:
            print(text)
        except Exception:
            pass

    # ============================================================ 数据源
    def list_assemblies(self):
        """扫描 CIRCOS_DATA_DIR 里形如 `karyotype_<asm>.tsv` 的文件，返回排好序的 asm 列表。"""
        out = []
        try:
            for name in os.listdir(CIRCOS_DATA_DIR):
                low = name.lower()
                if low.startswith("karyotype_") and low.endswith(".tsv"):
                    asm = name[len("karyotype_"):-len(".tsv")]
                    if asm and asm not in out:
                        out.append(asm)
        except Exception as exc:
            self.log("[circos] 扫描参考数据目录失败：%s（%s）" % (CIRCOS_DATA_DIR, exc))
            return []
        return sorted(out)

    def scan_gene_lists(self):
        """GENELIST_DIR 下的 xlsx/xls/txt/csv **绝对路径**（排序）；目录不存在返回 []。

        目录定位与文件名解析复用 `bulk_gene_set_utils`，保证全 App 一个口径。
        """
        paths = []
        if callable(_bulk_list_gene_set_files) and callable(_bulk_gene_set_file_path):
            try:
                for name in _bulk_list_gene_set_files():
                    p = _bulk_gene_set_file_path(name)
                    if p:
                        paths.append(p)
            except Exception as exc:
                self.log("[circos] 扫描基因列表目录失败：%s" % exc)
                paths = []
        else:
            self.log("[circos] 未能加载 bulk_gene_set_utils，改用内置扫描（%s）"
                     % (_BULK_GENESET_IMPORT_ERROR,))
            try:
                for name in os.listdir(GENELIST_DIR):
                    p = os.path.join(GENELIST_DIR, name)
                    if os.path.isfile(p) and name.lower().endswith(_GENE_LIST_EXTS):
                        paths.append(p)
            except Exception:
                return []
        return sorted(paths)

    def read_gene_list_file(self, path):
        """读外部基因列表文件，返回基因名列表（去重保序）；失败返回 [] 并记日志。

        · 收**绝对路径**（契约）；若传进来的是文件名，用 `gene_set_file_path()` 兜底解析；
        · xlsx/xls → 无表头取第一列；txt/csv → 逐行取首个字段（不用 sep=None 嗅探）；
        · 跳过表头行与空行。
        """
        if not path:
            return []
        target = str(path).strip().strip('"').strip("'")
        if not os.path.isfile(target):
            # 兜底：把"文件名"解析成 appdata/genelists 下的绝对路径
            if callable(_bulk_gene_set_file_path):
                try:
                    resolved = _bulk_gene_set_file_path(os.path.basename(target))
                except Exception:
                    resolved = None
                if resolved and os.path.isfile(resolved):
                    target = resolved
            if not os.path.isfile(target):
                self.log("[circos] 基因列表文件不存在：%s" % target)
                return []

        low = target.lower()
        genes = []
        if low.endswith((".xlsx", ".xls")):
            try:
                genes = _read_excel_genes(target)
            except Exception as exc:
                self.log("[circos] 读取 Excel 基因列表失败，改按文本逐行读：%s（%s）" % (target, exc))
                genes = _read_text_genes(target)
        else:
            genes = _read_text_genes(target)

        genes = self._dedupe(_drop_header_token(genes))
        if not genes:
            self.log("[circos] 基因列表为空或无法解析：%s" % target)
        return genes

    def parse_gene_text(self, text):
        """多行文本 → 基因列表：按 换行/制表/逗号/分号/空白 切分；去引号；去重保序。

        忽略以 `#` 开头的行（注释）。契约 §6.2 的占位提示即"每行一个，也支持逗号/空格分隔"。
        """
        if text is None:
            return []
        tokens = []
        for line in str(text).splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            for raw in re.split(r"[\s,;，；、]+", s):
                token = raw.strip().strip('"').strip("'").strip()
                if token:
                    tokens.append(token)
        return self._dedupe(tokens)

    # ============================================================ 查询
    def lookup_genes(self, symbols, assembly="hg38"):
        """基因符号 → 坐标定位。

        返回 {'found':[{'symbol','chrom','start','end','strand','has_coding'}...],
              'missing':[symbol...],
              'duplicated':{symbol:[chrom...]}}
        大小写不敏感（先精确匹配、再 upper 匹配）；一个符号落在多条染色体时**第一条为准**
        并在 `duplicated` 里登记所有染色体。查不到的走 `missing`，绝不静默丢弃。
        """
        by_symbol, upper_map = self._load_coords(assembly)
        found, missing = [], []
        duplicated = {}
        seen = set()
        for raw in (symbols or []):
            if isinstance(raw, dict):
                raw = raw.get("symbol") or raw.get("gene") or ""
            sym = str(raw or "").strip().strip('"').strip("'").strip()
            if not sym:
                continue
            entries = by_symbol.get(sym)
            if not entries:
                canonical = upper_map.get(sym.upper())
                if canonical:
                    entries = by_symbol.get(canonical)
            if not entries:
                if sym not in missing:
                    missing.append(sym)
                continue
            first = entries[0]
            key = first.get("symbol", sym)
            if key in seen:
                continue
            seen.add(key)
            chroms = []
            for entry in entries:
                if entry.get("chrom") not in chroms:
                    chroms.append(entry.get("chrom"))
            if len(chroms) > 1:
                duplicated[key] = chroms
            found.append(dict(first))
        if missing:
            self.log("[circos] %d 个基因在 %s 坐标表里没有记录（已跳过）：%s"
                     % (len(missing), assembly, "、".join(missing[:20])
                        + ("…" if len(missing) > 20 else "")))
        if duplicated:
            self.log("[circos] %d 个基因命中多条染色体（取第一条）：%s"
                     % (len(duplicated), "、".join(sorted(duplicated)[:20])))
        return {"found": found, "missing": missing, "duplicated": duplicated}

    # ============================================================ 绘图
    def render(self, found, *, assembly="hg38", tier=5,
               show_ideogram=True, show_gc=True, show_density_heatmap=True,
               show_density_bars=True, show_loci=True, show_gene_labels=True,
               show_legend=True, show_title=True,
               title_text="Chromosomal Distribution of Genes",
               species="Homo sapiens", max_labels=40,
               links=None, dpi=300, figsize=10, formats=("png",), out_dir=None,
               link_anchor=None, label_fontsize=9, label_layers=2, label_min_sep=10.0):
        """画 Circos 圈图并存盘。

        Args:
            found: `lookup_genes()['found']`（也兼容直接给基因名列表，内部会自己查一次）。
            tier: 窗口档位（1/2/5/10/20，可给 int 或 "5 Mb"）。
            links: PPI 连线，元素可为 (symA, symB[, score]) 或
                   (symA, symB, chromA, startA, endA, chromB, startB, endB, score) 或
                   参考脚本风格的 dict（a/ca/sa/ea/b/cb/sb/eb/score）。
            formats: 需要落盘的格式，png/svg/pdf 的任意子集。
            link_anchor: 契约 §14.1 —— `None`（默认）自动取"最内圈可见环的内缘"
                   （由内向外：位点环 70 → 密度柱 75.5 → 密度热图 83 → GC 88 → 核型带 94；
                   全环都关时回退 45）；给数字则强制该半径。基因名牵引线与弦用同一锚点。
            label_fontsize: 契约 §14.2 —— 基因名字号（4–16，默认 9）。
            label_layers: 契约 §14.2 —— 标签半径层数（1–4，默认 2；第 1 层 60，每层向内推 9，
                   半径下限 20）。
            label_min_sep: 契约 §14.2 —— 同层标签最小角度间隔（2–30 度，默认 10.0）。

        Returns:
            {'out_dir', 'files':[...], 'plot_path', 'genes':[...], 'stats':{...}}
            · `genes` 每项：symbol/chrom/start/end/length/cytoband/gene_density/gc/
              labeled/status（未匹配到窗口的值写 "-"，与试跑脚本口径一致）；
            · `plot_path`：用于界面预览，优先 png，无 png 时取第一个文件。
        """
        if Circos is None:
            raise RuntimeError("pycirclize 不可用，无法绘制 Circos 图：%s" % (_PYCIRCLIZE_IMPORT_ERROR,))

        # ---------------- 参数归一化 ----------------
        asm = str(assembly or "hg38").strip() or "hg38"
        tier_n = self._normalize_tier(asm, tier)
        fmt_list = self._normalize_formats(formats)
        try:
            dpi_v = int(round(float(dpi)))
        except Exception:
            dpi_v = 300
        if dpi_v <= 0:
            dpi_v = 300
        fig_w, fig_h = self._normalize_figsize(figsize)
        try:
            max_labels_v = int(float(max_labels))
        except Exception:
            max_labels_v = 40
        title_str = str(title_text or "").strip()
        title_shown = bool(show_title) and bool(title_str)
        # ---- 契约 §14 新增参数：一律钳到契约给定范围（界面越界或脏值都不会画出怪图）----
        anchor_v = None
        if link_anchor is not None and str(link_anchor).strip() != "":
            try:
                anchor_v = float(link_anchor)
                if anchor_v != anchor_v:      # NaN
                    anchor_v = None
            except Exception:
                anchor_v = None
                self.log("[circos] link_anchor 不是数字（%r），改用自动锚点" % (link_anchor,))
        label_fontsize_v = _clamp_float(label_fontsize, LABEL_FONTSIZE_RANGE, 9.0)
        label_layers_v = _clamp_int(label_layers, LABEL_LAYERS_RANGE, 2)
        label_min_sep_v = _clamp_float(label_min_sep, LABEL_MIN_SEP_RANGE, 10.0)

        out_dir = str(out_dir).strip() if out_dir else self.new_output_dir()
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as exc:
            self.log("[circos] 输出目录创建失败：%s（%s）" % (out_dir, exc))

        params = {
            "found": found,
            "assembly": asm,
            "tier": tier_n,
            "show_ideogram": bool(show_ideogram),
            "show_gc": bool(show_gc),
            "show_density_heatmap": bool(show_density_heatmap),
            "show_density_bars": bool(show_density_bars),
            "show_loci": bool(show_loci),
            "show_gene_labels": bool(show_gene_labels),
            "show_legend": bool(show_legend),
            "show_title": title_shown,
            "title_text": title_str,
            "species": str(species or "").strip(),
            "max_labels": max_labels_v,
            "links": links,
            "dpi": dpi_v,
            "figsize": (fig_w, fig_h),
            "link_anchor": anchor_v,
            "label_fontsize": label_fontsize_v,
            "label_layers": label_layers_v,
            "label_min_sep": label_min_sep_v,
        }

        targets = [(os.path.join(out_dir, "circos_genes.%s" % ext), ext) for ext in fmt_list]
        # ⚠️ 字体 rc_context 必须把「建图 + savefig」一起包住：matplotlib 的字体查找发生在
        #    **draw**（即 savefig）阶段，只包住建图会让粗体在落盘时又回退成 400。
        with matplotlib.rc_context(_FONT_RC):
            info = self._render_core(params)
            files = self._save_targets(info["fig"], targets, dpi_v,
                                       title=params["title_text"] if title_shown else None)

        plot_path = ""
        for path, ext in zip([t[0] for t in targets], fmt_list):
            if ext == "png":
                plot_path = path
                break
        if not plot_path:
            plot_path = files[0] if files else ""

        self._last_out_dir = out_dir
        self._last_render = {"params": dict(params), "out_dir": out_dir}
        stats = dict(info["stats"])
        stats["n_files"] = len(files)
        stats["plot_path"] = plot_path
        return {"out_dir": out_dir, "files": files, "plot_path": plot_path,
                "genes": info["genes"], "stats": stats}

    def new_output_dir(self):
        """`OUT_BASE/circos/<YYYYmmdd_HHMMSS>/`（已存在则追加 _2/_3… 保证唯一并创建）。"""
        base = os.path.join(OUT_BASE, "circos")
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = os.path.join(base, stamp)
        try:
            idx = 2
            while os.path.exists(target):
                target = os.path.join(base, "%s_%d" % (stamp, idx))
                idx += 1
            os.makedirs(target, exist_ok=True)
            return target
        except Exception as exc:
            self.log("[circos] 创建输出目录失败：%s（%s），改用临时目录" % (target, exc))
            import tempfile
            fallback = os.path.join(tempfile.gettempdir(), "koyuki_circos", stamp)
            os.makedirs(fallback, exist_ok=True)
            return fallback

    def export_current(self, dst_path):
        """用**最近一次 render 的参数**按 dst_path 的扩展名重新出图（png/svg/pdf）。

        返回实际写出的路径；无缓存 / 扩展名不支持 / 写失败时返回 ""（并记日志）。
        矢量格式是真的重新出图（不是把 PNG 改后缀）。
        """
        if not self._last_render:
            self.log("[circos] 导出失败：还没有可导出的图，请先点「运行」")
            return ""
        dst = str(dst_path or "").strip().strip('"')
        if not dst:
            self.log("[circos] 导出失败：没有指定目标路径")
            return ""
        ext = os.path.splitext(dst)[1].lower().lstrip(".")
        if ext not in _SUPPORTED_FORMATS:
            self.log("[circos] 导出失败：不支持的格式 .%s（只支持 png / svg / pdf）" % ext)
            return ""
        parent = os.path.dirname(os.path.abspath(dst))
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception as exc:
            self.log("[circos] 导出失败：无法创建目标目录 %s（%s）" % (parent, exc))
            return ""

        try:
            with matplotlib.rc_context(_FONT_RC):
                info = self._render_core(dict(self._last_render["params"]))
                title = info["stats"].get("title") or None
                files = self._save_targets(info["fig"], [(dst, ext)],
                                           info["stats"].get("dpi", 300), title=title)
        except Exception as exc:
            self.log("[circos] 导出重绘失败：%s" % exc)
            return ""
        if files:
            self.log("[circos] 已按 .%s 重新出图（%s）：%s"
                     % (ext, "矢量" if ext in ("svg", "pdf") else "位图", dst))
            return dst
        return ""

    def open_output_dir(self, out_dir=None):
        """打开输出目录（Windows `os.startfile`）；失败返回 False 并记日志。"""
        target = out_dir or self._last_out_dir
        if not target:
            self.log("[circos] 还没有输出目录，请先点「运行」")
            return False
        target = str(target)
        if not os.path.isdir(target):
            self.log("[circos] 输出目录不存在：%s" % target)
            return False
        if not hasattr(os, "startfile"):
            self.log("[circos] 当前系统不支持 os.startfile，请手动打开：%s" % target)
            return False
        try:
            os.startfile(target)  # noqa: S606 - Windows 打开资源管理器
            return True
        except Exception as exc:
            self.log("[circos] 打开输出目录失败：%s（%s）" % (target, exc))
            return False

    # ---------------------------------------------------------- 便捷属性
    @property
    def last_out_dir(self):
        """最近一次的输出目录（无则 None）——供界面给「导出」对话框做默认目录。"""
        return self._last_out_dir

    # ============================================================ 联网（可选）
    def fetch_string_links(self, symbols, *, min_score=0.7, top_n=20, timeout=60):
        """联网查 STRING 互作网络；**任何异常都返回 []** 并 self.log 说明原因。

        离线环境必须能正常用（返回空列表即可，绝不抛出）。
        返回 [(symbol_a, symbol_b, score), ...]（按 score 降序，最多 top_n 条），
        可直接作为 `render(links=...)` 的入参。
        """
        try:
            syms = []
            for raw in (symbols or []):
                s = str(raw or "").strip().strip('"').strip("'").strip()
                if s and s not in syms:
                    syms.append(s)
            if len(syms) < 2:
                self.log("[circos] STRING 连线跳过：至少需要 2 个基因（当前 %d 个）" % len(syms))
                return []
            try:
                score_i = int(round(float(min_score) * 1000))
            except Exception:
                score_i = 700
            score_i = min(max(score_i, 0), 1000)
            try:
                timeout_f = float(timeout)
            except Exception:
                timeout_f = 60.0
            if timeout_f <= 0:
                timeout_f = 60.0

            asm = "hg38"
            if self._last_render and self._last_render.get("params"):
                asm = self._last_render["params"].get("assembly", "hg38")
            species = _STRING_SPECIES.get(str(asm).lower(), 9606)

            payload = urllib.parse.urlencode({
                "identifiers": "\r".join(syms),
                "species": species,
                "required_score": score_i,
                "caller_identity": "koyuki_analyzer",
            }).encode("utf-8")
            request = urllib.request.Request(
                "https://string-db.org/api/tsv/network", data=payload,
                headers={"User-Agent": "koyuki_analyzer/circos",
                         "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(request, timeout=timeout_f) as resp:
                raw_text = resp.read().decode("utf-8", "replace")

            lines = [ln for ln in raw_text.splitlines() if ln.strip()]
            if not lines:
                self.log("[circos] STRING 返回空结果（可能这些基因间没有达到置信度的互作）")
                return []
            header = [h.strip() for h in lines[0].lstrip("#").split("\t")]
            idx_a = header.index("preferredName_A") if "preferredName_A" in header else 2
            idx_b = header.index("preferredName_B") if "preferredName_B" in header else 3
            idx_s = header.index("score") if "score" in header else 5
            pairs, seen = [], set()
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) <= max(idx_a, idx_b, idx_s):
                    continue
                a, b = parts[idx_a].strip(), parts[idx_b].strip()
                try:
                    score = float(parts[idx_s])
                except Exception:
                    continue
                if not a or not b or score < float(min_score):
                    continue
                key = tuple(sorted((a, b)))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append((a, b, score))
            pairs.sort(key=lambda item: -item[2])
            try:
                top_n_i = int(top_n)
            except Exception:
                top_n_i = 20
            if top_n_i > 0:
                pairs = pairs[:top_n_i]
            self.log("[circos] STRING 查到 %d 条互作（置信度 ≥ %.2f，取前 %s 条）"
                     % (len(pairs), float(min_score), top_n_i if top_n_i > 0 else "全部"))
            return pairs
        except Exception as exc:  # noqa: BLE001 - 联网功能绝不抛出
            self.log("[circos] STRING 查询失败，已跳过连线（不影响出图）：%s" % exc)
            return []

    # =========================================================================
    # 内部：参数归一化
    # =========================================================================
    def _normalize_tier(self, assembly, tier):
        """档位归一化：允许 int / '5' / '5 Mb'；缺失时取最接近的可用档并记日志。"""
        avail = self._available_tiers(assembly)
        value = None
        if isinstance(tier, str):
            m = re.search(r"(\d+)", tier)
            value = int(m.group(1)) if m else None
        else:
            try:
                value = int(tier)
            except Exception:
                value = None
        if not value or value <= 0:
            value = 5
        if avail:
            if value not in avail:
                nearest = min(avail, key=lambda n: (abs(n - value), n))
                self.log("[circos] %s 没有 %d Mb 档数据，改用 %d Mb（可用：%s）"
                         % (assembly, value, nearest,
                            "/".join("%d" % n for n in avail)))
                value = nearest
        else:
            self.log("[circos] 未找到 %s 的基因密度/GC 档位文件（目录：%s）" % (assembly, CIRCOS_DATA_DIR))
        return value

    def _available_tiers(self, assembly):
        """扫描 `gene_density_<asm>_<N>Mb.tsv` 得到可用档位列表。"""
        tiers = set()
        prefix = "gene_density_%s_" % assembly
        try:
            for name in os.listdir(CIRCOS_DATA_DIR):
                low = name.lower()
                if low.startswith(prefix.lower()) and low.endswith("mb.tsv"):
                    m = re.search(r"_(\d+)mb\.tsv$", low)
                    if m:
                        tiers.add(int(m.group(1)))
        except Exception:
            return []
        return sorted(tiers)

    @staticmethod
    def _normalize_formats(formats):
        """导出格式归一化：png/svg/pdf 子集，保序去重；非法项忽略。"""
        if isinstance(formats, str):
            formats = re.split(r"[,\s;|]+", formats)
        out = []
        for item in (formats or ()):
            ext = str(item or "").strip().lower().lstrip(".")
            if ext in (".png", "png"):
                ext = "png"
            if ext in _SUPPORTED_FORMATS and ext not in out:
                out.append(ext)
        if not out:
            out = ["png"]
        return out

    @staticmethod
    def _normalize_figsize(figsize):
        """图幅归一化：标量 → 正方形 (v, v)；二元组原样。"""
        if isinstance(figsize, (tuple, list)) and len(figsize) == 2:
            try:
                w, h = float(figsize[0]), float(figsize[1])
            except Exception:
                w = h = 10.0
        else:
            try:
                w = h = float(figsize)
            except Exception:
                w = h = 10.0
        if w <= 0:
            w = 10.0
        if h <= 0:
            h = 10.0
        return w, h

    @staticmethod
    def _dedupe(items):
        """去重保序（优先复用 bulk 基因集模块的同一实现）。"""
        if callable(_bulk_dedupe):
            try:
                return _bulk_dedupe(list(items))
            except Exception:
                pass
        out, seen = [], set()
        for item in items:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    # =========================================================================
    # 内部：参考数据加载（带缓存）
    # =========================================================================
    def _load_karyotype(self, assembly):
        """→ (sizes: {chrom: length}, order: [chrom...])，顺序即文件顺序。"""
        if assembly in self._karyotype_cache:
            return self._karyotype_cache[assembly]
        rows = _iter_tsv(os.path.join(CIRCOS_DATA_DIR, "karyotype_%s.tsv" % assembly),
                         3, _HEADER_FIRST)
        sizes, order = {}, []
        for parts in rows:
            chrom = parts[0]
            try:
                length = int(float(parts[2]))
            except Exception:
                continue
            if not chrom or length <= 0:
                continue
            if chrom not in sizes:
                order.append(chrom)
            sizes[chrom] = length
        if not sizes:
            self.log("[circos] 核型表为空或缺失：karyotype_%s.tsv" % assembly)
        else:
            self.log("[circos] 核型表：%d 条染色体（%s）" % (len(order), assembly))
        self._karyotype_cache[assembly] = (sizes, order)
        return sizes, order

    def _load_coords(self, assembly):
        """→ (by_symbol: {symbol: [entry...]}, upper_map: {UPPER: 首个 canonical symbol})"""
        if assembly in self._coords_cache:
            return self._coords_cache[assembly]
        rows = _iter_tsv(os.path.join(CIRCOS_DATA_DIR, "gene_coords_%s.tsv" % assembly),
                         5, _HEADER_FIRST)
        by_symbol, upper_map = {}, {}
        for parts in rows:
            symbol = parts[0]
            if not symbol:
                continue
            try:
                start = int(float(parts[2]))
                end = int(float(parts[3]))
            except Exception:
                continue
            entry = {
                "symbol": symbol,
                "chrom": parts[1],
                "start": start,
                "end": end,
                "strand": parts[4] if len(parts) > 4 else "+",
                "has_coding": _as_bool_flag(parts[5]) if len(parts) > 5 else False,
            }
            by_symbol.setdefault(symbol, []).append(entry)
            upper_map.setdefault(symbol.upper(), symbol)
        self._coords_cache[assembly] = (by_symbol, upper_map)
        return by_symbol, upper_map

    def _load_bands(self, assembly):
        """→ {chrom: [(start, end, name)]}（核型条带，用于基因 cytoband 列）。"""
        if assembly in self._band_cache:
            return self._band_cache[assembly]
        rows = _iter_tsv(os.path.join(CIRCOS_DATA_DIR, "cytoband_%s.tsv" % assembly), 4)
        bands = {}
        for parts in rows:
            try:
                start = int(float(parts[1]))
                end = int(float(parts[2]))
            except Exception:
                continue
            bands.setdefault(parts[0], []).append((start, end, parts[3]))
        self._band_cache[assembly] = bands
        return bands

    def _load_density(self, assembly, tier):
        """→ {chrom: [(start, end, gene_count)]}"""
        key = (assembly, tier)
        if key in self._density_cache:
            return self._density_cache[key]
        rows = _iter_tsv(os.path.join(CIRCOS_DATA_DIR,
                                      "gene_density_%s_%dMb.tsv" % (assembly, tier)),
                         4, _HEADER_FIRST)
        table = {}
        for parts in rows:
            try:
                start = int(float(parts[1]))
                end = int(float(parts[2]))
                count = int(float(parts[3]))
            except Exception:
                continue
            table.setdefault(parts[0], []).append((start, end, count))
        self._density_cache[key] = table
        return table

    def _load_gc(self, assembly, tier):
        """→ {chrom: [(start, end, gc_percent)]}；装配缺口写 NaN，原样保留给分段逻辑。"""
        key = (assembly, tier)
        if key in self._gc_cache:
            return self._gc_cache[key]
        rows = _iter_tsv(os.path.join(CIRCOS_DATA_DIR, "gc_%s_%dMb.tsv" % (assembly, tier)),
                         4, _HEADER_FIRST)
        table = {}
        for parts in rows:
            try:
                start = int(float(parts[1]))
                end = int(float(parts[2]))
            except Exception:
                continue
            raw = parts[3].strip().lower()
            if raw in ("nan", "na", "none", ""):
                value = float("nan")
            else:
                try:
                    value = float(parts[3])
                except Exception:
                    continue
            table.setdefault(parts[0], []).append((start, end, value))
        self._gc_cache[key] = table
        return table

    # =========================================================================
    # 内部：基因记录
    # =========================================================================
    def _coerce_found(self, found, assembly):
        """把 render 的入参统一成"坐标记录"列表（兼容直接给基因名/字符串列表）。"""
        entries = []
        symbols = []
        for item in (found or []):
            if isinstance(item, dict):
                entries.append(item)
            elif isinstance(item, str) or isinstance(item, (int, float)):
                symbols.append(item)
        if symbols:
            entries.extend(self.lookup_genes(symbols, assembly)["found"])
        return entries

    @staticmethod
    def _norm_chrom(chrom, sizes):
        """染色体名兼容（无 `chr` 前缀时补上）。"""
        name = str(chrom or "").strip()
        if not name:
            return ""
        if name in sizes:
            return name
        alt = name if name.lower().startswith("chr") else "chr" + name
        if alt in sizes:
            return alt
        return name

    def _build_records(self, entries, sizes, band_index, density, gc_table, chrom_order):
        """把坐标记录补全成绘图/表格记录（cytoband / gene_density / gc / labeled）。"""
        records, skipped = [], []
        for entry in entries:
            symbol = str(entry.get("symbol") or entry.get("gene") or "").strip()
            chrom = self._norm_chrom(entry.get("chrom"), sizes)
            if not symbol:
                continue
            if chrom not in sizes:
                skipped.append("%s(%s)" % (symbol, entry.get("chrom")))
                continue
            try:
                start = int(float(entry.get("start")))
                end = int(float(entry.get("end")))
            except Exception:
                skipped.append(symbol)
                continue
            if end < start:
                start, end = end, start
            mid = (start + end) // 2
            records.append({
                "symbol": symbol,
                "chrom": chrom,
                "start": start,
                "end": end,
                "length": end - start,
                "mid": mid,
                "cytoband": self._find_band(band_index, chrom, mid),
                "gene_density": self._find_window(density, chrom, mid),
                "gc": self._find_window(gc_table, chrom, mid),
                "labeled": False,
            })
        if skipped:
            self.log("[circos] %d 个基因不在核型表覆盖的染色体上（已跳过）：%s"
                     % (len(skipped), "、".join(skipped[:20]) + ("…" if len(skipped) > 20 else "")))
        ordered = sorted(records, key=lambda r: (chrom_order.index(r["chrom"]), r["start"]))
        return ordered, skipped

    @staticmethod
    def _find_band(band_index, chrom, pos):
        """按位置查核型带名（如 `17p13.1`），与试跑脚本口径一致。"""
        for start, end, name in band_index.get(chrom, []):
            if start <= pos < end:
                return "%s%s" % (chrom.replace("chr", ""), name)
        return "NA"

    @staticmethod
    def _find_window(table, chrom, pos):
        """按位置查窗口值（密度=基因数 int；GC=百分比 float，NaN 记为缺失）。"""
        for start, end, value in table.get(chrom, []):
            if start <= pos < end:
                if isinstance(value, float):
                    if value != value:
                        return None
                    return round(value, 2)
                return value
        return None

    def _resolve_links(self, links, assembly, sizes):
        """PPI 连线入参归一化 → [{'chrom_a','start_a','end_a','chrom_b','start_b','end_b','score'}]"""
        if not links:
            return []
        by_symbol, upper_map = self._load_coords(assembly)

        def _symbol_coord(symbol):
            name = str(symbol or "").strip()
            if not name:
                return None
            entry = None
            found = by_symbol.get(name)
            if not found:
                canonical = upper_map.get(name.upper())
                if canonical:
                    found = by_symbol.get(canonical)
            if found:
                entry = found[0]
            if not entry:
                return None
            chrom = self._norm_chrom(entry.get("chrom"), sizes)
            if chrom not in sizes:
                return None
            return (chrom, int(entry["start"]), int(entry["end"]))

        resolved, dropped = [], 0
        for item in links:
            try:
                coord_a = coord_b = None
                score = 1.0
                if isinstance(item, dict):
                    score = float(item.get("score", 1.0))
                    if item.get("ca") and item.get("sa") is not None:
                        ca = self._norm_chrom(item.get("ca"), sizes)
                        if ca in sizes:
                            coord_a = (ca, int(item["sa"]), int(item.get("ea", item["sa"])))
                    if item.get("cb") and item.get("sb") is not None:
                        cb = self._norm_chrom(item.get("cb"), sizes)
                        if cb in sizes:
                            coord_b = (cb, int(item["sb"]), int(item.get("eb", item["sb"])))
                    if coord_a is None:
                        coord_a = _symbol_coord(item.get("a") or item.get("geneA") or item.get("symbol_a"))
                    if coord_b is None:
                        coord_b = _symbol_coord(item.get("b") or item.get("geneB") or item.get("symbol_b"))
                elif isinstance(item, (tuple, list)):
                    if len(item) >= 9:
                        ca = self._norm_chrom(item[1], sizes)
                        cb = self._norm_chrom(item[5], sizes)
                        score = float(item[8])
                        if ca in sizes:
                            coord_a = (ca, int(item[2]), int(item[3]))
                        if cb in sizes:
                            coord_b = (cb, int(item[6]), int(item[7]))
                    elif len(item) >= 3:
                        coord_a = _symbol_coord(item[0])
                        coord_b = _symbol_coord(item[1])
                        score = float(item[2])
                    elif len(item) == 2:
                        coord_a = _symbol_coord(item[0])
                        coord_b = _symbol_coord(item[1])
                if coord_a is None or coord_b is None:
                    dropped += 1
                    continue
                resolved.append({"chrom_a": coord_a[0], "start_a": coord_a[1], "end_a": coord_a[2],
                                 "chrom_b": coord_b[0], "start_b": coord_b[1], "end_b": coord_b[2],
                                 "score": score})
            except Exception:
                dropped += 1
        if dropped:
            self.log("[circos] %d 条连线无法定位到坐标，已跳过" % dropped)
        return resolved

    # =========================================================================
    # 内部：真正画图
    # =========================================================================
    def _render_core(self, params):
        """按归一化参数出图；返回 {'fig','genes','stats'}（不做存盘，不碰实例状态）。"""
        assembly = params["assembly"]
        tier = params["tier"]
        dpi = params.get("dpi", 300)
        fig_w, fig_h = params.get("figsize", (10.0, 10.0))
        max_labels = params.get("max_labels", 40)

        sizes, chrom_order = self._load_karyotype(assembly)
        if not sizes:
            raise RuntimeError("核型表缺失：%s/karyotype_%s.tsv" % (CIRCOS_DATA_DIR, assembly))

        band_index = self._load_bands(assembly)
        # 密度/GC 恒加载：即使对应环被关掉，基因表的 gene_density/gc 列与 stats.gc_axis
        # 仍要完整（表格不该因为"没勾某个环"就变成 "-"）。
        density = self._load_density(assembly, tier)
        gc_table = self._load_gc(assembly, tier)

        entries = self._coerce_found(params.get("found"), assembly)
        records, skipped = self._build_records(entries, sizes, band_index, density, gc_table, chrom_order)

        # ---- 契约 §14.1：可见环统计 + 连线/牵引线锚点（"最内圈可见环的内缘"）----
        # 与真实绘制条件严格对齐：开关打开 **且** 该环确实有数据（位点环还需要有基因）。
        ring_visible = {
            "loci": bool(params.get("show_loci", True) and records),
            "bars": bool(params.get("show_density_bars", True) and density),
            "heatmap": bool(params.get("show_density_heatmap", True) and density),
            "gc": bool(params.get("show_gc", True) and gc_table),
            "ideogram": bool(params.get("show_ideogram", True)),
        }
        n_visible_rings = sum(1 for visible in ring_visible.values() if visible)
        forced_anchor = params.get("link_anchor")
        if forced_anchor is not None:
            r_anchor = float(forced_anchor)
            self.log("[circos] 连线/牵引线锚点：手动指定 r=%.2f（可见环 %d 个）"
                     % (r_anchor, n_visible_rings))
        else:
            r_anchor = None
            for ring_key, inner_r in RING_ANCHOR_ORDER:
                if ring_visible.get(ring_key):
                    r_anchor = float(inner_r)
                    break
            if r_anchor is None:
                r_anchor = float(LINK_FALLBACK_R)
                self.log("[circos] 所有环都已关闭：连线/牵引线锚点回退 r=%.0f（契约 §14.1）"
                         % r_anchor)
            else:
                self.log("[circos] 连线/牵引线锚点 = r=%.1f（最内圈可见环的内缘，可见环 %d 个）"
                         % (r_anchor, n_visible_rings))

        # ---- 契约 §14.2：标签半径分层与字号/最小角距 ----
        label_radii = _label_radii(params.get("label_layers", 2))
        label_fontsize = params.get("label_fontsize", 9)
        label_min_sep = params.get("label_min_sep", LABEL_MIN_SEP)
        # 弦最深点 ≈ r_anchor * LINK_DEPTH_RATIO（pycirclize 用 height_ratio 控制控制点半径：
        # 最深点半径 ≈ 0.5*(r_anchor - 100*(height_ratio-0.5))，反解出下面的 height_ratio）
        link_ctl_r = max(0.0, r_anchor * (1.0 - 2.0 * LINK_DEPTH_RATIO))
        link_height_ratio = 0.5 + link_ctl_r / LINK_MAX_R
        link_deepest = 0.5 * (r_anchor - link_ctl_r)

        # ---- 色阶：一条染色体一个颜色（同基色 → 深/浅变体）----
        chrom_color = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(chrom_order)}
        chrom_dark = {c: _shade(v, 0.78) for c, v in chrom_color.items()}
        chrom_tint = {c: _shade(v, 1.85) for c, v in chrom_color.items()}

        # ---- 密度色阶上限：97 分位（避免个别极端窗口吃掉整条色阶）----
        dens_values = sorted(n for rows in density.values() for _s, _e, n in rows)
        dens_vmax = dens_values[int(len(dens_values) * 0.97)] if dens_values else 1
        if dens_vmax <= 0:
            dens_vmax = 1

        # ---- GC 纵轴范围：**按该档实测极值**算（各档不同，1 Mb 档到 ~59%）----
        gc_valid = [v for rows in gc_table.values() for _s, _e, v in rows if v == v]
        if gc_valid:
            gc_vmin = float(math.floor(min(gc_valid) - 2))
            gc_vmax = float(math.ceil(max(gc_valid) + 2))
            if gc_vmax - gc_vmin < 20:
                mid = (gc_vmax + gc_vmin) / 2.0
                gc_vmin, gc_vmax = float(math.floor(mid - 10)), float(math.ceil(mid + 10))
        else:
            gc_vmin, gc_vmax = DEFAULT_GC_VMIN, DEFAULT_GC_VMAX

        # ---- 建圈 ----
        circos = Circos({c: sizes[c] for c in chrom_order}, space=1.5)

        # ---- R1 cytoband ideogram + 每 50 Mb 刻度 ----
        if params["show_ideogram"]:
            for sector in circos.sectors:
                band = sector.add_track(R_IDEO)
                band.axis(fc=chrom_color[sector.name], ec="#666666", lw=0.3)
                band.xticks_by_interval(
                    interval=50_000_000, outer=True, tick_length=1.5,
                    label_size=6.5, label_margin=0.4, show_bottom_line=False,
                    label_formatter=lambda v: "%d" % int(v // 1_000_000))
            cytoband_path = os.path.join(CIRCOS_DATA_DIR, "cytoband_%s.tsv" % assembly)
            if os.path.isfile(cytoband_path):
                try:
                    circos.add_cytoband_tracks(R_IDEO, cytoband_path, cytoband_cmap=CYTO_CMAP)
                except Exception as exc:
                    self.log("[circos] 核型条带轨绘制失败，保留纯色核型条：%s" % exc)
            else:
                self.log("[circos] 未找到核型条带表：%s" % cytoband_path)

        # ---- R2 GC 含量（面积 + 轮廓线；NaN 缺口按连续有效段分段画）----
        if params["show_gc"] and gc_table:
            for sector in circos.sectors:
                rows = gc_table.get(sector.name, [])
                if not rows:
                    continue
                track = sector.add_track(R_GC)
                track.axis(fc=chrom_tint[sector.name], ec="#e2e2e2", lw=0.3)
                runs, current = [], []
                for start, end, value in rows:
                    if value == value:                       # 非 NaN
                        current.append(((start + end) / 2.0, value))
                    elif current:
                        runs.append(current)
                        current = []
                if current:
                    runs.append(current)
                color = chrom_color[sector.name]
                dark = chrom_dark[sector.name]
                for run in runs:
                    xs = [x for x, _y in run]
                    ys = [y for _x, y in run]
                    if len(run) >= 2:
                        # 基线必须落在 [vmin, vmax] 内 → 用 gc_vmin，不能用 0
                        track.fill_between(xs, ys, gc_vmin, vmin=gc_vmin, vmax=gc_vmax,
                                           fc=color, alpha=0.75, ec="none")
                        track.line(xs, ys, vmin=gc_vmin, vmax=gc_vmax, color=dark, lw=0.6)
                    else:
                        track.scatter(xs, ys, vmin=gc_vmin, vmax=gc_vmax, s=8, color=dark)

        # ---- R3 基因密度 heatmap（该染色体自身色阶：白→深色）----
        if params["show_density_heatmap"] and density:
            for sector in circos.sectors:
                rows = density.get(sector.name, [])
                if not rows:
                    continue
                track = sector.add_track(R_HEAT)
                track.axis(fc="#ffffff", ec="#e2e2e2", lw=0.3)
                lo, hi = R_HEAT
                for start, end, count in rows:
                    t = min(count, dens_vmax) / float(dens_vmax)
                    fc = _blend("#FFFFFF", chrom_dark[sector.name], t) if count > 0 else "#f4f4f4"
                    track.rect(start, end, r_lim=(lo, hi), fc=fc, ec="none")

        # ---- R4 基因密度柱状（柱高随密度）----
        if params["show_density_bars"] and density:
            for sector in circos.sectors:
                rows = density.get(sector.name, [])
                if not rows:
                    continue
                track = sector.add_track(R_HIST)
                track.axis(fc=chrom_tint[sector.name], ec=chrom_color[sector.name], lw=0.3)
                lo, hi = R_HIST
                for start, end, count in rows:
                    if count <= 0:
                        continue
                    height = lo + (min(count, dens_vmax) / float(dens_vmax)) * (hi - lo)
                    track.rect(start, end, r_lim=(lo, height), fc=chrom_dark[sector.name], ec="none")

        # ---- R5 输入基因散点（同时算出各自的极角，供标签分层）----
        degrees = {}
        if params["show_loci"] and records:
            for sector in circos.sectors:
                group = [r for r in records if r["chrom"] == sector.name]
                if not group:
                    continue
                track = sector.add_track(R_LOCUS)
                track.axis(fc=chrom_tint[sector.name], ec="#e8e8e8", lw=0.3)
                lo, hi = R_LOCUS
                mid_r = (lo + hi) / 2.0
                for rec in group:
                    track.scatter([rec["mid"]], [mid_r], vmin=lo, vmax=hi, s=26,
                                  color=_shade(chrom_color[sector.name], 0.55),
                                  ec="white", lw=0.5, zorder=5)
                    try:
                        degrees[id(rec)] = math.degrees(sector.x_to_rad(rec["mid"])) % 360.0
                    except Exception:
                        degrees[id(rec)] = 0.0
        elif records:
            # 位点环关掉时，仍需要角度信息用于标签牵引线
            for sector in circos.sectors:
                for rec in [r for r in records if r["chrom"] == sector.name]:
                    try:
                        degrees[id(rec)] = math.degrees(sector.x_to_rad(rec["mid"])) % 360.0
                    except Exception:
                        degrees[id(rec)] = 0.0

        # ---- 染色体号（r=110 > 绘图半径 100 → 轴高必须 ≤0.80）----
        for sector in circos.sectors:
            circos.text(sector.name.replace("chr", ""), r=R_NUM, deg=sum(sector.deg_lim) / 2.0,
                        size=11, color=chrom_dark[sector.name], fontweight="bold")

        # ---- 圈内基因名 + 牵引线（水平书写；角度相近的自动换半径层，默认 60/51）----
        # 契约 §14.1（含协调者澄清）：牵引线外端接到同一个锚点 r_anchor（同样"不悬空"）；
        # 但**所有环都关（n_visible_rings == 0）时不画牵引线** —— 回退锚点 45 落在标签半径
        # （60/51）之内，画出来只会是"从标签朝圆心指"，没有可指的对象，纯属怪现象。
        # 这种情形下弦仍按回退半径 45 画（保留"基因间关系"信息）。
        draw_leader = bool(n_visible_rings >= 1)
        n_labeled = 0
        if params["show_gene_labels"] and records and max_labels > 0:
            ordered = sorted(records, key=lambda r: degrees.get(id(r), 0.0))
            slots = []          # 每层：[最近占用角度, 半径]
            placed = []
            for rec in ordered:
                deg = degrees.get(id(rec), 0.0)
                chosen = None
                for idx, (last_deg, _radius) in enumerate(slots):
                    delta = abs(deg - last_deg)
                    if min(delta, 360.0 - delta) >= label_min_sep:
                        chosen = idx
                        break
                if chosen is None:
                    if len(slots) >= len(label_radii):
                        continue        # 所有层都挤满 → 只画点不标名（避免叠字）
                    slots.append([deg, label_radii[len(slots)]])
                    chosen = len(slots) - 1
                else:
                    slots[chosen][0] = deg
                placed.append((deg, rec, slots[chosen][1]))
            # 超过 max_labels 时按顺序均匀抽稀（保证全圈都有标注，而不是只标左半圈）
            if len(placed) > max_labels:
                step = int(math.ceil(len(placed) / float(max_labels)))
                placed = placed[::step]
            for deg, rec, radius in placed:
                if draw_leader:
                    circos.line(r=(radius + 2.0, r_anchor), deg_lim=(deg, deg), arc=False,
                                color="#666666", lw=0.7)
                circos.text(rec["symbol"], r=radius, deg=deg,
                            ha=("right" if deg <= 180 else "left"), va="center",
                            size=label_fontsize, color="#111111")
                rec["labeled"] = True
                n_labeled += 1
            if n_labeled < len(records):
                self.log("[circos] 基因名标注 %d / %d 个（其余只画位点不标名；字号 %g，%d 层 %s）"
                         % (n_labeled, len(records), label_fontsize, len(label_radii),
                            "/".join("%g" % r for r in label_radii)))

        # ---- PPI 连线（契约 §14.1：外端接 r_anchor；最深点 ≈ r_anchor * 0.35）----
        link_list = self._resolve_links(params.get("links"), assembly, sizes)
        if link_list:
            scores = [lnk["score"] for lnk in link_list]
            smin, smax = min(scores), max(scores)
            for lnk in link_list:
                t = 0.0 if smax == smin else (lnk["score"] - smin) / (smax - smin)
                circos.link((lnk["chrom_a"], lnk["start_a"], lnk["end_a"]),
                            (lnk["chrom_b"], lnk["start_b"], lnk["end_b"]),
                            r1=r_anchor, r2=r_anchor, color="#B2182B",
                            alpha=0.18 + 0.42 * t, height_ratio=link_height_ratio)

        # ---- 圈中心：物种名（全英文）----
        species = params.get("species") or ""
        asm_label = _ASSEMBLY_LABELS.get(assembly.lower(), assembly)
        if species or asm_label:
            circos.text("%s\n(%s)" % (species, asm_label), r=0, deg=0, size=15,
                        color="#111111", fontweight="bold", linespacing=1.5)

        # ---- 出图：layout engine=none + 手工定位，保证导出严格 figsize*dpi ----
        fig = circos.plotfig(figsize=(fig_w, fig_h))
        fig.set_layout_engine("none")
        if fig.axes:
            # 染色体号在 r=110（超出 0~100 绘图半径）→ 轴框高度必须 ≤0.80
            fig.axes[0].set_position(list(AX_POSITION))
        try:
            fig.patch.set_facecolor("white")
        except Exception:
            pass
        if params["show_title"] and params["title_text"]:
            fig.suptitle(params["title_text"], fontsize=16, fontweight="bold", y=0.99)

        # ---- 图例：按环开关取舍 ----
        legend_info = None
        if params["show_legend"]:
            handles = []
            if params["show_ideogram"]:
                handles.append(Patch(fc="#4A4A4A", label="Cytoband (Giemsa)"))
            if params["show_gc"] and gc_table:
                handles.append(Patch(fc=_pick_color(chrom_order, ("chr3",), chrom_color),
                                     label="GC content (%)"))
            if params["show_density_heatmap"] and density:
                handles.append(Patch(
                    fc=_blend("#FFFFFF", _pick_color(chrom_order, ("chr3",), chrom_dark), 0.9),
                    label="Gene density (heatmap / %d Mb)" % tier))
            if params["show_density_bars"] and density:
                handles.append(Patch(fc=_pick_color(chrom_order, ("chr5",), chrom_dark),
                                     label="Gene density (bars)"))
            if params["show_loci"] and records:
                handles.append(Line2D([], [], marker="o", ls="", ms=7,
                                      mfc=_pick_color(chrom_order, ("chr7",), chrom_dark),
                                      mec="white",
                                      label="Input genes (n = %d)" % len(records)))
            if link_list:
                handles.append(Line2D([], [], color="#B2182B", alpha=0.6, lw=2,
                                      label="PPI links (STRING, n = %d)" % len(link_list)))
            if handles:
                legend_info = self._add_fitted_legend(fig, handles)

        # ---- 对外基因表 ----
        genes_out = []
        for rec in records:
            density_value = rec["gene_density"]
            gc_value = rec["gc"]
            genes_out.append({
                "symbol": rec["symbol"],
                "chrom": rec["chrom"],
                "start": rec["start"],
                "end": rec["end"],
                "length": rec["length"],
                "cytoband": rec["cytoband"],
                "gene_density": "-" if density_value is None else density_value,
                "gc": "-" if gc_value is None else gc_value,
                "labeled": bool(rec["labeled"]),
                "status": "labeled" if rec["labeled"] else "located",
            })

        stats = {
            "n_genes": len(genes_out),
            "n_chrom": len(chrom_order),
            "gc_axis": (float(gc_vmin), float(gc_vmax)),
            "tier": tier,
            "tier_label": "%d Mb" % tier,
            "assembly": assembly,
            "n_input": len(entries),
            "n_skipped": len(skipped),
            "n_labeled": n_labeled,
            "n_links": len(link_list),
            "density_vmax": dens_vmax,
            "dpi": dpi,
            "figsize": (fig_w, fig_h),
            "title": params["title_text"] if params["show_title"] else "",
            "legend": legend_info,
            # ---- 契约 §14.1 / §14.2 回报（门禁直接断言，不靠数像素）----
            "link_anchor": float(r_anchor),
            "link_anchor_forced": forced_anchor is not None,
            "link_height_ratio": round(float(link_height_ratio), 4),
            "link_deepest": round(float(link_deepest), 2),
            "label_radius": [float(r) for r in label_radii],
            "label_fontsize": float(label_fontsize),
            "label_layers": int(len(label_radii)),
            "label_min_sep": float(label_min_sep),
            "n_visible_rings": int(n_visible_rings),
            "visible_rings": sorted(k for k, v in ring_visible.items() if v),
            "label_leader": bool(draw_leader),
        }
        return {"fig": fig, "genes": genes_out, "stats": stats}

    def _legend_width_px(self, fig, legend):
        """量图例在画布上的像素宽度；量不出来返回 None。

        必须**先 draw 再量**：图例内部 offsetbox 的布局要到第一次绘制后才有正确的
        text extent，否则 `get_window_extent()` 会给出 0/错值，自适应就会失效。
        """
        try:
            fig.canvas.draw()
        except Exception:
            pass
        renderer = None
        try:
            renderer = fig.canvas.get_renderer()
        except Exception:
            renderer = None
        if renderer is None:
            try:
                from matplotlib.backends.backend_agg import RendererAgg
                renderer = RendererAgg(fig.bbox.width, fig.bbox.height, fig.dpi)
            except Exception:
                return None
        try:
            return float(legend.get_window_extent(renderer).width)
        except Exception:
            return None

    def _add_fitted_legend(self, fig, handles):
        """画图例并保证**不被画布左右裁切**（小图幅下固定 3 列必然溢出）。

        做法（确定性，不靠猜）：先按 3 列画 → `canvas.draw()` → 量宽度，与
        `fig.bbox.width * 0.96` 比较：超了就**减列**（3→2→1），1 列仍超就按比例**缩字号**
        （下限 6 号），最多迭代 5 次；实在放不下则保留最后一次并记日志。
        量与调都在同一张图、同一 dpi 下进行，而"图例宽/画布宽"是 dpi 无关的比例量，
        所以 100 dpi 下量准 ⇒ 300 dpi 导出也准。

        返回 {'ncol','fontsize','width_px','available_px','fitted','iterations'}。
        """
        available = float(fig.bbox.width) * LEGEND_WIDTH_FRACTION
        ncol = LEGEND_NCOL_DEFAULT
        fontsize = LEGEND_FONTSIZE_DEFAULT
        legend, width, iterations = None, None, 0
        for _attempt in range(LEGEND_MAX_ITER):
            iterations += 1
            if legend is not None:
                try:
                    legend.remove()
                except Exception:
                    pass
            legend = fig.legend(handles=handles, loc="lower center", ncol=ncol,
                                frameon=False, fontsize=fontsize,
                                bbox_to_anchor=(0.5, 0.005))
            width = self._legend_width_px(fig, legend)
            if width is None or width <= available:
                break
            if ncol > 1:
                ncol -= 1          # 列数越少越窄
                continue
            # 只剩 1 列还超宽 → 按比例缩字号（留 2% 余量）
            new_size = max(LEGEND_MIN_FONTSIZE, fontsize * (available / width) * 0.98)
            if new_size >= fontsize - 0.05:     # 已到字号下限，缩不动了
                break
            fontsize = round(new_size, 2)

        fitted = (width is not None) and (width <= available)
        if width is None:
            self.log("[circos] 图例宽度无法测量，跳过自适应（保持 %d 列 / %.2f 号字）"
                     % (ncol, fontsize))
        elif not fitted:
            self.log("[circos] 图幅过小：图例已压缩到 %d 列 / %.2f 号字仍可能超出画布"
                     "（宽 %.0f > 可用 %.0f px）" % (ncol, fontsize, width, available))
        elif iterations > 1:
            self.log("[circos] 图幅偏小，图例已自适应压缩为 %d 列 / %.2f 号字"
                     "（宽 %.0f ≤ 可用 %.0f px，迭代 %d 次）"
                     % (ncol, fontsize, width, available, iterations))
        return {"ncol": int(ncol), "fontsize": round(float(fontsize), 2),
                "width_px": None if width is None else round(float(width), 1),
                "available_px": round(available, 1), "fitted": bool(fitted),
                "iterations": int(iterations)}

    def _save_targets(self, fig, targets, dpi, title=None):
        """按 (path, ext) 列表存盘；返回成功写出的路径列表。

        ⚠️ 用 `rc_context` 局部强制 `savefig.bbox="standard"` + `pad_inches=0`
        —— 即使外部把 rcParams 污染成 tight，导出也严格等于 `figsize*dpi`。
        `svg.fonttype` **不强制**：模块导入时已把它还原成 App 原本的值（默认 path，
        即 SVG 文字转曲、自带字形），保存时沿用 App 自己的配置。
        `title` 非空时写进文件元数据（PNG tEXt / SVG dc:title / PDF /Info）——
        图里的标题文字是矢量轮廓、无法 grep，元数据让"标题是否显示"可被脚本验证。
        存完必须 `plt.close(fig)`（长驻 GUI 反复出图会泄漏 figure）。
        """
        saved = []
        try:
            with matplotlib.rc_context({"savefig.bbox": "standard",
                                        "savefig.pad_inches": 0.0}):
                for path, ext in targets:
                    try:
                        parent = os.path.dirname(os.path.abspath(path))
                        if parent:
                            os.makedirs(parent, exist_ok=True)
                        metadata = {"Title": str(title)} if title else None
                        if ext == "png":
                            fig.savefig(path, dpi=dpi, facecolor="white", metadata=metadata)
                        else:
                            fig.savefig(path, facecolor="white", metadata=metadata)
                        saved.append(path)
                        self.log("[circos] 已保存：%s" % path)
                    except Exception as exc:
                        # 元数据不被某后端接受时，退回不带元数据的保存，绝不因此丢掉图
                        try:
                            if ext == "png":
                                fig.savefig(path, dpi=dpi, facecolor="white")
                            else:
                                fig.savefig(path, facecolor="white")
                            saved.append(path)
                            self.log("[circos] 已保存（无元数据）：%s（%s）" % (path, exc))
                        except Exception as exc2:
                            self.log("[circos] 保存失败 %s：%s" % (path, exc2))
        finally:
            try:
                plt.close(fig)
            except Exception:
                pass
        return saved


__all__ = ["CircosAnalysis", "CIRCOS_DATA_DIR", "GENELIST_DIR"]
