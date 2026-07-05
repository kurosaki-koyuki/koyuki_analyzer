# -*- coding: utf-8 -*-
"""
bulk表达量分析算法脚本 - bulk表达量分析页面的核心生信分析方法
包含数据加载、数据筛选、绘图、显著性检验、导出等功能
"""

from script.utils_layer.import_config import *

class BulkExprAnalysis:
    """bulk表达量分析类 - 包含bulk表达量分析页面的核心生信分析方法"""

    color_schemes = [
        '#17a2b8', '#e0a800', '#3182bd', '#de2d26', '#4d4d4d',
        '#e08214', '#1b9e77', '#d95f02', '#4a1486', '#016c59',
        '#2b8cbe', '#f03b20', '#2ca25f', '#99d8c9', '#756bb1',
        '#c6dbef', '#fc9272', '#9ecae1', '#fb6a4a', '#6baed6'
    ]

    def __init__(self):
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.current_gene = None
        self.saved_figs = {}
        self.saved_data = {}
        self.all_clinical_columns = []

        self.show_insig = True
        self.ns_replace = False
        self.star_replace = False

    def set_adata(self, adata):
        """设置当前adata对象"""
        self.adata = adata
        if adata is not None:
            self.all_clinical_columns = self.get_obs_columns()
        else:
            self.all_clinical_columns = []

    def set_dataset_name(self, name):
        """设置数据集名称"""
        self.dataset_name = name

    def set_dataset_output_dir(self, output_dir):
        """设置数据集输出目录"""
        self.dataset_output_dir = output_dir

    def get_dataset_name(self):
        """获取数据集名称"""
        return self.dataset_name

    def get_adata_shape(self):
        """获取数据维度 (n_cells, n_genes)"""
        if self.adata is None:
            return 0, 0
        return self.adata.shape

    def get_obs_columns(self):
        """获取obs列名列表（排除生存信息列）"""
        if self.adata is None:
            return []
        survival_cols = ['time', 'time (month)', 'state']
        valid_cols = []
        for col in self.adata.obs.columns:
            if col.strip() in survival_cols:
                continue
            valid_cols.append(col)
        return valid_cols

    def get_obs_unique_values(self, col_name):
        """获取某obs列的唯一值列表"""
        if self.adata is None or col_name not in self.adata.obs.columns:
            return []
        unique_vals = self.adata.obs[col_name].unique()
        return sorted([str(v) for v in unique_vals if pd.notna(v)])

    def get_gene_expression(self, gene_name):
        """获取基因表达量"""
        if self.adata is None:
            raise ValueError("数据未加载")

        if gene_name not in self.adata.var_names:
            raise ValueError(f"基因 {gene_name} 不存在于数据集中")

        idx = np.where(self.adata.var_names == gene_name)[0][0]
        X = self.adata.X[:, idx]
        if issparse(X):
            return X.toarray().ravel()
        else:
            return X.ravel()

    def get_gene_exists(self, gene_name):
        """检查基因是否存在于数据集中"""
        if self.adata is None:
            return False
        return gene_name in self.adata.var_names

    def get_multiple_genes_expression(self, gene_names):
        """获取多个基因的表达量"""
        if self.adata is None:
            raise ValueError("数据未加载")

        valid_genes = []
        invalid_genes = []
        for gene in gene_names:
            if gene in self.adata.var_names:
                valid_genes.append(gene)
            else:
                invalid_genes.append(gene)

        return valid_genes, invalid_genes

    def filter_adata(self, filter1_col=None, filter1_groups=None,
                      filter2_col=None, filter2_groups=None):
        """根据筛选条件过滤adata"""
        if self.adata is None:
            return None

        filtered = self.adata.copy()

        if filter1_col and filter1_groups and filter1_col in filtered.obs.columns:
            filtered = filtered[filtered.obs[filter1_col].isin(filter1_groups)]

        if filter2_col and filter2_groups and filter2_col in filtered.obs.columns:
            filtered = filtered[filtered.obs[filter2_col].isin(filter2_groups)]

        return filtered

    def set_significance_options(self, show_insig=True, ns_replace=False, star_replace=False):
        """设置显著性显示选项"""
        self.show_insig = show_insig
        self.ns_replace = ns_replace
        self.star_replace = star_replace

    def calculate_pvalue(self, group1, group2):
        """计算两组之间的t检验p值"""
        g1 = group1[~np.isnan(group1)]
        g2 = group2[~np.isnan(group2)]
        if len(g1) < 2 or len(g2) < 2:
            return None
        try:
            stat, pvalue = stats.ttest_ind(g1, g2)
            return pvalue
        except:
            return None

    def get_significance_label(self, pvalue):
        """根据p值获取显著性标记"""
        show_insig = self.show_insig
        ns_replace = self.ns_replace
        star_replace = self.star_replace

        if pvalue is None:
            return ""
        elif star_replace:
            if pvalue < 0.0001:
                return "****"
            elif pvalue < 0.001:
                return "***"
            elif pvalue < 0.01:
                return "**"
            elif pvalue < 0.05:
                return "*"
            else:
                if ns_replace:
                    return "n.s."
                elif show_insig:
                    return f"p={pvalue:.3f}"
                else:
                    return ""
        else:
            if pvalue < 0.05:
                return f"p={pvalue:.3f}"
            else:
                if ns_replace:
                    return "n.s."
                elif show_insig:
                    return f"p={pvalue:.3f}"
                else:
                    return ""

    def prepare_data_for_col(self, gene_name, col_name, selected_groups=None):
        """为指定分类列准备数据"""
        if self.adata is None:
            return None, None, None

        gene_expr = self.adata[:, gene_name].X.flatten()
        if issparse(gene_expr):
            gene_expr = gene_expr.toarray().ravel()
        clinical_data = self.adata.obs[col_name].values

        df = pd.DataFrame({
            'Expression': gene_expr,
            'Group': clinical_data
        })

        df = df[df['Group'] != 'NA']
        df = df[~df['Group'].isna()]

        df['Group'] = df['Group'].astype(str)

        if col_name == "全部":
            df = df[df['Group'].notna()]
            df = df[df['Group'] != 'nan']
            df = df[df['Group'] != 'NaN']
            df = df[df['Group'] != 'None']
        else:
            df['Group'] = df['Group'].astype(str)

        if selected_groups is not None and len(selected_groups) > 0:
            df = df[df['Group'].isin(selected_groups)]

        if len(df) == 0:
            return None, None, None

        if col_name == 'age':
            try:
                df['Group'] = df['Group'].astype(float)
                median_age = df['Group'].median()
                df['Group'] = np.where(df['Group'] > median_age, f">{median_age:.1f} years", f"≤{median_age:.1f} years")
            except:
                pass

        groups = df['Group'].unique()
        n_groups = len(groups)

        if n_groups < 2:
            return None, None, None

        group_colors = [self.color_schemes[i % len(self.color_schemes)] for i in range(n_groups)]

        return df, groups, group_colors

    def add_significance_marks(self, ax, df, groups, group_colors, pairwise_groups=None, fontsize=11):
        """添加显著性标记"""
        if pairwise_groups is None or len(pairwise_groups) == 0:
            return

        max_expr = df['Expression'].max()
        y_pos = max_expr + max_expr * 0.08

        group_indices = {g: i for i, g in enumerate(groups)}

        comparisons_list = []
        for pair_str in pairwise_groups:
            if ' vs ' in pair_str:
                parts = pair_str.split(' vs ')
                group1 = parts[0].strip()
                group2 = parts[1].strip()
                if group1 in group_indices and group2 in group_indices:
                    comparisons_list.append((group_indices[group1], group_indices[group2]))
            else:
                if pair_str in group_indices:
                    pass

        if not comparisons_list and len(pairwise_groups) >= 2:
            old_selected_indices = [group_indices[g] for g in pairwise_groups if g in group_indices]
            comparisons_list = list(itertools.combinations(old_selected_indices, 2))

        for idx, (i, j) in enumerate(comparisons_list):
            group1_data = df[df['Group'] == groups[i]]['Expression'].values
            group2_data = df[df['Group'] == groups[j]]['Expression'].values

            pvalue = self.calculate_pvalue(group1_data, group2_data)
            sig_label = self.get_significance_label(pvalue)

            y_start = y_pos + idx * max_expr * 0.12
            ax.plot([i, i, j, j], [y_start, y_start + max_expr*0.02, y_start + max_expr*0.02, y_start],
                    color='black', linewidth=1.8)

            if sig_label:
                ax.text((i+j)/2, y_start + max_expr*0.02, sig_label,
                        ha='center', va='bottom', fontsize=fontsize)

        if comparisons_list:
            ax.set_ylim(df['Expression'].min() - max_expr*0.05,
                        y_pos + len(comparisons_list) * max_expr * 0.12)

    def add_global_pvalue(self, ax, df, groups, fontsize=12):
        """添加全局ANOVA p值"""
        data_list = [df[df['Group'] == g]['Expression'].values for g in groups]
        try:
            stat, pvalue = stats.f_oneway(*data_list)
            sig_label = self.get_significance_label(pvalue)
            if sig_label:
                ax.text(0.95, 0.95, f"p={pvalue:.4f}",
                        ha='right', va='top', transform=ax.transAxes,
                        fontsize=fontsize, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        except:
            pass

    def plot_single_violin_box(self, ax, df, groups, group_colors, col_name, title_name,
                               title_size, ylabel_name, axis_size, pairwise_size, global_size,
                               show_global, pairwise_groups, gene_name=None):
        """绘制单个分类列的箱线小提琴图"""
        n_groups = len(groups)
        df['Group'] = pd.Categorical(df['Group'], categories=groups, ordered=True)

        import seaborn as sns
        sns.violinplot(x='Group', y='Expression', data=df, ax=ax,
                       palette=group_colors, alpha=0.5,
                       linewidth=2.4, inner=None)

        for i, collection in enumerate(ax.collections):
            if i < n_groups:
                collection.set_edgecolor(group_colors[i])
                collection.set_linewidth(2.4)

        data_list = [df[df['Group'] == g]['Expression'].values for g in groups]

        bp = ax.boxplot(data_list,
                        labels=groups,
                        patch_artist=True,
                        widths=0.15,
                        showfliers=False,
                        positions=range(n_groups))

        for i in range(n_groups):
            color = group_colors[i]

            # 使用半透明填充而不是none，确保PDF中边框可见
            bp['boxes'][i].set_facecolor(color + '80')  # 80 = 50% alpha
            bp['boxes'][i].set_edgecolor(color)
            bp['boxes'][i].set_linewidth(2.4)

            bp['whiskers'][2*i].set_color(color)
            bp['whiskers'][2*i].set_linewidth(2.4)
            bp['whiskers'][2*i+1].set_color(color)
            bp['whiskers'][2*i+1].set_linewidth(2.4)

            bp['caps'][2*i].set_color(color)
            bp['caps'][2*i].set_linewidth(2.4)
            bp['caps'][2*i+1].set_color(color)
            bp['caps'][2*i+1].set_linewidth(2.4)

            bp['medians'][i].set_color(color)
            bp['medians'][i].set_linewidth(2.4)

        for i, group in enumerate(groups):
            group_data = df[df['Group'] == group]['Expression'].values

            q1 = np.percentile(group_data, 25)
            q3 = np.percentile(group_data, 75)

            above_q3 = group_data[group_data > q3]
            below_q1 = group_data[group_data < q1]

            if len(above_q3) > 0:
                x = np.random.normal(i, 0.06, size=len(above_q3))
                ax.scatter(x, above_q3, alpha=0.6, s=25, color=group_colors[i],
                           edgecolors='white', linewidths=0.5)

            if len(below_q1) > 0:
                x = np.random.normal(i, 0.06, size=len(below_q1))
                ax.scatter(x, below_q1, alpha=0.6, s=25, color=group_colors[i],
                           edgecolors='white', linewidths=0.5)

        self.add_significance_marks(ax, df, groups, group_colors, pairwise_groups, pairwise_size)

        if show_global:
            self.add_global_pvalue(ax, df, groups, global_size)

        plot_title = title_name if title_name else f"{gene_name}"
        ax.set_title(plot_title, fontsize=title_size, fontweight='bold', pad=20)
        ax.set_ylabel(ylabel_name, fontsize=axis_size)
        ax.set_xlabel("")

        if len(groups) > 3:
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=axis_size)
        else:
            ax.tick_params(axis='x', labelsize=axis_size)

        ax.tick_params(axis='y', labelsize=axis_size)
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(1.8)

    def plot_single_box(self, ax, df, groups, group_colors, col_name, title_name,
                        title_size, ylabel_name, axis_size, pairwise_size, global_size,
                        show_global, pairwise_groups, gene_name=None):
        """绘制单个分类列的箱线图"""
        n_groups = len(groups)
        data_list = [df[df['Group'] == g]['Expression'].values for g in groups]

        bp = ax.boxplot(data_list,
                        labels=groups,
                        patch_artist=True,
                        widths=0.5,
                        showfliers=False,
                        positions=range(n_groups))

        for i in range(n_groups):
            color = group_colors[i]

            bp['boxes'][i].set_facecolor(color)
            bp['boxes'][i].set_alpha(0.5)
            bp['boxes'][i].set_edgecolor(color)
            bp['boxes'][i].set_linewidth(2.4)

            bp['whiskers'][2*i].set_color(color)
            bp['whiskers'][2*i].set_linewidth(2.4)
            bp['whiskers'][2*i+1].set_color(color)
            bp['whiskers'][2*i+1].set_linewidth(2.4)

            bp['caps'][2*i].set_color(color)
            bp['caps'][2*i].set_linewidth(2.4)
            bp['caps'][2*i+1].set_color(color)
            bp['caps'][2*i+1].set_linewidth(2.4)

            bp['medians'][i].set_color(color)
            bp['medians'][i].set_linewidth(2.4)

        for i, group in enumerate(groups):
            group_data = df[df['Group'] == group]['Expression'].values
            x = np.random.normal(i, 0.08, size=len(group_data))
            ax.scatter(x, group_data, alpha=0.6, s=25, color=group_colors[i],
                       edgecolors='white', linewidths=0.5)

        self.add_significance_marks(ax, df, groups, group_colors, pairwise_groups, pairwise_size)

        if show_global:
            self.add_global_pvalue(ax, df, groups, global_size)

        plot_title = title_name if title_name else f"{gene_name}"
        ax.set_title(plot_title, fontsize=title_size, fontweight='bold', pad=20)
        ax.set_ylabel(ylabel_name, fontsize=axis_size)
        ax.set_xlabel("")

        if len(groups) > 3:
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=axis_size)
        else:
            ax.tick_params(axis='x', labelsize=axis_size)

        ax.tick_params(axis='y', labelsize=axis_size)
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(1.8)

    def plot_single_violin(self, ax, df, groups, group_colors, col_name, title_name,
                           title_size, ylabel_name, axis_size, pairwise_size, global_size,
                           show_global, pairwise_groups, gene_name=None):
        """绘制单个分类列的小提琴图"""
        n_groups = len(groups)
        df['Group'] = pd.Categorical(df['Group'], categories=groups, ordered=True)

        import seaborn as sns
        sns.violinplot(x='Group', y='Expression', data=df, ax=ax,
                       palette=group_colors, alpha=0.5,
                       linewidth=2.4, inner=None)

        for i, collection in enumerate(ax.collections):
            if i < n_groups:
                collection.set_edgecolor(group_colors[i])
                collection.set_linewidth(2.4)

        for line in ax.lines:
            for i in range(n_groups):
                xdata = line.get_xdata()
                if np.allclose(xdata, [i, i]) or np.any(np.abs(xdata - i) < 0.5):
                    line.set_color(group_colors[i])
                    line.set_linewidth(2.4)

        for i, group in enumerate(groups):
            group_data = df[df['Group'] == group]['Expression'].values

            median = np.median(group_data)
            q1 = np.percentile(group_data, 25)
            q3 = np.percentile(group_data, 75)
            iqr = q3 - q1

            lower_whisker_bound = q1 - 1.5 * iqr
            upper_whisker_bound = q3 + 1.5 * iqr

            lower_whisker = np.min(group_data[group_data >= lower_whisker_bound])
            upper_whisker = np.max(group_data[group_data <= upper_whisker_bound])

            x = np.random.normal(i, 0.06, size=len(group_data))
            ax.scatter(x, group_data, alpha=0.5, s=20, color=group_colors[i],
                       edgecolors='white', linewidths=0.5)

            ax.plot([i - 0.12, i + 0.12], [median, median], color=group_colors[i],
                    linewidth=2.4, solid_capstyle='round')

            ax.plot([i - 0.10, i + 0.10], [q1, q1], color=group_colors[i],
                    linewidth=2.0, solid_capstyle='round')

            ax.plot([i - 0.10, i + 0.10], [q3, q3], color=group_colors[i],
                    linewidth=2.0, solid_capstyle='round')

            ax.plot([i, i], [q1, q3], color=group_colors[i], linewidth=2.0)

            ax.plot([i - 0.08, i + 0.08], [lower_whisker, lower_whisker],
                    color=group_colors[i], linewidth=1.8, solid_capstyle='round')

            ax.plot([i - 0.08, i + 0.08], [upper_whisker, upper_whisker],
                    color=group_colors[i], linewidth=1.8, solid_capstyle='round')

            ax.plot([i, i], [q1, lower_whisker], color=group_colors[i],
                    linewidth=1.8, linestyle='-')

            ax.plot([i, i], [q3, upper_whisker], color=group_colors[i],
                    linewidth=1.8, linestyle='-')

        self.add_significance_marks(ax, df, groups, group_colors, pairwise_groups, pairwise_size)

        if show_global:
            self.add_global_pvalue(ax, df, groups, global_size)

        plot_title = title_name if title_name else f"{gene_name}"
        ax.set_title(plot_title, fontsize=title_size, fontweight='bold', pad=20)
        ax.set_ylabel(ylabel_name, fontsize=axis_size)
        ax.set_xlabel("")

        if len(groups) > 3:
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=axis_size)
        else:
            ax.tick_params(axis='x', labelsize=axis_size)

        ax.tick_params(axis='y', labelsize=axis_size)
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(1.8)

    def generate_violin_box_plot(self, gene_name, clinical_col, selected_groups=None,
                                  title_name=None, title_size=16, ylabel_name=None,
                                  axis_size=12, pairwise_size=11, global_size=12,
                                  show_global=False, pairwise_groups=None,
                                  filter1_col=None, filter1_groups=None,
                                  filter2_col=None, filter2_groups=None):
        """生成箱线小提琴图"""
        import matplotlib.pyplot as plt

        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

        filtered = self.filter_adata(filter1_col, filter1_groups, filter2_col, filter2_groups)
        if filtered is not None:
            original_adata = self.adata
            self.adata = filtered

        df, groups, group_colors = self.prepare_data_for_col(gene_name, clinical_col, selected_groups)

        if filtered is not None:
            self.adata = original_adata

        if df is None or groups is None:
            raise ValueError("没有可绘图的数据")

        if ylabel_name is None:
            ylabel_name = gene_name

        fig, ax = plt.subplots(figsize=(10, 6))
        self.plot_single_violin_box(ax, df, groups, group_colors, clinical_col, title_name,
                                     title_size, ylabel_name, axis_size, pairwise_size, global_size,
                                     show_global, pairwise_groups, gene_name)

        plt.tight_layout()

        # 保存到内存
        fig_key = f"{gene_name}_{clinical_col}_violin_box"
        self.saved_figs[fig_key] = fig
        self.saved_data[fig_key] = df

        return fig

    def generate_box_plot(self, gene_name, clinical_col, selected_groups=None,
                          title_name=None, title_size=16, ylabel_name=None,
                          axis_size=12, pairwise_size=11, global_size=12,
                          show_global=False, pairwise_groups=None,
                          filter1_col=None, filter1_groups=None,
                          filter2_col=None, filter2_groups=None):
        """生成箱线图"""
        import matplotlib.pyplot as plt

        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

        filtered = self.filter_adata(filter1_col, filter1_groups, filter2_col, filter2_groups)
        if filtered is not None:
            original_adata = self.adata
            self.adata = filtered

        df, groups, group_colors = self.prepare_data_for_col(gene_name, clinical_col, selected_groups)

        if filtered is not None:
            self.adata = original_adata

        if df is None or groups is None:
            raise ValueError("没有可绘图的数据")

        if ylabel_name is None:
            ylabel_name = gene_name

        fig, ax = plt.subplots(figsize=(10, 6))
        self.plot_single_box(ax, df, groups, group_colors, clinical_col, title_name,
                             title_size, ylabel_name, axis_size, pairwise_size, global_size,
                             show_global, pairwise_groups, gene_name)

        plt.tight_layout()

        fig_key = f"{gene_name}_{clinical_col}_box"
        self.saved_figs[fig_key] = fig
        self.saved_data[fig_key] = df

        return fig

    def generate_violin_plot(self, gene_name, clinical_col, selected_groups=None,
                              title_name=None, title_size=16, ylabel_name=None,
                              axis_size=12, pairwise_size=11, global_size=12,
                              show_global=False, pairwise_groups=None,
                              filter1_col=None, filter1_groups=None,
                              filter2_col=None, filter2_groups=None):
        """生成小提琴图"""
        import matplotlib.pyplot as plt

        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

        filtered = self.filter_adata(filter1_col, filter1_groups, filter2_col, filter2_groups)
        if filtered is not None:
            original_adata = self.adata
            self.adata = filtered

        df, groups, group_colors = self.prepare_data_for_col(gene_name, clinical_col, selected_groups)

        if filtered is not None:
            self.adata = original_adata

        if df is None or groups is None:
            raise ValueError("没有可绘图的数据")

        if ylabel_name is None:
            ylabel_name = gene_name

        fig, ax = plt.subplots(figsize=(10, 6))
        self.plot_single_violin(ax, df, groups, group_colors, clinical_col, title_name,
                                 title_size, ylabel_name, axis_size, pairwise_size, global_size,
                                 show_global, pairwise_groups, gene_name)

        plt.tight_layout()

        fig_key = f"{gene_name}_{clinical_col}_violin"
        self.saved_figs[fig_key] = fig
        self.saved_data[fig_key] = df

        return fig

    def export_plot_data_csv(self, gene_name, clinical_col, selected_groups=None,
                              filter1_col=None, filter1_groups=None,
                              filter2_col=None, filter2_groups=None,
                              save_path=None):
        """导出绘图数据到CSV"""
        if self.adata is None:
            raise ValueError("数据未加载")

        filtered = self.filter_adata(filter1_col, filter1_groups, filter2_col, filter2_groups)
        if filtered is None or filtered.shape[0] == 0:
            raise ValueError("筛选后没有剩余样本")

        gene_expr = filtered[:, gene_name].X.flatten()
        if issparse(gene_expr):
            gene_expr = gene_expr.toarray().ravel()

        df = pd.DataFrame({
            'Sample': filtered.obs_names,
            clinical_col: filtered.obs[clinical_col].values,
            gene_name: gene_expr
        })

        if selected_groups:
            df = df[df[clinical_col].isin(selected_groups)]

        if save_path:
            df.to_csv(save_path, index=False)
            return save_path
        elif self.dataset_output_dir:
            gene_dir = os.path.join(self.dataset_output_dir, gene_name)
            os.makedirs(gene_dir, exist_ok=True)
            csv_path = os.path.join(gene_dir, f"{gene_name}_{clinical_col}_data.csv")
            df.to_csv(csv_path, index=False)
            return csv_path

        return None

    def generate_combined_plots(self, gene_name, clinical_cols, selected_groups=None,
                                title_name=None, title_size=14, ylabel_name=None,
                                axis_size=10, pairwise_size=10, global_size=11,
                                show_global=False, pairwise_groups=None,
                                filter1_col=None, filter1_groups=None,
                                filter2_col=None, filter2_groups=None):
        """生成组合图表（支持多个分类列同时出图）

        用于当用户选择"全部"分类列时，一次性绘制多个分类列的图表

        Args:
            gene_name: 基因名称
            clinical_cols: 分类列列表（当选择"全部"时）
            selected_groups: 选中的组别列表
            title_name: 图表标题
            title_size: 标题字体大小
            ylabel_name: Y轴标签
            axis_size: 坐标轴字体大小
            pairwise_size: 两两比较字体大小
            global_size: 全局p值字体大小
            show_global: 是否显示全局p值
            pairwise_groups: 两两比较组列表
            filter1_col: 筛选1列名
            filter1_groups: 筛选1组列表
            filter2_col: 筛选2列名
            filter2_groups: 筛选2组列表

        Returns:
            dict: 包含三种组合图表fig对象的字典
        """
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

        if ylabel_name is None:
            ylabel_name = gene_name

        print(f"[DEBUG] generate_combined_plots: gene_name={gene_name}, clinical_cols={clinical_cols}")

        # 应用筛选条件
        filtered = self.filter_adata(filter1_col, filter1_groups, filter2_col, filter2_groups)
        if filtered is not None:
            original_adata = self.adata
            self.adata = filtered

        # 如果selected_groups为空，传递None以避免过滤
        effective_groups = selected_groups if (selected_groups and len(selected_groups) > 0) else None

        # 先检查哪些分类列有有效数据
        valid_cols = []
        for col_name in clinical_cols:
            df, groups, _ = self.prepare_data_for_col(gene_name, col_name, effective_groups)
            if df is not None and len(groups) >= 2:
                valid_cols.append(col_name)

        print(f"[DEBUG] Valid columns: {valid_cols}")

        if not valid_cols:
            print("[DEBUG] No valid columns found, returning empty dict")
            if filtered is not None:
                self.adata = original_adata
            return {}

        # 使用有效列计算图表布局
        n_cols = min(3, len(valid_cols))
        n_rows = (len(valid_cols) + n_cols - 1) // n_cols

        # 调整图表尺寸
        fig_width = 6 * n_cols
        fig_height = 5 * n_rows

        print(f"[DEBUG] generate_combined_plots: n_rows={n_rows}, n_cols={n_cols}, fig_size=({fig_width}, {fig_height})")

        # 创建图表
        figs = {}

        # 1. 组合箱线小提琴图
        fig1, axes1 = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height))
        if n_rows == 1 and n_cols == 1:
            axes1 = [axes1]
        elif n_rows == 1:
            axes1 = axes1.flatten()
        elif n_cols == 1:
            axes1 = axes1.flatten()
        else:
            axes1 = axes1.flatten()

        valid_idx = 0
        for col_name in valid_cols:
            if valid_idx >= len(axes1):
                break

            print(f"[DEBUG] Processing column: {col_name}")
            df, groups, group_colors = self.prepare_data_for_col(gene_name, col_name, effective_groups)
            if df is None:
                print(f"[DEBUG] Column {col_name} returned None data")
                valid_idx += 1
                continue
            print(f"[DEBUG] Column {col_name} returned data with groups: {groups}")

            plot_title = title_name if title_name else f"{gene_name}"
            self.plot_single_violin_box(axes1[valid_idx], df, groups, group_colors, col_name,
                                        plot_title, title_size, ylabel_name, axis_size,
                                        pairwise_size, global_size, show_global, pairwise_groups, gene_name)
            valid_idx += 1

        # 隐藏多余的子图
        for idx in range(valid_idx, len(axes1)):
            axes1[idx].set_visible(False)

        plt.tight_layout()
        figs['violin_box'] = fig1

        # 2. 组合箱线图
        fig2, axes2 = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height))
        if n_rows == 1 and n_cols == 1:
            axes2 = [axes2]
        elif n_rows == 1:
            axes2 = axes2.flatten()
        elif n_cols == 1:
            axes2 = axes2.flatten()
        else:
            axes2 = axes2.flatten()

        valid_idx = 0
        for col_name in valid_cols:
            if valid_idx >= len(axes2):
                break

            df, groups, group_colors = self.prepare_data_for_col(gene_name, col_name, effective_groups)
            if df is None:
                valid_idx += 1
                continue

            plot_title = title_name if title_name else f"{gene_name}"
            self.plot_single_box(axes2[valid_idx], df, groups, group_colors, col_name,
                                  plot_title, title_size, ylabel_name, axis_size,
                                  pairwise_size, global_size, show_global, pairwise_groups, gene_name)
            valid_idx += 1

        for idx in range(valid_idx, len(axes2)):
            axes2[idx].set_visible(False)

        plt.tight_layout()
        figs['box'] = fig2

        # 3. 组合小提琴图
        fig3, axes3 = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height))
        if n_rows == 1 and n_cols == 1:
            axes3 = [axes3]
        elif n_rows == 1:
            axes3 = axes3.flatten()
        elif n_cols == 1:
            axes3 = axes3.flatten()
        else:
            axes3 = axes3.flatten()

        valid_idx = 0
        for col_name in valid_cols:
            if valid_idx >= len(axes3):
                break

            df, groups, group_colors = self.prepare_data_for_col(gene_name, col_name, effective_groups)
            if df is None:
                valid_idx += 1
                continue

            plot_title = title_name if title_name else f"{gene_name}"
            self.plot_single_violin(axes3[valid_idx], df, groups, group_colors, col_name,
                                    plot_title, title_size, ylabel_name, axis_size,
                                    pairwise_size, global_size, show_global, pairwise_groups, gene_name)
            valid_idx += 1

        for idx in range(valid_idx, len(axes3)):
            axes3[idx].set_visible(False)

        plt.tight_layout()
        figs['violin'] = fig3

        # 恢复原始adata
        if filtered is not None:
            self.adata = original_adata

        print(f"[DEBUG] generate_combined_plots finished, figs keys: {list(figs.keys())}")

        for plot_type, fig in figs.items():
            fig_key = f"{gene_name}_combined_{plot_type}"
            self.saved_figs[fig_key] = fig

        return figs

    def generate_multi_gene_plots(self, gene_names, clinical_col, plot_type='violin_box',
                                  title_size=14, ylabel_name=None, axis_size=10,
                                  pairwise_size=10, global_size=11, show_global=False,
                                  pairwise_groups=None, filter1_col=None, filter1_groups=None,
                                  filter2_col=None, filter2_groups=None):
        """生成多基因组合图表

        将多个基因的图放在同一张大画布上，根据基因数量动态调整画布大小

        Args:
            gene_names: 基因名称列表
            clinical_col: 分类列
            plot_type: 图表类型 ('violin_box', 'box', 'violin')
            title_size: 标题字体大小
            ylabel_name: Y轴标签
            axis_size: 坐标轴字体大小
            pairwise_size: 两两比较字体大小
            global_size: 全局p值字体大小
            show_global: 是否显示全局p值
            pairwise_groups: 两两比较组列表
            filter1_col: 筛选1列名
            filter1_groups: 筛选1组列表
            filter2_col: 筛选2列名
            filter2_groups: 筛选2组列表

        Returns:
            dict: 包含图表fig对象的字典
        """
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

        n_genes = len(gene_names)

        if n_genes == 0:
            return {'fig': None, 'gene_names': gene_names}

        # 计算图表布局 - 根据基因数动态调整
        n_cols = min(3, n_genes)
        n_rows = (n_genes + n_cols - 1) // n_cols

        # 调整图表尺寸 - 根据基因数和行数列数动态调整
        fig_width = 8 * n_cols
        fig_height = 6 * n_rows

        # 应用筛选条件
        filtered = self.filter_adata(filter1_col, filter1_groups, filter2_col, filter2_groups)
        if filtered is not None:
            original_adata = self.adata
            self.adata = filtered

        # 创建图表
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height))

        # 处理axes维度
        if n_rows == 1 and n_cols == 1:
            axes = np.array([axes])
        elif n_rows == 1:
            axes = axes.reshape(1, -1)
        elif n_cols == 1:
            axes = axes.reshape(-1, 1)

        # 绘制每个基因的图
        for idx, gene_name in enumerate(gene_names):
            row = idx // n_cols
            col = idx % n_cols

            if row >= n_rows or col >= n_cols:
                break

            ax = axes[row, col]

            df, groups, group_colors = self.prepare_data_for_col(gene_name, clinical_col, None)
            if df is None:
                ax.set_visible(False)
                continue

            # 默认标题为基因名
            plot_title = gene_name

            # 选择绘图函数
            if plot_type == 'violin_box':
                self.plot_single_violin_box(ax, df, groups, group_colors, clinical_col,
                                            plot_title, title_size, gene_name, axis_size,
                                            pairwise_size, global_size, show_global, pairwise_groups, gene_name)
            elif plot_type == 'box':
                self.plot_single_box(ax, df, groups, group_colors, clinical_col,
                                    plot_title, title_size, gene_name, axis_size,
                                    pairwise_size, global_size, show_global, pairwise_groups, gene_name)
            elif plot_type == 'violin':
                self.plot_single_violin(ax, df, groups, group_colors, clinical_col,
                                        plot_title, title_size, gene_name, axis_size,
                                        pairwise_size, global_size, show_global, pairwise_groups, gene_name)

        # 隐藏多余的子图
        for idx in range(n_genes, n_rows * n_cols):
            row = idx // n_cols
            col = idx % n_cols
            if row < n_rows and col < n_cols:
                axes[row, col].set_visible(False)

        plt.tight_layout()

        # 恢复原始adata
        if filtered is not None:
            self.adata = original_adata

        # 保存到内存
        fig_key = f"multi_gene_{plot_type}"
        self.saved_figs[fig_key] = fig

        return {'fig': fig, 'gene_names': gene_names}

    def generate_default_filename(self, extension='png'):
        """生成默认导出文件名

        命名规则：{数据集文件名}_{基因名}_{类型}_{图类型}.pdf/png/csv

        Args:
            extension: 文件扩展名

        Returns:
            str: 默认文件名
        """
        dataset_name = self.dataset_name if self.dataset_name else "bulk_expr"
        
        # 从saved_figs中提取基因名和类型
        gene_names = []
        plot_types = set()
        
        for key in self.saved_figs.keys():
            parts = key.split('_')
            if len(parts) >= 3:
                gene_name = parts[0]
                if gene_name not in gene_names:
                    gene_names.append(gene_name)
                # 正确解析plot_type（可能是violin_box这样的组合类型）
                if 'combined' in parts:
                    combined_idx = parts.index('combined')
                    plot_type_parts = parts[combined_idx + 1:]
                    plot_type = '_'.join(plot_type_parts)
                else:
                    plot_type_parts = parts[-2:]
                    plot_type = '_'.join(plot_type_parts)
                plot_types.add(plot_type)
        
        # 处理基因名
        gene_part = "+".join(gene_names) if gene_names else "unknown_gene"
        
        # 处理类型
        if len(self.saved_figs) > 1 or 'combined' in str(list(self.saved_figs.keys())):
            type_part = "combined"
        elif gene_names and len(gene_names) > 1:
            type_part = "multi_gene"
        else:
            type_part = "single"
        
        # 处理图类型
        fig_type_part = "_".join(sorted(plot_types)) if plot_types else "plot"
        
        return f"{dataset_name}_{gene_part}_{type_part}_{fig_type_part}.{extension}"

    def export_to_png(self, save_path, fig_key=None, dpi=300):
        """导出图表为PNG

        Args:
            save_path: 保存路径
            fig_key: 图表key，如果为None则导出所有图表
            dpi: 分辨率

        Returns:
            str: 保存的文件路径
        """
        if fig_key and fig_key in self.saved_figs:
            fig = self.saved_figs[fig_key]
            fig.patch.set_facecolor('white')
            fig.savefig(save_path, dpi=dpi, bbox_inches='tight', facecolor='white')
            return save_path
        elif fig_key is None:
            saved_paths = []
            base_name = save_path.replace('.png', '')
            for key, fig in self.saved_figs.items():
                # 解析key格式: {gene_name}_{clinical_col}_{plot_type} 或 {gene_name}_combined_{plot_type}
                # plot_type 可能是 violin_box, box, violin
                parts = key.split('_')
                if len(parts) >= 3:
                    gene_name = parts[0]
                    # 检查是否是combined类型
                    if 'combined' in parts:
                        combined_idx = parts.index('combined')
                        # plot_type是从combined之后的所有部分
                        plot_type_parts = parts[combined_idx + 1:]
                        plot_type = '_'.join(plot_type_parts)
                    else:
                        # 普通类型: {gene_name}_{clinical_col}_{plot_type}
                        # clinical_col可能包含下划线，所以plot_type是最后两部分
                        plot_type_parts = parts[-2:]
                        plot_type = '_'.join(plot_type_parts)
                    file_name = f"{base_name}_{gene_name}_{plot_type}.png"
                else:
                    file_name = f"{base_name}_{key}.png"
                fig.patch.set_facecolor('white')
                fig.savefig(file_name, dpi=dpi, bbox_inches='tight', facecolor='white')
                saved_paths.append(file_name)
            return saved_paths if len(saved_paths) > 1 else saved_paths[0]
        return None

    def export_to_pdf(self, save_path, fig_key=None):
        """导出图表为PDF

        Args:
            save_path: 保存路径
            fig_key: 图表key，如果为None则导出所有图表

        Returns:
            str: 保存的文件路径
        """
        if fig_key and fig_key in self.saved_figs:
            fig = self.saved_figs[fig_key]
            fig.patch.set_facecolor('white')
            fig.savefig(save_path, format='pdf', bbox_inches='tight', 
                        facecolor='white', dpi=300)
            return save_path
        elif fig_key is None:
            saved_paths = []
            base_name = save_path.replace('.pdf', '')
            for key, fig in self.saved_figs.items():
                # 解析key格式: {gene_name}_{clinical_col}_{plot_type} 或 {gene_name}_combined_{plot_type}
                # plot_type 可能是 violin_box, box, violin
                parts = key.split('_')
                if len(parts) >= 3:
                    gene_name = parts[0]
                    # 检查是否是combined类型
                    if 'combined' in parts:
                        combined_idx = parts.index('combined')
                        # plot_type是从combined之后的所有部分
                        plot_type_parts = parts[combined_idx + 1:]
                        plot_type = '_'.join(plot_type_parts)
                    else:
                        # 普通类型: {gene_name}_{clinical_col}_{plot_type}
                        # clinical_col可能包含下划线，所以plot_type是最后两部分
                        plot_type_parts = parts[-2:]
                        plot_type = '_'.join(plot_type_parts)
                    file_name = f"{base_name}_{gene_name}_{plot_type}.pdf"
                else:
                    file_name = f"{base_name}_{key}.pdf"
                fig.patch.set_facecolor('white')
                fig.savefig(file_name, format='pdf', bbox_inches='tight',
                            facecolor='white', dpi=300)
                saved_paths.append(file_name)
            return saved_paths if len(saved_paths) > 1 else saved_paths[0]
        return None