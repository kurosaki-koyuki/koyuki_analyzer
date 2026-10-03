# -*- coding: utf-8 -*-
"""
页面模板 - analysis 层（纯业务逻辑，不涉及UI）

职责：
1. 复用项目统一的 R 内核接口（script.introduce_layer.r2p_layer.r_kernel_interface），
   读取「R 是否可用 / R 版本字符串 / R_HOME」；
2. 读取当前 Python 解释器版本信息（版本号、实现、解释器路径、完整构建信息）。

约定：
- 本文件属于 analysis 层，不导入任何 UI 模块、不依赖窗口对象；
- 不重复初始化 rpy2、不自行设置 R_HOME，R 相关能力全部走 get_r_kernel_interface()；
- 对外方法一律「绝不抛异常」，任何失败路径都返回结构完整的降级 dict。
"""

from script.utils_layer.import_config import os, sys
import platform

# 复用项目现有 R 内核接口（唯一入口），与 start.py 中的初始化方式保持一致
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface


class PageTemplateAnalysis:
    """页面模板分析类 - 纯业务逻辑，负责运行环境（R / Python）版本自检"""

    def __init__(self):
        # 延迟获取 R 接口：get_r_kernel_interface() 首次调用会触发 R 环境初始化（耗时较长），
        # 放在 __init__ 中会阻塞界面创建，因此这里只占位，真正获取推迟到首次调用时进行。
        self.r_interface = None
        # 记录获取接口失败的原因，用于拼装 detail
        self._r_interface_error = ""

    # ========================================
    # 内部工具
    # ========================================

    def _get_r_interface(self):
        """
        获取项目全局 R 内核接口实例（单例模式），失败时返回 None 并记录原因

        注意：不缓存失败结果。若本次获取失败，下一次调用会重新尝试，
        这样当 R 环境稍后变得可用时可以自动恢复，无需重启页面。

        Returns:
            RKernelInterface 或 None
        """
        # 已经成功获取过，直接复用
        if self.r_interface is not None:
            return self.r_interface

        try:
            self.r_interface = get_r_kernel_interface()
            self._r_interface_error = ""
        except Exception as e:
            # 获取失败不向外抛出（例如 rpy2 缺失、R_HOME 配置异常等）
            self.r_interface = None
            self._r_interface_error = f"获取R接口对象失败: {type(e).__name__}: {e}"

        return self.r_interface

    # ========================================
    # 对外接口
    # ========================================

    def get_r_version(self):
        """
        获取 R 环境信息（复用项目统一 R 接口，本文件不自行初始化 rpy2）

        Returns:
            dict: {
                'available': bool,  # R 环境是否可用
                'version':   str,   # R 版本字符串，失败时为 '未知'
                'r_home':    str,   # R_HOME 路径，失败时回落到环境变量或 '未知'
                'detail':    str    # 过程说明 / 失败原因
            }
        """
        # 兜底值：任何异常路径都返回这一组结构完整的字段
        detail_parts = []
        available = False
        version = "未知"
        r_home = os.environ.get("R_HOME", "") or "未知"

        try:
            # ---------- 1. 取接口对象 ----------
            interface = self._get_r_interface()
            if interface is None:
                detail_parts.append("R接口对象未取得")
                detail_parts.append(self._r_interface_error or "原因未知")
                return {
                    'available': False,
                    'version': version,
                    'r_home': r_home,
                    'detail': "；".join(detail_parts),
                }
            detail_parts.append("R接口对象获取成功")

            # ---------- 2. 是否可用（RKernelInterface.is_r_available） ----------
            try:
                available = bool(interface.is_r_available())
            except Exception as e:
                available = False
                detail_parts.append(f"调用 is_r_available() 异常: {type(e).__name__}: {e}")
            detail_parts.append(f"R环境可用={available}")

            # ---------- 3. 复用接口已有的版本信息方法（RKernelInterface.get_r_version_info） ----------
            info = None
            try:
                info = interface.get_r_version_info()
            except Exception as e:
                detail_parts.append(f"调用 get_r_version_info() 异常: {type(e).__name__}: {e}")
                info = None
            if not isinstance(info, dict):
                info = {}

            # 3.1 R_HOME：优先接口记录的 r_home，其次 r_path，最后保留环境变量兜底值
            for key in ("r_home", "r_path"):
                value = info.get(key)
                if value:
                    r_home = str(value)
                    break

            # 3.2 版本字符串
            raw_version = info.get("version")
            if raw_version:
                version = str(raw_version).strip()

            # 3.3 接口未给出字符串时，退化为用接口暴露的 robjects 实例求值
            #     （与 bulk_cluster_analysis / wgcna_analysis 等既有 analysis 层写法一致）
            if (not raw_version) and available:
                try:
                    robjects_obj = interface.get_robjects()
                    if robjects_obj is not None:
                        version = str(robjects_obj.r('R.version.string')[0]).strip()
                except Exception as e:
                    detail_parts.append(f"通过 robjects 取R版本失败: {type(e).__name__}: {e}")
                    version = "未知"

            # 3.4 接口自身的错误信息（例如 R 初始化失败原因）
            error_message = info.get("error")
            if error_message:
                detail_parts.append(f"R接口错误信息: {error_message}")

        except Exception as e:
            # 最后一道兜底：本方法绝不向外抛异常
            available = False
            detail_parts.append(f"未预期的异常: {type(e).__name__}: {e}")

        if not detail_parts:
            detail_parts.append("R环境信息读取完成")

        return {
            'available': available,
            'version': version,
            'r_home': r_home,
            'detail': "；".join(detail_parts),
        }

    def get_py_version(self):
        """
        获取当前 Python 解释器信息（不依赖 R 环境，稳定可用）

        Returns:
            dict: {
                'version':        str,  # platform.python_version()，如 '3.13.0'
                'implementation': str,  # platform.python_implementation()，如 'CPython'
                'executable':     str,  # sys.executable
                'detail':         str   # 完整 sys.version（含编译器/构建信息）+ platform.platform()
            }
        """
        version = "未知"
        implementation = "未知"
        executable = "未知"
        detail_parts = []

        # ---------- 1. 版本号 ----------
        try:
            version = platform.python_version()
        except Exception as e:
            detail_parts.append(f"读取Python版本号失败: {type(e).__name__}: {e}")

        # ---------- 2. 实现（CPython / PyPy 等） ----------
        try:
            implementation = platform.python_implementation()
        except Exception as e:
            detail_parts.append(f"读取Python实现失败: {type(e).__name__}: {e}")

        # ---------- 3. 解释器路径 ----------
        try:
            executable = sys.executable or "未知"
        except Exception as e:
            detail_parts.append(f"读取解释器路径失败: {type(e).__name__}: {e}")

        # ---------- 4. 详细信息：完整 sys.version + 平台信息 ----------
        try:
            detail_parts.append(str(sys.version).strip())
        except Exception as e:
            detail_parts.append(f"读取sys.version失败: {type(e).__name__}: {e}")

        try:
            detail_parts.append(platform.platform())
        except Exception as e:
            detail_parts.append(f"读取平台信息失败: {type(e).__name__}: {e}")

        return {
            'version': version,
            'implementation': implementation,
            'executable': executable,
            'detail': "\n".join(detail_parts),
        }
