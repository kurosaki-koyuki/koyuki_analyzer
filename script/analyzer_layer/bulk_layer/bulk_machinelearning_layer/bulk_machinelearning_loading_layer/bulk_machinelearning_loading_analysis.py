# -*- coding: utf-8 -*-
"""
bulk 机器学习分析 - 数据加载类子层核心算法层

职责：
1. 扫描 BULK_SCAN_DATA_PATH 下的 h5ad 文件
2. 多选数据集 -> 取基因交集合并 -> 生成 group_df（SampleID, Dataset）
3. 用 subprocess 调用 Rscript 执行 4 种预处理方法的 PCA 出图
4. 合并数据通过 main_analysis.set_merged_data() 供后续子层使用
"""

from script.utils_layer.import_config import os, pd, np, traceback, BULK_SCAN_DATA_PATH, OUT_BASE, get_r_script_path
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class BulkMachineLearningLoadingAnalysis:
    """机器学习数据加载类分析层 - 数据扫描/合并/PCA"""

    # 合并数据输出目录名（OUT_BASE 之下）- 用户要求输出到 OUTPUT/machinelearning/loading/
    MERGED_DIR_NAME = "machinelearning/loading"
    # PCA 输出子目录名（空字符串表示与合并数据同目录）
    PCA_OUTPUT_DIR_NAME = ""
    # 表达矩阵与分组文件名
    EXPR_FILE_NAME = "merged_exprdata.txt"
    GROUP_FILE_NAME = "merged_group.csv"
    # 4 种预处理方法名
    PCA_METHODS = ['raw', 'log2', 'log2_scaled', 'scaled']

    def __init__(self):
        self.r_interface = get_r_kernel_interface()
        self.robjects = None
        self.pandas2ri = None
        self._init_r_environment()
        # R脚本路径（阶段一 PCA）
        self.R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_machinelearning_loading_pca.R")
        # R脚本路径（阶段二 ComBat 去批次）
        self.R_COMBAT_SCRIPT_PATH = get_r_script_path(__file__, "bulk_machinelearning_loading_combat.R")

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
        # 重试一次
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
    # 数据扫描
    # ============================================================

    def scan_datasets(self):
        """扫描 BULK_SCAN_DATA_PATH 下的 h5ad 文件

        Returns:
            (success, files_list, error)
        """
        try:
            folder_path = BULK_SCAN_DATA_PATH
            if not os.path.exists(folder_path):
                return False, [], f"扫描路径不存在: {folder_path}"

            h5ad_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.h5ad')])
            if not h5ad_files:
                return False, [], f"{folder_path} 中没有找到 h5ad 文件"

            return True, h5ad_files, ""
        except Exception as e:
            traceback.print_exc()
            return False, [], f"扫描数据集失败: {str(e)}"

    # ============================================================
    # 加载并合并多个数据集（取基因交集）
    # ============================================================

    def load_and_merge_datasets(self, selected_files, main_analysis):
        """加载多个 h5ad，取基因交集合并，存入 main_analysis

        Args:
            selected_files: 文件名列表如 ['TCGAGBM_TPM.h5ad', 'CGGA325_TPM.h5ad']
            main_analysis: BulkMachineLearningAnalysis 实例（主层）

        Returns:
            (success, info_dict, error)
            info_dict: {'samples':总数, 'genes':交集数, 'datasets':数据集名列表}
        """
        if not selected_files:
            return False, {}, "未选择任何数据集"

        try:
            import anndata as ad

            folder_path = BULK_SCAN_DATA_PATH
            # 1. 读取所有数据集
            all_expr = []  # [(dataset_name, expr_df), ...]
            for fname in selected_files:
                h5ad_path = os.path.join(folder_path, fname)
                if not os.path.exists(h5ad_path):
                    return False, {}, f"数据集文件不存在: {h5ad_path}"
                a = ad.read_h5ad(h5ad_path)
                # 提取表达矩阵（行=样本, 列=基因）
                X = a.X
                if hasattr(X, "toarray"):
                    X = X.toarray()
                expr = pd.DataFrame(np.asarray(X), index=list(a.obs_names), columns=list(a.var_names))
                # 数据集名 = 文件名（去掉 .h5ad）
                dataset_name = os.path.splitext(fname)[0]
                all_expr.append((dataset_name, expr))

            if len(all_expr) < 1:
                return False, {}, "没有有效数据集"

            # 2. 取基因交集
            common_genes = None
            for name, expr in all_expr:
                gset = set(expr.columns)
                common_genes = gset if common_genes is None else (common_genes & gset)
            common_genes = sorted(common_genes)
            if not common_genes:
                return False, {}, "数据集间无共同基因，无法合并"

            # 3. 合并（统一到交集基因，行=样本，列=基因），样本名加数据集前缀防重复
            merged_expr = None
            group_rows = []
            for name, expr in all_expr:
                sub = expr[common_genes].copy()
                sub.index = [f"{name}__{s}" for s in sub.index]
                if merged_expr is None:
                    merged_expr = sub
                else:
                    merged_expr = pd.concat([merged_expr, sub], axis=0)
                for sid in sub.index:
                    group_rows.append({"SampleID": sid, "Dataset": name})

            merged_group = pd.DataFrame(group_rows)
            dataset_names = [n for n, _ in all_expr]

            # 4. 准备输出目录（OUT_BASE/machinelearning_merged/）
            merged_dir = os.path.join(OUT_BASE, self.MERGED_DIR_NAME)
            os.makedirs(merged_dir, exist_ok=True)

            # 5. 保存合并数据到临时文件供 R 读取
            #    - merged_exprdata.txt（行=基因, 列=样本, tab 分隔, 第一列 Gene）
            expr_out = merged_expr.T  # 行=基因, 列=样本
            expr_out.insert(0, "Gene", expr_out.index)
            expr_path = os.path.join(merged_dir, self.EXPR_FILE_NAME)
            expr_out.to_csv(expr_path, sep="\t", index=False)

            #    - merged_group.csv（SampleID, Dataset）
            group_path = os.path.join(merged_dir, self.GROUP_FILE_NAME)
            merged_group.to_csv(group_path, index=False)

            # 6. 调用 main_analysis.set_merged_data() 存储
            if main_analysis is not None:
                main_analysis.set_merged_data(
                    expr_df=merged_expr,
                    group_df=merged_group,
                    dataset_names=dataset_names,
                    common_genes=common_genes,
                )
                # 主层 analysis 持有合并输出目录，供后续子层使用
                if hasattr(main_analysis, 'merged_output_dir'):
                    main_analysis.merged_output_dir = merged_dir

            info = {
                'samples': int(merged_expr.shape[0]),
                'genes': int(len(common_genes)),
                'datasets': dataset_names,
                'merged_dir': merged_dir,
                'expr_file': self.EXPR_FILE_NAME,
                'group_file': self.GROUP_FILE_NAME,
            }
            return True, info, ""
        except Exception as e:
            traceback.print_exc()
            return False, {}, f"加载并合并数据集失败: {str(e)}"

    # ============================================================
    # 调用 R 脚本运行 4 种 PCA
    # ============================================================

    def run_pca_analysis(self, main_analysis, progress_callback=None):
        """调用 R 脚本运行 4 种 PCA 分析

        Args:
            main_analysis: 主层 Analysis 实例（含合并数据）
            progress_callback: 可选回调函数(method_name, message)

        Returns:
            (success, results_dict, error)
            results_dict: {method_name: {'plot_path':..., 'pc_csv':..., 'variance_png':...}}
        """
        try:
            # 1. 检查 R 环境
            if not self.is_r_available():
                return False, {}, "R 环境不可用，请在设置中配置 R 内核路径"

            # 2. 检查合并数据是否就绪
            if main_analysis is None or not getattr(main_analysis, 'is_data_loaded', lambda: False)():
                return False, {}, "请先加载数据集"

            # 合并目录与文件名
            merged_dir = getattr(main_analysis, 'merged_output_dir', None) or os.path.join(OUT_BASE, self.MERGED_DIR_NAME)
            if not os.path.exists(merged_dir):
                return False, {}, f"合并数据目录不存在: {merged_dir}"

            expr_path = os.path.join(merged_dir, self.EXPR_FILE_NAME)
            group_path = os.path.join(merged_dir, self.GROUP_FILE_NAME)
            if not os.path.exists(expr_path) or not os.path.exists(group_path):
                return False, {}, "合并数据文件缺失，请重新加载数据集"

            # 3. PCA 输出目录（OUT_BASE/machinelearning/loading/）
            if self.PCA_OUTPUT_DIR_NAME:
                output_dir = os.path.join(merged_dir, self.PCA_OUTPUT_DIR_NAME)
            else:
                output_dir = merged_dir
            os.makedirs(output_dir, exist_ok=True)

            # 4. 准备 Rscript.exe 路径
            r_path = self.r_interface.get_r_path()
            if not r_path:
                # 兜底：尝试从 R_HOME 推导
                r_home = os.environ.get('R_HOME')
                if r_home:
                    r_path = r_home
            if not r_path or not os.path.exists(r_path):
                return False, {}, "未找到 R 内核路径，请在设置中配置 R 内核"

            rscript_exe = os.path.join(r_path, "bin", "Rscript.exe")
            if not os.path.exists(rscript_exe):
                # 某些安装可能是 bin/Rscript（非 Windows）
                rscript_alt = os.path.join(r_path, "bin", "Rscript")
                if os.path.exists(rscript_alt):
                    rscript_exe = rscript_alt
                else:
                    return False, {}, f"Rscript 可执行文件不存在: {rscript_exe}"

            if not os.path.exists(self.R_SCRIPT_PATH):
                return False, {}, f"R 脚本不存在: {self.R_SCRIPT_PATH}"

            # 5. 用 subprocess 调用 Rscript 执行 R 脚本
            #    参数顺序：work_dir, expr_file, group_file, output_dir
            import subprocess
            cmd = [
                rscript_exe,
                self.R_SCRIPT_PATH,
                merged_dir,            # work_dir
                self.EXPR_FILE_NAME,   # expr_file
                self.GROUP_FILE_NAME,  # group_file
                output_dir,            # output_dir
            ]
            if progress_callback:
                progress_callback('ALL', f"调用 Rscript: {' '.join(cmd)}")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30 分钟超时
                    encoding='utf-8',
                    errors='replace',
                )
            except subprocess.TimeoutExpired:
                return False, {}, "R 脚本执行超时（>30 分钟）"
            except Exception as e:
                return False, {}, f"调用 Rscript 失败: {str(e)}"

            if result.returncode != 0:
                err_msg = (result.stderr or '').strip() or 'R 脚本执行失败（无 stderr 输出）'
                if progress_callback:
                    progress_callback('ALL', f"R 脚本 stderr:\n{result.stderr}")
                return False, {}, f"R 脚本执行失败: {err_msg}"

            if progress_callback and result.stdout:
                progress_callback('ALL', f"R 脚本输出:\n{result.stdout[-500:]}")

            # 6. 检查输出文件是否生成
            results_dict = {}
            for method in self.PCA_METHODS:
                plot_path = os.path.join(output_dir, f"pca_plot_{method}.png")
                plot_pdf = os.path.join(output_dir, f"pca_plot_{method}.pdf")
                pc_csv = os.path.join(output_dir, f"pca_results_{method}.csv")
                variance_png = os.path.join(output_dir, f"pca_variance_{method}.png")
                variance_pdf = os.path.join(output_dir, f"pca_variance_{method}.pdf")
                method_result = {
                    'plot_path': plot_path,
                    'plot_pdf': plot_pdf,
                    'pc_csv': pc_csv,
                    'variance_png': variance_png,
                    'variance_pdf': variance_pdf,
                }
                results_dict[method] = method_result
                # 7. 调用 main_analysis.set_pca_result() 存储每种方法结果
                if main_analysis is not None and hasattr(main_analysis, 'set_pca_result'):
                    main_analysis.set_pca_result(method, method_result)
                if progress_callback:
                    progress_callback(method, f"已生成: {plot_path}")

            return True, results_dict, ""
        except Exception as e:
            traceback.print_exc()
            return False, {}, f"PCA 分析失败: {str(e)}"

    # ============================================================
    # 阶段二：ComBat 去批次 + 去批次后 PCA
    # ============================================================

    def run_stage2_combat(self, main_analysis, preprocessing_method='log2', progress_callback=None):
        """运行阶段二：ComBat 去批次 + 去批次后 PCA

        Args:
            main_analysis: 主层 Analysis 实例（含合并数据路径）
            preprocessing_method: 预处理方法 (raw / log2 / log2_scaled / scaled)
            progress_callback: 回调函数(method_name, message)

        Returns:
            (success, result_dict, error)
            result_dict: {'plot_path':..., 'pc_csv':..., 'corrected_expr':...}
        """
        try:
            if not self.is_r_available():
                return False, {}, "R 环境不可用，请在设置中配置 R 内核路径"

            # 检查合并数据是否就绪
            if main_analysis is None or not getattr(main_analysis, 'is_data_loaded', lambda: False)():
                return False, {}, "请先加载数据集"

            merged_dir = getattr(main_analysis, 'merged_output_dir', None) or os.path.join(OUT_BASE, self.MERGED_DIR_NAME)
            if not os.path.exists(merged_dir):
                return False, {}, f"合并数据目录不存在: {merged_dir}"

            expr_path = os.path.join(merged_dir, self.EXPR_FILE_NAME)
            group_path = os.path.join(merged_dir, self.GROUP_FILE_NAME)
            if not os.path.exists(expr_path) or not os.path.exists(group_path):
                return False, {}, "合并数据文件缺失，请重新加载数据集"

            # 输出目录（与合并数据同目录：OUTPUT/machinelearning/loading/）
            output_dir = merged_dir

            # 准备 Rscript.exe 路径
            r_path = self.r_interface.get_r_path()
            if not r_path:
                r_home = os.environ.get('R_HOME')
                if r_home:
                    r_path = r_home
            if not r_path or not os.path.exists(r_path):
                return False, {}, "未找到 R 内核路径，请在设置中配置 R 内核"

            rscript_exe = os.path.join(r_path, "bin", "Rscript.exe")
            if not os.path.exists(rscript_exe):
                rscript_alt = os.path.join(r_path, "bin", "Rscript")
                if os.path.exists(rscript_alt):
                    rscript_exe = rscript_alt
                else:
                    return False, {}, f"Rscript 可执行文件不存在: {rscript_exe}"

            if not os.path.exists(self.R_COMBAT_SCRIPT_PATH):
                return False, {}, f"R 脚本不存在: {self.R_COMBAT_SCRIPT_PATH}"

            # 用 subprocess 调用 Rscript 执行 R 脚本
            # 参数顺序：mode, work_dir, expr_file, group_file, output_dir, preprocessing
            import subprocess
            cmd = [
                rscript_exe,
                self.R_COMBAT_SCRIPT_PATH,
                "stage2",                # mode
                merged_dir,               # work_dir
                self.EXPR_FILE_NAME,      # expr_file
                self.GROUP_FILE_NAME,     # group_file
                output_dir,               # output_dir
                preprocessing_method,     # preprocessing
            ]
            if progress_callback:
                progress_callback('ComBat', f"调用 Rscript: {' '.join(cmd)}")

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=1800,
                    encoding='utf-8', errors='replace',
                )
            except subprocess.TimeoutExpired:
                return False, {}, "R 脚本执行超时（>30 分钟）"
            except Exception as e:
                return False, {}, f"调用 Rscript 失败: {str(e)}"

            if result.returncode != 0:
                err_msg = (result.stderr or '').strip() or 'R 脚本执行失败（无 stderr 输出）'
                if progress_callback and result.stderr:
                    progress_callback('ComBat', f"R 脚本 stderr:\n{result.stderr[-500:]}")
                return False, {}, f"R 脚本执行失败: {err_msg}"

            if progress_callback and result.stdout:
                progress_callback('ComBat', f"R 脚本输出:\n{result.stdout[-500:]}")

            # 检查输出文件
            plot_path = os.path.join(output_dir, "pca_stage2_plot.png")
            plot_pdf = os.path.join(output_dir, "pca_stage2_plot.pdf")
            pc_csv = os.path.join(output_dir, "pca_stage2_results.csv")
            corrected_expr = os.path.join(output_dir, "combat_corrected_exprdata.txt")

            if not os.path.exists(plot_path):
                return False, {}, f"去批次后 PCA 图未生成: {plot_path}"

            result_dict = {
                'plot_path': plot_path,
                'plot_pdf': plot_pdf,
                'pc_csv': pc_csv,
                'corrected_expr': corrected_expr,
            }

            # 存储到 main_analysis
            if main_analysis is not None and hasattr(main_analysis, 'set_pca_result'):
                main_analysis.set_pca_result('combat', result_dict)

            if progress_callback:
                progress_callback('ComBat', f"已生成: {plot_path}")

            return True, result_dict, ""
        except Exception as e:
            traceback.print_exc()
            return False, {}, f"ComBat 去批次失败: {str(e)}"

    # ============================================================
    # 阶段三：同步临床信息
    # ============================================================

    def load_dataset_obs(self, selected_files):
        """读取每个数据集的 obs（临床信息）

        Args:
            selected_files: 文件名列表如 ['TCGAGBM_TPM.h5ad', 'CGGA325_TPM.h5ad']

        Returns:
            (success, dataset_obs_dict, error)
            dataset_obs_dict: {dataset_name: obs_df}
        """
        try:
            import anndata as ad

            folder_path = BULK_SCAN_DATA_PATH
            dataset_obs_dict = {}
            for fname in selected_files:
                h5ad_path = os.path.join(folder_path, fname)
                if not os.path.exists(h5ad_path):
                    return False, {}, f"数据集文件不存在: {h5ad_path}"
                a = ad.read_h5ad(h5ad_path)
                dataset_name = os.path.splitext(fname)[0]
                # obs 的索引改为样本名（保持原始）
                obs_df = a.obs.copy()
                # 过滤掉 nunique > 50 的列（非临床分类列）
                keep_cols = []
                for col in obs_df.columns:
                    try:
                        if obs_df[col].nunique() <= 50:
                            keep_cols.append(col)
                    except Exception:
                        continue
                dataset_obs_dict[dataset_name] = obs_df[keep_cols] if keep_cols else obs_df
            return True, dataset_obs_dict, ""
        except Exception as e:
            traceback.print_exc()
            return False, {}, f"读取临床信息失败: {str(e)}"

    def build_clinical_df(self, mapping_result, main_analysis=None):
        """根据向导结果构建组合临床信息 DataFrame

        输出列结构：
        - SampleID: 样本ID（带数据集前缀）
        - <column_name>_synced: 同步后的组别列（组别1/组别名）
        - <所有数据集的临床列>: 同名列合并，缺失填NA

        Args:
            mapping_result: ClinicalSyncDialog.get_result() 返回的 dict
            main_analysis: 主层 Analysis 实例

        Returns:
            (success, clinical_df, error)
        """
        try:
            if not mapping_result:
                return False, None, "映射结果为空"

            column_name = mapping_result['column_name']
            group1_name = mapping_result['group1_name']
            group2_name = mapping_result['group2_name']
            mappings = mapping_result['mappings']
            synced_col_name = f"{column_name}_synced"

            import anndata as ad
            folder_path = BULK_SCAN_DATA_PATH

            # 1. 读取所有数据集 obs，构建同步列并收集所有临床列名
            dataset_obs = {}       # {dataset_name: obs_df}
            all_clinical_cols = []  # 保持插入顺序的唯一列名
            seen_cols = set()
            synced_rows = []

            for dataset_name, mapping in mappings.items():
                h5ad_file = None
                for fname in os.listdir(folder_path):
                    if fname.endswith('.h5ad') and os.path.splitext(fname)[0] == dataset_name:
                        h5ad_file = fname
                        break
                if h5ad_file is None:
                    continue
                a = ad.read_h5ad(os.path.join(folder_path, h5ad_file))
                obs = a.obs
                dataset_obs[dataset_name] = obs

                # 收集临床列名（保持顺序，去重，过滤 nunique > 50）
                for col in obs.columns:
                    if col not in seen_cols:
                        try:
                            if obs[col].nunique() <= 50:
                                all_clinical_cols.append(col)
                                seen_cols.add(col)
                        except Exception:
                            continue

                # 构建同步列
                col = mapping['column']
                if col not in obs.columns:
                    continue
                group1_values = set(str(v) for v in mapping['group1_values'])
                group2_values = set(str(v) for v in mapping['group2_values'])

                for sample_id in obs.index:
                    raw_val = str(obs.at[sample_id, col]) if col in obs.columns else ""
                    prefixed_id = f"{dataset_name}__{sample_id}"
                    if raw_val in group1_values:
                        synced_rows.append({"SampleID": prefixed_id, synced_col_name: group1_name})
                    elif raw_val in group2_values:
                        synced_rows.append({"SampleID": prefixed_id, synced_col_name: group2_name})
                    # 未分配的样本丢弃

            if not synced_rows:
                return False, None, "没有样本被分配到组别1或组别2"

            synced_df = pd.DataFrame(synced_rows)

            # 2. 构建临床信息查找表 {prefixed_id: {col: value}}
            clinical_lookup = {}
            for dataset_name, obs in dataset_obs.items():
                for sample_id in obs.index:
                    prefixed_id = f"{dataset_name}__{sample_id}"
                    row_data = {}
                    for col in all_clinical_cols:
                        if col in obs.columns:
                            row_data[col] = str(obs.at[sample_id, col])
                        else:
                            row_data[col] = None
                    clinical_lookup[prefixed_id] = row_data

            # 3. 为保留样本追加所有临床列（同名列合并，缺失填NA）
            for col in all_clinical_cols:
                synced_df[col] = [
                    clinical_lookup.get(sid, {}).get(col, None)
                    for sid in synced_df['SampleID']
                ]

            return True, synced_df, ""
        except Exception as e:
            traceback.print_exc()
            return False, None, f"构建临床信息失败: {str(e)}"

    def save_clinical_txt(self, clinical_df, column_name, main_analysis=None):
        """保存组合临床信息到 txt 文件

        Args:
            clinical_df: DataFrame，包含 SampleID 和映射列
            column_name: 映射列名
            main_analysis: 主层 Analysis 实例

        Returns:
            (success, file_path, error)
        """
        try:
            merged_dir = getattr(main_analysis, 'merged_output_dir', None) or os.path.join(OUT_BASE, self.MERGED_DIR_NAME)
            os.makedirs(merged_dir, exist_ok=True)

            file_path = os.path.join(merged_dir, "merged_clinical.txt")
            clinical_df.to_csv(file_path, sep="\t", index=False)
            return True, file_path, ""
        except Exception as e:
            traceback.print_exc()
            return False, "", f"保存临床信息失败: {str(e)}"

