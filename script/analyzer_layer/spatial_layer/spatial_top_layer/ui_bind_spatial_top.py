# -*- coding: utf-8 -*-
"""
空转分析顶层导航界面功能绑定脚本 - 全权负责粘合内外
绑定信号 + 编排 analysis 与 func 的协作

M1 v2：加载数据集要**真读**（rpy2 readRDS，实测 475 MB ≈ 4.6–5.7 秒 / ≈2.4 GB 内存）。

★ 读取线程的选择（**判决性实验后定案：默认走后台 worker**）
  判据实验（干净进程、生产顺序、连续 5 次）：
      ① QApplication ② 建页面 ③ **主线程** prepare_dataset()（内含
      `_ensure_r_ready_on_caller_thread()` → 强制走一遍 get_robjects()）
      ④ SpatialReadWorker(...).start() ⑤ 等 finished_signal
      结果 **5/5 SUCCESS，exit=0，worker 墙钟 5.60–5.65 秒，均成功入内存 2433.3 Mb**。
  复现命令：`python -u debug_output/_w2_verdict_worker.py <run_index>`（脚本每次独立进程）

  **必要条件（缺一即崩）**：worker 里调 read_into_r() **之前**，必须已在**主线程**完成 R 初始化。
  依据：`RKernelInterface._initialize_rpy2()` 在"未初始化"时调 `rpy2.rinterface.initr()`，
  而 R 只允许在**初始化它的那个线程**里使用 → 一旦这步落在工作线程上就是
  **原生访问违例（exit 0xC0000005，无 Python traceback）**。
  实测两种失败配置（**都已不再出现在生产路径里**）：
    · 配置甲：worker 里**直接** read_into_r()，**从未**在主线程 prepare_dataset() → 崩；
    · 配置乙：主线程只调了 `is_r_available()`（**没有** get_robjects()）就起 worker → 仍崩
      （`is_r_available()` 只读标志位，不足以完成 R 初始化）。
  另一条已修的坑：rpy2 的转换规则存在 `contextvars.ContextVar` 里、**不跨线程继承**
  → 已加 `r_conversion_context()`（`localconverter(default_converter)`）在 worker 线程内激活。

  **兜底**：若某个环境的 `_ensure_r_ready_on_caller_thread()` 返回 False（R 没能就绪），
  本文件**自动降级为主线程同步读**（那条路径已实测稳定），并如实写日志。
  **代价（降级时）**：点击后界面卡约 5 秒 —— 因此降级路径也照样先写「正在读取…」+ 禁用按钮。
"""

from script.utils_layer.import_config import *
# 具名导入：该常量现已在 import_config.py 的 __all__（:337 已收录 'SPATIAL_SCAN_DATA_PATH'
# 与 'SPATIAL_RAW_ROOT'）；此处保留具名导入以防再次漂移（曾有一段时间它不在 __all__）。
from script.utils_layer.import_config import SPATIAL_SCAN_DATA_PATH
import time
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from script.mods_layer.mod_manager import global_mod_manager
from script.analyzer_layer.spatial_layer.spatial_top_layer.ui_func_spatial_top import SpatialTopFunc
from script.analyzer_layer.spatial_layer.spatial_top_layer.spatial_data_analysis import SpatialDataManager
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.gui_styles import bind_button_with_sound
from script.utils_layer.page_intersect import page_intersect
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong

# 子页面路由名（以 `page_intersect.py` 的 page_configs 已注册的 name 为准 —— 协调者实测已加）
REVIEW_PAGE_NAME = 'spatial_review_page'
INITIAL_PAGE_NAME = 'spatial_initial_page'
# ★ 2026-09-20 第二轮拍板：「表达量分析」**真拆成独立子页面**（不再与初始页共用"大类切换"）
EXPRESSION_PAGE_NAME = 'spatial_expression_page'
# ★ 绘制区域：用户 2026-09-20 拍板把它从审查页**剥离为 hub 的独立入口**（双入口）
REGION_PAGE_NAME = 'spatial_region_page'
# ★ 差异分析：hub 新增的第 4 分类「基因列表类」下的卡片（规格 §2/§3）。
#   与单细胞 `btn_diff_analysis` 的文案「差异分析」逐字一致，路由名见 page_intersect.py。
SPATIAL_DIFF_PAGE_NAME = 'spatial_diff_page'
# ★ v11（2026-09-25）三个新子页（规格 `_d_spec_v11_split_and_bubble.md` §1/§2）：
#   ① 小提琴图**从表达量页解离**为独立子页；② ③ 空转两种气泡图（1:1 复刻单细胞）。
#   路由名逐字等于 `page_intersect.py` 里登记的 `name`（也是 `attr_name`）。
VIOLIN_PAGE_NAME = 'spatial_violin_page'
GENELIST_BUBBLE_PAGE_NAME = 'spatial_genelist_bubble_page'
TARGETGENE_BUBBLE_PAGE_NAME = 'spatial_targetgene_bubble_page'


class SpatialReadWorker(QThread):
    """后台读取 .rds 进 R globalenv 的 worker（照 bulk 的 PcaWorker 范式）

    前置条件（见文件头）：调用方必须**已在主线程**跑过 `prepare_dataset()`
    （它内含 `_ensure_r_ready_on_caller_thread()`，把 R 初始化钉在主线程）。

    线程内**只碰 analysis（纯 Python/R）**，**绝不碰任何 Qt 控件**；
    所有日志/控件更新都回到主线程的 finished_signal 槽里做。
    """

    finished_signal = pyqtSignal(bool, str)

    def __init__(self, analysis, parent=None):
        super().__init__(parent)
        self.analysis = analysis

    def run(self):
        try:
            success, error = self.analysis.read_into_r()
        except Exception as e:
            # run() 里绝不抛：抛了会让 QThread 静默死掉、finished 不发、按钮永久禁用
            traceback.print_exc()
            success, error = False, f"后台读取线程异常: {e}"
        try:
            self.finished_signal.emit(bool(success), str(error or ""))
        except Exception:
            traceback.print_exc()


class SpatialTopBind:
    """空转分析顶层导航界面功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, ui_instance):
        self.parent = parent_window
        self.ui = ui_instance
        self.func = SpatialTopFunc(ui_instance, parent_window)
        self.analysis = SpatialDataManager()
        self.read_worker = None      # 后台读取线程句柄（重入判断 + 兜底检查都用它）
        self._loading = False        # 重入守卫（防连点 → 防重复读 → 防内存翻倍）
        self._load_started_at = 0.0  # 本次读取开始时间（兜底定时器判据）
        self._watchdog = None        # 兜底定时器：防 finished_signal 丢失导致按钮永久禁用
        # ★ 契约 C1：跨页传「待审查样本」。审查页 bind 进入时**读后即清**。
        #   放在顶层 bind（而不是 page_intersect）→ 不需要改那个共享热点文件。
        self.pending_review_sample = None
        # ⏱ `pending_initial_category` **已退休**（2026-09-20 第二轮拍板）：
        #   「表达量分析」真拆成独立子页面后，"初始页该开哪个大类"这个跨页传参
        #   **不再需要** —— 点哪张卡片就直接去哪个页面，不需要页面内部再切大类。
        #   ⚠ 别再加回来：契约里该字段已标 ⏱ 已退休。
        self.init_bindings()

    def init_bindings(self):
        """初始化所有绑定"""
        self.bind_music_controls()
        self.bind_navigation()
        self.bind_data_loading()

    def bind_navigation(self):
        """绑定页面导航 —— **分类（页内切面板）+ 图片卡片（跳独立页面）** 的 hub

        ## ★★ 两类按钮语义**不同**，别照抄（纪律）
          · **分类导航** `nav_btn_cat_overview` / `nav_btn_cat_initial` /
            `nav_btn_cat_genelist` 以及 `nav_btn_data` → **页内切面板**
            （`self.ui.show_panel(...)`），**不跳页**；
            （`nav_btn_cat_draw` 已随 W1 的布局退休，**不再接**。）
          · **图片卡片** `btn_card_overview` / `btn_card_review` / `btn_card_expression` /
            `btn_card_region` / `btn_card_spatial_diff` / `btn_card_violin` /
            `btn_card_targetgene_bubble` / `btn_card_genelist_bubble` → **跳转到独立页面**
            （`page_intersect.go_to_page_with_bind`）；
          · `nav_btn_back` → 回主界面（`page_intersect.go_to_home`）。
        路由名以 `page_intersect.py` 已注册的 `name` 为准
        （`spatial_review_page` / `spatial_initial_page` / `spatial_expression_page` /
        `spatial_region_page` / `spatial_diff_page` / `spatial_violin_page` /
        `spatial_targetgene_bubble_page` / `spatial_genelist_bubble_page`）。

        ## ★ 八张卡片 = 八个**独立页面**（2026-09-20 拍板 + 2026-09-25 差异分析 + v11 三页）
          总览 → 初始页；审查 → 审查页；**表达量分析 → 表达量页（新拆出来的）**；
          绘制区域 → 绘制区域页；**差异分析 → 差异分析页（第 4 分类「基因列表类」）**；
          **v11（2026-09-25，规格 §1/§2）**：「初步分析类」再加 3 张 ——
          **小提琴图 → `spatial_violin_page`（从表达量页解离）**、
          **自定义气泡图 → `spatial_targetgene_bubble_page`**、
          **基因集气泡图 → `spatial_genelist_bubble_page`**。
          ⇒ 不再需要 `pending_initial_category` 那种"跨页传大类"的约定
            （它已随本轮拆分**退休**）。

        ## ★ 更早退休的接线（不留死代码）
          `nav_btn_initial` / `nav_btn_review` / `btn_goto_review` 三段已删除 ——
          旧版"导航按钮直接跳子页"的模型被卡片取代。
          `_goto_review_page` / `_goto_initial_page` 两个 helper **保留复用**。
        """
        if hasattr(self.ui, 'nav_btn_back'):
            self.ui.nav_btn_back.clicked.connect(page_intersect.go_to_home)

        if hasattr(self.ui, 'nav_btn_data'):
            self.ui.nav_btn_data.clicked.connect(lambda: self.ui.show_panel('data'))

        # —— 分类导航：**页内切面板**（不跳页）——
        # ★ 2026-09-25（规格 §2 B1）：新增第 4 分类「基因列表类」→ `nav_btn_cat_genelist`。
        #   ⛔ 这里**只有这一份**面板名清单（不许在别处再抄一份）；缺失走 `_warn_missing_control`。
        for attr, panel in (('nav_btn_cat_overview', 'overview_review'),
                            ('nav_btn_cat_initial', 'initial_analysis'),
                            ('nav_btn_cat_genelist', 'genelist')):
            btn = getattr(self.ui, attr, None)
            if btn is None:
                self._warn_missing_control(attr)
                continue
            try:
                btn.clicked.connect(lambda _checked=False, p=panel: self.ui.show_panel(p))
            except Exception:
                traceback.print_exc()

        # —— 卡片：**跳各自独立页面**（★ 第 5 张 = 第 4 分类「基因列表类」的差异分析；
        #    ★ v11 再加 3 张：「初步分析类」里的小提琴图 / 自定义气泡图 / 基因集气泡图）——
        for attr, handler in (('btn_card_overview', self._on_card_overview),
                              ('btn_card_review', self._goto_review_page),
                              ('btn_card_expression', self._on_card_expression),
                              ('btn_card_region', self._goto_region_page),
                              ('btn_card_spatial_diff', self._goto_spatial_diff_page),
                              ('btn_card_violin', self._goto_violin_page),
                              ('btn_card_targetgene_bubble',
                               self._goto_targetgene_bubble_page),
                              ('btn_card_genelist_bubble',
                               self._goto_genelist_bubble_page)):
            btn = getattr(self.ui, attr, None)
            if btn is None:
                self._warn_missing_control(attr)
                continue
            try:
                btn.clicked.connect(lambda _checked=False, h=handler: h())
            except Exception:
                traceback.print_exc()

    def _warn_missing_control(self, name):
        """冻结控件名在布局里缺失 → **留痕一次**（不刷屏、不抛）

        ★ 为什么不做"旧控件兜底"：那会让后人以为旧接线还活着（用户明确要求
          "退休要彻底"）。缺失就**如实报出来**，等 W1 的布局到位。
        """
        try:
            seen = getattr(self, '_warned_missing_controls', None)
            if seen is None:
                seen = set()
                self._warned_missing_controls = seen
            if name in seen:
                return
            seen.add(name)
            self.func.log("⚠ 布局缺少控件 %s → 该入口未绑定（需要 W1 提供）" % name)
        except Exception:
            traceback.print_exc()

    def _on_card_overview(self):
        """『总览』卡片 → 初始页（**不再设大类**：总览就是初始页自身）"""
        self._goto_initial_page()

    def _goto_expression_page(self):
        """跳转到「表达量分析」子页面（**独立页面**，2026-09-20 真拆出来）"""
        try:
            page_intersect.go_to_page_with_bind(EXPRESSION_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转表达量分析失败（详见控制台 traceback）")
            except Exception:
                pass

    def _on_card_expression(self):
        """『表达量分析』卡片 → **直接跳独立页面**（不再设 pending、不再跳初始页）"""
        self._goto_expression_page()

    def bind_data_loading(self):
        """绑定数据加载相关控件（照 ui_bind_bulk_top.py:103-109 形状）

        只做信号绑定与编排：不解析 JSON、不判断文件（那些归 analysis）。
        """
        if hasattr(self.ui, 'btn_spatial_select_path'):
            bind_button_with_sound(
                self.ui.btn_spatial_select_path,
                self.select_data_path,
                log_widget=getattr(self.ui, 'spatial_status_text', None),
                success_msg="扫描完成",
                failure_msg="扫描失败")

        if hasattr(self.ui, 'btn_spatial_load'):
            bind_button_with_sound(
                self.ui.btn_spatial_load,
                self.load_data,
                log_widget=getattr(self.ui, 'spatial_status_text', None),
                success_msg="加载完成",
                failure_msg="加载失败")

    # ==================================================================
    # 子页面跳转（契约 C1 + page_intersect 已注册的路由名）
    # ==================================================================
    def _goto_review_page(self):
        """跳转到「审查模式」子页面（路由名以 page_intersect 注册的为准）"""
        try:
            page_intersect.go_to_page_with_bind(REVIEW_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转审查模式失败（详见控制台 traceback）")
            except Exception:
                pass

    def _goto_initial_page(self):
        """跳转到「初步分析」子页面"""
        try:
            page_intersect.go_to_page_with_bind(INITIAL_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转初步分析失败（详见控制台 traceback）")
            except Exception:
                pass

    def _goto_region_page(self):
        """跳转到「绘制区域」子页面（**hub 的独立入口**）

        ★ 用户 2026-09-20 拍板：绘图模式从审查页**剥离**，hub 与审查页**双入口**
          （审查页里那个入口保留不动）。
        """
        try:
            page_intersect.go_to_page_with_bind(REGION_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转绘制区域失败（详见控制台 traceback）")
            except Exception:
                pass

    def _goto_spatial_diff_page(self):
        """跳转到「差异分析」子页面（第 4 分类「基因列表类」下**唯一**的卡片）

        ★ 规格 §2 B3：与 `_goto_region_page`（:251-264）**同款写法** ——
          路由名走模块常量、跳转失败只留痕不抛（hub 的入口点绝不能崩）。
        ★ 本页是单细胞 `py_diff/ui_bind_diff.py`（`diff_page`）的近似 1:1 复刻，
          外加「按所选样本动态生成注释分组/注释值」的空转特有逻辑（规格 §4）。
        """
        try:
            page_intersect.go_to_page_with_bind(SPATIAL_DIFF_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转差异分析失败（详见控制台 traceback）")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # v11 三个新子页的跳转（规格 §1.5 / §2.2）
    #   照 `_goto_spatial_diff_page`（:275-290）**同款写法**：路由名走模块常量、
    #   跳转失败**只留痕不抛**（hub 的入口点绝不能崩）；
    #   ⛔ 不传 `parent_bind`（与单细胞 hub 的卡片接线一致）。
    # ------------------------------------------------------------------
    def _goto_violin_page(self):
        """跳转到「小提琴图」子页面（v11：从表达量页**解离**出来的独立子页）"""
        try:
            page_intersect.go_to_page_with_bind(VIOLIN_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转小提琴图失败（详见控制台 traceback）")
            except Exception:
                pass

    def _goto_targetgene_bubble_page(self):
        """跳转到「自定义气泡图」子页面（1:1 复刻单细胞 `sc_targetgene_bubble_page`）"""
        try:
            page_intersect.go_to_page_with_bind(TARGETGENE_BUBBLE_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转自定义气泡图失败（详见控制台 traceback）")
            except Exception:
                pass

    def _goto_genelist_bubble_page(self):
        """跳转到「基因集气泡图」子页面（1:1 复刻单细胞 `sc_genelist_bubble_page`）"""
        try:
            page_intersect.go_to_page_with_bind(GENELIST_BUBBLE_PAGE_NAME)
        except Exception:
            traceback.print_exc()
            try:
                self.func.log("跳转基因集气泡图失败（详见控制台 traceback）")
            except Exception:
                pass

    # ==================================================================
    # 扫描
    # ==================================================================
    def select_data_path(self):
        """扫描数据路径，把数据集名填进下拉框（只编排，不读数据文件）"""
        try:
            if self._is_loading():
                self.func.log("正在读取数据集，请稍候...")
                return

            self.func.log("=" * 40)
            self.func.log("开始扫描数据路径...")

            folder_path = SPATIAL_SCAN_DATA_PATH
            self.func.log(f"扫描目录: {folder_path}")
            exists = os.path.exists(folder_path)
            self.func.log(f"路径是否存在: {exists}")

            datasets = self.analysis.scan_data_folder(folder_path)

            if not datasets:
                if not exists:
                    msg = f"扫描路径不存在: {folder_path}"
                else:
                    msg = f"{folder_path} 中没有找到可用的数据集（需要 *.manifest.json + 同名 .rds）"
                self.func.log(msg)
                # 属正常空状态：不发警告音、不弹窗
                self.func.set_combo_items(self._dataset_combo(), [], keep_selection=False)
                return

            self.func.set_combo_items(self._dataset_combo(), datasets, keep_selection=True)
            self.func.log(f"扫描成功，找到 {len(datasets)} 个数据集: {', '.join(datasets)}")
        except Exception as e:
            traceback.print_exc()
            try:
                self.func.log(f"扫描数据路径失败: {e}")
                attention(self.parent, f"扫描数据路径失败: {e}")
            except Exception:
                pass

    # ==================================================================
    # 加载（秒开段在主线程 + 真读段默认后台，见文件头）
    # ==================================================================
    def load_data(self):
        """加载选中的数据集：读清单 → 校验 → **真读 .rds 进 R**（默认后台线程）

        界面表现：点下 → 秒开段立刻出样本清单 → 写「正在读取…」并禁用两个按钮 →
        后台读约 5 秒（**界面不冻结**）→ finished_signal 回主线程写真实结果 → 恢复按钮。
        """
        # 重入守卫（防连点）：必须在最外层，且不依赖 try 里的任何状态
        if self._loading:
            try:
                self.func.log("正在读取数据集，请稍候...")
            except Exception:
                pass
            return

        self._loading = True
        try:
            combo = self._dataset_combo()
            if combo is None or not hasattr(combo, 'currentText'):
                self.func.log("未找到数据集下拉框，无法加载")
                return

            selected = (combo.currentText() or "").strip()
            if not selected:
                self.func.log("请先扫描数据路径并选择一个数据集")
                attention(self.parent, "请先选择一个数据集")
                return

            # 幂等：同一数据集已经在内存里，就不要重复读（用户连点/重复点的常见情形）
            if self.analysis.data_in_memory and self.analysis.dataset_name == selected:
                self.func.log(f"数据集 {selected} 已在内存中，无需重复读取")
                self.func.log(self.analysis.get_memory_text())
                return

            self.func.log("=" * 40)
            self.func.log(f"正在加载数据集: {selected}")

            # ② 第一段（秒开，主线程；**同时把 R 初始化钉在主线程**——worker 的硬前提）
            manifest, error = self.analysis.prepare_dataset(selected)
            if manifest is None:
                self.func.log(f"加载失败: {error}")
                attention(self.parent, error)
                return

            # —— 清单已就绪：样本清单先显示出来（即使后面读数据失败，UI 也可用）——
            info = self.analysis.get_data_info()
            dataset_label = info.get('dataset') or selected
            n_samples = info.get('n_samples')
            n_spots = info.get('n_spots')
            summary_text = f"已加载：{dataset_label}"
            if n_samples is not None and n_spots is not None:
                summary_text += f"（{n_samples} 样本 / {n_spots:,} spots）"
            elif n_samples is not None:
                summary_text += f"（{n_samples} 样本）"
            self.func.log(summary_text)
            self.func.update_data_info(info)

            # ③ 主对象校验结果 + 清单提示（如实写出）
            artifact = self.analysis.artifact_info or {}
            if artifact.get('ok'):
                self.func.log(
                    f"主对象校验通过: {os.path.basename(artifact.get('path', ''))} "
                    f"({artifact.get('size_mb')} MB)")
            for warn in (artifact.get('warnings') or [])[:2]:
                self.func.log(f"警告 {warn}")
            for issue in (self.analysis.manifest_issues or [])[:3]:
                self.func.log(f"清单提示: {issue}")
            if artifact.get('bytes_match') is None:
                self.func.log("警告 清单未记录基准体积，已跳过体积比对")

            samples = self.analysis.get_sample_list()
            self.func.log(f"样本清单: {len(samples)} 条")
            self.func.update_sample_list(samples, selected)
            self.func.log(f"目标 R 对象名: {self.analysis.r_object_name}")

            # dataset_output_dir 按既有惯例创建（bulk_data_analysis.py:71-72 同款副作用）
            if self.analysis.dataset_output_dir:
                os.makedirs(self.analysis.dataset_output_dir, exist_ok=True)

            # ④ 读数据前：先把反馈写出来并禁用按钮（用户要能看到"在干活、别点"）
            size_mb = artifact.get('size_mb')
            self.func.log(
                f"正在读取数据集"
                f"（{size_mb if size_mb is not None else '?'} MB，约 5 秒）…")
            self._set_buttons_enabled(False)
            self.func.refresh()   # 立刻让上面这句话可见

            # ⑤ 真读：默认后台 worker；同步路径作为兜底（见文件头与 SPATIAL_LOAD_SYNC 开关）
            use_sync = self._force_sync_load()
            if use_sync:
                self.func.log("（同步模式）开始读取…界面会短暂卡顿")
                self.func.refresh()
                success, read_error = self.analysis.read_into_r()
                self._finish_load(success, read_error)
            elif self.analysis.r_ready_on_caller_thread:
                self._load_started_at = time.time()
                self.read_worker = SpatialReadWorker(self.analysis)
                self.read_worker.finished_signal.connect(self._on_read_finished)
                self.read_worker.start()
                self._start_watchdog()
            else:
                self.func.log("（降级）R 未能在主线程就绪，改用同步读取（界面会短暂卡顿）")
                self.func.refresh()
                success, read_error = self.analysis.read_into_r()
                self._finish_load(success, read_error)
        except Exception as e:
            traceback.print_exc()
            try:
                self.func.log(f"加载数据集失败: {e}")
                attention(self.parent, f"加载数据集失败: {e}")
            except Exception:
                pass
            # 异常路径也必须收尾（否则按钮永久禁用）
            self._loading = False
            self._set_buttons_enabled(True)

    # ------------------------------------------------------------------
    # 收尾（后台/同步/兜底三条路径共用，幂等）
    # ------------------------------------------------------------------
    def _finish_load(self, success, error):
        """写入读取结果 + 恢复按钮与守卫（幂等：可被 finished 槽或兜底定时器调用）"""
        try:
            self._loading = False
            self._stop_watchdog()
            self._set_buttons_enabled(True)

            # 延时释放上一轮退役下来的 R 对象（rm + gc 不在读的回调里同步做）
            try:
                QTimer.singleShot(0, self._release_stale_object)
            except Exception:
                self._release_stale_object()

            memory_text = self.analysis.get_memory_text()
            if success:
                self.func.log(memory_text or "已读入内存")
                info = self.analysis.memory_info or {}
                if info.get('n_spots') is not None and info.get('n_genes') is not None:
                    self.func.log(f"内存对象: {info.get('object_name')} "
                                  f"（{info.get('n_spots')} spots × {info.get('n_genes')} genes）")
                self.func.log("加载完成")
            else:
                self.func.log(f"数据未进内存: {error}")
                # ⚠ 关键：清单/样本清单仍然可用，必须明确告知，不能让 UI 看起来像成功了
                self.func.log_memory_state(memory_text, False)
                self.func.log("样本清单仍可用；需要真实数据的功能请在 R 环境恢复后重试")
                try:
                    attention(self.parent, f"数据未进内存:\n{error}")
                except Exception:
                    pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.func.log(f"处理读取结果时出错: {e}")
            except Exception:
                pass
        finally:
            self.read_worker = None

    def _on_read_finished(self, success, error):
        """后台读数据完成的槽（主线程）"""
        self._finish_load(success, error)

    # ------------------------------------------------------------------
    # 兜底定时器：防 finished_signal 丢失导致按钮永久禁用
    # ------------------------------------------------------------------
    def _start_watchdog(self):
        """启动兜底定时器（真实生效，不是占位）

        ★ 为什么需要：QThread 里 emit 的信号经事件队列投递；一旦因为任何原因
          （事件循环被打断、线程对象被提前回收等）主线程没收到 finished_signal，
          用户会看到**两个按钮永久灰掉**、只能重启程序 —— 比慢 5 秒糟糕得多。
          兜底判据：标志位仍在 + 线程已不 running + 已超过最小等待时长 → 主动收尾。
        """
        try:
            if self._watchdog is None:
                self._watchdog = QTimer()
                self._watchdog.setInterval(500)
                self._watchdog.timeout.connect(self._watchdog_tick)
            self._watchdog.start()
        except Exception:
            traceback.print_exc()

    def _stop_watchdog(self):
        try:
            if self._watchdog is not None and self._watchdog.isActive():
                self._watchdog.stop()
        except Exception:
            traceback.print_exc()

    def _watchdog_tick(self):
        """兜底检查：线程已结束但还没收尾 → 主动收尾（幂等，正常路径不会走到）"""
        try:
            if not self._loading:
                self._stop_watchdog()
                return
            worker = self.read_worker
            still_running = bool(worker is not None and hasattr(worker, 'isRunning')
                                 and worker.isRunning())
            if still_running:
                return
            if time.time() - self._load_started_at < 1.0:
                return
            self.func.log("（兜底）后台读取已结束但未收到完成通知，按已结束处理")
            self._finish_load(self.analysis.data_in_memory,
                              self.analysis.r_read_error or "后台读取异常结束")
        except Exception:
            traceback.print_exc()

    def _release_stale_object(self):
        """释放上一轮退役的 R 对象（rm + gc），保证连读两次不累积内存"""
        try:
            n = self.analysis.release_stale_objects()
            if n:
                self.func.log(f"已释放上一轮的内存对象（{n} 个）")
        except Exception:
            traceback.print_exc()

    # ==================================================================
    # 内部小工具
    # ==================================================================
    def _dataset_combo(self):
        """取数据集下拉框（契约控件名: spatial_dataset_combo）"""
        return getattr(self.ui, 'spatial_dataset_combo', None)

    def _force_sync_load(self):
        """是否强制走同步读（兜底开关）

        默认 False（走后台 worker）。置真值的方式（任一）：
          · 环境变量 `SPATIAL_LOAD_SYNC=1`
          · 实例属性 `bind.force_sync_load = True`
        用途：真机上若发现 worker 路线异常，可不改代码直接切回已验证稳定的同步路径。
        """
        try:
            if getattr(self, 'force_sync_load', False):
                return True
            return str(os.environ.get('SPATIAL_LOAD_SYNC', '')).strip() in ('1', 'true', 'True', 'yes')
        except Exception:
            return False

    def _is_loading(self):
        """是否有读取任务正在进行（重入守卫）

        ⚠ 双重判断：标志位 + 线程是否真的在跑，避免"标志位忘了复位"或
           "线程已结束但标志还在"这两种单点故障。

        ⚠⚠ 命名纪律：标志位字段叫 **`self._loading`**，**不叫 `self._is_loading`**。
           曾经用后者，结果**实例属性把同名方法遮蔽**（Python 里 `self.x = True` 会覆盖
           类上的 `def x(self)`）→ 第一次点击之后 `self._is_loading()` 就抛
           `TypeError: 'bool' object is not callable`；而它是在 `load_data()` 的 try 块里
           抛出的、被 except 兜住，表现为"加载失败"，并**极易被误读成 R 线程问题**。
           教训：检测方法不要与状态字段同名。
        """
        try:
            if self._loading:
                return True
            worker = self.read_worker
            if worker is not None and hasattr(worker, 'isRunning') and worker.isRunning():
                return True
            return False
        except Exception:
            traceback.print_exc()
            return False

    def _set_buttons_enabled(self, enabled):
        """统一启用/禁用与加载相关的按钮（照 bulk 的 _set_buttons_enabled 形状）"""
        try:
            self.func.set_load_buttons_enabled(enabled)
        except Exception:
            traceback.print_exc()

    # ------------------------------------------------------------------
    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.ui, 'music_controller'):
            fix_music_controller_bindings(self, self.ui.music_controller)

    def set_volume(self, value):
        """设置音量"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)


__all__ = ['SpatialTopBind', 'SpatialReadWorker']
