# -*- coding: utf-8 -*-
"""
scRNAseq 虚拟敲除界面UI布局脚本 - 只负责创建控件、规划窗口布局、摆放按钮/输入框/画布、设置样式尺寸
完全不写按钮点击、触发逻辑

布局依据：虚拟敲除层_实装说明书 §5.0~§5.8（标签与 help 文案逐字照抄）
控件冻结名：_d_spec_virtual_knockout.md §2（全部 vk_ 前缀）
"""

from script.utils_layer.import_config import *
from script.utils_layer.gui_styles import (
    get_mod_styles, get_mod_paths, get_stylesheet_for_widget, get_font_for_widget,
    create_styled_button, create_styled_label, create_styled_combo_box,
    create_styled_line_edit, create_styled_text_edit, create_styled_checkbox,
    create_styled_spinbox, create_styled_list_widget, create_styled_table,
    create_styled_panel, create_styled_group_box, create_styled_tab_widget,
    create_styled_tab_page, create_styled_image_tab, create_styled_progress_bar,
    create_labeled_param_with_help, create_questions_button
)
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.page_intersect import page_intersect

class VirtualKnockoutPageUI:
    def __init__(self, parent_widget, screen_width, screen_height):
        self.parent = parent_widget
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.virtual_knockout_page = None
        self.create_page()

    def update_background(self):
        styles = get_mod_styles()
        paths = get_mod_paths()
        bg_label = self.virtual_knockout_page.findChild(QLabel, "virtual_knockout_bg")
        if bg_label:
            if os.path.exists(paths['BG_IMAGE_PATH']):
                pixmap = QPixmap(paths['BG_IMAGE_PATH'])
                scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                              Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                bg_label.setPixmap(scaled_pixmap)
            else:
                bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")

    def update_styles(self):
        styles = get_mod_styles()

        title_label = self.virtual_knockout_page.findChild(QLabel, "virtual_knockout_title")
        if title_label:
            title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', styles.get('mutant_color', '#E91E63'))};")

        overlay = self.virtual_knockout_page.findChild(QWidget, "virtual_knockout_overlay")
        if overlay:
            overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        self.update_background()

    # ================================================================
    # 布局辅助：可折叠分组
    # ----------------------------------------------------------------
    # gui_styles 的 create_styled_group_box 只给 QGroupBox（单控件），
    # 工厂没有做"可折叠"；说明书 §5.6 要求【高级】组可折叠。
    # 这里自己实现：setCheckable(True) + setChecked(True) + 内部 content 容器，
    # 用 gb.toggled 控制 content 显隐。
    # ★ 这属于"布局行为"（折叠显隐），不是业务逻辑；除此之外本文件不连任何信号。
    # ================================================================
    def _make_collapsible_group(self, title):
        group_box = create_styled_group_box(title)
        # 工厂只建了 QGroupBox 并上了样式，**没有给它挂 layout**
        # （create_styled_group_box 里没有 setLayout / QVBoxLayout(group_box)），
        # 所以这里必须自己建 layout 并挂上，否则 group_box.layout() 是 None。
        group_box_layout = QVBoxLayout(group_box)
        group_box_layout.setContentsMargins(6, 6, 6, 6)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)
        group_box_layout.addWidget(content)
        group_box.setCheckable(True)
        group_box.setChecked(True)
        group_box.toggled.connect(lambda on: content.setVisible(on))
        return group_box, content_layout

    def create_page(self):
        self.virtual_knockout_page = QWidget(self.parent)

        styles = get_mod_styles()
        paths = get_mod_paths()
        mod_instance = global_mod_manager.get_current_mod()

        bg_label = QLabel(self.virtual_knockout_page)
        bg_label.setObjectName("virtual_knockout_bg")
        bg_label.setGeometry(0, 0, self.screen_width, self.screen_height)
        if os.path.exists(paths['BG_IMAGE_PATH']):
            pixmap = QPixmap(paths['BG_IMAGE_PATH'])
            scaled_pixmap = pixmap.scaled(self.screen_width, self.screen_height,
                                          Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            bg_label.setPixmap(scaled_pixmap)
        else:
            bg_label.setStyleSheet(f"background-color: {styles.get('sub_fill_color', 'rgba(26, 26, 46, 1)')};")
        bg_label.lower()

        overlay = QWidget(self.virtual_knockout_page)
        overlay.setObjectName("virtual_knockout_overlay")
        overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        overlay.setStyleSheet(f"background: {styles.get('overlay_background', 'rgba(0,0,0,0.3)')};")

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()

        self.btn_back_virtual_knockout = create_styled_button("← 返回上一页", font_size=12)
        top_layout.addWidget(self.btn_back_virtual_knockout)

        title_label = QLabel("虚拟敲除")
        title_label.setObjectName("virtual_knockout_title")
        title_label.setFont(get_font_for_widget('button', 32, bold=True))
        title_label.setStyleSheet(f"color: {styles.get('sub_mutant_color', '#E91E63')};")
        title_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title_label)

        MusicControllerClass = mod_instance.get_music_controller_class()
        self.music_controller = MusicControllerClass(self.virtual_knockout_page, mod_instance)

        music_container_width = styles.get('music_container_width', 200)
        music_container_height = styles.get('music_container_height', 50)
        music_container = self.music_controller.create_music_controls(music_container_width, music_container_height, variant='sub')

        music_container_x = styles.get('music_container_x', 0.85)
        music_container_y = styles.get('music_container_y', 15)
        if isinstance(music_container_x, float):
            music_container_x = int(self.screen_width * music_container_x)
        music_container.move(music_container_x, music_container_y)

        top_layout.addWidget(music_container)

        top_layout.setStretch(0, 1)
        top_layout.setStretch(1, 3)
        top_layout.setStretch(2, 1)
        layout.addLayout(top_layout)

        # ============================================================
        # 主区域：左侧参数面板（fixed_width=380，内容必须可滚动）+ 右侧结果区
        # 说明书 §5.0
        # ============================================================
        main_layout = QHBoxLayout()

        # ---------- 左侧参数面板（可滚动） ----------
        # 照抄 sc_monocle_genelists_layer/ui_layout_sc_monocle_genelists.py:203-215 的写法
        left_panel, left_outer_layout = create_styled_panel(fixed_width=380)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # 滚动区不手写样式：静态闸门 ③ 只允许骨架 bg_label/overlay/title_label 三个接收者
        # 调 setStyleSheet。滚动区保持透明（QScrollArea 默认），不影响滚动功能。

        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # ===== 【靶基因】组（说明书 §5.3）=====
        # ★ 用户要求「靶基因填写控件放在最顶上」，故本组为左栏第 1 组；
        #   其余 5 组相对顺序不变：【靶基因】→【细胞选择】→【基因选择】→【质控】→【统计与校准】→【高级】。
        gb_gko, l_gko = self._make_collapsible_group("【靶基因】")

        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "靶基因（必填）",
            "要虚拟敲除的基因名（如 SOX2）。\n必须存在于表达矩阵中。\n若它不在所选基因面板里，程序会自动把它加入面板并提示。",
            font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_gko.addLayout(row)

        self.vk_gko_edit = create_styled_line_edit(fixed_width=160)
        l_gko.addWidget(self.vk_gko_edit)

        left_layout.addWidget(gb_gko)

        # ===== 【细胞选择】组（说明书 §5.1）=====
        gb_cell, l_cell = self._make_collapsible_group("【细胞选择】")

        # 分组列：标签 + help（标签原文逐字）
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "分组选择",
            "选择用于分组的注释列（来自 Seurat 对象的 meta.data）。\n"
            "取不到默认列时用第一个分类列。",
            font_size=12, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_cell.addLayout(row)

        l_cell.addWidget(create_styled_label("选择用于分组的注释列", font_size=9, bold=False))

        self.vk_group_combo = create_styled_combo_box()
        l_cell.addWidget(self.vk_group_combo)

        l_cell.addSpacing(6)

        _lbl, _hbtn = create_labeled_param_with_help(
            "组别（多选）",
            "从分组列的唯一值里多选组别。\n不选 = 全选；多选后按并集取细胞。",
            font_size=10, bold=True)
        row = QHBoxLayout()
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_cell.addLayout(row)

        self.vk_group_list = create_styled_list_widget(fixed_height=90, multi_selection=True)
        l_cell.addWidget(self.vk_group_list)

        self.vk_group_hint = create_styled_label("不选=全选；多选后按并集取细胞", font_size=9, bold=False)
        l_cell.addWidget(self.vk_group_hint)

        l_cell.addSpacing(6)

        # 筛选条件1（可选）
        self.vk_filter1_col = create_styled_combo_box()
        self.vk_filter1_col.addItem("（不使用）")
        l_cell.addWidget(create_styled_label("筛选条件1（可选）", font_size=10, bold=True))
        l_cell.addWidget(self.vk_filter1_col)

        self.vk_filter1_list = create_styled_list_widget(fixed_height=70, multi_selection=True)
        self.vk_filter1_list.setEnabled(False)
        l_cell.addWidget(self.vk_filter1_list)

        l_cell.addSpacing(6)

        # 筛选条件2（可选）
        self.vk_filter2_col = create_styled_combo_box()
        self.vk_filter2_col.addItem("（不使用）")
        l_cell.addWidget(create_styled_label("筛选条件2（可选）", font_size=10, bold=True))
        l_cell.addWidget(self.vk_filter2_col)

        self.vk_filter2_list = create_styled_list_widget(fixed_height=70, multi_selection=True)
        self.vk_filter2_list.setEnabled(False)
        l_cell.addWidget(self.vk_filter2_list)

        left_layout.addWidget(gb_cell)

        # ===== 【基因选择】组（说明书 §5.2）=====
        gb_gene, l_gene = self._make_collapsible_group("【基因选择】")

        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "基因来源",
            "全部基因：用矩阵里全部基因（基因多时极耗内存，5000 基因约 8.6 GB、10000 基因约 34 GB）。\n高变基因前 N：按方差取前 N 个（推荐，默认 1000）。\n外部基因列表：使用 appdata/genelists 下的 xlsx/txt/csv 文件。\n不选外部列表文件时该模式不生效。",
            font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_gene.addLayout(row)

        self.vk_gene_mode_combo = create_styled_combo_box()
        self.vk_gene_mode_combo.addItem("全部基因", "all")
        self.vk_gene_mode_combo.addItem("高变基因前 N", "hvg")
        self.vk_gene_mode_combo.addItem("外部基因列表", "list")
        self.vk_gene_mode_combo.setCurrentIndex(1)
        l_gene.addWidget(self.vk_gene_mode_combo)

        l_gene.addSpacing(6)

        # 高变基因数 N（仅 hvg 模式可见）
        self.vk_hvg_n_label = create_styled_label("高变基因数 N", font_size=10, bold=True)
        l_gene.addWidget(self.vk_hvg_n_label)
        self.vk_hvg_n_spin = create_styled_spinbox(min_value=100, max_value=5000, default_value=1000, step=100)
        l_gene.addWidget(self.vk_hvg_n_spin)
        self.vk_hvg_n_hint = create_styled_label(
            "按方差取前 N 个（推荐，默认 1000）；基因越多越耗内存，内存按基因数平方增长。",
            font_size=9, bold=False)
        self.vk_hvg_n_hint.setWordWrap(True)
        l_gene.addWidget(self.vk_hvg_n_hint)

        l_gene.addSpacing(6)

        # 基因列表文件（仅 list 模式可见）
        # 标签与 help 分开建：W2 的 apply_gene_mode_visibility() 要连标签一起 setVisible
        self.vk_gene_list_label = create_styled_label("基因列表文件（appdata/genelists）", font_size=10, bold=True)
        l_gene.addWidget(self.vk_gene_list_label)
        self.vk_gene_list_help_btn = create_questions_button(
            "从 appdata/genelists 目录选择基因列表。\n支持 xlsx（第一列为基因名，无表头）与 txt（每行一个基因）。\n留空或不选 = 不使用外部列表。")
        l_gene.addWidget(self.vk_gene_list_help_btn)

        self.vk_gene_list_combo = create_styled_combo_box()
        # 第 1 项文本 = 空字符串（说明书 §5.2：「列表文件 … 默认 空 = 不使用」）。
        # ★ 这里**不能**用 §5.1 给筛选列下拉定的「（不使用）」字面量：
        #   W2 的 bind 取 currentText()，空 ⇒ 跳过外部列表；非空 ⇒ 当文件名去
        #   APPDATA_PATH/genelists/<名字> 找文件。若给「（不使用）」会被当文件名去找而报错。
        self.vk_gene_list_combo.addItem("")
        l_gene.addWidget(self.vk_gene_list_combo)

        self.vk_gene_list_path_label = create_styled_label("（未选择）", font_size=9, bold=False)
        l_gene.addWidget(self.vk_gene_list_path_label)

        self.vk_gene_list_hint = create_styled_label(
            "不选列表文件时该模式不生效（运行时会按高变基因前 N 兜底并在日志中说明）。",
            font_size=9, bold=False)
        self.vk_gene_list_hint.setWordWrap(True)
        l_gene.addWidget(self.vk_gene_list_hint)

        l_gene.addSpacing(6)

        self.vk_drop_mt_check = create_styled_checkbox("剔除线粒体基因")
        self.vk_drop_mt_check.setChecked(True)
        l_gene.addWidget(self.vk_drop_mt_check)

        self.vk_drop_ribo_check = create_styled_checkbox("剔除核糖体基因")
        self.vk_drop_ribo_check.setChecked(True)
        l_gene.addWidget(self.vk_drop_ribo_check)

        self.vk_gene_hint = create_styled_label(
            "生成的基因面板会剔除 MT-/MTRNR/MTATP/MTCO/MTCYB/MTND 与 RPS/RPL/MRPS/MRPL；靶基因一定会被加入面板",
            font_size=9, bold=False)
        self.vk_gene_hint.setWordWrap(True)
        l_gene.addWidget(self.vk_gene_hint)

        # 模式联动后的初始显隐：默认模式 = hvg（setCurrentIndex(1)）
        #   ⇒ vk_hvg_n_label / vk_hvg_n_spin / vk_hvg_n_hint 可见；
        #      vk_gene_list_label / vk_gene_list_help_btn / vk_gene_list_combo /
        #      vk_gene_list_path_label / vk_gene_list_hint 隐藏。
        # （照抄 ui_layout_sc_monocle_genelists.py:313-332 的 setVisible 写法；
        #   运行期切换联动归 W2 的 bind，本文件不连任何业务信号）
        self.vk_hvg_n_label.setVisible(True)
        self.vk_hvg_n_spin.setVisible(True)
        self.vk_hvg_n_hint.setVisible(True)
        self.vk_gene_list_label.setVisible(False)
        self.vk_gene_list_help_btn.setVisible(False)
        self.vk_gene_list_combo.setVisible(False)
        self.vk_gene_list_path_label.setVisible(False)
        self.vk_gene_list_hint.setVisible(False)

        left_layout.addWidget(gb_gene)

        # ===== 【质控】组（说明书 §5.4）=====
        gb_qc, l_qc = self._make_collapsible_group("【质控】")

        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "启用质控（在全部基因上做）",
            "质控在「全部基因 × 全部候选细胞」的矩阵上进行，做完再取高变基因面板。\n若反过来（先取面板再质控），文库大小会被严重低估，默认 1000 可能把细胞全部滤掉。",
            font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_qc.addLayout(row)

        self.vk_qc_check = create_styled_checkbox("启用质控（在全部基因上做）")
        self.vk_qc_check.setChecked(True)
        l_qc.addWidget(self.vk_qc_check)

        l_qc.addSpacing(6)

        self.vk_qc_minlib_spin = create_styled_spinbox(min_value=0, max_value=100000, default_value=1000, step=100)
        l_qc.addWidget(create_styled_label("最小文库大小", font_size=10, bold=True))
        l_qc.addWidget(self.vk_qc_minlib_spin)

        self.vk_qc_minpct_spin = create_styled_spinbox(min_value=0, max_value=1, default_value=0.05, step=0.01)
        l_qc.addWidget(create_styled_label("基因最小表达占比", font_size=10, bold=True))
        l_qc.addWidget(self.vk_qc_minpct_spin)

        self.vk_qc_mtratio_spin = create_styled_spinbox(min_value=0, max_value=1, default_value=0.1, step=0.01)
        l_qc.addWidget(create_styled_label("线粒体比例上限", font_size=10, bold=True))
        l_qc.addWidget(self.vk_qc_mtratio_spin)

        self.vk_qc_outlier_check = create_styled_checkbox("去除离群细胞")
        self.vk_qc_outlier_check.setChecked(True)
        l_qc.addWidget(self.vk_qc_outlier_check)

        self.vk_qc_hint = create_styled_label(
            "质控在全部基因上做，做完再取高变基因面板；矩阵里若没有 MT- 开头的基因，R 端会跳过线粒体过滤并打印提示。",
            font_size=9, bold=False)
        self.vk_qc_hint.setWordWrap(True)
        l_qc.addWidget(self.vk_qc_hint)

        left_layout.addWidget(gb_qc)

        # ===== 【统计与校准】组（说明书 §5.5）=====
        gb_stat, l_stat = self._make_collapsible_group("【统计与校准】")

        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "从显著性校准中排除被敲基因（推荐）",
            "被敲基因的位移是\"人为把它的出边置零\"的直接结果，属于同义反复、不是发现。\n它通常占全部基因距离平方和的 90%~99%，会把其余所有基因的 p 值整体压低（实测：不排除时只有靶基因自己显著；排除后同一份数据可得到 19 个显著基因）。\n默认开启。无论开关如何，两种口径的数字都会并列写盘。",
            font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_stat.addLayout(row)

        self.vk_exclude_gko_check = create_styled_checkbox("从显著性校准中排除被敲基因（推荐）")
        self.vk_exclude_gko_check.setChecked(True)
        l_stat.addWidget(self.vk_exclude_gko_check)

        l_stat.addSpacing(6)

        self.vk_fdr_spin = create_styled_spinbox(min_value=0, max_value=1, default_value=0.05, step=0.01)
        l_stat.addWidget(create_styled_label("FDR 阈值", font_size=10, bold=True))
        l_stat.addWidget(self.vk_fdr_spin)

        l_stat.addSpacing(6)

        # 经验零分布：说明书 §5.5 要求置灰（需要 locfdr 包，当前环境未安装）
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "经验零分布（Efron）",
            "需要 locfdr 包，当前环境未安装。\n该项不可用。",
            font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_stat.addLayout(row)

        self.vk_empnull_check = create_styled_checkbox("经验零分布（Efron）")
        self.vk_empnull_check.setChecked(False)
        self.vk_empnull_check.setEnabled(False)
        l_stat.addWidget(self.vk_empnull_check)

        left_layout.addWidget(gb_stat)

        # ===== 【高级】组（可折叠，说明书 §5.6）=====
        gb_adv, l_adv = self._make_collapsible_group("【高级】")

        self.vk_nnet_spin = create_styled_spinbox(min_value=3, max_value=20, default_value=10, step=1)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "网络个数 nc_nNet", "网络越多越稳、越慢；10 是官方默认。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_nnet_spin)

        self.vk_ncells_spin = create_styled_spinbox(min_value=50, max_value=2000, default_value=500, step=50)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "每网络子采样细胞数 nc_nCells", "不能超过可用细胞数，程序会自动下调。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_ncells_spin)

        self.vk_ncomp_spin = create_styled_spinbox(min_value=2, max_value=10, default_value=3, step=1)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "主成分数 nc_nComp", "官方默认 3。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_ncomp_spin)

        self.vk_nq_spin = create_styled_spinbox(min_value=0.5, max_value=0.99, default_value=0.9, step=0.01)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "关系分位 nc_q", "越大保留的关系越多、网络越稠密。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_nq_spin)

        self.vk_tdk_spin = create_styled_spinbox(min_value=1, max_value=10, default_value=3, step=1)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "张量秩 td_K", "官方默认 3。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_tdk_spin)

        self.vk_madim_spin = create_styled_spinbox(min_value=2, max_value=10, default_value=2, step=1)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "对齐维度 ma_nDim", "默认 2（出图与距离都用它）。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_madim_spin)

        self.vk_seed_spin = create_styled_spinbox(min_value=0, max_value=99999, default_value=1, step=1)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "随机种子 seed", "同一种子同一结果；换种子可看稳定性。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_seed_spin)

        self.vk_ncores_spin = create_styled_spinbox(min_value=1, max_value=16, default_value=4, step=1)
        row = QHBoxLayout()
        _lbl, _hbtn = create_labeled_param_with_help(
            "并行核数 nCores", "过大与 BLAS 线程叠加可能反而更慢。", font_size=10, bold=True)
        row.addWidget(_lbl)
        row.addWidget(_hbtn)
        row.addStretch()
        l_adv.addLayout(row)
        l_adv.addWidget(self.vk_ncores_spin)

        left_layout.addWidget(gb_adv)

        left_layout.addStretch()

        left_scroll.setWidget(left_content)
        left_outer_layout.addWidget(left_scroll)

        main_layout.addWidget(left_panel)

        # ---------- 右侧结果区（说明书 §5.7/§5.8） ----------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        run_row = QHBoxLayout()
        self.vk_btn_run = create_styled_button("运行虚拟敲除", font_size=14, button_type='run')
        run_row.addWidget(self.vk_btn_run)

        # ★ 「发送到列表文件夹」（契约 docs/features/gene_list_send_contract.md §4）：
        #   紧邻「运行虚拟敲除」放在结果区首行（本页**没有**其它导出/保存按钮），
        #   控件来自 gui_styles 工厂、导出族样式。
        #   ⚠ 语义：把**当前结果的显著基因**（`diffRegulation_significant.csv` 那批 `gene`）
        #      写进 `appdata/genelists`（单列无表头 xlsx），供后续分析的下拉框直接抓取。
        #   ⛔ 本层**只建控件**：不连接信号、不弹文件对话框、不调用系统打开
        #      （连接与取数/落盘全在 `ui_bind_virtual_knockout.py` 的 `on_send_to_genelist`）。
        self.vk_btn_send_to_genelist = create_styled_button(
            "发送到列表文件夹", font_size=12, button_type='export')
        run_row.addWidget(self.vk_btn_send_to_genelist)

        # 红字口径/出边警告位（说明书 §5.5/§8.8/§10）
        self.vk_warn_label = create_styled_label("", font_size=11, bold=True)
        run_row.addWidget(self.vk_warn_label)

        run_row.addStretch()
        right_layout.addLayout(run_row)

        self.vk_progress = create_styled_progress_bar()
        self.vk_progress.setRange(0, 100)
        self.vk_progress.setValue(0)
        self.vk_progress.setVisible(False)
        right_layout.addWidget(self.vk_progress)

        self.vk_tabs = create_styled_tab_widget()
        self.vk_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 页签 1：日志
        log_page, log_page_layout = create_styled_tab_page(self.vk_tabs, "日志")
        self.vk_log = create_styled_text_edit(read_only=True)
        log_page_layout.addWidget(self.vk_log)

        # 页签 2：显著基因
        sig_page, sig_page_layout = create_styled_tab_page(self.vk_tabs, "显著基因")
        self.vk_sig_table = create_styled_table()
        sig_page_layout.addWidget(self.vk_sig_table)

        # 页签 3：全部基因
        all_page, all_page_layout = create_styled_tab_page(self.vk_tabs, "全部基因")
        self.vk_all_table = create_styled_table()
        all_page_layout.addWidget(self.vk_all_table)

        # 页签 4：柱状图
        _, self.vk_img_bar = create_styled_image_tab(self.vk_tabs, "柱状图")

        # 页签 5：散点图
        _, self.vk_img_scatter = create_styled_image_tab(self.vk_tabs, "散点图")

        right_layout.addWidget(self.vk_tabs)

        main_layout.addWidget(right_panel, 1)

        layout.addLayout(main_layout, 1)

        self.update_styles()

        return self.virtual_knockout_page
