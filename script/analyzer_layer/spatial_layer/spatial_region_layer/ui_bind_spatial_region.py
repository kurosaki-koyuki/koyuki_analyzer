# -*- coding: utf-8 -*-
"""M4「绘制区域」子页面 —— 接线（契约 `docs/features/spatial_m2m3_contract.md` §13）

职责（§13.5 归 W2）：
  · 进页面：载 `regions.json` → 读当前样本的 `spots.csv` → 灌画布；
  · 画布交互：`region_finished` 建区域、`region_selected` 把样式回填右侧控件；
  · 右侧控件改动 → `canvas.set_active_style(...)` 实时预览；
  · 撤销顶点 / 删选中区域 / 清空本样本（**要确认框**）；
  · 确认：算标签 → 计数 → 导出 labels CSV → **调 W3 的 R 重绘** → 预览 → 落盘 → **日志报数**。

## 分层纪律
  · **不建控件**（控件由 W1 的 `ui_layout_spatial_region.py` + `region_canvas.py` 提供）；
  · **不重复实现点判定/标签计算**（全在 `spatial_region_analysis`，单一真相源）；
  · 本页**没有 func 层**（§13.5 归属表里没有 `ui_func_spatial_region.py`），
    所以"往已有控件里填内容"（样本列表条目、名字下拉建议）由本文件做，
    但**绝不 new 任何控件**。

## 子进程纪律（沿用既有）
  全 ASCII 路径断言、`stdin=DEVNULL`、超时、绝对路径 Rscript —— 都在
  `spatial_region_analysis.render_sample_regions()` 里统一做（与 `GEA` 同一套）。

## 绝不碰图集
  产物只落 `OUTPUT/<ds>/09_RegionOverride/`；不写 `_figure_manifest.csv`。
"""

import os
import time
import traceback

from script.utils_layer.import_config import *
# ★ 显式 import：不依赖 import_config 的导出清单（本会话已第 4 次强调该踩坑面）
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem

from script.analyzer_layer.spatial_layer.spatial_review_layer import spatial_review_analysis as RA
from script.analyzer_layer.spatial_layer.spatial_region_layer import spatial_region_analysis as SREG
from script.analyzer_layer.spatial_layer.spatial_expression_layer import spatial_gene_expression_analysis as GEA
from script.utils_layer.page_intersect import page_intersect

# 画布/控件的接口名（**W1 交付前不存在，一律 hasattr 守卫 + 留痕**）
CANVAS_SET_SPOTS = "set_spots"
CANVAS_SET_REGIONS = "set_regions"
CANVAS_SET_ACTIVE_STYLE = "set_active_style"
CANVAS_UNDO_POINT = "undo_last_point"
# ★ Phase 3①：`编辑边`/`编辑标签` 按钮 → 画布编辑模式（W1 的真接口名）
CANVAS_SET_EDIT_MODE = "set_edit_mode"
SIGNAL_REGION_FINISHED = "region_finished"
SIGNAL_REGION_SELECTED = "region_selected"
# ★★ §13.9 2c / §15.4 交互回写的**信号契约**（W1 发、W2 收）—— **以 W1 的真名为准**：
#      `region_edges_changed = pyqtSignal(int)`                # 区域索引（边显隐变了）
#      `region_label_moved   = pyqtSignal(int, float, float)`  # 区域索引, x, y（数据坐标）
#    ★ 我第一版按 `edge_toggled` / `label_moved` 写 ⇒ **两个名字都不对、一个也接不上**
#      （协调者实测指出）。现已改成上面两个真名。
#    ★ 核心约定：**画布只改自己的内部状态并发信号，绝不直接写 bind 的 `regions_data`**；
#      我收到信号后从 `canvas.get_regions()` **整份同步**（画布是几何的唯一真相源），
#      **不解析载荷去改字段** —— 所以载荷形状以后变了也不影响同步。
SIGNAL_REGION_EDGES_CHANGED = "region_edges_changed"
SIGNAL_REGION_LABEL_MOVED = "region_label_moved"
# ★★ 2026-09-23「选择模式」（`_d_spec_select_mode.md` §3.3/§5）—— W1 新增的两个画布信号：
#      regions_selected        = pyqtSignal(list)   # 选中区域索引（**顺序 = 命中顺序**；空 = 清空）
#      region_geometry_changed = pyqtSignal(int)    # 区域索引（顶点拖动**松开且坐标确实变了**）
#    ★ 本文件（W2）只负责：多选 ⇒ 禁用命名控件；顶点拖动 ⇒ 走既有链路落盘一次。
#    ★ W1 交付前这两个信号**不存在** ⇒ 一律 `getattr(canvas, name, None)` 存在性安全接线 +
#      留痕跳过，**绝不 AttributeError**（也绝不去写画布的私有字段）。
SIGNAL_REGIONS_SELECTED = "regions_selected"
SIGNAL_REGION_GEOMETRY_CHANGED = "region_geometry_changed"
#    `region_name_changed = pyqtSignal(int, str)`             # 区域索引, 新名字
#    ★ 改名的落盘**必须**由这条信号驱动（W1 在 `ui_layout_spatial_region.py` 明文：
#      "落盘由 bind 接 `canvas.region_name_changed` 完成"）。我第一版只接了输入框的
#      `editingFinished`，靠"W1 先 commit → 我再读模型"的**接线顺序**侥幸写对；
#      一旦顺序变了（或 W1 改成只走画布接口）就静默不落盘。现在补上这条线。
#    ★★ v2（`_d_spec_region_naming_v2.md` §3/§4）：自由文本改名入口**已整体删除**
#      ⇒ 这条信号在界面上**不会再发**；两级命名（分组 + 注释）的写盘走
#      `_commit_anno()` 一处。接线保留只为"画布侧将来另开改名入口"时不静默丢盘。
SIGNAL_REGION_NAME_CHANGED = "region_name_changed"
# 编辑模式名（§15.4 原为 {"draw","edges","label"}；2026-09 用户改为**两层范围层**）
#   ⛔ `"edges"`（"编辑边"）已**彻底退休**：`region_canvas.EDIT_MODES` 里没有它、
#      布局里也没有 `btn_region_edit_edges`。用户纠正：那个按钮真正要的是「可见区域」。
#      相关信号/抑制/miss 提示已随之上轮清掉；这里连常量也不再保留 ——
#      留一个"过渡期常量"只会让后人以为它是活路径。
EDIT_MODE_DRAW = "draw"
EDIT_MODE_LABEL = "label"
# ★ 可见区域（可见范围层）：**v9.3 起它自己也会出图**（带名字 —— 用户裁定它就是一个
#   可画的标注单元），**同时**被它罩住的区域其边界在画布上画虚线、普通区域要被它罩住才入选
#   ⇒ 「自己出图」与「当罩子」**两条并存**，别只记住后一条（沿革见 `_is_anno_blocked_region`）
EDIT_MODE_VISIBLE = "visible"
# ★ 隐形区域（隐形范围层）：**自己不出图**（只是『罩子』），决定这些虚线**哪些能出现在成图里**
EDIT_MODE_MASK = "mask"
# ★★ 2026-09-23 新增「选择模式」（规格 `_d_spec_select_mode.md` §2，字面量与属性名**冻结**）：
#   · 只用于**选中区域以便命名**（可见 + 隐形范围层都能被选中）；
#   · 点**独有的边/锚点** ⇒ 选中该区域（独有锚点还能直接拖动改形状）；
#   · 点**共享边/共享锚点** ⇒ 同时选中多个区域，**但不启动编辑**（画布负责）；
#   · 按钮名由模式名推导 ⇒ `btn_region_edit_select`（布局由 W1 建，本文件不写死按钮名）。
EDIT_MODE_SELECT = "select"

# 样本列表每项的冻结文案（契约 §14.2）
SAMPLE_ITEM_PAINTED = "✅ 已画 %d 区  %s"
SAMPLE_ITEM_UNPAINTED = "⚠ 未画  %s"

# ======================================================================
# ★★ v2 两级命名（契约 `_d_spec_region_naming_v2.md` §4）：冻结文案
# ----------------------------------------------------------------------
#   · `region_name_input`（**冻结属性名**）= 「分组」下拉框，`setEditable(False)`
#     ⇒ 本文件**不再读它的自由文本**，只读 `currentText()` 当分组名；
#   · 「自定义」在分组下拉里**永远是最后一项**（用户原话：下拉框点开的最底下还有
#     一个『自定义』）；
#   · 选「自定义」⇒ 写进区域的 `anno_group` 是**字面量** `group_graphed`
#     （真相源是 W3 的 `SREG.GROUP_GRAPHED`，这里只留一个字面量兜底）。
ANNO_GROUP_CELL_TYPE = "cell_type"
ANNO_GROUP_CLUSTER = "cluster"
ANNO_GROUP_CUSTOM = "自定义"                    # 分组下拉的"进入自定义"项（永远最后）
ANNO_GROUP_GRAPHED_FALLBACK = "group_graphed"   # `SREG.GROUP_GRAPHED` 取不到时的字面量
ANNO_LABEL_CUSTOM = "自定义"                    # 注释选择框的"新建注释"项（永远最后）
# ★★ §3.3/§3.4：**多选**或**选中范围层**时要一并禁用的四个命名控件（属性名冻结，只读不改名）
#   · `region_name_input`    = 分组下拉（**不可编辑**，v8 冻结契约，本轮仍不恢复自由文本）；
#   · `region_anno_list`     = 注释选择框；
#   · `region_anno_input`    = 自定义注释输入框；
#   · `btn_region_anno_ok`   = 自定义注释「确定」按钮。
ANNO_CONTROL_NAMES = ("region_name_input", "region_anno_list",
                      "region_anno_input", "btn_region_anno_ok")

# ★ 样式落盘的**尾沿合并窗口**（毫秒）：拖滑块/连续输入时把同一区域的连续改动
#   合并成一次写盘。方案 = "前沿立即 + 尾沿合并"，理由见 `_push_active_style` docstring。
#   ⚠ 只影响**落盘**；画布重绘永远是立即的（用户要"立刻看见"）。
STYLE_PERSIST_DEBOUNCE_MS = 400


class _RegionDumpWorker(QThread):
    """在**后台线程**里跑 `SREG.dump_spots`（subprocess + Rscript）

    ★ 仿 `ui_bind_spatial_initial._GeneExpressionWorker`（那套已被协调者独立验过）。
    ★ 为什么必须要线程：导出坐标表约 **6 s**，而这是**进页面时自动做**的 ——
      放主线程就是每次进页面卡 6 秒（用户会以为程序死了）。
    ★ 为什么可以放线程：`dump_spots` 走 `subprocess` + `Rscript`，**完全不碰 rpy2**。
    ★★ 线程里**绝不碰任何 Qt 控件**：只存纯数据、只 emit 信号。
    """

    done_ok = pyqtSignal(object)     # result dict
    done_fail = pyqtSignal(str)      # 失败原因

    def __init__(self, dataset, rds_path=None, timeout=600, parent=None):
        super(_RegionDumpWorker, self).__init__(parent)
        self._dataset = str(dataset or "")
        self._rds_path = rds_path
        self._timeout = timeout

    def run(self):
        try:
            ok, result, err = SREG.dump_spots(self._dataset, self._rds_path,
                                              timeout=self._timeout)
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self.done_fail.emit("后台线程异常：%s: %s" % (type(e).__name__, e))
            return
        if ok:
            self.done_ok.emit(result)
        else:
            self.done_fail.emit(err or "未知原因")


class SpatialRegionBind:
    """绘制区域页绑定类 - 只做接线，不做点判定、不建控件"""

    def __init__(self, main_window, ui_instance):
        self.parent = main_window
        self.ui = ui_instance
        self.analysis = None

        self.dataset = None
        self.samples = []                 # 当前数据集的样本清单
        self.regions_data = {}            # `load_regions()` 的返回（整份）
        self.current_sample = None
        self.spots = []                   # 当前样本的 spot 行（dict）
        self.spots_error = ""             # 读不到坐标表时的原因（如实显示）
        self.active_region_index = -1     # 右侧属性对应哪个区域（-1 = 新画一个）
        self._canvas_ready = False
        # ★ Phase 3①：编辑模式互斥收口时的**重入闸**（`set_edit_mode_buttons` 会
        #   反过来 `setChecked()` → 又发 `toggled` → 再进 handler；用标志挡掉内层）
        self._edit_mode_syncing = False
        # ★ 样式落盘去抖：尾沿定时器 + "已改画布但还没落盘"标志（懒建定时器）
        self._style_timer = None
        self._style_pending = False        # 有"已改画布、未落盘"的改动
        self._style_burst = False          # 是否正处于一次连续改动（突发）中
        self._style_pending_idx = -1
        self._last_style_persist = 0.0     # 仅供日志/排障（不参与判定）
        self._style_hint_shown = False     # "未选中区域"提示只在每段未选中期间打一次
        # ★ 区域列表重建守卫：`clear()` 会发 `currentRowChanged(-1)`，重建期间必须忽略
        #   （否则每跑一次 `_refresh_region_list` 就把用户的选中清掉）
        self._region_list_rebuilding = False
        # ---- ★★ v2 两级命名（分组 + 注释）的编排状态 ----
        # `_anno_filling`：**程序化回填**控件期间必须为 True —— `setCurrentIndex`/
        #   `clear()`/`setCurrentRow` 都会发信号，不挡住就会"回填一次 ⇒ 写一次盘"
        #   （还会把旧式区域的 `name` 顺手改掉，正好违反 §4.3 末条）。
        self._anno_filling = False
        # `_anno_list_rebuilding`：**注释选择框正在重建**（W1 的 `show_region_name` 会
        #   `clear()` items / 我自己重填）⇒ `clear()` 发出的空选择信号必须被跳过，
        #   且要说清"为什么跳过"（否则会被误读成"点了没反应"）。
        self._anno_list_rebuilding = False
        # `_anno_pending_*`：**未选中区域**时改控件 ⇒ 只记住"待用值"（§4.3 第 2 条），
        #   不报错、不建区域；下次选中区域/画新区域时它就是默认注释。
        self._anno_pending_group = ""
        self._anno_pending_label = ""
        # "未选中区域"提示每段只打一次（与 `_style_hint_shown` 同一理由：防刷屏）
        self._anno_hint_shown = False
        self._pending_logged = ""          # 上一次已留痕的待用值（同值不重复刷日志）
        self._anno_input_hint_shown = False
        # ---- ★★ 2026-09-23「选择模式」（`_d_spec_select_mode.md` §3.3/§3.4）----
        # `_multi_selected_indices`：画布 `regions_selected(list)` 的**最近一次选中快照**
        #   （顺序 = 命中顺序；空 = 清空）。命名控件的可用态 = 它 + 范围层判据（见
        #   `_apply_anno_enablement`）—— 只在 `regions_selected` 与区域列表行选中处更新。
        self._multi_selected_indices = []
        # `_anno_enable_state`：上一次"命名控件可用态"的**指纹**（只在变化时写日志）。
        #   这些路径（刷新/回填/`_persist` 之后）会被高频重入，不挡住会把日志刷满。
        self._anno_enable_state = None
        # ---- ★★ 2026-09-24 用户需求：**可见区域的默认区域颜色 = 白色**（只影响新画的）----
        # `_palette_programmatic`：**程序化切调色板期间**必须为 True。
        #   ★ 依据（协调者已核实）：`StyledColorPalette.set_color()` 会 **emit
        #     `color_changed`**（`script/utils_layer/gui_styles.py:3870-3877`），
        #     而 `color_changed` 接的是 `_push_active_style` —— 它在**有选中区域**时
        #     会写回该区域**并落盘**。不做抑制 ⇒ 用户一切到「可见区域」就把当前
        #     选中区域刷成白色（典型 D 系列事故：程序化回填写盘）。
        #   本标志为真时 `_push_active_style` **只做实时预览那一步**然后 return
        #   （见那里的抑制分支），**绝不写回区域、绝不落盘、绝不 emit 几何变化信号**。
        self._palette_programmatic = False
        # `_last_edit_mode`：**切换前**的编辑模式（调色板跟随模式要用）。
        #   初值 = `draw`；`init_bindings()` 末尾会用画布 `edit_mode()` 对齐一次
        #   （取不到就保持 `draw`，并留痕）。
        self._last_edit_mode = EDIT_MODE_DRAW
        # `_pre_visible_color`：进入可见区域模式**之前**的调色板色（离开时还原用）；
        #   None = 没有一次"进入"在生效中。**用户自己在可见区域模式下改过色 ⇒ 不还原**。
        self._pre_visible_color = None
        self._entered_key = None          # on_page_entered 幂等键
        self._warned_api = set()          # 已告警过的缺失接口（避免刷屏）
        # ---- §14.2：坐标表自动生成 ----
        self._dump_worker = None          # 当前导出线程（None = 没在跑）
        self._dump_error = ""             # 上次自动导出的失败原因（用户可据此重试）

        self.init_bindings()
        self.refresh_all(reason="构造")

    # ==================================================================
    # 小工具（控件缺失一律留痕，绝不静默）
    # ==================================================================
    def _log(self, msg):
        try:
            widget = getattr(self.ui, 'region_log_text', None)
            if widget is not None and hasattr(widget, 'append'):
                widget.append(str(msg))
                bar = widget.verticalScrollBar()
                if bar is not None:
                    bar.setValue(bar.maximum())
                return
        except Exception:
            traceback.print_exc()
        print("[SpatialRegion] %s" % msg)

    def _warn_once(self, key, msg):
        """同一类缺失只告警一次（否则每次重画都刷屏，日志反而没人看）"""
        if key in self._warned_api:
            return
        self._warned_api.add(key)
        self._log("⚠ %s" % msg)

    def _ctl(self, name):
        return getattr(self.ui, name, None)

    @staticmethod
    def _read_text(widget):
        """读"文本类"控件的当前值（QLineEdit / QTextEdit / QComboBox 都兼容）"""
        if widget is None:
            return ""
        for attr in ('toPlainText', 'text', 'currentText'):
            try:
                fn = getattr(widget, attr, None)
                if callable(fn):
                    v = fn()
                    if v is not None:
                        return str(v)
            except Exception:
                continue
        return ""

    @staticmethod
    def _read_number(widget, default):
        """读"数字类"控件的当前值

        ★ **`value()` 必须在候选最前**，因为 W1 的 `StyledNumberInput`（`gui_styles.py:802`）
          对外就是 `value()`，它返回 **int**（内部字段 `current_value`），
          **不是** `text()` 那种字符串 —— 所以不能靠"读文本再转数"当主路径。
          `setValue(value)`（`:806`）是它的写入口，`_write_number` 已经优先用它。
        ★ 文本兜底留给普通 `QLineEdit`（万一控件被换掉）。
        """
        if widget is None:
            return default
        try:
            fn = getattr(widget, 'value', None)
            if callable(fn):
                return float(fn())            # int / float 都收，统一成 float
        except Exception:
            pass
        try:
            t = SpatialRegionBind._read_text(widget).strip()
            return float(t) if t else default
        except Exception:
            return default

    @staticmethod
    def _read_palette_color(widget, default):
        """读调色板控件当前颜色

        ★ **真名是 `get_color()`**（W1 确认 + 协调者实测）。
          候选表里 `get_color` **放最前**；后面几个是"万一 W1 改了名"的兜底。
          全都没命中 → 返回默认色（并且调用方会留痕），绝不假装读到了。
        """
        if widget is None:
            return default
        for attr in ('get_color', 'current_color', 'get_current_color', 'selected_color',
                     'currentColor', 'color'):
            try:
                fn = getattr(widget, attr, None)
                if callable(fn):
                    v = fn()
                    if v:
                        return str(v)
            except Exception:
                continue
        try:
            t = SpatialRegionBind._read_text(widget)
            if t.strip().startswith("#") or t.strip().startswith("rgb"):
                return t.strip()
        except Exception:
            pass
        return default

    @staticmethod
    def _write_palette_color(widget, hex_color):
        """把颜色回填到调色板控件（真名 `set_color(hex)`，其余为兜底）"""
        if widget is None:
            return False
        for attr in ('set_color', 'set_current_color', 'set_current',
                     'setCurrentColor', 'setColor'):
            try:
                fn = getattr(widget, attr, None)
                if callable(fn):
                    fn(str(hex_color))
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _write_text(widget, text):
        if widget is None:
            return False
        for attr in ('setPlainText', 'setText', 'setEditText', 'setCurrentText'):
            try:
                fn = getattr(widget, attr, None)
                if callable(fn):
                    fn(str(text))
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _write_number(widget, value):
        if widget is None:
            return False
        try:
            fn = getattr(widget, 'setValue', None)
            if callable(fn):
                fn(value)
                return True
        except Exception:
            pass
        return SpatialRegionBind._write_text(widget, value)

    def _canvas(self):
        return self._ctl('region_canvas')

    def _call_canvas(self, api_name, *args):
        """调画布接口；不存在/调用失败 → **写进 `region_log_text`** 并返回 False（**不抛**）

        ★★ 第 5 轮事故（协调者真鼠标模拟发现，整页不可用的阻断性缺陷）：
          `RegionCanvasWidget.set_spots()` 的真签名是 **`(xs, ys, labels)` 三个参数**，
          而我只传了一个 `self.spots` ⇒ `TypeError`。
          `_call_canvas` **兜住了异常**（所以没崩），但**只 `print` 到控制台** ——
          用户在界面上一个提示都看不到，只看到"画布空的"。
          ⇒ 这就是"错误只在控制台"能把一个阻断性缺陷藏这么久的原因。
        ⇒ 现在：捕获后**必须再往 `region_log_text` 写一行**，并带上
          **接口名 + 实参个数 + 异常类型与原文**（缺参数会明说缺哪几个）。
        """
        c = self._canvas()
        if c is None:
            self._warn_once("canvas_missing",
                            "布局未提供 region_canvas → 画布相关操作无法进行")
            return False
        fn = getattr(c, api_name, None)
        if not callable(fn):
            self._warn_once("canvas_api_%s" % api_name,
                            "RegionCanvasWidget 未提供 %s() → 该功能不可用"
                            "（需要 W1 补这个接口）" % api_name)
            return False
        try:
            fn(*args)
            return True
        except Exception as e:
            traceback.print_exc()
            # ★ 界面上也要看得见（不只控制台）。不节流：这类错要么不出，要么每次都要修。
            self._log("⚠ 画布接口调用失败：%s（传了 %d 个实参）→ %s: %s；"
                      "该功能不会生效（画布可能因此没有任何点）"
                      % (api_name, len(args), type(e).__name__, e))
            return False

    # ==================================================================
    # 绑定
    # ==================================================================
    def init_bindings(self):
        self.bind_nav()
        self.bind_sample_list()
        self.bind_canvas_signals()
        self.bind_edit_mode_buttons()      # ★ Phase 3①（原缺失 → 编辑边/标签按钮是死的）
        self.bind_style_controls()
        self.bind_name_edit()
        self.bind_label_frame_checkbox()   # ★ Phase 4⑤（原缺失 → chk_label_frame 没人读）
        self.bind_action_buttons()
        self.bind_region_list()            # ★ 列表行选择（此前全仓库无人接 → 点选/删除无反应）
        self.fill_signature_suggestions()
        # ★ 调色板跟随模式：先对齐"切换前的模式"初值（画布 `edit_mode()`，取不到 = draw）
        self._sync_last_edit_mode_from_canvas()

    def bind_nav(self):
        try:
            # 本页返回按钮的真名就是 `nav_btn_back`（协调者实测确认，已在布局里）
            btn = self._ctl('nav_btn_back')
            if btn is not None and hasattr(btn, 'clicked'):
                btn.clicked.connect(self._on_back_clicked)
            else:
                self._warn_once("no_nav_back", "布局未提供 nav_btn_back → 返回按钮未绑定")
        except Exception:
            traceback.print_exc()

    def bind_sample_list(self):
        """`region_sample_list`：切换样本 → 重新读坐标 + 重画"""
        try:
            lst = self._ctl('region_sample_list')
            if lst is None:
                self._warn_once("no_sample_list", "布局未提供 region_sample_list → 无法切换样本")
                return
            if hasattr(lst, 'currentRowChanged'):
                lst.currentRowChanged.connect(self._on_sample_row_changed)
            elif hasattr(lst, 'itemSelectionChanged'):
                lst.itemSelectionChanged.connect(self._on_sample_selection_changed)
            else:
                self._warn_once("no_sample_signal",
                                "region_sample_list 没有 currentRowChanged/itemSelectionChanged")
        except Exception:
            traceback.print_exc()

    def bind_canvas_signals(self):
        """画布信号：`region_finished`（画完一个多边形）/ `region_selected`（选中区域）"""
        try:
            c = self._canvas()
            if c is None:
                self._warn_once("canvas_missing_sig",
                                "布局未提供 region_canvas → 画布信号未接")
                return
            sig = getattr(c, SIGNAL_REGION_FINISHED, None)
            if sig is not None and hasattr(sig, 'connect'):
                sig.connect(self._on_region_finished)
            else:
                self._warn_once("no_sig_finished",
                                "region_canvas 未提供 %s 信号" % SIGNAL_REGION_FINISHED)
            sig = getattr(c, SIGNAL_REGION_SELECTED, None)
            if sig is not None and hasattr(sig, 'connect'):
                sig.connect(self._on_region_selected)
            else:
                self._warn_once("no_sig_selected",
                                "region_canvas 未提供 %s 信号" % SIGNAL_REGION_SELECTED)
            # ★ §15.4 的两个新信号（W1 交付前不存在 → 留痕，功能暂不可用）
            for name, handler in ((SIGNAL_REGION_EDGES_CHANGED, self._on_region_edges_changed),
                                  (SIGNAL_REGION_LABEL_MOVED, self._on_region_label_moved),
                                  (SIGNAL_REGION_NAME_CHANGED, self._on_region_name_changed)):
                s2 = getattr(c, name, None)
                if s2 is not None and hasattr(s2, 'connect'):
                    s2.connect(handler)
                else:
                    self._warn_once("no_sig_%s" % name,
                                    "region_canvas 未提供 %s 信号 → 该编辑模式改不回模型"
                                    "（需要 W1 补这个信号）" % name)
            # ★★ 2026-09-23「选择模式」（`_d_spec_select_mode.md` §3.3/§5）：多选 + 顶点拖动。
            #    `regions_selected(list)`   ⇒ §3.3 多选禁用命名控件 / 单选走既有链路；
            #    `region_geometry_changed(int)` ⇒ §5 顶点拖动"整份读回画布并落盘一次"。
            #    ★ 两个信号 W1 交付前**不存在** ⇒ 存在性安全接线：不存在只留一行提示并跳过
            #      （**绝不 AttributeError**，也绝不写画布私有字段）。
            for name, handler, why in (
                    (SIGNAL_REGIONS_SELECTED, self._on_regions_selected,
                     "画布多选不会同步到本页（命名控件不会随多选禁用）；需要 W1 补这个信号"),
                    (SIGNAL_REGION_GEOMETRY_CHANGED, self._on_region_geometry_changed,
                     "拖动顶点改出来的形状不会落盘；需要 W1 补这个信号")):
                s3 = getattr(c, name, None)
                if s3 is not None and hasattr(s3, 'connect'):
                    s3.connect(handler)
                else:
                    self._warn_once("no_sig_%s" % name,
                                    "region_canvas 未提供 %s 信号 → %s" % (name, why))
            self._canvas_ready = True
        except Exception:
            traceback.print_exc()

    def _sync_from_canvas(self, reason=""):
        """★ 从画布**整份**同步区域（含 §15.3 的 `edge_override`/`label_pos`/`corner_radius_px`）

        为什么不解析信号载荷去改某一个字段：**画布已经是几何+样式的唯一真相源**，
        整份读回最稳、也最不会漏字段（信号载荷的语义以后变了也不影响）。
        同步后照常 `_persist`（落盘 + 对齐幂等键 + 刷新"已画/未画"文案）。
        """
        try:
            regs = self._read_canvas_regions()
            if regs is None:
                self._warn_once("sync_no_get_regions",
                                "画布未提供 get_regions() → 编辑结果无法同步到模型")
                return False
            SREG.set_sample_regions(self.regions_data, self.current_sample, regs)
            self._persist(reason=reason or "画布编辑同步")
            self._refresh_region_list()
            return True
        except Exception:
            traceback.print_exc()
            return False

    def _on_region_edges_changed(self, *args):
        """`edges` 模式改了某区域的边显隐 → 从画布整份同步（§15.3 `edge_override`）

        ★ 载荷只有"区域索引"，**没有边的明细**（`pyqtSignal(int)`），所以没法用载荷兜底；
          真正的数据只能来自画布字典里的 `edge_override`。
          ⚠ 因此这里加了一条**诊断**：同步回来发现该区域 `edge_override` 是空的，
          就说明**画布没把用户点的边写进区域字典**（W1 待修）—— 明确写出来，
          免得"点了边但重启后全没了"变成一个没人知道的静默丢数据。

        ## ★★ 为什么必须把"具体改了哪条边"打出来（用户体验事故）
          用户报"编辑边点选没有反应"——**功能其实是通的**（他 `regions.json` 里
          `edge_override={'12':'show','0':'hide'}` 证明他切换成功过），
          但视觉上只有"某条细虚线淡了一点点"，日志又只写"边显隐变更：区域 #0"，
          **给不出任何可核对的细节** ⇒ 用户只能得出"没反应"。
          ⇒ 现在从**同步前 vs 同步后**的 `edge_override` 做 diff，一行内说清：
            哪条边、切成 `hide` 还是 `show`、该区域当前"显示/隐藏（共 N 条边）"。
          ⇒ 点了空白（一条边都没变）时**也要如实说**一句，让用户能区分
            "我点空了"和"我点中了但看不出来" —— 这正是他当前最需要的信息。

        ## 键类型（`'0'` vs `0` 的坑，别再踩）
          · "同步前" = **模型**里的 `edge_override`（`SREG.get_sample_regions`）；
          · "同步后" = `_sync_from_canvas()` 跑完后的**模型**（它就是从画布整份读回来、
            过 `set_sample_regions` → `_norm_region` → `_norm_edge_override` 的**同一份数据**）；
          · 两侧都再用 `SREG._norm_edge_override()` 过一遍 ⇒ 一律是**整数键**，
            不会因为画布写 `'0'`、模型存 `0` 而把"没变"误判成"变了"（或反之）。
          · 统计用 `SREG.visible_edge_indices()`（**全库唯一的"哪条边可见"实现**，
            已含自动隐藏 + 手工 override）⇒ 日志里的"隐藏 N 条"与画布/出图口径一致。
        """
        try:
            idx = (list(args) + [None])[0]
            # ★ 同步前：模型里的 edge_override（唯一的"改之前"参照物）
            ov_before = None
            if isinstance(idx, int):
                try:
                    regs0 = SREG.get_sample_regions(self.regions_data, self.current_sample)
                    if 0 <= idx < len(regs0) and isinstance(regs0[idx], dict):
                        ov_before = SREG._norm_edge_override(regs0[idx].get("edge_override"))
                except Exception:
                    traceback.print_exc()
            self._sync_from_canvas(reason="边显隐变更")
            if idx is None or not isinstance(idx, int):
                self._log("边显隐变更：载荷没有区域索引（%r）→ 已整份同步，但无法说明改了哪条边"
                          % (idx,))
                return
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            if not (0 <= idx < len(regs)) or not isinstance(regs[idx], dict):
                self._log("边显隐变更：区域 #%d 不在当前样本里（共 %d 个区域）→ 已整份同步"
                          % (idx + 1, len(regs)))
                return
            r = regs[idx]
            ov_after = SREG._norm_edge_override(r.get("edge_override"))
            # ---- ① 诊断（保留）：画布没把 edge_override 写进字典 ⇒ 点的边存不下来
            if not ov_after:
                self._warn_once("edges_not_in_canvas_dict",
                                "画布未把 `edge_override` 写进区域字典（同步回来是空的）"
                                "→ 用户点的边**不会被保存**；需 W1 在区域字典里带上该字段")
            # ---- ② 具体发生了什么：同步前 vs 同步后 的 diff
            n_edges = len(r.get("points") or [])
            try:
                n_vis = len(SREG.visible_edge_indices(r, self.spots))
            except Exception:
                traceback.print_exc()
                n_vis = n_edges
            stat = "当前 显示 %d / 隐藏 %d（共 %d 条边）" % (n_vis, n_edges - n_vis, n_edges)
            changed = []
            if ov_before is not None:
                for e in sorted(set(ov_before.keys()) | set(ov_after.keys())):
                    b, a = ov_before.get(e), ov_after.get(e)
                    if b == a:
                        continue
                    # ★ 三态而不是两态：`a is None` = **手工覆盖被移除**（回到默认），
                    #   不能写成"→ 显示"——那会把"删除覆盖"和"显式设为显示"混为一谈。
                    if a == "hide":
                        what = "隐藏"
                    elif a == "show":
                        what = "显示"
                    else:
                        what = "移除手工覆盖（回到默认）"
                    changed.append("边 %d → %s" % (e, what))
            if changed:
                self._log("区域 #%d：%s；%s" % (idx + 1, "、".join(changed), stat))
            elif ov_before is None:
                self._log("区域 #%d：已整份同步，但**取不到同步前的 edge_override** → 无法 diff"
                          "（本次不判断『点了哪条边』）；%s" % (idx + 1, stat))
            else:
                self._log("边显隐未变（区域 #%d）—— 可能没点中边（请把鼠标移到虚线上再点，"
                          "不要点在区域内部的空白处）；%s" % (idx + 1, stat))
        except Exception:
            traceback.print_exc()

    def _on_region_label_moved(self, *args):
        """`label` 模式拖动了注释锚点 → 从画布整份同步（§15.3 `label_pos`）

        ## ★ 临时兼容（W1 修好 §13.9 2d 之前必须有）
          协调者实测：**W1 的画布还没把 `label_pos` 写进区域字典**
          （信号发了，但 `get_regions()[0]['label_pos']` 是 `None`）。
          而我的策略是"整份同步" ⇒ 那会把 `label_pos` 一路写回 `None`
          ⇒ **用户拖的注释位置被抹掉**。
          ⇒ 取舍：**载荷先留着当兜底** —— 同步后若该区域的 `label_pos` 仍是 `None`，
            就用载荷里的 `(x, y)` 补上，并把补好的整份**推回画布**（让画布与模型一致）。
          ⇒ W1 一旦写进字典（值非 None），这段兜底**自然不再触发**，无需再改代码。
          ★ 只对 `label_pos` 开这一个口子：`edge_override` 的载荷没有明细（见上一个槽），
            所以那边只能靠诊断告警，不能兜底。
        """
        try:
            idx, x, y = (list(args) + [None, None, None])[:3]
            self._log("注释位置变更：区域 #%s → (%s, %s)" % (idx, x, y))
            regs = self._read_canvas_regions()
            used_fallback = False
            if regs is not None and isinstance(idx, int) and 0 <= idx < len(regs) \
                    and isinstance(regs[idx], dict):
                if SREG._norm_label_pos(regs[idx].get("label_pos")) is None \
                        and x is not None and y is not None:
                    try:
                        regs[idx]["label_pos"] = [float(x), float(y)]
                        used_fallback = True
                        self._warn_once(
                            "label_pos_fallback",
                            "画布未把 `label_pos` 写进区域字典 → 本次用信号载荷兜底"
                            "（数据不会丢，但这是**临时兼容**；W1 修好后自动不再触发）")
                    except (TypeError, ValueError):
                        traceback.print_exc()
                SREG.set_sample_regions(self.regions_data, self.current_sample, regs)
                self._persist(reason="注释位置变更" + ("（载荷兜底）" if used_fallback else ""))
                self._refresh_region_list()
                if used_fallback:
                    # 把补好的整份推回画布：否则画布仍是 None，下次同步又会把它抹掉
                    self._call_canvas(CANVAS_SET_REGIONS, regs)
            else:
                # 拿不到画布区域 → 退回整份同步路径（并留痕）
                self._sync_from_canvas(reason="注释位置变更")
        except Exception:
            traceback.print_exc()

    def _on_region_name_changed(self, *args):
        """`region_name_changed(idx, name)`：W1 在 `canvas.set_region_name()` 里发（§16.2）

        ★ 这是**画布侧**改名落盘的正式通路（W1 文件里明文"落盘由 bind 接
          `canvas.region_name_changed` 完成"），不是可选增强。
        ★ v2（`_d_spec_region_naming_v2.md` §3/§4）起：界面上**已没有自由文本改名入口**
          （`region_name_edit` 已删、`region_name_input` 不可编辑）⇒ 正常情况下这条信号
          **不会发**。保留接线是为了"画布将来用别的入口改名"时不静默丢盘；
          它同步的是画布的整份区域（画布里的 dict 带 `anno_group`/`anno_label`，
          因为本文件每次写盘后都把整份推回画布）。
        ★ 为什么不解析载荷去改字段：与 `edges`/`label` 两个信号同一约定 ——
          **画布是几何+样式的唯一真相源**，收到信号就 `get_regions()` **整份读回**，
          载荷只用来写日志；载荷形状以后变了也不影响同步。
        ★ 不会循环：`set_region_name()` 同值直接 return 不 emit（W1 `region_canvas.py`），
          而我这里推回画布用的是 `set_regions()`（不 emit 本条信号）。
        """
        try:
            idx, name = (list(args) + [None, None])[:2]
            try:
                shown = "#%d" % (int(idx) + 1)
            except (TypeError, ValueError):
                shown = "#?"
            self._log("区域改名信号：区域 %s → 『%s』（从画布整份同步并落盘）"
                      % (shown, name))
            self._sync_from_canvas(reason="区域改名")
        except Exception:
            traceback.print_exc()

    def _on_corner_radius_changed(self, *args):
        """圆角输入变化 → 写进**当前选中区域**的 `corner_radius_px`（§15.3）

        ★ 为什么写"当前选中区域"而不是全局：圆角是**逐区域**字段
          （画布上各区域可以有不同圆角），全局输入框只是"改当前这个"的入口。
          没有选中区域时只做预览（`set_active_style` 已由 `_push_active_style` 处理），
          并**留痕**说明"没有选中区域，圆角只对新画的多边形生效"。
        """
        try:
            val = self._read_number(self._ctl('region_corner_radius_input'),
                                    SREG.DEFAULT_CORNER_RADIUS_PX)
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            idx = self.active_region_index
            if idx is None or not (0 <= idx < len(regs)):
                # ★ W1 指出：这里原来只调 `_push_active_style()`（那是"样式预览"），
                #   **没带半径** ⇒ 用户接着画的第一个多边形半径会是 0，
                #   与他刚在输入框里调的值不符。
                #   ⇒ 补一句 `set_active_corner_radius`（W1 已支持，并在闭合建区域时
                #     把半径写进新区域），这样"没有选中区域时只对接下来画的生效"才真成立。
                self._call_canvas('set_active_corner_radius', val)
                self._log("圆角 = %s（当前没有选中区域：只对**接下来画**的多边形生效）" % val)
                self._push_active_style()
                return
            regs[idx]["corner_radius_px"] = val
            SREG.set_sample_regions(self.regions_data, self.current_sample, regs)
            self._persist(reason="圆角变更（区域 #%d）" % (idx + 1))
            self._call_canvas(CANVAS_SET_REGIONS, regs)   # 让画布按新圆角重画
            self._log("区域 #%d 的圆角 = %s px" % (idx + 1, val))
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # ★★ v2 两级命名（分组 + 注释）—— 契约 `_d_spec_region_naming_v2.md` §4
    # ------------------------------------------------------------------
    # 旧链路（`region_name_input` 可编辑 + `region_name_edit.editingFinished` →
    # `_on_region_name_edited` 读自由文本改名）**整体删除**：
    #   · W1 已把 `region_name_input` 改成**不可编辑**的分组下拉、`region_name_edit`
    #     已随 `setEditable(False)` 消失 ⇒ 那条链上**一个控件都不存在**，
    #     留着只会变成"看着像活路的死代码"，或者更糟：**第二条写盘路径**。
    # 新链路（**本页唯一的命名写盘入口** = `_commit_anno`）：
    #   · 注释选择框 `currentRowChanged`（= 用户在列表里**点了具体注释**）；
    #   · 自定义输入框的『确定』按钮（或回车）；
    #   ⇒ 只有这两处调 `_commit_anno(...)`。
    #   ★ 分组下拉 `currentIndexChanged` **不写盘**（§4.3 表，2026-09-23 协调者收紧）：
    #     只重填注释选择框 + 更新待用分组，绝不因为"点开下拉看一眼"就改用户数据。
    # ==================================================================
    def bind_name_edit(self):
        """§4 两级命名接线：分组下拉 + 注释选择框 + 自定义输入框（**没有自由文本**）

        · `region_name_input`（不可编辑）→ `currentIndexChanged` → `_on_anno_group_changed`
          （**只重填注释框，不写盘** —— §4.3 表）；
        · `region_anno_list` → `currentRowChanged`（没有就退 `itemSelectionChanged`）
          → `_on_anno_label_changed`（**用户点了具体注释 ⇒ 写盘**）；
        · `btn_region_anno_ok` / `region_anno_input.returnPressed` → `_on_anno_new_ok_clicked`
          （**自定义新建确定 ⇒ 写盘**）；
        · **只连"值真的变了"的信号**（不再连 `editingFinished`）：写盘由本文件
          `_commit_anno()` 一处收口，同值不重复写盘（§4.3）。
        · 缺控件**绝不静默**（写一行日志说明缺哪个、哪条路不可用）。
        """
        try:
            combo = self._ctl('region_name_input')
            if combo is None:
                self._warn_once("no_name_input",
                                "布局未提供 region_name_input（分组下拉）→ 两级命名不可用")
            else:
                # ★ W1 实测提醒（2026-09-23）：`QComboBox` **没有** `editingFinished` /
                #   `returnPressed`（`setEditable(False)` 后 `lineEdit()` 还是 None）
                #   ⇒ 旧接法只会走到"缺信号"告警，`_on_region_name_edited` 永远连不上。
                #   现在的正确信号 = **`currentIndexChanged`**（值真的换了才发），
                #   老式样式退 `currentTextChanged`；两者都没有才告警（文案说清"换分组
                #   不会写盘"，不再提已不适用的 editingFinished）。
                hooked = False
                for sig_name in ('currentIndexChanged', 'currentTextChanged'):
                    sig = getattr(combo, sig_name, None)
                    if sig is not None and hasattr(sig, 'connect'):
                        sig.connect(self._on_anno_group_changed)
                        hooked = True
                        break
                if not hooked:
                    self._warn_once("no_group_sig",
                                    "region_name_input 上没有 currentIndexChanged/"
                                    "currentTextChanged → 换分组不会写盘（需要 W1 补信号）")
            lst = self._ctl('region_anno_list')
            if lst is None:
                self._warn_once("no_anno_list",
                                "布局未提供 region_anno_list（注释选择框）→ 注释不可选")
            else:
                hooked = False
                sig = getattr(lst, 'currentRowChanged', None)
                if sig is not None and hasattr(sig, 'connect'):
                    sig.connect(self._on_anno_label_changed)
                    hooked = True
                else:
                    sig = getattr(lst, 'itemSelectionChanged', None)
                    if sig is not None and hasattr(sig, 'connect'):
                        sig.connect(self._on_anno_label_selection_changed)
                        hooked = True
                if not hooked:
                    self._warn_once("no_anno_list_sig",
                                    "region_anno_list 没有 currentRowChanged/itemSelectionChanged "
                                    "→ 选注释不会写盘（需要 W1 补信号）")
            btn = self._ctl('btn_region_anno_ok')
            if btn is None:
                self._warn_once("no_anno_ok_btn",
                                "布局未提供 btn_region_anno_ok → 自定义注释无法确定")
            elif hasattr(btn, 'clicked'):
                btn.clicked.connect(self._on_anno_new_ok_clicked)
            inp = self._ctl('region_anno_input')
            if inp is None:
                self._warn_once("no_anno_input",
                                "布局未提供 region_anno_input → 自定义注释无法输入")
            else:
                sig = getattr(inp, 'returnPressed', None)
                if sig is not None and hasattr(sig, 'connect'):
                    sig.connect(self._on_anno_new_ok_clicked)
        except Exception:
            traceback.print_exc()
        self._check_anno_sreg_api()

    def _check_anno_sreg_api(self):
        """W3 的四个冻结接口在不在 —— 缺了要在日志里说清是哪一条（绝不静默降级）"""
        try:
            missing = [n for n in ('GROUP_GRAPHED', 'group_graphed_labels',
                                   'sample_has_group_graphed', 'anno_values_from_spots')
                       if not hasattr(SREG, n)]
            if missing:
                self._warn_once("anno_sreg_api",
                                "spatial_region_analysis 缺少两级命名的冻结接口 %s → "
                                "分组下拉/注释选择框会退化（需要 W3 补）" % ", ".join(missing))
        except Exception:
            traceback.print_exc()

    # ---- 小组件读写（一律防御式；缺接口一律留痕，绝不静默）----
    def _anno_group_graphed(self):
        """`"group_graphed"`（**真相源 = W3 的 `SREG.GROUP_GRAPHED`**；取不到才用字面量）"""
        try:
            v = str(getattr(SREG, 'GROUP_GRAPHED', '') or '').strip()
            if v:
                return v
        except Exception:
            traceback.print_exc()
        self._warn_once("no_sreg_group_graphed",
                        "SREG.GROUP_GRAPHED 取不到 → 用字面量 'group_graphed'"
                        "（需要 W3 补；写盘内容不受影响）")
        return ANNO_GROUP_GRAPHED_FALLBACK

    def _anno_values(self, column):
        """`SREG.anno_values_from_spots(self.spots, column)`（缺失 → `[]` + 留痕）"""
        try:
            fn = getattr(SREG, 'anno_values_from_spots', None)
            if not callable(fn):
                self._warn_once("no_anno_values_fn",
                                "SREG.anno_values_from_spots() 不存在 → 注释选择框按空处理"
                                "（需要 W3 补）")
                return []
            return [str(x).strip() for x in (fn(self.spots or [], column) or [])
                    if str(x).strip()]
        except Exception:
            traceback.print_exc()
            return []

    def _sample_has_group_graphed(self, regions):
        """`SREG.sample_has_group_graphed(regions)`（缺失 → False + 留痕）"""
        try:
            fn = getattr(SREG, 'sample_has_group_graphed', None)
            if not callable(fn):
                self._warn_once("no_has_gg_fn",
                                "SREG.sample_has_group_graphed() 不存在 → 一律按"
                                "『该样本没有自定义注释』处理（需要 W3 补）")
                return False
            return bool(fn(regions))
        except Exception:
            traceback.print_exc()
            return False

    @staticmethod
    def _list_index_of(lst, text):
        """在列表控件里按**逐字相等**找项（不用 `findItems/findText` 猜 API）；找不到 → -1"""
        try:
            if lst is None or not hasattr(lst, 'count') or not hasattr(lst, 'item'):
                return -1
            want = str(text)
            for i in range(int(lst.count())):
                it = lst.item(i)
                if it is not None and str(it.text()) == want:
                    return i
        except Exception:
            traceback.print_exc()
        return -1

    def _anno_list_text(self):
        """注释选择框当前项文本（没有当前项 → 空串）"""
        try:
            lst = self._ctl('region_anno_list')
            if lst is None:
                return ""
            fn = getattr(lst, 'currentItem', None)
            if callable(fn):
                it = fn()
                if it is not None:
                    return str(it.text())
            if hasattr(lst, 'currentRow') and hasattr(lst, 'item'):
                row = int(lst.currentRow())
                if row >= 0:
                    it = lst.item(row)
                    if it is not None:
                        return str(it.text())
        except Exception:
            traceback.print_exc()
        return ""

    def _set_anno_filling(self, on):
        """回填守卫开关（**嵌套安全**：直接置位，调用方用 try/finally 恢复原值）"""
        self._anno_filling = bool(on)

    def _select_list_text(self, lst, text, log_missing=False):
        """把列表当前行指到 `text`（守卫期内调用；找不到 → 取消选中 + 可选留痕）"""
        try:
            if lst is None:
                return False
            if not text:
                if hasattr(lst, 'setCurrentRow'):
                    lst.setCurrentRow(-1)
                elif hasattr(lst, 'clearSelection'):
                    lst.clearSelection()
                return False
            pos = self._list_index_of(lst, text)
            if pos < 0:
                if log_missing:
                    self._log("⚠ 注释『%s』不在当前分组的可选值里 → 选择框未选中它"
                              "（数据可能已变；请重新选一次）" % text)
                return False
            if hasattr(lst, 'setCurrentRow'):
                lst.setCurrentRow(pos)
            return True
        except Exception:
            traceback.print_exc()
            return False

    # ---- §4.1 分组下拉 ----
    def _fill_anno_group_combo(self):
        """填「分组」下拉（§4.1）：items **恰好**

            `[ "cell_type", "cluster", ("group_graphed" 当且仅当该样本已有自定义注释), "自定义" ]`

        · 「自定义」**永远最后一项**；
        · `cell_type` / `cluster` **缺列就跳过**（`SREG.anno_values_from_spots` 返回空
          ⇒ 该列没有可用值），不报错；
        · `group_graphed` 只在**该样本已有非空 `anno_label`** 时出现
          （判据 = W3 的 `sample_has_group_graphed`，不是我自己再写一份）；
        · 全程在 `_anno_filling` 守卫内（`clear()/setCurrentIndex` 都会发信号）。
        Returns: list[str] —— 实际填进去的 items（顺序即展示顺序）
        """
        items = []
        try:
            combo = self._ctl('region_name_input')
            if combo is None or not hasattr(combo, 'addItem'):
                self._warn_once("no_group_combo_fill",
                                "region_name_input 不支持 addItem → 分组下拉为空")
                return items
            # ① 现有分组列（缺列/无值 ⇒ 跳过，不报错）
            for col in (ANNO_GROUP_CELL_TYPE, ANNO_GROUP_CLUSTER):
                try:
                    if self._anno_values(col):
                        items.append(col)
                except Exception:
                    traceback.print_exc()
            # ② group_graphed：**仅当该样本已有自定义注释**
            gg = self._anno_group_graphed()
            try:
                regs = self._current_regions()
                has_gg = self._sample_has_group_graphed(regs) if regs else False
                if not regs:
                    # 内存里没有该样本的区域（如首次进页面/数据被清）→ 退回读盘（只读）
                    has_gg = self._sample_has_group_graphed(self._read_regions_for_sample())
                if has_gg:
                    items.append(gg)
            except Exception:
                traceback.print_exc()
            # ③ 「自定义」永远最后
            items.append(ANNO_GROUP_CUSTOM)

            prev = self._anno_filling
            self._anno_filling = True
            try:
                cur = ""
                try:
                    cur = str(combo.currentText() or "")
                except Exception:
                    cur = ""
                try:
                    combo.clear()
                except Exception:
                    traceback.print_exc()
                for it in items:
                    try:
                        combo.addItem(it)
                    except Exception:
                        traceback.print_exc()
                pos = -1
                # ★ 默认选中项：**优先沿用**当前分组（但「自定义」是"进入自定义"的
                #   过渡项，跨样本/跨刷新不保留 —— 否则第一次填充（spots 还没读到时
                #   只有「自定义」一项）会把这个占位选择一路带下去，用户看到的是
                #   空空的注释选择框）。取不到 ⇒ 归位 `cell_type`（§4.1 的第一项）。
                if cur and cur != ANNO_GROUP_CUSTOM:
                    fn = getattr(combo, 'findText', None)
                    if callable(fn):
                        try:
                            pos = int(fn(cur))
                        except Exception:
                            pos = -1
                if pos < 0:
                    fn = getattr(combo, 'findText', None)
                    for want in (ANNO_GROUP_CELL_TYPE, gg):
                        if want not in items:
                            continue
                        if callable(fn):
                            try:
                                pos = int(fn(want))
                            except Exception:
                                pos = -1
                        if pos >= 0:
                            break
                if pos < 0 and items:
                    pos = 0
                if pos >= 0:
                    combo.setCurrentIndex(pos)
            finally:
                self._anno_filling = prev
        except Exception:
            traceback.print_exc()
        return items

    # ---- §4.2 注释选择框 ----
    def _sample_anno_labels(self):
        """该样本**已有**的 `anno_label` 去重值（保序、去空）—— `group_graphed` 的可选值"""
        out, seen = [], set()
        try:
            for r in self._current_regions():
                if not isinstance(r, dict):
                    continue
                lb = str(r.get('anno_label') or '').strip()
                if lb and lb not in seen:
                    seen.add(lb)
                    out.append(lb)
        except Exception:
            traceback.print_exc()
        return out

    def _refill_anno_list(self, group):
        """按 `group` 重填注释选择框（§4.2 表）

        | combo 选中 | list 内容 |
        |---|---|
        | `cell_type` / `cluster` | 该样本 spots 里该列的**去重值（保序、去空）** |
        | `group_graphed` / `自定义` | 该样本**已有** `anno_label` 去重值 + 末尾「自定义」 |
        | 其它 | 空（日志写明"该分组没有可选项"） |

        ★ 只填不加选：**选中哪一项**由 `_sync_anno_controls` / 各 handler 决定
          （回填时不能顺手写盘，见 `_anno_filling`）。
        Returns: list[str] —— 实际填进去的值
        """
        values = []
        try:
            lst = self._ctl('region_anno_list')
            gg = self._anno_group_graphed()
            g = str(group or '').strip()
            if g in (gg, ANNO_GROUP_CUSTOM):
                values = self._sample_anno_labels() + [ANNO_LABEL_CUSTOM]
            elif g in (ANNO_GROUP_CELL_TYPE, ANNO_GROUP_CLUSTER):
                values = self._anno_values(g)
            else:
                self._log("⚠ 分组『%s』没有已知的注释来源 → 注释选择框为空" % (g or "（空）"))
            if lst is None or not hasattr(lst, 'addItem'):
                self._warn_once("no_anno_list_fill",
                                "region_anno_list 不支持 addItem → 注释选择框为空")
                return values
            prev = self._anno_filling
            self._anno_filling = True
            try:
                try:
                    lst.clear()
                except Exception:
                    traceback.print_exc()
                for v in values:
                    try:
                        lst.addItem(str(v))
                    except Exception:
                        traceback.print_exc()
                if hasattr(lst, 'setCurrentRow'):
                    lst.setCurrentRow(-1)
            finally:
                self._anno_filling = prev
        except Exception:
            traceback.print_exc()
        return values

    def _update_anno_input_visibility(self):
        """「自定义」被选中 ⇒ 显示输入框 + 确定按钮；否则隐藏（§4.2）"""
        try:
            is_custom = (self._anno_list_text().strip() == ANNO_LABEL_CUSTOM)
            for name in ('region_anno_input', 'btn_region_anno_ok'):
                w = self._ctl(name)
                if w is None or not hasattr(w, 'setVisible'):
                    continue
                try:
                    w.setVisible(bool(is_custom))
                except Exception:
                    traceback.print_exc()
            if is_custom and not self._anno_input_hint_shown:
                self._anno_input_hint_shown = True
                self._log("注释：已选『自定义』→ 请在下方输入框填写新注释名，再点『确定』"
                          "（确定后才会写盘）")
            if not is_custom:
                self._anno_input_hint_shown = False
        except Exception:
            traceback.print_exc()

    def _clear_anno_input(self):
        try:
            inp = self._ctl('region_anno_input')
            if inp is not None:
                self._write_text(inp, "")
        except Exception:
            traceback.print_exc()

    # ---- 取数（本样本的区域；内存优先，缺失才只读读盘）----
    def _current_regions(self):
        try:
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            return [r for r in regs if isinstance(r, dict)]
        except Exception:
            traceback.print_exc()
            return []

    def _read_regions_for_sample(self):
        """只读读盘取该样本区域（`load_regions` 缺失/损坏返回空骨架，不抛；绝不写盘）"""
        try:
            if not self.dataset or not self.current_sample:
                return []
            data = SREG.load_regions(self.dataset)
            return SREG.get_sample_regions(data, self.current_sample)
        except Exception:
            traceback.print_exc()
            return []

    def _current_group_text(self):
        """分组下拉当前文本（控件缺失 → 取待用值 → 兜底 `cell_type`）"""
        try:
            combo = self._ctl('region_name_input')
            if combo is not None:
                fn = getattr(combo, 'currentText', None)
                if callable(fn):
                    t = str(fn() or '').strip()
                    if t:
                        return t
        except Exception:
            traceback.print_exc()
        return str(self._anno_pending_group or '').strip() or ANNO_GROUP_CELL_TYPE

    # ---- 选中区域 → 回填（§4.5）----
    def _sync_anno_controls(self, index):
        """选中区域 ⇒ 回填：`anno_group` → 分组下拉、`anno_label` → 注释选择框（§4.5）

        规则：
          · 区域存了 `anno_group` 但下拉里没有这一项（例如它选的是"自定义"以外的历史值）
            ⇒ **补一项**（插在「自定义」之前，保证「自定义」永远最后）+ 留痕；
          · 旧式区域（`anno_group`/`anno_label` 都空）⇒ 分组归位 `cell_type`、
            注释选择框**不选中**、**一个字节都不写**（§4.3 末条：旧式区域的 `name` 不动）；
          · 全程在 `_anno_filling` 守卫内 —— 回填会发 `currentIndexChanged`/
            `currentRowChanged`，不挡住就会"看一眼就把旧区域改名了"。
        ★ 分组下拉的**归位**已由 W1 的 `show_region_name(index)` 做（§3），本方法
          再做一遍是**幂等兜底**（W1 的布局缺失时页面仍然可用），不构成第二份真相源。
        Returns: dict —— 本次回填进去的 {group, label}（供日志/探针核对）
        """
        info = {'group': '', 'label': ''}
        prev = self._anno_filling
        self._anno_filling = True
        try:
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            region = {}
            try:
                i = int(index)
            except (TypeError, ValueError):
                i = -1
            if 0 <= i < len(regs) and isinstance(regs[i], dict):
                region = regs[i]
            group = str(region.get('anno_group') or '').strip()
            label = str(region.get('anno_label') or '').strip()
            combo = self._ctl('region_name_input')
            # ① 分组项缺失 ⇒ 补一项（插在「自定义」之前）
            if group and combo is not None and hasattr(combo, 'insertItem') \
                    and hasattr(combo, 'findText') and hasattr(combo, 'count'):
                try:
                    if int(combo.findText(group)) < 0:
                        pos = int(combo.findText(ANNO_GROUP_CUSTOM))
                        combo.insertItem(pos if pos >= 0 else int(combo.count()), group)
                        self._log("分组下拉补入区域上保存的分组『%s』（避免回填时被改掉）" % group)
                except Exception:
                    traceback.print_exc()
            # ② 选中分组（旧式 ⇒ cell_type，再退第 0 项）
            target = group or ANNO_GROUP_CELL_TYPE
            if combo is not None and hasattr(combo, 'findText') and hasattr(combo, 'count'):
                try:
                    pos = int(combo.findText(target))
                    if pos < 0:
                        pos = int(combo.findText(ANNO_GROUP_CELL_TYPE))
                    if pos < 0 and int(combo.count()) > 0:
                        pos = 0
                    if pos >= 0:
                        combo.setCurrentIndex(pos)
                except Exception:
                    traceback.print_exc()
            # ③ 注释选择框按当前分组重填 + 选中该区域的 anno_label
            eff = self._current_group_text()
            values = self._refill_anno_list(eff)
            lst = self._ctl('region_anno_list')
            if label and label in values:
                self._select_list_text(lst, label)
            else:
                if label:
                    self._log("⚠ 区域 #%d 存的注释『%s』不在分组『%s』的现有值里 → "
                              "选择框未选中（数据可能已变）" % (i + 1, label, eff))
                self._select_list_text(lst, "")
            # ④ 待用值跟随该区域（旧式区域的待用注释 = 空，不继承它的旧 name）
            self._anno_pending_group = group or ANNO_GROUP_CELL_TYPE
            self._anno_pending_label = label
            info = {'group': group, 'label': label}
            self._update_anno_input_visibility()
            # ★★ 2026-09-23（`_d_spec_select_mode.md` §3.3/§3.4）：命名控件的**可用态**也在这里
            #   收口 —— 多选(≥2) 或 选中**隐形区域** ⇒ 四个命名控件 `setEnabled(False)`；
            #   否则恢复 True。★ v9.3 收窄：这里原写"选中范围层"，但**用户当初只说了隐形区域**、
            #   可见区域是我方擅自扩大 ⇒ 见 `_is_anno_blocked_region` 的沿革。
            #   ★ **复用本方法**（本文件所有"选中某区域"的路径最后都会走到这里），
            #     不另造一套启用逻辑 —— 否则必然出现"某条路恢复不了可用态"。
            #   ★ 只调 `setEnabled`：不发信号、不写盘（本方法整段还在 `_anno_filling` 守卫内）。
            self._apply_anno_enablement(i)
        except Exception:
            traceback.print_exc()
        finally:
            self._anno_filling = prev
        return info

    # ==================================================================
    # ★★ 2026-09-23「选择模式」：范围层判据 + 命名控件可用态（`_d_spec_select_mode.md` §3.3/§3.4）
    # ==================================================================
    def _is_layer_region(self, region):
        """`SREG.is_layer_region(region)` 的**存在性安全**调用（★ **"范围层"**判据，原义不变）

        ★ 判据 = "**范围层**"：`mask` 隐形 **或** `visible` 可见，两种都算 —— **本体不动**。
          ⚠ **v9.3 起命名链路不再用它**（改用更窄的 `_is_anno_blocked_region`，只看 `mask`）
          ⇒ 本包装方法**当前没有调用点**，按任务要求**保留不删**：它是"范围层"的存在性安全包装，
          将来别处（统计/诊断等）要用。
          ⚠ **v9.3 起出图链路也不再走它**（用户裁定：可见区域是**可画的标注单元**、
          自己也会出图，只有隐形区域不算可画区域）⇒ 『确认』里那条 `paintable` 过滤现在走
          `_is_anno_blocked_region`（**只排除隐形区域**）：既**不是**本方法，
          **也不再是** `SREG.is_layer_region(r)` 直调。
          ⇒ 本方法仍是"范围层"（`mask` **或** `visible`）判据，**不等于**出图判据，
          别拿它当出图依据。
        ★★ 沿革（**不许静默改口径**）：2026-09-23 规格 §3.4 曾把"不可命名"判据也写成这一条，
          并留下"若日后要放开'可见区域可命名'，**只改这一处判据**"的建议 —— **该建议已作废**：
          v9.3 用户报 bug（可见区域被禁用 ⇒ 下拉框/选择框点不动）后，改为**另立**更窄的
          `_is_anno_blocked_region`（只挡隐形区域），而**不把**本判据改窄 ——
          否则函数名（"范围层"）会撒谎，将来别的用途还会踩同样的坑。
        ★ 函数不存在（W3 还没交付）⇒ 降级为"**不判定为范围层**" + 留痕。
          为什么降级成 False 而不是 True：判 True 会把**普通区域**的命名入口整体堵死
          （用户什么都命名不了），而降级放过只是少了一层保护；两者都要留痕，不许静默。
          ⚠ v9.3：命名链路已**不依赖**本方法（改走 `_is_anno_blocked_region`，它自带
          `SREG._norm_flag` 的降级与留痕）⇒ 这条告警只影响"范围层"判据的其它将来用途。
        """
        try:
            fn = getattr(SREG, 'is_layer_region', None)
            if not callable(fn):
                self._warn_once("no_is_layer_region",
                                "SREG.is_layer_region() 不存在 → 本次**不判定为范围层**"
                                "（范围层的命名拒写守卫本次不生效；需要 W3 补这个函数）")
                return False
            return bool(fn(region))
        except Exception:
            traceback.print_exc()
            return False

    def _is_anno_blocked_region(self, region):
        """★ 命名链路**唯一**的"不参与命名"判据：**只**认隐形区域（`region["mask"]` 为真）

        ★★ v9.3（用户报 bug 后的**收窄**；**不许静默改口径**，沿革照实留在这里）：
          · 2026-09-23 规格 §3.4 原本把"不参与命名"的判据写成 `_is_layer_region`
            （`mask` 隐形 **+** `visible` 可见，两种都拒）；
          · 但**用户当初的原话只说了隐形区域**：「隐形区域我们不做命名或者注释归类处理，
            这个只是用来框定显示区域的」—— 把 `visible` 也一起挡掉是我方**擅自扩大**；
          · 后果（用户报的**真 bug**）：真实数据 `GSM7596590` / `GSM7596591` 里有 5 个
            `visible` 区域且**画在最后**（画布"后画优先"⇒ 一点就选中它）⇒ 四个命名控件
            被 `_apply_anno_enablement` 禁用、`_commit_anno` 也拒写 ⇒
            **「区域分组的下拉框和选择框点不动」**。
          ⇒ v9.3 起命名链路**只挡隐形区域**：选中 `visible` 区域 ⇒ 四控件可用、可写入。
        ★ 判据用 W3 的**严格布尔** `SREG._norm_flag(region.get("mask"))` ——
          不能直接 `bool(...)`：`bool("false") == True`，手改成 `"mask": "false"` 的条目会被
          误判成隐形区域（理由见 `spatial_region_analysis._norm_flag` 的说明）。
          `_norm_flag` 取不到（W3 未交付）⇒ 降级 `bool(region.get("mask"))` + **留痕一次**。
        ★ 本方法**绝不抛**：非 dict / 任何异常一律返回 `False`（= 不挡）——
          宁可少一层保护，也不把用户的命名入口整体堵死（那正是本次 bug 的形态）。
        ★ 与 `_is_layer_region` 的分工：那个是**范围层**（`mask` **或** `visible`），
          **本体原义不变**、别处另有用途；本方法专答"它参不参与命名与注释归类"。
        ★ 用本方法的**两处**（v9.3）：
          ① 命名链路 —— `_reject_anno_on_layer`（拒写）、`_apply_anno_enablement`（四控件禁用）；
          ② 「确认」出图入口的 `paintable` 过滤（`_on_confirm_clicked`）——
             **可见区域是可画的标注单元**，只有隐形区域不算可画区域（否则"只画了可见区域"
             的样本会被直接拒绝执行、永远出不了图）。
        Returns: bool —— 该区域是否**不参与命名**（隐形区域）
        """
        try:
            if not isinstance(region, dict):
                return False
            fn = getattr(SREG, '_norm_flag', None)
            if callable(fn):
                return bool(fn(region.get("mask")))
            self._warn_once(
                "no_norm_flag_anno_blocked",
                "SREG._norm_flag() 不存在 → 隐形区域判据降级为 bool(region.get('mask'))"
                "（手改成字符串 `\"mask\": \"false\"` 的条目可能被误判成隐形区域；"
                "需要 W3 补这个函数）")
            return bool(region.get("mask"))
        except Exception:
            traceback.print_exc()
            return False

    def _reject_anno_on_layer(self):
        """当前选中区域是**隐形区域**（`mask`）⇒ 写标准日志并返回 True（命名链路的**唯一**拒写判据与文案）

        ★★ v9.3 收窄（用户报 bug 后；**不许静默改口径**）：
          · 2026-09-23 规格 §3.4 原判据 = `_is_layer_region`（`mask` 隐形 **+** `visible` 可见都拒）；
          · 但**用户当初的原话只说了隐形区域**（「隐形区域我们不做命名或者注释归类处理，
            这个只是用来框定显示区域的」）—— 把可见区域也拒掉是我方**擅自扩大**；
          · 后果（用户报的真 bug）：`GSM7596590` / `GSM7596591` 里 5 个 `visible` 区域
            画在最后（画布"后画优先"⇒ 一点就选中它）⇒ 命名四件套被禁用、`_commit_anno` 拒写
            ⇒ **「区域分组的下拉框和选择框点不动」**。
          ⇒ 现在判据 = `_is_anno_blocked_region`（**只**看 `mask`）：可见区域恢复可命名。
        ★ 只在**两个地方**调用（同一句话不写两遍）：
          · `_commit_anno` 开头守卫①（**唯一写入口** ⇒ 隐形区域零写盘、零改字段）；
          · `_on_anno_group_changed`（换分组本来就不写盘，但选中隐形区域时必须说清
            "为什么这次操作不算数"，否则用户点了禁用控件会以为程序坏了）。
        ★ 取不到选中区域（没选/索引越界）⇒ 返回 False（交给后面的"没有选中区域"路径）。
        Returns: bool —— 是否**因为隐形区域**而拒绝
        """
        try:
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            idx = self.active_region_index
            if not (isinstance(idx, int) and 0 <= idx < len(regs)
                    and isinstance(regs[idx], dict)):
                return False
            r = regs[idx]
            if not self._is_anno_blocked_region(r):
                return False
            self._log("隐形区域不参与命名与注释归类 ⇒ 已拒绝写入"
                      "（隐形区域只用于框定显示范围）")
            return True
        except Exception:
            traceback.print_exc()
            return False

    @staticmethod
    def _layer_kind_text(region):
        """范围层的用户可读类型（**只用于日志**）：`隐形区域` / `可见区域` / `范围层`

        ★ 按 `region.get("mask")` 区分（隐形优先）；`is_layer_region` 为真但两个标记都取不到
          ⇒ 如实写「范围层」，**不猜**（§3.4 明确要求）。
        ★ v9.3：命名链路已改用更窄的 `_is_anno_blocked_region`（只看 `mask`）⇒ 目前**唯一**
          的调用点 `_apply_anno_enablement` 里它恒为「隐形区域」。本方法**保留不删**：
          上面那条"两个标记都取不到 ⇒ 范围层"的分支留给将来别的日志调用点，
          且 `_apply_anno_enablement` 的状态指纹仍按它取值（不改变指纹结构）。
        """
        try:
            if isinstance(region, dict):
                if region.get("mask"):
                    return "隐形区域"
                if region.get("visible"):
                    return "可见区域"
        except Exception:
            traceback.print_exc()
        return "范围层"

    def _set_anno_controls_enabled(self, enabled):
        """四个命名控件一律 `setEnabled(enabled)`（缺失的控件跳过，不告警刷屏）

        ★ 只动"可用态"，**不动值、不写盘**；属性名冻结在 `ANNO_CONTROL_NAMES`
          （`region_name_input` / `region_anno_list` / `region_anno_input` / `btn_region_anno_ok`）。
        """
        ok = True
        for name in ANNO_CONTROL_NAMES:
            w = self._ctl(name)
            if w is None or not hasattr(w, 'setEnabled'):
                ok = False
                continue
            try:
                w.setEnabled(bool(enabled))
            except Exception:
                traceback.print_exc()
                ok = False
        return ok

    def _apply_anno_enablement(self, index):
        """按**当前选择状态**决定四个命名控件是否可用（§3.3 多选 / §3.4 范围层）—— 唯一收口

        ★ 复用点：`_sync_anno_controls()` 末尾。本文件**所有**"选中某区域"的路径
          （画布单选 `region_selected(int)` / 画布多选 `regions_selected(list)` /
          区域列表行选中 / 刚画完一个区域）最后都会走到那里 ⇒ 启用/禁用**只有这一处**，
          **不另造一套启用逻辑**（否则必然出现"某条路恢复不了"）。

        ★ 判据（自上而下，命中即止）：
          ① `len(_multi_selected_indices) >= 2` 且当前索引在多选集合里
             ⇒ **多选不可编辑**（画布只把选中的都画成选中态、不启动编辑）⇒ 禁用；
          ② 该区域是**隐形区域**（`_is_anno_blocked_region`，**只看 `mask`**）
             ⇒ 禁用（§3.4：隐形区域只用于框定显示范围，不参与命名/注释归类）；
             ★★ v9.3 收窄（用户报 bug 后；**不许静默改口径**）：原判据是 `_is_layer_region`
             （`mask` **+** `visible`，两种都禁）—— 但**用户当初只说了隐形区域**，
             把可见区域也禁掉是我方擅自扩大，真实数据里可见区域画在最后（后画优先）
             ⇒ 一点就选中它、四控件被禁 ⇒ **「区域分组的下拉框和选择框点不动」**（用户报的 bug）。
             现改为只挡隐形区域；`_is_layer_region` 本体（`mask` 或 `visible`）**原义不变**，另作他用；
          ③ 其余（普通区域单选 / **可见区域**单选 / 没有选中区域）⇒ **恢复可用**。

        ★ 日志只在**状态真的变了**时写一行（指纹 `_anno_enable_state`）：这些路径会被
          刷新/回填/`_persist` 之后的链路高频重入，不挡住会把日志刷满、真问题反而看不见。
        ★ 本方法**绝不写盘**（只调 `setEnabled`；也不改任何区域字段、不碰 `save_regions`）。

        Returns: bool —— 本次四个控件的目标可用态
        """
        enabled, why_key = True, ("on",)
        try:
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            # ★ 不用 try/except 转 int（那会变成一条"静默吞异常"的旁路）：类型不对就是 -1
            i = index if (isinstance(index, int) and not isinstance(index, bool)) else -1
            idxs = list(self._multi_selected_indices or [])
            region = None
            if 0 <= i < len(regs) and isinstance(regs[i], dict):
                region = regs[i]
            if len(idxs) >= 2 and (i < 0 or i in idxs):
                enabled, why_key = False, ("off", "multi", len(idxs))
            elif region is not None and self._is_anno_blocked_region(region):
                # ★ v9.3：判据已收窄为**只挡隐形区域**（`_is_anno_blocked_region`）。
                #   指纹仍存 `_layer_kind_text` 的取值（此处恒为「隐形区域」），结构不变。
                enabled, why_key = False, ("off", "layer", self._layer_kind_text(region))
        except Exception:
            traceback.print_exc()
        self._set_anno_controls_enabled(enabled)
        if why_key != self._anno_enable_state:
            self._anno_enable_state = why_key
            if why_key[:2] == ("off", "multi"):
                self._log("多选（%d 个区域）⇒ 命名控件已禁用；"
                          "请点某区域独有的边或锚点再命名" % why_key[2])
            elif why_key[:2] == ("off", "layer"):
                # ★ v9.3：本条现在**只**会在选中隐形区域（`mask`）时触发（见
                #   `_is_anno_blocked_region` 的沿革）；`why_key[2]` 仍由 `_layer_kind_text`
                #   给出（此处恒为「隐形区域」）⇒ 文案里不再重复引用它，只说「隐形区域」。
                self._log("当前选中的是隐形区域 ⇒ 命名控件已禁用"
                          "（隐形区域只用于框定显示区域；可见区域可正常命名）")
        return bool(enabled)

    # ---- §4.3 唯一写盘入口 ----
    def _commit_anno(self, group, label, source=""):
        """**唯一**的两级命名写盘入口（§4.3）：把 (分组, 注释) 落到**当前选中的区域**

        ★ 谁调它（**只有两处**，见 §4.3 表）：
            · `_on_anno_label_changed`（用户在注释列表里**点了具体值**）；
            · `_on_anno_new_ok_clicked`（「自定义」新建并点确定）。
          **换分组不调它** —— `_on_anno_group_changed` 只重填列表 + 更新待用分组。

        ```python
        regions[idx]["anno_group"] = "group_graphed" if combo 文本 == "自定义" else combo 文本
        regions[idx]["anno_label"] = 注释值
        regions[idx]["name"]       = 注释值      # ★★ 同步 name（R 渲染器/region_labels/
                                                 #    区域列表文本全部照旧）
        ```

        · **没有选中区域** ⇒ 只记住待用值（`_anno_pending_*`）：不报错、不建区域；
        · **注释值为空** ⇒ 同样只记待用值（尚未"定了注释"，不写盘、不动 `name`）；
        · **同值** ⇒ 不重复写盘；
        · 落盘沿用**既有链路**（`SREG.save_regions` 原子写 + 列表文本刷新）——
          本方法是本页唯一写这两级命名的入口，**没有第二条**。

        ## ★★ 开头两道**拒写守卫**（2026-09-23，「选择模式」规格 §3.4 / §3.3；守卫①于 v9.3 收窄）
          ① **隐形区域**（`_is_anno_blocked_region`，**只看 `mask`**）：
             直接拒绝。`anno_group` / `anno_label` / `name` **三个字段一个都不动**、
             **不调 `save_regions`**、不发持久化、**连待用值也不改**（零副作用），
             日志 `隐形区域不参与命名与注释归类 ⇒ 已拒绝写入（隐形区域只用于框定显示范围）`。
             依据：`assign_labels` / `group_graphed_labels` / `_effective_regions` **全都跳过
             范围层** ⇒ 给它命名对逐 spot 注释毫无影响，只会污染数据。
             ★★ v9.3 收窄（用户报 bug 后；**不许静默改口径**）：本守卫原判据是
             `_is_layer_region`（`mask` 隐形 **+** `visible` 可见）；但**用户当初的原话只说了
             隐形区域**（「隐形区域我们不做命名或者注释归类处理，这个只是用来框定显示区域的」），
             把可见区域一起拒掉是我方**擅自扩大** ⇒ 真实数据里 `visible` 区域画在最后
             （后画优先 ⇒ 一点就选中它）导致「区域分组的下拉框和选择框点不动」。现只挡隐形区域；
             `_is_layer_region` 本体（`mask` 或 `visible`）**原义不变**，别处另有用途。
          ② **多选（≥2 个区域）**：同样拒绝（防御性；界面上四个命名控件此时已经被
             `_apply_anno_enablement` 禁用，本条只是保证"程序化驱动控件也写不进去"），
             日志 `多选（%d 个区域）⇒ 已拒绝写入（命名控件已禁用…）`。
          ⇒ 两道守卫都在"取 `gg`/改 `_anno_pending_*`"**之前**，所以隐形区域路径**零写盘、零改字段**。

        Returns: bool —— 本次是否真的写了盘
        """
        try:
            # ---- 守卫①：**隐形区域**不参与命名与注释归类（§3.4；v9.3 收窄为只挡 `mask`）----
            #   判据与文案收口在 `_reject_anno_on_layer()`：三个字段一个都不动、
            #   **不调 `save_regions`**、不发持久化、连待用值也不改（零副作用）。
            if self._reject_anno_on_layer():
                return False
            # ---- 守卫②：多选时不允许命名（§3.3；控件已禁用，这里是最后一道闸）----
            idx_guard = self.active_region_index
            sel_idxs = list(self._multi_selected_indices or [])
            if len(sel_idxs) >= 2 and (not isinstance(idx_guard, int) or idx_guard in sel_idxs):
                self._log("多选（%d 个区域）⇒ 已拒绝写入（命名控件已禁用；"
                          "请点某区域独有的边或锚点再命名）" % len(sel_idxs))
                return False
            gg = self._anno_group_graphed()
            g = str(group or '').strip()
            if g == ANNO_GROUP_CUSTOM:                    # 「自定义」⇒ 字面量 group_graphed
                g = gg
            if not g:
                g = str(self._anno_pending_group or '').strip() or ANNO_GROUP_CELL_TYPE
            l = str(label or '').strip()
            self._anno_pending_group = g
            self._anno_pending_label = l
            if not l:
                if self._pending_logged != (g, l):
                    self._pending_logged = (g, l)
                    self._log("两级命名：已记住待用值（分组=%s，注释=未选）→ 未写盘"
                              "（选中一个注释值后才会落到区域上）" % g)
                return False
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            idx = self.active_region_index
            if idx is None or not (0 <= idx < len(regs)) or not isinstance(regs[idx], dict):
                if not self._anno_hint_shown:
                    self._anno_hint_shown = True
                    self._log("两级命名：已记住待用值（分组=%s，注释=『%s』）但**当前没有选中区域**"
                              " → 未写盘、不新建区域（先在画布或区域列表上点一个区域）" % (g, l))
                return False
            self._anno_hint_shown = False
            r = regs[idx]
            old_g = str(r.get('anno_group') or '').strip()
            old_l = str(r.get('anno_label') or '').strip()
            old_n = str(r.get('name') or '').strip()
            if old_g == g and old_l == l and old_n == l:
                self._log("两级命名：区域 #%d 已是（分组=%s，注释=『%s』）→ 同值不重复写盘"
                          % (idx + 1, g, l))
                return False
            # ★ 先原地改（探针/外部按引用持有的那份也能看到），再交给既有链路归一化落盘
            r['anno_group'] = g
            r['anno_label'] = l
            r['name'] = l
            SREG.set_sample_regions(self.regions_data, self.current_sample, regs)
            self._persist(reason="两级命名（区域 #%d，%s）" % (idx + 1, source or "控件变更"))
            # 推回画布：否则画布上那条注释文字仍是旧名（它只认自己那份数据）
            self._call_canvas(CANVAS_SET_REGIONS,
                              SREG.get_sample_regions(self.regions_data, self.current_sample))
            # 列表文本刷新：优先 W1 的**就地**刷新（不动顺序/选中行），缺失才整份重建
            refreshed = False
            fn = getattr(self.ui, 'refresh_region_list_texts', None)
            if callable(fn):
                try:
                    fn(idx)
                    refreshed = True
                except Exception:
                    traceback.print_exc()
            if not refreshed:
                self._refresh_region_list()
            self._log("区域 #%d：分组=%s，注释=『%s』（`name` 已同步为注释值；旧值 name=『%s』"
                      "anno_group=%s anno_label=『%s』）"
                      % (idx + 1, g, l, old_n, old_g or "（空=旧式）", old_l))
            # ★★ §4.1 落差修正（2026-09-23 协调者点名）：这次真的写盘了 ⇒ 该样本
            #   "已有非空 anno_label" 的条件**此刻刚成立**，必须**当轮**就把
            #   `group_graphed` 项补进分组下拉并选中它（用户原话："然后确定后直接在下拉框
            #   以后多出来这样的一个新选项并且我们会自动选中它"）。只在**真改动**的这条
            #   路径上调（同值不写盘那次在函数中部就 return 了，不会走到这里）。
            self._refresh_group_combo_after_write(idx)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def _refresh_group_combo_after_write(self, idx):
        """「定下注释」写盘成功后**当轮**重填分组下拉（§4.1 判据刚成立 ⇒ 界面必须更新）

        · 只在"确实改了数据"的 `_commit_anno` 末尾调用；本方法**只动控件，不写盘**；
        · 整段（含嵌套调用）在 `_anno_filling` 守卫内：`clear()/addItem/setCurrentIndex/
          setCurrentRow` 都会发信号，不挡住就会回流到 `_on_anno_group_changed` /
          `_on_anno_label_changed`；
        · 重填后**保住当前语义**：
            - 该区域 `anno_group == "group_graphed"`（自定义）⇒ 下拉选中 `group_graphed` 项；
            - 否则选中该区域 `anno_group` 对应的项；
            - 注释选择框按（新）分组重填一次，并**选中该区域的 `anno_label`**；
        · **不会引发第二次写盘**：本方法不调 `_commit_anno`；即使某条信号漏过守卫，
          `_commit_anno` 的"同值不重复写"判据也会挡住（自检里断言 save 计数只增 1）。
        """
        prev = self._anno_filling
        self._anno_filling = True
        try:
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            region = {}
            if isinstance(idx, int) and 0 <= idx < len(regs) and isinstance(regs[idx], dict):
                region = regs[idx]
            group = str(region.get('anno_group') or '').strip()
            label = str(region.get('anno_label') or '').strip()
            gg = self._anno_group_graphed()
            combo = self._ctl('region_name_input')
            before = self._list_index_of(combo, gg) >= 0 if combo is not None else False
            # ① 重填分组下拉（内部自带守卫，嵌套安全）
            items = self._fill_anno_group_combo()
            after = gg in (items or [])
            # ② 选中"该区域存的那个分组"（自定义 ⇒ group_graphed）
            target = group or ANNO_GROUP_CELL_TYPE
            if combo is not None and hasattr(combo, 'findText') and hasattr(combo, 'count'):
                try:
                    pos = int(combo.findText(target))
                    if pos < 0:
                        pos = int(combo.findText(ANNO_GROUP_CELL_TYPE))
                    if pos < 0 and int(combo.count()) > 0:
                        pos = 0
                    if pos >= 0:
                        combo.setCurrentIndex(pos)
                except Exception:
                    traceback.print_exc()
            # ③ 注释选择框按新分组重填 + 选中该区域的 anno_label
            values = self._refill_anno_list(self._current_group_text())
            if label and label in values:
                self._select_list_text(self._ctl('region_anno_list'), label)
            else:
                self._select_list_text(self._ctl('region_anno_list'), "")
            self._update_anno_input_visibility()
            if after and not before:
                self._log("分组下拉已刷新（本样本现有自定义注释 ⇒ 新增 group_graphed 项）")
            else:
                self._log("分组下拉已刷新（区域 #%d 的分组=%s，当前选中『%s』）"
                          % ((idx + 1) if isinstance(idx, int) else -1,
                             group or ANNO_GROUP_CELL_TYPE, self._current_group_text()))
        except Exception:
            traceback.print_exc()
        finally:
            self._anno_filling = prev

    # ---- 控件 handler（写盘只发生在"选了具体注释"两处；换分组**不写**）----
    def _on_anno_group_changed(self, index=None):
        """「分组」下拉变了 ⇒ **只重填注释选择框 + 更新待用分组**（★ 一律不写盘，§4.3 表）

        ★★ 2026-09-23 协调者裁定（规则收紧；用户原话是「我们可以选现有的分组和具体注释，
          **选择后**直接变成那组注释」）：
            提交点是「**选了具体注释**」，**不是**「换了个分组」。
          用户真实 `regions.json` 里现在就有大量 `未命名`/`123` —— 只点开下拉看一眼
          就把它改名，等于"用户没做选择时静默改数据"（本项目零容忍）。
          ⇒ 本方法**绝不调用 `_commit_anno`**，只做三件事：
            ① 按新分组重填注释选择框；
            ② 更新"待用分组"（`_anno_pending_group`：没有选中区域时记待用值 /
               "新区域出生时套用"要用它）；
            ③ 若**当前选中区域**已有 `anno_label` 且它就在新分组的去重值里 ⇒ 在列表里
               **仅选中**它（让用户看到"这区域原本是这组的这个注释"），**仍不写盘**。
          ⇒ 写盘只发生在：注释列表里**选中一个值**（`_on_anno_label_changed`）/
            「自定义」新建并点确定（`_on_anno_new_ok_clicked`）；两者仍走**唯一入口**
            `_commit_anno`。
        ★ 回填期间（`_anno_filling`）**直接 return**：`show_region_name` 归位分组时
          也会发 `currentIndexChanged`，不挡住就会在"只是看一眼"的路径上重填/改选择。
        """
        try:
            if self._anno_filling:
                if self._anno_list_rebuilding:
                    self._log("注释选择框正在按新分组重建（`clear()` 的空选择信号）"
                              "→ 本次信号只跳过，**不写盘、不动区域**")
                return
            # ★★ §3.4（v9.3 收窄为**隐形区域**）：选中隐形区域时四个命名控件已被
            #   `_apply_anno_enablement` 禁用；若这条信号仍然到达（程序化驱动 / 布局未同步），
            #   **明确说清为什么不算数**并直接返回：不重填注释框、不更新待用分组、更不写盘。
            if self._reject_anno_on_layer():
                return
            group = self._current_group_text()
            if not group:
                return
            self._anno_pending_group = group
            values = self._refill_anno_list(group)
            old = ""
            idx = self.active_region_index
            try:
                regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
                if idx is not None and 0 <= idx < len(regs) and isinstance(regs[idx], dict):
                    old = str(regs[idx].get('anno_label') or '').strip()
            except Exception:
                traceback.print_exc()
            shown = ("#%d" % (idx + 1)) if isinstance(idx, int) and idx >= 0 else "#?"
            if old and old in values:
                # 仅选中（守卫内 ⇒ 不会触发写盘 handler）
                self._select_list_text(self._ctl('region_anno_list'), old)
                self._log("分组改为 %s：区域 %s 已有注释『%s』且属于新分组 ⇒ 只**选中**它，"
                          "未写盘（要在区域上定下来，请在注释列表里点选一次）"
                          % (group, shown, old))
            else:
                self._select_list_text(self._ctl('region_anno_list'), "")
                if old:
                    self._log("分组改为 %s：区域 %s 的注释『%s』不在新分组现有值里 ⇒ "
                              "注释框未选中，未写盘（切回原分组或重新选一个值才会写）"
                              % (group, shown, old))
                else:
                    self._log("分组改为 %s ⇒ 注释选择框已按该分组重填，**未写盘**"
                              "（在注释列表里点选一个值，才会把（分组,注释）落到区域上）"
                              % group)
            self._update_anno_input_visibility()
        except Exception:
            traceback.print_exc()

    def _on_anno_label_selection_changed(self, *args):
        """`itemSelectionChanged`（无载荷）→ 读出当前项再交给同一个槽"""
        self._on_anno_label_changed()

    def _on_anno_label_changed(self, *args):
        """注释选择框变了 ⇒ 写盘（§4.3）；选中「自定义」⇒ 显示输入框（**先不写盘**）

        ★ 重建期（W1 的 `show_region_name` 清 items / 本文件重填）会发
          `currentRowChanged(-1)`：那**不是**用户的选择 ⇒ 守卫期内直接 return，
          绝不把空 `anno_label` 写进当前区域（也不动它的 `name`）。
        """
        try:
            if self._anno_filling:
                if self._anno_list_rebuilding:
                    self._log("注释选择框正在重建（空选择信号）→ 跳过，不写盘")
                return
            label = self._anno_list_text().strip()
            self._update_anno_input_visibility()
            if label == ANNO_LABEL_CUSTOM:
                self._log("注释：已选『自定义』（分组=%s）→ 等输入框里填好名字并点『确定』"
                          % self._current_group_text())
                return
            self._commit_anno(self._current_group_text(), label, source="注释选择")
        except Exception:
            traceback.print_exc()

    def _on_anno_new_ok_clicked(self, *args):
        """『确定』（或输入框回车）：新建自定义注释（§4.2）

        · `strip()` 后为空 ⇒ **只写日志**（"注释名不能为空"）+ **不落盘**；
        · 与已有值重名 ⇒ **直接选中已有项**（不新建）；
        · 否则 `addItem` 到选择框并**自动选中**、清空并隐藏输入框 —— 选中动作会经
          `_on_anno_label_changed` 走同一个 `_commit_anno` 写盘（仍是唯一入口）。
        """
        try:
            text = self._read_text(self._ctl('region_anno_input')).strip()
            if not text:
                self._log("⚠ 注释名不能为空 → 未新建、未写入（请在输入框里填一个名字再点『确定』）")
                return
            lst = self._ctl('region_anno_list')
            if lst is None or not hasattr(lst, 'addItem'):
                self._warn_once("no_anno_list_new",
                                "region_anno_list 不可用 → 自定义注释无法加入选择框")
                return
            pos = self._list_index_of(lst, text)
            if pos >= 0:
                self._log("注释『%s』已存在 → 直接选中已有项（不新建）" % text)
                self._clear_anno_input()
                prev = self._anno_filling
                self._anno_filling = True
                try:
                    self._select_list_text(lst, text)
                finally:
                    self._anno_filling = prev
                self._update_anno_input_visibility()
                # 选中已有项也走同一个写盘入口（守卫期内不会再自动触发 handler）
                self._commit_anno(self._current_group_text(), text, source="自定义（已存在）")
                return
            prev = self._anno_filling
            self._anno_filling = True
            try:
                try:
                    lst.addItem(str(text))
                except Exception:
                    traceback.print_exc()
                    return
                self._select_list_text(lst, text)
            finally:
                self._anno_filling = prev
            self._clear_anno_input()
            self._update_anno_input_visibility()
            self._log("已新建注释『%s』并自动选中（分组=%s；输入框已清空并隐藏）"
                      % (text, self._current_group_text()))
            self._commit_anno(self._current_group_text(), text, source="自定义新建")
        except Exception:
            traceback.print_exc()

    # 编辑模式的用户可读说明：切换时**必须说清"现在能干什么、怎么退出"**
    # ★ 这个 dict 在**本文件**（bind）里，不是 W1 的布局文件 —— 协调者说 mask 文案由 W1 加，
    #   但 W1 没有这个 dict 可加（他改我的文件才需要动它）⇒ 由我补齐，并回报协调者。
    EDIT_MODE_HINTS = {
        # ★★ 2026-09-23「选择模式」文案（`_d_spec_select_mode.md` §2，**冻结**）
        EDIT_MODE_SELECT: ("选择模式：点独有的边或锚点选中该区域；点锚点可拖动改形状；"
                           "点共享边/共享锚点会同时选中多个区域但不能编辑"),
        EDIT_MODE_VISIBLE: ("可见区域模式：画出的多边形是**范围层** —— "
                            "**罩住的区域其边界会画虚线**（v9.3 起它**自己也会出图**："
                            "带名字，是一个可画的标注单元，同时仍决定普通区域是否入选）；"
                            "成图时还要再被『隐形区域』罩住才显示；"
                            "再点一次『可见区域』回到绘制模式"),
        EDIT_MODE_MASK: ("隐形区域模式：画出的多边形是**范围层** —— "
                         "它自己不出图，只决定**哪些区域的虚线能出现在最终成图里**"
                         "（成图 = 被『可见区域』罩住 ∧ 被『隐形区域』罩住；"
                         "两者都没画 = 照旧全画）；"
                         "再点一次『隐形区域』回到绘制模式"),
        EDIT_MODE_LABEL: ("编辑标签模式：点区域可选中；"
                          "注释标签在任何模式下都能直接拖动"),
        EDIT_MODE_DRAW: "绘制模式：左键加点、双击闭合多边形",
    }

    def bind_edit_mode_buttons(self):
        """★ Phase 3①：`编辑边`/`编辑标签` 两个 checkable 按钮 → 画布 `set_edit_mode(mode)`

        ★★ 这原来是一条**真断线**（协调者离屏真点实测）：两个按钮点了自己会
          `checked = True`（Qt 自己翻转），但**没有任何调用方去读它们** ——
          全仓库 `edit_mode_from_buttons` / `set_edit_mode_buttons` 只命中 W1 布局文件里
          **定义处**，一个调用方都没有。
          后果**不是**"少个便利功能"：画布**永远停在 `draw`** ⇒ 用户**没有任何入口**
          进 `edges` 模式 ⇒ Phase 3① 的"手工隐藏/显示单条边"（`edge_override`）
          **在 UI 上完全不可达**，`_on_region_edges_changed` 那条链写得再对也永不触发。

        ★ 模式取自 **W1 的 `edit_mode_from_buttons()`**（不在本文件里 `if` 两个按钮 ——
          那是第二份真相源，按钮语义以后变了两边就会漂移）。
        ★★ 但**必须把"是哪个按钮"带进 handler**（连接处用默认参数 `m=mode` 绑定）：
          我第一版只连 handler、进去再读按钮，**离屏真点实测直接失效** ——
          按钮是**独立** checkable（不在同一 `QButtonGroup`），点『编辑标签』时
          『编辑边』**还勾着**，而 helper 固定优先返回 `edges`
          ⇒ 我把刚勾上的 label 又按回 edges，**用户永远切不到 label**。

        ★ 2026-09 新增 **`visible`（可见区域）**，并把 **`mask` 文案改「隐形区域」**：
          按钮名仍**由模式名推导**（`btn_region_edit_<mode>`，冻结接口就是
          `btn_region_edit_visible` / `btn_region_edit_mask`），**不写死按钮名列表**。
          模式串以**冻结接口**为准；按钮的"谁被勾上"语义仍然只由 W1 的
          `edit_mode_from_buttons()` / `set_edit_mode_buttons()` 解释（本文件不 if 按钮）。

        ★ `edges`（"编辑边"）已**彻底退休**（用户纠正：那个按钮真正要的是「可见区域」）
          ⇒ 这里不再枚举它，`warn=False` 那套"可缺省"开关也随之删掉 ——
          剩下三个模式都是**活的冻结接口**，按钮缺失就是**真缺陷**，必须报警。

        ★★ 2026-09-23：**`select`（选择模式）纳入同一个循环元组**（规格 `_d_spec_select_mode.md`
          §2/§7）—— 按钮名仍**由模式名推导** `btn_region_edit_<mode>`（= `btn_region_edit_select`），
          **没有另写一套连接代码**。互斥（`set_edit_mode_buttons`）/`_reassert_edit_mode()`/
          常驻文案（`MODE_LABELS`）三处都只认 W1 布局里的 `MODE_BUTTONS`/`MODE_LABELS`，
          布局已把 `select` 加进那两张表 ⇒ 自动生效，本文件**无第二份模式清单**
          （唯一需要同步的就是下面这个元组与 `EDIT_MODE_HINTS`）。
        """
        try:
            for mode in (EDIT_MODE_SELECT, EDIT_MODE_VISIBLE, EDIT_MODE_MASK, EDIT_MODE_LABEL):
                name = "btn_region_edit_%s" % mode
                btn = self._ctl(name)
                if btn is None:
                    self._warn_once("no_%s" % name,
                                    "布局未提供 %s → 该编辑模式无法进入" % name)
                    continue
                sig = getattr(btn, 'toggled', None)
                if sig is None or not hasattr(sig, 'connect'):
                    self._warn_once("no_toggled_%s" % name,
                                    "%s 上没有 toggled 信号 → 编辑模式切不了（需要 W1 补）"
                                    % name)
                    continue
                sig.connect(lambda checked=False, m=mode:
                            self._on_edit_mode_button_toggled(m, checked))
        except Exception:
            traceback.print_exc()

    def _on_edit_mode_button_toggled(self, mode, checked=True):
        """某个编辑按钮 `toggled` → 互斥收口 + 压给画布 + **留痕**

        Args:
            mode: 发信号的按钮代表的模式（`edges`/`label`，由连接处的默认参数带进来）
            checked: 该按钮**当前**是否勾上（`toggled(bool)` 的载荷）

        ★ 目标模式 = **刚勾上的那个按钮**；取消勾选（`checked=False`）→ 回到 `draw`。
          为什么不能只读 `edit_mode_from_buttons()`：点 B 时 A 还勾着 ⇒ helper 固定
          返回 A（优先 `edges`）⇒ **切不过去**（离屏实测：点『编辑标签』毫无反应）。
        ★ 互斥：`set_edit_mode_buttons(target)` 把另一个按钮取消勾选。两个都勾着而画布
          只有一种模式，用户会以为"坏了"。
        ★ `setChecked()` 会**反过来再发 `toggled`** ⇒ `_edit_mode_syncing` 挡掉内层，
          否则同一次点击会重复调画布、重复写日志。
        ★ 最终仍以 W1 的 `edit_mode_from_buttons()` 为**准**（收口后按钮已一致），
          本文件不成为"按钮语义"的第二份真相源。
        """
        if self._edit_mode_syncing:
            return
        self._edit_mode_syncing = True
        try:
            target = str(mode) if checked else EDIT_MODE_DRAW
            setter = getattr(self.ui, 'set_edit_mode_buttons', None)
            if callable(setter):
                setter(target)                       # 互斥收口
            else:
                self._warn_once("no_set_edit_mode_buttons",
                                "布局未提供 set_edit_mode_buttons() → 两个按钮可能同时选中")
            getter = getattr(self.ui, 'edit_mode_from_buttons', None)
            mode_final = target
            if callable(getter):
                mode_final = str(getter() or target)
            else:
                self._warn_once("no_edit_mode_helper",
                                "布局未提供 edit_mode_from_buttons() → 编辑模式切不了"
                                "（需要 W1 补这个 helper）")
            if not self._call_canvas(CANVAS_SET_EDIT_MODE, mode_final):
                return
            self._log(self.EDIT_MODE_HINTS.get(mode_final, "编辑模式 = %s" % mode_final))
            # ★★ 2026-09-24 用户需求「可见区域的默认区域颜色 = 白色」（只影响**新画的**）：
            #   调色板**跟随模式**。顺序**必须**是"先读切换前的模式 → 再更新
            #   `_last_edit_mode` → 最后做调色板切换"：
            #     · 切换动作只在画布**真的**接受了新模式之后才做（上面那行 return 已经挡掉失败）；
            #     · `_last_edit_mode` 先落地 ⇒ 即使调色板那步内部出异常（它自己兜住并留痕），
            #       下一次切换也不会因为"前一个模式"读到旧值而误判进入/离开。
            prev_mode = self._last_edit_mode
            self._last_edit_mode = mode_final
            self._apply_visible_palette_switch(prev_mode, mode_final)
        except Exception:
            traceback.print_exc()
        finally:
            self._edit_mode_syncing = False

    def _sync_last_edit_mode_from_canvas(self):
        """bind 初始化：把 `_last_edit_mode` 对齐**画布当前模式**（取不到 → 保持 `draw`）

        ★ 为什么需要：`_last_edit_mode` 是"切换前的模式"的判据（进入/离开可见区域
          决定要不要动调色板）。它的初值取自画布 `edit_mode()`（W1 的只读接口），
          **不是**按钮态 —— 画布才是模式的真相源（`_reassert_edit_mode` 也是把按钮态
          压给画布）。读不到就按 `draw` 处理并**留痕**，绝不假装读到了。
        ★ 本方法**零副作用**：不调 `set_edit_mode`、不碰调色板、不写任何区域、不落盘。
        """
        try:
            c = self._canvas()
            fn = getattr(c, 'edit_mode', None) if c is not None else None
            if not callable(fn):
                self._warn_once("no_canvas_edit_mode",
                                "画布未提供 edit_mode() → 「切换前的编辑模式」初值按 draw 处理"
                                "（只影响进入/离开可见区域时调色板的还原判断）")
                return
            mode = str(fn() or EDIT_MODE_DRAW)
            self._last_edit_mode = mode
            self._log("编辑模式初值（画布 edit_mode()）= %s" % mode)
        except Exception:
            traceback.print_exc()
            self._log("⚠ 读画布 edit_mode() 失败 → 「切换前的编辑模式」初值按 draw 处理")

    def _apply_visible_palette_switch(self, prev_mode, mode_final):
        """编辑模式切换 ⇒ **调色板跟随**（只影响"下一个新画的多边形"，绝不改已有区域）

        ## 需求（2026-09-24 用户）：可见区域的**默认区域颜色 = 白色**
          · **进入** `visible`（前一个模式 ≠ visible）：记住当前调色板色
            （`self._pre_visible_color`）→ 静默切到 `#FFFFFF`；
          · **离开** `visible`（前一个是 visible，现在不是）：**仅当**当前调色板色仍是
            那个白（= 用户没在可见区域模式下自己改过色）才还原 `_pre_visible_color`；
            用户自己改过 ⇒ **保留用户的选择**（不抢用户的输入）；
          · 其它情况（visible → visible；非 visible → 非 visible）**不动调色板**。

        ## 为什么必须"静默"切（本方法的核心风险点）
          `StyledColorPalette.set_color()` 会 **emit `color_changed`**
          （`gui_styles.py:3870-3877`），而它接的是 `_push_active_style` —— 该方法在
          **有选中区域**时会写回该区域**并落盘**。若不做抑制，用户一切到「可见区域」
          就会把当前选中区域的颜色刷成白色（正是 D 系列"程序化回填写盘"事故）。
          ⇒ 切色一律走 `_set_palette_color_silent()`（置 `_palette_programmatic`，
          `_push_active_style` 在该标志下**只做实时预览**然后 return）。

        ## 本方法**绝不**做的事
          · 不改任何已有区域的字段（不碰 `regs[idx]`、不 `set_sample_regions`）；
          · 不落盘（不调 `_persist`/`save_regions`）；
          · 不 emit 任何区域几何变化信号（不调 `set_regions`）。
          唯一对画布的动作是 `set_active_style`（= "下一个新画的多边形样式"）。
        """
        try:
            was = (str(prev_mode or "") == EDIT_MODE_VISIBLE)
            now = (str(mode_final or "") == EDIT_MODE_VISIBLE)
            # 白：分析层本轮新增的常量；它还没落地时用字面量兜底（W3 并行加）
            white = getattr(SREG, "DEFAULT_VISIBLE_REGION_COLOR", "#FFFFFF")
            if now and not was:
                # ---- 进入可见区域：记住旧色 → 静默切白 ----
                pre = self._read_palette_color(self._ctl('region_color_palette'),
                                               SREG.DEFAULT_REGION_COLOR)
                self._pre_visible_color = str(pre)
                if self._set_palette_color_silent(white, why="进入可见区域模式"):
                    self._log("可见区域：调色板已切到默认白色（%s）——"
                              "只影响新画的可见区域，已有区域不改" % white)
            elif was and not now:
                # ---- 离开可见区域：只有"还是那个白"才还原（用户改过就保留）----
                pre = getattr(self, '_pre_visible_color', None)
                if not pre:
                    return
                cur = str(self._read_palette_color(self._ctl('region_color_palette'), "") or "")
                if cur.strip().upper() == str(white).strip().upper():
                    if self._set_palette_color_silent(pre, why="离开可见区域模式"):
                        self._log("已离开可见区域：调色板还原为 %s" % pre)
                else:
                    self._log("已离开可见区域：调色板保持用户自选色 %s（**不还原**为 %s ——"
                              "用户在可见区域模式下自己改过色）" % (cur, pre))
        except Exception:
            traceback.print_exc()
            self._log("⚠ 编辑模式切换时调色板跟随失败（模式本身已切换成功；"
                      "调色板保持当前值，绝不写任何已有区域）")

    def _reassert_edit_mode(self, reason=""):
        """把**按钮当前选中态**重新压给画布一次（幂等；**不复位**）

        ★ 为什么复位/不复位由我定：**不复位**。理由：
          · 用户切样本（`region_sample_list`）时通常还在做同一类编辑
            （逐个样本手工隐藏同一条边是常见操作），被静默踢回 `draw` 会让他
            下一次点击变成"加点"而不是"选边" —— 而且画布已经变了、他不知道为什么；
          · 按钮是常驻控件、跨样本不重建，所以"用户的模式选择"本来就该保持；
          · 但**必须把按钮态重新压给画布**：画布可能因为重建/重进页面回到默认
            `draw`，而按钮还显示着 `edges` ⇒ "看着选中却没反应"，正是本轮的病根。
        ★ 每次刷新都**留一行日志**说明当前模式（契约不许静默）。
        """
        try:
            getter = getattr(self.ui, 'edit_mode_from_buttons', None)
            if not callable(getter):
                return
            mode = str(getter() or EDIT_MODE_DRAW)
            self._call_canvas(CANVAS_SET_EDIT_MODE, mode)
            self._log("当前编辑模式 = %s（%s 时**不复位**，避免切样本被踢出编辑模式）"
                      % (mode, reason or "刷新"))
        except Exception:
            traceback.print_exc()

    def _label_frame_checked(self):
        """读 `chk_label_frame`（**全局**"注释加圆角矩形外框"开关）→ bool

        ★★ 这原来是一条**真断线**（协调者 grep + AST 审计确认）：`chk_label_frame`
          全仓库**只有创建处、没有任何读取方** ⇒ `export_outline_json(label_frame=None)`
          永远拿到默认 `None` ⇒ 回退到逐区域 `label_frame`（默认 False）
          ⇒ **勾选框打了勾也不会有外框**。W3 那次真实渲染 `labels_with_frame = 0`
          就是这个原因（**不是**"向后兼容路径生效"）。
        ★ 控件缺失/不可读 → `False` + `_warn_once` 留痕：静默就是"勾了没反应"复发。
        """
        try:
            w = self._ctl('chk_label_frame')
            if w is None:
                self._warn_once("no_chk_label_frame",
                                "布局未提供 chk_label_frame → 注释外框开关不可用"
                                "（本次按『关』处理）")
                return False
            fn = getattr(w, 'isChecked', None)
            if not callable(fn):
                self._warn_once("chk_label_frame_no_isChecked",
                                "chk_label_frame 没有 isChecked() → 本次按『关』处理")
                return False
            return bool(fn())
        except Exception:
            traceback.print_exc()
            return False

    def _label_frame_color(self):
        """读「注释外框颜色」调色板 → `"#RRGGBB"`；控件不存在/不可读 → `""`（= 不传）

        ★ 交付给 R 的是 **`geom_label` 那个圆角矩形底框的填充色**
          （R 侧默认写死 `fill = "#FFFFFFCC"`；给了颜色就覆盖它）。
        ★ 属性名由协调者**冻结**：`region_label_frame_color_palette`（W1 在建）。
        ★ 告警**只打一次**（`_warn_once`）：这个控件只在"勾了注释外框"时才用得到，
          若每次出图都刷一条"未提供"，会把真正的问题淹掉。
        ★ 返回 `""` 时**不写** `labels[].frame_color` ⇒ R 用默认白底（向后兼容）。
        """
        try:
            w = self._ctl('region_label_frame_color_palette')
            if w is None:
                self._warn_once("no_label_frame_color_palette",
                                "布局未提供 region_label_frame_color_palette → "
                                "注释外框颜色不可调（本次用 R 默认白底）")
                return ""
            col = self._read_palette_color(w, "")
            col = str(col or "").strip()
            if not col:
                self._warn_once("label_frame_color_empty",
                                "region_label_frame_color_palette 读不出颜色 → "
                                "本次用 R 默认白底")
                return ""
            return col
        except Exception:
            traceback.print_exc()
            return ""

    def bind_label_frame_checkbox(self):
        """★ Phase 4⑤：`chk_label_frame` 变化 → **留痕告知"下次出图生效"**

        ★ 为什么只记日志、不立刻重绘：它改的是 **R 侧出图**的样式
          （`export_outline_json` → R 给注释画圆角外框），而**画布本来就不画这个外框**
          ⇒ 屏幕上不会有任何变化。不吭声用户必然以为"勾了没用"（这正是它断线至今
          没人发现的原因之一）。
        """
        try:
            w = self._ctl('chk_label_frame')
            if w is None:
                self._warn_once("no_chk_label_frame",
                                "布局未提供 chk_label_frame → 注释外框开关不可用")
                return
            hooked = False
            for sig_name in ('toggled', 'stateChanged'):
                sig = getattr(w, sig_name, None)
                if sig is not None and hasattr(sig, 'connect'):
                    sig.connect(self._on_label_frame_toggled)
                    hooked = True
                    break
            if not hooked:
                self._warn_once("label_frame_sig",
                                "chk_label_frame 上没有 toggled/stateChanged → "
                                "勾选后不会有任何提示")
        except Exception:
            traceback.print_exc()

    def _on_label_frame_toggled(self, *args):
        """勾选框变化 → 只读它自己的状态（**不解析载荷**）并留痕"""
        try:
            on = self._label_frame_checked()
            self._log("注释圆角外框 = %s（**下次出图生效**：画布不画这个外框，"
                      "点『确认』重绘后才会看到）" % ("开" if on else "关"))
        except Exception:
            traceback.print_exc()

    def bind_style_controls(self):
        """右侧样式控件改动 → 即时预览（`set_active_style`）

        ★ 名字框**不**连 textChanged：每敲一个字就重画面布没必要；
          名字在"画完多边形"与"确认"两处读一次即可。
          但颜色/虚线/字号改了就立刻看得见，这才是"实时预览"的价值。
        """
        try:
            pairs = (('region_color_palette', None),
                     ('region_dash_width_input', None),
                     ('region_dash_gap_input', None),
                     ('region_font_size_input', None),
                     ('region_font_color_palette', None))
            for name, _ in pairs:
                w = self._ctl(name)
                if w is None:
                    self._warn_once("style_%s" % name, "布局未提供 %s" % name)
                    continue
                connected = False
                # ★ 候选顺序 = "真名优先，Qt 常规名兜底"：
                #   · 数字输入 `StyledNumberInput` 的真信号是 **`value_changed`（下划线式）**；
                #     我原来只列了 Qt 的 `valueChanged`（驼峰），**三个数字控件全是死的**
                #     （虚线粗细/间距/字号调不动）—— 是下面那条 ⚠ 警告把它暴露出来的，
                #     所以那条警告**保留**：它立功了，修好后应当自然消失。
                #   · 调色板 `StyledColorPalette` 的真信号是 **`color_changed(str)`**。
                for sig_name in ('value_changed',        # ← StyledNumberInput 真名
                                 'color_changed',        # ← StyledColorPalette 真名
                                 'valueChanged', 'currentColorChanged', 'colorChanged',
                                 'currentIndexChanged', 'clicked'):
                    sig = getattr(w, sig_name, None)
                    if sig is not None and hasattr(sig, 'connect'):
                        sig.connect(self._push_active_style)
                        connected = True
                        break
                if not connected:
                    self._warn_once("style_sig_%s" % name,
                                    "%s 上没有可连的信号 → 改动不会实时预览" % name)
            # ★ §15.3 圆角控件：单独接（它改的是**选中区域的字段**，不是全局样式）
            cr = self._ctl('region_corner_radius_input')
            if cr is None:
                self._warn_once("no_corner_radius",
                                "布局未提供 region_corner_radius_input → 圆角不可调")
            else:
                hooked = False
                for sig_name in ('value_changed', 'valueChanged'):
                    sig = getattr(cr, sig_name, None)
                    if sig is not None and hasattr(sig, 'connect'):
                        sig.connect(self._on_corner_radius_changed)
                        hooked = True
                        break
                if not hooked:
                    self._warn_once("corner_radius_sig",
                                    "%s 上没有可连的信号 → 圆角改动不会生效" % 'region_corner_radius_input')
        except Exception:
            traceback.print_exc()

    def bind_action_buttons(self):
        try:
            pairs = (('btn_region_confirm', self._on_confirm_clicked),
                     ('btn_region_undo', self._on_undo_clicked),
                     ('btn_region_delete', self._on_delete_clicked),
                     ('btn_region_clear', self._on_clear_clicked),
                     # §14.2 手动重试导出坐标表 / §14.6 下一个未画样本
                     ('btn_region_dump', self._on_dump_clicked),
                     ('btn_region_next_unpainted', self._on_next_unpainted_clicked))
            for name, handler in pairs:
                btn = self._ctl(name)
                if btn is not None and hasattr(btn, 'clicked'):
                    btn.clicked.connect(handler)
                else:
                    self._warn_once("%s" % name, "布局未提供 %s → 该按钮未绑定" % name)
        except Exception:
            traceback.print_exc()

    def bind_region_list(self):
        """★ `region_list_widget` 的行选择 → bind（**此前全仓库无人接**）

        ★★ 这是个**真缺陷**（协调者实测）：右侧面板标题写着「已画区域（选中可删）」，
          但没有任何代码把列表选择接到 bind ⇒ 用户按提示点一行、再点『删除选中区域』，
          得到的是「没有选中的区域 → 未删除」：**能点、没反应、没提示**。
          （全仓库只有 `region_sample_list` 接过选择信号。）
        ★ 信号优先 `currentRowChanged`（行语义最直接）；老式列表没有它就退
          `itemSelectionChanged`；都没有则**留痕**，绝不静默。
        """
        try:
            lst = self._ctl('region_list_widget')
            if lst is None:
                self._warn_once("no_region_list_widget",
                                "布局未提供 region_list_widget → 区域列表点选无效（无法选中区域）")
                return
            if hasattr(lst, 'currentRowChanged'):
                lst.currentRowChanged.connect(self._on_region_row_changed)
            elif hasattr(lst, 'itemSelectionChanged'):
                lst.itemSelectionChanged.connect(self._on_region_item_selection_changed)
            else:
                self._warn_once("no_region_list_signal",
                                "region_list_widget 没有 currentRowChanged/itemSelectionChanged "
                                "→ 区域列表点选无效（需要 W1 补信号）")
        except Exception:
            traceback.print_exc()

    def _on_region_item_selection_changed(self, *args):
        """`itemSelectionChanged`（无载荷）→ 读出当前行再交给同一个槽"""
        row = -1
        try:
            lst = self._ctl('region_list_widget')
            if lst is not None and hasattr(lst, 'currentRow'):
                row = int(lst.currentRow())
        except Exception:
            traceback.print_exc()
            row = -1
        self._on_region_row_changed(row)

    def _on_region_row_changed(self, row):
        """区域列表行选择 → `active_region_index` + 画布高亮 + 名字框回填

        ## ★ 重入守卫（必须）
          `_refresh_region_list()` 会 `clear()`，而 `clear()` 会发 `currentRowChanged(-1)`
          ⇒ 不忽略它，**每刷新一次就把用户的选中清掉**（`_persist` 之后就会刷新，很频繁）。
          守卫标志由 `_refresh_region_list()` 与 `_sync_region_list_selection()` 用
          `try/finally` 设置/清除，本槽在守卫期内**直接 return**。
        ## ★ 不碰画布的私有字段
          同步高亮只调 W1 的**公开 setter** `set_selected_index`；拿不到就跳过并留痕
          （绝不写 `c._selected_index` —— 那是私有实现，W1 一改就静默失效）。
        ## 语义
          · `row < 0`（取消选择）⇒ **只**把 `active_region_index = -1`，**不清画布、不删任何东西**；
          · `row` 合法 ⇒ 设 `active_region_index`、画布高亮、`show_region_name` 回填、记日志。
        """
        if self._region_list_rebuilding:
            return
        try:
            if row is None:
                return
            try:
                row = int(row)
            except (TypeError, ValueError):
                return
            regions = SREG.get_sample_regions(self.regions_data, self.current_sample)
            if row < 0 or not (0 <= row < len(regions)):
                if self.active_region_index != -1:
                    self._log("区域列表：已取消选中（当前编辑的区域 → 无）")
                self.active_region_index = -1
                # ★ 列表"取消选中"= 单选语义的清空 ⇒ 同步清掉多选镜像（§3.3）
                self._multi_selected_indices = []
                self._apply_anno_enablement(-1)
                return
            self.active_region_index = row
            # ★★ 区域列表的行选中 = **单选语义**（下面调的就是 `set_selected_index(row)`）
            #   ⇒ 多选镜像立刻收成 `[row]`。这样画布紧接着发的 `regions_selected([row])`
            #   只会把它再写成同一份；即使 W1 那条信号没发，可用态也不会被旧的多选卡住。
            self._multi_selected_indices = [row]
            name = str((regions[row] or {}).get("name") or "")
            # ---- 画布同步高亮（公开 setter，防御式）----
            c = self._canvas()
            setter = getattr(c, 'set_selected_index', None) if c is not None else None
            if callable(setter):
                try:
                    setter(row)
                except Exception:
                    traceback.print_exc()
            else:
                self._warn_once("no_set_selected_index",
                                "画布未提供 set_selected_index() → 列表选中不会同步高亮画布"
                                "（会跳过；**不会**去写画布的私有字段。需要 W1 补这个公开 setter）")
            # ---- 名字框回填（布局确有 `show_region_name`；防御式取）----
            #   ★ v2（§3/§4.5）：W1 的 `show_region_name` **只**按 `anno_group` 归位分组下拉、
            #     并把注释选择框 `clear()`（**清 items**）；"按分组填可选注释值 + 选中该区域的
            #     anno_label"归本文件 ⇒ **必须在它之后**再同步一次（否则刚填好就被它清空）。
            #   ★★ `clear()` 会发 `currentRowChanged(-1)`/`itemSelectionChanged`
            #     ⇒ 必须整段套在**重建守卫**里，否则那个"空选择"信号会走到
            #     `_on_anno_label_changed`（本会话栽过"信号重入把模型改坏"的坑）。
            shower = getattr(self.ui, 'show_region_name', None)
            if callable(shower):
                prev_fill = self._anno_filling
                self._anno_filling = True
                self._anno_list_rebuilding = True
                try:
                    shower(row)
                except Exception:
                    traceback.print_exc()
                finally:
                    self._anno_filling = prev_fill
                    self._anno_list_rebuilding = False
            else:
                self._warn_once("no_show_region_name",
                                "布局未提供 show_region_name() → 分组下拉的回填由 bind 兜底"
                                "（需要 W1 补这个接口）")
            self._sync_anno_controls(row)
            self._log("选中区域 #%d『%s』（列表）" % (row + 1, name))
        except Exception:
            traceback.print_exc()

    def _sync_region_list_selection(self, idx):
        """画布 → 列表：把 `region_list_widget` 当前行指到 `idx`（守卫 + 值不同才设）

        ★ 用与 `_refresh_region_list()` **同一个**守卫：`setCurrentRow` 会发
          `currentRowChanged`，不挡住就会绕回 `_on_region_row_changed`
          ⇒ 重复日志、重复调画布 setter（用户看到日志刷两遍）。
        ★ 只在"当前行真的 != idx"时才设：无谓的信号 + 列表滚动跳变都省掉。
        """
        try:
            lst = self._ctl('region_list_widget')
            if lst is None or not hasattr(lst, 'setCurrentRow') or not hasattr(lst, 'currentRow'):
                return
            if int(lst.currentRow()) == int(idx):
                return
            self._region_list_rebuilding = True
            try:
                lst.setCurrentRow(int(idx))
            finally:
                self._region_list_rebuilding = False
        except Exception:
            traceback.print_exc()

    def _on_next_unpainted_clicked(self):
        """跳到下一个**未画区域**的样本并重灌画布；全画完了就明确提示"""
        try:
            samples = self._sample_ids()
            if not samples:
                self._log("没有样本可跳（数据集样本清单为空）")
                return
            start = samples.index(self.current_sample) + 1 if self.current_sample in samples else 0
            order = list(samples[start:]) + list(samples[:start])   # 环回一圈
            for sid in order:
                if SREG.painted_region_count(self.regions_data, sid) <= 0:
                    self._log("跳到下一个未画样本：%s" % sid)
                    self._select_sample_in_list(sid)
                    self._on_sample_row_changed(self._row_of_sample(sid))
                    return
            self._log("所有样本都已画区域（共 %d 个）—— 没有未画的样本了" % len(samples))
        except Exception:
            traceback.print_exc()

    def _row_of_sample(self, sid):
        try:
            lst = self._ctl('region_sample_list')
            if lst is None or not hasattr(lst, 'count'):
                return -1
            for i in range(int(lst.count())):
                it = lst.item(i)
                if it is None:
                    continue
                val = None
                try:
                    val = it.data(Qt.UserRole)
                except Exception:
                    pass
                if str(val or it.text()).endswith(str(sid)) or str(val or "") == str(sid):
                    return i
            return -1
        except Exception:
            traceback.print_exc()
            return -1

    def fill_signature_suggestions(self):
        """**v2 起退休**：9 个 signature 名不再灌进 `region_name_input`

        ★ 历史：`region_name_input` 曾是**可编辑**下拉框，这里把 9 个 signature 当
          "名字建议"灌进去（契约 §13.3 第 3 条）。v2（`_d_spec_region_naming_v2.md` §3）
          起它改成**不可编辑的「分组」下拉**，items 由 `_fill_anno_group_combo()` 按
          §4.1 逐样本填 ⇒ 再灌 signature 会把这四个冻结项污染掉。
        ★ 方法名保留（历史探针可能按名字调用），现在**只**转调分组下拉填充并留一行痕。
          `SIGNATURE_SUGGESTIONS` 常量仍在 W1 的布局里（不许删，别的探针引用它）。
        """
        try:
            self._log("名字建议（9 个 signature）已随 v2 两级命名退休 → "
                      "`region_name_input` 现在按 §4.1 填分组项")
            self._fill_anno_group_combo()
            self._refill_anno_list(self._current_group_text())
            self._update_anno_input_visibility()
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 取数
    # ==================================================================
    def _top_bind(self):
        try:
            return getattr(self.parent, 'spatial_top_bind', None)
        except Exception:
            traceback.print_exc()
            return None

    def _resolve_analysis(self):
        try:
            top = self._top_bind()
            if top is None:
                self._log("无法获取空转顶层 bind（spatial_top_bind 不存在）")
                return None
            an = getattr(top, 'analysis', None)
            if an is None:
                self._log("顶层 bind 上没有 analysis 实例")
                return None
            self.analysis = an
            return an
        except Exception:
            traceback.print_exc()
            return None

    def _dataset_name(self):
        try:
            an = self.analysis
            if an is not None and getattr(an, 'dataset_name', None):
                return an.dataset_name
            top = self._top_bind()
            if top is not None:
                a2 = getattr(top, 'analysis', None)
                if a2 is not None:
                    return getattr(a2, 'dataset_name', None)
            return None
        except Exception:
            traceback.print_exc()
            return None

    def _rds_path(self):
        """成品 .rds 路径（优先 W3 的 `artifact_info['path']`，再退 scan 目录）"""
        try:
            an = self.analysis
            info = getattr(an, 'artifact_info', None) if an is not None else None
            if isinstance(info, dict):
                p = str(info.get('path') or "")
                if p and os.path.isfile(p):
                    return p
            d = SREG._spatial_main_dir()
            if d and self.dataset:
                cand = os.path.join(d, "%s.rds" % self.dataset)
                if os.path.isfile(cand):
                    return cand
            return ""
        except Exception:
            traceback.print_exc()
            return ""

    def _sample_ids(self):
        """样本清单（优先用已缓存的，其次从图集清单读）"""
        if self.samples:
            return list(self.samples)
        try:
            return list((RA.list_review_figures(self.dataset) or {}).get("samples") or [])
        except Exception:
            traceback.print_exc()
            return []

    # ==================================================================
    # 进入页面的钩子
    # ==================================================================
    def on_page_entered(self):
        """`page_intersect` 在跳转末尾调用（可选钩子）

        ★ 幂等键 = `(dataset, regions_version)`：区域文件没被动过就不重填，
          否则每次进页面都会重灌画布（用户正在画的多边形会被清掉）。
        """
        try:
            dataset = self._dataset_name()
            if not dataset:
                self._log("【绘制区域】进入页面，但顶层页尚未加载数据集 → 请先回主页加载")
                return
            rv = self._regions_version(dataset)
            key = (dataset, rv)
            if key == getattr(self, '_entered_key', None):
                self._log("【绘制区域】进入页面（%s / 区域版本 %s 未变，跳过重填）"
                          % (dataset, rv))
                return
            self._entered_key = key
            self.refresh_all(reason="进入页面（on_page_entered）")
        except Exception:
            traceback.print_exc()

    @staticmethod
    def _regions_version(dataset):
        """regions.json 的廉价版本指纹（(mtime_ns, size)；文件不存在 → ('none', 0)）"""
        try:
            st = os.stat(SREG.regions_path_for(dataset))
            return (int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return ("none", 0)

    # ==================================================================
    # 主刷新
    # ==================================================================
    def refresh_all(self, reason=""):
        try:
            self._log("=" * 40)
            self._log("【绘制区域】%s" % (reason or "刷新"))
            an = self._resolve_analysis()
            if an is None:
                self._set_empty_hint("无法获取空转数据（顶层页未就绪）")
                return
            dataset = self._dataset_name()
            if not dataset:
                self._log("顶层页尚未加载数据集 → 请先回主页加载数据集")
                self._set_empty_hint("请先在主页加载数据集")
                return
            self.dataset = dataset
            self._log("数据集: %s" % dataset)

            # ★ 顺序**必须**是"先载区域文件 → 再填样本列表"（协调者实测发现的 bug）：
            #   `_fill_sample_list` 内部就是**从 `self.regions_data` 数**"已画几区"
            #   （`painted_region_count(self.regions_data, sid)`）。
            #   原来先填列表、后载区域 ⇒ 带着已有 regions.json 打开 App 时，
            #   **19 项全显示 `⚠ 未画`**（列表读的是上一次的空数据）。
            # ① 区域文件（容错读；首次使用没有属正常）
            self.regions_data = SREG.load_regions(dataset)
            for issue in (self.regions_data.get("_issues") or []):
                self._log("区域文件：%s" % issue)
            n_region_samples = len((self.regions_data.get("samples") or {}))
            self._log("区域文件已载入：覆盖 %d 个样本" % n_region_samples)

            # ② 样本清单（**在载入区域之后**填，才能显示正确的 `✅ 已画 N 区`）
            samples = self._sample_ids()
            self.samples = list(samples)
            self._fill_sample_list(samples)

            # ③ 当前样本
            if self.current_sample not in samples:
                self.current_sample = samples[0] if samples else None
            self._select_sample_in_list(self.current_sample)

            # ④ 坐标表 + 区域 → 画布
            self.reload_current_sample(reason="刷新")

            # ⑤ ★ Phase 3①：编辑模式**不复位**（理由见 `_reassert_edit_mode` docstring），
            #    但把按钮态重新压给画布一次，保证"按钮显示什么 = 画布是什么"
            #    （画布重建/重进页面会回默认 `draw`，按钮却还显示 `edges`
            #     ⇒ "看着选中却没反应"，正是本轮那条断线的表现）。
            self._reassert_edit_mode(reason=reason or "刷新")
        except Exception:
            traceback.print_exc()

    def reload_current_sample(self, reason=""):
        """读当前样本的 spots.csv 与 regions → 灌画布（**缺文件如实提示，不抛**）

        ★ §14.2：坐标表**缺失时自动在后台生成**（绝不卡界面、绝不静默）。
        """
        try:
            # ★ 切样本前先把"合并中"的样式改动补落一次。安全依据：`_persist` 写的是
            #   **整份 `regions_data`**（含所有样本），而样式改动一产生就已写进该字典，
            #   所以任何时刻 flush 都不会把改动算到别的样本头上。
            self._flush_style_pending()
            if not self.dataset or not self.current_sample:
                self._set_empty_hint("尚未确定样本")
                return
            self.spots, self.spots_error = SREG.load_spots(self.dataset, self.current_sample)
            if self.spots_error:
                # ★ 坐标表可能还没生成（换数据集/清缓存/换机器）—— 如实显示 + **自动补生成**
                self._set_empty_hint(self.spots_error)
                self._log("⚠ %s" % self.spots_error)
                self._maybe_auto_dump()
            else:
                self._set_empty_hint("")
                self._log("样本 %s：spot 数 = %d（%s）"
                          % (self.current_sample, len(self.spots), reason or "载入"))
                self._log_no_annotation_if_needed()
            regions = SREG.get_sample_regions(self.regions_data, self.current_sample)
            self._log("样本 %s：已有区域 %d 个%s"
                      % (self.current_sample, len(regions),
                         ("（%s）" % ", ".join(str(r.get("name")) for r in regions))
                         if regions else ""))
            # 灌画布
            # ★★ `set_spots(xs, ys, labels)` 是**三个平行序列**（契约 §13.9 冻结的完整签名）。
            #    我原来只传 `self.spots` 一个参数 → `TypeError: missing 2 required
            #    positional arguments: 'ys' and 'labels'` → **画布上一个点都没有**，
            #    整页不可用（协调者真鼠标模拟发现的阻断性缺陷，根因是契约只冻了名字没冻签名）。
            #    `labels` 缺失一律填 `'NA'` —— 与画布"NA 固定灰"的约定一致。
            xs = [float(s.get("x")) for s in (self.spots or [])]
            ys = [float(s.get("y")) for s in (self.spots or [])]
            labels = [str(s.get("cell_type") or "NA") for s in (self.spots or [])]
            ok_spots = self._call_canvas(CANVAS_SET_SPOTS, xs, ys, labels)
            if self.spots and not ok_spots:
                # 失败原因 `_call_canvas` 已经写进日志；这里再点明后果（用户看得懂）
                self._log("画布没有接受这 %d 个 spot → 页面上不会显示任何点" % len(self.spots))
            self._call_canvas(CANVAS_SET_REGIONS, regions)
            # ★★ 换样本/重灌画布 ⇒ 画布的多选状态已失效，本文件的镜像快照必须同步清掉
            #   （否则旧样本的多选索引会把新样本同号区域的命名控件误判成"多选禁用"）。
            self._multi_selected_indices = []
            self._push_active_style()
            self._refresh_region_list()
            # ★★ v2 §4.1/§4.2：换样本/首次进页面都要按**该样本**重填两级命名控件：
            #   · 分组下拉 items = [cell_type, cluster, (group_graphed), 自定义]；
            #   · 注释选择框随当前分组填值（`group_graphed` = 该样本已有 anno_label + 自定义）。
            #   `active_region_index` 仍有效（如刷新时）⇒ 顺手回填选中区域的注释。
            self._fill_anno_group_combo()
            self._refill_anno_list(self._current_group_text())
            self._update_anno_input_visibility()
            idx_cur = self.active_region_index
            if isinstance(idx_cur, int) and 0 <= idx_cur < len(regions):
                self._sync_anno_controls(idx_cur)
            # ★ §15.5：进页面/换样本时也要把**已有的**两张预览显示出来
            #   （而不是等用户再点一次确认）。没有的图明确显示"尚未生成"。
            self._refresh_previews()
        except Exception:
            traceback.print_exc()

    def _refresh_previews(self):
        """刷新两个预览控件（带点 / 不带点）—— 现有的就显示，没有的写"尚未生成" """
        try:
            if not self.dataset or not self.current_sample:
                return
            png, _pdf = SREG.render_output_paths(self.dataset, self.current_sample)
            self._show_preview(png if (png and os.path.isfile(png)) else "",
                               'region_preview_label')
            ns_png, _ns_pdf = SREG.nospot_output_paths(self.dataset, self.current_sample)
            self._show_preview(ns_png if (ns_png and os.path.isfile(ns_png)) else "",
                               'region_preview_nospot_label')
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # §14.2 坐标表自动生成（后台线程；失败可重试）
    # ==================================================================
    def _log_no_annotation_if_needed(self):
        """§14.5：本数据集没有细胞注释 → 画布只显示点、不着色（**明确说明，不静默**）

        ★ 判据：所有 spot 的 `cell_type` 都为空 ⇒ `set_spots` 拿到的 labels 全是 `'NA'`
          ⇒ 画布按"单一 NA"着色。W3 的 dump 脚本在缺 `--ann` 时就是这么写的（空串）。
        """
        try:
            if not self.spots:
                return
            if any(str(s.get("cell_type") or "").strip() for s in self.spots):
                return
            self._warn_once("no_cell_annotation",
                            "本数据集没有细胞注释（cell_type 全为空）→ 画布只显示点、**不着色**"
                            "（坐标与画区功能不受影响）")
        except Exception:
            traceback.print_exc()

    def _maybe_auto_dump(self):
        """坐标表缺失 → 自动起后台线程生成（**约 6 s，绝不卡界面**）"""
        try:
            if self._dump_worker is not None:
                self._log("坐标表正在生成中…（不重复启动）")
                return
            if not self.dataset:
                return
            out_path = SREG.spots_path_for(self.dataset)
            if out_path and os.path.isfile(out_path):
                return                       # 已经有了（可能是别的线程刚写完）
            self._log("坐标表不存在 → 正在导出坐标表…（后台线程，界面不会卡；约 6 秒）")
            self._start_dump(reason="自动")
        except Exception:
            traceback.print_exc()

    def _start_dump(self, reason="自动"):
        """起 dump 线程；已在跑则忽略（防重复点按钮起两个）"""
        try:
            if self._dump_worker is not None:
                self._log("坐标表导出已在进行中 → 忽略这次请求（%s）" % reason)
                return False
            self._add_buttons_enabled(False)
            worker = _RegionDumpWorker(self.dataset, self._rds_path(), timeout=600)
            worker.done_ok.connect(self._on_dump_done)
            worker.done_fail.connect(self._on_dump_failed)
            worker.finished.connect(self._on_dump_thread_finished)
            self._dump_worker = worker
            worker.start()
            return True
        except Exception:
            traceback.print_exc()
            self._dump_worker = None
            return False

    def _add_buttons_enabled(self, enabled):
        """导出期间禁用「导出坐标表」按钮（手动重试不该并发跑两个 R）"""
        try:
            btn = self._ctl('btn_region_dump')
            if btn is not None and hasattr(btn, 'setEnabled'):
                btn.setEnabled(bool(enabled))
        except Exception:
            traceback.print_exc()

    def _on_dump_done(self, result):
        """**主线程**槽：导出成功 → 报数 → 自动重灌画布"""
        try:
            result = result if isinstance(result, dict) else {}
            rows = result.get("rows")
            samples = result.get("samples")
            unmatched = result.get("unmatched")
            csv_path = result.get("spots_csv") or ""
            self._dump_error = ""
            self._log("坐标表导出完成：%s 行 / %s 样本（未匹配注释 %s 个）"
                      % (rows, samples, unmatched))
            if result.get("ann_used"):
                self._log("  已用细胞注释：%s" % result.get("ann_used"))
            else:
                self._log("  未使用细胞注释（本数据集没有该 CSV）→ cell_type 列为空")
            self._log("  → %s（%.1f KB）"
                      % (csv_path,
                         (result.get("out_bytes") or 0) / 1024.0))
            if result.get("excluded_not_pass_qc") is not None:
                self._log("  透明度：对象内 %s spot，QC 通过 %s，因未过 QC 排除 %s"
                          % (result.get("spots_in_object"), result.get("spots_pass_qc"),
                             result.get("excluded_not_pass_qc")))
            # ★ 生成完成后**自动刷画布**（把新的三个平行序列灌进去）
            self.reload_current_sample(reason="坐标表刚生成")
        except Exception:
            traceback.print_exc()

    def _on_dump_failed(self, reason):
        """**主线程**槽：失败必须留痕，并让用户能重试（`btn_region_dump`）"""
        try:
            self._dump_error = str(reason or "未知原因")
            self._log("❌ 坐标表导出失败：%s" % self._dump_error)
            self._set_empty_hint("坐标表导出失败：%s\n可点「导出坐标表」重试" % self._dump_error)
            self._log("可点「导出坐标表」按钮重试（失败原因已留在上面）")
        except Exception:
            traceback.print_exc()

    def _on_dump_thread_finished(self):
        """线程收尾（**成功失败都要走到**，否则按钮永久禁用）"""
        try:
            self._dump_worker = None
            self._add_buttons_enabled(True)
        except Exception:
            traceback.print_exc()

    def _on_dump_clicked(self):
        """手动重试：`btn_region_dump`（§14.2，控件归 W1）"""
        try:
            if not self.dataset:
                self._log("尚未确定数据集 → 未导出")
                return
            if self._dump_worker is not None:
                self._log("坐标表导出已在进行中…")
                return
            out_path = SREG.spots_path_for(self.dataset)
            if out_path and os.path.isfile(out_path):
                self._log("坐标表已存在（%s）→ 仍按你的要求重新导出" % out_path)
            self._log("用户手动触发：正在导出坐标表…（后台线程）")
            self._start_dump(reason="手动")
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 画布交互
    # ==================================================================
    def _on_region_finished(self, *args):
        """双击闭合后：**从画布读回**那个区域（画布是几何的唯一真相源）

        ★★ 契约（协调者/W1 实测确认，我原来那条路是错的）：
          · `region_finished = pyqtSignal(str)` —— **载荷是"区域名"字符串，不是点列表**；
          · 双击闭合时**画布自己已经把 region append 进 `self._regions` 了**，
            然后才发 `region_finished(name)` + `region_selected(index)`。
          ⇒ 我原来"自己从点列表构造 region 再 append"会：
            ① 载荷里根本没有点列表 → 走不通；
            ② 就算从别处拿到点再 append，**画布已经加过一次 → 区域重复**。
          ⇒ 正解：**读回画布**（`canvas.get_regions()`），把它当唯一真相源。
            本文件只做"同步到我的 `regions_data`（供确认时算标签）＋ 刷新列表 ＋ 刷新日志"，
            **绝不自己造一个 region 塞回去**。
        """
        try:
            canvas_regions = self._read_canvas_regions()
            if canvas_regions is None:
                # 拿不到画布区域 → **什么都不做**（宁可不做，也不能重复添加）
                self._warn_once("no_get_regions",
                                "region_canvas 未提供 get_regions() → 新建的区域无法同步到"
                                "本页（确认时会漏掉它）；需要 W1 补这个接口")
                return
            if not canvas_regions:
                self._log("画布报告区域数为 0（闭合未成功？）→ 未同步")
                return

            # 画布刚 append 的那个 = 最后一个
            # ★ 元素形状已对着 W1 的真代码核对过（`region_canvas.py:446-454` 是 dict，
            #   `get_regions()` 返回深拷贝的 dict 列表，含 name/color/points/dash_width/
            #   dash_gap/label_font_size/label_font_color）——不是猜的。
            newest = canvas_regions[-1] if isinstance(canvas_regions[-1], dict) else None
            if newest is None:
                self._log("画布最后一个区域不是 dict（实际 %s）→ 未同步"
                          % type(canvas_regions[-1]).__name__)
                return
            points = [p for p in (SREG._norm_point(x) for x in (newest.get("points") or []))
                      if p is not None]
            if len(points) < 3:
                self._log("多边形顶点只有 %d 个（<3）→ 未同步（继续画或撤销）" % len(points))
                return

            # 名字：**以画布里的为准**（画布在建区域时用的就是它），信号载荷只作兜底
            # ★ v2（§3）：`region_name_input` 现在是**分组下拉**，它的文本是
            #   `cell_type`/`cluster`/`group_graphed`/`自定义` —— **绝不能**再当作区域名
            #   （那会把新区域命名成 "cell_type"）。兜底改用：
            #     ① 信号载荷里的名字 → ② 待用的注释值 → ③ "未命名"。
            name = str(newest.get("name") or "").strip()
            if not name:
                for a in (args or ()):
                    if isinstance(a, str) and a.strip():
                        name = a.strip()
                        break
            if not name:
                name = str(self._anno_pending_label or "").strip() or "未命名"

            # 同步：画布的整份列表 → 我的 regions_data（供确认时算标签）
            others = canvas_regions[:-1]
            self._warn_overlap(points, [r for r in others if isinstance(r, dict)])
            SREG.set_sample_regions(self.regions_data, self.current_sample, canvas_regions)
            self._persist(reason="新建区域（读回画布）")
            self._refresh_region_list()
            self.active_region_index = len(canvas_regions) - 1
            # ★ 新建区域后画布只选中"最新的这个"（单选语义）⇒ 多选镜像收成 `[新索引]`。
            #   否则旧的多选快照（如删掉一个区域后再画）会把新区域的命名误判成"多选禁用"。
            self._multi_selected_indices = [self.active_region_index]
            # 把画布那个区域里的样式回填右侧（用户看到的就是画布上真实生效的样式）
            self._apply_region_to_controls(newest)
            # ★ v2 §4.3 的"待用值"在这里兑现：没选中区域时选的（分组, 注释）就是
            #   接下来画的这个新区域的默认注释（走的仍是唯一的 `_commit_anno` 写盘入口）。
            #   ⚠ `_sync_anno_controls` 会用**新区域**（旧式）的字段覆盖 `_anno_pending_*`
            #     ⇒ 待用值必须**先取到局部变量**再同步/写盘。
            #   （在此之前，`region_canvas` 是逐字段新建 region dict 的 —— 它不会带
            #     `anno_group`/`anno_label`，所以"出生即旧式"必须由本文件在这里补上。）
            pending_g = str(self._anno_pending_group or '').strip()
            pending_l = str(self._anno_pending_label or '').strip()
            self._sync_anno_controls(self.active_region_index)
            if pending_l:
                # 只有**待用值非空**时才补写；空则保持旧式（不硬塞空串）
                if self._commit_anno(pending_g, pending_l, source="新区域沿用待用值"):
                    self._log("新区域已套用待用注释：%s（分组 %s）" % (pending_l, pending_g))
            self._log("已同步新区域 #%d『%s』：%d 个顶点（后画的会覆盖先画的）"
                      % (len(canvas_regions), name, len(points)))
        except Exception:
            traceback.print_exc()

    def _read_canvas_regions(self):
        """读画布的整份区域列表；接口不存在 → `None`（**与"空列表"区分开**）"""
        try:
            c = self._canvas()
            if c is None:
                return None
            fn = getattr(c, 'get_regions', None)
            if not callable(fn):
                return None
            raw = fn()
            if raw is None:
                return []
            return list(raw)
        except Exception:
            traceback.print_exc()
            return None

    def _apply_region_to_controls(self, region):
        """把某个区域的**样式**回填到右侧控件（`region_selected` 与"刚画完"共用这一处）

        ★ v2（契约 §3/§4.5）：**不再**往 `region_name_input` 写文本 —— 它现在是
          「分组」下拉（不可编辑），写 `name` 进去既选不中任何一项、又会被误当成
          "用户选了分组"。分组/注释的回填一律走 `_sync_anno_controls(index)`
          （那里有 `_anno_filling` 守卫，回填不会写盘）。
        """
        try:
            if not isinstance(region, dict):
                return
            if not self._write_palette_color(self._ctl('region_color_palette'),
                                            region.get("color") or SREG.DEFAULT_REGION_COLOR):
                self._warn_once("palette_setter",
                                "调色板控件没有可用的 setter 或颜色值是空 → 颜色回填失败")
            self._write_number(self._ctl('region_dash_width_input'),
                               region.get("dash_width", SREG.DEFAULT_DASH_WIDTH))
            self._write_number(self._ctl('region_dash_gap_input'),
                               region.get("dash_gap", SREG.DEFAULT_DASH_GAP))
            self._write_number(self._ctl('region_font_size_input'),
                               region.get("label_font_size", SREG.DEFAULT_LABEL_FONT_SIZE))
            self._write_palette_color(self._ctl('region_font_color_palette'),
                                      region.get("label_font_color")
                                      or SREG.DEFAULT_LABEL_FONT_COLOR)
        except Exception:
            traceback.print_exc()

    def _warn_overlap(self, points, regions):
        """新多边形是否与已有区域重叠（用"顶点落在别的区域里"近似判定，够用且便宜）"""
        try:
            hits = []
            for r in (regions or []):
                if not isinstance(r, dict) or r.get("invalid"):
                    continue
                for p in (points or []):
                    if SREG.point_in_polygon(p[0], p[1], r.get("points")):
                        hits.append(str(r.get("name")))
                        break
            if hits:
                self._log("⚠ 该多边形与已有区域重叠：%s（**后画的会覆盖先画的**）"
                          % ", ".join(hits))
        except Exception:
            traceback.print_exc()

    def _on_region_selected(self, *args):
        """选中某区域 → 把它的样式回填右侧控件

        ★ 区域索引**一律以画布为准**：画布可能被 `set_regions` 之外的路径改动
          （用户删/撤销），而 `get_regions()` 就是它的当前真相。
          索引或画布不可用时退回 `regions_data` 的快照（并留痕）。
        """
        try:
            idx = self._index_from_signal(args)
            canvas_regions = self._read_canvas_regions()
            regions = canvas_regions
            if regions is None:
                self._warn_once("selected_no_canvas_regions",
                                "画布未提供 get_regions() → 选中区域的样式只能从内存快照回填")
                regions = SREG.get_sample_regions(self.regions_data, self.current_sample)
            if idx is None or not (0 <= idx < len(regions)):
                return
            # 快照跟上画布（防"同一次点击里画布与快照索引错位"）
            if canvas_regions is not None:
                SREG.set_sample_regions(self.regions_data, self.current_sample, canvas_regions)
            r = regions[idx]
            self.active_region_index = idx
            # ★ 反向同步：把**列表高亮**也指到这个索引（守卫内 + 值不同才设 ⇒ 不成环）。
            #   否则"画布点选"与"列表高亮"会各说各话，用户看不出当前到底在编辑哪个。
            self._sync_region_list_selection(idx)
            # 回填与"刚画完"共用同一处（避免两份回填逻辑各写一半）
            self._apply_region_to_controls(r if isinstance(r, dict) else {})
            # ★ v2 §4.5：两级命名也回填（分组 → combo、注释 → list）；
            #   顺序无碍（`_sync_anno_controls` 自己会重填注释框），但必须在
            #   `_apply_region_to_controls` 之后 —— 它不再碰那两个控件。
            self._sync_anno_controls(idx)
            self._log("已选中区域 #%d『%s』（%d 个顶点），样式已回填右侧"
                      % (idx + 1, (r or {}).get("name") if isinstance(r, dict) else r,
                         len((r or {}).get("points") or []) if isinstance(r, dict) else 0))
        except Exception:
            traceback.print_exc()

    def _on_regions_selected(self, *args):
        """画布 `regions_selected(list)`：**多选变化** ⇒ 编排命名控件的禁用/恢复（§3.3）

        ★ 语义（`_d_spec_select_mode.md` §3.3 冻结）：
          · 画布 `_selected_indices` 的**顺序 = 命中顺序**，`selected_index()`（主选中项）
            = 第一项；`region_selected(int)` **照旧发**主选中项 ⇒ 单选链路完全不受影响；
          · **=1** ⇒ 走**既有单选链路**（`_on_region_selected`）：样式回填、两级命名回填、
            命名控件恢复可用（若这个区域是范围层则仍禁用 —— 见 §3.4 与
            `_apply_anno_enablement`，**不在这里再写一份判据**）；
          · **≥2** ⇒ 四个命名控件全部 `setEnabled(False)` + 一行日志；
            **不写盘、不因多选改任何区域字段**（`_apply_anno_enablement` 只动 `setEnabled`）；
          · **空** ⇒ 清空选择（`active_region_index = -1`），日志沿用既有"已取消选中"口径。

        ★ 为什么 ≥2 也**顺手**调一次 `_on_region_selected` 的同款链路是**不必要**的：
          多选时属性面板的区域名/注释**不回填可编辑态**（规格原话），所以这里只
          ①记快照 ②指列表高亮 ③定可用态。若此后 W1 又单独发了 `region_selected(int)`
          （主选中项），那条既有链路会照常回填 —— 此时 `_multi_selected_indices` 已是多选，
          `_apply_anno_enablement` 仍会保持禁用，**顺序无关**。

        ★ 本方法**不写盘**（没有 `save_regions`/`_persist`），也不解析载荷去改区域字段。
        """
        try:
            payload = None
            for a in (args or ()):
                if isinstance(a, (list, tuple)):
                    payload = a
                    break
            if payload is None:
                got = ", ".join(type(a).__name__ for a in (args or ())) or "（无载荷）"
                self._warn_once("regions_selected_no_list",
                                "regions_selected 的载荷不是 list（实际 %s）→ 本次按"
                                "『无多选信息』处理（不清空、不写盘）" % got)
                return
            idxs = []
            for v in payload:
                if isinstance(v, bool):
                    continue
                if not isinstance(v, int):
                    # ★ 契约是 `list[int]`；混进别的东西**不静默跳过**，如实写一行
                    self._log("⚠ regions_selected 载荷里混进了非整数项（%r，类型 %s）→ 已跳过它"
                              % (v, type(v).__name__))
                    continue
                if v >= 0 and v not in idxs:
                    idxs.append(v)
            self._multi_selected_indices = idxs
            if len(idxs) >= 2:
                # 主选中项 = 第一项（与画布 `selected_index()` 的语义一致）
                self.active_region_index = idxs[0]
                self._sync_region_list_selection(idxs[0])
                # ★ 这里就是 §3.3 要求的那行日志（在 `_apply_anno_enablement` 里按状态变化写）
                self._apply_anno_enablement(idxs[0])
                return
            if not idxs:
                if self.active_region_index != -1:
                    self._log("区域列表/画布：已取消选中（当前编辑的区域 → 无）")
                self.active_region_index = -1
                self._apply_anno_enablement(-1)
                return
            # ---- 单选（=1）⇒ 既有单选链路（含范围层判据与可用态收口）----
            self._on_region_selected(idxs[0])
        except Exception:
            traceback.print_exc()

    def _on_region_geometry_changed(self, *args):
        """画布 `region_geometry_changed(int)`：顶点拖动**松开且坐标确实变了** ⇒ 落盘一次（§5）

        ★ 与 `_on_region_edges_changed` **完全同款**：不解析载荷去改字段 ——
          画布是几何的唯一真相源，收到信号就"**整份读回画布 → 既有 persist 链路**"
          （`_sync_from_canvas` = `get_regions()` → `SREG.set_sample_regions` → `_persist`
          → `_refresh_region_list`）。**绝不新增写盘路径**。
        ★ "同值不写"由**画布**保证（坐标没变它不发信号，§3.2）；
          本方法**也不加任何节流/去抖定时器** —— 一次拖动 = 一次落盘，
          拖动期间画布自己不发信号、也不落盘。
        ★ 载荷里的索引**只用于日志**（区域可能已被删/顺序已变，不拿它去索引模型）。
        """
        try:
            idx = (list(args) + [None])[0]
            # ★ 不用 try/except 转 int（避免"静默吞异常"的旁路）：载荷不是整数就写 `#?`
            shown = ("#%d" % (idx + 1)) \
                if (isinstance(idx, int) and not isinstance(idx, bool)) else "#?"
            if not self._sync_from_canvas(reason="顶点拖动（区域 %s）" % shown):
                self._log("⚠ 区域 %s 的顶点已拖动，但**整份读回画布/落盘失败** → 形状可能没存下来"
                          "（原因见上面那行『画布接口/保存失败』提示）" % shown)
                return
            self._log("区域 %s 的顶点已拖动（形状已变）⇒ 已落盘" % shown)
        except Exception:
            traceback.print_exc()

    def _index_from_signal(self, args):
        """从信号载荷里认出区域索引（int / 区域 dict / 区域名 都认）"""
        try:
            regions = SREG.get_sample_regions(self.regions_data, self.current_sample)
            for a in (args or ()):
                if isinstance(a, bool):
                    continue
                if isinstance(a, int):
                    return a
                if isinstance(a, dict):
                    for i, r in enumerate(regions):
                        if r is a or r.get("name") == a.get("name"):
                            return i
                    return None
                if isinstance(a, str):
                    for i, r in enumerate(regions):
                        if str(r.get("name")) == a:
                            return i
            return None
        except Exception:
            traceback.print_exc()
            return None

    def _collect_style(self):
        """从右侧控件收集当前样式（缺控件用契约默认值）"""
        return {
            "color": self._read_palette_color(self._ctl('region_color_palette'),
                                              SREG.DEFAULT_REGION_COLOR),
            "dash_width": self._read_number(self._ctl('region_dash_width_input'),
                                            SREG.DEFAULT_DASH_WIDTH),
            "dash_gap": self._read_number(self._ctl('region_dash_gap_input'),
                                          SREG.DEFAULT_DASH_GAP),
            "label_font_size": self._read_number(self._ctl('region_font_size_input'),
                                                 SREG.DEFAULT_LABEL_FONT_SIZE),
            "label_font_color": self._read_palette_color(self._ctl('region_font_color_palette'),
                                                         SREG.DEFAULT_LABEL_FONT_COLOR),
        }

    def _set_palette_color_silent(self, color, why=""):
        """**静默**把颜色压到调色板控件，并只把新颜色压给"下一个新画的多边形"

        ★★ 为什么不能直接 `set_color()`（本方法存在的**唯一**理由）：
          `StyledColorPalette.set_color()` 会 **emit `color_changed`**
          （`script/utils_layer/gui_styles.py:3870-3877`），而 `color_changed` 接的是
          `_push_active_style` —— 它在**有选中区域**时会把 5 个样式值写回该区域并
          **落盘**。程序化切色（进/离可见区域模式）若不做抑制，就会把当前选中区域
          静默刷成白色并写进 `regions.json`（D 系列"程序化回填写盘"事故）。
          ⇒ 置 `self._palette_programmatic = True` → `set_color()` → `try/finally` 复位；
          `_push_active_style` 在该标志下**只做实时预览**（`set_active_style`）然后 return。

        ★ 切完之后**再**显式把新颜色压给画布的"下一个新画的多边形样式"
          （`CANVAS_SET_ACTIVE_STYLE`，其余 4 个样式值取自现有 `_collect_style()`）——
          这样即使某天信号被断开/抑制分支没跑到，预览也一定生效（不依赖信号链）。

        ⛔ 本方法**绝不**：写任何已有区域、`set_sample_regions`、`set_regions`、
          落盘（`_persist`/`save_regions`）、emit 任何区域几何变化信号。
        ⛔ 也**不**改 `_push_active_style` 的既有分流语义（去抖状态机/前沿立即写/日志）
           —— 抑制只发生在"本方法持旗期间"，旗一落就完全走原路径。

        Returns:
            bool: 颜色是否真的写进了调色板控件（False = 控件缺失/无 setter，已留痕）
        """
        try:
            w = self._ctl('region_color_palette')
            if w is None:
                self._warn_once("no_region_color_palette_silent",
                                "布局未提供 region_color_palette → 无法按编辑模式切换默认颜色"
                                "（本次不动调色板）")
                return False
            prev = self._palette_programmatic
            self._palette_programmatic = True
            try:
                ok = self._write_palette_color(w, color)
            finally:
                self._palette_programmatic = prev
            if not ok:
                self._warn_once("palette_silent_setter",
                                "调色板控件没有可用的 setter → 无法按编辑模式切换默认颜色"
                                "（本次不动调色板）")
                return False
            # ★ 只压给"下一个新画的多边形"（其余 4 个样式值仍取现有 `_collect_style()`）
            style = self._collect_style()
            self._call_canvas(CANVAS_SET_ACTIVE_STYLE,
                              style["dash_width"], style["dash_gap"], style["color"],
                              style["label_font_size"], style["label_font_color"])
            return True
        except Exception:
            traceback.print_exc()
            self._log("⚠ 静默切换调色板失败（%s）→ 调色板保持当前值；"
                      "**绝不写任何已有区域**" % (why or "未说明原因"))
            return False

    def _push_active_style(self, *args):
        """右侧样式控件改动 → ①**立刻**压给画布预览 ②选中了区域就写回该区域并落盘

        ## ★★ 本轮修的真断线（协调者对照实验实测）
          颜色/虚线粗/间距/字号/字色这 5 项原来**只**调 `canvas.set_active_style()`，
          而 W1 那个函数的 docstring 自己就写着"设置**接下来画的**多边形样式"
          ⇒ 已选中的区域**画布不变、磁盘不变**。实测对照（临时数据集）：
            【A 改字号 12→30】控件=30，画布区域 `label_font_size`=12，`_persist`=0，磁盘=12
            【B 改圆角 0→17】画布区域 `corner_radius_px`=17.0，`_persist`=1，磁盘=17.0
          而**同一排**的名字框/圆角框却能改（各有专门通路）⇒"一半通一半不通"，
          用户只会以为程序坏了。Phase 3 整体是"图美化"，**先画区域、再逐个调样式**
          是标准动作，所以这不是可选项。

        ## 分流（沿用 `name` / `corner_radius_px` 这条**已被验证**的通路，不发明新机制）
          · **选中了区域**（`active_region_index` 在 `0..len-1` 内）：
            把 5 个值写进 `regs[idx]` → `set_sample_regions` → **立刻** `set_regions()`
            推回画布（实时预览）→ 落盘（去抖，见下）→ 日志写明"哪个区域、改了哪几项"。
          · **没选中区域**：保持原行为（只 `set_active_style`，对"下一个新画的多边形"
            生效），但**补一条日志**说清楚 —— 否则用户还是会困惑"为什么没反应"。

        ## 去抖方案（我自己定，理由在此）：**前沿立即 + 尾沿合并**（显式"突发"状态机）
          · 一次突发里的**第一次**改动**立刻落盘**：任何时刻"已生效的样式"都已在盘上，
            程序/机器意外结束也不会丢（宁可多写一次，也不接受"改了没存"）；
          · 之后同一个区域的连续改动**只更新画布、不写盘**，并（重）启 single-shot 定时器；
            **安静满 `STYLE_PERSIST_DEBOUNCE_MS`** 后合并写一次，突发结束。
          · 突发是否结束由 `_style_burst` 显式记录，**不用"距上次写盘多久"来推断** ——
            我第一版就是这么写的（`not _style_pending or 距上次写盘 >= 窗口`），
            而"前沿"分支写完就把 `_style_pending` 清成 False ⇒ 下一次进来
            `not _style_pending` 恒为 True ⇒ **每次都判定为前沿**，
            实测连续 5 次改动**写了 5 次盘**，去抖等于没有。故改成显式状态机。
          · 为什么不用**纯尾沿**（只写最后一次）：那样"改完立刻切样本/关程序"在定时器
            触发前有一个丢改动的窗口；前沿立即把这个窗口消掉了，代价只是多一次写盘。
          · 为什么不用"值没变就跳过"：拖滑块 12→13→…→30 **每一步值都不同**，去不掉，
            必须按**时间**合并。
          · 兜底：`_on_back_clicked` 与 `reload_current_sample` 都会先 `_flush_style_pending()`
            （`_persist` 写的是**整份** `regions_data`，所以随时 flush 都不会串样本）。
          · ⚠ 尾沿依赖 **Qt 事件循环**（真实 GUI 一直有）；没有事件循环的裸脚本里
            定时器不会自己到点，需要 `processEvents()` 或显式 flush。
          · 为什么**不去抖画布重绘**：用户调样式要的是"立刻看见"，重绘不写盘、没有代价。

        ## ★★ 程序化切色的**抑制分支**（2026-09-24；本方法**开头**那一段）
          `StyledColorPalette.set_color()` 会 emit `color_changed`（`gui_styles.py:3870-3877`），
          而本方法在**有选中区域**时会写回该区域**并落盘**。程序化切色
          （`_set_palette_color_silent` 在"进/离可见区域模式"时调用）**不是用户改样式**
          ⇒ 持旗期间（`self._palette_programmatic`）**只做第 ① 步实时预览然后 return**，
          跳过下面"写回选中区域 + 落盘"整段。
          ⛔ 抑制**只覆盖持旗那一瞬间**（`try/finally` 复位）：旗落下后本方法的
            去抖状态机（前沿立即写 + 尾沿合并）、日志、分流语义**一字未改**。
        """
        try:
            # ★★ 抑制分支（**必须在写回/落盘之前**）：程序化切调色板期间只做实时预览。
            if self._palette_programmatic:
                style = self._collect_style()
                self._call_canvas(CANVAS_SET_ACTIVE_STYLE,
                                  style["dash_width"], style["dash_gap"], style["color"],
                                  style["label_font_size"], style["label_font_color"])
                return
            style = self._collect_style()
            # ① 实时预览（对"下一个新画的多边形"生效；这步永远做）
            self._call_canvas(CANVAS_SET_ACTIVE_STYLE,
                              style["dash_width"], style["dash_gap"], style["color"],
                              style["label_font_size"], style["label_font_color"])
            regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
            idx = self.active_region_index
            if idx is None or not (0 <= idx < len(regs)) or not isinstance(regs[idx], dict):
                # ★ 只提示**一次**（每段"未选中"期间）：拖滑块会连续 emit，
                #   一次一条会把日志刷满，反而没人看。
                if not self._style_hint_shown:
                    self._style_hint_shown = True
                    self._log("未选中区域 → 该样式只对**下一个新画**的多边形生效"
                              "（想改已有区域：先在画布上点一下它）")
                return
            self._style_hint_shown = False       # 又选中了 → 下次未选中时再提示一次
            # ② 选中了区域 → 写回区域字典（只记真的变了的字段）
            changed = []
            for key, val, is_color in (("color", str(style["color"] or ""), True),
                                       ("dash_width", style["dash_width"], False),
                                       ("dash_gap", style["dash_gap"], False),
                                       ("label_font_size", style["label_font_size"], False),
                                       ("label_font_color",
                                        str(style["label_font_color"] or ""), True)):
                old = regs[idx].get(key)
                try:
                    # ★ 颜色按**大小写无关**比较：调色板可能返回 `#ff6b35` 而区域里存的是
                    #   `#FF6B35` —— 直接 `!=` 会把"选中区域后回填控件"误判成"用户改了颜色"
                    #   ⇒ 多余的写盘。数值字段按数值比。
                    same = ((str(old or "").strip().upper() == val.strip().upper())
                            if is_color else (float(old or 0) == float(val)))
                except (TypeError, ValueError):
                    same = False
                if not same:
                    regs[idx][key] = val
                    changed.append(key)
            if not changed:
                return
            SREG.set_sample_regions(self.regions_data, self.current_sample, regs)
            # 立刻推回画布（`set_regions()` **不发** `region_*_changed` ⇒ 不会回流打架）
            self._call_canvas(CANVAS_SET_REGIONS, regs)
            self._persist_style_debounced(idx, changed, style)
        except Exception:
            traceback.print_exc()

    # 字段名 → 中文（日志用；不写进数据结构，纯展示）
    STYLE_FIELD_LABELS = {"color": "颜色", "dash_width": "虚线粗", "dash_gap": "间距",
                          "label_font_size": "字号", "label_font_color": "字色"}

    def _style_changed_text(self, idx, changed, style):
        """一句话说清"改了哪个区域的哪几项、改成什么"（**不许静默**）"""
        try:
            return "区域 #%d 样式：%s" % (
                idx + 1,
                "、".join("%s=%s" % (self.STYLE_FIELD_LABELS.get(k, k),
                                     (style or {}).get(k)) for k in changed))
        except Exception:
            traceback.print_exc()
            return "区域 #%d 样式变更" % (idx + 1)

    def _persist_style_debounced(self, idx, changed, style=None):
        """样式落盘的**前沿立即 + 尾沿合并**（方案与理由见 `_push_active_style`）

        Returns:
            bool: 本次是否**真的**写了盘
        """
        try:
            text = self._style_changed_text(idx, changed, style)
            # 换区域（或上一个区域还挂着合并中的改动）→ 先把上一个收口再开新突发
            if self._style_burst and self._style_pending_idx != idx:
                self._flush_style_pending()
            if not self._style_burst:
                # 前沿：立刻落盘 + 进入"合并中"（此后窗口内的连续改动只更新画布）
                self._style_burst = True
                self._style_pending = False
                self._style_pending_idx = idx
                self._last_style_persist = time.monotonic()
                self._persist(reason="样式变更（%s）" % text)
                self._log("%s（已落盘）" % text)
                self._start_style_timer()
                return True
            # 尾沿：只更新画布，安静满一个窗口后合并写一次
            self._style_pending = True
            self._style_pending_idx = idx
            self._start_style_timer()
            gap = (time.monotonic() - self._last_style_persist) * 1000.0
            self._log("%s（画布已更新；落盘合并中：距上次写盘 %.0f ms，"
                      "安静 %d ms 后合并写一次）" % (text, gap, STYLE_PERSIST_DEBOUNCE_MS))
            return False
        except Exception:
            traceback.print_exc()
            return False

    def _start_style_timer(self):
        """（重）启尾沿定时器；**懒建 + 无父对象 + 失败 fail-open**

        ## ★ 为什么**不给** QTimer 设父对象（协调者实测踩出的脆弱点）
          我第一版写的是 `QTimer(self.parent if self.parent is not None else None)`。
          生产里 `self.parent` 是 QMainWindow（QObject）所以没事，但两类情况会抛
          `TypeError: QTimer(parent): argument 1 has unexpected type '_MW'`：
            ① `self.parent` 不是 QObject（测试替身 / 别的宿主）；
            ② 父对象已被 Qt 销毁。
          ⇒ 改成**无父** `QTimer()`：不碰 `self.parent`，同时免疫上面两类。
          为什么**不用** `isinstance(self.parent, QObject)` 过滤：它**挡不住 ②** ——
          父对象 C++ 侧已删除时，Python 包装类的 `isinstance` 仍为 True，
          而 `QTimer(par)` 会抛 `RuntimeError: wrapped C/C++ object ... has been deleted`。
          无父的 QTimer **不会被 GC**（我们在 `self._style_timer` 里持有引用），
          线程亲和性取当前线程即可 —— 本页所有 Qt 操作都在主线程。

        ## ★ 失败必须 **fail-open**（本加固的核心）
          老写法失败时只留一条 traceback，后果却是：
          `_flush_style_pending` 永不被调用 ⇒ **`_style_burst` 永远是 True**
          ⇒ 之后**所有**样式改动都走"尾沿"分支、再也不落盘 ⇒
          **一次定时器故障 = 此后样式改动静默全丢**（协调者实测：磁盘停在旧值）。
          ⇒ 异常分支里**立刻 `_flush_style_pending()`**：它先把"已改画布、未落盘"的
          那次改动写下去，并**无条件结束当前突发**（`_style_burst = False`）
          ⇒ 下一次改动重新走"前沿立即落盘" ⇒ 效果是**每次改动都立即落盘**
          （宁可多写几次盘，也绝不丢用户的样式改动）。日志明说，**不静默**。
        """
        try:
            t = self._style_timer
            if t is None:
                t = QTimer()                      # ★ 无父：见上面 docstring
                t.setSingleShot(True)
                t.timeout.connect(self._flush_style_pending)
                self._style_timer = t
            t.start(int(STYLE_PERSIST_DEBOUNCE_MS))
        except Exception as e:
            traceback.print_exc()
            self._style_timer = None              # 下次重试创建
            try:
                self._flush_style_pending()       # ★ fail-open：先落盘 + 结束突发
            except Exception:
                traceback.print_exc()
            self._warn_once("style_timer_unavailable",
                            "样式落盘定时器不可用（%s: %s）→ 已改为**每次改动立即落盘**"
                            "（样式不会丢，只是写盘次数变多）" % (type(e).__name__, e))

    def _cancel_style_timer(self):
        try:
            if self._style_timer is not None:
                self._style_timer.stop()
        except Exception:
            traceback.print_exc()

    def _flush_style_pending(self, *args):
        """把"已改画布但还没落盘"的样式改动补写一次（定时器到点 / 离开页面 / 切样本）

        ★ 同时**结束当前突发**（`_style_burst = False`）：下一次改动重新算"前沿"。
        """
        try:
            did = False
            if self._style_burst and self._style_pending:
                idx = self._style_pending_idx
                self._persist(reason="样式变更（区域 #%d，连续改动合并）" % (idx + 1))
                self._log("区域 #%d 的连续样式改动已合并落盘" % (idx + 1))
                self._last_style_persist = time.monotonic()
                did = True
            self._style_pending = False
            self._style_burst = False
            self._cancel_style_timer()
            return did
        except Exception:
            traceback.print_exc()
            return False

    # ==================================================================
    # 样本列表 / 区域列表
    # ==================================================================
    def _fill_sample_list(self, samples):
        """填样本列表 —— 每项文案按契约 §14.2 **冻结**：

            `✅ 已画 N 区  <样本号>` / `⚠ 未画  <样本号>`

        N 由**本文件从 `regions.json` 数**（`SREG.painted_region_count`，只数顶点 ≥3 的有效区域）。
        ★ 本页没有 func 层（§13.5 归属表里没有 `ui_func_spatial_region.py`），
          所以条目由本文件填；**文案是契约逐字冻死的**，因此不存在"两边格式漂移"的风险。
        ★ `item.setData(Qt.UserRole, sid)` 保留 —— `_select_sample_in_list`/`_row_of_sample`
          都靠它取样本号（**不要**改成从 ✅/⚠ 文本里正则抽，那是脆的）。
        """
        try:
            lst = self._ctl('region_sample_list')
            if lst is None or not hasattr(lst, 'addItem'):
                self._warn_once("no_sample_list_fill",
                                "region_sample_list 不支持 addItem → 样本列表为空")
                return
            try:
                lst.clear()
            except Exception:
                pass
            painted = 0
            for sid in (samples or []):
                n = SREG.painted_region_count(self.regions_data, sid)
                if n > 0:
                    painted += 1
                    text = SAMPLE_ITEM_PAINTED % (n, sid)
                else:
                    text = SAMPLE_ITEM_UNPAINTED % sid
                item = QListWidgetItem(text)
                try:
                    item.setData(Qt.UserRole, str(sid))
                except Exception:
                    pass
                lst.addItem(item)
            self._log("样本列表：%d 个样本，其中**已画区域 %d 个**、未画 %d 个"
                      % (len(samples or []), painted, len(samples or []) - painted))
        except Exception:
            traceback.print_exc()

    def _restamp_sample_item(self, sid):
        """只重写**某一个**样本项的文字（✅已画 N 区 / ⚠未画）

        ★ 为什么不整体重建列表：重建会**重置当前行** → 触发 `currentRowChanged` →
          再重灌一次画布（用户正在画的多边形会被清掉）。所以只改那一行的文本。
        """
        try:
            lst = self._ctl('region_sample_list')
            if lst is None or not sid or not hasattr(lst, 'count'):
                return
            n = SREG.painted_region_count(self.regions_data, sid)
            text = (SAMPLE_ITEM_PAINTED % (n, sid)) if n > 0 else (SAMPLE_ITEM_UNPAINTED % sid)
            for i in range(int(lst.count())):
                it = lst.item(i)
                if it is None:
                    continue
                val = None
                try:
                    val = it.data(Qt.UserRole)
                except Exception:
                    pass
                if str(val or "") == str(sid):
                    try:
                        it.setText(text)
                    except Exception:
                        traceback.print_exc()
                    return
        except Exception:
            traceback.print_exc()

    def _select_sample_in_list(self, sid):
        try:
            lst = self._ctl('region_sample_list')
            if lst is None or not sid or not hasattr(lst, 'count'):
                return
            for i in range(lst.count()):
                it = lst.item(i)
                if it is None:
                    continue
                val = None
                try:
                    val = it.data(Qt.UserRole)
                except Exception:
                    pass
                # ★ UserRole 优先；退回"文本以样本号结尾"（文案是 `✅ 已画 N 区  <样本号>`）
                if str(val or "") == str(sid) or str(it.text()).endswith(str(sid)):
                    lst.setCurrentRow(i)
                    return
        except Exception:
            traceback.print_exc()

    def _refresh_region_list(self):
        """把当前样本的区域刷进 `region_list_widget`（同样只填条目）

        ★★ `clear()` 会发 `currentRowChanged(-1)`，而本函数在 `_persist` 之后**频繁**被调用
          ⇒ 必须用 `_region_list_rebuilding` 把这一段时间的选择信号**挡住**，
          否则"刷新一次就把用户的选中清掉"（用户会看到选中莫名其妙消失）。
          用 `try/finally` 保证标志一定被清（中途异常也不会把列表永久锁死）。
        ★ 填完把当前行**指回 `active_region_index`**（守卫内），让"列表高亮"与
          "当前编辑的区域"重建后仍然一致。
        """
        try:
            w = self._ctl('region_list_widget')
            if w is None or not hasattr(w, 'addItem'):
                return
            self._region_list_rebuilding = True
            try:
                try:
                    w.clear()
                except Exception:
                    pass
                regions = SREG.get_sample_regions(self.regions_data, self.current_sample)
                for i, r in enumerate(regions):
                    txt = "%d. %s（%d 点%s）" % (i + 1, r.get("name"), len(r.get("points") or []),
                                                "，无效" if r.get("invalid") else "")
                    item = QListWidgetItem(txt)
                    try:
                        item.setData(Qt.UserRole, i)
                    except Exception:
                        pass
                    w.addItem(item)
                # 重建后把当前行指回"正在编辑的区域"（仍在守卫内 ⇒ 不会再触发回环）
                try:
                    idx = self.active_region_index
                    if isinstance(idx, int) and 0 <= idx < len(regions) \
                            and hasattr(w, 'setCurrentRow'):
                        w.setCurrentRow(idx)
                except Exception:
                    traceback.print_exc()
            finally:
                self._region_list_rebuilding = False
        except Exception:
            traceback.print_exc()

    def _on_sample_row_changed(self, row):
        try:
            lst = self._ctl('region_sample_list')
            if lst is None or row is None or row < 0:
                return
            it = lst.item(int(row))
            if it is None:
                return
            val = None
            try:
                val = it.data(Qt.UserRole)
            except Exception:
                pass
            sid = str(val or it.text())
            if sid == str(self.current_sample):
                return
            self.current_sample = sid
            self.active_region_index = -1
            self._log("切换样本 → %s" % sid)
            self.reload_current_sample(reason="切换样本")
        except Exception:
            traceback.print_exc()

    def _on_sample_selection_changed(self):
        try:
            lst = self._ctl('region_sample_list')
            row = lst.currentRow() if (lst is not None and hasattr(lst, 'currentRow')) else -1
            self._on_sample_row_changed(row)
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 按钮
    # ==================================================================
    def _on_back_clicked(self):
        try:
            # ★ 离开页面前先把"合并中"的样式改动补落一次（否则可能丢在内存里）
            self._flush_style_pending()
            # ★★ 用户 2026-09-20 拍板：绘图模式已从审查页**剥离为 hub 的独立入口**，
            #   所以「返回」**一律回 hub**，不再 `go_to_parent_page('spatial_region_page')`
            #   （那条会回到**审查页**，与新的"双入口"模型不符）。
            #   ⚠ 不改 `page_intersect.py`（共享热点文件），只改本页自己的返回目标。
            page_intersect.go_to_page_with_bind('spatial_top_page')
        except Exception:
            traceback.print_exc()

    def _on_undo_clicked(self):
        """撤销当前多边形最后一个顶点（画布操作）"""
        try:
            ok = self._call_canvas(CANVAS_UNDO_POINT)
            if ok:
                self._log("已撤销最后一个顶点")
        except Exception:
            traceback.print_exc()

    def _on_delete_clicked(self):
        """删除选中的区域（按右侧回填时记录的索引）"""
        try:
            regions = SREG.get_sample_regions(self.regions_data, self.current_sample)
            idx = self.active_region_index
            if idx is None or not (0 <= idx < len(regions)):
                self._log("没有选中的区域 → 未删除（先在画布上点一个区域）")
                return
            gone = regions.pop(idx)
            SREG.set_sample_regions(self.regions_data, self.current_sample, regions)
            self._persist(reason="删除区域")
            self._call_canvas(CANVAS_SET_REGIONS, regions)
            self._refresh_region_list()
            self.active_region_index = -1
            # ★ 删掉一个区域后索引全体前移 ⇒ 旧的多选快照可能已经指到别的区域，必须清掉（§3.3）
            self._multi_selected_indices = []
            self._apply_anno_enablement(-1)
            self._log("已删除区域 #%d『%s』（本样本剩 %d 个）"
                      % (idx + 1, gone.get("name"), len(regions)))
        except Exception:
            traceback.print_exc()

    def _can_show_modal(self):
        """离屏（测试）下模态 `exec_()` 会让进程原生崩溃 —— 先问平台

        与审查页「清空重审」同一套判断（那是本会话唯一被允许保留模态的形态）。
        """
        try:
            plat = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
            if plat in ("offscreen", "minimal"):
                return False
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                return False
            if str(app.platformName() or "").strip().lower() in ("offscreen", "minimal"):
                return False
            return True
        except Exception:
            traceback.print_exc()
            return False

    def _on_clear_clicked(self):
        """清空**本样本**区域（不可逆 → 要确认框）

        ★ 离屏/测试下弹不了模态 → **拒绝执行**而不是自动放行（与审查页同一策略）：
          宁可测试里清不掉，也不能在没有人类确认时抹掉用户手画的区域。
          测试要覆盖请显式设 `bind._auto_confirm_clear = True`。
        """
        try:
            override = getattr(self, '_auto_confirm_clear', None)
            if override is None:
                if not self._can_show_modal():
                    self._log("当前平台无法弹出确认框（离屏/测试环境）→ 为安全起见未清空")
                    return
                r = QMessageBox.question(
                    self.parent, "确认清空",
                    "将清空样本 %s 的全部手画区域，且不可撤销。\n确定要清空吗？" % self.current_sample,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if r != QMessageBox.Yes:
                    self._log("已取消清空")
                    return
            elif not override:
                self._log("已取消清空（测试覆盖）")
                return
            SREG.set_sample_regions(self.regions_data, self.current_sample, [])
            self._persist(reason="清空本样本区域")
            self._call_canvas(CANVAS_SET_REGIONS, [])
            self._refresh_region_list()
            self.active_region_index = -1
            # ★ 区域全没了 ⇒ 多选快照一并清掉（§3.3），命名控件恢复可用（没有选中区域）
            self._multi_selected_indices = []
            self._apply_anno_enablement(-1)
            self._log("已清空样本 %s 的全部区域" % self.current_sample)
        except Exception:
            traceback.print_exc()

    def _on_confirm_clicked(self):
        """确认 → 算标签 → 计数 → 导出 labels → 调 R 重绘 → 预览 → 落盘 → 报数"""
        try:
            if not self.dataset or not self.current_sample:
                self._log("尚未确定数据集/样本 → 未执行")
                return
            if self.spots_error:
                self._log("⚠ 读不到坐标表，无法确认：%s" % self.spots_error)
                return
            regions = SREG.get_sample_regions(self.regions_data, self.current_sample)
            valid = [r for r in regions if not r.get("invalid")]
            if not valid:
                self._log("本样本一个有效区域都没有（每个区域至少要 3 个顶点）→ 未执行")
                return
            # ★★ v9.3（用户裁定）：**可见区域是可画的标注单元，只有隐形区域不算可画区域**。
            #   旧口径"范围层（`mask` 隐形 **或** `visible` 可见）都不是可画区域"已被推翻：
            #   可见区域**自己也会出图**（带名字），**同时**它仍决定普通区域是否入选 —— 两条并存。
            #   只画了隐形区域的样本必须**明确说清**，不能"什么都不发生" ——
            #   否则用户点『确认』没反应，会以为程序坏了。
            #   ⚠ 判据**只有这一处**，且**不在这里重写** `r.get("mask")`：调本文件 v9.3 收窄后的
            #     `_is_anno_blocked_region`（**只看 `mask`**，自带 `SREG._norm_flag` 的严格布尔
            #     与降级留痕），与命名链路共用同一份语义。
            #   ⛔ **不要**改回 `SREG.is_layer_region(r)`：它把 `visible` 一起排除，
            #     正是本轮"可见区域被漏挡/漏画"这类口径不一致的坑。
            paintable = [r for r in valid if not self._is_anno_blocked_region(r)]
            n_mask = sum(1 for r in valid if self._is_anno_blocked_region(r))
            n_vis = sum(1 for r in valid if r.get("visible"))
            if not paintable:
                self._log("本样本只画了 %d 个隐形区域、没有可画的区域 → 未执行"
                          "（隐形区域只是『罩子』：它决定别的区域能否出现在成图里，"
                          "自己不出图。请再画一个区域（普通区域或可见区域）后重试）" % n_mask)
                return
            if n_mask or n_vis:
                self._log("本样本另有 %d 个隐形区域、%d 个可见区域："
                          "**可见区域自己也会出图**（带名字）—— 它既是一个可画的标注单元，"
                          "同时仍决定普通区域是否入选（普通区域要被可见区域罩住才画）；"
                          "**隐形区域不出图**，只决定别的区域能否出现在成图里"
                          "（某一层没画 ⇒ 该层不过滤）" % (n_mask, n_vis))

            # ① 标签 + 计数
            counts = SREG.count_by_region(self.spots, regions)
            labels = counts.get("labels") or []
            self._log("-" * 40)
            self._log("样本 %s：spot 共 %d 个" % (self.current_sample, counts.get("total", 0)))
            for name, n in (counts.get("counts") or {}).items():
                self._log("  区域『%s』：%d 个 spot" % (name, n))
            self._log("  未覆盖（NA）：%d 个 spot" % counts.get("uncovered", 0))

            # ② 导出 labels CSV（**全 ASCII 路径**，子进程纪律）
            labels_path = SREG.labels_csv_path_for(self.dataset, self.current_sample)
            if not SREG.is_ascii_path(labels_path):
                # 退到系统临时目录（同样断言 ASCII，两道保险）
                labels_path = os.path.join(SREG.temp_dir_fallback(),
                                           "region_labels_%s.csv" % self.current_sample)
            if not SREG.export_labels_csv(self.spots, labels, labels_path):
                self._log("⚠ labels CSV 写出失败：%s" % (SREG.LAST_EXPORT_ERROR or "未知原因"))
                return
            self._log("labels CSV → %s（表头 spot,label；未覆盖写空串）" % labels_path)

            # ③ ★ §14.3 v2：**先把区域持久化，再渲染，渲染成功才补 `rendered_hash`**
            #    为什么把 persist 提到渲染之前：这样 regions.json 一定比 override PNG **旧**，
            #    即使走到"老文件"的 mtime 兼容路径也不会误报 expired（消灭时序窗口）。
            self._persist(reason="确认（渲染前先存区域）")
            render_hash = SREG.regions_hash(self.regions_data, self.current_sample)
            self._log("本次渲染对应的区域哈希 = %s" % render_hash)

            # ③b ★ §15.4：导出**轮廓 + 标签** JSON（R 侧画虚线轮廓与注释用）
            #     ★ 轮廓是**呈现**，判定仍用原始闭合多边形（§15.1）；这里不碰 labels。
            #     `px_per_data`：1 数据单位 = 多少输出图像像素。用它把 `corner_radius_px`
            #     （像素）换算成数据单位。图幅按 300 dpi 的常见输出估算；取不到就传 0
            #     ⇒ R 侧拿到的圆角为 0（尖角），**不会出错**，只是不倒角。
            outline_path = SREG.outline_json_path_for(self.dataset, self.current_sample)
            px_per_data = self._estimate_px_per_data()
            # ★ Phase 4⑤：`chk_label_frame` 是**全局开关**（一个勾选框管所有注释）
            #   ⇒ **总是显式传**，不再靠 `export_outline_json` 回退到逐区域字段
            #   （回退值默认 False ⇒ 勾了也等于没勾）。`export_outline_json` 的 docstring
            #   明写"bind 从 `chk_label_frame` 读"——就是这里。
            label_frame = self._label_frame_checked()
            # ★ v4 第 3 点：注释外框**底色**（`geom_label` 那个圆角矩形）。
            #   取不到 ⇒ `""` ⇒ 不写 `labels[].frame_color` ⇒ R 用默认白底。
            label_frame_color = self._label_frame_color()
            if SREG.export_outline_json(self.regions_data, self.current_sample, self.spots,
                                        outline_path, px_per_data=px_per_data,
                                        label_frame=label_frame,
                                        label_frame_color=(label_frame_color or None)):
                # ★ 日志要说**真的出图了几个**：以前这里报的是"本样本区域总数"，
                #   而**隐形区域**（`mask`）不是出图对象 ⇒ 会打出"区域 3 个"而实际只画 1 个
                #   （用户按这个数字核对会得出错误结论）。现在两个数都给。
                # ★★ v9.3：**可见区域自己也算出图区域**（用户裁定「可见区域就是我的标注单元」、
                #   带名字出图）⇒ 计数口径必须与 `export_outline_json` 的候选集**完全一致**：
                #     `visible_region_indices(...)`（被可见层罩住的**普通**区域）
                #     **∪** {`visible` 标记为真的区域自身}，**去重**
                #     ⇒ 同时"既 `visible` 又被别的可见区域罩住"的区域**只算一次**（不再少报）；
                #     同时带 `mask` 的仍**不算**（mask 优先 ⇒ 它自己永不出图、只做逐段裁剪）。
                #   ⛔ 判据**不在这里另写**：复用 `SREG.visible_region_indices` 与本文件的
                #      `_is_anno_blocked_region`（同一份 v9.3「只看 mask」语义）。
                _regs = SREG.get_sample_regions(self.regions_data, self.current_sample)
                _cand = set(SREG.visible_region_indices(_regs, self.spots) or [])
                _cand |= {i for i, r in enumerate(_regs)
                          if isinstance(r, dict) and r.get("visible")
                          and not self._is_anno_blocked_region(r)}
                _drawn = len(_cand)
                self._log("轮廓 JSON → %s（px_per_data=%.4g，出图区域 %d 个"
                          "（候选：含可见区域自身，去重）/ 本样本区域 %d 个，"
                          "注释外框=%s，注释外框颜色=%s）"
                          % (outline_path, px_per_data, _drawn, len(_regs),
                             "开" if label_frame else "关",
                             label_frame_color or "默认（白底）"))
            else:
                self._log("⚠ 轮廓 JSON 写出失败：%s（仍会出图，只是没有轮廓层）"
                          % (SREG.LAST_EXPORT_ERROR or "未知原因"))
                outline_path = ""

            # ④ 调 W3 的 R 重绘（**一次调用出两张**：带点 + 不带点）
            rds = self._rds_path()
            if not rds:
                self._log("⚠ 找不到成品 .rds → 无法重绘（区域已存盘，可重试）")
                return
            out_dir = SREG.region_override_dir(self.dataset)
            # ★★ `--raw-root`：hires 底图必须从原始切片图根读。
            #    但本机 `SPATIAL_RAW_ROOT` **含中文** ⇒ 我自己的 ASCII 断言会拒绝它
            #    ⇒ 先**暂存到 ASCII 目录**再传（否则永远退 lowres，用户"更美观"落空）。
            raw_root, raw_note = SREG.stage_raw_root_ascii(self.dataset, self.current_sample)
            if raw_note:
                self._log("底图：%s" % raw_note)
            if raw_root:
                self._log("--raw-root = %s" % raw_root)
            else:
                self._log("⚠ 未传 --raw-root（%s）→ R 会退回 lowres 底图（放大后发虚）"
                          % (raw_note or "原因未知"))
            self._log("正在重绘 Spatial_%s.png/pdf + SpatialNoSpots_%s.png/pdf …"
                      "（子进程，不碰图集）" % (self.current_sample, self.current_sample))
            t0 = time.time()
            ok, result, err = SREG.render_sample_regions(
                rds, labels_path, self.current_sample, out_dir, timeout=600,
                outline_json=outline_path or None, no_spots=True,
                raw_root=(raw_root or None),
                # ★ §15.4b：`--spots` 必填（R 自建绘图要自己读原始坐标）。
                #   显式传我们这份，别让它去猜目录结构。
                spots_csv=SREG.spots_path_for(self.dataset))
            dt = time.time() - t0
            if not ok:
                self._log("❌ 重绘失败（%.1f 秒）：%s" % (dt, err))
                self._log("（区域已存盘，但**没有**写入 rendered_hash ⇒ 该样本会显示"
                          "「自定义分区尚未生成或已过期」并仍是图集版 —— 这是如实的）")
                return
            png = str(result.get("png") or "")
            pdf = str(result.get("pdf") or "")
            self._log("重绘完成（%.1f 秒）：" % dt)
            # ★ R 侧自己的三个数（协调者点名要报）：入图多少 / 丢了多少 / 多少没圈到
            #   · `spots_plotted`          实际画进图里的 spot 数
            #   · `dropped_not_in_labels`  在 spots.csv 里但 labels 表里没有 → 被丢掉
            #   · `na`                     用户没圈到（标签为空）→ 图上灰色
            #   ⚠ 这三个数与我在上面用 `count_by_region` 自己算的**不是同一套账**
            #     （我算的是"标签分布"，R 算的是"画图时的取舍"），所以两个都报。
            r_spots = result.get("spots_plotted")
            r_drop = result.get("dropped_not_in_labels")
            r_na = result.get("na")
            r_labeled = result.get("labeled")
            r_in_sample = result.get("spots_in_sample")
            self._log("  R 侧报数：入图 spots_plotted = %s / 本样本 spots_in_sample = %s"
                      % (r_spots, r_in_sample))
            self._log("  R 侧报数：已圈 labeled = %s，未圈 NA = %s，被丢 dropped_not_in_labels = %s"
                      % (r_labeled, r_na, r_drop))
            if result.get("region_labels"):
                self._log("  R 侧图例区域：%s" % result.get("region_labels"))
            for key in ("png_bytes", "pdf_bytes"):
                if result.get(key) is not None:
                    self._log("  %s = %s" % (key, result.get(key)))
            if result.get("elapsed_sec") is not None:
                self._log("  R 侧 elapsed_sec = %s" % result.get("elapsed_sec"))
            # ★★ 底图等级必须**明确报出来**（协调者点名）：
            #    `base_image` = `hires` / `lowres`。若显示 lowres，说明 hires 没走通
            #    （放大到 2400×2100 会发虚，正好毁掉用户"更美观"的诉求）——
            #    **不能让用户以为底图已经升级了**。
            base_img = str(result.get("base_image") or "").strip()
            base_fit = result.get("base_fit")
            base_note = result.get("base_image_note")
            if base_img:
                if base_img.lower().startswith("hires"):
                    self._log("  底图 = **hires**（高清）base_fit=%s" % base_fit)
                else:
                    self._log("  ⚠ 底图 = **%s**（不是 hires！放大后会发虚）base_fit=%s"
                              % (base_img, base_fit))
                    self._log("     ⇒ 说明 `--raw-root` 那条路没走通"
                              "（检查 SPATIAL_RAW_ROOT 与原始切片图是否在）")
            else:
                self._log("  ⚠ R 未回报底图等级（base_image 缺失）—— 请检查 W3 的摘要字段")
            if base_note:
                self._log("  底图说明：%s" % base_note)
            if result.get("raw_root_note"):
                self._log("  ⚠ %s" % result.get("raw_root_note"))
            if result.get("raw_root"):
                self._log("  --raw-root = %s" % result.get("raw_root"))
            # ★ 轮廓以 **B 形状**（带 styles 的对象）为准、A 形状保留兼容。
            #   R 会回报它到底按哪种形状解析的 —— **必须报出来**，
            #   否则"R 悄悄退回 A 形状、样式全丢"这种降级没人看得见。
            if result.get("outline_shape") is not None:
                self._log("  R 解析到的轮廓形状 = %s（期望 B/带样式）" % result.get("outline_shape"))
            if result.get("n_segments") is not None:
                self._log("  轮廓段数 = %s（带样式 %s / 跳过 %s）"
                          % (result.get("n_segments"), result.get("segments_styled"),
                             result.get("segments_skipped")))
            # ★ §15.4b 新增的三个摘要字段也报出来（不报就等于没解析）：
            #   `spots_hidden` = 无点图里藏掉的 spot 数；`nospot_ok` = 不带点图是否成功；
            #   `encoding_ok` = 中文字体是否生效（用户②的乱码问题看这个）。
            if result.get("spots_hidden") is not None:
                self._log("  无点图隐藏 spot = %s" % result.get("spots_hidden"))
            if result.get("nospot_ok") is not None:
                self._log("  不带点图成功 = %s" % result.get("nospot_ok"))
            if result.get("encoding_ok") is not None:
                ok_enc = result.get("encoding_ok")
                self._log("  中文字体生效 = %s%s" % (ok_enc, ""
                          if ok_enc else "  ← ⚠ 中文可能显示为方块，检查 showtext/字体路径"))
            self._log("  PNG → %s%s" % (png, "" if (png and os.path.isfile(png)) else "（未找到该文件！）"))
            self._log("  PDF → %s%s" % (pdf, "" if (pdf and os.path.isfile(pdf)) else "（未找到该文件！）"))
            if result.get("stderr_tail"):
                self._log("  R stderr 末尾：%s" % str(result.get("stderr_tail"))[-300:])

            # 预览：**两张都贴**（带点 → 主预览；不带点 → §15.5 的第二预览）
            self._show_preview(png, 'region_preview_label')
            ns_png = str(result.get("nospot_png") or "")
            if not ns_png or not os.path.isfile(ns_png):
                # ★ 契约 §15.5：没有不带点那张就明确写"尚未生成"，**绝不拿带点版冒充**
                d_ns, _d = SREG.nospot_output_paths(self.dataset, self.current_sample)
                self._log("⚠ 不带点那张未生成（期望 %s）→ 第二预览显示『该图尚未生成』"
                          % (ns_png or d_ns))
                self._show_preview("", 'region_preview_nospot_label')
            else:
                self._show_preview(ns_png, 'region_preview_nospot_label')
                self._log("  不带点 PNG → %s" % ns_png)
            ns_pdf = str(result.get("nospot_pdf") or "")
            if ns_pdf:
                self._log("  不带点 PDF → %s%s"
                          % (ns_pdf, "" if os.path.isfile(ns_pdf) else "（未找到该文件！）"))

            # ⑤ ★★ §14.3 v2 的"已确认"凭据：渲染成功后**写回该样本的 `rendered_hash`**。
            #    这是判定"不过期"的唯一依据（替代原来那个结构上不成立的 mtime 比较）：
            #      · 只动**本样本**这一个字段 ⇒ 给 B 确认**不会**连带把 A 判过期；
            #      · 内容哈希比对没有时序窗口 ⇒ 存完 regions 比图新也无所谓。
            #    ★ §15.5 的不带点那张与带点那张**共用这一个凭据**（同一次 R 调用产出），
            #      所以第 24 页签的新鲜度自动与带点版一致。
            SREG.set_rendered_hash(self.regions_data, self.current_sample, render_hash)
            self._persist(reason="确认并重绘（已写入 rendered_hash）")
            self._log("已写入 rendered_hash = %s（该样本的「自定义分区」现在生效）" % render_hash)
        except Exception as e:
            traceback.print_exc()
            self._log("⚠ 确认流程异常：%s: %s" % (type(e).__name__, e))

    def _estimate_px_per_data(self):
        """估算"1 个数据单位 = 多少输出图像像素"（给圆角换算用）

        ★ 这是**估算**，只影响倒角大小，不影响任何判定：
          取该样本 spot 的跨度与 R 侧输出图幅的常见像素数（300 dpi 下 ~2400 px 量级）。
          拿不到 spot 就返回 `0.0` ⇒ `region_outline_paths` 不倒角（尖角），**不会出错**。
        ★ 为什么不查 scalefactor：那是**底图**的像素/数据比例（W1 的画布在用），
          而这里要的是"R 输出图的像素/数据比例"，两者不是一回事。
        """
        try:
            bbox = SREG._spots_bbox(self.spots, margin=0)
            if not bbox:
                return 0.0
            x0, y0, x1, y1 = bbox
            span = max(abs(x1 - x0), abs(y1 - y0))
            if span <= 0:
                return 0.0
            return 2400.0 / span          # 输出图长边约 2400 px（300 dpi 常见量级）
        except Exception:
            traceback.print_exc()
            return 0.0

    def _show_preview(self, png_path, widget_name='region_preview_label'):
        """把重绘出的 PNG 贴到预览控件（默认带点那张；§15.5 的第二张走 `widget_name`）

        ★ 兼容两种控件：`ZoomableImageLabel`（有 `set_pixmap`）与普通 QLabel（`setPixmap`）。
          两者都没有 → 留痕（不静默）。
        """
        try:
            lbl = self._ctl(widget_name)
            if lbl is None:
                self._warn_once("no_preview_%s" % widget_name,
                                "布局未提供 %s → 无法预览" % widget_name)
                return
            if not png_path or not os.path.isfile(png_path):
                self._log("⚠ 预览跳过（%s）：PNG 不存在（%s）"
                          % (widget_name, png_path or "路径为空"))
                # ★ 控件在但没有图 → 明确显示"尚未生成"，**不留白板也不假装有图**
                self._set_preview_text(lbl, "该图尚未生成")
                return
            pm = QPixmap(str(png_path))
            if pm.isNull():
                self._log("⚠ 预览失败：图片读不出来（%s）" % png_path)
                return
            fn = getattr(lbl, 'set_pixmap', None)
            if callable(fn):
                fn(pm)
            elif hasattr(lbl, 'setPixmap'):
                lbl.setPixmap(pm)
            else:
                self._warn_once("preview_api",
                                "%s 既没有 set_pixmap 也没有 setPixmap" % widget_name)
                return
            self._log("预览已更新（%s）：%dx%d px" % (widget_name, pm.width(), pm.height()))
        except Exception:
            traceback.print_exc()

    @staticmethod
    def _set_preview_text(lbl, text):
        """给预览控件写提示文字（QLabel 走 setText；ZoomableImageLabel 也支持 setText）"""
        try:
            if lbl is not None and hasattr(lbl, 'setText'):
                lbl.setText(str(text))
        except Exception:
            traceback.print_exc()

    def _persist(self, reason=""):
        try:
            ok = SREG.save_regions(self.dataset, self.regions_data)
            if ok:
                self._log("区域已保存（%s）" % reason)
                # 自己刚写完 → 对齐幂等键，避免"自己刷自己"
                self._entered_key = (self.dataset, SREG.regions_version(self.dataset))
                # ★ 区域数变了 → 该样本的"已画/未画"文案要跟着变（§14.2）
                self._restamp_sample_item(self.current_sample)
            else:
                self._log("⚠ 区域保存失败（%s）—— 请检查 appdata 目录权限" % reason)
            return ok
        except Exception:
            traceback.print_exc()
            return False

    # ==================================================================
    def _set_empty_hint(self, msg):
        """空/异常提示：没有专门的 hint 控件时退到日志（**不静默**）"""
        try:
            hint = self._ctl('region_empty_hint')
            if hint is not None and hasattr(hint, 'setText'):
                hint.setText(str(msg or ""))
                hint.setVisible(bool(msg))
            elif msg:
                self._log(msg)
        except Exception:
            traceback.print_exc()

    def set_volume(self, value):
        """设置音量（与其它顶层/子页同形，供 fix_music_controller_bindings 调用）"""
        try:
            from script.mods_layer.mod_manager import global_mod_manager
            mod_instance = global_mod_manager.get_current_mod()
            if hasattr(mod_instance, 'global_music_player'):
                mod_instance.global_music_player.set_volume(value / 100.0)
        except Exception:
            traceback.print_exc()


__all__ = ['SpatialRegionBind']
