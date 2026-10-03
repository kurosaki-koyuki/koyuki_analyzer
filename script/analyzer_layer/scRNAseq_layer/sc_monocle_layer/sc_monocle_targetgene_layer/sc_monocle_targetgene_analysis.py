# -*- coding: utf-8 -*-
"""
scRNAseq Monocle目的基因分析子层Analysis脚本
负责调用R脚本绘制目的基因的伪时间趋势图
"""

import os
import subprocess
import time
import pandas as pd


class ScMonocleTargetgeneAnalysis:
    def __init__(self):
        self._r_stage_script_path = os.path.join(os.path.dirname(__file__), 'run_monocle_targetgene_pseudotime.R')
        self._r_interface = None
        self._rscript_path = None
        
        self.cds_rds_path = None
        self.dataset_name = None
        
        self._cached_plot_path = None
        
        self._init_r_interface()

    def _init_r_interface(self):
        """初始化R接口"""
        try:
            from script.utils_layer.r_kernel_interface import get_r_kernel_interface
            self._r_interface = get_r_kernel_interface()
            self._rscript_path = self._get_rscript_path()
        except Exception as e:
            print(f"初始化R接口失败: {e}")
            self._rscript_path = r"A:\TOOLS\R\R-4.6.1\bin\Rscript.exe"

    def _get_rscript_path(self):
        """获取Rscript路径"""
        if self._r_interface:
            r_path = self._r_interface.get_r_path()
            if r_path:
                return os.path.join(r_path, "bin", "Rscript.exe")
        return r"A:\TOOLS\R\R-4.6.1\bin\Rscript.exe"

    def set_cds_rds_path(self, rds_path, dataset_name):
        """设置CDS RDS路径和数据集名称"""
        self.cds_rds_path = rds_path
        self.dataset_name = dataset_name

    def has_shared_data(self):
        """检查是否有共享数据"""
        return self.cds_rds_path is not None and os.path.exists(self.cds_rds_path)

    def run_pseudotime_plot(self, gene_list, anno_column=None, yaxis_format="count", progress_callback=None):
        """
        运行伪时间趋势图绘制
        
        Args:
            gene_list: 基因名称列表
            anno_column: 注释列名（用于着色分组），默认为None（按伪时间着色）
            yaxis_format: Y轴数据格式（count, log2, normalized），默认为count
            progress_callback: 进度回调函数
            
        Returns:
            (success, result_path, is_error)
        """
        if not self.has_shared_data():
            return False, "请先在数据加载类页面加载CDS RDS文件", True

        if not gene_list or len(gene_list) == 0:
            return False, "请输入至少一个基因名称", True

        genes_str = ",".join(gene_list)
        
        timestamp = int(time.time())
        plot_filename = f"targetgene_pseudotime_{self.dataset_name}_{timestamp}.png"
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = current_dir
        while not os.path.exists(os.path.join(project_root, "OUTPUT")):
            project_root = os.path.dirname(project_root)
            if project_root == os.path.dirname(project_root):
                project_root = os.path.dirname(os.path.dirname(current_dir))
                break
        
        output_path = os.path.join(project_root, "OUTPUT", "monocle3", "targetgene", plot_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        args = [
            self._rscript_path,
            self._r_stage_script_path,
            "--rds", self.cds_rds_path,
            "--genes", genes_str,
            "--output", output_path,
            "--yaxis", yaxis_format
        ]
        
        if anno_column:
            args.extend(["--anno", anno_column])

        if progress_callback:
            progress_callback("正在绘制伪时间趋势图...")

        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            stdout, stderr = process.communicate(timeout=300)
            
            if process.returncode != 0:
                error_msg = f"R脚本执行失败:\n{stderr}" if stderr else "R脚本执行失败"
                return False, error_msg, True

            if os.path.exists(output_path):
                self._cached_plot_path = output_path
                return True, output_path, False
            else:
                return False, "绘图失败，未生成图片", True

        except subprocess.TimeoutExpired:
            process.kill()
            return False, "R脚本执行超时", True
        except Exception as e:
            return False, f"执行R脚本时出错: {str(e)}", True

    def get_cached_plot_path(self):
        """获取缓存的图片路径"""
        return self._cached_plot_path