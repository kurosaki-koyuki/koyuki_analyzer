# -*- coding: utf-8 -*-
"""
bulk 一致性分析 Python接口层
此文件不包含任何R代码，只负责：
1. 数据准备和处理
2. 参数传递到R环境
3. 调用R脚本中的三阶段代码
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path, tempfile, shutil
from typing import Optional, List, Dict, Any

# 从统一R接口获取R环境
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from script.utils_layer.import_config import importr as _importr


class BulkClusterAnalysis:
    """bulk 一致性分析 Python接口层 - 不含R代码"""

    _r_debug_log: List[Dict[str, Any]] = []

    R_SCRIPT_PATH = get_r_script_path(__file__, "bulk_cluster_analysis.R")

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
        self._temp_dir = None
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
                           clinical_col=None, clinical_groups=None) -> bool:
        """阶段一：聚类计算"""
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

            # 执行阶段一代码
            r_code = self._read_stage_code("STAGE1")
            self.robjects.r(r_code)

            self._stage1_completed = True
            self._stage2_completed = False
            self._stage3_completed = False
            print(f"[阶段一] 聚类计算完成")
            return True

        except Exception as e:
            self._log_r_debug("stage1_cluster", e, {
                "mad_threshold": mad_threshold, "reps": reps,
                "cluster_alg": cluster_alg, "distance": distance,
                "min_k": min_k, "max_k": max_k
            })
            raise RuntimeError(f"阶段一R代码执行失败: {str(e)}")

    # ---------- 阶段二：CDF + PAC曲线 ----------

    def run_stage2_cdf_pac(self, min_k: int = 2, max_k: int = 9,
                           output_path: str = None,
                           plot_width: float = 10, plot_height: float = 6) -> str:
        """阶段二：生成CDF+PAC曲线"""
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一聚类计算")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if output_path is None:
            output_path = os.path.join(self.dataset_output_dir or ".",
                                       f"{self.dataset_name}_cdf_pac.png")

        try:
            from rpy2.robjects import StrVector, IntVector, FloatVector

            self.robjects.globalenv['min_k'] = IntVector([int(min_k)])
            self.robjects.globalenv['max_k'] = IntVector([int(max_k)])
            self.robjects.globalenv['output_path'] = StrVector([output_path])
            self.robjects.globalenv['plot_width'] = FloatVector([float(plot_width)])
            self.robjects.globalenv['plot_height'] = FloatVector([float(plot_height)])

            r_code = self._read_stage_code("STAGE2")
            self.robjects.r(r_code)

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
            raise RuntimeError(f"阶段二R代码执行失败: {str(e)}")

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
            'stage3': self._stage3_completed
        }


# 单例模式
_instance = None

def get_bulk_cluster_analysis() -> BulkClusterAnalysis:
    global _instance
    if _instance is None:
        _instance = BulkClusterAnalysis()
    return _instance
