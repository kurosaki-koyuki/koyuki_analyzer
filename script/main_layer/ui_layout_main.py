# -*- coding: utf-8 -*-
"""
主界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑

使用 5 函数模组开发模型：主界面组件使用 gui_styles(variant='main')
"""

from script.utils_layer.import_config import *
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsProxyWidget, QFrame
from PyQt5.QtGui import QPainter
from script.utils_layer.utils_tools import ScalableLabel
from script.utils_layer.gui_styles import create_styled_button, create_styled_combo_box, create_styled_slider
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class MainWindowUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        styles = global_mod_manager.get_current_styles()
        
        self.setWindowTitle(styles.get('window_title', "小雪生信工具箱"))
        self.base_width = 1920
        self.base_height = 1000
        self.screen_width = self.base_width
        self.screen_height = self.base_height
        self.resize(self.screen_width, self.screen_height)
        self.move(0, 0)
        
        paths = global_mod_manager.get_current_paths()
        icon_path = os.path.join(paths['GUI_PATH'], "koyuki_machine.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.graphics_view = QGraphicsView(central_widget)
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.graphics_view.setFrameShape(QFrame.NoFrame)
        self.graphics_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        main_layout.addWidget(self.graphics_view)
        
        self.graphics_scene = QGraphicsScene()
        self.graphics_scene.setSceneRect(0, 0, self.base_width, self.base_height)
        self.graphics_view.setScene(self.graphics_scene)
        
        self.content_widget = QWidget()
        self.content_widget.setFixedSize(self.base_width, self.base_height)
        
        self.stacked_widget = QStackedWidget(self.content_widget)
        self.stacked_widget.setGeometry(0, 0, self.base_width, self.base_height)
        
        self.proxy_widget = self.graphics_scene.addWidget(self.content_widget)
        self.proxy_widget.setPos(0, 0)
        
        self._current_scale = 1.0
        
        self.create_home_page()
        page_intersect.register_page('home_page', self.home_page)
        
        page_intersect.init_all_pages(self, self.stacked_widget)
        
        self.stacked_widget.setCurrentWidget(self.home_page)
        
        QTimer.singleShot(0, self._update_scene_scale)
    
    def create_styled_button(self, text, parent=None, font_size=16, color_style='blue'):
        """
        创建主界面按钮 - 使用统一样式函数
        注意：粉色按钮(pink)是特殊样式，需要单独处理
        """
        # 粉色按钮特殊处理 - 使用突变色
        if color_style == 'pink':
            btn = QPushButton(text, parent)
            btn.setFont(QFont("幼圆", font_size, QFont.Bold))
            styles = global_mod_manager.get_current_styles()
            mutant_color = styles.get('main_mutant_color', styles.get('mutant_color', '#FF6B35'))
            btn.setStyleSheet(f"""
                QPushButton {{
                    color: {styles.get('main_text_color', '#FFB6C1')};
                    background: {styles.get('main_fill_color', 'rgba(233, 30, 99, 0.2)')};
                    border: 2px solid {mutant_color};
                    border-radius: 5px;
                    padding: 8px 20px;
                    min-width: 180px;
                    min-height: 60px;
                }}
                QPushButton:hover {{
                    background: {styles.get('main_hover_color', styles.get('main_fill_alt', 'rgba(233, 30, 99, 0.3)'))};
                }}
                QPushButton:pressed {{
                    background: {styles.get('main_active_color', 'rgba(233, 30, 99, 0.4)')};
                }}
            """)
            return btn
        
        # 普通按钮使用统一样式函数（variant='main'）
        return create_styled_button(
            text=text,
            parent=parent,
            font_size=font_size,
            variant='main'
        )
    
    def create_home_page(self):
        styles = global_mod_manager.get_current_styles()
        self.home_page = QWidget()
        self.home_page.setGeometry(0, 0, self.base_width, self.base_height)
        
        self.video_bg_label = QLabel(self.home_page)
        self.video_bg_label.setGeometry(0, 0, self.base_width, self.base_height)
        self.video_bg_label.setStyleSheet(f"background-color: {styles.get('main_fill_color', '#1a1a2e')};")
        self.video_bg_label.lower()
        
        # 使用新的主界面样式 key
        border_color = styles.get('main_border_color', '#1E3A5F')
        text_color = styles.get('main_text_color', '#87CEEB')
        fill_color = styles.get('main_fill_color', 'rgba(30, 58, 95, 0.3)')
        fill_alt = styles.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)')
        gui_font = styles.get('main_gui_font', '幼圆')
        text_font = styles.get('main_text_font', '幼圆')
        combo_radius = '3px'
        button_radius = '5px'
        
        # 副标题样式
        subtitle_font = text_font
        subtitle_font_size = styles.get('subtitle_font_size', 14)
        subtitle_color = text_color
        subtitle_background = 'transparent'
        subtitle_bold = True
        
        mod_container = QWidget(self.home_page)
        mod_container.setGeometry(
            styles.get('mod_container_x', 15),
            styles.get('mod_container_y', 15),
            styles.get('mod_container_width', 250),
            styles.get('mod_container_height', 50)
        )
        mod_container.setStyleSheet(f"background: transparent;")
        
        self.mod_label = QLabel("模组:", mod_container)
        self.mod_label.setFont(QFont(text_font, styles.get('mod_label_font_size', 12), QFont.Bold))
        self.mod_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self.mod_label.move(0, 10)
        
        # 使用统一样式函数创建下拉框
        self.mod_combo = create_styled_combo_box(mod_container, variant='main')
        self.mod_combo.move(
            styles.get('mod_combo_x', 70),
            styles.get('mod_combo_y', 5)
        )
        self.mod_combo.setFixedSize(
            styles.get('mod_combo_width', 170),
            styles.get('mod_combo_height', 30)
        )
        
        available_mods = global_mod_manager.get_available_mods()
        self.mod_combo.addItems(available_mods)
        
        current_mod = global_mod_manager.get_current_mod()
        index = self.mod_combo.findText(current_mod.mod_name)
        if index >= 0:
            self.mod_combo.setCurrentIndex(index)
        
        original_show_popup = self.mod_combo.showPopup
        def fixed_show_popup():
            saved_idx = self.mod_combo.currentIndex()
            self.mod_combo.blockSignals(True)
            self.mod_combo.setCurrentIndex(0)
            original_show_popup()
            self.mod_combo.setCurrentIndex(saved_idx)
            self.mod_combo.blockSignals(False)
        self.mod_combo.showPopup = fixed_show_popup
        
        music_container = QWidget(self.home_page)
        music_container.setGeometry(
            int(self.base_width * styles.get('music_container_x', 0.9)),
            styles.get('music_container_y', 15),
            styles.get('music_container_width', 280),
            styles.get('music_container_height', 50)
        )
        
        # 使用统一样式函数创建音量滑块
        self.volume_slider = create_styled_slider(Qt.Horizontal, music_container, variant='main')
        self.volume_slider.setGeometry(
            styles.get('volume_slider_x', 5),
            styles.get('volume_slider_y', 25),
            styles.get('volume_slider_width', 100),
            styles.get('volume_slider_height', 25)
        )
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        
        self.music_btn = QPushButton(music_container)
        self.music_btn.setFixedSize(
            styles.get('music_button_width', 40),
            styles.get('music_button_height', 40)
        )
        self.music_btn.move(
            styles.get('music_button_x', 155),
            styles.get('music_button_y', 0)
        )
        paths = global_mod_manager.get_current_paths()
        if os.path.exists(paths['MUSIC_STOP_ICON']):
            self.music_btn.setIcon(QIcon(paths['MUSIC_STOP_ICON']))
        self.music_btn.setIconSize(QSize(32, 32))
        self.music_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {fill_color};
                border: 1px solid {border_color};
                border-radius: {button_radius};
            }}
            QPushButton:hover {{
                background-color: {fill_alt};
            }}
        """)
        
        # Settings按钮 - 独立widget，位于music_container正右方
        self.settings_btn = QPushButton(self.home_page)
        self.settings_btn.setFixedSize(
            styles.get('settings_button_width', 40),
            styles.get('settings_button_height', 40)
        )
        # 位置在music_container右侧，垂直位置与music_container相同
        container_x = int(self.base_width * styles.get('music_container_x', 0.9))
        container_y = styles.get('music_container_y', 15)
        container_width = styles.get('music_container_width', 200)
        self.settings_btn.move(
            container_x + container_width + 5,
            container_y
        )
        settings_icon_path = os.path.join(paths['GUI_PATH'], "settings.ico")
        if os.path.exists(settings_icon_path):
            self.settings_btn.setIcon(QIcon(settings_icon_path))
        self.settings_btn.setIconSize(QSize(32, 32))
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {fill_color};
                border: 1px solid {border_color};
                border-radius: {button_radius};
            }}
            QPushButton:hover {{
                background-color: {fill_alt};
            }}
        """)
        
        self.title_label = QLabel(styles.get('main_title', "生信工具一览"), self.home_page)
        self.title_label.setFont(QFont(text_font, styles.get('title_font_size', 20), QFont.Bold))
        self.title_label.setStyleSheet(f"color: {styles.get('title_color', text_color)}; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setGeometry(
            int(self.base_width * styles.get('title_x', 0.65)),
            int(self.base_height * styles.get('title_y', 0.18)),
            int(self.base_width * styles.get('title_width', 0.3)),
            styles.get('title_height', 50)
        )
        
        self.left_title_label = QLabel(styles.get('single_cell_title', "单细胞分析"), self.home_page)
        self.left_title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold if subtitle_bold else QFont.Normal))
        self.left_title_label.setStyleSheet(f"color: {subtitle_color}; background: {subtitle_background};")
        self.left_title_label.setAlignment(Qt.AlignCenter)
        self.left_title_label.setGeometry(
            int(self.base_width * styles.get('left_title_x', 0.68)),
            int(self.base_height * styles.get('left_title_y', 0.28)),
            styles.get('left_title_width', 180),
            styles.get('left_title_height', 30)
        )
        
        self.right_title_label = QLabel(styles.get('bulk_title', "bulk分析"), self.home_page)
        self.right_title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold if subtitle_bold else QFont.Normal))
        self.right_title_label.setStyleSheet(f"color: {subtitle_color}; background: {subtitle_background};")
        self.right_title_label.setAlignment(Qt.AlignCenter)
        self.right_title_label.setGeometry(
            int(self.base_width * styles.get('right_title_x', 0.78)),
            int(self.base_height * styles.get('right_title_y', 0.28)),
            styles.get('right_title_width', 180),
            styles.get('right_title_height', 30)
        )
        
        btn_w = styles.get('button_width', 180)
        btn_h = styles.get('button_height', 60)
        btn_font_size = styles.get('button_font_size', 16)
        btn_start_x = int(self.base_width * styles.get('button_start_x', 0.68))
        btn_start_y = int(self.base_height * styles.get('button_start_y', 0.32))
        row_gap = int(self.base_height * styles.get('button_row_gap', 0.08))
        
        self.btn_single_cell_main = self.create_styled_button("进入单细胞分析", parent=self.home_page, font_size=btn_font_size)
        self.btn_single_cell_main.setFixedSize(btn_w, btn_h)
        self.btn_single_cell_main.move(btn_start_x, btn_start_y)
        
        right_start_x = int(self.base_width * styles.get('right_title_x', 0.78))
        self.btn_bulk_main = self.create_styled_button("进入Bulk分析", parent=self.home_page, font_size=btn_font_size)
        self.btn_bulk_main.setFixedSize(btn_w, btn_h)
        self.btn_bulk_main.move(right_start_x, btn_start_y)
        
        tools_start_x = int(self.base_width * styles.get('tools_title_x', 0.88))
        self.tools_title_label = QLabel(styles.get('tools_title', "通用小工具"), self.home_page)
        self.tools_title_label.setFont(QFont(subtitle_font, subtitle_font_size, QFont.Bold if subtitle_bold else QFont.Normal))
        self.tools_title_label.setStyleSheet(f"color: {subtitle_color}; background: {subtitle_background};")
        self.tools_title_label.setAlignment(Qt.AlignCenter)
        self.tools_title_label.setGeometry(
            tools_start_x,
            int(self.base_height * styles.get('tools_title_y', 0.28)),
            styles.get('tools_title_width', 180),
            styles.get('tools_title_height', 30)
        )
        
        self.btn_venn = self.create_styled_button("韦恩图交集", parent=self.home_page, font_size=btn_font_size)
        self.btn_venn.setFixedSize(btn_w, btn_h)
        self.btn_venn.move(tools_start_x, btn_start_y)
        
        self.btn_donate = QPushButton("打赏作者", self.home_page)
        self.btn_donate.setFont(QFont(styles.get('label_font', "幼圆"), 14, QFont.Bold))
        donate_color = styles.get('main_mutant_color', styles.get('mutant_color', '#FF6B35'))
        btn_radius = styles.get('button_border_radius', '5px')
        self.btn_donate.setStyleSheet(f"""
            QPushButton {{
                color: white;
                background: {donate_color};
                border: 3px solid {donate_color};
                border-radius: {btn_radius};
                min-width: 150px;
                min-height: 40px;
            }}
            QPushButton:hover {{
                background: {styles.get('main_hover_color', '#D62839')};
            }}
        """)
        self.btn_donate.move(
            int(self.base_width * styles.get('donate_button_x', 0.725)),
            int(self.base_height * styles.get('donate_button_y', 0.80))
        )
        
        self.stacked_widget.addWidget(self.home_page)
    
    def update_button_positions(self, styles):
        """更新所有按钮位置 - 位置布局逻辑统一放在layout层"""
        btn_start_x = int(self.base_width * styles.get('button_start_x', 0.68))
        btn_start_y = int(self.base_height * styles.get('button_start_y', 0.32))
        row_gap = int(self.base_height * styles.get('button_row_gap', 0.08))
        right_start_x = int(self.base_width * styles.get('right_title_x', 0.78))
        tools_start_x = int(self.base_width * styles.get('tools_title_x', 0.88))
        
        buttons = [
            ('btn_single_cell_main', btn_start_x, btn_start_y),
            ('btn_bulk_main', right_start_x, btn_start_y),
            ('btn_venn', tools_start_x, btn_start_y),
        ]
        
        for btn_name, x, y in buttons:
            if hasattr(self, btn_name):
                getattr(self, btn_name).move(x, y)
    
    def go_to_home_page(self):
        """返回主页"""
        if hasattr(self, 'home_page') and self.home_page:
            self.stacked_widget.setCurrentWidget(self.home_page)
    
    def _update_scene_scale(self):
        """更新场景缩放比例，使内容适应视图大小"""
        try:
            view_width = self.graphics_view.width()
            view_height = self.graphics_view.height()
            
            if view_width <= 0 or view_height <= 0:
                return
            
            scale_x = view_width / self.base_width
            scale_y = view_height / self.base_height
            scale = min(scale_x, scale_y)
            
            self._current_scale = scale
            
            self.graphics_view.resetTransform()
            self.graphics_view.scale(scale, scale)
            
            self.screen_width = int(self.base_width * scale)
            self.screen_height = int(self.base_height * scale)
        except Exception as e:
            print(f"更新场景缩放失败: {e}")
    
    def resizeEvent(self, event):
        """窗口大小改变时重新计算缩放"""
        super().resizeEvent(event)
        self._update_scene_scale()
    
    def showEvent(self, event):
        """窗口显示时重新计算缩放"""
        super().showEvent(event)
        self._update_scene_scale()
