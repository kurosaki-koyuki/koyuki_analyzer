# -*- coding: utf-8 -*-
"""
自定义气泡图生信分析算法脚本 - 自定义气泡图页面的核心生信分析方法
包含基因加载、数据筛选、绘图、导出等功能
支持X轴和Y轴双注释，单基因/多基因表达量评估
"""

from script.utils_layer.import_config import *


class ScTargetgeneBubbleAnalysis:
    """自定义气泡图分析类 - 支持X轴和Y轴双注释的气泡图分析"""

    def __init__(self):
        self.adata = None
        self.target_gene_cell_total_df = None
        self.target_gene_list = []
        self.target_gene_final_df = None
        self.dataset_output_dir = None
        self.current_fig = None
        self.current_fig_path = None
        self.gene_bubble_param_templates = {}

    def set_adata(self, adata):
        """设置当前adata对象"""
        self.adata = adata

    def set_dataset_output_dir(self, dataset_output_dir):
        """设置数据集输出目录"""
        self.dataset_output_dir = dataset_output_dir

    def load_target_genes(self, gene_text):
        """加载目标基因数据"""
        if not gene_text:
            raise ValueError("请输入基因列表")

        if self.adata is None:
            raise ValueError("请先加载数据集")

        input_genes = [g.strip() for g in gene_text.splitlines() if g.strip()]
        if not input_genes:
            raise ValueError("请输入基因列表（每行一个）")

        var_sym = self.adata.var.gene_symbol.values if "gene_symbol" in self.adata.var.columns else self.adata.var_names.values
        valid_genes = [g for g in input_genes if g in var_sym]
        lost_genes = [g for g in input_genes if g not in var_sym]

        if not valid_genes:
            raise ValueError("无有效基因，请核对基因名")

        self.target_gene_cell_total_df = self.adata.obs.copy()
        self.target_gene_cell_total_df["cell_id"] = self.adata.obs_names

        gene2idx = {g: i for i, g in enumerate(var_sym)}
        for g in valid_genes:
            idx = gene2idx[g]
            expr_mat = self.adata.X[:, idx]
            if hasattr(expr_mat, "toarray"):
                expr_mat = expr_mat.toarray().ravel()
            self.target_gene_cell_total_df[g] = expr_mat

        self.target_gene_list = valid_genes

        valid_groups = [c for c in self.adata.obs.columns if c != 'cell_id']
        return valid_genes, lost_genes, valid_groups, len(self.target_gene_cell_total_df)

    def get_group_unique_vals(self, group):
        """获取某分组列的唯一值列表"""
        if self.adata is None:
            return []
        if group not in self.adata.obs.columns:
            return []
        return sorted([str(v) for v in self.adata.obs[group].unique()])

    def draw_target_gene_bubble_plot(self, x_col, x_sel, y_col, y_sel,
                                       f1_col=None, f1_sel=None, f2_col=None, f2_sel=None,
                                       main_title="Target Gene Expression Bubble Plot", scale_factor=750, legend_scale=1.0,
                                       main_right_ratio=0.65, title_fontsize=14, x_label_fontsize=12,
                                       y_label_fontsize=12, cbar_left=0.62, cbar_bottom=0.62, cbar_width=0.03,
                                       cbar_height=0.35, legend_anchor_x=1.0, legend_anchor_y=0.2,
                                       label_spacing=2.5, legend_title_fontsize=10, cbar_label_fontsize=10,
                                       cbar_label_text="Mean Expression", collapsed=False,
                                       fig_width=9, fig_height=7):
        """绘制自定义气泡图"""
        if self.adata is None:
            raise ValueError("请先加载数据集")

        if self.target_gene_cell_total_df is None:
            raise ValueError("请先加载基因数据")

        df = self.target_gene_cell_total_df.copy()

        if x_col and x_sel:
            df = df[df[x_col].isin(x_sel)]
        elif x_col and not x_sel:
            df = df.iloc[0:0]

        if y_col and y_sel:
            df = df[df[y_col].isin(y_sel)]
        elif y_col and not y_sel:
            df = df.iloc[0:0]

        if f1_col and f1_sel:
            df = df[df[f1_col].isin(f1_sel)]
        elif f1_col and not f1_sel:
            df = df.iloc[0:0]

        if f2_col and f2_sel:
            df = df[df[f2_col].isin(f2_sel)]
        elif f2_col and not f2_sel:
            df = df.iloc[0:0]

        if df.empty:
            raise ValueError("筛选后无细胞数据")

        valid_genes = [g for g in self.target_gene_list if g in df.columns]

        if len(valid_genes) == 1:
            gene = valid_genes[0]
            group_agg = df.groupby([x_col, y_col]).agg(
                mean_expr=(gene, "mean"),
                total_cells=("cell_id", "count"),
                expr_cells=(gene, lambda x: (x > 0).sum())
            ).reset_index()
            group_agg["Gene"] = gene
            group_agg["percent_expressed"] = group_agg["expr_cells"] / group_agg["total_cells"]
            agg_list = [group_agg]
        else:
            gene_expr_cols = [g for g in valid_genes if g in df.columns]
            df["gene_set_mean_expr"] = df[gene_expr_cols].mean(axis=1)
            df["gene_set_sum_expr"] = df[gene_expr_cols].sum(axis=1)
            df["gene_set_expr_count"] = (df[gene_expr_cols] > 0).sum(axis=1)
            df["gene_set_percent"] = df["gene_set_expr_count"] / len(gene_expr_cols)

            group_agg = df.groupby([x_col, y_col]).agg(
                mean_expr=("gene_set_mean_expr", "mean"),
                total_cells=("cell_id", "count"),
                expr_cells=("gene_set_expr_count", "sum")
            ).reset_index()
            group_agg["Gene"] = "+".join(valid_genes)
            group_agg["percent_expressed"] = group_agg["expr_cells"] / (group_agg["total_cells"] * len(valid_genes))
            group_agg["percent_expressed"] = group_agg["percent_expressed"].clip(0, 1)
            agg_list = [group_agg]

        if not agg_list:
            raise ValueError("无绘图数据")

        self.target_gene_final_df = pd.concat(agg_list, ignore_index=True)

        figsize = (fig_width, fig_height)

        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=figsize, dpi=120)

        df_plot = self.target_gene_final_df

        scatter = ax.scatter(
            data=df_plot,
            x=x_col,
            y=y_col,
            c="mean_expr",
            s=df_plot["percent_expressed"] * scale_factor,
            cmap="Reds",
            alpha=0.8,
            edgecolors="none"
        )

        unique_y = df_plot[y_col].unique()
        n_y = len(unique_y)
        ax.set_ylim(-0.5, n_y - 0.5)

        unique_x = df_plot[x_col].unique()
        n_x = len(unique_x)
        ax.set_xlim(-0.5, n_x - 0.5)

        plt.xticks(rotation=45, ha="right", fontsize=10)
        plt.yticks(fontsize=10)
        ax.set_title(main_title, fontsize=title_fontsize, pad=20)
        ax.set_xlabel(x_col, fontsize=x_label_fontsize)
        ax.set_ylabel(y_col, fontsize=y_label_fontsize)

        ax.xaxis.set_label_coords(0.5, -0.22)
        ax.yaxis.set_label_coords(-0.18, 0.5)

        plt.subplots_adjust(right=main_right_ratio, left=0.18, bottom=0.25, top=0.90)

        cbar = plt.colorbar(scatter, ax=ax, fraction=cbar_width, pad=0.08, location="right")
        cbar.ax.set_position([cbar_left, cbar_bottom, cbar_width, cbar_height])
        cbar.set_label("")
        cbar.ax.set_ylabel(cbar_label_text, rotation=270, labelpad=15, fontsize=cbar_label_fontsize)

        size_ticks = [0.2, 0.4, 0.6, 0.8, 1.0]
        handles = [plt.scatter([], [], s=v * scale_factor, color="black", alpha=0.8) for v in size_ticks]
        ax.legend(
            handles, [str(v) for v in size_ticks],
            title="Expression Ratio",
            loc="center left",
            bbox_to_anchor=(legend_anchor_x, legend_anchor_y),
            frameon=False,
            labelspacing=label_spacing,
            handletextpad=0.8,
            title_fontsize=legend_title_fontsize,
            fontsize=legend_title_fontsize,
            scatterpoints=1,
            markerscale=legend_scale
        )

        self.current_fig = fig

        if self.dataset_output_dir:
            od = os.path.join(self.dataset_output_dir, "target_gene_bubble")
        else:
            od = os.path.join(os.path.expanduser("~"), "koyuki_target_gene_bubble")
        os.makedirs(od, exist_ok=True)

        self.current_fig_path = os.path.join(od, "target_gene_bubble_temp.png")
        plt.savefig(self.current_fig_path, dpi=100, bbox_inches='tight')
        plt.close()

        return len(df), self.current_fig_path

    def export_png(self, save_path):
        """导出PNG"""
        if self.current_fig_path is None:
            raise ValueError("请先绘图")

        if not save_path.endswith('.png'):
            save_path += '.png'

        pixmap = QPixmap(self.current_fig_path)
        pixmap.save(save_path)

    def export_csv(self, save_path):
        """导出绘图数据为CSV"""
        if self.target_gene_final_df is None:
            raise ValueError("请先绘图")

        if not save_path.endswith('.csv'):
            save_path += '.csv'

        self.target_gene_final_df.to_csv(save_path, index=False, encoding='utf-8-sig')

    def export_other(self, save_path, fmt):
        """导出其他格式（PDF/SVG/EPS）"""
        if self.target_gene_final_df is None:
            raise ValueError("请先绘图")

        if not save_path.endswith(f'.{fmt}'):
            save_path += f'.{fmt}'

        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(10, 8), dpi=120)

        df_plot = self.target_gene_final_df
        x_col = df_plot.columns[0]
        y_col = df_plot.columns[1]

        scatter = ax.scatter(
            data=df_plot,
            x=x_col,
            y=y_col,
            c="mean_expr",
            s=df_plot["percent_expressed"] * 750,
            cmap="Reds",
            alpha=0.8,
            edgecolors="none"
        )

        unique_y = df_plot[y_col].unique()
        n_y = len(unique_y)
        ax.set_ylim(-0.5, n_y - 0.5)

        unique_x = df_plot[x_col].unique()
        n_x = len(unique_x)
        ax.set_xlim(-0.5, n_x - 0.5)

        plt.xticks(rotation=45, ha="right", fontsize=10)
        plt.yticks(fontsize=10)
        ax.set_title("目标基因表达气泡图", fontsize=14, pad=20)
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel(y_col, fontsize=12)

        ax.xaxis.set_label_coords(0.5, -0.22)
        ax.yaxis.set_label_coords(-0.18, 0.5)

        plt.subplots_adjust(right=0.65, left=0.18, bottom=0.25, top=0.90)

        cbar = plt.colorbar(scatter, ax=ax, fraction=0.03, pad=0.08, location="right")
        cbar.ax.set_position([0.62, 0.62, 0.03, 0.35])
        cbar.set_label("")
        cbar.ax.set_ylabel("表达量均值", rotation=270, labelpad=15, fontsize=10)

        size_ticks = [0.2, 0.4, 0.6, 0.8, 1.0]
        handles = [plt.scatter([], [], s=v * 750, color="black", alpha=0.8) for v in size_ticks]
        ax.legend(
            handles, [str(v) for v in size_ticks],
            title="表达占比",
            loc="center left",
            bbox_to_anchor=(1.0, 0.2),
            frameon=False,
            labelspacing=2.5,
            handletextpad=0.8,
            title_fontsize=10,
            scatterpoints=1,
            markerscale=1.0
        )

        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

    def save_template(self, name, template_data):
        """保存参数模板"""
        self.gene_bubble_param_templates[name] = template_data

    def load_template(self, name):
        """加载参数模板"""
        return self.gene_bubble_param_templates.get(name)

    def get_template_names(self):
        """获取所有模板名称"""
        return list(self.gene_bubble_param_templates.keys())


__all__ = ['ScTargetgeneBubbleAnalysis']