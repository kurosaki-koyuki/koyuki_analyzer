# -*- coding: utf-8 -*-
"""
bulk WGCNA分析 Python接口层
此文件不包含任何R代码，只负责：
1. 数据准备和处理
2. 参数传递到R环境
3. 调用R脚本中的四阶段代码
"""

from script.utils_layer.import_config import os, sys, traceback, np, pd, get_r_script_path, tempfile, shutil
from typing import Optional, List, Dict, Any

from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
from script.utils_layer.import_config import importr as _importr


class WgcnaAnalysis:
    """bulk WGCNA分析 Python接口层 - 不含R代码"""

    _r_debug_log: List[Dict[str, Any]] = []

    R_SCRIPT_PATH = get_r_script_path(__file__, "wgcna_analysis.R")

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
        self._stage5_completed = False
        self._stage6_completed = False
        self._init_r_environment()

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
        if self.adata is None:
            return []
        return list(self.adata.obs.columns)

    def get_obs_unique_values(self, col_name):
        if self.adata is None or col_name not in self.adata.obs.columns:
            return []
        unique_vals = self.adata.obs[col_name].unique()
        return sorted([str(v) for v in unique_vals if pd.notna(v)])

    def _load_r_script(self):
        if self._r_script_loaded:
            return True
        if not os.path.exists(self.R_SCRIPT_PATH):
            print(f"[R脚本检查] 脚本不存在: {self.R_SCRIPT_PATH}")
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
            _importr('WGCNA')
            _importr('dplyr')
            _importr('stringr')
            _importr('pheatmap')
            _importr('grDevices')
            _importr('openxlsx')
            _importr('ggplot2')
            _importr('gridExtra')
            _importr('clusterProfiler')
            _importr('org.Hs.eg.db')
            self._r_packages_loaded = True
            print("[R包加载] WGCNA, dplyr, stringr, pheatmap, grDevices, openxlsx, ggplot2, gridExtra, clusterProfiler, org.Hs.eg.db 已通过importr加载")
            return True
        except Exception as e:
            print(f"[R包加载失败] {e}")
            return False

    def _read_stage_code(self, stage: str) -> str:
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

    def prepare_expr_data(self, clinical_col=None, clinical_groups=None,
                          filter1_col=None, filter1_groups=None,
                          filter2_col=None, filter2_groups=None) -> Optional[pd.DataFrame]:
        if self.adata is None:
            return None

        X = self.adata.X
        if hasattr(X, 'toarray'):
            X = X.toarray()
        df = pd.DataFrame(X.T, index=self.adata.var_names, columns=self.adata.obs_names)

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
        
        trait_data = self.adata.obs.loc[selected_samples, [clinical_col]] if clinical_col else None
        if trait_data is not None:
            trait_data = trait_data.rename(columns={clinical_col: 'Cluster'})
        
        return df.loc[:, selected_samples], trait_data

    def run_stage1_gene_filter(self,
                             filter_mode: str = "MAD筛选",
                             mad_threshold: int = 5000,
                             external_gene_file: str = None,
                             clinical_col=None, clinical_groups=None,
                             filter1_col=None, filter1_groups=None,
                             filter2_col=None, filter2_groups=None) -> bool:
        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if not self._load_r_packages():
            raise RuntimeError("R包加载失败")

        if not self._load_r_script():
            raise RuntimeError("R脚本加载失败")

        expr_data, trait_data = self.prepare_expr_data(
            clinical_col, clinical_groups,
            filter1_col, filter1_groups,
            filter2_col, filter2_groups
        )
        if expr_data is None:
            raise RuntimeError("数据准备失败，请检查筛选条件")

        if filter_mode == '外部基因列表' and external_gene_file:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            for _ in range(4):
                base_dir = os.path.dirname(base_dir)
            gene_list_path = os.path.join(base_dir, 'appdata', 'genelists', external_gene_file)
            if not os.path.exists(gene_list_path):
                raise RuntimeError(f"外部基因列表文件不存在: {gene_list_path}")
            
            try:
                gene_df = pd.read_excel(gene_list_path)
                gene_list = gene_df.iloc[:, 0].tolist()
                gene_list = [str(g).strip() for g in gene_list if pd.notna(g) and str(g).strip()]
                
                available_genes = set(expr_data.index)
                matched_genes = [g for g in gene_list if g in available_genes]
                
                print(f"[外部基因列表] 加载了 {len(gene_list)} 个基因，匹配到 {len(matched_genes)} 个在表达矩阵中")
                
                if len(matched_genes) < 10:
                    raise RuntimeError(f"匹配到的基因太少 ({len(matched_genes)}个)，请检查基因列表格式")
                
                expr_data = expr_data.loc[matched_genes, :]
            except Exception as e:
                raise RuntimeError(f"读取外部基因列表失败: {str(e)}")

        if self.dataset_output_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="wgcna_")
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import pandas2ri, StrVector, IntVector
            from rpy2.robjects.conversion import localconverter

            with localconverter(pandas2ri.converter):
                self.robjects.globalenv['expr_data'] = expr_data
                if trait_data is not None:
                    self.robjects.globalenv['trait_data'] = trait_data

            self.robjects.globalenv['filter_mode'] = StrVector([filter_mode])
            self.robjects.globalenv['mad_threshold'] = IntVector([int(mad_threshold)]) if filter_mode == 'MAD筛选' else IntVector([0])
            self.robjects.globalenv['output_dir'] = StrVector([output_dir])

            self.robjects.r('enableWGCNAThreads(nThreads = 0.75 * parallel::detectCores())')
            
            r_code = self._read_stage_code("STAGE1")
            self.robjects.r(r_code)

            self._stage1_completed = True
            self._stage2_completed = False
            self._stage3_completed = False
            self._stage4_completed = False
            self._stage5_completed = False
            print(f"[阶段一] 数据准备+基因筛选完成 (方式: {filter_mode})")
            return True

        except Exception as e:
            print(f"[阶段一失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段一R代码执行失败: {str(e)}")

    def run_stage1_mad_filter(self,
                             mad_threshold: int = 5000,
                             clinical_col=None, clinical_groups=None,
                             filter1_col=None, filter1_groups=None,
                             filter2_col=None, filter2_groups=None) -> bool:
        return self.run_stage1_gene_filter(
            filter_mode="MAD筛选",
            mad_threshold=mad_threshold,
            clinical_col=clinical_col,
            clinical_groups=clinical_groups,
            filter1_col=filter1_col,
            filter1_groups=filter1_groups,
            filter2_col=filter2_col,
            filter2_groups=filter2_groups
        )

    def run_stage2_soft_threshold(self, network_type: str = "unsigned", 
                                   rsquared_cut: float = 0.85,
                                   manual_power: int = None) -> str:
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, FloatVector, IntVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['network_type'] = StrVector([network_type])
            self.robjects.globalenv['rsquared_cut'] = FloatVector([rsquared_cut])
            
            if manual_power is not None:
                self.robjects.globalenv['manual_power'] = IntVector([manual_power])

            r_code = self._read_stage_code("STAGE2")
            self.robjects.r(r_code)

            self._stage2_completed = True
            print(f"[阶段二] 软阈值选择完成")

            try:
                power_estimate = int(self.robjects.r('wgcna_power_estimate')[0])
                print(f"[阶段二] 推荐软阈值: {power_estimate}")
                return str(power_estimate)
            except:
                return None

        except Exception as e:
            print(f"[阶段二失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段二R代码执行失败: {str(e)}")

    def run_stage3_network_construction(self, power: int = 7,
                                        min_module_size: int = 30,
                                        merge_cut_height: float = 0.25,
                                        stage3_width: int = 1200,
                                        stage3_height: int = 1200) -> bool:
        if not self._stage1_completed:
            raise RuntimeError("请先运行阶段一")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector, FloatVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['power'] = IntVector([int(power)])
            self.robjects.globalenv['min_module_size'] = IntVector([int(min_module_size)])
            self.robjects.globalenv['merge_cut_height'] = FloatVector([float(merge_cut_height)])
            self.robjects.globalenv['stage3_width'] = IntVector([int(stage3_width)])
            self.robjects.globalenv['stage3_height'] = IntVector([int(stage3_height)])

            r_code = self._read_stage_code("STAGE3")
            self.robjects.r(r_code)

            self._stage3_completed = True
            print(f"[阶段三] 网络构建+模块识别完成")
            return True

        except Exception as e:
            print(f"[阶段三失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段三R代码执行失败: {str(e)}")

    def run_stage4_module_trait(self, trait_cols=None, stage4_width: int = 1200, stage4_height: int = 1000, cell_width: int = 80, cell_height: int = 35, show_significance: bool = True) -> bool:
        if not self._stage3_completed:
            raise RuntimeError("请先运行阶段三")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        if self.dataset_output_dir is None:
            output_dir = self._temp_dir
        else:
            output_dir = self.dataset_output_dir

        try:
            from rpy2.robjects import StrVector, IntVector, pandas2ri
            from rpy2.robjects.conversion import localconverter

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            self.robjects.globalenv['stage4_width'] = IntVector([int(stage4_width)])
            self.robjects.globalenv['stage4_height'] = IntVector([int(stage4_height)])
            self.robjects.globalenv['cell_width'] = IntVector([int(cell_width)])
            self.robjects.globalenv['cell_height'] = IntVector([int(cell_height)])
            self.robjects.globalenv['show_significance'] = show_significance

            if trait_cols and self.adata is not None:
                trait_data = self.adata.obs[trait_cols]
                
                try:
                    me_rownames = self.robjects.r('rownames(wgcna_net$MEs)')
                    me_samples = [str(s) for s in me_rownames]
                    print(f"[阶段四] MEs样本数: {len(me_samples)}")
                    print(f"[阶段四] MEs样本示例: {me_samples[:5]}")
                    
                    trait_data = trait_data.loc[me_samples, :]
                    print(f"[阶段四] 对齐后性状数据维度: {trait_data.shape}")
                except Exception as e:
                    print(f"[阶段四] 无法获取MEs行名，使用原始性状数据: {e}")
                
                with localconverter(pandas2ri.converter):
                    self.robjects.globalenv['wgcna_trait_data'] = trait_data
                print(f"[阶段四] 使用自定义性状列: {trait_cols}")
                print(f"[阶段四] 性状数据维度: {trait_data.shape}")
                print(f"[阶段四] 性状数据行名示例: {list(trait_data.index[:5])}")
            else:
                print("[阶段四] 未提供性状列，将使用阶段一保存的trait_data")

            r_code = self._read_stage_code("STAGE4")
            self.robjects.r(r_code)

            self._stage4_completed = True
            print(f"[阶段四] 模块-性状关联+出图完成")
            return True

        except Exception as e:
            print(f"[阶段四失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段四R代码执行失败: {str(e)}")

    def get_stage_status(self):
        return {
            'stage1': self._stage1_completed,
            'stage2': self._stage2_completed,
            'stage3': self._stage3_completed,
            'stage4': self._stage4_completed,
            'stage5': self._stage5_completed
        }

    def get_modules(self):
        if not self._stage3_completed or not self.robjects:
            return []
        
        try:
            modules = self.robjects.r('''
                if (exists("wgcna_net") && !is.null(wgcna_net)) {
                    unique(labels2colors(wgcna_net$colors))
                } else {
                    character(0)
                }
            ''')
            module_list = [str(m) for m in modules]
            return module_list
        except Exception as e:
            print(f"[获取模块列表失败] {e}")
            return []

    def run_stage5_go_kegg(self, selected_modules=None, organism="hsa", 
                          go_padj_cutoff=0.05, kegg_padj_cutoff=0.05,
                          go_top_n=15, kegg_top_n=15) -> bool:
        if not self._stage3_completed:
            raise RuntimeError("请先运行阶段三")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        print(f"[阶段五] GO/KEGG分析开始")
        print(f"[阶段五] 物种: {organism}")
        print(f"[阶段五] GO校正p值阈值: {go_padj_cutoff}")
        print(f"[阶段五] KEGG校正p值阈值: {kegg_padj_cutoff}")
        print(f"[阶段五] GO展示条目数: {go_top_n}")
        print(f"[阶段五] KEGG展示条目数: {kegg_top_n}")

        output_dir = self.dataset_output_dir if self.dataset_output_dir else self._temp_dir
        print(f"[阶段五] 使用输出目录: {output_dir}")

        try:
            from rpy2.robjects import StrVector

            self.robjects.globalenv['output_dir'] = StrVector([output_dir])
            
            if selected_modules:
                self.robjects.globalenv['selected_modules'] = StrVector(selected_modules)
            
            self.robjects.globalenv['organism'] = StrVector([organism])
            self.robjects.globalenv['go_padj_cutoff'] = go_padj_cutoff
            self.robjects.globalenv['kegg_padj_cutoff'] = kegg_padj_cutoff
            self.robjects.globalenv['go_top_n'] = go_top_n
            self.robjects.globalenv['kegg_top_n'] = kegg_top_n

            r_code = self._read_stage_code("STAGE5")
            self.robjects.r(r_code)

            print(f"[阶段五] 检查输出目录文件: {output_dir}")
            if os.path.exists(output_dir):
                for f in sorted(os.listdir(output_dir)):
                    if any(ext in f for ext in ['.pdf', '.png', '.xlsx', '.txt']):
                        f_path = os.path.join(output_dir, f)
                        f_size = os.path.getsize(f_path) / 1024
                        print(f"[阶段五] 生成文件: {f} ({f_size:.2f} KB)")
            else:
                print(f"[阶段五] 输出目录不存在: {output_dir}")

            self._stage5_completed = True
            print(f"[阶段五] GO和KEGG富集分析完成")
            return True

        except Exception as e:
            print(f"[阶段五失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段五R代码执行失败: {str(e)}")

    def run_stage6_export_genes(self, selected_modules=None, save_path=None, base_name=None, merge_modules=False, export_go_kegg=False) -> bool:
        if not self._stage3_completed:
            raise RuntimeError("请先运行阶段三")

        if not self.robjects:
            raise RuntimeError("R环境不可用")

        print(f"[阶段六] save_path参数: {save_path}")
        print(f"[阶段六] base_name参数: {base_name}")
        print(f"[阶段六] export_go_kegg参数: {export_go_kegg}")
        
        r_output_dir = self.dataset_output_dir if self.dataset_output_dir else self._temp_dir
        print(f"[阶段六] R输出目录: {r_output_dir}")
        
        final_save_dir = save_path if save_path else r_output_dir
        if not os.path.exists(final_save_dir):
            os.makedirs(final_save_dir, exist_ok=True)
        print(f"[阶段六] 最终保存目录: {final_save_dir}")

        try:
            from rpy2.robjects import StrVector

            self.robjects.globalenv['output_dir'] = StrVector([r_output_dir])
            
            if selected_modules:
                self.robjects.globalenv['selected_modules'] = StrVector(selected_modules)
            
            if base_name:
                self.robjects.globalenv['base_name'] = StrVector([base_name])
            else:
                self.robjects.globalenv['base_name'] = StrVector(['module_genes'])
            
            self.robjects.globalenv['merge_modules'] = merge_modules

            r_code = self._read_stage_code("STAGE6")
            self.robjects.r(r_code)

            if export_go_kegg and selected_modules:
                print("[阶段六] 开始导出GO/KEGG分析结果...")
                for mod in selected_modules:
                    go_kegg_patterns = [
                        f"GO_bubble_{mod}.png",
                        f"GO_bubble_{mod}.pdf",
                        f"GO_bar_{mod}.png",
                        f"GO_bar_{mod}.pdf",
                        f"GO_{mod}.txt",
                        f"GO_result_{mod}.xlsx",
                        f"KEGG_bubble_{mod}.png",
                        f"KEGG_bubble_{mod}.pdf",
                        f"KEGG_bar_{mod}.png",
                        f"KEGG_bar_{mod}.pdf",
                        f"KEGG_{mod}.txt",
                        f"KEGG_result_{mod}.xlsx"
                    ]
                    for pattern in go_kegg_patterns:
                        src_path = os.path.join(r_output_dir, pattern)
                        dst_path = os.path.join(final_save_dir, pattern)
                        if os.path.exists(src_path):
                            if r_output_dir != final_save_dir:
                                shutil.copy2(src_path, dst_path)
                            print(f"[阶段六] 复制GO/KEGG图表: {src_path} -> {dst_path}")

            gene_xlsx_patterns = [
                f"{base_name}.xlsx" if merge_modules else f"{base_name}_{mod}.xlsx"
                for mod in selected_modules
            ] if selected_modules else []
            for pattern in gene_xlsx_patterns:
                src_path = os.path.join(r_output_dir, pattern)
                dst_path = os.path.join(final_save_dir, pattern)
                if os.path.exists(src_path):
                    if r_output_dir != final_save_dir:
                        shutil.copy2(src_path, dst_path)
                    print(f"[阶段六] 复制基因列表: {src_path} -> {dst_path}")

            self._stage6_completed = True
            print(f"[阶段六] 基因集合导出完成")
            return True

        except Exception as e:
            print(f"[阶段六失败] {e}")
            traceback.print_exc()
            raise RuntimeError(f"阶段六R代码执行失败: {str(e)}")


_analysis_instance = None

def get_wgcna_analysis() -> WgcnaAnalysis:
    global _analysis_instance
    if _analysis_instance is None:
        _analysis_instance = WgcnaAnalysis()
    return _analysis_instance