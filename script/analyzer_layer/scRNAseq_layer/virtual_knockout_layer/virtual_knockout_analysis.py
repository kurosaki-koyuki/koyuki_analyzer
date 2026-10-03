# -*- coding: utf-8 -*-
"""
scRNAseq 虚拟敲除层（virtual_knockout_layer）- 分析算法层

规范来源：虚拟敲除参考/虚拟敲除层_实装说明书_交付乙方.md
  §2.2 R 解释器/短路径、§2.3 路径常量、§4.2.4 本文件方法清单、
  §6 参数总表（参数键名 vs R 端形参名）、§7.1/§7.2 命名参数契约（铁律）、
  §8.8 错误处理、§9 输出目录与产物、§10 诊断数字、§11 性能、§12.2 验收尺寸。

本层职责（房规，说明书 §3.1）：
  默认值常量 / 取数 / 拼命名参数 / 调 R（Popen + 实时日志 + 超时）/ 解析产物。
本层禁令：
  ⛔ 不 import 任何 Qt 控件（不碰 UI）；
  ⛔ 不使用位置参数调用 R（说明书 §7.1 有本仓真实事故）；
  ⛔ 不吞异常（每个 except 都要 traceback.print_exc()）。

模块级留痕前缀统一为 [virtual_knockout]，便于 grep。
"""

import os
import sys
import time
import struct
import ctypes
import subprocess
import traceback
import datetime

import pandas as pd

from script.utils_layer.import_config import (
    OUT_BASE,
    APPDATA_PATH,
    get_r_script_path,
)
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


# ============================================================
# 模块级工具：留痕 / 取值 / 命令行字面量
# ============================================================

LOG_PREFIX = "[virtual_knockout]"

# 每一行都原样写入 out_dir/run.log
RUN_LOG_NAME = "run.log"

# 产物文件名（说明书 §9；★ 一律 ASCII，不许改）
FULL_CSV_NAME = "diffRegulation_full.csv"
SIG_CSV_NAME = "diffRegulation_significant.csv"
FIG_BAR_NAME = "fig1_bar_Differentially_Related_Genes.png"
FIG_SCATTER_NAME = "fig2_scatter_Differentially_Related_Genes.png"
SUMMARY_NAME = "run_summary.txt"
RDS_NAME = "virtual_knockout_result.rds"
PARAMS_JSON_NAME = "params.json"

# 说明书 §12.2：两张图必须是同一个正方形（dpi=200 → 实测 1600×1600）
EXPECTED_FIG_SIZE = (1600, 1600)


def _trace(msg):
    """模块级留痕：统一前缀 + 立即 flush，便于 grep 与实时排查"""
    text = f"{LOG_PREFIX} {msg}"
    print(text, flush=True)
    return text


def _pct(value):
    """把 0.05 这类比例格式化成 5.00%"""
    try:
        return f"{float(value) * 100.0:.2f}%"
    except (TypeError, ValueError):
        return str(value)


class VirtualKnockoutAnalysis:
    """虚拟敲除分析层（算法核心，不含任何 UI 依赖）"""

    # ============================================================
    # 默认值常量（★ 与说明书 §6「参数键名」表逐字一致；勿自行改动）
    # ============================================================
    DEFAULT_GROUPS = ["Celltype (major-lineage)"]
    DEFAULT_GENE_MODE = "hvg"          # hvg | all | list
    DEFAULT_HVG_N = 1000
    DEFAULT_DROP_MT = True
    DEFAULT_DROP_RIBO = True
    DEFAULT_QC = True
    DEFAULT_QC_MINLIB = 1000
    DEFAULT_QC_MINPCT = 0.05
    DEFAULT_QC_MTRATIO = 0.1
    DEFAULT_QC_OUTLIER = True
    DEFAULT_EXCLUDE_GKO = True
    DEFAULT_FDR = 0.05
    DEFAULT_NNET = 10
    DEFAULT_NCELLS = 500
    DEFAULT_NCOMP = 3
    DEFAULT_NQ = 0.9
    DEFAULT_TDK = 3
    DEFAULT_MADIM = 2
    DEFAULT_SEED = 1
    # ★ 说明书 §6 F2：min(4, 核数)；§4.2.4 写作 4
    DEFAULT_NCORES = min(4, os.cpu_count() or 1)

    # 说明书 §6 C5/C6/C7/D3：不暴露但**每次都必须传给 R** 的固定参数
    FIXED_SCALE_SCORES = True
    FIXED_SYMMETRIC = False
    FIXED_LAMBDA = 0
    FIXED_TD_MAX_ITER = 1000
    FIXED_TD_MAX_ERROR = 1e-05
    FIXED_TD_N_DECIMAL = 3

    # 说明书 §11：1000 基因 ≈ 12.6 s，但 5000 基因官方基准 ≈ 4 min ⇒ 超时默认给足 1 小时
    DEFAULT_TIMEOUT = 3600
    # 失败时带回错误串的日志尾部行数
    ERROR_TAIL_LINES = 40

    # ---- 参数登记表：params 键名 → (R 端形参名, 值类型标识) ----
    # 类型标识：path=路径(需过 8.3 短路径) / bool=TRUE|FALSE / num=数值 / str=字符串
    # ⚠️ 形参名取说明书 §6「R 端形参」列，**不是**「参数键名」列（两列不同名，见 §3/§4）
    ARG_SPECS = (
        ("rds_path", "rds", "path"),
        ("out_dir", "out_dir", "path"),
        ("dataset_name", "dataset", "str"),
        ("gko", "gko", "str"),
        ("group_col", "group_col", "str"),
        ("group_values", "group_values", "str"),
        ("filter1_col", "filter1_col", "str"),
        ("filter1_values", "filter1_values", "str"),
        ("filter2_col", "filter2_col", "str"),
        ("filter2_values", "filter2_values", "str"),
        ("gene_mode", "gene_mode", "str"),
        ("n_top_genes", "n_top_genes", "num"),
        ("gene_list_file", "gene_list_file", "str"),
        ("drop_mt", "drop_mt", "bool"),
        ("drop_ribo", "drop_ribo", "bool"),
        ("qc", "qc", "bool"),
        ("qc_min_lib_size", "qc_min_lib_size", "num"),
        ("qc_min_pct", "qc_min_pct", "num"),
        ("qc_max_mt_ratio", "qc_max_mt_ratio", "num"),
        ("qc_remove_outlier", "qc_remove_outlier", "bool"),
        ("n_net", "n_net", "num"),
        ("n_cells", "n_cells", "num"),
        ("n_comp", "n_comp", "num"),
        ("q", "q", "num"),
        ("scale_scores", "scale_scores", "bool"),
        ("symmetric", "symmetric", "bool"),
        ("lambda", "lambda", "num"),
        ("td_k", "td_k", "num"),
        ("td_max_iter", "td_max_iter", "num"),
        ("td_max_error", "td_max_error", "num"),
        ("td_n_decimal", "td_n_decimal", "num"),
        ("ma_ndim", "ma_ndim", "num"),
        ("exclude_gko", "exclude_gko", "bool"),
        ("fdr", "fdr", "num"),
        ("empirical_null", "empirical_null", "bool"),
        ("seed", "seed", "num"),
        ("n_cores", "n_cores", "num"),
    )

    # ---------------- 构造与运行环境（说明书 §2.2） ----------------

    def __init__(self):
        # 数据来源（由 W2 从 sc_top_bind.analysis 注入，见 set_data_source）
        self.rds_path = None            # 当前数据集的 Seurat rds 绝对路径
        self.dataset_name = None        # 当前数据集名
        # 元数据（W2 从 sc_top_bind.analysis.seurat_metadata_columns/.values 注入）
        self._meta_columns = []
        self._meta_values = {}
        self._meta_r_checked = False    # rpy2 兜底是否已尝试过（避免反复读盘）
        self._meta_misses = set()       # rpy2 兜底已确认不存在的列名（避免反复读盘）
        # 最近一次运行
        self._last_out_dir = None
        self._last_error = ""

        # R 接口 / Rscript / R 脚本
        self._r_interface = get_r_kernel_interface()
        self._rscript_path = self._get_rscript_path()
        self._r_script_path = get_r_script_path(__file__, "virtual_knockout.R")
        # 当前正在跑的进程（供 stop() 中止）
        self._proc = None

    def _get_rscript_path(self):
        """R 解释器路径：优先框架配置，取不到再退回本仓真实兜底"""
        try:
            r_path = self._r_interface.get_r_path()
        except Exception:
            _trace("读取 R 路径失败，退回硬编码兜底")
            traceback.print_exc()
            r_path = None
        if r_path:
            return os.path.join(r_path, "bin", "Rscript.exe")
        # ★ 本仓真实兜底（不带 x64），照抄 sc_monocle_genelists_analysis.py:42
        return r"A:\TOOLS\R\R-4.6.1\bin\Rscript.exe"

    def _get_short_path(self, path):
        """Windows 中文/空格/长路径 → 8.3 短路径（说明书 §2.2 必须照抄）"""
        if not path:
            return path
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 260)
            short = buf.value
            return short if short else path
        except Exception:
            _trace(f"短路径转换失败，沿用原路径：{path}")
            traceback.print_exc()
            return path

    def get_rscript_path(self):
        """供 UI/日志显示当前使用的 Rscript.exe"""
        return self._rscript_path

    def get_r_script_path(self):
        """供 UI/日志显示当前使用的 virtual_knockout.R"""
        return self._r_script_path

    # ============================================================
    # 数据来源与元数据（数据由 W2 从 sc_top_bind.analysis 注入）
    # ============================================================

    def set_data_source(self, rds_path, dataset_name):
        """设置当前数据集的 Seurat rds 路径与数据集名（由数据加载类共享）"""
        self.rds_path = rds_path
        self.dataset_name = dataset_name
        _trace(f"设置数据源：dataset={dataset_name} rds={rds_path}")

    def has_data_source(self):
        """是否已共享可用的数据源（保守：路径非空且文件真实存在）"""
        if not self.rds_path or not self.dataset_name:
            return False
        try:
            return os.path.exists(self.rds_path)
        except Exception:
            traceback.print_exc()
            return False

    def set_meta(self, columns, values):
        """接收 W2 注入的元数据列与列值（来自 sc_top_bind.analysis）

        Args:
            columns: 列名列表（或 dict，此时取其 keys）
            values:  {列名: [值, ...]} 字典；也可传 DataFrame
        """
        if columns is None:
            columns = []
        if isinstance(columns, dict):
            columns = list(columns.keys())
        self._meta_columns = [str(c) for c in columns]
        if values is None:
            values = {}
        if isinstance(values, pd.DataFrame):
            self._meta_values = {
                str(c): [str(v) for v in values[c].dropna().unique().tolist()]
                for c in values.columns
            }
        elif isinstance(values, dict):
            self._meta_values = {str(k): list(v) for k, v in values.items()}
        else:
            _trace(f"set_meta 收到无法识别的 values 类型：{type(values)}，按空处理")
            self._meta_values = {}
        self._meta_r_checked = False
        _trace(f"接收元数据注入：{len(self._meta_columns)} 列 / {len(self._meta_values)} 列有值")

    def get_meta_columns(self):
        """读 Seurat 对象的 meta.data 列名；注入为空时可选 rpy2 现读兜底"""
        if self._meta_columns:
            return list(self._meta_columns)
        return self._read_meta_from_rds(columns_only=True)

    def get_meta_values(self, column):
        """读某一列的全部取值；注入为空时可选 rpy2 现读兜底"""
        if not column:
            return []
        if self._meta_values:
            vals = self._meta_values.get(str(column))
            if vals is not None:
                return list(vals)
            # 注入里没有这一列 → 兜底现读（可能确实不存在）
            return self._read_meta_from_rds(column=str(column))
        return self._read_meta_from_rds(column=str(column))

    def _read_meta_from_rds(self, column=None, columns_only=False):
        """可选兜底：用 rpy2 现读 Seurat meta.data（读不到返回 [] 并留痕）

        先例：sc_hdwgcna_layer/r_hdwgcna/sc_hdwgcna_analysis.py:164。
        ⚠️ 读 13558 细胞的 unique() 有一定开销，故只读一次并缓存；
           W2 最好直接注入，不要落到这条路径。
        """
        if self._meta_r_checked and not self._meta_columns:
            # 已经尝试过且仍然为空：不再重复读盘，但每次留痕（不许静默）
            if column:
                _trace(f"元数据兜底不可用，列 {column} 返回空（已尝试过 rpy2 现读）")
            return []
        if column and column in self._meta_misses:
            # 该列已确认不存在：避免每次点击都重新 readRDS（仍逐次留痕，不静默）
            _trace(f"元数据兜底：列 {column} 已确认不存在（跳过重复读盘）")
            return []
        if not self.rds_path or not self.has_data_source():
            _trace("元数据兜底跳过：没有可用的 rds 数据源")
            return []
        try:
            robjects = self._r_interface.get_robjects()
            if robjects is None:
                self._meta_r_checked = True
                _trace("元数据兜底失败：R 环境不可用（get_robjects() 返回 None）")
                return []
            rds = str(self.rds_path).replace("\\", "/")
            robjects.globalenv["vk_meta_rds"] = robjects.StrVector([rds])
            if not self._meta_columns:
                cols = robjects.r(
                    'colnames(readRDS(vk_meta_rds)@meta.data)')
                self._meta_columns = [str(c) for c in cols]
                _trace(f"元数据兜底：rpy2 现读到 {len(self._meta_columns)} 列")
            if columns_only:
                return list(self._meta_columns)
            if not column:
                return []
            if column not in self._meta_columns:
                self._meta_misses.add(column)
                _trace(f"元数据兜底：列 {column} 不存在于 meta.data")
                return []
            values = robjects.r(
                f'unique(as.character(readRDS(vk_meta_rds)@meta.data[["{column}"]]))')
            result = [str(v) for v in values]
            self._meta_values[column] = result
            return list(result)
        except Exception:
            self._meta_r_checked = True
            _trace(f"元数据兜底失败（rpy2 现读），列 {column} 返回空")
            traceback.print_exc()
            return []

    # ============================================================
    # 基因列表目录扫描（说明书 §4.2.4 / 参照 bulk_ml 的 _scan_dir）
    # ============================================================

    @property
    def GENELIST_DIR(self):
        """基因列表目录（APPDATA_PATH/genelists）"""
        return os.path.join(APPDATA_PATH, "genelists")

    def _scan_dir(self, dir_path, exts):
        """扫描目录下指定后缀的文件名列表（供 UI 下拉框）"""
        if not os.path.isdir(dir_path):
            return []
        try:
            files = []
            for f in os.listdir(dir_path):
                if f.lower().endswith(exts):
                    files.append(f)
            return sorted(files)
        except Exception:
            _trace(f"扫描目录失败：{dir_path}")
            traceback.print_exc()
            return []

    def scan_gene_lists(self):
        """列出 APPDATA_PATH/genelists 下的基因列表文件（xlsx/xls/txt/csv）"""
        return self._scan_dir(self.GENELIST_DIR, ('.xlsx', '.xls', '.txt', '.csv'))

    def get_gene_list_path(self, file_name):
        """把下拉框里的文件名拼成绝对路径（空/不存在返回 None）"""
        if not file_name:
            return None
        path = os.path.join(self.GENELIST_DIR, file_name)
        return path if os.path.exists(path) else None

    # ============================================================
    # detect_* 兜底 getter（无 UI 字段时使用；参照 bulk_ml 写法）
    # ============================================================

    def _coerce_bool(self, value, default):
        """把一个可能是 bool / 'true' / 1 / '1' 的值转成 bool"""
        if value is None:
            return bool(default)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    def _coerce_int(self, value, default, minimum=None):
        try:
            val = int(value) if value is not None else int(default)
        except (TypeError, ValueError):
            val = int(default)
        if minimum is not None:
            val = max(int(minimum), val)
        return val

    def _coerce_float(self, value, default, minimum=None):
        try:
            val = float(value) if value is not None else float(default)
        except (TypeError, ValueError):
            val = float(default)
        if minimum is not None:
            val = max(float(minimum), val)
        return val

    def detect_gene_mode(self, ui_obj=None):
        """基因来源模式：all / hvg / list（说明书 §5.2）"""
        v = getattr(ui_obj, 'vk_gene_mode', None) if ui_obj is not None else None
        v = str(v).lower() if v else self.DEFAULT_GENE_MODE
        return v if v in ("all", "hvg", "list") else self.DEFAULT_GENE_MODE

    def detect_n_top_genes(self, ui_obj=None):
        """高变基因前 N（说明书 §6 A6：100–5000）"""
        v = getattr(ui_obj, 'vk_n_top_genes', None) if ui_obj is not None else None
        return self._coerce_int(v, self.DEFAULT_HVG_N, minimum=100)

    def detect_drop_mt(self, ui_obj=None):
        """是否剔除线粒体基因"""
        v = getattr(ui_obj, 'vk_drop_mt', None) if ui_obj is not None else None
        return self._coerce_bool(v, self.DEFAULT_DROP_MT)

    def detect_drop_ribo(self, ui_obj=None):
        """是否剔除核糖体基因"""
        v = getattr(ui_obj, 'vk_drop_ribo', None) if ui_obj is not None else None
        return self._coerce_bool(v, self.DEFAULT_DROP_RIBO)

    def detect_qc(self, ui_obj=None):
        """是否启用质控"""
        v = getattr(ui_obj, 'vk_qc', None) if ui_obj is not None else None
        return self._coerce_bool(v, self.DEFAULT_QC)

    def detect_qc_params(self, ui_obj=None):
        """质控四项参数（说明书 §6 B2–B5）"""
        def _get(name):
            return getattr(ui_obj, name, None) if ui_obj is not None else None

        return {
            'qc_min_lib_size': self._coerce_int(
                _get('vk_qc_min_lib_size'), self.DEFAULT_QC_MINLIB, minimum=0),
            'qc_min_pct': self._coerce_float(
                _get('vk_qc_min_pct'), self.DEFAULT_QC_MINPCT, minimum=0.0),
            'qc_max_mt_ratio': self._coerce_float(
                _get('vk_qc_max_mt_ratio'), self.DEFAULT_QC_MTRATIO, minimum=0.0),
            'qc_remove_outlier': self._coerce_bool(
                _get('vk_qc_remove_outlier'), self.DEFAULT_QC_OUTLIER),
        }

    def detect_exclude_gko(self, ui_obj=None):
        """★ 铁律开关：是否从显著性校准里排除被敲基因（说明书 §5.5，默认开）"""
        v = getattr(ui_obj, 'vk_exclude_gko', None) if ui_obj is not None else None
        return self._coerce_bool(v, self.DEFAULT_EXCLUDE_GKO)

    def detect_fdr(self, ui_obj=None):
        """FDR 阈值（说明书 §6 E2：0–1）"""
        v = getattr(ui_obj, 'vk_fdr', None) if ui_obj is not None else None
        val = self._coerce_float(v, self.DEFAULT_FDR, minimum=0.0)
        return min(1.0, val)

    def detect_empirical_null(self, ui_obj=None):
        """经验零分布（locfdr 未装 ⇒ 必须 FALSE，说明书 §5.5/§14-3）"""
        v = getattr(ui_obj, 'vk_empirical_null', None) if ui_obj is not None else None
        return self._coerce_bool(v, False)

    def detect_n_net(self, ui_obj=None):
        """网络个数 nc_nNet（3–20）"""
        v = getattr(ui_obj, 'vk_n_net', None) if ui_obj is not None else None
        return self._coerce_int(v, self.DEFAULT_NNET, minimum=1)

    def detect_n_cells(self, ui_obj=None):
        """每网络子采样细胞数 nc_nCells（50–2000）"""
        v = getattr(ui_obj, 'vk_n_cells', None) if ui_obj is not None else None
        return self._coerce_int(v, self.DEFAULT_NCELLS, minimum=1)

    def detect_advanced_params(self, ui_obj=None):
        """高级组参数（说明书 §6 C3/C4/D1/D2/F1/F2）"""
        def _get(name):
            return getattr(ui_obj, name, None) if ui_obj is not None else None

        return {
            'n_comp': self._coerce_int(_get('vk_n_comp'), self.DEFAULT_NCOMP, minimum=1),
            'q': self._coerce_float(_get('vk_q'), self.DEFAULT_NQ, minimum=0.0),
            'td_k': self._coerce_int(_get('vk_td_k'), self.DEFAULT_TDK, minimum=1),
            'ma_ndim': self._coerce_int(_get('vk_ma_ndim'), self.DEFAULT_MADIM, minimum=1),
            'seed': self._coerce_int(_get('vk_seed'), self.DEFAULT_SEED, minimum=0),
            'n_cores': self._coerce_int(_get('vk_n_cores'), self.DEFAULT_NCORES, minimum=1),
        }

    # ============================================================
    # 参数拼装（说明书 §7：★ 一律命名参数，绝不用位置参数）
    # ============================================================

    def _resolve_params(self, params=None):
        """把外部 params 补全成完整取值表（缺失项一律走 §6 默认值）"""
        p = dict(params) if params else {}

        def _pick(key, default):
            if key not in p:
                return default
            val = p[key]
            return default if val is None else val

        resolved = {
            'rds_path': _pick('rds_path', self.rds_path),
            'out_dir': _pick('out_dir', None),
            'dataset_name': _pick('dataset_name', self.dataset_name),
            'gko': _pick('gko', ''),
            'group_col': _pick('group_col', self.DEFAULT_GROUPS[0]),
            'group_values': _pick('group_values', []),
            'filter1_col': _pick('filter1_col', ''),
            'filter1_values': _pick('filter1_values', []),
            'filter2_col': _pick('filter2_col', ''),
            'filter2_values': _pick('filter2_values', []),
            'gene_mode': _pick('gene_mode', self.DEFAULT_GENE_MODE),
            'n_top_genes': _pick('n_top_genes', self.DEFAULT_HVG_N),
            'gene_list_file': _pick('gene_list_file', ''),
            'drop_mt': _pick('drop_mt', self.DEFAULT_DROP_MT),
            'drop_ribo': _pick('drop_ribo', self.DEFAULT_DROP_RIBO),
            'qc': _pick('qc', self.DEFAULT_QC),
            'qc_min_lib_size': _pick('qc_min_lib_size', self.DEFAULT_QC_MINLIB),
            'qc_min_pct': _pick('qc_min_pct', self.DEFAULT_QC_MINPCT),
            'qc_max_mt_ratio': _pick('qc_max_mt_ratio', self.DEFAULT_QC_MTRATIO),
            'qc_remove_outlier': _pick('qc_remove_outlier', self.DEFAULT_QC_OUTLIER),
            'n_net': _pick('n_net', self.DEFAULT_NNET),
            'n_cells': _pick('n_cells', self.DEFAULT_NCELLS),
            'n_comp': _pick('n_comp', self.DEFAULT_NCOMP),
            'q': _pick('q', self.DEFAULT_NQ),
            'scale_scores': _pick('scale_scores', self.FIXED_SCALE_SCORES),
            'symmetric': _pick('symmetric', self.FIXED_SYMMETRIC),
            'lambda': _pick('lambda', self.FIXED_LAMBDA),
            'td_k': _pick('td_k', self.DEFAULT_TDK),
            'td_max_iter': _pick('td_max_iter', self.FIXED_TD_MAX_ITER),
            'td_max_error': _pick('td_max_error', self.FIXED_TD_MAX_ERROR),
            'td_n_decimal': _pick('td_n_decimal', self.FIXED_TD_N_DECIMAL),
            'ma_ndim': _pick('ma_ndim', self.DEFAULT_MADIM),
            'exclude_gko': _pick('exclude_gko', self.DEFAULT_EXCLUDE_GKO),
            'fdr': _pick('fdr', self.DEFAULT_FDR),
            'empirical_null': _pick('empirical_null', False),
            'seed': _pick('seed', self.DEFAULT_SEED),
            'n_cores': _pick('n_cores', self.DEFAULT_NCORES),
        }
        return resolved

    @staticmethod
    def _bool_literal(value):
        """布尔一律 TRUE / FALSE 大写（说明书 §7.2）"""
        if isinstance(value, str):
            value = value.strip().lower() in ("1", "true", "yes", "on")
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _value_literal(cls, value, kind):
        """把 Python 值转成命令行字面量"""
        if kind == "bool":
            return cls._bool_literal(value)
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return ",".join([str(v) for v in value])
        if kind == "num":
            if isinstance(value, bool):
                return cls._bool_literal(value)
            if isinstance(value, float):
                # 0.05 → "0.05"；1e-05 → "1e-05"（说明书 §7.2 原文即如此）
                return repr(value)
            return str(value)
        return str(value)

    def build_r_args(self, params):
        """拼装 R 命令行参数（★ 命名参数，顺序与说明书 §7.2 一致）

        Args:
            params: 参数字典（键名 = 说明书 §6「参数键名」列）
        Returns:
            list[str]：形如 ["--gko=SOX2", "--qc=TRUE", ...]
                      （不含 rscript 与脚本路径本身）
        """
        resolved = self._resolve_params(params)
        args = []
        for key, r_name, kind in self.ARG_SPECS:
            value = resolved.get(key)
            if kind == "path":
                # ★ 说明书 §7.2：<out_dir> 与 <rds> 必须先过 8.3 短路径
                if value:
                    value = self._get_short_path(value)
                else:
                    value = ""
            literal = self._value_literal(value, kind)
            args.append(f"--{r_name}={literal}")
        return args

    def get_params_for_summary(self, params):
        """返回补全后的参数快照（供日志/自测展示，不含短路径转换）"""
        return self._resolve_params(params)

    def list_r_arg_keys(self):
        """返回本层会传给 R 的全部形参名（供自测/探针核 §7.2 完整性）"""
        return [r_name for _key, r_name, _kind in self.ARG_SPECS]

    # ============================================================
    # 输出目录（说明书 §9）
    # ============================================================

    @staticmethod
    def _sanitize_name(name):
        """把数据集名里对文件名非法的字符替换为下划线"""
        if not name:
            return "unknown_dataset"
        bad = '<>:"/\\|?*'
        safe = "".join(('_' if ch in bad else ch) for ch in str(name))
        return safe.strip() or "unknown_dataset"

    def get_out_dir(self, dataset_name=None, timestamp=None):
        """生成输出目录路径：OUT_BASE/virtual_knockout/{dataset}/{YYYYmmdd_HHMMSS}/

        ⛔ 只生成路径，不建目录（是否先 makedirs 见 run()）
        """
        ds = self._sanitize_name(dataset_name or self.dataset_name)
        ts = timestamp or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(OUT_BASE, "virtual_knockout", ds, ts)

    def get_last_out_dir(self):
        """最近一次运行的输出目录（供 UI 打开目录）"""
        return self._last_out_dir

    def get_last_error(self):
        """最近一次失败的可读错误串"""
        return self._last_error

    # ============================================================
    # 调 R（Popen + 实时日志 + 超时 + 写 run.log）
    # ============================================================

    # 非 ASCII 路径（中文基因列表文件名 / 中文数据集名）要被 R 的 file.exists()
    # 转成 native 编码，R 子进程**必须**拿到 UTF-8 字符集的 locale。
    # 因此把这些"字符集被钉成 C"的变量从子进程环境里摘掉，让 R 回落到系统默认
    # （本机实测 = Chinese (Simplified)_China.utf8 ⇒ l10n_info()$UTF-8 = TRUE）。
    _C_CHARSET_LOCALES = ("C", "POSIX")

    @classmethod
    def _r_child_env(cls):
        """给 R 子进程准备环境变量：摘掉把字符集钉成 C 的 locale 变量

        ★ 真因（2026-09-25 甲方 GUI 实测 → 协调者定位 → 本层修正）：
          `script/utils_layer/import_config.py:179` 在 **import 期**执行
          `os.environ['LC_ALL'] = 'C'`（注释写"避免R输出编码问题"），
          它是进程级的 ⇒ **所有**子进程都继承 ⇒ R 的 `l10n_info()$UTF-8` 变成 FALSE
          ⇒ 任何**非 ASCII 路径**在 `file.exists()` 里抛
             `file name conversion problem -- name too long?`。

          `--rds` / `--out_dir` 侥幸没炸，只是因为它们被转成了 8.3 短路径（纯 ASCII）；
          `--gene_list_file` 是字符串参数、不走短路径，所以只有它炸 ⇒
          外部基因列表模式（用户 genelists 里全是中文名文件）100% 失败。

          本机实测（同一份 Rscript，只换子进程环境）：
            LC_ALL=C                      → UTF8=FALSE | CTYPE=C
            去掉 LC_ALL                   → UTF8=TRUE  | CTYPE=Chinese (Simplified)_China.utf8
        ⛔ 不去改 `import_config.py`（全仓文件、不在本层范围内，且那句是本仓历史决定）；
          只在我们**自己的子进程**上把它抵消掉。
        """
        env = dict(os.environ)
        # LC_ALL 会覆盖一切 LC_* 分类，必须先摘掉
        if 'LC_ALL' in env:
            _trace(f"R 子进程：摘掉 LC_ALL={env.get('LC_ALL')!r}"
                   f"（否则中文路径在 file.exists() 里失败）")
            env.pop('LC_ALL', None)
        # 父进程若把字符集单独钉成 C/POSIX，同样摘掉，让 R 用系统默认
        for _k in ('LC_CTYPE', 'LANG'):
            if str(env.get(_k, '')).strip().upper() in cls._C_CHARSET_LOCALES:
                _trace(f"R 子进程：摘掉 {_k}={env.get(_k)!r}（字符集为 C，会导致非 ASCII 路径失败）")
                env.pop(_k, None)
        return env

    def _run_r_script(self, args, out_dir, progress_callback=None,
                      timeout=None, script_path=None):
        """调用 R 脚本（subprocess.Popen + 逐行实时输出）

        ★ 与参考实现（sc_monocle_genelists_analysis.py:407-462）的三处差异：
          1) 参数一律 --key=value（由 build_r_args 保证，绝不位置参数）；
          2) 每一行原样写入 <out_dir>/run.log（UTF-8）；
          3) 先 os.makedirs(out_dir, exist_ok=True)。
          另：Popen 传 env=self._r_child_env()，抵消 import 期设下的 LC_ALL=C（见上）。
        Returns:
            (success, collected_lines, tail_text)
        """
        timeout = int(timeout or self.DEFAULT_TIMEOUT)
        r_script = script_path or self._r_script_path

        if not os.path.exists(r_script):
            msg = f"R 脚本不存在：{r_script}"
            _trace(msg)
            return False, [], msg
        if not os.path.exists(self._rscript_path):
            msg = f"Rscript.exe 不存在：{self._rscript_path}"
            _trace(msg)
            return False, [], msg

        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            _trace(f"创建输出目录失败：{out_dir}")
            traceback.print_exc()
            return False, [], f"创建输出目录失败：{out_dir}"

        log_path = os.path.join(out_dir, RUN_LOG_NAME)
        cmd = [self._rscript_path, self._get_short_path(r_script)] + list(args)
        _trace(f"输出目录：{out_dir}")
        _trace(f"R 脚本：{r_script}")
        _trace(f"命令行：{' '.join(cmd)}")

        collected = []
        try:
            with open(log_path, "w", encoding="utf-8", newline="\n") as log_fh:
                log_fh.write(f"# {LOG_PREFIX} command: {' '.join(cmd)}\n")
                log_fh.flush()

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,   # stderr 合并进 stdout
                    bufsize=1,
                    text=False,
                    # ★ 必须显式传 env：抵消 import 期设下的 LC_ALL=C，
                    #   否则 R 无法转换非 ASCII 路径（中文基因列表文件名）⇒ 见 _r_child_env
                    env=self._r_child_env(),
                )
                self._proc = proc
                try:
                    while True:
                        line_bytes = proc.stdout.readline()
                        if not line_bytes:
                            break
                        line = line_bytes.decode('utf-8', errors='ignore').rstrip()
                        # 空行也写文件（保持与 R 端输出一致的时序），但不回调
                        log_fh.write(line + "\n")
                        log_fh.flush()
                        if not line:
                            continue
                        collected.append(line)
                        # 与参考实现一致：只回调以 [ 开头的行（R 端为 [VK] ...）
                        if progress_callback and line.startswith('['):
                            try:
                                progress_callback(line)
                            except Exception:
                                _trace("progress_callback 抛异常（已忽略，不影响主流程）")
                                traceback.print_exc()
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    self._proc = None
                    tail = self._tail_text(collected)
                    msg = (f"R 脚本执行超时（>{timeout} s，可通过 timeout 参数覆写）。"
                           f"输出目录：{out_dir}\n--- 日志尾部 ---\n{tail}")
                    _trace(msg)
                    return False, collected, msg
                finally:
                    self._proc = None

            tail = self._tail_text(collected)
            if proc.returncode != 0:
                msg = (f"R 脚本返回码非 0（returncode={proc.returncode}）。"
                       f"输出目录：{out_dir}\n--- stdout/stderr 尾部 ---\n{tail}")
                _trace(msg)
                return False, collected, msg
            _trace(f"R 脚本执行完成：returncode=0，共 {len(collected)} 行输出")
            return True, collected, tail
        except Exception:
            _trace("调用 R 脚本异常")
            traceback.print_exc()
            self._proc = None
            return False, collected, f"调用 R 脚本异常：{traceback.format_exc()}"

    def _tail_text(self, lines, n=None):
        """取日志尾部用于错误串（说明书：失败时不许只说"失败"）"""
        n = n or self.ERROR_TAIL_LINES
        tail = lines[-n:] if len(lines) > n else list(lines)
        return "\n".join(tail)

    def stop(self):
        """中止当前正在运行的 R 进程（供 UI 取消，可选）"""
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                _trace("中止 R 进程失败")
                traceback.print_exc()
            else:
                _trace("已请求中止当前 R 进程")
            finally:
                self._proc = None

    # ============================================================
    # 主流程：run（说明书 §7.2 / §9）
    # ============================================================

    def run(self, params, progress_callback=None, timeout=None):
        """运行虚拟敲除（拼命名参数 → Popen → 写 run.log → 校验产物）

        Args:
            params: 参数字典（键名见说明书 §6）
            progress_callback: 可选；只对以 '[' 开头的行回调
            timeout: 可选；默认 DEFAULT_TIMEOUT = 3600 s
        Returns:
            (success: bool, out_dir: str) 成功
            (False, 可读错误串)           失败
        """
        t0 = time.time()
        self._last_error = ""
        _trace("=" * 60)
        _trace("开始虚拟敲除分析")

        if not self.has_data_source():
            msg = (f"未共享数据集或 rds 不存在：rds={self.rds_path}；"
                   f"请先在数据加载页面加载 Seurat 数据集")
            _trace(msg)
            self._last_error = msg
            return False, msg

        p = self._resolve_params(params)
        if not str(p.get('gko') or '').strip():
            msg = "靶基因（gko）为空，请先填写要虚拟敲除的基因名"
            _trace(msg)
            self._last_error = msg
            return False, msg

        # 输出目录（说明书 §9）
        out_dir = p.get('out_dir') or self.get_out_dir(p.get('dataset_name'))
        p['out_dir'] = out_dir
        self._last_out_dir = out_dir

        # ★ 必须先建目录：GetShortPathNameW 对**不存在的路径**返回空 ⇒ 短路径会静默失效
        #   （实测：已存在路径可转换，不存在的路径原样返回长路径）
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            _trace(f"创建输出目录失败：{out_dir}")
            traceback.print_exc()
            msg = f"创建输出目录失败：{out_dir}（{traceback.format_exc()}）"
            self._last_error = msg
            return False, msg

        try:
            args = self.build_r_args(p)
        except Exception:
            _trace("命令拼装失败")
            traceback.print_exc()
            msg = f"命令拼装失败：{traceback.format_exc()}"
            self._last_error = msg
            return False, msg

        _trace(f"命名参数共 {len(args)} 项：")
        for a in args:
            _trace(f"    {a}")

        ok, lines, tail = self._run_r_script(
            args, out_dir, progress_callback=progress_callback, timeout=timeout)
        elapsed = time.time() - t0

        if not ok:
            self._last_error = tail or "R 脚本执行失败"
            return False, self._last_error

        # 即便 returncode=0 也要校验产物齐不齐（说明书 §9 / §12.1）
        parsed = self.parse_outputs(out_dir)
        missing = []
        if parsed.get('full_csv') is None:
            missing.append(FULL_CSV_NAME)
        if parsed.get('sig_csv') is None:
            missing.append(SIG_CSV_NAME)
        if parsed.get('fig_bar') is None:
            missing.append(FIG_BAR_NAME)
        if parsed.get('fig_scatter') is None:
            missing.append(FIG_SCATTER_NAME)
        if parsed.get('rds') is None:
            missing.append(RDS_NAME)
        if missing:
            msg = (f"R 脚本返回 0 但产物缺失：{', '.join(missing)}；输出目录：{out_dir}\n"
                   f"--- 日志尾部 ---\n{tail}")
            _trace(msg)
            self._last_error = msg
            return False, msg

        if parsed.get('size_mismatch'):
            _trace(f"两张图像素尺寸不一致：{parsed.get('fig_bar_size')} vs "
                   f"{parsed.get('fig_scatter_size')}（说明书 §12.2 要求相等正方形）")

        _trace(f"运行完成，耗时 {elapsed:.1f} s，输出目录：{out_dir}")
        return True, out_dir

    # ============================================================
    # 产物解析（说明书 §9 / §10 / §12.2）
    # ============================================================

    @staticmethod
    def _read_png_size(path):
        """读 PNG 像素尺寸 (宽, 高)

        优先 PIL；PIL 不可用时直接解析 PNG 文件头（签名 8 字节 + IHDR 长/类型 8 字节
        + 宽 4 字节大端 + 高 4 字节大端 = 前 24 字节）。分析层不许碰 Qt（不用 QPixmap）。
        """
        if not path or not os.path.exists(path):
            return None
        try:
            from PIL import Image  # 可选依赖
            with Image.open(path) as im:
                return (int(im.size[0]), int(im.size[1]))
        except Exception:
            _trace(f"PIL 读取图片尺寸失败，改用 PNG 头解析：{path}")
            traceback.print_exc()
        try:
            with open(path, "rb") as f:
                header = f.read(24)
            if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
                _trace(f"不是合法 PNG（签名不匹配）：{path}")
                return None
            if header[12:16] != b"IHDR":
                _trace(f"PNG 头缺少 IHDR 块：{path}")
                return None
            width, height = struct.unpack(">II", header[16:24])
            return (int(width), int(height))
        except Exception:
            _trace(f"PNG 头解析失败：{path}")
            traceback.print_exc()
            return None

    @staticmethod
    def _parse_summary(path):
        """解析 run_summary.txt（key<TAB>value，UTF-8）"""
        summary = {}
        if not path or not os.path.exists(path):
            return summary
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.rstrip("\n").rstrip("\r")
                    if not line.strip():
                        continue
                    if "\t" in line:
                        key, value = line.split("\t", 1)
                    elif " " in line:
                        key, value = line.split(None, 1)
                    else:
                        key, value = line, ""
                    summary[key.strip()] = value.strip()
        except Exception:
            _trace(f"解析 run_summary.txt 失败：{path}")
            traceback.print_exc()
        return summary

    @staticmethod
    def _parse_params_json(path):
        """解析 params.json（参数指纹）"""
        if not path or not os.path.exists(path):
            return {}
        try:
            import json
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {"_value": data}
        except Exception:
            _trace(f"解析 params.json 失败：{path}")
            traceback.print_exc()
            return {}

    @staticmethod
    def _read_csv_safe(path):
        """读 CSV（失败返回 (None, 错误串)），不吞异常"""
        if not path or not os.path.exists(path):
            return None, f"文件不存在：{path}"
        try:
            df = pd.read_csv(path)
            return df, ""
        except Exception:
            _trace(f"读取 CSV 失败：{path}")
            traceback.print_exc()
            return None, f"读取 CSV 失败：{path}"

    @staticmethod
    def _parse_vk_lines(lines):
        """解析 [VK] 诊断行（说明书 §8.9/§10，只做叶子字段的提取）"""
        diag = {}
        for line in lines or []:
            line = (line or "").strip()
            if not line.startswith("[VK]"):
                continue
            body = line[len("[VK]"):].strip()
            if "|" not in body:
                continue
            head, rest = body.split("|", 1)
            head = head.strip()
            fields = rest.split("|")
            if head == "DATA":
                diag["data_genes"] = fields[0].split("=", 1)[-1] if fields else ""
                diag["data_cells"] = fields[1].split("=", 1)[-1] if len(fields) > 1 else ""
            elif head == "CELLS":
                diag["cells_after_filter"] = fields[0].split("=", 1)[-1] if fields else ""
            elif head == "QC":
                diag["qc_genes"] = fields[0].split("=", 1)[-1] if fields else ""
                diag["qc_cells"] = fields[1].split("=", 1)[-1] if len(fields) > 1 else ""
            elif head == "PANEL":
                diag["panel_genes"] = fields[0].split("=", 1)[-1] if fields else ""
                diag["panel_cells"] = fields[1].split("=", 1)[-1] if len(fields) > 1 else ""
                diag["panel_nonzero"] = fields[2].split("=", 1)[-1] if len(fields) > 2 else ""
            elif head == "TARGET":
                diag["target_detected_cells"] = fields[1].split("=", 1)[-1] if len(fields) > 1 else ""
                diag["target_total_counts"] = fields[2].split("=", 1)[-1] if len(fields) > 2 else ""
            elif head == "OUTDEG":
                edges = fields[1].split("=", 1)[-1] if len(fields) > 1 else ""
                diag["out_degree"] = edges
                # ★ 说明书 §8.8：edges=0 ⇒ 前端必须红字提示
                try:
                    diag["no_out_edges"] = (int(float(edges)) == 0)
                except (TypeError, ValueError):
                    diag["no_out_edges"] = None
            elif head == "E":
                diag["share_of_target"] = fields[0].split("=", 1)[-1] if fields else ""
                diag["E_pkg"] = fields[1].split("=", 1)[-1] if len(fields) > 1 else ""
                diag["E_noKO"] = fields[2].split("=", 1)[-1] if len(fields) > 2 else ""
            elif head == "SIG":
                diag["sig_calib_pkg"] = fields[0].split("=", 1)[-1] if fields else ""
                diag["sig_calib_noKO"] = fields[1].split("=", 1)[-1] if len(fields) > 1 else ""
                diag["sig_fdr"] = fields[2].split("=", 1)[-1] if len(fields) > 2 else ""
            elif head == "NCELLS":
                diag["n_cells_effective"] = fields[0].split("=", 1)[-1] if fields else ""
            elif head == "DONE":
                diag["done_out_dir"] = fields[0].split("=", 1)[-1] if fields else ""
            elif head == "ERROR":
                diag["r_error"] = rest
            elif head == "NOTE":
                notes = diag.setdefault("notes", [])
                notes.append(rest)
        return diag

    def parse_outputs(self, out_dir):
        """读回输出目录的全部产物（说明书 §9 / §10 / §12.2）

        Returns:
            {
              "out_dir", "full_csv", "sig_csv", "full_df", "sig_df",
              "fig_bar", "fig_scatter", "fig_bar_size", "fig_scatter_size",
              "summary", "rds", "params",   # params = params.json
              "run_log", "diagnostics", "size_mismatch", "missing"
            }
        """
        result = {
            "out_dir": out_dir,
            "full_csv": None,
            "sig_csv": None,
            "full_df": None,
            "sig_df": None,
            "fig_bar": None,
            "fig_scatter": None,
            "fig_bar_size": None,
            "fig_scatter_size": None,
            "summary": {},
            "rds": None,
            "params": {},
            # 附加（不破坏上面约定键，W2 可直接忽略）
            "run_log": None,
            "diagnostics": {},
            "size_mismatch": False,
            "missing": [],
        }
        if not out_dir or not os.path.isdir(out_dir):
            _trace(f"parse_outputs：输出目录不存在：{out_dir}")
            result["missing"] = ["<out_dir 不存在>"]
            return result

        # ---- CSV ----
        full_path = os.path.join(out_dir, FULL_CSV_NAME)
        sig_path = os.path.join(out_dir, SIG_CSV_NAME)
        if os.path.exists(full_path):
            result["full_csv"] = full_path
            df, err = self._read_csv_safe(full_path)
            result["full_df"] = df
            if err:
                _trace(err)
        else:
            _trace(f"parse_outputs：缺少 {FULL_CSV_NAME}")
        if os.path.exists(sig_path):
            result["sig_csv"] = sig_path
            df, err = self._read_csv_safe(sig_path)
            result["sig_df"] = df
            if err:
                _trace(err)
        else:
            _trace(f"parse_outputs：缺少 {SIG_CSV_NAME}")

        # ---- 两张图：存在性 + 像素尺寸（并校验尺寸相等） ----
        bar_path = os.path.join(out_dir, FIG_BAR_NAME)
        scatter_path = os.path.join(out_dir, FIG_SCATTER_NAME)
        if os.path.exists(bar_path):
            result["fig_bar"] = bar_path
            result["fig_bar_size"] = self._read_png_size(bar_path)
        else:
            _trace(f"parse_outputs：缺少 {FIG_BAR_NAME}")
        if os.path.exists(scatter_path):
            result["fig_scatter"] = scatter_path
            result["fig_scatter_size"] = self._read_png_size(scatter_path)
        else:
            _trace(f"parse_outputs：缺少 {FIG_SCATTER_NAME}")

        size_a = result["fig_bar_size"]
        size_b = result["fig_scatter_size"]
        if size_a and size_b and size_a != size_b:
            # ★ 说明书 §12.2 要求两张图尺寸相等（1600×1600 正方形）
            result["size_mismatch"] = True
            _trace(f"★ 尺寸不一致：柱状图 {size_a} vs 散点图 {size_b}"
                   f"（说明书 §12.2 要求相等，期望 {EXPECTED_FIG_SIZE}）")
        elif size_a and size_b and size_a != EXPECTED_FIG_SIZE:
            _trace(f"提示：图像尺寸 {size_a} 与说明书 §12.2 基线 {EXPECTED_FIG_SIZE} 不同")

        # ---- run_summary.txt ----
        summary_path = os.path.join(out_dir, SUMMARY_NAME)
        result["summary"] = self._parse_summary(summary_path)
        if not result["summary"]:
            _trace(f"parse_outputs：{SUMMARY_NAME} 缺失或为空")

        # ---- params.json（参数指纹） ----
        params_path = os.path.join(out_dir, PARAMS_JSON_NAME)
        result["params"] = self._parse_params_json(params_path)
        if not result["params"]:
            _trace(f"parse_outputs：{PARAMS_JSON_NAME} 缺失或为空")

        # ---- rds ----
        rds_path = os.path.join(out_dir, RDS_NAME)
        if os.path.exists(rds_path):
            result["rds"] = rds_path
        else:
            _trace(f"parse_outputs：缺少 {RDS_NAME}")

        # ---- run.log（本层写入；顺带解析 [VK] 诊断行） ----
        log_path = os.path.join(out_dir, RUN_LOG_NAME)
        if os.path.exists(log_path):
            result["run_log"] = log_path
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                result["diagnostics"] = self._parse_vk_lines(lines)
            except Exception:
                _trace(f"解析 {RUN_LOG_NAME} 失败：{log_path}")
                traceback.print_exc()
        else:
            _trace(f"parse_outputs：{RUN_LOG_NAME} 不存在（非本层运行生成？）")

        result["missing"] = [
            name for name, ok in (
                (FULL_CSV_NAME, result["full_csv"]),
                (SIG_CSV_NAME, result["sig_csv"]),
                (FIG_BAR_NAME, result["fig_bar"]),
                (FIG_SCATTER_NAME, result["fig_scatter"]),
                (RDS_NAME, result["rds"]),
                (SUMMARY_NAME, bool(result["summary"])),
                (PARAMS_JSON_NAME, bool(result["params"])),
            ) if not ok
        ]
        return result

    def describe_outputs(self, parsed):
        """把 parse_outputs 的结果压成一行中文摘要（供日志/回执）"""
        if not parsed:
            return "无产物"
        parts = [
            f"目录={parsed.get('out_dir')}",
            f"全基因表={'有' if parsed.get('full_df') is not None else '无'}",
            f"显著表={'有' if parsed.get('sig_df') is not None else '无'}",
            f"柱状图={parsed.get('fig_bar_size')}",
            f"散点图={parsed.get('fig_scatter_size')}",
        ]
        if parsed.get("size_mismatch"):
            parts.append("★尺寸不一致")
        if parsed.get("missing"):
            parts.append("缺=" + ",".join(parsed["missing"]))
        return " | ".join(str(x) for x in parts)
