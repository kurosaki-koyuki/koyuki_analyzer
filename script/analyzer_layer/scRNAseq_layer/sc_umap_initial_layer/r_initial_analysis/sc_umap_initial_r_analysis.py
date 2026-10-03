# -*- coding: utf-8 -*-
"""
UMAP初步作图R版本核心算法脚本
使用subprocess调用R脚本，绕过rpy2崩溃问题
"""

import os
import sys
import subprocess
import traceback


class ScUmapInitialRAnalysis:
    def __init__(self):
        self.seurat_path = None
        self.dataset_name = None
        self.dataset_output_dir = None
        self.metadata_columns = []
        self._r_script_path = os.path.join(os.path.dirname(__file__), 'run_umap_plots.R')

    def _run_r_script(self, args):
        try:
            cmd = ['Rscript', self._r_script_path] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                print(f"R脚本执行失败: {result.stderr}")
                return None, result.stderr
            
            return result.stdout.strip(), None
        except subprocess.TimeoutExpired:
            return None, "R脚本执行超时"
        except Exception as e:
            print(f"调用R脚本异常: {e}")
            traceback.print_exc()
            return None, str(e)

    def set_seurat_path(self, seurat_path):
        self.seurat_path = seurat_path

    def set_dataset_name(self, dataset_name):
        self.dataset_name = dataset_name

    def set_dataset_output_dir(self, dataset_output_dir):
        self.dataset_output_dir = dataset_output_dir

    def get_seurat_info(self):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return None
        
        output_dir = os.path.join(self.dataset_output_dir, "_r_umap_annotations") if self.dataset_output_dir else "."
        
        stdout, stderr = self._run_r_script([
            self.seurat_path,
            output_dir,
            self.dataset_name,
            "info"
        ])
        
        if stdout:
            parts = stdout.split("\t")
            if len(parts) >= 3:
                return {
                    'cells': int(parts[0]),
                    'genes': int(parts[1]),
                    'has_umap': parts[2] == "TRUE",
                    'dataset': self.dataset_name
                }
        
        return None

    def get_metadata_columns(self):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return []
        
        output_dir = os.path.join(self.dataset_output_dir, "_r_umap_annotations") if self.dataset_output_dir else "."
        
        stdout, stderr = self._run_r_script([
            self.seurat_path,
            output_dir,
            self.dataset_name,
            "metadata"
        ])
        
        if stdout:
            self.metadata_columns = [col for col in stdout.split("\t") if col.strip()]
            return self.metadata_columns
        
        return []

    def get_available_genes(self):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return []
        
        output_dir = os.path.join(self.dataset_output_dir, "_r_umap_expression") if self.dataset_output_dir else "."
        
        stdout, stderr = self._run_r_script([
            self.seurat_path,
            output_dir,
            self.dataset_name,
            "genes"
        ])
        
        if stdout:
            return [gene for gene in stdout.split("\t") if gene.strip()]
        
        return []

    def generate_all_annotation_plots(self):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return False, "Seurat对象路径不存在"
        
        if not self.dataset_output_dir:
            return False, "输出目录未设置"
        
        output_dir = os.path.join(self.dataset_output_dir, "_r_umap_annotations")
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            print("[R-UMAP] 正在绘制Cluster分群图...")
            stdout, stderr = self._run_r_script([
                self.seurat_path,
                output_dir,
                self.dataset_name,
                "annotation",
                "seurat_clusters"
            ])
            if stdout:
                print(f"[R-UMAP] Cluster图已保存: {stdout}")
            else:
                print(f"[R-UMAP] Cluster图绘制失败: {stderr}")
            
            columns = self.get_metadata_columns()
            annotation_cols = [col for col in columns if col != 'seurat_clusters']
            
            for col in annotation_cols:
                try:
                    print(f"[R-UMAP] 正在绘制 {col} 分群图...")
                    stdout, stderr = self._run_r_script([
                        self.seurat_path,
                        output_dir,
                        self.dataset_name,
                        "annotation",
                        col
                    ])
                    if stdout and stdout != "SKIP_CONTINUOUS":
                        print(f"[R-UMAP] {col}图已保存: {stdout}")
                    elif stdout == "SKIP_CONTINUOUS":
                        print(f"[R-UMAP] 跳过连续值列 {col}")
                    else:
                        print(f"[R-UMAP] {col}图绘制失败: {stderr}")
                except Exception as e:
                    print(f"[R-UMAP] 绘制 {col} 失败: {e}")
                    continue
            
            return True, output_dir
        except Exception as e:
            print(f"生成注释图失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def get_annotation_plot_path(self, annotation_col):
        if not self.dataset_output_dir:
            return None
        
        output_dir = os.path.join(self.dataset_output_dir, "_r_umap_annotations")
        
        if annotation_col == 'seurat_clusters':
            png_path = os.path.join(output_dir, f"{self.dataset_name}_Clusters_adv.png")
        else:
            annotation_name = annotation_col.replace(' ', '_').replace('(', '_').replace(')', '_')
            png_path = os.path.join(output_dir, f"{self.dataset_name}_{annotation_name}_adv.png")
        
        if os.path.exists(png_path):
            return png_path
        return None

    def generate_expression_plots(self, genes):
        if not self.seurat_path or not os.path.exists(self.seurat_path):
            return False, "Seurat对象路径不存在"
        
        if not self.dataset_output_dir:
            return False, "输出目录未设置"
        
        if not genes or len(genes) == 0:
            return False, "请输入基因名"
        
        output_dir = os.path.join(self.dataset_output_dir, "_r_umap_expression")
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            result_paths = []
            
            for gene in genes:
                try:
                    print(f"[R-UMAP] 正在绘制 {gene} 表达量图...")
                    stdout, stderr = self._run_r_script([
                        self.seurat_path,
                        output_dir,
                        self.dataset_name,
                        "expression",
                        gene
                    ])
                    if stdout:
                        result_paths.append(stdout)
                        print(f"[R-UMAP] {gene}表达量图已保存: {stdout}")
                    else:
                        print(f"[R-UMAP] {gene}表达量图绘制失败: {stderr}")
                except Exception as e:
                    print(f"[R-UMAP] 绘制 {gene} 失败: {e}")
                    continue
            
            if len(result_paths) == 0:
                return False, "所有基因绘制失败"
            
            return True, result_paths
        except Exception as e:
            print(f"生成表达量图失败: {e}")
            traceback.print_exc()
            return False, str(e)

    def get_expression_plot_path(self, gene):
        if not self.dataset_output_dir:
            return None
        
        output_dir = os.path.join(self.dataset_output_dir, "_r_umap_expression")
        gene_name = gene.replace(' ', '_').replace('(', '_').replace(')', '_').replace('-', '_')
        png_path = os.path.join(output_dir, f"{self.dataset_name}_{gene_name}_expression.png")
        
        if os.path.exists(png_path):
            return png_path
        return None


__all__ = ['ScUmapInitialRAnalysis']