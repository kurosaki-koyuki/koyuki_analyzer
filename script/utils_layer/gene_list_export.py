# -*- coding: utf-8 -*-
"""gene_list_export.py —— 「发送到基因列表文件夹」的共享逻辑（发送控件专用）

背景与口径（**写之前先读这段**）：
  `appdata/genelists` 是多种分析共用的"基因列表"目录。现有 4 个文件都是
  **单列 xlsx、无表头**（首格就是基因名，如 `HNRNPC` / `LFNG` / `C1orf61` / `AAK1`）。
  本模块默认按**同一口径**写出，保证与既有文件一致、与既有下拉框扫描一致。

  ⚠️ **已知的读取器不一致**（不是本模块能单方面解决的，实测证据见 probe）：
     · `bulk_gene_set_utils.load_gene_set_from_file`、`ui_bind_bulk_cox`、
       `bulk_logrank_py_analysis`、`wgcna_analysis` 都用 `pd.read_excel(path)`（**默认 header=0**）
       ⇒ 对"无表头"文件会**把第一个基因当表头吃掉**；
     · `bulk_cluster_analysis` 与 Circos 内核用 `header=None`（+跳过表头样首格）⇒ 正确。
  因此本模块提供 `write_header` 开关：
     · False（默认）= 与既有文件一致（4 个旧读者会少读 1 个 → 属既有 bug，非本模块引入）
     · True        = 让 4 个旧读者正确（cluster/circos 会看到一个名为 gene 的伪基因，需要 reader 侧跳过）
  **建议的最终修法**：本模块输出保持无表头（与既有文件一致），另把上述 4 个旧读者
  改为 `header=None`——那样所有读者与所有既有文件都同时正确。

对外接口（供各页面 bind 层调用）：
    gene_list_dir()                         -> 目录
    propose_name(prefix)                    -> 带时间戳的默认名
    sanitize_name(name)                     -> 去掉非法文件名字符
    exists(name) / list_names()             -> 目录内既有文件
    save_gene_list(genes, name, ...)        -> 真正落盘，返回结果字典（含各计数与提示语）
    ask_and_send(parent, genes, ...)        -> 弹窗取名 + 覆盖确认 + 落盘（页面只需调这一个）
    GeneListSendDialog                      -> 命名对话框（控件全部来自 gui_styles 工厂）
"""
import io
import os
import re
import time

from script.utils_layer.import_config import APPDATA_PATH

#: 基因列表目录（与 bulk_gene_set_utils / WGCNA / KM / Circos 完全同一个目录）
GENELIST_DIR = os.path.join(APPDATA_PATH, "genelists")

#: Windows 文件名非法字符
_ILLEGAL = r'[\\/:*?"<>|\r\n\t]'
_MAX_NAME = 80


def gene_list_dir():
    """返回基因列表目录（不存在则创建）。"""
    os.makedirs(GENELIST_DIR, exist_ok=True)
    return GENELIST_DIR


def sanitize_name(name):
    """去掉非法文件名字符、压缩空白、截断过长名字。空则返回 ""。"""
    s = str(name or "").strip()
    s = re.sub(_ILLEGAL, "_", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    if len(s) > _MAX_NAME:
        s = s[:_MAX_NAME].rstrip(" .")
    return s


def propose_name(prefix="基因列表"):
    """建议默认名：<前缀>_<YYYYmmdd_HHMM>（撞名时 save 会再报告冲突）。"""
    return "%s_%s" % (prefix, time.strftime("%Y%m%d_%H%M"))


def list_names(exts=(".xlsx", ".xls", ".txt", ".csv")):
    """目录内既有的列表文件名（排序，稳定顺序）。"""
    d = gene_list_dir()
    return sorted(f for f in os.listdir(d) if f.lower().endswith(exts))


def exists(name):
    """同名文件是否已存在（只按 .xlsx 判断，因为本模块只写 xlsx）。"""
    return os.path.exists(os.path.join(gene_list_dir(), sanitize_name(name) + ".xlsx"))


def _clean_genes(genes):
    """清洗：转字符串、去空白、丢空、去重保序；返回 (cleaned, n_dup, n_invalid)。"""
    seen, out, dup, invalid = set(), [], 0, 0
    for g in (genes or []):
        s = str(g).strip().strip('"').strip("'")
        if not s or s.lower() in ("nan", "none", "na"):
            invalid += 1
            continue
        if s in seen:
            dup += 1
            continue
        seen.add(s)
        out.append(s)
    return out, dup, invalid


def save_gene_list(genes, name, *, overwrite=False, base_dir=None, write_header=False,
                   sheet_name="Sheet1"):
    """把基因列表写成 `base_dir/<name>.xlsx`（**单列、默认无表头**，与既有文件同口径）。

    Returns dict:
      ok, path, n_input, n_written, n_dup, n_invalid, overwritten, message
    失败情形（ok=False）：名为空 / 基因清洗后为空 / 已存在且 overwrite=False。
    """
    import pandas as pd

    d = base_dir or gene_list_dir()
    os.makedirs(d, exist_ok=True)
    clean = sanitize_name(name)
    res = {"ok": False, "path": "", "n_input": len(list(genes or [])), "n_written": 0,
           "n_dup": 0, "n_invalid": 0, "overwritten": False, "message": ""}
    if not clean:
        res["message"] = "名称不能为空（或去掉非法字符后为空）"
        return res

    path = os.path.join(d, clean + ".xlsx")
    already = os.path.exists(path)
    if already and not overwrite:
        res["path"] = path
        res["message"] = "同名文件已存在：%s.xlsx（未覆盖）" % clean
        return res

    gs, dup, invalid = _clean_genes(genes)
    res.update(n_dup=dup, n_invalid=invalid, n_written=len(gs))
    if not gs:
        res["message"] = "没有可写入的基因（清洗后为空）"
        return res

    # ★ 单列、无表头：与 appdata/genelists 里 4 个既有文件完全同构
    df = pd.DataFrame({("gene" if write_header else 0): gs})
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet_name, index=False, header=bool(write_header))

    res["ok"] = True
    res["path"] = path
    res["overwritten"] = already
    res["message"] = ("已覆盖 %s.xlsx：写入 %d 个基因" if already else "已发送 %s.xlsx：写入 %d 个基因") \
        % (clean, len(gs))
    if dup or invalid:
        res["message"] += "（去重跳过 %d，无效值 %d）" % (dup, invalid)
    return res


# --------------------------------------------------------------------------
# 命名对话框（控件全部来自 gui_styles 工厂；页面无需自己拼控件）
# --------------------------------------------------------------------------
def _make_dialog_class():
    """延迟构造对话框类：只有真正用到 UI 时才 import Qt（便于无界面自检 import 本模块）。"""
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                                 QButtonGroup)
    from PyQt5.QtCore import Qt
    from script.utils_layer.gui_styles import (create_styled_line_edit, create_styled_button,
                                               create_styled_label, create_styled_checkbox,
                                               create_styled_combo_box)

    class GeneListSendDialog(QDialog):
        """给基因列表命名并发送到 appdata/genelists。

        两种输入形态：
          · `groups=None` —— 直接把传入的基因列表落盘（**旧口径，保持兼容**）；
          · `groups=[(标签, 基因列表[, 默认勾选]), ...]` —— 先让用户**选集合**
            （`multi=True` 用勾选框可多选；`multi=False` 用下拉框单选），
            发送的是所选集合的**并集并去重**（保序）。
        """

        def __init__(self, parent=None, default_name="", n_genes=0, dir_hint="",
                     groups=None, multi=True):
            super().__init__(parent)
            self.setWindowTitle("发送到基因列表文件夹")
            self.setModal(True)
            self.setMinimumWidth(520)
            self._groups = list(groups) if groups else []
            self._multi = bool(multi)
            self._checks = []            # [(checkbox, label, genes)]
            self._combo = None
            # ★ 只有 1 个子集时不显示选择区（契约 §3 末条）：没有可选项，
            #   多一个"只有一个选项的勾选框"只会让用户困惑。此时直接发这个子集。
            show_selector = len(self._groups) > 1
            self._single = self._groups[0] if (self._groups and not show_selector) else None
            lay = QVBoxLayout(self)

            self.lbl_tip = create_styled_label(
                "将 %d 个基因写入基因列表文件夹，后续分析可直接在下拉框中选用。" % n_genes)
            lay.addWidget(self.lbl_tip)

            if show_selector:
                if self._multi:
                    lay.addWidget(create_styled_label(
                        "选择要发送的集合（可多选；发送的是所选集合的并集并去重）："))
                else:
                    lay.addWidget(create_styled_label(
                        "选择要发送的集合（单选；发送前会去重）："))

                if self._multi:
                    grid_host = QGridLayout()
                    grid_host.setContentsMargins(0, 0, 0, 0)
                    for i, item in enumerate(self._groups):
                        label, genes = item[0], item[1]
                        default = item[2] if len(item) > 2 else True
                        cb = create_styled_checkbox("%s（%d 个）" % (label, len(genes)))
                        cb.setChecked(bool(default))
                        cb.stateChanged.connect(self._refresh_warn)
                        self._checks.append((cb, label, genes))
                        grid_host.addWidget(cb, i // 2, i % 2)   # 两列排布，避免超高
                    lay.addLayout(grid_host)
                    row_all = QHBoxLayout()
                    row_all.addStretch()
                    btn_all = create_styled_button("全选", parent=self, font_size=11)
                    btn_none = create_styled_button("清空", parent=self, font_size=11)
                    btn_all.clicked.connect(lambda: self._set_all(True))
                    btn_none.clicked.connect(lambda: self._set_all(False))
                    row_all.addWidget(btn_all)
                    row_all.addWidget(btn_none)
                    lay.addLayout(row_all)
                else:
                    self._combo = create_styled_combo_box(parent=self)
                    for item in self._groups:
                        self._combo.addItem("%s（%d 个）" % (item[0], len(item[1])))
                    self._combo.currentIndexChanged.connect(self._refresh_warn)
                    lay.addWidget(self._combo)

            row = QHBoxLayout()
            row.addWidget(create_styled_label("文件名："))
            self.edit_name = create_styled_line_edit()
            self.edit_name.setText(default_name)
            self.edit_name.selectAll()
            row.addWidget(self.edit_name, 1)
            lay.addLayout(row)

            self.lbl_ext = create_styled_label("扩展名：.xlsx（单列，与既有基因列表同格式）")
            lay.addWidget(self.lbl_ext)
            if dir_hint:
                lay.addWidget(create_styled_label("保存位置：%s" % dir_hint))
            self.lbl_count = create_styled_label("")
            lay.addWidget(self.lbl_count)
            self.lbl_warn = create_styled_label("")
            lay.addWidget(self.lbl_warn)

            btns = QHBoxLayout()
            btns.addStretch()
            self.btn_cancel = create_styled_button("取消", parent=self, font_size=12)
            self.btn_ok = create_styled_button("发送", parent=self, font_size=12, button_type='run')
            btns.addWidget(self.btn_cancel)
            btns.addWidget(self.btn_ok)
            lay.addLayout(btns)

            self.btn_cancel.clicked.connect(self.reject)
            self.btn_ok.clicked.connect(self._on_ok)
            self.edit_name.textChanged.connect(self._refresh_warn)
            self._refresh_warn()

        # ---- 选择区 ----
        def _set_all(self, on):
            for cb, _l, _g in self._checks:
                cb.setChecked(on)
            self._refresh_warn()

        def selected_labels(self):
            if not self._groups:
                return []
            if self._single is not None:          # 只有 1 个子集：它就是要发的东西
                return [self._single[0]]
            if self._multi:
                return [l for cb, l, _g in self._checks if cb.isChecked()]
            return [self._groups[self._combo.currentIndex()][0]] if self._combo else []

        def selected_genes(self):
            """所选集合的并集（**去重保序**）；无 groups 时返回 None 表示"用外部传入的列表"。"""
            if not self._groups:
                return None
            picked = []
            if self._single is not None:
                picked.extend(self._single[1])
            elif self._multi:
                for cb, _l, genes in self._checks:
                    if cb.isChecked():
                        picked.extend(genes)
            else:
                i = self._combo.currentIndex() if self._combo else 0
                picked.extend(self._groups[i][1])
            seen, out = set(), []
            for g in picked:
                s = str(g).strip()
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)
            return out

        # ---- 提示与校验 ----
        def _refresh_warn(self):
            nm = sanitize_name(self.edit_name.text())
            msgs = []
            if self._groups:
                n_sel = len(self.selected_labels())
                gs = self.selected_genes() or []
                self.lbl_count.setText("已选 %d 个集合 → 去重后 %d 个基因" % (n_sel, len(gs)))
                if n_sel == 0:
                    msgs.append("⚠ 至少要选择一个集合")
            if not nm:
                msgs.append("⚠ 文件名不能为空")
            elif exists(nm):
                msgs.append("⚠ 已存在同名文件：%s.xlsx —— 点“发送”将覆盖它" % nm)
            self.lbl_warn.setText("   ".join(msgs))

        def _on_ok(self):
            if not sanitize_name(self.edit_name.text()):
                self._refresh_warn()
                return
            if self._groups and not self.selected_labels():
                self._refresh_warn()
                return
            self.accept()

        def name(self):
            return sanitize_name(self.edit_name.text())

    return GeneListSendDialog


_DIALOG_CLASS = None


def dialog_class():
    global _DIALOG_CLASS
    if _DIALOG_CLASS is None:
        _DIALOG_CLASS = _make_dialog_class()
    return _DIALOG_CLASS


def normalize_groups(groups):
    """把页面传来的子集定义规整成 `[(标签, 基因列表, 默认勾选), ...]`。

    接受：`{"标签": [基因...]}`、`[("标签", [基因...])]`、`[("标签", [基因...], False)]`。
    空子集（无基因）会被**丢掉**（不显示空集合，避免用户勾了却什么都没发）。
    """
    out = []
    if not groups:
        return out
    items = groups.items() if isinstance(groups, dict) else groups
    for item in items:
        if isinstance(item, tuple) or isinstance(item, list):
            label = str(item[0])
            genes = list(item[1] or [])
            default = bool(item[2]) if len(item) > 2 else True
        else:
            continue
        genes = [str(g).strip() for g in genes if str(g).strip()]
        if genes:
            out.append((label, genes, default))
    return out


def ask_and_send(parent, genes=None, *, groups=None, multi=True, prefix="基因列表",
                 default_name=None, dlg_class=None):
    """完整流程：弹窗取名（+可选地**选集合**）→ 有同名先确认 → 落盘。

    两种用法（**向后兼容**）：
      1) 旧口径：`ask_and_send(self.parent_widget, gene_list, prefix="差异基因")`
      2) 选集合：`ask_and_send(self.parent_widget,
                               groups=[("上调", up), ("下调", down), ("全部显著", sig)],
                               prefix="差异基因")`
         · `multi=True` 勾选框多选；`multi=False` 下拉框单选
         · 发送内容 = **所选集合的并集并去重**（保序）

    返回：save_gene_list 的结果字典，另加 `selected_groups`（所选标签）与
    `cancelled`（用户取消时为 True）。
    """
    gs = normalize_groups(groups)
    if gs:
        all_genes = []
        for _l, _g, _d in gs:
            all_genes.extend(_g)
        n_hint = len({str(g).strip() for g in all_genes if str(g).strip()})
    else:
        all_genes = list(genes or [])
        n_hint = len(all_genes)

    if not gs and not all_genes:
        return {"ok": False, "path": "", "message": "没有可发送的基因（结果为空）",
                "cancelled": False, "selected_groups": []}

    cls = dlg_class or dialog_class()
    nm = default_name or propose_name(prefix)
    dlg = cls(parent=parent, default_name=nm, n_genes=n_hint, dir_hint=gene_list_dir(),
              groups=gs, multi=multi)
    if dlg.exec_() != 1:                     # QDialog.Accepted == 1
        return {"ok": False, "cancelled": True, "path": "", "message": "已取消",
                "selected_groups": []}

    name = dlg.name()
    picked = dlg.selected_genes()            # None = 旧口径（用外部传入的列表）
    payload = all_genes if picked is None else picked
    labels = dlg.selected_labels()

    # 覆盖需二次确认（对话框里已提示，这里再挡一道，避免误覆盖别人的列表）
    overwrite = False
    if exists(name):
        try:
            from PyQt5.QtWidgets import QMessageBox
            r = QMessageBox.question(parent, "确认覆盖",
                                     "基因列表文件夹里已有 %s.xlsx，确定覆盖吗？" % name,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            overwrite = (r == QMessageBox.Yes)
            if not overwrite:
                return {"ok": False, "cancelled": True, "path": "",
                        "message": "目标已存在，用户选择不覆盖", "selected_groups": labels}
        except Exception:
            overwrite = True                 # 无 UI 环境（自检）时直接覆盖
    res = save_gene_list(payload, name, overwrite=overwrite)
    res["selected_groups"] = labels
    res["cancelled"] = False
    return res
