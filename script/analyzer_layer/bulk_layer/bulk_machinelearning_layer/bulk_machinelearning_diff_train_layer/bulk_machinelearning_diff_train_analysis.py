# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 差异训练类(diff_train)子层核心算法层

职责：
- 读取 loading 层产物（去批次表达矩阵 + 同步后的临床信息）
- 通过 subprocess 调用 R 脚本，分 5 个阶段执行机器学习训练：
    stage1 数据准备（合成训练矩阵 + 基因集过滤 + 标准化）
    stage2 单模型（Lasso / RF / SVM + ROC）
    stage3 批量建模（113 种算法组合）
    stage4 AUC 计算 + 热图
    stage5 核心基因筛选 + 出图
- 输出目录：OUT_BASE/machinelearning/train/
"""

from script.utils_layer.import_config import os, pd, np, traceback, APPDATA_PATH, OUT_BASE, get_r_script_path
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class BulkMachineLearningDiffTrainAnalysis:
    """机器学习差异训练类分析层"""

    # loading 产物目录名（OUT_BASE 之下）
    LOADING_DIR_NAME = "machinelearning/loading"
    # 输出目录名（OUT_BASE 之下）
    OUT_DIR_NAME = "machinelearning/train"
    # loading 产物文件名
    COMBAT_EXPR_FILE = "combat_corrected_exprdata.txt"
    CLINICAL_FILE = "merged_clinical.txt"
    # synced 列后缀（阶段三生成的同步列，如 IDH_mutation_status_synced）
    SYNCED_SUFFIX = "_synced"
    # APPDATA 下基因集目录与机器学习资源目录
    GENELIST_DIR = os.path.join(APPDATA_PATH, "genelists")
    ML_RESOURCE_DIR = os.path.join(APPDATA_PATH, "machinelearning")
    # 阶段名
    STAGES = {
        "stage1": "数据准备",
        "stage2": "单模型(Lasso/RF/SVM)",
        "stage3": "批量建模(113算法)",
        "stage4": "AUC计算+热图",
        "stage5": "核心基因筛选",
    }
    # 默认参数
    DEFAULT_MAX_GENES = 1000
    # 种子默认 1234：与参考脚本「成功测试脚本.R」中的 set.seed(1234) 一致
    DEFAULT_SEED = 1234
    # 阶段五核心基因筛选参数默认值
    DEFAULT_FILTER_MODE = "composite"   # gene_rank / n_models / avg_rank / composite
    DEFAULT_TOP_N = 30
    # n_models 现为交集法阈值：基因须在 Top10 最优AUC模型中出现 >= 5 次(参考默认)
    DEFAULT_N_MODELS = 5
    DEFAULT_AVG_RANK = 100
    # 阶段四/五 AUC 阈值筛选默认值：0 表示不筛选；>0(0.5-1) 时仅保留 avg_AUC >= 该阈值的算法
    DEFAULT_AUC_THRESHOLD = 0

    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.pandas2ri = None
        self._init_r_environment()
        # R 脚本路径
        self.R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_machinelearning_diff_train.R")

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
        # 优先从主层读取实际合并输出目录
        if main_analysis is not None:
            merged_dir = getattr(main_analysis, 'merged_output_dir', None)
            if merged_dir and os.path.isdir(merged_dir):
                return merged_dir
        return os.path.join(OUT_BASE, self.LOADING_DIR_NAME)

    def get_out_dir(self):
        """获取 diff_train 输出目录并创建"""
        out_dir = os.path.join(OUT_BASE, self.OUT_DIR_NAME)
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    #: 阶段五的基因列表产物：(标签, 文件名) —— **顺序即"旧口径"优先级**（取第一个非空）
    GENE_LIST_FILES = (("核心基因集", "gene_all_list.txt"),
                       ("频率推荐集", "gene_frequency_recommended.txt"))

    def get_gene_list(self, file_name):
        """读**单个**输出文件的第一列 → 基因名列表（不存在/空 → []）。

        与 `export_gene_list_csv` 同一份产物；按无表头口径读（首格是 `Gene` 表头时跳过）。
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

        宁少勿假：文件不在（=该层结果不存在）就不列出这个子集。
        """
        out = []
        for label, name in self.GENE_LIST_FILES:
            genes = self.get_gene_list(name)
            if genes:
                out.append((label, genes))
        return out

    def get_final_gene_names(self):
        """旧口径（施工前的行为）：按 `GENE_LIST_FILES` 顺序取**第一个非空**文件的基因名。

        与 `export_gene_list_csv` 同一份输出文件；取不到 → []。
        """
        for _label, genes in self.list_gene_subsets():
            return genes
        return []

    def detect_label_column(self, clinical_path):
        """从临床文件中自动检测 synced 组别列（含 _synced 后缀）

        Returns:
            (col_name or None)
        """
        try:
            cli = pd.read_csv(clinical_path, sep="\t",
                              dtype=str, keep_default_na=False)
            synced_cols = [c for c in cli.columns if self.SYNCED_SUFFIX in c]
            if not synced_cols:
                return None
            # 取第一个含 synced 的列
            return synced_cols[0]
        except Exception:
            return None

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
            return []

    def list_gene_files(self):
        """列出基因集目录中的所有基因集文件（xlsx/xls/txt/csv）"""
        return self._scan_dir(self.GENELIST_DIR, ('.xlsx', '.xls', '.txt', '.csv'))

    def list_methods_files(self):
        """列出机器学习资源目录中的所有算法组合文件（txt）"""
        return self._scan_dir(self.ML_RESOURCE_DIR, ('.txt',))

    # 将带非 ASCII（如中文）字符的路径规范化为 ASCII 路径，
    # 避免 Windows 下 R 的 file.exists/file conversion 报错
    @staticmethod
    def _ascii_safe_path(src_path, ascii_name):
        """若路径含非 ASCII 字符，则把文件复制到 ascii_name 指定位置并返回 ASCII 路径

        位置固定放到 OUT_BASE/machinelearning/train/_input_ 下，避免每次重复复制。
        """
        if not src_path:
            return "NONE"
        if src_path.isascii():
            return src_path
        import shutil
        target_dir = os.path.join(OUT_BASE, "machinelearning", "train", "_input_")
        target = os.path.join(target_dir, ascii_name)
        try:
            os.makedirs(target_dir, exist_ok=True)
            shutil.copyfile(src_path, target)
            return target
        except Exception:
            # 复制失败则回退原始路径（可能仍会失败，但保留原有行为）
            return src_path

    def detect_gene_file(self, main_analysis=None):
        """获取用户在下拉框选择的基因集文件（若含中文则复制为 ASCII 名路径返回）

        Returns:
            (gene_file_path or "NONE")
        """
        if main_analysis is not None:
            sel = getattr(main_analysis, 'diff_train_gene_file', "")
            if sel and sel != "不使用基因集":
                path = os.path.join(self.GENELIST_DIR, sel)
                if os.path.exists(path):
                    ext = os.path.splitext(path)[1] or ".txt"
                    return self._ascii_safe_path(path, "gene_set_input" + ext.lower())
        return "NONE"

    def detect_methods_file(self, main_analysis=None):
        """获取用户在下拉框选择的算法组合文件（返回绝对路径）

        Returns:
            (methods_file_path or "NONE")
        """
        if main_analysis is not None:
            sel = getattr(main_analysis, 'diff_train_methods_file', "")
            if sel:
                path = os.path.join(self.ML_RESOURCE_DIR, sel)
                if os.path.exists(path):
                    return path
        return "NONE"

    def detect_max_genes(self, main_analysis=None):
        """获取高变异基因截断数参数"""
        if main_analysis is not None:
            v = getattr(main_analysis, 'diff_train_max_genes', None)
        else:
            v = None
        try:
            val = int(v) if v else self.DEFAULT_MAX_GENES
        except Exception:
            val = self.DEFAULT_MAX_GENES
        return max(50, val)

    def detect_seed(self, main_analysis=None):
        """获取随机种子参数"""
        if main_analysis is not None:
            v = getattr(main_analysis, 'diff_train_seed', None)
        else:
            v = None
        try:
            val = int(v) if v else self.DEFAULT_SEED
        except Exception:
            val = self.DEFAULT_SEED
        return max(1, val)

    def detect_filter_params(self, main_analysis=None):
        """获取阶段五核心基因筛选参数

        约定：0 表示「该条件不生效（不做筛选）」，由 UI 默认 top=30 / n_models=0 / avg_rank=0 体现。
        Returns:
            dict: {'filter_mode': str, 'top_n': int, 'n_models': int, 'avg_rank': int}
        """
        mode = self.DEFAULT_FILTER_MODE
        top_n = self.DEFAULT_TOP_N
        n_models = self.DEFAULT_N_MODELS
        avg_rank = self.DEFAULT_AVG_RANK
        if main_analysis is not None:
            m = getattr(main_analysis, 'diff_train_filter_mode', None)
            if m:
                mode = m
            # 用 is not None 语义：UI 传入 0 时保持 0（即“不筛选”），不得回退为默认值
            t = getattr(main_analysis, 'diff_train_filter_top_n', None)
            if t is not None:
                try:
                    top_n = int(t)
                except Exception:
                    pass
            n = getattr(main_analysis, 'diff_train_filter_n_models', None)
            if n is not None:
                try:
                    n_models = int(n)
                except Exception:
                    pass
            a = getattr(main_analysis, 'diff_train_filter_avg_rank', None)
            if a is not None:
                try:
                    avg_rank = int(a)
                except Exception:
                    pass
        return {
            'filter_mode': mode,
            'top_n': max(0, top_n),
            'n_models': max(0, n_models),
            'avg_rank': max(0, avg_rank),
        }

    def detect_auc_threshold(self, main_analysis=None):
        """获取阶段四/五 AUC 阈值筛选参数

        返回 float：0 表示不筛选，>0 时仅保留 avg_AUC >= 该阈值的算法。
        无效输入回退为默认 0。
        """
        if main_analysis is not None:
            v = getattr(main_analysis, 'diff_train_auc_threshold', None)
        else:
            v = None
        try:
            val = float(v) if v is not None and v != "" else self.DEFAULT_AUC_THRESHOLD
        except Exception:
            val = self.DEFAULT_AUC_THRESHOLD
        if val < 0:
            val = self.DEFAULT_AUC_THRESHOLD
        return val

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
        if not os.path.exists(rscript_exe):
            rscript_alt = os.path.join(r_path, "bin", "Rscript")
            if os.path.exists(rscript_alt):
                rscript_exe = rscript_alt
            else:
                return None
        return rscript_exe

    def _run_r(self, stage, work_dir, expr_file, clinical_file, out_dir,
               gene_file, label_col, methods_file="NONE", max_genes=None,
               seed=None, filter_params=None, progress_callback=None,
               auc_threshold=None):
        """调用 R 脚本执行指定阶段

        Args:
            filter_params: dict，阶段五筛选参数 {'filter_mode','top_n','n_models','avg_rank'}，
                           仅 stage5 使用，其他阶段忽略。
            auc_threshold: float，阶段四/五 AUC 阈值筛选（0 表示不筛选），作为 args[15]。

        Returns:
            (success, result_dict, error)
        """
        try:
            if not self.is_r_available():
                return False, {}, "R 环境不可用，请在设置中配置 R 内核路径"

            if not os.path.exists(self.R_SCRIPT_PATH):
                return False, {}, f"R 脚本不存在: {self.R_SCRIPT_PATH}"

            rscript_exe = self._resolve_rscript()
            if not rscript_exe:
                return False, {}, "未找到 Rscript 可执行文件，请在设置中配置 R 内核"

            import subprocess
            cmd = [
                rscript_exe,
                self.R_SCRIPT_PATH,
                stage,           # mode
                work_dir,        # work_dir
                expr_file,       # expr_file
                clinical_file,   # clinical_file
                out_dir,         # out_dir
                gene_file,       # gene_file
                label_col,       # label_col
                methods_file,    # methods_file
                str(max_genes),  # max_genes
                str(seed),       # seed
            ]
            # 阶段五筛选参数（args[11-14]），其他阶段填占位默认值即可
            if filter_params:
                fp = filter_params
                cmd += [
                    str(fp.get('filter_mode', self.DEFAULT_FILTER_MODE)),
                    str(fp.get('top_n', self.DEFAULT_TOP_N)),
                    str(fp.get('n_models', self.DEFAULT_N_MODELS)),
                    str(fp.get('avg_rank', self.DEFAULT_AVG_RANK)),
                ]
            else:
                cmd += [
                    self.DEFAULT_FILTER_MODE,
                    str(self.DEFAULT_TOP_N),
                    str(self.DEFAULT_N_MODELS),
                    str(self.DEFAULT_AVG_RANK),
                ]
            # 阶段四/五 AUC 阈值筛选参数（args[15]），0 表示不筛选
            if auc_threshold is None:
                auc_threshold = self.DEFAULT_AUC_THRESHOLD
            cmd.append(str(auc_threshold))
            stage_name = self.STAGES.get(stage, stage)
            if progress_callback:
                progress_callback(stage, f"调用 Rscript({stage_name}): {' '.join(cmd)}")

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=3600,
                    encoding='utf-8', errors='replace',
                )
            except subprocess.TimeoutExpired:
                return False, {}, f"{stage_name} 执行超时（>60 分钟）"
            except Exception as e:
                return False, {}, f"调用 Rscript 失败: {str(e)}"

            if result.returncode != 0:
                err_msg = (result.stderr or '').strip() or 'R 脚本执行失败（无 stderr 输出）'
                if progress_callback:
                    progress_callback(stage, f"R 脚本 stderr:\n{result.stderr[-1000:]}")
                return False, {}, f"{stage_name} 失败: {err_msg}"

            if progress_callback and result.stdout:
                progress_callback(stage, f"R 脚本输出:\n{result.stdout[-800:]}")

            return True, {"stdout": result.stdout}, ""
        except Exception as e:
            traceback.print_exc()
            return False, {}, f"{self.STAGES.get(stage, stage)} 失败: {str(e)}"

    # ============================================================
    # 各阶段入口
    # ============================================================

    def _prepare_inputs(self, main_analysis=None, label_col=None, progress_callback=None):
        """准备各阶段通用输入参数

        Args:
            progress_callback: 可选，用于向 UI 输出数据加载来源等进度信息，
                               以便用户在界面中确认实际读取的 loading 产物位置。

        Returns:
            (success, params_dict, error)
            params_dict: {'work_dir', 'expr_file', 'clinical_file', 'out_dir',
                          'gene_file', 'label_col'}
        """
        loading_dir = self.get_loading_dir(main_analysis)
        # 输出实际读取的 loading 目录，便于界面确认是否读到之前保存的产物
        if progress_callback:
            progress_callback("input", f"读取数据来源(loading产物)目录: {loading_dir}")
        if not os.path.isdir(loading_dir):
            return False, {}, f"loading 产物目录不存在: {loading_dir}\n请先运行「数据加载类」生成去批次数据"

        expr_file = self.COMBAT_EXPR_FILE
        clinical_file = self.CLINICAL_FILE
        expr_path = os.path.join(loading_dir, expr_file)
        clin_path = os.path.join(loading_dir, clinical_file)
        if not os.path.exists(expr_path):
            return False, {}, f"去批次表达矩阵缺失: {expr_path}\n请先运行「数据加载类」阶段二"
        if not os.path.exists(clin_path):
            return False, {}, f"同步临床信息缺失: {clin_path}\n请先运行「数据加载类」阶段三"
        if progress_callback:
            progress_callback("input", (
                f"  去批次表达矩阵: {expr_path} (存在:{os.path.exists(expr_path)})\n"
                f"  同步临床信息:   {clin_path} (存在:{os.path.exists(clin_path)})"
            ))

        # 检测 label 列（若未指定）
        if not label_col:
            label_col = self.detect_label_column(clin_path)
        if not label_col:
            cols = pd.read_csv(clin_path, sep="\t", nrows=1).columns.tolist()
            return False, {}, (
                f"未找到 synced 组别列（含 '_{self.SYNCED_SUFFIX}' 后缀）。\n"
                f"请先运行「数据加载类」阶段三同步临床信息。\n当前临床列: {cols}"
            )
        if progress_callback:
            progress_callback("input", f"自动检测组别列(label_col): {label_col}")

        out_dir = self.get_out_dir()
        gene_file = self.detect_gene_file(main_analysis)
        if not gene_file:
            gene_file = "NONE"
        methods_file = self.detect_methods_file(main_analysis)
        if not methods_file:
            methods_file = "NONE"
        max_genes = self.detect_max_genes(main_analysis)
        seed = self.detect_seed(main_analysis)

        params = {
            'work_dir': loading_dir,
            'expr_file': expr_file,
            'clinical_file': clinical_file,
            'out_dir': out_dir,
            'gene_file': gene_file,
            'label_col': label_col,
            'methods_file': methods_file,
            'max_genes': max_genes,
            'seed': seed,
        }
        return True, params, ""

    def run_stage1(self, main_analysis=None, label_col=None, progress_callback=None):
        """阶段一：数据准备"""
        ok, params, err = self._prepare_inputs(main_analysis, label_col, progress_callback)
        if not ok:
            return False, {}, err
        return self._run_r(
            "stage1", params['work_dir'], params['expr_file'], params['clinical_file'],
            params['out_dir'], params['gene_file'], params['label_col'],
            params['methods_file'], params['max_genes'], params['seed'],
            None, progress_callback=progress_callback,
        )

    def run_stage2(self, main_analysis=None, label_col=None, progress_callback=None):
        """阶段二：单模型（Lasso / RF / SVM）"""
        ok, params, err = self._prepare_inputs(main_analysis, label_col, progress_callback)
        if not ok:
            return False, {}, err
        return self._run_r(
            "stage2", params['work_dir'], params['expr_file'], params['clinical_file'],
            params['out_dir'], params['gene_file'], params['label_col'],
            params['methods_file'], params['max_genes'], params['seed'],
            None, progress_callback=progress_callback,
        )

    def run_stage3(self, main_analysis=None, label_col=None, progress_callback=None):
        """阶段三：批量建模（算法组合）"""
        ok, params, err = self._prepare_inputs(main_analysis, label_col, progress_callback)
        if not ok:
            return False, {}, err
        return self._run_r(
            "stage3", params['work_dir'], params['expr_file'], params['clinical_file'],
            params['out_dir'], params['gene_file'], params['label_col'],
            params['methods_file'], params['max_genes'], params['seed'],
            None, progress_callback=progress_callback,
        )

    def run_stage4(self, main_analysis=None, label_col=None, progress_callback=None):
        """阶段四：AUC 计算 + 热图"""
        ok, params, err = self._prepare_inputs(main_analysis, label_col, progress_callback)
        if not ok:
            return False, {}, err
        auc_threshold = self.detect_auc_threshold(main_analysis)
        if progress_callback:
            progress_callback("stage4", f"阶段四 AUC 阈值筛选: {auc_threshold} (0=不筛选)")
        return self._run_r(
            "stage4", params['work_dir'], params['expr_file'], params['clinical_file'],
            params['out_dir'], params['gene_file'], params['label_col'],
            params['methods_file'], params['max_genes'], params['seed'],
            None, progress_callback=progress_callback,
            auc_threshold=auc_threshold,
        )

    def run_stage5(self, main_analysis=None, label_col=None, progress_callback=None):
        """阶段五：核心基因筛选 + 出图"""
        ok, params, err = self._prepare_inputs(main_analysis, label_col, progress_callback)
        if not ok:
            return False, {}, err
        filter_params = self.detect_filter_params(main_analysis)
        auc_threshold = self.detect_auc_threshold(main_analysis)
        if progress_callback:
            progress_callback("stage5", (
                f"阶段五筛选参数: 模式={filter_params['filter_mode']}, "
                f"TopN={filter_params['top_n']}, nModels={filter_params['n_models']}, "
                f"AvgRank={filter_params['avg_rank']}, AUC阈值={auc_threshold}"
            ))
        return self._run_r(
            "stage5", params['work_dir'], params['expr_file'], params['clinical_file'],
            params['out_dir'], params['gene_file'], params['label_col'],
            params['methods_file'], params['max_genes'], params['seed'],
            filter_params,
            progress_callback,
            auc_threshold=auc_threshold,
        )

    # ============================================================
    # 导出辅助（需求6）
    # ============================================================

    def export_images_zip(self, ext='png', save_path=None):
        """将输出目录下所有指定扩展名图片打包为 zip

        Args:
            ext: 'png' 或 'pdf'
            save_path: 目标 zip 路径；None 表示默认目录与文件名

        Returns:
            (success, save_path_or_msg, error)
        """
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

    def export_gene_list_csv(self, save_path=None, source_file_name="gene_all_list.txt"):
        """将阶段五全基因列表导出为 csv

        Args:
            save_path: 目标 csv 路径；None 表示默认便于英文名 core_gene_list.csv
            source_file_name: 源数据文件名（R 脚本 output 的全基因表）

        Returns:
            (success, save_path_or_msg, error)
        """
        out_dir = self.get_out_dir()
        if not os.path.isdir(out_dir):
            return False, "", f"输出目录不存在: {out_dir}"
        src = os.path.join(out_dir, source_file_name)
        if not os.path.exists(src):
            # 兼容旧版输出名
            alt = os.path.join(out_dir, "gene_frequency_recommended.txt")
            if os.path.exists(alt):
                src = alt
            else:
                return False, "", "未找到可导出的基因列表，请先运行阶段五"
        try:
            data = pd.read_csv(src, sep="\t", dtype=str, keep_default_na=False,
                               header=0)
        except Exception as e:
            return False, "", f"读取基因列表失败: {str(e)}"
        if save_path is None:
            save_dir = os.path.join(out_dir, "export")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "core_gene_list.csv")
        try:
            data.to_csv(save_path, index=False, encoding='utf-8-sig')
            return True, save_path, ""
        except Exception as e:
            return False, "", f"导出 csv 失败: {str(e)}"
