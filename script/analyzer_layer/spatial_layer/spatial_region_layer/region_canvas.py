# -*- coding: utf-8 -*-
"""
绘制区域画布控件 - 空转「绘制区域」功能（M4）的自绘散点画布

为什么自绘（契约 §13.2）：
  图集 PNG **不能**当画布 —— 各样本坐标尺度差异极大（GSM7596588 的 x 到 11087，
  GSM7596605 只到 3319），且 PNG 里混着标题/图例/分面，**没有干净的坐标轴映射**。
  ⇒ 必须自渲染散点，并把坐标轴范围锁死在该样本数据范围内、保持等比，
    使 **屏幕像素 ↔ 数据坐标精确可逆**。

★ 本文件**不读任何数据/文件**：散点、区域、底图都由 bind 传入（gate H 同样适用）。

坐标系约定：
  - 数据坐标 = 该样本的 spot 原始坐标（与 `tissue_positions_list.csv` 同尺度）；
  - **y 轴不翻转**（数据 y 向下增大），与组织底图的行方向一致，便于底图/散点/多边形对齐；
  - `screen = (data - center) * scale + widget_center + pan`，`scale = base_scale * zoom`；
  - `base_scale = min(w/dx, h/dy)` ⇒ **x/y 同倍率（等比）**，圈不会变形。
"""

from script.utils_layer.import_config import *
# ★ 显式 import：以下 Qt 类不在 import_config 的导出清单里（本会话已因此踩坑 3 次）
from PyQt5.QtGui import QPolygonF, QPainterPath
from PyQt5.QtCore import QPointF
# ★ 同样必须显式 import：`json` / `glob` 也不在 import_config 的导出清单里
#   （实测该文件只 import 了 os/sys/traceback/tempfile/shutil/importlib/uuid/itertools/random …）
import json
import glob
import copy
# ★ 显式 import（别依赖 import_config 的导出清单）：本文件新增的容错分支都要留痕
import traceback


# ======================================================================
# ★ 2026-09-23 契约 `_d_spec_select_mode.md` §2：「选择模式」的模式名与容差（冻结）
# ----------------------------------------------------------------------
# · `SELECT_MODE` = **正好** `"select"`（与 bind 的 `EDIT_MODE_SELECT` 冻结一致）；
#   画布内部一律比这个常量，**不 import bind**（画布与 bind 之间只靠信号/接口）。
# · 两个屏幕容差 = 既有命中函数的默认值（`_anchor_hit(tol=7.0)` / `_edge_at(tol=12.0)`），
#   §3.1 要求"沿用画布既有 tol"，这里只是给"屏幕 → 数据"换算一个具名来源，
#   **不改那两个函数的签名与默认值**（契约 §6.4）。
# ======================================================================
SELECT_MODE = "select"
ANCHOR_TOL_SCREEN = 7.0
EDGE_TOL_SCREEN = 12.0
# 顶点拖动"坐标确实变了"的判定阈值（数据单位；纯浮点噪声不算变化）
VERTEX_MOVE_EPS = 1e-9

# ★ 主题色读取（画布**只读主题 token**、不硬编码颜色）：
#   读不到（或 gui_styles 不可用）时返回空 dict，画布用内置兜底色继续画，绝不抛。
try:
    from script.utils_layer.gui_styles import get_mod_styles as _get_mod_styles
except Exception:                                   # pragma: no cover
    _get_mod_styles = None


# ======================================================================
# ★ 2026-09-23 追加规格 v9.1（`_d_spec_select_mode.md` §11）：
#   **可见区域（`visible` 层）的圆角缺省 = 12**（普通区域 / 隐形区域 `mask` 仍是 0）
# ----------------------------------------------------------------------
# · 单一真相源在分析层：W3 的 `spatial_region_analysis.DEFAULT_VISIBLE_CORNER_RADIUS_PX`
#   （**必须同样是 12** —— 两处互相指向同一判据）；拿不到就用本文件的 12 兜底，
#   画布绝不因此抛（`getattr` 取，import 失败也只留痕）。
# · ⛔ 本常量**只**作用于可见层：① 新建可见区域时的缺省写入；② 渲染读数的缺省回填。
#   `set_active_corner_radius` / `active_corner_radius` 的签名与既有语义**不受影响**。
# ======================================================================
CORNER_RADIUS_VISIBLE_DEFAULT = 12
try:
    from script.analyzer_layer.spatial_layer.spatial_region_layer import (
        spatial_region_analysis as _SREG_CR)
    _ANALYSIS_VISIBLE_CR = getattr(_SREG_CR, "DEFAULT_VISIBLE_CORNER_RADIUS_PX", None)
except Exception:
    traceback.print_exc()
    print("[RegionCanvas] ⚠ 无法读取 analysis 层的可见层圆角缺省 ⇒ "
          "用本文件的 12 兜底（两处本就要求一致）")
    _ANALYSIS_VISIBLE_CR = None
if _ANALYSIS_VISIBLE_CR is not None:
    try:
        CORNER_RADIUS_VISIBLE_DEFAULT = int(_ANALYSIS_VISIBLE_CR)
    except (TypeError, ValueError):
        traceback.print_exc()
        print("[RegionCanvas] ⚠ analysis 层的可见层圆角缺省不是整数（%r）⇒ "
              "用本文件的 12 兜底" % (_ANALYSIS_VISIBLE_CR,))


# ======================================================================
# ★ v9.2 追加规格（2026-09-23）用户需求：
#   **可见区域（`visible` 层）的"默认区域颜色" = 白**
#   （普通区域 / 隐形区域 `mask` 仍是用户在调色板选的 `self._active_color`，行为不变）
# ----------------------------------------------------------------------
# · ★ 写法**完全镜像上面那条可见层圆角缺省规则**
#   （见 `CORNER_RADIUS_VISIBLE_DEFAULT`，v9.1 §11）：同样是"单一真相源在分析层 +
#   模块级 try/except import + `getattr` 取 + 本文件兜底 + 绝不抛"。
# · 单一真相源在分析层：W3 的 `spatial_region_analysis.DEFAULT_VISIBLE_REGION_COLOR`
#   （**必须同样是 `"#FFFFFF"`** —— 两处互相指向同一判据）；拿不到就用本文件的
#   `"#FFFFFF"` 兜底，画布绝不因此抛（`getattr` 取，import 失败也只留痕）。
# · ⛔ 本常量**只**作用于"新建可见区域块时，用户没改过调色板颜色"这一条：
#   ① 用户真调过颜色（`self._active_color` ≠ 本文件初始默认色 `"#FF6B35"`）⇒ **用用户的值**；
#   ② 普通区域 / mask ⇒ **行为完全不变**（仍一律 `self._active_color`）；
#   ③ 渲染侧**不动**（可见层的画布样式本就是主题 token；读 `region["color"]` 是
#      隐形区域 / 普通区域的口径，改了会连带 mask 与普通区域）。
#   `set_active_style` / `_active_color` 的签名与既有语义**不受影响**。
# · ⚠ 已知限制（**与圆角那条完全相同**）：调色板停在默认橙 `"#FF6B35"` 与"用户压根
#   没设过色"在**新建**时不可区分 ⇒ 新建可见区域一律写白 `"#FFFFFF"`；契约已如实登记。
#   （可见层颜色的**渲染读数回填**在分析层 `DEFAULT_VISIBLE_REGION_COLOR` 那条，
#     判据与 `_ANALYSIS_VISIBLE_CR` 同款 —— 本文件本轮只负责"新建块的缺省写入"。）
# ======================================================================
REGION_COLOR_VISIBLE_DEFAULT = "#FFFFFF"
try:
    from script.analyzer_layer.spatial_layer.spatial_region_layer import (
        spatial_region_analysis as _SREG_COLOR)
    _ANALYSIS_VISIBLE_COLOR = getattr(_SREG_COLOR, "DEFAULT_VISIBLE_REGION_COLOR", None)
except Exception:
    traceback.print_exc()
    print("[RegionCanvas] ⚠ 无法读取 analysis 层的可见层默认区域颜色 ⇒ "
          "用本文件的 '#FFFFFF' 兜底（两处本就要求一致）")
    _ANALYSIS_VISIBLE_COLOR = None
if _ANALYSIS_VISIBLE_COLOR is not None:
    try:
        REGION_COLOR_VISIBLE_DEFAULT = str(_ANALYSIS_VISIBLE_COLOR)
    except Exception:
        traceback.print_exc()
        print("[RegionCanvas] ⚠ analysis 层的可见层默认区域颜色无法转成字符串（%r）⇒ "
              "用本文件的 '#FFFFFF' 兜底" % (_ANALYSIS_VISIBLE_COLOR,))

# ★ "用户到底改没改过颜色"的**唯一比较基准** = `__init__` 里 `self._active_color` 的
#   初始值（原字面量 `"#FF6B35"`，这里抽成常量以便"判据只有一处"）。
#   ⛔ 不改 `_active_color` 的初值、不改 `set_active_style` 的签名与语义。
ACTIVE_COLOR_INITIAL_DEFAULT = "#FF6B35"


# ======================================================================
# 区域列表的独立副本（契约 §13.9：入口/出口都**不得**与调用方共享可变对象）
# ----------------------------------------------------------------------
# 🔴 曾经的缺陷：`set_regions` 只 `list(regions or [])` 拷了外层 list，
#   里面每个 dict 仍是 bind 侧 `regions_data` 的**同一个对象** ⇒ bind 之后
#   改名/改色/删除会穿透污染画布内部状态（画布与 bind 静默分叉）。
#   `get_regions()` 出口虽有拷贝，也挡不住"外部改了、里面跟着变"。
# ★ 入口与出口**共用本函数**，保证两侧对称。
# ======================================================================
def copy_regions(regions):
    """区域列表的独立副本（优先 `copy.deepcopy`）。

    · 不可拷贝的怪异对象 → 退化为「逐条浅拷 + 逐点复制」，**绝不抛**
      （画布不能因为 bind 多塞了一个字段就崩）；
    · 点统一规整成 `list`（与历史行为一致；deepcopy 可能保留调用方的 tuple）。
    """
    try:
        copied = copy.deepcopy(list(regions or []))
    except Exception:
        copied = []
        for r in (regions or []):
            try:
                item = dict(r or {})
            except Exception:
                item = {}
            try:
                item["points"] = [list(p) for p in (item.get("points") or [])]
            except Exception:
                item["points"] = []
            copied.append(item)
        return copied
    for r in copied:
        if isinstance(r, dict):
            try:
                r["points"] = [list(p) for p in (r.get("points") or [])]
            except Exception:
                r["points"] = []
    return copied


# ======================================================================
# 自动隐藏边的规则来源（契约 §15.4：规则在 W2 的 analysis 层，画布只消费）
# ----------------------------------------------------------------------
# ★ 单一真相源：画布**不**重写"哪条边跑到图外"的判定，只懒加载 W2 的
#   `spatial_region_analysis.auto_hidden_edge_indices`；W2 还没落地时返回 None，
#   绝不抛。
# ⛔⛔ **画布已不再使用它**（裁定"所见即所得"）：用户删掉了"出界不画"那套自动规则，
#   导出侧不再判出界 ⇒ 画布若还按它隐藏，就会出现"画布没这条边、出图却有"。
#   本模块保留 `_auto_hidden_edge_fn` / `_auto_hidden_for` 仅为不引入清理风险
#   （画布内已无调用方；W2 的 analysis 函数本体原样保留、不受影响）。
# ======================================================================
_AUTO_HIDDEN_FN = None
_AUTO_HIDDEN_PROBED = False


def _auto_hidden_edge_fn():
    """懒加载并缓存 W2 的 `auto_hidden_edge_indices`；拿不到 → None

    ⛔ 画布已不再调用（见本段顶部说明）。
    """
    global _AUTO_HIDDEN_FN, _AUTO_HIDDEN_PROBED
    if _AUTO_HIDDEN_PROBED:
        return _AUTO_HIDDEN_FN
    _AUTO_HIDDEN_PROBED = True
    try:
        from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as _SREG
        fn = getattr(_SREG, "auto_hidden_edge_indices", None)
        if callable(fn):
            _AUTO_HIDDEN_FN = fn
    except Exception:
        _AUTO_HIDDEN_FN = None
    return _AUTO_HIDDEN_FN


# ======================================================================
# 「可见区域」范围层：**哪些普通区域该画虚线边界**（规则在 W2 的 analysis 层）
# ----------------------------------------------------------------------
# ★ 用户裁定（2026-09）："可见区域"是**自己再画一套多边形当范围层**；画布上
#   **所有被可见区域罩住的区域**都画虚线轮廓；成图再与隐形区域取交集。
# ★ 单一真相源：画布**不自己写一份"罩住"判定**（那是第二份真相源），只懒加载
#   W2 的 `spatial_region_analysis.canvas_visible_region_indices(regions, spots)`。
# ★ W2 还没交付时返回 `None` ⇒ 画布按**"全画"**（= 老行为）并**留痕**，绝不抛。
# ======================================================================
_CANVAS_VISIBLE_FN = None
_CANVAS_VISIBLE_PROBED = False
_CANVAS_VISIBLE_WARNED = False


def _canvas_visible_fn():
    """懒加载并缓存 W2 的 `canvas_visible_region_indices`；拿不到 → None"""
    global _CANVAS_VISIBLE_FN, _CANVAS_VISIBLE_PROBED
    if _CANVAS_VISIBLE_PROBED:
        return _CANVAS_VISIBLE_FN
    _CANVAS_VISIBLE_PROBED = True
    try:
        from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as _SREG
        fn = getattr(_SREG, "canvas_visible_region_indices", None)
        if callable(fn):
            _CANVAS_VISIBLE_FN = fn
    except Exception:
        _CANVAS_VISIBLE_FN = None
    return _CANVAS_VISIBLE_FN


# ======================================================================
# ★ 2026-09-23 追加规格 v9.1（`_d_spec_select_mode.md` §10.1）：
#   「重合时**面积最小者优先**」需要"多边形面积" —— 单一真相源在分析层：
#   W3 公开的 `spatial_region_analysis.polygon_area(points)`（薄包装既有 `_poly_area`）。
# ----------------------------------------------------------------------
# ★ 照抄本文件既有的懒加载 + `getattr` 兜底写法（`_canvas_visible_fn` / `_vertices_at`）：
#   拿不到该函数 ⇒ 用**本地私有** shoelace 兜底（`print` 留痕一次），
#   **绝不让 AttributeError 冒泡**（W3 并行落地，画布不能因为还没到就崩）。
# ======================================================================
_POLYGON_AREA_FN = None
_POLYGON_AREA_PROBED = False
_POLYGON_AREA_WARNED = False


def _polygon_area_fn():
    """懒加载并缓存 W3 的 `polygon_area(points)`；拿不到 → None（调用方走本地 shoelace）"""
    global _POLYGON_AREA_FN, _POLYGON_AREA_PROBED, _POLYGON_AREA_WARNED
    if _POLYGON_AREA_PROBED:
        return _POLYGON_AREA_FN
    _POLYGON_AREA_PROBED = True
    try:
        from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as _SREG
        fn = getattr(_SREG, "polygon_area", None)
        if callable(fn):
            _POLYGON_AREA_FN = fn
    except Exception:
        traceback.print_exc()
        print("[RegionCanvas] ⚠ 选择模式：无法从 analysis 层取 `polygon_area` ⇒ "
              "改用本地 shoelace 兜底算面积")
        _POLYGON_AREA_FN = None
    if _POLYGON_AREA_FN is None and not _POLYGON_AREA_WARNED:
        _POLYGON_AREA_WARNED = True
        print("[RegionCanvas] ⚠ 选择模式：analysis 层尚未提供 `polygon_area` ⇒ "
              "用本地 shoelace 兜底（「重合时面积最小者优先」仍然生效）")
    return _POLYGON_AREA_FN


def _local_polygon_area(points):
    """本地私有 shoelace 兜底（只在 `polygon_area` 不可用时用）

    Returns: float —— 面积**绝对值**；坏点/坏区域/退化多边形 → `0.0`（**绝不抛**）
    """
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
        a = abs(s) / 2.0
        if a != a:                                   # NaN 防御（坏坐标）
            return 0.0
        return float(a)
    except Exception:
        traceback.print_exc()
        print("[RegionCanvas] ⚠ 选择模式：本地 shoelace 兜底面积计算失败 ⇒ 该区域按面积 0.0 处理")
        return 0.0


# ======================================================================
# 组织底图加载（契约 §13.2）
# ----------------------------------------------------------------------
# ★ 精确映射：**图像像素 = 数据坐标 × 该样本的 scalef**（x、y 同乘）。
#   scalef **必须逐样本读** `scalefactors_json.json`，**不许硬编码** 0.4737。
# ★ 本函数是"底图从哪来"的**唯一真相源**，供 bind 调用；
#   `RegionCanvasWidget` 本身只接收已加载好的 pixmap（不读文件、不在 __init__ 里读盘）。
# ======================================================================
BASE_IMAGE_NOTE_PREFIX = "[RegionCanvas]"


def candidate_raw_roots():
    """所有可能的原始切片根，**按数据集**列出（顺序 = 先各数据集 manifest 声明的，后兜底常量）。

    ★ 2026-09-25 新增（实装第二个数据集 Dryad_UKF 时发现）：原实现只用写死的
      `import_config.SPATIAL_RAW_ROOT`（= GSE237183 那一个目录）。装入 Dryad 后，
      区域页会去 GSE237183 的目录找 `UKF*/…` → 找不到 → **底图缺失**。

    ★ 为什么"按样本 id 逐个根去试"就够、不必把 `dataset` 一路传进本模块：
      GSE237183 的样本 id 是 `GSM*`、Dryad_UKF 的是 `UKF*`，**两套 id 天然不重名**，
      所以"哪个根里有这个样本目录"是**无歧义**的。manifest 的 `source.raw_root`
      是契约 §1/§2 规定的字段（相对 BASE_DIR），本来就有，不必新造。
    """
    roots = []
    try:
        try:
            from script.utils_layer.import_config import BASE_DIR as _BASE
        except Exception:
            _BASE = os.path.dirname(str(APPDATA_PATH))
        try:
            names = sorted(os.listdir(SPATIAL_SCAN_DATA_PATH))
        except Exception:
            traceback.print_exc()
            names = []
        for n in names:
            if not n.endswith(".manifest.json"):
                continue
            try:
                with open(os.path.join(SPATIAL_SCAN_DATA_PATH, n), "r", encoding="utf-8") as f:
                    m = json.load(f)
                rel = str(((m.get("source") or {}).get("raw_root")) or "").strip()
                if not rel:
                    continue
                # ★ 用 normpath 归一化后再去重：manifest 里是正斜杠、常量里是反斜杠，
                #   不归一化会出现"同一个目录在候选表里出现两次"（实测命中过）。
                p = os.path.normpath(os.path.join(_BASE, rel))
                if os.path.isdir(p) and p not in roots:
                    roots.append(p)
            except Exception:
                traceback.print_exc()
        fallback = os.path.normpath(str(SPATIAL_RAW_ROOT)) if SPATIAL_RAW_ROOT else ""
        if fallback and fallback not in roots:
            roots.append(fallback)
    except Exception:
        traceback.print_exc()
    return roots


def resolve_base_image(sample_id, raw_root=None):
    """按样本 id 找底图路径：优先 hires，退 lowres。

    逐个候选原始根（见 `candidate_raw_roots()`）尝试；传了 `raw_root` 就只用它。

    Returns:
        (path, scalef_key, kind)
        kind ∈ {'hires', 'lowres', 'none'}；找不到返回 (None, None, 'none')
    """
    sid = str(sample_id or "").strip()
    if not sid:
        return (None, None, "none")
    roots = [str(raw_root)] if raw_root else candidate_raw_roots()
    for root in roots:
        # ① hires：<RAW_ROOT>/<GSM>_<label>_detected_tissue_image.jpg
        #    ★ 用 glob 取 label（不猜 mgh258 这种代号）；★ 结尾必须是 .jpg，
        #      以排除同名 `.jpg.gz`（实测磁盘上两者并存，会误命中）。
        try:
            cands = sorted(glob.glob(os.path.join(root,
                                                  sid + "*_detected_tissue_image.jpg")))
        except Exception:
            traceback.print_exc()
            cands = []
        if cands:
            return (cands[0], "tissue_hires_scalef", "hires")
        # ② hires：<RAW_ROOT>/<样本>/tissue_hires_image.png
        #    ★ 2026-09-25 新增：Dryad/UKF 走 Space Ranger 标准输出，hires 是这张 png。
        #      GSE237183 的暂存目录**没有**这张（只有 lowres）⇒ 对它是纯新增分支，
        #      原行为逐字不变。
        hi = os.path.join(root, sid, "tissue_hires_image.png")
        if os.path.exists(hi):
            return (hi, "tissue_hires_scalef", "hires")
        # ③ lowres：<RAW_ROOT>/<样本>/tissue_lowres_image.png
        low = os.path.join(root, sid, "tissue_lowres_image.png")
        if os.path.exists(low):
            return (low, "tissue_lowres_scalef", "lowres")
    return (None, None, "none")


def read_scalefactors(sample_id, key, raw_root=None):
    """逐样本读 `scalefactors_json.json` 里的某个比例键（不硬编码）。

    ★ 2026-09-25：改为在**候选原始根**里找该样本目录（与 `resolve_base_image` 同一套根，
      确保底图与比例来自**同一个数据集**）。传了 `raw_root` 就只用它。

    Returns: float 或 None（缺文件/缺键/非法一律 None，不抛）
    """
    sid = str(sample_id or "").strip()
    if not sid or not key:
        return None
    roots = [str(raw_root)] if raw_root else candidate_raw_roots()
    path = None
    for root in roots:
        cand = os.path.join(root, sid, "scalefactors_json.json")
        if os.path.exists(cand):
            path = cand
            break
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    try:
        value = float(data.get(key))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def load_base_image(sample_id):
    """加载某样本的组织底图。

    Returns:
        (pixmap|None, scalef|None, note:str)
        `note` 是**给日志的一行如实说明** —— 取不到时**不静默**（契约 §13.2 第 3 条）。
    """
    sid = str(sample_id or "").strip()
    path, key, kind = resolve_base_image(sid)
    if path is None:
        return (None, None, "样本 %s 未找到组织底图（hires 与 lowres 都不存在）→ 用纯色背景" % sid)
    scalef = read_scalefactors(sid, key)
    if scalef is None:
        return (None, None,
                "样本 %s 底图存在（%s）但 scalefactors 缺 %s → 用纯色背景（不硬编码比例）"
                % (sid, os.path.basename(path), key))
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return (None, None, "样本 %s 底图读取失败：%s → 用纯色背景"
                % (sid, os.path.basename(path)))
    return (pixmap, scalef,
            "样本 %s 底图 = %s（%s %dx%d，%s=%.8f）"
            % (sid, os.path.basename(path), kind, pixmap.width(), pixmap.height(), key, scalef))


# ======================================================================
# 主题配色（"悬停高亮"与"已隐藏边"）—— **全部走主题 token**，不硬编码
# ----------------------------------------------------------------------
# · 悬停高亮：`{v}_mutant_color`（变异色）—— **当前渲染已不用**（`edges` 模式退休后
#   没有"悬停高亮即将切换的边"了）；键保留，避免以后要用时再改主题契约。
# · 已手动隐藏的边：`{v}_edge_hidden_color`（**新可选 token**）→ 没有就退化：
#     `{v}_text_muted` → `{v}_text_secondary` → 由 `{v}_text_color`/`{v}_input_text`
#     **去饱和**得到灰色（仍是主题派生色，换主题跟着变）。
# ======================================================================
def _theme_styles():
    """当前主题样式 dict（拿不到 → 空 dict，绝不抛）"""
    if _get_mod_styles is None:
        return {}
    try:
        return _get_mod_styles() or {}
    except Exception:
        return {}


def _desaturate(color, sat_scale=0.12, value_scale=0.85):
    """把一个主题色**去饱和**成灰调（用于"已隐藏/禁用"态；换主题仍是派生色）"""
    try:
        c = QColor(str(color))
        if c.isValid():
            h, s, v, a = c.getHsl()
            c.setHsl(h, int(max(0, s) * sat_scale), int(max(0, v) * value_scale), a)
            return c
    except Exception:
        pass
    try:
        return QColor(str(color))
    except Exception:
        return QColor(140, 140, 140)


def edge_style_colors(variant='sub'):
    """画布边要用的"非普通"配色（**只读主题 token**）

    Returns: {'highlight': QColor（变异色，悬停高亮用）, 'hidden': QColor（灰调，已隐藏边用）}
    """
    s = _theme_styles()
    accent = s.get(f'{variant}_mutant_color', s.get('mutant_color', '#FF6B35'))
    base_text = s.get(f'{variant}_text_color', s.get(f'{variant}_input_text', '#87CEEB'))
    hidden_raw = s.get(f'{variant}_edge_hidden_color',
                       s.get(f'{variant}_text_muted', s.get(f'{variant}_text_secondary')))
    highlight = QColor(str(accent))
    if not highlight.isValid():
        highlight = QColor('#FF6B35')
    if hidden_raw:
        hidden = QColor(str(hidden_raw))
        if not hidden.isValid():
            hidden = _desaturate(base_text)
    else:
        hidden = _desaturate(base_text)          # 主题里没有专用灰 → 由字体色去饱和派生
    return {'highlight': highlight, 'hidden': hidden}


def layer_outline_style(kind, region_color, variant='sub'):
    """两种**范围层**在画布上的样式（**颜色走主题 token**，不硬编码）

    · `kind='mask'`    = 隐形区域：用自己的区域色 + **细密虚线**(dw 1)
    · `kind='visible'` = 可见区域：主题色 + **粗长虚线**(dw 2)
      （色 = `{v}_layer_visible_color`；**主题没定义该 token（或取到的颜色非法）⇒ 缺省 `#FFFFFF`**
        （v9.1 用户要求：可见区域虚线默认白色））
    ⇒ 两者在画布上**一眼可分**（颜色来源不同 + 线宽不同 + 虚线节奏不同），
      且都不画名字、都不参与"普通区域轮廓"的语义。
    """
    s = _theme_styles()
    if kind == 'visible':
        # ★ v9.1（用户：「可见区域的虚线颜色默认应该是白色」）：
        #   仍**优先尊重主题显式定义**的 `{v}_layer_visible_color`（这条机制不许写死），
        #   主题没有（或取到的颜色非法）⇒ 默认白色 `#FFFFFF`（不再回退 `{v}_input_text`）。
        token = s.get(f'{variant}_layer_visible_color')
        c = QColor(str(token)) if token else QColor('#FFFFFF')
        if not c.isValid():
            c = QColor('#FFFFFF')
        return {'color': c, 'width': 2, 'dash': (6.0, 5.0), 'alpha': 130, 'fill_alpha': 10}
    c = QColor(str(region_color))
    if not c.isValid():
        c = QColor('#FF6B35')
    return {'color': c, 'width': 1, 'dash': (1.0, 4.0), 'alpha': 110, 'fill_alpha': 18}


# 确定性色板：按「标签首次出现顺序」分配，**同一次会话内不变**
# （契约要求：同标签同色、确定性，别每次重绘变色）
_LABEL_PALETTE = [
    "#FF6B35", "#4E9BE8", "#7ED321", "#F5A623", "#BD10E0",
    "#50E3C2", "#B8E986", "#D0021B", "#8B572A", "#9013FE",
    "#417505", "#F8E71C", "#00A4EF", "#E91E63", "#607D8B",
]
_NA_COLOR = "#9E9E9E"          # 契约 13.3①：圈外 = NA（灰色）


class RegionCanvasWidget(QWidget):
    """自绘散点 + 缩放/平移 + 多边形绘制 + 虚线轮廓 + 区域名标签"""

    # 一个多边形闭合时发出（带当前区域名；未命名则为空串）
    region_finished = pyqtSignal(str)
    # 选中某个区域（索引；-1 = 无）
    region_selected = pyqtSignal(int)
    # ★ Phase 3 追加：编辑边 / 拖动注释锚点（供 bind 持久化；不接也不影响画布预览）
    region_edges_changed = pyqtSignal(int)                 # 区域索引
    region_label_moved = pyqtSignal(int, float, float)     # 区域索引, x, y（数据坐标）
    # ★★ 冻结信号（协调者）：**逐边切换的载荷** = (区域索引, 边号, "hide"|"show")
    #   在 `ov[str(edge)] = new` **写完立刻**发射 ⇒ bind 不必再从"同步前基线"做 diff
    #   （那条 diff 路径会因为 `region_selected` 先触发整份同步而恒判"未变"，
    #     真机上会让日志骗用户说"没点中边"）。
    #   ★ 取值域固定 `"hide"` / `"show"`，**不承载"移除手工覆盖"**。
    region_edge_toggled = pyqtSignal(int, int, str)
    # ★ Phase 4 追加：区域改名（写回 `name` 后发；W2 据此落盘 + 刷新列表）
    region_name_changed = pyqtSignal(int, str)             # 区域索引, 新名字
    # ★★ 2026-09-23 契约 `_d_spec_select_mode.md` §3.3/§5（W1 新增，冻结名）：
    #   · `regions_selected(list)`       —— **多选**变化时发（载荷 = 当前选中的区域索引列表，
    #                                        顺序 = 命中顺序；单选 ⇒ 单元素列表；清空 ⇒ `[]`）；
    #   · `region_geometry_changed(int)` —— **顶点拖动松开且坐标确实变了**时发**一次**
    #                                        （载荷 = 区域索引）；拖动期间**绝不**发。
    #   ★ `region_selected(int)` **照旧发**（发"主选中项"，清空时发 `-1`）⇒ 既有接线不断。
    regions_selected = pyqtSignal(list)
    region_geometry_changed = pyqtSignal(int)

    # 编辑模式（§15.4 + Phase 5 + 2026-09 用户纠正 + 2026-09-23 选择模式）
    #   · `"edges"`（编辑边）**已退休** —— 用户原话："根本就不是编辑边，而是改成
    #     **可见区域选择**"；取而代之 `"visible"` = **自己再画一套多边形当"可见区域"范围层**。
    #   · `"visible"` / `"mask"` 的左键行为都与 `"draw"` **完全一致**（加点/双击闭合/
    #     锚点复用/右键取消），唯一区别 = 闭合出来的区域分别带 `"visible": True` / `"mask": True`。
    #   · `"select"`（新增，契约 §2）= **选择模式**：不画点、不闭合，只按优先级选中区域
    #     （见 `_select_press`）；点独有的锚点可拖动改形状。
    EDIT_MODES = ("draw", "visible", "label", "mask", SELECT_MODE)
    # 画法同 draw 的模式（**同一段代码**，不复制画点逻辑）；`select` **不在**其中
    DRAW_LIKE_MODES = ("draw", "visible", "mask")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)          # 需要键盘（空格=平移模式）
        self.setMinimumSize(320, 240)

        # ---- 数据 ----
        self._xs = []
        self._ys = []
        self._labels = []
        self._label_colors = {}                      # label -> QColor
        self._regions = []                           # list[dict]
        self._base_pixmap = None                     # 真实组织底图（bind 传入）
        self._base_scalef = 1.0                      # 图像像素 = 数据坐标 × scalef
        self._base_scaled_cache = {}                 # (id(pixmap), w, h) -> 已缩放 QPixmap
        self._base_scaled_key = None
        # ★ Phase 3⑤：「底图 + spot」预渲染缓存（paintEvent 只 blit 它，绝不重铺点）
        self._content_cache = None                   # QPixmap
        self._content_key = None
        self._content_builds = 0                     # 重建次数（供性能断言/自检）
        self._spots_version = 0                      # spot 指纹（set_spots 时 +1）
        self._base_version = 0                       # 底图指纹（set_base_image 时 +1）
        self._analysis_spots = []                    # [(x, y)]，给 analysis 的 spots 形态

        # ---- 视图 ----
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)

        # ---- 绘制中状态 ----
        self._drawing_points = []                    # 数据坐标 [[x,y], ...]
        self._cursor_data = None                     # 鼠标处的数据坐标（画橡皮筋）

        # ---- 当前画笔样式 ----
        self._active_name = ""
        self._active_dash_width = 2
        self._active_dash_gap = 6
        self._active_color = "#FF6B35"               # ＝ 模块级 ACTIVE_COLOR_INITIAL_DEFAULT（v9.2 判据基准）
        self._active_font_size = 12
        self._active_font_color = "#FFFFFF"
        self._active_corner_radius = 0               # §15.3 corner_radius_px（仅呈现）

        # ---- 编辑模式（§15.4）----
        self._edit_mode = "draw"                     # {"draw","visible","label","mask","select"}
        self._selected_index = -1                    # 最近选中/新画的区域（= 主选中项）
        # ★★ 2026-09-23（契约 `_d_spec_select_mode.md` §3.3）：**多选**状态。
        #   顺序 = 命中顺序；恒有 `_selected_index == (_selected_indices[0] if _selected_indices else -1)`。
        #   ⛔ 别在任何地方直接写 `_selected_index`：一律走 `_set_selection(...)`（唯一收口）。
        self._selected_indices = []
        self._dragging_label = -1                    # 正在拖动注释的区域索引
        self._drag_label_data = None                 # 拖动中的 (x, y)
        # ★★ 2026-09-23（契约 §3.2）：**顶点拖动**状态（只在 `select` 模式的"独有锚点"上激活）
        self._dragging_vertex = -1                   # 正在拖动顶点的区域索引（-1 = 没在拖）
        self._drag_vertex_no = -1                    # 该顶点在 `points` 里的**原始**下标
        self._drag_vertex_start = None               # 按下时的数据坐标 (x, y)（判"是否真变"）
        self._auto_hidden_cache = {}                 # region_idx -> set(自动隐藏边号)
        self._auto_hidden_key = None                 # (spots_version, regions_version)
        self._regions_version = 0
        self._auto_hidden_shape = None               # 探测成功的 spots 形态
        self._hover_label = False                    # 悬停是否在注释矩形内（光标反馈）
        self._hover_anchor = (-1, -1)                # 悬停的锚点（区域, 顶点）
        self._visible_outline_key = None             # 「可见区域」过滤结果缓存键
        self._visible_outline_cache = None

        # ---- 平移 ----
        self._space_down = False
        self._panning = False
        self._pan_last = QPoint()

        self._bg_color = QColor("#1a1a2e")

    # ==================================================================
    # 数据接口（全部由 bind 传入，本控件不读文件）
    # ==================================================================
    def set_spots(self, xs, ys, labels):
        """设置散点。`labels` 为字符串列表（当前细胞类型，可能含 "NA"）。"""
        self._xs = list(xs or [])
        self._ys = list(ys or [])
        self._labels = list(labels or [])
        self._label_colors = {}
        order = []
        for lab in self._labels:
            key = str(lab) if lab is not None and str(lab) != "" else "NA"
            if key not in order:
                order.append(key)
        for i, key in enumerate(order):
            if key == "NA":
                self._label_colors[key] = QColor(_NA_COLOR)
            else:
                self._label_colors[key] = QColor(_LABEL_PALETTE[i % len(_LABEL_PALETTE)])
        # ★ spot 变了 → 内容缓存与自动隐藏边缓存全部失效
        self._spots_version += 1
        self._invalidate_content()
        self._invalidate_auto_hidden()
        try:
            n = min(len(self._xs), len(self._ys))
            self._analysis_spots = [(self._xs[i], self._ys[i]) for i in range(n)]
        except Exception:
            self._analysis_spots = []
        self.reset_view()

    def label_colors(self):
        """返回 {label: QColor}（供 bind 画图例，避免两处各推一套色）"""
        return dict(self._label_colors)

    def set_base_image(self, pixmap, scalef=1.0):
        """设置真实组织底图（`pixmap` 由 bind 读好后传入；scalef 来自该样本的
        `scalefactors_json.json`，**不许硬编码**）。传 None 表示无底图。"""
        self._base_pixmap = pixmap
        self._base_scaled_cache = {}          # 换底图 → 缓存失效
        self._base_scaled_key = None
        try:
            self._base_scalef = float(scalef) if scalef else 1.0
        except (TypeError, ValueError):
            self._base_scalef = 1.0
        self._base_version += 1               # ★ 底图变了 → 内容缓存失效
        self._invalidate_content()
        self.update()

    def load_base_image_for(self, sample_id):
        """便捷入口：按样本 id 加载底图并设置（★ 唯一真相源在模块级 `load_base_image`）。

        Returns: str —— 给日志的一行如实说明（找不到/缺 scalef 都会说明，不静默）
        """
        pixmap, scalef, note = load_base_image(sample_id)
        self.set_base_image(pixmap, scalef if scalef else 1.0)
        return note

    def _scaled_base_for(self, w, h):
        """按需缩放底图并缓存。

        ★ 为什么必须缓存：原图达 1799×2000；而**绘制多边形时每次 mouse move 都会 repaint**
          （橡皮筋），若每帧都 `scaled()` 会明显卡。这里按 (底图, 目标尺寸) 缓存**最近一张**，
          所以"移动鼠标重绘"这一最热的路径全部命中缓存。
        """
        if self._base_pixmap is None or self._base_pixmap.isNull():
            return None
        w = max(1, int(w))
        h = max(1, int(h))
        key = (id(self._base_pixmap), w, h)
        cached = self._base_scaled_cache.get(key)
        if cached is not None:
            self._base_scaled_key = key
            return cached
        try:
            scaled = self._base_pixmap.scaled(w, h, Qt.IgnoreAspectRatio,
                                              Qt.SmoothTransformation)
        except Exception:
            return None
        # 只留最近一张，避免缓存无限增长
        self._base_scaled_cache = {key: scaled}
        self._base_scaled_key = key
        return scaled

    def set_regions(self, regions):
        """设置区域列表（结构见契约 §13.7 的 `regions`）

        ★ 入口即**深拷贝**（`copy_regions`）：只拷外层 list 的话，元素 dict
          仍与 bind 的 `regions_data` 共享引用 —— 外部改名/改色会穿透污染
          画布内部状态。与 `get_regions()` 出口的拷贝配对（§13.9）。
        """
        self._regions = copy_regions(regions)
        self._regions_version += 1
        # ★ 整份重载 ⇒ 旧的多选索引可能已越界/指向别的区域 ⇒ 一并清空
        #  （走唯一收口 `_set_selection`，保证 `_selected_indices` 与 `_selected_index` 不打架；
        #    `emit=False` 与历史行为一致：本接口过去也**不发** `region_selected`）
        self._set_selection([], emit=False)
        self._invalidate_auto_hidden()
        self.update()

    def get_regions(self):
        """取回区域列表（深拷贝一份，避免 bind 误改内部状态）"""
        return copy_regions(self._regions)

    def set_active_style(self, dash_width, dash_gap, color, label_font_size, label_font_color):
        """设置"接下来画的"多边形样式"""
        try:
            self._active_dash_width = int(dash_width)
        except (TypeError, ValueError):
            pass
        try:
            self._active_dash_gap = int(dash_gap)
        except (TypeError, ValueError):
            pass
        if color:
            self._active_color = str(color)
        try:
            self._active_font_size = int(label_font_size)
        except (TypeError, ValueError):
            pass
        if label_font_color:
            self._active_font_color = str(label_font_color)
        self.update()

    def set_active_name(self, name):
        """设置"接下来画的"多边形名字（附加接口，供 bind 在闭合前推入输入框文本）"""
        self._active_name = str(name or "")

    # ==================================================================
    # Phase 4①：区域改名（选中区域可用 `region_name_input` 改）
    # ==================================================================
    def set_region_name(self, index, name):
        """把第 `index` 个区域的 `name` 改成 `name`（写进区域字典 → `get_regions()` 带出）。

        · 非法索引 → 返回 False（不抛）；
        · 名字没变 → 返回 True 但**不发信号**（避免"回填文本框"反过来触发落盘）；
        · 改名成功后发 `region_name_changed(index, name)`，供 bind 落盘 + 刷新列表。
        """
        try:
            idx = int(index)
        except (TypeError, ValueError):
            return False
        if not (0 <= idx < len(self._regions)):
            return False
        region = self._regions[idx]
        if not isinstance(region, dict):
            return False
        new_name = str(name or "")
        old_name = str(region.get("name") or "")
        if new_name == old_name:
            return True
        region["name"] = new_name
        self._regions_version += 1
        self.update()
        try:
            self.region_name_changed.emit(idx, new_name)
        except Exception:
            pass
        return True

    def region_name(self, index):
        """读第 `index` 个区域的名字（非法索引 → 空串）"""
        try:
            idx = int(index)
        except (TypeError, ValueError):
            return ""
        if 0 <= idx < len(self._regions) and isinstance(self._regions[idx], dict):
            return str(self._regions[idx].get("name") or "")
        return ""

    # ==================================================================
    # Phase 3 接口（§15.4）：编辑模式 / 圆角预览 / 缓存自检
    # ==================================================================
    def set_edit_mode(self, mode):
        """切换编辑模式：`mode ∈ {"draw","visible","label","mask","select"}`（§15.4 + 2026-09）。

        · `draw`    ：左键加点、双击闭合、右键取消（普通区域）；
        · `visible` ：**画"可见区域"范围层**（左键行为与 draw 完全一致），
                      闭合出来的区域带 `"visible": True`；
        · `label`   ：左键拖动注释锚点 = 写 `label_pos`；**不加点**；
        · `mask`    ：**画"隐形区域"范围层**（左键行为与 draw 完全一致），
                      闭合出来的区域带 `"mask": True`；
        · `select`  ：**选择模式**（2026-09-23 契约 `_d_spec_select_mode.md` §2/§3）：
                      左键按"锚点 → 边 → 区域内 → 空白"优先级**选中区域**（含可见/隐形范围层），
                      点**独有锚点**可拖动改形状；点**公用锚点/共有边**只多选、**不能编辑**。
        （原 `"edges"`（编辑边）**已退休**：用户纠正那个按钮本该是"可见区域"。）

        非法值一律退化为 `"draw"`，**绝不抛**。
        Returns: str —— 实际生效的模式
        """
        m = str(mode or "").strip().lower()
        if m not in self.EDIT_MODES:
            m = "draw"
        self._edit_mode = m
        # 切模式时收尾：拖动中的注释不再跟着走（不写半截状态）；锚点悬停清掉
        if self._dragging_label >= 0:
            self._dragging_label = -1
            self._drag_label_data = None
        # ★ 同上：切模式时把**未完成的顶点拖动**一并清掉（不把半截坐标留给下个模式；
        #   清理**不**发 `region_geometry_changed` —— 契约 §5 规定只有"松开且坐标真变"才发）
        if self._dragging_vertex >= 0:
            self._dragging_vertex = -1
            self._drag_vertex_no = -1
            self._drag_vertex_start = None
        self._hover_anchor = (-1, -1)
        try:
            if m == "label":
                self.setCursor(Qt.OpenHandCursor)
            elif m in ("mask", "visible"):
                # 两种范围层都是"圈范围"：给十字光标
                self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        except Exception:
            pass
        self.update()
        return m

    def edit_mode(self):
        """当前编辑模式（只读）"""
        return self._edit_mode

    def _draw_like(self):
        """当前模式是否是"画多边形"类（`draw` / `visible` / `mask`）——**同一段代码**"""
        return self._edit_mode in self.DRAW_LIKE_MODES

    def selected_index(self):
        """**主选中项**的区域索引（-1 = 无；只读）

        ★ 返回类型**仍是 `int`**（契约 §6.2）：语义收窄为"主选中项" = `selected_indices()[0]`，
          空则 `-1`；老调用点（属性面板/列表回填等）完全不受影响。
        ★ 配对写入接口见 `set_selected_index()`（bind 命令画布"把某个区域显示为选中"）。
        """
        return self._selected_index

    def selected_indices(self):
        """当前**全部**选中区域索引（**副本**；顺序 = 命中顺序，`[]` = 无选中）"""
        return list(self._selected_indices)

    def _normalize_indices(self, indices):
        """把任意输入规整成"合法、去重、保序"的区域索引列表。

        · `None` / 标量 / 可迭代都能吃；非法项（非整数、越界）**静默丢弃**（只丢那一项）；
        · **保序**：保留调用方给的顺序（选择模式的"命中顺序"就靠这个）；
        · 结果恒满足 `0 <= i < len(self._regions)`。
        """
        out = []
        if indices is None or isinstance(indices, bool):
            return out
        if isinstance(indices, int):
            indices = [indices]
        # 非可迭代（如 float）：按"无选中"处理（**不用 try/except**，免得留一处静默兜底）
        if isinstance(indices, str) or not hasattr(indices, "__iter__"):
            return out
        for raw in indices:
            try:
                i = int(raw)
            except (TypeError, ValueError):
                continue          # 窄类型兜底（与 `set_selected_index` 同款）：只丢这一项
            if 0 <= i < len(self._regions) and i not in out:
                out.append(i)
        return out

    def _set_selection(self, indices, emit=False):
        """★★ **选中的唯一收口**：写 `_selected_indices` / `_selected_index` / `update()` / 信号。

        Args:
            indices: 任意形态（内部会过 `_normalize_indices`）
            emit:    True ⇒ 发 `region_selected(int主选中项)` + `regions_selected(list)`；
                     False ⇒ **一个字都不发**（供 `set_selected_index` /
                             `set_selected_indices` / `set_regions` 这类"外部命令"路径用，
                             避免与 bind 的槽形成回环 —— 既有硬约定，别改）。

        ★ 只在这里写状态 ⇒ `_selected_indices`、`_selected_index`、两个信号、`update()`
          **永远一致**；任何分支都别再各写一套。
        Returns: list[int] —— 实际生效的索引（副本）
        """
        try:
            normalized = self._normalize_indices(indices)
        except Exception:
            traceback.print_exc()
            normalized = []
        self._selected_indices = normalized
        self._selected_index = normalized[0] if normalized else -1
        try:
            self.update()
        except Exception:
            traceback.print_exc()
        if emit:
            # ★ 顺序：`region_selected` 先（与历史路径逐字一致，老槽看到的时序不变），
            #   再补新的 `regions_selected`（多选信息，W2 §3.3 用它禁用命名控件）。
            try:
                self.region_selected.emit(int(self._selected_index))
            except Exception:
                traceback.print_exc()
            try:
                self.regions_selected.emit([int(i) for i in normalized])
            except Exception:
                traceback.print_exc()
        return list(normalized)

    def set_selected_index(self, index):
        """**外部（bind）命令画布**把第 `index` 个区域**显示为选中**（无 → `-1`）。

        Args:
            index: `int` / `None` / 任何非法值。只有落在 `[-1, len(regions)-1]` 的整数生效；
                   **越界（如 99）或非法（如 "x" / None）一律按 `-1`（= 取消选中）**。

        Returns:
            int —— **实际生效的索引**（`-1` 表示无选中）；任何异常都吞掉并返回 `-1`。

        ★ 语义**仍是单选**（契约 §6.2）：内部就是 `_set_selection([i])`
          ⇒ 多选状态被这一个索引取代（`selected_indices()` 变成 `[i]` 或 `[]`）。

        ★★ **绝不 emit `region_selected`**（本接口的硬约定，别改）：
           本接口是"**外部**命令画布改选中态"，若在这里再发信号，会与 bind 的
           `region_selected` 槽形成回环（bind 收到信号 → 又调本接口 → 又发信号 …）。
           **画布内部因用户点击而改变选中时，仍照旧由 `mousePressEvent` /
           `mouseDoubleClickEvent` 发 `region_selected`**，本接口不参与那条路径。
        """
        try:
            if index is None:
                idx = -1
            else:
                idx = int(index)
            if idx < -1 or idx >= len(self._regions):
                idx = -1
            self._set_selection([] if idx < 0 else [idx], emit=False)
            return self._selected_index
        except Exception:
            traceback.print_exc()
            try:
                self._set_selection([], emit=False)
            except Exception:
                traceback.print_exc()
            return -1

    def set_selected_indices(self, indices):
        """**外部（bind）命令画布**把若干区域**显示为选中**（多选；`[]`/`None` = 清空）。

        ★ 过滤非法/越界索引、**去重保序**，并同步 `_selected_index`（= 第一个）；
        ★★ 与 `set_selected_index` 同一硬约定：**绝不 emit**（防回环）。
        Returns: list[int] —— 实际生效的索引（副本）
        """
        try:
            return self._set_selection(indices, emit=False)
        except Exception:
            traceback.print_exc()
            try:
                return self._set_selection([], emit=False)
            except Exception:
                traceback.print_exc()
                return []

    def set_active_corner_radius(self, radius, region_index=None):
        """设置圆角半径（§15.3 `corner_radius_px`，**仅呈现、不影响判定**）。

        Args:
            radius: 0..40（超范围夹紧；非法值 → 0）
            region_index: 目标区域索引；None ⇒ 优先「当前选中区域」，
                          **没有选中则用最后一个区域**（用户刚画完就在调它），
                          一个区域都没有时只记作“下次画用的半径”。

        Returns: int —— 实际生效的半径
        """
        try:
            r = int(radius)
        except (TypeError, ValueError):
            r = 0
        r = max(0, min(40, r))
        self._active_corner_radius = r
        idx = self._selected_index if region_index is None else region_index
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            idx = -1
        if idx < 0 and self._regions:
            idx = len(self._regions) - 1
        if 0 <= idx < len(self._regions):
            region = self._regions[idx]
            if isinstance(region, dict):
                # ★ 一律写入（含 0）：字段存在、值可预测，`get_regions()` 形状统一；
                #   0 = 尖角（旧行为），不是"字段缺失"
                region["corner_radius_px"] = r
        self._regions_version += 1
        self.update()
        return r

    def active_corner_radius(self):
        """当前生效的圆角半径（只读）"""
        return self._active_corner_radius

    def content_cache_stats(self):
        """性能自检：内容缓存（底图+spot）的重建次数与当前键。

        供验收断言「连续 mouseMove 不重铺 spot」：`builds` 不变 = 全部命中缓存。
        """
        return {"builds": self._content_builds,
                "cached": self._content_cache is not None,
                "key": self._content_key,
                "spots_version": self._spots_version,
                "base_version": self._base_version}

    def _invalidate_content(self):
        """让「底图 + spot」预渲染缓存失效（下次 paint 重建一次）"""
        self._content_cache = None
        self._content_key = None

    def _invalidate_auto_hidden(self):
        """让自动隐藏边缓存失效"""
        self._auto_hidden_cache = {}
        self._auto_hidden_key = None

    # ---------- 未闭合草稿的读/改（供 bind 的「撤销上一点」与"闭合前拿点"）----------
    def get_draft_points(self):
        """返回当前**未闭合**多边形的点列表（数据坐标的拷贝；没有则 `[]`）。

        给 bind 当兜底：闭合前可先拿点做校验，不必依赖 `region_finished` 的时序。
        """
        return [list(p) for p in self._drawing_points]

    def undo_last_point(self):
        """撤销（弹出）未闭合多边形的**最后一个点**。

        Returns:
            bool —— 成功弹出一个点返回 True；当前没有未闭合多边形返回 False。
        ★ 容错：任何异常都不抛（W2 的 `CANVAS_UNDO_POINT = "undo_last_point"` 依赖它存在）。
        """
        try:
            if not self._drawing_points:
                return False
            self._drawing_points.pop()
            if not self._drawing_points:
                self._cursor_data = None      # 弹空后不再画橡皮筋
            self.update()
            return True
        except Exception:
            return False

    # ==================================================================
    # 坐标变换（★ 必须精确可逆）
    # ==================================================================
    def _data_bounds(self):
        if not self._xs or not self._ys:
            return (0.0, 1.0, 0.0, 1.0)
        minx, maxx = min(self._xs), max(self._xs)
        miny, maxy = min(self._ys), max(self._ys)
        if maxx <= minx:
            maxx = minx + 1.0
        if maxy <= miny:
            maxy = miny + 1.0
        return (float(minx), float(maxx), float(miny), float(maxy))

    def _base_scale(self):
        """等比基准倍率 = min(w/dx, h/dy)（x/y 同倍率 ⇒ 圈不变形）"""
        minx, maxx, miny, maxy = self._data_bounds()
        dx = maxx - minx
        dy = maxy - miny
        w = max(1, self.width())
        h = max(1, self.height())
        return min(w / dx, h / dy)

    def _scale(self):
        return self._base_scale() * self._zoom

    def _data_to_screen_f(self, x, y):
        """数据 → 屏幕（浮点版，内部几何计算用）"""
        minx, maxx, miny, maxy = self._data_bounds()
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0
        s = self._scale()
        wx = self.width() / 2.0
        wy = self.height() / 2.0
        return ((x - cx) * s + wx + self._pan.x(),
                (y - cy) * s + wy + self._pan.y())

    def data_to_screen(self, x, y):
        """数据 → 屏幕（QPoint）"""
        sx, sy = self._data_to_screen_f(x, y)
        return QPoint(int(round(sx)), int(round(sy)))

    def screen_to_data(self, pos):
        """屏幕 → 数据（★ 关键 API：与 `data_to_screen` 精确互逆）"""
        if hasattr(pos, "x") and callable(pos.x):
            px, py = float(pos.x()), float(pos.y())
        else:
            px, py = float(pos[0]), float(pos[1])
        minx, maxx, miny, maxy = self._data_bounds()
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0
        s = self._scale()
        if s <= 0:
            return (cx, cy)
        wx = self.width() / 2.0
        wy = self.height() / 2.0
        x = (px - wx - self._pan.x()) / s + cx
        y = (py - wy - self._pan.y()) / s + cy
        return (x, y)

    # ==================================================================
    # 缩放 / 平移
    # ==================================================================
    def zoom_in(self):
        self._zoom_at(1.25, None)

    def zoom_out(self):
        self._zoom_at(0.8, None)

    def reset_view(self):
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self.update()

    def _zoom_at(self, factor, anchor_pos):
        """以 `anchor_pos`（屏幕点）为锚点缩放；anchor 为 None 时用画布中心"""
        if anchor_pos is None:
            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
            anchor_pos = QPoint(int(anchor.x()), int(anchor.y()))
        before = self.screen_to_data(anchor_pos)
        new_zoom = self._zoom * float(factor)
        self._zoom = max(0.05, min(50.0, new_zoom))
        after_x, after_y = self._data_to_screen_f(before[0], before[1])
        self._pan = QPointF(self._pan.x() + (anchor_pos.x() - after_x),
                            self._pan.y() + (anchor_pos.y() - after_y))
        self.update()

    # ==================================================================
    # 交互
    # ==================================================================
    def mousePressEvent(self, event):
        pos = event.pos()
        if event.button() == Qt.MiddleButton or (self._space_down and event.button() == Qt.LeftButton):
            # 中键 / 空格+拖动 = 平移（左键已被绘制占用，不抢）
            self._panning = True
            self._pan_last = pos
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.RightButton:
            # 右键 = 取消当前未闭合的绘制
            if self._drawing_points:
                self._drawing_points = []
                self._cursor_data = None
                self.update()
            return
        if event.button() != Qt.LeftButton:
            return

        # ★★ 裁定（2026-09，用户真机被挡住后拍板）：**左键在每个模式下只做一件事**。
        #   `draw`/`visible`/`mask` = 只加点；`label` = 只选中/拖注释。
        #   ⛔ 这里**不再**先做"注释命中"：那条旧逻辑对**所有模式**生效，而注释命中框是
        #      `_label_rect_screen()` 给的**至少 120×24 屏幕像素的隐形矩形**（锚点=质心），
        #      用户围着已有区域点遮罩时高频撞上它 ⇒ **点了不加点、还把注释悄悄拖走**
        #      （真机症状："点不上去点"；他 regions.json 里 label_pos 被拖偏即铁证）。
        #   ⇒ 注释命中挪进 `label` 分支（见下）。
        # ⛔ `edges`（编辑边）分支**已退休**（2026-09 用户纠正：那个按钮本该是"可见区域"）
        #   ⇒ 旧"点边切显隐"分支与 per-edge 悬停高亮都删掉了。
        #   ★ 数据字段 `edge_override` **照旧读取/渲染**（用户 regions.json 里就有），
        #     只是画布不再提供"切它"的入口；`_toggle_edge_at` / `region_edge_toggled`
        #     保留（无 UI 入口、但不再有死 UI 分支）。

        # ---- select（选择模式，契约 `_d_spec_select_mode.md` §3.1）：**只选中、绝不画点** ----
        # ★ 放在最前面（除平移/右键/非左键之外）：本模式的点击优先级 = 锚点 → 边 →
        #   区域内 → 空白清空，与既有四模式的逻辑**完全隔离**（那些分支一个字不动）。
        if self._edit_mode == SELECT_MODE:
            self._select_press(pos)
            return

        # ---- label：**只有这个模式**才拖注释 ----
        if self._edit_mode == "label":
            label_idx = self._label_rect_at(pos)
            if label_idx >= 0:
                self._dragging_label = label_idx
                self._drag_label_data = self._label_anchor_data(label_idx, self._regions[label_idx])
                self.setCursor(Qt.ClosedHandCursor)
                # ★ 走唯一收口（状态 + `region_selected` + `regions_selected` + update 一起）
                self._set_selection([label_idx], emit=True)
                return
            # 没点在注释上 → 退化为"选中该区域"；**绝不静默改动任何东西**
            hit = self._hit_region(pos)
            if hit >= 0:
                self._set_selection([hit], emit=True)
            return

        # ---- draw / mask：**任何一次左键落点都加点**（含注释矩形内）----
        # ★ Phase 4②：左键**正好点在已有锚点**上 → 直接用那个顶点（显式复用，**不自动吸附**）
        anchor = self._anchor_hit(pos)
        if anchor[0] >= 0:
            try:
                p = self._regions[anchor[0]]["points"][anchor[1]]
                data = (float(p[0]), float(p[1]))
            except Exception:
                data = self.screen_to_data(pos)
        else:
            data = self.screen_to_data(pos)
        if not self._drawing_points:
            # 开始新多边形 → 取消选中（清空 ⇒ `region_selected(-1)`，与既有约定一致）
            self._set_selection([], emit=True)
        self._drawing_points.append([float(data[0]), float(data[1])])
        self.update()

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_last
            self._pan = QPointF(self._pan.x() + delta.x(), self._pan.y() + delta.y())
            self._pan_last = event.pos()
            self.update()
            return
        # ---- select（选择模式，契约 §3.2）：顶点拖动实时预览 / 锚点悬停反馈 ----
        #   ★ 拖动期间**只改坐标 + update()**：绝不 emit、绝不写盘（落盘在 `mouseReleaseEvent`）。
        if self._edit_mode == SELECT_MODE:
            if self._dragging_vertex >= 0:
                self._move_dragged_vertex(self.screen_to_data(event.pos()))
                self.update()
                return
            hov = self._anchor_hit(event.pos(), ANCHOR_TOL_SCREEN)
            if hov != self._hover_anchor:
                self._hover_anchor = hov
                self.update()
            return
        # ★ 拖动注释锚点：实时跟随鼠标（走内容缓存 blit，不重铺 spot）
        if self._dragging_label >= 0:
            data = self.screen_to_data(event.pos())
            self._drag_label_data = (float(data[0]), float(data[1]))
            self._write_label_pos(self._dragging_label, self._drag_label_data)
            self.update()
            return
        pos = event.pos()
        # ⛔ 原 `edges` 模式的"悬停高亮即将切换的边"已随该模式一起退休（2026-09）：
        #   那条高亮只服务于"点边切显隐"，现在没有这个入口了 ⇒ 整块删除，不留死代码。
        # ★ 悬停注释 → "移动"光标：**只在 `label` 模式**（裁定：左键每个模式只做一件事）。
        #   draw/visible/mask 下显示移动光标会暗示"可以拖"，而那里左键其实是加点 ⇒ 不显示。
        over_label = (self._edit_mode == "label") and (self._label_rect_at(pos) >= 0)
        if over_label != self._hover_label:
            self._hover_label = over_label
            if over_label:
                try:
                    self.setCursor(Qt.SizeAllCursor)
                except Exception:
                    pass
            else:
                self._restore_mode_cursor()
        # ★ Phase 4②：锚点悬停高亮（只是"看得见"，**不做任何吸附**）
        if self._draw_like():
            hov = self._anchor_hit(pos)
            if hov != self._hover_anchor:
                self._hover_anchor = hov
                self.update()
        # ★ draw / mask 模式：画橡皮筋（内容缓存命中 ⇒ 不再重铺底图与 spot）
        if self._draw_like() and self._drawing_points:
            self._cursor_data = self.screen_to_data(pos)
            self.update()

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._panning = False
            self.setCursor(Qt.OpenHandCursor)
            return
        # ---- select（选择模式，契约 §3.2/§5）：松开顶点拖动 ⇒ 坐标真变了才发**一次** ----
        if self._dragging_vertex >= 0 and event.button() == Qt.LeftButton:
            self._finish_vertex_drag()
            return
        if self._dragging_label >= 0 and event.button() == Qt.LeftButton:
            idx = self._dragging_label
            self._dragging_label = -1
            pos = self._drag_label_data
            self._drag_label_data = None
            try:
                self.setCursor(Qt.OpenHandCursor)
            except Exception:
                pass
            # ★★ 硬要求（契约 §13.9 2d）：**先落进区域字典再发信号**。
            #   只按不拖（press→release 中间没有 move）时 `_drag_label_data` 是
            #   按下时的锚点，以前这条路径**不发**数据进 dict ⇒ 信号说"挪到 X"、
            #   而 `get_regions()` 里 `label_pos` 仍是 None ⇒ 绑定层按整份同步时
            #   把用户拖的位置抹回质心。这里保证「信号的载荷一定有模型背书」。
            if pos is None:
                pos = self._label_anchor_data(idx, self._regions[idx]) \
                    if 0 <= idx < len(self._regions) else None
            if pos is not None:
                self._write_label_pos(idx, pos)
                self.update()
            if pos is not None:
                self.region_label_moved.emit(int(idx), float(pos[0]), float(pos[1]))
            self._restore_mode_cursor()

    def _restore_mode_cursor(self):
        """把光标恢复成当前模式该有的样子（拖动结束后调用）"""
        try:
            m = self._edit_mode
            if m in ("mask", "visible"):
                self.setCursor(Qt.CrossCursor)
            elif m == "label":
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        except Exception:
            pass

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        # ★ select（选择模式）：双击**不改变**选择 —— 第一下 `mousePressEvent` 已按
        #   §3.1 优先级（锚点 → 边 → 区域内）选好了；若在这里再按 `_hit_region` 选一次，
        #   会把"点锚点/点边"的结果覆盖成"区域内容最上面那个"。
        if self._edit_mode == SELECT_MODE:
            return
        # ★ 非"画多边形"模式：双击只做"选中"，绝不闭合（本轮新增模式不抢加点行为）
        if not self._draw_like():
            idx = self._hit_region(event.pos())
            if idx >= 0:
                self._set_selection([idx], emit=True)
            return
        if self._drawing_points:
            # 双击 = 闭合（≥3 点才允许；否则忽略并留痕）
            if len(self._drawing_points) >= 3:
                region = {
                    "name": self._active_name or "",
                    "color": self._active_color,
                    "points": [list(p) for p in self._drawing_points],
                    "dash_width": self._active_dash_width,
                    "dash_gap": self._active_dash_gap,
                    "label_font_size": self._active_font_size,
                    "label_font_color": self._active_font_color,
                }
                # ★ 2026-09：两种**范围层** —— 隐形区域(`mask`) / 可见区域(`visible`)
                #   （普通区域**不写**这两个键 —— 契约要求"不写或 False"）
                if self._edit_mode == "mask":
                    region["mask"] = True
                elif self._edit_mode == "visible":
                    region["visible"] = True
                # 颜色（v9.2 用户需求："可见区域默认区域颜色 = 白"）：
                #   ★ **镜像上面圆角那条规则**（v9.1 §11）的写法 —— 同样是"可见层 +
                #     用户没调过 ⇒ 分层缺省；用户真调过 ⇒ 用用户的值；
                #     普通区域 / mask ⇒ 行为完全不变"。
                #   · 用户真调过调色板（`self._active_color` ≠ `__init__` 的初始默认色
                #     `ACTIVE_COLOR_INITIAL_DEFAULT`("#FF6B35")）⇒ **一律用用户的值**
                #     （普通 / mask / 可见层都一样）；
                #   · **可见层且 `self._active_color` 仍是初始默认色 ⇒
                #     缺省 `REGION_COLOR_VISIBLE_DEFAULT`("#FFFFFF")**；
                #   · 普通区域 / mask ⇒ **完全不变**（仍一律 `self._active_color`）。
                #   · ⚠ 已知限制（**与圆角那条完全相同**）：调色板停在默认橙 "#FF6B35"
                #     与"用户压根没设过色"在**新建**时不可区分 ⇒ 新建可见区域一律白；
                #     契约已如实登记。
                if (region.get("visible")
                        and self._active_color == ACTIVE_COLOR_INITIAL_DEFAULT):
                    region["color"] = REGION_COLOR_VISIBLE_DEFAULT
                else:
                    region["color"] = self._active_color
                # 圆角（§15.3）：
                #   · 用户真的调过（>0）⇒ 一律用用户的值（普通 / mask / 可见层都一样）；
                #   · **可见层且用户没调过（<=0）⇒ 缺省 `CORNER_RADIUS_VISIBLE_DEFAULT`(12)**
                #     （v9.1 §11 用户要求；已知限制：输入框=0 与"没设过"在新建时不可区分，
                #      故新建可见区域一律 12 —— 契约已如实登记）；
                #   · 普通区域 / mask ⇒ **行为完全不变**（仍只在 >0 时才写字段）。
                if self._active_corner_radius > 0:
                    region["corner_radius_px"] = self._active_corner_radius
                elif region.get("visible"):
                    region["corner_radius_px"] = CORNER_RADIUS_VISIBLE_DEFAULT
                self._regions.append(region)
                self._regions_version += 1
                self._invalidate_auto_hidden()
                self._drawing_points = []
                self._cursor_data = None
                self.update()
                # ★ 走唯一收口：新画的区域 = 单选它（`region_selected` 照旧发最后一次闭合者）
                self._set_selection([len(self._regions) - 1], emit=True)
                self.region_finished.emit(region["name"])
            else:
                print("[RegionCanvas] 少于 3 个点，忽略闭合（当前 %d 点）"
                      % len(self._drawing_points))
            return
        # 未在绘制 → 双击命中已有区域则选中
        idx = self._hit_region(event.pos())
        if idx >= 0:
            self._set_selection([idx], emit=True)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self._zoom_at(1.25 if delta > 0 else 0.8, event.pos())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_down = True
            self.setCursor(Qt.OpenHandCursor)
        elif event.key() == Qt.Key_Escape:
            if self._drawing_points:
                self._drawing_points = []
                self.update()
            # ★ select 模式（契约 §3.1 第 4 条的加分项，**不新造快捷键**：Esc 本来就在）：
            #   清空选择；既有四模式走到这里是空操作（`_selected_indices` 只在选择模式里有意义）
            elif self._edit_mode == SELECT_MODE and self._selected_indices:
                self._set_selection([], emit=True)
                print("[RegionCanvas] 已清空选择")
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_down = False
            self.setCursor(Qt.ArrowCursor)
        super().keyReleaseEvent(event)

    def _hit_region(self, pos):
        """屏幕点是否落在某区域内（在**数据坐标**下判定；后画的优先）"""
        data = self.screen_to_data(pos)
        for i in range(len(self._regions) - 1, -1, -1):
            pts = (self._regions[i] or {}).get("points") or []
            if len(pts) >= 3 and self._point_in_polygon(data[0], data[1], pts):
                return i
        return -1

    @staticmethod
    def _point_in_polygon(x, y, pts):
        """射线法（点在多边形内）"""
        inside = False
        n = len(pts)
        j = n - 1
        for i in range(n):
            try:
                xi, yi = float(pts[i][0]), float(pts[i][1])
                xj, yj = float(pts[j][0]), float(pts[j][1])
            except (TypeError, ValueError, IndexError):
                j = i
                continue
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    # ==================================================================
    # ★ 2026-09-23 追加规格 v9.1（`_d_spec_select_mode.md` §10.1，用户原话：
    #   「小区域是优先被选中的，然后才是大区域（我指的是两者重合时）」）
    # ------------------------------------------------------------------
    # · **只**给选择模式的 ③「区域内」分支用（`_select_press` 调用）；
    #   ⛔ `_hit_region(pos)` 本体与签名**一个字都不改**（它被 `label` / `visible` /
    #      `mask` 等既有模式与双击路径共用，契约 §6.4 冻结）。
    # · 判据：包含落点的所有区域（`len(pts) >= 3` + `_point_in_polygon`，数据坐标）里
    #   取**多边形面积最小者**；面积相等 / 面积取不到 ⇒ 回退既有"后画优先"。
    # ==================================================================
    def _hit_region_smallest(self, pos):
        """"区域内"命中：重合时**面积最小者优先**（v9.1；相等才回退后画优先）

        Returns: int —— 命中的区域索引；没有命中 → -1。
        · 0 个包含 ⇒ `-1`；1 个 ⇒ 它；
        · ≥2 个 ⇒ **多边形面积最小**的那个；面积并列最小 / 面积取不到 ⇒
          回退既有"后画优先"（= `_hit_region` 的索引最大者语义）。
        ⛔ 全函数**绝不抛**：坏点/坏区域安全跳过；真异常 ⇒
          `traceback.print_exc()` + 回退 `self._hit_region(pos)`。
        """
        try:
            data = self.screen_to_data(pos)
            cands = []
            for i in range(len(self._regions)):
                try:
                    pts = (self._regions[i] or {}).get("points") or []
                    if len(pts) >= 3 and self._point_in_polygon(data[0], data[1], pts):
                        cands.append(i)
                except Exception:
                    # 坏区域/坏点：安全跳过（只留痕，不影响其它候选）
                    traceback.print_exc()
                    print("[RegionCanvas] ⚠ 选择模式：区域 #%d 的包含判定失败 ⇒ 跳过它" % i)
                    continue
            if not cands:
                return -1
            if len(cands) == 1:
                return int(cands[0])
            areas = {}
            for i in cands:
                try:
                    a = self._region_area_or_none(self._regions[i])
                except Exception:
                    traceback.print_exc()
                    print("[RegionCanvas] ⚠ 选择模式：区域 #%d 的面积取不到 ⇒ 回退「后画优先」" % i)
                    a = None
                if a is None:
                    # 面积取不到 ⇒ 回退"后画优先"（与 `_hit_region` 同序语义：索引最大者）
                    print("[RegionCanvas] ⚠ 选择模式：有候选区域面积取不到（#%d）⇒ "
                          "本次回退「后画优先」" % i)
                    return int(max(cands))
                areas[i] = float(a)
            min_area = min(areas.values())
            # 面积并列最小 ⇒ 取索引最大者（"后画优先"，与 `_hit_region` 同序语义）
            winners = [i for i in cands if areas[i] == min_area]
            return int(max(winners))
        except Exception:
            traceback.print_exc()
            print("[RegionCanvas] ⚠ 选择模式：`_hit_region_smallest` 异常 ⇒ 回退 `_hit_region`"
                  "（后画优先）")
            try:
                return int(self._hit_region(pos))
            except Exception:
                traceback.print_exc()
                print("[RegionCanvas] ⚠ 选择模式：连 `_hit_region` 回退都失败 ⇒ 视为未命中（-1）")
                return -1

    @staticmethod
    def _region_area_or_none(region):
        """区域多边形面积（**绝对值**）；取不到 → `None`（调用方回退"后画优先"）

        ★ 面积来源优先级（v9.1 §10.1）：W3 的 `analysis.polygon_area(points)`
          → 本地私有 shoelace 兜底（`_local_polygon_area`）。**绝不抛**。
        """
        if not isinstance(region, dict):
            print("[RegionCanvas] ⚠ 选择模式：区域不是 dict ⇒ 面积取不到")
            return None
        pts = region.get("points") or []
        if len(pts) < 3:
            return None
        # 顶点合法性预检（坏点/坏区域 ⇒ 面积"取不到"，由调用方回退后画优先）
        try:
            for p in pts:
                float(p[0])
                float(p[1])
        except (TypeError, ValueError, IndexError):
            traceback.print_exc()
            print("[RegionCanvas] ⚠ 选择模式：区域含非法顶点 ⇒ 面积取不到（回退「后画优先」）")
            return None
        fn = _polygon_area_fn()
        if fn is not None:
            try:
                # ★ 传**副本**：判定函数不该有机会改到画布内部状态（同 `_vertices_at` 的写法）
                pts_arg = [list(p) for p in pts]
            except Exception:
                traceback.print_exc()
                print("[RegionCanvas] ⚠ 选择模式：顶点副本构造失败 ⇒ 直接传原列表给 `polygon_area`")
                pts_arg = pts
            try:
                a = abs(float(fn(pts_arg)))
                if a != a:                               # NaN 防御
                    print("[RegionCanvas] ⚠ 选择模式：`polygon_area` 返回 NaN ⇒ 面积取不到")
                    return None
                return a
            except Exception:
                traceback.print_exc()
                print("[RegionCanvas] ⚠ 选择模式：`polygon_area` 调用失败 ⇒ 改用本地 shoelace 兜底")
        return float(_local_polygon_area(pts))

    # ==================================================================
    # ★ 2026-09-23 契约 `_d_spec_select_mode.md` §3：「选择模式」（`select`）
    # ------------------------------------------------------------------
    # 点击优先级（命中即止）：① 锚点(7px) ② 边(12px) ③ 区域内 ④ 空白清空
    #   · 公用锚点（≥2 个区域顶点重合）/ 共有边 ⇒ **多选但绝不进入编辑**（"不能编辑"）；
    #   · 独有锚点 ⇒ 单选 + **顶点拖动**（只改坐标：不增删顶点、不改顺序、不碰 `label_pos`）；
    #   · 独有边 / 区域内 ⇒ 单选（只为"选中以便命名"）。
    # ★ 几何判定（`vertices_at` / `shared_edge_partners`）的**唯一真相源在 W3 的
    #   analysis 层**；本层只消费：函数缺失 / 调用异常一律**降级为"只有命中项、不共享"**
    #   （= 单选 + 允许拖动）并留痕，**绝不让 AttributeError 冒泡**（契约 §3/B3）。
    # ★ 命中判据完全复用既有的 `_anchor_hit` / `_edge_at` / `_hit_region`
    #   （签名与默认容差一个字不动，契约 §6.4）。
    # ==================================================================
    def _tol_data(self, tol_screen):
        """屏幕容差 → 数据容差：`tol_screen / max(self._scale(), 1e-9)`（契约 §4）"""
        try:
            s = float(self._scale())
        except Exception:
            traceback.print_exc()
            s = 0.0
        if s <= 1e-9:
            s = 1e-9
        return float(tol_screen) / s

    @staticmethod
    def _region_index_list(indices):
        """区域索引列表 → 日志用的短串（如 `#0, #2`；异常 → `?`，绝不抛）"""
        try:
            return ", ".join("#%d" % int(i) for i in (indices or []))
        except (TypeError, ValueError):
            return "?"

    def _vertices_at(self, x, y):
        """所有与 `(x, y)` 距离 ≤ 容差的顶点 → `[(区域索引, 顶点号), ...]`

        ★ 判定委托给 W3 的 `spatial_region_analysis.vertices_at`（**单一真相源**）。
        Returns:
            list —— 命中项（可能为空列表 = 没有共享者）；
            **None** —— 判定不可用（W3 未落地 / import 失败 / 调用异常）⇒ 调用方
                       必须降级为"只有命中项、不共享"（单选 + 允许拖动）。**绝不抛**。
        """
        try:
            from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as _SREG
        except Exception:
            traceback.print_exc()
            print("[RegionCanvas] ⚠ 选择模式：无法 import analysis 层 ⇒ 降级为「只有命中项、不共享」"
                  "（公用锚点暂时不能多选）")
            return None
        fn = getattr(_SREG, "vertices_at", None)
        if not callable(fn):
            print("[RegionCanvas] ⚠ 选择模式：analysis 层尚未提供 `vertices_at` ⇒ "
                  "降级为「只有命中项、不共享」（公用锚点暂时不能多选）")
            return None
        try:
            # ★ 传**副本**：W2/W3 的判定函数不该有机会改到画布内部状态
            res = fn(float(x), float(y), copy_regions(self._regions),
                     self._tol_data(ANCHOR_TOL_SCREEN))
            out = []
            for item in (res or []):
                try:
                    pair = (int(item[0]), int(item[1]))
                except (TypeError, ValueError, IndexError):
                    continue
                if pair not in out:
                    out.append(pair)
            return out
        except Exception:
            traceback.print_exc()
            print("[RegionCanvas] ⚠ 选择模式：`vertices_at` 调用失败 ⇒ "
                  "降级为「只有命中项、不共享」（公用锚点暂时不能多选）")
            return None

    def _edge_partners(self, index, edge_no):
        """区域 `index` 第 `edge_no` 条边的**共享伙伴**区域索引（升序、去重、不含自己）

        ★ 判定委托给 W3 的 `spatial_region_analysis.shared_edge_partners`（**单一真相源**）。
        Returns:
            list —— 伙伴索引（`[]` = 独有边）；**None** = 判定不可用（W3 未落地 / 调用异常）
                    ⇒ 调用方降级为"独有边"（只选中自己，不进入编辑）。**绝不抛**。
        """
        try:
            from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as _SREG
        except Exception:
            traceback.print_exc()
            print("[RegionCanvas] ⚠ 选择模式：无法 import analysis 层 ⇒ 降级为「独有边」"
                  "（共有边暂时不能多选）")
            return None
        fn = getattr(_SREG, "shared_edge_partners", None)
        if not callable(fn):
            print("[RegionCanvas] ⚠ 选择模式：analysis 层尚未提供 `shared_edge_partners` ⇒ "
                  "降级为「独有边」（共有边暂时不能多选）")
            return None
        try:
            res = fn(int(index), int(edge_no), copy_regions(self._regions),
                     self._tol_data(EDGE_TOL_SCREEN))
            out = []
            for raw in (res or []):
                try:
                    other = int(raw)
                except (TypeError, ValueError):
                    continue
                if other == int(index) or other in out or not (0 <= other < len(self._regions)):
                    continue
                out.append(other)
            return out
        except Exception:
            traceback.print_exc()
            print("[RegionCanvas] ⚠ 选择模式：`shared_edge_partners` 调用失败 ⇒ "
                  "降级为「独有边」（共有边暂时不能多选）")
            return None

    @staticmethod
    def _region_valid_point_indices(region):
        """`points` 里**合法点**的原始下标（顺序与 `_region_screen_points` 一一对应）

        ★ 为什么需要：`_region_screen_points` 会**跳过非法点**，`_anchor_hit` 返回的
          顶点号因此是"合法点序号"；写回 `points` 必须换回原始下标，否则会改错顶点。
        """
        out = []
        for k, p in enumerate(((region or {}).get("points") or [])):
            try:
                float(p[0])
                float(p[1])
            except (TypeError, ValueError, IndexError):
                continue
            out.append(k)
        return out

    def _vertex_raw_no(self, index, vertex_no):
        """`_anchor_hit` 的顶点号（合法点序号）→ `points` 的**原始下标**；拿不到 → -1"""
        try:
            idx = int(index)
        except (TypeError, ValueError):
            return -1
        if not (0 <= idx < len(self._regions)):
            return -1
        try:
            k = int(vertex_no)
        except (TypeError, ValueError):
            return -1
        try:
            mapping = self._region_valid_point_indices(self._regions[idx])
        except Exception:
            traceback.print_exc()
            return k
        if 0 <= k < len(mapping):
            return mapping[k]
        return -1

    def _vertex_data(self, index, raw_no):
        """区域 `index` 第 `raw_no` 个顶点的数据坐标；非法/越界 → None（窄类型兜底，不抛）"""
        try:
            idx = int(index)
            k = int(raw_no)
        except (TypeError, ValueError):
            return None
        if not (0 <= idx < len(self._regions)) or k < 0:
            return None
        region = self._regions[idx]
        if not isinstance(region, dict):
            return None
        try:
            p = (region.get("points") or [])[k]
            return (float(p[0]), float(p[1]))
        except (TypeError, ValueError, IndexError):
            return None

    def _select_press(self, pos):
        """选择模式的左键按下（契约 §3.1 优先级，命中即止）"""
        # ---- ① 锚点（屏幕容差沿用既有 7.0） ----
        anchor = self._anchor_hit(pos, ANCHOR_TOL_SCREEN)
        if anchor[0] >= 0:
            ri = int(anchor[0])
            raw_no = self._vertex_raw_no(ri, anchor[1])
            data = self._vertex_data(ri, raw_no) if raw_no >= 0 else None
            if data is None:
                data = self.screen_to_data(pos)
            # 所有与该点重合的顶点（一次判定拿到"谁和谁公用这个锚点"）
            shared = self._vertices_at(data[0], data[1])
            involved = []
            if shared is not None:
                for pair in shared:
                    if pair[0] not in involved and 0 <= pair[0] < len(self._regions):
                        involved.append(pair[0])
            if ri not in involved:
                involved.insert(0, ri)
            if len(involved) >= 2:
                # 公用锚点 ⇒ 多选，**绝不进入拖动**
                self._set_selection(involved, emit=True)
                print("[RegionCanvas] 共享锚点：同时选中 %d 个区域（%s）⇒ 不能编辑"
                      "（要单独编辑请点某区域独有的边或锚点）"
                      % (len(involved), self._region_index_list(involved)))
                return
            # 独有锚点 ⇒ 单选 + 进入顶点拖动
            self._set_selection([ri], emit=True)
            self._begin_vertex_drag(ri, raw_no, data)
            return
        # ---- ② 边（屏幕容差沿用既有 12.0） ----
        edge = self._edge_at(pos, EDGE_TOL_SCREEN)
        if edge[0] >= 0:
            ri = int(edge[0])
            edge_no = int(edge[1])
            partners = self._edge_partners(ri, edge_no)
            sel = [ri]
            for other in (partners or []):
                if other not in sel:
                    sel.append(other)
            if len(sel) >= 2:
                # 共有边 ⇒ 多选，**不能编辑**
                self._set_selection(sel, emit=True)
                print("[RegionCanvas] 共享边：同时选中 %d 个区域（%s）⇒ 不能编辑"
                      % (len(sel), self._region_index_list(sel)))
                return
            # 独有边 ⇒ 只选中自己（**不拖动**：本条只为"选中以便命名"）
            self._set_selection([ri], emit=True)
            return
        # ---- ③ 区域内 ⇒ **重合时面积最小者优先**（用户 v9.1 需求）；相等才回退后画优先 ----
        #   ★ v9.1 §10.1：改用新私有 `_hit_region_smallest`（被隐形区域包住的小区域也能选中）；
        #     ⛔ `_hit_region(pos)` 本体与签名一个字不动（契约 §6.4，既有多模式共用）。
        hit = self._hit_region_smallest(pos)
        if hit >= 0:
            self._set_selection([hit], emit=True)
            return
        # ---- ④ 空白 ⇒ 清空选择（`region_selected(-1)` 语义沿用既有约定） ----
        self._set_selection([], emit=True)
        print("[RegionCanvas] 已清空选择")

    def _begin_vertex_drag(self, index, raw_no, data):
        """进入顶点拖动（只在"独有锚点"上调用；坐标与顶点号非法则**不进入**）"""
        try:
            idx = int(index)
            k = int(raw_no)
        except (TypeError, ValueError):
            return False
        if not (0 <= idx < len(self._regions)) or k < 0 or data is None:
            return False
        if self._vertex_data(idx, k) is None:
            return False
        self._dragging_vertex = idx
        self._drag_vertex_no = k
        self._drag_vertex_start = (float(data[0]), float(data[1]))
        try:
            self.setCursor(Qt.ClosedHandCursor)
        except Exception:
            traceback.print_exc()
        return True

    def _move_dragged_vertex(self, data):
        """把正在拖动的顶点写成 `data`（**只改坐标**）

        ⛔ 不增删顶点、不改顺序、**不碰 `label_pos`**（那是「编辑注释」模式的事，契约 §3.2）；
        ⛔ 本方法**不发任何信号、不写盘**（落盘只在 `_finish_vertex_drag` 里发生一次）。
        Returns: bool —— 是否真的写进去了
        """
        try:
            idx = int(self._dragging_vertex)
            k = int(self._drag_vertex_no)
        except (TypeError, ValueError):
            return False
        if not (0 <= idx < len(self._regions)) or k < 0:
            return False
        region = self._regions[idx]
        if not isinstance(region, dict):
            return False
        pts = region.get("points")
        if not isinstance(pts, list) or not (0 <= k < len(pts)):
            return False
        try:
            pts[k] = [float(data[0]), float(data[1])]
        except (TypeError, ValueError, IndexError):
            return False
        return True

    def _finish_vertex_drag(self):
        """结束顶点拖动（契约 §3.2/§5）：坐标**确实变了** ⇒ 发 `region_geometry_changed(ri)` 一次

        · 坐标未变（只按不拖 / 拖回原点）⇒ **不发信号**；
        · 无论变没变都清理拖动状态并恢复模式光标；
        · 画布**自己绝不写盘**：落盘由 bind 收到信号后的既有链路负责。
        Returns: bool —— 是否发了信号
        """
        try:
            idx = int(self._dragging_vertex)
        except (TypeError, ValueError):
            idx = -1
        raw_no = self._drag_vertex_no
        start = self._drag_vertex_start
        # 先无条件清理临时状态（中途 return 也不会留半截拖动状态）
        self._dragging_vertex = -1
        self._drag_vertex_no = -1
        self._drag_vertex_start = None
        self._restore_mode_cursor()
        if idx < 0 or start is None:
            return False
        cur = self._vertex_data(idx, raw_no)
        if cur is None:
            return False
        if (abs(cur[0] - start[0]) <= VERTEX_MOVE_EPS
                and abs(cur[1] - start[1]) <= VERTEX_MOVE_EPS):
            return False                       # ★ 同值 ⇒ 不发信号、不落盘
        self._regions_version += 1
        self.update()
        try:
            self.region_geometry_changed.emit(int(idx))
        except Exception:
            traceback.print_exc()
        return True

    # ==================================================================
    # 绘制
    # ==================================================================
    def resizeEvent(self, event):
        """窗口尺寸变化后仍居中/等比（base_scale 由 width/height 推导，故自动成立）"""
        super().resizeEvent(event)
        self.update()

    # ==================================================================
    # Phase 3⑤：「底图 + spot」预渲染缓存（绘制卡顿的根治手段）
    # ------------------------------------------------------------------
    # 🔴 原缺陷：`mouseMoveEvent` 每动一次就 `update()`，而 paintEvent 会重画
    #    「底图 + 全部 spot + 多边形」；底图有缩放缓存、**spot 没有** ⇒ 每动一下
    #    鼠标就把几千个点重铺一遍。
    # ★ 现在：底图+spot 预渲染进一张 QPixmap，paintEvent 只 `drawPixmap` 它；
    #    多边形/标签/草稿折线仍每帧画（很便宜）。缓存键含尺寸/缩放/平移/spots 指纹/
    #    底图指纹 ⇒ 只有这些变了才重建。**缓存命中时绝不重铺 spot**。
    # ==================================================================
    def _content_cache_key(self):
        return (int(self.width()), int(self.height()),
                round(float(self._zoom), 6),
                round(float(self._pan.x()), 3), round(float(self._pan.y()), 3),
                int(self._spots_version), int(self._base_version),
                id(self._base_pixmap) if self._base_pixmap is not None else 0)

    def _ensure_content_cache(self):
        """返回「底图 + spot」缓存 pixmap；未命中才重建一次。"""
        key = self._content_cache_key()
        if self._content_cache is not None and key == self._content_key:
            return self._content_cache                    # ★ 命中：不重铺点
        w = max(1, int(self.width()))
        h = max(1, int(self.height()))
        pm = QPixmap(w, h)
        pm.fill(self._bg_color)
        p = QPainter(pm)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            self._paint_base_and_spots(p)
        finally:
            try:
                p.end()
            except Exception:
                pass
        self._content_cache = pm
        self._content_key = key
        self._content_builds += 1
        return pm

    def _paint_base_and_spots(self, painter):
        """把「组织底图 + 散点」画进缓存 pixmap（只在重建时执行）"""
        # ---- 1) 组织底图（图像像素 = 数据坐标 × scalef ⇒ 用同一变换绘制）----
        if self._base_pixmap is not None and not self._base_pixmap.isNull():
            try:
                scalef = self._base_scalef or 1.0
                # 底图在数据坐标下的范围：0..(px/scalef)
                iw = self._base_pixmap.width() / scalef
                ih = self._base_pixmap.height() / scalef
                sx0, sy0 = self._data_to_screen_f(0.0, 0.0)
                sx1, sy1 = self._data_to_screen_f(iw, ih)
                tw = max(1, int(abs(sx1 - sx0)))
                th = max(1, int(abs(sy1 - sy0)))
                # ★ 走缓存（重建时也不能每帧缩放 1799×2000 的大图）
                base_scaled = self._scaled_base_for(tw, th)
                if base_scaled is not None:
                    painter.setOpacity(0.55)
                    painter.drawPixmap(QRectF(min(sx0, sx1), min(sy0, sy1), tw, th),
                                       base_scaled, QRectF(base_scaled.rect()))
                    painter.setOpacity(1.0)
            except Exception:
                pass

        # ---- 2) 散点（同标签同色，确定性）----
        s = self._scale()
        radius = 2.0 if s < 2 else (3.0 if s < 6 else 4.0)
        for i in range(min(len(self._xs), len(self._ys))):
            lab = self._labels[i] if i < len(self._labels) else "NA"
            key = str(lab) if lab is not None and str(lab) != "" else "NA"
            color = self._label_colors.get(key, QColor(_NA_COLOR))
            sx, sy = self._data_to_screen_f(self._xs[i], self._ys[i])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(sx, sy), radius, radius)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # ---- 1+2) 底图与 spot：整张缓存 blit（命中时**绝不重铺**）----
        cached = self._ensure_content_cache()
        if cached is not None:
            painter.drawPixmap(0, 0, cached)
        else:
            painter.fillRect(self.rect(), self._bg_color)

        # ---- 3) 已有区域（半透明填充 + 逐边显隐轮廓 + 圆角 + 注释）----
        # ★ 先算一次"可见区域范围层罩住了哪些普通区域"（每帧一次，别在循环里重复算）
        visible_outline = self._visible_outline_indices()
        for i, region in enumerate(self._regions):
            self._draw_region(painter, region, i, visible_outline)

        # ---- 3b) 已画区域的顶点锚点（Phase 4②：留作参考，可被显式复用）----
        self._draw_anchors(painter)

        # ---- 3c) 选择模式（契约 §3.3）：把**选中的每一个**区域都画成选中态 ----
        self._draw_selection(painter)

        # ---- 4) 正在画的多边形（实线预览 + 橡皮筋）----
        if self._drawing_points:
            path = QPolygonF()
            for p in self._drawing_points:
                sx, sy = self._data_to_screen_f(p[0], p[1])
                path.append(QPointF(sx, sy))
            painter.setBrush(Qt.NoBrush)
            pen = QPen(QColor(self._active_color))
            pen.setWidth(max(1, int(self._active_dash_width)))
            painter.setPen(pen)
            painter.drawPolyline(path)
            for p in self._drawing_points:
                sx, sy = self._data_to_screen_f(p[0], p[1])
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(self._active_color)))
                painter.drawEllipse(QPointF(sx, sy), 3.5, 3.5)
            if self._cursor_data is not None:
                lx, ly = self._data_to_screen_f(*self._cursor_data)
                painter.setPen(pen)
                painter.drawLine(QPointF(path.last()), QPointF(lx, ly))
        painter.end()

    def _region_screen_points(self, region):
        """区域顶点 → 屏幕 QPointF 列表（非法点跳过；与判定无关，纯呈现）"""
        out = []
        for p in ((region or {}).get("points") or []):
            try:
                sx, sy = self._data_to_screen_f(float(p[0]), float(p[1]))
            except (TypeError, ValueError, IndexError):
                continue
            out.append(QPointF(sx, sy))
        return out

    def _visible_outline_indices(self):
        """哪些**普通区域**该画虚线边界（被"可见区域"范围层罩住的那些）。

        Returns:
            None —— **不过滤**（全画）。两种情况：
                    · 画布上一个"可见区域"范围层都没有（用户还没圈范围 ⇒ 照旧全画）；
                    · W2 的 `canvas_visible_region_indices` 还没交付（占位，**留痕一次**）。
            set[int] —— 只给这些**普通区域索引**画虚线边界。

        ★ 判定本身**不在这里**（避免第二份真相源）：命中判定在 W2 的 analysis 层，
          画布只消费它的返回值。范围层自身（`mask`/`visible`）永远照自己的淡样式画。
        """
        global _CANVAS_VISIBLE_WARNED
        # ★ 每帧只算一次（进 W2 的 analysis 做多边形重叠判定，别在 paint 里反复调）：
        #   键 = (区域版本, spot 版本)；两者变了才重算。
        key = (self._regions_version, self._spots_version)
        if self._visible_outline_key == key:
            return self._visible_outline_cache
        result = None
        has_layer = any(isinstance(r, dict) and r.get("visible") for r in self._regions)
        if has_layer:
            fn = _canvas_visible_fn()
            if fn is None:
                if not _CANVAS_VISIBLE_WARNED:
                    _CANVAS_VISIBLE_WARNED = True
                    print("[RegionCanvas] ⚠ 可见区域范围层已画，但 analysis 层尚未提供 "
                          "`canvas_visible_region_indices` ⇒ 暂时**全画**虚线边界"
                          "（占位，不是最终行为）")
            else:
                try:
                    # ★ 传**副本**：W2 的判定函数不该有机会改到画布内部状态
                    res = fn(copy_regions(self._regions), list(self._analysis_spots))
                    result = set(int(i) for i in (res or []))
                except Exception:
                    result = None            # 判定失败也不许把画布画空
        self._visible_outline_key = key
        self._visible_outline_cache = result
        return result

    def _draw_region(self, painter, region, index=-1, visible_outline=None):
        """画一个区域：半透明填充 + **逐边显隐**轮廓 + 圆角 + 注释锚点。

        ★ §15.1 总原则：填充与判定**永远**用原始尖角 `points`；
          隐藏边 / 圆角 / 注释位置只影响"画出来给人看的线"。
        """
        pts = (region or {}).get("points") or []
        if len(pts) < 3:
            return
        screen = self._region_screen_points(region)
        n = len(screen)
        if n < 3:
            return
        poly = QPolygonF()
        for p in screen:
            poly.append(p)

        color = QColor(str(region.get("color") or "#FF6B35"))
        if not color.isValid():
            color = QColor("#FF6B35")

        # ★ 两种**范围层**（2026-09）：`mask` = 隐形区域、`visible` = 可见区域。
        #   都是"能看见但很淡、不画名字"，但**样式必须能区分**（用户要在画布上分别看出哪个是哪个）：
        #     · 隐形区域 = 自己的区域色 + 细密虚线(dw1)
        #     · 可见区域 = 主题 token 色 + 粗长虚线(dw2)
        is_mask = bool(region.get("mask"))
        is_visible_layer = bool(region.get("visible"))
        is_layer = is_mask or is_visible_layer
        layer = layer_outline_style('mask' if is_mask else 'visible', color) if is_layer else None

        # ---- 1) 半透明填充（判定用的原始多边形，绝不变形）----
        fill = QColor(color)
        fill.setAlpha(int(layer['fill_alpha']) if layer else 60)
        painter.setBrush(QBrush(fill))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(poly)

        # ---- 2) 轮廓：可见边分段 + 相邻可见边之间倒角（圆角）----
        try:
            dw = max(1, int(region.get("dash_width", 2)))
        except (TypeError, ValueError):
            dw = 2
        try:
            dg = max(1, int(region.get("dash_gap", 6)))
        except (TypeError, ValueError):
            dg = 6
        if layer is not None:
            dw = int(layer['width'])
            dash = layer['dash']
        else:
            dash = (float(dw), float(dg))
        # ★ v9.1 §11：**可见层**且 `corner_radius_px` **缺失/None** ⇒ 取 12；
        #   显式给了值（含 0）⇒ 以给的为准。普通区域 / mask：缺省仍是 0（旧行为不变）。
        try:
            raw_radius = region.get("corner_radius_px", None)
        except Exception:
            traceback.print_exc()
            print("[RegionCanvas] ⚠ 读取 corner_radius_px 失败 ⇒ 按缺省处理")
            raw_radius = None
        if raw_radius is None and is_visible_layer:
            radius_px = int(CORNER_RADIUS_VISIBLE_DEFAULT)
        else:
            try:
                radius_px = int(raw_radius or 0)
            except (TypeError, ValueError):
                traceback.print_exc()
                print("[RegionCanvas] ⚠ corner_radius_px 非法（%r）⇒ 按 0 处理" % (raw_radius,))
                radius_px = 0
        radius = self._screen_corner_radius(radius_px)

        # ★ 可见区域范围层：**决定普通区域的虚线边界画不画**
        #   （`None` = 不做过滤/全画；规则本身在 W2 的 analysis 层，画布不自己写一份）
        if (not is_layer) and (visible_outline is not None) and (index not in visible_outline):
            draw_boundary = False
        else:
            draw_boundary = True

        visible, hidden = self._visible_and_hidden_edges(index, region, n)
        runs = self._split_visible_runs(visible, n)

        if draw_boundary:
            line_color = QColor(layer['color']) if layer is not None else QColor(color)
            if layer is not None:
                line_color.setAlpha(int(layer['alpha']))   # 低透明度（仍看得见、仍能点中）
            pen = QPen(line_color)
            pen.setWidth(dw)
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern([float(dash[0]), float(dash[1])])
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for run_indices, is_closed in runs:
                run_pts = [screen[i % n] for i in run_indices]
                path = self._rounded_polyline(run_pts, radius, is_closed)
                if path is not None:
                    painter.drawPath(path)

            # ---- 3) 已隐藏的边：**灰调 + 更低不透明度**（一眼可辨；但仍画着 ⇒ 仍能点回来）----
            #   旧样式（同色 + alpha 89）在组织图上几乎看不出差别 —— 用户因此以为"没生效"。
            #   ★ 数据里的 `edge_override` 照旧生效（画布不再提供"切它"的入口，但读/画都在）。
            hidden_color = edge_style_colors()['hidden']
            for e, kind in sorted(hidden.items()):
                ghost = QColor(hidden_color)
                ghost.setAlpha(70 if kind == "manual" else 40)
                gp = QPen(ghost)
                gp.setWidth(dw)
                gp.setStyle(Qt.CustomDashLine)
                gp.setDashPattern([float(dash[0]), float(dash[1])])
                painter.setPen(gp)
                painter.drawLine(screen[e % n], screen[(e + 1) % n])
        # ⛔ 原 3b)"edges 模式悬停高亮"已随该模式退休（2026-09），不留死代码。

        # ---- 4) 注释：`label_pos` 优先，否则质心 ----
        #   ★ v4（用户 2026-09-20 反馈）起：**范围层（`mask` / `visible`）也画注释名字** ——
        #     用户原话："注释没有在一个可见区域框选完成后在图中实时显示出注释名字，
        #     只有确认并重绘后才在结果图预览里见到"。
        #   ⇒ 原 `if is_layer: return`（两种范围层都不画名字）**已删除**；
        #     范围层与普通区域**走同一段注释绘制逻辑**（名字为空则跳过，
        #     `label` 模式下的拖动也照旧走 `_label_rect_at` / `_write_label_pos`）。
        name = str(region.get("name") or "")
        if not name:
            return
        anchor = self._label_anchor_screen(index, region)
        if anchor is None:
            return
        font = QFont()
        try:
            fs = max(6, int(region.get("label_font_size", 12)))
        except (TypeError, ValueError):
            fs = 12
        font.setPointSize(fs)
        painter.setFont(font)
        fc = QColor(str(region.get("label_font_color") or "#FFFFFF"))
        if not fc.isValid():
            fc = QColor("#FFFFFF")
        painter.setPen(QPen(fc))
        painter.setBrush(Qt.NoBrush)
        # ★ 画字与"能不能拖"用**同一个矩形口径**（`_label_rect_screen`），不会各写一份
        painter.drawText(self._label_rect_screen(anchor, name, fs), Qt.AlignCenter, name)
        # label 模式 / 悬停时给锚点画小十字 → 用户知道哪儿能拖
        if self._edit_mode == "label" or self._hover_label:
            painter.drawLine(QPointF(anchor.x() - 5, anchor.y()),
                             QPointF(anchor.x() + 5, anchor.y()))
            painter.drawLine(QPointF(anchor.x(), anchor.y() - 5),
                             QPointF(anchor.x(), anchor.y() + 5))

    # ==================================================================
    # Phase 4②③：注释矩形 / 锚点命中（画与命中同口径）
    # ==================================================================
    @staticmethod
    def _label_rect_screen(anchor, name, font_size):
        """注释的**屏幕矩形**（画字与拖动命中判定共用；宽度按字数估）"""
        try:
            fs = max(6, int(font_size))
        except (TypeError, ValueError):
            fs = 12
        try:
            text = str(name or "")
        except Exception:
            text = ""
        w = max(120.0, len(text) * fs * 1.15 + 18.0)
        h = max(24.0, fs * 1.7)
        return QRectF(anchor.x() - w / 2.0, anchor.y() - h / 2.0, w, h)

    def _label_rect_at(self, pos):
        """屏幕点命中的注释矩形所在区域索引（后画的优先）；没命中 → -1

        ★ 与画字用同一矩形 ⇒ "看得见就能拖"，不需要先切「编辑注释」模式。
        """
        try:
            px, py = float(pos.x()), float(pos.y())
        except Exception:
            return -1
        for i in range(len(self._regions) - 1, -1, -1):
            region = self._regions[i]
            if not isinstance(region, dict):
                continue
            name = str(region.get("name") or "")
            if not name:
                continue
            anchor = self._label_anchor_screen(i, region)
            if anchor is None:
                continue
            try:
                fs = int(region.get("label_font_size", 12))
            except (TypeError, ValueError):
                fs = 12
            if self._label_rect_screen(anchor, name, fs).contains(QPointF(px, py)):
                return i
        return -1

    def _anchor_hit(self, pos, tol=7.0):
        """屏幕点命中的最近**区域顶点** → (区域索引, 顶点号)；没命中 → (-1, -1)。

        ★ 只用于"用户正点在锚点上"的**显式复用**（Phase 4②）。
          **不做任何自动吸附**：鼠标在别处时落点就是鼠标位置本身。
        """
        try:
            px, py = float(pos.x()), float(pos.y())
        except Exception:
            return (-1, -1)
        best = (-1, -1)
        best_d = float(tol)
        for i in range(len(self._regions) - 1, -1, -1):
            for j, p in enumerate(self._region_screen_points(self._regions[i])):
                d = ((px - p.x()) ** 2 + (py - p.y()) ** 2) ** 0.5
                if d <= best_d:
                    best_d = d
                    best = (i, j)
        return best

    def _draw_anchors(self, painter):
        """把已画区域的每个顶点画成小圆点（颜色 = 区域色）—— 供下一轮绘制参考。

        ★ 用户明确要「只显示当参考、**不自动吸**」：这里只画点；
          真正复用发生在"左键正好点在点上"（见 `mousePressEvent`）。
        ★ 2026-09-23：`select`（选择模式）也用同一套锚点悬停圈（它同样以"点锚点"为主线），
          既有四模式的判据（`_draw_like()`）**一个字不改**。
        """
        hover = self._hover_anchor if (self._draw_like() or self._edit_mode == SELECT_MODE) else (-1, -1)
        for i, region in enumerate(self._regions):
            color = QColor(str((region or {}).get("color") or "#FF6B35"))
            if not color.isValid():
                color = QColor("#FF6B35")
            dot = QColor(color)
            dot.setAlpha(210)
            for j, p in enumerate(self._region_screen_points(region)):
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(dot))
                painter.drawEllipse(p, 2.6, 2.6)
                if hover == (i, j):
                    pen = QPen(color)
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(p, 6.5, 6.5)

    def _draw_selection(self, painter):
        """选择模式：把 `_selected_indices` 里的区域**都**画成选中态（契约 §3.3）。

        ★ **既有四个模式（`draw`/`visible`/`label`/`mask`）的画面逐像素不变** ——
          本方法只在 `select` 模式下画。⚠ 如实说明：`region_canvas.py` **原本没有任何
          "选中态"绘制**（`_draw_region` 不读 `_selected_index`；全文件唯一近似物是
          `_draw_anchors` 的锚点**悬停**圈，而那是悬停不是选中）⇒ 本方法即"选中样式"
          的落地处，且只作用于新模式，不去改老模式的画面。
        ★ 颜色**不硬编码**：走主题 token `{v}_mutant_color`（与按钮"选中态=变异色"同口径）。
        ★ 多选 ⇒ 逐个区域画同一套样式（用户一眼看出"这几个被一起选中了"）。
        ★ 只读 `_selected_indices` / `_regions`，不写任何状态；异常一律留痕，绝不打断重绘。
        """
        if self._edit_mode != SELECT_MODE or not self._selected_indices:
            return
        try:
            styles = _theme_styles()
            accent = styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))
            color = QColor(str(accent))
            if not color.isValid():
                color = QColor('#FF6B35')
            for idx in list(self._selected_indices):
                if not (0 <= idx < len(self._regions)):
                    continue
                screen = self._region_screen_points(self._regions[idx])
                if len(screen) < 2:
                    continue
                poly = QPolygonF()
                for p in screen:
                    poly.append(p)
                pen = QPen(color)
                pen.setWidth(2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPolygon(poly)
                # 顶点小环：告诉用户"这些点可以（独有时）拖动"
                ring = QColor(color)
                ring.setAlpha(200)
                ring_pen = QPen(ring)
                ring_pen.setWidth(1)
                painter.setPen(ring_pen)
                for p in screen:
                    painter.drawEllipse(p, 5.0, 5.0)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # Phase 3①②④：逐边显隐 / 注释锚点 / 圆角（**仅呈现**，判定不受影响）
    # ==================================================================
    @staticmethod
    def _edge_override_map(region):
        """`edge_override` → {边号(int): 'show'|'hide'}（非法项丢弃）"""
        out = {}
        ov = (region or {}).get("edge_override")
        if isinstance(ov, dict):
            for k, v in ov.items():
                try:
                    i = int(k)
                except (TypeError, ValueError):
                    continue
                s = str(v or "").strip().lower()
                if s in ("show", "hide"):
                    out[i] = s
        return out

    def _auto_hidden_for(self, index, region):
        """该区域「自动隐藏」的边号集合（规则在 W2 的 analysis 层；拿不到 → 空集）。

        ⛔⛔ **画布已不再调用本函数**（裁定：所见即所得 —— 用户删掉了"出界不画"那套
          自动规则，导出侧也不再判出界）。画布的显示与 `edges` 模式点击默认值
          **只看 `edge_override`**，没有 override 的边一律显示。
        ★ 保留原因（协调者裁定"有疑问就留着，别为清理引入风险"）：
          · 唯一调用方 `_visible_and_hidden_edges` / `_toggle_edge_at` 已解耦；
          · W2 的 `spatial_region_analysis.auto_hidden_edge_indices` **本体原样保留**，
            他们自己的 `visible_edge_indices`/`region_outline_paths` 仍可用它做中间量；
          · 本函数是那个规则的**只读消费口**，留着不影响任何显示（全仓已无调用方）。
        ★ 单一真相源：不在这里重写"边跑到图外"的判定。
        """
        key = (self._spots_version, self._regions_version)
        if self._auto_hidden_key != key:
            self._auto_hidden_cache = {}
            self._auto_hidden_key = key
        if index in self._auto_hidden_cache:
            return self._auto_hidden_cache[index]
        hidden = set()
        fn = _auto_hidden_edge_fn()
        if fn is not None and index >= 0:
            shapes = []
            if self._auto_hidden_shape is not None:
                shapes.append(self._auto_hidden_shape)
            for s in ("rows", "xy"):
                if s not in shapes:
                    shapes.append(s)
            for shape in shapes:
                try:
                    spots = self._analysis_spots if shape == "rows" else (list(self._xs), list(self._ys))
                    res = fn(region, spots)
                    hidden = set(int(e) for e in (res or []))
                    self._auto_hidden_shape = shape
                    break
                except Exception:
                    continue
        self._auto_hidden_cache[index] = hidden
        return hidden

    def _screen_corner_radius(self, radius_px):
        """`corner_radius_px`（§15.3：单位 = **输出图像像素**）→ 画布上的屏幕半径。

        ⚠ 这是**预览口径**，不是 1:1 映射（输出图的 px/数据 比例只有 R 侧知道）：
          这里直接按"屏幕像素"画，保证 0..40 的改动**肉眼立刻可见**（用户要的即时预览）。
          若你要求严格按比例预览，把下面这行换成
          `int(round(r * self._scale() / max(self._base_scalef or 1.0, 1e-9)))`
          即可（单点改动）。取值一律夹紧在 0..40。
        """
        try:
            r = int(radius_px or 0)
        except (TypeError, ValueError):
            r = 0
        return max(0, min(40, r))

    def _visible_and_hidden_edges(self, index, region, n):
        """画布上"这条边显示还是隐藏" → (可见边号 list, {边号: 'manual'})

        ★★ 裁定（**所见即所得**）：画布**只**看用户显式 `edge_override`。
          · `"hide"` → 隐藏（手动，35% 透明度）；
          · `"show"` 或**缺省** → **显示**。
          ⛔ 画布**不再**用"出界自动隐藏"规则（`SREG.auto_hidden_edge_indices`）：
            用户已裁定删掉那套规则、导出侧也不再判出界 ⇒ 若画布还按它隐藏，
            就会出现"画布上没这条边、出图却有"的所见非所得。
          （`index` 参数保留只为不改调用方签名，本函数已不使用它，
            因此返回的 hidden 里**只会**出现 `'manual'`。）
        """
        ov = self._edge_override_map(region)
        visible = []
        hidden = {}
        for e in range(n):
            if ov.get(e) == "hide":
                hidden[e] = "manual"
            else:
                visible.append(e)          # 'show' 或缺省 → 显示
        return visible, hidden

    @staticmethod
    def _split_visible_runs(visible, n):
        """连续可见边 → [(屏幕点号列表, 是否闭合环), ...]

        全可见 ⇒ 一个闭合环；否则在隐藏边处断开成若干开放折线。
        """
        vis = set(visible)
        if n < 3:
            return []
        if len(vis) == n:
            return [(list(range(n)), True)]
        hidden_edges = [e for e in range(n) if e not in vis]
        if not hidden_edges:
            return [(list(range(n)), True)]
        start = hidden_edges[0]
        runs = []
        cur = []
        for k in range(1, n + 1):
            e = (start + k) % n
            if e in vis:
                if not cur:
                    cur = [e]
                cur.append((e + 1) % n)
            else:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
        if len(cur) >= 2:
            runs.append(cur)
        return [(r, False) for r in runs]

    @staticmethod
    def _rounded_polyline(pts, radius, closed):
        """带圆角的折线/闭合多边形 → QPainterPath（屏幕坐标；radius 单位 = 屏幕像素）

        `radius <= 0` ⇒ 原样尖角。倒角用 `quadTo`，半径按相邻边长夹紧（不会翻边）。
        """
        path = QPainterPath()
        n = len(pts)
        if n < 2:
            return None
        if radius <= 0 or n < 3:
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
            if closed and n >= 3:
                path.closeSubpath()
            return path

        def trim(a, b, r):
            dx = b.x() - a.x()
            dy = b.y() - a.y()
            d = (dx * dx + dy * dy) ** 0.5
            if d <= 1e-9:
                return QPointF(a)
            r = min(r, d * 0.5)
            return QPointF(a.x() + dx / d * r, a.y() + dy / d * r)

        if closed:
            count = n
            offset = 0
        else:
            count = n - 2
            offset = 1
            path.moveTo(pts[0])
        for k in range(count):
            i = (offset + k) % n
            cur = pts[i]
            prev = pts[(i - 1) % n]
            nxt = pts[(i + 1) % n]
            enter = trim(cur, prev, float(radius))
            leave = trim(cur, nxt, float(radius))
            if closed and k == 0:
                path.moveTo(enter)
            else:
                path.lineTo(enter)
            path.quadTo(cur, leave)
        if closed:
            path.closeSubpath()
        else:
            path.lineTo(pts[n - 1])
        return path

    def _label_anchor_data(self, index, region):
        """注释锚点（数据坐标）：`label_pos` 优先，否则质心；都拿不到 → None"""
        lp = (region or {}).get("label_pos")
        if isinstance(lp, (list, tuple)) and len(lp) >= 2:
            try:
                return (float(lp[0]), float(lp[1]))
            except (TypeError, ValueError):
                pass
        xs, ys = [], []
        for p in ((region or {}).get("points") or []):
            try:
                xs.append(float(p[0]))
                ys.append(float(p[1]))
            except (TypeError, ValueError, IndexError):
                continue
        if not xs:
            return None
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def _label_anchor_screen(self, index, region):
        data = self._label_anchor_data(index, region)
        if data is None:
            return None
        try:
            sx, sy = self._data_to_screen_f(float(data[0]), float(data[1]))
        except (TypeError, ValueError, IndexError):
            return None
        return QPointF(sx, sy)

    def _write_label_pos(self, index, xy):
        """写 `label_pos`（拖动中每帧调用；**不**动 auto-hidden 缓存，不影响判定）"""
        if 0 <= index < len(self._regions) and isinstance(self._regions[index], dict):
            try:
                self._regions[index]["label_pos"] = [float(xy[0]), float(xy[1])]
            except (TypeError, ValueError, IndexError):
                pass

    @staticmethod
    def _point_segment_distance(px, py, ax, ay, bx, by):
        """点 (px,py) 到线段 (ax,ay)-(bx,by) 的距离（屏幕像素）"""
        dx = bx - ax
        dy = by - ay
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx = ax + t * dx
        cy = ay + t * dy
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    def _edge_at(self, pos, tol=12.0):
        """屏幕点命中的最近边 → (区域索引, 边号)；没命中 → (-1, -1)。

        ★ 容差 12.0 屏幕像素（原 6.0）：协调者实测"偏移 0~5px 命中、≥6px 全落空"，
          而用户是**用眼睛瞄组织图上的虚线**（线本身只有 1~2px 宽）⇒ 6px 等于点不中。
          取 12px 的理由：≈2× 原值、且在常见缩放下仍**小于相邻两条边的间距**
          （区域跨屏数百像素），所以"最近边"的语义不会被破坏；
          本函数是**全局最近边**（跨区域取最近），放宽后可能命中相邻区域的边 ——
          这是可接受的（用户点的就是"这里的那条线"），且**悬停高亮用的是同一个
          本函数** ⇒ "高亮哪条就切哪条"。
        ★ 隐藏边**也能点到**（否则用户没法把隐藏的边改回来）。
        """
        try:
            px, py = float(pos.x()), float(pos.y())
        except Exception:
            return (-1, -1)
        best = (-1, -1)
        best_d = float(tol)
        for i in range(len(self._regions) - 1, -1, -1):
            screen = self._region_screen_points(self._regions[i])
            n = len(screen)
            if n < 3:
                continue
            for e in range(n):
                a = screen[e]
                b = screen[(e + 1) % n]
                d = self._point_segment_distance(px, py, a.x(), a.y(), b.x(), b.y())
                if d <= best_d:
                    best_d = d
                    best = (i, e)
        return best

    def _label_at(self, pos, tol=14.0):
        """屏幕点命中的注释锚点所在区域索引；没命中 → -1"""
        try:
            px, py = float(pos.x()), float(pos.y())
        except Exception:
            return -1
        for i in range(len(self._regions) - 1, -1, -1):
            anchor = self._label_anchor_screen(i, self._regions[i])
            if anchor is None:
                continue
            if ((px - anchor.x()) ** 2 + (py - anchor.y()) ** 2) ** 0.5 <= tol:
                return i
        return -1

    def _toggle_edge_at(self, pos):
        """翻转某条边的显隐（写 `edge_override`）——**保留但已无 UI 入口**。

        ⛔ `edges`（编辑边）模式 2026-09 已退休（用户纠正："根本就不是编辑边，而是改成
           **可见区域**"）⇒ 画布里**没有**任何分支会调本函数了。
        ★ 保留原因（协调者"有疑问就留着，别为清理引入风险"）：
          · 它是 `edge_override` 的**唯一写入实现**，也是 `region_edge_toggled`
            （冻结信号，(idx, edge, "hide"|"show")）的唯一发射点；
          · 用户真实数据里已有 `edge_override`，读取/渲染照旧（见 `_visible_and_hidden_edges`）；
          · 将来若在别处恢复"手工逐边显隐"的入口，直接复用即可。

        · 已有覆盖 ⇒ 在 `hide`/`show` 之间翻；
        · 没有覆盖 ⇒ 缺省是"显示" ⇒ 点一下写 `"hide"`（不再看自动出界规则）。
        Returns: bool —— 是否真的翻到了一条边
        """
        try:
            idx, edge = self._edge_at(pos)
            if idx < 0:
                return False
            region = self._regions[idx]
            if not isinstance(region, dict):
                return False
            n = len(region.get("points") or [])
            if n < 3 or edge >= n:
                return False
            ov = region.get("edge_override")
            if not isinstance(ov, dict):
                ov = {}
                region["edge_override"] = ov
            cur = None
            for key in (str(edge), edge):
                if key in ov:
                    cur = str(ov[key] or "").strip().lower()
                    break
            # ★★ 裁定（所见即所得）：默认值 = **按当前显示状态取反**，只看 `edge_override`。
            #   缺省（没有 override）= 显示 ⇒ 点一下写 `"hide"`；
            #   ⛔ 不再拿"出界自动隐藏"当默认（那会让画布与出图不一致）。
            if cur == "hide":
                new = "show"          # 当前隐藏 → 点一下就显示回来
            else:
                new = "hide"          # 当前显示（含缺省）→ 点一下就隐藏
            ov[str(edge)] = new
            # ★ 走唯一收口（单选 = `[idx]`；`emit=False` —— 本路径的发射顺序在下面显式保留）
            self._set_selection([idx], emit=False)
            # ★★ 发射顺序（协调者裁定，别调回去）：
            #   ① `region_edge_toggled` —— 字典**刚写完就发**，载荷 (idx, edge, new)；
            #      bind 直接拿载荷即可，不必依赖"同步前基线"做 diff。
            #   ② `region_edges_changed` —— 必须**早于** `region_selected`：
            #      `region_selected` 会让 bind 把画布**整份同步**进模型，一同步基线就变成新值
            #      ⇒ 后发的 handler 再去 diff 只会得到"未变"（真机日志谎报"没点中边"）。
            #   ③ `region_selected` —— 语义不变（回填右侧控件）；此刻模型已是新值，同步无副作用。
            self.region_edge_toggled.emit(idx, int(edge), new)
            self.update()
            self.region_edges_changed.emit(idx)
            self.region_selected.emit(idx)
            return True
        except Exception:
            return False

