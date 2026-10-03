# -*- coding: utf-8 -*-
"""
空转审查模式 —— 评分与图集分析脚本（纯业务逻辑，不碰 UI 控件）

职责（M2a/M3 契约 §4.2）：
  · figure_set_id(manifest_path)   图集身份（run_id 优先；回退 sha256 前 16 位 + 行数）
  · color_for_stars(score, ...)    星级 → 文字色（W1 §6.2/§6.3 亮度钳制方案）
  · list_review_figures(dataset)   审查矩阵的图清单（19 样本 × N 个逐样本图型）
  · load_review_scores(dataset)    读评分（原子读；损坏/缺失 → 空，绝不抛）
  · save_review_scores(dataset, d) 原子写评分（临时文件 + os.replace）
  · review_state(sample_id, ...)   'unreviewed' | 'scored'

四层分离：本文件属 **analysis 层** —— 不 import 任何 UI 模块、不创建控件、不读图片字节。
唯一允许的 Qt 依赖是 `QColor`（评分的**业务语义**就是颜色，契约 R4 明确把配色放这里，
不许写进 `gui_styles.py`）。`QColor` 已在 `import_config.py:331` 的导出清单里，
但按本轮教训（W1 踩过 `QPolygonF` 不在导出清单 → `NameError` → 进程 abort）**仍显式 import**。

一律不抛：失败返回空结构 / False / 安全默认值，把原因写进返回结构或 stderr。
"""

import os
import io
import re
import csv
import json
import time
import colorsys
import hashlib

from script.utils_layer.import_config import *
# ★ 显式 import：不依赖 import_config 的导出清单（本轮已两次因导出口径不一致踩坑）
from PyQt5.QtGui import QColor
from script.utils_layer.import_config import BASE_DIR, APPDATA_PATH, OUT_BASE
from script.utils_layer.gui_styles import get_mod_styles

# =============================================================================
# 常量
# =============================================================================
REVIEW_JSON_SUFFIX = ".review.json"
FIGURE_MANIFEST_NAME = "_figure_manifest.csv"

# color_for_stars 用到的两个主题键（子界面）
_KEY_FILL = "sub_fill_color"
_KEY_MUTANT = "sub_mutant_color"
_KEY_TEXT = "sub_text_primary"

# 亮度钳制下限（W1 §6.2/§6.3：Y★ = max(Y_raw, 0.30)）
_LUM_FLOOR = 0.30
# 低分提亮时的饱和度地板（W1 §6.3.3：饱和度 max(s_raw, 0.60)）
_SAT_FLOOR = 0.60
# 底衬（CHIP_BG = HSL(h, 0.40, 0.12)）
_CHIP_SAT = 0.40
_CHIP_LIGHT = 0.12

# 安全兜底色（is_rgb_valid/主题取不到时用；与 mod_manager 默认值一致）
_FILL_FALLBACK = (30, 58, 95)
_MUTANT_FALLBACK = (255, 107, 53)
_TEXT_FALLBACK = "#87CEEB"


# =============================================================================
# 颜色工具（纯算术，可供独立复算 —— W1 §6.3.3 给了逐通道中间量）
# =============================================================================
def _srgb_to_linear(c):
    """sRGB 通道 (0-255) → 线性值（WCAG 定义）"""
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_lum(rgb):
    """WCAG 相对亮度。rgb = (r, g, b) 各 0-255"""
    try:
        r, g, b = rgb[0], rgb[1], rgb[2]
        return (0.2126 * _srgb_to_linear(r)
                + 0.7152 * _srgb_to_linear(g)
                + 0.0722 * _srgb_to_linear(b))
    except Exception:
        return 0.0


def contrast_ratio(rgb_a, rgb_b):
    """WCAG 对比度 (L1+0.05)/(L2+0.05)"""
    try:
        ya, yb = rel_lum(rgb_a), rel_lum(rgb_b)
        hi, lo = max(ya, yb), min(ya, yb)
        return (hi + 0.05) / (lo + 0.05)
    except Exception:
        return 0.0


def _parse_color(value, fallback_rgb):
    """'rgba(30, 58, 95, 0.3)' / '#RRGGBB' / '#RGB' / QColor → (r,g,b)，**丢 alpha**

    ★ W1 §6.2.1（本方案唯一"不这么做就必然出 bug"的一条）：
      从 `fill_color` 派生的**任何文字色都必须丢掉原 alpha**。
      `fill_color` = `rgba(30,58,95,0.3)` —— 它不是"深蓝"，是"只有 30% 不透明度的深蓝"；
      直接当文字色压在半透明面板 + 背景图上，对比度约 2.4，**低分样本名会看不见**。
    """
    try:
        if isinstance(value, QColor):
            return (value.red(), value.green(), value.blue())
        if not isinstance(value, str):
            return fallback_rgb
        s = value.strip()
        if not s:
            return fallback_rgb
        if s.startswith('#'):
            h = s[1:]
            if len(h) == 3:
                return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
            if len(h) >= 6:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            return fallback_rgb
        if s.lower().startswith('rgb'):
            inner = s[s.index('(') + 1:s.rindex(')')]
            parts = [p.strip() for p in inner.split(',')]
            if len(parts) >= 3:
                return (int(round(float(parts[0]))),
                        int(round(float(parts[1]))),
                        int(round(float(parts[2]))))
            return fallback_rgb
    except Exception:
        traceback.print_exc()
    return fallback_rgb


def _rgb_to_hls(rgb):
    """(r,g,b) → (h, l, s)，均 0..1（注意 colorsys 的返回序是 h, l, s）"""
    r, g, b = [c / 255.0 for c in rgb]
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_rgb(h, l, s):
    """(h,l,s) → (r,g,b)，各通道 **round** 到整数

    ⚠ 量化口径（实测过三种，选此）：
      · `round` 比 `floor` 更接近 W1 §6.3.2 的表（round 命中 3/5，floor 2/5）；
      · 配合下面"取**最小 ≥ 目标亮度**的候选"（ceil 口径），
        3 分 `#DB7A6D` 与 4 分 `#D87D61` 与 W1 表**逐位一致**，
        1 分 `#6697D9`→`#6698D9`、2 分 `#DA6CCC`→`#DA6CCD` 各差 **1 个 LSB**。
      → 1 LSB 属量化误差（对比度差 <0.01，肉眼不可辨），且**本实现只会偏高不会偏低**，
        因此对 R3 的可读性下限（最差 5.44:1）**只会更安全**。
    """
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (max(0, min(255, int(round(r * 255)))),
            max(0, min(255, int(round(g * 255)))),
            max(0, min(255, int(round(b * 255)))))


def _solve_lightness_for_lum(h, s, target_y, lo, hi, iters=60):
    """二分求 lightness，使 rel_lum(hls→rgb) **不小于** target_y 且尽量小（ceil 口径）

    返回 (lightness, rgb, actual_lum)。

    ⚠ 口径选择的依据（实测）：W1 §6.3.3 给出的中间量显示其 3 分 `Y_text = 0.300833`
      **大于** 0.30 —— 说明设计用的是"**最小 ≥ 目标**"而不是"最大 ≤ 目标"。
      改用 ceil 后 3 分/4 分与设计表逐位一致。
      附带好处：**永不跌破亮度下限 0.30**，可读性有硬保证。
    """
    best_rgb = None
    best_l = hi
    best_y = rel_lum(_hls_to_rgb(h, hi, s))
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        rgb = _hls_to_rgb(h, mid, s)
        y = rel_lum(rgb)
        if y >= target_y:
            best_l, best_rgb, best_y = mid, rgb, y
            hi = mid
        else:
            lo = mid
    if best_rgb is None:
        best_rgb = _hls_to_rgb(h, 1.0, s)
        best_y = rel_lum(best_rgb)
    return best_l, best_rgb, best_y


def _theme_colors():
    """取当次主题的 (fill_rgb, mutant_rgb, text_color_str)

    ★ 每次现算 —— 内部调 `get_mod_styles()`。**禁止跨主题缓存结果**：
      颜色语义随主题走，缓存会让"切 mod 后分数色停在旧主题"。
    """
    fill_rgb, mut_rgb, text_str = _FILL_FALLBACK, _MUTANT_FALLBACK, _TEXT_FALLBACK
    try:
        styles = get_mod_styles() or {}
        fill_rgb = _parse_color(styles.get(_KEY_FILL), _FILL_FALLBACK)
        mut_rgb = _parse_color(styles.get(_KEY_MUTANT), _MUTANT_FALLBACK)
        text_str = styles.get(_KEY_TEXT) or _TEXT_FALLBACK
    except Exception:
        traceback.print_exc()
    return fill_rgb, mut_rgb, text_str


def colors_for_stars(score, max_stars=5):
    """星级 → ({'text': QColor, 'chip': QColor, 'text_rgb':…, 'chip_rgb':…, 'ratio':…, 'clamped':bool})

    W1 §6.2 公式（可独立复算）：
        t = (score-1)/(max_stars-1)；raw = 逐通道插值(fill → mutant)
        Y★ = max(rel_lum(raw), 0.30)
        TEXT = raw                                   若 Y★ <= Y_raw（高分不处理，5 分就是 mutant 本色）
             = HSL(h_raw, max(s_raw,0.60), 二分求得 L) 否则（低分：只提亮，不改色相）
        CHIP = HSL(h_raw, 0.40, 0.12)，alpha=255
    """
    result = {"text": None, "chip": None, "text_rgb": None, "chip_rgb": None,
              "ratio": 0.0, "clamped": False}
    try:
        fill_rgb, mut_rgb, _ = _theme_colors()
        color_map = {1: _FILL_FALLBACK, 2: _MUTANT_FALLBACK}

        # score=0（未打分）→ 主题文字色（中性），**不是** 1 分色
        if score is None or int(score) <= 0:
            _, _, text_str = _theme_colors()
            text_rgb = _parse_color(text_str, _parse_color(_TEXT_FALLBACK, (135, 206, 235)))
            h, l, s = _rgb_to_hls(text_rgb)
            chip_rgb = _hls_to_rgb(h, _CHIP_LIGHT, _CHIP_SAT)
            result.update({"text": QColor(text_rgb[0], text_rgb[1], text_rgb[2], 255),
                           "chip": QColor(chip_rgb[0], chip_rgb[1], chip_rgb[2], 255),
                           "text_rgb": text_rgb, "chip_rgb": chip_rgb,
                           "ratio": contrast_ratio(text_rgb, chip_rgb),
                           "clamped": False})
            return result

        s_int = int(score)
        try:
            m = int(max_stars) if max_stars else 5
        except Exception:
            m = 5
        if m < 2:
            m = 2
        s_int = max(1, min(m, s_int))

        t = (s_int - 1) / float(m - 1)
        raw = tuple(int(round(fill_rgb[i] * (1 - t) + mut_rgb[i] * t)) for i in range(3))
        h, l_raw, s_raw = _rgb_to_hls(raw)
        y_raw = rel_lum(raw)
        y_star = max(y_raw, _LUM_FLOOR)

        if y_star <= y_raw:
            text_rgb = raw
            clamped = False
        else:
            _, text_rgb, _ = _solve_lightness_for_lum(
                h, max(s_raw, _SAT_FLOOR), y_star, l_raw, 1.0)
            clamped = True

        chip_rgb = _hls_to_rgb(h, _CHIP_LIGHT, _CHIP_SAT)
        result.update({"text": QColor(text_rgb[0], text_rgb[1], text_rgb[2], 255),
                       "chip": QColor(chip_rgb[0], chip_rgb[1], chip_rgb[2], 255),
                       "text_rgb": text_rgb, "chip_rgb": chip_rgb,
                       "ratio": contrast_ratio(text_rgb, chip_rgb),
                       "clamped": clamped})
    except Exception:
        traceback.print_exc()
    return result


def color_for_stars(score, max_stars=5):
    """星级 → 文字色 QColor（契约 §4.2 的冻结签名）

    `score ∈ {0,1,2,3,4,5}`：**0 → 未打分，用主题文字色（中性）**，不是 1 分色
    （契约 R2 / W1 §4.2.4：避免"没打分却显示成 1 分色"被误读）。
    1..5 → W1 §6.2/§6.3 的亮度钳制方案；5 分 = `mutant` 本色（未提亮）。
    **每次现算，不缓存**（切 mod 后必须跟着主题变）。
    """
    try:
        c = colors_for_stars(score, max_stars).get("text")
        if c is not None:
            return c
    except Exception:
        traceback.print_exc()
    return QColor(_TEXT_FALLBACK)


def chip_color_for_stars(score, max_stars=5):
    """星级 → 底衬色 QColor（W1 §6.3：同色相深底衬，把"四层合成"降为"两层合成"）"""
    try:
        c = colors_for_stars(score, max_stars).get("chip")
        if c is not None:
            return c
    except Exception:
        traceback.print_exc()
    return QColor(0, 0, 0)


# =============================================================================
# 路径工具
# =============================================================================
def _spatial_main_dir():
    """成品目录 `appdata/spatial_main`（与 M1 的 SPATIAL_SCAN_DATA_PATH 同源）"""
    try:
        from script.utils_layer.import_config import SPATIAL_SCAN_DATA_PATH
        return SPATIAL_SCAN_DATA_PATH
    except Exception:
        return os.path.join(APPDATA_PATH, "spatial_main")


def _manifest_path_for(dataset):
    return os.path.join(_spatial_main_dir(), "%s.manifest.json" % dataset)


def _figure_csv_path_for(dataset):
    return os.path.join(OUT_BASE, dataset, FIGURE_MANIFEST_NAME)


def _review_json_path_for(dataset):
    return os.path.join(_spatial_main_dir(), str(dataset) + REVIEW_JSON_SUFFIX)


# =============================================================================
# ★★ 真实数据集保护（本轮事故后的硬约束）
# =============================================================================
# 事故：测试脚本"先把原文件读进内存、finally 逐字节写回"，在"原先不存在"的分支里
#       直接 `os.remove`。后来该文件已经变成**用户真机打的分**，同一段逻辑再跑一次
#       就会**删掉用户的人工评分**。
# ⇒ 从此：**测试一律打 `__SPATIAL_TEST__` 前缀的数据集**；生产函数对"看起来像测试名"
#    以外的数据集**只在显式放行时才写盘**。
#    这样"忘带备份的测试"最多写坏测试文件，**永远碰不到 `GSE237183` 这类真实数据集**。
TEST_DATASET_PREFIX = "__SPATIAL_TEST__"
# 显式放行开关（默认关闭）。只为"确实想对真实数据集做一次受控写入"的场景预留，
# 例如将来加一个官方迁移脚本；**测试代码不得打开它**。
ALLOW_REAL_DATASET_WRITE = False


def is_test_dataset(dataset):
    """数据集名是否属于"测试专用"（前缀 `__SPATIAL_TEST__`）"""
    try:
        return str(dataset or "").startswith(TEST_DATASET_PREFIX)
    except Exception:
        return False


def _write_allowed(dataset):
    """是否允许对 `dataset` 落盘：测试名一律允许；真实名需显式放行"""
    try:
        return bool(is_test_dataset(dataset) or ALLOW_REAL_DATASET_WRITE)
    except Exception:
        return False


def _norm_abs(p):
    """把 manifest/CSV 里的路径规整为绝对路径（原样可能是绝对 + 正斜杠混用）"""
    try:
        if not p:
            return ""
        s = str(p).replace("\\", "/")
        if os.path.isabs(s):
            return os.path.normpath(s)
        return os.path.normpath(os.path.join(BASE_DIR, s))
    except Exception:
        return ""


# =============================================================================
# 静默容错小工具
# =============================================================================
def _read_json(path):
    """读 JSON；任何失败 → (None, 原因)。**绝不抛**"""
    try:
        if not path or not os.path.isfile(path):
            return None, "文件不存在: %s" % path
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f), ""
    except Exception as e:
        return None, "读取失败: %s: %s" % (type(e).__name__, e)


def _read_manifest(dataset):
    """读数据集 manifest；失败 → (None, 原因)"""
    return _read_json(_manifest_path_for(dataset))


def _read_figure_csv(dataset):
    """读 `_figure_manifest.csv`；返回 (rows, 原始bytes, 原因)。**绝不抛**"""
    path = _figure_csv_path_for(dataset)
    try:
        if not os.path.isfile(path):
            return [], b"", "图集清单不存在: %s" % path
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8-sig", errors="replace")
        rows = list(csv.DictReader(io.StringIO(text)))
        return rows, raw, ""
    except Exception as e:
        traceback.print_exc()
        return [], b"", "读取图集清单失败: %s: %s" % (type(e).__name__, e)


def _sample_ids_from_manifest(manifest):
    """从 manifest 取样本 id 清单（列表顺序即显示顺序）"""
    out = []
    try:
        for s in (manifest or {}).get("samples") or []:
            if isinstance(s, dict) and s.get("id"):
                out.append(str(s["id"]))
    except Exception:
        traceback.print_exc()
    return out


def _extract_sample_from_stem(stem, known_samples):
    """从文件名 stem 里认出样本 id

    策略（按可靠性降序，实测两种命名都能覆盖）：
      ① 清单样本 id（`GSM*`）直接出现在 stem 里 → 取它（最长匹配优先，防 GSM759658 误配 GSM7596587）
      ② 回退：stem 里用 `GSM\\d+` 形态抓一个
      ③ 再回退：stem 按 `_` / `-` 切分，取最后一个纯数字/字母数字片段
    认不出 → 返回 ""（由调用方记为"未归属"，**不静默丢**）
    """
    try:
        if not stem:
            return ""
        s = str(stem)
        hits = [sid for sid in (known_samples or []) if sid and sid in s]
        if hits:
            return max(hits, key=len)
        import re
        m = re.search(r'(GSM\d+)', s)
        if m:
            return m.group(1)
        for tok in reversed([t for t in s.replace('-', '_').split('_') if t]):
            if tok.isalnum() and any(ch.isdigit() for ch in tok):
                return tok
    except Exception:
        traceback.print_exc()
    return ""


# =============================================================================
# 原始组织切片图（不带 spot 的 H&E）—— **来自原始数据集，不是图集产物**
# =============================================================================
#: 审查页第 7 个逐样本页签的图型 id
#  ★ 三处必须**逐字一致**且**都放在最后**：W1 `FIGURE_TYPE_LABELS` 的键、
#    本模块 `list_review_figures()['figure_types']`、bind 取图时的 `matrix[sid][ft]`。
#    次序也必须是同构的 —— bind 用 `tabs.currentIndex()` 去索引 `figure_types`
#    （`_refresh_figure_area`），两边顺序不一致会"切到 A 显示 B"。
RAW_TISSUE_TYPE_ID = "tissue_raw"
RAW_TISSUE_LABEL = "原始组织切片（H&E，无 spot）"


def dataset_raw_root(dataset):
    """该数据集 manifest 声明的原始切片根（绝对路径）；取不到 / 目录不存在 → None

    ★ 为什么显式取"这个数据集自己的" `source.raw_root`，而不是直接用
      `region_canvas.candidate_raw_roots()`（全数据集候选根）：
      当前两套样本 id（`GSM*` / `UKF*`）天然不重名，所以全候选根也能命中；
      但显式传根是**确定性**的，将来第三个数据集若出现 id 撞名也不会串数据。
      （实测：两个数据集"显式传根"与"全候选根"的解析结果**逐样本一致**。）
    """
    try:
        manifest, _err = _read_manifest(dataset)
        rel = str(((manifest or {}).get("source") or {}).get("raw_root") or "").strip()
        if not rel:
            return None
        try:
            from script.utils_layer.import_config import BASE_DIR
        except Exception:
            traceback.print_exc()
            return None
        path = os.path.normpath(os.path.join(BASE_DIR, rel))
        return path if os.path.isdir(path) else None
    except Exception:
        traceback.print_exc()
        return None


def list_raw_tissue_images(dataset):
    """逐样本**原始组织切片图**（不带 spot 的 H&E）—— 审查页要"对着原图看"

    ## 为什么必须有（用户 2026-09 明确要求）
      图集里的 `load_per_sample` 那类是"画在切片上的表达量点图"；
      而用户要看的是**没有任何 spot 的原始 H&E** —— 原始数据集里每个样本都自带一张
      （Visium/Space Ranger 标准输出）。审查时先看原图、再看画了点/注释的图，才有参照。

    ## 唯一真相源：`region_canvas.resolve_base_image()`
      与**区域页画布**用的是同一个解析器（hires → lowres 的优先级也在那里定），
      本模块**不自己拼路径**、不硬编码 `<sid>/tissue_hires_image.png` ——
      否则就会出现"区域页看得到底图、审查页看不到"的两套逻辑（本会话已栽过两次）。

    Returns:
        dict: {sample_id: {'png': path|None, 'kind': 'hires'|'lowres'|'none'}}
              解析器不可用 / 清单为空 → 空 dict（调用方如实表达"取不到"，不静默）
    """
    out = {}
    try:
        manifest, _err = _read_manifest(dataset)
        samples = _sample_ids_from_manifest(manifest)
        if not samples:
            return out
        raw_root = dataset_raw_root(dataset)
        try:
            from script.analyzer_layer.spatial_layer.spatial_region_layer import (
                region_canvas as _region_canvas)
        except Exception:
            traceback.print_exc()
            return out
        for sid in samples:
            path, _key, kind = _region_canvas.resolve_base_image(sid, raw_root=raw_root)
            out[str(sid)] = {"png": path, "kind": kind or "none"}
    except Exception:
        traceback.print_exc()
    return out


# =============================================================================
# figure_set_id
# =============================================================================
def figure_set_id(target):
    """图集身份（契约 R1）—— **一个数据集恰好一个 id**

    取值顺序（协调者裁决；`atlas.run_id` 优先，**不用 CSV 某一行的 run_id**）：
      ① `appdata/spatial_main/<数据集>.manifest.json` 的 **`atlas.run_id`**
         （非空、非 NA/null，且 `atlas.runs[].dir` 只有 0/1 项）→ `run_id:<值>`
      ② 回退：`sha256(_figure_manifest.csv 原始字节)[:16] + 行数` → `sha:<16hex>:<rows>`

    ⚠ **为什么不能用 CSV 里某一行的 `run_id`**：分节跑时不同行属于不同 run
      （实测当前 CSV 的 `run_id` 去重 = `['NA', '20260919-040131']`，代表不了整个图集）。
      `atlas.run_id` 才是 W3 对整个图集的标识。

    ⚠ **为什么必须"一个数据集一个 id"**（协调者实测指出）：本函数原来"按传入路径就地算"，
      于是 `manifest.json` 与 `_figure_manifest.csv` 会算出**两个不同 id**；
      只要一处存、另一处比，审查页就会**永远误报「当前评分对应的是旧图集」**——
      这正是 R1「绝不静默沿用/清空」的**反面（永远误报）**。故统一为：
      **先定位数据集，再只走 atlas.run_id / CSV 哈希这同一条链**。

    Args:
        target: 数据集名（推荐）／`_figure_manifest.csv` 路径／`.manifest.json` 路径
    Returns:
        str: 图集 id；定位不到时返回 ""（调用方据此判定"无法绑定"，**不抛**）
    """
    try:
        if not target:
            return ""
        s = str(target)
        dataset = ""

        # ---- 定位数据集（三种入参都支持；**之后只走同一条链**）----
        if os.path.isfile(s):
            base = os.path.basename(s)
            if base.endswith(".manifest.json"):
                dataset = base[:-len(".manifest.json")]
            elif base.lower().endswith(".csv"):
                dataset = os.path.basename(os.path.dirname(os.path.abspath(s)))
            else:
                dataset = os.path.splitext(base)[0]
        elif s.endswith(".manifest.json"):
            dataset = os.path.basename(s)[:-len(".manifest.json")]
        else:
            dataset = s

        if not dataset:
            return ""

        # ---- ① atlas.run_id（唯一权威）----
        manifest, _ = _read_manifest(dataset)
        if isinstance(manifest, dict):
            atlas = manifest.get("atlas")
            if isinstance(atlas, dict):
                rid = atlas.get("run_id")
                if isinstance(rid, str):
                    rid = rid.strip()
                    runs = atlas.get("runs")
                    n_runs = len(runs) if isinstance(runs, list) else 0
                    if rid and rid.upper() not in ("NA", "N/A", "NULL", "NONE") and n_runs <= 1:
                        return "run_id:%s" % rid

        # ---- ② 回退：CSV 内容哈希 + 行数 ----
        path = _figure_csv_path_for(dataset)
        if not os.path.isfile(path):
            return ""
        try:
            with open(path, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8-sig", errors="replace")
            n_rows = len(list(csv.DictReader(io.StringIO(text))))
            return "sha:%s:%d" % (hashlib.sha256(raw).hexdigest()[:16], n_rows)
        except Exception:
            traceback.print_exc()
            return ""
    except Exception:
        traceback.print_exc()
        return ""


# =============================================================================
# figure_set_id 的"纯追加"判定（L2 实测事故：只补了 PDF 孪生文件却误报"旧图集"）
# =============================================================================
# ★★ 事故经过（协调者实测的三行数字）：
#     W3 补 PDF 前 `_figure_manifest.csv` = 53681 B / 297 数据行 / sha256 AB8EDD08…
#     W3 补 PDF 后                        = 54803 B / 304 数据行 / sha256 673CE4E7…
#     新增 7 行**全部是 `.pdf` 孪生文件**（6×gene_spatial + 1×gene_panel），
#     既有 53681 字节**逐字节未变**（前缀 sha256 仍 AB8EDD08…）。
#   ⇒ `figure_set_id` 由 `sha:ab8edd08676e49c0:297` 变成 `sha:673ce4e79c319f83:304`，
#     而用户 `GSE237183.review.json` 里存的是**旧值**（19 个样本的人工评分）。
#   ⇒ 审查页 `_check_atlas()` 判 `old != cur and has_scores` → 弹「当前评分对应的是旧图集」
#     且 `_persist_scores` 在冲突未解期间**拒绝落盘**，逼用户在
#     「按旧评分继续」（会写他的评分文件）与「清空重审」（**不可逆**）之间二选一。
#   ⇒ **而他评过的那 6 类 PNG 一张都没变** —— 纯追加导致的**误报**，
#     还紧挨着一个不可逆按钮，风险不对称。
# ★ 裁定：**不动** `figure_set_id` 的公式（那是冻结契约），改**比较处**：
#     用"旧 id 是不是当前 CSV 的**字节前缀**"精确表达"当前图集是在被评分的那份之上
#     纯追加出来的 ⇒ 用户评过的任何一行都没有被改动"。
# 最近一次判定的明细（供日志与人工复核；**不抛**）
LAST_PREFIX_CHECK = {"matched": False, "n_bytes": -1, "hex16": "",
                     "expected_hex16": "", "rows": -1, "reason": "尚未调用"}

# `sha:<16hex>:<rows>`（大小写都收，比较时统一 lower）
_SHA_FIGURE_SET_ID_RE = re.compile(r'^sha:([0-9a-fA-F]{16}):(\d+)$')


def figure_set_id_is_append_prefix(stored_id, dataset, raw=None):
    """★ 评分图集 `stored_id` 是否为当前 `_figure_manifest.csv` 的**字节前缀**

    语义（**精确**，不是"差不多就行"）：`stored_id` 里的哈希覆盖的正是当前文件的
    **前 `rows+1` 行**（1 行表头 + `rows` 条数据行）⇒ 当前图集＝在旧图集上**纯追加**，
    **用户评过的每一行都还在原位置、一个字节没动** ⇒ 应当判为**同一图集**、不弹警示。

    判据（逐条实现；任何一条不满足 → `False`，调用方走原来的"不符"分支）：
      1. `stored_id` 必须形如 `sha:<16hex>:<rows>`（正则，大小写都收）。
         其它形态（如 `run_id:…`、空串）→ `False`；
      2. 取当前 CSV 的**原始字节** `raw`：调用方可传入以免重复读盘，
         否则用**既有的** `_read_figure_csv()`（**不另开一条读盘路径**）；
      3. `splitlines(keepends=True)` 按行切（CRLF/LF 都能切），取**前 `rows+1` 行**
         的字节切片；当前行数 `< rows+1` → `False`（图集反而变短，绝不是纯追加）；
      4. `sha256(切片).hexdigest()[:16] == <16hex>` → 命中；
      5. 切片字节长度 / 算出的 hex16 / 期望 hex16 / 行数 记进 `LAST_PREFIX_CHECK`。

    ⚠ **只认"严格短前缀"**：`stored_id` 恰好等于当前 id（全长哈希，`old == cur`）时
      返回 **False**。理由：调用方只在 `old != cur` 时才会问这个问题，相等时**根本走不到**；
      而把"相等"也判 True 会让本函数语义变成"是前缀**或**相等"，两个分支都能成立、
      排障时会看不懂到底走的哪条。前缀就按通常含义 = **更短**的真前缀。

    ⚠ **已知假设（偏保守）**：`<rows>` 是 `csv.DictReader` 的**逻辑行**数，这里按
      **物理行**切。表头或字段里若含真正的换行，两者会对不上 → 哈希不匹配 → 返回
      `False` ⇒ **宁可多报一次"图集不符"，也绝不放过一次真实改动**。

    Args:
        stored_id: 评分文件里记录的图集 id（`scores["figure_set_id"]`）
        dataset: 数据集名
        raw: 可选，当前 CSV 的原始字节（给了就读它，不再读盘）
    Returns:
        bool（**绝不抛**；任何异常 → False，原因在 `LAST_PREFIX_CHECK["reason"]`）
    """
    global LAST_PREFIX_CHECK
    LAST_PREFIX_CHECK = {"matched": False, "n_bytes": -1, "hex16": "",
                         "expected_hex16": "", "rows": -1, "reason": "尚未判定"}
    try:
        sid = str(stored_id or "").strip()
        m = _SHA_FIGURE_SET_ID_RE.match(sid)
        if m is None:
            LAST_PREFIX_CHECK["reason"] = ("id 形态不是 sha:<16hex>:<rows>（%r）"
                                           "→ 不做前缀判定，走原来的不符分支" % sid)
            return False
        want_hex = m.group(1).lower()
        want_rows = int(m.group(2))
        LAST_PREFIX_CHECK["expected_hex16"] = want_hex
        LAST_PREFIX_CHECK["rows"] = want_rows
        if raw is None:
            _rows_now, raw, err = _read_figure_csv(dataset)
            if err:
                LAST_PREFIX_CHECK["reason"] = "读当前图集清单失败：%s" % err
                return False
        if not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
            LAST_PREFIX_CHECK["reason"] = "当前图集清单为空 → 不可能是前缀"
            return False
        raw = bytes(raw)
        lines = raw.splitlines(keepends=True)
        need = want_rows + 1                     # 表头 + rows 条数据行
        if len(lines) < need:
            LAST_PREFIX_CHECK["reason"] = ("当前 %d 行 < 需要的 %d 行 → 图集变短，"
                                           "不是纯追加" % (len(lines), need))
            return False
        slice_bytes = b"".join(lines[:need])
        # ★ 严格短前缀：切片必须**短于**整个文件。相等（`stored_id` 就是全长哈希，
        #   即 `old == cur`）→ 返回 False，语义单一（见 docstring 的"只认严格短前缀"）。
        if len(slice_bytes) >= len(raw):
            LAST_PREFIX_CHECK["n_bytes"] = len(slice_bytes)
            LAST_PREFIX_CHECK["reason"] = ("前 %d 行正好覆盖整个文件（%d 字节）"
                                           "⇒ 全长相等，不是**更短的**真前缀 → False"
                                           % (need, len(slice_bytes)))
            return False
        got_hex = hashlib.sha256(slice_bytes).hexdigest()[:16]
        LAST_PREFIX_CHECK["n_bytes"] = len(slice_bytes)
        LAST_PREFIX_CHECK["hex16"] = got_hex
        hit = (got_hex == want_hex)
        LAST_PREFIX_CHECK["matched"] = hit
        LAST_PREFIX_CHECK["reason"] = ("前 %d 字节（%d 行）sha256[:16] = %s %s %s"
                                       % (len(slice_bytes), need, got_hex,
                                          "==" if hit else "!=", want_hex))
        return hit
    except Exception as e:
        traceback.print_exc()
        LAST_PREFIX_CHECK["reason"] = "异常：%s: %s" % (type(e).__name__, e)
        return False


# =============================================================================
# list_review_figures
# =============================================================================
def list_review_figures(dataset):
    """审查矩阵的图清单（契约 §4.2 / v1.2）

    Returns:
        dict: {
          'ok': bool, 'reason': str,
          'figure_types': [str, ...],              # ★ list[str]，只含 id，顺序 = 冻结顺序
          'figure_type_info': {id: {'label','n_png','n_pdf'}},   # ★ 富信息放这里
          'samples': [sample_id...],                             # 以 manifest 清单为准（19 个）
          'matrix': {sample: {ftype: {'png':path|None, 'pdf':path|None}}},
          'figure_set_id': str,
          'unmatched': {ftype: [无法归属的样本名...]},            # 差异如实标出，不静默丢
          'sample_diff': {'extra_in_figures': [...], 'missing_in_figures': [...]},
        }

    ★ **图型清单 = 6 个图集逐样本型 + 1 个 `tissue_raw`（原始组织切片，第 7 个页签）**：
      前 6 个由 `artifacts[].per_sample` / CSV 回退判定、按 manifest order 排序；
      `tissue_raw` **恒定追加在最后**（`figure_type_info['tissue_raw']['source'] == 'raw_dataset'`），
      数据来自原始数据集（`list_raw_tissue_images`，复用区域页的解析器），**不属于图集 CSV**。
      `ok` 只由**图集**那 6 型决定 —— 原图存在不代表图集读得出来。

    ★ **`figure_types` 必须是 `list[str]`**（协调者实测指出的集成缺陷）：
      W1 的 `verify_figure_types(types)` 内部做 `key = str(type_id)` 再查自己的标签表 ——
      若喂 dict 列表，`str(dict)` 会变成 `"{'id': 'load_per_sample', ...}"`，
      **6 个全部对不上** → `matched=False`、`extra` 6 个垃圾串、`missing` 全部 6 个
      → 每次进页面都误报"图型不一致"。
      富信息（label / n_png / n_pdf）移到 **`figure_type_info`**，形状知识不泄漏进编排层。

    ★ **`label` 仅作信息，bind 不得用它去 `setTabText`**：页签标题由 W1 布局期的
      `FIGURE_TYPE_LABELS` 决定；bind 再改会导致"进页面时标题变一下"。

    **只返回路径字符串**：不 `QPixmap`、不读图片字节
    （实测整组织图 13.4 MB/张 vs 逐样本图 1.16 MB/张，**差 12 倍**；
      预读会把审查页的进入成本从"秒开"变成"分钟级"）。

    **逐样本图型怎么判定**（v1.1 说读 manifest 的 `figure_types[].per_sample` —— 实测**不成立**）：
      实测 `figure_types[]` 的条目只有 `id/label/order/panel/panel_label`，**没有 `per_sample`**；
      `per_sample` 实际挂在 **`artifacts[]`** 上（例：`load_per_sample` 有
      `per_sample{files:19, pattern:"01_nCount_{sample_key}.png"}`）。
      → 因此判定顺序为：① `artifacts[].per_sample`（标准来源）
                      ② 回退：该图型在 CSV 里**同时含 PNG 与 PDF**、且 PNG 覆盖 ≥2 个样本
                        （整组织图型如 `cluster_spatial` 只有 2 行、`gene_panel` 1 行，天然被排除）
      **不硬编码那 6 个图型字符串**（将来图型变了要能自动跟上）。
    """
    result = {"ok": False, "reason": "", "figure_types": [], "samples": [],
              "matrix": {}, "figure_set_id": "", "unmatched": {},
              "sample_diff": {"extra_in_figures": [], "missing_in_figures": []}}
    try:
        manifest, m_err = _read_manifest(dataset)
        rows, raw, c_err = _read_figure_csv(dataset)

        if manifest is None and not rows:
            result["reason"] = "；".join([x for x in (m_err, c_err) if x]) or "无可用数据"
            return result

        samples = _sample_ids_from_manifest(manifest)
        if not samples:
            result["reason"] = "manifest 里没有样本清单" + (("；" + m_err) if m_err else "")
            return result

        # ---- 逐样本图型判定 ----
        per_sample_ids = []
        # ① 标准来源：artifacts[].per_sample
        try:
            for a in (manifest or {}).get("artifacts") or []:
                if not isinstance(a, dict):
                    continue
                ps = a.get("per_sample")
                if not isinstance(ps, dict):
                    continue
                fid = a.get("figure_type") or a.get("id")
                n_files = ps.get("files")
                n_samp = ps.get("samples")
                covered = (isinstance(n_files, int) and n_files >= len(samples)) or \
                          (isinstance(n_samp, int) and n_samp >= len(samples))
                if fid and covered:
                    per_sample_ids.append(str(fid))
        except Exception:
            traceback.print_exc()

        # ② 回退：从 CSV 行形态推断（同时有 PNG+PDF，且 PNG 覆盖 ≥2 样本）
        if not per_sample_ids and rows:
            try:
                by_ft = {}
                for r in rows:
                    ft = (r.get("figure_type") or "").strip()
                    if not ft:
                        continue
                    by_ft.setdefault(ft, []).append(r)
                for ft, rs in by_ft.items():
                    has_png = any((r.get("path") or "").lower().endswith(".png") for r in rs)
                    has_pdf = any((r.get("path") or "").lower().endswith(".pdf") for r in rs)
                    if not (has_png and has_pdf):
                        continue
                    stems = set()
                    for r in rs:
                        p = r.get("path") or ""
                        if not p.lower().endswith(".png"):
                            continue
                        stems.add(_extract_sample_from_stem(
                            os.path.splitext(os.path.basename(p))[0], samples))
                    stems.discard("")
                    if len(stems) >= 2:
                        per_sample_ids.append(ft)
            except Exception:
                traceback.print_exc()

        # 保持 manifest figure_types 的 order；不在其中的排后面（按 CSV 出现序）
        order_map = {}
        label_map = {}
        try:
            for e in (manifest or {}).get("figure_types") or []:
                if isinstance(e, dict) and e.get("id"):
                    order_map[str(e["id"])] = e.get("order") if isinstance(e.get("order"), int) else 999
                    label_map[str(e["id"])] = e.get("label") or str(e["id"])
        except Exception:
            traceback.print_exc()
        csv_order = []
        for r in rows:
            ft = (r.get("figure_type") or "").strip()
            if ft and ft not in csv_order:
                csv_order.append(ft)
        per_sample_ids = sorted(set(per_sample_ids),
                                key=lambda f: (order_map.get(f, 999),
                                               csv_order.index(f) if f in csv_order else 999))

        # ---- 组装矩阵 ----
        matrix = {sid: {} for sid in samples}
        unmatched = {}
        seen_samples = set()
        n_png_by_ft = {}
        n_pdf_by_ft = {}

        for r in rows:
            ft = (r.get("figure_type") or "").strip()
            if ft not in per_sample_ids:
                continue
            # 契约：ok != TRUE 的行不进矩阵
            ok_val = (r.get("ok") or "").strip().upper()
            if ok_val != "TRUE":
                continue
            p = r.get("path") or ""
            low = p.lower()
            if low.endswith(".png"):
                kind = "png"
            elif low.endswith(".pdf"):
                kind = "pdf"
            else:
                continue
            stem = os.path.splitext(os.path.basename(p))[0]
            sid = _extract_sample_from_stem(stem, samples)
            if not sid or sid not in matrix:
                unmatched.setdefault(ft, [])
                if stem not in unmatched[ft]:
                    unmatched[ft].append(stem)
                continue
            seen_samples.add(sid)
            cell = matrix[sid].setdefault(ft, {"png": None, "pdf": None})
            # 同一 (样本,图型,类型) 出现多行：保留第一条并记差异（不静默覆盖）
            if cell.get(kind):
                unmatched.setdefault(ft, [])
                note = "%s(重复 %s)" % (stem, kind)
                if note not in unmatched[ft]:
                    unmatched[ft].append(note)
            else:
                cell[kind] = p

        # ---- ★ 原始组织切片（第 7 个逐样本页签）：来自原始数据集，**不在图集 CSV 里** ----
        #   为什么追加在**最后**：bind 用 `tabs.currentIndex()` 索引 `figure_types`，
        #   而 W1 的 `FIGURE_TYPE_LABELS` 也把这一型放在最后 ⇒ 两边顺序同构。
        raw_kinds = {}
        try:
            raw_images = list_raw_tissue_images(dataset) or {}
            for sid in samples:
                info = raw_images.get(str(sid)) or {}
                cell = matrix.setdefault(str(sid), {})
                cell[RAW_TISSUE_TYPE_ID] = {"png": info.get("png"), "pdf": None}
                raw_kinds[str(sid)] = info.get("kind") or "none"
        except Exception:
            traceback.print_exc()
        if RAW_TISSUE_TYPE_ID not in per_sample_ids:
            per_sample_ids.append(RAW_TISSUE_TYPE_ID)

        for ft in per_sample_ids:
            n_png_by_ft[ft] = sum(1 for sid in samples
                                  if (matrix.get(sid, {}).get(ft) or {}).get("png"))
            n_pdf_by_ft[ft] = sum(1 for sid in samples
                                  if (matrix.get(sid, {}).get(ft) or {}).get("pdf"))

        # ★ `figure_types` = list[str]（契约冻结形状，W1 的 verify_figure_types 按 str 比对）
        result["figure_types"] = list(per_sample_ids)
        # 富信息移到独立键，形状知识不泄漏进编排层
        result["figure_type_info"] = {
            ft: {"label": label_map.get(ft) or ft,
                 "n_png": n_png_by_ft.get(ft, 0),
                 "n_pdf": n_pdf_by_ft.get(ft, 0),
                 "per_sample": True}
            for ft in per_sample_ids}
        # ★ 原始组织切片**不是图集产物**：标签与来源单列（否则 label 会退化成裸 id；
        #   `source` 让下游一眼看出这张图不归"重跑图集"管 —— 重跑也变不出原图）。
        result["figure_type_info"][RAW_TISSUE_TYPE_ID] = {
            "label": RAW_TISSUE_LABEL,
            "n_png": n_png_by_ft.get(RAW_TISSUE_TYPE_ID, 0),
            "n_pdf": 0,
            "per_sample": True,
            "source": "raw_dataset",
            "kinds": sorted(set(v for v in raw_kinds.values() if v)),
        }
        result["samples"] = samples
        result["matrix"] = matrix
        result["unmatched"] = unmatched
        result["figure_set_id"] = figure_set_id(dataset)
        # 差异如实标出（不静默丢）
        extra = sorted(seen_samples - set(samples))
        missing = sorted(set(samples) - seen_samples)
        result["sample_diff"] = {"extra_in_figures": extra, "missing_in_figures": missing}
        # ★ `ok` 只看**图集**的逐样本图型：原始切片有图不等于"图集读得出来"，
        #   否则一个图集坏掉的数据集会因为原图存在而误判为"可进入审查"。
        atlas_types = [t for t in per_sample_ids if t != RAW_TISSUE_TYPE_ID]
        result["ok"] = bool(atlas_types and samples)
        if not result["ok"]:
            result["reason"] = "未能判定任何逐样本图型（artifacts.per_sample 与 CSV 回退都失败）"
        return result
    except Exception as e:
        traceback.print_exc()
        result["reason"] = "list_review_figures 异常: %s: %s" % (type(e).__name__, e)
        return result


# =============================================================================
# list_all_figures（初步分析页专用；契约外新增，协调者已批准）
# =============================================================================
def list_all_figures(dataset):
    """初步分析页的**全部**图型清单（23 个），不是审查专用那 6 个图集逐样本型

    为什么需要单独一个函数：W1 的初步分析页 `verify_figure_types()` 期望 **23 个
    `figure_type` id**（平铺 23 个页签：`figure_type_order` / `figure_views` 各 23 项；早先是
    `INITIAL_FIGURE_GROUPS` 5 组 → 23 个图位），
    而 `list_review_figures()` 是**审查专用**、返回 6 个图集逐样本型 **+ 1 个原始组织切片**
    （`tissue_raw`，19 样本 × 7 的矩阵）。两者用途不同，**不能互相替代** ——
    且 `tissue_raw` **不得**混进本函数的 `per_sample_paths`（它是审查页的原图参照，
    不是图集产物；本函数的图型来自 manifest / CSV）。

    Returns:
        dict: {
          'ok': bool, 'reason': str, 'figure_set_id': str,
          'figure_types': list[str],                 # 23 个 id，顺序 = manifest 的 order
          'figure_type_info': {id: {'label','panel','panel_label','order',
                                    'per_sample': bool, 'n_files': int}},
          'paths': {id: {'png':p|None, 'pdf':p|None, 'list':[p...]}},  # 非逐样本型
          'per_sample_paths': {id: {sample: {'png':…,'pdf':…}}},       # 仅逐样本型
          'samples': list[str],
        }

    **只返回路径字符串**（不 `QPixmap`、不读图片字节）——
      实测整组织图 13.4 MB/张 vs 逐样本图 1.16 MB/张，差 12 倍；
      W1 另实测"逐样本 6 型 × 19 = 114 张 ≈ 24 秒解码（缩略图只省 12% 时间）"，
      所以**解码时机必须由 bind 按可见性控制**，本函数只负责给路径。

    `per_sample` 布尔取自 **`artifacts[].per_sample`**（实测挂在 artifacts 上，
    不是 figure_types 上），回退判据与 `list_review_figures` 一致 —— **不硬编码那 6 个字符串**。
    """
    result = {"ok": False, "reason": "", "figure_set_id": "",
              "figure_types": [], "figure_type_info": {},
              "paths": {}, "per_sample_paths": {}, "samples": []}
    try:
        manifest, m_err = _read_manifest(dataset)
        rows, raw, c_err = _read_figure_csv(dataset)

        if manifest is None and not rows:
            result["reason"] = "；".join([x for x in (m_err, c_err) if x]) or "无可用数据"
            return result

        samples = _sample_ids_from_manifest(manifest)
        result["samples"] = samples

        # ---- 逐样本型：复用 list_review_figures（同一套判据，避免两份逻辑漂移）----
        #   ★ 原始组织切片（`tissue_raw`）**刻意不并入**这里：它是审查页的"原图参照"，
        #     不是图集产物；而本函数是**初步分析页的图集模型**（23 型 / 24 型）。
        #     混进来会让初步分析页多出一个它没有页签的图型（那边页签是静态常量）。
        review = list_review_figures(dataset)
        per_sample_ids = [ft for ft in (review.get("figure_types") or [])
                          if ft != RAW_TISSUE_TYPE_ID]
        result["per_sample_paths"] = {ft: {sid: dict(
            (review.get("matrix", {}).get(sid, {}).get(ft) or {"png": None, "pdf": None}))
            for sid in samples} for ft in per_sample_ids}

        # ---- 全量图型与元信息（以 manifest 的 figure_types 为准，顺序 = order）----
        ft_meta = {}
        ordered = []
        try:
            entries = [e for e in ((manifest or {}).get("figure_types") or [])
                       if isinstance(e, dict) and e.get("id")]
            entries.sort(key=lambda e: e.get("order") if isinstance(e.get("order"), int) else 999)
            for e in entries:
                fid = str(e["id"])
                ft_meta[fid] = {"label": e.get("label") or fid,
                                "panel": e.get("panel"),
                                "panel_label": e.get("panel_label"),
                                "order": e.get("order")}
                ordered.append(fid)
        except Exception:
            traceback.print_exc()

        # manifest 里没列到、但 CSV 里有的 → 追加并标出（不静默丢）
        csv_types = []
        for r in rows:
            ft = (r.get("figure_type") or "").strip()
            if ft and ft not in csv_types:
                csv_types.append(ft)
        for ft in csv_types:
            if ft not in ft_meta:
                ft_meta[ft] = {"label": ft, "panel": None, "panel_label": None, "order": None}
                ordered.append(ft)

        # per_sample 布尔（artifacts[].per_sample 优先；否则用审查函数的判定结果）
        per_sample_flag = {}
        try:
            for a in (manifest or {}).get("artifacts") or []:
                if not isinstance(a, dict):
                    continue
                ps = a.get("per_sample")
                fid = a.get("figure_type") or a.get("id")
                if fid and isinstance(ps, dict):
                    n_files = ps.get("files")
                    n_samp = ps.get("samples")
                    n_known = len(samples) if samples else 0
                    covered = ((isinstance(n_files, int) and n_files >= max(2, n_known))
                               or (isinstance(n_samp, int) and n_samp >= max(2, n_known)))
                    per_sample_flag[str(fid)] = bool(covered)
        except Exception:
            traceback.print_exc()
        for ft in per_sample_ids:
            per_sample_flag[ft] = True

        # ---- 逐型收集路径 ----
        paths = {}
        try:
            by_ft = {}
            for r in rows:
                ft = (r.get("figure_type") or "").strip()
                if ft:
                    by_ft.setdefault(ft, []).append(r)
            for ft, rs in by_ft.items():
                pngs, pdfs = [], []
                for r in rs:
                    if (r.get("ok") or "").strip().upper() != "TRUE":
                        continue
                    p = r.get("path") or ""
                    low = p.lower()
                    if low.endswith(".png"):
                        pngs.append(p)
                    elif low.endswith(".pdf"):
                        pdfs.append(p)
                is_ps = bool(per_sample_flag.get(ft))
                paths[ft] = {
                    "png": None if is_ps else (pngs[0] if pngs else None),
                    "pdf": None if is_ps else (pdfs[0] if pdfs else None),
                    "list": [] if is_ps else (pngs + pdfs),
                }
        except Exception:
            traceback.print_exc()

        # 补齐没有 CSV 行的图型
        for ft in ordered:
            paths.setdefault(ft, {"png": None, "pdf": None, "list": []})

        info = {}
        for ft in ordered:
            meta = ft_meta.get(ft) or {}
            info[ft] = {"label": meta.get("label") or ft,
                        "panel": meta.get("panel"),
                        "panel_label": meta.get("panel_label"),
                        "order": meta.get("order"),
                        "per_sample": bool(per_sample_flag.get(ft)),
                        "n_files": len((paths.get(ft) or {}).get("list") or [])}
        # 逐样本型的 n_files 用矩阵覆盖率算（更准）
        for ft in per_sample_ids:
            if ft in info:
                info[ft]["n_files"] = sum(
                    1 for sid in samples
                    if (((review.get("matrix", {}).get(sid, {}) or {}).get(ft) or {}).get("png")))

        result["figure_types"] = list(ordered)
        result["figure_type_info"] = info
        result["paths"] = paths
        result["figure_set_id"] = figure_set_id(dataset)
        result["ok"] = bool(ordered)
        if not result["ok"]:
            result["reason"] = "manifest 与图集清单都没有可用的图型"
        return result
    except Exception as e:
        traceback.print_exc()
        result["reason"] = "list_all_figures 异常: %s: %s" % (type(e).__name__, e)
        return result


# =============================================================================
# 评分存取
# =============================================================================
def _empty_scores(dataset="", fs_id=""):
    return {"schema": 1, "dataset": dataset, "figure_set_id": fs_id, "samples": {}}


# 便于 review_state(sample_id) 单参调用（契约冻结签名只有 sample_id）
_LAST_DATASET = None
_LAST_SCORES = None

# 原子写临时文件名用的进程内自增序号（见 `save_review_scores` 的唯一性说明）
_TMP_SEQ = 0


# =============================================================================
# 备注（⑥ 用户明确要求的对外接口）
# =============================================================================
def get_sample_note(sample_id, dataset=None):
    """取某样本的**审查备注**（⑥ 对外接口，供"其他空转分析"消费）

    Args:
        sample_id: 样本 id（`GSM*`）
        dataset: 数据集名；None 时用**最近一次 `load_review_scores` 的缓存**
    Returns:
        str: 备注原文；**读不到 / 损坏 / 无备注一律返回 `""`，绝不抛**

    ★ 约定（本轮冻结）：
      · 备注存在 `review.json` 的 `samples[<sid>]['note']`（字符串）；
      · **老文件没有该字段 → 视为 `""`**（不迁移、不写回、不抛）；
      · 本函数是**唯一对外读备注的入口**（消费方不要自己读 JSON / 猜路径）。
    """
    try:
        if not sample_id:
            return ""
        src = None
        if dataset:
            src = load_review_scores(dataset)
        elif _LAST_SCORES is not None:
            src = _LAST_SCORES
        if not isinstance(src, dict):
            return ""
        entry = (src.get("samples") or {}).get(str(sample_id))
        if not isinstance(entry, dict):
            return ""
        note = entry.get("note")
        return "" if note is None else str(note)
    except Exception:
        traceback.print_exc()
        return ""


def get_sample_note_label(sample_id, dataset=None, prefix="备注"):
    """带前缀的便利版（供 tooltip / 日志直接用）

    · 有备注 → `"备注：<原文>"`
    · **无备注 → `""`**（调用方据此**不显示提示**，避免空框或"无备注"）
    """
    try:
        note = get_sample_note(sample_id, dataset)
        return ("%s：%s" % (prefix, note)) if note else ""
    except Exception:
        traceback.print_exc()
        return ""


def set_sample_note(dataset, sample_id, note):
    """单点写备注（读-改-原子写）。常规路径是**改内存 + 与评分同一次落盘**，本函数备用。

    Returns:
        bool: 是否成功（失败不抛；测试数据集外默认拒绝写，见 `_write_allowed`）
    """
    try:
        if not dataset or not sample_id:
            return False
        if not _write_allowed(dataset):
            print("[spatial_review] 拒绝写入非测试数据集: %s（见 _write_allowed 说明）" % dataset)
            return False
        data = load_review_scores(dataset)
        entry = (data.setdefault("samples", {})).setdefault(str(sample_id), {})
        entry["note"] = str(note or "")
        return bool(save_review_scores(dataset, data))
    except Exception:
        traceback.print_exc()
        return False


def review_version(dataset):
    """评分存储的**廉价版本指纹**（需求④：让"评分变了"能进幂等键）

    Returns:
        tuple: `(mtime_ns, size)`；**文件不存在 / 读不到属性 → `("none", 0)`**

    ## 为什么需要它（用户第二轮实测报的 bug）
      初步分析页 `on_page_entered()` 的幂等键原本是 `(dataset, figure_set_id)` ——
      **评分变化根本不在这个键里**（`figure_set_id` 只反映图集）。
      于是：去审查页打分 → 回初步分析页 → 键没变 → 跳过刷新 →
      `⚠未审` 角标 / `已审查 N/19` / 备注悬停提示**全是旧的**，**只有重启才更新**。

    ## 为什么用 (mtime_ns, size) 而不是读文件算哈希
      · 这个函数会被**每次进页面**调用，而 review.json 只有几百字节到几十 KB，
        真读一次也不算贵；但 `load_review_scores` 已经会读它，
        **再算一次哈希等于读两遍**，且哈希对"内容没变但被重写"会给出相同值 ——
        而 `(mtime_ns, size)` 反而能反映"有人动过这个文件"。
      · `save_review_scores` 走的是**临时文件 + `os.replace`**（原子替换），
        `os.replace` 会换掉 inode，`st_mtime_ns` 必然变 ⇒ 能可靠检测到"保存过了"。
      · `st_mtime_ns` 在 Windows/NTFS 上是 100 ns 精度，同一秒内的两次保存也能区分。

    ★ 只读，**绝不写盘、绝不迁移**；任何异常都退化成 `("none", 0)`，不抛。
    """
    try:
        path = _review_json_path_for(dataset)
        st = os.stat(path)
        return (int(st.st_mtime_ns), int(st.st_size))
    except Exception:
        # 文件不存在 / 无权限 / 路径非法 —— 全归为"没有评分存储"
        return ("none", 0)


def load_review_scores(dataset):
    """读评分（契约 §4.2）

    Returns:
        dict: `{"schema":1, "dataset":…, "figure_set_id":…, "samples":{…}, "_issues":[…]}`。
              **读不到 / 损坏 / 结构不对 → 返回空结构（并写 `_issues`），绝不抛**。
              空结构与"读到了但一个分都没有"在语义上等价，调用方用 `_issues` 区分。

    ★ **`figure_set_id` 的语义（协调者裁决，必读）**：
      本文件里的 `figure_set_id` 一律指 **`list_review_figures()['figure_set_id']`
      返回的那个值**（或等价的 `figure_set_id(dataset)`）。
      **调用方绝对不要自己另算一个 id**（例如拿 manifest 路径再调一次 `figure_set_id`）——
      历史上"按传入路径就地算"会给出不同 id，导致审查页**永远误报**"评分对应旧图集"。
      比较时：`scores.get('figure_set_id') != current_figure_set_id` → 才算图集变了。
    """
    global _LAST_DATASET, _LAST_SCORES
    try:
        path = _review_json_path_for(dataset)
        data, err = _read_json(path)
        issues = []
        if data is None:
            d = _empty_scores(dataset, "")
            d["_issues"] = [err] if err else []
            _LAST_DATASET, _LAST_SCORES = dataset, d
            return d
        if not isinstance(data, dict):
            d = _empty_scores(dataset, "")
            d["_issues"] = ["评分文件顶层不是对象（实际是 %s）" % type(data).__name__]
            _LAST_DATASET, _LAST_SCORES = dataset, d
            return d
        if not isinstance(data.get("samples"), dict):
            issues.append("samples 字段缺失或不是对象，已按空处理")
            data["samples"] = {}
        if not isinstance(data.get("figure_set_id"), str):
            issues.append("figure_set_id 缺失或类型不对")
            data["figure_set_id"] = data.get("figure_set_id") or ""
        if data.get("schema") is None:
            issues.append("schema 缺失")
            data["schema"] = 1
        data["_issues"] = issues
        _LAST_DATASET, _LAST_SCORES = dataset, data
        return data
    except Exception as e:
        traceback.print_exc()
        d = _empty_scores(dataset, "")
        d["_issues"] = ["load_review_scores 异常: %s: %s" % (type(e).__name__, e)]
        return d


def save_review_scores(dataset, data):
    """原子写评分（契约 §4.2：临时文件 + `os.replace`）

    Returns:
        bool: 是否写入成功（失败已写日志，**不抛**）

    ⚠ 原子性不是可选项：并发/崩溃若损毁已有评分，用户**几十分钟的人工打分就没了**。
      同目录临时文件 + `os.replace` 保证"要么是旧的完整文件、要么是新的完整文件"。

    ★ **`data['figure_set_id']` 必须是 `list_review_figures()['figure_set_id']`**（见
      `load_review_scores` 的说明）——**不要自己另算**，否则读回来必然 `!=`，页面永远误报旧图集。
    """
    try:
        if not dataset:
            return False
        if not isinstance(data, dict):
            return False
        payload = {k: v for k, v in data.items() if not (isinstance(k, str) and k.startswith("_"))}
        payload.setdefault("schema", 1)
        payload["dataset"] = payload.get("dataset") or dataset
        payload.setdefault("samples", {})

        path = _review_json_path_for(dataset)
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)

        # ★ 临时名必须**唯一到"同一毫秒内的两个进程/两次调用也不会撞"**：
        #   只用毫秒时间戳时，两个进程同毫秒写同一数据集会共用同一个 tmp 文件，
        #   先写完的那个被后一个 `os.replace` 消耗掉 → 后者 `FileNotFoundError`，
        #   更糟的是可能把**半个文件**replace 上去。加 pid + 进程内自增序号把窗口关死。
        global _TMP_SEQ
        _TMP_SEQ += 1
        tmp = "%s.tmp.%d.%d.%d" % (path, os.getpid(), int(time.time() * 1000), _TMP_SEQ)
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)     # 同目录 rename，Windows 下原子
        return True
    except Exception as e:
        traceback.print_exc()
        try:
            if 'tmp' in dir() and tmp and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def review_state(sample_id, scores=None, dataset=None):
    """样本审查状态（契约 §4.2 冻结签名 `review_state(sample_id)`）

    Returns:
        'scored'      —— 该样本**总分**已打分（>0）
        'unreviewed'  —— 未打分 / 数据缺失 / 任何异常

    取分顺序：显式传入的 `scores` → 显式 `dataset` 的评分文件 → 最近一次 load 的缓存。
    （契约只给了一个参数，但审查页通常已持有 scores；两条路都支持，便于调用方省一次 IO。）
    """
    try:
        if not sample_id:
            return "unreviewed"
        src = scores
        if src is None:
            if dataset:
                src = load_review_scores(dataset)
            elif _LAST_SCORES is not None:
                src = _LAST_SCORES
        if not isinstance(src, dict):
            return "unreviewed"
        entry = (src.get("samples") or {}).get(str(sample_id))
        if not isinstance(entry, dict):
            return "unreviewed"
        total = entry.get("total")
        try:
            if total is not None and int(total) > 0:
                return "scored"
        except Exception:
            pass
        return "unreviewed"
    except Exception:
        traceback.print_exc()
        return "unreviewed"


def reviewed_high_score_samples(scores, min_stars=4):
    """总分 ≥ min_stars 的样本 id 清单（供初步分析页的「选已审查高分」快捷按钮）

    Args:
        scores: load_review_scores() 的返回值
        min_stars: 阈值（默认 4）
    Returns:
        list[str]
    """
    out = []
    try:
        for sid, entry in ((scores or {}).get("samples") or {}).items():
            if not isinstance(entry, dict):
                continue
            try:
                if int(entry.get("total") or 0) >= int(min_stars):
                    out.append(str(sid))
            except Exception:
                continue
    except Exception:
        traceback.print_exc()
    return out


__all__ = [
    'figure_set_id',
    'color_for_stars',
    'chip_color_for_stars',
    'colors_for_stars',
    'list_review_figures',
    'list_all_figures',
    'load_review_scores',
    'save_review_scores',
    'review_state',
    'reviewed_high_score_samples',
    'rel_lum',
    'contrast_ratio',
]
