# -*- coding: utf-8 -*-
"""
通用GUI样式工具函数
提供统一的样式获取和控件创建方法，供所有子界面使用
使用三层架构：色板→语义→控件，通过 variant 参数区分主/子界面
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from PyQt5.QtWidgets import QDialog

# 统一字体家族 - 英文优先 Arial，中文 fallback 幼圆
# 切换 mod 时字体保持不变，只改颜色搭配
_UNIFIED_FONT_FAMILIES = ["Arial", "幼圆"]

def get_unified_font(size=11, bold=False):
    """统一字体函数 - 英文优先 Arial，中文 fallback 幼圆。
    切换 mod 时字体保持不变，避免控件 sizeHint 变化导致出界。
    """
    font = QFont()
    font.setFamilies(_UNIFIED_FONT_FAMILIES)
    font.setPointSize(size)
    if bold:
        font.setBold(True)
    return font

def get_mod_styles():
    """获取当前模组的样式配置"""
    return global_mod_manager.get_current_styles()

def get_mod_paths():
    """获取当前模组的路径配置"""
    return global_mod_manager.get_current_paths()

def create_styled_label(text, font_size=12, bold=True, parent=None, variant='sub'):
    """创建样式化的标签"""
    s = get_mod_styles()
    label = QLabel(text, parent)

    label.setFont(get_unified_font(font_size, bold))
    
    text_color = s.get(f'{variant}_text_primary', '#87CEEB')
    label.setStyleSheet(f"""
        color: {text_color};
        background: transparent;
    """)
    
    return label

def create_styled_button(text, font_size=14, parent=None, bold=True, variant='sub', button_type='normal'):
    """创建样式化的按钮"""
    s = get_mod_styles()
    btn = QPushButton(text, parent)

    btn.setFont(get_unified_font(font_size, bold))
    
    btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    
    btn.setObjectName(f'styled_btn_{button_type}')
    
    if button_type in ['import', 'run', 'export']:
        btn.setStyleSheet(get_stylesheet_for_widget(f'{button_type}_button'))
    elif variant == 'main':
        from script.utils_layer.gui_styles import get_main_gui_styles
        main_styles = get_main_gui_styles()
        btn.setStyleSheet(main_styles['button_stylesheet'])
    else:
        button_text = s.get(f'{variant}_button_text', '#87CEEB')
        button_bg = s.get(f'{variant}_button_bg', 'rgba(30, 58, 95, 0.3)')
        button_border = s.get(f'{variant}_button_border', '#1E3A5F')
        button_hover_bg = s.get(f'{variant}_button_hover_bg', 'rgba(30, 58, 95, 0.5)')
        button_pressed_bg = s.get(f'{variant}_button_pressed_bg', 'rgba(135, 206, 235, 0.4)')
        button_radius = s.get(f'{variant}_button_radius', '5px')
        
        btn.setStyleSheet(f"""
            QPushButton {{
                color: {button_text};
                background: {button_bg};
                border: 2px solid {button_border};
                border-radius: {button_radius};
                padding: 5px 15px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background: {button_hover_bg};
            }}
            QPushButton:pressed {{
                background: {button_pressed_bg};
            }}
        """)
    
    return btn

def create_styled_combo_box(parent=None, fixed_height=None, variant='sub'):
    """创建样式化的下拉框"""
    s = get_mod_styles()
    combo = QComboBox(parent)

    combo.setFont(get_unified_font(11))
    
    # 设置默认高度
    if fixed_height is None:
        fixed_height = s.get(f'{variant}_combo_default_height', 22)
    if fixed_height:
        combo.setFixedHeight(fixed_height)
    
    # 直接使用新架构 key
    combo_text = s.get(f'{variant}_combo_text', '#87CEEB')
    combo_bg = s.get(f'{variant}_combo_bg', 'rgba(30, 58, 95, 0.3)')
    combo_border = s.get(f'{variant}_combo_border', '#1E3A5F')
    combo_radius = s.get(f'{variant}_combo_radius', '3px')
    combo_dropdown_text = s.get(f'{variant}_combo_dropdown_text', combo_text)
    combo_dropdown_bg = s.get(f'{variant}_combo_dropdown_bg', 'rgba(30, 58, 95, 0.6)')
    selection_color = s.get(f'{variant}_selection_color', 'rgba(135, 206, 235, 0.3)')
    
    combo.setStyleSheet(f"""
        QComboBox {{
            color: {combo_text};
            background: {combo_bg};
            border: 1px solid {combo_border};
            border-radius: {combo_radius};
            padding: 3px;
        }}
        QComboBox::drop-down {{
            border-left: 1px solid {combo_border};
        }}
        QComboBox QAbstractItemView {{
            color: {combo_dropdown_text};
            background: {combo_dropdown_bg};
            selection-background-color: {selection_color};
        }}
    """)
    
    return combo

def create_styled_line_edit(parent=None, fixed_height=None, fixed_width=None, variant='sub'):
    """创建样式化的输入框"""
    s = get_mod_styles()
    line_edit = QLineEdit(parent)

    line_edit.setFont(get_unified_font(11))
    
    # 设置默认高度
    if fixed_height is None:
        fixed_height = s.get(f'{variant}_input_default_height', 28)
    if fixed_height:
        line_edit.setFixedHeight(fixed_height)
    
    # 设置固定宽度
    if fixed_width:
        line_edit.setFixedWidth(fixed_width)
    
    # 直接使用新架构 key
    input_text = s.get(f'{variant}_input_text', '#87CEEB')
    input_bg = s.get(f'{variant}_input_bg', 'rgba(30, 58, 95, 0.3)')
    input_border = s.get(f'{variant}_input_border', '#1E3A5F')
    input_focus_border = s.get(f'{variant}_input_focus_border', '#87CEEB')
    input_radius = s.get(f'{variant}_input_radius', '3px')
    
    line_edit.setStyleSheet(f"""
        QLineEdit {{
            color: {input_text};
            background: {input_bg};
            border: 1px solid {input_border};
            border-radius: {input_radius};
            padding: 3px 8px;
        }}
        QLineEdit:focus {{
            border-color: {input_focus_border};
        }}
    """)
    
    return line_edit

def create_styled_text_edit(parent=None, read_only=False, variant='sub'):
    """创建样式化的文本编辑框"""
    s = get_mod_styles()
    text_edit = QTextEdit(parent)

    text_edit.setFont(get_unified_font(11))
    
    # 直接使用新架构 key
    input_text = s.get(f'{variant}_input_text', '#87CEEB')
    input_bg = s.get(f'{variant}_input_bg', 'rgba(30, 58, 95, 0.3)')
    input_border = s.get(f'{variant}_input_border', '#1E3A5F')
    input_radius = s.get(f'{variant}_input_radius', '3px')
    
    if read_only:
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                color: {input_text};
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: {input_radius};
                padding: 5px 8px;
            }}
        """)
    else:
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                color: {input_text};
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: {input_radius};
                padding: 5px 8px;
            }}
            QTextEdit:focus {{
                border-color: {s.get(f'{variant}_input_focus_border', '#87CEEB')};
            }}
        """)
    
    return text_edit


def create_styled_slider(orientation, parent=None, variant='sub'):
    """创建样式化的滑块"""
    s = get_mod_styles()
    slider = QSlider(orientation, parent)
    
    # 直接使用新架构 key
    slider_bg = s.get(f'{variant}_slider_bg', 'rgba(30, 58, 95, 0.4)')
    slider_handle = s.get(f'{variant}_slider_handle', '#1E3A5F')
    slider_handle_hover = s.get(f'{variant}_slider_handle_hover', '#2E4A6F')
    slider_border = s.get(f'{variant}_border_default', '#1E3A5F')
    
    slider.setStyleSheet(f"""
        QSlider {{
            background: transparent;
        }}
        QSlider::groove:horizontal {{
            border: 1px solid {slider_border};
            height: 8px;
            background: {slider_bg};
            border-radius: 4px;
        }}
        QSlider::handle:horizontal {{
            background: {slider_handle};
            border: 1px solid {slider_border};
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {slider_handle_hover};
        }}
    """)
    
    return slider

def create_styled_checkbox(text="", parent=None, fixed_height=None, variant='sub'):
    """创建样式化的复选框"""
    s = get_mod_styles()
    checkbox = QCheckBox(text, parent)

    font_size = s.get(f'{variant}_checkbox_font_size', s.get('text_font_size', 9))
    checkbox.setFont(get_unified_font(font_size))
    
    # 不设置固定高度，让复选框自适应内容高度
    checkbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    
    checkbox.setStyleSheet(get_stylesheet_for_widget('checkbox', variant))
    
    return checkbox


class StyledNumberInput(QWidget):
    """自定义数字输入框控件（带上下调按钮）"""
    
    def __init__(self, parent=None, min_value=0, max_value=100, default_value=0, 
                 fixed_height=None, variant='sub'):
        super().__init__(parent)
        
        s = get_mod_styles()

        # 从style模板获取所有样式参数
        input_text = s.get(f'{variant}_input_text', '#87CEEB')
        input_bg = s.get(f'{variant}_input_bg', 'rgba(30, 58, 95, 0.3)')
        input_border = s.get(f'{variant}_input_border', '#1E3A5F')
        input_radius = s.get(f'{variant}_input_radius', '3px')
        button_bg = s.get(f'{variant}_input_bg', 'rgba(30, 58, 95, 0.3)')
        button_hover = s.get(f'{variant}_bg_pressed', 'rgba(135, 206, 235, 0.3)')
        button_border = s.get(f'{variant}_input_border', '#1E3A5F')
        button_radius = s.get(f'{variant}_input_radius', '3px')
        arrow_color = s.get(f'{variant}_input_text', '#87CEEB')
        
        # 从style模板获取按钮宽度
        button_width = s.get(f'{variant}_spinbox_button_width', 18)
        
        # 设置默认高度
        if fixed_height is None:
            fixed_height = s.get(f'{variant}_input_default_height', 28)
        
        self.min_value = min_value
        self.max_value = max_value
        self.current_value = default_value
        
        # 创建主水平布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(1)
        
        # 创建输入框
        self.line_edit = QLineEdit()
        self.line_edit.setFont(get_unified_font(10))
        self.line_edit.setText(str(default_value))
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.setFixedHeight(fixed_height)
        self.line_edit.setStyleSheet(f"""
            QLineEdit {{
                color: {input_text};
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: {input_radius};
                padding: 0px 4px;
            }}
            QLineEdit:focus {{
                border: 1px solid {arrow_color};
            }}
        """)
        
        # 创建按钮容器（宽度从模板获取）
        btn_container = QWidget()
        btn_container.setFixedWidth(button_width)
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(0)
        
        # 计算按钮高度（上下按钮各占一半）
        btn_height = fixed_height // 2
        
        # 创建上调按钮（向上箭头）
        self.up_button = QPushButton()
        self.up_button.setObjectName("number_input_btn_up")
        self.up_button.setFixedSize(button_width, btn_height)
        self.up_button.setText("▲")
        self.up_button.setStyleSheet(f"""
            QPushButton {{
                color: {arrow_color};
                background: {button_bg};
                border: 1px solid {button_border};
                border-bottom: none;
                border-top-left-radius: {button_radius};
                border-top-right-radius: {button_radius};
            }}
            QPushButton:hover {{
                background: {button_hover};
            }}
        """)
        font = get_unified_font(8)
        self.up_button.setFont(font)
        
        # 创建下调按钮（向下箭头）
        self.down_button = QPushButton()
        self.down_button.setObjectName("number_input_btn_down")
        self.down_button.setFixedSize(button_width, btn_height)
        self.down_button.setText("▼")
        self.down_button.setStyleSheet(f"""
            QPushButton {{
                color: {arrow_color};
                background: {button_bg};
                border: 1px solid {button_border};
                border-top: none;
                border-bottom-left-radius: {button_radius};
                border-bottom-right-radius: {button_radius};
            }}
            QPushButton:hover {{
                background: {button_hover};
            }}
        """)
        self.down_button.setFont(font)
        
        btn_layout.addWidget(self.up_button)
        btn_layout.addWidget(self.down_button)
        
        main_layout.addWidget(self.line_edit)
        main_layout.addWidget(btn_container)
        
        # 连接信号
        self.up_button.clicked.connect(self._on_increase)
        self.down_button.clicked.connect(self._on_decrease)
        self.line_edit.editingFinished.connect(self._on_text_changed)
    
    def _on_increase(self):
        """增加数值"""
        new_value = min(self.current_value + 1, self.max_value)
        self.setValue(new_value)
    
    def _on_decrease(self):
        """减少数值"""
        new_value = max(self.current_value - 1, self.min_value)
        self.setValue(new_value)
    
    def _on_text_changed(self):
        """文本变化时验证并更新"""
        try:
            value = int(self.line_edit.text())
            if self.min_value <= value <= self.max_value:
                self.current_value = value
            else:
                self.line_edit.setText(str(self.current_value))
        except ValueError:
            self.line_edit.setText(str(self.current_value))
    
    def value(self):
        """获取当前值"""
        return self.current_value
    
    def setValue(self, value):
        """设置值"""
        self.current_value = max(self.min_value, min(value, self.max_value))
        self.line_edit.setText(str(self.current_value))
    
    def setRange(self, min_val, max_val):
        """设置范围"""
        self.min_value = min_val
        self.max_value = max_val
        if self.current_value < min_val:
            self.setValue(min_val)
        elif self.current_value > max_val:
            self.setValue(max_val)


def create_styled_number_input(parent=None, fixed_height=None, min_value=0, max_value=100, default_value=0, variant='sub'):
    """创建样式化的数字输入框（带上下调按钮）
    
    弃用create_styled_spinbox，改用自定义控件
    """
    return StyledNumberInput(
        parent=parent,
        min_value=min_value,
        max_value=max_value,
        default_value=default_value,
        fixed_height=fixed_height,
        variant=variant
    )


# 兼容旧接口
def create_styled_spinbox(parent=None, fixed_height=None, min_value=0, max_value=100, default_value=0, variant='sub'):
    """创建样式化的数字输入框（兼容旧接口，内部使用StyledNumberInput）"""
    return create_styled_number_input(
        parent=parent,
        fixed_height=fixed_height,
        min_value=min_value,
        max_value=max_value,
        default_value=default_value,
        variant=variant
    )

def create_styled_list_widget(parent=None, fixed_height=None, multi_selection=False, selection_mode=None, variant='sub'):
    """创建样式化的列表控件"""
    s = get_mod_styles()
    list_widget = QListWidget(parent)

    list_widget.setFont(get_unified_font(9))
    
    # 设置默认高度
    if fixed_height is None:
        fixed_height = s.get(f'{variant}_list_widget_default_height', 100)
    if fixed_height:
        list_widget.setMaximumHeight(fixed_height)
    
    # 设置选择模式
    if selection_mode is not None:
        list_widget.setSelectionMode(selection_mode)
    elif multi_selection:
        list_widget.setSelectionMode(QListWidget.MultiSelection)
    
    # 直接使用新架构 key
    list_text = s.get(f'{variant}_list_text', '#87CEEB')
    list_bg = s.get(f'{variant}_list_bg', 'rgba(30, 58, 95, 0.3)')
    list_border = s.get(f'{variant}_list_border', '#1E3A5F')
    list_selected_bg = s.get(f'{variant}_list_item_selected_bg', 'rgba(135, 206, 235, 0.3)')
    list_radius = s.get(f'{variant}_radius_sm', '3px')
    
    list_widget.setStyleSheet(f"""
        QListWidget {{
            color: {list_text};
            background: {list_bg};
            border: 1px solid {list_border};
            border-radius: {list_radius};
        }}
        QListWidget::item {{
            padding: 2px;
        }}
        QListWidget::item:selected {{
            background: {list_selected_bg};
        }}
    """)
    
    return list_widget

def create_styled_table(parent=None, variant='sub'):
    """创建样式化的表格控件
    
    样式表只负责：边框、选中态、悬停态、表头。
    交替行和字体色由调用方在填充数据时显式设置，避免 Qt 样式表
    的 alternate-background-color 与半透明色混合导致亮度异常，
    同时避免 setForeground 与样式表 color 属性冲突导致字体变黑。
    """
    s = get_mod_styles()
    table = QTableWidget(parent)

    table_border = s.get(f'{variant}_border_color', '#1E3A5F')
    table_text = s.get(f'{variant}_text_color', '#87CEEB')
    table_selection = s.get(f'{variant}_active_color',
                            s.get(f'{variant}_fill_alt', 'rgba(135, 206, 235, 0.3)'))
    table_header_bg = s.get(f'{variant}_fill_alt',
                            s.get(f'{variant}_fill_color', 'rgba(30, 58, 95, 0.8)'))
    table_hover = s.get(f'{variant}_hover_color',
                        s.get(f'{variant}_fill_alt', 'rgba(30, 58, 95, 0.4)'))

    table.setFont(get_font_for_widget('label', 9))

    # 样式表不设置 item 默认背景/颜色，完全交给 bind 层控制
    table.setStyleSheet(f"""
        QTableWidget {{
            border: 1px solid {table_border};
            gridline-color: {table_border};
        }}
        QTableWidget::item {{
            padding: 3px;
        }}
        QTableWidget::item:selected {{
            background: {table_selection};
        }}
        QTableWidget::item:hover {{
            background: {table_hover};
        }}
        QHeaderView::section {{
            color: {table_text};
            background: {table_header_bg};
            border: 1px solid {table_border};
            padding: 5px;
            font-weight: bold;
        }}
    """)

    # 禁用 Qt 内置交替行，由 bind 层显式控制
    table.setAlternatingRowColors(False)

    # 只选中单个单元格
    table.setSelectionBehavior(QAbstractItemView.SelectItems)
    table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)
    table.setSortingEnabled(True)

    return table


class EditableInputTable(QTableWidget):
    """可编辑输入表格类 - 封装表格自身所有功能，支持在不同界面复用
    
    功能：
    - 撤销/重做（最多50步）
    - 复制/剪切/粘贴（支持Excel格式）
    - Delete键删除选中内容
    - 行列数动态调整
    """

    def __init__(self, parent=None, variant='sub', row_count=5000, col_count=30):
        super().__init__(parent)
        
        self.variant = variant
        self.undo_stack = []
        self.max_undo = 50
        self._key_press_handler = None
        
        self._setup_table(row_count, col_count)

    def _setup_table(self, row_count, col_count):
        """初始化表格设置"""
        s = get_mod_styles()
        
        self.setRowCount(row_count)
        self.setColumnCount(col_count)
        self.setFont(get_font_for_widget('label', 9))

        table_border = s.get(f'{self.variant}_border_color', '#1E3A5F')
        table_text = s.get(f'{self.variant}_text_color', '#87CEEB')
        table_bg = s.get(f'{self.variant}_fill_color', 'rgba(30, 58, 95, 0.4)')
        table_fill_alt = s.get(f'{self.variant}_fill_alt', 'rgba(30, 58, 95, 0.5)')
        table_selection = s.get(f'{self.variant}_active_color', 'rgba(135, 206, 235, 0.3)')
        table_header_bg = s.get(f'{self.variant}_fill_alt', 'rgba(30, 58, 95, 0.7)')
        table_header_bold_bg = s.get(f'{self.variant}_fill_color', 'rgba(30, 58, 95, 0.5)')

        self._table_fill_color = table_bg
        self._table_fill_alt = table_fill_alt
        self._table_text_color = table_text

        self.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {table_border};
                gridline-color: {table_border};
            }}
            QTableWidget::item {{
                padding: 3px;
                border-bottom: 1px solid {table_border};
            }}
            QTableWidget::item:selected {{
                background: {table_selection};
            }}
            QHeaderView::section {{
                color: {table_text};
                background: {table_header_bg};
                border: 1px solid {table_border};
                padding: 4px;
                font-weight: bold;
            }}
            QTableWidget QHeaderView::section:horizontal {{
                background: {table_header_bg};
            }}
            QTableWidget QHeaderView::section:vertical {{
                background: {table_header_bold_bg};
            }}
        """)

        self.setAlternatingRowColors(False)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed)
        
        self.horizontalHeader().setVisible(True)
        self.horizontalHeader().setSectionsClickable(True)
        self.verticalHeader().setVisible(True)
        self.verticalHeader().setSectionsClickable(True)
        
        self.itemChanged.connect(self._on_item_changed)
        
        self._apply_row_colors()
        self.save_undo_state()

    def _on_item_changed(self, item):
        """单元格内容变化后重新设置颜色"""
        row = item.row()
        col = item.column()
        
        fill_color = self._parse_color(self._table_fill_color)
        fill_alt = self._parse_color(self._table_fill_alt)
        text_color = self._parse_color(self._table_text_color)
        
        row_bg = fill_alt if (row % 2 == 0) else fill_color
        item.setBackground(row_bg)
        item.setForeground(text_color)

    def _parse_color(self, color_str):
        """解析颜色字符串为QColor"""
        if isinstance(color_str, QColor):
            return color_str
        if color_str.startswith('#'):
            return QColor(color_str)
        if color_str.startswith('rgba'):
            import re
            match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
            if match:
                r, g, b, a = match.groups()
                return QColor(int(r), int(g), int(b), int(float(a) * 255))
        return QColor(color_str)

    def _apply_row_colors(self):
        """手动应用交替行颜色，避免Qt样式表的alternate-background-color与半透明色混合导致亮度异常"""
        fill_color = self._parse_color(self._table_fill_color)
        fill_alt = self._parse_color(self._table_fill_alt)
        text_color = self._parse_color(self._table_text_color)

        for row in range(self.rowCount()):
            row_bg = fill_alt if (row % 2 == 0) else fill_color
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    self.setItem(row, col, item)
                item.setBackground(row_bg)
                item.setForeground(text_color)

    def set_key_press_handler(self, handler):
        """设置自定义键盘事件处理函数"""
        self._key_press_handler = handler

    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._handle_enter_key()
            return
        
        if self._key_press_handler is not None:
            self._key_press_handler(event)
        else:
            super().keyPressEvent(event)

    def _handle_enter_key(self):
        """处理Enter键：移动到下一行同一列"""
        current_row = self.currentRow()
        current_col = self.currentColumn()
        
        if current_row < self.rowCount() - 1:
            next_row = current_row + 1
            self.setCurrentCell(next_row, current_col)
            self.editItem(self.item(next_row, current_col))

    def save_undo_state(self):
        """保存当前表格状态用于撤销"""
        state = []
        for row in range(self.rowCount()):
            row_data = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                row_data.append(item.text() if item else "")
            state.append(row_data)
        
        self.undo_stack.append(state)
        
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

    def undo(self):
        """撤销上一步操作"""
        if len(self.undo_stack) <= 1:
            return False
        
        self.undo_stack.pop()
        state = self.undo_stack[-1]
        
        for row, row_data in enumerate(state):
            for col, text in enumerate(row_data):
                if row < self.rowCount() and col < self.columnCount():
                    self.setItem(row, col, QTableWidgetItem(text))
        
        return True

    def clear_table(self):
        """清空表格数据"""
        self.save_undo_state()
        
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                self.setItem(row, col, QTableWidgetItem(""))

    def apply_params(self, new_rows, new_cols):
        """应用表格参数（行列数）"""
        old_rows = self.rowCount()
        old_cols = self.columnCount()
        
        if old_rows == new_rows and old_cols == new_cols:
            return 0
        
        old_data = []
        for row in range(old_rows):
            row_data = []
            for col in range(old_cols):
                item = self.item(row, col)
                row_data.append(item.text() if item else "")
            old_data.append(row_data)
        
        self.save_undo_state()
        
        self.setRowCount(new_rows)
        self.setColumnCount(new_cols)
        
        restore_count = 0
        for row_idx in range(min(len(old_data), new_rows)):
            for col_idx in range(min(len(old_data[row_idx]), new_cols)):
                cell_text = old_data[row_idx][col_idx]
                if cell_text:
                    self.setItem(row_idx, col_idx, QTableWidgetItem(cell_text))
                    restore_count += 1
        
        self._apply_row_colors()
        
        return restore_count

    def copy_selection(self):
        """复制选中的单元格内容到剪贴板"""
        selected_items = self.selectedItems()
        if not selected_items:
            return ""
        
        rows = sorted(set(item.row() for item in selected_items))
        cols = sorted(set(item.column() for item in selected_items))
        
        if len(rows) == 1 and len(cols) >= self.columnCount():
            row = rows[0]
            row_data = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                row_data.append(item.text() if item else "")
            clipboard_text = '\t'.join(row_data)
        else:
            copy_text = []
            for row in rows:
                row_data = []
                for col in cols:
                    item = self.item(row, col)
                    row_data.append(item.text() if item else "")
                copy_text.append('\t'.join(row_data))
            clipboard_text = '\n'.join(copy_text)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(clipboard_text)
        
        return clipboard_text

    def cut_selection(self):
        """剪切选中的单元格内容到剪贴板"""
        selected_items = self.selectedItems()
        if not selected_items:
            return ""
        
        self.save_undo_state()
        
        rows = sorted(set(item.row() for item in selected_items))
        cols = sorted(set(item.column() for item in selected_items))
        
        if len(rows) == 1 and len(cols) >= self.columnCount():
            row = rows[0]
            row_data = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                row_data.append(item.text() if item else "")
                self.setItem(row, col, QTableWidgetItem(""))
            clipboard_text = '\t'.join(row_data)
        else:
            copy_text = []
            for row in rows:
                row_data = []
                for col in cols:
                    item = self.item(row, col)
                    if item:
                        row_data.append(item.text())
                        self.setItem(row, col, QTableWidgetItem(""))
                    else:
                        row_data.append("")
                        self.setItem(row, col, QTableWidgetItem(""))
                copy_text.append('\t'.join(row_data))
            clipboard_text = '\n'.join(copy_text)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(clipboard_text)
        
        return clipboard_text

    def paste_from_clipboard(self):
        """从剪贴板粘贴数据到表格（支持Excel复制）"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return 0
        
        clipboard_rows = text.split('\n')
        if not clipboard_rows:
            return 0
        
        self.save_undo_state()
        
        current_row = self.currentRow()
        current_col = self.currentColumn()
        
        if current_row < 0:
            current_row = 0
        if current_col < 0:
            current_col = 0
        
        pasted_count = 0
        
        if '\n' not in text.rstrip('\r'):
            cells = clipboard_rows[0].rstrip('\r').split('\t')
            for col_idx, cell_text in enumerate(cells):
                target_col = current_col + col_idx
                if target_col >= self.columnCount():
                    break
                cell_text = cell_text.strip('\r')
                self.setItem(current_row, target_col, QTableWidgetItem(cell_text))
                pasted_count += 1
        else:
            for row_idx, row_text in enumerate(clipboard_rows):
                row_text = row_text.rstrip('\r')
                if not row_text:
                    cells = []
                else:
                    cells = row_text.split('\t')
                
                for col_idx, cell_text in enumerate(cells):
                    target_row = current_row + row_idx
                    target_col = current_col + col_idx
                    
                    if target_row >= self.rowCount() or target_col >= self.columnCount():
                        continue
                    
                    cell_text = cell_text.strip('\r')
                    self.setItem(target_row, target_col, QTableWidgetItem(cell_text))
                    pasted_count += 1
        
        return pasted_count

    def delete_selected(self):
        """删除选中的单元格内容"""
        selected_items = self.selectedItems()
        if not selected_items:
            return 0
        
        self.save_undo_state()
        
        rows_selected = sorted(set(item.row() for item in selected_items))
        cols_selected = sorted(set(item.column() for item in selected_items))
        
        is_full_row = (len(cols_selected) == self.columnCount())
        is_full_col = (len(rows_selected) == self.rowCount())
        
        if is_full_row and len(rows_selected) == 1:
            target_row = rows_selected[0]
            for col in range(self.columnCount()):
                self.setItem(target_row, col, QTableWidgetItem(""))
            return self.columnCount()
        elif is_full_col and len(cols_selected) == 1:
            target_col = cols_selected[0]
            for row in range(self.rowCount()):
                self.setItem(row, target_col, QTableWidgetItem(""))
            return self.rowCount()
        else:
            for item in selected_items:
                self.setItem(item.row(), item.column(), QTableWidgetItem(""))
            return len(selected_items)


def create_editable_input_table(parent=None, variant='sub', row_count=5000, col_count=30):
    """创建可编辑的输入表格控件（专门用于韦恩图等需要用户输入大量数据的场景）
    
    特性：
    - 支持大量行列数据输入（默认5000行×30列）
    - 双击编辑模式
    - 启用交替行颜色
    - 启用行和列标题点击选择
    - ExtendedSelection模式支持多选
    - 表头可见且可点击
    
    与create_styled_table的区别：
    - 本函数创建的表格是可编辑的，用于用户输入数据
    - create_styled_table创建的表格主要用于数据展示，编辑由bind层控制
    """
    return EditableInputTable(parent, variant, row_count, col_count)

def create_styled_panel(parent=None, fixed_width=None, variant='sub'):
    """创建样式化的面板容器"""
    s = get_mod_styles()
    panel = QWidget(parent)
    
    if fixed_width:
        panel.setFixedWidth(fixed_width)
    
    panel.setObjectName(f"styled_panel_{uuid.uuid4().hex[:8]}")
    
    # 直接使用新架构 key
    panel_bg = s.get(f'{variant}_panel_bg', 'rgba(30, 58, 95, 0.5)')
    panel_border = s.get(f'{variant}_panel_border', '#1E3A5F')
    panel_radius = s.get(f'{variant}_panel_radius', '8px')
    panel_padding = s.get(f'{variant}_panel_padding', 10)
    
    panel.setStyleSheet(f"""
        background: {panel_bg};
        border: 1px solid {panel_border};
        border-radius: {panel_radius};
    """)
    
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(panel_padding, panel_padding, panel_padding, panel_padding)
    
    return panel, layout

def create_styled_group_box(title, parent=None, variant='sub'):
    """创建样式化的分组框"""
    s = get_mod_styles()
    group_box = QGroupBox(title, parent)

    group_box.setFont(get_unified_font(12, bold=True))
    
    # 直接使用新架构 key
    group_text = s.get(f'{variant}_group_text', '#87CEEB')
    group_bg = s.get(f'{variant}_group_bg', 'rgba(30, 58, 95, 0.3)')
    group_border = s.get(f'{variant}_group_border', '#1E3A5F')
    group_title_bg = s.get(f'{variant}_group_title_bg', 'rgba(30, 58, 95, 0.6)')
    group_radius = s.get(f'{variant}_group_radius', '8px')
    
    group_box.setStyleSheet(f"""
        QGroupBox {{
            color: {group_text};
            background: {group_bg};
            border: 2px solid {group_border};
            border-radius: {group_radius};
            padding-top: 20px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            background: {group_title_bg};
            border-radius: 3px;
        }}
    """)
    
    return group_box


def create_styled_frame(parent=None, variant='sub'):
    """创建样式化的框架容器"""
    s = get_mod_styles()
    frame = QFrame(parent)
    
    frame.setObjectName(f"styled_frame_{uuid.uuid4().hex[:8]}")
    
    frame_bg = s.get(f'{variant}_fill_color', 'rgba(30, 58, 95, 0.3)')
    frame_border = s.get(f'{variant}_border_color', '#1E3A5F')
    frame_radius = s.get(f'{variant}_panel_radius', '5px')
    frame_padding = s.get(f'{variant}_panel_padding', 5)
    
    frame.setStyleSheet(f"""
        background: {frame_bg};
        border: 1px solid {frame_border};
        border-radius: {frame_radius};
        padding: {frame_padding}px;
    """)
    
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(frame_padding, frame_padding, frame_padding, frame_padding)
    
    return frame, layout


def create_styled_tab_widget(parent=None, variant='sub', movable=False, document_mode=False):
    """创建样式化的标签页控件
    
    Args:
        parent: 父控件
        variant: 样式变体 ('main' 或 'sub')
        movable: 是否支持拖动标签页重新排序
        document_mode: 是否使用文档模式（标签页在顶部，没有面板边框）
    """
    s = get_mod_styles()
    tab_widget = QTabWidget(parent)

    tab_widget.setFont(get_unified_font(10))
    
    # 设置标签页可拖动排序
    if movable:
        tab_widget.setMovable(True)
    
    # 文档模式
    if document_mode:
        tab_widget.setDocumentMode(True)
    
    # 直接使用新架构 key
    tab_text = s.get(f'{variant}_tab_text', '#87CEEB')
    tab_bg = s.get(f'{variant}_tab_bg', 'rgba(30, 58, 95, 0.6)')
    tab_border = s.get(f'{variant}_tab_border', '#1E3A5F')
    tab_hover_bg = s.get(f'{variant}_tab_hover_bg', 'rgba(30, 58, 95, 0.5)')
    tab_selected_bg = s.get(f'{variant}_tab_selected_bg', 'rgba(135, 206, 235, 0.2)')
    
    tab_widget.setStyleSheet(f"""
        QTabWidget::tab-bar {{
            alignment: left;
        }}
        QTabBar::tab {{
            color: {tab_text};
            background: {tab_bg};
            padding: 5px 15px;
            border: 1px solid {tab_border};
            border-bottom: none;
        }}
        QTabBar::tab:hover {{
            background: {tab_hover_bg};
        }}
        QTabBar::tab:selected {{
            background: {tab_selected_bg};
        }}
        QTabWidget::pane {{
            border: 1px solid {tab_border};
            background: rgba(0, 0, 0, 0.3);
        }}
    """)
    
    return tab_widget

def create_styled_tab_page(tab_widget, title):
    """为标签页控件创建一个新的标签页"""
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(10, 10, 10, 10)
    tab_widget.addTab(page, title)
    return page, layout

def get_stylesheet_for_widget(widget_type, variant='sub'):
    """获取指定控件类型的样式表"""
    s = get_mod_styles()
    
    # 直接使用新架构 key
    text_primary = s.get(f'{variant}_text_primary', '#87CEEB')
    bg_default = s.get(f'{variant}_bg_default', 'rgba(30, 58, 95, 0.3)')
    bg_dark = s.get(f'{variant}_bg_dark', 'rgba(30, 58, 95, 0.6)')
    bg_hover = s.get(f'{variant}_bg_hover', 'rgba(30, 58, 95, 0.5)')
    bg_pressed = s.get(f'{variant}_bg_pressed', 'rgba(135, 206, 235, 0.4)')
    border_default = s.get(f'{variant}_border_default', '#1E3A5F')
    radius_md = s.get(f'{variant}_radius_md', '5px')
    radius_sm = s.get(f'{variant}_radius_sm', '3px')
    selection_color = s.get(f'{variant}_selection_color', 'rgba(135, 206, 235, 0.3)')
    
    stylesheets = {
        'button': f"""
            QPushButton {{
                color: {text_primary};
                background: {bg_default};
                border: 2px solid {border_default};
                border-radius: {radius_md};
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background: {bg_hover};
            }}
            QPushButton:pressed {{
                background: {bg_pressed};
            }}
        """,
        'import_button': f"""
            QPushButton {{
                background-color: rgba(128, 0, 128, 0.6);
                color: white;
                border: 2px solid rgba(128, 0, 128, 0.8);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(148, 20, 148, 0.7);
            }}
            QPushButton:pressed {{
                background-color: rgba(108, 0, 108, 0.8);
            }}
        """,
        'export_button': f"""
            QPushButton {{
                background-color: rgba(0, 128, 0, 0.6);
                color: white;
                border: 2px solid rgba(0, 128, 0, 0.8);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(20, 148, 20, 0.7);
            }}
            QPushButton:pressed {{
                background-color: rgba(0, 108, 0, 0.8);
            }}
        """,
        'run_button': f"""
            QPushButton {{
                background-color: rgba(200, 0, 0, 0.6);
                color: white;
                border: 2px solid rgba(200, 0, 0, 0.8);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(220, 20, 20, 0.7);
            }}
            QPushButton:pressed {{
                background-color: rgba(180, 0, 0, 0.8);
            }}
        """,
        'label': f"""
            color: {text_primary};
            background: transparent;
        """,
        'combo': f"""
            QComboBox {{
                color: {s.get(f'{variant}_combo_text', text_primary)};
                background: {s.get(f'{variant}_combo_bg', bg_default)};
                border: 1px solid {s.get(f'{variant}_combo_border', border_default)};
                border-radius: {radius_sm};
                padding: 3px;
            }}
            QComboBox::drop-down {{
                border-left: 1px solid {s.get(f'{variant}_combo_border', border_default)};
            }}
            QComboBox QAbstractItemView {{
                color: {s.get(f'{variant}_combo_dropdown_text', text_primary)};
                background: {s.get(f'{variant}_combo_dropdown_bg', bg_dark)};
                selection-background-color: {selection_color};
            }}
        """,
        'line_edit': f"""
            QLineEdit {{
                color: {s.get(f'{variant}_input_text', text_primary)};
                background: {s.get(f'{variant}_input_bg', bg_default)};
                border: 1px solid {s.get(f'{variant}_input_border', border_default)};
                border-radius: {radius_sm};
                padding: 3px 8px;
            }}
            QLineEdit:focus {{
                border-color: {s.get(f'{variant}_input_focus_border', text_primary)};
            }}
        """,
        'slider': f"""
            QSlider {{
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {border_default};
                height: 8px;
                background: {s.get(f'{variant}_slider_bg', 'rgba(30, 58, 95, 0.4)')};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {s.get(f'{variant}_slider_handle', border_default)};
                border: 1px solid {border_default};
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {s.get(f'{variant}_slider_handle_hover', bg_hover)};
            }}
        """,
        'checkbox': f"""
            QCheckBox {{
                color: {text_primary};
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {border_default};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background: {text_primary};
                border: 1px solid {text_primary};
            }}
        """,
        'group_box': f"""
            QGroupBox {{
                color: {s.get(f'{variant}_group_text', text_primary)};
                background: {s.get(f'{variant}_group_bg', bg_default)};
                border: 2px solid {s.get(f'{variant}_group_border', border_default)};
                border-radius: 8px;
                padding-top: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background: {s.get(f'{variant}_group_title_bg', bg_dark)};
                border-radius: 3px;
            }}
        """,
        'text_edit': f"""
            QTextEdit {{
                color: {s.get(f'{variant}_input_text', text_primary)};
                background: {s.get(f'{variant}_input_bg', bg_default)};
                border: 1px solid {s.get(f'{variant}_input_border', border_default)};
                border-radius: {radius_sm};
                padding: 5px;
            }}
        """,
        'scroll_area': f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {bg_default};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {border_default};
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {s.get(f'{variant}_slider_handle_hover', bg_hover)};
            }}
        """,
        'widget': f"""
            background: {bg_default};
            border: 1px solid {border_default};
            border-radius: {radius_sm};
        """,
        'image_label': f"""
            color: {text_primary};
            background: {bg_dark};
            border: 2px solid {border_default};
            border-radius: {radius_md};
        """,
        'table': f"""
            QTableWidget {{
                color: black;
                background: rgba(0, 0, 0, 0.2);
                border: 1px solid {s.get(f'{variant}_table_border', border_default)};
                gridline-color: {s.get(f'{variant}_table_border', border_default)};
                font-family: "幼圆";
                font-size: 9pt;
            }}
            QTableWidget::item {{
                padding: 3px;
                color: black;
                font-family: "幼圆";
                font-size: 9pt;
            }}
            QTableWidget::item:selected {{
                background: {selection_color};
            }}
            QHeaderView::section {{
                color: white;
                background: {s.get(f'{variant}_table_header_bg', bg_dark)};
                border: 1px solid {s.get(f'{variant}_table_border', border_default)};
                padding: 5px;
                font-weight: bold;
                font-family: "幼圆";
                font-size: 9pt;
            }}
        """,
    }

    return stylesheets.get(widget_type, '')

def get_font_for_widget(widget_type, font_size=12, bold=False, variant='sub'):
    """
    获取指定控件类型的 QFont 对象（统一使用 Arial/幼圆 fallback，不读 mod）

    Args:
        widget_type: 控件类型 ('button', 'label', 'combo', 'input', 'title')
        font_size: 字体大小
        bold: 是否加粗
        variant: 变体（保留兼容，不再影响字体选择）

    Returns:
        QFont 对象
    """
    return get_unified_font(font_size, bold)

def get_main_gui_styles():
    """
    根据 5 函数模型生成主界面完整样式（供 ui_bind.py 使用）
    
    返回包含所有主界面控件样式的字典：
    - primary_color: 主色（用于文字、选中态）
    - secondary_color: 副色（用于边框）
    - bg_color: 背景色
    - hover_color: 悬停色
    - pressed_color: 按下色
    - border_radius: 圆角
    - combo_radius: 下拉框圆角
    - button_stylesheet: 按钮样式表
    - combo_stylesheet: 下拉框样式表
    - slider_stylesheet: 滑块样式表
    - music_btn_stylesheet: 音乐按钮样式表
    """
    s = get_mod_styles()
    
    # 从 5 函数模型获取主界面配色
    primary_color = s.get('main_text_color', '#87CEEB')  # 主色 = 字体色
    secondary_color = s.get('main_border_color', '#1E3A5F')  # 副色 = 边框色
    bg_color = s.get('main_fill_color', 'rgba(30, 58, 95, 0.3)')  # 背景色 = 填充色
    hover_color = s.get('main_hover_color', s.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)'))  # 悬停色
    active_color = s.get('main_active_color', 'rgba(50, 88, 135, 0.4)')  # 选中色
    pressed_color = s.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)')  # 按下色
    dark_bg = s.get('main_fill_alt', 'rgba(30, 58, 95, 0.5)')  # 深色背景
    
    # 圆角
    border_radius = '5px'
    combo_radius = '3px'
    
    # 字体
    button_font = s.get('main_gui_font', '幼圆')
    label_font = s.get('main_text_font', '幼圆')
    
    # 按钮样式表
    button_stylesheet = f"""
        QPushButton {{
            color: {primary_color};
            background: {bg_color};
            border: 2px solid {secondary_color};
            border-radius: {border_radius};
            padding: 5px 15px;
            min-width: 150px;
            min-height: 40px;
            font-family: '{button_font}';
        }}
        QPushButton:hover {{
            background: {hover_color};
        }}
        QPushButton:pressed {{
            background: {pressed_color};
        }}
    """
    
    # 下拉框样式表
    combo_stylesheet = f"""
        QComboBox {{
            color: {primary_color};
            background: {bg_color};
            border: 1px solid {secondary_color};
            border-radius: {combo_radius};
            padding: 3px;
        }}
        QComboBox::drop-down {{
            border-left: 1px solid {secondary_color};
        }}
        QComboBox QAbstractItemView {{
            color: {primary_color};
            background: {dark_bg};
            selection-background-color: {hover_color};
        }}
    """
    
    # 滑块样式表（填充色=bg_color，边框色=secondary_color）
    slider_stylesheet = f"""
        QSlider {{
            background: transparent;
        }}
        QSlider::groove:horizontal {{
            border: 1px solid {secondary_color};
            height: 8px;
            background: {bg_color};
            border-radius: 4px;
        }}
        QSlider::handle:horizontal {{
            background: {bg_color};
            border: 1px solid {secondary_color};
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {hover_color};
        }}
    """
    
    # 音乐按钮样式表
    music_btn_stylesheet = f"""
        QPushButton {{
            background-color: {bg_color};
            border: 1px solid {secondary_color};
            border-radius: {border_radius};
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
    """
    
    # 字体映射
    fonts = {
        'title_font': s.get('main_text_font', '幼圆'),
        'label_font': s.get('main_text_font', '幼圆'),
        'button_font': s.get('main_gui_font', '幼圆'),
    }
    
    return {
        'primary_color': primary_color,
        'secondary_color': secondary_color,
        'bg_color': bg_color,
        'hover_color': hover_color,
        'pressed_color': pressed_color,
        'dark_bg': dark_bg,
        'border_radius': border_radius,
        'combo_radius': combo_radius,
        'button_stylesheet': button_stylesheet,
        'combo_stylesheet': combo_stylesheet,
        'slider_stylesheet': slider_stylesheet,
        'music_btn_stylesheet': music_btn_stylesheet,
        'button_font': button_font,
        'label_font': label_font,
        'title_font': label_font,
        **fonts
    }

def get_sub_gui_styles():
    """
    根据 5 函数模型生成子界面完整样式（供子界面使用）

    返回包含所有子界面控件样式的字典：
    - primary_color: 主色（用于文字、选中态）
    - secondary_color: 副色（用于边框）
    - bg_color: 背景色
    - hover_color: 悬停色
    - pressed_color: 按下色
    - dark_bg: 深色背景
    - mutant_color: 突变色（反差色）
    - border_radius: 圆角
    - combo_radius: 下拉框圆角
    - button_stylesheet: 按钮样式表
    - combo_stylesheet: 下拉框样式表
    - slider_stylesheet: 滑块样式表
    - music_btn_stylesheet: 音乐按钮样式表
    """
    s = get_mod_styles()

    # 从 5 函数模型获取子界面配色
    primary_color = s.get('sub_text_color', '#87CEEB')  # 主色 = 字体色
    secondary_color = s.get('sub_border_color', '#1E3A5F')  # 副色 = 边框色
    bg_color = s.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')  # 背景色 = 填充色
    hover_color = s.get('sub_hover_color', s.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)'))  # 悬停色
    active_color = s.get('sub_active_color', 'rgba(50, 88, 135, 0.4)')  # 选中色
    pressed_color = s.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')  # 按下色
    dark_bg = s.get('sub_fill_alt', 'rgba(30, 58, 95, 0.5)')  # 深色背景
    mutant_color = s.get('sub_mutant_color', '#FF6B35')  # 突变色 = 反差色

    # 圆角
    border_radius = s.get('sub_button_radius', '5px')
    combo_radius = s.get('sub_combo_radius', '3px')

    # 字体
    button_font = s.get('sub_button_font', s.get('button_font', '幼圆'))
    label_font = s.get('sub_text_font', s.get('text_font', '幼圆'))

    # 按钮样式表
    button_stylesheet = f"""
        QPushButton {{
            color: {primary_color};
            background: {bg_color};
            border: 2px solid {secondary_color};
            border-radius: {border_radius};
            padding: 5px 15px;
            min-width: 100px;
            font-family: '{button_font}';
        }}
        QPushButton:hover {{
            background: {hover_color};
        }}
        QPushButton:pressed {{
            background: {pressed_color};
        }}
    """

    # 下拉框样式表
    combo_stylesheet = f"""
        QComboBox {{
            color: {primary_color};
            background: {bg_color};
            border: 1px solid {secondary_color};
            border-radius: {combo_radius};
            padding: 3px;
        }}
        QComboBox::drop-down {{
            border-left: 1px solid {secondary_color};
        }}
        QComboBox QAbstractItemView {{
            color: {primary_color};
            background: {dark_bg};
            selection-background-color: {hover_color};
        }}
    """

    # 滑块样式表（与主界面一致：填充色=bg_color，边框色=secondary_color）
    slider_stylesheet = f"""
        QSlider {{
            background: transparent;
        }}
        QSlider::groove:horizontal {{
            border: 1px solid {secondary_color};
            height: 8px;
            background: {bg_color};
            border-radius: 4px;
        }}
        QSlider::handle:horizontal {{
            background: {primary_color};
            border: 1px solid {secondary_color};
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {hover_color};
        }}
    """

    # 音乐按钮样式表（与主界面一致：填充色=bg_color，边框色=secondary_color）
    music_btn_stylesheet = f"""
        QPushButton {{
            background-color: {bg_color};
            border: 1px solid {secondary_color};
            border-radius: {border_radius};
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
    """

    # 字体映射
    fonts = {
        'title_font': label_font,
        'label_font': label_font,
        'button_font': button_font,
    }

    return {
        'primary_color': primary_color,
        'secondary_color': secondary_color,
        'bg_color': bg_color,
        'hover_color': hover_color,
        'pressed_color': pressed_color,
        'dark_bg': dark_bg,
        'mutant_color': mutant_color,
        'border_radius': border_radius,
        'combo_radius': combo_radius,
        'button_stylesheet': button_stylesheet,
        'combo_stylesheet': combo_stylesheet,
        'slider_stylesheet': slider_stylesheet,
        'music_btn_stylesheet': music_btn_stylesheet,
        'button_font': button_font,
        'label_font': label_font,
        'title_font': label_font,
        **fonts
    }

def bind_button_with_sound(button, handler, log_widget=None, success_msg="操作成功", failure_msg="操作失败"):
    """
    绑定按钮与handler，自动处理成功/失败的音效和日志输出
    
    成功：handler正常完成，无异常，且没有触发attention/wrong弹窗
    失败：handler抛出异常 OR 触发了attention/wrong弹窗
    """
    from script.utils_layer.emoji_trigger import trigger_happy, get_and_reset_dialog_triggered
    
    def wrapped_handler():
        try:
            result = handler()  # 执行实际业务逻辑
            
            # 检查handler内部是否触发了attention/wrong弹窗
            if get_and_reset_dialog_triggered():
                # 触发了弹窗 → 算失败（handler内部已弹窗，不重复处理）
                if log_widget:
                    log_widget.append(f"✗ {failure_msg}")
            else:
                # 无弹窗无异常 → 成功，播放happy音效
                if log_widget:
                    log_widget.append(f"✓ {success_msg} 🎉")
                trigger_happy(use_dialog=False)
            
            return result
            
        except Exception as e:
            # handler抛出异常 → 失败，播放wrong音效
            from script.utils_layer.emoji_trigger import trigger_wrong
            error_detail = str(e) if str(e) else "未知错误"
            if log_widget:
                log_widget.append(f"✗ {failure_msg}: {error_detail}")
            trigger_wrong()  # 只播放音效，不弹窗（handler已弹过）
    
    button.clicked.connect(wrapped_handler)

class ZoomableImageLabel(QLabel):
    """支持拖动和缩放的图片标签控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        self.dragging = False
        self.last_pos = QPoint(0, 0)
        self._original_pixmap = None
        self._scaled_pixmap = None
    
    def set_pixmap(self, pixmap):
        """设置图片，自动缩放到适应label尺寸并居中显示"""
        self._original_pixmap = pixmap
        self.reset_view()
    
    def reset_view(self):
        """重置视图到自适应大小并居中"""
        if self._original_pixmap is not None and self.size().isValid():
            label_width = self.size().width()
            label_height = self.size().height()
            
            if label_width > 0 and label_height > 0:
                scale_x = label_width / self._original_pixmap.width()
                scale_y = label_height / self._original_pixmap.height()
                self.scale_factor = min(scale_x, scale_y, 1.0)
            else:
                self.scale_factor = 1.0
        else:
            self.scale_factor = 1.0
        
        self._center_image()
        self._update_scaled_pixmap()
        self.update()
    
    def _center_image(self):
        """计算居中偏移量"""
        if self._original_pixmap is None:
            self.offset = QPoint(0, 0)
            return
        
        scaled_width = int(self._original_pixmap.width() * self.scale_factor)
        scaled_height = int(self._original_pixmap.height() * self.scale_factor)
        
        label_width = self.size().width()
        label_height = self.size().height()
        
        offset_x = (label_width - scaled_width) // 2
        offset_y = (label_height - scaled_height) // 2
        
        self.offset = QPoint(max(0, offset_x), max(0, offset_y))
    
    def _update_scaled_pixmap(self):
        """更新缩放后的图片"""
        if self._original_pixmap is None:
            self._scaled_pixmap = None
            return
        
        try:
            orig_size = self._original_pixmap.size()
            scaled_width = int(max(1, orig_size.width() * self.scale_factor))
            scaled_height = int(max(1, orig_size.height() * self.scale_factor))
            
            self._scaled_pixmap = self._original_pixmap.scaled(
                scaled_width, scaled_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        except Exception as e:
            self._scaled_pixmap = None
    
    def paintEvent(self, event):
        """自定义绘制事件，使用offset绘制图片"""
        if self._scaled_pixmap is not None and not self._scaled_pixmap.isNull():
            painter = QPainter(self)
            painter.drawPixmap(self.offset, self._scaled_pixmap)
            painter.end()
        else:
            # 如果没有图片，调用父类的paintEvent来显示文本
            super().paintEvent(event)
    
    def update_display(self):
        """更新显示"""
        if self._original_pixmap is None:
            self._scaled_pixmap = None
            self.update()
            return
        
        if not self.isVisible():
            return
        
        self._update_scaled_pixmap()
        self.update()
    
    def resizeEvent(self, event):
        """容器大小变化时重新自适应居中"""
        super().resizeEvent(event)
        if self._original_pixmap is not None:
            self.reset_view()
    
    def showEvent(self, event):
        """控件显示时重新自适应居中（处理标签页切换）"""
        super().showEvent(event)
        if self._original_pixmap is not None:
            self.reset_view()
    
    def wheelEvent(self, event):
        """滚轮缩放 - 以鼠标位置为中心"""
        if self._original_pixmap is None:
            event.accept()
            return
        
        mouse_pos = event.pos()
        
        scaled_width = self._original_pixmap.width() * self.scale_factor
        scaled_height = self._original_pixmap.height() * self.scale_factor
        
        img_left = self.offset.x()
        img_top = self.offset.y()
        img_right = img_left + scaled_width
        img_bottom = img_top + scaled_height
        
        if (mouse_pos.x() < img_left or mouse_pos.x() > img_right or
            mouse_pos.y() < img_top or mouse_pos.y() > img_bottom):
            rel_x = 0.5
            rel_y = 0.5
            anchor_x = img_left + scaled_width / 2
            anchor_y = img_top + scaled_height / 2
        else:
            rel_x = (mouse_pos.x() - img_left) / scaled_width
            rel_y = (mouse_pos.y() - img_top) / scaled_height
            anchor_x = mouse_pos.x()
            anchor_y = mouse_pos.y()
        
        old_scale = self.scale_factor
        
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale_factor = min(self.scale_factor * 1.15, 10.0)
        else:
            self.scale_factor = max(self.scale_factor / 1.15, 0.1)
        
        new_scale = self.scale_factor
        
        new_scaled_width = self._original_pixmap.width() * new_scale
        new_scaled_height = self._original_pixmap.height() * new_scale
        
        new_img_left = anchor_x - rel_x * new_scaled_width
        new_img_top = anchor_y - rel_y * new_scaled_height
        
        self.offset.setX(int(new_img_left))
        self.offset.setY(int(new_img_top))
        
        self.update_display()
        event.accept()
    
    def mousePressEvent(self, event):
        """鼠标按下开始拖动"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动拖动"""
        if self.dragging and self._original_pixmap is not None:
            delta = event.pos() - self.last_pos
            self.offset += delta
            self.last_pos = event.pos()
            self.update_display()
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放结束拖动"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
    
    def mouseDoubleClickEvent(self, event):
        """双击重置视图到自适应大小"""
        self.reset_view()
        event.accept()


def create_zoomable_image_label(parent=None, fixed_height=None):
    """
    创建可缩放拖动的图片标签控件（工厂函数）
    
    功能：
    - 自动居中并自适应容器大小
    - 滚轮缩放（以鼠标位置为中心）
    - 鼠标拖动平移
    - 双击重置视图
    - 容器resize时自动重新居中
    
    使用方式：
        label = create_zoomable_image_label(parent, fixed_height=300)
        layout.addWidget(label)
    
    Args:
        parent: 父控件
        fixed_height: 固定高度（可选）
    
    Returns:
        ZoomableImageLabel实例
    """
    label = ZoomableImageLabel(parent)
    label.setCursor(Qt.OpenHandCursor)
    label.setAlignment(Qt.AlignCenter)
    if fixed_height:
        label.setMinimumHeight(fixed_height)
    return label


def create_styled_image_tab(tab_widget, title, parent=None, default_text="请加载数据并生成图表", data_hint_template="数据: {dataset_name}\n样本数: {n_samples}\n基因数: {n_genes}\n\n请输入基因名称并点击「生成结果图」"):
    """
    创建带图片显示的样式化标签页（模板函数）
    
    创建一个包含ZoomableImageLabel的标签页，图片会自动居中并自适应标签页大小
    所有使用此模板创建的标签页都具有一致的图片显示行为：
    - 居中显示
    - 自适应容器大小
    - 支持缩放拖动
    - resize时重新居中
    
    Args:
        tab_widget: QTabWidget实例
        title: 标签页标题
        parent: 父控件
        default_text: 默认显示文本（未加载数据时）
        data_hint_template: 数据加载后的提示文本模板
    
    Returns:
        (tab_page, image_label): 标签页容器和图片标签
    """
    tab_page = QWidget(parent)
    layout = QVBoxLayout(tab_page)
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(0)
    
    image_label = create_zoomable_image_label(tab_page)
    image_label.setObjectName("styled_image_label")
    image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    image_label.setStyleSheet(get_stylesheet_for_widget('image_label'))
    
    image_label.setText(default_text)
    image_label.setFont(get_font_for_widget('label', 14))
    image_label.setMinimumSize(400, 300)
    
    image_label.data_hint_template = data_hint_template
    
    layout.addWidget(image_label)
    tab_widget.addTab(tab_page, title)
    
    return tab_page, image_label


__all__ = [
    'get_mod_styles',
    'get_mod_paths',
    'create_styled_label',
    'create_styled_button',
    'create_styled_combo_box',
    'create_styled_line_edit',
    'create_styled_slider',
    'create_styled_checkbox',
    'create_styled_spinbox',
    'create_styled_number_input',
    'create_styled_list_widget',
    'create_styled_table',
    'create_styled_panel',
    'create_styled_group_box',
    'create_styled_tab_widget',
    'create_styled_tab_page',
    'create_styled_image_tab',
    'create_zoomable_image_label',
    'get_stylesheet_for_widget',
    'get_font_for_widget',
    'get_main_gui_styles',
    'get_sub_gui_styles',
    'bind_button_with_sound',
    'ZoomableImageLabel',
    'StyledNumberInput',
    'QuestionsButton',
    'create_questions_button',
    'create_labeled_param_with_help',
]


# ========================================
# 问号帮助按钮控件
# ========================================

class QuestionsButton(QPushButton):
    """圆形问号按钮 - 点击后弹出无边框对话框显示说明文字"""

    def __init__(self, help_text="", parent=None):
        super().__init__("?", parent)
        self._help_text = help_text
        self._dialog = None
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()
        self.clicked.connect(self._toggle_dialog)

    def _apply_style(self):
        s = get_mod_styles()
        fg = s.get('mutant_color', '#E91E63')
        border = s.get('sub_border_color', '#1E3A5F')
        bg = s.get('sub_fill_color', 'rgba(30, 58, 95, 0.5)')
        self.setStyleSheet(f"""
            QPushButton {{
                color: {fg};
                background: {bg};
                border: 1px solid {border};
                border-radius: 11px;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {s.get('sub_hover_color', 'rgba(50, 88, 135, 0.6)')};
            }}
        """)

    def set_help_text(self, text):
        self._help_text = text

    def _toggle_dialog(self):
        if self._dialog is not None and self._dialog.isVisible():
            self._dialog.close()
            return

        dialog = _HelpDialog(self._help_text, self.window(), self)
        self._dialog = dialog
        dialog.finished.connect(self._on_dialog_finished)

        btn_pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        dialog.move(btn_pos)
        dialog.show()

    def _on_dialog_finished(self, result):
        self._dialog = None


class _HelpDialog(QDialog):
    """无边框帮助对话框 - 点击外部自动关闭"""

    def __init__(self, help_text, parent=None, anchor_button=None):
        super().__init__(parent)
        self._anchor_button = anchor_button
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._build_ui(help_text)

    def _build_ui(self, help_text):
        s = get_mod_styles()
        bg = s.get('sub_fill_color', 'rgba(30, 58, 95, 0.95)')
        border = s.get('sub_border_color', '#1E3A5F')
        text_color = s.get('mutant_color', '#E91E63')

        container = QWidget(self)
        container.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)

        label = QLabel(help_text, container)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {text_color}; background: transparent; font-size: 13px;")
        label.setMaximumWidth(320)
        layout.addWidget(label)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

        self.adjustSize()

    def mousePressEvent(self, event):
        if not self.rect().contains(event.pos()):
            self.close()
        super().mousePressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()

    def focusOutEvent(self, event):
        self.close()
        super().focusOutEvent(event)


def create_questions_button(help_text="", parent=None):
    """创建圆形问号按钮

    Args:
        help_text: 点击后显示的说明文字
        parent: 父控件

    Returns:
        QuestionsButton 实例
    """
    return QuestionsButton(help_text, parent)


def create_labeled_param_with_help(label_text, help_text, font_size=12, bold=True, variant='sub'):
    """创建带问号按钮的参数标签行

    Args:
        label_text: 参数名称
        help_text: 问号按钮的说明文字
        font_size: 字体大小
        bold: 是否粗体
        variant: 样式变体

    Returns:
        tuple: (label, questions_btn) 可放入 QHBoxLayout
    """
    label = create_styled_label(label_text, font_size=font_size, bold=bold, variant=variant)
    q_btn = create_questions_button(help_text)
    return label, q_btn


# ========================================
# 通用模态弹窗样式（模态无标题栏、居中于主窗口、mod色彩）
# 所有绑定进入界面的弹窗都应继承 StyledDialog 或调用 get_dialog_stylesheet
# ========================================

def get_dialog_stylesheet(variant='sub'):
    """获取弹窗的统一样式表（mod色彩，无标题栏）

    Args:
        variant: 样式变体，'sub' 为子界面样式，'main' 为主界面样式

    Returns:
        str: QSS 样式表字符串，用于 dialog.setStyleSheet()
    """
    s = get_mod_styles()
    bg_color = s.get(f'{variant}_fill_color', 'rgba(30, 58, 95, 0.9)')
    border_color = s.get(f'{variant}_border_color', '#1E3A5F')
    text_color = s.get(f'{variant}_text_primary', '#87CEEB')
    mutant_color = s.get(f'{variant}_mutant_color', s.get('mutant_color', '#FF6B35'))
    hover_color = s.get(f'{variant}_hover_color', mutant_color)
    radius = s.get(f'{variant}_panel_radius', '10px')
    return f"""
        QDialog {{
            background: {bg_color};
            border: 2px solid {border_color};
            border-radius: {radius};
        }}
        QLabel {{
            color: {text_color};
            background: transparent;
        }}
        QPushButton {{
            color: {text_color};
            background: {s.get(f'{variant}_button_bg', 'rgba(30, 58, 95, 0.3)')};
            border: 2px solid {border_color};
            border-radius: 5px;
            padding: 5px 15px;
            min-width: 100px;
        }}
        QPushButton:hover {{
            background: {s.get(f'{variant}_button_hover_bg', 'rgba(30, 58, 95, 0.5)')};
        }}
        QPushButton:pressed {{
            background: {s.get(f'{variant}_button_pressed_bg', 'rgba(135, 206, 235, 0.4)')};
        }}
    """


def get_dialog_close_button_stylesheet(variant='sub'):
    """获取弹窗关闭按钮的样式（突变色背景，醒目）"""
    s = get_mod_styles()
    mutant_color = s.get(f'{variant}_mutant_color', s.get('mutant_color', '#FF6B35'))
    hover_color = s.get(f'{variant}_hover_color', mutant_color)
    return f"""
        QPushButton {{
            color: white;
            background-color: {mutant_color};
            border: none;
            border-radius: 5px;
            padding: 8px 30px;
            min-width: 100px;
            min-height: 35px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
    """


class StyledDialog(QDialog):
    """通用模态无标题栏弹窗基类 - 居中于主窗口，使用mod统一样式

    使用方式：
        class MyDialog(StyledDialog):
            def _build_ui(self):
                # 自定义内容，样式已由基类设置好
                ...

    子界面弹窗继承此类即可获得：
    - 模态无标题栏（Qt.FramelessWindowHint | Qt.Dialog）
    - 居中于主窗口中央（showEvent 自动处理）
    - mod统一样式（背景、边框、文字、按钮颜色跟随mod）
    - 点击音效过滤器自动安装
    """

    def __init__(self, main_window, variant='sub', fixed_size=None):
        """
        Args:
            main_window: 主窗口对象，用于居中定位和音效安装
            variant: 样式变体，'sub' 或 'main'
            fixed_size: (width, height) 固定尺寸，None 则由内容决定
        """
        super().__init__(main_window)
        self.main_window = main_window
        self.variant = variant
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)

        # 应用统一样式
        self.setStyleSheet(get_dialog_stylesheet(variant))

        # 设置固定尺寸（如有）
        if fixed_size:
            self.setFixedSize(*fixed_size)

        # 子类构建内容
        self._build_ui()

        # 安装点击音效过滤器
        self._install_click_filter()

    def _build_ui(self):
        """子类重写此方法构建弹窗内容"""
        pass

    def _install_click_filter(self):
        """安装点击音效过滤器到弹窗及所有子控件"""
        try:
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'get_click_filter_class') and hasattr(mod_instance, 'global_sound_player'):
                ClickFilterClass = mod_instance.get_click_filter_class()
                self._click_filter = ClickFilterClass(mod_instance.global_sound_player)
                self.installEventFilter(self._click_filter)
                self._install_click_filter_recursively(self)
        except Exception as e:
            print(f"安装点击音效过滤器失败: {e}")

    def _install_click_filter_recursively(self, widget):
        """递归安装点击音效过滤器到所有子控件"""
        try:
            if widget and hasattr(widget, 'installEventFilter'):
                widget.installEventFilter(self._click_filter)
            if hasattr(widget, 'children'):
                for child in widget.children():
                    self._install_click_filter_recursively(child)
        except Exception:
            pass

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
        """对话框关闭时清理（子类可重写添加恢复逻辑）"""
        super().done(result)

    def closeEvent(self, event):
        """关闭事件"""
        super().closeEvent(event)
