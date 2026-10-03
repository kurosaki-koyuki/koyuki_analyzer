# -*- coding: utf-8 -*-
"""
小提琴图生信分析算法脚本 - 自定义小提琴图页面的核心生信分析方法
包含基因加载、数据筛选、绘图、显著性检验、导出等功能
"""

from script.utils_layer.import_config import *

class ViolinAnalysis:
    """小提琴图分析类 - 包含自定义小提琴图页面的核心生信分析方法"""
    
    def __init__(self):
        self.adata = None
        self.violin_df = None
        self.violin_gene = None
        self.current_violin_box_fig_path = None
        self.current_box_fig_path = None
        self.current_violin_fig_path = None
        self.filtered_df = None
        self.dataset_output_dir = None
        self.current_figs = {}
        self.current_axes = {}
    
    def set_adata(self, adata):
        """设置当前adata对象"""
        self.adata = adata
    
    def set_dataset_output_dir(self, dataset_output_dir):
        """设置数据集输出目录"""
        self.dataset_output_dir = dataset_output_dir
    
    def get_gene_expression(self, gene_name):
        """获取基因表达量"""
        if gene_name in self.adata.var_names:
            idx = np.where(self.adata.var_names == gene_name)[0][0]
        elif gene_name in self.adata.var.index:
            idx = np.where(self.adata.var.index == gene_name)[0][0]
        else:
            raise ValueError(f"基因 {gene_name} 不存在")
        
        X = self.adata.X[:, idx]
        if issparse(X):
            return X.toarray().ravel()
        else:
            return X.ravel()
    
    def load_gene(self, gene_name):
        """加载基因数据"""
        if not gene_name:
            raise ValueError("请输入基因名")

        if self.adata is None:
            raise ValueError("请先在初步分析页面加载数据集")

        expr = self.get_gene_expression(gene_name)
        self.violin_gene = gene_name

        self.violin_df = pd.DataFrame({
            "cell": self.adata.obs_names,
            **self.adata.obs.to_dict("list"),
            gene_name: expr
        })

        groups = [c for c in self.adata.obs.columns if self.violin_df[c].nunique() < 60]

        return groups, len(self.violin_df)

    def get_group_unique_vals(self, group):
        """获取某分组列的唯一值列表（纯数据，不操作控件）"""
        if self.violin_df is None:
            return []
        if group not in self.violin_df.columns:
            return []
        return sorted([str(v) for v in self.violin_df[group].unique()])
    
    def _perform_mannwhitneyu(self, data1, data2):
        """执行Mann-Whitney U检验"""
        try:
            stat, p_value = mannwhitneyu(data1, data2, alternative='two-sided')
            return p_value
        except Exception:
            return 1.0
    
    def _get_significance_mark(self, p_value, pvalue_mode=0, show_insig=True, ns_replace=True, star_replace=True):
        """根据p值获取显著性标记"""
        if pvalue_mode == 0:
            if star_replace:
                if p_value < 0.001:
                    return '***'
                elif p_value < 0.01:
                    return '**'
                elif p_value < 0.05:
                    return '*'
                else:
                    if ns_replace:
                        return 'n.s.'
                    elif show_insig:
                        return f'p={p_value:.3f}'
                    else:
                        return ''
            else:
                if p_value < 0.05:
                    return f'p={p_value:.3f}'
                else:
                    if ns_replace:
                        return 'n.s.'
                    elif show_insig:
                        return f'p={p_value:.3f}'
                    else:
                        return ''
        elif pvalue_mode == 1:
            if p_value < 0.001:
                return '***'
            elif p_value < 0.01:
                return '**'
            elif p_value < 0.05:
                return '*'
            else:
                if ns_replace:
                    return 'n.s.'
                elif show_insig:
                    return f'p={p_value:.3f}'
                else:
                    return ''
        elif pvalue_mode == 2:
            if p_value < 0.05:
                return f'p={p_value:.3f}'
            else:
                if ns_replace:
                    return 'n.s.'
                elif show_insig:
                    return f'p={p_value:.3f}'
                else:
                    return ''
        else:
            return f'p={p_value:.3f}'
    
    def _perform_kruskal(self, group_data_list):
        """执行Kruskal-Wallis检验"""
        try:
            stat, p_value = kruskal(*group_data_list)
            return p_value
        except Exception:
            return 1.0
    
    def add_significance_marks(self, ax, df, groups, group_colors, pairwise_groups, pairwise_size, 
                               pvalue_mode=0, show_insig=True, ns_replace=True, star_replace=True):
        """添加组间比较显著性标记"""
        if not pairwise_groups or len(groups) < 2:
            return

        max_expr = df[self.violin_gene].max()
        y_pos = max_expr + max_expr * 0.08

        group_indices = {g: i + 1 for i, g in enumerate(groups)}

        for idx, pair in enumerate(pairwise_groups):
            group1_data = df[df['Group'] == pair[0]][self.violin_gene].values
            group2_data = df[df['Group'] == pair[1]][self.violin_gene].values

            if len(group1_data) == 0 or len(group2_data) == 0:
                continue

            p_value = self._perform_mannwhitneyu(group1_data, group2_data)

            mark = self._get_significance_mark(p_value, 0, show_insig, ns_replace, star_replace)
            if not mark:
                continue

            i = group_indices[pair[0]]
            j = group_indices[pair[1]]

            y_start = y_pos + idx * max_expr * 0.12
            ax.plot([i, i, j, j], [y_start, y_start + max_expr * 0.02, y_start + max_expr * 0.02, y_start],
                    color='black', linewidth=1.8)
            ax.text((i + j) / 2, y_start + max_expr * 0.02, mark,
                    ha='center', va='bottom', fontsize=pairwise_size, fontweight='bold')

        if pairwise_groups:
            ax.set_ylim(bottom=0, top=y_pos + len(pairwise_groups) * max_expr * 0.15)
    
    def plot_violin_box(self, df, groups, title_name=None, title_size=16, 
                        ylabel_name=None, axis_size=12, pairwise_groups=None, 
                        pairwise_size=11, show_insig=True, ns_replace=True, star_replace=True,
                        overall_pvalue=False):
        """绘制箱线小提琴图"""
        fig, ax = plt.subplots(figsize=(9, 5), dpi=100)

        order = sorted([str(v) for v in df['Group'].unique()])

        palette = sns.color_palette("Set2", len(order))
        group_colors = {group: palette[i] for i, group in enumerate(order)}

        violin_parts = ax.violinplot([df[df['Group'] == group][self.violin_gene].values 
                                       for group in order],
                                      showmeans=False, showmedians=False, showextrema=False)

        for i, collection in enumerate(violin_parts['bodies']):
            collection.set_facecolor(group_colors[order[i]])
            collection.set_edgecolor(group_colors[order[i]])
            collection.set_linewidth(2.4)
            collection.set_alpha(0.45)

        bp = ax.boxplot([df[df['Group'] == group][self.violin_gene].values 
                         for group in order],
                        widths=0.25, showfliers=False, patch_artist=True)

        for i, group in enumerate(order):
            color = group_colors[group]
            bp['boxes'][i].set_facecolor(color)
            bp['boxes'][i].set_alpha(0.45)
            bp['boxes'][i].set_edgecolor(color)
            bp['boxes'][i].set_linewidth(2.4)
            bp['whiskers'][2*i].set_color(color)
            bp['whiskers'][2*i + 1].set_color(color)
            bp['whiskers'][2*i].set_linewidth(2.0)
            bp['whiskers'][2*i + 1].set_linewidth(2.0)
            bp['caps'][2*i].set_color(color)
            bp['caps'][2*i + 1].set_color(color)
            bp['caps'][2*i].set_linewidth(2.0)
            bp['caps'][2*i + 1].set_linewidth(2.0)
            bp['medians'][i].set_color(color)
            bp['medians'][i].set_linewidth(2.4)

        for i, group in enumerate(order):
            group_data = df[df['Group'] == group][self.violin_gene].values
            x = np.random.normal(i + 1, 0.04, size=len(group_data))
            ax.scatter(x, group_data, alpha=0.4, s=15, color=group_colors[group],
                       edgecolors='white', linewidths=0.3)

        ax.set_xticks(range(1, len(order) + 1))
        ax.set_xticklabels(order)
        ax.set_ylim(bottom=0)

        self.add_significance_marks(ax, df, order, group_colors, pairwise_groups,
                                    pairwise_size, show_insig=show_insig,
                                    ns_replace=ns_replace, star_replace=star_replace)

        if overall_pvalue and len(order) >= 2:
            group_data_list = [df[df['Group'] == group][self.violin_gene].values for group in order]
            p_value = self._perform_kruskal(group_data_list)
            if p_value < 0.001:
                mark = 'Kruskal-Wallis: ***'
            elif p_value < 0.01:
                mark = 'Kruskal-Wallis: **'
            elif p_value < 0.05:
                mark = 'Kruskal-Wallis: *'
            else:
                mark = f'Kruskal-Wallis: p={p_value:.3f}'
            
            max_expr = df[self.violin_gene].max()
            y_pos = max_expr + max_expr * 0.08 + len(pairwise_groups) * max_expr * 0.12 if pairwise_groups else max_expr + max_expr * 0.08
            ax.text((1 + len(order)) / 2, y_pos + max_expr * 0.03, mark,
                    ha='center', va='bottom', fontsize=pairwise_size, fontweight='bold')
            
            ax.set_ylim(bottom=0, top=y_pos + max_expr * 0.1)

        plot_title = title_name if title_name else f"{self.violin_gene}"
        ax.set_title(plot_title, fontsize=title_size, fontweight='bold', pad=20)
        if ylabel_name:
            ax.set_ylabel(ylabel_name, fontsize=axis_size)
        else:
            ax.set_ylabel(self.violin_gene, fontsize=axis_size)

        ax.set_xlabel('Group', fontsize=axis_size)
        ax.tick_params(axis='both', labelsize=axis_size)
        plt.xticks(rotation=30, ha="right")
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        # 设置外框样式
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(1.8)

        plt.tight_layout()

        self.current_figs['violin_box'] = fig
        self.current_axes['violin_box'] = ax

        return fig
    
    def plot_box(self, df, groups, title_name=None, title_size=16, 
                 ylabel_name=None, axis_size=12, pairwise_groups=None, 
                 pairwise_size=11, show_insig=True, ns_replace=True, star_replace=True,
                 overall_pvalue=False):
        """绘制箱线图"""
        fig, ax = plt.subplots(figsize=(9, 5), dpi=100)

        order = sorted([str(v) for v in df['Group'].unique()])

        palette = sns.color_palette("Set2", len(order))
        group_colors = {group: palette[i] for i, group in enumerate(order)}

        bp = ax.boxplot([df[df['Group'] == group][self.violin_gene].values 
                         for group in order],
                        widths=0.5, showfliers=False, patch_artist=True)

        for i, group in enumerate(order):
            color = group_colors[group]
            bp['boxes'][i].set_facecolor(color)
            bp['boxes'][i].set_alpha(0.45)
            bp['boxes'][i].set_edgecolor(color)
            bp['boxes'][i].set_linewidth(2.4)
            bp['whiskers'][2*i].set_color(color)
            bp['whiskers'][2*i + 1].set_color(color)
            bp['whiskers'][2*i].set_linewidth(2.0)
            bp['whiskers'][2*i + 1].set_linewidth(2.0)
            bp['caps'][2*i].set_color(color)
            bp['caps'][2*i + 1].set_color(color)
            bp['caps'][2*i].set_linewidth(2.0)
            bp['caps'][2*i + 1].set_linewidth(2.0)
            bp['medians'][i].set_color(color)
            bp['medians'][i].set_linewidth(2.4)

        for i, group in enumerate(order):
            group_data = df[df['Group'] == group][self.violin_gene].values
            x = np.random.normal(i + 1, 0.06, size=len(group_data))
            ax.scatter(x, group_data, alpha=0.5, s=20, color=group_colors[group],
                       edgecolors='white', linewidths=0.5)

        ax.set_xticks(range(1, len(order) + 1))
        ax.set_xticklabels(order)
        ax.set_ylim(bottom=0)

        self.add_significance_marks(ax, df, order, group_colors, pairwise_groups,
                                    pairwise_size, show_insig=show_insig,
                                    ns_replace=ns_replace, star_replace=star_replace)

        if overall_pvalue and len(order) >= 2:
            group_data_list = [df[df['Group'] == group][self.violin_gene].values for group in order]
            p_value = self._perform_kruskal(group_data_list)
            if p_value < 0.001:
                mark = 'Kruskal-Wallis: ***'
            elif p_value < 0.01:
                mark = 'Kruskal-Wallis: **'
            elif p_value < 0.05:
                mark = 'Kruskal-Wallis: *'
            else:
                mark = f'Kruskal-Wallis: p={p_value:.3f}'
            
            max_expr = df[self.violin_gene].max()
            y_pos = max_expr + max_expr * 0.08 + len(pairwise_groups) * max_expr * 0.12 if pairwise_groups else max_expr + max_expr * 0.08
            ax.text((1 + len(order)) / 2, y_pos + max_expr * 0.03, mark,
                    ha='center', va='bottom', fontsize=pairwise_size, fontweight='bold')
            
            ax.set_ylim(bottom=0, top=y_pos + max_expr * 0.1)

        plot_title = title_name if title_name else f"{self.violin_gene}"
        ax.set_title(plot_title, fontsize=title_size, fontweight='bold', pad=20)
        if ylabel_name:
            ax.set_ylabel(ylabel_name, fontsize=axis_size)
        else:
            ax.set_ylabel(self.violin_gene, fontsize=axis_size)

        ax.set_xlabel('Group', fontsize=axis_size)
        ax.tick_params(axis='both', labelsize=axis_size)
        plt.xticks(rotation=30, ha="right")
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        # 设置外框样式
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(1.8)

        plt.tight_layout()

        self.current_figs['box'] = fig
        self.current_axes['box'] = ax

        return fig
    
    def plot_violin(self, df, groups, title_name=None, title_size=16, 
                    ylabel_name=None, axis_size=12, pairwise_groups=None, 
                    pairwise_size=11, show_insig=True, ns_replace=True, star_replace=True,
                    overall_pvalue=False):
        """绘制小提琴图（带完整箱线骨架+须+散点）"""
        fig, ax = plt.subplots(figsize=(9, 5), dpi=100)

        order = sorted([str(v) for v in df['Group'].unique()])

        palette = sns.color_palette("Set2", len(order))
        group_colors = {group: palette[i] for i, group in enumerate(order)}

        n_groups = len(order)

        sns.violinplot(x='Group', y=self.violin_gene, data=df, palette=palette,
                       ax=ax, order=order, inner=None, linewidth=0.5)

        for line in ax.lines:
            for i in range(n_groups):
                xdata = line.get_xdata()
                if np.allclose(xdata, [i, i]) or np.any(np.abs(xdata - i) < 0.5):
                    line.set_color(group_colors[order[i]])
                    line.set_linewidth(2.4)

        for i, group in enumerate(order):
            group_data = df[df['Group'] == group][self.violin_gene].values

            median = np.median(group_data)
            q1 = np.percentile(group_data, 25)
            q3 = np.percentile(group_data, 75)
            iqr = q3 - q1

            lower_whisker_bound = q1 - 1.5 * iqr
            upper_whisker_bound = q3 + 1.5 * iqr

            lower_whisker = np.min(group_data[group_data >= lower_whisker_bound])
            upper_whisker = np.max(group_data[group_data <= upper_whisker_bound])

            x = np.random.normal(i, 0.06, size=len(group_data))
            ax.scatter(x, group_data, alpha=0.5, s=20, color=group_colors[group],
                       edgecolors='white', linewidths=0.5)

            ax.plot([i - 0.12, i + 0.12], [median, median], color=group_colors[group],
                    linewidth=2.4, solid_capstyle='round')

            ax.plot([i - 0.10, i + 0.10], [q1, q1], color=group_colors[group],
                    linewidth=2.0, solid_capstyle='round')

            ax.plot([i - 0.10, i + 0.10], [q3, q3], color=group_colors[group],
                    linewidth=2.0, solid_capstyle='round')

            ax.plot([i, i], [q1, q3], color=group_colors[group], linewidth=2.0)

            ax.plot([i - 0.08, i + 0.08], [lower_whisker, lower_whisker],
                    color=group_colors[group], linewidth=1.8, solid_capstyle='round')

            ax.plot([i - 0.08, i + 0.08], [upper_whisker, upper_whisker],
                    color=group_colors[group], linewidth=1.8, solid_capstyle='round')

            ax.plot([i, i], [q1, lower_whisker], color=group_colors[group],
                    linewidth=1.8, linestyle='-')

            ax.plot([i, i], [q3, upper_whisker], color=group_colors[group],
                    linewidth=1.8, linestyle='-')

        self.add_significance_marks(ax, df, order, group_colors, pairwise_groups,
                                    pairwise_size, show_insig=show_insig,
                                    ns_replace=ns_replace, star_replace=star_replace)

        if overall_pvalue and len(order) >= 2:
            group_data_list = [df[df['Group'] == group][self.violin_gene].values for group in order]
            p_value = self._perform_kruskal(group_data_list)
            if p_value < 0.001:
                mark = 'Kruskal-Wallis: ***'
            elif p_value < 0.01:
                mark = 'Kruskal-Wallis: **'
            elif p_value < 0.05:
                mark = 'Kruskal-Wallis: *'
            else:
                mark = f'Kruskal-Wallis: p={p_value:.3f}'
            
            max_expr = df[self.violin_gene].max()
            y_pos = max_expr + max_expr * 0.08 + len(pairwise_groups) * max_expr * 0.12 if pairwise_groups else max_expr + max_expr * 0.08
            ax.text((1 + len(order)) / 2, y_pos + max_expr * 0.03, mark,
                    ha='center', va='bottom', fontsize=pairwise_size, fontweight='bold')
            
            ax.set_ylim(bottom=0, top=y_pos + max_expr * 0.1)
        else:
            ax.set_ylim(bottom=0)

        plot_title = title_name if title_name else f"{self.violin_gene}"
        ax.set_title(plot_title, fontsize=title_size, fontweight='bold', pad=20)

        if ylabel_name:
            ax.set_ylabel(ylabel_name, fontsize=axis_size)
        else:
            ax.set_ylabel(self.violin_gene, fontsize=axis_size)

        ax.set_xlabel('Group', fontsize=axis_size)
        ax.tick_params(axis='both', labelsize=axis_size)
        plt.xticks(rotation=30, ha="right")
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        # 设置外框样式
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(1.8)

        plt.tight_layout()

        self.current_figs['violin'] = fig
        self.current_axes['violin'] = ax

        return fig
    
    def draw_violin_plot(self, main_col, main_selected_items, 
                         filter1_col=None, filter1_selected=None,
                         filter2_col=None, filter2_selected=None,
                         title_name=None, title_size=16, ylabel_name=None, 
                         axis_size=12, pairwise_enable=True, pairwise_size=11, 
                         pairwise_selected_pairs=None, pvalue_mode=0, overall_pvalue=False,
                         show_insig=True, ns_replace=True, star_replace=True):
        """绘制小提琴图（支持三种类型：箱线小提琴图、箱线图、小提琴图）"""
        if self.violin_df is None:
            raise ValueError("请先加载基因")
        
        df = self.violin_df.copy()
        
        if main_selected_items:
            df = df[df[main_col].isin(main_selected_items)]
        
        if filter1_col and filter1_selected:
            df = df[df[filter1_col].isin(filter1_selected)]
        
        if filter2_col and filter2_selected:
            df = df[df[filter2_col].isin(filter2_selected)]
        
        if len(df) == 0:
            raise ValueError("无符合条件细胞")
        
        self.filtered_df = df

        df_plot = df.rename(columns={main_col: 'Group'})
        groups = sorted([str(v) for v in df_plot['Group'].unique()])

        if pvalue_mode == 0:
            star_replace = True
            ns_replace = True
            show_insig = True
        elif pvalue_mode == 1:
            star_replace = True
            ns_replace = False
            show_insig = True
        elif pvalue_mode == 2:
            star_replace = False
            ns_replace = True
            show_insig = True
        else:
            star_replace = True
            ns_replace = True
            show_insig = True

        pairwise_groups = []
        if pairwise_enable and len(groups) >= 2:
            all_pairs = list(itertools.combinations(groups, 2))
            if pairwise_selected_pairs:
                for selected_pair_str in pairwise_selected_pairs:
                    parts = selected_pair_str.split(' vs ')
                    if len(parts) == 2:
                        pair_tuple = (parts[0], parts[1])
                        if pair_tuple in all_pairs:
                            pairwise_groups.append(pair_tuple)
            else:
                pairwise_groups = all_pairs

        fig_violin_box = self.plot_violin_box(df_plot, groups, title_name=title_name,
                                               title_size=title_size, ylabel_name=ylabel_name,
                                               axis_size=axis_size, pairwise_groups=pairwise_groups,
                                               pairwise_size=pairwise_size, show_insig=show_insig,
                                               ns_replace=ns_replace, star_replace=star_replace,
                                               overall_pvalue=overall_pvalue)

        fig_box = self.plot_box(df_plot, groups, title_name=title_name,
                                title_size=title_size, ylabel_name=ylabel_name,
                                axis_size=axis_size, pairwise_groups=pairwise_groups,
                                pairwise_size=pairwise_size, show_insig=show_insig,
                                ns_replace=ns_replace, star_replace=star_replace,
                                overall_pvalue=overall_pvalue)

        fig_violin = self.plot_violin(df_plot, groups, title_name=title_name,
                                      title_size=title_size, ylabel_name=ylabel_name,
                                      axis_size=axis_size, pairwise_groups=pairwise_groups,
                                      pairwise_size=pairwise_size, show_insig=show_insig,
                                      ns_replace=ns_replace, star_replace=star_replace,
                                      overall_pvalue=overall_pvalue)

        if self.dataset_output_dir:
            od = os.path.join(self.dataset_output_dir, self.violin_gene)
        else:
            od = os.path.join(os.path.expanduser("~"), "koyuki_violin")
        os.makedirs(od, exist_ok=True)

        self.current_violin_box_fig_path = os.path.join(od, f"{self.violin_gene}_箱线小提琴图.png")
        fig_violin_box.savefig(self.current_violin_box_fig_path, dpi=300, bbox_inches="tight")

        self.current_box_fig_path = os.path.join(od, f"{self.violin_gene}_箱线图.png")
        fig_box.savefig(self.current_box_fig_path, dpi=300, bbox_inches="tight")

        self.current_violin_fig_path = os.path.join(od, f"{self.violin_gene}_小提琴图.png")
        fig_violin.savefig(self.current_violin_fig_path, dpi=300, bbox_inches="tight")

        return len(df), self.current_violin_box_fig_path, self.current_box_fig_path, self.current_violin_fig_path
    
    def export_png(self, save_path, width=None, height=None, fig_type='violin_box'):
        """导出PNG"""
        if fig_type not in self.current_figs:
            raise ValueError("请先绘图")
        
        if not save_path.endswith('.png'):
            save_path += '.png'
        
        fig = self.current_figs[fig_type]
        fig_size = fig.get_size_inches()
        if width and height:
            fig.set_size_inches(width, height)
        
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        
        if width and height:
            fig.set_size_inches(fig_size)
    
    def export_pdf(self, save_path, width=None, height=None, fig_type='violin_box'):
        """导出PDF"""
        if fig_type not in self.current_figs:
            raise ValueError("请先绘图")
        
        if not save_path.endswith('.pdf'):
            save_path += '.pdf'
        
        fig = self.current_figs[fig_type]
        fig_size = fig.get_size_inches()
        if width and height:
            fig.set_size_inches(width, height)
        
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        
        if width and height:
            fig.set_size_inches(fig_size)
    
    def export_svg(self, save_path, width=None, height=None, fig_type='violin_box'):
        """导出SVG"""
        if fig_type not in self.current_figs:
            raise ValueError("请先绘图")
        
        if not save_path.endswith('.svg'):
            save_path += '.svg'
        
        fig = self.current_figs[fig_type]
        fig_size = fig.get_size_inches()
        if width and height:
            fig.set_size_inches(width, height)
        
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        
        if width and height:
            fig.set_size_inches(fig_size)
    
    def export_plot_csv(self, save_path):
        """导出当前绘图所用CSV表格"""
        if self.filtered_df is None:
            raise ValueError("请先绘图")
        
        if not save_path.endswith('.csv'):
            save_path += '.csv'
        
        export_df = self.filtered_df.copy()
        export_df.to_csv(save_path, index=False, encoding="utf-8-sig")
    
    def get_available_groups(self):
        """获取当前数据可用的注释列"""
        if self.violin_df is None:
            return []
        return sorted([str(col) for col in self.violin_df.columns])

__all__ = ['ViolinAnalysis']