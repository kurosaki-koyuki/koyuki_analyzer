# -*- coding: utf-8 -*-
"""
单细胞StaVIA分析数据分析脚本 - 负责核心业务算法、数据处理等
完全不涉及UI操作
"""

import os
import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import scanpy as sc
from script.utils_layer.import_config import OUT_BASE


class ScStaviaAnalysis:
    """单细胞StaVIA分析数据分析类"""

    def __init__(self):
        self.adata = None
        self.via_object = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.results = {}
        self.plot_figures = {}

    def set_data(self, adata, dataset_name, dataset_output_dir):
        self.adata = adata.copy()
        self.dataset_name = dataset_name
        self.dataset_output_dir = dataset_output_dir

    def get_output_dir(self):
        output_dir = os.path.join(OUT_BASE, 'stavia')
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def run_via_analysis(self, ncomps=30, knn=15, root_user=['0'], memory=10,
                         edgepruning_clustering_resolution=0.15,
                         cluster_graph_pruning=0.15, resolution_parameter=1.5,
                         random_seed=4, use_rep='X_pca', clusters='seurat_clusters',
                         basis='X_umap', re_dim=False, filter_params=None):
        from omicverse.external import VIA

        if self.adata is None:
            raise ValueError("数据未设置")

        if filter_params is None:
            filter_params = {}

        filtered_adata = self.adata.copy()

        def _to_matching_type(selected_list, target_series):
            if len(selected_list) == 0:
                return selected_list
            target_dtype = target_series.dtype
            if pd.api.types.is_numeric_dtype(target_dtype) and not pd.api.types.is_bool_dtype(target_dtype):
                converted = []
                for s in selected_list:
                    try:
                        if pd.api.types.is_integer_dtype(target_dtype):
                            converted.append(int(float(s)))
                        else:
                            converted.append(float(s))
                    except (ValueError, TypeError):
                        converted.append(s)
                return converted
            return selected_list

        mask = np.ones(len(filtered_adata), dtype=bool)

        main_col = filter_params.get('main_col')
        main_selected = filter_params.get('main_selected', [])
        if main_col and main_selected and main_col in filtered_adata.obs.columns:
            main_selected_typed = _to_matching_type(main_selected, filtered_adata.obs[main_col])
            mask &= filtered_adata.obs[main_col].isin(main_selected_typed).values

        filter1_enabled = filter_params.get('filter1_enabled', False)
        filter1_col = filter_params.get('filter1_col')
        filter1_selected = filter_params.get('filter1_selected', [])
        if filter1_enabled and filter1_col and filter1_selected and filter1_col in filtered_adata.obs.columns:
            filter1_selected_typed = _to_matching_type(filter1_selected, filtered_adata.obs[filter1_col])
            mask &= filtered_adata.obs[filter1_col].isin(filter1_selected_typed).values

        filter2_enabled = filter_params.get('filter2_enabled', False)
        filter2_col = filter_params.get('filter2_col')
        filter2_selected = filter_params.get('filter2_selected', [])
        if filter2_enabled and filter2_col and filter2_selected and filter2_col in filtered_adata.obs.columns:
            filter2_selected_typed = _to_matching_type(filter2_selected, filtered_adata.obs[filter2_col])
            mask &= filtered_adata.obs[filter2_col].isin(filter2_selected_typed).values

        if not np.all(mask):
            filtered_adata = filtered_adata[mask]

        if re_dim:
            use_hv = 'highly_variable' in filtered_adata.var.columns
            if use_hv:
                sc.pp.pca(filtered_adata, n_comps=ncomps, mask_var='highly_variable')
            else:
                sc.pp.pca(filtered_adata, n_comps=ncomps)
            sc.pp.neighbors(filtered_adata, n_neighbors=knn)
            sc.tl.umap(filtered_adata)

        if use_rep not in filtered_adata.obsm:
            raise ValueError(f"{use_rep} 不在 adata.obsm 中")

        if clusters not in filtered_adata.obs:
            raise ValueError(f"{clusters} 不在 adata.obs 中")

        filtered_adata.obs[clusters] = filtered_adata.obs[clusters].astype(str)
        filtered_adata.obs[clusters] = filtered_adata.obs[clusters].astype('category')

        if f'{clusters}_colors' not in filtered_adata.uns:
            sc.pl._utils.add_colors_for_categorical_sample_annotation(filtered_adata, clusters)

        self.via_object = VIA.core.VIA(
            data=filtered_adata.obsm[use_rep][:, 0:ncomps],
            true_label=filtered_adata.obs[clusters],
            edgepruning_clustering_resolution=edgepruning_clustering_resolution,
            cluster_graph_pruning=cluster_graph_pruning,
            knn=knn,
            root_user=root_user,
            resolution_parameter=resolution_parameter,
            dataset='',
            random_seed=random_seed,
            memory=memory
        )

        self.via_object.run_VIA()

        self.adata = filtered_adata

        self.results = {
            'ncomps': ncomps,
            'knn': knn,
            'memory': memory,
            'clusters': clusters,
            'basis': basis,
            'use_rep': use_rep,
            'num_cells': self.adata.shape[0],
            'num_clusters': len(set(self.via_object.labels)),
            'num_terminal_clusters': len(self.via_object.terminal_clusters),
        }

        return self.results

    def generate_plots(self, clusters='seurat_clusters', basis='X_umap'):
        from omicverse.external import VIA

        if self.via_object is None:
            raise ValueError("VIA分析尚未运行")

        self.plot_figures = {}
        dpi = 300

        n_cells = self.adata.shape[0]
        if n_cells > 10000:
            density_grid = 5.0
            smooth_grid = 5.0
        elif n_cells > 5000:
            density_grid = 3.0
            smooth_grid = 3.0
        else:
            density_grid = 1.0
            smooth_grid = 1.0

        try:
            fig, ax, ax1 = VIA.core.plot_piechart_viagraph_ov(
                self.adata,
                clusters=clusters,
                dpi=dpi,
                via_object=self.via_object,
                ax_text=False,
                show_legend=False
            )
            fig.set_size_inches(8, 4)
            self.plot_figures['piechart'] = fig
        except Exception as e:
            self.plot_figures['piechart'] = None

        try:
            self.adata.obs['pt_via'] = self.via_object.single_cell_pt_markov
            fig, ax = plt.subplots(figsize=(8, 8))
            sc.pl.embedding(self.adata, basis=basis, color=['pt_via'], frameon='small', cmap='Reds', show=False, ax=ax)
            self.plot_figures['pt_via'] = fig
        except Exception as e:
            self.plot_figures['pt_via'] = None

        try:
            fig, ax, ax1 = VIA.core.plot_trajectory_curves_ov(
                self.adata,
                clusters=clusters,
                dpi=dpi,
                via_object=self.via_object,
                embedding=self.adata.obsm[basis],
                draw_all_curves=False,
                scatter_size=10,
                scatter_alpha=0.3
            )
            self.plot_figures['trajectory'] = fig
        except Exception as e:
            self.plot_figures['trajectory'] = None

        try:
            self.via_object.embedding = self.adata.obsm[basis]
            fig, ax = VIA.core.plot_atlas_view(
                via_object=self.via_object,
                n_milestones=150,
                sc_labels=self.adata.obs[clusters],
                fontsize_title=12,
                fontsize_labels=12,
                dpi=dpi,
                extra_title_text='Atlas View colored by pseudotime'
            )
            fig.set_size_inches(4, 4)
            self.plot_figures['atlas'] = fig
        except Exception as e:
            self.plot_figures['atlas'] = None

        try:
            fig, ax = VIA.core.via_streamplot_ov(
                self.adata,
                clusters=clusters,
                via_object=self.via_object,
                embedding=self.adata.obsm[basis],
                density_grid=density_grid,
                arrow_size=0.7,
                arrow_color='k',
                arrow_style="-|>",
                max_length=4,
                linewidth=1,
                min_mass=1,
                cutoff_perc=5,
                scatter_size=10,
                scatter_alpha=0.5,
                marker_edgewidth=0.1,
                density_stream=2,
                smooth_transition=1,
                smooth_grid=smooth_grid,
                color_scheme='annotation',
                gp_color='white',
                bg_color='black',
                dpi=dpi,
                title='Streamplot (Cluster)'
            )
            current_size = fig.get_size_inches()
            fig.set_size_inches(current_size[1], current_size[1])
            self.plot_figures['streamplot_cluster'] = fig
        except Exception as e:
            import traceback
            error_log = os.path.join(self.get_output_dir(), 'streamplot_error.log')
            with open(error_log, 'a') as f:
                f.write(f"Streamplot Cluster Error (n_cells={n_cells}, density_grid={density_grid}):\n{str(e)}\n{traceback.format_exc()}\n")
            self.plot_figures['streamplot_cluster'] = None

        try:
            fig, ax = VIA.core.via_streamplot_ov(
                self.adata,
                clusters=clusters,
                via_object=self.via_object,
                embedding=self.adata.obsm[basis],
                density_grid=density_grid,
                arrow_size=0.7,
                arrow_color='k',
                arrow_style="-|>",
                max_length=4,
                linewidth=1,
                min_mass=1,
                cutoff_perc=5,
                scatter_size=10,
                scatter_alpha=0.5,
                marker_edgewidth=0.1,
                density_stream=2,
                smooth_transition=1,
                smooth_grid=smooth_grid,
                color_scheme='time',
                gp_color='white',
                bg_color='black',
                dpi=dpi,
                title='Streamplot (Pseudotime)'
            )
            current_size = fig.get_size_inches()
            fig.set_size_inches(current_size[1], current_size[1])
            self.plot_figures['streamplot_pt'] = fig
        except Exception as e:
            import traceback
            error_log = os.path.join(self.get_output_dir(), 'streamplot_error.log')
            with open(error_log, 'a') as f:
                f.write(f"Streamplot PT Error (n_cells={n_cells}, density_grid={density_grid}):\n{str(e)}\n{traceback.format_exc()}\n")
            self.plot_figures['streamplot_pt'] = None

        self.results['plots'] = list(self.plot_figures.keys())

        output_dir = self.get_output_dir()
        print(f"[StaVIA] 图片保存目录: {output_dir}")
        print(f"[StaVIA] dataset_name: {self.dataset_name}")
        for key, fig in self.plot_figures.items():
            if fig is not None:
                file_path = os.path.join(output_dir, f'{self.dataset_name}_stavia_{key}.png')
                try:
                    fig.savefig(file_path, format='png', dpi=300, bbox_inches='tight')
                    print(f"[StaVIA] 已保存: {file_path}")
                except Exception as e:
                    print(f"[StaVIA] 保存失败 {key}: {e}")

        return self.plot_figures

    def get_figure_as_pixmap(self, key):
        if key not in self.plot_figures or self.plot_figures[key] is None:
            return None
        fig = self.plot_figures[key]
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap

    def save_figure(self, key, file_path, fmt='png', dpi=300):
        if key not in self.plot_figures or self.plot_figures[key] is None:
            return False
        fig = self.plot_figures[key]
        fig.savefig(file_path, format=fmt, dpi=dpi, bbox_inches='tight')
        return True

    def save_all_figures(self, output_dir=None, fmt='png', dpi=300):
        if output_dir is None:
            output_dir = self.get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        saved = {}
        for key, fig in self.plot_figures.items():
            if fig is not None:
                file_path = os.path.join(output_dir, f'{self.dataset_name}_stavia_{key}.{fmt}')
                try:
                    fig.savefig(file_path, format=fmt, dpi=dpi, bbox_inches='tight')
                    saved[key] = file_path
                except Exception:
                    saved[key] = None
            else:
                saved[key] = None
        return saved

    def get_current_tab_figure(self, tab_name):
        tab_map = {
            '谱系饼图': 'piechart',
            '伪时间图': 'pt_via',
            '轨迹曲线': 'trajectory',
            'Atlas视图': 'atlas',
            '轨迹箭头图': 'streamplot_cluster',
            '轨迹箭头图(PT)': 'streamplot_pt',
        }
        key = tab_map.get(tab_name)
        if key and key in self.plot_figures:
            return self.plot_figures[key]
        return None

    def close_all_figures(self):
        for key, fig in self.plot_figures.items():
            if fig is not None:
                plt.close(fig)
        self.plot_figures = {}
