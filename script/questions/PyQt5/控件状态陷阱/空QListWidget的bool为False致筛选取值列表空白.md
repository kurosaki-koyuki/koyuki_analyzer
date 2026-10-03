# 空 QListWidget 的 bool() 为 False，导致筛选取值列表永远空白

## 现象

bulk 差异分析（R 版与 py 版**都出现**）：
- 「分组选择」下拉有值、选列后「组别1/组别2」列表正常填充；
- 两个「样本筛选」的下拉框也有正常列名；
- 但**筛选取值列表**（下拉框下方的可勾选列表）无论选哪一列都是空白。

## 涉及代码（修复后）

- `script/analyzer_layer/bulk_layer/bulk_diff_layer/py_diff/ui_bind_bulk_diff_py.py`
- `script/analyzer_layer/bulk_layer/bulk_diff_layer/r_diff/ui_bind_bulk_diff_r.py`

两处 `_update_filter_list()` 中的守卫：

```python
# 修复前（错）
if not col_widget or not list_widget:
    return
# 修复后（对）
if col_widget is None or list_widget is None:
    return
```

## 定位过程（复盘，这次耗时主要在“归因”）

1. 代码审计：R/py 布局控件命名一致、绑定一致、填充逻辑一致，静态看不出问题；
2. 用“假控件 + 桩模块”的无头测试**全通过**——未复现；
3. 换成**真实 PyQt5 控件**（离屏 `QT_QPA_PLATFORM=offscreen`）→ 复现：选列后列表仍为空；
4. 插桩信号与处理函数：`on_filter1_col_changed` 确实被调用、`col='source'` 正确、
   adata 存在，但 `_fill_checkable_list` 没被调用——**在守卫处静默 return**；
5. 打印 `bool(list_widget)`：对一个**空的、未填充**的 QListWidget 竟是 `False`；
   对照实验：空 QComboBox/QListWidget → `bool()==False`，塞入一个 item 后 → `True`。

## 根因

**PyQt5 对 QComboBox / QListWidget 这类控件的 `bool()` 判断不等于“对象是否存在”**——
空控件（无条目）在 `bool()` 下为 `False`，与可见性/启用状态无关。

筛选取值列表在“第一次填充之前”恰好是空的 → `if not list_widget:` 把它当成控件缺失，
静默 `return`，于是永远轮不到填充代码。**组别列表正常**是因为它走 `_fill_checkable_list()`
直填路径，没有经过这个真值守卫。

## 最小修复

把守卫从“真值判断”改成“是否缺失判断”：

```python
if col_widget is None or list_widget is None:
    return
```

R 与 py 两处同改。只动这一行，行为无其它变化。

## 验证

- 真实 PyQt5 控件 + 真实信号（离屏）复测：
  - 筛选1 切到 `source` → 列表出现 `MGG4/MGG6/MGG8`；
  - 筛选2 切到 `type` → 出现 `DGC/GSC`；
  - 切回「不筛选」→ 列表清空并禁用。
- 两个文件 `py_compile` 通过。

## 经验教训

- **对 Qt 控件不要用 `if not widget:` 判存在**，应写 `if widget is None:`（或先 `hasattr`）；
  空下拉/空列表的真值是 False，极易造成“看起来控件丢了”的假早退。
- “代码看对了但现象还在”时，先用**真实控件 + 真实信号**做最小复现，再逐行插桩定位，
  比继续读代码更快收敛。
- 同类写法排查过 `script` 下其它 `not label_widget`：那是 QLabel（真值恒 True，只拦 None），不受影响。
