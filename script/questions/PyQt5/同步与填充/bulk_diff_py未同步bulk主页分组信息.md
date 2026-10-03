# bulk差异分析 py版不填充分组下拉（未同步bulk主页数据）

## 现象

bulk 主页（`bulk_top_page`）加载 h5ad 数据集后，进入「bulk 差异分析 → Python版本」，
「分组选择」下拉框与两个「样本筛选」下拉框均为空；切到 R 版本却正常。

## 涉及代码（修复后）

- `script/analyzer_layer/bulk_layer/bulk_diff_layer/py_diff/ui_bind_bulk_diff_py.py`
- 参照实现：`script/analyzer_layer/bulk_layer/bulk_diff_layer/r_diff/ui_bind_bulk_diff_r.py`

## 定位过程

对比 R / py 两个绑定的 `sync_data_from_bulk_main()`：

- R 版：同步 adata 后调用 `_populate_group_columns()`，按 obs 列填充下拉框；
- py 版：只执行了 `self.adata = ...` 并打一行日志，**没有任何填充逻辑**（页面是骨架，
  `bulk_diff_py_analysis.py` 与 `ui_func_bulk_diff_py.py` 均为空类）。

## 根因

py 版绑定的“从 bulk 主页同步”函数只存数据、不刷新 UI，属**功能未接线**，不是 Qt 行为问题。

## 最小修复

在 `BulkDiffPyBind` 中补齐（照 R 版逻辑，控件命名两版页面一致）：

- `sync_data_from_bulk_main()` 末尾调用 `_populate_group_columns()`
- `_populate_group_columns()`：分组下拉只放取值数 2~50 的 obs 列；筛选下拉放「不筛选」+ 全部 obs 列
- 绑定 `diff_group_combo / diff_filter1_col / diff_filter2_col` 的 `currentIndexChanged`
- `on_group_col_changed()`：联动刷新「组别1/组别2」可勾选列表
- `on_filter1/2_col_changed()` + `_update_filter_list()`：联动刷新筛选取值列表（选「不筛选」则清空禁用）
- `_fill_checkable_list()`：向 QListWidget 填充可勾选项

未改动 py 版算法层与执行/导出（当时确认修复范围只到“同步+下拉框可用”）。

## 验证

- 无头测试：桩掉 mod/page 依赖，用假控件 + 真实 AnnData 跑通：
  同步 → 分组下拉仅含 2~50 取值的列；切换分组列组别列表联动；筛选列联动；二次同步覆盖旧选项。
- `py_compile` 通过。

> 后续教训见同目录另一篇：`控件状态陷阱/空QListWidget的bool为False致筛选取值列表空白.md`
> —— 填好了下拉，还要小心“控件真值判断”这个坑。
