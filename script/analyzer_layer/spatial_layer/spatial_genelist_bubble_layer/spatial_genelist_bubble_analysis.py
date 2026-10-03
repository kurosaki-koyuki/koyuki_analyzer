# -*- coding: utf-8 -*-
"""
空转「基因集气泡图」分析层（纯逻辑，无 UI）—— 单细胞
`sc_genelist_bubble_layer/sc_genelist_bubble_analysis.py`（301 行）的**近似 1:1 复刻**，
只换两件事：**数据从哪来**（继承空转差异分析页的 R dump + mtx 装配）与
**有哪些分组/注释值可选**（按所选样本取并集，契约 `_d_spec_spatial_diff.md` §4.2）。

契约：`_d_spec_v11_split_and_bubble.md` §2.5 / §2.6 / §2.7 / §2.8。

## 一句话设计
    `SpatialGenelistBubbleAnalysis(SpatialDiffAnalysis)`：
      · **白拿（一行都不重写）**：`set_context` / `available_group_columns` /
        `group_unique_values` / `participating_samples` / `prepare` / `load_expression` /
        `run_dump` / `clear_cache` / `keep_dump_files` / `timeout`。
        ⇒ 「按所选样本动态给出注释选项」的语义与差异分析页**逐位相同**
          （用户硬要求；也是 I6「判据真相源唯一」的物理保证——本文件**没有**第二套判据）。
      · **新增**：`load_gene_set` / `draw_gene_set_bubble_plot` / `export_png` /
        `export_csv` / `export_other`。取数仍走基类的 `self.adata`（不自己读盘）。

## ⛔ 相对单细胞**有意不照抄**的地方（规格 §2.8，逐条）
1. **不写任何模板机制**（`save_template` / `load_template` / `get_template_names` /
   `gene_bubble_param_templates`）——单细胞那套是死代码：它守卫的
   `genelist_bubble_temp_combo` 控件在 layout 里根本不存在，`save_template()` 一调必
   `AttributeError`（`ui_bind_sc_genelist_bubble.py:119-120`）。
   ★ v11.2：本页**连「加载基因」按钮也没有**（用户拍板删除）—— 基因由绘图自己解析。
2. **`export_other` 不照抄 y 轴取法**：单细胞基因集页用 `df_plot.columns[0]` 取 x 轴、
   y 轴写死 `"Gene"`，且把标题/色条标签/图例标题**硬编中文**、忽略用户的
   `fig_width`/`fig_height` 与字号。本页：x 轴 / y 轴**显式变量**，全部绘图参数
   **复用用户当前值**（见 `export_other` 的 docstring）。
3. `export_png` 用 `shutil.copyfile` 而**不是** `QPixmap(path).save(...)`
   ——理由见 `export_png` 的 docstring（分析层不引入 Qt 依赖，且拷贝是逐字节无损）。
4. **不写 `self.current_fig = fig`**：单细胞在 `plt.close()` 之后留了一个**死引用**
   （图已关闭，属性仍指着它）。本页只留 `self.current_fig_path`（规格 §2.8 缺陷 6）。
5. `collapsed` 是单细胞的**死参数**（传进来什么都不做）⇒ 本页签名**不含**它（规格 §2.8）。
6. 术语 `cell` → `spot`（`cell_id` → `spot_id`、`total_cells` → 语义为「该组的 spot 数」，
   但**列名照抄单细胞** `total_cells`/`expr_cells` —— 列顺序与列名是隐式契约，
   W2 的导出与探针按这些名字取列，改名会静默错位）。

## ★ 表达口径（v11 协调者裁决，已落地；原先的 §2.6 表述有误已作废）
    `spatial_diff_analysis.py` 的 `load_expression` 装配出来的 `self.adata.X`
    是 **原始 counts**（CSR float32）—— `spatial_diff_dump.R:280-290` **只取 counts 层**
    （R 侧带「非负 + 整数」完整性检查，取不到 counts 就**硬失败**，绝不回退 `data` 层）；
    流水线里唯一的标准化发生在差异统计内部（`diff_analysis.py:162-182` 自己算 CP10K + log1p）。
    ⇒ 气泡图的颜色用的是 **组内 mean CP10K**（`counts / spot_libsize * 10000.0`）：
      ① 原始 counts 的组内均值会让「测序深度大的 spot 对**所有**基因都显得高表达」
         ⇒ 色标退化成**文库大小伪影**；
      ② 差异页报的均值列名就叫 `mean_CP10K` ⇒ 两个页面**必须**同口径。
    ⇒ 色条标签默认 = `"Mean Expression (CP10K)"`（自解释；`P_bubble_cbar_label` 用户可改）。
    ★ `percent_expressed` 不受影响：CP10K 是线性缩放，**零仍是零**。
    ★ 分母的共享实现 = `spatial_diff_analysis.spot_libsize()`（`max(libsize, 1)` 防除零，
      与 `diff_analysis.py:166-167` 逐位同源）。

## 落盘（自动，唯一允许的写盘）
    `<self.dataset_output_dir>/gene_set_bubble/gene_set_bubble_temp.png`
    （`dataset_output_dir` 为空 ⇒ 退回 `~/koyuki_gene_set_bubble`），固定名覆盖，
    `dpi=100`、`bbox_inches='tight'`；目录不存在则 `os.makedirs(..., exist_ok=True)`。

## 异常纪律（沿 v10 §0 的 I5）
    每个 `except` 都 `traceback.print_exc()` + 留痕（`print` 带统一前缀
    `[spatial_genelist_bubble]`），**绝不静默**；对外失败一律
    `raise ValueError("<可读原因>")`。
"""

from script.utils_layer.import_config import *          # os / traceback / np / pd / plt …

from script.analyzer_layer.spatial_layer.spatial_diff_layer.spatial_diff_analysis import (
    SpatialDiffAnalysis, spot_libsize, ON_DEMAND_SUBDIR)

# 留痕前缀（与本层其它页一致；便于在整合日志里 grep）
_LOG_PREFIX = "[spatial_genelist_bubble]"

# 自动落盘子目录 / 固定文件名（规格 §2.5 冻结）
BUBBLE_SUBDIR = "gene_set_bubble"
BUBBLE_PNG_NAME = "gene_set_bubble_temp.png"

# 没有 `dataset_output_dir` 时的兜底目录（照抄单细胞 `:190`）
FALLBACK_DIRNAME = "koyuki_gene_set_bubble"

# ⚠ 绘制参数中**不允许**被覆盖的内部量（规格 §2.6 冻结；不开放给 UI）
GENE_AXIS_NAME = "Gene"

# 气泡大小图例的刻度（规格 §2.6 冻结，写死；照抄单细胞 `:169`）
SIZE_TICKS = (0.2, 0.4, 0.6, 0.8, 1.0)
LEGEND_TITLE = "Expression Ratio"

# 字体回退链（照抄单细胞 `:128`）
_FONT_SANS = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]


def _warn(msg):
    """留痕（本层纪律：不许静默）。统一前缀，方便在整合日志里 grep。"""
    print("%s %s" % (_LOG_PREFIX, msg))
    try:
        sys.stdout.flush()
    except Exception as e:                      # pragma: no cover - 极端环境
        print("%s flush failed: %r" % (_LOG_PREFIX, e))


class SpatialGenelistBubbleAnalysis(SpatialDiffAnalysis):
    """空转基因集气泡图：取数/注释选项**全部继承**，只加绘图与导出。"""

    def __init__(self):
        super().__init__()
        # ---- 本页自有的状态（名字与单细胞逐字对齐，便于对照阅读）----
        self.gene_set_total_df = None       # 逐 spot 表：obs 全列 + spot_id + 每个入选基因一列
        self.gene_set_list = []             # 入选基因（保序、与输入顺序一致）
        self.loaded_gene_text = None         # ★ v11.1：上次加载所依据的文本框原文（绘图前比对）
        self.gene_set_final_df = None       # 绘图用聚合表（列顺序 = 冻结契约）
        self.current_fig_path = None        # 最近一次落盘的 png（**不留 current_fig 死引用**）
        # 最近一次绘图的**用户参数快照**：`export_other` 只收 `(path, fmt)`，
        #   要「复用用户当前参数」就只能在这里留一份（详见 `export_other`）。
        self._last_gene_set_params = {}

    # -------------------------------------------------------------------------
    # 基因加载（照抄单细胞 `sc_genelist_bubble_analysis.py:31-64`）
    # -------------------------------------------------------------------------
    def load_gene_set(self, gene_text):
        """加载基因集：手输文本框 → 逐行切分 → 与 `var_names` 全等匹配。

        Args:
            gene_text: 多行文本，**每行一个基因**。
        Returns:
            `(valid_genes, lost_genes, valid_groups, spot_count)`
            · `valid_genes`：匹配上的基因（**保序**，重复输入会保留重复项 —— 与单细胞同款）；
            · `lost_genes`：匹配不上的（原样回给 UI 提示，**不静默丢弃**）；
            · `valid_groups`：可选分组列 = 基类 `available_group_columns()`
              （= 白名单 ∩ 所选样本的非空值并集；`group_graphed` 仅在 ≥1 个所选样本
               真的画过图时才出现 —— 这是继承来的语义，本文件**不重写**）；
            · `spot_count`：`self.adata.n_obs`（参与装配的全部 spot 数）。
        Raises:
            `ValueError("<可读原因>")`（空文本框 / 无 adata / 一个基因都没匹配上）。
        """
        if not gene_text:
            raise ValueError("请输入基因列表")

        # ★★ v11.1 修复（用户真机反馈：「加载基因」永远提示"请先加载数据集"，怎么也加载不上）：
        #   原实现要求 `self.adata` **已经**存在，而 `adata` 只在**绘图**路径里经
        #   `_ensure_gene_set_adata()` → `prepare()` 装配；偏偏绘图又要求
        #   `self.gene_set_total_df` 非空（= 必须先"加载基因"）⇒ **死锁**：
        #     加载基因 需要 adata ← 只有绘图会装配
        #     绘图     需要已加载基因 ← 只有加载基因会置
        #   两个入口谁都走不通，用户的报错正是这条。
        #   ⇒ 本方法**自己保证装配**：`prepare()` 昂贵但**自带幂等**
        #     （同一 `(dataset, samples)` 只跑一次 R dump，第二次直接命中缓存）。
        self._ensure_gene_set_adata()

        input_genes = [g.strip() for g in str(gene_text).splitlines() if g.strip()]
        if not input_genes:
            raise ValueError("请输入基因列表（每行一个）")

        # ★ 匹配口径 = `var_names`（空转装配出来的 var.index 就是**基因名**）；
        #   若某个数据集额外带了 `gene_symbol` 列，则与单细胞一致地优先用它。
        if "gene_symbol" in self.adata.var.columns:
            var_sym = self.adata.var.gene_symbol.values
        else:
            var_sym = self.adata.var_names.values
        valid_genes = [g for g in input_genes if g in var_sym]
        lost_genes = [g for g in input_genes if g not in var_sym]

        if not valid_genes:
            raise ValueError("无有效基因，请核对基因名")

        # ---- 逐 spot 表：obs（含 sample/group_graphed/group 等） + spot_id + 逐基因表达 ----
        self.gene_set_total_df = self.adata.obs.copy()
        self.gene_set_total_df["spot_id"] = self.adata.obs_names

        gene2idx = {g: i for i, g in enumerate(var_sym)}
        # ★★ CP10K 归一（v11 协调者裁决，见 `spot_libsize` 的口径说明）：
        #   空转 dump 出来的是 **counts 层** ⇒ `self.adata.X` 是**原始 counts**。
        #   直接算组内均值会让「测序深度大的 spot 对所有基因都显得高表达」，
        #   色标退化成文库大小的伪影；而差异页报的均值叫 `mean_CP10K`
        #   ⇒ 气泡图的颜色**必须**同样是 CP10K，两个页面口径才一致。
        #   分母只算一次（逐 spot 总 counts），`max(libsize, 1)` 防除零。
        #   ★ `percent_expressed` 不受影响：CP10K 是线性缩放，零**仍是**零。
        _libsize = spot_libsize(self.adata.X)
        for g in valid_genes:
            idx = gene2idx[g]
            expr_mat = self.adata.X[:, idx]
            if hasattr(expr_mat, "toarray"):
                expr_mat = expr_mat.toarray().ravel()
            self.gene_set_total_df[g] = np.asarray(expr_mat, dtype=float) / _libsize * 10000.0

        self.gene_set_list = valid_genes
        # ★ v11.1：记住"这次加载的是哪段文本" ⇒ 绘图前可比对，**文本框改了才重新解析**
        #   （用户要求："直接在跑图时跑相应的基因" ⇒ 绘图以**当前文本框**为准）
        self.loaded_gene_text = str(gene_text)

        # ★ 可分组列**不走 obs.columns**（那会把 `spot_id` 这类内部列也放出去）：
        #   一律走基类的并集判据（规格 §2.4：与差异页逐位同源）。
        valid_groups = self.available_group_columns()

        spot_count = int(self.adata.n_obs)
        _warn("load_gene_set: 输入=%d | 有效=%d | 未匹配=%d | 可选分组=%s | spots=%d"
              % (len(input_genes), len(valid_genes), len(lost_genes),
                 valid_groups or "（无）", spot_count))
        if lost_genes:
            _warn("load_gene_set: 以下基因未匹配上，已按原样回给 UI（不静默）：%s"
                  % ", ".join(lost_genes))
        return valid_genes, lost_genes, valid_groups, spot_count

    # ★ 注意：`get_group_unique_vals(col)` **有意不覆写**。
    #   基类 `SpatialDiffAnalysis.get_group_unique_vals()` 已经是
    #   「委托 `group_unique_values(col)`（= 所选样本的取值并集）」——
    #   规格 §2.5 明文冻结「此处不再覆写」。覆写回单细胞的
    #   `self.adata.obs[col].unique()` 会把「按所选样本取并集」的语义打回原形。

    # -------------------------------------------------------------------------
    # 内部：装配绘图表（统计口径见模块 docstring 与规格 §2.6）
    # -------------------------------------------------------------------------
    def _ensure_gene_set_adata(self):
        """绘图前确保 `self.adata` 已装配（`prepare()` 很贵，但**自带幂等**）

        Raises:
            `ValueError`：无 adata 且装配失败（文案带上 `self.last_prepare_error`）。
        """
        if self.adata is not None:
            return
        ok = self.prepare()                 # 同一 (dataset, samples) 命中幂等 ⇒ 不重跑 R dump
        if not ok or self.adata is None:
            raise ValueError("数据集未装配成功，无法绘图：%s"
                             % (getattr(self, "last_prepare_error", "") or "未知原因"))

    def _selected_spot_ids(self, x_col):
        """按**参与样本**取 spot_id 集合（`participating_samples(x_col)`）

        · `x_col` 为空 ⇒ 返回 `None`，表示「不做样本层过滤」；
        · `group_graphed` ⇒ 基类只回「真的画过图」的样本
          （用户原话：「如果对比的是 graph 分组，只分析带 graph 注释的那个样本」）；
        · 参与/被排除的样本都**留痕**（I5；基类 `participating_samples` 自己也会 print）。
        """
        if not x_col:
            return None
        try:
            used = list(self.participating_samples(x_col) or [])
        except Exception as e:
            traceback.print_exc()
            _warn("participating_samples(%s) 异常（%s）⇒ 本次不做样本层过滤（如实留痕）"
                  % (x_col, e))
            return None
        used_set = set(used)
        excluded = [sid for sid in (self.samples or []) if sid not in used_set]
        _warn("绘制 %s：参与样本=%s | 被排除样本=%s"
              % (x_col, used or "（无）", excluded or "（无）"))
        return used_set

    def _build_gene_set_final_df(self, x_col, x_sel,
                                 f1_col=None, f1_sel=None, f2_col=None, f2_sel=None):
        """按冻结口径筛选 + 逐基因聚合，写入 `self.gene_set_final_df`，返回筛选后的 df

        ## 筛选口径（与单细胞 `:91-107` 逐条一致，**不退化成"全部"**）
        每个 (列, 值列表) 对：列非空 ⇒ 一律 `isin(值列表)`；
        「选了列但一个值都没选」⇒ `isin([])` ⇒ 空 df ⇒ 后续 `raise ValueError`。
        ## 样本口径（空转独有）
        用 `participating_samples(x_col)` 只保留参与样本的行
        （`group_graphed` 时自动只剩带 graph 注释的样本 —— **不在这里再判一次**）。
        """
        df = self.gene_set_total_df.copy()

        # ---- ① 参与样本（空转独有；只在 x_col 非空且能解析出参与集合时生效）----
        sel_spots = self._selected_spot_ids(x_col)
        if sel_spots is not None:
            df = df[df["sample"].isin(list(sel_spots))]

        # ---- ② X / 筛选1 / 筛选2（逐条照抄单细胞）----
        if x_col and x_sel:
            df = df[df[x_col].isin(x_sel)]
        elif x_col and not x_sel:
            df = df.iloc[0:0]

        if f1_col and f1_sel:
            df = df[df[f1_col].isin(f1_sel)]
        elif f1_col and not f1_sel:
            df = df.iloc[0:0]

        if f2_col and f2_sel:
            df = df[df[f2_col].isin(f2_sel)]
        elif f2_col and not f2_sel:
            df = df.iloc[0:0]

        if df.empty:
            raise ValueError("筛选后无 spot 数据")

        # ---- ③ 逐基因聚合（每基因一行）----
        valid_genes = [g for g in self.gene_set_list if g in df.columns]
        agg_list = []
        for gene in valid_genes:
            group_agg = df.groupby(x_col).agg(
                mean_expr=(gene, "mean"),
                total_cells=("spot_id", "count"),
                expr_cells=(gene, lambda x: (x > 0).sum())
            ).reset_index()
            group_agg["Gene"] = gene
            group_agg["percent_expressed"] = group_agg["expr_cells"] / group_agg["total_cells"]
            agg_list.append(group_agg)

        if not agg_list:
            raise ValueError("无绘图数据")

        # ★ 列顺序是**隐式契约**（W2 导出 / 探针按名字取列）：照单细胞
        #   `[x_col, mean_expr, total_cells, expr_cells, Gene, percent_expressed]`
        self.gene_set_final_df = pd.concat(agg_list, ignore_index=True)
        _warn("_build_gene_set_final_df: 筛选后 spot=%d | 基因=%d | 聚合行=%d"
              % (len(df), len(valid_genes), len(self.gene_set_final_df)))
        return df

    # -------------------------------------------------------------------------
    # 内部：把聚合表画成图（主图与 export_other **共用同一段口径**）
    # -------------------------------------------------------------------------
    @staticmethod
    def _draw_gene_set_scatter(df_plot, p):
        """把 `gene_set_final_df` 画成气泡图并落盘，返回 `(fig, path)`

        Args:
            df_plot: 聚合表（列含 `x_col` / `mean_expr` / `percent_expressed` / `Gene`）
            p: 参数字典（键见 `draw_gene_set_bubble_plot`；**x 轴与 y 轴是显式列名**）

        ★ 与主图的唯一差别：`p['dpi']` 与 `p['save_path']`。
          这样 `export_other` 复用用户参数就**不可能**与主图漂移（规格 §2.8 缺陷 2 的根治）。
        """
        x_col = p["x_col"]
        y_axis = p["y_axis"]                       # 基因集页恒为 `"Gene"`（显式量，不靠列序号）
        figsize = (p["fig_width"], p["fig_height"])

        plt.rcParams["font.sans-serif"] = list(_FONT_SANS)
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=figsize, dpi=120)

        scatter = ax.scatter(
            data=df_plot,
            x=x_col,
            y=y_axis,
            c="mean_expr",
            s=df_plot["percent_expressed"] * p["scale_factor"],
            cmap="Reds",
            alpha=0.8,
            edgecolors="none"
        )

        unique_genes = df_plot[y_axis].unique()
        n_genes = len(unique_genes)
        ax.set_ylim(-0.5, n_genes - 0.5)

        unique_x = df_plot[x_col].unique()
        n_x = len(unique_x)
        ax.set_xlim(-0.5, n_x - 0.5)

        plt.xticks(rotation=45, ha="right", fontsize=10)
        plt.yticks(fontsize=10)
        ax.set_title(p["main_title"], fontsize=p["title_fontsize"], pad=20)
        ax.set_xlabel(x_col, fontsize=p["x_label_fontsize"])
        ax.set_ylabel("基因", fontsize=p["y_label_fontsize"])

        ax.xaxis.set_label_coords(0.5, -0.22)
        ax.yaxis.set_label_coords(-0.18, 0.5)

        plt.subplots_adjust(right=p["main_right_ratio"], left=0.18, bottom=0.25, top=0.90)

        cbar = plt.colorbar(scatter, ax=ax, fraction=p["cbar_width"], pad=0.08, location="right")
        cbar.ax.set_position([p["cbar_left"], p["cbar_bottom"],
                              p["cbar_width"], p["cbar_height"]])
        cbar.set_label("")
        cbar.ax.set_ylabel(p["cbar_label_text"], rotation=270, labelpad=15,
                           fontsize=p["cbar_label_fontsize"])

        handles = [plt.scatter([], [], s=v * p["scale_factor"], color="black", alpha=0.8)
                   for v in SIZE_TICKS]
        ax.legend(
            handles, [str(v) for v in SIZE_TICKS],
            title=LEGEND_TITLE,
            loc="center left",
            bbox_to_anchor=(p["legend_anchor_x"], p["legend_anchor_y"]),
            frameon=False,
            labelspacing=p["label_spacing"],
            handletextpad=0.8,
            title_fontsize=p["legend_title_fontsize"],
            fontsize=p["legend_title_fontsize"],
            scatterpoints=1,
            markerscale=p["legend_scale"]
        )

        save_path = p["save_path"]
        out_dir = save_path if os.path.isdir(save_path) else os.path.dirname(save_path)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            traceback.print_exc()
            plt.close(fig)
            raise ValueError("无法创建出图目录（%s）：%s" % (out_dir, e))

        fig.savefig(save_path, dpi=p["dpi"], bbox_inches="tight")
        plt.close(fig)                             # ★ 收尾关图；**不留 current_fig 死引用**
        _warn("气泡图落盘：%s（dpi=%s）" % (save_path, p["dpi"]))
        return save_path

    def _bubble_output_dir(self):
        """出图目录：`<out_dir>/08_GeneOnDemand/gene_set_bubble`

        无 `out_dir` ⇒ 退回 `~/koyuki_gene_set_bubble`。

        ★★ v11.2 修复（门禁 `14k` 抓到，属真缺陷）：
          本类继承 `SpatialDiffAnalysis`，而基类 `set_context()` 会把
          `self.dataset_output_dir` 设成**差异页自己的** `…/08_GeneOnDemand/_diff`
          ⇒ 原实现（`<dataset_output_dir>/gene_set_bubble`）会把气泡图**塞进差异页的
          dump 目录里**，后果两条：
            ① 语义错 —— `_diff/` 是差异分析"R dump 中间产物"的地盘（那个目录的契约是
               **装完 AnnData 就清空**），气泡图不该住在里面；
            ② 真坏了别人的断言 —— `_d_verify_spatial_diff_real.py` 会断言
               「`_diff/` 中间产物已按契约自动清理」，气泡图留在那儿就把它判红。
          ⇒ 改为**不依赖** `dataset_output_dir`，直接用 `self.out_dir`（= `OUTPUT/<dataset>`）
            拼出**本页自己**的按需子目录，与差异页平级、互不干扰。
        """
        if self.out_dir:
            return os.path.join(str(self.out_dir), ON_DEMAND_SUBDIR, BUBBLE_SUBDIR)
        if self.dataset_output_dir:      # 兜底：上下文不完整时仍能落盘（不报错）
            return os.path.join(str(self.dataset_output_dir), BUBBLE_SUBDIR)
        return os.path.join(os.path.expanduser("~"), FALLBACK_DIRNAME)

    # -------------------------------------------------------------------------
    # 绘图（签名逐字冻结，规格 §2.5）
    # -------------------------------------------------------------------------
    def draw_gene_set_bubble_plot(self, x_col, x_sel, f1_col=None, f1_sel=None, f2_col=None, f2_sel=None,
                                  main_title="Gene Set Expression Bubble Plot", scale_factor=750, legend_scale=1.0,
                                  main_right_ratio=0.65, title_fontsize=14, x_label_fontsize=12,
                                  y_label_fontsize=12, cbar_left=0.62, cbar_bottom=0.62, cbar_width=0.03,
                                  cbar_height=0.35, legend_anchor_x=1.0, legend_anchor_y=0.2,
                                  label_spacing=2.5, legend_title_fontsize=10, cbar_label_fontsize=10,
                                  cbar_label_text="Mean Expression (CP10K)",
                                  fig_width=9, fig_height=7):
        """绘制基因集气泡图并**自动落盘**固定名 png。

        Args:
            x_col / x_sel: X 轴分组注释列 / 选中值（多选）。
            f1_col / f1_sel / f2_col / f2_sel: 筛选 1 / 筛选 2（None = 未启用）。
            main_title / cbar_label_text: 用户可改的标题与色条标签（**不硬编中文**）。
            scale_factor: 气泡大小系数（`s = percent_expressed × scale_factor`）。
            legend_scale: 图例标记缩放（**单细胞的 legend_scale 是死参数**，本页真的用上）。
            fig_width / fig_height: 主图英寸尺寸（`export_other` 也复用它）。
        Returns:
            `(spot_count, fig_path)`
            · `spot_count` = **筛选后**参与绘图的 spot 数（与单细胞 `len(df)` 同义）；
            · `fig_path` = 刚落盘的 png 绝对路径（同时记入 `self.current_fig_path`）。
        Raises:
            `ValueError`：无 adata / 未加载基因 / 筛选后无 spot 数据 / 无绘图数据。
        """
        self._ensure_gene_set_adata()               # ★ 需要时先 prepare()（昂贵但幂等）

        if self.gene_set_total_df is None:
            raise ValueError("请先加载基因数据")

        df = self._build_gene_set_final_df(x_col, x_sel, f1_col, f1_sel, f2_col, f2_sel)

        params = {
            "x_col": x_col,
            "y_axis": GENE_AXIS_NAME,               # ★ 显式量：基因集页 y 轴恒为基因名
            "main_title": main_title,
            "scale_factor": scale_factor,
            "legend_scale": legend_scale,
            "main_right_ratio": main_right_ratio,
            "title_fontsize": title_fontsize,
            "x_label_fontsize": x_label_fontsize,
            "y_label_fontsize": y_label_fontsize,
            "cbar_left": cbar_left,
            "cbar_bottom": cbar_bottom,
            "cbar_width": cbar_width,
            "cbar_height": cbar_height,
            "legend_anchor_x": legend_anchor_x,
            "legend_anchor_y": legend_anchor_y,
            "label_spacing": label_spacing,
            "legend_title_fontsize": legend_title_fontsize,
            "cbar_label_fontsize": cbar_label_fontsize,
            "cbar_label_text": cbar_label_text,
            "fig_width": fig_width,
            "fig_height": fig_height,
        }
        # 参数快照：`export_other` 只有 `(path, fmt)` 两个入参，靠它复用用户当前参数
        self._last_gene_set_params = dict(params)

        params["dpi"] = 100                         # 主图固定 dpi=100（规格 §2.5）
        params["save_path"] = os.path.join(self._bubble_output_dir(), BUBBLE_PNG_NAME)
        self._draw_gene_set_scatter(self.gene_set_final_df, params)

        self.current_fig_path = params["save_path"]
        return int(len(df)), self.current_fig_path

    # -------------------------------------------------------------------------
    # 导出（规格 §2.7）
    # -------------------------------------------------------------------------
    def export_png(self, save_path):
        """导出 PNG：**直接拷贝**刚落盘的那张 png（规格 §2.7）

        ★ 为什么用 `shutil.copyfile` 而**不是**单细胞的 `QPixmap(path).save(...)`：
          ① 拷贝是**逐字节无损**的，`QPixmap` 会经过解码/再编码，可能丢元数据或轻微失真；
          ② 本层是纯业务层（无 Qt 依赖），`QPixmap` 需要 QApplication 存在才稳
             —— 在无 GUI 的探针/自检里它是**静默返回 null pixmap** 的（写不出文件还不报错，
             正是仓库反复出事的"静默失败"形态）；
          ③ 单细胞这么写只是因为它的导出路径恰好在 Qt 环境里，不是有意的语义。
        """
        if self.current_fig_path is None:
            raise ValueError("请先绘图")

        if not str(save_path).endswith('.png'):
            save_path = str(save_path) + '.png'

        src = str(self.current_fig_path)
        if not os.path.isfile(src):
            raise ValueError("中间图已丢失，请重新绘图：%s" % src)
        try:
            shutil.copyfile(src, str(save_path))
        except OSError as e:
            traceback.print_exc()
            raise ValueError("拷贝 PNG 失败（%s → %s）：%s" % (src, save_path, e))
        _warn("export_png: %s → %s" % (src, save_path))

    def export_csv(self, save_path):
        """导出绘图数据为 CSV（`utf-8-sig`，Excel 直接可读）"""
        if self.gene_set_final_df is None:
            raise ValueError("请先绘图")

        if not str(save_path).endswith('.csv'):
            save_path = str(save_path) + '.csv'

        self.gene_set_final_df.to_csv(save_path, index=False, encoding='utf-8-sig')
        _warn("export_csv: %s（%d 行）" % (save_path, len(self.gene_set_final_df)))

    def export_other(self, save_path, fmt):
        """导出其它矢量格式（PDF/SVG/EPS）：**重画**，并**复用用户当前参数**

        ## 与单细胞的关键差别（规格 §2.8 缺陷 2 的根治）
        单细胞基因集页的 `export_other` 把 x 轴写成 `df_plot.columns[0]`、标题/色条标签/
        图例标题**硬编中文**、尺寸写死 `(10, 8)`、`scale_factor` 写死 750
        ⇒ 导出的 PDF 与屏幕上那张图**不是同一张**。
        本页：
          · x 轴 = 显式保存的 `x_col`；y 轴 = 显式的 `"Gene"`
            （**绝不**用 `df_plot.columns[i]` —— 自定义页的 `columns[1]` 是
             `mean_expr` 这个**数值**列，靠列序号取 y 会画成「分组 vs 平均表达」）；
          · 标题 / 色条标签 / 全部字号 / 图例位置 / `fig_width` / `fig_height` /
            `scale_factor` 一律取 `self._last_gene_set_params`（= 用户当前控件值）；
          · 只把 dpi 提到 300（矢量格式的 dpi 只影响内嵌位图与预览，不影响矢量精度）。
        若尚未绘图 ⇒ `ValueError("请先绘图")`（无参数可复用，不许瞎画一张）。
        """
        if self.gene_set_final_df is None:
            raise ValueError("请先绘图")

        fmt = str(fmt or "").lstrip(".").lower()
        if not fmt:
            raise ValueError("未指定导出格式")

        if not str(save_path).endswith('.%s' % fmt):
            save_path = str(save_path) + '.%s' % fmt

        params = dict(self._last_gene_set_params or {})
        if not params:
            raise ValueError("请先绘图")
        params["dpi"] = 300
        params["save_path"] = str(save_path)
        self._draw_gene_set_scatter(self.gene_set_final_df, params)
        _warn("export_other: %s（fmt=%s，参数复用用户当前值）" % (save_path, fmt))


__all__ = ['SpatialGenelistBubbleAnalysis']
