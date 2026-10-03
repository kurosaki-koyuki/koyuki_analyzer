# -*- coding: utf-8 -*-
"""
UMAP初步作图Python版本核心算法脚本
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong

DPI = 300

class ScUmapInitialPyAnalysis:
    def __init__(self):
        self.adata = None
        self.current_gene = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.static_umap_dir = None
        self.umap_key = "X_umap"
        self.valid_groups = []
        self.current_data_folder = None
    
    def scan_data_folder(self):
        folder_path = SCAN_DATA_PATH
        if not os.path.exists(folder_path):
            return False, [], f"扫描路径不存在: {folder_path}"

        h5ad_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.h5ad')])
        if not h5ad_files:
            return False, [], f"{folder_path} 中没有找到h5ad文件"

        self.current_data_folder = folder_path
        return True, h5ad_files, ""

    def load_data(self, selected_file):
        if not self.current_data_folder:
            return False, {}, "请先选择数据路径"

        if not selected_file:
            return False, {}, "请选择要加载的h5ad文件"

        self.clear_data()
        data_path = os.path.join(self.current_data_folder, selected_file)

        try:
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"数据文件不存在: {data_path}")

            import scanpy as sc
            self.adata = sc.read_h5ad(data_path)

            possible_keys = ["X_umap", "X_UMAP"]
            for key in possible_keys:
                if key in self.adata.obsm:
                    self.umap_key = key
                    break

            PREFERRED_GROUPS = ["cell_type", "group", "sample_type", "sample"]
            self.valid_groups = []
            for col in PREFERRED_GROUPS:
                if col in self.adata.obs.columns and self.adata.obs[col].nunique() <= 50:
                    self.valid_groups.append(col)

            if not self.valid_groups:
                for col in self.adata.obs.columns:
                    try:
                        if self.adata.obs[col].nunique() <= 50:
                            self.valid_groups.append(col)
                    except Exception:
                        continue

            from script.utils_layer.import_config import OUT_BASE
            self.dataset_name = os.path.splitext(selected_file)[0]
            self.dataset_output_dir = os.path.join(OUT_BASE, self.dataset_name)
            os.makedirs(self.dataset_output_dir, exist_ok=True)

            self.static_umap_dir = os.path.join(self.dataset_output_dir, "_static_umap_groups")
            os.makedirs(self.static_umap_dir, exist_ok=True)

            data_info = {
                'cells': self.adata.shape[0],
                'genes': self.adata.shape[1],
                'umap_key': self.umap_key,
                'dataset': self.dataset_name,
                'valid_groups': self.valid_groups,
            }

            self.draw_static_umap_all()

            return True, data_info, ""

        except Exception as e:
            traceback.print_exc()
            return False, {}, f"加载失败: {str(e)}"

    def clear_data(self):
        self.adata = None
        self.current_gene = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.static_umap_dir = None
        self.valid_groups = []
    
    def set_adata(self, adata):
        self.adata = adata
        if adata is not None:
            possible_keys = ["X_umap", "X_UMAP"]
            for key in possible_keys:
                if key in self.adata.obsm:
                    self.umap_key = key
                    break
            
            PREFERRED_GROUPS = ["cell_type", "group", "sample_type", "sample"]
            self.valid_groups = []
            for col in PREFERRED_GROUPS:
                if col in self.adata.obs.columns and self.adata.obs[col].nunique() <= 50:
                    self.valid_groups.append(col)
            
            if not self.valid_groups:
                for col in self.adata.obs.columns:
                    try:
                        if self.adata.obs[col].nunique() <= 50:
                            self.valid_groups.append(col)
                    except Exception:
                        continue
    
    def set_dataset_output_dir(self, dataset_output_dir):
        self.dataset_output_dir = dataset_output_dir
        if dataset_output_dir:
            self.dataset_name = os.path.basename(dataset_output_dir)
            self.static_umap_dir = os.path.join(dataset_output_dir, "_static_umap_groups")
            os.makedirs(self.static_umap_dir, exist_ok=True)
    
    def get_data_info(self):
        if self.adata is None:
            return {}
        return {
            'cells': self.adata.shape[0],
            'genes': self.adata.shape[1],
            'umap_key': self.umap_key,
            'dataset': self.dataset_name,
            'valid_groups': self.valid_groups,
        }

    def get_plot_items_for_source(self, source_text):
        if self.adata is None:
            return []
        if source_text == "基因表达量":
            return ["表达量UMAP"] + self.valid_groups
        else:
            return self.valid_groups

    def get_plot_image_path(self, source_text, plot_text):
        if self.adata is None:
            return None, "请先加载数据"

        if source_text == "基因表达量" and plot_text != "表达量UMAP" and not self.current_gene:
            return None, ""

        if not plot_text:
            return None, ""

        try:
            if source_text == "基因表达量":
                if plot_text == "表达量UMAP":
                    return self._get_expr_umap_path()
                else:
                    return self._get_violin_path(plot_text)
            else:
                if plot_text in self.valid_groups:
                    return self._get_anno_umap_path(plot_text)
            return None, ""
        except Exception as e:
            return None, f"切换绘图失败: {str(e)}"
    
    def get_gene_expression(self, gene_name):
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
    
    def run_gene_full_plot(self, gene_name):
        gene_dir = os.path.join(self.dataset_output_dir, gene_name)
        os.makedirs(gene_dir, exist_ok=True)
        
        expr_vals = self.get_gene_expression(gene_name)
        
        if self.umap_key in self.adata.obsm:
            umap_png = os.path.join(gene_dir, f"{gene_name}_UMAP_EXPR.png")
            umap_pdf = os.path.join(gene_dir, f"{gene_name}_UMAP_EXPR.pdf")
            if not os.path.exists(umap_png) or not os.path.exists(umap_pdf):
                plt.figure(figsize=(6.3, 6.5))
                plt.scatter(
                    self.adata.obsm[self.umap_key][:, 0],
                    self.adata.obsm[self.umap_key][:, 1],
                    c=expr_vals, s=1.5, cmap="viridis"
                )
                cbar = plt.colorbar()
                cbar.ax.tick_params(labelsize=12)
                cbar.set_label(gene_name, fontsize=14)
                plt.title(f"{gene_name} Expression", fontsize=28, fontweight='bold')
                plt.xlabel("UMAP1", fontsize=14)
                plt.ylabel("UMAP2", fontsize=14)
                plt.tick_params(axis='both', labelsize=18)
                plt.tight_layout()
                plt.savefig(umap_png, dpi=DPI, bbox_inches="tight")
                plt.savefig(umap_pdf, dpi=DPI, bbox_inches="tight")
                plt.close()
        
        for group in self.valid_groups:
            violin_png = os.path.join(gene_dir, f"{gene_name}_Violin_{group}.png")
            if os.path.exists(violin_png):
                continue
            df_plot = pd.DataFrame({"x": self.adata.obs[group], "y": expr_vals})
            plt.figure(figsize=(14, 6))
            sns.violinplot(x="x", y="y", data=df_plot)
            plt.xticks(rotation=90)
            plt.title(f"{gene_name} | {group}")
            plt.tight_layout()
            plt.savefig(violin_png, dpi=DPI, bbox_inches="tight")
            plt.close()
    
    def query_gene(self, gene_name):
        if not gene_name:
            return False, None, "请输入基因名"

        if self.adata is None:
            return False, None, "请先加载数据"

        try:
            self.get_gene_expression(gene_name)
        except ValueError:
            return False, None, f"基因 {gene_name} 不存在"

        self.current_gene = gene_name

        try:
            self.run_gene_full_plot(gene_name)
            image_path, err = self._get_expr_umap_path()
            if err:
                return False, None, err
            return True, image_path, ""
        except Exception as e:
            traceback.print_exc()
            return False, None, f"分析失败: {str(e)}"

    def _get_expr_umap_path(self):
        if not self.current_gene:
            return None, "请先输入基因名"
        gene_dir = os.path.join(self.dataset_output_dir, self.current_gene)
        umap_png = os.path.join(gene_dir, f"{self.current_gene}_UMAP_EXPR.png")
        if not os.path.exists(umap_png):
            self.run_gene_full_plot(self.current_gene)
        if os.path.exists(umap_png):
            return umap_png, ""
        return None, "表达量UMAP图生成失败"

    def _get_violin_path(self, group):
        if not self.current_gene:
            return None, "请先输入基因名"
        gene_dir = os.path.join(self.dataset_output_dir, self.current_gene)
        violin_png = os.path.join(gene_dir, f"{self.current_gene}_Violin_{group}.png")
        if not os.path.exists(violin_png):
            self.run_gene_full_plot(self.current_gene)
        if os.path.exists(violin_png):
            return violin_png, ""
        return None, f"小提琴图生成失败: {group}"

    def _get_anno_umap_path(self, group):
        if self.adata is None:
            return None, "请先加载数据"
        if not self.static_umap_dir:
            return None, "静态UMAP目录未创建"
        if group not in self.adata.obs.columns:
            return None, f"注释类型 '{group}' 不存在"

        png_path = os.path.join(self.static_umap_dir, f"UMAP_{group}.png")
        if os.path.exists(png_path):
            return png_path, ""

        try:
            plt.figure(figsize=(10, 8))
            for cat in self.adata.obs[group].unique():
                idx = self.adata.obs[group] == cat
                plt.scatter(self.adata.obsm[self.umap_key][idx, 0],
                           self.adata.obsm[self.umap_key][idx, 1],
                           s=0.1, label=cat)
            plt.legend(markerscale=10, fontsize=6, bbox_to_anchor=(1.05, 1))
            plt.title(f"UMAP {group}")
            plt.tight_layout()
            plt.savefig(png_path, dpi=DPI, bbox_inches="tight")
            plt.close()

            if os.path.exists(png_path):
                return png_path, ""
            return None, "UMAP图生成失败"
        except Exception as e:
            traceback.print_exc()
            return None, f"显示UMAP失败: {str(e)}"
    
    def draw_static_umap_all(self):
        for group in self.valid_groups:
            png_path = os.path.join(self.static_umap_dir, f"UMAP_{group}.png")
            pdf_path = os.path.join(self.static_umap_dir, f"UMAP_{group}.pdf")
            if os.path.exists(png_path) and os.path.exists(pdf_path):
                continue
            
            plt.figure(figsize=(10, 6.5))
            for cat in self.adata.obs[group].unique():
                idx = self.adata.obs[group] == cat
                plt.scatter(self.adata.obsm[self.umap_key][idx, 0],
                           self.adata.obsm[self.umap_key][idx, 1],
                           s=1.5, label=cat)
            plt.legend(markerscale=10, fontsize=18, bbox_to_anchor=(1.05, 1))
            plt.title(f"UMAP {group}", fontsize=28, fontweight='bold')
            plt.xlabel("UMAP1", fontsize=14)
            plt.ylabel("UMAP2", fontsize=14)
            plt.tick_params(axis='both', labelsize=18)
            plt.tight_layout()
            plt.savefig(png_path, dpi=DPI, bbox_inches="tight")
            plt.savefig(pdf_path, dpi=DPI, bbox_inches="tight")
            plt.close()
    
    def get_export_default_name(self, source_text, plot_text, ext):
        dataset_name = self.dataset_name.replace('.h5ad', '') if self.dataset_name else ""
        name_parts = [part for part in [dataset_name, source_text, plot_text] if part]
        default_name = "_".join(name_parts) if name_parts else "plot"
        return f"{default_name}.{ext}"

    def get_export_pdf_path(self, source_text, plot_text):
        if source_text == "基因表达量":
            if plot_text == "表达量UMAP" and self.current_gene:
                gene_dir = os.path.join(self.dataset_output_dir, self.current_gene)
                return os.path.join(gene_dir, f"{self.current_gene}_UMAP_EXPR.pdf")
            elif self.current_gene:
                gene_dir = os.path.join(self.dataset_output_dir, self.current_gene)
                return os.path.join(gene_dir, f"{self.current_gene}_Violin_{plot_text}.pdf")
        elif plot_text and self.static_umap_dir:
            return os.path.join(self.static_umap_dir, f"UMAP_{plot_text}.pdf")
        return None

    def save_pixmap_as_png(self, pixmap, save_path):
        if not save_path.endswith('.png'):
            save_path += '.png'
        return pixmap.save(save_path)

    def copy_or_convert_to_pdf(self, pixmap, source_text, plot_text, save_path):
        if not save_path.endswith('.pdf'):
            save_path += '.pdf'

        pdf_path = self.get_export_pdf_path(source_text, plot_text)
        if pdf_path and os.path.exists(pdf_path):
            import shutil
            shutil.copy2(pdf_path, save_path)
            return True

        qimage = pixmap.toImage()
        qimage.save(save_path)
        return True

__all__ = ['ScUmapInitialPyAnalysis']