# -*- coding: utf-8 -*-
"""
scRNAseq Monocle数据加载类子层 - 分析算法层
负责：1) 扫描pseudo_rds_data目录；2) 调用R脚本生成带轨迹的伪时间测试图
"""

import os
import subprocess
import traceback
import ctypes

from script.utils_layer.import_config import APPDATA_PATH, OUT_BASE
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class ScMonocleLoadingAnalysis:
    """Monocle数据加载类分析算法"""

    def __init__(self):
        self.cds_rds_path = None  # 用户选中的CDS rds文件路径
        self.dataset_name = None  # 数据集名称（基于rds文件名）
        self._r_script_path = os.path.join(os.path.dirname(__file__), 'run_monocle_loading.R')
        self._r_interface = get_r_kernel_interface()
        self._rscript_path = self._get_rscript_path()

    def _get_rscript_path(self):
        r_path = self._r_interface.get_r_path()
        if r_path:
            return os.path.join(r_path, "bin", "Rscript.exe")
        return r"A:\TOOLS\R\R-4.6.1\bin\Rscript.exe"

    def _get_short_path(self, path):
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetShortPathNameW(path, buf, 260)
            return buf.value
        except Exception:
            return path

    def _get_pseudo_rds_folder(self):
        """获取伪时间rds扫描目录：appdata/analyze_data/pseudo_rds_data"""
        return os.path.join(APPDATA_PATH, "analyze_data", "pseudo_rds_data")

    def _get_loading_test_output_dir(self):
        """获取测试图输出目录：OUTPUT/monocle3/loading_test/{dataset_name}/"""
        if not self.dataset_name:
            raise ValueError("dataset_name未设置")
        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(os.path.abspath(__file__))
                        )
                    )
                )
            )
        )
        output_dir = os.path.join(project_root, "OUTPUT", "monocle3", "loading_test", self.dataset_name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def scan_pseudo_rds_folder(self):
        """扫描pseudo_rds_data目录，返回rds文件列表
        返回: (success, rds_files, error_msg)
        """
        folder_path = self._get_pseudo_rds_folder()
        if not os.path.exists(folder_path):
            return False, [], f"扫描路径不存在: {folder_path}"

        rds_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.rds')])
        if not rds_files:
            return False, [], f"{folder_path} 中没有找到rds文件"

        return True, rds_files, ""

    def generate_test_plot(self, selected_file):
        """加载CDS rds并生成带轨迹的伪时间测试图
        返回: (success, png_path_or_error, is_error)
        """
        folder_path = self._get_pseudo_rds_folder()
        rds_path = os.path.join(folder_path, selected_file)

        if not os.path.exists(rds_path):
            return False, f"rds文件不存在: {rds_path}", True

        # 基于文件名设置dataset_name（去掉.rds扩展名）
        self.dataset_name = os.path.splitext(selected_file)[0]
        self.cds_rds_path = rds_path

        try:
            output_dir = self._get_loading_test_output_dir()
        except ValueError as e:
            return False, str(e), True

        try:
            print(f"[MonocleLoading] 正在生成测试图: {selected_file}")
            stdout, stderr = self._run_r_script([
                rds_path,
                output_dir,
                self.dataset_name
            ])

            if stdout and "ERROR" not in stdout:
                # 从输出中解析PNG路径
                png_path = self._parse_png_path(stdout)
                if png_path and os.path.exists(png_path):
                    print(f"[MonocleLoading] 测试图生成完成: {png_path}")
                    return True, png_path, False
                # 如果没解析到路径但R成功，按约定路径返回
                expected_png = os.path.join(output_dir, f"{self.dataset_name}_pseudotime_test.png")
                if os.path.exists(expected_png):
                    return True, expected_png, False
                return False, f"R脚本执行完成但未找到PNG文件\nR输出: {stdout}", True

            error_msg = stderr if stderr else (stdout if stdout else "R脚本执行失败")
            return False, error_msg, True

        except Exception as e:
            print(f"[MonocleLoading] 生成测试图异常: {e}")
            traceback.print_exc()
            return False, str(e), True

    def _run_r_script(self, args):
        """调用R脚本"""
        try:
            short_args = []
            for arg in args:
                if isinstance(arg, str) and ('\\' in arg or '/' in arg):
                    short_path = self._get_short_path(arg)
                    short_args.append(short_path if short_path else arg)
                else:
                    short_args.append(arg)

            cmd = [self._rscript_path, self._get_short_path(self._r_script_path)] + short_args

            result = subprocess.run(cmd, capture_output=True, text=False, timeout=600)

            stdout = result.stdout.decode('utf-8', errors='ignore').strip() if result.stdout else ""
            stderr = result.stderr.decode('utf-8', errors='ignore').strip() if result.stderr else ""

            if result.returncode != 0:
                print(f"R脚本执行失败: {stderr}")
                return None, stderr

            return stdout, None
        except subprocess.TimeoutExpired:
            return None, "R脚本执行超时"
        except Exception as e:
            print(f"调用R脚本异常: {e}")
            traceback.print_exc()
            return None, str(e)

    def _parse_png_path(self, stdout):
        """从R脚本输出中解析PNG文件路径"""
        for line in stdout.split('\n'):
            line = line.strip()
            if line.endswith('.png') and os.path.exists(line):
                return line
            # 尝试匹配 "Pseudotime测试图已保存: <path>" 行
            if '测试图已保存' in line and '.png' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    path = parts[1].strip()
                    if os.path.exists(path):
                        return path
        return None
