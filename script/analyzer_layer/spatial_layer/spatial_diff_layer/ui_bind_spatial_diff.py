# -*- coding: utf-8 -*-
"""
空转差异分析界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作

## 复刻来源（**近似 1:1**）
`script/analyzer_layer/scRNAseq_layer/diff_layer/py_diff/ui_bind_diff.py`（421 行）。
逐字保留的骨架：`self.analysis = <分析层>()` + `self.func = <Func>(ui, parent_window)` +
`init_bindings()`；`get_filter_mask`；「三条空选校验 → 6 行日志 → 跑分析 → 更新统计 →
填三张表 → 渲染火山图 → 收尾日志」；`ValueError → alert_error` / 其它 →
`alert_failure` + traceback 进日志；导出 xlsx 的 4 个 sheet 与组名折叠规则。

## ★★ 本页的灵魂（原型**没有**，全部新增）：按所选样本动态生成「注释分组 / 注释值」
规格 §4。判据**一行都不在本文件里** —— 全部委托给 W3 的
`SpatialDiffAnalysis.available_group_columns()` / `group_unique_values(col)` /
`participating_samples(col)`；本页只负责「读控件 → 调分析层 → 重填控件 → 写日志」。
- `sample_list.selectionChanged` → 重算分组下拉（保住当前选中，不在列表里则回落第一项）
  → 再按当前分组重算两个注释值列表 + 两个筛选列/筛选值列表；
- `diff_group_combo.currentIndexChanged` → 只重算两个注释值列表（**不自动勾选**）；
- 两个筛选列下拉变更 → 只重填对应筛选值列表；
- ⛔ 以上重算**只改控件内容**：不写盘、不落盘、不调分析层跑统计；
  `samples` 为空 ⇒ 三个下拉/列表清空 + 日志「请先选择样本」（不崩）。

## ⛔ 不做的事
- **不复制**原型的 `nav_btn_python` / `nav_btn_r` 切换逻辑（规格 §5.2：本轮只做一种实现，
  不留点了没反应的按钮）；
- 不写盘：中间产物归 W3（`OUTPUT/<ds>/08_GeneOnDemand/_diff/`），导出走 `QFileDialog`；
- 不自己筛样本再交给分析层（覆写版 `run_diff_analysis` 内部自己按 `participating_samples`
  跑 R dump 并装配数据）⇒ 调用方式与原型**逐字一致**（规格 §6.1）。
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.spatial_layer.spatial_diff_layer.ui_func_spatial_diff import SpatialDiffFunc
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.gene_list_export import ask_and_send                       # noqa: F401
from script.utils_layer.page_intersect import page_intersect


def _warn(msg):
    """模块级留痕（与 `spatial_violin_analysis._warn` 同款形状：打印 + 不抛）"""
    try:
        print("[SpatialDiffBind] %s" % msg)
    except Exception:
        pass


class SpatialDiffBind:
    """空转差异分析功能绑定类 - 全权负责粘合内外"""

    #: 空选守卫文案（规格 §4.4/§4.5：**绝不静默**、**绝不抛**）
    NO_SAMPLE_MSG = "⚠ 请先在左侧选择样本（注释分组/注释值按所选样本的并集生成）"

    def __init__(self, parent_window, ui_instance):
        self.parent = parent_window
        self.ui = ui_instance
        self.analysis = self._make_analysis()
        self.func = SpatialDiffFunc(ui_instance, parent_window)
        # 重算守卫：程序化重填控件期间为 True（防信号回环 + 防重复重算）
        self._recomputing = False
        # 三个"当前已知可选"的缓存：控件缺失/无数据集时仍能给日志一个确定的空值
        self._group_cols = []
        self._analysis_notes = []
        self.init_bindings()

    # ==================================================================
    # 分析层（★ 延迟 + 容错构造：W3 的文件缺失时本页**不崩**，只留痕）
    # ==================================================================
    def _make_analysis(self):
        """构造 `SpatialDiffAnalysis`（规格 §4 的判据全部在它里面）

        ## ★ 为什么用延迟 import 而不是模块顶层 import
          原型（`ui_bind_diff.py:9`）是顶层 import；本页是**并行施工**的新页
          （W3 的 `spatial_diff_analysis.py` 与本文件同时产出），顶层 import 会让
          「分析层文件还没到位」直接炸掉**整个空转 hub 的页面初始化**。故：
          `try/except` + `traceback.print_exc()` 留痕 → 返回 None →
          真正要跑分析时再给一句可读提示（**绝不静默、绝不抛**）。
        """
        try:
            from script.analyzer_layer.spatial_layer.spatial_diff_layer.spatial_diff_analysis import (
                SpatialDiffAnalysis)
            return SpatialDiffAnalysis()
        except Exception:
            traceback.print_exc()
            _warn("⚠ 无法构造 SpatialDiffAnalysis（W3 的分析层未就位？）"
                  "→ 本页的选项重算与运行将不可用（已留痕，不抛）")
            return None

    def _require_analysis(self):
        """取分析层；没有就留痕 + 可读提示 + 返回 None（**绝不抛**）"""
        if self.analysis is None:
            self.func.log("⚠ 差异分析层不可用（SpatialDiffAnalysis 未就绪，见控制台 traceback）")
            self.func.alert_failure("差异分析层不可用")
            return None
        return self.analysis

    # ==================================================================
    # 绑定入口
    # ==================================================================
    def init_bindings(self):
        """初始化所有绑定（每个槽自带 try/except，防 PyQt5 对未捕获异常 qFatal）"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_sample_list()
        self.bind_diff_functions()
        self.bind_sample_buttons()

    def bind_music_controls(self):
        """绑定音乐控制"""
        try:
            if hasattr(self.ui, 'music_controller'):
                fix_music_controller_bindings(self, self.ui.music_controller)
        except Exception:
            traceback.print_exc()

    def bind_navigation(self):
        """绑定页面导航按钮

        ★ 返回 **hub**（`spatial_top_page`），与其它空转子页一致
          （`spatial_region_layer/ui_bind_spatial_region.py:3503` 同款写法）。
        ⛔ **不接** `nav_btn_python` / `nav_btn_r`（规格 §5.2：本轮不复制原型那两个页签）。
        """
        try:
            if hasattr(self.ui, 'nav_btn_back'):
                self.ui.nav_btn_back.clicked.connect(self._on_back_clicked)
            else:
                self.func.log("⚠ 布局缺少控件 nav_btn_back → 返回主页未绑定（需要 W1 提供）")
        except Exception:
            traceback.print_exc()

    def _on_back_clicked(self):
        """回 hub（空转子页的「返回」一律回 hub）"""
        try:
            page_intersect.go_to_page_with_bind('spatial_top_page')
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 数据来源（契约：从 `self.parent.spatial_top_bind.analysis` 读）
    # ==================================================================
    def _top_bind(self):
        """取空转顶层 bind（`self.parent.spatial_top_bind`；**不是** scRNAseq_top_bind）"""
        try:
            return getattr(self.parent, 'spatial_top_bind', None)
        except Exception:
            traceback.print_exc()
            return None

    def _dataset_context(self):
        """读数据来源（**只读**，不写盘）→ `(dataset, out_dir, error)`

        ★ 数据源 = `self.parent.spatial_top_bind.analysis` 的
          `dataset_name` / `dataset_output_dir`（与审查页/初始页/表达页同一真相源）。
        ★ 取不到 ⇒ 返回 `error` 文案，**由调用方写日志 + 给可读提示**（绝不抛）；
          也**绝不**在这里 `os.makedirs` —— 本页不写盘（规格 §7.7）。
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
                return None, out_dir, "尚未加载空转数据集（请先在主页『扫描数据路径』并『加载数据集』）"
            if not out_dir:
                # 数据集名有了、输出目录没有：**不猜**、不写盘，只留痕
                return dataset, None, "数据集 %s 已加载，但 dataset_output_dir 为空" % dataset
            return dataset, out_dir, None
        except Exception:
            traceback.print_exc()
            return None, None, "读取数据来源时异常（见控制台 traceback）"

    def _sample_records(self):
        """返回样本清单 `[{id, label}, ...]`（**只读** manifest 的 samples[]，不写盘）"""
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
                    records.append({'id': sid,
                                    'label': str(row.get('label', '') or '')})
                else:
                    sid = str(row or '').strip()
                    if sid:
                        records.append({'id': sid, 'label': ''})
        except Exception:
            traceback.print_exc()
        return records

    def _read_selected_sample_ids(self):
        """读当前选中的样本 id（★ 以 UI 为准；取不到且**有数据来源**时给可读提示）

        ⛔ 数据来源根本没加载时**绝不弹窗**（那是正常空状态，照表达页的空选守卫语义：
          只写日志 + 返回空列表），否则每次进页都会弹一次"请先选择样本"。
        """
        ids = []
        try:
            if hasattr(self.func, 'get_selected_sample_ids'):
                raw = self.func.get_selected_sample_ids()
                ids = [str(x) for x in (raw or []) if x]
        except Exception:
            traceback.print_exc()
            ids = []
        if not ids:
            dataset, _out, error = self._dataset_context()
            if error:
                self._log("⚠ %s" % error)
            else:
                self._log(self.NO_SAMPLE_MSG)
        return ids

    # ==================================================================
    # ★★ 样本选择 → 重算「注释分组 / 注释值」（规格 §4）
    # ==================================================================
    def bind_sample_list(self):
        """`sample_list.itemSelectionChanged` → 重算分组与注释值（规格 §4.3）

        ## ★★ 信号选择：`itemSelectionChanged` **必须优先**（D 系列修复）
          `QListWidget` 上 `hasattr(lst, 'selectionChanged')` 为 **True**，但那是
          `QAbstractItemView` 的**受保护槽**透出来的属性，**连接后从不发火**
          （协调者离屏实测：挂三路记录器后 `setSelected(True)` 只有
          `itemSelectionChanged` 与 `selectionModel().selectionChanged` 触发）
          ⇒ 之前写成 `selectionChanged` 优先，结果是**样本选择永远不会触发选项重算**、
          `diff_group_combo` 恒为空（控件建成 ≠ 数据路径通）。
          ⇒ 现在与同项目既有两个页保持一致：
            `ui_bind_spatial_expression.py:360` / `ui_bind_spatial_initial.py:497`
            都是**先认 `itemSelectionChanged`**；`selectionChanged` 仅作兜底保留
            （防 W1 之后把控件换成别的类型）。
        """
        try:
            lst = getattr(self.ui, 'sample_list', None)
            if lst is None:
                self.func.log("⚠ 布局缺少控件 sample_list → 样本选择未绑定（需要 W1 提供）")
                return
            if hasattr(lst, 'itemSelectionChanged'):
                lst.itemSelectionChanged.connect(self._on_sample_selection_changed)
            elif hasattr(lst, 'selectionChanged') and hasattr(lst.selectionChanged, 'connect'):
                # 兜底：QListWidget 上 selectionChanged 是 `QAbstractItemView` 的**受保护槽**
                # （实测 `hasattr` 为 True、却是 builtin method，**没有 `.connect`**）
                # ⇒ 必须再查 `.connect` 才安全；保留它只为防 W1 之后把控件换成别的类型。
                lst.selectionChanged.connect(self._on_sample_selection_changed)
            else:
                self.func.log("⚠ sample_list 没有可用的选择信号 → 样本选择未绑定")
        except Exception:
            traceback.print_exc()

    def bind_sample_buttons(self):
        """`btn_sample_all` / `btn_sample_invert`（规格 §5.2 的快捷选择）"""
        try:
            for attr, handler in (('btn_sample_all', self._on_select_all_clicked),
                                  ('btn_sample_invert', self._on_select_invert_clicked)):
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(handler)
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
            lst = getattr(self.ui, 'sample_list', None)
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
            if hasattr(self.func, 'refresh_selected_count'):
                self.func.refresh_selected_count()
        except Exception:
            traceback.print_exc()

    def _on_sample_selection_changed(self):
        """样本选择变化槽（槽内**绝不抛**：PyQt5 对未捕获异常会 qFatal）"""
        try:
            self._recompute_from_samples("样本选择变化")
        except Exception:
            traceback.print_exc()

    def _recompute_from_samples(self, reason=""):
        """按当前 UI 上的样本选择，重算**整条选项链**（规格 §4.3）

        链路：样本 → `set_context(dataset, samples)` → 分组下拉 →
              两个注释值列表 + 两个筛选列/筛选值列表。
        ⛔ 只改控件内容：**不写盘、不落盘、不调分析层跑统计**。
        """
        logs = []
        try:
            if self._recomputing:
                # 程序化重填控件导致的回环 → 直接忽略（不是错误）
                return
            self._recomputing = True
            try:
                # ① 读当前选中（以 UI 为准；空选时本方法内部会写日志/提示）
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
                    logs.append("⚠ 差异分析层不可用（SpatialDiffAnalysis 未就绪）→ 选项未重算")
                    return
                if not dataset:
                    logs.append("⚠ 尚未确定数据集 → 选项未重算")
                    return
                # ③ 上下文（覆写版内部自己按 participating_samples 跑 R dump，bind 不筛样本）
                try:
                    an.set_context(dataset, samples)
                except Exception:
                    traceback.print_exc()
                    logs.append("⚠ 同步分析上下文失败（见控制台 traceback）")
                # ③b ★ rds 真实路径注入（存在性安全）
                #   W3 报告：`set_context(dataset, samples)` 只传数据集名 ⇒ 分析层按
                #   `SPATIAL_SCAN_DATA_PATH/<dataset>.rds` 推断；**用户在自定义目录扫的数据集**
                #   就找不到 rds（读不到矩阵 ⇒ 差异分析跑不起来）。
                #   真相源 = hub 的 `analysis.artifact_info['path']`（主页已校验过的成品 rds）。
                #   ⛔ 只读注入：拿不到/无该方法一律**只留痕不抛**，沿用分析层默认推断。
                try:
                    top = self._top_bind()
                    top_an = getattr(top, 'analysis', None)
                    art = getattr(top_an, 'artifact_info', None) or {}
                    rds = str(art.get('path') or '')
                    if rds:
                        setter = getattr(an, 'set_rds_path', None)
                        if callable(setter):
                            setter(rds)
                            logs.append("rds 真实路径（取自 hub artifact_info）: %s" % rds)
                        else:
                            logs.append("⚠ 分析层无 set_rds_path()（W3 未就位？）→ 沿用默认扫描目录推断")
                    else:
                        logs.append("⚠ hub 的 artifact_info 无 path → 沿用默认扫描目录推断 rds")
                except Exception:
                    traceback.print_exc()
                    logs.append("⚠ 注入 rds 路径失败 → 沿用默认推断（见控制台 traceback）")
                # ④ 分组下拉（保住当前选中；不在列表里则回落第一项）
                self._recompute_group_options(an, logs)
                # ⑤ 两个注释值列表 + 两个筛选列/筛选值列表
                current = self._combo_text('diff_group_combo')
                self._recompute_group_lists(an, current, logs)
                self._recompute_filter_cols(an, logs)
                self._recompute_filter_values(logs)
                if out_dir:
                    logs.append("输出根目录（**本页不写盘**，中间产物归分析层）: %s" % out_dir)
            finally:
                self._recomputing = False
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重算注释分组/注释值时异常（见控制台 traceback）")
        finally:
            self._log_lines(logs)

    def _clear_option_controls(self, logs):
        """空选/无数据时的清空路径（规格 §4.5：三个下拉/列表清空 + 「请先选择样本」）"""
        try:
            for name in ('diff_group1_list', 'diff_group2_list',
                         'diff_filter1_list', 'diff_filter2_list'):
                w = getattr(self.ui, name, None)
                if w is not None:
                    try:
                        self.func.fill_list_widget(w, [], select_all=False)
                    except Exception:
                        traceback.print_exc()
            self._safe_set_combo_items('diff_filter1_col', [''])
            self._safe_set_combo_items('diff_filter2_col', [''])
            self._safe_set_combo_items('diff_group_combo', [])
            self._group_cols = []
            logs.append("分组/注释值/筛选控件已清空（未选择任何样本）")
            logs.append("⛔ 说明：本次只清空控件内容，**未**写盘、未调用分析层跑统计")
        except Exception:
            traceback.print_exc()

    def _recompute_group_options(self, an, logs):
        """重算 `diff_group_combo`（规格 §4.2.1/§4.3：**保住当前选中**，否则回落第一项）"""
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
        # ★ 保住当前选中：仍在列表里就保持（`set_combo_items` 内部按 saved_text 判定），
        #   否则它会自动落到 addItems 后的**第一项**（= 规格的"回落到第一项"）。
        self._safe_set_combo_items('diff_group_combo', cols)
        logs.append("可用注释分组（按所选样本的并集）: %s" % (", ".join(cols) if cols else "（无）"))

    def _recompute_group_lists(self, an, group_col, logs):
        """重算 `diff_group1_list` / `diff_group2_list`（**不自动勾选**）+ 参与/排除样本日志"""
        values = []
        try:
            if group_col:
                getter = getattr(an, 'group_unique_values', None)
                if callable(getter):
                    values = [str(v) for v in (getter(group_col) or [])]
                else:
                    logs.append("⚠ 分析层没有 group_unique_values() → 注释值列表未重算")
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 读取注释值列表失败（见控制台 traceback）")
            values = []
        for name in ('diff_group1_list', 'diff_group2_list'):
            w = getattr(self.ui, name, None)
            if w is None:
                continue
            try:
                self.func.fill_list_widget(w, values, select_all=False)
            except Exception:
                traceback.print_exc()
        if group_col:
            logs.append("分组『%s』的注释值（并集去重排序）: %s"
                        % (group_col, ", ".join(values) if values else "（无）"))
            if len(values) <= 1:
                logs.append("⚠ 分组『%s』只有一个取值，无法比较（允许点运行，但会提示）" % group_col)
        self._log_participating_samples(an, group_col, logs)

    def _log_participating_samples(self, an, group_col, logs):
        """★ 规格 §4.2.3 + §7.4：把**参与分析的样本**与**被排除的样本**写进日志（不许静默）"""
        try:
            if not group_col:
                return
            getter = getattr(an, 'participating_samples', None)
            if not callable(getter):
                logs.append("⚠ 分析层没有 participating_samples() → 参与样本未能核实")
                return
            part = [str(s) for s in (getter(group_col) or [])]
            selected = [str(x) for x in (self._read_selected_sample_ids() or [])]
            excluded = [s for s in selected if s not in set(part)]
            logs.append("参与分析的样本（%d/%d）: %s"
                        % (len(part), len(selected), ", ".join(part) if part else "（无）"))
            if excluded:
                logs.append("被排除的样本（%d）: %s"
                            % (len(excluded), ", ".join(excluded)))
                if group_col == 'group_graphed':
                    logs.append("（`group_graphed` 只在**有绘图注释**的样本里分析，"
                                "其余样本无 graph 注释 → 已排除）")
                else:
                    logs.append("（这些样本在『%s』列上没有非空值 → 已排除）" % group_col)
            else:
                logs.append("被排除的样本: 无（所选样本全部参与）")
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 两个筛选列 / 筛选值（照原型 `ui_bind_diff.py:120-149`）
    # ==================================================================
    def _recompute_filter_cols(self, an, logs):
        """筛选列下拉 = `[''] + available_group_columns()`（首项空串 = 不筛，照原型 `:126`）"""
        try:
            getter = getattr(an, 'available_group_columns', None)
            cols = [str(c) for c in (getter() or [])] if callable(getter) else []
            items = [''] + cols
            for name in ('diff_filter1_col', 'diff_filter2_col'):
                self._safe_set_combo_items(name, items)
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重填筛选列下拉失败（见控制台 traceback）")

    def _recompute_filter_values(self, logs):
        """两个筛选值列表按各自当前列重填（照原型 `load_filter_values` `:137-149`）"""
        try:
            for col_name, list_name in (('diff_filter1_col', 'diff_filter1_list'),
                                        ('diff_filter2_col', 'diff_filter2_list')):
                col = self._combo_text(col_name)
                values = []
                if col and self.analysis is not None:
                    getter = getattr(self.analysis, 'group_unique_values', None)
                    if callable(getter):
                        try:
                            values = [str(v) for v in (getter(col) or [])]
                        except Exception:
                            traceback.print_exc()
                            values = []
                w = getattr(self.ui, list_name, None)
                if w is None:
                    continue
                try:
                    self.func.fill_list_widget(w, values, select_all=False)
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重填筛选值列表失败（见控制台 traceback）")

    def on_filter1_col_changed(self):
        """筛选条件1 列变化（原型 `:112-114`）"""
        try:
            logs = []
            self._recompute_filter_values(logs)
            self._log_lines(logs)
        except Exception:
            traceback.print_exc()

    def on_filter2_col_changed(self):
        """筛选条件2 列变化（原型 `:116-118`）"""
        try:
            logs = []
            self._recompute_filter_values(logs)
            self._log_lines(logs)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 功能绑定（照原型 `bind_diff_functions` `:81-110`）
    # ==================================================================
    def bind_diff_functions(self):
        """绑定差异分析功能信号"""
        try:
            log_widget = getattr(self.ui, 'diff_log', None)

            if hasattr(self.ui, 'btn_run_diff'):
                bind_button_with_sound(self.ui.btn_run_diff, self.run_diff_analysis,
                                       log_widget, "差异分析完成", "差异分析失败")
            else:
                self.func.log("⚠ 布局缺少控件 btn_run_diff → 运行入口未绑定（需要 W1 提供）")

            if hasattr(self.ui, 'btn_export_csv'):
                bind_button_with_sound(self.ui.btn_export_csv, self.export_results,
                                       log_widget, "导出完成", "导出失败")
            else:
                self.func.log("⚠ 布局缺少控件 btn_export_csv → 导出 Excel 未绑定")

            if hasattr(self.ui, 'btn_export_png'):
                bind_button_with_sound(self.ui.btn_export_png, self.export_png,
                                       log_widget, "PNG导出完成", "PNG导出失败")
            else:
                self.func.log("⚠ 布局缺少控件 btn_export_png → 导出火山图未绑定")

            # ★ 「发送到列表文件夹」（契约 §1/§4）：**直接** `clicked.connect` 到本页回调。
            #   ⛔ 不套 `bind_button_with_sound`：那会额外弹 happy 音效/写 ✓ 日志，
            #      而契约 §4.4 要求成功后只留「[INFO] 已发送 …（写入 N 个基因）」。
            if hasattr(self.ui, 'btn_send_to_genelist'):
                self.ui.btn_send_to_genelist.clicked.connect(self.send_gene_list_to_folder)
            else:
                self.func.log("⚠ 布局缺少控件 btn_send_to_genelist → 发送到列表文件夹未绑定")

            if hasattr(self.ui, 'diff_group_combo'):
                self.ui.diff_group_combo.currentIndexChanged.connect(self.on_group_combo_changed)
            else:
                self.func.log("⚠ 布局缺少控件 diff_group_combo → 分组选项未绑定")

            if hasattr(self.ui, 'diff_filter1_col'):
                self.ui.diff_filter1_col.currentIndexChanged.connect(self.on_filter1_col_changed)
            if hasattr(self.ui, 'diff_filter2_col'):
                self.ui.diff_filter2_col.currentIndexChanged.connect(self.on_filter2_col_changed)

            # ★ 基因搜索走既有 Mixin（`SpatialDiffFunc.setup_gene_search`），此处只接线
            if hasattr(self.ui, 'gene_search_btn') and self.func:
                self.ui.gene_search_btn.clicked.connect(self.func.search_gene)
            if hasattr(self.ui, 'gene_search_input') and self.func:
                self.ui.gene_search_input.returnPressed.connect(self.func.search_gene)
        except Exception:
            traceback.print_exc()

    def on_group_combo_changed(self):
        """分组下拉变化 → 只重算两个注释值列表（规格 §4.3；**不自动勾选**）"""
        logs = []
        try:
            if self._recomputing:
                return
            self._recomputing = True
            try:
                if self.analysis is None:
                    logs.append("⚠ 差异分析层不可用 → 注释值未重算")
                    return
                col = self._combo_text('diff_group_combo')
                if not col:
                    logs.append(self.NO_SAMPLE_MSG)
                    self._recompute_group_lists(self.analysis, '', logs)
                    return
                self._recompute_group_lists(self.analysis, col, logs)
            finally:
                self._recomputing = False
        except Exception:
            traceback.print_exc()
            logs.append("⚠ 重算注释值列表时异常（见控制台 traceback）")
        finally:
            self._log_lines(logs)

    # ==================================================================
    # ★ 进页钩子（原型没有；规格 §7.6 必须实现）
    # ==================================================================
    def on_page_entered(self):
        """每次跳转到本页时由 `page_intersect.go_to_page_with_bind` 调用（可选钩子）

        ## ★ 为什么必须有它（规格 §7.6）
          原型两个 diff 页都**没有**这个钩子 ⇒ 数据集在首次进页**之后**才加载时，
          样本列表与下拉永远不会刷新（D8 事故同型）。
          本页要做四件事：
            ① 重填样本列表（**保住已选**）→ ② `set_context` → ③ 重算分组 →
            ④ 重算注释值（两个注释值列表 + 两个筛选列/筛选值列表）。
        ★ 无数据集时**只留痕、不抛**；且**不弹窗**（正常空状态）。
        """
        try:
            self._log("【差异分析】进入页面")
            dataset, out_dir, error = self._dataset_context()
            if dataset:
                self._log("数据集: %s" % dataset)
            # ① 样本列表（保住已选）—— **无论有没有数据集都做**（清单可能已可用）
            self._fill_sample_list()
            if error:
                self._log("⚠ %s" % error)
                # ★ **无数据集** ⇒ 到此为止（不去 set_context / 重算）；
                #   ⚠ 但"有数据集、只是 dataset_output_dir 缺失"**不算无数据集** ——
                #     `set_context(dataset, samples)` 只需要数据集名，故照样往下重算，
                #     否则分组/注释值会一直空着（该情形由分析层在跑 R dump 时如实报错）。
                if not dataset:
                    return
            # ②③④ 上下文 + 分组 + 注释值
            self._recompute_from_samples("进入页面")
        except Exception:
            traceback.print_exc()

    def _fill_sample_list(self):
        """重填样本列表；**尽量保住用户已选样本**（`set_sample_items(None)` = 读当前选择）"""
        try:
            records = self._sample_records()
            if not records:
                self.func.log("⚠ 样本清单为空（数据集未加载？）→ 样本列表保持为空")
                return
            try:
                self.func.set_sample_items(records, self._read_selected_sample_ids())
            except TypeError:
                # 兜底：func 若是老签名（只收 1 个参数）→ 退回不带选择的调用（留痕）
                traceback.print_exc()
                self.func.set_sample_items(records)
            except Exception:
                traceback.print_exc()
                return
            self._log("样本清单: %d 条（保持已选 %d 条）"
                      % (len(records), len(self._read_selected_sample_ids())))
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 运行（照原型 `:194-263` 逐字一致的骨架）
    # ==================================================================
    def run_diff_analysis(self):
        """执行差异分析"""
        try:
            group_col = self._combo_text('diff_group_combo')

            group1_items = self._selected_texts('diff_group1_list')
            group2_items = self._selected_texts('diff_group2_list')

            # —— 三条空选校验（原型 `:202-212`）：**不调分析层** ——
            if not group_col:
                # ★ 空选样本时 `diff_group_combo` 也是空的 → 文案要指向**真正的原因**
                if not self._read_selected_sample_ids():
                    self.func.alert_error("请先选择样本")
                    self.func.log(self.NO_SAMPLE_MSG)
                else:
                    self.func.alert_error("请先选择分组列")
                return

            if len(group1_items) == 0:
                self.func.alert_error("请至少选择1个组别1")
                return

            if len(group2_items) == 0:
                self.func.alert_error("请至少选择1个组别2")
                return

            an = self._require_analysis()
            if an is None:
                return

            method = "mannwhitney"
            min_cells = self.ui.diff_min_cells.value()
            min_expr = self.ui.diff_min_expr.value()
            use_fdr = self.ui.diff_use_fdr.isChecked()

            pval_threshold = self.ui.diff_pval_spin.value()
            logfc_threshold = self.ui.diff_logfc_spin.value()
            pct_threshold = self.ui.diff_pct_spin.value()

            method_display = "Mann-Whitney U检验" if method == "mannwhitney" else "scanpy-mast检验"
            self.func.log("开始差异分析...")
            self.func.log(f"分组: {group_col}")
            self.func.log(f"组别1: {', '.join(group1_items)}")
            self.func.log(f"组别2: {', '.join(group2_items)}")
            self.func.log(f"方法: {method_display}, min_cells={min_cells}")
            self.func.log(f"阈值: pval={pval_threshold}, logfc={logfc_threshold}, pct={pct_threshold}")
            # ★ 规格 §4.2.3：参与/被排除样本**必须**写进日志（不许静默）
            self._log_participating_samples(an, group_col, [])

            # ★ 规格 §6.1：先让分析层装配数据（`prepare()` 幂等），
            #   否则下面的筛选掩码拿不到 `adata.obs.index` ⇒ 首次运行时用户在页面上
            #   勾的「细胞筛选」会被**静默忽略**（第二次运行才生效）—— 真实功能缺口。
            #   `prepare()` 缺失/失败/抛异常一律**只留痕不抛**，后续 `get_filter_mask()`
            #   仍按原行为返回 None（= 不筛），`run_diff_analysis(...)` 参数**逐字不变**。
            prep = getattr(an, 'prepare', None)
            if callable(prep):
                try:
                    if not prep():
                        self.func.log("⚠ 分析层 prepare() 失败 → 本次不做额外细胞筛选"
                                      "（见控制台 traceback）")
                except Exception:
                    traceback.print_exc()
                    self.func.log("⚠ 调 prepare() 异常 → 本次不做额外细胞筛选"
                                  "（见控制台 traceback）")
            else:
                self.func.log("⚠ 分析层无 prepare()（W3 未就位？）→ 本次可能无法应用细胞筛选")

            filter_mask = self.get_filter_mask()

            results_df = an.run_diff_analysis(
                group_col=group_col,
                selected_groups=[group1_items, group2_items],
                method=method,
                min_cells=min_cells,
                min_expr=min_expr,
                use_fdr=use_fdr,
                pval_threshold=pval_threshold,
                logfc_threshold=logfc_threshold,
                pct_threshold=pct_threshold,
                filter_mask=filter_mask
            )

            self.func.update_diff_stats(results_df, group1_items, group2_items)
            self.func.fill_result_tables(
                results_df,
                results_df[results_df['change'] == 'up'],
                results_df[results_df['change'] == 'down']
            )
            self.func.render_volcano_plot(results_df, group_col, [group1_items, group2_items])

            self.func.log(f"找到 {len(results_df)} 个差异基因")

        except ValueError as e:
            self.func.alert_error(str(e))
            self.func.log(f"❌ ValueError: {str(e)}")
        except Exception as e:
            import traceback as _tb
            self.func.alert_failure(f"差异分析失败: {str(e)}")
            self.func.log(f"❌ {str(e)}")
            self.func.log(f"详细错误:\n{_tb.format_exc()}")

    def get_filter_mask(self):
        """获取细胞筛选掩码（支持多选）—— **逐字照抄**原型 `:178-192`

        ★ 掩码长度以 `analysis.adata` 为准；`adata` 未就绪时返回 None（= 不筛），
          并留痕（**绝不静默**、**绝不抛**）。分析层会自己按 `participating_samples`
          装配数据，本掩码只是"用户在页面上额外勾的筛选条件"。
        """
        try:
            an = self.analysis
            adata = getattr(an, 'adata', None) if an is not None else None
            if adata is None:
                self.func.log("⚠ 分析层 adata 未就绪 → 本次不做额外细胞筛选（filter_mask=None）")
                return None

            mask = pd.Series([True] * len(adata), index=adata.obs.index)

            filter1_col = self._combo_text('diff_filter1_col')
            filter1_vals = self._selected_texts('diff_filter1_list')
            if filter1_col and filter1_vals:
                mask = mask & adata.obs[filter1_col].isin(filter1_vals)

            filter2_col = self._combo_text('diff_filter2_col')
            filter2_vals = self._selected_texts('diff_filter2_list')
            if filter2_col and filter2_vals:
                mask = mask & adata.obs[filter2_col].isin(filter2_vals)

            return mask
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("⚠ 生成筛选用掩码失败 → 本次不做额外细胞筛选（见控制台 traceback）")
            except Exception:
                pass
            return None

    # ==================================================================
    # 导出（**全部走 QFileDialog，不自动落盘到 OUTPUT**；规格 §5.3/§7.7）
    # ==================================================================
    def export_results(self):
        """导出差异分析结果到 xlsx（4 个 sheet：统计信息 / 总体差异分析列表 /
        `{组1名}显著上调基因` / `{组1名}显著下调基因`）—— 逐字照抄原型 `:265-357`"""
        if self.analysis is None or getattr(self.analysis, 'diff_gene_df', None) is None \
                or len(getattr(self.analysis, 'diff_gene_df')) == 0:
            self.func.alert_error("请先执行差异分析")
            return

        try:
            import openpyxl
            from openpyxl.utils.dataframe import dataframe_to_rows
        except ImportError:
            self.func.alert_error("请安装 openpyxl 库以导出xlsx文件")
            return

        group1_items = self._selected_texts('diff_group1_list')
        group2_items = self._selected_texts('diff_group2_list')

        group1_name = self._build_group_name(group1_items, "组1")
        group2_name = self._build_group_name(group2_items, "组2")

        filter_info = self._filter_info()
        filter_str = "_筛选=" + ";".join(filter_info) if filter_info else "_筛选=无"
        default_name = f"差异分析_{group1_name}vs{group2_name}{filter_str}.xlsx"

        save_path = self.func.get_save_file_path("导出差异分析结果", default_name, "Excel文件 (*.xlsx)")

        if save_path:
            try:
                wb = openpyxl.Workbook()

                ws1 = wb.active
                ws1.title = "统计信息"
                stats_data = [
                    ["统计项", "数值"],
                    ["比较组1", group1_name],
                    ["比较组2", group2_name],
                    [self.ui.diff_group1_cell_label.text().split(":")[0],
                     self.ui.diff_group1_cell_label.text().split(":")[1].strip()],
                    [self.ui.diff_group2_cell_label.text().split(":")[0],
                     self.ui.diff_group2_cell_label.text().split(":")[1].strip()],
                    [self.ui.diff_up_label.text().split(":")[0],
                     self.ui.diff_up_label.text().split(":")[1].strip()],
                    [self.ui.diff_down_label.text().split(":")[0],
                     self.ui.diff_down_label.text().split(":")[1].strip()],
                    [self.ui.diff_stable_label.text().split(":")[0],
                     self.ui.diff_stable_label.text().split(":")[1].strip()],
                    [self.ui.diff_total_label.text().split(":")[0],
                     self.ui.diff_total_label.text().split(":")[1].strip()],
                    ["筛选条件", ";".join(filter_info) if filter_info else "无"]
                ]
                for row in stats_data:
                    ws1.append(row)

                ws2 = wb.create_sheet(title="总体差异分析列表")
                for r in dataframe_to_rows(self.analysis.diff_gene_df, index=False, header=True):
                    ws2.append(r)

                ws3 = wb.create_sheet(title=f"{group1_name}显著上调基因")
                up_df = self.analysis.diff_gene_df[self.analysis.diff_gene_df['change'] == 'up']
                for r in dataframe_to_rows(up_df, index=False, header=True):
                    ws3.append(r)

                ws4 = wb.create_sheet(title=f"{group1_name}显著下调基因")
                down_df = self.analysis.diff_gene_df[self.analysis.diff_gene_df['change'] == 'down']
                for r in dataframe_to_rows(down_df, index=False, header=True):
                    ws4.append(r)

                wb.save(save_path)
                self.func.alert_success(f"结果已保存到:\n{save_path}")
            except Exception as e:
                traceback.print_exc()
                self.func.alert_failure(f"导出失败: {str(e)}")

    def export_png(self):
        """导出火山图为 PNG（默认名 `火山图_{组1}vs{组2}_筛选={...}.png`）

        ★ 重画走 `analysis.export_png(path)`（写死阈值 + `dpi=300`，规格 §6.2.5），
          **不**复用页内那张图。
        """
        if self.analysis is None or getattr(self.analysis, 'diff_gene_df', None) is None \
                or len(getattr(self.analysis, 'diff_gene_df')) == 0:
            self.func.alert_error("请先执行差异分析")
            return

        group1_items = self._selected_texts('diff_group1_list')
        group2_items = self._selected_texts('diff_group2_list')

        group1_name = self._build_group_name(group1_items, "组1")
        group2_name = self._build_group_name(group2_items, "组2")

        filter_info = self._filter_info()
        filter_str = "_筛选=" + ";".join(filter_info) if filter_info else "_筛选=无"
        default_name = f"火山图_{group1_name}vs{group2_name}{filter_str}.png"
        save_path = self.func.get_save_file_path("导出火山图", default_name, "PNG文件 (*.png)")

        if save_path:
            try:
                self.analysis.export_png(save_path)
                self.func.alert_success(f"火山图已保存到:\n{save_path}")
            except Exception as e:
                traceback.print_exc()
                self.func.alert_failure(f"导出失败: {str(e)}")

    # ==================================================================
    # ★ 「发送到列表文件夹」（契约 `docs/features/gene_list_send_contract.md` §1/§3/§4）
    # ==================================================================
    def send_gene_list_to_folder(self):
        """把**当前差异结果**按子集发送到 `appdata/genelists`（★ v2：子集可选）

        ## 子集（契约 §3 表：空转差异）
          上调 / 下调 / **全部显著**（上+下） / 所有基因（结果表全部）；
          **默认只勾「全部显著」⇒ 与"加子集可选之前"的发送内容逐字一致**。
        ## 取数来源（契约 §3「子集来自当前结果、不重算不重跑」）
          = `self.analysis.diff_gene_df`——**与同页「导出Excel」(`export_results`) 完全同一份
            内存结果**（即 `run_diff_analysis` 刚返回、`update_diff_stats` / `fill_result_tables`
            刚填表的那一份 DataFrame）：
            · 上调 = `change == 'up'`；下调 = `change == 'down'`（与导出的两个 sheet 逐字同口径）；
            · 全部显著 = 上调 ∪ 下调；
            · 所有基因 = 该 df 的全部基因（= 页内「总体列表」`diff_result_table` 的全部行）。
          兜底（df 缺失但页内表已填）：从 `diff_result_table_up` / `diff_result_table_down`
            第 0 列取（**同一份结果的视图**）；此时「所有基因」子集**不造**（宁少勿假，契约 §3 末条）。
        ⛔ 结果为空 / 未运行时：只写 `[WARN]` 日志 + 可读提示，**绝不写空文件**（契约 §3 末条）。
        ⛔ 落盘**只**走共享工具 `ask_and_send`，本页**不自己 `to_excel`**（契约 §1）。
        """
        try:
            groups, flat = self._build_send_groups()
            if not groups:
                msg = "没有可发送的基因：请先点「▶ 执行差异分析」，并确认当前阈值下有显著上调/下调基因"
                self.func.log("[WARN] %s" % msg)
                self.func.alert_error(msg)
                return None
            labels = ", ".join("%s(%d)" % (l, len(g)) for l, g, _d in groups)
            self.func.log("[INFO] 可发送子集: %s（共 %d 个去重基因）" % (labels, len(flat)))
            if len(groups) > 1:
                r = ask_and_send(self.parent, groups=groups, multi=True, prefix="差异基因")
            else:
                # 只有 1 个子集（如 df 缺失、仅表格兜底）⇒ 旧口径，不弹选择区（契约 §3 末条）
                r = ask_and_send(self.parent, flat, groups=groups, prefix="差异基因")
            self._report_gene_list_send(r, flat)
            return r
        except Exception as e:            # 槽内**绝不抛**（PyQt5 对未捕获异常会 qFatal）
            traceback.print_exc()
            self.func.log("[WARN] 发送到列表文件夹失败: %s" % e)
            return None

    def _build_send_groups(self):
        """构造发送子集 `[(标签, 基因, 默认勾选), ...]`；同时返回一个扁平兜底列表

        默认勾选（契约 §3）：**仅「全部显著」= True**，其余 False。
        返回 `([], [])` 表示当前结果为空（调用方给提示，不落盘）。
        """
        df = getattr(self.analysis, 'diff_gene_df', None) if self.analysis is not None else None
        up, down, allg, sig = [], [], [], []
        if df is not None and len(df) > 0:
            try:
                gene_col = 'gene' if 'gene' in getattr(df, 'columns', []) else df.columns[0]
                allg = [str(g).strip() for g in df[gene_col].tolist()]
                allg = [g for g in allg if g and g.lower() not in ('nan', 'none')]
                if 'change' in getattr(df, 'columns', []):
                    up = [str(g).strip() for g in df[df['change'] == 'up'][gene_col].tolist()]
                    down = [str(g).strip() for g in df[df['change'] == 'down'][gene_col].tolist()]
                    up = [g for g in up if g and g.lower() not in ('nan', 'none')]
                    down = [g for g in down if g and g.lower() not in ('nan', 'none')]
                    up, down = self._dedup(up), self._dedup(down)   # 各自去重保序
                else:
                    up = list(allg)      # 无 change 列（异常数据层）⇒ 全部按显著处理（与旧口径同）
                sig = self._dedup(up + down)
            except Exception:
                traceback.print_exc()
                up, down, allg, sig = [], [], [], []
        if not up and not down:
            # 兜底：页内两张显著表（同一份结果的视图，**不重算**）
            up = self._dedup(self._genes_from_table('diff_result_table_up'))
            down = self._dedup(self._genes_from_table('diff_result_table_down'))
            sig = self._dedup(up + down)
        groups = []
        if up:
            groups.append(("上调", up, False))
        if down:
            groups.append(("下调", down, False))
        if sig:
            groups.append(("全部显著", sig, True))       # ★ 默认勾选 = 复现旧行为
        if allg:
            groups.append(("所有基因", self._dedup(allg), False))
        # 兜底扁平 = 所有子集的并集（仅在"只有 1 个子集"的旧口径调用里用到）
        flat = self._dedup([g for _l, gs, _d in groups for g in gs])
        return groups, flat

    def _dedup(self, genes):
        """保序去重 + 丢空值（与共享工具 `_clean_genes` 同口径，便于两处对齐）

        ★ 注意：这是**实例方法**（不是 staticmethod）—— 早前一版误写成 staticmethod
          却用 `self._dedup(...)` 调用，`self` 占掉了 `genes` 形参，导致所有去重结果
          恒为空。教训：`self.x(...)` 与 `@staticmethod` 不可混用。
        """
        seen, out = set(), []
        for g in (genes or []):
            s = str(g).strip()
            if not s or s.lower() in ('nan', 'none', 'na'):
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    def _collect_significant_genes(self):
        """取当前结果里的显著基因（上调+下调合并、保序去重）；无结果 → 空列表

        ★ 保留本方法：既是"默认勾选复现旧行为"的**对照基准**（自测用它逐字比对），
          也是 `_build_send_groups()` 里「全部显著」子集的同一口径。
        """
        _groups, flat = self._build_send_groups()
        for label, genes, default in _groups:
            if label == "全部显著" and default:
                return list(genes)
        return list(flat)

    def _genes_from_table(self, attr_name):
        """从结果表第 0 列取基因名（跳过表头行 = 与表头文本相同的首行）"""
        try:
            table = getattr(self.ui, attr_name, None)
            if table is None or not hasattr(table, 'rowCount'):
                return []
            header = ''
            try:
                item = table.horizontalHeaderItem(0)
                header = str(item.text()).strip() if item is not None else ''
            except Exception:
                header = ''
            genes = []
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item is None:
                    continue
                txt = str(item.text()).strip()
                if not txt or txt == header:
                    continue
                genes.append(txt)
            return genes
        except Exception:
            traceback.print_exc()
            return []

    def _report_gene_list_send(self, r, genes):
        """按 `r["ok"]` 用页面既有日志接口打 `[INFO]`/`[WARN]`（契约 §4.4）"""
        try:
            r = r or {}
            if r.get('cancelled'):
                self.func.log("[INFO] 已取消发送")
                return
            if r.get('ok'):
                self.func.log("[INFO] %s" % r.get('message', '已发送'))
                self.func.alert_success(r.get('message', '已发送'))
            else:
                msg = r.get('message') or "发送失败"
                self.func.log("[WARN] %s" % msg)
                self.func.alert_error(msg)
        except Exception:
            traceback.print_exc()

    def _build_group_name(self, categories, default_name):
        """组名折叠规则 —— **逐字照抄**原型 `ui_bind_diff.py:281-292 / :368-379`

        1 个直接用；多个用 `"+"` 连接；仍 >28 字则各取前 3 字再连；再 >28 字则各取前 1 字。
        """
        if not categories:
            return default_name
        if len(categories) == 1:
            return categories[0]
        full_name = "+".join(categories)
        if len(full_name) <= 28:
            return full_name
        short_name_3 = "+".join([cat[:3] for cat in categories])
        if len(short_name_3) <= 28:
            return short_name_3
        return "+".join([cat[:1] for cat in categories])

    def _filter_info(self):
        """筛选条件文本（照原型 `:297-308`：`列=值1,值2`，多条用 `;` 连接）"""
        info = []
        try:
            filter1_col = self._combo_text('diff_filter1_col')
            filter1_vals = self._selected_texts('diff_filter1_list')
            if filter1_col and filter1_vals:
                info.append(f"{filter1_col}={','.join(filter1_vals)}")

            filter2_col = self._combo_text('diff_filter2_col')
            filter2_vals = self._selected_texts('diff_filter2_list')
            if filter2_col and filter2_vals:
                info.append(f"{filter2_col}={','.join(filter2_vals)}")
        except Exception:
            traceback.print_exc()
        return info

    # ==================================================================
    # 内部小工具（**全部 getattr 守卫**：缺控件只留痕、不抛）
    # ==================================================================
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
                return []
            return [str(item.text()) for item in w.selectedItems()]
        except Exception:
            traceback.print_exc()
            return []

    def _safe_set_combo_items(self, name, items):
        """经 `func.set_combo_items` 设下拉内容（保住当前选中；控件缺失只留痕）"""
        try:
            w = getattr(self.ui, name, None)
            if w is None:
                self.func.log("⚠ 布局缺少控件 %s → 该下拉未重算（需要 W1 提供）" % name)
                return
            self.func.set_combo_items(w, items)
        except Exception:
            traceback.print_exc()

    def _log(self, msg):
        """写日志（`func.log` 缺失时退回 print，**绝不静默**）"""
        try:
            if hasattr(self.func, 'log'):
                self.func.log(msg)
            else:
                print("[SpatialDiffBind] %s" % msg)
        except Exception:
            traceback.print_exc()

    def _log_lines(self, lines):
        """批量写日志（空列表直接返回）"""
        try:
            for line in (lines or []):
                self._log(line)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 音量（照原型 `:406-413`）
    # ==================================================================
    def set_volume(self, value):
        """设置音量"""
        try:
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_music_player'):
                mod_instance.global_music_player.set_volume(value / 100.0)

            if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
                self.parent._sync_all_volume_sliders_from_subinterface(value)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 兼容接口（原型有，保留签名；本页数据来自 `set_context`，不再走 adata 注入）
    # ==================================================================
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


__all__ = ['SpatialDiffBind']
