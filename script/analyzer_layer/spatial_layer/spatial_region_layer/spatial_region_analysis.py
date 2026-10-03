# -*- coding: utf-8 -*-
"""M4「绘制区域（手画分区改注释）」- analysis 层（纯逻辑，**无 Qt**）

契约：`docs/features/spatial_m2m3_contract.md` §13。

## 本模块负责（§13.5 归 W2）
  · `<ds>.regions.json` 的**容错读**与**原子写**（§13.7 冻结结构）；
  · **点是否在多边形内**（自己实现射线法，**不引新依赖**）；
  · 逐 spot 新标签计算（圈外 = `""`，即 NA；**重叠时后画的覆盖先画的**，§13.3）；
  · 各区域 spot 计数 + 未覆盖数；
  · labels CSV 导出（表头逐字 `spot,label`）；
  · 9 个 signature 名（从 `01_cluster_signature_mean.csv` 的列名读，**不硬编码**，§13.1）；
  · `spots.csv` 的读取（W3 产出，表头冻结 `spot,sample,x,y,cluster,cell_type`）；
  · **调 W3 的 `spatial_region_render.R`** 重绘该样本（沿用 `spatial_gene_expression_analysis`
    的"subprocess + 绝对路径 Rscript + stdin=DEVNULL + 超时 + 全 ASCII 断言"纪律）。

## 明确不做
  · **不碰图集**：不写 `_figure_manifest.csv`、不改 `figure_set_id`；
    产物只落 `OUTPUT/<ds>/09_RegionOverride/`（独立目录，§13.6）。
  · **不读 `.rds` 里的 `cell_type`**：那里 **100% 是 NA**（§13.1 实测），
    细胞类型只从 `spots.csv`（W3 用 `02_cell_type_annotation.csv` join 出来的）取。

## 所有函数**绝不抛**（沿用空转既有范式）
"""

import csv
import io
import math
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback

# -----------------------------------------------------------------------------
# 路径与文件名（契约 §13.6 / §13.7 冻结）
# -----------------------------------------------------------------------------
REGIONS_SUFFIX = ".regions.json"
WORKBENCH_DIR = "_region_workbench"
SPOTS_CSV_NAME = "spots.csv"
SPOTS_HEADER = ("spot", "sample", "x", "y", "cluster", "cell_type")
REGION_OVERRIDE_DIR = "09_RegionOverride"
SIGNATURE_CSV_REL = ("07_CellTypeAnno", "01_cluster_signature_mean.csv")
# 逐 spot 细胞注释 CSV（W3 的 dump 脚本用它 join 出 cell_type；**可选**，§14.5）
ANN_CSV_REL = ("07_CellTypeAnno", "02_cell_type_annotation.csv")
SIGNATURE_COL_PREFIX = "Score_"
SIGNATURE_DROP_COLS = ("cluster",)
LABELS_CSV_HEADER = ("spot", "label")

# ★ 契约 §14.3 冻结的两条后缀文案（**逐字**，不许改写）
OVERRIDE_SUFFIX_OK = "（自定义分区）"
OVERRIDE_SUFFIX_PENDING = "（自定义分区尚未生成或已过期，请回「绘制区域」重新确认）"

# 区域默认样式（§13.7：缺字段一律容错为这些默认值）
DEFAULT_REGION_COLOR = "#FF6B35"
# ★★ v9.2（用户 2026-09-23 新需求）：「**可见区域**的**默认区域颜色**改成**白色**」
#   ⇒ 这是**可见区域**（`visible` 层，即"罩住的区域其边界画虚线"的那一层）的**缺省**颜色；
#     由 `_norm_region` 在"**没给颜色**（缺失 / None / 空串）**且**该区域是可见层"时写入，
#     判据集中在唯一的私有函数 `_region_color_default`（`_norm_region` 与
#     `export_outline_json` 的样式色**共用同一处判据**）。
# ⛔ **不要**动 `DEFAULT_REGION_COLOR`（上面那行）：**普通区域与隐形区域 `mask` 的默认颜色
#   仍然是 `#FF6B35`** —— 把它改成 `#FFFFFF` 是"**全局**默认白"的一行开关（连普通区域一起），
#   不是本次需求。
#   ★ 判据是"分层缺省"：**显式给了非空颜色**一律以给的为准（见 `_region_color_default`）。
DEFAULT_VISIBLE_REGION_COLOR = "#FFFFFF"
DEFAULT_DASH_WIDTH = 2
DEFAULT_DASH_GAP = 6
DEFAULT_LABEL_FONT_SIZE = 12
DEFAULT_LABEL_FONT_COLOR = "#FFFFFF"
# 未覆盖（圈外）的标签 = 空串（§13.3 第 1 条："没有覆盖的叫 NA"）
NA_LABEL = ""
# ★★ §2（`_d_spec_region_naming_v2.md`，2026-09-23）绘图模式**两级命名**：
#   区域名下拉框在"自定义"时新建的那个**分组名**（字面量，冻结）。
#   `anno_group == GROUP_GRAPHED` ⇒ 该区域属于 group_graphed 分组（注释值存在 `anno_label`）；
#   选"现有分组"（cell_type / cluster / ...）时 `anno_group` = 该分组的**列名**。
#   **逐 spot 的 `group_graphed` 列 = 覆盖它的区域的 `anno_label`**（见 `group_graphed_labels`）。
GROUP_GRAPHED = "group_graphed"
# ★★ v11（`_d_spec_v11_split_and_bubble.md` §3.2）**分组候选白名单的唯一真相源**。
#   顺序冻结 = 下拉框顺序（`group`, `cell_type`, `cluster`, `sample`, `region_label`,
#   `group_graphed`）；`group_graphed` **必须在末尾**（v8 冻结口径）。
#   本模块**零项目内 import**（只有标准库）⇒ 放这里不会产生循环 import；
#   空转各页（小提琴 / 差异 / 两个气泡 / 区域）一律从这里取，**不许各自再抄一份**。
#   ⛔ 只统一"白名单"；**不**统一各页的分组筛选判据（小提琴的 `MIN/MAX_GROUP_NUNIQUE`
#      窗口、表达页注释图的固定三项、区域页的单样本枚举 —— 三者语义不同，见 §3.4）。
ANNOTATION_CANDIDATES = ("group", "cell_type", "cluster", "sample",
                         "region_label", GROUP_GRAPHED)
# §15.3：仅呈现用的圆角半径（单位 = 输出图像像素），0 = 尖角，夹到 0..40
DEFAULT_CORNER_RADIUS_PX = 0
# ★★ v9.1（`_d_spec_select_mode.md` §11，2026-09-23）用户原话：
#   「改一下参数，**针对可见区域**，…它的**圆角参数默认调成12**」
#   ⇒ 这是**可见区域**（`visible` 层，即"罩住的区域其边界画虚线"的那一层）的**缺省**圆角；
#     由 `_norm_region` 在"**没给值**（缺失 / None / 空串 / 非数值）且该区域是可见层"时写入。
# ⛔ **不要**动 `DEFAULT_CORNER_RADIUS_PX`（普通区域默认**仍是 0**；隐形区域 mask 也是 0）：
#   把它改成 12 是"**全局**默认 12"的一行开关（连普通区域一起），不是本次需求。
#   ★ 判据是"分层缺省"：**显式给了值（含显式 0）**一律以给的为准（见 `_norm_region`）。
DEFAULT_VISIBLE_CORNER_RADIUS_PX = 12
CORNER_RADIUS_MAX = 40
# §15.4：自动隐藏边规则用的包围盒外扩比例（2% 跨度）
AUTO_HIDE_BBOX_MARGIN = 0.02
# §15.5：第 24 个（**虚拟**）图型 —— 不带 spot 的组织片子 + 虚线轮廓 + 注释
CELLTYPE_SPATIAL_NOSPOT = "celltype_spatial_nospot"
NOSPOT_PREFIX = "SpatialNoSpots"
# 圆角倒角时每条弧用多少段折线近似（段数越多越圆，但 JSON/R 端都更重）
CORNER_ARC_STEPS = 8
# ★ 选择模式（`_d_spec_select_mode.md` §4，2026-09-23）：**数据单位**下"同一个点"的默认容差。
#   调用方（画布 `region_canvas.py`）会把屏幕容差换算成数据单位后显式传入
#   （`tol_data = tol_screen / scale`）⇒ 本常量**只在调用方不传 `tol` 时**才生效；
#   它是**数据坐标**的容差，**不是像素**（本模块无 Qt、不猜缩放）。
SHARED_TOL_DEFAULT = 1e-6

# 本机开发兜底（R_HOME 拿不到时才用；与 GEA 同一策略）
_DEV_RSCRIPT_FALLBACK = r"A:\TOOLS\R\R-4.6.1\bin\x64\Rscript.exe"
_HERE = os.path.dirname(os.path.abspath(__file__))
# 迁移 2026-09-23：每页一个文件夹后，两个 R 脚本与本模块**同目录**（传统层惯例）
_REGION_R_SCRIPT_REL = "spatial_region_render.R"
_DUMP_R_SCRIPT_REL = "spatial_region_dump.R"

# 最近一次导出的失败原因（`export_labels_csv` 只返回 bool，原因放这里，便于排障）
LAST_EXPORT_ERROR = ""
# 原子写临时文件名用的进程内自增序号（与 RA.save_review_scores 同一做法）
_TMP_SEQ = 0


# =============================================================================
# 路径工具
# =============================================================================
def _spatial_main_dir():
    """成品目录 `appdata/spatial_main`（与 M1 的 SPATIAL_SCAN_DATA_PATH 同源）"""
    try:
        from script.utils_layer.import_config import SPATIAL_SCAN_DATA_PATH
        return SPATIAL_SCAN_DATA_PATH
    except Exception:
        try:
            from script.utils_layer.import_config import APPDATA_PATH
            return os.path.join(APPDATA_PATH, "spatial_main")
        except Exception:
            return ""


def _out_base():
    try:
        from script.utils_layer.import_config import OUT_BASE
        return OUT_BASE
    except Exception:
        return ""


def regions_path_for(dataset):
    """`appdata/spatial_main/<ds>.regions.json`（与 review.json 同级）"""
    if not dataset:
        return ""
    d = _spatial_main_dir()
    return os.path.join(d, "%s%s" % (dataset, REGIONS_SUFFIX)) if d else ""


def spots_path_for(dataset):
    """`OUTPUT/<ds>/_region_workbench/spots.csv`（W3 产出）"""
    if not dataset:
        return ""
    o = _out_base()
    return os.path.join(o, dataset, WORKBENCH_DIR, SPOTS_CSV_NAME) if o else ""


def region_override_dir(dataset):
    """`OUTPUT/<ds>/09_RegionOverride/`（重绘产物；**与图集完全隔离**）"""
    if not dataset:
        return ""
    o = _out_base()
    return os.path.join(o, dataset, REGION_OVERRIDE_DIR) if o else ""


def render_output_paths(dataset, sample_id):
    """该样本重绘产物的 `(png, pdf)` 路径（**只是路径**，不保证已存在）"""
    d = region_override_dir(dataset)
    if not d or not sample_id:
        return "", ""
    return (os.path.join(d, "Spatial_%s.png" % sample_id),
            os.path.join(d, "Spatial_%s.pdf" % sample_id))


def is_ascii_path(p):
    """路径是否全为可打印 ASCII（§13 子进程纪律：非 ASCII 会被 R 这边拒）"""
    if not isinstance(p, str) or not p:
        return False
    try:
        p.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


# =============================================================================
# regions.json：容错读 / 原子写（§13.7）
# =============================================================================
def _empty_regions(dataset):
    return {"schema": 1, "dataset": dataset or "", "samples": {}}


def _norm_point(p):
    """一个顶点 → `[float, float]`；不合法 → `None`"""
    try:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            return [float(p[0]), float(p[1])]
        return None
    except (TypeError, ValueError):
        return None


def _norm_edge_override(raw):
    """`edge_override` → `{int边号: "show"|"hide"}`（**JSON 里键是字符串**，要容错）

    ★ 语义（§15.3 冻结）：边号 `i` = `points[i] → points[(i+1) % n]`。
    ★ 容错：键写成 `"0"` / `0` 都收；值不是 `show`/`hide` 的条目**直接丢掉**
      （宁可少一条覆盖，也不要让一个非法值把整份区域拖成无效）。
    """
    out = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        try:
            i = int(str(k).strip())
        except (TypeError, ValueError):
            continue
        sv = str(v or "").strip().lower()
        if sv in ("show", "hide"):
            out[i] = sv
    return out


def _norm_flag(v):
    """★ **严格布尔**：只认 `True` / `1` / `"true"` / `"True"` / `"1"`（去空格、大小写不敏感）

    ⚠ 为什么不能直接 `bool(v)`：`bool("false") == True` —— `regions.json` 是**文本文件**，
      用户/外部工具手改出 `"mask": "false"` 会被当成**真选区**
      ⇒ 那张图**整片虚线被隐藏**，而原因埋在 JSON 一个引号里，极难查。
    ⇒ 白名单之外的一切（`"false"` / `0` / `"0"` / `None` / 缺失 / 其它任意值）**一律 `False`**。
    """
    try:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v == 1                     # 1 / 1.0 → True；0 / 2 / -1 → False
        return str(v).strip().lower() in ("true", "1")
    except Exception:
        return False


def _norm_label_pos(raw):
    """`label_pos` → `[x, y]` 或 `None`（缺失/非法一律 None = 用质心）"""
    try:
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return [float(raw[0]), float(raw[1])]
    except (TypeError, ValueError):
        return None
    return None


def _region_color_default(region, is_visible_layer=None):
    """该区域在"**没给颜色**"时应回落的**默认颜色**（★ v9.2 唯一的一处分层判据）

    · **可见层** ⇒ `DEFAULT_VISIBLE_REGION_COLOR` = `#FFFFFF`
      （用户 v9.2："可见区域的默认区域颜色改成白色"）；
    · 其余（普通区域 / 隐形区域 `mask`）⇒ `DEFAULT_REGION_COLOR` = `#FF6B35`（**原样**）。

    ★ 判据与 `"visible"` 字段**同一套严格布尔** `_norm_flag`（理由见该函数：
      `bool("false") == True` 会把字符串 `"false"` 误判成可见层 ⇒ 白悄悄落到普通区域上）。
    ★ `_norm_flag` 自身**绝不抛**（白名单外一律 False）+ 本函数对非 dict 走 `{}`
      ⇒ 本函数是**全函数，永不抛**，故无需 `except`（房规"不许静默"自然满足）。
    ★ 由 `_norm_region` 与 `export_outline_json` 的样式色**共用** —— 不要在两处各写一份判据
      （正是 `is_layer_region` docstring 里"漏一处就出错"的同一类坑）。

    Args:
        region: 区域 dict（非 dict 一律按"普通区域"处理）
        is_visible_layer: `_norm_region` 已算好的严格布尔（**复用同一个局部量**，避免重复判定）；
            `None` ⇒ 本函数自己用 `_norm_flag(region.get("visible"))` 判一次。
    """
    if is_visible_layer is None:
        is_visible_layer = _norm_flag((region if isinstance(region, dict) else {}).get("visible"))
    return DEFAULT_VISIBLE_REGION_COLOR if is_visible_layer else DEFAULT_REGION_COLOR


def _norm_region(raw):
    """一个区域 → 归一化 dict；**缺字段一律用默认值，绝不抛**（§13.7 / §15.3）

    ★ 顶点数 <3 的区域**保留但标 `invalid=True`**：点判定会直接判否（见
      `point_in_polygon`），但**不静默丢掉** —— 用户画到一半的点也应该能存下来，
      否则"画两个点后刷新页面"就白画了（静默丢数据比留个无效区域更糟）。

    ★★ §15.3 的三个新字段（`edge_override` / `corner_radius_px` / `label_pos`）
      **都是"区域内部"字段**，所以只要本函数带上它们，
      `set_sample_regions` 与 `save_regions` 就**自动**不会丢（两处都调 `_norm_region`）。
      这是刻意设计的：`rendered_hash` 当年会丢，是因为它挂在 **samples 层级**、
      不归本函数管 —— **新字段一律放进区域内部**，从结构上避免同一类坑再犯。
      ⇒ §2（2026-09-23）的两个新字段 `anno_group` / `anno_label` 遵循**同一条纪律**：
        放进本函数的 `out` 里 ⇒ `save_regions` / `set_sample_regions` **自动保留**
        （两处都是 `_norm_region(x)` 后再落盘），**不需要**在读写链路上再加一行。

    ★ §2 两级命名（默认空串，`strip()` 后存放）：
      · `anno_group` —— 选"现有分组"时 = 该分组的**列名**（`cell_type` / `cluster` / …）；
        选"自定义"时 = 字面量 `GROUP_GRAPHED`（`"group_graphed"`）；
      · `anno_label` —— 注释值（用户选的现有值，或自定义输入的名字）。
      · **两者缺失/空 ⇒ 该区域是"旧式"（只有 `name`）**，`assign_labels` / 出图 / 渲染
        一切照旧；`group_graphed_labels` 对旧式区域一律给空串（见该函数）。

    ★★ v9.1（`_d_spec_select_mode.md` §11）：`corner_radius_px` 的**缺省值分两层** ——
      · **可见层**（`_norm_flag(raw["visible"])` 为真）且**没给值** ⇒
        `DEFAULT_VISIBLE_CORNER_RADIUS_PX = 12`（用户："可见区域的圆角参数默认调成12"）；
      · 其余（普通区域 / 隐形区域 `mask`）没给值 ⇒ `DEFAULT_CORNER_RADIUS_PX = 0`（原样）；
      · **显式给了值（含显式 0）一律以给的为准**（"右侧输入框清零"与"没设过"在画布上暂不可分，
        这是规格 §11 已登记的已知限制，归 W1；本函数只认"字段里到底有没有值"）。
      · 判定与 `"visible"` 字段**同一套严格布尔** `_norm_flag`（理由见该函数的说明：
        `bool("false") == True` 会把字符串 `"false"` 误判成可见层 ⇒ 12 悄悄落到普通区域上）。

    ★★ v9.2（用户 2026-09-23 新需求）：`color` 的**缺省值同样分两层**（与上面的圆角同款写法）——
      · **可见层**（**复用同一个局部量** `_is_visible_layer`）且**没给颜色** ⇒
        `DEFAULT_VISIBLE_REGION_COLOR = "#FFFFFF"`（用户："可见区域的默认区域颜色改成白色"）；
      · 其余（普通区域 / 隐形区域 `mask`）没给颜色 ⇒ `DEFAULT_REGION_COLOR = "#FF6B35"`（原样）；
      · **显式给了非空颜色一律以给的为准** —— 沿用一个判定点 `_region_color_default`
        （`export_outline_json` 的样式色也用它，见该行的注释）。
      ⛔ `DEFAULT_REGION_COLOR` 的值**不动**（普通区域与 mask 仍是 `#FF6B35`）。
    """
    if not isinstance(raw, dict):
        return None
    pts = []
    for p in (raw.get("points") or []):
        np_ = _norm_point(p)
        if np_ is not None:
            pts.append(np_)
    # ★★ v9.1（`_d_spec_select_mode.md` §11）：圆角**缺省值分层**（只影响"没给值"的情形）
    #   · 判定用**同一套严格布尔** `_norm_flag`（与下面的 `"visible"` 字段一字不差的口径）：
    #     `bool("false")` 会把字符串 `"false"` 当成可见层 ⇒ 普通区域被悄悄改成 12；
    #   · `_norm_flag` 自身 **绝不抛**（白名单外一律 False）⇒ 放在 `out` 构造前是安全的；
    #   · "没给值"的口径**复用 `_as_float` 既有语义**（`None`/`""` → default，其余走 `float(v)`）
    #     ⇒ **显式 0 仍然是 0**（`0` 既不是 `None` 也不是 `""`），可见层也只有"真没值"才吃 12。
    _is_visible_layer = _norm_flag(raw.get("visible"))
    _corner_radius_default = (DEFAULT_VISIBLE_CORNER_RADIUS_PX if _is_visible_layer
                              else DEFAULT_CORNER_RADIUS_PX)
    out = {
        "name": str(raw.get("name") or "").strip() or "未命名",
        # ★★ v9.2（用户 2026-09-23 新需求）：颜色**缺省值分层**（与上面的圆角同款写法）——
        #   · 可见层（`_is_visible_layer`，即 `"visible"` 字段那套严格布尔）且**没给颜色** ⇒
        #     `DEFAULT_VISIBLE_REGION_COLOR` = `#FFFFFF`（用户："可见区域的默认区域颜色改成白色"）；
        #   · 其余（普通区域 / 隐形区域 `mask`）没给颜色 ⇒ `DEFAULT_REGION_COLOR`（原样 `#FF6B35`）；
        #   · `or` 的既有语义**一个字没改**：`None` / 空串 / 缺失 ⇒ 走兜底；**显式非空色原样保留**
        #     （⛔ 别再叠一层新的判空：那会把 `0` / `False` 这类现有的"走兜底"情形变成"显式值"）。
        # ★ **复用同一个局部量** `_is_visible_layer`（不另起判据）+ 唯一的缺省函数
        #   `_region_color_default`（`export_outline_json` 的样式色也用它 ⇒ 判据只有一处）。
        "color": str(raw.get("color") or _region_color_default(raw, _is_visible_layer)),
        "points": pts,
        "dash_width": _as_float(raw.get("dash_width"), DEFAULT_DASH_WIDTH),
        "dash_gap": _as_float(raw.get("dash_gap"), DEFAULT_DASH_GAP),
        "label_font_size": _as_float(raw.get("label_font_size"), DEFAULT_LABEL_FONT_SIZE),
        "label_font_color": str(raw.get("label_font_color") or DEFAULT_LABEL_FONT_COLOR),
        # ---- §15.3 三个新字段 ----
        "edge_override": _norm_edge_override(raw.get("edge_override")),
        # ★ v9.1：缺省值**分层**（可见层 12 / 其余 0，见上面的 `_corner_radius_default`）；
        #   ⛔ 这里**不能**再写死 `DEFAULT_CORNER_RADIUS_PX`：那会让"可见层缺省 12"
        #   只在字段存在时生效，而"字段缺失"这条最常见的路径反而回落 0（静默不一致）。
        "corner_radius_px": _as_float(raw.get("corner_radius_px"), _corner_radius_default),
        "label_pos": _norm_label_pos(raw.get("label_pos")),
        # ---- §2（2026-09-23）两级命名：分组名 + 注释值（**区域内部**字段）----
        # ★ 放在本函数的 `out` 里 = 放进"区域内部" ⇒ `save_regions` / `set_sample_regions`
        #   自动保留（它们都调本函数）；默认**空串** ⇒ 老 JSON 读回来就是"旧式区域"，一切照旧。
        # ★ `str(... or "").strip()`：JSON 里写 `null` / 缺字段 / 带空格的脏值都归一成干净的空串。
        "anno_group": str(raw.get("anno_group") or "").strip(),   # 列名 或 GROUP_GRAPHED
        "anno_label": str(raw.get("anno_label") or "").strip(),   # 注释值（空 = 旧式区域）
        # ---- 范围层：隐形区域（mask）★ 全链路的命门 ----
        # 丢了这一行，选区会被当成普通区域 ⇒ 出图时**把图糊满虚线**，
        # 而且 `assign_labels` 会让它抢走 spot 归属。缺省/0/""/None → False（普通区域）。
        # ★ 用 `_norm_flag`（**严格布尔**）而不是 `bool(...)`：`bool("false") == True`
        #   会把手改成字符串 `"false"` 的条目当成**真选区**（见 `_norm_flag` 的说明）。
        "mask": _norm_flag(raw.get("mask")),
        # ---- 范围层：可见区域（visible）★ 2026-09 用户新增 ----
        # `"visible": True` = 用户手画的**范围层**多边形：**罩住的区域其边界画虚线**
        # （它自己不出图）；成图时还要再被 `mask` 层罩住才显示。
        # `mask or visible` 为真 ⇒ **范围层**（两个字段各自的判定见 `visible_region_indices`）。
        "visible": _norm_flag(raw.get("visible")),
        "invalid": len(pts) < 3,
    }
    # 圆角按契约夹到 0..40（越界不报错、直接夹）
    # ★ v9.1：下面**两条兜底路径**（夹紧、`except` 回落）必须与上面的分层缺省**同一口径** ——
    #   可见层回落 12、普通/隐形层回落 0。⛔ 别在 `except` 里写死 `DEFAULT_CORNER_RADIUS_PX`：
    #   否则"非数值的圆角"会把这个区域悄悄打回尖角，而同一份数据里缺字段的区域却是 12（静默不一致）。
    try:
        out["corner_radius_px"] = max(0.0, min(float(CORNER_RADIUS_MAX),
                                              float(out["corner_radius_px"])))
    except Exception:
        # ★ 房规：**不许静默** —— 留痕（真调用栈）+ 一条中文日志，然后回落分层缺省
        traceback.print_exc()
        _geo_warn("[spatial_region] _norm_region: corner_radius_px 非法 -> 回落分层缺省 %s"
                  "（visible=%s，name=%r，原值=%r）"
                  % (_corner_radius_default, _is_visible_layer, out.get("name"),
                     raw.get("corner_radius_px")))
        out["corner_radius_px"] = float(_corner_radius_default)
    return out


def _as_float(v, default):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def regions_hash(regions_data, sample_id):
    """★ 契约 §14.3 v2：该样本区域列表的**规范化内容哈希**（与顺序有关、与格式无关）

    Returns:
        str: 16 位 hex；取不到数据时返回 `""`（绝不抛）

    ## 为什么必须用它替代"文件 mtime"（协调者实测认定，这是结构性错）
      `regions.json` 是**整个数据集一个文件** ⇒ 一个文件的 mtime **表达不了逐样本新鲜度**：
        · 确认流程是"先渲染、后存 regions" ⇒ 存完 regions 比图新 ⇒ **刚确认完就判"过期"**；
        · 给**样本 B** 保存会更新同一个文件的 mtime ⇒ **样本 A 的 override 被连带判过期**
          ⇒ 用户在概览页看到第一个样本的成果"消失"。
      ⇒ 改成**逐样本内容哈希**：`samples[<sid>].rendered_hash` 记下"渲染这次用的是哪份区域"，
        与当前区域哈希一比即知新不新。**完全没有时序窗口。**

    ## 规范化（"与格式无关"的具体含义）
      · 先过 `_norm_region`（缺字段补默认值）⇒ 缺 `dash_width` 与显式 `dash_width=2` **同哈希**；
      · 颜色统一大写（`#ff6b35` 与 `#FF6B35` 同哈希）；
      · 数值统一 `float` 并把坐标四舍五入到 **6 位小数**（吃掉浮点格式化噪声，
        但不影响"点真的动了"这种变化 —— 鼠标坐标级别的差异远大于 1e-6）；
      · **列表顺序参与哈希**（后画的覆盖先画的，顺序是语义的一部分）。

    ## ★★ canon 版本 = 3（v2：协调者裁定补齐漏字段；v3：新增 `visible`）
      canon 第一项是 `["canon", <版本>]`；**版本一变，所有历史 `rendered_hash` 全部不再匹配**
      ⇒ 概览页把所有已确认的图判成"过期/需重绘"。这是**如实**的，不是静默：
      旧哈希确实没有覆盖下面这些字段，"它是否新鲜"无从判断。
      ⚠ **绝对不要**为了让提示消失去回写/清理 `regions.json` 里已存的 `rendered_hash`。

    ## 改了哪些字段会让已确认的图**变陈旧**（v3 起，逐项）
      出图结果依赖这些输入，所以它们**必须**在 canon 里，否则就是"静默陈旧"
      （用户改了、图没变、界面还说新鲜）：
        · `name` / `color` / `points` / `dash_width` / `dash_gap` /
          `label_font_size` / `label_font_color`   ← v1 就有
        · **`mask`**（v2 新增）：隐形区域范围层，直接决定"哪些区域出图"；
        · **`visible`**（v3 新增）：可见区域范围层，同样直接决定"哪些区域出图"；
        · **`edge_override`**（v2 新增）：手工显隐边；归一化后**按键号排序**成
          `[[边号, "show"|"hide"], ...]` ⇒ 与字典插入序无关；
        · **`corner_radius_px`**（v2 新增）：圆角倒角；
        · **`label_pos`**（v2 新增）：注释位置；缺省 → `null`
          （**不放质心**：质心由 `points` 决定，已在 canon 里，重复无意义）。
      ⚠ 仍**不在** canon 里、因此改了不会判陈旧的：**UI 全局态**（如 `chk_label_frame`
        的注释外框开关）—— 它不存在区域字典里，canon 无从得知；要修得把"上次出图用的值"
        随 `rendered_hash` 一起存（协调者已裁定**本轮不修**，属新一轮设计）。
    """
    try:
        regs = get_sample_regions(regions_data, sample_id)
        # ★ canon 版本标识：改 canon 结构/字段时必须 +1（理由见 docstring）
        #   v3（2026-09）：新增 `visible`（可见区域范围层）—— 与 `mask` 同理，
        #   它直接决定"哪些区域的虚线出图"，不纳入 canon 就是**静默陈旧**。
        canon = [["canon", 3]]
        for r in regs:
            n = _norm_region(r)
            if n is None:
                continue
            pts = []
            for p in n.get("points") or []:
                try:
                    pts.append([round(float(p[0]), 6), round(float(p[1]), 6)])
                except Exception:
                    continue
            # `edge_override` 按键号排序 ⇒ 与字典插入序无关（否则同内容不同哈希）
            ov = _norm_edge_override(n.get("edge_override"))
            eo = [[int(k), str(ov[k])] for k in sorted(ov.keys())]
            # `label_pos`：缺省 null（不用质心，理由见 docstring）
            lp = n.get("label_pos")
            lp_canon = None
            try:
                if isinstance(lp, (list, tuple)) and len(lp) >= 2:
                    lp_canon = [round(float(lp[0]), 4), round(float(lp[1]), 4)]
            except (TypeError, ValueError):
                lp_canon = None
            canon.append([
                str(n.get("name") or ""),
                str(n.get("color") or "").upper(),
                pts,
                round(float(n.get("dash_width") or 0), 4),
                round(float(n.get("dash_gap") or 0), 4),
                round(float(n.get("label_font_size") or 0), 4),
                str(n.get("label_font_color") or "").upper(),
                bool(n.get("mask")),                                    # v2
                _norm_flag(n.get("visible")),                            # v3
                eo,                                                     # v2
                round(float(n.get("corner_radius_px") or 0), 4),        # v2
                lp_canon,                                               # v2
            ])
        blob = json.dumps(canon, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    except Exception:
        traceback.print_exc()
        return ""


def get_rendered_hash(regions_data, sample_id):
    """读该样本的 `rendered_hash`（渲染成功时写入的"已确认"凭据）；没有 → `""`"""
    try:
        entry = ((regions_data or {}).get("samples") or {}).get(str(sample_id)) or {}
        h = entry.get("rendered_hash")
        return str(h) if h else ""
    except Exception:
        return ""


def set_rendered_hash(regions_data, sample_id, h):
    """写该样本的 `rendered_hash`（**保留它的 regions**，只动这一个字段）

    ★ 只写这一个键：`set_sample_regions` 会整块替换 entry，若在这里用它就会
      把"别的样本的凭据"或"本样本的区域"搞丢（这正是 v1 会连带判过期的根源）。
    """
    try:
        if not isinstance(regions_data, dict):
            return regions_data
        regions_data.setdefault("samples", {})
        sid = str(sample_id)
        entry = regions_data["samples"].get(sid)
        if not isinstance(entry, dict):
            entry = {"regions": []}
        entry["rendered_hash"] = str(h or "")
        regions_data["samples"][sid] = entry
        return regions_data
    except Exception:
        traceback.print_exc()
        return regions_data


def regions_version(dataset):
    """`regions.json` 的廉价版本指纹 `(mtime_ns, size)`；不存在 → `("none", 0)`

    ★ 契约 §14.3 第 4 条要它："`regions.json` 的 `(mtime_ns, size)` 变化 ⇒ 重取该页签图"。
      **只读，绝不写盘**；任何异常都退化成 `("none", 0)`。
    """
    try:
        st = os.stat(regions_path_for(dataset))
        return (int(st.st_mtime_ns), int(st.st_size))
    except Exception:
        return ("none", 0)


def painted_region_count(regions_data, sample_id):
    """该样本**可出图**的区域数（顶点 ≥3 的才算；画到一半的 2 点区域不算一"区"）

    ★ 为什么用"有效区域"而不是"任意区域"来数：2 个顶点的多边形**判不出任何点、
      也确认不出图**，把它算成"已画 1 区"会让用户以为完成了（而概览页不会有任何变化）。
    ★★ **隐形区域（`mask`）不计入**（用户裁定）：
      它是"罩子"，**自己不出图**，只决定别的区域画不画。把只画了隐形区域的样本算成
      "已画 1 区"，会让样本列表显示 `✅ 已画`、`_override_state` 也不再判 `no_regions`
      ⇒ 概览页出现一张"什么都没有"的图。**只画了隐形区域 = 未画。**
    ★★ v9.3 收窄（用户回话后）：本函数判据从 `is_layer_region`（`mask` **+** `visible`）
      收窄为 `is_anno_blocked_region`（**只** `mask`）——**可见区域（`visible`）要计入**。
      理由（三层，缺一不可）：
        ① 用户裁定「可见区域」就是他的**标注单元**，而且本轮起可见区域会在成图里
           **被真正画出来（带名字）**（见 `export_outline_json`）⇒ "范围层自己不出图"
           这个前提对可见区域**不再成立**，它当然算"已画"；
        ② 用户真实数据 `GSM7596590`（1 个隐形 + 3 个可见、**没有普通区域**）与
           `GSM7596591`（只有 2 个可见）正是这种样本：可见区域不计入 ⇒ 它们被判
           `painted_region_count == 0` ⇒ `_override_state`（本文件稍后定义）返回 `"no_regions"`
           ⇒ 概览页/审查页显示"未画"、区域成图不渲染 ⇒ **用户的注释永远出不来图**。
           这是与 `assign_labels`/`export_outline_json` 同一条链路的**最后一环**；
        ③ 隐形区域（`mask`）**保持原样不计入**（它确实自己不出图）。
      ⚠ `is_layer_region` 本体不动（它仍是"范围层 = mask 或 visible"，别处另有用途）。
    """
    try:
        regs = get_sample_regions(regions_data, sample_id)
        return sum(1 for r in regs
                   if isinstance(r, dict) and not r.get("invalid")
                   and not is_anno_blocked_region(r))
    except Exception:
        traceback.print_exc()
        return 0


def ann_csv_path_for(dataset):
    """逐 spot 细胞注释 CSV 的路径（**可能不存在**；§14.5 允许缺）"""
    if not dataset:
        return ""
    o = _out_base()
    return os.path.join(o, dataset, *ANN_CSV_REL) if o else ""


def override_note_suffix(state):
    """把 override 状态翻成**说明行后缀**（§14.3 的两条冻结文案）

    · `ok` → `（自定义分区）`
    · `stale` / `expired` → `（自定义分区尚未生成或已过期，请回「绘制区域」重新确认）`
    · `no_regions` → `""`（无后缀，与今天一致）
    """
    try:
        if state == "ok":
            return OVERRIDE_SUFFIX_OK
        if state in ("stale", "expired"):
            return OVERRIDE_SUFFIX_PENDING
        return ""
    except Exception:
        return ""


# =============================================================================
# §15.1/§15.4 呈现几何：**判定用原始闭合多边形，呈现用派生轮廓**
# =============================================================================
# ★★ 总原则（契约 §15.1，必须落到数据模型）：
#    · **判定**（spot 归属、`point_in_polygon`）**永远用原始闭合多边形**，
#      **不受**隐藏边 / 圆角 / 标签位置影响 —— 下面这些函数**一个都不参与 `assign_labels`**；
#    · **呈现**（画布绘制、R 出图）才用派生的轮廓路径。
#    这是用户 ①③④ 三条的共同结论：为了好看去改判定输入 = 把科研结论画歪，
#    所以两者在**函数层面**就分开，不靠"小心别用错"。

def _spots_bbox(spots, margin=AUTO_HIDE_BBOX_MARGIN):
    """该样本 spot 的包围盒（按跨度外扩 `margin`）→ `(x0, y0, x1, y1)`；无点 → `None`

    ★ 外扩用**跨度**（`x1-x0`）而不是固定像素：不同样本坐标尺度差很多
      （实测 `GSM7596588` x 到 11087，`GSM7596605` 只到 3319），
      按比例外扩才对所有样本一致。
    """
    try:
        xs, ys = [], []
        for s in (spots or []):
            xy = _spot_xy(s)
            if xy is not None:
                xs.append(xy[0])
                ys.append(xy[1])
        if not xs or not ys:
            return None
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        dx = (x1 - x0) * float(margin)
        dy = (y1 - y0) * float(margin)
        return (x0 - dx, y0 - dy, x1 + dx, y1 + dy)
    except Exception:
        traceback.print_exc()
        return None


def _edge_midpoint(points, i):
    """边 `i` 的中点（边 i = `points[i] → points[(i+1) % n]`）；取不到 → `None`"""
    try:
        n = len(points)
        a = points[i % n]
        b = points[(i + 1) % n]
        return ((float(a[0]) + float(b[0])) / 2.0, (float(a[1]) + float(b[1])) / 2.0)
    except Exception:
        return None


def auto_hidden_rule(region, spots):
    """★ **当前采用的自动隐藏规则**（独立成函数 = 换规则只改这一处，别散在代码里）

    冻结规则（§15.4）：**边的中点落在该样本 spot 包围盒（外扩 2% 跨度）之外 ⇒ 自动隐藏**。

    为什么选它：
      · 治的正是用户说的"有些片子自身出界，闭合后边跑到图外"；
      · 它**永远不会让轮廓变空** —— 一个区域只要有点落在包围盒里，至少有一条边可见；
      · 计算是 O(边数)，不碰 37672 个 spot 的逐个判定（不是 O(n²)）。

    ⚠ 用户原话里还有"只想保留和其他区域交界的线"，那是**更激进**的规则：
      单区域样本会一条线都不画（轮廓全空）。**本版暂不采用**（协调者已向用户报备）。
      **要改就替换本函数**（它的返回是"自动隐藏的边号集合"），其余代码一行不用动。
    """
    hidden = set()
    try:
        pts = (region or {}).get("points") or []
        n = len(pts)
        if n < 3:
            return hidden
        bbox = _spots_bbox(spots)
        if bbox is None:
            # 没有 spot 就无从判断"是否跑到图外" ⇒ **不隐藏任何边**
            # （宁可多画几条线，也不要凭空调隐藏；这也是"轮廓永不为空"的保证）
            return hidden
        x0, y0, x1, y1 = bbox
        for i in range(n):
            mid = _edge_midpoint(pts, i)
            if mid is None:
                continue
            if not (x0 <= mid[0] <= x1 and y0 <= mid[1] <= y1):
                hidden.add(i)
        return hidden
    except Exception:
        traceback.print_exc()
        return hidden


def auto_hidden_edge_indices(region, spots):
    """自动隐藏的边号（**升序 list**，契约 §15.4 冻结签名）"""
    try:
        return sorted(auto_hidden_rule(region, spots))
    except Exception:
        traceback.print_exc()
        return []


def visible_edge_indices(region, spots):
    """应用 `edge_override` 之后**可见**的边号（升序 list，§15.4 冻结签名）

    · 起点 = `auto_hidden_rule` 的自动隐藏集合；
    · `edge_override` 里 `"show"` → **强制可见**（把自动隐藏的边救回来）；
    · `edge_override` 里 `"hide"` → **强制隐藏**；
    · 越界边号（`<0` 或 `>= n`）忽略（老文件里可能残留，不该让整块失效）。
    """
    try:
        pts = (region or {}).get("points") or []
        n = len(pts)
        if n < 3:
            return []
        hidden = set(i for i in auto_hidden_rule(region, spots) if 0 <= i < n)
        ov = _norm_edge_override((region or {}).get("edge_override"))
        for i, v in ov.items():
            if not (0 <= i < n):
                continue
            if v == "show":
                hidden.discard(i)
            elif v == "hide":
                hidden.add(i)
        return [i for i in range(n) if i not in hidden]
    except Exception:
        traceback.print_exc()
        return []


def _fillet(p, a, b, r_data, steps=CORNER_ARC_STEPS):
    """把顶点 `p` 处、两侧边指向 `a`/`b` 的尖角换成圆弧倒角

    Args:
        p: 顶点；a: 上一条边的**另一端**；b: 下一条边的**另一端**（都在数据坐标）
        r_data: 圆角半径（**数据单位**，调用方已用 `px_per_data` 换算过）
    Returns:
        `[T1, ...弧上采样点..., T2]`；无法倒角（边长太短/退化）→ `[p]`（保持尖角）

    ## 几何（标准 fillet）
      u1 = unit(a - p)、u2 = unit(b - p)（从顶点指向两侧）
      夹角 φ = angle(u1, u2)；切点距离 `t = r / tan(φ/2)`；
      圆心 `C = p + unit(u1 + u2) * (r / sin(φ/2))`。
      ★ 切点距离**必须夹到边长的一半以内**，否则短边上的两个圆角会互相咬进来，
        折线会出现回折（画出来像打结）。夹紧后圆角变小但**形状仍然合法**。
      ★ 只夹切点距离、**不改半径**，是为了让"切点仍落在原边上"这一条保持成立
        （验收要求：倒角后折线**首尾仍在原边上**）。
    """
    try:
        import math
        if r_data is None or r_data <= 0:
            return [list(p)]
        ax, ay = float(a[0]) - float(p[0]), float(a[1]) - float(p[1])
        bx, by = float(b[0]) - float(p[0]), float(b[1]) - float(p[1])
        la = math.hypot(ax, ay)
        lb = math.hypot(bx, by)
        if la <= 1e-9 or lb <= 1e-9:
            return [list(p)]                      # 退化边（重合点）→ 保持尖角
        u1 = (ax / la, ay / la)
        u2 = (bx / lb, by / lb)
        cos_phi = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        phi = math.acos(cos_phi)
        if phi <= 1e-6 or abs(math.pi - phi) <= 1e-6:
            return [list(p)]                      # 180°（直线）或 0°（回折）→ 不倒角
        half = phi / 2.0
        t = r_data / math.tan(half)
        t = min(t, la / 2.0, lb / 2.0)            # ★ 夹紧，避免圆角互相咬
        if t <= 1e-9:
            return [list(p)]
        # 圆心：沿角平分线方向，距离 r / sin(half)
        bis = (u1[0] + u2[0], u1[1] + u2[1])
        lbis = math.hypot(bis[0], bis[1])
        if lbis <= 1e-9:
            return [list(p)]                      # 两边反向 → 角平分线退化
        bis = (bis[0] / lbis, bis[1] / lbis)
        r_eff = t * math.tan(half)                # 夹紧后**实际**半径（<= 原半径）
        cx = float(p[0]) + bis[0] * (r_eff / math.sin(half))
        cy = float(p[1]) + bis[1] * (r_eff / math.sin(half))
        t1 = (float(p[0]) + u1[0] * t, float(p[1]) + u1[1] * t)
        t2 = (float(p[0]) + u2[0] * t, float(p[1]) + u2[1] * t)
        a0 = math.atan2(t1[1] - cy, t1[0] - cx)
        a1 = math.atan2(t2[1] - cy, t2[0] - cx)
        # 取**劣弧**（走角内那一侧）：|Δ| > π 时反向绕
        d = a1 - a0
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        out = [list(t1)]
        for k in range(1, max(1, int(steps))):
            ang = a0 + d * (float(k) / float(steps))
            out.append([cx + r_eff * math.cos(ang), cy + r_eff * math.sin(ang)])
        out.append(list(t2))
        return out
    except Exception:
        traceback.print_exc()
        return [list(p)]


def _visible_runs(n, visible):
    """把可见边号切成**若干连续段**（按环）

    Returns:
        `[(first_edge, [edge, ...], closed), ...]`

    ## 算法（简单且无特例）
      · 全部边可见 → **一段且 `closed=True`**（首尾相接的闭环）；
      · 否则：一段的**起点** = 那些"前一条边不可见"的可见边
        （`(e-1) % n` 不可见）。从起点沿环往前走，走到下一条不可见就收尾。
      · 这样**自动处理绕环**的情况：`visible=[n-1, 0, 1]` 时只有 `n-1` 是起点
        （`0` 的前一条 `n-1` 可见，所以不是起点），走 `n-1 → 0 → 1` 得到一整段。
        （我第一版用"先分段再合并首尾"的写法，绕环情况会漏掉，已改成上面这个。）
      · 一条可见边都没有 → `[]`（调用方据此不画线）。
    """
    try:
        vis = sorted(set(i for i in (visible or []) if 0 <= i < n))
        if not vis:
            return []
        if len(vis) == n:
            return [(vis[0], vis, True)]
        vis_set = set(vis)
        runs = []
        for e in vis:
            if ((e - 1) % n) in vis_set:
                continue                       # 不是段起点（前一条可见）
            edges = []
            cur = e
            while cur in vis_set and len(edges) < n:
                edges.append(cur)
                cur = (cur + 1) % n
            if edges:
                runs.append((edges[0], edges, False))
        return runs
    except Exception:
        traceback.print_exc()
        return []


def region_outline_paths(region, spots, px_per_data=None):
    """★ 派生的**轮廓折线**（数据坐标）—— 隐藏边处断开 + 相邻可见边处圆角倒角

    Args:
        px_per_data: 1 个数据单位 = 多少**输出图像像素**（把 `corner_radius_px`
                     从像素换算成数据单位）。**None / <=0 / radius<=0 ⇒ 不倒角（尖角）**。
    Returns:
        `list[list[[x, y]]]`；顶点数 <3 / 数据非法 / 一条边都不可见 → **`[]`，绝不抛**

    ★ 这是**呈现专用**：形状与原始多边形不同（少了隐藏边、拐角磨圆），
      所以**绝不能拿它做 spot 判定**（§15.1 的红线）。
    ★ 段端点保持**原始顶点**；闭环段的首尾 = 顶点 0 处两条边上的**切点**
      （切点落在原边上 ⇒ 满足"倒角后首尾仍在原边上"）。
    """
    try:
        pts = [p for p in ((region or {}).get("points") or []) if _norm_point(p)]
        n = len(pts)
        if n < 3:
            return []
        # ★★ v9.1 判定留痕（`_d_spec_select_mode.md` §11 第 4 点）：这里的缺省**故意保持
        #   `DEFAULT_CORNER_RADIUS_PX`(=0)，不跟着做"可见层 12"的分层**，理由（有据）：
        #   · 本函数是**冻结函数**（签名 + 行为一个字不许变）；
        #   · 它拿到的 `region` 在生产链路上**必然已过 `_norm_region`** ⇒ `corner_radius_px`
        #     **键一定存在**，"缺省行"只可能因调用方手搓 dict 才走到：
        #       ① `export_outline_json`（下方 `synthetic = dict(r)`，L1782）的 `regs` 来自
        #          `get_sample_regions(regions_data, sample_id)`，而 `regions_data` 在 bind 里
        #          = `SREG.load_regions(dataset)`（`ui_bind_spatial_region.py` L2308），
        #          `load_regions` 对每个区域跑 `_norm_region`（L2003）；写回侧
        #          `set_sample_regions` 同样归一化（L2047）⇒ 两条入口都带上了该键；
        #       ② 已停用的 `shared_boundary_paths`（L1660，**无生产调用方**，docstring 自述 deprecated）。
        #   ⇒ 可见层的 12 由 `_norm_region` 在**上游**写进区域字典，这里分层只会**重复**一份
        #     判据（且会改掉冻结行为：手搓的 `visible` dict 会突然被倒角）。
        #      ⚠ 若日后 `region_canvas` 直接拿**未归一化**的 dict 调本函数，必须回来看这一行。
        radius_px = _as_float((region or {}).get("corner_radius_px"),
                              DEFAULT_CORNER_RADIUS_PX)
        try:
            ppd = float(px_per_data) if px_per_data is not None else 0.0
        except (TypeError, ValueError):
            ppd = 0.0
        r_data = (radius_px / ppd) if (ppd > 0 and radius_px > 0) else 0.0

        paths = []
        for _first, edges, closed in _visible_runs(n, visible_edge_indices(region, spots)):
            k = len(edges)
            if k < 1:
                continue
            # 该段经过的顶点序号（沿环）：v_j = edges[0] + j，j = 0..k
            path = []
            for j in range(k + 1):
                vid = (edges[0] + j) % n
                is_corner = (0 < j < k) or (closed and j < k)
                if not is_corner:
                    path.append(list(pts[vid]))          # 段端点：保持原顶点
                    continue
                a = pts[(vid - 1) % n]                   # 入边另一端
                b = pts[(vid + 1) % n]                   # 出边另一端
                for q in _fillet(pts[vid], a, b, r_data):
                    path.append(list(q))
            if closed and len(path) >= 2:
                path.append(list(path[0]))               # 闭环：补回首点
            # 去重相邻重复点（尖角/夹紧后可能出现完全重合的点）
            dedup = []
            for q in path:
                if not dedup or (abs(q[0] - dedup[-1][0]) > 1e-12
                                 or abs(q[1] - dedup[-1][1]) > 1e-12):
                    dedup.append(q)
            if len(dedup) >= 2:
                paths.append(dedup)
        return paths
    except Exception:
        traceback.print_exc()
        return []


def label_anchor(region):
    """注释锚点 `(x, y)`：`label_pos` 优先，否则**面积质心**（退化时取顶点均值）

    ★ 为什么不用顶点均值当默认：凹多边形（L 形）的顶点均值可能落在**形状外**，
      标签会飘到区域外看着像别人的标注。面积质心在凸/凹形状里都落在形状内。
    """
    try:
        lp = _norm_label_pos((region or {}).get("label_pos"))
        if lp is not None:
            return (lp[0], lp[1])
        pts = [p for p in ((region or {}).get("points") or []) if _norm_point(p)]
        n = len(pts)
        if n == 0:
            return (0.0, 0.0)
        if n < 3:
            return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)
        area2 = 0.0
        cx = 0.0
        cy = 0.0
        for i in range(n):
            x0, y0 = float(pts[i][0]), float(pts[i][1])
            x1, y1 = float(pts[(i + 1) % n][0]), float(pts[(i + 1) % n][1])
            cross = x0 * y1 - x1 * y0
            area2 += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        if abs(area2) < 1e-9:                        # 退化（共线）→ 顶点均值
            return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)
        return (cx / (3.0 * area2), cy / (3.0 * area2))
    except Exception:
        traceback.print_exc()
        return (0.0, 0.0)


# =============================================================================
# §16.1 成图规则：区域**关系**决定画哪些线（取代 Phase 3 的"逐边隐藏"作为唯一判据）
# =============================================================================
# ★ 判定仍是"原始闭合多边形"（§15.1 的红线）；这里只决定**呈现**画哪几段。
#   `edge_override` 仍然生效（用户手动显隐优先），叠加在四种情形之上。

def _poly_area(points):
    """多边形**有向**面积（用于"谁包含谁"的兜底比较）；退化 → 0"""
    try:
        pts = points or []
        n = len(pts)
        if n < 3:
            return 0.0
        s = 0.0
        for i in range(n):
            x0, y0 = float(pts[i][0]), float(pts[i][1])
            x1, y1 = float(pts[(i + 1) % n][0]), float(pts[(i + 1) % n][1])
            s += x0 * y1 - x1 * y0
        return s / 2.0
    except Exception:
        return 0.0


def polygon_area(points):
    """★ v9.1 **公开薄包装**：多边形**面积**（= |`_poly_area`|，单位 = **数据单位²**）

    ## 谁在用（为什么必须公开）
      · 画布 `region_canvas._hit_region_smallest`（W1）：选择模式"区域内"这一步改成
        **重合时面积最小者优先** —— `_d_spec_select_mode.md` §10.1 / v9.1 用户原话
        「小区域是优先被选中的，然后才是大区域（我指的是两者重合时）」。
        典型场景：一个**小区域**整个被一圈**隐形区域（mask）**包住，现状点进去只会选中 mask。
      · W1 用 `getattr(_SREG, "polygon_area", None)` 懒加载 + **自带兜底**
        （拿不到就退回 `_hit_region` 的老语义并留痕）⇒ 本函数缺失也不致命，签名可自由演进时告知 W1。

    ## 语义与实现
      · **直接委托**本文件既有的私有 `_poly_area(points)`（几何算法**只有一份**，见下）；
      · 取 `abs()`：`_poly_area` 返回的是**有向**面积（§"谁包含谁"的比较用），而本函数的用途是
        "**谁更小**" —— 一个**顺时针的大区域**在有向面积下是**大负数**，直接比大小会把它
        误判成"最小" ⇒ 用户的"小区域优先"反而失效。所以公开接口给**大小**，不给绕向。
      · ⛔ **不改 `_poly_area` 的行为**（它是冻结函数，`region_relations` 的嵌套判定在用）。

    ## Returns
      `float`：面积（**数据单位²**，≥ 0；退化/共线多边形 = 0.0）。
      `points` 为 `None` / 非序列（`int`/`dict`/`str`/`bytes`）/ 有点非法 / 点数 < 3
      ⇒ **`0.0`**，并且 `traceback.print_exc()` + `_geo_warn` **留痕**；**绝不抛**给画布。
      （`_poly_area` 自己会**静默**吞异常返回 0.0；本包装先做参数体检 ⇒ "为什么是 0" 有栈可查。）
    """
    try:
        if points is None or isinstance(points, (str, bytes, bytearray, dict)):
            raise TypeError("points 必须是点序列，实际 %s" % type(points).__name__)
        try:
            pts = list(points)                       # 非序列（int / 生成器以外的标量）在这里抛
        except TypeError:
            raise TypeError("points 不可迭代，实际 %s" % type(points).__name__)
        if len(pts) < 3:
            raise ValueError("点数 %d < 3，退化多边形没有面积" % len(pts))
        # 点体检复用本文件既有的 `_norm_point`（与 `_norm_region` / `vertices_at` 同一口径，
        # 幂等、不抛）⇒ **只做校验、不替换原点**，`_poly_area` 拿到的还是调用方给的点。
        for _i, _p in enumerate(pts):
            if _norm_point(_p) is None:
                raise ValueError("第 %d 个点非法（需要 [x, y] 两个数）：%r" % (_i, _p))
        return abs(_poly_area(pts))
    except Exception:
        traceback.print_exc()                        # 房规：**绝不静默**
        _geo_warn("[spatial_region] polygon_area 坏输入 -> 返回 0.0（不抛，"
                  "points 类型=%s）" % type(points).__name__)
        return 0.0


def _seg_cross(a1, a2, b1, b2, eps=1e-9):
    """两条线段是否**真交叉**（不含共线重叠；共线重叠由"中点在边上"那条判据覆盖）"""
    try:
        def cross(o, p, q):
            return ((float(p[0]) - float(o[0])) * (float(q[1]) - float(o[1]))
                    - (float(p[1]) - float(o[1])) * (float(q[0]) - float(o[0])))
        d1 = cross(b1, b2, a1)
        d2 = cross(b1, b2, a2)
        d3 = cross(a1, a2, b1)
        d4 = cross(a1, a2, b2)
        return ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
               ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps))
    except Exception:
        return False


def _poly_contains(outer, inner):
    """`inner` 的**每个顶点**都在 `outer` 内（含边上）⇒ 视为被包含

    ★ 用"顶点全在内"而不是"面积差"：两者结合足够稳，而且**不需要多边形布尔运算库**
      （本模块纪律：不引新依赖）。凹多边形的极端互扣图形可能被误判为"包含"，
      但那种图形在画布上手工画不出来，取舍划算。
    """
    try:
        ipts = (inner or {}).get("points") or []
        opts = (outer or {}).get("points") or []
        if len(ipts) < 3 or len(opts) < 3:
            return False
        for p in ipts:
            if not point_in_polygon(float(p[0]), float(p[1]), opts):
                return False
        return True
    except Exception:
        traceback.print_exc()
        return False


def _poly_touch_or_overlap(a, b):
    """两区域是否**相交或相接**（有共享边界）

    四条判据任一成立即可（从便宜到贵）：
      ① a 有顶点落在 b 内（含边上）；② b 有顶点落在 a 内；
      ③ 有一对边**真交叉**；④ a 边中点落在 b 的某条边上（**"相接"最常见的形态**：
         两个矩形并排贴着、共享一条边，此时端点都不在对方内部）。
    """
    try:
        ap = (a or {}).get("points") or []
        bp = (b or {}).get("points") or []
        na, nb = len(ap), len(bp)
        if na < 3 or nb < 3:
            return False
        for p in ap:
            if point_in_polygon(float(p[0]), float(p[1]), bp):
                return True
        for p in bp:
            if point_in_polygon(float(p[0]), float(p[1]), ap):
                return True
        for i in range(na):
            a1, a2 = ap[i], ap[(i + 1) % na]
            ma = _edge_midpoint(ap, i)
            for j in range(nb):
                b1, b2 = bp[j], bp[(j + 1) % nb]
                if _seg_cross(a1, a2, b1, b2):
                    return True
                if ma is not None and _on_segment(ma[0], ma[1],
                                                  float(b1[0]), float(b1[1]),
                                                  float(b2[0]), float(b2[1])):
                    return True
        return False
    except Exception:
        traceback.print_exc()
        return False


def _shared_edges(i, j, regions):
    """`i` 的**共享边界边号**（该边中点落在 `j` 内/边上）

    · **相接**（共享一条边）→ 那条边的中点正好落在 j 的边上 ⇒ `point_in_polygon`
      按"边上算在内"（§13 冻结语义）返回 True ⇒ 命中；
    · **相交**（重叠一块）→ 落在对方内部的那些边 ⇒ 命中。
    ⇒ 一条判据同时覆盖"相交"和"相接"，**不写两套**。
    """
    try:
        regs = regions or []
        if not (0 <= i < len(regs)) or not (0 <= j < len(regs)):
            return set()
        pts = (regs[i] or {}).get("points") or []
        jpts = (regs[j] or {}).get("points") or []
        n = len(pts)
        if n < 3 or len(jpts) < 3:
            return set()
        out = set()
        for e in range(n):
            mid = _edge_midpoint(pts, e)
            if mid is None:
                continue
            if point_in_polygon(mid[0], mid[1], jpts):
                out.add(e)
        return out
    except Exception:
        traceback.print_exc()
        return set()


def _apply_override_to_draw(region, spec, n):
    """把 `draw` 规格（`"all"` / `[边号]` / `[]`）叠加 `edge_override` 后再规格化

    ★ `edge_override` **优先于**自动判定（§16.1 明文）：`show` 加回来、`hide` 去掉。
      叠加后若恰好等于"全部边" ⇒ 规格化成 `"all"`（下游少一层判断）。
    """
    try:
        if spec == "all":
            s = set(range(n))
        elif isinstance(spec, (list, tuple, set)):
            s = set(int(x) for x in spec
                    if isinstance(x, (int, float)) and 0 <= int(x) < n)
        else:
            s = set()
        ov = _norm_edge_override((region or {}).get("edge_override"))
        for e, v in ov.items():
            if not (0 <= e < n):
                continue
            if v == "show":
                s.add(e)
            elif v == "hide":
                s.discard(e)
        if s == set(range(n)):
            return "all"
        return sorted(s)
    except Exception:
        traceback.print_exc()
        return spec


# =============================================================================
# ★ 隐形选区（mask）—— 用户裁定：**出图虚线可见性由用户手画的隐形选区决定**
# -----------------------------------------------------------------------------
# 用户原话要点（协调者转述）：
#   ① 新增「隐形选区」：也是选区域、可以选多个，它**是隐形的**；它选中的区域内
#      会在最终出图时呈现那些虚线，区域外的虚线被隐藏；
#   ② 粒度 = **相交即整条**；
#   ③ **一个隐形选区都没有时 = 按老样子把所有区域虚线都画**；
#   ④ **删掉**原来的自动规则（`nested`/`adjacent`/`isolated` → `draw` 规格、
#      "出界不画"那套）；**保留** spot 归属"后画赢"、圆角 `corner_radius_px`、
#      手工 `edge_override`。
# ⇒ 判定只有**一处**：本文件的 `visible_region_indices()`（W3 侧"只画不判断"）。
# =============================================================================
def _point_strictly_inside(x, y, points):
    """点是否**严格落在**多边形内部（落在边/顶点上 → `False`）

    ★ 为什么不能直接用 `point_in_polygon`：契约（§13 冻结）规定"**点在边上算作在内**"，
      而 mask 的重叠判据要求"**仅共边（面积 0）不算重叠**"（协调者冻结）
      ⇒ 必须先显式排掉"落在边上"，再谈"内部"。
    """
    try:
        if not point_in_polygon(x, y, points):
            return False
        pts = points or []
        n = len(pts)
        for i in range(n):
            ax, ay = float(pts[i][0]), float(pts[i][1])
            bx, by = float(pts[(i + 1) % n][0]), float(pts[(i + 1) % n][1])
            if _on_segment(x, y, ax, ay, bx, by):
                return False
        return True
    except Exception:
        traceback.print_exc()
        return False


def _polys_overlap_area_positive(a, b):
    """两个闭合多边形是否**面积重叠 > 0**（仅共边/共点接触 → `False`）

    ## 判据（协调者冻结的"面积重叠 > 0，或互相包含"，逐条实现）
      ① `a` 有顶点**严格落在** `b` 内部，或反之（边上不算）；
      ② 有一对边**真交叉**（`_seg_cross`：内部相交；端点接触、共线重叠都不算）；
      ③ **任一边的中点严格落在**对方内部 —— ★ 我补的（见下）；
      ④ **互相包含**（含**完全重合**）：`_poly_contains` 任一方向成立。
      ⑤ 其余 → `False`（**仅共一条边/一个点 = 面积 0，不算重叠**）。

    ## 为什么必须有 ③ 和 ④（不是过度设计，是实打实的漏判）
      · 缺 ④：**mask 与区域完全重合**时，顶点全落在对方**边上** ⇒ ①（严格内部）
        与 ②（真交叉）都不成立，但重叠面积是 100% ⇒ 选区会"选不中"它盖住的区域。
      · 缺 ③：两个**同高、水平错开**的矩形（A: x∈[0,50]、M: x∈[25,75]、y 相同）
        ⇒ A 的顶点 (50,0)/(50,50) 落在 M 的**边上**、M 的 (25,0)/(25,50) 落在 A 的边上，
        没有顶点严格在内部；边之间只在中点以外"端点相接"（A 右边是竖线、M 上下边是横线）
        ⇒ ①② 全不成立，而重叠面积 = 25×50 > 0 ⇒ **A 会被判"不重叠"而丢掉虚线**。
        ③ 取"边中点严格在对方内部"正好覆盖这类"边贴着/穿过对方内部但没有顶点在内"的图形。
      · ③ 的必要性还在于：若某条边**穿过**对方内部，它必然在进出处与对方边界**真交叉**
        （② 已覆盖）；所以 ③ 只需补"边完全在对方内部或沿边界的弦"这一类。

    ⚠ **已知局限**：用几何图元而不是多边形布尔运算（本模块纪律：不引新依赖）。
      极端的凹多边形互相扣住、且所有顶点与边中点都在外部的病态图形仍可能漏判 ——
      那种图形在画布上用鼠标画不出来，取舍划算（与 `_poly_contains` 的取舍一致）。
    """
    try:
        apts = [p for p in ((a or {}).get("points") or []) if _norm_point(p)]
        bpts = [p for p in ((b or {}).get("points") or []) if _norm_point(p)]
        na, nb = len(apts), len(bpts)
        if na < 3 or nb < 3:
            return False
        # ---- ① 顶点严格落在对方内部 ----
        for p in apts:
            if _point_strictly_inside(float(p[0]), float(p[1]), bpts):
                return True
        for p in bpts:
            if _point_strictly_inside(float(p[0]), float(p[1]), apts):
                return True
        # ---- ② 有一对边真交叉 ----
        for i in range(na):
            a1, a2 = apts[i], apts[(i + 1) % na]
            for j in range(nb):
                b1, b2 = bpts[j], bpts[(j + 1) % nb]
                if _seg_cross(a1, a2, b1, b2):
                    return True
        # ---- ③ 边中点严格落在对方内部 ----
        for pts_src, pts_dst in ((apts, bpts), (bpts, apts)):
            m = len(pts_src)
            for i in range(m):
                p1, p2 = pts_src[i], pts_src[(i + 1) % m]
                mx = (float(p1[0]) + float(p2[0])) / 2.0
                my = (float(p1[1]) + float(p2[1])) / 2.0
                if _point_strictly_inside(mx, my, pts_dst):
                    return True
        # ---- ④ 互相包含（含完全重合）----
        if _poly_contains(a, b) or _poly_contains(b, a):
            return True
        return False
    except Exception:
        traceback.print_exc()
        return False


def is_layer_region(r):
    """该区域是不是**范围层多边形**（`mask` 隐形区域 / `visible` 可见区域）

    ★ 范围层 = 用户额外画的一层"罩子"（`_norm_region` 把两个字段都归一化成严格布尔，
      所以这里直接取即可；仍走 `_norm_flag` 以容错外部直接构造的 dict）。
    ★★ **v9.3 起两类范围层的语义不再相同**（用户裁定「可见区域就是我的标注单元」）：
      · `mask`（隐形区域）：真正的"罩子" —— **自己永不出图、永不计已画、永不抢 spot 归属**；
      · `visible`（可见区域）：**参与命名与注释归类、计入"已画"、会抢 spot 归属、
        并会出现在成图里（带名字）**；它同时**仍然**决定"哪些普通区域入选成图"。
      ⇒ 于是"要不要排除这个区域"分两种问法，别混：
        · 画布样式 / 列表行标记 / 可见范围过滤（"它是不是范围层"）⇒ 用**本函数**；
        · 命名与注释归类（"它参不参与"）⇒ 用 **`is_anno_blocked_region`**（只认 `mask`）。
    ⛔ 不要再各写一份 `r.get("mask")` —— 本轮就是"mask 排除了、visible 忘了排除"
      这类漏一处就出错的典型场景。
    """
    try:
        return bool(isinstance(r, dict) and (_norm_flag(r.get("mask"))
                                             or _norm_flag(r.get("visible"))))
    except Exception:
        return False


def is_anno_blocked_region(r):
    """该区域是不是**不参与命名与注释归类**的区域（v9.3 冻结判据：**只**看 `mask` 隐形区域）

    Returns:
        bool —— `mask` 严格布尔为真 ⇒ True；其余（含 `visible` 可见区域、普通区域、
               非 dict / 坏值 / 异常）⇒ False（**绝不抛**）

    ## ① 与 `is_layer_region` 的区别（★ 两者**不是**同一件事，别混用）
      · `is_layer_region(r)`（L1237，紧邻本函数之上）= "这是不是**范围层**"= `mask` 隐形区域 **或** `visible`
        可见区域。它回答的是"这是不是一层罩子"，仍被 `layer_polygon_indices` /
        `covered_region_indices` 等**范围层机制**使用；**本函数的出现不改变它一个字节**。
      · `is_anno_blocked_region(r)` = "这个区域**阻不阻断命名与注释归类**"= **只有** `mask`。
        ⇒ `visible`（可见区域）**不再受阻**：用户裁定「可见区域」就是他的**标注单元** ——
        每个可见区域要能**命名**、注释要能**映射到 spot / 出图**。

    ## ② v9.3 沿革（用户报 bug 后的**语义收窄**；**不许静默改口径**）
      用户当初的原话（只针对隐形区域）：
        「隐形区域我们不做命名或者注释归类处理，这个只是用来框定显示区域的」
      —— 用户**只**说了隐形区域。我方曾把这条**擅自扩大**成 `is_layer_region`
      （`mask` 隐形 **+** `visible` 可见），于是可见区域也被拒于命名/归类之外；
      真实数据里可见区域往往画在最后（后画优先 ⇒ 在画布上一点就选中它）
      ⇒ 用户实测报出「区域分组的下拉框和选择框点不动，所以也并不能映射到可见区域的
      每个区域上对应的注释」。用户当面裁定：**「可见区域」就是他的标注单元**。
      ⇒ 本轮把"不参与注释归类"**收窄回只挡 `mask`**，并让可见区域在成图里**真正被画出来
      （带名字）**（见 `export_outline_json`）—— 否则图例会指向一个看不见的区域。
      ⚠ 与 W2 `ui_bind_spatial_region.py` 的命名守卫 `_reject_anno_on_layer`
        （判据 `_is_anno_blocked_region`）**同名同义**：两处口径必须一致。

    ## ③ 谁在用（归类链路四处 + W2 命名守卫）
      · `assign_labels`（逐 spot 标签：可见区域**会**抢 spot 归属 ⇒ 这才是"映射"）
      · `count_by_region`（区域计数：可见区域**会**出现在 `counts` 里）
      · `_effective_regions`（⇒ `group_graphed_labels` 采纳可见区域的 `anno_label`）
      · `painted_region_count`（"已画 ≥1 区"计数：**只画了隐形区域 = 未画**；
        只画了可见区域 ⇒ **算已画**，否则该样本被 `_override_state` 判 `no_regions`）
      · W2：`ui_bind_spatial_region.py::_reject_anno_on_layer`（命名写入守卫）

    ★ **严格布尔**：与 `_norm_region` 里 `"mask": _norm_flag(...)`（L368）**同一套** `_norm_flag`
      ⇒ `"false"` / `"0"` / `0` / 缺字段 / 任意白名单外的值一律 False；非 dict ⇒ False。
    ★ **绝不抛**：`_norm_flag` 自身全函数（白名单外一律 False），本函数仍保留 `except`
      兜底并**留痕**（房规"不许静默"：`traceback.print_exc()` + `_geo_warn`）。
    """
    try:
        return bool(isinstance(r, dict) and _norm_flag(r.get("mask")))
    except Exception:
        # ★ 房规：**不许静默** —— 真调用栈 + 一条中文日志，然后按"不阻断"处理
        traceback.print_exc()
        _geo_warn("[spatial_region] is_anno_blocked_region 判定异常 -> 按 False 处理（不阻断命名）")
        return False


def layer_polygon_indices(regions):
    """**范围层多边形**的索引（`mask or visible`；`invalid` 的不算）"""
    try:
        return [i for i, r in enumerate(list(regions or []))
                if isinstance(r, dict) and not r.get("invalid") and is_layer_region(r)]
    except Exception:
        traceback.print_exc()
        return []


def _layer_flag_indices(regions, flag):
    """某一层（`flag ∈ {"visible","mask"}`）的多边形索引（`invalid` 的不算）"""
    try:
        return [i for i, r in enumerate(list(regions or []))
                if isinstance(r, dict) and not r.get("invalid") and _norm_flag(r.get(flag))]
    except Exception:
        traceback.print_exc()
        return []


def mask_polygons(regions):
    """该样本**所有隐形区域多边形**的点列表（`mask=True` 且未 `invalid`）

    Returns:
        `list[list[[x, y]]]`；没有 ⇒ `[]`（**绝不抛**）

    ★ v4：隐形区域的角色从"决定整条区域画不画"改成**只对成图做逐段裁剪**
      （见 `clip_polyline_to_mask` 与 `visible_region_indices` 的 docstring）。
    """
    out = []
    try:
        for r in list(regions or []):
            if not isinstance(r, dict) or r.get("invalid") or not _norm_flag(r.get("mask")):
                continue
            pts = [p for p in ((r.get("points") or [])) if _norm_point(p)]
            if len(pts) >= 3:
                out.append([[float(p[0]), float(p[1])] for p in pts])
        return out
    except Exception:
        traceback.print_exc()
        return out


def _lerp_pt(a, b, t):
    """边 `a→b` 上参数 `t` 处的点（**精确插值**，不是只取原顶点）"""
    return [float(a[0]) + (float(b[0]) - float(a[0])) * t,
            float(a[1]) + (float(b[1]) - float(a[1])) * t]


def _pt_eq(a, b, eps=1e-9):
    try:
        return abs(float(a[0]) - float(b[0])) <= eps and abs(float(a[1]) - float(b[1])) <= eps
    except Exception:
        return False


def _finite_pt(p):
    """点是否**两个坐标都是有限数**（`NaN` / `±Inf` / `None` / 非数 → False）

    ★★ 这是 W3 的**硬要求**（`spatial_region_render.R:311/314`）：R 会把"点数 <2 或
      含 NA"的 `segments` 条目**静默丢弃**（只计入 `segments_skipped`，不报错）
      ⇒ 我们这边必须保证**发出去的每一段都是 ≥2 个有限点**，
      否则"两边同时少"会造成**假绿**（协调者会断言 `n_segments == len(segments)`
      且 `segments_skipped == 0`）。
    """
    try:
        return (isinstance(p, (list, tuple)) and len(p) >= 2
                and math.isfinite(float(p[0])) and math.isfinite(float(p[1])))
    except Exception:
        return False


def _finite_pts(seq):
    """把点序列规范成 `[[float, float], ...]`，**丢弃**任何非有限点"""
    out = []
    for p in (seq or []):
        np_ = _norm_point(p)
        if np_ is None:
            continue
        try:
            x, y = float(np_[0]), float(np_[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            out.append([x, y])
    return out


def _clip_edge_params(p1, p2, mask_polys, eps=1e-9):
    """边 `p1→p2` 上**与 mask 边界相交**的所有参数 `t ∈ (0,1)`（升序、去重）

    · 真交叉（`_seg_cross`）→ 解线性方程求 t；
    · **共线重叠**那种"没有单点交点"的情形：把落在该边上的 mask 顶点投影成 t
      —— 少了这一条，两条共线的边重叠时切不出分界点。
    """
    ts = []
    try:
        dx = float(p2[0]) - float(p1[0])
        dy = float(p2[1]) - float(p1[1])
        l2 = dx * dx + dy * dy
        if l2 <= eps:
            return ts
        for poly in (mask_polys or []):
            n = len(poly)
            if n < 3:
                continue
            for i in range(n):
                q1, q2 = poly[i], poly[(i + 1) % n]
                if _seg_cross(p1, p2, q1, q2):
                    ex = float(q2[0]) - float(q1[0])
                    ey = float(q2[1]) - float(q1[1])
                    den = dx * ey - dy * ex
                    if abs(den) > eps:
                        ts.append(((float(q1[0]) - float(p1[0])) * ey
                                   - (float(q1[1]) - float(p1[1])) * ex) / den)
                else:
                    for q in (q1, q2):
                        if _on_segment(float(q[0]), float(q[1]),
                                       float(p1[0]), float(p1[1]),
                                       float(p2[0]), float(p2[1])):
                            ts.append(((float(q[0]) - float(p1[0])) * dx
                                       + (float(q[1]) - float(p1[1])) * dy) / l2)
        out = []
        for t in sorted(ts):
            if eps < t < 1.0 - eps and (not out or abs(t - out[-1]) > 1e-9):
                out.append(t)
        return out
    except Exception:
        traceback.print_exc()
        return ts


def clip_polyline_to_mask(points, mask_polys, closed=True):
    """★ 把折线按 `mask_polys` 的**并集**裁剪，**只保留落在并集内部**的段

    ## 用户原话（v4 裁定，照抄）
    > 「不一定是整条，一条虚线边比方说它的下半部分在隐形区域内，那么我们就单纯画它的
    > 下半部分在区域内的那部分，上半部分出界的不画」

    ## 语义
      · 逐边切开：求该边与所有 mask 边的交点参数 `t`（**精确插值**，不是只保留原顶点），
        按 `t` 把边切成子区间；**取每个子区间的中点**做"是否在并集内"的
        `point_in_polygon` 测试，保留命中的子区间；
      · 再把**首尾相接的相邻命中子区间合并**成一段（所以"整条都在里面"只会返回 1 段，
        且点与输入一致）；
      · **`mask_polys` 为空 ⇒ 原样返回 `[points]`**（＝没画隐形区域就不裁剪）。
      · `closed=True` 时最后一条边是 `p[-1]→p[0]`；首尾相接的闭环段会**回卷合并**。
        ⚠ **点数 <3 时一律按开放折线处理**（2 点构不成闭合多边形，否则会凭空多一个收尾点）；
        **零长边跳过、连续重复点去掉**（闭合折线首尾重复时必然出现）。

    Args:
        points: `[[x, y], ...]`（数据坐标）
        mask_polys: `mask_polygons()` 的返回（`list[list[[x,y]]]`）
        closed: 折线是否闭合（最后一条边 `p[-1]→p[0]`）
    Returns:
        `list[list[[x, y]]]`；**每一段都 ≥2 点且坐标全是有限数**（单点/含 `NaN`/`Inf` 的段一律丢弃）

    ## 退化输入的处理（我选的口径 + 理由）
      · `points` 不是列表 / 有效点数 `<2`（含坐标非数、`NaN`/`Inf`）⇒ 返回 **`[]`**；
      · mask 多边形点数 `<3`（或含非有限点）⇒ **忽略它**；若因此有效 mask 为空 ⇒ 走
        "不裁剪"那条（把**已过滤掉非有限点**的折线原样返回一段）。
      **理由（v4 修订）**：协调者转来 W3 的硬要求 —— 送出去的每一段必须 ≥2 个有限点，
      否则 R 会**静默丢弃**（只计 `segments_skipped`），造成"两边同时少"的**假绿**。
      ⇒ 原来那条"点 <2 就原样返回"会让**含 NaN 的输入原样流到 R**，与硬要求冲突；
        现在一律**先过滤成有限点**，过滤后不足 2 点就返回 `[]`（宁可不出这段）。
        `mask_polys` 为空时仍然是"**不裁剪、原样返回一段**"，只是"原样"指的是
        **过滤后的有限点**。
    ★ 纯函数：无 I/O、不读全局、**绝不抛**（异常时回退"过滤后原样返回 / `[]`"）。
    """
    try:
        if not isinstance(points, (list, tuple)):
            return []
        pts = _finite_pts(points)
        if len(pts) < 2:
            return []                          # 不足 2 个有限点 ⇒ 不可能满足输出约束
        polys = []
        for poly in (mask_polys or []):
            q = _finite_pts(poly)
            if len(q) >= 3:
                polys.append(q)
        if not polys:
            return [pts]                       # 没画（或没有有效）隐形区域 ⇒ 不裁剪
        n = len(pts)
        # ⚠ **必须在算 `edge_idx` 之前**判定"少于 3 点按开放折线处理"：
        #   第一次我把这行放在 `edge_idx` 之后 ⇒ 2 点输入仍按闭合算（两条边来回走）
        #   ⇒ 输出凭空多一个收尾点（探针第 ② 条当场抓到）。
        if closed and n < 3:
            closed = False
        edge_idx = list(range(n)) if closed else list(range(n - 1))
        # ---- ① 逐边切成子区间，用**中点**判是否在并集内 ----
        pieces = []
        for i in edge_idx:
            a, b = pts[i], pts[(i + 1) % n]
            if _pt_eq(a, b):
                continue                       # 零长边（闭合折线首尾重复时会出现）跳过
            cuts = [0.0] + _clip_edge_params(a, b, polys) + [1.0]
            for k in range(len(cuts) - 1):
                t0, t1 = cuts[k], cuts[k + 1]
                if t1 - t0 <= 1e-12:
                    continue
                p0 = _lerp_pt(a, b, t0)
                p1 = _lerp_pt(a, b, t1)
                pm = _lerp_pt(a, b, (t0 + t1) / 2.0)
                hit = False
                for poly in polys:
                    if point_in_polygon(pm[0], pm[1], poly):
                        hit = True
                        break
                pieces.append((p0, p1, hit))
        # ---- ② 合并首尾相接的命中子区间（同时**去掉连续重复点**）----
        runs = []
        for p0, p1, hit in pieces:
            if not hit or _pt_eq(p0, p1):
                continue
            if runs and _pt_eq(runs[-1][-1], p0):
                if not _pt_eq(runs[-1][-1], p1):
                    runs[-1].append(p1)
            else:
                runs.append([p0, p1])
        # ---- ③ 闭环回卷：末段终点 == 首段起点 ⇒ 合成一段 ----
        if closed and len(runs) >= 2 and _pt_eq(runs[-1][-1], runs[0][0]):
            runs[0] = runs[-1] + runs[0][1:]
            runs.pop()
        # ---- ④ 出口再验一遍：**≥2 点 且 全为有限数**（W3 的硬要求，见 docstring）----
        out = []
        for r in runs:
            rr = _finite_pts(r)
            if len(rr) >= 2:
                out.append(rr)
        return out
    except Exception:
        traceback.print_exc()
        try:
            rr = _finite_pts(points)
            return [rr] if len(rr) >= 2 else []
        except Exception:
            return []


def covered_region_indices(regions, flag, spots=None):
    """被 **`flag` 层**（`"visible"` / `"mask"`）任一多边形**罩住**的普通区域索引

    ⚠⚠ **v4 起 `flag="mask"` 不再构成"成图门槛"**（2026-09 用户裁定）：
      隐形区域改成**逐段裁剪**（`clip_polyline_to_mask`），
      `visible_region_indices()` **不再**调用 `covered_region_indices(regions, "mask")`。
      本函数保留 `"mask"` 分支**只作参考 / 旧调用**（以及"重叠参考"这种诊断用途）。
      —— 画布门槛仍然用它（`flag="visible"`）。

    Args:
        regions: 归一化后的区域列表（顺序 = 绘制顺序）
        flag: `"visible"`（可见区域层，**在用**）或 `"mask"`（隐形区域层，**仅参考**）
        spots: **保留但当前不用**（签名稳定，与另两个门槛函数同形）
    Returns:
        `list[int]`（升序，索引相对于传入的 `regions`）；**范围层自身永不在返回值里**

    ★★ **该层一个多边形都没有 ⇒ 返回全部普通区域**（"没有范围层就不过滤"）：
      这是**向后兼容的默认**（§16.1.1 冻结的"默认全画"）—— 用户刚进页面、
      两层都没画时，**必须照旧把所有区域虚线都画出来，而不是给一张空白图**。
    ★ 重叠判据（协调者冻结）：「面积重叠 > 0，或互相包含」；**仅边界接触（面积 0）不算**，
      实现见 `_polys_overlap_area_positive`（含我补的"错位重合/完全重合"两条边界情形）。
    ★ 粒度 = **相交即整条**（区域级；v4 的逐段粒度在 `clip_polyline_to_mask` 里）。
    """
    try:
        src = list(regions or [])
        layers = _layer_flag_indices(src, flag)
        out = []
        for i, r in enumerate(src):
            if not isinstance(r, dict) or r.get("invalid") or is_layer_region(r):
                continue                      # 无效区域 / 范围层自己：永不出图
            if not layers:
                out.append(i)                 # ★ 该层为空 ⇒ 不过滤（默认全画）
                continue
            for li in layers:
                if _polys_overlap_area_positive(r, src[li]):
                    out.append(i)             # 相交即整条
                    break
        return out
    except Exception:
        traceback.print_exc()
        return []


def canvas_visible_region_indices(regions, spots=None):
    """★ **画布门槛**：画布上该**画虚线边界**的普通区域索引

    = 被「**可见区域**」层罩住的区域（`covered_region_indices(regions, "visible")`）。
    ★ 该层为空 ⇒ 全部普通区域（默认全画）。
    ★ 画布**只看可见区域层**，**不看**隐形区域层 —— 隐形区域决定的是"能不能出现在成图里"，
      不是"画布上画不画"（用户原话：成图 = 再与隐形区域取交集）。
    """
    return covered_region_indices(regions, "visible", spots)


def visible_region_indices(regions, spots=None):
    """★ **成图候选集**：最终出图时**要考虑**的普通区域索引（导出侧唯一调用点）

    ## ★★ v4（2026-09 用户新裁定）：隐形区域**不再决定整条区域画不画**
      用户原话（照抄）：
      > 「不一定是整条，一条虚线边比方说它的下半部分在隐形区域内，那么我们就单纯画它的
      > 下半部分在区域内的那部分，上半部分出界的不画」

      ⇒ v4 语义：**成图候选集 = `canvas_visible_region_indices(regions)`**
        （即"被可见区域罩住"那一套；可见层没画 ⇒ 全部）。
        **mask 只在导出时逐段裁剪**（`clip_polyline_to_mask`），
        **不再**做原来的区域级 `∩ covered_region_indices(regions, "mask")`
        —— 那条会把"没被 mask 罩住"的整条区域整个丢掉，与用户要的"画里面那一半"不符。
      ⇒ 这个口径**只作用于成图**：画布仍然只看「可见区域」层（用户明确）。

    ## 默认行为（★ **两层都没画 ⇒ 照旧全画**，向后兼容）
      `canvas_visible_region_indices` 在"可见层为空"时返回**全部**普通区域
      ⇒ 用户刚进页面、两层都没画时，**照旧把所有区域虚线都画出来，绝不是空白图**。

    Args:
        regions: 归一化后的区域列表（顺序 = 绘制顺序）
        spots: **保留但当前不用**（签名稳定；将来若要"只按 spot 判定"可直接用）
    Returns:
        `list[int]`（升序，索引相对于传入的 `regions`）；
        **范围层自身（`mask` 或 `visible`）永不在返回值里**；`invalid` 的也不出现。
    ★ 注意：返回值是**候选**集。—— 候选区域经 `clip_polyline_to_mask` 裁剪后可能
      **一段都不剩**（此时该区域不产生任何 `segment`），这正是用户要的"出界的不画"。
    """
    try:
        return canvas_visible_region_indices(regions, spots)
    except Exception:
        traceback.print_exc()
        return []


def region_relations(regions, spots=None):
    """⛔ **已停用（deprecated）**：自动关系规则 —— 被用户裁定的"隐形选区"取代

    ★ 2026-09 用户裁定 ④：**删掉**原 ③ 的自动规则（`nested`/`adjacent`/`isolated`
      → `draw` 规格、"出界不画"那套），改成**用户手画的隐形选区**决定虚线可见性
      ⇒ 现由 `visible_region_indices()` 负责，`export_outline_json` **不再调用本函数**。
    ★ **函数暂时保留、不删**（协调者要求"先别删，避免打断别人"）：
      当前仍引用它的有 `docs/features/spatial_m2m3_contract.md`（§16.1/§16.2 的接口表）
      与协调者的探针脚本 `_dsh_r6_goalcheck.py`；生产代码里**只有本文件的历史注释**。
      W3 的 `spatial_region_render.R:921` 只在一句注释里提到本函数名，**不调用**。
      ⇒ 等协调者裁定"契约同步改完"后再整段删除（连同 `shared_boundary_paths`）。
    ★ 下面的原说明保留，仅为追溯旧语义。

    ---------------------------------------------------------------------------
    ★ §16.1/§16.2 **（旧）冻结**：逐区域判定"该画哪些线"

    Args:
        regions: 归一化后的区域列表（顺序 = 绘制顺序）
        spots: 该样本的 spot 行；**只有"孤立区域是否出界"这一条需要它**。
               `None` ⇒ `auto_hidden_rule` 返回空集（无 spot 无从判断出界）
               ⇒ 孤立区域一律照画（**偏保守：宁可多画，也不凭空调"不画"**）。

    Returns:
        `{"nested": [(inner_idx, outer_idx), ...],
          "adjacent": [(i, j), ...],
          "isolated": [idx, ...],
          "draw": {idx: [边号] | "all" | []}}`

    ## 规则（§16.1 的表，逐条实现）
      · **嵌套**（R 被 P 完全包含）→ R 的**全部边**；P 中**落在 R 内**的边不画；
      · **相交/相接** → 只画 `R∩Q` 的**共享边界段**，各自单独的边不画；
      · **孤立且不出界** → 全部边；
      · **孤立且出界** → **不画**（`[]`）。★ 出界粒度是**整区域**：
        只要有一条边出界，整个孤立区域就不画（**不再逐边隐藏** —— 这是 Phase 4 的改动，
        依据：用户原话"出界的说明范围很大，这种我们就不画"）；
      · 最后统一叠加 `edge_override`（用户手动显隐优先）。

    ★ `spots` 是**可选补充**：契约冻的是 `region_relations(regions)`，
      单参数调用照样能用（"出界"那条退化为"不出界"）。
    """
    result = {"nested": [], "adjacent": [], "isolated": [], "draw": {}}
    try:
        regs = [r for r in (regions or [])
                if isinstance(r, dict) and not r.get("invalid")]
        n = len(regs)
        if n == 0:
            return result
        nested = []
        adjacent = []
        for i in range(n):
            for j in range(i + 1, n):
                ri, rj = regs[i], regs[j]
                ai, aj = abs(_poly_area(ri.get("points"))), abs(_poly_area(rj.get("points")))
                if _poly_contains(ri, rj) and ai > aj + 1e-9:
                    nested.append((j, i))          # j 在里面，i 在外面
                elif _poly_contains(rj, ri) and aj > ai + 1e-9:
                    nested.append((i, j))
                elif _poly_touch_or_overlap(ri, rj):
                    adjacent.append((i, j))
        nested_idx = set()
        for a, b in nested:
            nested_idx.add(a)
            nested_idx.add(b)
        adj_idx = set()
        for a, b in adjacent:
            adj_idx.add(a)
            adj_idx.add(b)
        isolated = [i for i in range(n) if i not in nested_idx and i not in adj_idx]

        inner_of = {}
        outer_to_inners = {}
        for inner, outer in nested:
            inner_of.setdefault(inner, outer)
            outer_to_inners.setdefault(outer, []).append(inner)

        draw = {}
        for i in range(n):
            n_edges = len(regs[i].get("points") or [])
            if i in inner_of:
                draw[i] = "all"                      # 嵌套小区域：虚线全画
            elif i in outer_to_inners:
                # 大区域：去掉"落在它包含的小区域内部"的那些边
                s = set(range(n_edges))
                for inner in outer_to_inners[i]:
                    s -= _shared_edges(i, inner, regs)
                draw[i] = "all" if s == set(range(n_edges)) else sorted(s)
            elif i in adj_idx:
                s = set()
                for a, b in adjacent:
                    if a == i:
                        s |= _shared_edges(i, b, regs)
                    elif b == i:
                        s |= _shared_edges(i, a, regs)
                draw[i] = sorted(s)
            else:
                hidden = auto_hidden_rule(regs[i], spots)
                draw[i] = [] if hidden else "all"    # 孤立：出界 ⇒ 整条不画
            draw[i] = _apply_override_to_draw(regs[i], draw[i], n_edges)
        result.update({"nested": nested, "adjacent": adjacent,
                       "isolated": isolated, "draw": draw})
        return result
    except Exception:
        traceback.print_exc()
        return result


def shared_boundary_paths(i, j, regions, spots, px_per_data=None):
    """⛔ **已停用（deprecated）**：两区域**共享边界**的折线 —— 随自动关系规则一起停用

    ★ 用户裁定 ④（2026-09）后，"相邻 ⇒ 只画共享边界"这条规则**没有了**：
      现在每个出图区域画**整条轮廓**（由 `visible_region_indices` 决定谁出图）
      ⇒ `export_outline_json` **不再调用本函数**。
    ★ **函数暂时保留、不删**（协调者要求"先别删，避免打断别人"），
      引用方清单见 `region_relations` 的说明。
    ★ 下面原说明保留，仅为追溯旧语义。

    ---------------------------------------------------------------------------
    ★ §16.2 **（旧）冻结**：两区域**共享边界**的折线（数据坐标，已按圆角处理）

    Returns:
        `list[list[[x, y]]]`（与 `region_outline_paths` **同形**）；无共享边 → `[]`

    ★ **两侧各出一份**：几何上它们是同一段，但两个区域的颜色/虚线可能不同，
      所以各自带自己的样式返回，由调用方（`export_outline_json`）分别成段 ——
      这样我**不必替用户编一条"交界线该用谁的颜色"的规则**（那是产品决策）。
    ★ `px_per_data` 不在冻结签名里（契约只冻 4 个参数）⇒ 做成可选：
      不传就是**尖角**（与 `region_outline_paths(px_per_data=None)` 行为一致）。
    """
    out = []
    try:
        regs = regions or []
        for src, dst in ((i, j), (j, i)):
            if not (0 <= src < len(regs)) or not (0 <= dst < len(regs)):
                continue
            shared = _shared_edges(src, dst, regs)
            if not shared:
                continue
            r = regs[src]
            n = len(r.get("points") or [])
            if n < 3:
                continue
            # 合成一个"只有共享边可见"的区域 → 复用同一套断开 + 倒角逻辑
            synthetic = dict(r)
            synthetic["edge_override"] = {str(e): ("show" if e in shared else "hide")
                                          for e in range(n)}
            for poly in region_outline_paths(synthetic, spots, px_per_data=px_per_data):
                out.append(poly)
        return out
    except Exception:
        traceback.print_exc()
        return out


def _norm_frame_color(v):
    """注释外框底色 → 规范化 `"#RRGGBB"` / `"#RRGGBBAA"`；非法/非 ASCII → `None`

    ★ 契约 §16.9.1：**送进 R 的字符串一律 ASCII** ⇒ 这里只接受 `#` + 6/8 位十六进制，
      别的一律丢弃（宁可不写这个键，也不要把非 ASCII 塞给 R）。
    ★ 返回 `None` 时调用方**不写** `labels[].frame_color` ⇒ R 走默认白底（向后兼容）。
    """
    try:
        s = str(v or "").strip()
        if not s:
            return None
        try:
            s.encode("ascii")
        except UnicodeEncodeError:
            print("[spatial_region] label_frame_color 含非 ASCII → 忽略: %r" % s)
            return None
        if len(s) not in (7, 9) or not s.startswith("#"):
            print("[spatial_region] label_frame_color 不是 #RRGGBB[AA] → 忽略: %r" % s)
            return None
        int(s[1:], 16)                       # 十六进制校验（失败 → 走 except）
        return "#" + s[1:].upper()
    except Exception:
        print("[spatial_region] label_frame_color 非法 → 忽略: %r" % (v,))
        return None


def export_outline_json(regions_data, sample_id, spots, path, px_per_data=None,
                        label_frame=None, *, label_frame_color=None):
    """把该样本的**轮廓 + 标签**导出成 R 侧要用的 JSON（§15.4）

    Returns:
        bool（失败原因在 `LAST_EXPORT_ERROR`；**绝不抛**）

    ## 结构（★ 2026-09 可见区域 / 隐形区域 双层改版后）
    ```json
    {"sample": "...", "spots": <n>, "px_per_data": <float|0>,
     "mask_n": <int>,          // 隐形区域（隐形范围层）多边形个数
     "mask_active": <bool>,    // 是否画了隐形区域
     "visible_n": <int>,       // 可见区域（可见范围层）多边形个数
     "visible_active": <bool>, // 是否画了可见区域
     "clip_mask_n": <int>,     // 参与裁剪的隐形区域多边形个数
     "clipped": <bool>,        // 本次是否真的做了裁剪（= clip_mask_n > 0）
     "segments": [{"points": [[x,y],...], "name":"MES", "color":"#..",
                   "dash_width":2, "dash_gap":6, "reason":"visible",
                   "clipped": true|false}, ...],
     "segments_points": [[[x,y],...], ...],   // 契约 §15.4 的纯点列表形态（兼容）
     "labels": [{"name":..,"x":..,"y":..,"font_size":..,"color":..,"frame":bool,
                 "frame_color":"#RRGGBB"|"#RRGGBBAA"(可选)}, ...]}
    ```
    ★ `segments` 用**带样式的对象**（每个区域颜色/虚线各不相同，纯点列表表达不了）。
      同时保留契约原文的 `segments_points`（纯点列表），两种读者都能用。
    ★★ **成图候选区域 = `visible_region_indices()`（普通区域，被可见层罩住那套）**
      **并上**「所有 `visible` 标记为真的区域自身的索引」（去重、升序；`union_candidates`）：
      · **可见区域（`visible`）v9.3 起自己出图** —— 用它的 `name`/`color`/`dash_width`/
        `dash_gap` 产生自己的 `segment` 与 `labels[]`（名字走既有 `style["name"]`；
        v8 起 `name` 与 `anno_label` 同步 ⇒ 图上显示的就是用户的注释文字）。
        依据：用户当面裁定「可见区域就是我的标注单元」—— 若可见区域自己不出图，
        图例会指向一个**看不见的区域**（这正是 v9.3 前跳过它的理由，本轮一并解决）；
      · **隐形区域（`mask`）自己永不出图、也永不出 `labels[]`**（行为**一个字未变**）：
        它**只**参与逐段裁剪（`clip_polyline_to_mask`），`mask_n`/`mask_active`/
        `clip_mask_n`/`clipped` 的语义与数值口径**原样**；
        ⇒ 同时带 `mask` 与 `visible` 的区域按**隐形区域**处理（mask 优先，见代码注释）；
      · 候选 = 被**可见区域**罩住的普通区域（可见层没画 ⇒ 全部；**两层都没画 ⇒ 默认全画**，
        向后兼容）∪ **可见区域自身**；
      · **v4：隐形区域不再决定整条区域画不画**，而是对每条可见折线**逐段裁剪**
        （`clip_polyline_to_mask`）：只保留落在 mask 并集内的那部分，
        **截断点按参数 t 精确插值**；
      · **每留下一段 = 单独一个 `segment` 条目**（同名/同样式/同 `reason`），
        该条目带 `"clipped"`；一段都不剩的候选区域**不产生任何 segment**
        —— 这正是用户要的"**上半部分出界的不画**"；
      · 画的是**整条轮廓**再裁剪（不再有"共享边界另外成段"那套）。
      ⇒ `reason` 现在**恒为 `"visible"`**（`nested`/`adjacent`/`isolated` 那套自动规则
        已被用户删掉，`region_relations`/`shared_boundary_paths` **不再被调用**）。
      ★ `visible_region_indices()` **本身一个字节未动**（它是"普通区域候选集"，
        签名与语义原样）；本函数的并集只发生在本函数的局部变量上。
    ★ **手工 `edge_override` 仍然生效且优先**：`region_outline_paths` 里先算"自动隐藏"、
      再由 override 覆盖。这里给出一份**副本**，把 override 里**没显式指定**的边一律置 `"show"`
      ⇒ 等价于"整条轮廓"，同时**用户显式 `"hide"` 的边依旧隐藏**（不会被本函数抹掉）。
    ★ `labels[].frame`（§16.2）：注释是否加圆角矩形外框。优先用显式 `label_frame`
      （bind 从 `chk_label_frame` 读）；没给则取区域自身的 `label_frame` 字段；默认 False。
    ★ `label_frame_color`（**仅关键字**，v4 第 3 点）：给 `geom_label` 那个圆角矩形底框上色。
      给了 ⇒ 每个 `labels[]` 加 `"frame_color"`（`#RRGGBB`/`#RRGGBBAA`，**必定 ASCII**）；
      **没给 / 非法 / 非 ASCII ⇒ 不写该键** ⇒ R 用默认白底（`fill = "#FFFFFFCC"`，向后兼容）。
    ★ **注释口径（v4 修正）**：`labels[]` **只给"最终真的产生了 ≥1 条 segment"的区域出**；
      某候选区域被裁完一段都不剩 ⇒ **既不出 segment、也不出 label**
      （否则成图上会留一个没有虚线的孤立名字，与"圈外不可见"相反）。
      部分裁剪（还有段剩下）⇒ 标签保留，位置仍走 `label_pos` / 质心，**不因裁剪挪标签**。
      ⇒ 不变式：`sorted(set(s["name"] for s in segments)) == sorted(l["name"] for l in labels)`。
    """
    global LAST_EXPORT_ERROR
    LAST_EXPORT_ERROR = ""
    try:
        if not path:
            LAST_EXPORT_ERROR = "输出路径为空"
            return False
        regs = [r for r in get_sample_regions(regions_data, sample_id)
                if isinstance(r, dict) and not r.get("invalid")]
        # ★ 两层范围层：判定只有一处（`visible_region_indices`），本函数只管成段与写盘
        mask_n = sum(1 for r in regs if _norm_flag(r.get("mask")))
        visible_n = sum(1 for r in regs if _norm_flag(r.get("visible")))
        mask_active = bool(mask_n > 0)
        visible_active = bool(visible_n > 0)
        # ★★ v9.3 候选集并集：既有「被可见区域罩住的**普通区域**」∪「**可见区域自己**」。
        #   为什么可见区域自己也要出图：用户当面裁定「可见区域就是我的标注单元」——
        #   若它自己不出图，图例会指向一个**看不见的区域**（这正是 v9.3 前跳过它的理由）。
        #   ⛔ `visible_region_indices`（"普通区域候选集"）**签名与语义一个字节未动**，
        #      并集只发生在下面这两个局部变量上；`canvas_visible_region_indices` /
        #      `_visible_filter_indices` 的 v4 语义也原样不动。
        #   ⛔ **隐形区域（mask）绝不进候选集**（它自己永不出图、只做逐段裁剪）：
        #      用 `is_anno_blocked_region` 挡住 ⇒ 同时带 `mask` 与 `visible` 的区域
        #      按**隐形区域**处理（mask 优先，保持"mask 行为一个字不许变"）。
        union_candidates = sorted(
            set(visible_region_indices(regs, spots) or [])
            | {i for i, r in enumerate(regs)
               if _norm_flag(r.get("visible")) and not is_anno_blocked_region(r)})
        visible = union_candidates
        # ★ v4：隐形区域**只做逐段裁剪**（不再决定整条区域画不画）
        mpolys = mask_polygons(regs)
        clip_mask_n = len(mpolys)
        clipped = bool(clip_mask_n > 0)
        # 注释外框底色（仅关键字参数；非法/非 ASCII → 不写该键，保持向后兼容）
        frame_color = _norm_frame_color(label_frame_color)

        segments = []
        labels = []
        # ★ 候选集是**并集**（普通区域 ∪ 可见区域）⇒ **下面这段循环是唯一一处画线逻辑**，
        #   可见区域走的是同一段（不复制第二份）：`reason` 仍恒为 `"visible"`。
        for idx in visible:
            r = regs[idx]
            style = {"name": str(r.get("name") or ""),
                     # ★ v9.2：与 `_norm_region` 的 `color` 行**共用同一处判据**
                     #   `_region_color_default`（⛔ 不要在这里再写一份 `visible` 判定）。
                     #   本行行为**逐字不变**，依据：
                     #   ① 走到这里的 `r` 在生产链路上**必然已归一化** —— `regs` 来自
                     #      `get_sample_regions`（函数 `get_sample_regions`），`regions_data` 在 bind 里 =
                     #      `SREG.load_regions(dataset)`（`ui_bind_spatial_region.py`），
                     #      而 `load_regions` 对每个区域跑 `_norm_region`；写回侧
                     #      `set_sample_regions` 同样归一化 ⇒ `color` 键**必定是非空字符串**
                     #      （`_norm_region` 的 `or` 兜底保证非空）⇒ 这里取到区域自带色
                     #      （**可见区域** v9.2 的无色默认值 = `DEFAULT_VISIBLE_REGION_COLOR`，
                     #       已由 `_norm_region` 写进 `color`）。
                     #   ② 即便拿到**未归一化**的 dict：普通区域 ⇒ `_region_color_default(r)`
                     #      回落 `DEFAULT_REGION_COLOR`；`visible` 为真的区域 ⇒ 回落
                     #      `DEFAULT_VISIBLE_REGION_COLOR`（该函数的 `visible` 分支）——
                     #      两种情况都与"改动前"一致，判据仍**只有一处** `_region_color_default`。
                     "color": str(r.get("color") or _region_color_default(r)),
                     "dash_width": float(r.get("dash_width") or DEFAULT_DASH_WIDTH),
                     "dash_gap": float(r.get("dash_gap") or DEFAULT_DASH_GAP),
                     "reason": "visible"}
            # ★ 整条轮廓 + 手工 override 优先（做法见 docstring 的 ★）
            n_edges = len(r.get("points") or [])
            ov = _norm_edge_override(r.get("edge_override"))
            synthetic = dict(r)
            synthetic["edge_override"] = {str(e): (ov.get(e) or "show")
                                          for e in range(n_edges)}
            n_seg_before = len(segments)
            for poly in region_outline_paths(synthetic, spots, px_per_data=px_per_data):
                # ★ v4：每条可见折线先按隐形区域**逐段裁剪**；
                #   闭合与否看 `region_outline_paths` 的产物：闭环段首尾同点。
                is_closed = bool(len(poly) >= 2 and _pt_eq(poly[0], poly[-1]))
                for piece in clip_polyline_to_mask(poly, mpolys, closed=is_closed):
                    # ★ 出口再验一遍（W3 硬要求）：**≥2 点且全为有限数**，否则不发这个条目
                    #   —— R 会静默丢弃（`segments_skipped`），这里先挡住，避免"两边同时少"。
                    fp = _finite_pts(piece)
                    if len(fp) < 2:
                        continue
                    # **每留下一段 = 单独一个 segment 条目**（同名/同样式/同 reason）
                    seg = dict(style)
                    seg["points"] = [[float(p[0]), float(p[1])] for p in fp]
                    seg["clipped"] = clipped
                    segments.append(seg)
            # ★★ v4 修正：**只给"最终真的产生了 ≥1 条 segment"的区域出标签**。
            #   原来这里是"候选区域一律出标签" ⇒ 某区域被隐形区域**整条裁光**时，
            #   成图上会留下一个**没有对应虚线的孤立名字**，与用户"圈外不可见"的意图相反
            #   （协调者实测场景 C：`segments=[]` 却 `labels=['A']`；v3 时是两者都空）。
            #   ⇒ 裁完一段不剩 ⇒ **既不出 segment、也不出 label**。
            #   ⚠ 部分裁剪（还有段剩下）⇒ 标签照旧保留，位置仍走 `label_pos`/质心，
            #     **不为了裁剪去挪标签**。
            if len(segments) == n_seg_before:
                continue
            ax, ay = label_anchor(r)
            if label_frame is None:
                fr = bool(r.get("label_frame", False))
            else:
                fr = bool(label_frame)
            lab = {"name": style["name"], "x": float(ax), "y": float(ay),
                   "font_size": float(r.get("label_font_size")
                                      or DEFAULT_LABEL_FONT_SIZE),
                   "color": str(r.get("label_font_color")
                                or DEFAULT_LABEL_FONT_COLOR),
                   "frame": fr}
            if frame_color:                    # ★ 没给 ⇒ **不写该键**（R 用默认白底）
                lab["frame_color"] = frame_color
            labels.append(lab)
        try:
            ppd = float(px_per_data) if px_per_data is not None else 0.0
        except (TypeError, ValueError):
            ppd = 0.0
        # ⚠ `"relations"` 键**已删除**（自动关系规则被用户裁定删掉）。
        #   不要再往这里加回旧键：docstring 已同步，不承诺不存在的键。
        payload = {"sample": str(sample_id or ""),
                   "spots": len(spots or []),
                   "px_per_data": ppd,
                   "mask_n": int(mask_n),
                   "mask_active": mask_active,
                   "visible_n": int(visible_n),
                   "visible_active": visible_active,
                   "clip_mask_n": int(clip_mask_n),
                   "clipped": clipped,
                   "segments": segments,
                   "segments_points": [s["points"] for s in segments],
                   "labels": labels}
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        return True
    except Exception as e:
        traceback.print_exc()
        LAST_EXPORT_ERROR = "%s: %s" % (type(e).__name__, e)
        print("[spatial_region] outline JSON 写出失败: %s" % LAST_EXPORT_ERROR)
        return False


def nospot_output_paths(dataset, sample_id):
    """§15.5 的**不带点**产物路径 `(png, pdf)`：`09_RegionOverride/SpatialNoSpots_<样本>.png`

    ★ 名字**冻结**（契约 §15.4 的产物表 + §15.5）：R 侧一次调用同时出两张，
      所以"有没有这张图"完全由 `rendered_hash` 决定（与带点那张同一批产物）。
    """
    d = region_override_dir(dataset)
    if not d or not sample_id:
        return "", ""
    return (os.path.join(d, "%s_%s.png" % (NOSPOT_PREFIX, sample_id)),
            os.path.join(d, "%s_%s.pdf" % (NOSPOT_PREFIX, sample_id)))


def _override_state(dataset, sample_id, png, data):
    """override 新鲜度的**共同判定**（带点 / 不带点两张图共用这一处）

    返回 `"ok"` / `"no_regions"` / `"stale"` / `"expired"`（语义见 `override_png_for`）。
    ★ 两张图是**同一次 R 调用**的产物、共用同一个 `rendered_hash`，
      所以判定逻辑必须只有一份（否则两张图会各自"过期"，用户看到自相矛盾的界面）。
    """
    try:
        n = painted_region_count(data, sample_id)
        if n <= 0:
            return "no_regions"
        if not png or not os.path.isfile(png):
            return "stale"
        cur = regions_hash(data, sample_id)
        stored = get_rendered_hash(data, sample_id)
        if stored:
            return "ok" if stored == cur else "expired"
        # 兼容老文件：没有 rendered_hash 才回退 mtime（**+2 秒容差**）
        try:
            rp = regions_path_for(dataset)
            if rp and os.path.isfile(rp):
                if os.stat(png).st_mtime + 2.0 < os.stat(rp).st_mtime:
                    return "expired"
        except Exception:
            traceback.print_exc()
        return "ok"
    except Exception:
        traceback.print_exc()
        return "no_regions"


def override_png_for(dataset, sample_id, regions_data=None):
    """★ 契约 §14.3 **v2** 的 override 判定（**带点**那张）—— 全库唯一实现

    Returns:
        (png_path: str, state: str)，state ∈ `{"ok","no_regions","stale","expired"}`

    ## 为什么必须用内容哈希替代"文件 mtime"（协调者实测认定，这是结构性错）
      `regions.json` 是**整个数据集一个文件** ⇒ 一个文件的 mtime **表达不了逐样本新鲜度**：
        · 确认流程是"先渲染、后存 regions" ⇒ 存完 regions 比图新 ⇒ **刚确认完就判"过期"**；
        · 给**样本 B** 保存会更新同一个文件的 mtime ⇒ **样本 A 的 override 被连带判过期**。
      ⇒ 改成**逐样本内容哈希**（`samples[<sid>].rendered_hash`），没有时序窗口。
      兼容老文件（无该字段）时才回退 mtime，且 **+2 秒容差**。
    ★ 绝不静默：任何非 `ok` 都只回报状态，**不替调用方决定**用哪张图。
    """
    try:
        if not dataset or not sample_id:
            return "", "no_regions"
        data = regions_data if regions_data is not None else load_regions(dataset)
        png, _pdf = render_output_paths(dataset, sample_id)
        state = _override_state(dataset, sample_id, png, data)
        return (png, state) if state == "ok" else ("", state)
    except Exception:
        traceback.print_exc()
        return "", "no_regions"


def override_nospot_png_for(dataset, sample_id, regions_data=None):
    """§15.5 的「不带点」那张的 override 判定（**与带点那张同一套规则/同一个凭据**）

    Returns: `(png_path, state)`；state 语义同上。
    ★ 没有 override 时返回 `("", "stale")` 或 `("", "no_regions")` ⇒
      调用方**显示"该图尚未生成"**，**绝不拿带点版冒充**（§15.5 明文要求）。
    """
    try:
        if not dataset or not sample_id:
            return "", "no_regions"
        data = regions_data if regions_data is not None else load_regions(dataset)
        png, _pdf = nospot_output_paths(dataset, sample_id)
        state = _override_state(dataset, sample_id, png, data)
        return (png, state) if state == "ok" else ("", state)
    except Exception:
        traceback.print_exc()
        return "", "no_regions"


def outline_json_path_for(dataset, sample_id):
    """轮廓 JSON 的落地路径（放 workbench 里，**全 ASCII**，便于排障与重跑）"""
    if not dataset or not sample_id:
        return ""
    o = _out_base()
    if not o:
        return ""
    return os.path.join(o, dataset, WORKBENCH_DIR, "region_outline_%s.json" % sample_id)


def load_regions(dataset):
    """读 `<ds>.regions.json`（**缺失/损坏/结构不对一律返回空骨架，绝不抛**）

    Returns:
        dict: `{"schema":1,"dataset":…,"samples":{样本: {"regions":[区域,...]}}, "_issues":[…]}`

    ★ 每个区域都被 `_norm_region` 归一化：**缺字段用默认值**，而不是让上层到处
      写 `.get(..., 默认)`（那是把默认值散落成多个真相源）。
    ★ `_issues` 只用于如实说明"文件怎么了"，**不参与业务**（与 RA.load_review_scores 同风格）。
    """
    d = _empty_regions(dataset)
    issues = []
    try:
        path = regions_path_for(dataset)
        if not path:
            d["_issues"] = ["无法解析 regions.json 路径（dataset 为空或 appdata 不可用）"]
            return d
        if not os.path.isfile(path):
            d["_issues"] = ["尚无区域文件（首次使用属正常）: %s" % path]
            return d
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            d["_issues"] = ["区域文件读取失败: %s: %s" % (type(e).__name__, e)]
            return d
        if not isinstance(raw, dict):
            d["_issues"] = ["区域文件顶层不是对象（实际 %s）" % type(raw).__name__]
            return d
        samples = raw.get("samples")
        if not isinstance(samples, dict):
            issues.append("samples 字段缺失或不是对象，已按空处理")
            samples = {}
        out_samples = {}
        for sid, entry in samples.items():
            regs_raw = (entry or {}).get("regions") if isinstance(entry, dict) else None
            # ★ §14.3 v2：`rendered_hash` 必须**原样带出来**（它是"已确认"的唯一凭据）。
            #   漏掉它 ⇒ 每次读回都退化成"老文件" ⇒ 走 mtime 兼容路径 ⇒ 上述连带过期问题复发。
            rh = ""
            if isinstance(entry, dict):
                rh = str(entry.get("rendered_hash") or "")
            if not isinstance(regs_raw, list):
                if entry is not None:
                    issues.append("样本 %s 的 regions 不是数组，已按空处理" % sid)
                out_samples[str(sid)] = {"regions": [], "rendered_hash": rh}
                continue
            regs = []
            for r in regs_raw:
                nr = _norm_region(r)
                if nr is None:
                    issues.append("样本 %s 有 1 个区域不是对象，已跳过" % sid)
                    continue
                regs.append(nr)
            out_samples[str(sid)] = {"regions": regs, "rendered_hash": rh}
        d.update({"schema": int(raw.get("schema") or 1) if str(raw.get("schema") or "1").isdigit() else 1,
                  "dataset": str(raw.get("dataset") or dataset or ""),
                  "samples": out_samples})
        d["_issues"] = issues
        return d
    except Exception as e:
        traceback.print_exc()
        d["_issues"] = ["load_regions 异常: %s: %s" % (type(e).__name__, e)]
        return d


def get_sample_regions(data, sample_id):
    """从 `load_regions()` 的返回里取某样本的区域列表（**永远返回 list，绝不 None**）"""
    try:
        entry = ((data or {}).get("samples") or {}).get(str(sample_id)) or {}
        regs = entry.get("regions")
        return list(regs) if isinstance(regs, list) else []
    except Exception:
        traceback.print_exc()
        return []


def set_sample_regions(data, sample_id, regions):
    """把某样本的区域列表写回 `data`（原地修改并返回 data；便于 bind 保存前组装）

    ★ **必须保留 `rendered_hash`**：区域一改，那个"已确认"凭据在语义上就**过期**了，
      但**过期由哈希比对自然得出**（`rendered_hash != regions_hash`），
      所以**不能在这里把它删掉** —— 删了就退化成"老文件"，走 mtime 兼容路径，
      又会回到"给 B 保存把 A 判过期"的老毛病（§14.3 v2 的根因）。
      即：**保留旧凭据 + 内容变了 ⇒ 自动 expired**，这正是我们要的语义。
    """
    try:
        if not isinstance(data, dict):
            return _empty_regions("")
        data.setdefault("samples", {})
        sid = str(sample_id)
        keep = get_rendered_hash(data, sid)
        data["samples"][sid] = {
            "regions": [r for r in (_norm_region(x) for x in (regions or [])) if r is not None],
            "rendered_hash": keep,
        }
        return data
    except Exception:
        traceback.print_exc()
        return data


def save_regions(dataset, data):
    """原子写（临时名带 pid/ms/seq，`os.replace` 收口）

    Returns:
        bool: 是否写入成功（失败已写日志，**不抛**）

    ⚠ 原子性不是可选项：写到一半崩掉会毁掉用户**手画了半天的区域**。
      同目录临时文件 + `os.replace` 保证"要么是旧的完整文件、要么是新的完整文件"。

    ★ **生产路径**：确认按钮就是靠它落盘，所以**不加**"仅测试数据集可写"的闸
      （那会把功能锁死）。作为补偿，**每次写入都把目标路径打出来**，
      任何写错地方的情况在日志里都看得见。
    """
    global _TMP_SEQ
    try:
        if not dataset:
            return False
        if not isinstance(data, dict):
            return False
        path = regions_path_for(dataset)
        if not path:
            print("[spatial_region] 无法解析 regions.json 路径，未写入")
            return False
        payload = {k: v for k, v in data.items()
                   if not (isinstance(k, str) and k.startswith("_"))}
        payload["schema"] = 1
        payload["dataset"] = str(payload.get("dataset") or dataset)
        if not isinstance(payload.get("samples"), dict):
            payload["samples"] = {}
        # 落盘前把每个区域再归一化一次（内存里被外部改脏也能自愈）；
        # ★ `rendered_hash` 一起带出去（见 set_sample_regions 的说明：它是"已确认"凭据）
        clean = {}
        for sid, entry in payload["samples"].items():
            regs = (entry or {}).get("regions") if isinstance(entry, dict) else None
            rh = str((entry or {}).get("rendered_hash") or "") if isinstance(entry, dict) else ""
            clean[str(sid)] = {"regions": [r for r in
                                           (_norm_region(x) for x in (regs or []))
                                           if r is not None],
                               "rendered_hash": rh}
        payload["samples"] = clean

        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        _TMP_SEQ += 1
        tmp = "%s.tmp.%d.%d.%d" % (path, os.getpid(), int(time.time() * 1000), _TMP_SEQ)
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
        print("[spatial_region] 区域已保存 → %s（样本 %d 个）" % (path, len(clean)))
        return True
    except Exception as e:
        traceback.print_exc()
        try:
            if 'tmp' in dir() and tmp and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        print("[spatial_region] 区域保存失败: %s: %s" % (type(e).__name__, e))
        return False


# =============================================================================
# spots.csv（W3 产出的坐标 + 细胞类型表）
# =============================================================================
def load_spots(dataset, sample_id=None):
    """读 `_region_workbench/spots.csv`

    Args:
        sample_id: None = 全部样本；否则只返回该样本的行
    Returns:
        (rows, error)：rows 是 `[{'spot','sample','x','y','cluster','cell_type'}, ...]`，
        **x/y 已转成 float**；error 非空表示读不到（真机上"W3 还没导出"属正常情况）。

    ★ 缺文件**不是异常**（§13 说明：该文件可能还没生成）——返回明确的中文原因，
      由上层显示"尚未导出坐标表"，**不抛、不静默**。
    """
    rows = []
    try:
        path = spots_path_for(dataset)
        if not path:
            return [], "无法解析 spots.csv 路径（dataset 为空或 OUTPUT 不可用）"
        if not os.path.isfile(path):
            return [], "尚未导出坐标表: %s" % path
        with io.open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            header = [str(h or "").strip() for h in (reader.fieldnames or [])]
            missing = [h for h in ("spot", "x", "y") if h not in header]
            if missing:
                return [], ("坐标表表头不符（缺 %s）：%s；实际表头 = %s"
                            % (",".join(missing), path, header))
            for raw in reader:
                try:
                    x = float(raw.get("x"))
                    y = float(raw.get("y"))
                except (TypeError, ValueError):
                    continue                      # 坏行跳过（下面用计数反映）
                r = {
                    "spot": str(raw.get("spot") or ""),
                    "sample": str(raw.get("sample") or ""),
                    "x": x, "y": y,
                    "cluster": str(raw.get("cluster") or ""),
                    "cell_type": str(raw.get("cell_type") or ""),
                }
                if sample_id and r["sample"] != str(sample_id):
                    continue
                rows.append(r)
        if sample_id and not rows:
            return [], ("坐标表里没有样本 %s 的行（可能该样本尚未导出）：%s"
                        % (sample_id, path))
        return rows, ""
    except Exception as e:
        traceback.print_exc()
        return [], "读取坐标表异常: %s: %s" % (type(e).__name__, e)


# =============================================================================
# 点在多边形内（射线法；**不引依赖**）
# =============================================================================
def _on_segment(px, py, ax, ay, bx, by, eps=1e-9):
    """点是否落在线段 AB 上（含端点）

    ★ 为什么需要显式判这个：纯射线法对"点正好在边上"的结果**取决于舍入方向**
      （横穿记一次、顶点处记 0 或 2 次），会出现同一条边两侧行为不一致。
      契约要求"**点在边上算作在内**"（§13 冻结），所以先把边界单独判掉。
    ★ 用 `eps` 而不是裸 `==`：这些坐标是 float（R 侧来的 double），
      裸 `==` 在数学上"共线"的点上几乎必然不成立 —— 那反而会让契约失效。
      `eps=1e-9` 对 1e4 量级的坐标相当于 1e-13 相对误差，**只吃真正的共线**。
    """
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > eps:
        return False
    if px < min(ax, bx) - eps or px > max(ax, bx) + eps:
        return False
    if py < min(ay, by) - eps or py > max(ay, by) + eps:
        return False
    return True


def point_in_polygon(x, y, points):
    """点 `(x, y)` 是否在多边形 `points` 内（射线法 + 边界算在内）

    · **顶点数 <3 → 直接判否**（契约冻结）；
    · **点在边上/顶点上 → 算在内**（契约冻结，见 `_on_segment` 的说明）；
    · 复杂度 **O(V)**（V = 顶点数），**不是 O(n²)** —— 逐 spot 调用一次，
      37672 spot × 若干区域在这种实现下是几百毫秒级。

    ★ 射线法用**半开规则**（`(ay > y) != (by > y)`）：跨过水平边的交点只算一次，
      避免"射线正好穿过顶点"被记两次。这是射线法不重复计数所必需的。
    """
    try:
        pts = points or []
        n = len(pts)
        if n < 3:
            return False                      # 少于 3 个顶点构不成多边形
        inside = False
        j = n - 1
        for i in range(n):
            ax, ay = float(pts[j][0]), float(pts[j][1])
            bx, by = float(pts[i][0]), float(pts[i][1])
            # ① 边界优先：点在边上算在内
            if _on_segment(x, y, ax, ay, bx, by):
                return True
            # ② 射线横穿这条边？（半开规则）
            if (ay > y) != (by > y):
                x_cross = (bx - ax) * (y - ay) / (by - ay) + ax
                if x < x_cross:
                    inside = not inside
            j = i
        return inside
    except Exception:
        traceback.print_exc()
        return False


# =============================================================================
# ★ 选择模式（`_d_spec_select_mode.md` §4，2026-09-23）：**公用锚点 / 共享边**判定
# -----------------------------------------------------------------------------
# 两个**公开纯函数**（无 Qt、无 I/O、无副作用、**绝不抛**）：
#   · `vertices_at`            —— 某坐标上有哪些 `(区域, 顶点号)`（"公用锚点"= 命中 ≥2）
#   · `shared_edge_partners`   —— 某条边与哪些**其它区域**共享（判据见各自 docstring）
# ★ 容差一律是**数据单位**：调用方把屏幕容差换算后传入（`tol_data = tol_screen / scale`），
#   所以本模块**不猜像素**、不做任何显示相关的事（`SHARED_TOL_DEFAULT` 只是不传时的兜底）。
# ★★ 两者都**不跳过范围层**（`mask` 隐形区域 / `visible` 可见区域）：用户要求选择模式里
#   "可见 + 隐形都能选"；范围层的"不可命名"由写盘守卫（§3.4）负责，**不在几何层过滤**。
# ★ 取点方式照抄本文件既有写法（`_shared_edges` / `_edge_midpoint` / `visible_edge_indices`）：
#   `(r.get("points") or [])` 取顶点列表，单个顶点过 `_norm_point`；**绝不自己发明字段名**。
# ⚠ `_shared_edges(i, j, regions)` 是**另一条语义**（"i 的边中点落在 j 内/边上"），
#   本节的函数**不改它、也不复用它**（判据不同：这里比的是**边与边**的端点/共线重叠）。
# =============================================================================

def _geo_warn(msg):
    """选择模式几何函数的**留痕出口**：打印一条日志，**自身绝不抛**

    ★ 为什么要包一层（本机实测踩到的坑）：`print` 在 **GBK 控制台**上遇到 GBK 编码
      不含的字符（例如 `⇒`、`≥`）会抛 `UnicodeEncodeError`。如果这个 `print` 写在
      `except` 块里（本节的函数都是这个结构），它就会把**已经兜住的异常**重新变成
      **真异常抛给画布** —— 直接违反"绝不抛"。
      ⇒ 先尝试原样打印；失败则退化成 **ASCII 安全**（`backslashreplace`）的转义形式。
    """
    try:
        print(msg)
    except Exception:
        try:
            print(str(msg).encode("ascii", "backslashreplace").decode("ascii"))
        except Exception:
            pass


def _edge_collinear_overlap(a1, a2, b1, b2, tol):
    """两线段**共线且重叠**时，在公共直线上的**重叠长度**；不共线/退化 → `0.0`

    ## 判据（选择模式 §4 的 ②，实现细节）
      · **共线**：`b1`/`b2` 到 **A 所在直线**的距离、`a1`/`a2` 到 **B 所在直线**的距离
        **都 ≤ `tol`**（点到直线距离 = `|叉积| / 线段长`）；
      · **重叠长度** = 两条线段在 A 方向上的**投影区间交集长度**（A 自身区间 = `[0, |A|]`）；
      · 退化边（长度 ≤ tol）⇒ `0.0`（零长边谈不上"重叠"，端点重合那条判据会覆盖它）。

    ★ 为什么**不能**直接用本文件的 `_on_segment(..., eps=tol)` 做共线判定：
      它的 `eps` 比的是**叉积**（量纲 = 长度²），会随边长放大/缩小 —— 数据单位下边长可上万
      （实测 `GSM7596588` x 到 11087），此时 1e-6 的垂直偏离会算出 1e-2 量级的叉积，
      长边上"真共线"会被误判成"不共线"。所以这里显式做**距离**量纲的比较。
    ★ **绝不抛**：异常 ⇒ `traceback.print_exc()` + `0.0`（调用方据此判"不共享"）。
    """
    try:
        ax, ay = float(a1[0]), float(a1[1])
        bx, by = float(a2[0]), float(a2[1])
        cx, cy = float(b1[0]), float(b1[1])
        dx, dy = float(b2[0]), float(b2[1])
        t = abs(float(tol))
        ux, uy = bx - ax, by - ay
        la = math.hypot(ux, uy)
        vx, vy = dx - cx, dy - cy
        lb = math.hypot(vx, vy)
        if la <= t or lb <= t:
            return 0.0                        # 退化（近零长）边：判不了重叠
        # ---- 共线：双方端点到对方直线的距离都 ≤ tol ----
        d_b1 = abs(ux * (cy - ay) - uy * (cx - ax)) / la
        d_b2 = abs(ux * (dy - ay) - uy * (dx - ax)) / la
        d_a1 = abs(vx * (ay - cy) - vy * (ax - cx)) / lb
        d_a2 = abs(vx * (by - cy) - vy * (bx - cx)) / lb
        if max(d_b1, d_b2, d_a1, d_a2) > t:
            return 0.0
        # ---- 投影到 A 方向：A = [0, la]，B = [t1, t2] ⇒ 交集长度 ----
        t1 = ((cx - ax) * ux + (cy - ay) * uy) / la
        t2 = ((dx - ax) * ux + (dy - ay) * uy) / la
        lo = max(0.0, min(t1, t2))
        hi = min(la, max(t1, t2))
        return (hi - lo) if hi > lo else 0.0
    except Exception:
        traceback.print_exc()
        return 0.0


def vertices_at(x, y, regions, tol=SHARED_TOL_DEFAULT):
    """返回**所有**与 `(x, y)` 距离 ≤ `tol` 的顶点 `(区域索引, 顶点号)`（§4 冻结签名）

    ## 语义（选择模式规格 §4）
      · 顺序 = **区域顺序 → 顶点号顺序**（调用方据此判"公用锚点"：
        `len(vertices_at(...)) >= 2` ⇒ 该锚点被 ≥2 个区域共用）；
      · ★ **不跳过范围层**（`mask` 隐形区域 / `visible` 可见区域）：用户要求
        "可见 + 隐形都能选"，范围层顶点也必须能判成共享/独占；"不可命名"由 §3.4 的
        写盘守卫负责，**不在几何层过滤**；
      · `invalid`（顶点 <3）之类的**坏区域安全跳过**（它构不成形状，顶点号也无编辑意义）；
      · 顶点**逐个**过本文件既有的 `_norm_point`（取点写法与 `region_outline_paths` 一致），
        但**不预先过滤点列表** —— 先过滤会让"顶点号"整体前移，返回的 `(区域, 顶点号)`
        与画布上的顶点**静默错位**（这是必须避免的错，宁可为坏顶点跳过一格）。

    Args:
        x, y: 数据坐标（可 `float()` 即可）
        regions: 本模块既有的区域列表（顶点在各自的 `points` 字段）
        tol: **数据单位**容差（调用方已按 `tol_screen / scale` 换算）；默认 `SHARED_TOL_DEFAULT`
    Returns:
        `list[tuple[int, int]]`（区域顺序、顶点号顺序）；参数非法/内部异常 ⇒ `[]`（+ 留痕）
    ★ **绝不抛**（沿用本模块范式）：一切异常 `traceback.print_exc()` 后返回 `[]`，且**不静默**。
    """
    out = []
    try:
        fx = float(x)
        fy = float(y)
        t = abs(float(tol))
        if not (math.isfinite(fx) and math.isfinite(fy) and math.isfinite(t)):
            raise ValueError("坐标/容差不是有限数：x=%r y=%r tol=%r" % (x, y, tol))
        for ri, r in enumerate(list(regions or [])):
            if not isinstance(r, dict) or r.get("invalid"):
                continue                      # 坏区域 / 非区域条目：安全跳过（判不了形状）
            for vi, p in enumerate(r.get("points") or []):
                np_ = _norm_point(p)
                if np_ is None:
                    continue                  # 坏顶点：跳过，但**保留顶点号**（见 docstring）
                if math.hypot(np_[0] - fx, np_[1] - fy) <= t:
                    out.append((int(ri), int(vi)))
        return out
    except Exception:
        traceback.print_exc()
        _geo_warn("[spatial_region] vertices_at 参数非法或内部异常 -> 返回 []"
                  "（x=%r y=%r tol=%r regions=%s）"
                  % (x, y, tol, type(regions).__name__))
        return []


def shared_edge_partners(i, edge_no, regions, tol=SHARED_TOL_DEFAULT):
    """与区域 `i` 的第 `edge_no` 条边**共享**的其它区域索引（**升序、去重**；§4 冻结签名）

    ## "共享"判据（选择模式规格 §4，**冻结**，两条**任一**成立即算）
      ① **两端点各自重合**：存在 `j` 的某条边 `(q_k, q_{k+1})`，使
         `|p_k − q_k| ≤ tol` 且 `|p_{k+1} − q_{k+1}| ≤ tol`，**或反向配对**
         （`p_k↔q_{k+1}`、`p_{k+1}↔q_k`）也成立 —— 用户"显式复用顶点"画出来的就是这种；
      ② **共线且重叠长度 > tol**（`_edge_collinear_overlap`）—— 覆盖"两次分别画、
         坐标略有差异但贴在一起"的情形。

    ## 其它约定
      · 边号沿用本文件冻结语义：边 `k` = `points[k] → points[(k+1) % n]`（§15.3）；
      · `j == i` **必须跳过**（同一条边与自己必然满足 ①）；
      · **不跳过范围层**（`mask`/`visible` 也算"共享"，与 `vertices_at` 同一口径）；
      · `invalid` / 非 dict / 顶点数 <2 的区域**安全跳过**（它构不成有意义的边）。
      · ⚠ 本函数判的是**边与边**（端点重合 / 共线重叠），与 `_shared_edges(i, j, regions)`
        的"边中点落在 j 内/边上（含相交情形）"**语义不同**，所以**没有**调用它；
        `point_in_polygon` 同样用不上（那需要"点在多边形内"，而这里只需要两条线段的比较）。

    Args:
        i: 区域索引
        edge_no: 该区域的边号（`0 .. n-1`）
        regions: 本模块既有的区域列表
        tol: **数据单位**容差（调用方按 `tol_screen / scale` 换算）；默认 `SHARED_TOL_DEFAULT`
    Returns:
        `list[int]`（升序、去重）；`i`/`edge_no` 越界、坏区域、参数非法 ⇒ `[]`（+ 留痕）

    ★ **绝不抛**，但也**绝不静默**：越界等调用方 bug 在这里**显式 raise 后立刻捕获**，
      于是 `traceback.print_exc()` 打出的是**真调用栈**（而不是无异常时的
      `NoneType: None`），同时按本文件既有风格补一条中文日志 —— 既不把异常抛给画布，
      也留下可定位的信息。
    """
    partners = set()
    try:
        regs = list(regions or [])
        idx = int(i)
        k = int(edge_no)
        t = abs(float(tol))
        if not math.isfinite(t):
            raise ValueError("tol 不是有限数：%r" % (tol,))
        if not (0 <= idx < len(regs)):
            raise IndexError("区域索引越界：i=%r，区域数=%d" % (i, len(regs)))
        r = regs[idx]
        if not isinstance(r, dict) or r.get("invalid"):
            raise ValueError("区域 #%d 不是有效区域（非 dict 或 invalid）" % idx)
        # ★ 取点写法与 `_shared_edges` / `_edge_midpoint` 一致：直接用 `points` 的**原位索引**
        #   （不过滤坏点 —— 否则边号会整体前移，与画布给的 `edge_no` 对不上）
        pts = (r.get("points") or [])
        n = len(pts)
        if n < 2:
            raise ValueError("区域 #%d 的顶点数 <2，没有边：%d" % (idx, n))
        if not (0 <= k < n):
            raise IndexError("边号越界：edge_no=%r，区域 #%d 的边数=%d" % (edge_no, idx, n))
        p1 = _norm_point(pts[k])
        p2 = _norm_point(pts[(k + 1) % n])
        if p1 is None or p2 is None:
            raise ValueError("区域 #%d 的第 %d 条边含非法顶点" % (idx, k))
        for j, rj in enumerate(regs):
            if j == idx or not isinstance(rj, dict) or rj.get("invalid"):
                continue
            jpts = (rj.get("points") or [])
            nj = len(jpts)
            if nj < 2:
                continue
            for m in range(nj):
                q1 = _norm_point(jpts[m])
                q2 = _norm_point(jpts[(m + 1) % nj])
                if q1 is None or q2 is None:
                    continue
                # ---- ① 两端点各自重合（顺序可反）----
                if ((math.hypot(p1[0] - q1[0], p1[1] - q1[1]) <= t
                     and math.hypot(p2[0] - q2[0], p2[1] - q2[1]) <= t)
                        or (math.hypot(p1[0] - q2[0], p1[1] - q2[1]) <= t
                            and math.hypot(p2[0] - q1[0], p2[1] - q1[1]) <= t)):
                    partners.add(int(j))
                    break
                # ---- ② 共线且重叠长度 > tol ----
                if _edge_collinear_overlap(p1, p2, q1, q2, t) > t:
                    partners.add(int(j))
                    break
        return sorted(partners)
    except Exception:
        traceback.print_exc()
        _geo_warn("[spatial_region] shared_edge_partners 参数越界/区域非法/内部异常 -> 返回 []"
                  "（i=%r edge_no=%r tol=%r regions=%s）"
                  % (i, edge_no, tol, type(regions).__name__))
        return []


def _spot_xy(row):
    """从一行 spot 里取 `(x, y)`；支持 dict 行与 `(x, y)` 元组；取不到 → `None`"""
    try:
        if isinstance(row, dict):
            return float(row.get("x")), float(row.get("y"))
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            return float(row[0]), float(row[1])
    except (TypeError, ValueError):
        return None
    return None


def _spot_id(row, idx):
    """从一行 spot 里取 spot id；dict 行用 `spot` 键，元组行退化成序号字符串"""
    try:
        if isinstance(row, dict):
            return str(row.get("spot") or "")
    except Exception:
        pass
    return str(idx)


def assign_labels(spots, regions):
    """逐 spot 算新标签（**与 `spots` 等长、同序**）

    Args:
        spots: `[{...'x','y'...}, ...]`（也接受 `(x, y)` 元组）
        regions: 归一化后的区域列表，**顺序 = 绘制顺序**
    Returns:
        list[str]: 落入某区域的 → 该区域名；**未被任何区域覆盖 → `""`（NA）**

    ★ **重叠时后画的覆盖先画的**（§13.3 第 2 条）：按列表顺序遍历并**直接覆盖**，
      所以顺序里靠后的（后画的）赢。这里**不能用 `break`**——一 `break` 就变成
      "先画的赢"，与契约相反。
    ★ 只有 `invalid`（顶点 <3）的区域跳过：它们判不出任何点，留着参与覆盖没有意义。
    ★★ v9.3：**只跳过"命名受阻区域"= 隐形区域（`mask`）**（判据 `is_anno_blocked_region`）：
      隐形区域是"罩子"、自己不出图；若让它参与"后画赢"，用户区域里的 spot 会被
      改判成**隐形区域的颜色与命名**，而隐形区域**根本不出现在图上** ⇒ 图上颜色与图例全错
      （这才是最坏的结果：图看着正常，颜色却对应一个看不见的区域）。
      ⚠ **可见区域（`visible`）不再跳过 —— 它现在会抢 spot 归属**，这正是用户要的"映射"：
        用户裁定「可见区域」就是他的标注单元（v9.3 前本处用的是 `is_layer_region`，
        把可见区域一起跳过了 ⇒ 可见区域上的注释映射不到 spot，用户报 bug 后收窄）。
    """
    out = []
    try:
        regs = [r for r in (regions or [])
                if isinstance(r, dict) and not r.get("invalid")
                and not is_anno_blocked_region(r)]
        for idx, row in enumerate(spots or []):
            xy = _spot_xy(row)
            if xy is None:
                out.append(NA_LABEL)
                continue
            x, y = xy
            label = NA_LABEL
            for r in regs:
                if point_in_polygon(x, y, r.get("points")):
                    label = str(r.get("name") or "")
            out.append(label)
        return out
    except Exception:
        traceback.print_exc()
        # 出错时返回"全 NA"而不是短列表：长度对不上比标签错更危险
        return [NA_LABEL] * len(spots or [])


def count_by_region(spots, regions):
    """各区域 spot 数 + 未覆盖数

    Returns:
        dict: `{"counts": {区域名: n}, "uncovered": n, "total": n, "labels": [...]}`
              · `counts` **含 0 个 spot 的区域**（日志要能说"MES: 0"，不许静默省略）
              · 同名区域会**合并计数**（用户可能给两块区域起同一个名字）
              · `total` = spot 总数；`uncovered` = 标签为空串的数量
    ★★ v9.3：**隐形区域（`mask`）不出现在 `counts` 里**（`assign_labels` 已跳过它们）：
      它自己不出图，列出来只会让日志/图例多一个"看不见的区域"。
      **可见区域（`visible`）现在会出现**（以及它有 spot 时的计数）—— 用户裁定可见区域
      就是标注单元，它既出图也参与归类 ⇒ 必须可见（v9.3 前本处用的是 `is_layer_region`，
      把可见区域一起挡在 `counts` 外，用户报 bug 后收窄）。
    """
    try:
        labels = assign_labels(spots, regions)
        counts = {}
        for r in (regions or []):
            if not isinstance(r, dict) or r.get("invalid") or is_anno_blocked_region(r):
                continue
            counts.setdefault(str(r.get("name") or ""), 0)
        uncovered = 0
        for lb in labels:
            if lb == NA_LABEL:
                uncovered += 1
            else:
                counts[lb] = counts.get(lb, 0) + 1
        return {"counts": counts, "uncovered": uncovered,
                "total": len(labels), "labels": labels}
    except Exception:
        traceback.print_exc()
        return {"counts": {}, "uncovered": 0, "total": 0, "labels": []}


# =============================================================================
# §2（2026-09-23）两级命名的**派生量**：逐 spot 的 `group_graphed` 注释值
# -----------------------------------------------------------------------------
# ★ 真相源永远是**区域内部**字段（`anno_group` / `anno_label`）；这里**只派生、绝不写盘**。
# ★ 与 `assign_labels` **同一套遍历语义**（同一份"有效区域"过滤 + 按列表顺序直接覆盖、
#   后画的赢、**不 break**）；唯一差别：取 `anno_label` 且**非空才生效**
#   ⇒ 旧式区域（`anno_label` 空）在 group_graphed 里等于"没画"，
#     它那自由文本的 `name` **绝不会**混进这一列（§2 要的"旧数据照旧"）。
# =============================================================================
def _effective_regions(regions):
    """该样本**参与逐 spot 判定**的有效区域（顺序不变；`invalid` 与**隐形区域**排除）

    ★ 过滤条件与 `assign_labels` 里那一段**逐字一致**（顶点 <3 的 `invalid` 区域判不出任何点；
      **隐形区域 `mask`** 是"罩子"，自己不出图、也不抢 spot 归属）。
      `assign_labels` 本身**刻意不动**（§2-4：它的语义一个字节都不许变），
      所以这里单独成一个私有函数，供本节的三个新函数复用。
    ★★ v9.3 收窄：判据从 `is_layer_region`（`mask` **+** `visible`）换成
      `is_anno_blocked_region`（**只** `mask`）⇒ **可见区域（`visible`）参与**
      （`group_graphed_labels` 会采纳它的 `anno_label`，非空才生效这条不变）。
      依据 = 用户当面裁定「可见区域就是我的标注单元」（v9.3 前擅自把可见区域一起排除，
      用户报「点不动、映射不到注释」后收窄）。
    """
    try:
        return [r for r in (regions or [])
                if isinstance(r, dict) and not r.get("invalid")
                and not is_anno_blocked_region(r)]
    except Exception:
        traceback.print_exc()
        return []


def group_graphed_labels(spots, regions):
    """逐 spot 算 `group_graphed` 注释值（**与 `spots` 等长、同序**；§2-3 冻结签名）

    Args:
        spots: `[{...'x','y'...}, ...]`（也接受 `(x, y)` 元组）—— 与 `assign_labels` 同一入参形态
        regions: 归一化后的区域列表，**顺序 = 绘制顺序**
    Returns:
        list[str]: 落入某"有效区域"且该区域 `anno_label` 非空 → 该 `anno_label`；
                   **未被覆盖 / 只被旧式区域（`anno_label` 空）覆盖 → `""`**

    ★ 遍历语义与 `assign_labels` **完全一致**：按列表顺序**直接覆盖**、**不用 break**
      ⇒ 顺序里靠后的（后画的）赢。**非空才生效**是这里唯一的差别：
      后画但 `anno_label` 为空的（旧式）区域**不会**清掉先画区域已经给出的注释值。
    ★ 取不出坐标的行（如 `(x, y)` 里混了坏值）⇒ 该行空串（与 `assign_labels` 同款）。
    ★★ v9.3：**有效区域 = `invalid` 与隐形区域（`mask`）之外的区域**
      （判据 `is_anno_blocked_region`，见 `_effective_regions`）——
      **可见区域（`visible`）参与**：它的 `anno_label` 会被采纳（"非空才生效"不变）。
      v9.3 前这里用的是 `is_layer_region`（`mask` **+** `visible`），把可见区域一并排除
      ⇒ 可见区域上的注释**映射不到 spot**（用户报「点不动、映射不到注释」后收窄）。
    ★ **绝不抛**：异常 ⇒ 返回**全空串**（长度对不上比标签错更危险，与 `assign_labels` 同一条理由）。
    """
    out = []
    try:
        regs = _effective_regions(regions)
        for row in (spots or []):
            xy = _spot_xy(row)
            if xy is None:
                out.append(NA_LABEL)
                continue
            x, y = xy
            label = NA_LABEL
            for r in regs:
                if point_in_polygon(x, y, r.get("points")):
                    lb = str(r.get("anno_label") or "").strip()
                    if lb:                                  # ★ 非空才生效（空 = 旧式，不改判）
                        label = lb
            out.append(label)
        return out
    except Exception:
        traceback.print_exc()
        return [NA_LABEL] * len(spots or [])


def sample_has_group_graphed(regions):
    """该样本是否存在 **≥1 个有效区域且 `anno_label` 非空**（§2-3 冻结签名）

    Returns:
        bool: True = 这个样本有"绘图模式注释"（可以出注释图 / 可进 group_graphed 分组）；
              **False = 旧式（只有自由文本 `name`）/ 没有任何有效区域 / 只有隐形区域（`mask`）**

    ★ 供 §5.2 的"注释图"跳过规则与 §4.1 的 `group_graphed` 选项是否出现使用；
      **不判 `anno_group`**：只要用户真定过注释值（`anno_label` 非空）就算有
      —— 这正是"选了现有分组（如 cell_type）也照样出注释图"的语义。
    ★ v9.3：判据全部来自 `_effective_regions`（**只排除隐形区域 `mask`**）⇒
      **只有可见区域（`visible`）且其 `anno_label` 非空 ⇒ True**（用户裁定可见区域就是
      标注单元；v9.3 前"只有范围层"一律 False，把可见区域一起算了进去）。
    ★ **绝不抛**：异常 ⇒ `False` + `traceback.print_exc()`。
    """
    try:
        for r in _effective_regions(regions):
            if str(r.get("anno_label") or "").strip():
                return True
        return False
    except Exception:
        traceback.print_exc()
        return False


def anno_values_from_spots(spots, column):
    """取 `spots` 里 `column` 列的**去重值**（保序、去空、`strip()`；列缺失 ⇒ `[]`）

    Args:
        spots: `[{...}, ...]`（与 `assign_labels` 同一入参形态；**dict 行**才有"列"的概念）
        column: 分组列名（如 `"cell_type"` / `"cluster"`）
    Returns:
        list[str]: **首次出现顺序**（不做排序）、已去重、已 `strip()`、空串剔除；
                   `column` 为空 / `spots` 为空 / 列缺失 / 入参不合法 ⇒ `[]`

    ★ 供绘制区域页填"细分注释选择框"（§4.2）：顺序冻结 = **首次出现顺序**，
      与 `spots.csv` 里的顺序一致，便于用户逐条核对（排序会把这层对照关系打乱）。
    ★ **绝不抛**：异常 ⇒ `[]` + `traceback.print_exc()`。
    """
    out = []
    try:
        if not column:
            return out
        col = str(column)
        seen = set()
        for row in (spots or []):
            if not isinstance(row, dict):
                # 非 dict 行（`(x, y)` 元组等）没有"列"的概念 ⇒ 跳过。
                # 这**不是异常**（`assign_labels` 也接受这种入参），所以不刷日志。
                continue
            v = str(row.get(col) or "").strip()
            if not v or v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out
    except Exception:
        traceback.print_exc()
        return []


# =============================================================================
# ★★ v11（`_d_spec_v11_split_and_bubble.md` §3.1/§3.2）**多选样本的注释选项并集**
#    —— 空转"按所选样本动态给出分组/注释值"的**唯一真相源**。
#    两个函数都是**纯函数**：不读盘、不写盘、无全局状态、**自己不吞异常**
#    （逐样本/逐列的容错与留痕由调用方负责 —— 见 `SpatialDiffAnalysis` 的同名方法）。
#    ★ "哪些候选列**可见**"（= 并集非空）由 `SpatialDiffAnalysis.available_group_columns()`
#      统一实现，两个气泡页**继承**它 ⇒ 不在这里再放一个只被一处调用的包装函数
#      （本项目明令禁止死代码：见 `collapsed` / `gene_set_sum_expr` 的前车之鉴）。
#
#    入参一律是**已归一化的字典**（调用方负责归一化）：
#      rows_by_sample      = {sample_id: [ann_row, …]}，行键 = FROZEN_OBS_COLUMNS
#                            （`spot,sample,cluster,cell_type,region_label,
#                             group_graphed,group`；`group = region_label or cell_type`）
#      has_graph_by_sample = {sample_id: bool}（真相源 = `sample_has_group_graphed`，
#                            ⛔ 绝不是产物存在性）
#
#    语义（v10 冻结，逐位不变）：
#      · 候选列 = `ANNOTATION_CANDIDATES` ∩「该列在所选样本的**并集**里有非空值」，
#        顺序 = `ANNOTATION_CANDIDATES`；**不加** `nunique ≥ 2` 过滤；
#      · `group_graphed`：**只**统计 `has_graph` 为真的样本 ⇒ 全为假时该列**完全不出现**；
#        取值也只并集带 graph 的样本（用户原话："只分析带 graph 注释的那个样本"）；
#      · 取值列表 = `sorted(去重去空并集)`（排序口径对齐单细胞 `get_group_unique_vals()`；
#        `anno_values_from_spots` 的"保序"是区域页口径，**不**用于这里）；
#      · 所选样本为空 ⇒ 一律 `[]`（**不**退化成"全部样本"）。
# =============================================================================
def anno_union_values(rows_by_sample, col, has_graph_by_sample=None):
    """§4.2.2 多选样本在某列上的**取值并集**（`list[str]`）

    Args:
        rows_by_sample: `{sample_id: [ann_row, …]}`（顺序 = 所选样本顺序，无意义时也无害）
        col: 分组列名；空 / `None` ⇒ `[]`
        has_graph_by_sample: `{sample_id: bool}`；仅 `col == GROUP_GRAPHED` 时起作用，
            缺省 `None` 视为"全部样本都无 graph"（**保守**，绝不默认放行）
    Returns:
        list[str]: `sorted()` 后的去重非空并集；无值 ⇒ `[]`

    ★ `col == GROUP_GRAPHED` 时 `has_graph` 为假的样本**零贡献**（连循环都不进）。
    ★ **不吞异常**：`rows_by_sample` 形态不合法（非 dict）时直接抛给调用方。
    """
    if not col:
        return []
    col = str(col)
    if not isinstance(rows_by_sample, dict) or not rows_by_sample:
        return []
    graph_map = has_graph_by_sample if isinstance(has_graph_by_sample, dict) else {}
    seen = set()
    out = []
    for sid, rows in rows_by_sample.items():
        if col == GROUP_GRAPHED and not bool(graph_map.get(sid, False)):
            # ★ 没画图/没注释值的样本对 group_graphed 并集**零贡献**（契约 §4.2.1）
            continue
        for v in anno_values_from_spots(rows, col):
            if v not in seen:
                seen.add(v)
                out.append(v)
    return sorted(out)


def participating_samples_for_col(samples, rows_by_sample, col,
                                  has_graph_by_sample=None):
    """§4.2.3 **实际参与分析/绘图的样本**（保序 = `samples` 顺序，`list[str]`）

    · `col == GROUP_GRAPHED` ⇒ 只保留 `has_graph` 为真的样本；
    · 其它列 ⇒ 保留"该列在该样本里有非空值"的样本；
    · 空 `samples` / 空 `col` ⇒ `[]`；取不到某样本的行（不在 `rows_by_sample` 里）⇒ 不参与。

    ★ 返回的**被排除**样本由调用方自行求差并写日志（§4.2.3 明令：不许静默）。
    ★ **不吞异常**：形态不合法直接抛给调用方（调用方逐样本兜底 + 留痕）。
    """
    if not samples or not col:
        return []
    col = str(col)
    if not isinstance(rows_by_sample, dict):
        rows_by_sample = {}
    graph_map = has_graph_by_sample if isinstance(has_graph_by_sample, dict) else {}
    used = []
    for sid in samples:
        rows = rows_by_sample.get(sid)
        if col == GROUP_GRAPHED:
            hit = bool(graph_map.get(sid, False))
        else:
            hit = bool(anno_values_from_spots(rows or [], col))
        if hit:
            used.append(sid)
    return used


# =============================================================================
# labels CSV 导出（表头逐字 `spot,label`）
# =============================================================================
def export_labels_csv(spots, labels, path):
    """写 `<spot>,<label>` CSV（**未覆盖写空串**）

    Returns:
        bool: 是否成功（失败原因在模块级 `LAST_EXPORT_ERROR`，便于排障）

    ★ 表头**逐字就是 `spot,label`**（契约 §13.6）——R 侧按字面读，多一个空格都算违约。
    ★ `lineterminator="\n"`：R 的 `read.csv` 能吃 CRLF，但统一成 LF 更省事，
      也避免"最后一列多一个 \\r"这种经典坑。
    ★ `newline=""`：交给 csv 模块自己管换行（不写会被 Windows 转成 \\r\\n 两次）。
    ★ 编码用 **utf-8**（区域名是自由文本，可能是中文）。
    """
    global LAST_EXPORT_ERROR
    LAST_EXPORT_ERROR = ""
    try:
        if not path:
            LAST_EXPORT_ERROR = "输出路径为空"
            return False
        if len(labels or []) != len(spots or []):
            LAST_EXPORT_ERROR = ("标签数与 spot 数不一致（%d vs %d）——拒绝写出错位的表"
                                 % (len(labels or []), len(spots or [])))
            print("[spatial_region] %s" % LAST_EXPORT_ERROR)
            return False
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(list(LABELS_CSV_HEADER))
            for idx, row in enumerate(spots or []):
                w.writerow([_spot_id(row, idx), str(labels[idx] or "")])
        return True
    except Exception as e:
        traceback.print_exc()
        LAST_EXPORT_ERROR = "%s: %s" % (type(e).__name__, e)
        print("[spatial_region] labels CSV 写出失败: %s" % LAST_EXPORT_ERROR)
        return False


# =============================================================================
# 9 个 signature 名（从列名读，**不硬编码**）
# =============================================================================
def signature_csv_path(dataset):
    if not dataset:
        return ""
    o = _out_base()
    return os.path.join(o, dataset, *SIGNATURE_CSV_REL) if o else ""


def list_signature_names(dataset):
    """从 `07_CellTypeAnno/01_cluster_signature_mean.csv` 的**列名**取 9 个 signature

    · 列名形如 `Score_MES` → 去掉 `Score_` 前缀得到 `MES`；
    · 丢掉 `cluster` 这类非 signature 列；
    · **保持文件里的列顺序**（= 契约里列的那 9 个顺序）；
    · 文件缺失/读不出 → 返回 `[]`（**不抛**；上层据此决定要不要给下拉建议）。
    """
    try:
        path = signature_csv_path(dataset)
        if not path or not os.path.isfile(path):
            return []
        with io.open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            header = next(csv.reader(f), [])
        names = []
        for col in header:
            c = str(col or "").strip().strip('"')
            if not c or c in SIGNATURE_DROP_COLS:
                continue
            if c.startswith(SIGNATURE_COL_PREFIX):
                c = c[len(SIGNATURE_COL_PREFIX):]
            if c and c not in names:
                names.append(c)
        return names
    except Exception:
        traceback.print_exc()
        return []


# =============================================================================
# 调 W3 的 R 脚本重绘该样本（subprocess 纪律与 GEA 完全一致）
# =============================================================================
def resolve_region_r_script():
    """定位 `spatial_region_render.R`（相对本文件；找不到返回 ''）"""
    p = os.path.normpath(os.path.join(_HERE, _REGION_R_SCRIPT_REL))
    return p if os.path.isfile(p) else ""


def find_rscript():
    """定位 Rscript（优先级与 GEA 一致：R_HOME → PATH → 本机兜底）"""
    rh = os.environ.get("R_HOME")
    if rh:
        for sub in (os.path.join(rh, "bin", "x64", "Rscript.exe"),
                    os.path.join(rh, "bin", "Rscript.exe"),
                    os.path.join(rh, "bin", "Rscript")):
            if os.path.isfile(sub):
                return sub
    found = shutil.which("Rscript")
    if found:
        return found
    if os.path.isfile(_DEV_RSCRIPT_FALLBACK):
        return _DEV_RSCRIPT_FALLBACK
    return "Rscript"


def stage_raw_root_ascii(dataset, sample_id, raw_root=None):
    """返回一个**全 ASCII** 的原始切片图目录（必要时把该样本的两份文件复制过去）

    Returns:
        `(dir, note)`；拿不到 → `("", 原因)`

    ## 为什么必须做这一步（本机实测发现）
      `SPATIAL_RAW_ROOT` 实测是
      `...\\空间转录组代码参考\\练习\\GSE237183`（**含中文**）。
      而非 ASCII 路径会让 R 弹**交互式目录菜单**（本会话实测过无限循环 + 1.14 GB 日志），
      所以 `render_sample_regions` **会拒绝**把非 ASCII 的 `--raw-root` 传给 R。
      ⇒ 直接传 = 被拒（退 lowres）；不传 = 也是 lowres。
      ⇒ 唯一能让 hires 真正生效的路：把该样本要用的两份文件**复制到 ASCII 暂存目录**，
        再把暂存目录当 `--raw-root` 传过去。

    ## 暂存目录结构（**契约 §15.4 已冻结**，与 W3 的候选链逐条对应）
      ```
      OUTPUT/<ds>/_region_workbench/_rawroot/
          <GSM>_<label>_tissue_hires_image.png      ← 顶层 glob（若有；GSE237183 没有）
          <GSM>_<label>_aligned_fiducials.jpg       ← 顶层 glob ★ 本数据集唯一可用的 hires
          <GSM>_<label>_detected_tissue_image.jpg   ← 顶层 glob（最后一档兜底）
          <GSM>/tissue_hires_image.png              ← 子目录（若有）
          <GSM>/tissue_lowres_image.png             ← 子目录
          <GSM>/scalefactors_json.json              ← 子目录
      ```
      R 的优选顺序（`spatial_region_render.R:398-402` 逐行核对）：
      `tissue_hires_image.* > aligned_fiducials.jpg > detected_tissue_image.jpg > lowres`

    ★ 协调者已**批准**这条路（原话："放宽非 ASCII 断言我不接受 —— 那条规矩是用事故换来的"），
      并会通知 W3：`--raw-root` **可能指向暂存目录**，别假设它一定是原始根。
    ★ 只复制，**绝不删改源**；已暂存且大小一致就跳过（不每次渲染都重拷，hires jpg 有 MB 级）。
    ★🔴 **`detected_tissue_image.jpg` 是 Space Ranger 的 QC 叠加图**（蓝色 spot 网格 +
      红色 fiducial 环都**烧在像素里**）—— 单独用它当底图会让用户误以为
      "无点图没去掉点"。所以 `aligned_fiducials.jpg`（组织干净、只有外圈红环，R 会裁掉）
      在本数据集上是**唯一可用的 hires**，必须一起暂存。
    """
    try:
        rr = str(raw_root) if raw_root is not None else raw_root_dir(dataset)
        if not rr:
            return "", "拿不到 SPATIAL_RAW_ROOT"
        if not os.path.isdir(rr):
            return "", "原始根目录不存在：%s" % rr
        if is_ascii_path(rr):
            return rr, ""                      # 本来就是 ASCII → 原样用，不复制
        if not dataset or not sample_id:
            return "", "缺 dataset/sample_id，无法暂存"
        o = _out_base()
        if not o:
            return "", "拿不到 OUT_BASE，无法建 ASCII 暂存目录"
        # 暂存目录 = OUTPUT/<ds>/_region_workbench/_rawroot（整条链都是 ASCII）
        stage = os.path.join(o, dataset, WORKBENCH_DIR, "_rawroot")
        if not is_ascii_path(stage):
            return "", "暂存目录本身含非 ASCII（无法规避）：%s" % stage
        if not os.path.isdir(stage):
            os.makedirs(stage, exist_ok=True)
        sid_dir = os.path.join(stage, str(sample_id))
        if not os.path.isdir(sid_dir):
            os.makedirs(sid_dir, exist_ok=True)

        # ★★ 暂存清单**逐条对应 W3 的候选链**（真源码 `spatial_region_render.R:398-402`）：
        #      R 的优选顺序 = tissue_hires_image.* > aligned_fiducials.jpg
        #                     > detected_tissue_image.jpg > tissue_lowres_image.png
        #    其中前三条是**顶层 glob**（`^<sid>.*…`），后一条是**子目录**
        #    （`<raw_root>/<sid>/tissue_lowres_image.png`），scalefactors 同理在子目录。
        #
        #    🔴 为什么必须把 fiducials 也暂存（W3 实测发现）：
        #      GSE237183 **没有**干净的 `tissue_hires_image.png`；而
        #      `detected_tissue_image.jpg` 是 Space Ranger 的 **QC 叠加图**
        #      —— 蓝色 spot 网格与红色 fiducial 环**烧在像素里**，
        #      直接当底图 ⇒ 用户会以为"无点图没去掉点"，其实是这张图自带的。
        #      `aligned_fiducials.jpg` 组织本身干净（只有外圈红环，R 会裁掉），
        #      所以它是这个数据集**唯一可用的 hires 底图**。
        import glob as _glob
        plan = []
        for pat in ("%s*tissue_hires_image.png" % sample_id,
                    "%s*tissue_hires_image.jpg" % sample_id,
                    "%s*tissue_hires_image.jpeg" % sample_id,
                    "%s*aligned_fiducials.jpg" % sample_id,
                    "%s*detected_tissue_image.jpg" % sample_id):
            plan.append(("top", pat, stage))                 # 顶层 glob → 顶层
        for fn in ("tissue_hires_image.png", "tissue_lowres_image.png",
                   "scalefactors_json.json"):
            plan.append(("sub", os.path.join(rr, str(sample_id), fn), sid_dir))

        copied, staged, missing = [], [], []
        for kind, src_spec, dst_dir in plan:
            try:
                if kind == "top":
                    hits = _glob.glob(os.path.join(rr, src_spec))
                    src = hits[0] if hits else ""      # R 侧也只取第一个命中
                else:
                    src = src_spec if os.path.isfile(src_spec) else ""
                if not src:
                    missing.append(os.path.basename(src_spec))
                    continue
                dst = os.path.join(dst_dir, os.path.basename(src))
                if os.path.abspath(src) == os.path.abspath(dst) or _same_size(src, dst):
                    staged.append(os.path.basename(dst))   # 已暂存（或本来就是同一个文件）
                    continue
                shutil.copy2(src, dst)
                copied.append(dst)
                staged.append(os.path.basename(dst))
            except Exception as e:
                traceback.print_exc()
                missing.append("%s（%s: %s）" % (os.path.basename(src_spec),
                                                type(e).__name__, e))
        note = ("原始根目录含非 ASCII（R 会弹交互式目录菜单）→ 已把该样本的底图候选与 "
                "scalefactors 暂存到 ASCII 目录：%s（本次新拷 %d 个，已在位 %d 个）"
                % (stage, len(copied), len(staged) - len(copied)))
        note += "；已备齐：%s" % (", ".join(staged) or "（无）")
        if missing:
            # ★ 缺哪个候选**如实列出来**（不影响 R 继续往下一档选，但用户/我们排障时要知道）
            note += "；⚠ 源目录里没有：%s" % ", ".join(missing)
        print("[spatial_region] %s" % note)
        return stage, note
    except Exception as e:
        traceback.print_exc()
        return "", "暂存原始根目录时异常：%s: %s" % (type(e).__name__, e)


def _same_size(a, b):
    """两个文件大小一致即认为"已暂存过"（避免每次渲染重拷 MB 级底图）"""
    try:
        return os.path.isfile(b) and os.path.getsize(a) == os.path.getsize(b)
    except Exception:
        return False


def raw_root_dir(dataset=None, out_dir=None):
    """原始切片图根目录 —— **按数据集解析**（★ 2026-09-25 新增）—— **必须显式传给 R**

    ★ 为什么必须传（协调者/W3 定）：R 侧要 glob `<GSM>*_detected_tissue_image.jpg`
      （hires，1799×2000）并逐样本读 `<GSM>/scalefactors_json.json` 的
      `tissue_hires_scalef`（各样本 **0.1289~0.5270**，硬编码必错）。
      不传 ⇒ R 只能退 lowres（600×540），放大到 2400×2100 会发虚，
      **正好毁掉用户"更美观"的诉求**。
    ★ 取不到就返回 `""`，调用方**不传 `--raw-root`**（R 侧自己退 lowres）并留痕。

    ★ 2026-09-25 修订：原实现只返回写死的 `import_config.SPATIAL_RAW_ROOT`
      （= GSE237183 那一个目录）。装入第二个数据集（**Dryad_UKF**，样本名 `UKF*`）后，
      若仍返回 GSE237183 的根，区域页会去那里找 `UKF*/…` → 找不到 → 底图缺失。
      解析顺序：
        ① 有 `dataset` 时，读 `appdata/spatial_main/<dataset>.manifest.json` 的
           `source.raw_root`（契约 §1/§2 规定该字段**相对 BASE_DIR**），目录存在就用它；
        ② `dataset` 为空但有 `out_dir`（`OUTPUT/<数据集>/…`）时，从父目录名反推数据集再走 ①；
        ③ 都不成 → 回落 `import_config.SPATIAL_RAW_ROOT`（**GSE237183 行为逐字不变**：
           它的 manifest 里 raw_root 就是同一个路径）。
    """
    ds = str(dataset or "").strip()
    if not ds and out_dir:
        try:
            ds = os.path.basename(os.path.dirname(os.path.abspath(out_dir)))
        except Exception:
            traceback.print_exc()
            ds = ""
    try:
        from script.utils_layer.import_config import (
            SPATIAL_RAW_ROOT, SPATIAL_SCAN_DATA_PATH, BASE_DIR)
        # ① 按数据集读 manifest 的 source.raw_root
        if ds:
            try:
                mp = os.path.join(SPATIAL_SCAN_DATA_PATH, ds + ".manifest.json")
                if os.path.isfile(mp):
                    with open(mp, "r", encoding="utf-8") as f:
                        m = json.load(f)
                    rel = str(((m.get("source") or {}).get("raw_root")) or "").strip()
                    if rel:
                        p = os.path.join(BASE_DIR, rel)
                        if os.path.isdir(p):
                            return p
                        print("[spatial_region] manifest 的 source.raw_root 不是目录，"
                              "回落 SPATIAL_RAW_ROOT：%s" % p)
            except Exception:
                traceback.print_exc()
        return str(SPATIAL_RAW_ROOT or "")
    except Exception:
        traceback.print_exc()
        try:
            from script.utils_layer.import_config import APPDATA_PATH
            # 兜底猜测（仅当 import_config 没导出该名字时；留痕在调用方做）
            return os.path.join(APPDATA_PATH, "spatial_raw")
        except Exception:
            traceback.print_exc()
            return ""


def spots_path_from_out_dir(out_dir):
    """从 `out_dir`（惯例是 `OUTPUT/<ds>/09_RegionOverride`）反推 `spots.csv` 路径

    ★ 为什么需要：`render_sample_regions()` 收的是 `out_dir` 而**不是 `dataset`**，
      而 §15.4b 之后 `--spots` 是**必填**。调用方显式传 `spots_csv` 是首选；
      没传时用这条**约定推导**兜底（`09_RegionOverride` 的上一级就是数据集目录，
      目录结构是我们自己定的），比"直接报错"对调用方更友好。
    ★ 推不出来（或推出来的文件不存在）就返回 `""`，由调用方给出明确报错。
    """
    try:
        if not out_dir:
            return ""
        ds_dir = os.path.dirname(os.path.abspath(out_dir))       # OUTPUT/<ds>
        if not ds_dir:
            return ""
        cand = os.path.join(ds_dir, WORKBENCH_DIR, SPOTS_CSV_NAME)
        return cand if os.path.isfile(cand) else ""
    except Exception:
        traceback.print_exc()
        return ""


def render_sample_regions(rds_path, labels_csv, sample_id, out_dir, timeout=600,
                          outline_json=None, no_spots=False, raw_root=None,
                          spots_csv=None):
    """调 `spatial_region_render.R --rds --labels --spots --sample --out-dir
    [--outline] [--no-spots] [--raw-root]`

    Returns:
        (ok: bool, result: dict, error: str)
        · result 至少含 `png`/`pdf`（**带点**那一张，键名归一化）；
          若 R 出了不带点那张，另含 `nospot_png`/`nospot_pdf`；
          底图与透明度摘要原样透传：`base_image`（`hires`/`lowres`）/`base_fit`/
          `base_image_note`/`spots_hidden`/`nospot_ok`/`encoding_ok`；
        · **任何失败都返回 (False, {}, 原因)，绝不抛**。

    ## ★ §15.4b：`--spots` 是**必填**
      R 改成"自建 ggplot2 绘图"后要**自己读原始坐标**，所以必须给它 `spots.csv`
      （协调者实测：不传 ⇒ R 直接失败 ⇒ 一个摘要字段都解析不到）。
      取值优先级：显式 `spots_csv` → 按 `out_dir` 推导（`spots_path_from_out_dir`）。
      两者都拿不到 ⇒ **明确报错**（而不是让 R 那边报一个难懂的错）。
      与 `--labels` 一样，**做全 ASCII 断言**。

    ## 其余可选参数
      · `outline_json` → `--outline <path>`（轮廓 + 标签 JSON）；
      · `no_spots=True` → `--no-spots` ⇒ R **一次调用出两张**
        （`Spatial_<样本>` 带点 + `SpatialNoSpots_<样本>` 不带点）；
      · `raw_root` → `--raw-root <dir>`，默认自动取 `import_config.SPATIAL_RAW_ROOT`。

    ★ 参数校验全部走返回值：非 ASCII 路径**在 Python 侧就拒**（非 ASCII 会让 R 弹
      交互式目录菜单，本会话实测过无限循环事故）；
      `stdin=DEVNULL` + `timeout`：绝不给 R 任何交互机会。
    """
    try:
        if not rds_path or not isinstance(rds_path, str):
            return False, {}, "rds_path 为空"
        if not labels_csv or not isinstance(labels_csv, str):
            return False, {}, "labels_csv 为空"
        if not sample_id or not isinstance(sample_id, str):
            return False, {}, "sample_id 为空"
        if not out_dir or not isinstance(out_dir, str):
            return False, {}, "out_dir 为空"
        rds_path = os.path.abspath(rds_path)
        labels_csv = os.path.abspath(labels_csv)
        out_dir = os.path.abspath(out_dir)
        outline_json = os.path.abspath(outline_json) if outline_json else ""
        # ★ §15.4b：`--spots` 必填 —— 显式参数优先，其次按 out_dir 推导
        spots_csv = (os.path.abspath(spots_csv) if spots_csv
                     else spots_path_from_out_dir(out_dir))
        if not spots_csv or not os.path.isfile(spots_csv):
            return False, {}, ("spots.csv 不存在或未提供（§15.4b 之后 `--spots` 是必填）：%s"
                               % (spots_csv or "（空）"))
        # ★ 2026-09-25：按数据集解析（本函数没有 dataset 参数，从 out_dir=OUTPUT/<ds>/… 反推）
        rr = str(raw_root) if raw_root is not None else raw_root_dir(out_dir=out_dir)
        # 底图根目录：**存在才传**（不存在时 R 会自己退 lowres；这里留痕说明）
        raw_note = ""
        if rr:
            rr_abs = os.path.abspath(rr)
            if not is_ascii_path(rr_abs):
                raw_note = "SPATIAL_RAW_ROOT 含非 ASCII，已拒绝传给 R：%s" % rr_abs
                print("[spatial_region] %s" % raw_note)
                rr = ""
            elif not os.path.isdir(rr_abs):
                raw_note = "SPATIAL_RAW_ROOT 不是目录，已不传 --raw-root：%s" % rr_abs
                print("[spatial_region] %s" % raw_note)
                rr = ""
            else:
                rr = rr_abs
        else:
            raw_note = "拿不到 SPATIAL_RAW_ROOT，未传 --raw-root（R 会退回 lowres 底图）"
            print("[spatial_region] %s" % raw_note)
        for label, p in (("rds_path", rds_path), ("labels_csv", labels_csv),
                         ("spots_csv", spots_csv),
                         ("out_dir", out_dir), ("sample_id", sample_id),
                         ("outline_json", outline_json), ("raw_root", rr)):
            if p and not is_ascii_path(p):
                return False, {}, "%s 含非 ASCII 字符，已拒绝：%s" % (label, p)
        if not os.path.isfile(rds_path):
            return False, {}, "成品 .rds 不存在：%s" % rds_path
        if not os.path.isfile(labels_csv):
            return False, {}, "labels CSV 不存在：%s" % labels_csv
        if outline_json and not os.path.isfile(outline_json):
            # 轮廓缺失**不致命**（图照出，只是没轮廓层）—— 但必须留痕，绝不静默
            print("[spatial_region] 轮廓 JSON 不存在，将不传 --outline：%s" % outline_json)
            outline_json = ""
        script = resolve_region_r_script()
        if not script:
            return False, {}, ("找不到 R 脚本 spatial_region_render.R（期望位置：%s）"
                               % os.path.normpath(os.path.join(_HERE, _REGION_R_SCRIPT_REL)))
        try:
            timeout_val = int(timeout)
        except (TypeError, ValueError):
            return False, {}, "timeout 不是整数：%r" % (timeout,)
        if timeout_val <= 0:
            return False, {}, "timeout 必须为正数：%d" % timeout_val
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            return False, {}, "无法创建输出目录：%s（%s）" % (out_dir, e)

        cmd = [find_rscript(), script, "--rds", rds_path, "--labels", labels_csv,
               "--spots", spots_csv,        # ★ §15.4b 必填：R 自建绘图要自己读坐标
               "--sample", sample_id, "--out-dir", out_dir]
        if outline_json:
            cmd += ["--outline", outline_json]
        if no_spots:
            cmd += ["--no-spots"]
        if rr:
            cmd += ["--raw-root", rr]
        try:
            proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=timeout_val, cwd=out_dir)
        except subprocess.TimeoutExpired:
            return False, {}, "区域重绘超时（>%ds）：%s" % (timeout_val, sample_id)
        except OSError as e:
            return False, {}, "无法启动 R 子进程（%s）：%s" % (cmd[0], e)

        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        result = _parse_result_line(stdout, RESULT_MARKER)
        if result is None:
            reason = (stderr or stdout or "").strip()
            if len(reason) > 800:
                reason = reason[-800:]
            return False, {}, ("R 子进程未产出可解析结果（returncode=%s）：%s"
                               % (proc.returncode, reason or "无任何输出"))
        if not result.get("ok"):
            return False, {}, "R 报告失败：%s" % result.get("error", "未知原因")
        # ★ 字段名归一化：带点那张接受 `out_png`/`png`；不带点那张接受
        #   `out_nospot_png`/`nospot_png`/`out_nospots_png`（**多种键名都容错**，
        #   别再犯"猜一个键名就写死"的错）。
        png = str(result.get("out_png") or result.get("png")
                  or os.path.join(out_dir, "Spatial_%s.png" % sample_id))
        pdf = str(result.get("out_pdf") or result.get("pdf")
                  or os.path.join(out_dir, "Spatial_%s.pdf" % sample_id))
        result["png"], result["pdf"] = png, pdf
        result["out_png"], result["out_pdf"] = png, pdf
        ns_png = (result.get("out_nospot_png") or result.get("nospot_png")
                  or result.get("out_nospots_png"))
        ns_pdf = (result.get("out_nospot_pdf") or result.get("nospot_pdf")
                  or result.get("out_nospots_pdf"))
        if ns_png or result.get("nospot_ok") is not None or no_spots:
            # ⚠ 这里 `out_dir` **已经就是** override 目录（调用方传进来的），
            #   所以直接拼文件名，**不能**再调 `nospot_output_paths()`（它会再加一层）。
            d_png = os.path.join(out_dir, "%s_%s.png" % (NOSPOT_PREFIX, sample_id))
            d_pdf = os.path.join(out_dir, "%s_%s.pdf" % (NOSPOT_PREFIX, sample_id))
            ns_png = str(ns_png or d_png)
            ns_pdf = str(ns_pdf or d_pdf)
        if ns_png:
            result["nospot_png"], result["nospot_pdf"] = str(ns_png), str(ns_pdf or "")
            result["out_nospot_png"], result["out_nospot_pdf"] = str(ns_png), str(ns_pdf or "")
        result["outline_json"] = outline_json
        result["no_spots_requested"] = bool(no_spots)
        # ★ `raw_root` **不要覆盖** R 自己报的值：R 报的是"它实际用了哪个根目录"
        #   （我这里只是"我传了什么"）。我原来直接赋值会把权威值盖掉 ——
        #   万一我没传（非 ASCII 被拒）而 R 从环境变量拿到了，就会显示错的信息。
        result.setdefault("raw_root", rr)
        result["raw_root_arg"] = rr
        result["spots_csv_arg"] = spots_csv     # 便于核对"R 读的是哪一份坐标"
        if raw_note:
            result["raw_root_note"] = raw_note
        # ★ §15.4b 的新摘要字段：**原样透传**（R 有就带，没有就不造）——
        #   这里只是把它们显式列出来，避免以后有人以为要"挑字段"。
        #   `base_image`/`base_fit`/`base_image_note`（底图等级与贴合方式）、
        #   `spots_hidden`（无点图里藏掉的 spot 数）、`nospot_ok`（不带点图成功与否）、
        #   `encoding_ok`（中文字体是否生效）。
        result["r_script"] = script
        result["r_returncode"] = proc.returncode
        if stderr:
            result["stderr_tail"] = stderr[-800:]
        return True, result, ""
    except Exception as e:
        traceback.print_exc()
        return False, {}, "调用区域重绘时异常：%s: %s" % (type(e).__name__, e)


# ★ W3 的实际标记（协调者实测纠正）：**不是** `##SPATIAL_REGION_RESULT##`。
#    我原来照 GEA 的形状猜了一个，结果一个字段都解析不到（R 明明 returncode=0）。
#    留这条注释当"猜接口"的教训：**子进程输出标记必须先实测再写死**。
RESULT_MARKER = "##SPATIAL_REGION_RENDER##"
# dump 脚本的标记（同一套纪律：**读 W3 的源码确认**，不是猜）
DUMP_RESULT_MARKER = "##SPATIAL_REGION_DUMP##"


def _parse_result_line(stdout, marker=RESULT_MARKER):
    """从子进程 stdout 里取结果 JSON —— **两条路都试**

    1. **带标记**行 `<marker>{...}`（主路径，取最后一条）；
    2. **整行裸 JSON**（兜底）：两个 R 脚本都明确**打印两行**（一行带标记 + 一行裸 JSON），
       就是为了两种调用方都能用。标记那条万一格式变了，还有这条。

    Returns: dict 或 None（**绝不抛**）
    """
    if stdout is None:
        return None
    marked = None
    last_json = None
    for line in stdout.splitlines():
        s = (line or "").strip()
        if not s:
            continue
        idx = s.find(marker)
        if idx >= 0:
            payload = s[idx + len(marker):].strip()
            if payload:
                try:
                    obj = json.loads(payload)
                    if isinstance(obj, dict):
                        marked = obj                 # 取**最后一条**带标记的
                except ValueError:
                    pass
            continue
        # 裸 JSON 兜底：只认"整行就是一个对象"，避免把日志里的裸 `{` 误当结果
        if s.startswith("{") and s.endswith("}"):
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    last_json = obj
            except ValueError:
                pass
    if isinstance(marked, dict):
        return marked
    return last_json if isinstance(last_json, dict) else None


def resolve_dump_r_script():
    """定位 `spatial_region_dump.R`（相对本文件；找不到返回 ''）"""
    p = os.path.normpath(os.path.join(_HERE, _DUMP_R_SCRIPT_REL))
    return p if os.path.isfile(p) else ""


def dump_spots(dataset, rds_path=None, timeout=600):
    """**自动生成坐标表** `_region_workbench/spots.csv`（契约 §14.2 冻结签名）

    Returns:
        (ok: bool, result: dict, error: str) —— 与 `render_sample_regions` / `run_gene_expression` 同形。
        result 至少含 `spots_csv` / `rows` / `samples` / `unmatched`
        （R 侧字段名是 `out`，这里**映射**成契约要求的 `spots_csv`，两个键都留）。

    ## 为什么这个函数是"M4 生产可用"的关键
      之前 `spots.csv` 是**手工跑 R** 生成的 ⇒ 换数据集 / 清缓存 / 换机器后，
      页面只会显示"尚未导出坐标表"，功能直接不可用（§14.1 缺口 1）。
      现在 App 自己会生成它。

    ## 纪律（与 render_sample_regions 完全一致，两处都只在本层）
      · 全 ASCII 路径在 Python 侧就断言（非 ASCII 会让 R 弹交互式目录菜单）；
      · `stdin=DEVNULL` + 超时 + `cwd` 也设在 ASCII 目录；
      · `Rscript` 走绝对路径（R_HOME → PATH → 本机兜底）；
      · **绝不抛**，一切失败走返回值。

    ## §14.5：`--ann` **可选**
      逐 spot 细胞注释 CSV 不存在时**不传 `--ann`**（W3 已把它改成可选）：
      仍出坐标，`cell_type` 列写空串。`result["ann_used"]` 会写明到底传没传，
      上层据此在日志里说明"本数据集没有细胞注释，画布只显示点、不着色"。
    """
    try:
        if not dataset or not isinstance(dataset, str):
            return False, {}, "dataset 为空"
        out_path = spots_path_for(dataset)
        if not out_path:
            return False, {}, "无法解析坐标表输出路径（OUTPUT 不可用）"
        # rds：调用方给了就用它，否则按数据集名在成品目录里找
        rds = str(rds_path or "")
        if not rds:
            d = _spatial_main_dir()
            rds = os.path.join(d, "%s.rds" % dataset) if d else ""
        rds = os.path.abspath(rds) if rds else ""
        out_path = os.path.abspath(out_path)
        ann = ann_csv_path_for(dataset)
        ann = os.path.abspath(ann) if (ann and os.path.isfile(ann)) else ""

        if not is_ascii_path(out_path):
            return False, {}, "坐标表输出路径含非 ASCII 字符，已拒绝：%s" % out_path
        if not rds or not is_ascii_path(rds):
            return False, {}, "rds 路径为空或含非 ASCII 字符，已拒绝：%s" % (rds or "（空）")
        if not os.path.isfile(rds):
            return False, {}, "成品 .rds 不存在：%s" % rds
        if ann and not is_ascii_path(ann):
            return False, {}, "细胞注释 CSV 路径含非 ASCII 字符，已拒绝：%s" % ann

        script = resolve_dump_r_script()
        if not script:
            return False, {}, ("找不到 R 脚本 spatial_region_dump.R（期望位置：%s）"
                               % os.path.normpath(os.path.join(_HERE, _DUMP_R_SCRIPT_REL)))
        try:
            timeout_val = int(timeout)
        except (TypeError, ValueError):
            return False, {}, "timeout 不是整数：%r" % (timeout,)
        if timeout_val <= 0:
            return False, {}, "timeout 必须为正数：%d" % timeout_val
        work_dir = os.path.dirname(out_path)
        try:
            os.makedirs(work_dir, exist_ok=True)
        except OSError as e:
            return False, {}, "无法创建输出目录：%s（%s）" % (work_dir, e)
        if not is_ascii_path(work_dir):
            return False, {}, "输出目录含非 ASCII 字符，已拒绝：%s" % work_dir

        cmd = [find_rscript(), script, "--rds", rds]
        if ann:
            cmd += ["--ann", ann]
        cmd += ["--out", out_path]
        try:
            proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=timeout_val, cwd=work_dir)
        except subprocess.TimeoutExpired:
            return False, {}, "导出坐标表超时（>%ds）" % timeout_val
        except OSError as e:
            return False, {}, "无法启动 R 子进程（%s）：%s" % (cmd[0], e)

        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        result = _parse_result_line(stdout, DUMP_RESULT_MARKER)
        if result is None:
            reason = (stderr or stdout or "").strip()
            if len(reason) > 800:
                reason = reason[-800:]
            return False, {}, ("R 子进程未产出可解析结果（returncode=%s）：%s"
                               % (proc.returncode, reason or "无任何输出"))
        if not result.get("ok"):
            return False, {}, "R 报告失败：%s" % result.get("error", "未知原因")
        # ★ R 侧字段名是 `out`；契约 §14.2 要 `spots_csv` ⇒ 两个键都写，谁读都对
        csv_path = str(result.get("spots_csv") or result.get("out") or out_path)
        result["spots_csv"] = csv_path
        result["out"] = csv_path
        result["ann_used"] = ann
        result.setdefault("rows", 0)
        result.setdefault("samples", 0)
        result.setdefault("unmatched", 0)
        result["r_script"] = script
        result["r_returncode"] = proc.returncode
        if stderr:
            result["stderr_tail"] = stderr[-800:]
        return True, result, ""
    except Exception as e:
        traceback.print_exc()
        return False, {}, "导出坐标表时异常：%s: %s" % (type(e).__name__, e)


def _decode(b):
    """子进程输出解码（本机 R 的 console 编码可能是 GBK，逐级退化，绝不因编码失败）"""
    if b is None:
        return ""
    if isinstance(b, str):
        return b
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return b.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return b.decode("utf-8", errors="replace")


def labels_csv_path_for(dataset, sample_id):
    """labels CSV 的落地路径（放在 workbench 里，**保证 ASCII**，便于排障与重跑）

    ★ 为什么不用系统临时目录：契约写的是 `<tmp>/region_labels.csv`，但把中间产物
      放在数据集目录下有两个实际好处——① 出问题时用户/我们能直接看到它；
      ② 它是**全 ASCII**（临时目录名偶尔带中文用户名）。两者都不违反契约。
    """
    if not dataset or not sample_id:
        return ""
    o = _out_base()
    if not o:
        return ""
    return os.path.join(o, dataset, WORKBENCH_DIR, "region_labels_%s.csv" % sample_id)


def make_probe_labels_csv(dataset, sample_id):
    """写一个"仅表头"的 labels CSV（用于 W3 脚本尚未就位时自检/占位）"""
    try:
        p = labels_csv_path_for(dataset, sample_id)
        if not p:
            return ""
        with io.open(p, "w", encoding="utf-8", newline="") as f:
            f.write(",".join(LABELS_CSV_HEADER) + "\n")
        return p
    except Exception:
        traceback.print_exc()
        return ""


def temp_dir_fallback():
    """系统临时目录（仅在拿不到 OUT_BASE 时兜底用）"""
    try:
        return tempfile.gettempdir()
    except Exception:
        return ""
