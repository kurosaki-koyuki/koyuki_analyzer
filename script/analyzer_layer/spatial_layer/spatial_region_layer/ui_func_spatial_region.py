# -*- coding: utf-8 -*-
"""M4「绘制区域」子页面 —— 显示层（契约 `docs/features/spatial_m2m3_contract.md` §13 / §14.2）

职责（W1）：
  · `region_sample_list` 每项文本的**唯一生成处**（§14.2 冻结的两种逐字格式）；
  · 往**既有**控件里填条目 / 重刷条目文本 —— **绝不 new 控件、绝不读数据文件**。

冻结格式（**逐字**，符号与样本号之间是两个空格）：

    已画：``✅ 已画 N 区  <样本号>``
    未画：``⚠ 未画  <样本号>``

分层与生命周期：
  · 本文件不 import 任何 analysis / 数据模块 ⇒ 布局构造期不读数据（闸门 H）；
  · 区域个数由 W2 通过
    `SpatialRegionPageUI.set_region_counts()` / `set_sample_items()` 传入；
    **取不到就按「未画」渲染**，任何异常形态一律容错，绝不抛。

★ 「重刷不能冲掉」：
  `install_sample_autostamp()` 会把 `region_sample_list` 的
  `addItem / addItems / insertItem` 包一层 → W2 在画布/列表重建时
  `clear()` + 重新 `addItem`，条目文本仍会被本地重新盖成冻结格式；
  而没有更权威计数的**既有冻结文本不会被降级覆盖**（见 `_restamp_item`）。
"""

import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QListWidgetItem

__all__ = [
    'FMT_PAINTED',
    'FMT_UNPAINTED',
    'MASK_ROW_TAG',
    'VISIBLE_ROW_TAG',
    'region_row_tag',
    'region_sample_text',
    'is_frozen_sample_text',
    'parse_sample_id_from_text',
    'set_sample_items',
    'restamp_sample_items',
    'install_sample_autostamp',
    'region_list_item_text',
    'refresh_region_list_names',
    'install_region_list_autostamp',
]

# ---- §14.2 冻结文本（逐字，勿改空格）----
FMT_PAINTED = "✅ 已画 %d 区  %s"
FMT_UNPAINTED = "⚠ 未画  %s"

_FROZEN_RE = re.compile(r"^(?:✅ 已画 \d+ 区|⚠ 未画)  ")

# ---- 区域列表行：「<序号>. [可选范围层标记] <名字>（…）」 ----
#   ★ 两种**范围层**必须一眼分清（2026-09 用户把"编辑边"改成"可见区域"后新增）：
#       `👁 [可见]` = 可见区域范围层（决定哪些区域的虚线边界画出来）
#       `🫥 [隐形]` = 隐形区域范围层（决定这些虚线在最终出图里是否呈现）
#   ★ 标记与名字**分开捕获**：改名时只换名字，标记不丢；
#     标记态真的变了（普通 ↔ 可见 ↔ 隐形）则整行重写（见 refresh_region_list_names）。
MASK_ROW_TAG = "🫥 [隐形] "
VISIBLE_ROW_TAG = "👁 [可见] "
_REGION_ROW_RE = re.compile(
    r"^(?P<head>\s*\d+\.\s*)(?P<tag>🫥 \[隐形\]\s*|👁 \[可见\]\s*)?"
    r"(?P<name>.*?)(?P<tail>[（(].*)?$")


def _sreg_module():
    """惰性取 analysis 层（避免 import 期循环依赖）；拿不到 → None"""
    try:
        from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as _SREG
        return _SREG
    except Exception:
        return None


def region_row_tag(region):
    """该区域行首的**范围层标记**（普通区域 = 空串）

    ★★ 判据**只有一处真相源**：直接复用分析层的
      `SREG.is_layer_region()` + `SREG._norm_flag()`，
      **不自己写 `if reg.get("mask")` 这种真值判断**。
      原因（协调者探针实测的分歧）：
        `bool("false") == True` ⇒ `{"mask": "false"}` 在**列表里标成 [隐形]**，
        而门槛 `SREG.is_layer_region()` 按严格白名单判**普通区域** ⇒ 同一条区域两套说法。
      `_norm_flag` 的白名单 = `True/1/"true"/"True"/"1"`（其余 false/0/None 一律假）。
    ★ 两者都为真时 **mask 优先**（保持原行为）。
    ★ analysis 层不可用时返回 `""`（**保守：不声称它是范围层**）——
      宁可少一个标记，也不要再引入第二套判据。
    """
    reg = region if isinstance(region, dict) else {}
    sreg = _sreg_module()
    if sreg is None:
        return ""
    try:
        if not sreg.is_layer_region(reg):
            return ""
        if sreg._norm_flag(reg.get("mask")):
            return MASK_ROW_TAG
        if sreg._norm_flag(reg.get("visible")):
            return VISIBLE_ROW_TAG
        return ""
    except Exception:
        return ""

# ---- 容错取字段（W2 传什么形状都能吃）----
_SID_KEYS = ('sample_id', 'sid', 'sample', 'id', 'name')
_COUNT_KEYS = ('region_count', 'regions_count', 'n_regions', 'regions', 'count', 'n')
_PAINTED_KEYS = ('painted', 'has_regions', 'has_region', 'drawn')

_AUTOSTAMP_FLAG = '_dsh_sample_autostamp'


# ======================================================================
# 文本
# ======================================================================
def region_sample_text(sample_id, region_count=None, painted=None):
    """按 §14.2 冻结格式生成样本条目文本（唯一生成处）。

    Args:
        sample_id: 样本号（任意可 str 化的值）
        region_count: 区域个数；None / 非法 → 视为「未画」（**不崩**）
        painted: 显式已画标记；None 时由 `region_count > 0` 推断。
                 显式 True 但个数取不到时仍按「未画」渲染（渲染不出 N 就不假装已画）。

    Returns:
        str: `✅ 已画 N 区  <样本号>` 或 `⚠ 未画  <样本号>`
    """
    sid = _norm_sid(sample_id)
    n = _to_int(region_count)
    if painted is None:
        is_painted = (n is not None and n > 0)
    else:
        is_painted = bool(painted) and (n is not None and n > 0)
    if is_painted:
        return FMT_PAINTED % (n, sid)
    return FMT_UNPAINTED % sid


def is_frozen_sample_text(text):
    """文本是否已符合冻结格式（用于「别把已有标记冲掉」的判断）"""
    try:
        return bool(_FROZEN_RE.match(str(text or "")))
    except Exception:
        return False


def parse_sample_id_from_text(text):
    """从条目文本里反解样本号（先剥冻结前缀，否则取最后一个空白分词）"""
    try:
        raw = str(text or "")
    except Exception:
        return ""
    if _FROZEN_RE.match(raw):
        return _FROZEN_RE.sub("", raw, count=1).strip()
    parts = raw.split()
    return parts[-1] if parts else ""


# ======================================================================
# 条目填充 / 重刷
# ======================================================================
def set_sample_items(list_widget, samples, region_counts=None, selected_id=None):
    """清空并重建样本列表条目（文本一律走 `region_sample_text`）。

    Args:
        list_widget: `region_sample_list`（QListWidget）；None / 无 addItem → 直接返回 0
        samples: list，元素可为
                 · dict（`id`/`sample_id`/`sid`…，可选 `region_count`/`count`/`n_regions`…、
                   `painted`/`has_regions`/`drawn`）
                 · (sid, count[, painted]) 元组 / 列表
                 · str（只有样本号 ⇒ 渲染为未画）
                 **顺序原样保留**（样本号排序由调用方给出，本层不重排）
        region_counts: {样本号: 区域个数}，比条目自带字段更权威
        selected_id: 需要选中的样本号（可选）

    Returns:
        int: 实际加入的条目数
    """
    if list_widget is None or not hasattr(list_widget, 'addItem'):
        return 0
    counts = _norm_counts(region_counts)
    try:
        list_widget.clear()
    except Exception:
        return 0
    entries = samples if isinstance(samples, (list, tuple)) else []
    want = _norm_sid(selected_id)
    added = 0
    for entry in entries:
        sid, count, painted = _entry_parts(entry, counts)
        if not sid:
            continue
        item = QListWidgetItem(region_sample_text(sid, count, painted))
        try:
            item.setData(Qt.UserRole, sid)
        except Exception:
            pass
        try:
            list_widget.addItem(item)
        except Exception:
            continue
        added += 1
        if want and sid == want:
            try:
                list_widget.setCurrentItem(item)
            except Exception:
                pass
    return added


def restamp_sample_items(list_widget, region_counts=None):
    """就地重刷所有条目的冻结文本（**不动顺序、不清空、不碰 UserRole**）。

    Returns:
        int: 文本真正发生变化的条目数
    """
    if list_widget is None or not hasattr(list_widget, 'item'):
        return 0
    counts = _norm_counts(region_counts)
    try:
        total = int(list_widget.count())
    except Exception:
        return 0
    changed = 0
    for row in range(total):
        item = list_widget.item(row)
        if item is None:
            continue
        if _restamp_item(item, counts):
            changed += 1
    return changed


def install_sample_autostamp(list_widget, counts_provider=None):
    """把 `addItem / addItems / insertItem` 包一层，加入的条目自动盖冻结文本。

    ★ 这样 W2 现有的 `clear()` + `addItem(QListWidgetItem(sid))` 重建路径
      也会自动得到 `⚠ 未画  <样本号>`，且**重建后不会被冲掉**。

    Args:
        list_widget: 目标 QListWidget
        counts_provider: 无参可调用对象 → {样本号: 区域个数}（取不到/抛异常 → 视为空）

    Returns:
        bool: 是否成功装上（装上过就不再重复包，幂等）
    """
    if list_widget is None:
        return False
    if getattr(list_widget, _AUTOSTAMP_FLAG, False):
        return True
    try:
        orig_add_item = list_widget.addItem
        orig_add_items = getattr(list_widget, 'addItems', None)
        orig_insert_item = getattr(list_widget, 'insertItem', None)
    except Exception:
        return False

    def _counts():
        if counts_provider is None:
            return {}
        try:
            return _norm_counts(counts_provider())
        except Exception:
            return {}

    def _stamp_last():
        try:
            row = int(list_widget.count()) - 1
            if row < 0:
                return
            _restamp_item(list_widget.item(row), _counts())
        except Exception:
            pass

    def add_item(*args):
        orig_add_item(*args)
        _stamp_last()

    def add_items(*args):
        if orig_add_items is None:
            return
        try:
            before = int(list_widget.count())
        except Exception:
            before = 0
        orig_add_items(*args)
        try:
            total = int(list_widget.count())
        except Exception:
            total = before
        counts = _counts()
        for row in range(max(before, 0), total):
            _restamp_item(list_widget.item(row), counts)

    def insert_item(*args):
        if orig_insert_item is None:
            return
        orig_insert_item(*args)
        try:
            row = int(args[0]) if args else 0
            _restamp_item(list_widget.item(row), _counts())
        except Exception:
            pass

    try:
        list_widget.addItem = add_item
        if orig_add_items is not None:
            list_widget.addItems = add_items
        if orig_insert_item is not None:
            list_widget.insertItem = insert_item
        setattr(list_widget, _AUTOSTAMP_FLAG, True)
    except Exception:
        return False
    return True


# ======================================================================
# 区域列表（`region_list_widget`）行文本 —— 改名后列表要跟着变
# ======================================================================
def region_list_item_text(index, region):
    """区域列表一行的**兜底**文本（`1. MES（12 点）`；范围层行带标记前缀）

    ★ 两种范围层各自一眼可辨：`🫥 [隐形] <名字>（N 点）` / `👁 [可见] <名字>（N 点）`
      —— 能看出是哪种范围层（标记，判据见 `region_row_tag`）、能改名（名字就在行里）、
      能删（"删除选中区域"按钮，靠选中该行生效）。
    """
    try:
        i = int(index)
    except (TypeError, ValueError):
        i = 0
    reg = region if isinstance(region, dict) else {}
    name = str(reg.get("name") or "").strip() or "未命名"
    tag = region_row_tag(reg)
    try:
        npts = len(reg.get("points") or [])
    except Exception:
        npts = 0
    return "%d. %s%s（%d 点%s）" % (i + 1, tag, name, npts,
                                    "，无效" if reg.get("invalid") else "")


def refresh_region_list_names(list_widget, regions, only_index=None):
    """就地更新区域列表里的**名字**（改名后调用）。

    Args:
        list_widget: `region_list_widget`
        regions: 区域列表（通常就是 `canvas.get_regions()`）
        only_index: 只刷这一行（None = 全部）

    ★ 只改名字，**保留行内其余信息**（点数/无效标记等由 bind 生成的部分不动）、
      **不清空、不重排、不动 UserRole、不切当前行**（清单行 ↔ 区域索引一一对应）。
    ★ 正则匹配不上时用 `region_list_item_text` 兜底整行重写。
    Returns: int —— 真正改动过的行数
    """
    if list_widget is None or not hasattr(list_widget, "item"):
        return 0
    regs = regions if isinstance(regions, (list, tuple)) else []
    try:
        total = int(list_widget.count())
    except Exception:
        return 0
    want = None
    if only_index is not None:
        try:
            want = int(only_index)
        except (TypeError, ValueError):
            want = None
    changed = 0
    for row in range(total):
        if want is not None and row != want:
            continue
        item = list_widget.item(row)
        if item is None:
            continue
        region = regs[row] if (row < len(regs) and isinstance(regs[row], dict)) else None
        if region is None:
            continue
        name = str(region.get("name") or "").strip()
        try:
            old = str(item.text() or "")
        except Exception:
            continue
        match = _REGION_ROW_RE.match(old)
        # ★ 只有"名字非空"且"范围层标记态没变"时才能只换名字；标记态变了要整行重写
        #   （普通 ↔ 可见 ↔ 隐形：三种标记互不相同，必须按 region_row_tag 逐字比）
        same_tag = bool(match is not None
                        and (match.group("tag") or "") == region_row_tag(region))
        if match is not None and name and same_tag:
            new = (match.group("head") + (match.group("tag") or "")
                   + name + (match.group("tail") or ""))
        else:
            new = region_list_item_text(row, region)
        if new == old:
            continue
        try:
            item.setText(new)
        except Exception:
            continue
        changed += 1
    return changed


# ======================================================================
# 区域列表行的"自动盖章"：bind 重建列表时**选区标记不会被冲掉**
# ------------------------------------------------------------
# bind 的 `_refresh_region_list()` 是 `clear()` + 自己格式串 `addItem`；
# 若只靠 rename 时重刷，下一次绑定层刷新就会把 `🫥 [选区]` 抹掉。
# 这里与样本列表 `install_sample_autostamp` 同一手法：把 `addItem/addItems/
# insertItem` 包一层，加入的条目**按画布当前区域重算整行文本**（幂等）。
# ======================================================================
_REGION_AUTOSTAMP_FLAG = '_dsh_region_list_autostamp'


def _restamp_region_row(item, row, regions):
    """把第 row 行文本重算成 `region_list_item_text(row, regions[row])`（幂等）"""
    if item is None or not isinstance(regions, (list, tuple)):
        return False
    if not (0 <= row < len(regions)) or not isinstance(regions[row], dict):
        return False
    try:
        new = region_list_item_text(row, regions[row])
    except Exception:
        return False
    try:
        if str(item.text() or "") == new:
            return False
        item.setText(new)
    except Exception:
        return False
    return True


def install_region_list_autostamp(list_widget, regions_provider=None):
    """给 `region_list_widget` 装"自动盖章"：新加入的条目自动带选区标记

    Args:
        list_widget: `region_list_widget`
        regions_provider: 无参可调用 → 区域列表（通常 `canvas.get_regions()`）
    Returns:
        bool —— 是否装上（已装过则幂等返回 True）
    """
    if list_widget is None:
        return False
    if getattr(list_widget, _REGION_AUTOSTAMP_FLAG, False):
        return True
    try:
        orig_add_item = list_widget.addItem
        orig_add_items = getattr(list_widget, 'addItems', None)
        orig_insert_item = getattr(list_widget, 'insertItem', None)
    except Exception:
        return False

    def _regions():
        if regions_provider is None:
            return []
        try:
            regs = regions_provider()
            return regs if isinstance(regs, (list, tuple)) else []
        except Exception:
            return []

    def add_item(*args):
        orig_add_item(*args)
        try:
            _restamp_region_row(list_widget.item(int(list_widget.count()) - 1),
                                int(list_widget.count()) - 1, _regions())
        except Exception:
            pass

    def add_items(*args):
        if orig_add_items is None:
            return
        try:
            before = int(list_widget.count())
        except Exception:
            before = 0
        orig_add_items(*args)
        regs = _regions()
        try:
            total = int(list_widget.count())
        except Exception:
            total = before
        for row in range(max(before, 0), total):
            _restamp_region_row(list_widget.item(row), row, regs)

    def insert_item(*args):
        if orig_insert_item is None:
            return
        orig_insert_item(*args)
        try:
            _restamp_region_row(list_widget.item(int(args[0])), int(args[0]), _regions())
        except Exception:
            pass

    try:
        list_widget.addItem = add_item
        if orig_add_items is not None:
            list_widget.addItems = add_items
        if orig_insert_item is not None:
            list_widget.insertItem = insert_item
        setattr(list_widget, _REGION_AUTOSTAMP_FLAG, True)
    except Exception:
        return False
    return True


# ======================================================================
# 内部工具
# ======================================================================
def _restamp_item(item, counts):
    """把单条 item 的文本盖成冻结格式；已有冻结文本且无更权威计数时**不降级**"""
    try:
        old = str(item.text() or "")
    except Exception:
        return False
    sid = ""
    has_role = True
    try:
        raw_role = item.data(Qt.UserRole)
    except Exception:
        raw_role = None
    sid = _norm_sid(raw_role)
    if not sid:
        sid = parse_sample_id_from_text(old)
        has_role = False
    if not sid:
        return False
    if not has_role:
        # ★ 以字符串加入的条目本来没有 UserRole；而文本现在带 ✅/⚠ 前缀后
        #   bind 侧「按 UserRole 取样本号，取不到回退 text()」会取到整条文本 ⇒ 必须补回
        try:
            item.setData(Qt.UserRole, sid)
        except Exception:
            pass
    known = counts.get(sid)
    if known is not None:
        new = region_sample_text(sid, known)
    elif is_frozen_sample_text(old):
        return False            # ★ 别把已有的 ✅/⚠ 标记冲掉
    else:
        new = region_sample_text(sid, None)      # 取不到就按「未画」
    if new == old:
        return False
    try:
        item.setText(new)
    except Exception:
        return False
    return True


def _entry_parts(entry, counts):
    """把任意元素形态解析成 (sid, region_count, painted)；解析不到一律 None"""
    sid = None
    count = None
    painted = None
    if isinstance(entry, dict):
        for key in _SID_KEYS:
            if key in entry:
                sid = _norm_sid(entry.get(key))
                break
        for key in _COUNT_KEYS:
            if key in entry:
                count = _to_int(entry.get(key))
                break
        for key in _PAINTED_KEYS:
            if key in entry:
                painted = bool(entry.get(key))
                break
    elif isinstance(entry, (list, tuple)):
        if len(entry) >= 1:
            sid = _norm_sid(entry[0])
        if len(entry) >= 2:
            second = entry[1]
            if isinstance(second, bool):
                painted = second
            else:
                count = _to_int(second)
        if len(entry) >= 3 and painted is None:
            painted = bool(entry[2])
    else:
        sid = _norm_sid(entry)
    if sid and counts:
        known = counts.get(sid)
        if known is not None:
            count = known
    return sid, count, painted


def _norm_counts(region_counts):
    """把 {样本号: 个数} 规整为 {str: int}（非法值丢弃，绝不抛）"""
    out = {}
    if not isinstance(region_counts, dict):
        return out
    for key, value in region_counts.items():
        sid = _norm_sid(key)
        if not sid:
            continue
        n = _to_int(value)
        if n is None:
            continue
        out[sid] = n
    return out


def _norm_sid(value):
    if value is None or isinstance(value, bool):
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _to_int(value):
    """宽容取整数：None / 文本 / 浮点都能吃，取不到返回 None（bool 视为非数）"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        try:
            return int(value)
        except Exception:
            return None
    try:
        return int(str(value).strip())
    except Exception:
        pass
    try:
        return int(float(str(value).strip()))
    except Exception:
        return None
