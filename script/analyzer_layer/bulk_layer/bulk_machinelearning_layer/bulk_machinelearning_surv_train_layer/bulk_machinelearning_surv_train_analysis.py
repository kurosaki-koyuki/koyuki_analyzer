# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 生存训练类(surv_train)子层核心算法层

职责：
- 读取 loading 层产物（去批次表达矩阵 + 临床信息）
- 从各数据集 h5ad 的 obs 提取生存信息（time/status），生成 surv_meta.txt
- 通过 subprocess 调用 R 脚本，分 4 个阶段执行生存分析：
    stage1 数据准备（合成训练矩阵 + 基因集过滤 + 数据集拆分 + 标准化 + 生存表对齐）
    stage2 算法建模（各算法用 event 二分类提取选中基因）
    stage3 生存分析（单变量Cox筛显著 -> 多变量Cox -> 三队列iAUC+C-index -> 排序 + iAUC热图）
    stage4 最优基因（最优算法 + 其生存意义基因单变量Cox表）
- 输出目录：OUT_BASE/machinelearning/surv_train/
"""

from script.utils_layer.import_config import os, pd, np, traceback, APPDATA_PATH, BULK_SCAN_DATA_PATH, OUT_BASE, get_r_script_path
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class BulkMachineLearningSurvTrainAnalysis:
    """机器学习生存训练类分析层"""

    # loading 产物目录名（OUT_BASE 之下）
    LOADING_DIR_NAME = "machinelearning/loading"
    # 输出目录名（OUT_BASE 之下）
    OUT_DIR_NAME = "machinelearning/surv_train"
    # loading 产物文件名
    COMBAT_EXPR_FILE = "combat_corrected_exprdata.txt"
    CLINICAL_FILE = "merged_clinical.txt"
    # surv_meta 输出文件名（写入 out_dir，供 R 阶段一读取）
    SURV_META_FILE = "surv_meta.txt"
    # 生存列名
    TIME_COLUMN = "time (month)"
    STATUS_COLUMN = "state"
    # APPDATA 下基因集目录与机器学习资源目录
    GENELIST_DIR = os.path.join(APPDATA_PATH, "genelists")
    ML_RESOURCE_DIR = os.path.join(APPDATA_PATH, "machinelearning")
    # 阶段名
    STAGES = {
        "stage1": "数据准备",
        "stage2": "批量建模(算法选基因)",
        "stage3": "生存分析(iAUC热图)",
        "stage4": "最优基因",
    }
    # 默认参数
    DEFAULT_MAX_GENES = 1000
    DEFAULT_SEED = 1234
    DEFAULT_MAX_FEATURES = 50
    DEFAULT_TOP_FRAC = 0.3
    DEFAULT_PLOT_WIDTH_CM = 12     # 热图设备宽度(cm)
    DEFAULT_PLOT_HEIGHT_CM = 8     # 热图设备高度(cm)
    # iAUC 生存评价时间点（月）。必须显式传给 R 脚本的 args[13]：
    # R 侧按 <...> <top_frac> <time_points> <plot_width_cm> <plot_height_cm> 解析，
    # 此前 Python 只送 14 个实参（从 time_points 的位置起就整串错位），
    # 导致 time_points 取到热图宽度、宽度取到高度、高度永远走默认值。
    DEFAULT_TIME_POINTS = "6,12,24,36"

    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.pandas2ri = None
        self._init_r_environment()
        # R 脚本路径
        self.R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_machinelearning_surv_train.R")

    def _init_r_environment(self):
        """初始化 R 环境（用于 is_r_available 检查）"""
        if self.r_interface.is_r_available():
            self.robjects = self.r_interface.get_robjects()
            self.pandas2ri = self.r_interface.get_pandas2ri()
        else:
            saved_path = self.r_interface._load_saved_r_path()
            if saved_path:
                success = self.r_interface.set_r_path(saved_path)
                if success:
                    self.robjects = self.r_interface.get_robjects()
                    self.pandas2ri = self.r_interface.get_pandas2ri()

    def is_r_available(self):
        """检查 R 环境是否可用"""
        if self.robjects is not None:
            return True
        saved_path = self.r_interface._load_saved_r_path()
        if saved_path:
            try:
                success = self.r_interface.set_r_path(saved_path)
                if success:
                    self.robjects = self.r_interface.get_robjects()
                    self.pandas2ri = self.r_interface.get_pandas2ri()
            except Exception:
                pass
        return self.robjects is not None

    # ============================================================
    # 路径与产物查找
    # ============================================================

    def get_loading_dir(self, main_analysis=None):
        """获取 loading 产物目录"""
        if main_analysis is not None:
            merged_dir = getattr(main_analysis, 'merged_output_dir', None)
            if merged_dir and os.path.isdir(merged_dir):
                return merged_dir
        return os.path.join(OUT_BASE, self.LOADING_DIR_NAME)

    def get_out_dir(self):
        """获取 surv_train 输出目录并创建"""
        out_dir = os.path.join(OUT_BASE, self.OUT_DIR_NAME)
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    #: 阶段四主产物（**旧口径优先级最高**）
    BEST_GENE_FILE = "surv_best_gene_list.txt"
    #: 旧版/按方法分文件的产物前缀
    METHOD_GENE_PREFIX = "best_method_genes_"
    METHOD_GENE_SUFFIX = ".txt"

    def get_gene_list(self, file_name):
        """读**单个**输出文件的第一列 → 基因名列表（不存在/空 → []）。

        与 `export_gene_list_csv` 同一份产物；按无表头口径读（首格是 `Gene`/`Symbol`
        表头时跳过）。
        """
        if not file_name:
            return []
        try:
            out_dir = self.get_out_dir()
        except Exception:
            return []
        src = os.path.join(out_dir, file_name)
        if not os.path.exists(src):
            return []
        try:
            from script.analyzer_layer.bulk_layer.bulk_gene_set_utils import (
                read_gene_list_first_column, drop_gene_header_token,
            )
            genes = drop_gene_header_token(read_gene_list_first_column(src))
            return [str(g).strip() for g in genes if str(g).strip()]
        except Exception:
            return []

    def list_gene_subsets(self):
        """当前结果里**真实存在**的基因子集：`[(标签, 基因列表), ...]`（保序）。

        顺序 = 旧口径优先级：先 `surv_best_gene_list.txt`，再按方法名排序的
        `best_method_genes_<方法>.txt`（旧版按方法分别输出的产物）。
        宁少勿假：文件不在就不列出这个子集。
        """
        names = []
        if os.path.exists(os.path.join(self.get_out_dir(), self.BEST_GENE_FILE)):
            names.append(("最优基因集", self.BEST_GENE_FILE))
        try:
            import glob
            for p in sorted(glob.glob(os.path.join(self.get_out_dir(),
                                                   self.METHOD_GENE_PREFIX + "*" + self.METHOD_GENE_SUFFIX))):
                base = os.path.basename(p)
                method = base[len(self.METHOD_GENE_PREFIX):-len(self.METHOD_GENE_SUFFIX)]
                names.append(("方法最优基因：%s" % method, base))
        except Exception:
            pass

        out = []
        for label, name in names:
            genes = self.get_gene_list(name)
            if genes:
                out.append((label, genes))
        return out

    def get_final_gene_names(self):
        """旧口径（施工前的行为）：按 `list_gene_subsets()` 顺序取**第一个非空**文件的基因名。

        与 `export_gene_list_csv` 同一份输出文件；取不到 → []。
        """
        for _label, genes in self.list_gene_subsets():
            return genes
        return []

    def _scan_dir(self, dir_path, exts):
        """扫描目录下指定后缀的文件名列表（供 UI 下拉框）"""
        if not os.path.isdir(dir_path):
            return []
        try:
            return sorted([f for f in os.listdir(dir_path)
                           if f.lower().endswith(exts)])
        except Exception:
            return []

    def list_gene_files(self):
        """列出基因集目录中的所有基因集文件"""
        return self._scan_dir(self.GENELIST_DIR, ('.xlsx', '.xls', '.txt', '.csv'))

    def list_methods_files(self):
        """列出机器学习资源目录中的所有算法组合文件"""
        return self._scan_dir(self.ML_RESOURCE_DIR, ('.txt',))

    @staticmethod
    def _ascii_safe_path(src_path, ascii_name):
        """若路径含非 ASCII 字符，则把文件复制到指定 ASCII 位置并返回"""
        if not src_path:
            return "NONE"
        if src_path.isascii():
            return src_path
        import shutil
        target_dir = os.path.join(OUT_BASE, "machinelearning", "surv_train", "_input_")
        target = os.path.join(target_dir, ascii_name)
        try:
            os.makedirs(target_dir, exist_ok=True)
            shutil.copyfile(src_path, target)
            return target
        except Exception:
            return src_path

    def detect_gene_file(self, main_analysis=None):
        """获取用户在下拉框选择的基因集文件（含中文则复制为 ASCII 名路径）"""
        if main_analysis is not None:
            sel = getattr(main_analysis, 'surv_train_gene_file', "")
            if sel and sel != "不使用基因集":
                path = os.path.join(self.GENELIST_DIR, sel)
                if os.path.exists(path):
                    ext = os.path.splitext(path)[1] or ".txt"
                    return self._ascii_safe_path(path, "gene_set_input" + ext.lower())
        return "NONE"

    def detect_methods_file(self, main_analysis=None):
        """获取用户在下拉框选择的算法组合文件（返回绝对路径）"""
        if main_analysis is not None:
            sel = getattr(main_analysis, 'surv_train_methods_file', "")
            if sel:
                path = os.path.join(self.ML_RESOURCE_DIR, sel)
                if os.path.exists(path):
                    return path
        return "NONE"

    def detect_max_genes(self, main_analysis=None):
        """获取高变异基因截断数参数"""
        v = getattr(main_analysis, 'surv_train_max_genes', None) if main_analysis is not None else None
        try:
            val = int(v) if v else self.DEFAULT_MAX_GENES
        except Exception:
            val = self.DEFAULT_MAX_GENES
        return max(50, val)

    def detect_seed(self, main_analysis=None):
        """获取随机种子参数"""
        v = getattr(main_analysis, 'surv_train_seed', None) if main_analysis is not None else None
        try:
            val = int(v) if v else self.DEFAULT_SEED
        except Exception:
            val = self.DEFAULT_SEED
        return max(1, val)

    def detect_max_features(self, main_analysis=None):
        """获取每个算法提取基因数上限"""
        v = getattr(main_analysis, 'surv_train_max_features', None) if main_analysis is not None else None
        try:
            val = int(v) if v else self.DEFAULT_MAX_FEATURES
        except Exception:
            val = self.DEFAULT_MAX_FEATURES
        return max(3, val)

    def detect_top_frac(self, main_analysis=None):
        """获取重要性Top-N比例"""
        v = getattr(main_analysis, 'surv_train_top_frac', None) if main_analysis is not None else None
        try:
            val = float(v) if v is not None and v != "" else self.DEFAULT_TOP_FRAC
        except Exception:
            val = self.DEFAULT_TOP_FRAC
        if val <= 0 or val > 1:
            val = self.DEFAULT_TOP_FRAC
        return val

    def detect_plot_width_cm(self, main_analysis=None):
        """获取热图设备宽度(cm)"""
        v = getattr(main_analysis, 'surv_train_plot_width_cm', None) if main_analysis is not None else None
        try:
            val = float(v) if v is not None and v != "" else self.DEFAULT_PLOT_WIDTH_CM
        except Exception:
            val = self.DEFAULT_PLOT_WIDTH_CM
        return val if val > 0 else self.DEFAULT_PLOT_WIDTH_CM

    def detect_plot_height_cm(self, main_analysis=None):
        """获取热图设备高度(cm)"""
        v = getattr(main_analysis, 'surv_train_plot_height_cm', None) if main_analysis is not None else None
        try:
            val = float(v) if v is not None and v != "" else self.DEFAULT_PLOT_HEIGHT_CM
        except Exception:
            val = self.DEFAULT_PLOT_HEIGHT_CM
        return val if val > 0 else self.DEFAULT_PLOT_HEIGHT_CM

    def detect_time_points(self, main_analysis=None):
        """获取 iAUC 生存评价时间点(月)，返回逗号分隔字符串

        UI 目前没有该参数，故默认返回 DEFAULT_TIME_POINTS("6,12,24,36")；
        若将来 main_analysis 提供 surv_train_time_points，则优先采用。
        返回逗号分隔字符串以保持与 R 侧 args[13] 的 strsplit(args[13], ",") 契约一致。
        """
        v = getattr(main_analysis, 'surv_train_time_points', None) if main_analysis is not None else None
        if v is None or v == "":
            return self.DEFAULT_TIME_POINTS
        # 允许 list/tuple 或 "6,12" 字符串两种形式，统一成逗号分隔字符串
        try:
            if isinstance(v, (list, tuple)):
                parts = [str(float(x)) for x in v]
            else:
                parts = [str(float(x)) for x in str(v).replace(";", ",").split(",") if str(x).strip() != ""]
            parts = [p[:-2] if p.endswith(".0") else p for p in parts]
            return ",".join(parts) if parts else self.DEFAULT_TIME_POINTS
        except Exception:
            return self.DEFAULT_TIME_POINTS

    # ============================================================
    # 生存信息提取（Py 端：从各数据集 h5ad obs 提取 time/status）
    # ============================================================

    def _extract_surv_meta(self, loading_dir):
        """从 combat 表达列名 + 各数据集 h5ad obs 提取生存信息

        Returns:
            (success, surv_df, cohorts, error)
            surv_df: 列 sample(表达矩阵列名), time, status, cohort
        """
        # 1. 读取 combat 表达列名为 sample
        expr_path = os.path.join(loading_dir, self.COMBAT_EXPR_FILE)
        if not os.path.exists(expr_path):
            return False, None, [], f"去批次表达矩阵缺失: {expr_path}"
        # 仅读表头（第一行）获取样本列名，避免读全矩阵
        header = pd.read_csv(expr_path, sep="\t", nrows=0)
        samples = [c for c in header.columns if c != "Gene"]
        if not samples:
            return False, None, [], "表达矩阵无样本列"

        # 2. 每个样本归属的数据集（含"__"取前缀，否则取第一个"_"前）
        def _cohort_of(s):
            if "__" in s:
                return s.split("__")[0]
            return s.split("_")[0]

        # 3. 聚类唯一数据集
        cohorts = []
        for s in samples:
            c = _cohort_of(s)
            if c not in cohorts:
                cohorts.append(c)

        # 4. 扫描 h5ad 文件，读取 obs 生存列
        #    对每个 cohort 找到承载其样本的 h5ad（h5ad 文件名去后缀与 cohort 前缀匹配，或检测其 obs 含样本）
        if not os.path.isdir(BULK_SCAN_DATA_PATH):
            return False, None, cohorts, f"h5ad 目录不存在: {BULK_SCAN_DATA_PATH}"
        import anndata as ad
        h5ads = sorted([f for f in os.listdir(BULK_SCAN_DATA_PATH) if f.endswith('.h5ad')])

        # 构建 cohort -> {'obs':, 't_col':, 's_col':}
        cohort_info = {}
        missing_time_cols = []
        for cohort in cohorts:
            target = None
            # 优先文件名去后缀 == cohort（如 CGGA325_TPM.h5ad <-> CGGA325_TPM）
            for fn in h5ads:
                if os.path.splitext(fn)[0] == cohort:
                    target = fn
                    break
            obs = None
            if target:
                try:
                    obs = ad.read_h5ad(os.path.join(BULK_SCAN_DATA_PATH, target)).obs
                except Exception:
                    obs = None
            # 退化：若未匹配到文件，找任意一个 obs 含该 cohort 首个样本的文件
            if obs is None:
                probe = next((s for s in samples if _cohort_of(s) == cohort), None)
                simple_probe = probe.split("__")[-1] if probe else None
                for fn in h5ads:
                    try:
                        o2 = ad.read_h5ad(os.path.join(BULK_SCAN_DATA_PATH, fn)).obs
                        if simple_probe and simple_probe in o2.index:
                            obs = o2
                            break
                    except Exception:
                        continue
            t_col = None
            if obs is not None:
                t_col = self.TIME_COLUMN if self.TIME_COLUMN in obs.columns else \
                        ("time" if "time" in obs.columns else None)
                if t_col is None:
                    missing_time_cols.append(cohort)
            s_col = (self.STATUS_COLUMN if obs is not None and self.STATUS_COLUMN in obs.columns else None)
            cohort_info[cohort] = {'obs': obs, 't_col': t_col, 's_col': s_col}

        # 逐样本提取 time/status
        rows = []
        for s in samples:
            cohort = _cohort_of(s)
            simple = s.split("__")[-1]
            ci = cohort_info.get(cohort, {'obs': None, 't_col': None, 's_col': None})
            obs, t_col, s_col = ci['obs'], ci['t_col'], ci['s_col']
            t, st = np.nan, np.nan
            if obs is not None and simple in obs.index and t_col is not None:
                t = pd.to_numeric(obs.at[simple, t_col], errors="coerce")
                st = pd.to_numeric(obs.at[simple, s_col], errors="coerce") if s_col else np.nan
            rows.append({"sample": s, "time": t, "status": st, "cohort": cohort})

        surv_df = pd.DataFrame(rows)
        # 过滤掉 time/status 全缺失的 sample（无法生存分析）
        surv_df = surv_df.dropna(subset=["time", "status"])
        if len(surv_df) == 0:
            detail = ("；含时间列的数据集: " + ",".join(sorted(set(missing_time_cols)))) if missing_time_cols else ""
            return False, None, cohorts, f"所有样本均缺失有效生存信息(time/status){detail}。\n请检查各数据集 h5ad obs 是否含 '{self.TIME_COLUMN}' 与 '{self.STATUS_COLUMN}' 列。"
        return True, surv_df, cohorts, ""

    def extract_and_save_surv_meta(self, main_analysis=None, progress_callback=None):
        """提取生存信息并写入 out_dir/surv_meta.txt

        Returns:
            (success, surv_meta_path, info, error)
        """
        loading_dir = self.get_loading_dir(main_analysis)
        out_dir = self.get_out_dir()
        if progress_callback:
            progress_callback("input", f"提取生存信息：读取 loading 产物目录 {loading_dir}")
        ok, surv_df, cohorts, err = self._extract_surv_meta(loading_dir)
        if not ok:
            return False, "", {}, err
        surv_path = os.path.join(out_dir, self.SURV_META_FILE)
        surv_df.to_csv(surv_path, sep="\t", index=False)
        if progress_callback:
            progress_callback("input", (
                f"生存信息已提取: {len(surv_df)} 样本, 数据集: {','.join(cohorts)}\n"
                f"事件数量(status=1): {int((surv_df['status']==1).sum())}\n"
                f"写出: {surv_path}"
            ))
        return True, surv_path, {"cohorts": cohorts, "n_samples": len(surv_df)}, ""

    # ============================================================
    # 通用 Rscript 调用
    # ============================================================

    def _resolve_rscript(self):
        """解析 Rscript 可执行文件路径"""
        r_path = self.r_interface.get_r_path()
        if not r_path:
            r_home = os.environ.get('R_HOME')
            if r_home:
                r_path = r_home
        if not r_path or not os.path.exists(r_path):
            return None
        rscript_exe = os.path.join(r_path, "bin", "Rscript.exe")
        if os.path.exists(rscript_exe):
            return rscript_exe
        alt = os.path.join(r_path, "bin", "Rscript")
        return alt if os.path.exists(alt) else None

    def _run_r(self, stage, work_dir, expr_file, clinical_file, out_dir,
               gene_file, surv_meta_file, methods_file="NONE", max_genes=None,
               seed=None, max_features=None, top_frac=None,
               time_points=None,
               plot_width_cm=None, plot_height_cm=None,
               progress_callback=None):
        """调用 R 脚本执行指定阶段"""
        try:
            if not self.is_r_available():
                return False, {}, "R 环境不可用，请在设置中配置 R 内核路径"
            if not os.path.exists(self.R_SCRIPT_PATH):
                return False, {}, f"R 脚本不存在: {self.R_SCRIPT_PATH}"
            rscript_exe = self._resolve_rscript()
            if not rscript_exe:
                return False, {}, "未找到 Rscript 可执行文件"

            import subprocess
            cmd = [
                rscript_exe, self.R_SCRIPT_PATH,
                stage, work_dir, expr_file, clinical_file, out_dir,
                gene_file, surv_meta_file,
                methods_file,
                str(max_genes), str(seed), str(max_features), str(top_frac),
                str(time_points),
                str(plot_width_cm), str(plot_height_cm),
            ]
            if progress_callback:
                progress_callback(stage, f"调用 Rscript({self.STAGES.get(stage, stage)}): "
                                          f"{os.path.basename(rscript_exe)} ...")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        timeout=7200, encoding='utf-8', errors='replace')
            except subprocess.TimeoutExpired:
                return False, {}, f"{self.STAGES.get(stage, stage)} 执行超时（>2 小时）"
            except Exception as e:
                return False, {}, f"调用 Rscript 失败: {str(e)}"

            if result.returncode != 0:
                err_msg = (result.stderr or '').strip() or 'R 脚本执行失败（无 stderr）'
                if progress_callback and result.stderr:
                    progress_callback(stage, f"R 脚本 stderr:\n{result.stderr[-1200:]}")
                return False, {}, f"{self.STAGES.get(stage, stage)} 失败: {err_msg}"

            if progress_callback and result.stdout:
                progress_callback(stage, f"R 脚本输出:\n{result.stdout[-900:]}")
            return True, {"stdout": result.stdout}, ""
        except Exception as e:
            traceback.print_exc()
            return False, {}, f"{self.STAGES.get(stage, stage)} 失败: {str(e)}"

    # ============================================================
    # 各阶段入口
    # ============================================================

    def _prepare_inputs(self, main_analysis=None, progress_callback=None):
        """准备各阶段通用输入参数

        Returns:
            (success, params_dict, error)
        """
        loading_dir = self.get_loading_dir(main_analysis)
        if progress_callback:
            progress_callback("input", f"读取数据来源(loading产物)目录: {loading_dir}")
        if not os.path.isdir(loading_dir):
            return False, {}, f"loading 产物目录不存在: {loading_dir}\n请先运行「数据加载类」生成去批次数据"

        expr_path = os.path.join(loading_dir, self.COMBAT_EXPR_FILE)
        clin_path = os.path.join(loading_dir, self.CLINICAL_FILE)
        if not os.path.exists(expr_path):
            return False, {}, f"去批次表达矩阵缺失: {expr_path}\n请先运行「数据加载类」阶段二"
        if not os.path.exists(clin_path):
            return False, {}, f"同步临床信息缺失: {clin_path}\n请先运行「数据加载类」阶段三"

        out_dir = self.get_out_dir()
        # 提取生存信息并写入 out_dir/surv_meta.txt
        ok, surv_path, info, err = self.extract_and_save_surv_meta(main_analysis, progress_callback)
        if not ok:
            return False, {}, err

        gene_file = self.detect_gene_file(main_analysis) or "NONE"
        methods_file = self.detect_methods_file(main_analysis)
        max_genes = self.detect_max_genes(main_analysis)
        seed = self.detect_seed(main_analysis)
        max_features = self.detect_max_features(main_analysis)
        top_frac = self.detect_top_frac(main_analysis)
        plot_width_cm = self.detect_plot_width_cm(main_analysis)
        plot_height_cm = self.detect_plot_height_cm(main_analysis)
        time_points = self.detect_time_points(main_analysis)

        params = {
            'work_dir': loading_dir,
            'expr_file': self.COMBAT_EXPR_FILE,
            'clinical_file': self.CLINICAL_FILE,
            'out_dir': out_dir,
            'gene_file': gene_file,
            'surv_meta_file': self.SURV_META_FILE,
            'methods_file': methods_file,
            'max_genes': max_genes,
            'seed': seed,
            'max_features': max_features,
            'top_frac': top_frac,
            'time_points': time_points,
            'plot_width_cm': plot_width_cm,
            'plot_height_cm': plot_height_cm,
        }
        return True, params, ""

    def _common_run(self, stage, main_analysis=None, progress_callback=None):
        ok, params, err = self._prepare_inputs(main_analysis, progress_callback)
        if not ok:
            return False, {}, err
        return self._run_r(
            stage, params['work_dir'], params['expr_file'], params['clinical_file'],
            params['out_dir'], params['gene_file'], params['surv_meta_file'],
            params['methods_file'], params['max_genes'], params['seed'],
            params['max_features'], params['top_frac'],
            params['time_points'],
            params['plot_width_cm'], params['plot_height_cm'],
            progress_callback=progress_callback,
        )

    def run_stage1(self, main_analysis=None, progress_callback=None):
        """阶段一：数据准备"""
        return self._common_run("stage1", main_analysis, progress_callback)

    def run_stage2(self, main_analysis=None, progress_callback=None):
        """阶段二：批量建模（算法选基因）"""
        return self._common_run("stage2", main_analysis, progress_callback)

    def run_stage3(self, main_analysis=None, progress_callback=None):
        """阶段三：生存分析（Cox + iAUC + 热图 + 排序）"""
        return self._common_run("stage3", main_analysis, progress_callback)

    def run_stage4(self, main_analysis=None, progress_callback=None):
        """阶段四：最优基因"""
        return self._common_run("stage4", main_analysis, progress_callback)

    # ============================================================
    # 导出辅助
    # ============================================================

    def export_images_zip(self, ext='png', save_path=None):
        """将输出目录下所有指定扩展名图片打包为 zip"""
        import zipfile
        out_dir = self.get_out_dir()
        if not os.path.isdir(out_dir):
            return False, "", f"输出目录不存在: {out_dir}"
        ext = ext.strip().lower().lstrip('.')
        files = [f for f in os.listdir(out_dir)
                 if f.lower().endswith(f'.{ext}') and not os.path.isdir(os.path.join(out_dir, f))]
        if not files:
            return False, "", f"输出目录中未找到任何 .{ext} 图片文件: {out_dir}"
        if save_path is None:
            save_dir = os.path.join(out_dir, "export")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"all_images_{ext}.zip")
        try:
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for fn in files:
                    zf.write(os.path.join(out_dir, fn), arcname=fn)
            return True, save_path, ""
        except Exception as e:
            return False, "", f"打包 {ext} 图片失败: {str(e)}"

    def export_gene_list_csv(self, save_path=None, source_file_name="surv_best_gene_list.txt"):
        """将阶段四最优基因表导出为 csv"""
        out_dir = self.get_out_dir()
        if not os.path.isdir(out_dir):
            return False, "", f"输出目录不存在: {out_dir}"
        src = os.path.join(out_dir, source_file_name)
        if not os.path.exists(src):
            # 兼容带方法名前缀的 best_method_genes_*.txt
            import glob
            cand = sorted(glob.glob(os.path.join(out_dir, "best_method_genes_*.txt")))
            if cand:
                src = cand[0]
            else:
                return False, "", "未找到可导出的生存基因列表，请先运行阶段四"
        try:
            data = pd.read_csv(src, sep="\t", dtype=str, keep_default_na=False, header=0)
        except Exception as e:
            return False, "", f"读取基因列表失败: {str(e)}"
        if save_path is None:
            save_dir = os.path.join(out_dir, "export")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "surv_best_genes.csv")
        try:
            data.to_csv(save_path, index=False, encoding='utf-8-sig')
            return True, save_path, ""
        except Exception as e:
            return False, "", f"导出 csv 失败: {str(e)}"
