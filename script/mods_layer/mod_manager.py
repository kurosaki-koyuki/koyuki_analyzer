# -*- coding: utf-8 -*-
"""
模组管理器脚本 - 管理多个模组的加载和切换
支持多个独立风格的模组，每个模组必须同时满足：
1. 在 appdata/mods/ 目录下有对应的资源文件夹
2. 在 appdata/mods/xxx/mod_script/ 或 script/mods_layer/xxx/ 目录下有对应的脚本文件

============================================================
5 函数模组开发模型（第三阶段）
============================================================
模组开发者只需要重写 5 个函数就能控制整个应用的外观：

【主界面 3 个函数】
1. _get_main_layout()   - 主界面位置函数（只做总体平移）
2. _get_main_colors()   - 主界面配色函数（边框色/填充色/字体色）
3. _get_main_fonts()     - 主界面字体函数（文字字体/GUI字体）

【子界面 2 个函数】
4. _get_sub_colors()    - 子界面配色函数（四色模型：边框/填充/候补填充/字体）
5. _get_sub_fonts()      - 子界面字体函数（GUI字体/信息字体）
"""

import os
import sys
import importlib
import importlib.util
import glob
import warnings

if getattr(sys, 'frozen', False):
    _MOD_BASE_DIR = os.path.dirname(sys.executable)
else:
    _MOD_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _find_appdata_path():
    candidates = [
        os.path.join(_MOD_BASE_DIR, "appdata"),
        os.path.join(_MOD_BASE_DIR, "_internal", "appdata"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return os.path.join(_MOD_BASE_DIR, "appdata")

_MOD_APPDATA_PATH = _find_appdata_path()

from script.utils_layer.import_config import *

BASE_DIR = _MOD_BASE_DIR
APPDATA_PATH = _MOD_APPDATA_PATH

class BaseMod:
    """
    模组基类 - 定义模组的标准接口
    所有模组必须继承此类并实现抽象方法
    """
    
    def __init__(self, mod_name):
        self.mod_name = mod_name
        self.resource_paths = self._get_resource_paths()
        self.style_config = self._build_style_config()
    
    def _rgba(self, hex_color, alpha):
        """把 #RRGGBB 转成 rgba(R, G, B, alpha)"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    
    def _hex_from_rgba(self, rgba_str):
        """从 rgba(R, G, B, a) 提取 #RRGGBB 部分"""
        import re
        match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', rgba_str)
        if match:
            r, g, b = match.groups()
            return f'#{int(r):02x}{int(g):02x}{int(b):02x}'
        return '#000000'
    
    # =============================================================
    # 5 函数模组开发模型 - 模组开发者只需重写这 5 个函数
    # =============================================================
    
    def _get_main_layout(self):
        """
        【主界面位置函数】
        模组想改主界面各组分的位置，重写这个函数就行
        设计原则：只做总体平移，不微调
        
        注意：布局 key 不需要 main_ 前缀，因为布局只用于主界面
        """
        return {
            # ===== 模组选择器位置 =====
            'mod_container_x': 15,
            'mod_container_y': 15,
            'mod_container_width': 250,
            'mod_container_height': 50,
            'mod_label_font_size': 12,
            'mod_combo_x': 70,
            'mod_combo_y': 5,
            'mod_combo_width': 170,
            'mod_combo_height': 30,
            
            # ===== 音乐控制器位置 =====
            'music_container_x': 0.9,
            'music_container_y': 15,
            'music_container_width': 200,
            'music_container_height': 50,
            'volume_slider_x': 0,
            'volume_slider_y': 25,
            'volume_slider_width': 150,
            'volume_slider_height': 25,
            'music_button_x': 155,
            'music_button_y': 0,
            'music_button_width': 40,
            'music_button_height': 40,
            
            # ===== 主标题位置 =====
            'title_x': 0.65,
            'title_y': 0.18,
            'title_width': 0.3,
            'title_height': 50,
            'title_font_size': 20,
            'title_color': '#87CEEB',
            
            # ===== 副标题位置 =====
            'left_title_x': 0.68,
            'left_title_y': 0.28,
            'left_title_width': 180,
            'left_title_height': 30,
            'right_title_x': 0.78,
            'right_title_y': 0.28,
            'right_title_width': 180,
            'right_title_height': 30,
            'tools_title_x': 0.88,
            'tools_title_y': 0.28,
            'tools_title_width': 180,
            'tools_title_height': 30,
            'section_title_font_size': 14,
            
            # ===== 按钮位置 =====
            'button_font_size': 16,
            'button_width': 180,
            'button_height': 60,
            'button_start_x': 0.68,
            'button_start_y': 0.32,
            'button_row_gap': 0.08,
            
            # ===== 打赏按钮位置 =====
            'donate_button_x': 0.725,
            'donate_button_y': 0.80,
        }
    
    def _get_main_colors(self):
        """
        【主界面配色函数】
        模组想改主界面的颜色，重写这个函数就行
        
        返回 3 个核心色：
        - border_color: 边框色（所有边框、分割线）
        - fill_color: 填充色（所有背景、面板、按钮默认态）
        - text_color: 字体色（所有文字、图标）
        """
        return {
            'border_color': '#1E3A5F',                          # 边框色：深蓝灰
            'fill_color': 'rgba(30, 58, 95, 0.3)',               # 填充色：深蓝灰 + 透明度
            'text_color': '#87CEEB',                            # 字体色：天蓝色
            'fill_alt': 'rgba(30, 58, 95, 0.5)',               # 候补填充色
            'hover_color': 'rgba(30, 58, 95, 0.4)',             # 悬停色：稍深于填充色
            'active_color': 'rgba(50, 88, 135, 0.4)',           # 选中色：略高于填充色（更亮）
        }
    
    def _get_main_fonts(self):
        """
        【主界面字体函数】
        模组想改主界面的字体，重写这个函数就行
        
        返回 2 种字体：
        - text_font: 文字字体（标题、副标题、说明文字等内容性文字）
        - gui_font: GUI 字体（按钮、下拉框等控件上的文字）
        """
        return {
            'text_font': '幼圆',     # 文字字体：标题、副标题等
            'gui_font': '幼圆',          # GUI 字体：按钮、下拉框等
        }
    
    def _get_sub_colors(self):
        """
        【子界面配色函数】五色模型
        模组想改子界面的颜色，重写这个函数就行

        返回 5 个核心色：
        - border_color: 边框色（GUI 和区域边框）
        - fill_color: 填充色（区域填充色和 GUI 填充色）
        - fill_alt: 候补填充色（比填充色稍暗，用于表格交替行等）
        - text_color: 字体色（所有文字）
        - mutant_color: 突变色（反差色，用于特殊强调、高对比场景）
        - hover_color: 悬停色（稍深于填充色，用于控件悬停态）
        - active_color: 选中色（略高于填充色，用于控件选中/激活态）
        """
        return {
            'border_color': '#1E3A5F',                          # 边框色：深蓝灰
            'fill_color': 'rgba(30, 58, 95, 0.3)',              # 填充色：深蓝灰 + 透明度
            'fill_alt': 'rgba(30, 58, 95, 0.5)',               # 候补填充色：比填充色稍暗
            'text_color': '#87CEEB',                            # 字体色：天蓝色
            'mutant_color': '#FF6B35',                          # 突变色：橙红色（与蓝色系互补）
            'hover_color': 'rgba(30, 58, 95, 0.4)',             # 悬停色：稍深于填充色
            'active_color': 'rgba(50, 88, 135, 0.4)',           # 选中色：略高于填充色（更亮）
        }
    
    def _get_sub_fonts(self):
        """
        【子界面字体函数】
        模组想改子界面的字体，重写这个函数就行
        
        返回 2 种字体：
        - gui_font: GUI 字体（按钮、下拉框、输入框等控件上的文字）
        - info_font: 信息字体（标签、说明文字、表格内容等其他信息）
        """
        return {
            'gui_font': '幼圆',          # GUI 字体：按钮、下拉框等
            'info_font': '幼圆',     # 信息字体：标签、说明文字等
        }
    
    # =============================================================
    # 内部三层架构推导 - 从 5 函数推导出所有控件样式
    # =============================================================
    
    def _build_style_config(self):
        """
        组装完整的样式配置
        1. 从 5 函数获取主/子界面配色和字体
        2. 推导主界面语义层和控件层
        3. 推导子界面语义层和控件层
        4. 合并所有配置（带变体前缀）
        5. 合并主界面布局配置
        """
        # ===== 1. 从 5 函数获取核心配置 =====
        main_colors = self._get_main_colors()
        main_fonts = self._get_main_fonts()
        sub_colors = self._get_sub_colors()
        sub_fonts = self._get_sub_fonts()
        main_layout = self._get_main_layout()
        
        # ===== 2. 推导主界面语义层 =====
        main_semantic = self._build_semantic_from_colors(main_colors, main_fonts, is_main=True)
        
        # ===== 3. 推导子界面语义层 =====
        sub_semantic = self._build_semantic_from_colors(sub_colors, sub_fonts, is_main=False)
        
        # ===== 4. 推导控件层 =====
        main_controls = self._build_controls(main_semantic, is_main=True)
        sub_controls = self._build_controls(sub_semantic, is_main=False)
        
        # ===== 5. 合并到 style_config =====
        style_config = {}
        
        # 主界面原始配色（带 main_ 前缀）
        for key in ['border_color', 'fill_color', 'fill_alt', 'text_color', 'hover_color', 'active_color']:
            if key in main_colors:
                style_config[f'main_{key}'] = main_colors[key]
        
        # 主界面字体（带 main_ 前缀）
        for key in main_fonts:
            style_config[f'main_{key}'] = main_fonts[key]
        
        # 子界面原始配色（带 sub_ 前缀）
        for key in ['border_color', 'fill_color', 'fill_alt', 'text_color', 'mutant_color', 'hover_color', 'active_color']:
            if key in sub_colors:
                style_config[f'sub_{key}'] = sub_colors[key]
        
        # 子界面字体（带 sub_ 前缀）
        for key in sub_fonts:
            style_config[f'sub_{key}'] = sub_fonts[key]
        
        # 主界面控件（带 main_ 前缀）
        for key, value in main_controls.items():
            style_config[f'main_{key}'] = value
        
        # 子界面控件（带 sub_ 前缀，且不带前缀的 key 默认等于子界面）
        for key, value in sub_controls.items():
            style_config[f'sub_{key}'] = value
            # 兼容：没有前缀的 key 默认等于子界面
            if key not in style_config:
                style_config[key] = value
        
        # 主界面布局（带 main_ 前缀）
        for key, value in main_layout.items():
            style_config[f'main_{key}'] = value
            # 同时保留不带前缀的版本（兼容）
            style_config[key] = value
        
        # 合并 _get_style_config() 返回的配置（界面文本等）
        style_config.update(self._get_style_config())
        
        return style_config
    
    def _build_semantic_from_colors(self, colors, fonts, is_main=True):
        """
        从颜色和字体配置推导语义层
        
        Args:
            colors: 配色函数返回的字典
            fonts: 字体函数返回的字典
            is_main: 是否为主界面
        
        Returns:
            语义层字典
        """
        # 计算填充色和候补填充色的 rgba 透明度
        fill_rgba = colors['fill_color']
        alt_rgba = colors.get('fill_alt', colors['fill_color'])
        
        # 如果 fill_color 是 hex，转成 rgba
        if fill_rgba.startswith('#'):
            fill_rgba = self._rgba(fill_rgba, 0.3)
        if alt_rgba.startswith('#'):
            alt_rgba = self._rgba(alt_rgba, 0.5)
        
        return {
            # 文字
            'text_primary': colors['text_color'],
            'text_secondary': colors['border_color'],
            
            # 背景
            'bg_default': fill_rgba,
            'bg_hover': colors.get('hover_color', alt_rgba),
            'bg_active': colors.get('active_color', self._rgba(colors['text_color'], 0.3)),
            'bg_dark': colors.get('fill_alt', alt_rgba),
            'bg_pressed': self._rgba(colors['text_color'], 0.3),
            
            # 边框
            'border_default': colors['border_color'],
            'border_focus': colors['text_color'],
            
            # 字体（主界面和子界面字体 key 不同）
            'font_button': fonts.get('gui_font', fonts.get('text_font', '幼圆')),
            'font_label': fonts.get('info_font', fonts.get('text_font', '幼圆')),
            'font_title': fonts.get('text_font', fonts.get('gui_font', '幼圆')),
            
            # 圆角
            'radius_sm': '3px',
            'radius_md': '5px',
            'radius_lg': '8px',
            
            # 选择色
            'selection_color': self._rgba(colors['text_color'], 0.3),
        }
    
    def _build_controls(self, semantic, is_main=True):
        """
        从语义层推导控件层
        
        Args:
            semantic: 语义层字典
            is_main: 是否为主界面
        
        Returns:
            控件层字典
        """
        s = semantic
        prefix = 'main' if is_main else 'sub'
        
        return {
            # ===== 按钮 =====
            'button_text': s['text_primary'],
            'button_bg': s['bg_default'],
            'button_border': s['border_default'],
            'button_hover_bg': s['bg_hover'],
            'button_active_bg': s['bg_active'],
            'button_pressed_bg': s['bg_pressed'],
            'button_radius': s['radius_md'],
            'button_font': s['font_button'],
            'button_default_height': 30,
            
            # ===== 下拉框 =====
            'combo_text': s['text_primary'],
            'combo_bg': s['bg_default'],
            'combo_border': s['border_default'],
            'combo_radius': s['radius_sm'],
            'combo_dropdown_text': s['text_primary'],
            'combo_dropdown_bg': s['bg_dark'],
            'combo_default_height': 22,
            
            # ===== 输入框 =====
            'input_text': s['text_primary'],
            'input_bg': s['bg_default'],
            'input_border': s['border_default'],
            'input_focus_border': s['border_focus'],
            'input_radius': s['radius_sm'],
            'input_default_height': 28,
            
            # ===== 滑块 =====
            'slider_bg': s['bg_default'],
            'slider_handle': s['border_default'],
            'slider_handle_hover': s['bg_hover'],
            
            # ===== 面板 =====
            'panel_bg': s['bg_default'],
            'panel_border': s['border_default'],
            'panel_radius': s['radius_lg'],
            'panel_padding': 10,
            
            # ===== 分组框 =====
            'group_text': s['text_primary'],
            'group_bg': s['bg_default'],
            'group_border': s['border_default'],
            'group_title_bg': s['bg_dark'],
            'group_radius': s['radius_lg'],
            
            # ===== 标签页 =====
            'tab_text': s['text_primary'],
            'tab_bg': s['bg_dark'],
            'tab_border': s['border_default'],
            'tab_hover_bg': s['bg_hover'],
            'tab_selected_bg': s['bg_pressed'],
            
            # ===== 表格（四色模型应用：交替行用 fill_alt）=====
            'table_border': s['border_default'],
            'table_header_bg': s['bg_dark'],
            'table_row_1': s['bg_default'],       # 填充色
            'table_row_2': s['bg_hover'],          # 候补填充色
            'table_text': 'black',                 # 表格文字用黑色
            
            # ===== 列表 =====
            'list_text': s['text_primary'],
            'list_bg': s['bg_default'],
            'list_border': s['border_default'],
            'list_item_bg': s['bg_default'],
            'list_item_hover_bg': s['bg_hover'],
            'list_item_selected_bg': s['selection_color'],
            
            # ===== 复选框 =====
            'checkbox_default_height': 20,
            
            # ===== 数字输入框 =====
            'spinbox_default_height': 25,
            'spinbox_button_width': 18,
            
            # ===== 列表控件 =====
            'list_widget_default_height': 100,
        }
    
    # =============================================================
    # 资源路径 - 旧接口保留
    # =============================================================
    
    def _get_resource_paths(self):
        """获取模组资源路径"""
        mod_base = os.path.join(APPDATA_PATH, "mods", self.mod_name)
        
        return {
            'BG_IMAGE_PATH': os.path.join(mod_base, "background", "bg.png"),
            'GUI_PATH': os.path.join(mod_base, "GUI"),
            'MUSIC_PATH': os.path.join(mod_base, "music"),
            'MAIN_MUSIC': os.path.join(mod_base, "music", "main_page.ogg"),
            'SOUND_PATH': os.path.join(mod_base, "sound"),
            'UI_CLICK_SOUND': os.path.join(mod_base, "sound", "UI_Bleep_Open.wav"),
            'MUSIC_PLAY_ICON': os.path.join(mod_base, "GUI", "run_music.ico"),
            'MUSIC_STOP_ICON': os.path.join(mod_base, "GUI", "stop_music.ico"),
            'VIDEO_PATH': os.path.join(mod_base, "start"),
            'STARTUP_VIDEO': os.path.join(mod_base, "start", "startup_main.webm"),
            'STARTUP_RETURN_VIDEO': os.path.join(mod_base, "start", "startup.webm"),
            'STARTREMAIN_VIDEO': os.path.join(mod_base, "start", "startremain.webm")
        }
    
    def _get_style_config(self):
        """
        【旧接口保留 - 兼容用】
        布局配置层：只保留非样式类配置（布局参数、文本内容）
        现在由 _get_main_layout() 和 _build_style_config() 统一管理
        """
        return {
            # ===== 界面文本 =====
            'window_title': '小雪生信工具箱',
            'main_title': '小雪生信工具一览',
            'single_cell_title': '单细胞分析',
            'bulk_title': 'bulk分析',
            'tools_title': '通用小工具',
            
            # ===== 主界面特殊样式覆盖 =====
            'mod_label_color': '#87CEEB',
            'mod_label_background': 'transparent',
            'mod_container_background': 'transparent',
            'subtitle_color': '#87CEEB',
            'subtitle_background': 'transparent',
            'subtitle_font_size': 14,
            'subtitle_font': '幼圆',
            'subtitle_bold': True,
            
            # ===== 主界面突变色（用于特殊按钮）=====
            'mutant_color': '#FF6B35',
        }
    
    def get_resource_path(self, key):
        """获取指定资源的路径"""
        return self.resource_paths.get(key, '')
    
    def get_style(self, key):
        """获取指定风格配置"""
        return self.style_config.get(key, '')
    
    def get_all_resources(self):
        """获取所有资源路径"""
        return self.resource_paths
    
    def get_all_styles(self):
        """获取所有风格配置"""
        return self.style_config
    
    def on_load(self):
        """模组加载时的初始化操作"""
        pass
    
    def on_unload(self):
        """模组卸载时的清理操作"""
        pass
    
    def get_music_controller_class(self):
        """获取音乐控制器类 - 子类应重写此方法返回具体的音乐控制器类"""
        # 延迟导入避免循环依赖
        from PyQt5.QtWidgets import QWidget, QPushButton, QSlider
        from PyQt5.QtCore import Qt
        
        class DefaultMusicController:
            """默认音乐控制器 - 用于没有模组或模组加载失败时"""
            
            def __init__(self, parent_widget, mod_instance, on_volume_changed=None):
                self.parent = parent_widget
                self.mod_instance = mod_instance
                self.music_container = None
                self.music_button = None
                self.volume_slider = None
            
            def create_music_controls(self, container_width=200, container_height=50, variant='main'):
                """创建音乐控制容器"""
                self.music_container = QWidget(self.parent)
                self.music_container.setFixedSize(container_width, container_height)
                self.music_container.setStyleSheet("background: rgba(50, 50, 80, 150); border-radius: 5px;")
                return self.music_container
            
            def get_music_button(self):
                return self.music_button
            
            def get_volume_slider(self):
                return self.volume_slider
        
        return DefaultMusicController


class ModManager:
    """模组管理器 - 管理多个模组的加载和切换"""
    
    def __init__(self):
        self.current_mod_name = "kurosaki_koyuki"
        self.available_mods = self._scan_available_mods()
        self.current_mod_instance = None
        self._load_current_mod()
    
    def _scan_available_mods(self):
        """扫描可用的模组 - 只加载同时有资源和脚本的模组"""
        available = []
        
        mods_dir = os.path.join(APPDATA_PATH, "mods")
        scripts_dir_new = os.path.join(APPDATA_PATH, "mods")
        scripts_dir_old = os.path.join(BASE_DIR, "script", "mods_layer")
        
        if not os.path.exists(mods_dir):
            return ["kurosaki_koyuki"]
        
        for item in os.listdir(mods_dir):
            mod_path = os.path.join(mods_dir, item)
            if os.path.isdir(mod_path):
                # 首先检查新的脚本位置：appdata/mods/xxx/mod_script/
                script_dir_new = os.path.join(mod_path, "mod_script")
                script_file_new = os.path.join(script_dir_new, "mod_script.py")
                
                if os.path.exists(script_file_new):
                    available.append(item)
                    continue
                
                # 然后检查旧的脚本位置：script/mods_layer/xxx/
                script_file_old = os.path.join(scripts_dir_old, item, "mod_script.py")
                if os.path.exists(script_file_old) and item not in available:
                    available.append(item)
        
        return available if available else ["kurosaki_koyuki"]
    
    def _load_mod_script(self, mod_name):
        """动态加载模组脚本 - 使用唯一模块名避免冲突"""
        # 首先尝试从新的脚本位置加载：appdata/mods/xxx/mod_script/
        try:
            mod_script_dir = os.path.join(APPDATA_PATH, "mods", mod_name, "mod_script")
            mod_script_file = os.path.join(mod_script_dir, "mod_script.py")
            
            if os.path.exists(mod_script_file):
                # 使用唯一的模块名来避免不同模组之间的冲突
                # 关键：每个模组使用不同的模块名，这样reload才能正确工作
                unique_module_name = f"mod_script_{mod_name}"
                
                # 如果模块已存在，先删除旧的模块缓存
                if unique_module_name in sys.modules:
                    del sys.modules[unique_module_name]
                
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(unique_module_name, mod_script_file)
                module = importlib.util.module_from_spec(spec)
                sys.modules[unique_module_name] = module
                spec.loader.exec_module(module)
                
                # 从模块中获取 ModClass
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseMod) and attr != BaseMod:
                        return attr
                
                raise ImportError(f"Module {mod_name} does not define a ModClass")
            else:
                raise FileNotFoundError(f"Script not found: {mod_script_file}")
        except Exception as e:
            print(f"Failed to load mod script from new location: {e}")
            
            # 回退到旧的脚本位置：script/mods_layer/xxx/
            try:
                mod_script_dir = os.path.join(BASE_DIR, "script", "mods_layer", mod_name)
                mod_script_file = os.path.join(mod_script_dir, "mod_script.py")
                
                if os.path.exists(mod_script_file):
                    unique_module_name = f"mod_script_{mod_name}"
                    
                    if unique_module_name in sys.modules:
                        del sys.modules[unique_module_name]
                    
                    spec = importlib.util.spec_from_file_location(unique_module_name, mod_script_file)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[unique_module_name] = module
                    spec.loader.exec_module(module)
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BaseMod) and attr != BaseMod:
                            return attr
                    
                    raise ImportError(f"Module {mod_name} does not define a ModClass")
                else:
                    raise FileNotFoundError(f"Script not found: {mod_script_file}")
            except Exception as e2:
                print(f"Failed to load mod script from old location: {e2}")
                return None
    
    def _load_current_mod(self):
        """加载当前模组"""
        mod_class = self._load_mod_script(self.current_mod_name)
        if mod_class:
            self.current_mod_instance = mod_class(self.current_mod_name)
        else:
            # 如果加载失败，使用默认模组
            self.current_mod_instance = BaseMod(self.current_mod_name)
    
    def set_current_mod(self, mod_name):
        """切换当前模组"""
        if mod_name in self.available_mods:
            self.current_mod_name = mod_name
            self._load_current_mod()
            return True
        return False
    
    def get_current_mod_name(self):
        """获取当前模组名称"""
        return self.current_mod_name
    
    def get_available_mods(self):
        """获取可用模组列表"""
        return self.available_mods
    
    def get_current_paths(self):
        """获取当前模组的资源路径"""
        if self.current_mod_instance:
            return self.current_mod_instance.get_all_resources()
        return {}
    
    def get_current_styles(self):
        """获取当前模组的风格配置"""
        if self.current_mod_instance:
            return self.current_mod_instance.get_all_styles()
        return {}
    
    def get_current_mod(self):
        """获取当前模组实例"""
        return self.current_mod_instance


# 全局模组管理器实例
global_mod_manager = ModManager()
