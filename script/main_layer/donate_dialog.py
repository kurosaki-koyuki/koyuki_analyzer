# -*- coding: utf-8 -*-
"""
打赏弹窗 - 显示V50图片 + 强制播放V50音乐
进入弹窗时保存主界面音乐状态，强制播放V50.ogg（音量最大）
关闭弹窗时恢复主界面原音乐状态
"""

from script.utils_layer.import_config import (
    os, APPDATA_PATH, pygame, QPushButton, QSlider, QLabel, QDialog,
    QVBoxLayout, QHBoxLayout, Qt, QIcon, QSize, QPixmap, QWidget, QTimer,
    QEvent, QObject
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.gui_styles import get_mod_styles, get_mod_paths


class ClickableSlider(QSlider):
    """可点击跳转的进度条 - 点击 groove 任意位置直接跳转到该位置"""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.orientation() == Qt.Horizontal:
            # 计算点击位置对应的值
            if self.width() > 0:
                ratio = event.x() / self.width()
                value = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
                value = max(self.minimum(), min(self.maximum(), value))
                self.setValue(value)
                self.sliderPressed.emit()
                self.sliderMoved.emit(value)
                self.sliderReleased.emit()
                event.accept()
                return
        super().mousePressEvent(event)


class DonateDialog(QDialog):
    """打赏弹窗 - 显示V50图片，强制播放V50音乐"""

    V50_IMAGE = os.path.join(APPDATA_PATH, "elements", "V50.png")
    V50_MUSIC = os.path.join(APPDATA_PATH, "elements", "V50.ogg")

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)

        # 保存主界面音乐状态
        self._was_playing = False
        self._original_music = None
        self._original_volume = 1.0
        self._save_main_music_state()

        # 进度条相关
        self._music_duration_ms = 0
        self._current_pos_ms = 0  # 自己维护的播放位置（不依赖 get_pos）
        self._is_paused = False
        self._is_seeking = False  # 正在拖动进度条时暂停自动更新
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)

        # 获取音乐总时长
        self._music_duration_ms = self._get_music_duration_ms()

        # 构建UI
        self._build_ui()

        # 安装点击音效过滤器到弹窗及所有子控件
        self._install_click_filter()

        # 切换到V50音乐
        self._play_v50_music()

    def _save_main_music_state(self):
        """保存主界面音乐状态（播放状态、音乐路径、音量）"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            player = mod_instance.global_music_player
            self._was_playing = player.is_playing
            self._original_music = player.current_music
            self._original_volume = player.get_volume()

    def _get_music_duration_ms(self):
        """获取V50音乐总时长（毫秒）"""
        try:
            sound = pygame.mixer.Sound(self.V50_MUSIC)
            duration_ms = int(sound.get_length() * 1000)
            del sound
            return duration_ms
        except Exception as e:
            print(f"获取V50音乐时长失败: {e}")
            return 0

    def _play_v50_music(self):
        """停止主界面音乐，加载并播放V50.ogg（音量最大，循环）"""
        mod_instance = global_mod_manager.get_current_mod()
        if not hasattr(mod_instance, 'global_music_player'):
            return

        player = mod_instance.global_music_player

        # 停止当前音乐
        if player.is_playing:
            player.stop()

        # 加载并播放V50
        player.load_music(self.V50_MUSIC)
        player.set_volume(1.0)
        player.play(loops=-1)

        # 更新弹窗内音乐按钮图标为"正在播放"状态
        self._update_music_button_icon(True)

        # 重置播放位置并启动进度条定时器
        self._current_pos_ms = 0
        if self._music_duration_ms > 0:
            self._progress_timer.start(100)

    def _restore_main_music_state(self):
        """恢复主界面原音乐状态"""
        # 停止进度条定时器
        if self._progress_timer.isActive():
            self._progress_timer.stop()

        mod_instance = global_mod_manager.get_current_mod()
        if not hasattr(mod_instance, 'global_music_player'):
            return

        player = mod_instance.global_music_player

        # 停止V50
        player.stop()

        # 恢复原音乐
        if self._original_music:
            player.load_music(self._original_music)

        player.set_volume(self._original_volume)

        if self._was_playing:
            player.play()

        # 更新主界面音乐按钮图标和音量滑块显示
        if hasattr(self.main_window, 'func'):
            self.main_window.func.update_music_icon(self._was_playing)
            # 同步主界面音量滑块显示为恢复后的音量
            volume_percent = int(self._original_volume * 100)
            self.main_window.func.sync_volume_sliders(volume_percent)

    def _install_click_filter(self):
        """安装点击音效过滤器到弹窗及所有子控件"""
        try:
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'get_click_filter_class') and hasattr(mod_instance, 'global_sound_player'):
                ClickFilterClass = mod_instance.get_click_filter_class()
                self.click_filter = ClickFilterClass(mod_instance.global_sound_player)
                self.installEventFilter(self.click_filter)
                self._install_click_filter_recursively(self)
        except Exception as e:
            print(f"安装点击音效过滤器失败: {e}")

    def _install_click_filter_recursively(self, widget):
        """递归安装点击音效过滤器到所有子控件"""
        try:
            if widget and hasattr(widget, 'installEventFilter'):
                widget.installEventFilter(self.click_filter)
            if hasattr(widget, 'children'):
                for child in widget.children():
                    self._install_click_filter_recursively(child)
        except Exception:
            pass

    def _build_ui(self):
        """构建弹窗UI"""
        styles = get_mod_styles()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === 图片区域（带缩放保护）===
        image_label = QLabel(self)
        pixmap = QPixmap(self.V50_IMAGE)
        if not pixmap.isNull():
            # 图片过大缩放保护：按主窗口尺寸的90%为上限
            max_width = int(self.main_window.screen_width * 0.9)
            max_height = int(self.main_window.screen_height * 0.8)
            if pixmap.width() > max_width or pixmap.height() > max_height:
                scaled_pixmap = pixmap.scaled(
                    max_width, max_height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            else:
                scaled_pixmap = pixmap
            image_label.setPixmap(scaled_pixmap)
            image_label.setScaledContents(False)
            display_pixmap = scaled_pixmap
        else:
            image_label.setText("V50 图片加载失败")
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setFixedSize(400, 300)
            display_pixmap = pixmap
        layout.addWidget(image_label)

        # === 进度条 + 暂停按钮区域 ===
        progress_widget = QWidget(self)
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(15, 8, 15, 8)
        progress_layout.setSpacing(10)

        # 播放时间标签
        self.time_label = QLabel("00:00 / 00:00", progress_widget)
        time_color = styles.get('main_text_color', '#87CEEB')
        self.time_label.setStyleSheet(f"color: {time_color}; background: transparent; font-size: 11px;")
        progress_layout.addWidget(self.time_label)

        # 进度条（可点击跳转 + 可拖动跳转）
        self.progress_slider = ClickableSlider(Qt.Horizontal, progress_widget)
        self.progress_slider.setRange(0, max(self._music_duration_ms, 1))
        self.progress_slider.setValue(0)
        self.progress_slider.setStyleSheet(self._get_progress_stylesheet(styles))
        self.progress_slider.sliderPressed.connect(self._on_progress_pressed)
        self.progress_slider.sliderReleased.connect(self._on_progress_released)
        self.progress_slider.valueChanged.connect(self._on_progress_value_changed)
        progress_layout.addWidget(self.progress_slider, 1)

        # 进度条区域背景
        progress_bg = styles.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)')
        progress_widget.setStyleSheet(f"background: {progress_bg};")
        layout.addWidget(progress_widget)

        # === 感谢文字 + 音乐控件区域 ===
        bottom_widget = QWidget(self)
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(15, 10, 15, 10)
        bottom_layout.setSpacing(10)

        # 感谢文字
        thanks_label = QLabel("感谢您的支持！", bottom_widget)
        thanks_color = styles.get('main_text_color', '#87CEEB')
        thanks_label.setStyleSheet(f"color: {thanks_color}; background: transparent; font-size: 14px; font-weight: bold;")
        bottom_layout.addWidget(thanks_label)

        bottom_layout.addStretch()

        # 音量滑块
        self.volume_slider = QSlider(Qt.Horizontal, bottom_widget)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        slider_stylesheet = self._get_slider_stylesheet(styles)
        self.volume_slider.setStyleSheet(slider_stylesheet)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        bottom_layout.addWidget(self.volume_slider)

        # 音乐按钮
        self.music_btn = QPushButton(bottom_widget)
        self.music_btn.setFixedSize(40, 40)
        self.music_btn.setStyleSheet(self._get_button_stylesheet(styles))
        self.music_btn.clicked.connect(self._on_music_clicked)
        bottom_layout.addWidget(self.music_btn)

        # 关闭按钮（hover颜色使用styles七色函数，不硬编码）
        close_btn = QPushButton("✕", bottom_widget)
        close_btn.setFixedSize(40, 40)
        close_color = styles.get('main_mutant_color', '#FF6B35')
        close_hover_color = styles.get('main_hover_color', close_color)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: white;
                background-color: {close_color};
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {close_hover_color};
            }}
        """)
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)

        # 设置底部背景
        bg_color = styles.get('main_fill_color', 'rgba(30, 58, 95, 0.8)')
        bottom_widget.setStyleSheet(f"background: {bg_color};")

        layout.addWidget(bottom_widget)

        # 根据图片尺寸调整窗口大小（使用缩放后的尺寸 + 进度条高度40）
        if not display_pixmap.isNull():
            img_width = display_pixmap.width()
            img_height = display_pixmap.height()
            bottom_height = 60
            progress_height = 52
            self.setFixedSize(img_width, img_height + progress_height + bottom_height)
        else:
            self.setFixedSize(400, 412)

    def _get_progress_stylesheet(self, styles):
        """获取进度条样式（mod色彩）"""
        slider_bg = styles.get('main_fill_color', 'rgba(30, 58, 95, 0.3)')
        slider_handle = styles.get('main_mutant_color', '#FF6B35')
        slider_border = styles.get('main_border_color', '#1E3A5F')
        groove_color = styles.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)')
        return f"""
            QSlider {{
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {slider_border};
                height: 6px;
                background: {groove_color};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {slider_handle};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {slider_handle};
                border: 1px solid {slider_border};
                width: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }}
        """

    def _get_slider_stylesheet(self, styles):
        """获取音量滑块样式"""
        slider_bg = styles.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)')
        slider_handle = styles.get('main_border_color', '#1E3A5F')
        slider_border = styles.get('main_border_color', '#1E3A5F')
        return f"""
            QSlider {{
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {slider_border};
                height: 6px;
                background: {slider_bg};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {slider_handle};
                border: 1px solid {slider_border};
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
        """

    def _get_button_stylesheet(self, styles):
        """获取音乐按钮样式"""
        fill_color = styles.get('main_fill_color', 'rgba(30, 58, 95, 0.3)')
        border_color = styles.get('main_border_color', '#1E3A5F')
        fill_alt = styles.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)')
        return f"""
            QPushButton {{
                background-color: {fill_color};
                border: 1px solid {border_color};
                border-radius: 18px;
            }}
            QPushButton:hover {{
                background-color: {fill_alt};
            }}
        """

    def _update_music_button_icon(self, is_playing):
        """更新音乐按钮图标"""
        paths = get_mod_paths()
        icon_path = paths.get('MUSIC_STOP_ICON') if is_playing else paths.get('MUSIC_PLAY_ICON')
        if icon_path and os.path.exists(icon_path):
            self.music_btn.setIcon(QIcon(icon_path))
            self.music_btn.setIconSize(QSize(32, 32))

    def _format_time(self, ms):
        """毫秒转 mm:ss 格式"""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _update_progress(self):
        """QTimer回调 - 自己累计播放位置并更新进度条（不依赖 get_pos）"""
        if self._is_seeking or self._is_paused:
            return
        # 累计播放时间（QTimer间隔约100ms）
        self._current_pos_ms += 100
        # 循环播放，超过总时长则重置
        if self._current_pos_ms >= self._music_duration_ms:
            self._current_pos_ms = 0
        # 更新进度条（不触发valueChanged信号，避免循环）
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(self._current_pos_ms)
        self.progress_slider.blockSignals(False)
        # 更新时间标签
        self.time_label.setText(
            f"{self._format_time(self._current_pos_ms)} / {self._format_time(self._music_duration_ms)}"
        )

    def _on_progress_pressed(self):
        """进度条按下 - 暂停自动更新"""
        self._is_seeking = True

    def _on_progress_released(self):
        """进度条释放 - 跳转到指定位置并恢复自动更新"""
        pos_ms = self.progress_slider.value()
        # 更新自己维护的播放位置
        self._current_pos_ms = pos_ms
        # 调用 pygame 跳转到指定位置（ogg 文件参数为秒数）
        try:
            pygame.mixer.music.set_pos(pos_ms / 1000.0)
        except Exception as e:
            print(f"跳转进度失败: {e}")
        self._is_seeking = False
        # 立即刷新时间标签
        self.time_label.setText(
            f"{self._format_time(pos_ms)} / {self._format_time(self._music_duration_ms)}"
        )

    def _on_progress_value_changed(self, value):
        """进度条值变化 - 更新时间标签"""
        if self._is_seeking:
            self.time_label.setText(
                f"{self._format_time(value)} / {self._format_time(self._music_duration_ms)}"
            )

    def _on_pause_clicked(self):
        """切换V50播放/暂停状态（供音乐按钮调用）"""
        mod_instance = global_mod_manager.get_current_mod()
        if not hasattr(mod_instance, 'global_music_player'):
            return
        player = mod_instance.global_music_player
        if self._is_paused:
            player.unpause()
            self._is_paused = False
        else:
            player.pause()
            self._is_paused = True
        # 同步音乐按钮图标
        self._update_music_button_icon(not self._is_paused)

    def _on_music_clicked(self):
        """音乐按钮点击 - 切换V50播放/暂停状态"""
        self._on_pause_clicked()

    def _on_volume_changed(self, value):
        """音量滑块变化 - 设置V50音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            player = mod_instance.global_music_player
            player.set_volume(value / 100.0)

    def showEvent(self, event):
        """显示事件 - 居中到主窗口中央"""
        super().showEvent(event)
        if self.main_window:
            main_geo = self.main_window.geometry()
            self.move(
                main_geo.center().x() - self.width() // 2,
                main_geo.center().y() - self.height() // 2
            )

    def done(self, result):
        """对话框关闭时（accept/reject/ESC/外部点击）恢复主界面音乐状态
        注意：QDialog的accept/reject不会触发closeEvent，必须重写done方法
        """
        self._restore_main_music_state()
        super().done(result)

    def closeEvent(self, event):
        """关闭事件 - 恢复主界面音乐状态（处理窗口管理器关闭按钮）"""
        self._restore_main_music_state()
        super().closeEvent(event)
