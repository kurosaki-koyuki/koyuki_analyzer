# -*- coding: utf-8 -*-
"""
scRNAseq Monocle基因列表类子层 - 分析算法层
负责：1) 调用R脚本运行graph_test(Moran's I检验)；2) 读取TSV结果；3) 按阈值筛显著基因
基因筛选模式：all(全部基因) / hvg(高变基因前N个) / list(外部基因列表)
"""

import os
import subprocess
import traceback
import ctypes

import pandas as pd

from script.utils_layer.import_config import APPDATA_PATH, OUT_BASE
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class ScMonocleGenelistsAnalysis:
    """Monocle基因列表类分析算法"""

    def __init__(self):
        self.cds_rds_path = None       # 共享自数据加载类
        self.dataset_name = None       # 共享自数据加载类
        self._r_script_path = os.path.join(os.path.dirname(__file__), 'run_monocle_genelists.R')
        self._r_stage3_script_path = os.path.join(os.path.dirname(__file__), 'run_monocle_genelists_stage3.R')
        self._r_interface = get_r_kernel_interface()
        self._rscript_path = self._get_rscript_path()
        # 缓存最近一次graph_test结果（避免重跑R脚本筛显著基因）
        self._cached_result_df = None
        self._cached_tsv_path = None
        # 缓存最近一次Spearman相关性结果（阶段三原始结果）
        self._cached_spearman_df = None
        self._cached_spearman_tsv_path = None
        # 缓存阶段三分类后的结果（含direction列）
        self._cached_stage3_result_df = None

    def _get_rscript_path(self):
        r_path = self._r_interface.get_r_path()
        if r_path:
            return os.path.join(r_path, "bin", "Rscript.exe")
        return r"A:\TOOLS\R\R-4.6.1\bin\Rscript.exe"

    def _get_short_path(self, path):
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetShortPathNameW(path, buf, 260)
            return buf.value
        except Exception:
            return path

    def _get_genelists_output_dir(self):
        """获取输出目录：OUTPUT/monocle3/genelists_test/{dataset_name}/"""
        if not self.dataset_name:
            raise ValueError("dataset_name未设置")
        output_dir = os.path.join(OUT_BASE, "monocle3", "genelists_test", self.dataset_name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def set_cds_rds_path(self, cds_rds_path, dataset_name):
        """设置CDS rds路径和数据集名称（由数据加载类共享）"""
        self.cds_rds_path = cds_rds_path
        self.dataset_name = dataset_name

    def has_shared_data(self):
        """是否已共享CDS数据"""
        return bool(self.cds_rds_path) and os.path.exists(self.cds_rds_path)

    def load_gene_list_from_file(self, file_path):
        """从txt/xlsx文件加载基因列表
        返回: (success, gene_list, error_msg)
        """
        if not os.path.exists(file_path):
            return False, [], f"文件不存在: {file_path}"

        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.xlsx':
                df = pd.read_excel(file_path)
                # 取第一列作为基因名
                genes = df.iloc[:, 0].dropna().astype(str).tolist()
            elif ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 支持换行、逗号、制表符、分号分隔
                genes_raw = content.replace('\n', ',').replace('\t', ',').replace(';', ',').split(',')
                genes = [g.strip() for g in genes_raw if g.strip()]
            else:
                return False, [], f"不支持的文件格式: {ext}（仅支持txt/xlsx）"

            if not genes:
                return False, [], "文件中未找到基因名"

            return True, genes, ""
        except Exception as e:
            return False, [], f"读取基因列表失败: {e}"

    def run_graph_test(self, gene_filter_mode='all', n_top=2000, gene_list_file=None, progress_callback=None):
        """运行graph_test分析
        Args:
            gene_filter_mode: 'all' / 'hvg' / 'list'
            n_top: 高变基因前N个（mode=hvg时使用）
            gene_list_file: 外部基因列表文件路径（mode=list时使用）
            progress_callback: 进度回调函数(msg: str) -> None
        Returns:
            (success, result_df_or_error, is_error)
        """
        def _log(msg):
            print(f"[GenelistsAnalysis] {msg}")
            if progress_callback:
                progress_callback(msg)

        if not self.has_shared_data():
            return False, "未共享CDS rds路径，请先在数据加载类页面加载rds文件", True

        try:
            output_dir = self._get_genelists_output_dir()
        except ValueError as e:
            return False, str(e), True

        # 准备R脚本参数
        r_args = [
            self.cds_rds_path,
            output_dir,
            self.dataset_name,
            gene_filter_mode,
        ]

        if gene_filter_mode == 'hvg':
            try:
                n_top_int = int(n_top)
                if n_top_int <= 0:
                    return False, "高变基因数N必须为正整数", True
            except (ValueError, TypeError):
                return False, f"高变基因数N无效: {n_top}", True
            r_args.append(str(n_top_int))
        else:
            r_args.append("2000")  # 占位

        if gene_filter_mode == 'list':
            if not gene_list_file or not os.path.exists(gene_list_file):
                return False, f"基因列表文件不存在: {gene_list_file}", True
            r_args.append(gene_list_file)
        else:
            r_args.append("")  # 占位

        _log(f"开始运行graph_test，模式={gene_filter_mode}")
        if gene_filter_mode == 'hvg':
            _log(f"高变基因前 {r_args[4]} 个")
        elif gene_filter_mode == 'list':
            _log(f"基因列表文件: {gene_list_file}")

        stdout, stderr = self._run_r_script(r_args, progress_callback=progress_callback)

        if stdout is None:
            return False, stderr or "R脚本执行失败", True

        # 解析TSV路径
        tsv_path = self._parse_tsv_path(stdout)
        if not tsv_path or not os.path.exists(tsv_path):
            # 按约定路径尝试
            expected_tsv = os.path.join(output_dir, f"{self.dataset_name}_graph_test_result.tsv")
            if os.path.exists(expected_tsv):
                tsv_path = expected_tsv
            else:
                return False, f"R脚本执行完成但未找到TSV文件\nR输出: {stdout}", True

        _log(f"TSV结果路径: {tsv_path}")

        # 读取TSV为DataFrame
        try:
            result_df = pd.read_csv(tsv_path, sep='\t')
        except Exception as e:
            return False, f"读取TSV结果失败: {e}", True

        # 缓存结果
        self._cached_result_df = result_df
        self._cached_tsv_path = tsv_path

        _log(f"结果行数: {len(result_df)}")
        return True, result_df, False

    def filter_significant_genes(self, threshold_field='morans_I_p', threshold_value=0.05):
        """从缓存的结果DataFrame中筛显著基因（不重跑R脚本）
        Args:
            threshold_field: 'morans_I_p' 或 'morans_I_q'
            threshold_value: 阈值（默认0.05）
        Returns:
            (success, sig_df_or_error, is_error)
        """
        if self._cached_result_df is None:
            return False, "无缓存结果，请先运行graph_test", True

        if threshold_field not in self._cached_result_df.columns:
            return False, f"结果中无字段: {threshold_field}（可用: {list(self._cached_result_df.columns)}）", True

        try:
            threshold = float(threshold_value)
        except (ValueError, TypeError):
            return False, f"阈值无效: {threshold_value}", True

        sig_df = self._cached_result_df[
            (self._cached_result_df[threshold_field] < threshold) &
            (self._cached_result_df[threshold_field].notna())
        ].copy()

        # 按p/q值升序排序
        sig_df = sig_df.sort_values(by=threshold_field, ascending=True).reset_index(drop=True)

        return True, sig_df, False

    def get_cached_result(self):
        """获取缓存的graph_test结果（DataFrame或None）"""
        return self._cached_result_df

    # ========== 阶段三：Spearman相关性分析（上下调分类） ==========

    def _write_temp_gene_list(self, gene_list):
        """将基因列表写入临时txt文件（供R脚本读取）
        Returns: 临时文件路径
        """
        import tempfile
        tmp_dir = os.path.join(OUT_BASE, "monocle3", "genelists_test", "_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f"_stage3_genes_{os.getpid()}.txt")
        with open(tmp_path, 'w', encoding='utf-8') as f:
            for gene in gene_list:
                f.write(f"{gene}\n")
        return tmp_path

    def run_spearman_analysis(self, calc_scope='sig', threshold_field='p_value',
                              threshold_value=0.05, algorithm='spearman', progress_callback=None):
        """阶段三：运行基因表达与伪时间关系分析（支持多种算法）

        Args:
            calc_scope: 'sig'=仅显著基因（从阶段二缓存取） / 'all'=全部基因（从阶段一缓存取）
            threshold_field: 阈值字段 'p_value' 或 'q_value'（用于阶段三分类）
            threshold_value: 阈值（默认0.05）
            algorithm: 分析算法 'spearman' / 'loess' / 'wilcoxon'（默认spearman）
            progress_callback: 进度回调函数(msg: str) -> None
        Returns:
            (success, result_df_or_error, is_error)
        """
        def _log(msg):
            print(f"[Stage3Analysis] {msg}")
            if progress_callback:
                progress_callback(msg)

        if not self.has_shared_data():
            return False, "未共享CDS rds路径，请先在数据加载类页面加载rds文件", True

        # 检查缓存结果
        cached_df = self._cached_result_df
        if cached_df is None:
            return False, "无graph_test结果，请先运行阶段一", True

        # 根据calc_scope获取基因列表
        if calc_scope == 'sig':
            # 从阶段二缓存筛选显著基因
            sig_field = threshold_field if threshold_field in cached_df.columns else 'p_value'
            try:
                threshold = float(threshold_value)
            except (ValueError, TypeError):
                return False, f"阈值无效: {threshold_value}", True

            if sig_field not in cached_df.columns:
                return False, f"缓存结果中无字段: {sig_field}（可用: {list(cached_df.columns)}）", True

            sig_df = cached_df[
                (cached_df[sig_field] < threshold) &
                (cached_df[sig_field].notna())
            ].copy()
            gene_list = sig_df['gene_id'].tolist() if 'gene_id' in sig_df.columns else []
            _log(f"计算范围: 显著基因({sig_field}<{threshold}), 共 {len(gene_list)} 个")
        else:
            # 全部基因（从阶段一缓存取）
            gene_list = cached_df['gene_id'].tolist() if 'gene_id' in cached_df.columns else []
            _log(f"计算范围: 全部基因, 共 {len(gene_list)} 个")

        if not gene_list:
            return False, "基因列表为空，无法计算Spearman相关性", True

        try:
            output_dir = self._get_genelists_output_dir()
        except ValueError as e:
            return False, str(e), True

        # 写临时基因列表文件
        gene_list_path = self._write_temp_gene_list(gene_list)
        _log(f"基因列表临时文件: {gene_list_path}")

        # 准备R脚本参数
        r_args = [
            self.cds_rds_path,
            gene_list_path,
            output_dir,
            self.dataset_name,
            algorithm,
        ]

        _log(f"开始运行{algorithm}分析...")

        # 调用R脚本（复用_run_r_script，但需要切换脚本路径）
        stdout, stderr = self._run_r_script(r_args, progress_callback=progress_callback,
                                             script_path=self._r_stage3_script_path)

        # 清理临时文件
        try:
            os.remove(gene_list_path)
        except Exception:
            pass

        if stdout is None:
            return False, stderr or "R脚本执行失败", True

        # 解析TSV路径
        tsv_path = self._parse_tsv_path(stdout)
        if not tsv_path or not os.path.exists(tsv_path):
            expected_tsv = os.path.join(output_dir, f"{self.dataset_name}_spearman_result.tsv")
            if os.path.exists(expected_tsv):
                tsv_path = expected_tsv
            else:
                return False, f"R脚本执行完成但未找到TSV文件\nR输出: {stdout}", True

        _log(f"TSV结果路径: {tsv_path}")

        # 读取TSV为DataFrame
        try:
            result_df = pd.read_csv(tsv_path, sep='\t')
        except Exception as e:
            return False, f"读取TSV结果失败: {e}", True

        # 缓存结果
        self._cached_spearman_df = result_df
        self._cached_spearman_tsv_path = tsv_path

        _log(f"结果行数: {len(result_df)}")
        return True, result_df, False

    def classify_up_down_genes(self, threshold_field='p_value', threshold_value=0.05):
        """从缓存的Spearman结果中分类上下调基因（不重跑R脚本）

        分类规则：
        - rho > 0 且 p_value/q_value < 阈值 → up（上调）
        - rho < 0 且 p_value/q_value < 阈值 → down（下调）
        - p_value/q_value >= 阈值 → not_significant（不显著）
        - rho = NA → not_significant

        Args:
            threshold_field: 'p_value' 或 'q_value'
            threshold_value: 阈值（默认0.05）
        Returns:
            (success, result_dict, is_error)
            result_dict: {
                'all': 总体DataFrame（含direction列）,
                'up': 上调DataFrame,
                'down': 下调DataFrame
            }
        """
        if self._cached_spearman_df is None:
            return False, "无Spearman结果，请先运行阶段三", True

        cached_df = self._cached_spearman_df.copy()

        if threshold_field not in cached_df.columns:
            return False, f"结果中无字段: {threshold_field}（可用: {list(cached_df.columns)}）", True

        try:
            threshold = float(threshold_value)
        except (ValueError, TypeError):
            return False, f"阈值无效: {threshold_value}", True

        # 分类
        import numpy as np
        direction = np.where(
            cached_df['rho'].isna() | cached_df[threshold_field].isna() | (cached_df[threshold_field] >= threshold),
            'not_significant',
            np.where(cached_df['rho'] > 0, 'up', 'down')
        )
        cached_df['direction'] = direction

        up_df = cached_df[cached_df['direction'] == 'up'].copy()
        down_df = cached_df[cached_df['direction'] == 'down'].copy()

        # 按 rho 绝对值降序排序
        up_df = up_df.reindex(up_df['rho'].abs().sort_values(ascending=False).index)
        down_df = down_df.reindex(down_df['rho'].abs().sort_values(ascending=False).index)

        # 缓存分类后的结果（含direction列）
        self._cached_stage3_result_df = cached_df

        result = {
            'all': cached_df,
            'up': up_df,
            'down': down_df,
        }
        return True, result, False

    def get_cached_spearman_result(self):
        """获取缓存的Spearman结果（DataFrame或None）"""
        return self._cached_spearman_df

    def get_cached_stage3_result(self):
        """获取阶段三分类后的结果（含direction列）"""
        return self._cached_stage3_result_df

    def _run_r_script(self, args, progress_callback=None, script_path=None):
        """调用R脚本（subprocess方式，避免rpy2崩溃）
        使用subprocess.Popen + 行读取实现实时进度输出

        Args:
            args: R脚本参数列表
            progress_callback: 进度回调函数
            script_path: R脚本路径（默认用self._r_script_path）
        """
        try:
            r_script = script_path or self._r_script_path
            short_args = []
            for arg in args:
                if isinstance(arg, str) and ('\\' in arg or '/' in arg):
                    short_path = self._get_short_path(arg)
                    short_args.append(short_path if short_path else arg)
                else:
                    short_args.append(arg)

            cmd = [self._rscript_path, self._get_short_path(r_script)] + short_args

            # 使用Popen实时读取stdout
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并stderr到stdout
                bufsize=1,
                text=False,
            )

            collected_lines = []
            try:
                while True:
                    line_bytes = proc.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode('utf-8', errors='ignore').rstrip()
                    if line:
                        collected_lines.append(line)
                        if progress_callback and line.startswith('['):
                            # 只回调形如 [xxx] xxx 的进度行（兼容[Genelists]和[Stage3]）
                            progress_callback(line)
                proc.wait(timeout=900)  # 15分钟超时
            except subprocess.TimeoutExpired:
                proc.kill()
                return None, "R脚本执行超时(>15分钟)"

            stdout = "\n".join(collected_lines).strip()
            if proc.returncode != 0:
                return None, stdout or f"R脚本返回码非0: {proc.returncode}"

            return stdout, None
        except Exception as e:
            print(f"调用R脚本异常: {e}")
            traceback.print_exc()
            return None, str(e)

    def _parse_tsv_path(self, stdout):
        """从R脚本输出中解析TSV文件路径"""
        for line in stdout.split('\n'):
            line = line.strip()
            if '结果已保存' in line and '.tsv' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    path = parts[1].strip()
                    if os.path.exists(path):
                        return path
            if line.endswith('.tsv') and os.path.exists(line):
                return line
        return None

    def _parse_image_path(self, stdout):
        """从R脚本输出中解析图片文件路径"""
        for line in stdout.split('\n'):
            line = line.strip()
            if '火山图已保存' in line and '.png' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    path = parts[1].strip()
                    if os.path.exists(path):
                        return path
            if line.endswith('.png') and os.path.exists(line):
                return line
        return None

    # ========== 阶段四：火山图可视化 ==========

    def run_volcano_plot(self, x_axis='rho', y_axis='p_value',
                         fc_threshold=1.0, p_threshold=0.05, top_n=10,
                         progress_callback=None):
        """阶段四：基于阶段三结果绘制火山图

        Args:
            x_axis: 'rho' 或 'log2fc'（X轴指标）
            y_axis: 'p_value' 或 'q_value'（Y轴指标）
            fc_threshold: FC阈值（默认1.0）
            p_threshold: p/q值阈值（默认0.05）
            top_n: 标记基因数量（默认10）
            progress_callback: 进度回调函数(msg: str) -> None
        Returns:
            (success, image_path_or_error, is_error)
        """
        def _log(msg):
            print(f"[Stage4Analysis] {msg}")
            if progress_callback:
                progress_callback(msg)

        # 检查阶段三缓存结果
        if self._cached_spearman_tsv_path is None:
            return False, "无阶段三结果，请先运行阶段三", True

        input_tsv = self._cached_spearman_tsv_path
        if not os.path.exists(input_tsv):
            return False, f"阶段三结果文件不存在: {input_tsv}", True

        _log(f"输入文件: {input_tsv}")

        try:
            output_dir = self._get_genelists_output_dir()
        except ValueError as e:
            return False, str(e), True

        # 准备R脚本参数
        r_args = [
            input_tsv,
            output_dir,
            self.dataset_name,
            x_axis,
            y_axis,
            str(fc_threshold),
            str(p_threshold),
            str(top_n),
        ]

        # 如果需要计算log2FC，传递CDS路径
        if x_axis == 'log2fc' and self.cds_rds_path:
            r_args.append(self.cds_rds_path)

        _log(f"开始绘制火山图...")
        _log(f"  X轴: {x_axis}")
        _log(f"  Y轴: {y_axis}")
        _log(f"  FC阈值: {fc_threshold}")
        _log(f"  p阈值: {p_threshold}")
        _log(f"  标记基因数: {top_n}")

        stage4_script = os.path.join(os.path.dirname(__file__), 'run_monocle_genelists_stage4.R')
        stdout, stderr = self._run_r_script(r_args, progress_callback=progress_callback,
                                             script_path=stage4_script)

        if stdout is None:
            return False, stderr or "R脚本执行失败", True

        # 解析图片路径
        image_path = self._parse_image_path(stdout)
        if not image_path or not os.path.exists(image_path):
            expected_image = os.path.join(output_dir, f"{self.dataset_name}_volcano.png")
            if os.path.exists(expected_image):
                image_path = expected_image
            else:
                return False, f"R脚本执行完成但未找到图片文件\nR输出: {stdout}", True

        _log(f"火山图已保存: {image_path}")
        return True, image_path, False
