# -*- coding: utf-8 -*-
"""
bulk免疫分析弹窗 - 模态无标题栏，居中于主窗口
标题行 + 按钮区域（每3个按钮另起一行）+ 关闭按钮行
点击按钮跳转到对应子界面

继承 StyledDialog 基类，样式由 gui_styles 统一管理（mod色彩、居中、音效）
"""

from script.utils_layer.import_config import (
    os, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    Qt, QWidget
)
from script.utils_layer.gui_styles import (
    StyledDialog, get_dialog_close_button_stylesheet,
    get_font_for_widget, create_styled_button, get_mod_styles
)
from script.utils_layer.page_intersect import page_intersect


class ImmuneDialog(StyledDialog):
    """bulk免疫分析弹窗 - 显示功能按钮，点击跳转到对应子界面"""

    def __init__(self, main_window):
        super().__init__(main_window, variant='sub', fixed_size=(500, 250))

    def _build_ui(self):
        """构建弹窗UI"""
        styles = get_mod_styles()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # === 标题行 ===
        title_label = QLabel("bulk免疫分析", self)
        title_label.setObjectName("immune_dialog_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_color = styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))
        title_label.setStyleSheet(f"color: {title_color}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # === 按钮区域（网格布局，每3个按钮一行）===
        button_widget = QWidget(self)
        button_layout = QGridLayout(button_widget)
        button_layout.setSpacing(10)
        button_layout.setAlignment(Qt.AlignCenter)

        btn_font_size = styles.get('button_font_size', 14)

        # 功能按钮列表（后续会扩展）
        self._buttons = []
        button_configs = [
            {'text': 'ESTIMATE分析', 'page': 'bulk_immune_estimate_page'},
        ]

        for i, config in enumerate(button_configs):
            btn = create_styled_button(config['text'], font_size=btn_font_size)
            btn.clicked.connect(lambda checked, p=config['page']: self._on_button_clicked(p))
            row = i // 3
            col = i % 3
            button_layout.addWidget(btn, row, col)
            self._buttons.append(btn)

        layout.addWidget(button_widget)

        # === 关闭按钮行 ===
        close_btn = QPushButton("关闭", self)
        close_btn.setFont(get_font_for_widget('button', 12))
        close_btn.setStyleSheet(get_dialog_close_button_stylesheet('sub'))
        close_btn.clicked.connect(self.accept)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        close_layout.addStretch()
        layout.addLayout(close_layout)

    def _on_button_clicked(self, page_name):
        """功能按钮点击 - 关闭弹窗并跳转到对应子界面"""
        self.accept()
        page_intersect.go_to_page_with_bind(page_name)
