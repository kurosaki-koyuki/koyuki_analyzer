# -*- coding: utf-8 -*-
"""
R内核接口脚本 - 提供R环境配置和rpy2支持

功能：
- 对外：提供获取R内核路径的接口（供前端输入框使用）
- 对内：为R类分析脚本提供R内核支持

使用方式：
1. 获取R内核路径：r_interface.get_r_path()
2. 设置R内核路径：r_interface.set_r_path(path)
3. 检查R环境是否可用：r_interface.is_r_available()
4. 获取R对象：r_interface.get_robjects()
5. 执行R代码：r_interface.execute_r_code(code)
"""

from script.utils_layer.import_config import os, sys
from typing import Optional, Dict, Any, Callable

# 从import_config导入rpy2相关模块（安全导入）
from script.utils_layer.import_config import (
    rpy2, robjects, pandas2ri, importr, RPY2_AVAILABLE
)


class RKernelInterface:
    """R内核接口类 - 提供对外和对内的R环境支持"""
    
    def __init__(self):
        """初始化R内核接口"""
        self._r_path: Optional[str] = None  # R内核路径（可配置）
        self._r_home: Optional[str] = None  # R_HOME环境变量
        self._is_initialized: bool = False  # 是否已初始化
        self._error_message: str = ""  # 错误信息
        
        # 尝试自动检测R环境
        self._auto_detect_r_environment()
    
    # ========================================
    # 对外接口 - 供前端输入框使用
    # ========================================
    
    def get_r_path(self) -> Optional[str]:
        """
        获取当前配置的R内核路径
        
        对外接口：供前端输入框控件显示当前R路径
        
        Returns:
            str: R内核路径，如果未配置则返回None
        """
        return self._r_path
    
    def set_r_path(self, path: str) -> bool:
        """
        设置R内核路径

        对外接口：供前端输入框控件设置R路径

        Args:
            path: R内核路径（如 "C:/Program Files/R/R-4.3.1"）

        Returns:
            bool: 设置是否成功
        """
        if not os.path.exists(path):
            self._error_message = f"R路径不存在: {path}"
            return False

        # 验证是否为有效的R目录
        bin_dir = os.path.join(path, "bin")
        if not os.path.exists(bin_dir):
            self._error_message = f"路径不是有效的R目录（缺少bin目录）: {path}"
            return False

        # 检查R环境是否已初始化
        if self._is_initialized:
            self._error_message = f"R环境已初始化（当前: {self._r_path}），无法在同一进程中切换R内核。请重启应用以使用新的R路径: {path}"
            print(f"[RKernelInterface] {self._error_message}")
            return False

        # R环境未初始化，可以安全切换
        self._r_path = path
        self._r_home = path

        # 设置R_HOME环境变量（rpy2需要）
        os.environ["R_HOME"] = path

        # 尝试重新初始化rpy2
        self._initialize_rpy2()

        return self._is_initialized
    
    def get_r_path_placeholder(self) -> str:
        """
        获取R路径输入框的占位符文本
        
        对外接口：供前端输入框控件显示提示信息
        
        Returns:
            str: 占位符文本
        """
        if self._r_path:
            return self._r_path
        return "请输入R内核路径（如：C:/Program Files/R/R-4.3.1）"
    
    def get_error_message(self) -> str:
        """
        获取最近的错误信息
        
        对外接口：供前端显示错误信息
        
        Returns:
            str: 错误信息
        """
        return self._error_message
    
    def get_r_version_info(self) -> Dict[str, Any]:
        """
        获取R版本信息
        
        对外接口：供前端显示R版本
        
        Returns:
            dict: 包含R版本信息的字典
        """
        info = {
            "r_path": self._r_path,
            "r_home": self._r_home,
            "rpy2_available": RPY2_AVAILABLE,
            "is_initialized": self._is_initialized,
            "version": None,
            "error": self._error_message
        }
        
        if self._is_initialized and robjects:
            try:
                version = robjects.R('R.version.string')[0]
                info["version"] = version
            except Exception as e:
                info["error"] = str(e)
        
        return info
    
    # ========================================
    # 对内接口 - 供R类分析脚本使用
    # ========================================
    
    def is_r_available(self) -> bool:
        """
        检查R环境是否可用
        
        对内接口：供分析脚本检查R环境
        
        Returns:
            bool: R环境是否可用
        """
        return RPY2_AVAILABLE and self._is_initialized
    
    def get_robjects(self) -> Optional[Any]:
        """
        获取rpy2.robjects对象
        
        对内接口：供分析脚本执行R操作
        
        Returns:
            rpy2.robjects: R对象模块，如果R不可用则返回None
        """
        if not self.is_r_available():
            return None
        return robjects
    
    def get_pandas2ri(self) -> Optional[Any]:
        """
        获取pandas2ri转换器
        
        对内接口：供分析脚本转换pandas DataFrame到R
        
        Returns:
            pandas2ri: pandas转换器，如果R不可用则返回None
        """
        if not self.is_r_available():
            return None
        return pandas2ri
    
    def import_r_package(self, package_name: str) -> Optional[Any]:
        """
        导入R包
        
        对内接口：供分析脚本加载R包
        
        Args:
            package_name: R包名称（如 "survival", "survminer"）
        
        Returns:
            R包对象，如果失败则返回None
        """
        if not self.is_r_available() or importr is None:
            self._error_message = "R环境不可用"
            return None
        
        try:
            r_package = importr(package_name)
            return r_package
        except Exception as e:
            self._error_message = f"导入R包 '{package_name}' 失败: {str(e)}"
            return None
    
    def execute_r_code(self, code: str) -> Optional[Any]:
        """
        执行R代码
        
        对内接口：供分析脚本执行任意R代码
        
        Args:
            code: R代码字符串
        
        Returns:
            执行结果，如果失败则返回None
        """
        if not self.is_r_available() or robjects is None:
            self._error_message = "R环境不可用"
            return None
        
        try:
            result = robjects.R(code)
            return result
        except Exception as e:
            self._error_message = f"执行R代码失败: {str(e)}"
            return None
    
    def convert_dataframe_to_r(self, df) -> Optional[Any]:
        """
        将pandas DataFrame转换为R数据框
        
        对内接口：供分析脚本传递数据到R
        
        Args:
            df: pandas DataFrame
        
        Returns:
            R数据框对象，如果失败则返回None
        """
        if not self.is_r_available() or pandas2ri is None:
            self._error_message = "R环境不可用"
            return None
        
        try:
            with pandas2ri:
                r_dataframe = pandas2ri.py2rpy(df)
            return r_dataframe
        except Exception as e:
            self._error_message = f"转换DataFrame失败: {str(e)}"
            return None
    
    def convert_r_to_dataframe(self, r_df) -> Optional[Any]:
        """
        将R数据框转换为pandas DataFrame
        
        对内接口：供分析脚本从R获取数据
        
        Args:
            r_df: R数据框对象
        
        Returns:
            pandas DataFrame，如果失败则返回None
        """
        if not self.is_r_available() or pandas2ri is None:
            self._error_message = "R环境不可用"
            return None
        
        try:
            with pandas2ri:
                df = pandas2ri.rpy2py(r_df)
            return df
        except Exception as e:
            self._error_message = f"转换R数据框失败: {str(e)}"
            return None
    
    def activate_pandas2ri(self) -> bool:
        """
        激活pandas2ri转换器
        
        对内接口：供分析脚本激活自动转换
        
        Returns:
            bool: 是否成功激活
        """
        if not self.is_r_available() or pandas2ri is None:
            return False
        
        try:
            pandas2ri.activate()
            return True
        except Exception as e:
            self._error_message = f"激活pandas2ri失败: {str(e)}"
            return False
    
    def deactivate_pandas2ri(self) -> bool:
        """
        关闭pandas2ri转换器
        
        对内接口：供分析脚本关闭自动转换
        
        Returns:
            bool: 是否成功关闭
        """
        if not self.is_r_available() or pandas2ri is None:
            return False
        
        try:
            pandas2ri.deactivate()
            return True
        except Exception as e:
            self._error_message = f"关闭pandas2ri失败: {str(e)}"
            return False
    
    # ========================================
    # 内部方法 - 自动检测和初始化
    # ========================================
    
    def _auto_detect_r_environment(self):
        """自动检测系统中的R环境"""
        # 首先检查rpy2是否可用
        if not RPY2_AVAILABLE:
            self._error_message = "rpy2库未安装，请先安装: pip install rpy2"
            return

        # 尝试从环境变量获取R_HOME
        self._r_home = os.environ.get("R_HOME", None)

        # 如果没有设置R_HOME，尝试从配置文件加载保存的路径
        if not self._r_home:
            saved_path = self._load_saved_r_path()
            if saved_path and os.path.exists(saved_path):
                self._r_home = saved_path
                self._r_path = saved_path
                os.environ["R_HOME"] = self._r_home

        # 如果还是没有，尝试自动检测
        if not self._r_home:
            self._detect_r_home()

        # 尝试初始化rpy2
        self._initialize_rpy2()

    def _load_saved_r_path(self) -> Optional[str]:
        """从配置文件加载保存的R路径"""
        try:
            # 动态获取mod路径，与settings界面保持一致
            import sys
            import importlib
            
            # 直接使用BASE_DIR常量
            from script.utils_layer.import_config import BASE_DIR
            mod_base = os.path.join(BASE_DIR, "appdata", "mods", "kurosaki_koyuki")

            if not mod_base:
                return None

            config_file = os.path.join(mod_base, "config", "r_kernel_config.txt")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_path = f.read().strip()
                print(f"从配置文件加载R路径: {saved_path}")
                return saved_path
        except Exception as e:
            print(f"加载R配置失败: {e}")
        return None
    
    def _detect_r_home(self):
        """自动检测R_HOME路径"""
        # Windows常见R安装路径
        common_paths = [
            os.environ.get("ProgramFiles", "C:/Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"),
        ]
        
        for base_path in common_paths:
            if not os.path.exists(base_path):
                continue
            
            # 查找R目录
            r_dirs = [d for d in os.listdir(base_path) if d.startswith("R") and os.path.isdir(os.path.join(base_path, d))]
            
            if r_dirs:
                # 选择最新版本
                r_dirs.sort(reverse=True)
                self._r_home = os.path.join(base_path, r_dirs[0])
                self._r_path = self._r_home
                
                # 设置环境变量
                os.environ["R_HOME"] = self._r_home
                break
    
    def _initialize_rpy2(self) -> bool:
        """初始化rpy2连接"""
        print(f"[_initialize_rpy2] RPY2_AVAILABLE={RPY2_AVAILABLE}, robjects is None={robjects is None}")
        print(f"[_initialize_rpy2] R_HOME={os.environ.get('R_HOME', 'NOT SET')}")

        if not RPY2_AVAILABLE or robjects is None:
            print(f"[_initialize_rpy2] rpy2不可用，跳过初始化")
            return False

        try:
            # 在Windows上，可能需要设置额外的环境变量
            r_home = self._r_home or os.environ.get('R_HOME')
            if r_home:
                # 设置R_USER（用于R的个人文件夹）
                r_user = os.path.expanduser("~")
                os.environ["R_USER"] = r_user
                # 设置R_LIBS_USER
                os.environ["R_LIBS_USER"] = os.path.join(r_user, "R", "library")
                # 确保PATH包含R的bin目录（放最前面，去重）
                r_bin = os.path.join(r_home, "bin")
                r_bin_x64 = os.path.join(r_home, "bin", "x64")
                current_path = os.environ.get("PATH", "")
                path_parts = current_path.split(os.pathsep)
                non_r_parts = [p for p in path_parts if p and 'R-4' not in p and 'R-3' not in p and '\\R\\' not in p and '/R/' not in p]
                new_path_parts = [r_bin_x64, r_bin] + non_r_parts
                os.environ["PATH"] = os.pathsep.join(new_path_parts)

            # 检查R是否已初始化
            print(f"[_initialize_rpy2] 检查R是否已初始化...")
            import rpy2.rinterface

            try:
                # 尝试访问 R 环境，如果失败则表示未初始化
                _ = rpy2.rinterface.evalr("1")
                print(f"[_initialize_rpy2] R环境已初始化")
                self._is_initialized = True
                self._error_message = ""
                print(f"[_initialize_rpy2] 环境更新成功（R环境已存在）")
                return True
            except Exception:
                # R环境未初始化，进行初始化
                print(f"[_initialize_rpy2] R环境未初始化，开始初始化...")
                rpy2.rinterface.initr()
                self._is_initialized = True
                self._error_message = ""
                print(f"[_initialize_rpy2] R初始化成功")
                return True
        except Exception as e:
            self._error_message = f"初始化rpy2失败: {str(e)}"
            self._is_initialized = False
            print(f"[_initialize_rpy2] R初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


# ========================================
# 全局单例实例
# ========================================
_global_r_interface: Optional[RKernelInterface] = None


def get_r_kernel_interface() -> RKernelInterface:
    """
    获取全局R内核接口实例（单例模式）
    
    Returns:
        RKernelInterface: R内核接口实例
    """
    global _global_r_interface
    
    if _global_r_interface is None:
        _global_r_interface = RKernelInterface()
        # 启动时尝试从配置文件加载R路径
        saved_path = _global_r_interface._load_saved_r_path()
        if saved_path:
            print(f"[RKernelInterface] 启动时加载到保存的R路径: {saved_path}")
            _global_r_interface.set_r_path(saved_path)
        else:
            print(f"[RKernelInterface] 启动时未找到保存的R路径")
    
    return _global_r_interface