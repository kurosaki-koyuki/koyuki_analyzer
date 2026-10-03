# -*- coding: utf-8 -*-
"""
空转基因表达按需出图 - analysis 层（纯逻辑，无 UI）
把「输入基因 / 基因集 → 出表达量图」交给一个**独立 Rscript 子进程**完成。

设计要点（契约 spatial_m2m3_contract.md §9）：
  · **走 subprocess + Rscript，不用 rpy2**（§9.1.1）——这样彻底绕开"M1 的 rpy2 只能主线程"
    的限制，因此本函数**可以被放到后台线程**里跑，界面不冻结；
  · **一次进程、一次 readRDS、循环画完所有基因**（R 侧实现）。对照单细胞 R 版的缺陷：
    它是"每基因一个子进程 + 每次 readRDS 整个数据集"（侦察 §7 坑 1），N 基因 = N 次全量重载；
  · 图落在 `<out_dir>/08_GeneOnDemand/<基因>/`，**绝不碰 `_figure_manifest.csv`**
    ⇒ `figure_set_id` 不变、用户已打的审查评分不受影响（§9.1.2/§9.1.3 硬要求）；
  · 失败一律 `(False, {}, 原因)`，**不抛异常**（沿用空转既有范式）。

两条硬安全措施（§9.4）：
  1. **非 ASCII 路径在 Python 侧就拒绝**（不只靠 R 侧断言）。依据：本会话实测"非 ASCII 路径会让 R 弹
     交互式目录菜单，在 rpy2 下变成无限循环 + 1.14 GB 失控日志"（spatial_rpy2_recipe.md §5）；
  2. 子进程一律 `stdin=DEVNULL` + `timeout`（默认 900 s，**不再照抄单细胞的 300**）。

关于进度（协调者要求说明选择）：
  本机子进程 stdout 是**全量缓冲**的，所以 `capture_output` 拿不到中途进度。
  我选择**另写进度文件**：R 侧逐基因把一行 JSON 追加到
  `<out_dir>/08_GeneOnDemand/_progress.jsonl`，调用方用 `read_progress()` 轮询即可。
  理由：不改 stdout 缓冲行为、不改 R 的输出契约，W2 侧实现进度条最省事。

导入风格说明：本模块**有意只用标准库**。它是"外部工具薄封装"，不需要 pandas/numpy；
刻意不 import `import_config` / `r_kernel_interface`，一是避免把 scanpy 等重依赖拖进后台线程，
二是 `r_kernel_interface` 会做 R 环境探测（启动期重活）。这是**有意偏离** analysis 层
"具名导入 import_config"的惯例，特此标明。
"""

import json
import os
import shutil
import subprocess
import tempfile

# 按需出图的固定子目录（契约 §9.1.2）
ON_DEMAND_SUBDIR = "08_GeneOnDemand"

# R 结果行的前缀（与 R 脚本严格一致）
RESULT_MARKER = "##SPATIAL_GENE_RESULT##"

# 基因数量上限（契约 §9.3）
MAX_GENES = 20

# 本机开发兜底（R_HOME 与 PATH 都拿不到时才用；R_HOME 由 start.py 在启动时写入）
_DEV_RSCRIPT_FALLBACK = r"A:\TOOLS\R\R-4.6.1\bin\x64\Rscript.exe"

_HERE = os.path.dirname(os.path.abspath(__file__))
# 迁移 2026-09-23：改为**每页一个文件夹**后，R 脚本与本模块**同目录**（传统层惯例，
# 如 bulk_cox_layer/bulk_cox_r.R）。这里仍走显式相对定位（不换 import_config 的
# get_r_script_path()）：两者在非 frozen 模式下等价，但显式写法在 frozen 下行为可预期、
# 且不改变既有 4 条不变量（R_HOME→PATH→兜底、全 ASCII、stdin=DEVNULL、绝不抛）。
# ⚠ 顺带修正旧注释：原注释说"R 在 spatial_r/、不同目录"，那个目录已不存在。
_R_SCRIPT_REL = "spatial_gene_expression.R"


def resolve_r_script():
    """定位 spatial_gene_expression.R（相对本文件；找不到返回 ''）"""
    p = os.path.normpath(os.path.join(_HERE, _R_SCRIPT_REL))
    return p if os.path.isfile(p) else ""


def find_rscript():
    """
    定位 Rscript 可执行文件。优先级：
      1) `R_HOME`（start.py:47 在启动时写入）下的 bin/x64 或 bin
      2) PATH 里的 Rscript
      3) 本机开发兜底路径
    返回可直接交给 subprocess 的字符串（找不到时返回 'Rscript'，让 OS 再试一次 PATH）。
    """
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


def is_ascii_path(p):
    """路径是否全为可打印 ASCII（§9.4 硬要求；非 ASCII 一律拒绝，不做兜底）"""
    if not isinstance(p, str) or not p:
        return False
    try:
        p.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def sanitize_genes(genes):
    """
    解析并清洗基因输入（契约 §9.3，补上单细胞缺的四样：切分/去空/去重保序/上限）。
    参数 genes 可以是 str（按换行、逗号、空白切分）或 list/tuple。
    返回 (clean: list[str], dropped: list[str], error: str)
      · dropped = 含非法字符（不能安全用作目录名）的项
      · error 非空表示整体不可用
    """
    if genes is None:
        return [], [], "基因输入为空"
    if isinstance(genes, str):
        raw = genes.replace(",", "\n").replace("\t", "\n").replace(" ", "\n").split("\n")
    elif isinstance(genes, (list, tuple, set)):
        raw = []
        for item in genes:
            if item is None:
                continue
            for piece in str(item).replace(",", "\n").split("\n"):
                raw.append(piece)
    else:
        return [], [], "基因输入类型不支持：%s" % type(genes).__name__

    clean, dropped, seen = [], [], set()
    for item in raw:
        g = (item or "").strip()
        if not g:
            continue
        if not _is_safe_gene(g):
            if g not in dropped:
                dropped.append(g)
            continue
        if g in seen:
            continue
        seen.add(g)
        clean.append(g)
    if not clean:
        return [], dropped, "没有解析出任何合法基因名"
    if len(clean) > MAX_GENES:
        return [], dropped, "基因数量 %d 超过上限 %d（契约 §9.3）" % (len(clean), MAX_GENES)
    return clean, dropped, ""


def _is_safe_gene(g):
    """基因名会被当作**目录名**使用，字符集必须收窄（与 R 侧同一规则）"""
    if not g or not g[0].isalnum():
        return False
    for ch in g:
        if not (ch.isalnum() or ch in "_.-"):
            return False
        if ord(ch) > 127:
            return False
    return True


def sanitize_samples(samples):
    """
    解析并校验**样本子集**输入（用户第二轮实测新增"只画选中的样本"）。
    参数 samples 可以是 None（= 全部样本）、str（按逗号/换行/空白切分）或 list/tuple。
    返回 (clean: list[str], error: str)。

    ⚠ 含非法字符的样本名**直接报错**（不静默丢弃）——因为丢弃一个用户明确选中的样本，
    正是这一轮要消灭的"静默偏离"行为。样本是否**在对象里真实存在**由 R 侧判定并如实报错。
    """
    if samples is None:
        return [], ""
    if isinstance(samples, str):
        raw = samples.replace(",", "\n").replace("\t", "\n").split("\n")
    elif isinstance(samples, (list, tuple, set)):
        raw = []
        for item in samples:
            if item is None:
                continue
            for piece in str(item).replace(",", "\n").split("\n"):
                raw.append(piece)
    else:
        return [], "samples 类型不支持：%s" % type(samples).__name__

    clean, seen, bad = [], set(), []
    for item in raw:
        s = (item or "").strip()
        if not s:
            continue
        if not _is_safe_gene(s):        # 与基因名同一套字符集规则
            bad.append(s)
            continue
        if s in seen:
            continue
        seen.add(s)
        clean.append(s)
    if bad:
        return [], "样本名含非法字符，已拒绝：%s" % ", ".join(bad)
    if not clean:
        return [], "samples 解析后为空"
    return clean, ""


def progress_path(out_dir):
    """进度文件路径（R 侧逐基因追加一行 JSON；调用方可轮询）"""
    if not out_dir:
        return ""
    return os.path.join(out_dir, ON_DEMAND_SUBDIR, "_progress.jsonl")


def read_progress(out_dir, run_id=None):
    """
    读进度文件，返回 [{i,n,gene,status,elapsed,run_id?}, ...]（**永不抛异常**）。
    传 run_id 时只返回该次运行的行（文件每次运行会被 R 侧重置，但并发时仍建议按 run_id 过滤）。
    """
    p = progress_path(out_dir)
    out = []
    if not p or not os.path.isfile(p):
        return out
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    if run_id is None or rec.get("run_id") == run_id:
                        out.append(rec)
    except OSError:
        return out
    return out


def _as_list(v):
    """把可能是标量的字段强制成 list（跨语言接口的稳定性措施）"""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _normalize_result(result):
    """
    归一化 R 侧 JSON 里"应该是数组"的字段。
    ⚠ 为什么两侧都要做：R 的 `jsonlite::toJSON(auto_unbox=TRUE)` 会把**长度为 1** 的向量
    脱成标量，于是 `files` 在 1 个文件时是字符串、2 个文件时是数组 —— 调用方必然踩。
    R 侧已用 `I()` 修好；这里再兜一层，防止以后有人漏加 `I()`。
    """
    if not isinstance(result, dict):
        return result
    for key in ("not_found", "available_genes", "dropped_unsafe_genes"):
        result[key] = _as_list(result.get(key))
    gc_ = result.get("gene_check")
    if isinstance(gc_, dict):
        for key in ("requested", "hit", "miss"):
            gc_[key] = _as_list(gc_.get(key))
    pg = result.get("per_gene")
    if isinstance(pg, dict):
        for _gene, rec in pg.items():
            if isinstance(rec, dict):
                rec["files"] = _as_list(rec.get("files"))
                # pdf_files 是用户第 5 轮新增的独立字段（一键导出全部 PDF 用）；
                # **files 的语义与顺序未变**（仍只含 PNG），PDF 绝不混进 files。
                rec["pdf_files"] = _as_list(rec.get("pdf_files"))
    gs = result.get("gene_set_score")
    if isinstance(gs, dict):
        gs["files"] = _as_list(gs.get("files"))
        gs["pdf_files"] = _as_list(gs.get("pdf_files"))
        gs["genes_used"] = _as_list(gs.get("genes_used"))
    return result


def _parse_result_line(stdout):
    """从子进程 stdout 里取**最后一条** ##SPATIAL_GENE_RESULT## JSON（找不到返回 None）"""
    if stdout is None:
        return None
    found = None
    for line in stdout.splitlines():
        idx = line.find(RESULT_MARKER)
        if idx < 0:
            continue
        payload = line[idx + len(RESULT_MARKER):].strip()
        if not payload:
            continue
        try:
            found = json.loads(payload)
        except ValueError:
            continue
    return found if isinstance(found, dict) else None


def run_gene_expression(rds_path, out_dir, dataset_id, genes, dpi=300, timeout=900, samples=None):
    """
    输入基因 / 基因集 → 出表达量图（**冻结签名 + samples 扩展**）。

    参数：
      rds_path   : 成品 .rds 绝对路径（必须全 ASCII）
      out_dir    : **数据集输出根**（= OUTPUT/<dataset_id>，必须全 ASCII）；
                   R 脚本在其下建 08_GeneOnDemand/<基因>/ 与 08_GeneOnDemand/_geneset/
      dataset_id : 数据集名（用于基因集评分图命名与结果标注）
      genes      : str（按换行/逗号/空白切分）或 list
      dpi        : 出图分辨率（50..1200）
      timeout    : 子进程超时秒数（默认 900；**不再照抄单细胞的 300**）
      samples    : **样本子集**（用户第二轮实测新增）。None = 全部样本；
                   str（逗号/换行切分）或 list。给不存在的样本名 → R 侧**如实报错**，
                   绝不静默退化成"画全部"。

    返回 (ok: bool, result: dict, error: str)：
      result 至少含 {"per_gene": {...}, "not_found": [...], "available_genes": [...]}，
      另含 samples_requested / samples_used / samples_missing / n_panels / figure_layout
      （调用方据此自证"真的只画了选中的样本"）。**任何失败都返回 (False, {}, 原因)，绝不抛异常。**
    """
    # ---------------- 参数校验（全部走返回值，不抛） ----------------
    if rds_path is None or not isinstance(rds_path, str) or not rds_path:
        return False, {}, "rds_path 为空"
    if out_dir is None or not isinstance(out_dir, str) or not out_dir:
        return False, {}, "out_dir 为空"
    if dataset_id is None or not isinstance(dataset_id, str) or not dataset_id:
        return False, {}, "dataset_id 为空"

    # ★ 先转绝对路径再断言/使用。
    #   理由：子进程的 cwd 被刻意设在 ASCII 的按需出图目录（见下），
    #   若此时仍传相对路径，R 侧会按那个 cwd 解析而找不到文件（本轮实测踩到：
    #   "rds not found: appdata/spatial_main/GSE237183.rds"）。
    #   相对路径按**调用方当前工作目录**解析；建议调用方直接传绝对路径。
    rds_path = os.path.abspath(rds_path)
    out_dir = os.path.abspath(out_dir)

    # ★ §9.4 硬要求：非 ASCII 路径在 Python 侧就拒绝（不是只靠 R 断言）
    if not is_ascii_path(out_dir):
        return False, {}, ("out_dir 含非 ASCII 字符，已拒绝：%s（非 ASCII 路径会使 R 弹出交互式目录菜单，"
                           "在 rpy2 下会变成无限循环）" % out_dir)
    if not is_ascii_path(rds_path):
        return False, {}, "rds_path 含非 ASCII 字符，已拒绝：%s" % rds_path
    if not is_ascii_path(dataset_id):
        return False, {}, "dataset_id 含非 ASCII 字符，已拒绝：%s" % dataset_id

    clean_genes, dropped_genes, gerr = sanitize_genes(genes)
    if gerr:
        return False, {}, gerr

    clean_samples, serr = sanitize_samples(samples)
    if serr:
        return False, {}, serr

    if not os.path.isfile(rds_path):
        return False, {}, "成品 .rds 不存在：%s" % rds_path

    r_script = resolve_r_script()
    if not r_script:
        return False, {}, "找不到 R 脚本 spatial_gene_expression.R（期望位置：%s）" % \
                          os.path.normpath(os.path.join(_HERE, _R_SCRIPT_REL))

    try:
        dpi_int = int(dpi)
    except (TypeError, ValueError):
        return False, {}, "dpi 不是整数：%r" % (dpi,)
    if dpi_int < 50 or dpi_int > 1200:
        return False, {}, "dpi 超出范围（50..1200）：%d" % dpi_int
    try:
        timeout_val = int(timeout)
    except (TypeError, ValueError):
        return False, {}, "timeout 不是整数：%r" % (timeout,)
    if timeout_val <= 0:
        return False, {}, "timeout 必须为正数：%d" % timeout_val

    # ---------------- 准备输出目录与基因清单文件 ----------------
    on_demand_root = os.path.join(out_dir, ON_DEMAND_SUBDIR)
    genes_file = ""
    try:
        os.makedirs(on_demand_root, exist_ok=True)
        if not os.path.isdir(on_demand_root):
            return False, {}, "无法创建按需出图目录：%s" % on_demand_root
        # 基因清单走**文件**（不靠 argv 传长列表，避免命令行长度与转义问题）
        fd, genes_file = tempfile.mkstemp(prefix="_genes_input_", suffix=".txt", dir=on_demand_root)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for g in clean_genes:
                f.write(g + "\n")
    except OSError as e:
        return False, {}, "准备输出目录/基因清单失败：%s" % e

    # ---------------- 调 R（subprocess，不用 rpy2） ----------------
    cmd = [find_rscript(), r_script, rds_path, out_dir, dataset_id, genes_file,
           "--dpi", str(dpi_int)]
    if clean_samples:
        cmd += ["--samples", ",".join(clean_samples)]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,      # ★ §9.4：绝不给 R 任何交互机会
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_val,
            cwd=on_demand_root,            # cwd 也放在已断言为 ASCII 的目录里
        )
    except subprocess.TimeoutExpired:
        _safe_unlink(genes_file)
        return False, {}, ("R 出图超时（>%ds）。基因数 %d，按实测约 9 s/基因 + 6 s 载入，"
                           "可提高 timeout 或减少基因数。" % (timeout_val, len(clean_genes)))
    except OSError as e:
        _safe_unlink(genes_file)
        return False, {}, "无法启动 R 子进程（%s）：%s" % (cmd[0], e)

    _safe_unlink(genes_file)

    stdout = _decode(proc.stdout)
    stderr = _decode(proc.stderr)
    result = _parse_result_line(stdout)

    if result is None:
        # 连机器可读结果都没有 ⇒ 硬失败（缺 R 包、路径被拒、脚本语法错等都会走到这里）
        reason = (stderr or stdout or "").strip()
        if len(reason) > 800:
            reason = reason[-800:]
        return False, {}, ("R 子进程未产出可解析结果（returncode=%s）：%s"
                           % (proc.returncode, reason or "无任何输出"))

    if not result.get("ok"):
        return False, {}, "R 报告失败：%s" % result.get("error", "未知原因")

    # 子进程退出码非 0 但结果 ok=true 属于异常组合，如实反映（不掩盖）
    if proc.returncode != 0:
        result["r_returncode"] = proc.returncode

    # 补两个 Python 侧的信息，方便调用方排障
    result = _normalize_result(result)
    result["r_script"] = r_script
    result["samples_arg"] = clean_samples      # Python 侧原样传入的样本（便于与 samples_used 对照）
    result["dropped_genes"] = dropped_genes
    if stderr:
        result["stderr_tail"] = stderr[-800:]

    return True, result, ""


def _decode(b):
    """子进程输出解码：本机 R 的 console 编码可能是 GBK，逐级退化，绝不因编码失败"""
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


def _safe_unlink(path):
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
