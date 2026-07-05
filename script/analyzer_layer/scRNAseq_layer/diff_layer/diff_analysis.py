# -*- coding: utf-8 -*-
"""
差异分析生信分析算法脚本 - 差异分析页面的核心生信分析方法
包含分组加载、差异基因分析、显著性检验、导出等功能

优化：使用向量化操作和稀疏矩阵处理，提升大规模数据处理速度
"""

from script.utils_layer.import_config import *


class DiffAnalysis:
    """差异分析类 - 包含差异分析页面的核心生信分析方法"""
    
    def __init__(self):
        self.adata = None
        self.diff_gene_df = None
        self.current_fig = None
        self.dataset_output_dir = None
        self.group_col = None
        self.selected_groups = None
    
    def set_adata(self, adata):
        """设置当前adata对象"""
        self.adata = adata
    
    def set_dataset_output_dir(self, dataset_output_dir):
        """设置数据集输出目录"""
        self.dataset_output_dir = dataset_output_dir
    
    def get_available_groups(self):
        """获取所有可用于分组的注释列"""
        if self.adata is None:
            return []
        
        groups = []
        for col in self.adata.obs.columns:
            try:
                nunique = self.adata.obs[col].nunique()
                if nunique >= 2 and nunique <= 100:
                    groups.append(col)
            except Exception:
                continue
        
        return groups
    
    def get_group_unique_vals(self, group_col):
        """获取分组列的唯一值列表（纯数据，不操作控件）"""
        if self.adata is None:
            return []
        if not group_col or group_col not in self.adata.obs.columns:
            return []
        return sorted([str(v) for v in self.adata.obs[group_col].unique()])

    def bh_fdr(self, pvals):
        """Benjamini-Hochberg FDR校正"""
        p = np.asarray(pvals, dtype=np.float64)
        q = np.ones_like(p)
        finite = np.isfinite(p)
        if not finite.any():
            return q
        idx = np.where(finite)[0]
        order = idx[np.argsort(p[idx])]
        ranked = p[order] * len(order) / np.arange(1, len(order) + 1)
        ranked = np.minimum.accumulate(ranked[::-1])[::-1]
        q[order] = np.clip(ranked, 0, 1)
        return q
    
    def run_diff_analysis(self, group_col, selected_groups, method="mannwhitney", 
                          min_cells=3, min_expr=0, use_fdr=True,
                          pval_threshold=0.05, logfc_threshold=1.0, pct_threshold=0.1):
        """执行差异分析
        
        Args:
            group_col: 分组列名
            selected_groups: 选中的分组列表（至少2个）
            method: 检验方法 (目前只支持mannwhitney)
            min_cells: 基因表达的最小细胞数
            min_expr: 基因表达的最小值
            use_fdr: 是否使用FDR校正
            pval_threshold: p值阈值
            logfc_threshold: logFC阈值
            pct_threshold: 表达百分比阈值
        
        Returns:
            DataFrame with differential expression results
        """
        if self.adata is None:
            raise ValueError("请先加载数据")
        
        if len(selected_groups) < 2:
            raise ValueError("请至少选择2个分组进行比较")
        
        if group_col not in self.adata.obs.columns:
            raise ValueError(f"分组列 {group_col} 不存在")
        
        self.group_col = group_col
        self.selected_groups = selected_groups
        
        # 构建组名称
        group1_name = selected_groups[0]
        group2_name = selected_groups[1] if len(selected_groups) > 1 else "组2"
        
        # 过滤只包含选中分组的细胞
        mask = self.adata.obs[group_col].isin(selected_groups)
        adata_subset = self.adata[mask].copy()
        
        if len(adata_subset) == 0:
            raise ValueError("没有符合条件的细胞")
        
        # 获取两组细胞的索引
        group1_cells = adata_subset.obs[adata_subset.obs[group_col] == selected_groups[0]].index.tolist()
        group2_cells = adata_subset.obs[adata_subset.obs[group_col] == selected_groups[1]].index.tolist()
        
        if len(group1_cells) < min_cells or len(group2_cells) < min_cells:
            raise ValueError(f"细胞数不足：组1={len(group1_cells)}, 组2={len(group2_cells)}, 最小要求={min_cells}")
        
        # 获取表达矩阵（保持稀疏格式）
        X = adata_subset.X
        if issparse(X):
            X = X.tocsr()
        
        # 获取细胞索引位置
        all_cells = adata_subset.obs.index.tolist()
        group1_idx = [all_cells.index(cell) for cell in group1_cells]
        group2_idx = [all_cells.index(cell) for cell in group2_cells]
        
        # 提取两组细胞的表达矩阵
        X1 = X[group1_idx, :]
        X2 = X[group2_idx, :]
        
        # 计算CP10K标准化
        libsize1 = np.array(X1.sum(axis=1)).flatten()
        libsize2 = np.array(X2.sum(axis=1)).flatten()
        
        # 避免除零
        libsize1 = np.maximum(libsize1, 1)
        libsize2 = np.maximum(libsize2, 1)
        
        # CP10K标准化
        if issparse(X1):
            cp10k1 = X1.multiply(10000.0 / libsize1[:, np.newaxis])
            cp10k2 = X2.multiply(10000.0 / libsize2[:, np.newaxis])
        else:
            cp10k1 = X1 * (10000.0 / libsize1[:, np.newaxis])
            cp10k2 = X2 * (10000.0 / libsize2[:, np.newaxis])
        
        # log1p转换用于统计检验
        if issparse(cp10k1):
            log_expr1 = np.log1p(cp10k1.toarray())
            log_expr2 = np.log1p(cp10k2.toarray())
        else:
            log_expr1 = np.log1p(cp10k1)
            log_expr2 = np.log1p(cp10k2)
        
        # 计算表达百分比
        if issparse(X1):
            pct1 = np.array((X1 > 0).mean(axis=0)).flatten()
            pct2 = np.array((X2 > 0).mean(axis=0)).flatten()
        else:
            pct1 = (X1 > 0).mean(axis=0)
            pct2 = (X2 > 0).mean(axis=0)
        
        # 计算平均CP10K
        if issparse(cp10k1):
            mean_cp10k1 = np.array(cp10k1.mean(axis=0)).flatten()
            mean_cp10k2 = np.array(cp10k2.mean(axis=0)).flatten()
        else:
            mean_cp10k1 = cp10k1.mean(axis=0)
            mean_cp10k2 = cp10k2.mean(axis=0)
        
        # 计算log2FC（添加伪计数0.1）- 组1/组2，使上调表示组1高于组2
        log2fc = np.log2((mean_cp10k1 + 0.1) / (mean_cp10k2 + 0.1))
        
        # Mann-Whitney U检验（向量化操作）
        try:
            pvals = mannwhitneyu(log_expr1, log_expr2, axis=0, alternative="two-sided", method="asymptotic").pvalue
        except TypeError:
            # 如果批量处理失败，逐个基因处理
            pvals = np.zeros(log_expr1.shape[1])
            for i in range(log_expr1.shape[1]):
                pvals[i] = mannwhitneyu(log_expr1[:, i], log_expr2[:, i], alternative="two-sided", method="asymptotic").pvalue
        
        # 处理无效p值
        pvals = np.asarray(pvals, dtype=np.float64)
        pvals[~np.isfinite(pvals)] = 1.0
        
        # FDR校正
        if use_fdr:
            qvals = self.bh_fdr(pvals)
        else:
            qvals = pvals.copy()
        
        # 构建结果DataFrame
        gene_names = adata_subset.var.index.tolist()
        results = pd.DataFrame({
            'gene': gene_names,
            'mean_CP10K_group1': mean_cp10k1,
            'mean_CP10K_group2': mean_cp10k2,
            'log2FC': log2fc,
            'pct_expr_group1': pct1,
            'pct_expr_group2': pct2,
            'p_val': pvals,
            'p_val_adj': qvals,
            'n_cells_group1': len(group1_cells),
            'n_cells_group2': len(group2_cells)
        })
        
        # 添加显著性标记和分组
        results['significant'] = (results['p_val_adj'] < pval_threshold) & \
                                (abs(results['log2FC']) > logfc_threshold)
        
        # 添加变化方向标记（up/down/stable）
        results['change'] = 'stable'
        results.loc[(results['p_val_adj'] < pval_threshold) & 
                   (results['log2FC'] > logfc_threshold), 'change'] = 'up'
        results.loc[(results['p_val_adj'] < pval_threshold) & 
                   (results['log2FC'] < -logfc_threshold), 'change'] = 'down'
        
        # 按p值排序
        results = results.sort_values('p_val')
        
        self.diff_gene_df = results
        return results
    
    def get_results(self):
        """获取差异分析结果"""
        return self.diff_gene_df
    
    def export_csv(self, save_path):
        """导出结果为CSV"""
        if self.diff_gene_df is None or len(self.diff_gene_df) == 0:
            raise ValueError("没有可导出的结果")
        
        if not save_path.endswith('.csv'):
            save_path += '.csv'
        
        self.diff_gene_df.to_csv(save_path, index=False, encoding='utf-8-sig')
    
    def export_png(self, save_path):
        """导出火山图为PNG"""
        if self.diff_gene_df is None or len(self.diff_gene_df) == 0:
            raise ValueError("请先执行差异分析")
        
        if not save_path.endswith('.png'):
            save_path += '.png'
        
        fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
        
        df = self.diff_gene_df.copy()
        
        # 添加显著性标签
        df['-log10(p值)'] = -np.log10(df['p_val'] + 1e-300)
        
        # 上调、下调、不显著
        df['颜色'] = 'grey'
        df.loc[(df['log2FC'] > 1) & (df['p_val_adj'] < 0.05), '颜色'] = 'red'
        df.loc[(df['log2FC'] < -1) & (df['p_val_adj'] < 0.05), '颜色'] = 'blue'
        
        # 绘图
        ax.scatter(df['log2FC'], df['-log10(p值)'], c=df['颜色'], alpha=0.6, s=20)
        
        ax.set_xlabel('log2 Fold Change', fontsize=12)
        ax.set_ylabel('-log10(p-value)', fontsize=12)
        ax.set_title(f'Differential Expression: {self.group_col}\n{self.selected_groups}', fontsize=14)
        
        # 添加参考线
        ax.axhline(y=-np.log10(0.05), color='gray', linestyle='--', alpha=0.5)
        ax.axvline(x=1, color='gray', linestyle='--', alpha=0.5)
        ax.axvline(x=-1, color='gray', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        if self.dataset_output_dir:
            os.makedirs(self.dataset_output_dir, exist_ok=True)
        
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        
        self.current_fig = fig
