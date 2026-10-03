# -*- coding: utf-8 -*-
"""空转「基因集气泡图」子页面 bind —— 1:1 复刻单细胞
`scRNAseq_layer/sc_genelist_bubble_layer/ui_bind_sc_genelist_bubble.py`（380 行）。

## 与单细胞原型的三处**有意差异**（规格 v11 §2.4 / §2.5 / §2.8）
1. **空转独有：样本多选驱动「动态注释选项」**
   左侧样本表 `spatial_sample_list` 的选中变化 → `_recompute_from_samples()` →
   `analysis.set_context(dataset, samples=所选)` → `available_group_columns()` 填候选列 →
   `group_unique_values(col)` 填注释值 → `participating_samples(col)` 写日志。
   ⇒ **判据一行都不在本文件里** —— 全部由 `SpatialGenelistBubbleAnalysis` **继承**
   `SpatialDiffAnalysis` 得到（I6 真相源唯一）；本页只做
   「读控件 → 调分析层 → 重填控件 → 写日志」。
2. ⛔ **不照抄模板机制**（原型 `save_template` / `load_template` /
   `on_template_combo_changed` + `..._temp_combo` 守卫）：规格 §2.8 缺陷 1 判定为死代码
   （控件在 layout 里根本不存在，`save_template()` 直接 `.text()` 必 AttributeError）。
3. ★★ **「加载基因」按钮已删（v11.2 用户拍板）**：基因输入只有文本框；点「筛选并绘图」时
   由 `_ensure_genes_loaded_for_draw()` 自己解析 —— 见 `bind_gene_input()` 的说明。
4. **不保留**单细胞的 `collapsed` 死参数与 `current_fig` 死引用（规格 §2.8 缺陷 2/6）。

## 数据层共享（与差异页/表达页同一约定）
`getattr(self.parent, 'spatial_top_bind', None)` → `.analysis`（**绝不自己 load_data / 读 R**）。
本页 `self.analysis` 是**本页自己的** `SpatialGenelistBubbleAnalysis`（继承差异分析层 ⇒
取数链路与差异页逐位同源）；hub 的 analysis 只用来**只读**样本清单与成品 rds 路径。

## 四层纪律（I1）
bind **只连信号 + 编排**：业务在 analysis（`spatial_genelist_bubble_analysis.py`）、
显示在 func（`ui_func_spatial_genelist_bubble.py`）。本文件**不写盘**：中间产物归分析层，
导出走用户选的 `QFileDialog` 路径。

## ★ 信号选择（D 系列事故）
样本列表的选择信号**必须**用 `itemSelectionChanged`：同名语义的另一个受保护槽
`hasattr` 为真却**永不触发**、也没有 `.connect`
（协调者离屏实测，详见 `ui_bind_spatial_diff.py:236-266` 的长注释）。

## ⛔ 不做的事
- 不写 `save_template` / `load_template` / `on_template_combo_changed`（§2.8 缺陷 1）；
- 不自己实现一套「候选分组列 / 注释值」判据（I6：判据只允许一处实现，全部调分析层）；
- 控件守卫一律 `if widget is None:`（**不许** `if not widget:` —— 空 `QListWidget` /
  空 `QComboBox` 的 `bool()` 是 `False`，§2.8 缺陷 5 的事故）；
- 无静默 except：每个 `except` 都 `traceback.print_exc()` + 写日志留痕（I5）。
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
# ★ 「选已审查高分（≥4★）」的判据真相源 = 审查层（与审查页/表达页**同一套**，
#   本页绝不自己再判一份 —— I6）
from script.analyzer_layer.spatial_layer.spatial_review_layer import spatial_review_analysis as RA

#: 本页在 `page_intersect.page_configs` 里登记的 `name`（`go_to_parent_page` 的唯一入参）
PAGE_NAME = 'spatial_genelist_bubble_page'
#: hub 侧顶层 bind 的属性名（数据层唯一来源）
TOP_BIND_ATTR = 'spatial_top_bind'


def _warn(msg):
    """模块级留痕（与 `ui_bind_spatial_diff._warn` 同款形状：打印 + 不抛）"""
    try:
        print("[SpatialGenelistBubbleBind] %s" % msg)
    except Exception:
        traceback.print_exc()


class SpatialGenelistBubbleBind:
    """空转基因集气泡图功能绑定类 - 全权负责粘合内外"""

    #: 空选守卫文案（规格 §2.4：**绝不静默**、**绝不抛**、**绝不退化成全部样本**）
    NO_SAMPLE_MSG = "⚠ 请先在左侧选择样本（候选分组列与注释值按所选样本的并集生成）"

    def __init__(self, parent_window, ui_instance):
        self.parent = parent_window
        self.ui = ui_instance
        self.analysis = self._make_analysis()
        self.func = self._make_func()
        # 重算守卫：程序化重填控件期间为 True（防信号回环 + 防重复重算）
        self._recomputing = False
        # 宽高双向同步的重入守卫（防两个 spinbox 互刷）
        self._syncing_size = False
        # 已留痕一次的键集合（防刷屏：同一条降级说明只写一次，见 `_note_once`）
        self._noted_once = set()
        # "当前已知可选"的缓存（控件缺失/无数据集时仍能给日志一个确定的空值）
        self._group_cols = []
        self.init_bindings()

    # ==================================================================
    # 分析层 / 显示层（★ 延迟 + 容错构造：W3b 的文件缺失时本页**不崩**，只留痕）
    # ==================================================================
    def _make_analysis(self):
        """构造 `SpatialGenelistBubbleAnalysis`（规格 §2.5：**继承** `SpatialDiffAnalysis`）

        ## ★ 为什么用延迟 import 而不是模块顶层 import
          单细胞原型是顶层 import；本页是**并行施工**的新页（W3b 的
          `spatial_genelist_bubble_analysis.py` 与本文件同时产出），顶层 import 会让
          「分析层文件还没到位」直接炸掉**整个空转 hub 的页面初始化**。故：
          `try/except` + `traceback.print_exc()` 留痕 → 返回 None →
          真正要跑分析时再给一句可读提示（**绝不静默、绝不抛**）。
        """
        try:
            from script.analyzer_layer.spatial_layer.spatial_genelist_bubble_layer.\
                spatial_genelist_bubble_analysis import SpatialGenelistBubbleAnalysis
            return SpatialGenelistBubbleAnalysis()
        except Exception:
            traceback.print_exc()
            _warn("⚠ 无法构造 SpatialGenelistBubbleAnalysis（W3b 的分析层未就位？）"
                  "→ 本页的选项重算与绘图将不可用（已留痕，不抛）")
            return None

    def _make_func(self):
        """构造 `SpatialGenelistBubbleFunc`（显示层；缺失时**只留痕不抛**，返回 None）

        ★ func 只做显示（下拉/列表重填、图片上屏、日志、弹窗、保存对话框）；
          它缺失时本页的**业务**（分析层调用）不受影响，只是界面更新会让位给日志。
        """
        try:
            from script.analyzer_layer.spatial_layer.spatial_genelist_bubble_layer.\
                ui_func_spatial_genelist_bubble import SpatialGenelistBubbleFunc
            return SpatialGenelistBubbleFunc(ui_instance=self.ui, parent_widget=self.parent)
        except TypeError:
            # 兜底：若 func 采用单细胞原型的位置参数签名 `(ui, parent)`
            traceback.print_exc()
            try:
                from script.analyzer_layer.spatial_layer.spatial_genelist_bubble_layer.\
                    ui_func_spatial_genelist_bubble import SpatialGenelistBubbleFunc
                return SpatialGenelistBubbleFunc(self.ui, self.parent)
            except Exception:
                traceback.print_exc()
                _warn("⚠ 无法构造 SpatialGenelistBubbleFunc（W3b 的 ui_func_* 未就位？）"
                      "→ 界面更新将退化为日志（已留痕，不抛）")
                return None
        except Exception:
            traceback.print_exc()
            _warn("⚠ 无法构造 SpatialGenelistBubbleFunc（W3b 的 ui_func_* 未就位？）"
                  "→ 界面更新将退化为日志（已留痕，不抛）")
            return None

    def _require_analysis(self):
        """取分析层；没有就留痕 + 可读提示 + 返回 None（**绝不抛**）"""
        if self.analysis is None:
            self._log("⚠ 基因集气泡分析层不可用（SpatialGenelistBubbleAnalysis 未就绪，"
                      "见控制台 traceback）")
            self._alert('failure', "基因集气泡分析层不可用")
            return None
        return self.analysis

    def _call_func(self, name, *args, **kwargs):
        """调 func 上的方法；func/方法缺失或抛异常 → **留痕** + 返回 `(False, None)`

        ★ 为什么不静默跳过：本轮事故的根因就是「缺名字被 except 吞掉」
          （`py_compile` 看不出来、界面表现为"点了没反应"）。故一律写日志。
        """
        try:
            fn = getattr(self.func, name, None) if self.func is not None else None
            if not callable(fn):
                self._log("⚠ func 缺少 %s() → 该步跳过（需要 W3b 的 ui_func_* 提供）" % name)
                return False, None
            return True, fn(*args, **kwargs)
        except Exception:
            traceback.print_exc()
            self._log("⚠ 调 func.%s() 异常（见控制台 traceback）" % name)
            return False, None

    def _alert(self, kind, message):
        """弹窗提示（`func.alert_error` / `alert_failure` / `alert_success`）

        ★ **绝不静默吞掉**：func 缺失时退回日志控件（用户仍看得见这条消息）。
        """
        try:
            fn = getattr(self.func, 'alert_%s' % kind, None) if self.func is not None else None
            if callable(fn):
                try:
                    fn(str(message))
                    return
                except Exception:
                    traceback.print_exc()
            self._log("[%s] %s" % (kind, message))
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 绑定入口（★ 顺序与规格 §2.3 的左→中→右→导出一致）
    # ==================================================================
    def init_bindings(self):
        """初始化所有绑定（每个槽自带 try/except，防 PyQt5 对未捕获异常 qFatal）"""
        self.bind_navigation()
        self.bind_sample_list()
        self.bind_music_controls()
        self.bind_gene_input()
        self.bind_filter_enable()
        self.bind_draw()
        self.bind_export()

    def bind_navigation(self):
        """`btn_back_bubble` → 回 hub（空转子页的「返回」一律回 hub，I3）

        ★ 走 `go_to_parent_page(PAGE_NAME)`：与表达页/差异页同款 —— 父页关系只在
          `page_intersect.page_configs` 里登记一处，不在这里硬编码 hub 路由名。
        """
        try:
            btn = getattr(self.ui, 'btn_back_bubble', None)
            if btn is None:
                self._log("⚠ 布局缺少控件 btn_back_bubble → 返回主页未绑定（需要 W1 提供）")
                return
            if hasattr(btn, 'clicked'):
                btn.clicked.connect(self._on_back_clicked)
            else:
                self._log("⚠ btn_back_bubble 没有 clicked 信号 → 返回主页未绑定")
        except Exception:
            traceback.print_exc()

    def _on_back_clicked(self):
        """回 hub"""
        try:
            page_intersect.go_to_parent_page(PAGE_NAME)
        except Exception:
            traceback.print_exc()

    def bind_music_controls(self):
        """绑定音乐控制（逐字照抄单细胞 `:59-62`）"""
        try:
            if getattr(self.ui, 'music_controller', None) is not None:
                fix_music_controller_bindings(self, self.ui.music_controller)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # ★★ 样本选择 → 重算「候选分组列 / 注释值」（规格 §2.4）
    # ==================================================================
    def bind_sample_list(self):
        """`spatial_sample_list.itemSelectionChanged` → 重算分组与注释值（规格 §2.4.1）

        ## ★★ 信号选择：`itemSelectionChanged`（D 系列修复）
          `QListWidget` 上 `hasattr(lst, 'selectionChanged')` 为 **True**，但那是
          `QAbstractItemView` 的**受保护槽**透出来的属性，**连接后从不发火**
          ⇒ 之前若写成它优先，结果是**样本选择永远不会触发选项重算**（控件建成 ≠
          数据路径通）。`ui_bind_spatial_expression.py:360` /
          `ui_bind_spatial_initial.py:497` / `ui_bind_spatial_diff.py:256` 都先认
          `itemSelectionChanged` ⇒ 本页只认它。
        ★ 顺带接两个**可选**的快捷选择按钮（W1 提供才接；缺失不刷屏，与差异页同款）。
        """
        try:
            lst = self._sample_list_widget()
            if lst is None:
                self._log("⚠ 布局缺少样本列表控件（spatial_sample_list/sample_list）"
                          "→ 样本选择未绑定（需要 W1 提供）")
            elif hasattr(lst, 'itemSelectionChanged'):
                lst.itemSelectionChanged.connect(self._on_sample_selection_changed)
            else:
                self._log("⚠ 样本列表没有 itemSelectionChanged 信号 → 样本选择未绑定")
            for attr, handler in (('btn_sample_all', self._on_select_all_clicked),
                                  ('btn_sample_high_score', self._on_select_high_score_clicked),
                                  ('btn_sample_invert', self._on_select_invert_clicked)):
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(handler)
        except Exception:
            traceback.print_exc()

    def _sample_list_widget(self):
        """样本列表控件（**唯一冻结名** = `sample_list`，与差异分析页逐字一致）

        ★ v11 协调者收敛：本页样本列是**整块照抄差异页**的（`sample_panel` / `sample_list` /
          `sample_count_label` / `btn_sample_*`），所以属性名就用差异页那一套，**不另起**
          `spatial_sample_list`。原先那句"非冻结名"的留痕已删除 —— 它会把**正确**的名字
          说成错的。
        ★ 仍然两个名字都探并**只留痕一次**：万一将来布局改名，这里能立刻发现而不是静默空白。
        """
        try:
            widget = getattr(self.ui, 'sample_list', None)
            if widget is not None:
                return widget
            widget = getattr(self.ui, 'spatial_sample_list', None)
            if widget is not None:
                self._note_once('sample_list_alias',
                                "⚠ 布局用的是 `spatial_sample_list`（差异页口径的冻结名是 "
                                "`sample_list`）→ 已按兼容名绑定")
            return widget
        except Exception:
            traceback.print_exc()
            return None

    def _sample_count_label(self):
        """样本计数标签（唯一冻结名 = `sample_count_label`；兼容 `spatial_sample_count_label`）"""
        try:
            label = getattr(self.ui, 'sample_count_label', None)
            if label is not None:
                return label
            return getattr(self.ui, 'spatial_sample_count_label', None)
        except Exception:
            traceback.print_exc()
            return None

    def _on_sample_selection_changed(self):
        """样本选择变化槽（槽内**绝不抛**：PyQt5 对未捕获异常会 qFatal）"""
        try:
            self._recompute_from_samples("样本选择变化")
        except Exception:
            traceback.print_exc()

    def _on_select_all_clicked(self):
        """全选（只改控件 → 触发一次重算；**不写盘**）"""
        try:
            self._set_all_selected(True)
            self._log("样本快捷选择：全选")
            self._recompute_from_samples("全选样本")
        except Exception:
            traceback.print_exc()

    def _on_select_invert_clicked(self):
        """反选（只改控件 → 触发一次重算；**不写盘**）"""
        try:
            self._set_all_selected(None)
            self._log("样本快捷选择：反选")
            self._recompute_from_samples("反选样本")
        except Exception:
            traceback.print_exc()

    def _set_all_selected(self, value):
        """批量设置选中态（`value=None` = 逐个取反）；**不触发信号**，重算由调用方显式做"""
        try:
            lst = self._sample_list_widget()
            if lst is None or not hasattr(lst, 'count'):
                return
            lst.blockSignals(True)
            try:
                for i in range(lst.count()):
                    item = lst.item(i)
                    if item is None:
                        continue
                    item.setSelected((not item.isSelected()) if value is None else bool(value))
            finally:
                lst.blockSignals(False)
            self._refresh_count()
        except Exception:
            traceback.print_exc()

    def _current_selected_ids(self):
        """**静默**读当前选中样本 id（以 UI 为准；取不到返回空列表，不写"请选择样本"）

        ★ func 优先（与差异页 `get_selected_sample_ids` 同口径）；func 未提供该方法时
          **bind 直接读控件**（`Qt.UserRole` = 真实样本 id）—— 样本是注释选项的唯一来源，
          这条路绝不能因为"func 少一个方法"而断掉。
        """
        ids = []
        try:
            fn = getattr(self.func, 'get_selected_sample_ids', None) if self.func else None
            if callable(fn):
                raw = fn()
                ids = [str(x) for x in (raw or []) if x]
        except Exception:
            traceback.print_exc()
            ids = []
        if ids:
            return ids
        return self._selected_ids_from_widget()

    def _selected_ids_from_widget(self):
        """从样本列表控件读选中 id（只读控件；控件缺失 → 空列表）"""
        try:
            lst = self._sample_list_widget()
            if lst is None or not hasattr(lst, 'selectedItems'):
                return []
            out = []
            for item in lst.selectedItems():
                sid = str(item.data(Qt.UserRole) or "")
                if sid:
                    out.append(sid)
            return out
        except Exception:
            traceback.print_exc()
            return []

    def _read_selected_sample_ids(self):
        """读当前选中的样本 id（★ 以 UI 为准；空选时**留痕**，与差异页同款）

        ⛔ 数据来源根本没加载时**绝不弹窗**（那是正常空状态）：只写日志 + 返回空列表，
          否则每次进页都会弹一次"请先选择样本"。
        """
        ids = self._current_selected_ids()
        if not ids:
            dataset, _out, error = self._dataset_context()
            if error:
                self._log("⚠ %s" % error)
            else:
                self._log(self.NO_SAMPLE_MSG)
        return ids

    def _refresh_count(self):
        """刷新「已选 N / M」计数（func 优先；func 未提供 → bind 直接写计数标签）"""
        try:
            fn = getattr(self.func, 'refresh_selected_count', None) if self.func else None
            if callable(fn):
                try:
                    fn()
                    return
                except Exception:
                    traceback.print_exc()
            self._fallback_note('refresh_selected_count')
            label = self._sample_count_label()
            if label is None or not hasattr(label, 'setText'):
                return
            lst = self._sample_list_widget()
            total = lst.count() if (lst is not None and hasattr(lst, 'count')) else 0
            selected = len(lst.selectedItems()) if (lst is not None
                                                    and hasattr(lst, 'selectedItems')) else 0
            label.setText("已选 %d / %d" % (selected, total))
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # ★ 样本列表的**写入口**（func 优先 + bind 内置最小实现兜底）
    #   规格 §2.4：样本列归本页（W1 只建控件）。差异页把这三件事放在
    #   `ui_func_spatial_diff.py`（`set_sample_items` / `get_selected_sample_ids` /
    #   `refresh_selected_count`），而本页的 func 归 W3b（可能没有这三个方法）
    #   ⇒ **func 优先、缺失则 bind 兜底并留痕**。若不兜底，整页会因为"样本选不了"
    #   而彻底不可用（样本是候选分组列/注释值的**唯一来源**）。
    # ==================================================================
    def _note_once(self, key, msg):
        """同一条降级/兼容说明**只留痕一次**（防刷屏；绝不静默）"""
        try:
            if key in self._noted_once:
                return
            self._noted_once.add(key)
            self._log(msg)
        except Exception:
            traceback.print_exc()

    def _fallback_note(self, name):
        """记录一次"func 缺方法 → bind 内置最小实现"（**只留痕一次**，不刷屏）"""
        self._note_once('func:' + str(name),
                        "⚠ func 无 %s() → 样本列表改用 bind 内置最小实现"
                        "（W3b 交付该方法后本行消失）" % name)

    def _set_sample_items_direct(self, records, keep):
        """bind 内置最小实现：填样本列表（语义与差异页 func 逐条一致）

        · 文本 = label（label 已含样本号时不重复）；· `Qt.UserRole` = **真实样本 id**；
        · `keep` 里的样本置为已选（保住用户上次的选择，D8 型事故的防线）。
        """
        try:
            widget = self._sample_list_widget()
            if widget is None or not hasattr(widget, 'clear'):
                self._log("⚠ 样本列表控件缺失 → 样本列无法填充（需要 W1 提供）")
                return False
            chosen = {str(x) for x in (keep or [])}
            widget.blockSignals(True)
            try:
                widget.clear()
                for entry in (records or []):
                    if not isinstance(entry, dict):
                        continue
                    sid = str(entry.get('id', '') or '').strip()
                    if not sid:
                        continue
                    label = str(entry.get('label', '') or '')
                    if label and sid in label:
                        text = label
                    elif label:
                        text = ("%s %s" % (sid, label)).strip()
                    else:
                        text = sid
                    item = QListWidgetItem(text)
                    item.setData(Qt.UserRole, sid)
                    widget.addItem(item)
                    if sid in chosen:
                        item.setSelected(True)
            finally:
                widget.blockSignals(False)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def _on_select_high_score_clicked(self):
        """「选已审查高分（≥4★）」：判据走审查层 `RA`（本页不自己判一套）"""
        try:
            dataset, _out, error = self._dataset_context()
            if not dataset:
                self._log("⚠ %s → 无法读取审查评分" % (error or "尚未确定数据集"))
                return
            scores = RA.load_review_scores(dataset)
            high = {str(s) for s in (RA.reviewed_high_score_samples(scores, min_stars=4) or [])}
            lst = self._sample_list_widget()
            if lst is None or not hasattr(lst, 'count'):
                self._log("⚠ 样本列表控件缺失 → 「选已审查高分」不可用")
                return
            lst.blockSignals(True)
            try:
                for i in range(lst.count()):
                    item = lst.item(i)
                    if item is None:
                        continue
                    sid = str(item.data(Qt.UserRole) or "")
                    item.setSelected(sid in high)
            finally:
                lst.blockSignals(False)
            self._refresh_count()
            if high:
                self._log("样本快捷选择：选已审查高分（≥4★）= %d 个" % len(high))
            else:
                self._log("样本快捷选择：没有 ≥4★ 的样本（可先去审查模式打分）"
                          "→ 已清空选择")
            self._recompute_from_samples("快捷选择：已审查高分")
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 数据来源（契约：从 `self.parent.spatial_top_bind.analysis` 只读）
    # ==================================================================
    def _top_bind(self):
        """取空转顶层 bind（**不是** scRNAseq_top_bind）"""
        try:
            return getattr(self.parent, TOP_BIND_ATTR, None)
        except Exception:
            traceback.print_exc()
            return None

    def _dataset_context(self):
        """读数据来源（**只读**，不写盘）→ `(dataset, out_dir, error)`

        ★ 数据源 = `self.parent.spatial_top_bind.analysis` 的 `dataset_name` /
          `dataset_output_dir`（与审查页/初始页/表达页/差异页同一真相源）。
        ★ 取不到 ⇒ 返回 `error` 文案，**由调用方写日志 + 给可读提示**（绝不抛）；
          也**绝不**在这里 `os.makedirs` —— 本页不写盘。
        """
        try:
            top = self._top_bind()
            if top is None:
                return None, None, "尚未加载空转数据集（spatial_top_bind 不存在）"
            an = getattr(top, 'analysis', None)
            if an is None:
                return None, None, "空转顶层 bind 没有 analysis（数据层未就绪）"
            dataset = getattr(an, 'dataset_name', None)
            out_dir = getattr(an, 'dataset_output_dir', None)
            if not dataset:
                return None, out_dir, ("尚未加载空转数据集"
                                       "（请先在主页『扫描数据路径』并『加载数据集』）")
            if not out_dir:
                return dataset, None, "数据集 %s 已加载，但 dataset_output_dir 为空" % dataset
            return dataset, out_dir, None
        except Exception:
            traceback.print_exc()
            return None, None, "读取数据来源时异常（见控制台 traceback）"

    def _rds_path(self):
        """成品 `.rds` 真实路径（**只读** hub 已校验过的 `artifact_info['path']`）"""
        try:
            top = self._top_bind()
            top_an = getattr(top, 'analysis', None)
            art = getattr(top_an, 'artifact_info', None) or {}
            return str(art.get('path') or '')
        except Exception:
            traceback.print_exc()
            return ""

    def _sample_records(self):
        """返回样本清单 `[{id, label}, ...]`（**只读** hub 的样本表，不写盘）"""
        records = []
        try:
            top = self._top_bind()
            if top is None:
                return records
            an = getattr(top, 'analysis', None)
            if an is None:
                return records
            rows = []
            getter = getattr(an, 'get_sample_list', None)
            if callable(getter):
                try:
                    rows = list(getter() or [])
                except Exception:
                    traceback.print_exc()
                    rows = []
            if not rows:
                rows = list(getattr(an, 'samples', None) or [])
            for row in rows:
                if isinstance(row, dict):
                    sid = str(row.get('id', '') or '').strip()
                    if not sid:
                        continue
                    records.append({'id': sid, 'label': str(row.get('label', '') or '')})
                else:
                    sid = str(row or '').strip()
                    if sid:
                        records.append({'id': sid, 'label': ''})
        except Exception:
            traceback.print_exc()
        return records

    # ==================================================================
    # ★ 进页钩子（规格 §2.1 / I4：**必须实现**）
    # ==================================================================
    def on_page_entered(self):
        """每次跳转到本页时由 `page_intersect.go_to_page_with_bind` 调用（可选钩子）

        ## ★ 为什么必须有它（规格 §2.1 / I4）
          空转子页**不用** `data_source_page`/`sync_method`，改为在这里**自取上下文**；
          没有钩子的话，数据集在首次进页**之后**才加载时，样本列表与下拉永远不会刷新。
          本页做四件事：
            ① 取数据集上下文（hub 的 bind）→ ② 重填样本列表（**保住已选**）→
            ③ 刷新计数 → ④ `set_context` + 重算候选分组列 / 注释值。
        ⛔ **不自己 load_data()、不自己读 R**（数据层只有 hub 一处）。
        ★ 无数据集时**只留痕、不抛**、且**不弹窗**（正常空状态）。
        """
        try:
            self._log("【基因集气泡图】进入页面")
            dataset, out_dir, error = self._dataset_context()
            if dataset:
                self._log("数据集: %s" % dataset)
            # ① 样本列表（保住已选）—— **无论有没有数据集都做**（清单可能已可用）
            self._fill_sample_list()
            if error:
                self._log("⚠ %s" % error)
                # ★ **无数据集** ⇒ 到此为止（不去 set_context / 重算）；
                #   ⚠ "有数据集、只是 dataset_output_dir 缺失"**不算无数据集** —— 照样往下重算。
                if not dataset:
                    return
            # ②③④ 上下文 + 候选分组列 + 注释值
            self._recompute_from_samples("进入页面")
        except Exception:
            traceback.print_exc()

    def _fill_sample_list(self):
        """重填样本列表；**尽量保住用户已选样本**（`set_sample_items(..., 已选)`）

        ★ 为什么必须保住已选：`on_page_entered()` 每次进页都调本方法；
          若默认清空选择，"用户选好样本 → 回 hub → 再进来"就丢选择（D8 型事故），
          而样本是**注释选项的唯一来源** ⇒ 回来会看到一片空白。
        ★ func 优先（差异页同款签名 `set_sample_items(records, selected_ids)`）；
          func 未提供该方法时走 bind 内置最小实现（见 `_set_sample_items_direct`）。
        """
        try:
            records = self._sample_records()
            if not records:
                self._log("⚠ 样本清单为空（数据集未加载？）→ 样本列表保持为空")
                return
            keep = self._current_selected_ids()
            ok = False
            fn = getattr(self.func, 'set_sample_items', None) if self.func else None
            if callable(fn):
                try:
                    fn(records, keep)
                    ok = True
                except TypeError:
                    # 兜底：func 若是老签名（只收 1 个参数）→ 退回不带选择的调用（留痕）
                    traceback.print_exc()
                    try:
                        fn(records)
                        ok = True
                    except Exception:
                        traceback.print_exc()
                except Exception:
                    traceback.print_exc()
            if not ok:
                self._fallback_note('set_sample_items')
                ok = self._set_sample_items_direct(records, keep)
            if not ok:
                self._log("⚠ 样本列表未能重填 → 本页注释选项可能为空（需要 W1 的控件）")
                return
            self._refresh_count()
            self._log("样本清单: %d 条（保持已选 %d 条%s）"
                      % (len(records), len(keep),
                         "；未选任何样本时不会退化成全部" if not keep else ""))
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # ★★ 重算整条选项链（规格 §2.4）
    # ==================================================================
    def _recompute_from_samples(self, reason=""):
        """按当前 UI 上的样本选择，重算**整条选项链**

        链路：样本 → `set_context(dataset, samples=所选)` → 候选分组列 →
              各注释值列表 + 两个筛选列 / 筛选值列表。
        ⛔ 只改控件内容：**不写盘、不落盘、不调分析层跑统计**。
        """
        logs = []
        try:
            if self._recomputing:
                # 程序化重填控件导致的回环 → 直接忽略（不是错误）
                return
            self._recomputing = True
            try:
                # ① 读当前选中（以 UI 为准；空选时本方法内部会写日志）
                samples = self._read_selected_sample_ids()
                # ② 数据来源（只读）
                dataset, out_dir, error = self._dataset_context()
                if error:
                    logs.append("⚠ %s" % error)
                if not samples:
                    logs.append(self.NO_SAMPLE_MSG)
                    self._clear_option_controls(logs)
                    return
                an = self.analysis
                if an is None:
                    logs.append("⚠ 基因集气泡分析层不可用"
                                "（SpatialGenelistBubbleAnalysis 未就绪）→ 选项未重算")
                    return
                if not dataset:
                    logs.append("⚠ 尚未确定数据集 → 选项未重算")
                    return
                # ③ 上下文（**只记上下文**，不跑 R：装配在分析层 prepare() 里）
                try:
                    an.set_context(dataset, samples)
                except Exception:
                    traceback.print_exc()
                    logs.append("⚠ 同步分析上下文失败（见控制台 traceback）")
                # ③b ★ rds 真实路径注入（存在性安全）
                #   真相源 = hub 的 `analysis.artifact_info['path']`（主页已校验过的成品 rds）；
                #   ⛔ 只读注入：拿不到/无该方法一律**只留痕不抛**，沿用分析层默认推断。
                rds = self._rds_path()
                if rds:
                    setter = getattr(an, 'set_rds_path', None)
                    if callable(setter):
                        try:
                            setter(rds)
                            logs.append("rds 真实路径（取自 hub artifact_info）: %s" % rds)
                        except Exception:
                            traceback.print_exc()
                            logs.append("⚠ 注入 rds 路径失败 → 沿用默认推断（见控制台 traceback）")
                    else:
                        logs.append("⚠ 分析层无 set_rds_path() → 沿用默认扫描目录推断")
                else:
                    logs.append("⚠ hub 的 artifact_info 无 path → 沿用默认扫描目录推断 rds")
                # ④ 候选分组列 → 主分组下拉框（+ 两个筛选列下拉框）
                self._recompute_group_options(an, logs)
                # ⑤ 各注释值列表（默认全选，与单细胞 `fill_list_widget` 默认一致）
                self._recompute_group_lists(an, logs)
                # ⑥ 两个筛选列 / 筛选值列表
                self._recompute_filter_values(logs)
                if out_dir:
                    logs.append("输出根目录（**本页不写盘**，中间产物归分析层）: %s" % out_dir)
                if reason:
                    logs.append("选项重算原因: %s" % reason)
            finally:
                self._recomputing = False
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重算候选分组列/注释值时异常（见控制台 traceback）")
        finally:
            self._log_lines(logs)

    def _clear_option_controls(self, logs):
        """空选/无数据时的清空路径（规格 §2.4：清空 + 「请先选择样本」，不退化成全部）"""
        try:
            for name in ('spatial_genelist_bubble_main_list',
                         'spatial_genelist_bubble_filter1_list',
                         'spatial_genelist_bubble_filter2_list'):
                w = getattr(self.ui, name, None)
                if w is None:
                    continue
                try:
                    self.func.fill_list_widget(w, [], select_all=False)
                except Exception:
                    traceback.print_exc()
            self._safe_set_combo_items('spatial_genelist_bubble_main_combo', [])
            self._safe_set_combo_items('spatial_genelist_bubble_filter1_combo', [''])
            self._safe_set_combo_items('spatial_genelist_bubble_filter2_combo', [''])
            self._group_cols = []
            logs.append("分组/注释值/筛选控件已清空（未选择任何样本）")
            logs.append("⛔ 说明：本次只清空控件内容，**未**写盘、未调用分析层跑统计")
        except Exception:
            traceback.print_exc()

    def _recompute_group_options(self, an, logs):
        """重算候选分组列（规格 §2.4.2：`available_group_columns()`，**不加** nunique 过滤）

        · 主分组下拉 `spatial_genelist_bubble_main_combo` ← 候选列（保住当前选中，
          不在列表里则落回第一项）；
        · 两个筛选列下拉 ← `[''] + 候选列`（首项空串 = 不筛，照单细胞/差异页口径）。
        """
        cols = []
        try:
            getter = getattr(an, 'available_group_columns', None)
            if not callable(getter):
                logs.append("⚠ 分析层没有 available_group_columns() → 分组下拉未重算")
                self._group_cols = []
                return
            cols = [str(c) for c in (getter() or [])]
            self._group_cols = list(cols)
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 读取可用分组列失败（见控制台 traceback）")
            self._group_cols = []
            return
        self._safe_set_combo_items('spatial_genelist_bubble_main_combo', cols)
        for name in ('spatial_genelist_bubble_filter1_combo',
                     'spatial_genelist_bubble_filter2_combo'):
            self._safe_set_combo_items(name, [''] + cols)
        logs.append("可用注释分组（按所选样本的并集）: %s"
                    % (", ".join(cols) if cols else "（无）"))

    def _recompute_group_lists(self, an, logs):
        """重算 `spatial_genelist_bubble_main_list`（值列表**默认全选**，与单细胞一致）

        ★ 值列表的真相源 = `analysis.group_unique_values(col)`（§2.4.3 = `sorted(⋃ anno_values)`）。
        ★ 同时把**参与/被排除的样本**写进日志（I5，不许静默）。
        """
        col = self._combo_text('spatial_genelist_bubble_main_combo')
        values = self._unique_values(an, col, logs)
        w = getattr(self.ui, 'spatial_genelist_bubble_main_list', None)
        if w is not None:
            try:
                self.func.fill_list_widget(w, values, select_all=True)
            except Exception:
                traceback.print_exc()
                logs.append("⚠ 填充主分组注释值列表失败（见控制台 traceback）")
        if col:
            logs.append("分组『%s』的注释值（并集去重排序）: %s"
                        % (col, ", ".join(values) if values else "（无）"))
            if not values:
                logs.append("⚠ 分组『%s』在所选样本里没有任何非空值 → 无法绘图" % col)
        self._log_participating_samples(an, col, logs)

    def _recompute_filter_values(self, logs):
        """两个筛选值列表按各自当前列重填（值列表**默认全选**，照单细胞）"""
        try:
            for col_name, list_name in (
                    ('spatial_genelist_bubble_filter1_combo',
                     'spatial_genelist_bubble_filter1_list'),
                    ('spatial_genelist_bubble_filter2_combo',
                     'spatial_genelist_bubble_filter2_list')):
                col = self._combo_text(col_name)
                values = self._unique_values(self.analysis, col, logs)
                w = getattr(self.ui, list_name, None)
                if w is None:
                    continue
                try:
                    self.func.fill_list_widget(w, values, select_all=True)
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重填筛选值列表失败（见控制台 traceback）")

    def _unique_values(self, an, col, logs):
        """`analysis.group_unique_values(col)`（§2.4.3：值列表真相源**只此一处**）"""
        if not col or an is None:
            return []
        try:
            getter = getattr(an, 'group_unique_values', None)
            if not callable(getter):
                logs.append("⚠ 分析层没有 group_unique_values() → 注释值列表未重算")
                return []
            return [str(v) for v in (getter(col) or [])]
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 读取注释值列表失败（见控制台 traceback）")
            return []

    def _log_participating_samples(self, an, col, logs):
        """把**参与绘图的样本**与**被排除的样本**写进日志（I5 / §2.4.4，不许静默）"""
        try:
            if not col:
                return
            getter = getattr(an, 'participating_samples', None)
            if not callable(getter):
                logs.append("⚠ 分析层没有 participating_samples() → 参与样本未能核实")
                return
            part = [str(s) for s in (getter(col) or [])]
            selected = [str(x) for x in (self._current_selected_ids() or [])]
            excluded = [s for s in selected if s not in set(part)]
            logs.append("参与绘图的样本（%d/%d）: %s"
                        % (len(part), len(selected), ", ".join(part) if part else "（无）"))
            if excluded:
                logs.append("被排除的样本（%d）: %s" % (len(excluded), ", ".join(excluded)))
                if col == 'group_graphed':
                    logs.append("（`group_graphed` 只在**有绘图注释**的样本里取数，"
                                "其余样本无 graph 注释 → 已排除）")
                else:
                    logs.append("（这些样本在『%s』列上没有非空值 → 已排除）" % col)
            else:
                logs.append("被排除的样本: 无（所选样本全部参与）")
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 基因输入 / 分组下拉 / 筛选开关（照单细胞 `bind_bubble_functions` 顺序）
    # ==================================================================
    def bind_gene_input(self):
        """主分组下拉变化 → 重填对应值列表

        ★★ v11.2（2026-09-25 用户拍板）：**「加载基因」按钮已删**
          （用户原话：「把加载基因这个按钮控件去掉，我们只保留绘图按钮即可」）。
          ⇒ 这里**不再**给 `btn_load_gene_set` 接线；基因由**绘图**自己解析
          （`_ensure_genes_loaded_for_draw()` → `load_gene_set_data()`）。
          ⛔ 别在这里 `getattr(self.ui, 'btn_load_gene_set', None)` 再兜一次：
            布局已经不建它了，兜底只会每次进页面刷一条无意义的"缺少控件"日志。
        """
        try:
            combo = getattr(self.ui, 'spatial_genelist_bubble_main_combo', None)
            if combo is None:
                self._log("⚠ 布局缺少控件 spatial_genelist_bubble_main_combo → 分组选项未绑定")
            else:
                sig = getattr(combo, 'currentIndexChanged', None)
                if sig is not None and hasattr(sig, 'connect'):
                    sig.connect(self.on_main_combo_changed)
                else:
                    self._log("⚠ 主分组下拉没有 currentIndexChanged → 切分组不会重填注释值")
        except Exception:
            traceback.print_exc()

    def bind_filter_enable(self):
        """两个筛选开关 + 两个筛选列下拉（照单细胞 `on_filter1/2_enable_changed`）"""
        try:
            for box_name, combo_name, list_name in (
                    ('spatial_genelist_bubble_filter1_enable',
                     'spatial_genelist_bubble_filter1_combo',
                     'spatial_genelist_bubble_filter1_list'),
                    ('spatial_genelist_bubble_filter2_enable',
                     'spatial_genelist_bubble_filter2_combo',
                     'spatial_genelist_bubble_filter2_list')):
                box = getattr(self.ui, box_name, None)
                if box is None:
                    self._log("⚠ 布局缺少控件 %s → 该筛选开关未绑定" % box_name)
                else:
                    sig = getattr(box, 'stateChanged', None)
                    if sig is not None and hasattr(sig, 'connect'):
                        sig.connect(lambda _state, c=combo_name, l=list_name:
                                    self._on_filter_enable_changed(c, l, _state))
                    else:
                        self._log("⚠ %s 没有 stateChanged → 该筛选开关未绑定" % box_name)
                combo = getattr(self.ui, combo_name, None)
                if combo is None:
                    self._log("⚠ 布局缺少控件 %s → 该筛选列未绑定" % combo_name)
                    continue
                sig = getattr(combo, 'currentIndexChanged', None)
                if sig is not None and hasattr(sig, 'connect'):
                    sig.connect(lambda _idx, l=list_name: self.on_filter_combo_changed(l))
                else:
                    self._log("⚠ %s 没有 currentIndexChanged → 该筛选值列表不会重填" % combo_name)
        except Exception:
            traceback.print_exc()

    def bind_draw(self):
        """`btn_draw_bubble` → 绘图（走 `bind_button_with_sound`，照单细胞用法）；
        另外接 `fig_width/height` ↔ `export_width/height` 双向同步（规格 §2.3）"""
        try:
            log_widget = self._log_widget()
            btn = getattr(self.ui, 'btn_draw_bubble', None)
            if btn is None:
                self._log("⚠ 布局缺少控件 btn_draw_bubble → 绘图入口未绑定（需要 W1 提供）")
            elif hasattr(btn, 'clicked'):
                bind_button_with_sound(btn, self.draw_gene_set_bubble_plot, log_widget,
                                       "绘图完成", "绘图失败")
            else:
                self._log("⚠ btn_draw_bubble 没有 clicked 信号 → 绘图入口未绑定")
            self._bind_size_sync()
        except Exception:
            traceback.print_exc()

    def _bind_size_sync(self):
        """`fig_width/height` ↔ `export_width/height` **双向同步**（规格 §2.3 冻结）

        ★ 两种控件形态都兼容：单细胞那种带 `line_edit.editingFinished` 的自定义
          spinbox，以及普通 `QSpinBox.valueChanged`（W1 的布局用哪种都能接上）。
        ★ 控件缺失只**跳过**（不刷屏）：这是可选联动，不是功能入口。
        """
        try:
            pairs = (('spatial_genelist_bubble_fig_width',
                      'spatial_genelist_bubble_export_width'),
                     ('spatial_genelist_bubble_fig_height',
                      'spatial_genelist_bubble_export_height'))
            for src_name, dst_name in pairs:
                src = getattr(self.ui, src_name, None)
                dst = getattr(self.ui, dst_name, None)
                if src is None or dst is None:
                    continue
                for a, b in ((src, dst), (dst, src)):
                    sig = getattr(getattr(a, 'line_edit', None), 'editingFinished', None)
                    if sig is None:
                        sig = getattr(a, 'valueChanged', None)
                    if sig is not None and hasattr(sig, 'connect'):
                        sig.connect(lambda _v=None, s=a, d=b: self._sync_size(s, d))
        except Exception:
            traceback.print_exc()

    def _sync_size(self, src, dst):
        """把一个 spinbox 的值同步到另一个（带重入守卫，防互刷）"""
        try:
            if self._syncing_size:
                return
            self._syncing_size = True
            try:
                value = src.value()
                if dst.value() != value:
                    dst.setValue(value)
            finally:
                self._syncing_size = False
        except Exception:
            traceback.print_exc()

    def bind_export(self):
        """5 个导出按钮（png/pdf/svg/eps/csv）→ 照抄单细胞 bind 的写法"""
        try:
            log_widget = self._log_widget()
            pairs = (('btn_export_png', self.export_png, "PNG导出完成", "PNG导出失败"),
                     ('btn_export_pdf', lambda: self.export_other('pdf'),
                      "PDF导出完成", "PDF导出失败"),
                     ('btn_export_svg', lambda: self.export_other('svg'),
                      "SVG导出完成", "SVG导出失败"),
                     ('btn_export_eps', lambda: self.export_other('eps'),
                      "EPS导出完成", "EPS导出失败"),
                     ('btn_export_csv', self.export_csv, "CSV导出完成", "CSV导出失败"))
            for attr, handler, ok_msg, fail_msg in pairs:
                btn = getattr(self.ui, attr, None)
                if btn is None:
                    self._log("⚠ 布局缺少控件 %s → 该导出未绑定（需要 W1 提供）" % attr)
                    continue
                if not hasattr(btn, 'clicked'):
                    self._log("⚠ %s 没有 clicked 信号 → 该导出未绑定" % attr)
                    continue
                bind_button_with_sound(btn, handler, log_widget, ok_msg, fail_msg)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 槽：分组下拉 / 筛选开关（每个槽**绝不抛**）
    # ==================================================================
    def on_main_combo_changed(self, *args):
        """主分组下拉变化 → 只重填该分组的注释值列表（**不自动改样本选择**）"""
        logs = []
        try:
            if self._recomputing:
                return
            self._recomputing = True
            try:
                col = self._combo_text('spatial_genelist_bubble_main_combo')
                if not col:
                    logs.append(self.NO_SAMPLE_MSG)
                self._recompute_group_lists(self.analysis, logs)
            finally:
                self._recomputing = False
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重算注释值列表时异常（见控制台 traceback）")
        finally:
            self._log_lines(logs)

    def on_filter_combo_changed(self, list_name):
        """筛选列下拉变化 → 只重填对应筛选值列表（照单细胞 `on_filter1/2_combo_changed`）"""
        logs = []
        try:
            if self._recomputing:
                return
            self._recomputing = True
            try:
                combo_name = str(list_name).replace('_list', '_combo')
                col = self._combo_text(combo_name)
                values = self._unique_values(self.analysis, col, logs)
                w = getattr(self.ui, list_name, None)
                if w is None:
                    logs.append("⚠ 布局缺少控件 %s → 该筛选值列表未重填" % list_name)
                    return
                self.func.fill_list_widget(w, values, select_all=True)
                if col:
                    logs.append("筛选列『%s』的取值（并集去重排序）: %s"
                                % (col, ", ".join(values) if values else "（无）"))
            finally:
                self._recomputing = False
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重填筛选值列表时异常（见控制台 traceback）")
        finally:
            self._log_lines(logs)

    def _on_filter_enable_changed(self, combo_name, list_name, state):
        """启用/禁用某个筛选的 combo + list（复刻单细胞 `on_filter1_enable_changed`）"""
        try:
            enabled = (state == Qt.Checked) if state is not None else False
            for name in (combo_name, list_name):
                w = getattr(self.ui, name, None)
                if w is not None and hasattr(w, 'setEnabled'):
                    w.setEnabled(enabled)
                else:
                    self._log("⚠ 布局缺少控件 %s → 该筛选的启用态无法切换" % name)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 加载基因（单细胞 `load_gene_set_data` 的 1:1 骨架 + 空转的并集重算）
    # ==================================================================
    def load_gene_set_data(self):
        """加载基因：`analysis.load_gene_set(gene_text)` → 重算候选分组列/注释值 → 日志

        ★ 空选守卫：没有选中样本 ⇒ 分析层拿不到注释并集，先给出可读提示（不崩）。
        ★ 候选分组列**不取** `load_gene_set` 的 `valid_groups` 直接塞控件 —— 真相源是
          `available_group_columns()`（按所选样本的并集），统一由 `_recompute_from_samples()`
          走一遍，避免"两处口径"（I6）。
        """
        try:
            gene_text = self._text_of('spatial_genelist_bubble_text_input',
                                      'spatial_genelist_text_input')
            if not self._current_selected_ids():
                self._log(self.NO_SAMPLE_MSG)
                self._alert('error', "请先选择样本")
                return
            an = self._require_analysis()
            if an is None:
                return
            loader = getattr(an, 'load_gene_set', None)
            if not callable(loader):
                self._log("⚠ 分析层没有 load_gene_set() → 基因未加载（W3b 未就位？）")
                self._alert('failure', "分析层不支持加载基因")
                return
            valid_genes, lost_genes, valid_groups, spot_count = loader(gene_text)
            valid_genes = [str(g) for g in (valid_genes or [])]
            lost_genes = [str(g) for g in (lost_genes or [])]
            valid_groups = [str(g) for g in (valid_groups or [])]
            if not valid_genes:
                self._log("❌ 没有匹配到任何基因（输入 %r）" % (gene_text or ""))
                self._alert('error', "没有匹配到任何基因，请检查基因名")
                return
            # ★ 统一重算（候选列 + 值列表）：与"样本选择变化"走**同一条**链路
            self._recompute_from_samples("加载基因后")
            self._log("基因加载完成，有效基因数：%d，总 spot 数：%s"
                      % (len(valid_genes), spot_count))
            self._log("   有效基因: %s" % ", ".join(valid_genes[:10]))
            if lost_genes:
                tail = "..." if len(lost_genes) > 5 else ""
                self._log("未找到基因：%s%s" % (", ".join(lost_genes[:5]), tail))
            self._log("   分析层报告的可用分组: %s"
                      % (", ".join(valid_groups) if valid_groups else "（无）"))
        except ValueError as e:
            traceback.print_exc()
            self._log("❌ ValueError: %s" % e)
            self._alert('error', str(e))
        except Exception as e:
            traceback.print_exc()
            self._log("❌ 加载失败: %s: %s" % (type(e).__name__, e))
            self._alert('failure', "加载失败: %s" % e)

    # ==================================================================
    # 绘图（单细胞 `draw_gene_set_bubble_plot` 的 1:1 骨架；⛔ 不带 `collapsed`）
    # ==================================================================
    def _ensure_genes_loaded_for_draw(self):
        """★ v11.1：**绘图自己解析基因** —— 让「加载基因」按钮变成**可选**的早期校验

        用户真机反馈原话：「空转没必要带这个加载基因，而是直接在跑图时跑相应的基因即可」。

        判据：以**当前文本框**为准 ——
          · 文本框为空 ⇒ 给可读提示、不绘图；
          · 已加载且 `analysis.loaded_gene_text` 与当前文本**逐字相同** ⇒ 直接放行（不重复装配）；
          · 否则先走一遍 `load_gene_set_data()`（它会顺带装配数据集 + 重算分组选项），
            再放行。

        ★ 首次会触发数据集装配（`prepare()`：R dump + 装 AnnData），实测**约 10–30 秒**，
          所以**先写日志再动手**，避免用户以为卡死（幂等，之后每次都是瞬时）。
        """
        an = self._require_analysis()
        if an is None:
            return False
        text = self._text_of('spatial_genelist_bubble_text_input',
                             'spatial_genelist_text_input') or ""
        if not text.strip():
            self._log("⚠ 基因文本框是空的 —— 请先输入基因（每行一个）再绘图")
            self._alert('error', "请先输入基因（每行一个）")
            return False
        try:
            loaded = list(getattr(an, "gene_set_list", None) or [])
            same_text = getattr(an, "loaded_gene_text", None) == text
            # ★ 还必须要求 `adata` **仍在**：用户改样本选择会让 `set_context` 判定上下文已变
            #   ⇒ 丢弃上一次装配的 `adata`（防用旧数据建掩码）。此时旧基因表已过期，
            #   必须**按新上下文重新解析一遍**，否则会拿旧 spot 表去筛新样本（口径错）。
            data_alive = getattr(an, "adata", None) is not None
        except Exception:
            traceback.print_exc()
            loaded, same_text, data_alive = [], False, False
        if loaded and same_text and data_alive:
            return True
        self._log("正在按当前文本框解析基因并装配数据集（首次较慢，约 10–30 秒；之后走缓存）…")
        try:
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()          # 让上面那行日志先画出来
        except Exception:
            traceback.print_exc()
        try:
            self.load_gene_set_data()
        except Exception:
            traceback.print_exc()
            return False
        ok = bool(list(getattr(an, "gene_set_list", None) or []))
        if not ok:
            self._log("⚠ 基因没有加载成功 ⇒ 本次不绘图（原因见上方日志）")
        return ok

    def draw_gene_set_bubble_plot(self):
        """绘制基因集气泡图：读控件参数 → `analysis.draw_gene_set_bubble_plot(...)` → 图片上屏"""
        try:
            x_col = self._combo_text('spatial_genelist_bubble_main_combo')
            x_sel = self._selected_texts('spatial_genelist_bubble_main_list')

            if not x_col:
                if not self._current_selected_ids():
                    self._alert('error', "请先选择样本")
                    self._log(self.NO_SAMPLE_MSG)
                else:
                    self._alert('error', "请先选择 X轴分组注释")
                return
            if not x_sel:
                self._alert('error', "请至少选择一个分组取值")
                return

            f1_col, f1_sel = self._filter_selection('spatial_genelist_bubble_filter1')
            f2_col, f2_sel = self._filter_selection('spatial_genelist_bubble_filter2')

            main_title = self._text_of('spatial_genelist_bubble_bubble_main_title',
                                       'spatial_genelist_bubble_main_title')
            fig_width = self._spin_value('spatial_genelist_bubble_fig_width', 9)
            fig_height = self._spin_value('spatial_genelist_bubble_fig_height', 7)
            scale_factor = self._spin_value('spatial_genelist_bubble_scale_factor', 750)
            legend_scale = self._spin_value('spatial_genelist_bubble_legend_scale', 10) / 10.0
            main_right_ratio = (self._spin_value(
                'spatial_genelist_bubble_main_right_ratio', 65) / 100.0)
            title_fontsize = self._spin_value('spatial_genelist_bubble_title_fontsize', 14)
            x_label_fontsize = self._spin_value('spatial_genelist_bubble_x_label_fontsize', 12)
            y_label_fontsize = self._spin_value('spatial_genelist_bubble_y_label_fontsize', 12)
            label_spacing = self._spin_value('spatial_genelist_bubble_label_spacing', 25) / 10.0
            legend_title_fontsize = self._spin_value(
                'spatial_genelist_bubble_legend_label_fontsize', 10)
            cbar_label_fontsize = self._spin_value(
                'spatial_genelist_bubble_cbar_label_fontsize', 10)
            cbar_label_text = self._text_of('spatial_genelist_bubble_bubble_cbar_label',
                                            'spatial_genelist_bubble_cbar_label')

            # ★★ v11.1：绘图**自己**解析基因（用户要求"直接在跑图时跑相应的基因"）
            #   ⇒ 用户可以跳过「加载基因」，直接点「筛选并绘图」。
            if not self._ensure_genes_loaded_for_draw():
                return

            an = self._require_analysis()
            if an is None:
                return
            drawer = getattr(an, 'draw_gene_set_bubble_plot', None)
            if not callable(drawer):
                self._log("⚠ 分析层没有 draw_gene_set_bubble_plot() → 未绘图（W3b 未就位？）")
                self._alert('failure', "分析层不支持基因集气泡图")
                return

            self._log("开始绘制基因集气泡图...")
            self._log("X轴分组: %s（选中 %d 个取值）" % (x_col, len(x_sel)))
            self._log("筛选1: %s | 筛选2: %s"
                      % (("%s=%s" % (f1_col, f1_sel)) if f1_col else "未启用",
                         ("%s=%s" % (f2_col, f2_sel)) if f2_col else "未启用"))
            # ★ §2.4.4：参与/被排除样本**必须**写进日志（不许静默）
            self._log_participating_samples(an, x_col, [])

            spot_count, fig_path = drawer(
                x_col, x_sel,
                f1_col=f1_col, f1_sel=f1_sel, f2_col=f2_col, f2_sel=f2_sel,
                main_title=main_title, scale_factor=scale_factor, legend_scale=legend_scale,
                main_right_ratio=main_right_ratio, title_fontsize=title_fontsize,
                x_label_fontsize=x_label_fontsize, y_label_fontsize=y_label_fontsize,
                label_spacing=label_spacing, legend_title_fontsize=legend_title_fontsize,
                cbar_label_fontsize=cbar_label_fontsize, cbar_label_text=cbar_label_text,
                fig_width=fig_width, fig_height=fig_height)

            self._log("筛选后 spot 数: %s" % spot_count)
            self._call_func('display_image', fig_path)
            self._log("绘图完成")
        except ValueError as e:
            traceback.print_exc()
            self._log("❌ ValueError: %s" % e)
            self._alert('error', str(e))
        except Exception as e:
            traceback.print_exc()
            self._log("❌ 绘图失败: %s: %s" % (type(e).__name__, e))
            self._alert('failure', "绘图失败: %s" % e)

    # ==================================================================
    # 导出（默认文件名与前置检查照抄单细胞；⛔ 不自动落盘）
    # ==================================================================
    def export_png(self):
        """导出 PNG（默认名 `gene_set_bubble.png`；前置检查 `current_fig_path is None`）"""
        if self.analysis is None or getattr(self.analysis, 'current_fig_path', None) is None:
            self._log("请先绘图（还没有可导出的图片）")
            self._alert('error', "请先绘图")
            return
        default_name = "gene_set_bubble.png"
        save_path = self._save_path("保存图片为PNG", default_name, "PNG文件 (*.png)")
        if not save_path:
            self._log("已取消导出 PNG（用户没有选择保存路径）")
            return
        try:
            self.analysis.export_png(save_path)
            self._log("图片已保存到: %s" % save_path)
            self._alert('success', "图片已保存到:\n%s" % save_path)
        except Exception as e:
            traceback.print_exc()
            self._log("❌ 导出 PNG 失败: %s: %s" % (type(e).__name__, e))
            self._alert('failure', "导出失败: %s" % e)

    def export_csv(self):
        """导出 CSV（默认名 `gene_set_bubble_data.csv`；前置检查 `gene_set_final_df is None`）"""
        if self.analysis is None or getattr(self.analysis, 'gene_set_final_df', None) is None:
            self._log("请先绘图（还没有可导出的绘图数据）")
            self._alert('error', "请先绘图")
            return
        default_name = "gene_set_bubble_data.csv"
        save_path = self._save_path("保存数据为CSV", default_name, "CSV文件 (*.csv)")
        if not save_path:
            self._log("已取消导出 CSV（用户没有选择保存路径）")
            return
        try:
            self.analysis.export_csv(save_path)
            self._log("数据已保存到: %s" % save_path)
            self._alert('success', "数据已保存到:\n%s" % save_path)
        except Exception as e:
            traceback.print_exc()
            self._log("❌ 导出 CSV 失败: %s: %s" % (type(e).__name__, e))
            self._alert('failure', "导出失败: %s" % e)

    def export_other(self, fmt):
        """导出 PDF/SVG/EPS（默认名 `基因集气泡图.<fmt>`；**重画**由分析层负责）

        ★ 规格 §2.7/§2.8 缺陷 2：空转版**必须复用用户当前参数**（由分析层从上下文取），
          且 y 轴取**基因名**（不是 `columns[1]`）——故这里只把 `fmt` 交给分析层。
        """
        if self.analysis is None or getattr(self.analysis, 'gene_set_final_df', None) is None:
            self._log("请先绘图（还没有可导出的绘图数据）")
            self._alert('error', "请先绘图")
            return
        fmt = str(fmt).lower()
        default_name = "基因集气泡图.%s" % fmt
        save_path = self._save_path("保存图片为%s" % fmt.upper(), default_name,
                                    "%s文件 (*.%s)" % (fmt.upper(), fmt))
        if not save_path:
            self._log("已取消导出 %s（用户没有选择保存路径）" % fmt.upper())
            return
        try:
            exporter = getattr(self.analysis, 'export_other', None)
            if not callable(exporter):
                self._log("⚠ 分析层没有 export_other() → 未导出 %s" % fmt.upper())
                self._alert('failure', "分析层不支持导出 %s" % fmt.upper())
                return
            exporter(save_path, fmt)
            self._log("图片已保存到: %s" % save_path)
            self._alert('success', "图片已保存到:\n%s" % save_path)
        except Exception as e:
            traceback.print_exc()
            self._log("❌ 导出 %s 失败: %s: %s" % (fmt.upper(), type(e).__name__, e))
            self._alert('failure', "导出失败: %s" % e)

    def _save_path(self, title, default_name, filter_text):
        """保存对话框（走 func；func 缺失 → 留痕并返回空串，**绝不自己落盘**）"""
        try:
            ok, path = self._call_func('get_save_file_path', title, default_name, filter_text)
            if not ok:
                return ""
            return str(path or "")
        except Exception:
            traceback.print_exc()
            return ""

    # ==================================================================
    # 内部小工具（**全部 getattr 守卫**：缺控件只留痕、不抛）
    # ==================================================================
    def _widget(self, *names):
        """按顺序取第一个存在的控件（**别名兼容**；都没有 → None）

        ★ 规格 §2.3 的前缀公式 `P_bubble_*`（P 已含 `_bubble`）会得到
          `spatial_genelist_bubble_bubble_*` 这种"双 bubble"名；单细胞原型对应的是
          `..._bubble_log` / `..._bubble_main_title` / `..._bubble_cbar_label`。
          两种写法都可能是 W1 的落地形态 ⇒ 本页**两个名字都探**，取到就用，避免
          「控件建成 ≠ 数据路径通」这类只在运行期暴露的错位。
        """
        try:
            for name in names:
                w = getattr(self.ui, name, None)
                if w is not None:
                    return w
            return None
        except Exception:
            traceback.print_exc()
            return None

    def _log_widget(self):
        """本页日志控件（兼容 §2.3 公式名与单细胞同款名）"""
        return self._widget('spatial_genelist_bubble_bubble_log',
                            'spatial_genelist_bubble_log')

    def _text_of(self, *names):
        """读 QLineEdit/QTextEdit 的文本（控件缺失 → 空串；**守卫用 `is None`**）"""
        try:
            w = self._widget(*names)
            if w is None:
                self._log("⚠ 布局缺少控件 %s → 该参数取默认值" % (names[0] if names else "?"))
                return ""
            if hasattr(w, 'text'):
                return str(w.text() or "").strip()
            if hasattr(w, 'toPlainText'):
                return str(w.toPlainText() or "").strip()
            return ""
        except Exception:
            traceback.print_exc()
            return ""

    def _spin_value(self, name, default):
        """读 QSpinBox 的值（控件缺失 → 默认值）"""
        try:
            w = getattr(self.ui, name, None)
            if w is None or not hasattr(w, 'value'):
                self._log("⚠ 布局缺少控件 %s → 使用默认值 %s" % (name, default))
                return default
            return w.value()
        except Exception:
            traceback.print_exc()
            return default

    def _combo_text(self, name):
        """读下拉框当前文本（控件缺失 → 空串）"""
        try:
            w = getattr(self.ui, name, None)
            if w is None:
                return ""
            return str(w.currentText() or "")
        except Exception:
            traceback.print_exc()
            return ""

    def _selected_texts(self, list_name):
        """读多选列表当前选中的文本（控件缺失 → 空列表）"""
        try:
            w = getattr(self.ui, list_name, None)
            if w is None:
                self._log("⚠ 布局缺少控件 %s → 该取值列表按空处理" % list_name)
                return []
            return [str(item.text()) for item in w.selectedItems()]
        except Exception:
            traceback.print_exc()
            return []

    def _filter_selection(self, prefix):
        """读一个筛选（`<prefix>_enable` / `_combo` / `_list`）→ `(col, values)`

        ★ 未勾选「启用筛选N」⇒ 返回 `(None, [])`（= 不筛），与单细胞逐字一致。
        """
        try:
            box = getattr(self.ui, prefix + '_enable', None)
            if box is None or not hasattr(box, 'isChecked') or not box.isChecked():
                return None, []
            return (self._combo_text(prefix + '_combo'),
                    self._selected_texts(prefix + '_list'))
        except Exception:
            traceback.print_exc()
            return None, []

    def _safe_set_combo_items(self, name, items):
        """经 `func.set_combo_items` 设下拉内容（保住当前选中；控件缺失只留痕）"""
        try:
            w = getattr(self.ui, name, None)
            if w is None:
                self._log("⚠ 布局缺少控件 %s → 该下拉未重算（需要 W1 提供）" % name)
                return
            self._call_func('set_combo_items', w, items)
        except Exception:
            traceback.print_exc()

    def _log(self, msg):
        """写日志（优先 func.log → 本页日志控件 → 控制台；**绝不静默**）"""
        try:
            if self.func is not None and hasattr(self.func, 'log'):
                self.func.log(msg)
                return
            widget = self._log_widget()
            if widget is not None and hasattr(widget, 'append'):
                widget.append(str(msg))
                return
            print("[SpatialGenelistBubbleBind] %s" % msg)
        except Exception:
            traceback.print_exc()
            try:
                print("[SpatialGenelistBubbleBind] %s" % msg)
            except Exception:
                pass

    def _log_lines(self, lines):
        """批量写日志（空列表直接返回）"""
        try:
            for line in (lines or []):
                self._log(line)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 音量 / 兼容接口（照差异页；本页数据来自 hub 的 set_context）
    # ==================================================================
    def set_volume(self, value):
        """设置音量（音乐控件回调）"""
        try:
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_music_player'):
                mod_instance.global_music_player.set_volume(value / 100.0)
            if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
                self.parent._sync_all_volume_sliders_from_subinterface(value)
        except Exception:
            traceback.print_exc()

    def set_adata(self, adata):
        """设置 adata 对象（兼容旧接口；本页正常路径不调用）"""
        try:
            if self.analysis is not None and hasattr(self.analysis, 'set_adata'):
                self.analysis.set_adata(adata)
            else:
                self._log("⚠ 分析层没有 set_adata → 本次注入被忽略（本页走 set_context）")
        except Exception:
            traceback.print_exc()

    def set_dataset_output_dir(self, dataset_output_dir):
        """设置数据集输出目录（兼容旧接口；本页正常路径不调用）"""
        try:
            if self.analysis is not None and hasattr(self.analysis, 'set_dataset_output_dir'):
                self.analysis.set_dataset_output_dir(dataset_output_dir)
            else:
                self._log("⚠ 分析层没有 set_dataset_output_dir → 本次注入被忽略")
        except Exception:
            traceback.print_exc()


__all__ = ['SpatialGenelistBubbleBind']
