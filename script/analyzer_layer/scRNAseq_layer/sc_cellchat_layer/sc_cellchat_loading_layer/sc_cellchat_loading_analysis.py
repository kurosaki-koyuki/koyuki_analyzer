# -*- coding: utf-8 -*-
"""
CellChat数据加载类分析层
负责调用R脚本从CellChat RDS重新生成可视化图表
并保存加载的数据状态，供其他子层使用
"""

import os
import subprocess
import sys


class ScCellChatLoadingAnalysis:
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self._dataset_name = None
        self._output_dir = None
        self._rds_path = None
        self._is_loaded = False  # 标记数据是否已加载
        
        # 保存生成的文件路径，供其他子层使用
        self._files = {
            'count': None,
            'weight': None,
            'info': None
        }
    
    # ========== 数据状态访问接口（供其他子层使用）==========
    
    @property
    def is_loaded(self):
        """数据是否已加载"""
        return self._is_loaded
    
    @property
    def dataset_name(self):
        """数据集名称"""
        return self._dataset_name
    
    @property
    def output_dir(self):
        """输出目录"""
        return self._output_dir
    
    @property
    def rds_path(self):
        """RDS文件路径"""
        return self._rds_path
    
    @property
    def files(self):
        """生成的文件路径"""
        return self._files
    
    def get_file_paths(self):
        """获取所有生成的文件路径"""
        return {
            'count': self._files.get('count'),
            'weight': self._files.get('weight'),
            'info': self._files.get('info')
        }
    
    # ========== 核心方法 ==========
    
    def _get_script_dir(self):
        """获取R脚本所在目录"""
        return os.path.dirname(os.path.abspath(__file__))
    
    def _get_output_dir(self):
        """获取输出目录"""
        if self._output_dir:
            return self._output_dir
        # 默认使用OUTPUT/cellchat目录
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        output_dir = os.path.join(base_dir, "OUTPUT", "cellchat", self._dataset_name or "default")
        return output_dir
    
    def visualize_from_rds(self, rds_path, output_dir=None):
        """从CellChat RDS文件重新生成可视化"""
        self._rds_path = rds_path
        self._dataset_name = os.path.splitext(os.path.basename(rds_path))[0]
        # 如果文件名包含_cellchat，去掉它
        if self._dataset_name.endswith('_cellchat'):
            self._dataset_name = self._dataset_name[:-9]
        
        self._output_dir = output_dir or self._get_output_dir()
        
        # 确保输出目录存在
        os.makedirs(self._output_dir, exist_ok=True)
        
        # R脚本路径
        script_path = os.path.join(self._get_script_dir(), "run_cellchat_load_visualize.R")
        
        # 构建Rscript命令
        cmd = [
            "Rscript",
            script_path,
            rds_path,
            self._output_dir,
            self._dataset_name
        ]
        
        try:
            # 运行R脚本
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"R脚本执行失败:\n{error_msg}")
            
            # 检查输出文件是否生成
            count_img = os.path.join(self._output_dir, f"{self._dataset_name}_cellchat_count.png")
            weight_img = os.path.join(self._output_dir, f"{self._dataset_name}_cellchat_weight.png")
            info_csv = os.path.join(self._output_dir, "pathway_info.csv")
            
            # 更新保存的文件路径
            self._files = {
                'count': count_img if os.path.exists(count_img) else None,
                'weight': weight_img if os.path.exists(weight_img) else None,
                'info': info_csv if os.path.exists(info_csv) else None
            }
            
            # 标记数据已加载
            self._is_loaded = True
            
            return {
                'success': True,
                'output_dir': self._output_dir,
                'dataset_name': self._dataset_name,
                'files': self._files,
                'stdout': result.stdout
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': "R脚本执行超时（超过5分钟）"
            }
        except Exception as e:
            self._is_loaded = False
            return {
                'success': False,
                'error': str(e)
            }
