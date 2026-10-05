# AGENTS.md —— 后续 AI Agent 作业规则（koyuki_analyzer 3.0）

> 这份文件**是给 AI 看的**，不是给用户看的说明书。
> 它记录「这套项目怎么协作、结构长什么样、子代理怎么建」的可复用规则，
> 写于 **2026-10-03**，基于一次真实交付（小工具主页 + Circos 圈图页 + 全站「发送到基因列表文件夹」控件）
> 的全部经验，**包括我踩过的每一个坑**。请先读完再动手。

---

## 0. 30 秒速览：新 Agent 的第一件事

```
1) 读本文件（尤其 §1 铁律、§2 结构、§5 环境坑）
2) 找到当前任务的契约：docs/features/<主题>_contract.md —— 契约是唯一规格来源
3) 跑一次现有门禁看基线：python _d_gate_*.py（或 tests/ 下的脚本），记下 PASS/FAIL 数
4) 确认工作目录与 git 状态：git -C <repo> status --porcelain | wc -l
5) 再动手：小改动自己改；跨多文件/多页面的改动 → 按 §3 拆子代理
6) 交回后必须**独立复跑**，不许只看子代理的结论（§4.2）
```

**三条最容易犯的错**（都已真实发生过）：
- ❌ 只看子代理的汇报就下结论 → 必须自己跑一遍
- ❌ 用「文本匹配」当验证手段 → 会被注释/字符串骗到，必须用 AST 或运行期实测
- ❌ 删除/移动用户文件（哪怕看起来是"临时文件"）→ 曾导致 ~119 个验证脚本与 49 篇文档丢失

---

## 1. 我们怎么运作（协作模型）

### 1.1 三种角色

| 角色 | 职责 | 边界 |
|---|---|---|
| **协调者（Coordinator）** | 写契约、写门禁/探针、拆任务、独立复核、向用户汇报 | **不写产品代码**（页面/内核等 worker 所有的文件） |
| **Worker（实现子代理）** | 按契约实现自己名下的文件、自测、如实汇报 | 只动自己范围内的文件；不改契约与共享工具 |
| **Researcher（调研子代理）** | 找资料、找参考图、给方案建议 | **不写产品代码**，产物放独立参考目录 |

### 1.2 八条铁律

1. **契约先行**：任何跨文件/跨页面的改动，先在 `docs/features/` 落一份契约 md，冻结接口、口径、验收条件，再动手。
2. **验收可脚本化**：不许写"看起来正确"这种验收；每条都要能变成一段能跑出 PASS/FAIL 的代码。
3. **一个文件一个作者**：同一时间只允许一个 worker 写同一个文件。共享文件（`gui_styles.py`、`page_intersect.py`、`import_config.py`、`gene_list_export.py`）默认**谁也不许改**，要改必须协调者批准并串行化。
4. **独立复核**：worker 交回的每个结论，协调者都要用自己的手段复现一遍（跑它的自测 + 自己的门禁 + 抽检）。
5. **先量再说**：任何"大概/应该是"的判断都要用命令量出来（行数、条数、字节、md5、像素）。
6. **如实报错**：自己引入的 bug 要写进报告（本项目历史上最好的三次 bug 定位都来自"报错"而不是"成功"）。
7. **不碰用户数据**：见 §6。`appdata/genelists` 是用户数据，只读；`OUTPUT/` 下任何既有内容不许删。
8. **留痕**：契约里追加「验收结果」「已知限制」「事故记录」三节；门禁日志写进 `debug_output/`。

### 1.3 一轮交付的标准流程

```
① 用户提需求
② 协调者侦察：量现状、找相关文件、确认哪一层该改（§2.2）
③ 写契约 docs/features/xxx_contract.md（含：事实、接口、每文件所有权、验收清单 G1..Gn）
④ 写门禁 _d_gate_xxx.py（先跑一次，确认它对"未改动状态"如实报红）
⑤ 拆子代理（§3），并发派发；worker 各自实现 + 自测
⑥ worker 交回 → 协调者复跑自测 + 跑门禁 + 抽检 → 有假信号就修**自己的判据**
⑦ 冻结修订（记录参与文件 md5）→ 向用户汇报：做了什么、证据、局限、待决策项
```

---

## 2. 项目结构

### 2.1 顶层（`koyuki_beta3.0test/`，本仓库）

```
start.py                 程序入口（git 跟踪）
script/                  全部代码（git 跟踪，380 个文件 / 约 13.6 万行 / 106k 代码行）
appdata/                 运行数据（**git 忽略**，37 GB）
  ├ circos_data/         恒定数据：核型带/基因坐标/密度/GC（1.4 MB，运行必需）
  ├ genelists/           基因列表（各分析共用输入；**用户数据，只读**）
  ├ elements/            界面素材（19.5 MB）
  ├ mods/                主题/角色模组（940 MB，其中 start/*.webm 开场动画占 897 MB）
  ├ main/ bulk_main/ R_sc_main/ spatial_main/   大数据（h5ad/rds，共约 35 GB）
  └ circos_data_source/  离线原始数据（1.67 GB，不进发布包）
OUTPUT/                  分析结果（**git 忽略**，6.3 GB）—— 约定 OUTPUT/<工具>/<YYYYmmdd_HHMMSS>/
AGENTS.md                本文件
```

> ⚠️ **`docs/`、`tests/`、`koyuki_analyzer.spec`、`requirements.txt` 目前在兄弟目录
> `../koyuki_beta2.5test/`**（那是历史工作区，仍保留完整副本）。**建议尽快把它们并进
> 3.0test 并纳入 git**——2026-10-03 发生过一次误删，文档只能从 git stash 里捞回来。

### 2.2 `script/` 四层架构（必须遵守）

每个页面 = 一个目录 + **四个文件**，职责严格分离：

| 文件 | 职责 | **禁止** |
|---|---|---|
| `ui_layout_<页>.py` | 只建控件（全部来自 `gui_styles` 工厂） | 禁止 `clicked.connect`、`QFileDialog`、`os.startfile` |
| `ui_bind_<页>.py` | 信号连接、取数、编排 | 禁止写业务算法 |
| `ui_func_<页>.py` | 只做展示（更新控件、日志） | 禁止写业务逻辑 |
| `<页>_analysis.py` | 业务/算法（可调 R） | 禁止碰 Qt 控件 |

**门禁会 AST 检查这条**：layout 层出现"业务信号连接/文件对话框/startfile"即失败
（注意：`toggled` 这类 UI 局部行为允许，见 §4.4 的假信号教训）。

模块划分（实测规模，会随开发增长）：

| 目录 | 说明 |
|---|---|
| `script/analyzer_layer/bulk_layer/` | 转录组：差异/KM/Cox/logrank/WGCNA/一致性分型/机器学习/免疫浸润/GDSC |
| `script/analyzer_layer/scRNAseq_layer/` | 单细胞：UMAP/小提琴/气泡/差异/hdWGCNA/StaVIA/monocle3/CellChat/虚拟敲除 |
| `script/analyzer_layer/spatial_layer/` | 空转：初始/区域画布/表达/小提琴/差异/两种气泡/review |
| `script/analyzer_layer/commontools_layer/` | 小工具：`commontools_top_layer`(hub) / `vennplot_layer` / `circos_layer` / `page_template_layer` |
| `script/utils_layer/` | `gui_styles.py`(样式工厂，**142 个文件依赖，改动风险最高**)、`page_intersect.py`(页面注册表)、`gene_list_export.py`、`import_config.py` |
| `script/main_layer/` | 主窗口与入口绑定（`MainWindowBind`） |
| `script/mods_layer/` | 主题/角色/BGM/音效（换肤就靠它，不要硬编码颜色） |

**变体子层**：少数页面有 `py_diff/` `r_diff/` 子目录（Python 版/R 版实现），
注册表指向哪个就以哪个为准；**不要假设同名文件都在同一层**（用 `git ls-files` 或 glob 查实际路径）。

### 2.3 页面注册表（`script/utils_layer/page_intersect.py`）

每个页面登记一条：

```python
{
    'name': 'circos_page',                     # 路由名
    'ui_class': 'CircosPageUI',
    'ui_module': 'script.analyzer_layer...ui_layout_circos',
    'bind_class': 'CircosBind',
    'bind_module': 'script.analyzer_layer...ui_bind_circos',
    'attr_name': 'circos_page',                # 约定：== name
    'data_source_page': 'commontools_top_page', # 可选：数据从哪个页面同步
    'sync_method': '...',                       # 可选
}
```

- 当前 **41 个页面**；`init_all_pages` 逐页 try/except 构造，单页失败不拖垮主界面。
- 该文件自称「`attr_name` 必须逐字等于 `name`（本项目测试断言）」，但**有 4 处历史例外**
  （`scRNAseq_r_diff_page→r_diff_page` 等，见 `_d_gate_bulk_cluster.py` 的已知例外表）。
  **不要擅自改这 4 处**——那些页面 bind 引用的是 `self.r_diff_page` 这类属性，改了会断绑定。
- 新增页面必须同时：注册 + 建四层文件 + 在对应 hub 加卡片 + 跑 `_d_probe_pages_init.py`。

### 2.4 数据与输出约定

- **路径唯一来源**：`script/utils_layer/import_config.py`（`APPDATA_PATH`、`BASE_DIR` 等）。**不要自己拼路径**（历史上 45 个文件各拼了一遍 `genelists` 路径，导致行为不一致）。
- **基因列表格式**：`appdata/genelists/*.xlsx` = **单列、无表头**（首格即基因名）。
  - 读取统一走 `bulk_gene_set_utils.read_gene_list_first_column()`（+ `drop_gene_header_token`）**单一真相源**。
  - 历史上 4 个 reader 用 `pd.read_excel()`（默认 `header=0`）**静默丢掉第一个基因**，已修；**新代码禁止直接 `pd.read_excel` 读基因列表**。
  - 发送新列表：`from script.utils_layer.gene_list_export import ask_and_send`，支持
    `ask_and_send(parent, genes=None, *, groups=[(标签, 基因, 默认勾选)], multi=True, prefix=...)`。
- **输出目录**：`OUT_BASE = <BASE_DIR>/OUTPUT`，工具内一律 `OUT_BASE/<工具>/<时间戳>/`；
  导出走 `QFileDialog.getSaveFileName`（在 bind 层），格式按扩展名分派（PNG/SVG/PDF）。
- **图必须正方形**：`savefig` **不要用 `bbox_inches="tight"`**（它会把标题/图例算进外接框，
  输出就不是 `figsize×dpi` 的正方形了 —— 这个坑踩过两次）。

### 2.5 技术栈与运行环境

- GUI：PyQt5；绘图：matplotlib / seaborn / **pycirclize**（Circos 页）
- 单细胞/空转：scanpy / anndata / omicverse（`appdata` 里有对照环境）
- R 侧：Seurat / WGCNA / monocle3 / CellChat / StaVIA / GDSC，**经 rpy2 调用**，
  本机 `R_HOME=A:/TOOLS/R/R-4.6.1`
- 解释器：`C:\Users\totoko\AppData\Local\Programs\Python\Python313\python.exe`
- **没有 pytest**（`tests/*.py` 是 pytest 风格但跑不起来 → 见 §4.3 的"手动执行"手法）

### 2.6 git 与版本控制（含必须知道的坑）

- 分支 **`beta3.0`**（独立根提交），只跟踪 `script/` + `start.py`（+ 本文件）；`appdata/`、`OUTPUT/` 被忽略。
- **`.gitignore` 不支持行尾注释**：`!/appdata/circos_data/   # 说明` 会被当成带 `#` 的模式而**静默失效**
  —— 本项目第一次建库时因此把 6.3 GB 的 `OUTPUT/` 提交了进去。注释必须单独成行。
- 本机全局配置有 `url.https://ghfast.top/https://github.com/.insteadof = https://github.com/`
  ⇒ 所有 `github.com` 地址被改写成加速代理，而**代理上没有缓存凭据、推送会卡认证**。
  现有配置：`remote.origin.url` = 正常 github.com（拉取走代理，快）、
  `remote.origin.pushurl` = `https://GitHub.com/...`（**大小写变体绕过重写**，直连并用已缓存凭据）。
  **不要把 pushurl 改成小写 `github.com`**，否则推送又要凭据。
- `git ls-files` 默认转义非 ASCII 路径（`core.quotepath`）⇒ 脚本里一律加 `-c core.quotepath=false`，或用 Python 处理。
- 日常三条命令：`git add -A` → `git commit -m "..."` → `git push`。

---

## 3. 如何创建与定义子代理（Worker）

### 3.1 什么时候该拆

| 场景 | 做法 |
|---|---|
| 改 1-2 个文件、逻辑清楚 | 协调者自己改 |
| 跨 ≥3 个文件 / ≥2 个页面 / 需要长自测 | **拆 worker** |
| 纯调研（找参考图、比方案） | 拆 **researcher**（严禁它写产品代码） |
| 需要"第二双眼睛"复核结论 | 拆 **verifier**（只读、给证据） |

### 3.2 按模块切分，不要按"步骤"切分

**一个 worker 一个互不重叠的文件集合**。例（本项目实际用法）：

| worker | 范围 |
|---|---|
| BULK | `bulk_layer/**` 的 5 个页面 + 4 处基因列表读者 |
| SC | `scRNAseq_layer/**` 的 3 个页面 |
| MISC | 空转差异页 + 韦恩图页 |

共享文件（`gui_styles.py`、`page_intersect.py`、`gene_list_export.py`、`import_config.py`）
**永远由协调者独占**；如果多个 worker 都要改共享文件 → **串行**，不要并发。

### 3.3 Worker 提示词模板（可直接抄）

> Worker **看不到你的对话上下文**，提示词必须自包含。必备七段：

```
你是 <项目> 的实现 worker，代号 **worker <X>**。工作目录：<绝对路径>。

## 先读（必读，别凭印象）
1. 契约：docs/features/<xxx>_contract.md —— **唯一规格来源**，尤其 §<相关节>
2. 共享工具：<path>（已完成并验证，**不要改它**）
3. 证据探针：<gate 脚本>（可先跑一遍看行为）

## 你的范围（只动这些文件，别的不许碰）
- <文件路径 + 关键行号/函数名>
- <...>

## 口径要求（照契约，不要自由发挥）
- <接口签名、默认值、命名、日志格式>

## 硬性约束
- <用户数据只读路径> **只读**：自测只能用临时名（如 `_x_<pid>_test.xlsx`）并在**结束前删除**，
  结束时列出目录确认无残留、md5 未变
- 不装依赖；不动 `appdata/` 其它内容；**不删除 `OUTPUT/` 下任何既有内容**
- 分层纪律：layout 只建控件；bind 连信号与逻辑；func 只管展示；业务逻辑进 analysis
- 临时脚本/日志放 `debug_output/<你的命名空间>/`

## 自测（必须真跑，贴出命令与结果）
1. <针对本次改动的关键断言，逐条列>
2. **回归**：确认没弄坏原有功能（有现成探针就跑）
3. 用**真实读者/真实后端**回读（不要只断言"函数被调用了"）

## 报告要求（简洁）
1. 改了哪些文件（路径 + 关键行）
2. 关键口径的取数来源（具体到函数/属性名）
3. 自测命令与 PASS/FAIL 数字
4. **已知不确定处**（没跑到的真实路径要明说）
5. 确认用户数据未被改动（md5）
```

### 3.4 并发与通信规则

- **并发上限**：同时 ≤3-4 个 worker（再多人就管不过来，共享文件冲突风险上升）。
- 后台运行（`run_in_background: true`）→ 协调者继续做自己的事（写门禁/量数据），**不要空等**。
- worker 中途提问 → 协调者给**明确裁决 + 理由**（不要"你看着办"）；缺信息就自己先去量。
- worker 完成后可 `send_message` 追加增量任务（同一个 worker 续做同一模块，比新开更省上下文）。
- 协调者要结束时：确认所有 worker 状态、收齐产物、`interrupt_agent` 掉不再需要的。

### 3.5 Worker 交回后，协调者必须做的五件事

1. **复跑它的自测**（自己敲命令，不信它贴的日志）
2. **跑自己的门禁**（跨模块的那份）
3. **抽检语义**：读代码确认"取数来源"符合契约（门禁只能查结构，查不了语义）
4. **查假信号**：如果门禁红了，先怀疑**门禁自己的判据**（§4.4）
5. **冻结修订**：把参与文件 md5 记下来（`_d_record_revision.py` 的做法），下次比对判断"之前的验证还算不算数"

---

## 4. 验证纪律（本项目最值钱的部分）

### 4.1 门禁长什么样

```python
# _d_gate_<主题>.py —— 独立、可重复、非零退出即失败
PASS, FAIL = [], []
def chk(cond, name, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("[OK]  " if cond else "[FAIL]") + " " + name + ("  |  " + detail if detail else ""), flush=True)
...
print("门禁结果：PASS = %d   FAIL = %d" % (len(PASS), len(FAIL)))
sys.exit(0 if not FAIL else 1)
```

- 每个断言都要**打印实测值**（不是只打 OK）：`读到 %d 个，应 %d 个`。
- 门禁**先对"未改动状态"跑一次**：如果它一开始就全绿，说明它测不出东西。
- 命名：协调者 `_d_*.py`；worker 用 `_b_`/`_c_`/`_sc_`/`_m_`/`_w_` + 自己的编号，避免互相覆盖。

### 4.2 独立复核的铁律

- **不信转述**：worker 说"读回 11 个"，你要自己读一遍。
- **交叉证据**：同一个事实用两条独立路径验证（例：本地 tree 哈希 vs 远端 tree 哈希；
  内核自报 `stats` vs 从 PNG 像素量出来的半径）。
- **老实报错**：复核发现的问题，一半来自"我自己的判据写错了"（§4.4），要写进报告。

### 4.3 有效的验证手法（照抄即可）

| 手法 | 用途 | 例子 |
|---|---|---|
| **AST 检查** | 分层纪律、接口签名、必须调用的函数 | layout 无 `clicked.connect`；bind 必须含 `ask_and_send(...groups=...)` |
| **黄金图回归** | 防止视觉悄悄漂移 | 首次生成基线 PNG，之后逐像素 diff 必须为 0 |
| **字节级比对** | 证明"发出去的与本地一致" | `git rev-parse HEAD^{tree}` vs `origin/branch^{tree}` |
| **真实读者回读** | 证明产物能被下游消费 | 写完 xlsx 后用项目自己的 reader 读回并比数量 |
| **像素量化** | 主观观感变成数字 | 径向墨迹剖面里"最宽空环带"宽度（改前 52px → 改后 16px） |
| **领域标志物抽检** | 生信数据正确性 | 机械刺激集合里必须能查到 PIEZO1/PIEZO2/TRPV4 |
| **md5/revision 冻结** | 判断旧验证是否仍有效 | 记录参与文件 md5，改了就重跑门禁 |
| **手动执行 pytest 风格用例** | 本机没装 pytest | 注入最小 `pytest` 替身模块后 `import` 并逐个调用 `test_*()` |

### 4.4 我们踩过的假信号（**不要重复**）

| 假信号 | 真相 | 正确做法 |
|---|---|---|
| 门禁报"layout 有 `clicked.connect`" | 匹配到了 layout 里**说明纪律的注释** | 用 AST 查真实调用，不查文本 |
| 门禁报"共享文件被违规改动" | 判据是"最近 90 分钟 mtime 有变"，而整个工作区都是未提交状态 | 改用**内容不变量**（注册表完整性、工厂函数仍在） |
| 门禁报"G5 读者修复失败" | 实现方把 3 个 reader 改成调用共享函数，门禁却要求"每个文件都有 read_excel" | 判据要接受**多条合法实现路径** |
| 探针报"按钮文字没渲染" | Qt **offscreen 平台不绘制文字**（真机正常） | 文字内容用程序断言；要截图就用原生平台 |
| worker 自测报 1 个 FAIL | 它的**文档解析器**把契约代码块里的注释当成参数名 | 解析前剥注释；别怪实现 |
| 测试断言页面总数 39 实际 41 | 上一轮合法新增了 2 个页面，**冻结哨兵过期** | 按盘上事实同步哨兵，并写明理由 |
| `Measure-Object -Line` 数出的行数偏少 | PowerShell 不统计空行 | 用 Python 数行 |

---

## 5. 环境与工具坑（都是本机实测过的）

### 5.1 PowerShell（Windows）

- **内联 `python -c "..."` 会被吃掉引号**（尤其中文/嵌套引号）→ **写成 .py 文件再跑**。
- `"..." + (if(...){"a"}else{"b"})` **不是合法语法**（`if` 不能当表达式）→ 写成函数。
- `<<<` 是 bash heredoc，PowerShell 不支持 → 用 `@'...'@ | Set-Content`。
- `Get-Content | Select-Object -First/-Last` 会截断管道 ⇒ `$LASTEXITCODE` 变 1（**假失败**）→ 用
  `*> log.txt` 落盘再读。
- `Measure-Object -Line` **不数空行**（少报 8~10%）→ 用 Python。
- 非 ASCII 路径：`git` 输出会被转义（`\233\276`），`Test-Path` 直接报"非法字符"→ 交给 Python 处理。
- `robocopy` 退出码 **0-7 都算成功**，`>=8` 才是错误。
- `cmdkey /list` 可查 Windows 凭据（排查 git 认证问题很有用）。

### 5.2 Python

- **双引号字符串里不要再用 ASCII 双引号**（`print("... "x" ...")` 会 SyntaxError）→ 用 `「」`。
- 本机 Python 直连 HTTPS 有时报证书错 → 用 `curl.exe`（`subprocess.run(["curl.exe", ...])`）。
- 读文件一律 `io.open(..., encoding="utf-8", errors="replace")`（项目里有历史非 UTF-8 文件）。

### 5.3 Qt / matplotlib

- **离屏（`QT_QPA_PLATFORM=offscreen`）不绘制文字**；`emoji_function_for_mods.happy()/wrong()/attention()`
  的弹窗在离屏会**段错误（0xC0000005）** → 探针要避开这些路径。
- 构造页面/窗口前**先 `import numpy, pandas, anndata`**（历史段错误就是这么规避的）。
- `import pycirclize` 会**全局改** 3 个 matplotlib rcParams（`savefig.bbox`→`tight`、`savefig.pad_inches`、
  `svg.fonttype`）→ 必须存-还，否则污染 App 里所有其它图。
- 中文字体：App 的 `font.sans-serif=['SimHei',...]`，而 **SimHei 没有粗体字面** ⇒ 粗体静默失效。
  正确做法：`rc_context({"font.family": ["DejaVu Sans", "<有真粗体的中文字体>"]})`，
  且 `rc_context` **必须包住 `savefig`**（字体是延迟解析的）。

### 5.4 R / rpy2

- `R_HOME=A:/TOOLS/R/R-4.6.1`，导入 rpy2 时会打印自身日志（不是错误）。
- R 侧报错要 `tryCatch` 吃掉并返回空（不要让整个页面崩）。

---

## 6. 安全与数据保护（不可违反）

1. **`appdata/genelists/` 是用户数据**：只读。需要测试就写临时名（`_x_<pid>_*.xlsx`）并**在结束前删除**，
   结束时报"目录内只剩原 N 个文件、md5 未变"。
2. **不许删除 `OUTPUT/` 下任何既有内容**（曾发生一次清理把用户的结果图删掉）。
3. **不许删除/移动用户工作区里的文件**（哪怕看着像临时文件）。
   2026-10-03 的事故：用户"挪"文件后，**~119 个验证脚本与 49 篇文档从老工作区消失**；
   文档靠 git stash 捞回，**脚本因为从未提交而永久丢失**。
   ⇒ **教训：可复用的门禁/测试必须进 git**（建议放 `tests/probes/`），不要只在工作区里裸放。
4. **不许 `pip install` 新依赖**（除非用户明确同意）；优先用现有栈（networkx/igraph 都已在）。
5. **改共享文件前必须串行化**并跑 `_d_gate_bulk_cluster.py` 里的共享文件不变量检查。
6. 临时产物统一放 `debug_output/`，命名带前缀（`_d_`/`_b_`/…）便于清理与识别。

---

## 7. 附录：模板与速查

### 7.1 契约骨架

```markdown
# <主题> 契约（冻结）
## §0 事实基础（已实测，勿凭印象改）  ← 数字、路径、接口现状
## §1 接口（冻结，不要在页面里另写）    ← 函数签名、默认值、返回结构
## §2 需要改的文件与改法                ← 表：文件 | 行 | 改法
## §3 覆盖范围与口径                    ← 每个页面/模块的具体行为
## §4 UI / 分层约定
## §5 验收（G1..Gn，逐条可脚本化）
## §6 文件所有权（协调者 / worker X / worker Y）
## §7 验收结果（复跑数字 + 证据）
## §8 已知限制与待决策项
## §9 事故记录与流程约定
```

### 7.2 常用命令速查

```powershell
# 统计代码量（别用 PowerShell 数行）
python _d_count_lines.py

# 语法检查（内存 compile，别写 __pycache__）
python -c "import io,os;[compile(io.open(os.path.join(dp,f),encoding='utf-8',errors='replace').read(),f,'exec') for dp,dn,fn in os.walk('script') if '__pycache__' not in dp for f in fn if f.endswith('.py')]"

# 页面注册表体检（41 页、attr_name 一致性）
python _d_probe_pages_init.py

# git 状态与远端一致性
git -c core.quotepath=false status --porcelain
git rev-parse "HEAD^{tree}"; git rev-parse "origin/beta3.0^{tree}"
```

### 7.3 术语表

| 词 | 含义 |
|---|---|
| **契约** | `docs/features/*.md` 里的冻结规格，唯一真相来源 |
| **门禁** | 可执行的验收脚本（`_d_gate_*.py`），非零退出即失败 |
| **探针** | 用于量现状/取证据的临时脚本（`_d_probe_*.py`） |
| **黄金图** | 用作视觉回归基线的输出图 |
| **冻结修订** | 记录参与文件的 md5，用于判断旧验证是否仍有效 |
| **宁少勿假** | 取不到的数据就不造；宁可少一个子集，也不塞假数据 |
| **默认复现旧行为** | 新功能上线时，用户不动手的结果必须与改动前逐字一致 |

---

*本文件由 2026-10-03 那轮协作的协调者编写。如果你（后续 Agent）在实践中发现了新的坑或更好的做法，
**请直接更新本文件并提交**——这份文件的价值就在于它是活的。*
