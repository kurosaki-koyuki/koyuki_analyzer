# -*- coding: utf-8 -*-
"""
r2p_layer - R to Python 接口层

提供R环境配置和rpy2支持，连接Python和R语言环境

模块：
- r_kernel_interface: R内核接口，提供对外和对内的R环境支持
"""

from .r_kernel_interface import RKernelInterface, get_r_kernel_interface

__all__ = ['RKernelInterface', 'get_r_kernel_interface']