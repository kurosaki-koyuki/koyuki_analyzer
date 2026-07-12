# -*- coding: utf-8 -*-
"""
运行库配置脚本 - 集中管理所有导入和配置
"""

# ========================================
# 标准库导入
# ========================================
import os
import sys
import traceback
import tempfile
import shutil
import importlib
import uuid
import itertools
import random

# ========================================
# 路径配置（必须在第三方库导入之前定义，因为mod_manager会立即使用）
# ========================================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_ROOT = BASE_DIR
OUT_BASE = os.path.join(OUTPUT_ROOT, "OUTPUT")
os.makedirs(OUT_BASE, exist_ok=True)

def _find_appdata_path():
    """查找appdata目录的正确路径，支持多种打包布局"""
    candidates = [
        os.path.join(BASE_DIR, "appdata"),
        os.path.join(BASE_DIR, "_internal", "appdata"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return os.path.join(BASE_DIR, "appdata")

APPDATA_PATH = _find_appdata_path()
DATA_PATH = os.path.join(APPDATA_PATH, "main", "GSE223065.h5ad")
SCAN_DATA_PATH = os.path.join(APPDATA_PATH, "main")
BULK_SCAN_DATA_PATH = os.path.join(APPDATA_PATH, "bulk_main")

# ========================================
# 第三方库导入
# ========================================
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.stats import mannwhitneyu
from scipy.sparse import issparse

import importlib.metadata
original_version = importlib.metadata.version
def mock_version(package):
    try:
        return original_version(package)
    except importlib.metadata.PackageNotFoundError:
        if package == 'scipy':
            return '1.14.0'
        elif package == 'scanpy':
            return '1.10.0'
        elif package == 'anndata':
            return '0.10.0'
        elif package == 'pandas':
            return '2.2.0'
        elif package == 'numpy':
            return '1.26.0'
        elif package == 'matplotlib':
            return '3.8.0'
        elif package == 'scikit-learn':
            return '1.4.0'
        elif package == 'scikit-image':
            return '0.22.0'
        elif package == 'leidenalg':
            return '0.10.0'
        elif package == 'igraph':
            return '0.11.0'
        elif package == 'networkx':
            return '3.2.0'
        elif package == 'numba':
            return '0.59.0'
        elif package == 'tqdm':
            return '4.66.0'
        elif package == 'joblib':
            return '1.3.0'
        elif package == 'natsort':
            return '8.4.0'
        elif package == 'packaging':
            return '24.0'
        elif package == 'h5py':
            return '3.10.0'
        elif package == 'pynndescent':
            return '0.5.12'
        elif package == 'python-igraph':
            return '0.11.0'
        elif package == 'session-info':
            return '1.0.0'
        elif package == 'setuptools':
            return '69.0.0'
        else:
            print(f"[WARNING] Missing package metadata for: {package}, returning '0.0.0'")
            return '0.0.0'
importlib.metadata.version = mock_version

import inspect
original_getsource = inspect.getsource
original_getsourcelines = inspect.getsourcelines
def mock_getsource(obj):
    try:
        return original_getsource(obj)
    except OSError:
        return ""
def mock_getsourcelines(obj):
    try:
        return original_getsourcelines(obj)
    except OSError:
        return ([], 1)
inspect.getsource = mock_getsource
inspect.getsourcelines = mock_getsourcelines

import scanpy as sc
import anndata
import h5py

# 初始化 pygame 用于音乐播放
import pygame
pygame.mixer.init()

# 设置matplotlib后端（必须在matplotlib.pyplot之前）
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

import cv2
from PIL import Image

# ========================================
# R语言支持（rpy2）
# ========================================
# rpy2导入采用安全模式，避免在没有安装rpy2或R环境时崩溃
RPY2_AVAILABLE = False
rpy2 = None
robjects = None
pandas2ri = None
importr = None

def _ensure_rpy2_environment():
    """
    确保R环境变量正确设置后再导入rpy2
    在Windows上，rpy2需要正确的R_HOME和PATH才能正常工作
    """
    # 设置Python编码为UTF-8，避免Windows GBK编码问题
    import sys
    if sys.stdout is not None and sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    elif sys.stdout is None:
        import io
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['LC_ALL'] = 'C'  # 避免R输出编码问题
    
    # 无论R_HOME是否已设置，都要确保R_USER和PATH等环境变量正确
    # 设置R_USER（用于R的个人文件夹）
    r_user = os.path.expanduser("~")
    os.environ["R_USER"] = r_user
    os.environ["R_LIBS_USER"] = os.path.join(r_user, "R", "library")
    
    # 如果已经设置过R_HOME且路径有效，确保PATH也正确设置
    r_home = os.environ.get('R_HOME')
    if r_home and os.path.exists(r_home):
        # 确保R的bin/x64目录在PATH最前面
        r_bin = os.path.join(r_home, "bin")
        r_bin_x64 = os.path.join(r_home, "bin", "x64")
        current_path = os.environ.get("PATH", "")
        # 把R目录放最前面，其余保留
        path_parts = current_path.split(os.pathsep)
        non_r_parts = [p for p in path_parts if p and 'R-4' not in p and 'R-3' not in p and '\\R\\' not in p and '/R/' not in p]
        new_path_parts = [r_bin_x64, r_bin] + non_r_parts
        os.environ["PATH"] = os.pathsep.join(new_path_parts)
        return
    
    # 尝试从配置文件加载R路径
    r_path = None
    try:
        # 尝试从 start.py 同级目录的 appdata 中读取
        start_dir = os.path.dirname(os.path.abspath(__file__))
        # 向上两级到项目根目录
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(start_dir)))
        config_path = os.path.join(base_dir, "appdata", "mods", "kurosaki_koyuki", "config", "r_kernel_config.txt")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                r_path = f.read().strip()
            if r_path and os.path.exists(r_path):
                os.environ["R_HOME"] = r_path
                print(f"[rpy2环境] 从配置文件加载R_HOME: {r_path}")
    except Exception as e:
        print(f"[rpy2环境] 读取R配置失败: {e}")
    
    # 如果还是没有R_HOME，尝试自动检测
    if not os.environ.get('R_HOME'):
        common_paths = [
            os.path.join(os.environ.get("ProgramFiles", "C:/Program Files"), "R"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"), "R"),
            "A:/TOOLS/R",
        ]
        for base_path in common_paths:
            if os.path.exists(base_path):
                try:
                    # 只匹配 R-x.x.x 格式的目录（如 R-4.6.1），不匹配 Rstudio 等
                    r_dirs = [d for d in os.listdir(base_path) if d.startswith("R-") and os.path.isdir(os.path.join(base_path, d))]
                    if r_dirs:
                        r_dirs.sort(reverse=True)
                        r_path = os.path.join(base_path, r_dirs[0])
                        os.environ["R_HOME"] = r_path
                        print(f"[rpy2环境] 自动检测到R_HOME: {r_path}")
                        break
                except:
                    pass
    
    # 设置PATH包含R的bin目录（放最前面）
    r_home = os.environ.get('R_HOME')
    if r_home:
        r_bin = os.path.join(r_home, "bin")
        r_bin_x64 = os.path.join(r_home, "bin", "x64")
        current_path = os.environ.get("PATH", "")
        # 重新排序PATH，把R目录放最前面
        path_parts = current_path.split(os.pathsep)
        non_r_parts = [p for p in path_parts if p and 'R-4' not in p and 'R-3' not in p and '\\R\\' not in p and '/R/' not in p]
        new_path_parts = [r_bin_x64, r_bin] + non_r_parts
        os.environ["PATH"] = os.pathsep.join(new_path_parts)
        # 设置R_USER和R_LIBS_USER
        r_user = os.path.expanduser("~")
        os.environ["R_USER"] = r_user
        os.environ["R_LIBS_USER"] = os.path.join(r_user, "R", "library")

# 先确保环境变量正确，再导入rpy2
_ensure_rpy2_environment()

try:
    import rpy2
    import rpy2.robjects as robjects
    from rpy2.robjects import pandas2ri
    from rpy2.robjects.packages import importr
    RPY2_AVAILABLE = True
    print(f"[rpy2导入] 成功导入rpy2模块")
    print(f"[rpy2导入] R_HOME={os.environ.get('R_HOME', 'NOT SET')}")
    print(f"[rpy2导入] PATH包含R: {'R' in os.environ.get('PATH', '')}")
except (ImportError, UnicodeDecodeError, Exception) as e:
    print(f"[rpy2导入] 导入失败: {e}")
    import traceback
    traceback.print_exc()
    RPY2_AVAILABLE = False

# ========================================
# PyQt5 相关导入
# ========================================
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QComboBox, QTextEdit, QMessageBox, QStackedWidget, QSlider,
                             QSizePolicy, QListWidget, QListWidgetItem, QCheckBox, QFrame,
                             QGroupBox, QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem,
                             QTabWidget, QFileDialog, QShortcut, QHeaderView, QAbstractItemView,
                             QScrollArea, QDialog, QGridLayout)
from PyQt5.QtGui import QFont, QPixmap, QIcon, QImage, QColor, QKeySequence, QPainter
from PyQt5.QtCore import Qt, QSize, QTimer, QObject, QEvent, QPoint, pyqtSignal

def get_r_script_path(caller_file, r_script_name):
    """
    动态获取R脚本路径，支持开发模式和打包模式
    
    Args:
        caller_file: __file__（调用者的文件路径）
        r_script_name: R脚本文件名（如 "bulk_km_r.R"）
    
    Returns:
        R脚本的完整路径
    """
    if getattr(sys, 'frozen', False):
        script_dir = os.path.join(BASE_DIR, "script")
        caller_dir_relative = os.path.dirname(os.path.relpath(caller_file, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        r_script_path = os.path.join(script_dir, caller_dir_relative, r_script_name)
        if os.path.exists(r_script_path):
            return r_script_path
        return os.path.join(BASE_DIR, "script", r_script_name)
    else:
        return os.path.join(os.path.dirname(caller_file), r_script_name)

DPI = 150



# ========================================
# 导出常用变量和函数
# ========================================
__all__ = [
    # 标准库
    'os', 'sys', 'traceback', 'tempfile', 'shutil', 'importlib', 'uuid', 'itertools', 'random',
    # 数据处理
    'np', 'pd', 'sns', 'stats', 'mannwhitneyu', 'issparse',
    # 图形和多媒体
    'pygame', 'matplotlib', 'plt', 'gridspec', 'FigureCanvas', 'cv2', 'Image',
    # R语言支持
    'rpy2', 'robjects', 'pandas2ri', 'importr', 'RPY2_AVAILABLE',
    # PyQt5
    'QApplication', 'QMainWindow', 'QWidget', 'QVBoxLayout',
    'QHBoxLayout', 'QPushButton', 'QLabel', 'QLineEdit',
    'QComboBox', 'QTextEdit', 'QMessageBox', 'QStackedWidget', 'QSlider',
    'QSizePolicy', 'QListWidget', 'QListWidgetItem', 'QCheckBox', 'QFrame',
    'QGroupBox', 'QDoubleSpinBox', 'QSpinBox', 'QTableWidget', 'QTableWidgetItem',
    'QTabWidget', 'QFileDialog', 'QShortcut', 'QHeaderView', 'QAbstractItemView',
    'QScrollArea', 'QDialog', 'QGridLayout', 'QFont', 'QPixmap', 'QIcon', 'QImage', 'QColor', 'QKeySequence', 'QPainter',
    'Qt', 'QSize', 'QTimer', 'QObject', 'QEvent', 'QPoint', 'pyqtSignal',
    # 路径配置
    'BASE_DIR', 'OUTPUT_ROOT', 'OUT_BASE', 'DATA_PATH', 'APPDATA_PATH', 'get_r_script_path',
    'SCAN_DATA_PATH', 'BULK_SCAN_DATA_PATH', 'DPI'
]