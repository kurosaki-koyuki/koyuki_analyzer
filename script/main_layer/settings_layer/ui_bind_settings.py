# -*- coding: utf-8 -*-
"""
Settings界面功能绑定脚本
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import get_mod_paths
from script.utils_layer.music_config import (
    is_startup_music_enabled, set_startup_music_enabled,
    is_click_sound_enabled, set_click_sound_enabled,
    get_default_volume, set_default_volume,
    get_click_volume, set_click_volume,
    is_role_sound_enabled, set_role_sound_enabled,
    get_role_volume, set_role_volume,
)
from script.utils_layer.mod_config import get_startup_mod_name, set_startup_mod_name
from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface, RKernelInterface
from script.mods_layer.mod_manager import global_mod_manager
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong
from script.utils_layer.page_intersect import page_intersect


class SettingsBind:
    """Settings界面功能绑定类"""
    
    def __init__(self, main_window, settings_ui):
        self.main_window = main_window
        self.settings_ui = settings_ui
        self.bind_signals()
        self.load_r_kernels()
        self.load_music_settings()
        self.load_click_and_volume_settings()
        self.load_role_settings()
        self.load_startup_mod_settings()

    def bind_signals(self):
        """绑定所有信号"""
        self.settings_ui.btn_back_settings.clicked.connect(page_intersect.go_to_home)
        
        self.settings_ui.btn_scan_r_kernel.clicked.connect(self.scan_r_kernels)
        
        self.settings_ui.btn_confirm_r_kernel.clicked.connect(self.confirm_r_kernel)

    def load_music_settings(self):
        """加载启动音乐设置到开关控件，并绑定保存"""
        if not hasattr(self.settings_ui, 'check_startup_music'):
            return
        try:
            enabled = is_startup_music_enabled()
            self.settings_ui.check_startup_music.setChecked(enabled)
            # 切换时立即保存（不弹确认，保持与R内核不同：这是即改即生效的开关）
            self.settings_ui.check_startup_music.toggled.connect(self._on_startup_music_toggled)
            print(f"加载启动音乐设置: 自动播放={'开启' if enabled else '关闭'}")
        except Exception as e:
            print(f"加载启动音乐设置失败: {e}")

    def _on_startup_music_toggled(self, checked):
        """勾选状态变化 -> 保存配置"""
        set_startup_music_enabled(bool(checked))

    def _get_sound_player(self):
        """获取当前模组的全局音效播放器"""
        try:
            mod_instance = global_mod_manager.get_current_mod()
            if mod_instance is not None and hasattr(mod_instance, 'global_sound_player'):
                return mod_instance.global_sound_player
        except Exception:
            pass
        return None

    def load_click_and_volume_settings(self):
        """加载点击音效开关与默认音量拉条，并绑定即时生效"""
        # ---- 点击音效开关 ----
        if hasattr(self.settings_ui, 'check_click_sound'):
            try:
                enabled = is_click_sound_enabled()
                self.settings_ui.check_click_sound.setChecked(enabled)
                self.settings_ui.check_click_sound.toggled.connect(
                    self._on_click_sound_toggled
                )
                # 启动/打开设置页时同步一次实际播放器状态
                sp = self._get_sound_player()
                if sp is not None:
                    sp.set_enabled(enabled)
                print(f"加载点击音效设置: 开启={'是' if enabled else '否'}")
            except Exception as e:
                print(f"加载点击音效设置失败: {e}")

        # ---- 默认音量拉条 ----
        if hasattr(self.settings_ui, 'settings_volume_slider'):
            try:
                default_volume = get_default_volume()
                self.settings_ui.settings_volume_slider.setValue(default_volume)
                self.settings_ui.settings_volume_label.setText(str(default_volume))
                self.settings_ui.settings_volume_slider.valueChanged.connect(
                    self._on_settings_volume_changed
                )
                print(f"加载默认音量设置: {default_volume}")
            except Exception as e:
                print(f"加载默认音量设置失败: {e}")

        # ---- 按钮音效音量拉条 ----
        if hasattr(self.settings_ui, 'settings_click_volume_slider'):
            try:
                click_volume = get_click_volume()
                self.settings_ui.settings_click_volume_slider.setValue(click_volume)
                self.settings_ui.settings_click_volume_label.setText(str(click_volume))
                self.settings_ui.settings_click_volume_slider.valueChanged.connect(
                    self._on_settings_click_volume_changed
                )
                # 打开设置页时同步一次实际播放器的音效音量
                sp = self._get_sound_player()
                if sp is not None and hasattr(sp, 'set_click_volume'):
                    sp.set_click_volume(click_volume / 100.0)
                print(f"加载按钮音效音量设置: {click_volume}")
            except Exception as e:
                print(f"加载按钮音效音量设置失败: {e}")

    def _on_settings_click_volume_changed(self, value):
        """按钮音效音量拉条变化 -> 立即应用到播放器 + 存为重启默认"""
        value = int(value)
        slider = getattr(self.settings_ui, 'settings_click_volume_label', None)
        if slider is not None:
            self.settings_ui.settings_click_volume_label.setText(str(value))
        sp = self._get_sound_player()
        if sp is not None and hasattr(sp, 'set_click_volume'):
            sp.set_click_volume(value / 100.0)
        set_click_volume(value)

    def _on_click_sound_toggled(self, checked):
        """点击音效开关变化 -> 立即应用到播放器 + 保存配置"""
        enabled = bool(checked)
        sp = self._get_sound_player()
        if sp is not None:
            sp.set_enabled(enabled)
        set_click_sound_enabled(enabled)

    def load_role_settings(self):
        """加载角色音效开关与音量，并绑定即时生效（独立于点击音效）"""
        # ---- 角色音效开关 ----
        if hasattr(self.settings_ui, 'check_role_sound'):
            try:
                enabled = is_role_sound_enabled()
                self.settings_ui.check_role_sound.setChecked(enabled)
                self.settings_ui.check_role_sound.toggled.connect(
                    self._on_role_sound_toggled
                )
                # 打开设置页时同步一次实际播放器的角色音效开关
                sp = self._get_sound_player()
                if sp is not None and hasattr(sp, 'set_role_enabled'):
                    sp.set_role_enabled(enabled)
                print(f"加载角色音效设置: 开启={'是' if enabled else '否'}")
            except Exception as e:
                print(f"加载角色音效设置失败: {e}")

        # ---- 角色音效音量 ----
        if hasattr(self.settings_ui, 'settings_role_volume_slider'):
            try:
                role_volume = get_role_volume()
                self.settings_ui.settings_role_volume_slider.setValue(role_volume)
                self.settings_ui.settings_role_volume_label.setText(str(role_volume))
                self.settings_ui.settings_role_volume_slider.valueChanged.connect(
                    self._on_settings_role_volume_changed
                )
                # 打开设置页时同步一次实际播放器的角色音效音量
                sp = self._get_sound_player()
                if sp is not None and hasattr(sp, 'set_role_volume'):
                    sp.set_role_volume(role_volume / 100.0)
                print(f"加载角色音效音量设置: {role_volume}")
            except Exception as e:
                print(f"加载角色音效音量设置失败: {e}")

    def _on_role_sound_toggled(self, checked):
        """角色音效开关变化 -> 立即应用到播放器 + 保存配置"""
        enabled = bool(checked)
        sp = self._get_sound_player()
        if sp is not None and hasattr(sp, 'set_role_enabled'):
            sp.set_role_enabled(enabled)
        set_role_sound_enabled(enabled)

    def _on_settings_role_volume_changed(self, value):
        """角色音效音量变化 -> 立即应用到播放器 + 存为重启默认"""
        value = int(value)
        self.settings_ui.settings_role_volume_label.setText(str(value))
        sp = self._get_sound_player()
        if sp is not None and hasattr(sp, 'set_role_volume'):
            sp.set_role_volume(value / 100.0)
        set_role_volume(value)

    def _on_settings_volume_changed(self, value):
        """默认音量拉条变化 -> 立即同步到音乐音量，并存为重启默认"""
        value = int(value)
        self.settings_ui.settings_volume_label.setText(str(value))
        # 立即同步到后台音乐播放器与音乐控件音量条（单向：设置 -> 音乐）
        mod_instance = global_mod_manager.get_current_mod()
        if mod_instance is not None and hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)
        main_window = self.main_window
        if main_window is not None and hasattr(main_window, 'func'):
            main_window.func.sync_volume_sliders(value)
        # 保存为重启默认音量
        set_default_volume(value)

    def load_startup_mod_settings(self):
        """加载默认启动模组下拉框，并绑定选择保存（不立即切换）"""
        if not hasattr(self.settings_ui, 'startup_mod_combo'):
            return
        try:
            # 初始显示：当前配置的启动默认模组（UI 已填充，此处无需再设）
            current = get_startup_mod_name("kurosaki_koyuki")
            idx = self.settings_ui.startup_mod_combo.findText(current)
            if idx >= 0:
                self.settings_ui.startup_mod_combo.setCurrentIndex(idx)
            # 选择变化 -> 保存配置，不切换当前运行的模组
            self.settings_ui.startup_mod_combo.currentIndexChanged.connect(
                self._on_startup_mod_changed
            )
            print(f"加载默认启动模组: {current}")
        except Exception as e:
            print(f"加载默认启动模组失败: {e}")

    def _on_startup_mod_changed(self, index):
        """下拉框选择变化 -> 保存“启动默认模组”配置"""
        combo = self.settings_ui.startup_mod_combo
        mod_name = combo.itemText(index) if index >= 0 else ""
        if mod_name:
            set_startup_mod_name(mod_name)
            print(f"已设置启动默认模组（重启生效）: {mod_name}")

    def scan_r_kernels(self):
        """扫描并检测本机R内核 - 全盘扫描"""
        import os
        import subprocess
        import win32api
        
        self.settings_ui.r_kernel_combo.clear()
        
        detected_paths = []
        scanned_drives = set()
        
        # 方法1: 获取所有可用盘符
        try:
            drives = win32api.GetLogicalDriveStrings().split('\0')[:-1]
            for drive in drives:
                # 转换路径格式，确保盘符格式正确 (如 "C:\\")
                drive_letter = drive.rstrip('\\').rstrip('/') + '\\'
                scanned_drives.add(drive_letter)
        except Exception as e:
            print(f"获取盘符失败: {e}")
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']:
                scanned_drives.add(f"{letter}:\\")
        
        print(f"扫描盘符: {scanned_drives}")
        
        # 方法2: 使用where命令查找R.exe
        try:
            result = subprocess.run(['where', 'R.exe'], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line:
                        r_exe_dir = os.path.dirname(line)
                        if r_exe_dir.endswith('\\bin') or r_exe_dir.endswith('/bin'):
                            r_path = os.path.dirname(r_exe_dir)
                        else:
                            r_path = r_exe_dir
                        if r_path and os.path.exists(os.path.join(r_path, "bin")):
                            if r_path not in detected_paths:
                                detected_paths.append(r_path)
                                print(f"通过where找到R: {r_path}")
        except Exception as e:
            print(f"where命令查找失败: {e}")
        
        # 方法3: 从PATH环境变量搜索R
        for path_dir in os.environ.get('PATH', '').split(os.pathsep):
            r_exe = os.path.join(path_dir, 'R.exe')
            if os.path.exists(r_exe):
                try:
                    if path_dir.endswith('\\bin') or path_dir.endswith('/bin'):
                        r_path = os.path.dirname(path_dir)
                    else:
                        r_path = path_dir
                    if r_path and os.path.exists(os.path.join(r_path, "bin")):
                        if r_path not in detected_paths:
                            detected_paths.append(r_path)
                            print(f"通过PATH找到R: {r_path}")
                except Exception:
                    pass
        
        # 方法4: 扫描所有盘符的常见R安装目录
        for drive in scanned_drives:
            common_paths = [
                os.path.join(drive, "Program Files", "R"),
                os.path.join(drive, "Program Files (x86)", "R"),
                os.path.join(drive, "TOOLS", "R"),
                os.path.join(drive, "TOOLS", "r"),
                os.path.join(drive, "TOOLS"),  # 直接扫描TOOLS目录
            ]
            for scan_path in common_paths:
                if os.path.exists(scan_path):
                    try:
                        for item in os.listdir(scan_path):
                            item_path = os.path.join(scan_path, item)
                            # 检查item是否是R版本目录（以R-开头）
                            if os.path.isdir(item_path) and item.upper().startswith('R-'):
                                # 检查是否有x64子目录（Windows R的常见结构）
                                x64_bin_path = os.path.join(item_path, "bin", "x64")
                                if os.path.exists(os.path.join(x64_bin_path, "R.exe")):
                                    if item_path not in detected_paths:
                                        detected_paths.append(item_path)
                                        print(f"通过目录扫描找到R (x64): {item_path}")
                                elif os.path.exists(os.path.join(item_path, "bin", "R.exe")):
                                    if item_path not in detected_paths:
                                        detected_paths.append(item_path)
                                        print(f"通过目录扫描找到R: {item_path}")
                    except PermissionError:
                        continue
                    except Exception as e:
                        print(f"扫描目录失败 {scan_path}: {e}")
        
        # 去重
        detected_paths = list(dict.fromkeys(detected_paths))
        
        # 保存到内存
        self._detected_r_paths = detected_paths
        
        # 填充下拉框
        if detected_paths:
            for path in detected_paths:
                self.settings_ui.r_kernel_combo.addItem(path)
            happy(self.main_window, f"成功扫描到 {len(detected_paths)} 个R内核")
        else:
            self.settings_ui.r_kernel_combo.addItem("未检测到R内核")
            attention(self.main_window, "未在系统中检测到R内核，请确认R已正确安装")

    def confirm_r_kernel(self):
        """确认选择的R内核"""
        selected_path = self.settings_ui.r_kernel_combo.currentText()
        if selected_path and selected_path != "未检测到R内核" and selected_path != "点击扫描R内核" and selected_path != "--- 扫描更多 ---":
            # 保存选择的R内核路径
            self._save_r_kernel_path(selected_path)

            # 同时更新全局RKernelInterface
            from script.introduce_layer.r2p_layer.r_kernel_interface import get_r_kernel_interface
            r_interface = get_r_kernel_interface()
            success = r_interface.set_r_path(selected_path)
            if success:
                print(f"R内核已更新到RKernelInterface: {selected_path}")
            else:
                print(f"R内核更新失败: {r_interface.get_error_message()}")

            # 更新状态显示
            if hasattr(self.settings_ui, 'r_status_text'):
                self.settings_ui.r_status_text.setText(selected_path)
            happy(self.main_window, f"R内核已设置为: {selected_path}")
        else:
            attention(self.main_window, "请先扫描并选择一个有效的R内核")

    def _save_r_kernel_path(self, r_path):
        """保存R内核路径到配置文件"""
        import os
        # 正确获取mod目录路径
        from script.utils_layer.import_config import BASE_DIR
        mod_base = os.path.join(BASE_DIR, "appdata", "mods", "kurosaki_koyuki")
        config_dir = os.path.join(mod_base, "config")
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "r_kernel_config.txt")
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(r_path)
            print(f"R内核路径已保存: {r_path}")
        except Exception as e:
            print(f"保存R内核路径失败: {e}")

    def _load_saved_r_path(self):
        """加载保存的R内核路径"""
        import os
        from script.utils_layer.import_config import BASE_DIR
        mod_base = os.path.join(BASE_DIR, "appdata", "mods", "kurosaki_koyuki")
        config_file = os.path.join(mod_base, "config", "r_kernel_config.txt")
        print(f"尝试加载R内核配置: {config_file}")
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    print(f"读取到R内核路径: {content}")
                    return content
        except Exception as e:
            print(f"加载R内核路径失败: {e}")
        return None

    def load_r_kernels(self):
        """加载可用的R内核到下拉框"""
        self.settings_ui.r_kernel_combo.clear()
        
        # 如果已有保存的配置R路径，选中它
        saved_path = self._load_saved_r_path()
        if saved_path:
            self.settings_ui.r_kernel_combo.addItem(saved_path)
            self.settings_ui.r_kernel_combo.addItem("--- 扫描更多 ---")
            # 更新状态显示
            if hasattr(self.settings_ui, 'r_status_text'):
                self.settings_ui.r_status_text.setText(saved_path)
        else:
            self.settings_ui.r_kernel_combo.addItem("点击扫描R内核")
