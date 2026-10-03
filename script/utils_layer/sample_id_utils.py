# -*- coding: utf-8 -*-
"""样本 id 解析：从**任意文本**里取回真实样本 id（唯一实现处）

## 为什么要有这个模块（真 bug 的根因件）
空转层的列表项文本形如：
    `⚠未审  UKF241_C_ST UKF241_C_ST`
    `★★★★☆  GSM7596587 mgh258`
四个 UI 绑定层各自写死 `re.search(r'(GSM\\d+)', text)` 来从文本里抠样本号。
这在 GSE237183（GEO，样本 id 是 `GSM*`）上碰巧成立，但对
**Dryad_UKF（`UKF241_C_ST` 这种 id）完全抓不到** —— 解析恒返回 None，后果：

  · 审查页：`_select_sample_in_list` 找不到样本 ⇒ `current_sample` 恒为 None
    ⇒ `_fill_figure_page` 拿不到 sid ⇒ **每个样本每个图型页签都不出图**（用户报的 bug）；
  · 初始/表达页：`_apply_selection` 无法把 `self._selected` 落到列表项
    ⇒ 勾选状态同步失效（同源缺陷，未等到用户报就先修）。

契约依据：`spatial_manifest` 的**契约修订 R1** 已把样本 id 判据从
`sid.startswith('GSM')` 放宽为 `^[A-Za-z][A-Za-z0-9_.\\-]*$`
（GEO 之外的数据集根本没有 GSM 编号）。本模块是该判据在**取 id**方向的对应实现。

## 取 id 的正确顺序（"清单优先，形态兜底"）
  ① `QListWidgetItem` 的 `Qt.UserRole`（**权威**：写入方就是建列表的人）；
  ② 已知样本清单里的 id 出现在文本里 —— **最长优先 + 右侧词边界**：
     · 最长优先：`UKF313_T_ST` 必须赢过它的前缀 `UKF313_T`（两者都可能是合法样本）；
     · 右侧边界：`GSM759658` 不能命中 `GSM7596587` 的中间（防截断误配；
       判据是"紧邻字母/数字/`_`/`-`"，**`.` 不算**，否则 `..._<sid>.png` 永远认不出）；
       左侧**允许紧邻**（文件名是 `<前缀>_<sid>`，左侧那个 `_` 不能当成越界）。
  ③ 兜底（拿不到清单时）：形状像 id、且**至少含一个数字**的最长 token。

★ 全程**不做** `re.escape`（用 `str.find` 匹配清单项，天然免转义），也不按空格硬切
  （文本前缀里有中文、全角字符与 ★☆⚠）。
"""
import re

#: 样本 id 形态（与 `spatial_manifest._SAMPLE_ID_RE` 同一判据，契约修订 R1）
SAMPLE_ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_.\-]*$')

_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789_.-")

#: 右侧"紧邻即视为 id 被截断"的字符集：**不含 `.`**
#  （`.png` / `.pdf` 是扩展名分隔，不是 id 延续；而 `GSM7596587` 的尾部 `7` 必须拦住）
_RIGHT_BLOCK = set("abcdefghijklmnopqrstuvwxyz"
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   "0123456789_-")

_TOKEN_RE = re.compile(r'[A-Za-z][A-Za-z0-9_.\-]*')


def is_valid_sample_id(value):
    """形态校验：首字符必须是字母（纯数字 / 空串 / 带空格一律 False）"""
    try:
        return bool(SAMPLE_ID_RE.match(str(value or "")))
    except Exception:
        return False


def _boundary_ok(text, start, end, left_required=True):
    """命中区间**右侧**不能紧邻 id 延续字符（防 `GSM759658` 命中 `GSM7596587` 内部）

    ★ 右侧判据用的是 `_RIGHT_BLOCK`（字母/数字/`_`/`-`，**不含 `.`**）：
      图文件名场景 `05_umap_UKF313_T_ST.png` 的 id 后面紧跟 `.png`，
      若把 `.` 也算延续字符，这条最常用的形态就永远认不出来。
    ★ 左侧默认要求不紧邻，但允许在第二遍放开（`left_required=False`）：
      图文件名场景是 `<前缀>_<sid>`（如 `01_nCount_UKF241_C_ST`），
      左侧恒为 `_`（本身就是 id 字符）—— 死守左边界会把整条 stem 当成样本号。
    """
    if left_required and start > 0 and text[start - 1] in _ID_CHARS:
        return False
    if end < len(text) and text[end] in _RIGHT_BLOCK:
        return False
    return True


def _find_known(text, known):
    """① 已知清单：**最长优先**；先要求双侧边界，再放开左边界重试一遍

    Returns:
        str | None
    """
    ordered = sorted({str(s) for s in known if str(s)}, key=len, reverse=True)
    for left_required in (True, False):
        for sid in ordered:
            start = text.find(sid)
            while start != -1:
                if _boundary_ok(text, start, start + len(sid), left_required):
                    return sid
                start = text.find(sid, start + 1)
    return None


def _find_by_shape(text):
    """③ 兜底：形状像 id 且至少含一个数字的最长 token"""
    best = None
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        if not is_valid_sample_id(tok):
            continue
        if not any(ch.isdigit() for ch in tok):
            continue        # 纯字母 token 多半是标签词（如样本分组名），不认
        if best is None or len(tok) > len(best):
            best = tok
    return best


def extract_sample_id(text, known_samples=None):
    """从任意文本里取样本 id（列表项文本 / 图片文件名 / 备注均可）

    Args:
        text: 待解析文本（None / 非字符串一律安全处理）
        known_samples: 可选，权威样本清单（list/tuple/set of str）
    Returns:
        str | None —— 取不到返回 None（**绝不返回空串或猜测值**）
    """
    try:
        t = str(text or "")
        if not t:
            return None
        known = []
        if known_samples:
            if isinstance(known_samples, (str, bytes)):
                known = [known_samples]
            else:
                known = [str(s) for s in known_samples if str(s)]
        if known:
            hit = _find_known(t, known)
            if hit:
                return hit
        return _find_by_shape(t)
    except Exception:
        return None


def sample_id_from_item(item, known_samples=None):
    """从 `QListWidgetItem` 取样本 id：先读 `Qt.UserRole`（权威），再解析文本

    ★ PyQt 为**惰性导入**：本模块在没有 Qt 的解释器里（数据层脚本 / 单测）照样可用。
      取不到 `UserRole`（控件没写、或写的是非法值）时**静默回退文本解析**——
      这是正常的兼容路径，不是错误路径。
    """
    role = None
    try:
        from PyQt5.QtCore import Qt
        role = item.data(Qt.UserRole)
    except Exception:
        role = None
    if role not in (None, ""):
        s = str(role)
        known = []
        if known_samples:
            known = [str(x) for x in known_samples if str(x)]
        if not known or s in known:
            return s
    try:
        txt = item.text()
    except Exception:
        txt = ""
    return extract_sample_id(txt, known_samples)


__all__ = ["SAMPLE_ID_RE", "is_valid_sample_id",
           "extract_sample_id", "sample_id_from_item"]
