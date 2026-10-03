# -*- coding: utf-8 -*-
"""
bulk 一致性分析 Python接口层
此文件不包含任何R代码，只负责：
1. 数据准备和处理
2. 参数传递到R环境
3. 调用R脚本中的三阶段代码
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path, tempfile, shutil
from script.utils_layer.import_config import APPDATA_PATH
import io
from typing import Optional, List, Dict, Any

# 从统一R接口获取R环境
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from script.utils_layer.import_config import importr as _importr


# ========================================
# R 交互辅助（ASCII 协议）
# ========================================
# ★ 背景：rpy2 嵌入的 R 会话 LC_CTYPE = "C"（Rscript 单跑是 UTF-8，所以只有走 rpy2 才暴露）。
#   在该会话里，R 代码中的**非 ASCII 字面量在解析期就被毁**：
#     nchar("=== 基因面板 ===") == 40，长度等于 "<U+57FA><U+56E0><U+9762><U+677F>" 这段转义文本。
#   因此：R 侧一律只用 ASCII（错误码 + [VK] 键值行 + 纯数据回传），
#   所有**用户可见的中文**都在本文件（Python）里拼装。
#   注意：Python 经 rpy2 送入 R 的字符串（数据）不受影响，可正常携带中文。

# R stop() 错误码 → 契约 §7 逐字中文消息
_R_ERROR_MESSAGES = {
    "NO_GENE_LIST": "基因列表分型模式需要提供基因列表",
    "TOO_FEW_GENES": "基因列表在表达矩阵内命中的基因过少（{0} 个），请检查基因名格式",
    "FIXK_RANGE": "固定 k={0} 不在 K 范围 {1}~{2} 内",
    "REF_LABEL_LEN": "参考分组标签数（{0}）与样本数（{1}）不一致",
    # STAGE4 段内（同样是 R 侧中文字面量，LC_CTYPE=C 下会被毁）
    "NEED_STAGE1": "请先运行阶段一聚类计算",
    "FINAL_K_MIN": "final_k 必须大于等于2",
    "FINAL_K_RANGE": "选定 k={0} 不在 K 范围 {1}~{2} 内",
    "DIM_ERROR": "表达矩阵 ccp_exprSet 维度异常",
}


def _translate_r_error(text: str) -> str:
    """把 R 的 ASCII 错误码（VKERR|CODE|a|b）映射回契约中文消息；无错误码则原样返回。"""
    if not text:
        return text
    marker = "VKERR|"
    idx = text.find(marker)
    if idx < 0:
        return text
    fields = []
    for line in text[idx:].splitlines():
        line = line.strip()
        if line:
            fields = line.split("|")
            break
    if len(fields) < 2:
        return text
    template = _R_ERROR_MESSAGES.get(fields[1])
    if template is None:
        return text
    try:
        return template.format(*fields[2:])
    except (IndexError, KeyError):
        return template


def _fmt_eval_num(value) -> str:
    """NA → 'NA'；极小/极大值用科学计数；其余 %g(4)（与契约示例一致）"""
    if value is None:
        return "NA"
    try:
        if pd.isna(value):
            return "NA"
    except (TypeError, ValueError):
        pass
    number = float(value)
    if not np.isfinite(number):
        return "NA"
    if abs(number) < 1e-3 or abs(number) >= 1e5:
        return f"{number:.2e}"
    return f"{number:g}"


def _r_output_lines(value) -> List[str]:
    """把 R 的字符向量（[VK] 标记行）规整成 Python list[str]"""
    if value is None:
        return []
    try:
        return [str(v) for v in list(value)]
    except TypeError:
        return []



class BulkClusterAnalysis:
    """bulk 一致性分析 Python接口层 - 不含R代码"""

    _r_debug_log: List[Dict[str, Any]] = []

    R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_cluster_analysis.R")

    # 外部基因列表目录（契约 §4.1）
    GENELIST_DIR = os.path.join(APPDATA_PATH, "genelists")

    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.pandas2ri = None
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self._r_script_loaded = False
        self._r_packages_loaded = False
        self._stage1_completed = False
        self._stage2_completed = False
        self._stage3_completed = False
        self._stage4_completed = False
        self._temp_dir = None
        # 契约 §4.2：记录最近一次 prepare_expr_data 的样本列，供 get_ref_labels 对齐
        self._last_expr_columns: List[str] = []
        self._init_r_environment()

    # ---------- R环境初始化 ----------

    def _init_r_environment(self):
        if self.r_interface.is_r_available():
            self.robjects = self.r_interface.get_robjects()
            self.pandas2ri = self.r_interface.get_pandas2ri()
        else:
            self._reinit_r_environment()

    def _reinit_r_environment(self):
        saved_path = self.r_interface._load_saved_r_path()
        if saved_path:
            success = self.r_interface.set_r_path(saved_path)
            if success:
                self.robjects = self.r_interface.get_robjects()
                self.pandas2ri = self.r_interface.get_pandas2ri()

    def _log_r_debug(self, operation: str, error: Exception, context: Dict[str, Any] = None):
        import datetime
        debug_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }
        self._r_debug_log.append(debug_entry)
        print(f"[R_DEBUG:{operation}] {type(error).__name__}: {error}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    @classmethod
    def get_r_debug_log(cls) -> List[Dict[str, Any]]:
        return cls._r_debug_log

    @classmethod
    def clear_r_debug_log(cls):
        cls._r_debug_log.clear()

    def is_available(self) -> bool:
        if self.robjects is not None:
            return True
        self._reinit_r_environment()
        return self.robjects is not None

    def get_r_version(self) -> str:
        if self.robjects:
            try:
                return str(self.robjects.r('R.version.string')[0])
            except:
                pass
        self._reinit_r_environment()
        if self.robjects:
            try:
                return str(self.robjects.r('R.version.string')[0])
            except:
                pass
        return "R环境不可用"

    # ---------- 数据设置 ----------

    def set_adata(self, adata):
        self.adata = adata

    def set_dataset_name(self, name):
        self.dataset_name = name

    def set_dataset_output_dir(self, output_dir):
        self.dataset_output_dir = output_dir

    def get_dataset_name(self):
        return self.dataset_name

    def get_adata_shape(self):
        if self.adata is None:
            return 0, 0
        return self.adata.shape

    def get_obs_columns(self):
        """获取obs列名列表"""
        if self.adata is None:
            return []
        return list(self.adata.obs.columns)

    def get_obs_unique_values(self, col_name):
        if self.adata is None or col_name not in self.adata.obs.columns:
            return []
        unique_vals = self.adata.obs[col_name].unique()
        return sorted([str(v) for v in unique_vals if pd.notna(v)])

    # ---------- 外部基因列表（契约 §4.1） ----------

    def _norm_genelist_path(self, filename: str) -> str:
        """允许传入完整路径或仅文件名；相对时落到 self.GENELIST_DIR 下"""
        if filename and os.path.isabs(filename):
            return filename
        return os.path.join(self.GENELIST_DIR, filename or "")

    @staticmethod
    def _is_gene_list_header(value: str) -> bool:
        """判断某行是否为表头（契约 §4.1 冻结清单）"""
        key = str(value).strip().lower()
        return key in ('gene', 'genes', 'symbol', 'gene_name', 'genename',
                       'gene_symbol', 'gene symbol', '基因', '基因名')

    @staticmethod
    def _clean_gene_column(raw_values) -> List[str]:
        """清洗+保序去重"""
        cleaned: List[str] = []
        for value in raw_values:
            if value is None:
                continue
            try:
                if pd.isna(value):
                    continue
            except (TypeError, ValueError):
                pass
            text = str(value).strip()
            if text == '' or text.lower() == 'nan':
                continue
            if BulkClusterAnalysis._is_gene_list_header(text):
                continue
            cleaned.append(text)
        return list(dict.fromkeys(cleaned))

    def scan_gene_lists(self) -> list:
        """扫描 genelists 目录，返回文件名列表（扩展名 ∈ xlsx/xls/txt/csv，排序）"""
        if not self.GENELIST_DIR or not os.path.isdir(self.GENELIST_DIR):
            return []
        allowed = ('.xlsx', '.xls', '.txt', '.csv')
        names = [name for name in os.listdir(self.GENELIST_DIR)
                 if name.lower().endswith(allowed)
                 and os.path.isfile(os.path.join(self.GENELIST_DIR, name))]
        return sorted(names)

    def read_gene_list_file(self, filename: str) -> list:
        """读取基因列表文件，返回去重保序的基因名列表（契约 §4.1）"""
        path = self._norm_genelist_path(filename)
        if not os.path.exists(path):
            raise RuntimeError(f"基因列表文件不存在: {path}")

        try:
            lower = path.lower()
            raw_values = []
            if lower.endswith('.xlsx') or lower.endswith('.xls'):
                frame = pd.read_excel(path, header=None)
                if frame.shape[1] >= 1:
                    raw_values = frame.iloc[:, 0].tolist()
            else:
                # ★ 不要用 pd.read_csv(sep=None)：pandas 嗅探器会把单列基因名里的数字当分隔符
                #   （实测 G00..G09 被切成 'G'，命中 0）。逐行读 + 取第一个分隔符前的字段，稳定可预期。
                raw_values = []
                with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
                    for line in fh:
                        s = line.strip().lstrip('\ufeff')
                        if not s:
                            continue
                        for sep in (',', '\t', ';'):
                            if sep in s:
                                s = s.split(sep)[0]
                                break
                        raw_values.append(s.strip().strip('"').strip("'"))
            return self._clean_gene_column(raw_values)
        except Exception as e:
            raise RuntimeError(f"读取基因列表失败: {e}")

    def match_gene_list(self, gene_list: list, available_genes) -> dict:
        """基因列表与表达矩阵基因交集（含大小写诊断，契约 §4.1）"""
        try:
            available_lookup = set(str(g) for g in available_genes)
        except TypeError:
            available_lookup = set()

        gene_list = list(gene_list or [])
        n_list = len(gene_list)
        n_dedup = len(list(dict.fromkeys(gene_list)))
        matched = [g for g in gene_list if g in available_lookup]

        available_upper = set(g.upper() for g in available_lookup)
        upper_matched = [g for g in gene_list if g not in available_lookup
                         and g.upper() in available_upper]

        case_hint = ''
        if n_list > 0:
            hit_rate = len(matched) / float(n_list)
            if hit_rate < 0.3 and len(upper_matched) > len(matched):
                case_hint = (f"基因名大小写可能与表达矩阵不一致：{len(upper_matched)} 个基因"
                             f"忽略大小写后可在表达矩阵内命中（当前仅命中 {len(matched)} 个），"
                             f"请检查基因列表文件的大小写格式")

        return {
            'n_list': n_list,
            'n_dedup': n_dedup,
            'n_matched': len(matched),
            'matched': matched,
            'case_hint': case_hint,
        }

    def get_ref_labels(self, col: str) -> list:
        """返回与 self._last_expr_columns 对齐的参考分组标签（缺失→'NA'，契约 §4.1）"""
        if not col or col == '不使用':
            return []
        if self.adata is None or col not in self.adata.obs.columns:
            return []
        labels = []
        for sample in self._last_expr_columns:
            if sample in self.adata.obs.index:
                value = self.adata.obs.loc[sample, col]
                if pd.isna(value):
                    labels.append('NA')
                else:
                    labels.append(str(value))
            else:
                labels.append('NA')
        return labels

    # ---------- 阶段四评估文本（Python 侧生成，契约 §5.4 格式） ----------

    def _collect_stage4_eval_text(self, eval_text_path: str, final_k: int,
                                  eval_ref_col: str) -> str:
        """从 R 回传的纯数据拼出评估文本（中文模板在 Python，R 侧只有 ASCII）"""
        from rpy2.robjects import pandas2ri
        from rpy2.robjects.conversion import localconverter

        with localconverter(pandas2ri.converter):
            k_table = pd.DataFrame(self.robjects.r('eval_k_table'))

        ref_used = bool(self.robjects.r('eval_ref_used')[0])
        pac_from_stage2 = bool(self.robjects.r('eval_pac_from_stage2')[0])
        r_mode = str(self.robjects.r('as.character(analysis_mode)[1]')[0])
        # 样本/基因数直接取矩阵维度（数据通道，最可靠）
        n_genes = int(self.robjects.r('nrow(ccp_exprSet)')[0])
        n_samples = int(self.robjects.r('ncol(ccp_exprSet)')[0])

        def cell(row, col_name, fallback='NA'):
            if col_name not in k_table.columns or row >= len(k_table):
                return fallback
            return _fmt_eval_num(k_table.iloc[row][col_name])

        mode_label = '基因列表分型' if r_mode == 'signature' else '传统一致性聚类'
        pac_label = '阶段二（PAC 曲线）' if pac_from_stage2 \
            else '阶段四本地计算（与阶段二同一公式）'
        ref_col_label = eval_ref_col if (eval_ref_col and eval_ref_col != '不使用') else '不使用'

        lines = [
            '=== 基因面板 ===',
            f'模式: {mode_label}',
            f'使用基因数: {n_genes}',
            f'样本数: {n_samples}',
            f'参考分组列: {ref_col_label}',
            '',
            '=== 各 k 评估 ===',
            f'PAC 来源: {pac_label}',
            '\t'.join(['K', 'PAC', 'silhouette', 'minClusterSize', 'ARI', 'NMI', 'chisq_p']),
        ]
        for row in range(len(k_table)):
            k_val = k_table.iloc[row]['K']
            k_str = str(int(k_val)) if not pd.isna(k_val) else 'NA'
            size_val = cell(row, 'minClusterSize')
            size_str = 'NA' if size_val in ('NA', 'nan') else str(int(float(size_val)))
            lines.append('\t'.join([
                k_str,
                cell(row, 'PAC'),
                cell(row, 'silhouette'),
                size_str,
                cell(row, 'ARI'),
                cell(row, 'NMI'),
                cell(row, 'chisq_p'),
            ]))

        lines.append('')
        lines.append(f'=== 最终 k={final_k} 交叉表（参考分组 × 一致性分群）===')
        if ref_used:
            # R 侧回传的 matrix：行=参考分组，列=一致性分群（dimnames 是用户自己的标签）
            cross = self.robjects.r('eval_crosstab')
            matrix = np.asarray(cross)
            row_names = list(cross.names[0]) if cross.names and cross.names[0] is not None \
                else [f'row{i + 1}' for i in range(matrix.shape[0])]
            col_names = list(cross.names[1]) if len(cross.names) > 1 and cross.names[1] is not None \
                else [f'col{j + 1}' for j in range(matrix.shape[1])]
            lines.append('\t'.join([''] + [str(c) for c in col_names]))
            for ri in range(matrix.shape[0]):
                values = [str(int(v)) for v in matrix[ri]]
                lines.append('\t'.join([str(row_names[ri])] + values))
            final_ari = _fmt_eval_num(self.robjects.r('eval_final_ari')[0])
            final_nmi = _fmt_eval_num(self.robjects.r('eval_final_nmi')[0])
            final_p = _fmt_eval_num(self.robjects.r('eval_final_p')[0])
            lines.append(f'ARI = {final_ari} ; NMI = {final_nmi} ; 卡方 p = {final_p}')
        else:
            lines.append('参考分组: 未提供（跳过 ARI/NMI/卡方）')

        text = '\n'.join(lines) + '\n'
        text_dir = os.path.dirname(eval_text_path)
        if text_dir and not os.path.isdir(text_dir):
            os.makedirs(text_dir, exist_ok=True)
        # newline='' → 不做 \n → \r\n 转换，保证返回值与落盘内容逐字一致
        with io.open(eval_text_path, 'w', encoding='utf-8', newline='') as handle:
            handle.write(text)
        return text

    # ---------- R脚本和包加载 ----------

    def _load_r_script(self):
        if self._r_script_loaded:
            return True
        if not os.path.exists(self.R_SCRIPT_PATH):
            self._log_r_debug("load_r_script",
                              FileNotFoundError(f"R脚本不存在: {self.R_SCRIPT_PATH}"),
                              {"script_path": self.R_SCRIPT_PATH})
            return False
        self._r_script_loaded = True
        print(f"[R脚本检查] 脚本存在: {self.R_SCRIPT_PATH}")
        return True

    def _load_r_packages(self):
        if self._r_packages_loaded:
            return True
        if _importr is None:
            return False
        try:
            _importr('ConsensusClusterPlus')
            _importr('pheatmap')
            _importr('grDevices')
            self._r_packages_loaded = True
            print("[R包加载] ConsensusClusterPlus, pheatmap, grDevices 已通过importr加载")
            return True
        except Exception as e:
            self._log_r_debug("load_r_packages", e, {"importr": str(_importr)})
            return False

    # ---------- R 输出捕获（[VK] ASCII 协议 → Python 中文日志） ----------

    def _log_vk_lines(self, lines: List[str]) -> None:
        """把 R 的 [VK] 键值行翻译成中文日志（R 侧不能安全输出中文）"""
        for line in _r_output_lines(lines):
            line = line.strip()
            if not line.startswith('[VK]'):
                continue
            body = line[4:].strip()
            if not body:
                continue
            fields = body.split('|')
            key = fields[0].upper()
            kv = {}
            for item in fields[1:]:
                if '=' in item:
                    name, _, value = item.partition('=')
                    kv[name.strip().lower()] = value.strip()
            if key == 'SEED':
                print(f"[随机种子] set.seed({fields[1] if len(fields) > 1 else ''})")
            elif key == 'PANEL':
                mode_label = '基因列表分型' if kv.get('mode') == 'signature' else '传统一致性聚类'
                print(f"[基因面板] 模式={mode_label} | 最终使用 {kv.get('genes', '?')} 个基因")
            elif key == 'MADFILTER':
                print(f"[基因面板] 列表内 MAD 过滤：{fields[1]} -> {fields[2]} 个基因")
            elif key == 'FIXK':
                print(f"[固定k] 按用户指定固定 k={fields[1]}"
                      f"（PAC 最优为 k={kv.get('pacbest', '?')}，仅作参考）")
            elif key == 'EVAL':
                pac_src = '阶段二（PAC 曲线）' if kv.get('pac_src') == 'stage2' \
                    else '阶段四本地计算（与阶段二同一公式）'
                print(f"[阶段四] PAC 来源={pac_src} | 轮廓系数={'开' if kv.get('silhouette') == 'on' else '关'}"
                      f" | 基因热图={'开' if kv.get('heatmap') == 'on' else '关'}"
                      f" | 参考分组={'有' if kv.get('ref') == 'on' else '无'}")

    def _run_r_capture(self, r_code: str) -> List[str]:
        """执行 R 代码段，并把 R 侧 stdout（ASCII [VK] 行）读回 Python 侧打中文日志

        说明：rpy2 下 R 的 cat() 不经过 Python 的 sys.stdout，无法用 redirect_stdout 捕获，
        这里用 R 自己的 sink() 落盘再读回，避免污染用户控制台。
        """
        capture_path = os.path.join(tempfile.gettempdir(), '_vk_r_capture.log')
        if os.path.exists(capture_path):
            try:
                os.remove(capture_path)
            except OSError:
                pass
        self.robjects.r(
            f'sink("{capture_path.replace(chr(92), "/")}", split = FALSE, type = "output")')
        error = None
        try:
            self.robjects.r(r_code)
        except Exception as exc:
            error = exc
        finally:
            try:
                self.robjects.r('sink(type = "output")')
            except Exception:
                pass
        lines: List[str] = []
        if os.path.exists(capture_path):
            try:
                with io.open(capture_path, 'r', encoding='utf-8', errors='replace') as handle:
                    lines = handle.read().splitlines()
            except OSError:
                lines = []
        self._log_vk_lines(lines)
        if error is not None:
            raise error
        return lines

    def _read_stage_code(self, stage: str) -> str:
        """读取指定阶段的R代码段"""
        with open(self.R_SCRIPT_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        start_marker = f"# --- {stage}_BODY_START ---"
        end_marker = f"# --- {stage}_BODY_END ---"

        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if start_marker in line:
                start_idx = i + 1
            if end_marker in line:
                end_idx = i

        if start_idx is None or end_idx is None:
            raise RuntimeError(f"未找到标记行: {start_marker} / {end_marker}")

        if start_idx >= end_idx:
            raise RuntimeError(f"标记行顺序错误: {stage}")

        code = ''.join(lines[start_idx:end_idx]).strip()
        if not code:
            raise RuntimeError(f"提取的代码段为空: {stage}")
        return code

    # ---------- 数据准备 ----------

    def prepare_expr_data(self, filter1_col=None, filter1_groups=None,
                          filter2_col=None, filter2_groups=None,
                          clinical_col=None, clinical_groups=None) -> Optional[pd.DataFrame]:
        """从adata提取表达矩阵并应用筛选

        Returns:
            表达矩阵DataFrame（行为基因，列为样本）
        """
        if self.adata is None:
            return None

        # 获取表达矩阵并转置（adata.X是样本×基因，需要转成基因×样本）
        X = self.adata.X
        if hasattr(X, 'toarray'):
            X = X.toarray()
        df = pd.DataFrame(X.T, index=self.adata.var_names, columns=self.adata.obs_names)

        # 应用筛选条件
        selected_samples = df.columns.tolist()
        print(f"[数据准备] 初始样本数: {len(selected_samples)}")

        if clinical_col and clinical_groups and clinical_col in self.adata.obs.columns:
            mask = self.adata.obs.loc[selected_samples, clinical_col].astype(str).isin(clinical_groups)
            selected_samples = [s for s, m in zip(selected_samples, mask) if m]
            print(f"[数据准备] 分类列筛选后 ({clinical_col}): {len(selected_samples)} 样本")

        if filter1_col and filter1_groups and filter1_col in self.adata.obs.columns:
            mask = self.adata.obs.loc[selected_samples, filter1_col].astype(str).isin(filter1_groups)
            selected_samples = [s for s, m in zip(selected_samples, mask) if m]
            print(f"[数据准备] 筛选1后 ({filter1_col}): {len(selected_samples)} 样本")

        if filter2_col and filter2_groups and filter2_col in self.adata.obs.columns:
            mask = self.adata.obs.loc[selected_samples, filter2_col].astype(str).isin(filter2_groups)
            selected_samples = [s for s, m in zip(selected_samples, mask) if m]
            print(f"[数据准备] 筛选2后 ({filter2_col}): {len(selected_samples)} 样本")

        if len(selected_samples) < 3:
            print(f"[数据准备] 筛选后样本数不足3个，返回None")
            return None

        print(f"[数据准备] 最终样本数: {len(selected_samples)}")
        return df.loc[:, selected_samples]

    # ---------- 阶段一：聚类计算 ----------

    def run_stage1_cluster(self,
                           mad_threshold: int = 5000,
                           reps: int = 1000,
                           cluster_alg: str = "hc",
                           distance: str = "pearson",
                           p_item: float = 0.8,
                           p_feature: float = 1.0,
                           min_k: int = 2,
                           max_k: int = 9,
                           plot_format: str = "png",
                           filter1_col=None, filter1_groups=None,
                           filter2_col=None, filter2_groups=None,
                           clinical_col=None, clinical_groups=None,
                           mode: str = "traditional",
                           gene_list_file: str = "",
                           mad_filter_in_list: bool = False,
                           seed: int = 123456) -> bool:
        """阶段一：聚类计算

        mode: 'traditional'（MAD 前 N 基因）| 'signature'（外部基因列表）
        """
        # 契约 §8-G5：R 可用性/包/脚本 检查保持在数据准备之前（改造前顺序）
        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if not self._load_r_packages():
            raise RuntimeError("R包加载失败")

        if not self._load_r_script():
            raise RuntimeError("R脚本加载失败")

        # 准备数据
        expr_data = self.prepare_expr_data(
            filter1_col, filter1_groups,
            filter2_col, filter2_groups,
            clinical_col, clinical_groups
        )
        if expr_data is None:
            raise RuntimeError("数据准备失败，请检查筛选条件")

        # 契约 §4.2 步骤1：记录样本列顺序，供 get_ref_labels 对齐
        self._last_expr_columns = list(expr_data.columns)

        # 契约 §4.2 步骤2：signature 模式的基因列表处理
        # （缺列表文件的用户提示由 bind 层先给，这里只做兜底）
        mode_value = str(mode) if mode else "traditional"
        matched_genes: List[str] = []
        mad_filter_flag = bool(mad_filter_in_list)
        if mode_value == "signature":
            if not gene_list_file:
                raise RuntimeError("基因列表分型模式需要先选择基因列表文件")
            gene_list_path = self._norm_genelist_path(gene_list_file)
            if not os.path.exists(gene_list_path):
                raise RuntimeError(f"基因列表文件不存在: {gene_list_path}")

            gene_list = self.read_gene_list_file(gene_list_path)
            match_info = self.match_gene_list(gene_list, expr_data.index)
            matched_genes = list(match_info['matched'])
            n_list = match_info['n_list']
            n_dedup = match_info['n_dedup']
            n_matched = match_info['n_matched']

            print(f"[基因列表] 文件={gene_list_file} | 列表基因 {n_list} 个 | "
                  f"去重后 {n_dedup} 个 | 命中表达矩阵 {n_matched} 个")
            print(f"[基因面板] 模式=基因列表分型 | 使用 {n_matched} 个基因 | "
                  f"列表内MAD过滤={'开' if mad_filter_flag else '关'}")
            if match_info['case_hint']:
                print(f"[基因列表] {match_info['case_hint']}")

            if n_matched < 10:
                raise RuntimeError(
                    f"基因列表中在表达矩阵内命中的基因过少（{n_matched} 个，至少需要 10 个），"
                    f"请检查基因列表文件与基因名格式")

        # 创建临时目录
        self._temp_dir = tempfile.mkdtemp(prefix="ccp_")
        print(f"[阶段一] 临时目录: {self._temp_dir}")

        try:
            from rpy2.robjects import pandas2ri, StrVector, IntVector, FloatVector
            from rpy2.robjects.conversion import localconverter

            # 传递数据到R环境
            with localconverter(pandas2ri.converter):
                self.robjects.globalenv['expr_data'] = expr_data

            # 传递参数
            self.robjects.globalenv['mad_threshold'] = IntVector([int(mad_threshold)])
            self.robjects.globalenv['reps'] = IntVector([int(reps)])
            self.robjects.globalenv['cluster_alg'] = StrVector([cluster_alg])
            self.robjects.globalenv['distance'] = StrVector([distance])
            self.robjects.globalenv['p_item'] = FloatVector([float(p_item)])
            self.robjects.globalenv['p_feature'] = FloatVector([float(p_feature)])
            self.robjects.globalenv['min_k'] = IntVector([int(min_k)])
            self.robjects.globalenv['max_k'] = IntVector([int(max_k)])
            self.robjects.globalenv['plot_format'] = StrVector([plot_format])
            self.robjects.globalenv['title_dir'] = StrVector([self._temp_dir])

            # 契约 §4.2 步骤3：模式相关新参数
            self.robjects.globalenv['analysis_mode'] = StrVector([mode_value])
            self.robjects.globalenv['gene_list'] = StrVector([str(g) for g in matched_genes])
            self.robjects.globalenv['mad_filter_in_list'] = IntVector(
                [1 if mad_filter_flag else 0])
            self.robjects.globalenv['seed'] = IntVector([int(seed)])

            # 执行阶段一代码
            r_code = self._read_stage_code("STAGE1")
            self._run_r_capture(r_code)

            self._stage1_completed = True
            self._stage2_completed = False
            self._stage3_completed = False
            self._stage4_completed = False
            print(f"[阶段一] 聚类计算完成")
            return True

        except Exception as e:
            self._log_r_debug("stage1_cluster", e, {
                "mad_threshold": mad_threshold, "reps": reps,
                "cluster_alg": cluster_alg, "distance": distance,
                "min_k": min_k, "max_k": max_k,
                "mode": mode_value, "gene_list_file": gene_list_file,
                "mad_filter_in_list": mad_filter_flag, "seed": seed
            })
            raise RuntimeError(f"阶段一R代码执行失败: {_translate_r_error(str(e))}")

    # ---------- 阶段二：CDF + PAC曲线 ----------

    def run_stage2_cdf_pac(self, min_k: int = 2, max_k: int = 9,
                           output_path: str = None,
                           plot_width: float = 10, plot_height: float = 6,
                           fix_k_enable: bool = False,
                           fixed_k: int = None) -> tuple:
        """阶段二：生成CDF+PAC曲线

        fix_k_enable 为真时，R 端直接使用 fixed_k 作为最优 k（PAC 最优仅作参考）。
        """
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一聚类计算")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if output_path is None:
            output_path = os.path.join(self.dataset_output_dir or ".",
                                       f"{self.dataset_name}_cdf_pac.png")

        fixed_k_value = int(min_k) if fixed_k is None else int(fixed_k)

        try:
            from rpy2.robjects import StrVector, IntVector, FloatVector

            self.robjects.globalenv['min_k'] = IntVector([int(min_k)])
            self.robjects.globalenv['max_k'] = IntVector([int(max_k)])
            self.robjects.globalenv['output_path'] = StrVector([output_path])
            self.robjects.globalenv['plot_width'] = FloatVector([float(plot_width)])
            self.robjects.globalenv['plot_height'] = FloatVector([float(plot_height)])
            # 契约 §4.3：固定 k 支持
            self.robjects.globalenv['fix_k_enable'] = IntVector(
                [1 if fix_k_enable else 0])
            self.robjects.globalenv['fixed_k'] = IntVector([fixed_k_value])

            r_code = self._read_stage_code("STAGE2")
            self._run_r_capture(r_code)

            self._stage2_completed = True
            print(f"[阶段二] CDF+PAC曲线生成成功")

            # 获取最优k值
            try:
                opt_k = self.robjects.r('optimal_k')[0]
                print(f"[阶段二] 最优k值: {opt_k}")
                return output_path, int(opt_k)
            except:
                return output_path, None

        except Exception as e:
            self._log_r_debug("stage2_cdf_pac", e, {"output_path": output_path})
            raise RuntimeError(f"阶段二R代码执行失败: {_translate_r_error(str(e))}")

    # ---------- 阶段四：分型评估 + 基因表达热图 ----------

    def run_stage4_eval(self, min_k: int = 2, max_k: int = 9, final_k: int = 3,
                        eval_ref_col: str = "不使用",
                        ref_labels=None,
                        silhouette_enable: bool = True,
                        gene_heatmap_enable: bool = True,
                        gene_heatmap_max: int = 200,
                        eval_plot_path: str = None,
                        gene_heatmap_path: str = None,
                        eval_text_path: str = None,
                        color_scheme: str = "blue",
                        heatmap_width: float = 8, heatmap_height: float = 8,
                        title_font_size: int = 14, legend_font_size: int = 12,
                        clustering_method: str = "average") -> dict:
        """阶段四：分型评估（轮廓系数/ARI/NMI/卡方）+ signature 基因表达热图

        eval_ref_col: 仅用于评估文本里的「参考分组列: …」回显。
        ref_labels:   参考分组标签（与样本数对齐）；None 视为空（不做 ARI/NMI/卡方）。
                      是否计算 ARI/NMI/卡方只看 ref_labels 是否为空，与 eval_ref_col 解耦。

        Returns:
            {'eval_plot': str, 'gene_heatmap': str|None, 'eval_text': str}
        """
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一聚类计算")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        min_k_value = int(min_k)
        max_k_value = int(max_k)
        final_k_value = int(final_k)
        if final_k_value < min_k_value or final_k_value > max_k_value:
            raise RuntimeError(
                f"选定 k={final_k_value} 不在 K 范围 {min_k_value}~{max_k_value} 内")

        base_dir = self._temp_dir or "."
        dataset_name = self.dataset_name or "bulk_cluster"

        if eval_plot_path is None:
            eval_plot_path = os.path.join(base_dir, f"{dataset_name}_eval.png")
        if eval_text_path is None:
            eval_text_path = os.path.join(base_dir, f"{dataset_name}_eval.txt")

        need_heatmap = bool(gene_heatmap_enable)
        if not need_heatmap:
            gene_heatmap_path = None
        elif gene_heatmap_path is None:
            gene_heatmap_path = os.path.join(
                base_dir, f"{dataset_name}_gene_heatmap.png")

        # 参考分组标签：None → 空（视为未提供，不计算 ARI/NMI/卡方）
        if ref_labels is None:
            ref_label_values = []
        else:
            ref_label_values = [str(v) for v in ref_labels]

        # 契约裁决④：廉价保险——ref_labels 与 STAGE1 记录的样本列序必须等长
        if ref_label_values:
            n_expected = len(self._last_expr_columns)
            if len(ref_label_values) != n_expected:
                raise RuntimeError(
                    f"参考分组标签数（{len(ref_label_values)}）与样本数（{n_expected}）不一致")

        try:
            from rpy2.robjects import StrVector, IntVector, FloatVector

            self.robjects.globalenv['min_k'] = IntVector([min_k_value])
            self.robjects.globalenv['max_k'] = IntVector([max_k_value])
            self.robjects.globalenv['final_k'] = IntVector([final_k_value])
            self.robjects.globalenv['eval_ref_col'] = StrVector([str(eval_ref_col or "不使用")])
            self.robjects.globalenv['ref_labels'] = StrVector(ref_label_values)
            self.robjects.globalenv['silhouette_enable'] = IntVector(
                [1 if silhouette_enable else 0])
            self.robjects.globalenv['gene_heatmap_enable'] = IntVector(
                [1 if need_heatmap else 0])
            self.robjects.globalenv['gene_heatmap_max'] = IntVector([int(gene_heatmap_max)])
            self.robjects.globalenv['eval_plot_path'] = StrVector([eval_plot_path])
            self.robjects.globalenv['gene_heatmap_path'] = StrVector(
                [gene_heatmap_path or ""])
            self.robjects.globalenv['eval_text_path'] = StrVector([eval_text_path])
            self.robjects.globalenv['color_scheme'] = StrVector([color_scheme])
            self.robjects.globalenv['heatmap_width'] = FloatVector([float(heatmap_width)])
            self.robjects.globalenv['heatmap_height'] = FloatVector([float(heatmap_height)])
            self.robjects.globalenv['title_font_size'] = IntVector([int(title_font_size)])
            self.robjects.globalenv['legend_font_size'] = IntVector([int(legend_font_size)])
            self.robjects.globalenv['clustering_method'] = StrVector([clustering_method])

            r_code = self._read_stage_code("STAGE4")
            self._run_r_capture(r_code)

            self._stage4_completed = True
            print(f"[阶段四] 分型评估完成 (final_k={final_k_value})")

            try:
                # 文本由 Python 生成并落盘（R 只回传纯数据）
                eval_text = self._collect_stage4_eval_text(
                    eval_text_path, final_k_value, eval_ref_col)
                return {
                    'eval_plot': eval_plot_path,
                    'gene_heatmap': gene_heatmap_path if need_heatmap else None,
                    'eval_text': eval_text,
                }
            except Exception as read_error:
                self._log_r_debug("stage4_read_text", read_error,
                                  {"eval_text_path": eval_text_path})
                raise RuntimeError(f"阶段四评估文本生成失败: {str(read_error)}")

        except Exception as e:
            self._log_r_debug("stage4_eval", e, {
                "min_k": min_k_value, "max_k": max_k_value, "final_k": final_k_value,
                "eval_ref_col": eval_ref_col,
                "silhouette_enable": silhouette_enable,
                "gene_heatmap_enable": need_heatmap,
                "eval_plot_path": eval_plot_path,
                "gene_heatmap_path": gene_heatmap_path,
                "eval_text_path": eval_text_path
            })
            raise RuntimeError(f"阶段四R代码执行失败: {_translate_r_error(str(e))}")

    # ---------- 阶段三：最终热图 ----------

    def run_stage3_heatmap(self,
                           final_k: int,
                           output_mode: int = 1,
                           output_path: str = None,
                           heatmap_width: float = 8,
                           heatmap_height: float = 8,
                           color_scheme: str = "blue",
                           title_font_size: int = 14,
                           legend_font_size: int = 12,
                           clustering_method: str = "average") -> str:
        """阶段三：生成最终选定k值的热图"""
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一聚类计算")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if output_path is None:
            output_path = os.path.join(self.dataset_output_dir or ".",
                                       f"{self.dataset_name}_heatmap_k{final_k}.png")

        try:
            from rpy2.robjects import StrVector, IntVector, FloatVector

            self.robjects.globalenv['final_k'] = IntVector([int(final_k)])
            self.robjects.globalenv['output_mode'] = IntVector([int(output_mode)])
            self.robjects.globalenv['output_path'] = StrVector([output_path])
            self.robjects.globalenv['heatmap_width'] = FloatVector([float(heatmap_width)])
            self.robjects.globalenv['heatmap_height'] = FloatVector([float(heatmap_height)])
            self.robjects.globalenv['color_scheme'] = StrVector([color_scheme])
            self.robjects.globalenv['title_font_size'] = IntVector([int(title_font_size)])
            self.robjects.globalenv['legend_font_size'] = IntVector([int(legend_font_size)])
            self.robjects.globalenv['clustering_method'] = StrVector([clustering_method])

            r_code = self._read_stage_code("STAGE3")
            self.robjects.r(r_code)

            self._stage3_completed = True
            print(f"[阶段三] 最终热图(k={final_k})生成成功")
            return output_path

        except Exception as e:
            self._log_r_debug("stage3_heatmap", e, {
                "final_k": final_k, "output_mode": output_mode,
                "output_path": output_path
            })
            raise RuntimeError(f"阶段三R代码执行失败: {str(e)}")

    # ---------- 保存聚类结果到adata ----------

    def save_consensus_to_adata(self, final_k: int, is_filtered: bool = False) -> str:
        """将选定k值的聚类结果写入adata.obs

        Args:
            final_k: 选定的k值
            is_filtered: 是否使用了筛选条件（True则列名加_typed后缀）

        Returns:
            写入的列名
        """
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一聚类计算")

        if not self.robjects or self.adata is None:
            raise RuntimeError("R环境或adata不可用")

        try:
            from rpy2.robjects import pandas2ri
            from rpy2.robjects.conversion import localconverter

            consensus_class_r = self.robjects.r(
                f'ccp_results[[{final_k}]][["consensusClass"]]'
            )

            sample_names = list(consensus_class_r.names)
            cluster_labels = [f'Cluster{int(c)}' for c in list(consensus_class_r)]

            col_name = f'consensus_k{final_k}_output'
            if is_filtered:
                col_name += '_typed'

            if col_name not in self.adata.obs.columns:
                self.adata.obs[col_name] = pd.NA
                self.adata.obs[col_name] = self.adata.obs[col_name].astype('object')

            for sample, label in zip(sample_names, cluster_labels):
                if sample in self.adata.obs.index:
                    self.adata.obs.loc[sample, col_name] = label

            print(f"[聚类结果] 已写入adata.obs['{col_name}']，共{len(sample_names)}个样本")
            return col_name

        except Exception as e:
            self._log_r_debug("save_consensus_to_adata", e, {"final_k": final_k, "is_filtered": is_filtered})
            raise RuntimeError(f"保存聚类结果到adata失败: {str(e)}")

    # ---------- 导出h5ad ----------

    def export_h5ad(self, save_path: str) -> bool:
        """导出带聚类结果的adata为h5ad文件

        Args:
            save_path: 保存路径

        Returns:
            是否成功
        """
        if self.adata is None:
            raise RuntimeError("未加载数据")

        try:
            self.adata.write_h5ad(save_path)
            print(f"[h5ad导出] 成功: {save_path}")
            return True
        except Exception as e:
            print(f"[h5ad导出] 失败: {e}")
            raise RuntimeError(f"h5ad导出失败: {str(e)}")

    # ---------- 导出CSV ----------

    def export_csv(self, final_k: int, save_path: str) -> bool:
        """导出选定k值的一致性矩阵和聚类归属为CSV"""
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一聚类计算")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        try:
            # 从R环境获取一致性矩阵和聚类归属
            consensus_matrix_r = self.robjects.r(
                f'ccp_results[[{final_k}]][["consensusMatrix"]]'
            )
            consensus_class_r = self.robjects.r(
                f'ccp_results[[{final_k}]][["consensusClass"]]'
            )

            # 转换为pandas
            from rpy2.robjects import pandas2ri
            from rpy2.robjects.conversion import localconverter

            with localconverter(pandas2ri.converter):
                matrix_df = pd.DataFrame(consensus_matrix_r)
                class_df = pd.DataFrame({
                    'Sample': list(consensus_class_r.names),
                    'Cluster': [f'Cluster{int(c)}' for c in list(consensus_class_r)]
                })

            # 合并写入CSV（两个表用空行分隔）
            with open(save_path, 'w', encoding='utf-8-sig') as f:
                f.write(f"# Consensus Matrix (K={final_k})\n")
                matrix_df.to_csv(f, index=False)
                f.write("\n# Cluster Assignment\n")
                class_df.to_csv(f, index=False)

            print(f"[CSV导出] 成功: {save_path}")
            return True

        except Exception as e:
            self._log_r_debug("export_csv", e, {"final_k": final_k, "save_path": save_path})
            raise RuntimeError(f"CSV导出失败: {str(e)}")

    # ---------- 清理 ----------

    def cleanup(self):
        """清理临时目录"""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                print(f"[清理] 临时目录已删除: {self._temp_dir}")
            except Exception as e:
                print(f"[清理] 删除临时目录失败: {e}")
            self._temp_dir = None

    def get_stage_status(self):
        """获取各阶段完成状态"""
        return {
            'stage1': self._stage1_completed,
            'stage2': self._stage2_completed,
            'stage3': self._stage3_completed,
            'stage4': self._stage4_completed
        }


# 单例模式
_instance = None

def get_bulk_cluster_analysis() -> BulkClusterAnalysis:
    global _instance
    if _instance is None:
        _instance = BulkClusterAnalysis()
    return _instance
