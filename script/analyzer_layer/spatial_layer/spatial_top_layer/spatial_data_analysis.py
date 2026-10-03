# -*- coding: utf-8 -*-
"""
空转分析数据管理脚本 - 负责数据集扫描、加载与状态管理
供所有空转分析子界面共享数据

M1 范围（见 docs/features/spatial_m1_contract.md §3 修订 v2）：
- 数据集身份 = *.manifest.json（不是 .rds 文件名）
- load_data() = 读 manifest JSON（秒开）+ 校验主对象（存在性/体积/mtime）
              + **通过 rpy2 把 .rds 真正读进 R 的 globalenv**

R 侧四条硬要求（契约 §3 v2）：
1. 对象名带命名空间：`koyuki_spatial_<dataset_id>` —— 同一 R 会话里 scRNAseq 的 rds 通道
   也在用 globalenv（scRNAseq_data_analysis.py:151-152），**绝不能用** sce/sce.all/obj 这类通用名；
2. 读新对象前**先释放上一个**（rm + gc），否则连读两个 = 4.8 GB；
3. clear_data() 必须真的释放 R 对象（rm + gc），不能只清 Python 字段；
4. 一律优雅降级、不抛异常：R 不可用 / readRDS 失败 / 内存不足 →
   **manifest / samples / data_info 照常填好**（样本清单仍可显示），只是明确标注"数据未进内存"。

R 通道的既有范式（r_kernel_interface.py）：失败返回 None + _error_message 而不抛
 → **判空一律用 `is None`，不要用 `not result`**（空串是"成功但无输出"）。
"""

import time
import datetime
import contextlib

from script.utils_layer.import_config import *
# ★ SPATIAL_SCAN_DATA_PATH 目前【不在】import_config.py 的 __all__（实测 :315-336 只有
#   SCAN_DATA_PATH / BULK_SCAN_DATA_PATH / DPI），`import *` 取不到 → 必须具名导入。
#   协调者已在 import_config.py:47 定义该常量（实测存在）。
from script.utils_layer.import_config import SPATIAL_SCAN_DATA_PATH


# W3 清单模块的【冻结】导入路径（契约 §3 指定）
_MANIFEST_MODULE = "script.analyzer_layer.spatial_layer.spatial_top_layer.spatial_manifest"
_MANIFEST_SUFFIX = ".manifest.json"
_ARTIFACT_SUFFIX = ".rds"

# 放进 R globalenv 的对象名前缀（命名空间，防与 scRNAseq 通道撞名）
R_OBJECT_PREFIX = "koyuki_spatial_"

# R 小工具（模板里 %s 是对象名）
_R_HAS_OBJECT_TPL = 'exists("%s", envir = globalenv(), inherits = FALSE)'
_R_RELEASE_TPL = ('if (exists("%s", envir = globalenv(), inherits = FALSE)) '
                  'rm(list = "%s", envir = globalenv()); invisible(gc())')
_R_READ_TPL = '%s <- readRDS(%s)'
_R_SIZE_TPL = 'format(object.size(%s), units = "MB")'

# 致命 issue 的判据前缀（W3 的 validate_manifest 返回【问题清单】而不是布尔，
# 所以必须由调用方分档：结构性/磁盘性缺失 → 阻断；一致性/脏名提示 → 只警告）
_FATAL_ISSUE_PREFIXES = (
    "manifest.schema", "manifest.dataset_id",
    "artifact.path", "artifact.bytes", "artifact.kind",
    "artifact:", "source.", "summary.", "rebuild.",
    "samples:", "samples[",
)
# 宽松 issue（不阻断加载，仅提示）
# ⚠ artifact.mtime 刻意放这里：mtime 是**弱信号**（拷贝/恢复/touch 都会变），
#    单独不一致不足以判定"清单描述的是另一个文件"；真正决定性的是 artifact.bytes。
_SOFT_ISSUE_PREFIXES = (
    "dataset_id: 命中已知脏名片段",
    "pipeline[",
    "artifact.mtime",
)


def _split_issues(issues):
    """把 W3 的问题清单分成 (致命, 宽松) 两组。永远返回两个 list，不抛异常。"""
    fatal, soft = [], []
    try:
        for item in (issues or []):
            text = str(item)
            if any(text.startswith(p) for p in _SOFT_ISSUE_PREFIXES):
                soft.append(text)
            elif any(text.startswith(p) for p in _FATAL_ISSUE_PREFIXES):
                fatal.append(text)
            else:
                # 未知形态的问题：保守起见只当提示，不阻断
                # （避免"新版本 W3 加了检查项就把加载全堵死"）
                soft.append(text)
    except Exception:
        traceback.print_exc()
    return fatal, soft


@contextlib.contextmanager
def r_conversion_context():
    """在**当前线程**里激活 rpy2 的转换上下文（把 R 调用放进 QThread 时**必须**）

    ★ 为什么需要（本轮实测的根因，不是环境玄学）：
       rpy2 的转换规则存放在 **Python `contextvars.ContextVar`** 里
       （`rpy2.robjects.conversion.converter_ctx`）。`QThread` 起的线程**不会继承**
       主线程的 context → 在后台线程里直接调 `readRDS` 会报
       「Conversion rules for `rpy2.robjects` appear to be missing ...
         This could be caused by multithreading code not passing context to the thread」
       （本环境实测还会进一步表现为**原生访问违例 exit 0xC0000005**，无 Python traceback）。
       实测修法：在**该线程内**用 `localconverter(default_converter)` 包住所有 R 调用 → 正常返回
       （实测 `2433.3 Mb | dims=(39566, 22426)`，exit=0）。

    本上下文管理器是**可选加固**：拿不到 rpy2 转换 API 时退化为无操作（只放弃加固，不阻断流程）。
    """
    cm = None
    try:
        from rpy2.robjects import default_converter
        from rpy2.robjects.conversion import localconverter
        cm = localconverter(default_converter)
        cm.__enter__()
    except Exception:
        # 拿不到转换 API：退化为无操作（不抛，不影响主流程）
        traceback.print_exc()
        cm = None
    try:
        yield
    finally:
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                traceback.print_exc()


def _sanitize_r_name(dataset_id):
    """把 dataset_id 洗成合法的 R 符号后缀（只留字母/数字/下划线）

    R 的变量名不允许 '-' '.' 等字符，而 manifest 的 dataset_id 是自由字符串
    （台账里就有 `GSE15209_CPM（GSC, NSC）` 这种）。洗不干净就追加短哈希保证唯一，
    绝不产出非法符号，也绝不让两个不同 dataset_id 洗成同一个名字。
    """
    try:
        raw = str(dataset_id or "")
        cleaned = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in raw)
        cleaned = cleaned.strip("_") or "dataset"
        if not (cleaned[0].isalpha() or cleaned[0] == "_"):
            cleaned = "d_" + cleaned
        if cleaned != raw:
            # 发生过替换/前缀补丁 → 追加短哈希，保证唯一与可追溯
            try:
                import hashlib
                cleaned = "%s_%s" % (cleaned, hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8])
            except Exception:
                pass
        return cleaned
    except Exception:
        traceback.print_exc()
        return "dataset"


class SpatialDataManager:
    """空转（spatial）数据管理类 - 供所有空转分析子界面共享数据

    与 BulkDataManager 保持同名字段，保证将来接入 page_intersect 的 sync_method 零改动。
    """

    def __init__(self):
        # —— 照抄 bulk_data_analysis.py:13-20 的同名字段（逐字一致，勿改名）——
        # ⚠ adata：M1 的主对象是 Seurat .rds（对象本体留在 R 里），这里保持 None；
        #    真正的数据在 R 的 globalenv，Python 侧只记对象名与内存信息。
        self.adata = None
        self.current_gene = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.valid_groups = []
        self.current_data_folder = None
        self.data_info = {}

        # —— 空转新增（M1）——
        self.manifest = {}          # 完整 manifest 字典（内存里的唯一真源，不含 _issues）
        self.manifest_issues = []   # W3 给出的【宽松】问题清单（不阻断加载，仅提示/日志）
        self.samples = []           # manifest['samples'] 的引用（逐样本清单）
        self.artifact_info = {}     # 主对象校验结果 {ok, path, bytes, mtime, ...}
        self.dataset_id = None      # manifest['dataset_id']（稳定键）
        self.display_name = None    # manifest['display_name']（给人看的）

        # —— M1 v2：真读进内存（R globalenv）的状态 ——
        self.data_in_memory = False  # ★ 数据是否真的已在 R globalenv 里
        self.memory_info = {}        # ★ {object_name, bytes, seconds, size_text, n_spots, ...}
        self.r_object_name = None    # ★ 当前数据集在 R 里的对象名（带命名空间）
        self.r_read_error = ""       # ★ 上一次 R 读取失败的原因（供 UI 如实展示）
        self.r_ready_on_caller_thread = False  # ★ 主线程是否已把 R 初始化就绪（后台 worker 的硬前提）

    # ==================================================================
    # 扫描
    # ==================================================================
    def scan_data_folder(self, path=None):
        """扫描数据目录，返回数据集名列表（排序）

        契约 §3：只 os.listdir 一层 + 白名单 endswith('.manifest.json')
                 + 同 stem 的 .rds 存在性检查。
        不做：不递归、不打开 .rds、不算哈希、不按体积去重。

        Args:
            path: 扫描目录；为 None 时用 SPATIAL_SCAN_DATA_PATH

        Returns:
            list[str]: 通过校验的数据集名（= manifest 文件名去掉 .manifest.json）
        """
        folder_path = path or SPATIAL_SCAN_DATA_PATH
        names = []
        try:
            if not folder_path or not os.path.exists(folder_path):
                # 目录不存在属正常状态（首次使用），静默返回空列表
                return names

            if not os.path.isdir(folder_path):
                return names

            try:
                entries = os.listdir(folder_path)
            except Exception:
                traceback.print_exc()
                return names

            # 只扫一层，只认 manifest 白名单；同 stem 的 .rds 必须存在
            for entry in sorted(entries):
                if not entry.endswith(_MANIFEST_SUFFIX):
                    continue
                stem = entry[:-len(_MANIFEST_SUFFIX)]
                if not stem:
                    continue
                manifest_path = os.path.join(folder_path, entry)
                if not os.path.isfile(manifest_path):
                    continue
                artifact_path = os.path.join(folder_path, stem + _ARTIFACT_SUFFIX)
                if not os.path.isfile(artifact_path):
                    # 只有 manifest 没有主对象 → 不列入下拉框（避免"能选但加载必失败"）
                    continue
                names.append(stem)

            self.current_data_folder = folder_path
            return names
        except Exception:
            traceback.print_exc()
            return names

    # ==================================================================
    # 加载（两段式：prepare 只读清单，read_into_r 真读数据）
    # ==================================================================
    def prepare_dataset(self, dataset_name):
        """第一段：找清单 + 读清单 + 结构校验 + 磁盘校验（**不读数据，秒开**）

        与 read_into_r() 拆开，是为了让 UI 能把"秒开的部分"和"约 5 秒的读数据"分开反馈，
        也便于把慢操作放到后台线程。

        Returns:
            tuple: (manifest_or_None, error_msg)
        """
        try:
            if not dataset_name:
                return None, "请选择要加载的数据集"

            folder_path = self.current_data_folder or SPATIAL_SCAN_DATA_PATH
            manifest_path = os.path.join(folder_path, dataset_name + _MANIFEST_SUFFIX)

            if not os.path.exists(manifest_path):
                return None, f"清单文件不存在: {manifest_path}"

            # ① 取 W3 的清单模块（方法内 import；缺失即降级，不抛）
            try:
                manifest_module = importlib.import_module(_MANIFEST_MODULE)
            except Exception as e:
                return None, (f"清单模块不可用（{_MANIFEST_MODULE}）：{e}。"
                              f"请确认 W3 的 spatial_manifest.py 已就位")

            read_manifest = getattr(manifest_module, "read_manifest", None)
            validate_manifest = getattr(manifest_module, "validate_manifest", None)
            if read_manifest is None or validate_manifest is None:
                return None, ("清单模块缺少 read_manifest / validate_manifest，"
                              "无法读取清单（接口以契约为准）")
            check_artifact = getattr(manifest_module, "check_artifact", None)
            resolve_artifact_path = getattr(manifest_module, "resolve_artifact_path", None)

            # ② 读清单
            #    W3 的 read_manifest 已把 validate_manifest 的结果注入 manifest['_issues']；
            #    硬失败（不存在/非法 JSON/顶层非对象）会抛 ManifestError —— 一律降级不抛。
            try:
                manifest = read_manifest(manifest_path)
            except Exception as e:
                traceback.print_exc()
                return None, f"读取清单失败: {e}"

            if not isinstance(manifest, dict) or not manifest:
                return None, "清单内容为空或格式不正确"

            # ③ 结构校验：W3 返回【问题清单】而不是布尔 → 由本层分档
            structural_issues = self._safe_validate(validate_manifest, manifest)
            fatal, soft = _split_issues(structural_issues)

            # ④ 磁盘侧校验（存在性 / 体积 / mtime）—— 用 W3 的 check_artifact（契约 §3 要求）
            disk_issues = []
            if check_artifact is not None:
                try:
                    disk_issues = list(check_artifact(manifest, BASE_DIR) or [])
                except Exception:
                    traceback.print_exc()
                    disk_issues = ["artifact: 磁盘校验异常"]
            fatal_disk, soft_disk = _split_issues(disk_issues)
            fatal.extend(fatal_disk)
            soft.extend(soft_disk)

            # ⑤ 数据集身份核对：契约 §1「身份 = manifest」，故与文件名不一致时报警
            man_id = manifest.get("dataset_id")
            if isinstance(man_id, str) and man_id and man_id != dataset_name:
                soft.append(f"清单 dataset_id({man_id}) 与文件名({dataset_name}) 不一致，以清单为准")

            # ⑥ 致命问题 → 阻断，且把前 3 条原因拼进返回文案（便于 UI 区分）
            if fatal:
                return None, "清单校验未通过: " + "；".join(fatal[:3])

            # ⑦ 落地内存状态（先清，避免上一次的残留）
            self.clear_data()
            self.current_data_folder = folder_path
            # _issues 是 W3 注入的保留键，不留在 manifest 里（避免误回写污染文件）
            issues_in_manifest = manifest.pop("_issues", None)
            self.manifest = manifest
            self.manifest_issues = list(soft) + list(issues_in_manifest or [])
            self.dataset_name = dataset_name
            self.dataset_id = man_id or dataset_name
            self.display_name = manifest.get("display_name") or dataset_name
            self.samples = manifest.get("samples") or []
            self.dataset_output_dir = os.path.join(OUT_BASE, dataset_name)
            self.data_info = self._build_data_info(manifest, self.samples)
            self.artifact_info = self._build_artifact_info(
                folder_path, dataset_name, manifest,
                resolve_artifact_path=resolve_artifact_path,
                check_artifact=check_artifact)

            # 预置 R 对象名（带命名空间），供 read_into_r / release 使用
            self.r_object_name = R_OBJECT_PREFIX + _sanitize_r_name(self.dataset_id)
            self.data_in_memory = False
            self.memory_info = {}
            self.r_read_error = ""

            # ★★ 关键：在【调用方所在线程（=主线程）】上先把 R 环境初始化好。
            #    实测教训：若首次 R 初始化发生在 QThread 工作线程里，
            #    rpy2 会在 "R环境未初始化，开始初始化..." 处**原生崩溃**
            #    （exit 1 / 0xC0000005，无 Python traceback），
            #    且 Python 侧 try/except 抓不到 → 界面按钮会永久卡在禁用态。
            #    这里提前探一次（成本极低：已初始化时是 no-op），把初始化固定在主线程完成。
            self._ensure_r_ready_on_caller_thread()
            return manifest, ""
        except Exception as e:
            traceback.print_exc()
            return None, f"读取数据集清单失败: {e}"

    def load_data(self, dataset_name):
        """加载数据集 = 读清单 + 校验主对象 + **真读 .rds 进 R globalenv**

        契约 §3 v2：本方法是**同步版本**（会给调用方阻塞约 5 秒）。**带界面的调用方
        应用 prepare_dataset() + read_into_r() 两段式**（可把慢操作放后台线程），
        本方法保留给无界面/脚本场景与向后兼容。

        Returns:
            tuple: (success, manifest_dict, error_msg)
                   - success=True  → 数据已进 R globalenv（data_in_memory=True）
                   - success=False → **manifest / samples / data_info 仍已填好**，
                                     仅"数据未进内存"，error_msg 说明原因
        """
        manifest, error = self.prepare_dataset(dataset_name)
        if manifest is None:
            return False, {}, error
        ok, read_err = self.read_into_r()
        if not ok:
            return False, manifest, read_err
        return True, manifest, ""

    # ------------------------------------------------------------------
    # 真读进 R（慢操作：实测 475 MB / ≈4.6–5.4 秒 / ≈2.4 GB 内存）
    # ------------------------------------------------------------------
    def _ensure_r_ready_on_caller_thread(self):
        """在**调用方线程**上把 R 环境初始化好（幂等、极低开销、永不抛）

        ★ 为什么必须做（判决性实验结论）：把 `read_into_r()` 放进 QThread 时，
          **worker 里绝不能是"首次"触发 R 初始化**。因为
          `RKernelInterface._initialize_rpy2()` 在未初始化时会调用
          `rpy2.rinterface.initr()`，而 **R 只允许在初始化它的那个线程里使用** ——
          这步一旦落在工作线程上就是**原生访问违例（exit 0xC0000005，无 Python traceback）**，
          Python 侧 try/except 抓不到，按钮会永久卡在禁用态。

        ⚠ 本方法**故意不短路**：不做"先判 `is_r_available()` 就返回"，而是**无条件**走一遍
          `get_r_kernel_interface()` → `is_r_available()` → `get_robjects()`。
          实测依据（判决性实验 vs 中间探针）：
            · 主线程只调 `is_r_available()` 就起 worker → worker 里**仍**出现
              `R环境未初始化，开始初始化...` 并原生崩溃；
              （原因：`is_r_available()` 只读 `_is_initialized` 标志位，不足以完成初始化）
            · 主线程**多走一步 `get_robjects()`** → worker 路线 **5/5 exit=0、5.60–5.65 秒、
              均成功入内存 2433.3 Mb**（复现：`python -u debug_output/_w2_verdict_worker.py <i>`）
          成本可忽略（R 已就绪时近似 no-op），因此宁可不省这一下。

        本方法**不读任何数据**，因此仍是"秒开"；失败也不影响清单加载（只影响后续真读）。
        结果同时写入 `self.r_ready_on_caller_thread`，供界面层决定"走后台 worker 还是降级同步"。

        Returns:
            bool: 主线程是否已把 R 就绪
        """
        ready = False
        try:
            from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            r = get_r_kernel_interface()
            try:
                available = bool(r.is_r_available())
            except Exception:
                traceback.print_exc()
                available = False
            # ★ 关键的一步：无论 available 与否都取一次句柄（这一步才真正把 R 初始化钉在主线程）
            robjects = None
            try:
                robjects = r.get_robjects()
            except Exception:
                traceback.print_exc()
            ready = bool(available and robjects is not None)
        except Exception:
            # 初始化失败属可降级情形：清单照常可用，真读时再如实报错
            traceback.print_exc()
            ready = False
        self.r_ready_on_caller_thread = ready
        return ready

    def read_into_r(self):
        """把当前数据集的 .rds 读进 R 的 globalenv

        前置：prepare_dataset() 已成功（r_object_name / artifact_info 已就位）。
        **本方法不抛异常**；失败时 data_in_memory 保持 False，原因写入 r_read_error。

        进入前会**先把上一个对象挪走并置空句柄**（契约硬要求 2）——
        不释放就会连读两个对象 = 4.8 GB。

        ⚠ 为什么"挪走"而不是"就地 rm+gc"：本方法常被 QThread 调用，而 `gc()` 在大对象上
          可能耗时可观；更关键的是**在事件回调/槽函数里同步释放 Qt 侧正持有的句柄**容易踩坑。
          因此约定：**read 只负责把旧对象"退役"（改名 + 清空 self.r_object_name），
          真正的 rm+gc 交给调用方用 QTimer.singleShot(0, ...) 在下一轮事件循环里执行**
          （UI 侧由 `SpatialTopBind._release_stale_object()` 完成）。
          若调用方没接这一手，旧对象会以 `<name>__stale_<ts>` 留在 globalenv 直到 clear_data。
        """
        try:
            if not self.dataset_name:
                return False, "请先读取数据集清单"
            if not self.artifact_info.get("ok"):
                self.r_read_error = f"主对象校验未通过: {self.artifact_info.get('reason', '未知原因')}"
                return False, self.r_read_error

            artifact_path = self.artifact_info.get("path") or ""
            if not artifact_path or not os.path.isfile(artifact_path):
                self.r_read_error = f"主对象不存在: {artifact_path}"
                return False, self.r_read_error

            if not self.r_object_name:
                self.r_object_name = R_OBJECT_PREFIX + _sanitize_r_name(self.dataset_id)
            obj_name = self.r_object_name

            # ① 先把上一个退役（契约硬要求 2）：改名 → 清句柄 → 交给调用方延时 rm+gc
            #    ⚠ _retire 会把 self.r_object_name 清空（那是"上一个"的句柄），
            #      所以**必须**把本次要用的名字重新写回，否则第一次读就会把句柄丢掉
            #      （实测踩过：read 成功、data_in_memory=True，但 self.r_object_name 变成 None，
            #        导致后续 exists/rm 全在操作字符串 "None"）。顺序不能颠倒。
            self._retire_previous_r_object()
            self.r_object_name = obj_name

            # ② 取 R 通道（方法内 import —— 绝不在模块顶层或 create_page 里初始化 R）
            try:
                from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            except Exception as e:
                self.r_read_error = f"R 通道模块不可用: {e}"
                return False, self.r_read_error

            r = get_r_kernel_interface()

            # ③ 先判可用性再动（契约 §3 ③）
            try:
                available = bool(r.is_r_available())
            except Exception:
                traceback.print_exc()
                available = False
            if not available:
                self.r_read_error = "R 环境不可用（请检查 R 内核配置）"
                return False, self.r_read_error

            robjects = None
            try:
                robjects = r.get_robjects()
            except Exception:
                traceback.print_exc()
            # ⚠ 既有范式：失败返回 None 而不抛 → 判空必须用 `is None`（不能用 not）
            if robjects is None:
                self.r_read_error = getattr(r, "_error_message", "") or "R 环境不可用"
                return False, self.r_read_error

            # ④ readRDS —— 唯一的重活
            #    ⚠ 必须整段包在 r_conversion_context() 里：
            #      本方法会被 QThread 调用，而 rpy2 的转换规则在 contextvars 里、不跨线程继承。
            started = time.time()
            with r_conversion_context():
                try:
                    robjects.globalenv["koyuki_spatial_read_path"] = robjects.StrVector([artifact_path])
                    robjects.r(_R_READ_TPL % (obj_name, "koyuki_spatial_read_path"))
                except Exception as e:
                    traceback.print_exc()
                    self._safe_release(obj_name)
                    self.r_read_error = f"readRDS 失败: {e}"
                    return False, self.r_read_error
                finally:
                    # 清掉临时路径变量（不留垃圾在 globalenv）
                    try:
                        robjects.r('if (exists("koyuki_spatial_read_path", envir = globalenv(), '
                                   'inherits = FALSE)) rm(list = "koyuki_spatial_read_path", '
                                   'envir = globalenv())')
                    except Exception:
                        pass

                elapsed = time.time() - started

                # ⑤ 读回真实标量（探测失败只影响展示，不影响"已进内存"的事实）
                size_text, size_bytes, n_spots, n_genes = self._probe_r_object(robjects, obj_name)

            self.memory_info = {
                "object_name": obj_name,
                "path": artifact_path,
                "bytes": size_bytes,          # R 侧 object.size 的字节数
                "size_text": size_text,       # 如 "2433.3 Mb"（R 的 units="MB" 是 1e6）
                "seconds": round(elapsed, 2),
                "n_spots": n_spots,
                "n_genes": n_genes,
                "file_bytes": self.artifact_info.get("bytes"),
            }
            self.data_in_memory = True
            self.r_read_error = ""
            return True, ""
        except Exception as e:
            traceback.print_exc()
            self.r_read_error = f"读取数据集进内存失败: {e}"
            self.data_in_memory = False
            return False, self.r_read_error

    def _probe_r_object(self, robjects, obj_name):
        """探测 R 对象的体积与维度（失败只返回空值，不抛、不影响加载结论）

        Returns:
            tuple: (size_text, size_bytes, n_spots, n_genes)
        """
        size_text, size_bytes, n_spots, n_genes = "", None, None, None
        try:
            result = robjects.r(_R_SIZE_TPL % obj_name)
            # ⚠ 既有范式：用 is None 判失败（空串是"成功但无输出"）
            if result is not None and len(result) > 0:
                size_text = str(result[0])
        except Exception:
            traceback.print_exc()
        # 把 "2433.3 Mb" 解析成字节（R 的 units="MB" = 1e6，不是 MiB）
        try:
            if size_text:
                size_bytes = int(float(size_text.split()[0]) * 1e6)
        except Exception:
            size_bytes = None
        try:
            v = robjects.r('ncol(%s)' % obj_name)
            if v is not None and len(v) > 0:
                n_spots = int(v[0])
        except Exception:
            pass
        try:
            v = robjects.r('nrow(%s)' % obj_name)
            if v is not None and len(v) > 0:
                n_genes = int(v[0])
        except Exception:
            pass
        return size_text, size_bytes, n_spots, n_genes

    # ------------------------------------------------------------------
    # R 对象释放
    # ------------------------------------------------------------------
    def _retire_previous_r_object(self):
        """把上一个 R 对象"退役"：改名成 `<name>__stale_<ts>`，并清空当前句柄

        **不在这里 rm+gc** —— 交给调用方延时执行（见 read_into_r 的 docstring）。

        ⚠ 本方法会清空 `self.r_object_name`。调用方（read_into_r）**必须随后写回本次的名字**。

        Returns:
            str: 退役后的对象名（没有旧对象则返回 ""）
        """
        try:
            old = self.r_object_name
            self.r_object_name = None
            self.data_in_memory = False
            if not old or old == "None":
                # 没有旧对象（或句柄已失效）：什么都不用做
                return ""
            try:
                from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            except Exception:
                return ""
            r = get_r_kernel_interface()
            try:
                if not r.is_r_available():
                    return ""
            except Exception:
                return ""
            robjects = r.get_robjects()
            if robjects is None:
                return ""
            stale = old + "__stale_" + str(int(time.time()))
            with r_conversion_context():
                # 只有存在时才改名（避免报错）
                robjects.r('if (exists("%s", envir = globalenv(), inherits = FALSE)) '
                           'assign("%s", get("%s", envir = globalenv()), envir = globalenv())'
                           % (old, stale, old))
                robjects.r('if (exists("%s", envir = globalenv(), inherits = FALSE)) '
                           'rm(list = "%s", envir = globalenv())' % (stale, old))
            return stale
        except Exception:
            traceback.print_exc()
            return ""

    def release_r_object(self):
        """释放当前数据集在 R globalenv 里的对象（rm + gc）

        Returns:
            bool: 是否确实执行了释放（对象本来就不存在也算成功）
        """
        try:
            return self._safe_release(self.r_object_name)
        except Exception:
            traceback.print_exc()
            return False

    def release_stale_objects(self):
        """清掉所有 `koyuki_spatial_*__stale_*` 残留对象（rm + gc）

        由 UI 侧在下一轮事件循环里调用（`QTimer.singleShot(0, ...)`），
        保证"读新对象前旧对象已退役、且很快被真正释放"，从而**不累积成两倍内存**。

        Returns:
            int: 清掉的对象个数（失败返回 0）
        """
        count = 0
        try:
            from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            r = get_r_kernel_interface()
            if not r.is_r_available():
                return 0
            robjects = r.get_robjects()
            if robjects is None:
                return 0
            with r_conversion_context():
                names_r = robjects.r('ls(envir = globalenv(), pattern = "^koyuki_spatial_.*__stale_")')
                stale_names = [str(x) for x in names_r] if names_r is not None else []
                for nm in stale_names:
                    try:
                        robjects.r('rm(list = "%s", envir = globalenv())' % nm)
                        count += 1
                    except Exception:
                        traceback.print_exc()
                if count:
                    robjects.r("invisible(gc())")
            return count
        except Exception:
            traceback.print_exc()
            return count

    def _safe_release(self, obj_name):
        """按对象名释放（内部用；永不抛）"""
        try:
            if not obj_name:
                return True
            try:
                from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            except Exception:
                return False
            r = get_r_kernel_interface()
            try:
                if not r.is_r_available():
                    return False
            except Exception:
                return False
            robjects = r.get_robjects()
            if robjects is None:
                return False
            # 同样需要转换上下文（本方法也可能在 QThread 里被调用）
            with r_conversion_context():
                robjects.r(_R_RELEASE_TPL % (obj_name, obj_name))
            self.data_in_memory = False
            return True
        except Exception:
            traceback.print_exc()
            return False

    def r_object_exists(self, obj_name=None):
        """查询对象是否存在于 R globalenv（供测试/诊断用；失败返回 False，不抛）"""
        try:
            name = obj_name or self.r_object_name
            if not name:
                return False
            from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            r = get_r_kernel_interface()
            if not r.is_r_available():
                return False
            robjects = r.get_robjects()
            if robjects is None:
                return False
            with r_conversion_context():
                res = robjects.r(_R_HAS_OBJECT_TPL % name)
            return bool(res[0]) if res is not None and len(res) > 0 else False
        except Exception:
            traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    # 清空 / 查询
    # ------------------------------------------------------------------
    def clear_data(self):
        """清空数据：**Python 字段 + R globalenv 对象都要清**（契约硬要求 3）

        R 对象释放失败不影响 Python 侧清空（清理绝不能成为故障源）。
        """
        try:
            if self.r_object_name:
                self._safe_release(self.r_object_name)
            # 顺手清掉可能残留的退役对象（读新对象前旧对象会先改名为 __stale_*）
            self.release_stale_objects()
        except Exception:
            traceback.print_exc()

        self.adata = None
        self.current_gene = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.valid_groups = []
        self.data_info = {}
        self.manifest = {}
        self.manifest_issues = []
        self.samples = []
        self.artifact_info = {}
        self.dataset_id = None
        self.display_name = None
        self.data_in_memory = False
        self.memory_info = {}
        self.r_object_name = None
        self.r_read_error = ""
        self.r_ready_on_caller_thread = False

    def is_data_loaded(self):
        """检查数据是否已加载

        ★ M1 v2 语义选择（采纳协调者倾向）：**以「清单已加载」为准返回 True**。
        理由：
          1) UI 的样本清单（spatial_sample_list）依赖本方法决定是否展示，而样本清单
             只需要 manifest —— 若要求"数据在内存"才算 loaded，则 R 不可用/读失败时
             **用户连样本清单都看不到**，界面直接变砖；
          2) "数据是否真的进了 R 内存"是**另一个正交维度**，由 `data_in_memory` 单独表达。
             调用方（尤其将来要真算数据的 M2）**必须显式读 data_in_memory**，
             不能只看 is_data_loaded；
          3) 这与 load_data() 失败时仍返回非空 manifest 是同一设计意图：
             **让 UI 可用，同时如实告知"数据未进内存"**。

        ⚠ 与 bulk 的 `return self.adata is not None`（bulk_data_analysis.py:95-97）**有意不同**：
           M1 的主对象是 Seurat .rds（对象本体留在 R 里），Python 侧 adata 恒为 None。
        """
        try:
            return bool(self.dataset_name) and bool(self.manifest)
        except Exception:
            return False

    def is_data_in_memory(self):
        """数据是否真的已在 R globalenv（供 UI 与 M2 显式判断）"""
        try:
            return bool(self.data_in_memory)
        except Exception:
            return False

    def get_data_info(self):
        """获取当前数据信息（供 UI 显示）"""
        try:
            return self.data_info or {}
        except Exception:
            return {}

    def get_sample_list(self):
        """返回 manifest 的 samples[]（逐样本清单，供 UI 只读展示）"""
        try:
            return self.samples or []
        except Exception:
            return []

    def get_memory_text(self):
        """返回一句可显示的内存描述（未进内存则返回空串）

        注意：R 的 `units="MB"` 是 1e6 字节（不是 MiB），故按 1 GB = 1e9 换算给用户看。
        """
        try:
            if not self.data_in_memory:
                return ""
            info = self.memory_info or {}
            size_text = info.get("size_text") or ""
            seconds = info.get("seconds")
            bytes_ = info.get("bytes")
            if bytes_ and seconds is not None:
                return f"已读入内存（{float(bytes_) / 1e9:.1f} GB，用时 {seconds} 秒）"
            if size_text and seconds is not None:
                return f"已读入内存（{size_text}，用时 {seconds} 秒）"
            return "已读入内存"
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # 内部：派生字段（纯数据组装，不读盘）
    # ------------------------------------------------------------------
    def _safe_validate(self, validate_manifest, manifest):
        """调用 W3 的 validate_manifest 并把返回值归一成 list[str]（永不抛）"""
        try:
            result = validate_manifest(manifest)
        except Exception:
            traceback.print_exc()
            return ["清单结构校验异常"]
        if result is None:
            return []
        if isinstance(result, (list, tuple)):
            return [str(x) for x in result]
        # 兼容"返回布尔"的其它实现：False → 未知问题；True → 通过
        return [] if result else ["清单结构校验未通过（未给出原因）"]

    def _build_data_info(self, manifest, samples):
        """从 manifest 组装 data_info（键名尽量与 bulk 对齐 + 空转新增）"""
        summary = manifest.get("summary") or {}
        if not isinstance(summary, dict):
            summary = {}
        n_samples = summary.get("n_samples")
        if not isinstance(n_samples, int):
            n_samples = len(samples) if isinstance(samples, list) else 0
        n_spots = summary.get("n_spots")
        if not isinstance(n_spots, int):
            n_spots = None
        n_genes = summary.get("n_genes")
        if not isinstance(n_genes, int):
            n_genes = None
        source = manifest.get("source")
        if not isinstance(source, dict):
            source = {}
        return {
            # 与 bulk 同名的键（dataset/samples/genes/valid_groups）
            "dataset": self.display_name or self.dataset_id,
            "samples": n_samples,
            "genes": n_genes,
            "valid_groups": self.valid_groups,
            # 空转新增
            "n_spots": n_spots,
            "n_samples": n_samples,
            "n_genes": n_genes,
            "n_clusters": summary.get("n_clusters"),
            "n_spots_pass_qc": summary.get("n_spots_pass_qc"),
            "dataset_id": self.dataset_id,
            "created_at": manifest.get("created_at"),
            "engine": source.get("engine"),
        }

    def _build_artifact_info(self, folder_path, dataset_name, manifest,
                             resolve_artifact_path=None, check_artifact=None):
        """组装主对象校验信息（路径解析与磁盘校验都优先复用 W3 的实现）

        Returns:
            dict: {ok, path, exists, bytes, bytes_expected, bytes_match,
                   size_mb, mtime, mtime_str, mtime_expected, issues, warnings, reason}
        """
        info = {"ok": False, "reason": "", "issues": [], "warnings": []}
        try:
            artifact = manifest.get("artifact") or {}
            if not isinstance(artifact, dict):
                artifact = {}

            # ① 路径解析：优先用 W3 的 resolve_artifact_path（保证与它同一套规则）
            abs_path = ""
            if callable(resolve_artifact_path):
                try:
                    abs_path = resolve_artifact_path(manifest, BASE_DIR) or ""
                except Exception:
                    traceback.print_exc()
            if not abs_path:
                rel_path = artifact.get("path")
                if isinstance(rel_path, str) and rel_path:
                    abs_path = rel_path if os.path.isabs(rel_path) else os.path.join(BASE_DIR, rel_path)
                else:
                    abs_path = os.path.join(folder_path, dataset_name + _ARTIFACT_SUFFIX)
            info["path"] = abs_path

            exists = os.path.isfile(abs_path)
            info["exists"] = exists
            if not exists:
                info["reason"] = f"主对象不存在: {abs_path}"
                return info

            try:
                actual_bytes = os.path.getsize(abs_path)
                actual_mtime = os.path.getmtime(abs_path)
            except Exception:
                traceback.print_exc()
                info["reason"] = "无法读取主对象属性"
                return info

            expected_bytes = artifact.get("bytes")
            expected_mtime = artifact.get("mtime")
            info["bytes"] = actual_bytes
            info["bytes_expected"] = expected_bytes
            info["size_mb"] = round(actual_bytes / 1048576.0, 1)
            info["mtime"] = actual_mtime
            try:
                info["mtime_str"] = datetime.datetime.fromtimestamp(
                    actual_mtime).strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                info["mtime_str"] = ""
            info["mtime_expected"] = expected_mtime
            info["bytes_match"] = (expected_bytes == actual_bytes) if isinstance(expected_bytes, int) else None

            # ② 磁盘校验：优先用 W3 的 check_artifact
            if callable(check_artifact):
                try:
                    raw_issues = list(check_artifact(manifest, BASE_DIR) or [])
                except Exception:
                    traceback.print_exc()
                    raw_issues = ["artifact: 磁盘校验异常"]
                # mtime 差异只当提示（弱信号），其余（存在性/体积）才是致命
                for issue in raw_issues:
                    text = str(issue)
                    if text.startswith("artifact.mtime"):
                        info["warnings"].append(text)
                    else:
                        info["issues"].append(text)

            info["ok"] = not info["issues"]
            if not info["ok"]:
                info["reason"] = "；".join(str(x) for x in info["issues"][:3])
            return info
        except Exception:
            traceback.print_exc()
            info["reason"] = "主对象校验异常"
            return info


__all__ = ['SpatialDataManager']
