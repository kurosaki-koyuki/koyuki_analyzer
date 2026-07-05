# -*- coding: utf-8 -*-
"""
bulk KM曲线分析算法脚本 - bulk KM曲线页面的核心生信分析方法
包含数据加载、数据筛选、KM曲线绘制、p值计算、导出等功能
"""

from script.utils_layer.import_config import *

class BulkKmAnalysis:
    """bulk KM曲线分析类"""

    HIGH_COLORS = [
        '#e41a1c', '#ff7f00', '#f781bf', '#a65628', '#e6194b',
        '#ff0000', '#ff69b4', '#ffb6c1', '#ff6347', '#ff4500',
        '#dc143c', '#c71585', '#ff1493', '#ff7f50', '#ffa500'
    ]

    LOW_COLORS = [
        '#0000ff', '#377eb8', '#4daf4a', '#984ea3', '#56b4e9',
        '#00ced1', '#008080', '#40e0d0', '#87ceeb', '#6495ed',
        '#4682b4', '#5f9ea0', '#708090', '#2f4f4f', '#1e90ff'
    ]

    def __init__(self):
        self.adata = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.current_km_fig_path = None
        self.filtered_df = None

    def set_adata(self, adata):
        """设置当前adata对象"""
        self.adata = adata

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
        """获取数据维度"""
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

    def get_gene_exists(self, gene_name):
        """检查基因是否存在于数据集中"""
        if self.adata is None:
            return False
        return gene_name in self.adata.var_names

    def prepare_km_data(self, gene_name, time_unit='days'):
        """准备KM分析数据"""
        adata = self.adata
        gene_name = gene_name.strip()

        if gene_name not in adata.var_names:
            return None

        gene_expr = adata[:, gene_name].X.flatten()

        if time_unit == 'days':
            time_col = 'time'
        else:
            time_col = 'time (month)'

        if time_col not in adata.obs.columns:
            return None

        time_data = adata.obs[time_col].values
        state_data = adata.obs['state'].values

        df = pd.DataFrame({
            'time': time_data,
            'state': state_data,
            'expression': gene_expr
        }, index=adata.obs.index)

        df['time'] = pd.to_numeric(df['time'], errors='coerce')
        df['state'] = pd.to_numeric(df['state'], errors='coerce')
        df['expression'] = pd.to_numeric(df['expression'], errors='coerce')

        df = df[df['time'].notna() & df['state'].notna() & df['expression'].notna()]
        df = df[df['time'] > 0]

        if len(df) < 10:
            return None

        return df

    def filter_data(self, df, filter1_col=None, filter1_groups=None,
                    filter2_col=None, filter2_groups=None):
        """根据筛选条件过滤数据"""
        if df is None:
            return None

        filtered = df.copy()

        if filter1_col and filter1_groups and filter1_col in self.adata.obs.columns:
            filtered[filter1_col] = self.adata.obs.loc[filtered.index, filter1_col].values
            filtered = filtered[filtered[filter1_col].astype(str).isin(filter1_groups)]

        if filter2_col and filter2_groups and filter2_col in self.adata.obs.columns:
            filtered[filter2_col] = self.adata.obs.loc[filtered.index, filter2_col].values
            filtered = filtered[filtered[filter2_col].astype(str).isin(filter2_groups)]

        if len(filtered) < 10:
            return None

        return filtered

    def split_groups_by_clinical(self, df, clinical_col, selected_groups=None):
        """根据临床分类列分组数据"""
        if df is None:
            return []

        df = df.copy()
        df[clinical_col] = self.adata.obs.loc[df.index, clinical_col].values

        if selected_groups:
            df = df[df[clinical_col].astype(str).isin(selected_groups)]
            unique_groups = selected_groups
        else:
            unique_groups = sorted(df[clinical_col].dropna().unique().astype(str))

        grouped_dfs = []
        for group_name in unique_groups:
            group_df = df[df[clinical_col].astype(str) == group_name].copy()
            if len(group_df) < 5:
                continue

            median_expr = group_df['expression'].median()
            high_idx = group_df['expression'] >= median_expr
            low_idx = group_df['expression'] < median_expr

            high_df = group_df[high_idx].copy()
            low_df = group_df[low_idx].copy()

            if len(high_df) >= 2:
                high_df['group'] = f'{group_name} High ({len(high_df)})'
                grouped_dfs.append(high_df)
            if len(low_df) >= 2:
                low_df['group'] = f'{group_name} Low ({len(low_df)})'
                grouped_dfs.append(low_df)

        if not grouped_dfs:
            return []

        return pd.concat(grouped_dfs, ignore_index=True)

    def split_groups_simple(self, df):
        """简单分组（High vs Low）"""
        if df is None:
            return None, 0, 0

        df = df.copy()
        median_expr = df['expression'].median()
        high_idx = df['expression'] >= median_expr
        low_idx = df['expression'] < median_expr

        n_high = high_idx.sum()
        n_low = low_idx.sum()

        df['group'] = np.where(high_idx, f'High ({n_high})', f'Low ({n_low})')

        return df, n_high, n_low

    def calculate_logrank_pvalue(self, df):
        """计算log-rank检验的p值"""
        from lifelines.statistics import logrank_test

        high_data = df[df['group'].str.startswith('High')]
        low_data = df[df['group'].str.startswith('Low')]

        if len(high_data) < 2 or len(low_data) < 2:
            return None

        try:
            results = logrank_test(
                high_data['time'].values, low_data['time'].values,
                event_observed_A=high_data['state'].values,
                event_observed_B=low_data['state'].values
            )
            return results.p_value
        except Exception:
            return None

    def _render_single_km_subplot(self, ax_main, ax_risk, df, gene_name, time_label, **kwargs):
        """渲染单个KM曲线子图（单基因和组合图共用）"""
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test, multivariate_logrank_test

        title = kwargs.get('title', '')
        title_size = kwargs.get('title_size', 18)
        legend_size = kwargs.get('legend_size', 12)
        axis_size = kwargs.get('axis_size', 16)
        pval_size = kwargs.get('pval_size', 14)
        show_table = kwargs.get('show_table', True)
        table_size = kwargs.get('table_size', 10)
        show_ci = kwargs.get('show_ci', True)
        show_n = kwargs.get('show_n', True)
        pval_mode = kwargs.get('pval_mode', 0)  # 默认为具体值
        show_global_pval = kwargs.get('show_global_pval', True)
        show_pairwise = kwargs.get('show_pairwise', False)
        selected_pairwise = kwargs.get('selected_pairwise', [])
        font_scale = kwargs.get('font_scale', 1.0)  # 用于组合图时的字体缩放

        unique_groups = sorted(df['group'].unique())
        km_fitters = []
        labels = []
        full_labels = []  # 保存原始完整标签名用于筛选
        group_colors = {}

        for i, group_name in enumerate(unique_groups):
            group_data = df[df['group'] == group_name]

            if len(group_data) < 2:
                continue

            if 'High' in group_name:
                color = self.HIGH_COLORS[i % len(self.HIGH_COLORS)]
                if '(' in group_name:
                    display_name = group_name.split('(')[0].strip()
                else:
                    display_name = group_name
            else:
                color = self.LOW_COLORS[i % len(self.LOW_COLORS)]
                if '(' in group_name:
                    display_name = group_name.split('(')[0].strip()
                else:
                    display_name = group_name

            if show_n:
                label_for_plot = group_name
            else:
                label_for_plot = display_name

            kmf = KaplanMeierFitter()
            kmf.fit(
                group_data['time'],
                event_observed=group_data['state'],
                label=label_for_plot
            )
            kmf.color = color
            km_fitters.append(kmf)
            labels.append(label_for_plot)
            full_labels.append(group_name)  # 保存完整标签名用于筛选
            group_colors[label_for_plot] = color

            kmf.plot_survival_function(
                ax=ax_main,
                ci_show=show_ci,
                color=color,
                linewidth=2.5,
                show_censors=True,
                censor_styles={'marker': '+', 'ms': 7, 'mew': 1.5}
            )

        ax_main.set_title(title, fontsize=title_size, fontweight='bold', pad=15)
        ax_main.set_xlabel(time_label, fontsize=axis_size)
        ax_main.set_ylabel('Survival Probability', fontsize=axis_size)
        ax_main.set_ylim(0, 1.05)
        ax_main.grid(True, linestyle='--', alpha=0.3)

        for kmf in km_fitters:
            median_survival = kmf.median_survival_time_
            if median_survival is not None and not np.isinf(median_survival):
                ax_main.axhline(y=0.5, color='gray', linestyle='--', linewidth=1, alpha=0.5)
                ax_main.axvline(x=median_survival, color='gray', linestyle='--', linewidth=1, alpha=0.5)

        y_pos = 0.12
        if len(km_fitters) >= 2:
            if show_global_pval and len(km_fitters) > 2:
                try:
                    results = multivariate_logrank_test(
                        df['time'].values, df['group'].values, df['state'].values
                    )
                    global_pval = results.p_value

                    if pval_mode == 0:
                        if global_pval < 0.0001:
                            pval_text = f'Global P = {global_pval:.2e}'
                        else:
                            pval_text = f'Global P = {global_pval:.4f}'
                    elif pval_mode == 1:
                        if global_pval < 0.0001:
                            pval_text = 'Global P < 0.0001'
                        elif global_pval < 0.001:
                            pval_text = 'Global P < 0.001'
                        elif global_pval < 0.01:
                            pval_text = 'Global P < 0.01'
                        elif global_pval < 0.05:
                            pval_text = 'Global P < 0.05'
                        else:
                            pval_text = 'Global P >= 0.05'
                    else:
                        if global_pval < 0.0001:
                            pval_text = f'Global P < 0.0001 ({global_pval:.2e})'
                        elif global_pval < 0.001:
                            pval_text = f'Global P < 0.001 ({global_pval:.2e})'
                        elif global_pval < 0.01:
                            pval_text = f'Global P < 0.01 ({global_pval:.3f})'
                        elif global_pval < 0.05:
                            pval_text = f'Global P < 0.05 ({global_pval:.4f})'
                        else:
                            pval_text = f'Global P >= 0.05 ({global_pval:.4f})'

                    ax_main.text(0.02, y_pos, pval_text,
                                 transform=ax_main.transAxes,
                                 fontsize=pval_size * font_scale, fontweight='bold',
                                 color='black')
                    y_pos += 0.08
                except Exception:
                    pass
            elif show_global_pval and len(km_fitters) == 2:
                try:
                    # 使用full_labels进行筛选而不是labels
                    results = logrank_test(
                        df[df['group'] == full_labels[0]]['time'].values,
                        df[df['group'] == full_labels[1]]['time'].values,
                        event_observed_A=df[df['group'] == full_labels[0]]['state'].values,
                        event_observed_B=df[df['group'] == full_labels[1]]['state'].values
                    )
                    global_pval = results.p_value

                    if pval_mode == 0:
                        if global_pval < 0.0001:
                            pval_text = f'P = {global_pval:.2e}'
                        else:
                            pval_text = f'P = {global_pval:.4f}'
                    elif pval_mode == 1:
                        if global_pval < 0.0001:
                            pval_text = 'P < 0.0001'
                        elif global_pval < 0.001:
                            pval_text = 'P < 0.001'
                        elif global_pval < 0.01:
                            pval_text = 'P < 0.01'
                        elif global_pval < 0.05:
                            pval_text = 'P < 0.05'
                        else:
                            pval_text = 'P >= 0.05'
                    else:
                        if global_pval < 0.0001:
                            pval_text = f'P < 0.0001 ({global_pval:.2e})'
                        elif global_pval < 0.001:
                            pval_text = f'P < 0.001 ({global_pval:.2e})'
                        elif global_pval < 0.01:
                            pval_text = f'P < 0.01 ({global_pval:.3f})'
                        elif global_pval < 0.05:
                            pval_text = f'P < 0.05 ({global_pval:.4f})'
                        else:
                            pval_text = f'P >= 0.05 ({global_pval:.4f})'

                    ax_main.text(0.02, y_pos, pval_text,
                                 transform=ax_main.transAxes,
                                 fontsize=pval_size * font_scale, fontweight='bold',
                                 color='black')
                    y_pos += 0.08
                except Exception:
                    pass

        if show_pairwise:
            for item_text in selected_pairwise:
                if y_pos > 0.9:
                    break

                if ' High vs Low' in item_text:
                    compare_gene = item_text.replace(' High vs Low', '')
                else:
                    compare_gene = item_text

                high_label = None
                low_label = None
                for full_lbl, lbl in zip(full_labels, labels):
                    if full_lbl.startswith(f'{compare_gene} High'):
                        high_label = full_lbl
                    elif full_lbl.startswith(f'{compare_gene} Low'):
                        low_label = full_lbl

                if high_label and low_label:
                    try:
                        results = logrank_test(
                            df[df['group'] == high_label]['time'].values,
                            df[df['group'] == low_label]['time'].values,
                            event_observed_A=df[df['group'] == high_label]['state'].values,
                            event_observed_B=df[df['group'] == low_label]['state'].values
                        )
                        p_val = results.p_value

                        # 根据pval_mode格式化p值
                        if pval_mode == 0:
                            if p_val < 0.0001:
                                p_text = f'{compare_gene}: {p_val:.2e}'
                            else:
                                p_text = f'{compare_gene}: {p_val:.4f}'
                        elif pval_mode == 1:
                            if p_val < 0.0001:
                                p_text = f'{compare_gene}: < 0.0001'
                            elif p_val < 0.001:
                                p_text = f'{compare_gene}: < 0.001'
                            elif p_val < 0.01:
                                p_text = f'{compare_gene}: < 0.01'
                            elif p_val < 0.05:
                                p_text = f'{compare_gene}: < 0.05'
                            else:
                                p_text = f'{compare_gene}: >= 0.05'
                        else:
                            if p_val < 0.0001:
                                p_text = f'{compare_gene}: < 0.0001 ({p_val:.2e})'
                            elif p_val < 0.001:
                                p_text = f'{compare_gene}: < 0.001 ({p_val:.2e})'
                            elif p_val < 0.01:
                                p_text = f'{compare_gene}: < 0.01 ({p_val:.3f})'
                            elif p_val < 0.05:
                                p_text = f'{compare_gene}: < 0.05 ({p_val:.4f})'
                            else:
                                p_text = f'{compare_gene}: >= 0.05 ({p_val:.4f})'

                        ax_main.text(0.02, y_pos, p_text,
                                     transform=ax_main.transAxes,
                                     fontsize=pval_size * 0.8 * font_scale, fontweight='bold',
                                     color='black')
                        y_pos += 0.06
                    except Exception:
                        pass

        ax_main.legend(loc='upper right', fontsize=legend_size * font_scale,
                      title=f'{gene_name} expression level' if gene_name else 'Group',
                      title_fontsize=legend_size * font_scale + 1)

        # 风险表格
        if show_table and ax_risk is not None and km_fitters:
            ax_risk.set_xlim(ax_main.get_xlim())
            ax_risk.set_ylim(0, 1)
            ax_risk.axis('off')

            max_time = df['time'].max()
            time_points = np.linspace(0, max_time, 6)
            time_points = np.unique(np.round(time_points))

            table_data = []
            header = [''] + [f'{int(t)}' for t in time_points]

            for kmf, group_label in zip(km_fitters, labels):
                row_data = [group_label]
                group_size = len(df[df['group'] == group_label])
                for t in time_points:
                    risk_at_t = kmf.survival_function_at_times(t).values[0]
                    n_at_risk = int(group_size * risk_at_t)
                    row_data.append(str(n_at_risk))
                table_data.append(row_data)

            row_labels = [row[0] for row in table_data]

            table = ax_risk.table(cellText=[row[1:] for row in table_data],
                                  rowLabels=row_labels,
                                  colLabels=header[1:],
                                  loc='center',
                                  cellLoc='center')

            table.auto_set_font_size(False)
            table.set_fontsize(table_size * font_scale)

            for i, key in enumerate(table.get_celld().keys()):
                cell = table.get_celld()[key]
                cell.set_edgecolor('black')
                cell.set_linewidth(0.5)

                if key[0] == 0:
                    cell.set_facecolor('#f0f0f0')
                    cell.set_text_props(fontweight='bold', fontsize=(table_size + 1) * font_scale)
                else:
                    cell.set_facecolor('white')

    def draw_km_plot(self, df, time_label='Time', **kwargs):
        """绘制KM曲线"""
        import matplotlib.pyplot as plt

        title = kwargs.get('title', self.dataset_name or 'KM Curve')
        title_size = kwargs.get('title_size', 18)
        legend_size = kwargs.get('legend_size', 12)
        axis_size = kwargs.get('axis_size', 16)
        pval_size = kwargs.get('pval_size', 14)
        show_table = kwargs.get('show_table', True)
        table_size = kwargs.get('table_size', 10)
        show_ci = kwargs.get('show_ci', True)
        show_n = kwargs.get('show_n', True)
        pval_mode = kwargs.get('pval_mode', 0)  # 默认为具体值
        show_global_pval = kwargs.get('show_global_pval', True)
        show_pairwise = kwargs.get('show_pairwise', False)
        selected_pairwise = kwargs.get('selected_pairwise', [])
        export_width = kwargs.get('export_width', 8)
        export_height = kwargs.get('export_height', 6)
        gene_name = kwargs.get('gene_name', '')

        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

        if show_table:
            fig = plt.figure(figsize=(export_width, export_height))
            ax_main = fig.add_axes([0.12, 0.28, 0.82, 0.6])
            ax_risk = fig.add_axes([0.12, 0.02, 0.82, 0.22])
        else:
            fig, ax_main = plt.subplots(figsize=(export_width, export_height))
            ax_risk = None

        self._render_single_km_subplot(
            ax_main, ax_risk, df, gene_name, time_label,
            title=title, title_size=title_size, legend_size=legend_size,
            axis_size=axis_size, pval_size=pval_size, show_table=show_table,
            table_size=table_size, show_ci=show_ci, show_n=show_n,
            pval_mode=pval_mode, show_global_pval=show_global_pval,
            show_pairwise=show_pairwise, selected_pairwise=selected_pairwise,
            font_scale=1.0
        )

        # 根据是否有基因名决定文件名
        if gene_name:
            output_path = os.path.join(self.dataset_output_dir, f"{gene_name}_{self.dataset_name}_km.png")
        else:
            output_path = os.path.join(self.dataset_output_dir, f"{self.dataset_name}_km.png")
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        self.current_km_fig_path = output_path
        return output_path

    def draw_combined_km_plot(self, km_data_list, time_label='Time', **kwargs):
        """绘制多基因组合KM曲线"""
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec

        num_genes = len(km_data_list)
        if num_genes == 0:
            return None

        export_width = kwargs.get('export_width', 8)
        export_height = kwargs.get('export_height', 6)
        title_size = kwargs.get('title_size', 18)
        legend_size = kwargs.get('legend_size', 12)
        axis_size = kwargs.get('axis_size', 16)
        pval_size = kwargs.get('pval_size', 14)
        show_table = kwargs.get('show_table', False)
        table_size = kwargs.get('table_size', 10)
        pval_mode = kwargs.get('pval_mode', 0)  # 默认为具体值
        show_global_pval = kwargs.get('show_global_pval', True)
        show_pairwise = kwargs.get('show_pairwise', False)
        selected_pairwise = kwargs.get('selected_pairwise', [])
        show_ci = kwargs.get('show_ci', True)
        show_n = kwargs.get('show_n', True)
        dataset_name = kwargs.get('dataset_name', self.dataset_name or '')

        max_per_row = 3
        n_cols = min(num_genes, max_per_row)
        n_rows = int(np.ceil(num_genes / n_cols))

        # 计算字体缩放比例：组合图比单图大，需要缩小字体
        # 基于基因数量和是否有风险表格来调整
        if num_genes <= 2:
            font_scale = 0.75
        elif num_genes <= 4:
            font_scale = 0.65
        else:
            font_scale = 0.55

        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

        if show_table:
            gs = GridSpec(n_rows * 2, n_cols, height_ratios=[0.6] + [0.22] + [0.6, 0.22] * (n_rows - 1))
            combined_width = export_width * n_cols
            combined_height = export_height * n_rows
            fig = plt.figure(figsize=(combined_width, combined_height))

            for i, (gene_name, df) in enumerate(km_data_list):
                row_idx = i // n_cols
                col_idx = i % n_cols

                main_row = row_idx * 2
                table_row = row_idx * 2 + 1

                ax_main = fig.add_subplot(gs[main_row, col_idx])
                ax_risk = fig.add_subplot(gs[table_row, col_idx])

                plot_title = f"{gene_name} {dataset_name}"
                self._render_single_km_subplot(
                    ax_main, ax_risk, df, gene_name, time_label,
                    title=plot_title, title_size=title_size, legend_size=legend_size,
                    axis_size=axis_size, pval_size=pval_size, show_table=show_table,
                    table_size=table_size, show_ci=show_ci, show_n=show_n,
                    pval_mode=pval_mode, show_global_pval=show_global_pval,
                    show_pairwise=show_pairwise, selected_pairwise=selected_pairwise,
                    font_scale=font_scale
                )

            plt.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.02, hspace=0.05, wspace=0.2)
        else:
            combined_width = export_width * n_cols
            combined_height = export_height * n_rows
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(combined_width, combined_height))
            axes = axes.flatten() if num_genes > 1 else [axes]

            for i, (gene_name, df) in enumerate(km_data_list):
                if i >= len(axes):
                    break

                ax_main = axes[i]
                ax_risk = None

                plot_title = f"{gene_name} {dataset_name}"
                self._render_single_km_subplot(
                    ax_main, ax_risk, df, gene_name, time_label,
                    title=plot_title, title_size=title_size, legend_size=legend_size,
                    axis_size=axis_size, pval_size=pval_size, show_table=show_table,
                    table_size=table_size, show_ci=show_ci, show_n=show_n,
                    pval_mode=pval_mode, show_global_pval=show_global_pval,
                    show_pairwise=show_pairwise, selected_pairwise=selected_pairwise,
                    font_scale=font_scale
                )

            for i in range(num_genes, len(axes)):
                axes[i].axis('off')

            plt.tight_layout()

        output_path = os.path.join(self.dataset_output_dir, f"{self.dataset_name}_km_combined.png")
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        self.current_km_fig_path = output_path
        return output_path

    def export_png(self, output_path=None):
        """导出PNG"""
        if self.current_km_fig_path and os.path.exists(self.current_km_fig_path):
            if output_path:
                import shutil
                shutil.copy(self.current_km_fig_path, output_path)
                return output_path
            return self.current_km_fig_path
        return None

    def export_pdf(self, pdf_path):
        """导出PDF"""
        if self.current_km_fig_path and os.path.exists(self.current_km_fig_path):
            try:
                from PIL import Image
                img = Image.open(self.current_km_fig_path)
                img = img.convert('RGB')
                img.save(pdf_path, 'PDF', resolution=150)
                return pdf_path
            except ImportError:
                import shutil
                base_name = os.path.splitext(pdf_path)[0]
                shutil.copy(self.current_km_fig_path, f"{base_name}.png")
                return pdf_path
        return None

    def export_svg(self, svg_path):
        """导出SVG"""
        if hasattr(self, 'current_km_df') and self.current_km_df is not None:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from lifelines import KaplanMeierFitter
            from lifelines.statistics import logrank_test, multivariate_logrank_test
            import warnings
            warnings.filterwarnings('ignore')

            df = self.current_km_df
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
            plt.rcParams['axes.unicode_minus'] = False

            fig, ax = plt.subplots(figsize=(8, 6))
            unique_groups = sorted(df['group'].unique())
            km_fitters = []
            labels = []

            for i, group_name in enumerate(unique_groups):
                group_data = df[df['group'] == group_name]
                if len(group_data) < 2:
                    continue
                color = self.HIGH_COLORS[i % len(self.HIGH_COLORS)] if 'High' in group_name else self.LOW_COLORS[i % len(self.LOW_COLORS)]
                kmf = KaplanMeierFitter()
                kmf.fit(group_data['time'], event_observed=group_data['state'], label=group_name)
                kmf.color = color
                km_fitters.append(kmf)
                labels.append(group_name)
                kmf.plot_survival_function(ax=ax, ci_show=True, color=color, linewidth=2.5)

            ax.set_xlabel('Time', fontsize=12)
            ax.set_ylabel('Survival Probability', fontsize=12)
            ax.set_ylim(0, 1.05)
            ax.grid(True, linestyle='--', alpha=0.3)
            ax.legend(loc='upper right')
            plt.tight_layout()
            plt.savefig(svg_path, format='svg', bbox_inches='tight')
            plt.close()
            return svg_path
        return None

    def export_csv(self, csv_path):
        """导出CSV数据"""
        if hasattr(self, 'current_km_df') and self.current_km_df is not None:
            self.current_km_df.to_csv(csv_path, index=False)
            return csv_path
        return None