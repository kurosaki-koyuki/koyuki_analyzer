# -*- coding: utf-8 -*-
"""
introduce_layer - 外部工具接口层

该层负责提供对外和对内的接口：
- 对外：获取外部工具（如R内核）的路径配置
- 对内：为分析脚本提供外部工具的支持

子模块：
- r2p_layer: R to Python接口层，提供R环境配置和rpy2支持
- r_support: R支持层，包含R包管理等功能（预留）
"""

from .r2p_layer import RKernelInterface, get_r_kernel_interface

__all__ = ['RKernelInterface', 'get_r_kernel_interface']