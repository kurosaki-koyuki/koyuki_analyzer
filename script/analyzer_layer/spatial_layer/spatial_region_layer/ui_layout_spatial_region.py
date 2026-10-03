# -*- coding: utf-8 -*-
"""
空转「绘制区域」页面UI布局脚本（M4 · Phase 1）- 只负责创建控件、规划布局、设置样式尺寸
完全不写按钮点击、触发逻辑

结构：HBox[ 左导航(220) | 中：画布(stretch) | 右：区域属性面板(约 300) ]
★ 硬约束：本文件**任何地方都不读数据** ——
  不读 regions.json / spots.csv / 图集、不扫目录、不建 QPixmap（背景图除外，与其它页同款）、
  不 import/实例化 analysis 类。散点/区域/组织底图**全部由 bind 传入**。

## v2 两级命名（契约 `_d_spec_region_naming_v2.md` §3，2026-09-23）
右栏「区域名」一行改成**两级命名**（与小提琴"combo 在上、list 在下"同构）：
    `region_name_input`（**不可编辑**的分组下拉，items 由 bind §4.1 填）
      └─ `region_anno_list`（细分注释选择框，内容由 bind §4.2 填）
           └─ `region_anno_input` + `btn_region_anno_ok`（自定义注释，初始隐藏，同一行）
`region_name_edit`（旧自由文本 `combo.lineEdit()`）**已删除**；`commit_region_name()`
改为空操作（写盘归 bind §4.3）。★ 本层依旧**只建控件**，不读数据、不写盘。
"""

import traceback

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_panel, create_styled_label,
    create_styled_list_widget, create_styled_text_edit, create_styled_combo_box,
    create_styled_line_edit,
    create_styled_spinbox, create_signaled_number_input,
    create_styled_color_palette, create_zoomable_image_label,
    create_styled_checkbox,
    create_styled_mode_toggle, apply_mode_toggle_styles, MODE_TOGGLE_PROPERTY,
    create_navigation_panel, create_navigation_button, create_navigation_divider,
    create_navigation_header
)
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.spatial_layer.spatial_region_layer.region_canvas import (
    RegionCanvasWidget)
# ★ 显示层（M4 §14.2）：样本条目冻结文本的唯一生成处；本层只转发数据，不读文件
from script.analyzer_layer.spatial_layer.spatial_region_layer.ui_func_spatial_region import (
    region_sample_text, set_sample_items as func_set_sample_items,
    restamp_sample_items as func_restamp_sample_items, install_sample_autostamp,
    refresh_region_list_names, install_region_list_autostamp)


class SpatialRegionPageUI:
    """「绘制区域」页面布局类（只建控件）"""

    # 9 个 signature 名（契约 §13.1，**历史常量：保留供别的探针引用**）
    # ★ v2（2026-09-23，契约 `_d_spec_region_naming_v2.md` §3）：**不再**作为
    #   `region_name_input` 的 items —— 该项已改成"分组下拉"（items 由 bind §4.1 填）。
    SIGNATURE_SUGGESTIONS = ["MES", "NPC", "OPC", "AC", "Hypoxia",
                             "Myeloid", "Tcell", "Oligo", "Vessel"]

    # 各控件固定高度（沿用"别被拉高"的做法）
    H_INPUT = 28
    H_BTN = 34
    H_ROW = 30
    H_LOG = 90

    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.create_page()

    # ------------------------------------------------------------------
    def update_background(self):
        """切换模组时重载背景图（只碰背景 QLabel，不读任何数据）"""
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.spatial_region_page.findChild(QLabel, "spatial_region_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(
                    f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        """刷新样式：跳过导航按钮/背景标签/画布内部；只刷普通按钮/标签/标题/面板底色"""
        styles = get_mod_styles()

        button_style = get_stylesheet_for_widget('button')
        nav_buttons = [getattr(self, attr) for attr in dir(self) if attr.startswith('nav_btn_')]
        explicit_names = ('btn_region_confirm', 'btn_region_undo',
                          'btn_region_delete', 'btn_region_clear',
                          'btn_region_dump', 'btn_region_next_unpainted')
        explicit_buttons = [getattr(self, n) for n in explicit_names if hasattr(self, n)]
        for child in self.spatial_region_page.findChildren(QPushButton):
            if child in nav_buttons:
                continue
            # 画布内部的按钮（无）/ 调色板色块：调色板自管样式，别覆盖
            if self.region_canvas is not None and self.region_canvas.isAncestorOf(child):
                continue
            # ★ 模式按钮**不许**被通用按钮样式覆盖（会把"选中态变异色"洗掉）；
            #   它们的样式由 apply_mode_button_styles() 按主题重套（下一段）。
            if child.property(MODE_TOGGLE_PROPERTY):
                continue
            child.setStyleSheet(button_style)
        # ★ 「导出坐标表 / 下一个未画样本」等按钮除通用循环外**再显式刷一次**：
        #   不能只在构造期设一次，切模组后样式必须跟随（同时兜住固定高度）。
        for btn in explicit_buttons:
            btn.setStyleSheet(button_style)
            if btn.height() != self.H_BTN:
                btn.setFixedHeight(self.H_BTN)
        # ★ 模式按钮（N 个通用）：按当前主题 + 各自勾选态重套（选中态 = 变异色）
        self.apply_mode_button_styles()
        self.update_mode_label()

        label_style = get_stylesheet_for_widget('label')
        for child in self.spatial_region_page.findChildren(QLabel):
            if child.objectName() == "spatial_region_bg":
                continue
            combo_parent = child.parent()
            if isinstance(combo_parent, QComboBox):
                continue
            child.setStyleSheet(label_style)

        title_label = self.spatial_region_page.findChild(QLabel, "spatial_region_title")
        if title_label:
            title_label.setStyleSheet(
                f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")

        panel_bg = styles.get('sub_fill_color', 'rgba(30, 58, 95, 0.3)')
        panel_border = styles.get('sub_border_color', '#1E3A5F')
        panel_radius = styles.get('sub_panel_radius', '5px')
        panel_style = f"""
            background: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: {panel_radius};
        """
        for child in self.spatial_region_page.findChildren(QWidget):
            if child.objectName() and child.objectName().startswith("styled_panel"):
                child.setStyleSheet(panel_style)

    # ------------------------------------------------------------------
    def _create_sample_panel(self, parent, layout):
        """左导航下半：样本选择（列当前数据集所有样本，含已画/未画标记）

        条目文本 = §14.2 冻结格式，**由显示层唯一生成**（本文件只转发）：
            已画：`✅ 已画 N 区  <样本号>`   未画：`⚠ 未画  <样本号>`
        区域个数来自 W2 的 `set_region_counts()` / `set_sample_items()`；
        取不到就按「未画」渲染。`install_sample_autostamp` 保证 W2 侧
        `clear()` + 重新 `addItem` 的重建路径也**不会把标记冲掉**。
        """
        layout.addWidget(create_styled_label("样本（逐个画）", font_size=10,
                                             bold=False, parent=parent))
        self.region_sample_list = create_styled_list_widget(
            parent=parent, fixed_height=260, multi_selection=False)
        layout.addWidget(self.region_sample_list)
        # ★ 自动盖冻结文本（W2 直接 addItem 也生效；已有 ✅/⚠ 不被降级覆盖）
        self.region_sample_autostamp = install_sample_autostamp(
            self.region_sample_list, self.get_region_counts)

        # ---- 手动重试 / 跳转按钮（只建控件；点击逻辑归 W2）----
        self.btn_region_dump = create_styled_button(
            "导出坐标表", font_size=10, parent=parent, button_type='normal')
        self.btn_region_dump.setFixedHeight(self.H_BTN)
        layout.addWidget(self.btn_region_dump)

        self.btn_region_next_unpainted = create_styled_button(
            "下一个未画样本", font_size=10, parent=parent, button_type='normal')
        self.btn_region_next_unpainted.setFixedHeight(self.H_BTN)
        layout.addWidget(self.btn_region_next_unpainted)

        self.region_sample_hint = create_styled_label(
            "⚠ = 尚未画区域 · ✅ = 已画 N 区", font_size=9, bold=False, parent=parent)
        layout.addWidget(self.region_sample_hint)

    # ---- 样本条目文本接口（W2 用；本文件只转发，文本逻辑在 ui_func_spatial_region）----
    def get_region_counts(self):
        """当前 {样本号: 区域个数}（供自动盖文本用；只读，不读文件）"""
        return dict(getattr(self, '_region_counts', {}) or {})

    def set_region_counts(self, mapping, restamp=True):
        """W2 传入/更新 {样本号: 区域个数}；restamp=True 时就地重刷条目文本。

        ★ 只更新已有条目文本，**不清空列表、不重排、不切样本**；
          UserRole 已有的**绝不覆盖**（缺失时按文本补回样本号，供 bind 侧取号）。
        """
        merged = dict(getattr(self, '_region_counts', {}) or {})
        if isinstance(mapping, dict):
            for key, value in mapping.items():
                sid = str(key or "").strip()
                if not sid:
                    continue
                if value is None:
                    continue
                try:
                    merged[sid] = int(value)
                except Exception:
                    continue
        self._region_counts = merged
        if not restamp:
            return 0
        return func_restamp_sample_items(self.region_sample_list, merged)

    def set_sample_items(self, samples, region_counts=None, selected_id=None):
        """W2 填充样本列表（沿用既有 `set_sample_items` 形态，容错取区域个数）。

        Args:
            samples: list，元素可为 dict（`id`/`sample_id`…，可选 `region_count`/`count`/
                     `n_regions`… 或 `painted`/`has_regions`/`drawn`）、
                     (sid, count[, painted]) 元组、或纯样本号 str。
                     **顺序原样保留**（不重排）。
            region_counts: {样本号: 区域个数}（可选，比条目字段更权威）
            selected_id: 需要选中的样本号（可选）

        Returns:
            int: 实际加入的条目数
        """
        if isinstance(region_counts, dict):
            self.set_region_counts(region_counts, restamp=False)
        return func_set_sample_items(self.region_sample_list, samples,
                                     self.get_region_counts(), selected_id)

    def restamp_sample_items(self):
        """按当前 `_region_counts` 就地重刷条目文本；返回变化的条目数"""
        return func_restamp_sample_items(self.region_sample_list, self.get_region_counts())

    def region_sample_item_text(self, sample_id, region_count=None, painted=None):
        """暴露给 W2 的文本生成口径（保证与列表里逐字一致）"""
        return region_sample_text(sample_id, region_count, painted)

    # ---- Phase 4① 区域命名 → v2 两级命名（分组下拉 + 注释选择框）
    #      `show_region_name(index)` 只按 `anno_group` 选中分组下拉并清空注释框；
    #      写盘（`anno_group`/`anno_label`/`name`）归 W2 的 bind（契约 §4.3）。----
    def selected_region_index(self):
        """当前"正在编辑"的区域索引：画布选中优先，其次区域列表当前行；无 → -1"""
        try:
            idx = int(self.region_canvas.selected_index())
            if idx >= 0:
                return idx
        except Exception:
            pass
        try:
            idx = int(self.region_list_widget.currentRow())
            if idx >= 0:
                return idx
        except Exception:
            pass
        return -1

    def show_region_name(self, index):
        """按第 `index` 个区域的 `anno_group` 选中「分组」下拉，并清空注释选择框。

        ★ v2（契约 `_d_spec_region_naming_v2.md` §3）：本页已是**两级命名** ——
          `region_name_input` = 分组下拉（不可编辑）+ `region_anno_list` = 细分注释。
          本方法**只**做两件事，且**不读任何自由文本**：
            ① 把分组下拉切到该区域的 `anno_group`；没有该项目 / 取不到 / 旧式区域
               ⇒ 归位 `cell_type`，再退到第 0 项；
            ② **清空**注释选择框（`clear()`）—— 真正的"按当前分组回填注释值"
               归 W2 的 bind（契约 §4.2），本层不读数据、不知道有哪些注释值。
        ★ 不读 regions.json / spots.csv，不写盘、不建区域；拿不到画布或区域字段时
          **不抛**（只留痕）。
        Returns: str —— 该区域的 `anno_group`（取不到 → 空串）
        """
        group = ""
        try:
            region = None
            regions = self.region_canvas.get_regions()
            try:
                idx = int(index)
            except Exception:
                idx = -1
            if isinstance(regions, list) and 0 <= idx < len(regions):
                region = regions[idx]
            if isinstance(region, dict):
                group = str(region.get("anno_group") or "").strip()
        except Exception:
            traceback.print_exc()
            group = ""

        try:
            combo = self.region_name_input
            target = group if group else "cell_type"
            pos = combo.findText(target)
            if pos < 0:
                pos = combo.findText("cell_type")
            if pos < 0 and combo.count() > 0:
                pos = 0            # 兜底：至少选第 0 项（bind 还没填 items 时 count == 0，不动）
            if pos >= 0:
                combo.setCurrentIndex(pos)
        except Exception:
            traceback.print_exc()

        try:
            self.region_anno_list.clear()
        except Exception:
            traceback.print_exc()
        return group

    def commit_region_name(self):
        """**空操作**：两级命名（分组 + 注释）的写盘已归 bind 的 combo/list 链路。

        ★ v2（契约 `_d_spec_region_naming_v2.md` §3/§4.3）：区域名不再由自由文本框写回 ——
          分组 / 注释值由 **W2 的 bind** 在 `region_name_input` / `region_anno_list` 变化时
          写进区域模型（`anno_group` + `anno_label`，并同步 `name`）。
          本方法**不再读任何文本、不调 `set_region_name`、不写盘**，只保留方法名与文档，
          免得历史接线（`region_name_edit.editingFinished` 那一处）留成"看不出来的死写盘"。
        ★ `region_name_edit` 已随 `setEditable(False)` 一并删除（见契约 §3）。
        Returns: bool —— 恒为 False（未做任何写入）
        """
        return False

    def refresh_region_list_texts(self, only_index=None):
        """就地刷新 `region_list_widget` 的名字部分（不动顺序/选中行/UserRole）。

        Returns: int —— 改动过的行数
        """
        try:
            regions = self.region_canvas.get_regions()
        except Exception:
            return 0
        return refresh_region_list_names(self.region_list_widget, regions, only_index)

    def _create_canvas_panel(self, parent, layout):
        """中栏：编辑模式开关 + 画布 + 两个预览（带点 / 无点）"""
        # ---- 编辑模式（N 个按钮通用；都不选 = draw；接线归 W2）----
        #   ★ 按钮由工厂 `create_styled_mode_toggle` 建：自带"选中态=变异色"样式、
        #     主题注册（切模组不掉色）、`dshModeToggle` 标记（可被自动发现）。
        #   ★ 加第 4 个模式：这里加一行 `_add_mode_button(...)` + 在类常量
        #     `MODE_BUTTONS` 加一行 —— **样式代码一行都不用改**。
        mode_row = QHBoxLayout()
        self._mode_buttons = []
        # ★ 2026-09-23 契约 `_d_spec_select_mode.md` §2：新增「选择模式」，放在模式行**最前面**
        #   （= 在「可见区域」之前）。按钮顺序必须与类常量 `MODE_BUTTONS` 顺序一致
        #   （`edit_mode_from_buttons()` / `set_edit_mode_buttons()` 依赖该表）。
        self._add_mode_button(mode_row, 'btn_region_edit_select', "选择模式", parent)
        # ★ 2026-09 用户纠正：原「编辑边」不是编辑边，而是**画"可见区域"范围层**
        #   （用户原话："根本就不是编辑边，而是改成**可见区域选择**"）⇒ 按钮/模式都换掉。
        self._add_mode_button(mode_row, 'btn_region_edit_visible', "可见区域", parent)
        self._add_mode_button(mode_row, 'btn_region_edit_label', "编辑注释", parent)
        self._add_mode_button(mode_row, 'btn_region_edit_mask', "隐形区域", parent)
        mode_row.addStretch()

        # ★ 常驻"当前模式"文案：**都不勾（= 绘制）时唯一的可见标记**
        #   （选它的理由：绘制态没有对应按钮，标签是唯一不需要加"第四个按钮"
        #     就能表达"现在是绘制模式"的方式；而且模式再多也不会漏。）
        self.region_mode_label = create_styled_label(
            "当前模式：绘制", font_size=10, bold=True, parent=parent)
        mode_row.addWidget(self.region_mode_label)
        layout.addLayout(mode_row)

        self.region_canvas = RegionCanvasWidget(parent=parent)
        layout.addWidget(self.region_canvas, stretch=3)

        self.region_canvas_hint = create_styled_label(
            "左键单击=加顶点 · 双击=闭合 · 右键=取消 · 滚轮=缩放 · 中键/空格+拖动=平移",
            font_size=9, bold=False, parent=parent)
        self.region_canvas_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.region_canvas_hint)

        # ---- 预览区：带点 / 无点 **并排**（省纵向空间；两张图都由 W2 填）----
        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)

        left_col = QVBoxLayout()
        left_col.addWidget(create_styled_label("带点（重绘结果）", font_size=9,
                                               bold=False, parent=parent))
        self.region_preview_label = create_zoomable_image_label(parent=parent, fixed_height=220)
        self.region_preview_label.setText("确认后这里显示重绘结果")
        self.region_preview_label.setAlignment(Qt.AlignCenter)
        left_col.addWidget(self.region_preview_label)
        preview_row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.addWidget(create_styled_label("无点（成图）", font_size=9,
                                                bold=False, parent=parent))
        self.region_preview_nospot_label = create_zoomable_image_label(parent=parent,
                                                                       fixed_height=220)
        self.region_preview_nospot_label.setText("确认后这里显示无点成图")
        self.region_preview_nospot_label.setAlignment(Qt.AlignCenter)
        right_col.addWidget(self.region_preview_nospot_label)
        preview_row.addLayout(right_col)

        layout.addLayout(preview_row, stretch=1)

    # ---- 编辑模式按钮 ↔ 模式（互斥；W2 只需接 toggled → 这两行）----
    #   ★ 加一个模式 = ① 建按钮（`_add_mode_button`）② 下表加一行 ③ `MODE_LABELS` 加一行。
    #     样式（选中态变异色）与互斥**自动生效**，不用改任何样式代码。
    MODE_BUTTONS = (
        ('btn_region_edit_select', 'select'),     # 选择区域（含可见/隐形）；选中以便命名（契约 §2）
        ('btn_region_edit_visible', 'visible'),   # 画"可见区域"范围层（取代退休的 edges）
        ('btn_region_edit_label', 'label'),
        ('btn_region_edit_mask', 'mask'),         # 隐形区域（画法同 draw，闭合带 mask=True）
    )
    MODE_LABELS = {
        'draw': '绘制',
        'select': '选择模式',
        'visible': '可见区域',
        'label': '编辑注释',
        'mask': '隐形区域',
    }

    def edit_mode_from_buttons(self):
        """模式按钮的当前选中态 → 模式串（都不勾 = `"draw"`）

        Returns: `"edges"` / `"label"` / `"mask"` / `"draw"`
        """
        for attr, mode in self.MODE_BUTTONS:
            btn = getattr(self, attr, None)
            try:
                if btn is not None and btn.isChecked():
                    return mode
            except Exception:
                continue
        return "draw"

    def set_edit_mode_buttons(self, mode):
        """按模式勾/取消**所有**模式按钮（**互斥**：最多一个；其它值 ⇒ 都不选）

        ★ 收口处顺带刷新"选中态变异色"样式与常驻"当前模式"文案
          ⇒ 只要模式变更走这里（W2 现在就是这么调的），长相一定跟得上。
        """
        m = str(mode or "").strip().lower()
        if m not in self.MODE_LABELS:
            m = "draw"
        for attr, btn_mode in self.MODE_BUTTONS:
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.setChecked(m == btn_mode)
            except Exception:
                continue
        self.apply_mode_button_styles()
        self.update_mode_label()
        return self.edit_mode_from_buttons()

    # ---- 模式按钮的"长相"（N 个按钮通用；与按钮个数、顺序无关）----
    def _add_mode_button(self, row, attr_name, text, parent):
        """建一个模式按钮：工厂自带选中态变异色 + 主题注册 + `dshModeToggle` 标记"""
        btn = create_styled_mode_toggle(text, parent=parent, fixed_height=self.H_BTN)
        setattr(self, attr_name, btn)
        try:
            self._mode_buttons.append(btn)
        except Exception:
            pass
        # 只刷"长相"，**不改按钮状态**（互斥/模式语义归 W2；见 _refresh_mode_visuals）
        try:
            btn.toggled.connect(self._refresh_mode_visuals)
        except Exception:
            pass
        row.addWidget(btn)
        return btn

    def mode_buttons(self, discover=True):
        """全部模式按钮：登记表优先，`discover=True` 时按工厂标记**自动发现**

        ⇒ 任何人用 `create_styled_mode_toggle` 新建的模式按钮都会被自动纳入样式刷新，
          **不需要改本文件的样式代码**。
        """
        out = []
        for btn in (getattr(self, '_mode_buttons', None) or []):
            if btn is not None and btn not in out:
                out.append(btn)
        if discover:
            try:
                page = getattr(self, 'spatial_region_page', None)
                if page is not None:
                    for child in page.findChildren(QPushButton):
                        if child.property(MODE_TOGGLE_PROPERTY) and child not in out:
                            out.append(child)
            except Exception:
                pass
        return out

    def apply_mode_button_styles(self, buttons=None):
        """给**任意个数**的模式按钮套"选中态 = 变异色"样式

        Args:
            buttons: 指定按钮列表（None = 自动发现全部模式按钮）
        Returns: int —— 实际套上样式的按钮数
        """
        target = list(buttons) if buttons else self.mode_buttons()
        return apply_mode_toggle_styles(target)

    def update_mode_label(self):
        """刷新常驻"当前模式"文案（都不勾 → 「当前模式：绘制」）"""
        mode = self.edit_mode_from_buttons()
        text = "当前模式：%s" % self.MODE_LABELS.get(mode, mode)
        try:
            self.region_mode_label.setText(text)
        except Exception:
            pass
        return text

    def _refresh_mode_visuals(self, *args):
        """某个模式按钮 toggled → 重套样式 + 刷新文案（**只改长相，不动状态**）"""
        try:
            self.apply_mode_button_styles()
            self.update_mode_label()
        except Exception:
            pass

    def _create_property_panel(self, parent, layout):
        """右栏：区域属性（名字/颜色/虚线/字号字色）+ 区域列表 + 操作按钮 + 日志"""
        # ★ v2 纵向预算（1920×1000 实测；协调者 2026-09-23 拍板「真回归必须修」）：
        #   本面板高 904px（内容区 888px）。只加"两级命名"那条 80px 列表后，
        #   布局最小高 807 → 908（默认态）/ 944（"自定义"态：输入框+确定显示时）
        #   ⇒ 冻结控件 `region_list_widget` 被压到 71px（应为 120px），
        #      `region_log_text` 底边越界被面板裁掉。
        #   **只压本面板行间距 + 新增列表高度，不动任何冻结控件**：
        #     · 行间距 6 → 3（21 个布局项 ⇒ 20 个间隙，回收 ≈60px）
        #     · `region_anno_list` 最大高 80 → 64（列表最小高随之 71 → 64，回收 7px；
        #       64 = 协调者 2026-09-23 选定档："能看 3 行注释"，仍满足下面三条）
        #   实测（修复后）：默认态最小高 → 847（`region_list_widget` 恢复 120px）；
        #     "自定义"态 → 880 ≤ 904（两者日志底边 888 / 896 均在面板内）。
        #   ★ 整页恒按 1920×1000 建（`page_intersect.py` 传 base_width/base_height，
        #     整场由 QGraphicsView 缩放贴合屏幕）⇒ 面板恒 904 高，余量是确定的。
        #   ⛔ spacing 不要再低于 3；⛔ 不要动其它控件的固定高度。
        layout.setSpacing(3)
        layout.addWidget(create_styled_label("区域属性", font_size=12, parent=parent))

        # ---- 区域分组（两级命名①：**不可编辑**下拉；items 由 bind 按 §4.1 填）----
        #   ★ 用户原话：「区域名可自由输入直接给个输入框太直接了，容易输入错」
        #     ⇒ 控件名仍是冻结的 `region_name_input`，但语义 = **分组下拉框**，
        #       不许再自由输入（`setEditable(False)`）。
        layout.addWidget(create_styled_label("区域分组", font_size=9,
                                             bold=False, parent=parent))
        self.region_name_input = create_styled_combo_box(parent=parent)
        self.region_name_input.setEditable(False)
        self.region_name_input.setFixedHeight(self.H_INPUT)
        # 占位文案（Qt≥5.15 才有 setPlaceholderText；拿不到就跳过，不抛）
        set_placeholder = getattr(self.region_name_input, 'setPlaceholderText', None)
        if callable(set_placeholder):
            set_placeholder("（分组由样本数据填充）")
        layout.addWidget(self.region_name_input)

        # ---- 细分注释选择框（两级命名②：紧贴分组下拉**下方**，与小提琴 combo 上/list 下同构）----
        #   ★ 选项内容由 bind 按当前分组回填（契约 §4.2）；本层只建控件。
        #   ★ 高度：契约 §3 原写 80，但 1920×1000 下 80 会把右栏挤爆
        #     （见 `_create_property_panel` 顶部的预算账）⇒ 经协调者 2026-09-23 授权
        #     下调到 **64**（≥56 的下限之上：能看 3 行注释 + 滚动，对挑选注释更友好；
        #     工厂走的是 `setMaximumHeight`，即"最多 64"，不是 `setFixedHeight`）。
        #   ★ 整页**恒按 1920×1000 建**（`page_intersect.py` 传 base_width/base_height，
        #     整场再由 QGraphicsView 缩放贴合屏幕）⇒ 属性面板恒为 904 高，余量是确定的，
        #     64 档实测：默认态布局最小高 847（`region_list_widget` 仍满 120px）、
        #     "自定义"态 880 ≤ 904（日志底边 896，不裁）。
        self.region_anno_list = create_styled_list_widget(
            parent=parent, fixed_height=64, multi_selection=False)
        layout.addWidget(self.region_anno_list)

        # ---- 自定义注释：输入框 + 确定按钮（**同一行**；初始隐藏，显隐由 bind §4.2 控制）----
        self.region_anno_input = create_styled_line_edit(parent=parent)
        self.region_anno_input.setFixedHeight(self.H_INPUT)
        self.region_anno_input.setVisible(False)
        self.btn_region_anno_ok = create_styled_button(
            "确定", font_size=10, parent=parent, button_type='run')
        self.btn_region_anno_ok.setFixedHeight(self.H_ROW)
        self.btn_region_anno_ok.setVisible(False)
        anno_row = QHBoxLayout()
        # ★ 本行是"页内联排"，**不要**子布局默认的 9px 边距：右栏纵向预算紧
        #   （1920×1000 下面板内容区高 888px，两级命名已占一条 64px 列表），
        #   "自定义"态（输入框 + 确定显示时）默认边距会白吃 18px 高度。
        anno_row.setContentsMargins(0, 0, 0, 0)
        anno_row.addWidget(self.region_anno_input, stretch=1)
        anno_row.addWidget(self.btn_region_anno_ok)
        layout.addLayout(anno_row)
        # ★ `region_name_edit`（旧自由文本 `combo.lineEdit()`）**已删除**：
        #   `setEditable(False)` 后它本来就是 `None`，留着只会误导（契约 §3）。

        # ---- 区域颜色 ----
        layout.addWidget(create_styled_label("区域颜色", font_size=9, bold=False, parent=parent))
        self.region_color_palette, _ = create_styled_color_palette(
            parent=parent, selected="#FF6B35")
        layout.addWidget(self.region_color_palette)

        # ---- 虚线粗细 / 间距 ----
        dash_row = QHBoxLayout()
        dash_row.addWidget(create_styled_label("虚线粗", font_size=9, bold=False, parent=parent))
        self.region_dash_width_input = create_signaled_number_input(
            parent=parent, fixed_height=self.H_ROW, min_value=1, max_value=10,
            default_value=2, step=1)
        self.region_dash_width_input.setFixedHeight(self.H_ROW)
        dash_row.addWidget(self.region_dash_width_input)
        dash_row.addWidget(create_styled_label("间距", font_size=9, bold=False, parent=parent))
        self.region_dash_gap_input = create_signaled_number_input(
            parent=parent, fixed_height=self.H_ROW, min_value=1, max_value=30,
            default_value=6, step=1)
        self.region_dash_gap_input.setFixedHeight(self.H_ROW)
        dash_row.addWidget(self.region_dash_gap_input)
        layout.addLayout(dash_row)

        # ---- 圆角（§15.3 corner_radius_px：**仅呈现**，判定永远用尖角多边形）----
        corner_row = QHBoxLayout()
        corner_row.addWidget(create_styled_label("圆角", font_size=9, bold=False, parent=parent))
        self.region_corner_radius_input = create_signaled_number_input(
            parent=parent, fixed_height=self.H_ROW, min_value=0, max_value=40,
            default_value=0, step=1)
        self.region_corner_radius_input.setFixedHeight(self.H_ROW)
        corner_row.addWidget(self.region_corner_radius_input)
        corner_row.addStretch()
        layout.addLayout(corner_row)

        # ---- 注释圆角外框（Phase 4⑤ `chk_label_frame`：默认**不勾**）----
        self.chk_label_frame = create_styled_checkbox(
            "注释加圆角矩形外框", parent=parent, fixed_height=self.H_ROW)
        try:
            self.chk_label_frame.setChecked(False)
        except Exception:
            pass
        layout.addWidget(self.chk_label_frame)

        # ---- 注释外框颜色（v4：结果图里 `geom_label` 圆角矩形底框的颜色）----
        #   默认 `#FFFFFF` = 现在的写死白底（用户不选时行为不变）。
        #   ★ 只在本层建控件；成图侧由 W2 读该调色板（画布暂不画外框）。
        layout.addWidget(create_styled_label("注释外框颜色（仅成图）", font_size=9,
                                            bold=False, parent=parent))
        self.region_label_frame_color_palette, _ = create_styled_color_palette(
            parent=parent, selected="#FFFFFF")
        layout.addWidget(self.region_label_frame_color_palette)

        # ---- 注释字号 / 字色 ----
        font_row = QHBoxLayout()
        font_row.addWidget(create_styled_label("字号", font_size=9, bold=False, parent=parent))
        self.region_font_size_input = create_signaled_number_input(
            parent=parent, fixed_height=self.H_ROW, min_value=6, max_value=48,
            default_value=12, step=1)
        self.region_font_size_input.setFixedHeight(self.H_ROW)
        font_row.addWidget(self.region_font_size_input)
        layout.addLayout(font_row)

        layout.addWidget(create_styled_label("注释字色", font_size=9, bold=False, parent=parent))
        self.region_font_color_palette, _ = create_styled_color_palette(
            parent=parent, selected="#FFFFFF")
        layout.addWidget(self.region_font_color_palette)

        # ---- 已有区域列表 ----
        layout.addWidget(create_styled_label("已画区域（选中可删）", font_size=9,
                                             bold=False, parent=parent))
        self.region_list_widget = create_styled_list_widget(
            parent=parent, fixed_height=120, multi_selection=False)
        # ★ Phase 5：bind 重建列表（clear + 自己的格式串）时，**选区标记不被冲掉**
        #   —— 加入的条目按画布当前区域重算整行（含 `🫥 [选区]`）。
        try:
            install_region_list_autostamp(self.region_list_widget,
                                          self.region_canvas.get_regions)
        except Exception:
            pass
        layout.addWidget(self.region_list_widget)

        # ---- 操作按钮（两列两行，固定高度）----
        row1 = QHBoxLayout()
        self.btn_region_confirm = create_styled_button(
            "确认并重绘", font_size=10, parent=parent, button_type='run')
        self.btn_region_confirm.setFixedHeight(self.H_BTN)
        row1.addWidget(self.btn_region_confirm)
        self.btn_region_undo = create_styled_button(
            "撤销上一点", font_size=10, parent=parent, button_type='normal')
        self.btn_region_undo.setFixedHeight(self.H_BTN)
        row1.addWidget(self.btn_region_undo)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_region_delete = create_styled_button(
            "删除选中区域", font_size=10, parent=parent, button_type='normal')
        self.btn_region_delete.setFixedHeight(self.H_BTN)
        row2.addWidget(self.btn_region_delete)
        self.btn_region_clear = create_styled_button(
            "清空本样本区域", font_size=10, parent=parent, button_type='normal')
        self.btn_region_clear.setFixedHeight(self.H_BTN)
        row2.addWidget(self.btn_region_clear)
        layout.addLayout(row2)

        # ---- 日志（定高，余量给弹簧）----
        self.region_log_text = create_styled_text_edit(read_only=True)
        self.region_log_text.setFixedHeight(self.H_LOG)
        self.region_log_text.setFont(get_font_for_widget('label', 10))
        self.region_log_text.setText("等待操作...")
        layout.addWidget(self.region_log_text)

        layout.addStretch()

    # ------------------------------------------------------------------
    def create_page(self):
        self.spatial_region_page = QWidget(self.parent)
        self.region_canvas = None          # 先占位，供 update_styles 守卫
        self._region_counts = {}           # {样本号: 区域个数}（只由 W2 传入，本层不读文件）

        styles = get_mod_styles()
        paths = get_mod_paths()

        bg_label = QLabel(self.spatial_region_page)
        bg_label.setObjectName("spatial_region_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(
                f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.spatial_region_page)
        overlay.setObjectName("spatial_region_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(
            f"background: {styles.get('overlay_background', styles.get('sub_fill_color', 'rgba(26, 26, 46, 0.3)'))};")

        main_layout = QHBoxLayout(overlay)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 左导航 =====
        nav_panel, nav_layout = create_navigation_panel(parent=overlay, fixed_width=220)

        self.nav_btn_back = create_navigation_button("← 返回审查", font_size=13, parent=nav_panel)
        nav_layout.addWidget(self.nav_btn_back)

        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_divider(parent=nav_panel))
        nav_layout.addSpacing(10)
        nav_layout.addWidget(create_navigation_header("绘制区域", font_size=11, parent=nav_panel))

        self.region_nav_hint = create_styled_label(
            "手画虚线分区，\n改掉太细碎的注释；\n圈外一律为 NA。",
            font_size=10, bold=False, parent=nav_panel)
        self.region_nav_hint.setWordWrap(True)
        nav_layout.addWidget(self.region_nav_hint)

        nav_layout.addSpacing(10)
        self._create_sample_panel(nav_panel, nav_layout)
        nav_layout.addStretch()

        main_layout.addWidget(nav_panel)

        # ===== 中部内容 =====
        content_panel = QWidget(overlay)
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)

        top_bar, top_bar_layout = create_styled_panel(parent=content_panel)
        top_bar_layout.setContentsMargins(15, 8, 15, 8)
        title_row_layout = QHBoxLayout()

        title_label = QLabel("绘制区域")
        title_label.setObjectName("spatial_region_title")
        title_label.setFont(get_font_for_widget('button', 24, bold=True))
        title_label.setStyleSheet(
            f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#FF6B35'))};")
        title_label.setAlignment(Qt.AlignCenter)
        title_row_layout.addWidget(title_label)

        mod_instance = global_mod_manager.get_current_mod()
        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.spatial_region_page, mod_instance)
        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(
            music_container_width, music_container_height, variant='sub')
        title_row_layout.addWidget(music_container)

        title_row_layout.setStretch(0, 5)
        title_row_layout.setStretch(1, 1)
        top_bar_layout.addLayout(title_row_layout)
        content_layout.addWidget(top_bar)

        # 三栏：画布(stretch) + 右属性面板(约 300)
        body = QWidget(content_panel)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(16, 8, 16, 16)
        body_layout.setSpacing(12)

        canvas_panel, canvas_layout = create_styled_panel(parent=body)
        canvas_layout.setContentsMargins(8, 8, 8, 8)
        self._create_canvas_panel(canvas_panel, canvas_layout)
        body_layout.addWidget(canvas_panel, stretch=1)

        prop_panel, prop_layout = create_styled_panel(parent=body, fixed_width=300)
        prop_layout.setContentsMargins(8, 8, 8, 8)
        self._create_property_panel(prop_panel, prop_layout)
        body_layout.addWidget(prop_panel)

        content_layout.addWidget(body, stretch=1)
        main_layout.addWidget(content_panel)

        return self.spatial_region_page


__all__ = ['SpatialRegionPageUI']
