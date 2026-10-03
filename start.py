# -*- coding: utf-8 -*-
"""
启动脚本 - 用于启动GUI应用程序
"""

import sys
import os

# 直接使用脚本所在目录作为根目录
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 确保路径标准化
if _SCRIPT_DIR.endswith('\\') or _SCRIPT_DIR.endswith('/'):
    _SCRIPT_DIR = _SCRIPT_DIR[:-1]

# 添加到 Python 路径
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# ========================================
# 预加载R内核路径（在导入rpy2相关模块之前设置R_HOME）
# ========================================
def _find_appdata_for_startup(base_dir):
    """查找appdata目录的正确路径"""
    candidates = [
        os.path.join(base_dir, "appdata"),
        os.path.join(base_dir, "_internal", "appdata"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return os.path.join(base_dir, "appdata")

def _load_and_set_r_home():
    """从配置文件加载R路径并设置R_HOME环境变量"""
    try:
        # 直接使用脚本所在目录作为基础
        base_dir = _SCRIPT_DIR
        appdata_path = _find_appdata_for_startup(base_dir)
        config_file = os.path.join(appdata_path, "mods", "kurosaki_koyuki", "config", "r_kernel_config.txt")
        print(f"[Startup] 查找R配置文件: {config_file}")
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                r_path = f.read().strip()
            print(f"[Startup] 读取到R路径: '{r_path}'")
            # 检查路径是否存在
            if r_path and os.path.exists(r_path):
                os.environ["R_HOME"] = r_path
                print(f"[Startup] R_HOME已设置为: {r_path}")
                return
            else:
                print(f"[Startup] R路径不存在: {r_path}")
        print(f"[Startup] 未找到R配置文件或R路径无效")
    except Exception as e:
        print(f"[Startup] 加载R配置失败: {e}")
        import traceback
        traceback.print_exc()

# 在导入rpy2相关模块之前设置R_HOME
_load_and_set_r_home()

from script.utils_layer.import_config import *

# QtWebEngineWidgets必须在QApplication创建之前导入，否则可能加载失败
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView as _TestWebEngineView
    print("[Startup] QtWebEngineWidgets 加载成功")
except ImportError as _e:
    print(f"[Startup] QtWebEngineWidgets 加载失败: {_e}")

from script.main_layer.ui_bind import MainWindowBind

# 预加载R内核接口，触发R环境初始化
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
print("[Startup] 初始化R内核接口...")
_r_interface = get_r_kernel_interface()
print(f"[Startup] R接口初始化完成，可用状态: {_r_interface.is_r_available()}")

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindowBind()

    window.showMaximized()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()