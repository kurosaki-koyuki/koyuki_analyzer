# -*- coding: utf-8 -*-
"""空转「一键批量导出」- analysis 层（纯逻辑，**无 Qt**）

用户第 5 轮原话：「弄简单粗暴些一键批量导出，可选路径…导出一键所有 PDF，
或者导出一键所有 png，就别一个一个选了导出了」。

本模块**只做一件事**：把一批 (显示名, 源路径) 里**符合指定格式**的图**复制**到用户选的目录。

## 明确不做什么（都是有意为之）
  · **不改源、不删源、不做格式转换**：PNG 导出只搬 `.png`、PDF 只搬 `.pdf`；
    不做 PNG→PDF、不重编码、不缩放。源文件在本函数里**只被读**。
  · **不弹对话框、不碰控件**：目录由调用方（bind）用 `QFileDialog` 选好后传进来。
    （这也是本模块能不 import Qt 的原因。）
  · **不并发**：一次导出几十张图，串行复制已经足够快，
    而且串行才能保证"文件名冲突分配"是确定的（并发下同名分配会互相抢）。

## 三条硬要求（协调者 §12.2）
  1. 同名不覆盖：目标目录里**已存在**的文件、以及**本批已经占过**的名字，
     一律改用 `<名>_1.<后缀>`、`<名>_2.<后缀>`…（取最小可用序号，结果确定）；
  2. 单文件失败**不中断整批**：记进 `errors` 继续搬下一张；
  3. 一切异常都走返回值，**绝不抛**（沿用空转既有范式）。
"""

import os
import shutil

# 支持的格式（与契约 §12.2 的四个按钮一一对应）
SUPPORTED_FORMATS = ("png", "pdf")


def normalize_format(fmt):
    """把 'PNG' / '.pdf' 之类规整成 'png' / 'pdf'；不支持 → ''"""
    try:
        f = str(fmt or "").strip().lower().lstrip(".")
    except Exception:
        return ""
    if f == "jpg" or f == "jpeg":      # 明确不支持：不要"顺手"帮用户转换
        return ""
    return f if f in SUPPORTED_FORMATS else ""


def _check_dest(dest_dir):
    """校验目标目录：返回 (ok, 原因)

    ★ 可写性**用真的写一个探针文件**来判断，而不是 `os.access(W_OK)` ——
      后者在 Windows 上对目录基本不可靠（ACL 与只读属性它看不出来），
      会出现"检查说能写、复制时全失败"的假报告。
    """
    if not dest_dir or not isinstance(dest_dir, str):
        return False, "未选择导出目录"
    try:
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        return False, "导出目录不存在且无法创建: %s（%s）" % (dest_dir, e)
    if not os.path.isdir(dest_dir):
        return False, "导出目录不存在: %s" % dest_dir
    probe = os.path.join(dest_dir, ".spatial_export_write_test")
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
    except OSError as e:
        return False, "导出目录不可写: %s（%s）" % (dest_dir, e)
    return True, ""


def _unique_dest(dest_dir, filename, taken):
    """为 `filename` 找一个**不覆盖任何已有文件**的目标路径

    Args:
        taken: set，本批已经分配出去的目标路径（小写，Windows 不区分大小写）
    Returns:
        (目标路径, 是否有过改名)
    """
    base, ext = os.path.splitext(filename)
    if not base:
        base = "figure"
    cand = os.path.join(dest_dir, filename)
    renamed = False
    idx = 0
    while True:
        key = os.path.normcase(os.path.abspath(cand))
        if key not in taken and not os.path.exists(cand):
            taken.add(key)
            return cand, renamed
        idx += 1
        renamed = True
        cand = os.path.join(dest_dir, "%s_%d%s" % (base, idx, ext))


def batch_export(items, dest_dir, fmt):
    """把 `items` 里符合 `fmt` 的图**复制**到 `dest_dir`。

    Args:
        items: `[(显示名, 路径), ...]`；可混着 png 与 pdf，本函数按 `fmt` 过滤。
               显示名只用于错误/跳过信息，**不参与目标文件名**（目标名取源文件名）。
        dest_dir: 用户选的目录（不存在会尝试创建）
        fmt: 'png' / 'pdf'（大小写与前导点都容错）

    Returns:
        dict: {
          'ok': bool,                 # 整批是否成功启动并至少把"能搬的都处理了"
          'reason': str,              # ok=False 时的原因
          'dest': str,
          'fmt': str,
          'copied': int,              # 真正复制成功的张数
          'skipped': int,             # 格式不符 / 该项没有路径（含去重）
          'errors': [(名称, 原因), ...],       # **真失败**（复制出错、源读不了）
          'skipped_detail': [(名称, 原因), ...],  # 跳过明细（**留痕，不静默**）
          'renamed': [(原名, 新名), ...],      # 因同名而改名的（让用户知道多了 _1）
          'files': [复制后的路径, ...],
        }

    ★ **绝不抛异常**：任何失败都体现在返回值里。
    """
    result = {"ok": False, "reason": "", "dest": str(dest_dir or ""), "fmt": "",
              "copied": 0, "skipped": 0, "errors": [], "skipped_detail": [],
              "renamed": [], "files": []}
    f = normalize_format(fmt)
    result["fmt"] = f
    if not f:
        result["reason"] = "不支持的导出格式：%r（只支持 png / pdf）" % (fmt,)
        return result
    okd, why = _check_dest(dest_dir)
    if not okd:
        result["reason"] = why
        return result

    try:
        seq = list(items or [])
    except Exception as e:
        result["reason"] = "导出清单不可用：%s: %s" % (type(e).__name__, e)
        return result

    want_ext = "." + f
    taken = set()
    seen_src = {}          # 归一化后的源路径 → 已复制后的目标路径（去重）
    for entry in seq:
        try:
            name, src = "", ""
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                name, src = str(entry[0] or ""), str(entry[1] or "")
            else:
                name = str(entry)
            src = src.strip()
            if not src:
                # 该图型/该样本本来就没有这个格式的图 —— 跳过，但留痕
                result["skipped"] += 1
                result["skipped_detail"].append((name, "没有该格式的源文件路径"))
                continue
            if os.path.splitext(src)[1].lower() != want_ext:
                result["skipped"] += 1
                result["skipped_detail"].append(
                    (name, "格式不符（要 %s，实际 %s）" % (f, os.path.splitext(src)[1] or "无后缀")))
                continue
            skey = os.path.normcase(os.path.abspath(src))
            if skey in seen_src:
                # 同一个源文件出现两次 → 只搬一次（清单里天然会有重复来源）
                result["skipped"] += 1
                result["skipped_detail"].append((name, "与该批中另一项是同一个源文件（已去重）"))
                continue
            if not os.path.isfile(src):
                result["skipped"] += 1
                result["skipped_detail"].append((name, "源文件不存在: %s" % src))
                continue

            dst, renamed = _unique_dest(dest_dir, os.path.basename(src), taken)
            try:
                shutil.copy2(src, dst)      # copy2 = 复制内容 + 元数据；**不碰源文件**
            except Exception as e:
                # ★ 单文件失败不中断整批
                taken.discard(os.path.normcase(os.path.abspath(dst)))
                result["errors"].append((name, "%s: %s" % (type(e).__name__, e)))
                continue
            seen_src[skey] = dst
            result["copied"] += 1
            result["files"].append(dst)
            if renamed:
                result["renamed"].append((os.path.basename(src), os.path.basename(dst)))
        except Exception as e:
            # 单个清单项的意外异常也不许中断整批
            result["errors"].append((str(entry)[:60], "处理该项时异常：%s: %s"
                                     % (type(e).__name__, e)))
            continue

    # ok 的语义 = "目录可用 + 整批跑完（失败项已如实记录）"
    result["ok"] = True
    return result


def format_report(result):
    """把 `batch_export` 的返回值整理成**一行摘要 + 明细行**（供 bind 直接写日志）

    Returns: (summary: str, details: [str, ...])
    """
    try:
        r = result or {}
        if not r.get("ok"):
            return ("导出失败：%s" % (r.get("reason") or "未知原因")), []
        summary = ("已导出 %d 张 %s → %s（跳过 %d，失败 %d）"
                   % (r.get("copied", 0), str(r.get("fmt", "")).upper(),
                      r.get("dest", ""), r.get("skipped", 0), len(r.get("errors") or [])))
        details = []
        for nm, why in (r.get("errors") or []):
            details.append("  ✗ %s：%s" % (nm, why))
        for old, new in (r.get("renamed") or []):
            details.append("  ⚠ 同名已存在，改名为：%s" % new)
        return summary, details
    except Exception as e:
        return ("导出结果整理异常：%s: %s" % (type(e).__name__, e)), []
