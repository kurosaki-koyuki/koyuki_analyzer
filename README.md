# Koyuki Analyzer - 单细胞 / Bulk 分析工具

基于 PyQt5 的生物信息学分析工具，支持单细胞（scRNA-seq）和 Bulk 转录组数据的可视化与分析。采用模组化设计，支持自定义主题皮肤，遵循四层分离架构。

---

## 目录结构

```
koyuki_analyzer/
├── start.py                    # 应用程序入口
├── koyuki_analyzer.spec        # PyInstaller打包配置文件
├── 打包注意事项.md              # 打包问题记录与关键文件清单
├── config/
│   └── r_kernel_config.txt     # R内核配置文件
├── script/
│   ├── utils_layer/             # 工具层（公共基础能力）
│   │   ├── import_config.py     # ⭐ 集中导入配置（所有库在这里加载）
│   │   ├── gui_styles.py        # GUI样式模板函数（所有控件统一创建入口）
│   │   ├── gui_god_type_style.py # 样式配置（god type风格）
│   │   ├── page_intersect.py    # ⭐ 页面路由管理器（统一注册、跳转、数据同步）
│   │   ├── music_controller_fix.py # 音乐控制器修复工具
│   │   ├── emoji_trigger.py     # 表情触发器
│   │   └── utils_tools.py       # 通用工具函数
│   ├── mods_layer/              # 模组层（皮肤/主题系统）
│   │   ├── mod_manager.py       # 模组管理器（含独立路径锚定）
│   │   └── emoji_function_for_mods.py # 模组表情弹窗功能
│   ├── main_layer/              # 主界面层
│   │   ├── ui_layout_main.py    # 主界面布局
│   │   ├── ui_bind.py           # 主界面绑定（导航统一走page_intersect）
│   │   ├── ui_func_main.py      # 主界面前端功能
│   │   └── settings_layer/      # 设置页面（子页面）
│   ├── introduce_layer/         # R语言交互层
│   │   └── r2p_layer/
│   │       └── r_kernel_interface.py # R内核接口
│   └── analyzer_layer/          # 分析功能层
│       ├── scRNAseq_layer/      # 单细胞分析模块
│       │   ├── scRNAseq_top_layer/    # ⭐ 单细胞主页（数据加载入口）
│       │   │   ├── ui_layout_scRNAseq_top.py
│       │   │   ├── ui_bind_scRNAseq_top.py
│       │   │   ├── ui_func_scRNAseq_top.py
│       │   │   └── scRNAseq_data_analysis.py
│       │   ├── initial_analysis_layer/  # 初步分析
│       │   ├── violin_layer/            # 小提琴图
│       │   ├── diff_layer/              # 差异分析
│       │   ├── sc_genelist_bubble_layer/ # 基因集气泡图
│       │   └── sc_targetgene_bubble_layer/ # 目标基因气泡图
│       ├── bulk_layer/          # Bulk 分析模块
    │       │   ├── bulk_top_layer/         # ⭐ Bulk主页（数据加载入口）
    │       │   │   ├── ui_layout_bulk_top.py
    │       │   │   ├── ui_bind_bulk_top.py
    │       │   │   ├── ui_func_bulk_top.py
    │       │   │   └── bulk_data_analysis.py
    │       │   ├── bulk_expr_layer/     # 表达量分析
    │       │   ├── bulk_cox_layer/      # Cox 生存分析
    │       │   ├── bulk_cluster_layer/  # 一致性分析
    │       │   ├── bulk_km_layer/       # KM 生存曲线
│       │   │   └── bulk_km_r_layer/ # KM R模式（基于R的生存分析）
│       │   ├── bulk_corre_layer/    # 相关性分析
│       │   │   ├── bulk_corredot_layer/     # 相关性散点图
│       │   │   └── bulk_correbubble_layer/  # 相关性气泡图
│       │   │       ├── bulk_correbubble_type1_layer/
│       │   │       ├── bulk_correbubble_type2_layer/
│       │   │       ├── bulk_correbubble_type3_layer/
│       │   │       ├── bulk_correbubble_type4_layer/
│       │   │       ├── bulk_correbubble_type5_layer/
│       │   │       └── bulk_correbubble_type6_layer/
│       │   └── wgcna_layer/         # WGCNA 共表达网络
│       └── commontools_layer/       # 通用工具
│           └── vennplot_layer/      # 韦恩图交集
└── appdata/
    ├── mods/                        # 模组资源
    │   ├── kurosaki_koyuki/         # 默认模组
    │   ├── Misaka_mikoto/           # 御坂美琴模组
    │   └── Asuna_ichinose/          # 一之濑明日奈模组
    ├── main/                        # 单细胞数据目录
    ├── bulk_main/                   # Bulk 数据目录
    └── pics/                        # 公共图片资源
```

---

## 架构设计

### 四层分离架构

本项目采用 **四层分离** 的模块化设计，确保各层职责清晰、易于维护：

```
┌─────────────────────────────────────────────────────────┐
│                    ui_layout_xxx.py                     │
│  布局层：创建控件、规划布局、设置样式尺寸                   │
│  - 只负责UI创建                                           │
│  - 不写业务逻辑                                           │
│  - 不绑定信号（导航绑定全部在bind层）                       │
│  - 控件必须从gui_styles模板调用                            │
├─────────────────────────────────────────────────────────┤
│                    ui_bind_xxx.py                       │
│  绑定层：信号绑定、编排analysis与func的协作                 │
│  - 全权负责粘合内外                                       │
│  - 连接信号与业务                                         │
│  - 不直接操作数据                                         │
│  - 页面导航绑定统一在 bind_navigation() 方法              │
├─────────────────────────────────────────────────────────┤
│                    ui_func_xxx.py                       │
│  功能层：前端显示、控件内容更新、图片渲染                    │
│  - 负责UI逻辑显示                                         │
│  - 不绑定信号                                             │
│  - 不写业务算法                                           │
├─────────────────────────────────────────────────────────┤
│                    xxx_analysis.py                       │
│  分析层：纯业务逻辑，不涉及UI                              │
│  - 数据处理                                               │
│  - 统计分析                                               │
│  - 图表生成                                               │
└─────────────────────────────────────────────────────────┘
```

### 集中导入机制

所有第三方库和标准库的导入统一在 `import_config.py` 中进行，其他脚本只引用该文件：

```python
from script.utils_layer.import_config import *
```

**设计优势：**
- 避免重复导入，提高性能
- 统一管理依赖版本
- 便于打包配置
- 支持动态路径锚定
- 包含打包兼容性处理（元数据模拟、inspect模拟等）

### 路径动态锚定

支持开发模式和打包模式的路径自动适配：

```python
# 在import_config.py中定义
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _find_appdata_path():
    """查找appdata目录的正确路径，支持多种打包布局"""
    candidates = [
        os.path.join(BASE_DIR, "appdata"),
        os.path.join(BASE_DIR, "_internal", "appdata"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return os.path.join(BASE_DIR, "appdata")
```

### 页面路由系统（PageIntersect）

**核心特点：** 所有页面注册、跳转、数据同步统一由 `page_intersect.py` 管理。

```
                    PageIntersect（单例）
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   页面注册中心      跳转接口         数据同步机制
  (page_configs)  (go_to_page_*)   (sync_method配置)
        │                 │                 │
        └─────────────────┴─────────────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                 │
  主界面（home_page）              各分析子页面
         │                    （启动时创建UI，跳转时初始化bind）
         │
    btn_single_cell_main ──→ scRNAseq_top_page
    btn_bulk_main        ──→ bulk_top_page
    btn_venn             ──→ venn_page
    ...
```

**关键机制：**
- **统一入口**：所有跳转必须走 `go_to_page_with_bind()`
- **预加载**：Bind层在启动时预加载，确保页面切换丝滑
- **自动同步**：配置了 `data_source_page` + `sync_method` 的页面会自动从父页面同步数据
- **父页返回**：子页面通过 `go_to_parent_page(page_name)` 返回父页面
- **解耦设计**：主界面不直接import任何子页面的bind类

---

## 核心模块详解

### 1. 工具层 (utils_layer)

#### import_config.py ⭐
集中导入配置和路径定义，是项目的核心配置文件。

**主要功能：**
- 定义 `BASE_DIR` 根目录和 `APPDATA_PATH` 数据路径
- 导入所有第三方库（PyQt5、Scanpy、Pandas、rpy2等）
- 定义数据路径常量
- 处理打包兼容性问题（元数据模拟、inspect模拟等）

**关键变量：**
```python
BASE_DIR              # 项目根目录
APPDATA_PATH          # appdata目录路径（支持动态查找）
DATA_PATH             # 默认H5AD数据文件路径
SCAN_DATA_PATH        # 单细胞数据扫描目录
BULK_SCAN_DATA_PATH   # Bulk数据扫描目录
OUT_BASE              # 分析结果输出根目录
```

**打包兼容性处理：**
- `importlib.metadata.version` 模拟 - 解决打包后包元数据缺失问题
- `inspect.getsource` 模拟 - 解决打包后源代码不可用问题
- `sys.stdout` 非空检查 - 解决 `--windowed` 模式下编码问题

---

#### gui_styles.py
GUI样式模板函数库，提供**所有控件**的统一创建入口。子界面不得自行创建原始控件，必须使用模板函数。

**可用控件模板：**

| 函数 | 功能 |
|------|------|
| `create_styled_button(text, ...)` | 样式化按钮（支持import/run/export/normal类型） |
| `create_styled_combo_box()` | 样式化下拉框 |
| `create_styled_line_edit()` | 样式化输入框 |
| `create_styled_text_edit(read_only)` | 样式化文本编辑框 |
| `create_styled_label(text, ...)` | 样式化标签 |
| `create_styled_panel()` | 样式化面板容器（返回widget+layout） |
| `create_styled_group_box(title)` | 样式化分组框 |
| `create_styled_frame()` | 样式化框架容器 |
| `create_styled_list_widget(...)` | 样式化列表控件 |
| `create_styled_table()` | 样式化表格控件 |
| `create_styled_checkbox(text)` | 样式化复选框 |
| `create_styled_number_input(...)` | 样式化数字输入框（带上下按钮） |
| `create_styled_slider(orientation)` | 样式化滑块 |
| `create_styled_tab_widget(movable, ...)` | 样式化标签页（支持拖动排序） |
| `create_styled_tab_page(tab_widget, title)` | 创建标签页 |
| `create_editable_input_table(...)` | 可编辑输入表格（支持Excel粘贴） |
| `bind_button_with_sound(btn, callback, ...)` | 绑定带音效的按钮 |

---

#### page_intersect.py ⭐
**页面路由管理器** - 全权管理所有页面的注册、跳转、数据同步。

**单例实例：**
```python
from script.utils_layer.page_intersect import page_intersect
```

**页面配置字段：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✓ | 页面唯一名称 |
| `ui_class` | ✓ | UI类名 |
| `ui_module` | ✓ | UI模块路径 |
| `bind_class` | ✓ | Bind类名 |
| `bind_module` | ✓ | Bind模块路径 |
| `attr_name` | ✓ | 页面widget在UI类中的属性名 |
| `parent_page` | ✗ | 父页面名称（用于返回上一页） |
| `data_source_page` | ✗ | 数据来源页面名称 |
| `sync_method` | ✗ | 数据同步方法名 |

**核心方法：**

```python
# 跳转页面（唯一入口）
page_intersect.go_to_page_with_bind('目标页面', parent_bind=None)

# 返回主页
page_intersect.go_to_home()

# 返回父页面
page_intersect.go_to_parent_page('当前页面名')

# 绑定按钮到页面跳转
page_intersect.bind_page_button(button, '目标页面', parent_bind=None)

# 初始化所有页面
page_intersect.init_all_pages(main_window, stacked_widget)
```

**当前已注册页面（共18个）：**

| 页面名称 | 类型 | 父页面 | 数据来源 |
|----------|------|--------|----------|
| `scRNAseq_top_page` | 单细胞主页 | - | 独立加载 |
| `analysis_page` | 单细胞/初步分析 | - | scRNAseq_top_page |
| `violin_page` | 单细胞/小提琴图 | - | scRNAseq_top_page |
| `diff_page` | 单细胞/差异分析 | - | scRNAseq_top_page |
| `sc_genelist_bubble_page` | 单细胞/基因集气泡图 | - | scRNAseq_top_page |
| `sc_targetgene_bubble_page` | 单细胞/目标基因气泡图 | - | scRNAseq_top_page |
| `bulk_top_page` | Bulk主页 | - | 独立加载 |
| `bulk_expr_page` | Bulk/表达量分析 | - | bulk_top_page |
| `bulk_cox_page` | Bulk/Cox分析 | - | bulk_top_page |
| `bulk_cluster_page` | Bulk/一致性分析 | - | bulk_top_page |
| `bulk_km_page` | Bulk/KM曲线 | - | bulk_top_page |
| `bulk_km_r_page` | Bulk/KM-R模式 | bulk_km_page | bulk_km_page |
| `bulk_corre_page` | Bulk/相关性分析 | - | bulk_top_page |
| `bulk_corredot_page` | Bulk/相关性散点图 | bulk_corre_page | bulk_corre_page |
| `bulk_correbubble_page` | Bulk/相关性气泡图 | bulk_corre_page | bulk_corre_page |
| `wgcna_page` | Bulk/WGCNA | - | bulk_top_page |
| `venn_page` | 通用/韦恩图 | - | - |
| `settings_page` | 设置 | - | - |

---

### 2. 模组层 (mods_layer)

#### mod_manager.py
模组管理器，负责模组的加载、切换和资源管理。

**独立路径锚定：**
由于存在循环导入问题，`mod_manager.py` 独立定义路径变量，避免依赖 `import_config.py`：

```python
if getattr(sys, 'frozen', False):
    _MOD_BASE_DIR = os.path.dirname(sys.executable)
else:
    _MOD_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

**5函数模组开发模型：**
模组开发者只需重写5个函数即可控制整个应用外观：

```python
# 【主界面 3 个函数】
_get_main_layout()   # 主界面位置配置
_get_main_colors()   # 主界面配色
_get_main_fonts()    # 主界面字体

# 【子界面 2 个函数】
_get_sub_colors()    # 子界面配色
_get_sub_fonts()     # 子界面字体
```

**核心方法：**
| 方法 | 功能 |
|------|------|
| `get_current_mod()` | 获取当前模组实例 |
| `set_current_mod(name)` | 切换当前模组 |
| `get_music_controller_class()` | 获取音乐控制器类 |
| `get_current_styles()` | 获取当前样式配置 |
| `get_current_paths()` | 获取当前资源路径 |

---

### 3. 主界面层 (main_layer)

#### ui_layout_main.py
主界面布局脚本，定义主界面的UI结构。

**关键流程：**
```python
# 1. 创建堆叠窗口
self.stacked_widget = QStackedWidget()

# 2. 创建并注册主页
self.create_home_page()
page_intersect.register_page('home_page', self.home_page)

# 3. 统一初始化所有分析子页面（由page_intersect管理）
page_intersect.init_all_pages(self, self.stacked_widget)

# 4. 设置初始页面
self.stacked_widget.setCurrentWidget(self.home_page)
```

---

#### ui_bind.py
主界面绑定脚本。

**注意：** 主界面不再直接管理子页面跳转，所有导航统一走 `page_intersect`：

```python
def bind_page_navigation(self):
    # 所有按钮绑定到 page_intersect.go_to_page_with_bind
    self.btn_single_cell_main.clicked.connect(
        lambda: page_intersect.go_to_page_with_bind('scRNAseq_top_page')
    )
    self.btn_bulk_main.clicked.connect(
        lambda: page_intersect.go_to_page_with_bind('bulk_top_page')
    )
    # ...
```

---

### 4. 分析层 (analyzer_layer)

#### 子页面标准结构

每个分析子页面都遵循 **四层分离** 架构，包含4个脚本文件：

```
xxx_layer/
├── ui_layout_xxx.py      # 布局：创建控件（全部用gui_styles模板）
├── ui_bind_xxx.py        # 绑定：信号绑定 + 导航绑定 + 编排
├── ui_func_xxx.py        # 功能：纯前端显示逻辑
└── xxx_analysis.py       # 分析：纯业务算法
```

#### 导航绑定规范

每个子页面的bind层必须实现 `bind_navigation()` 方法：

```python
def init_bindings(self):
    self.bind_music_controls()
    self.bind_xxx_functions()
    self.bind_navigation()  # ← 导航统一在这里

def bind_navigation(self):
    # 一级页面：返回主页
    if hasattr(self.xxx_ui, 'btn_back_xxx'):
        self.xxx_ui.btn_back_xxx.clicked.connect(page_intersect.go_to_home)
    
    # 二级子页面：返回父页面
    # if hasattr(self.xxx_ui, 'btn_back_xxx'):
    #     self.xxx_ui.btn_back_xxx.clicked.connect(
    #         lambda: page_intersect.go_to_parent_page('当前页面名')
    #     )
```

#### 数据同步规范

继承父页面数据的子页面需实现同步方法：

```python
def sync_data_from_xxx(self, source_bind=None):
    """从xxx页面同步数据"""
    if source_bind is None:
        source_bind = getattr(self.parent, 'xxx_bind', None)
    if source_bind is None:
        return
    
    # 从 source_bind 获取数据
    self.adata = source_bind.adata
    self.analysis.set_adata(self.adata)
    # ...
```

---

## 数据加载流程

### 单细胞数据加载流程

```
主界面 → 单细胞主页(scRNAseq_top_page) → 各分析子页面
              │
              ├── 选择数据目录
              ├── 扫描h5ad文件
              ├── 选择文件并加载
              └── 数据同步到子页面
```

### Bulk数据加载流程

```
主界面 → Bulk主页(bulk_top_page) → 各分析子页面
              │
              ├── 选择数据目录
              ├── 扫描h5ad文件
              ├── 选择文件并加载
              └── 数据同步到子页面
```

**关键设计：**
- 子界面不保留加载/扫描数据的控件，一切从主页获取
- 数据通过 `page_intersect` 的 `sync_method` 自动同步
- 支持从主页跳转到任何子页面，子页面返回主页

---

## 现有分析模块

### scRNAseq 单细胞分析

| 模块 | 路径 | 功能 | 数据来源 |
|------|------|------|----------|
| 单细胞主页 | `scRNAseq_layer/scRNAseq_top_layer/` | 数据加载、扫描、目录选择 | 独立加载 |
| 初步分析 | `scRNAseq_layer/initial_analysis_layer/` | 数据质控、统计分析 | 单细胞主页 |
| 小提琴图 | `scRNAseq_layer/violin_layer/` | 单基因小提琴图可视化 | 单细胞主页 |
| 差异分析 | `scRNAseq_layer/diff_layer/` | 差异基因分析、统计检验 | 单细胞主页 |
| 基因集气泡图 | `scRNAseq_layer/sc_genelist_bubble_layer/` | 基因集表达量气泡图 | 单细胞主页 |
| 目标基因气泡图 | `scRNAseq_layer/sc_targetgene_bubble_layer/` | 目标基因表达量气泡图 | 单细胞主页 |

### Bulk 转录组分析

| 模块 | 路径 | 功能 | 数据来源 |
|------|------|------|----------|
| Bulk主页 | `bulk_layer/bulk_top_layer/` | 数据加载、扫描、目录选择 | 独立加载 |
| 表达量分析 | `bulk_layer/bulk_expr_layer/` | 表达量分布、箱线图 | Bulk主页 |
| Cox分析 | `bulk_layer/bulk_cox_layer/` | 单因素/多因素Cox回归 | Bulk主页 |
| 一致性分析 | `bulk_layer/bulk_cluster_layer/` | 一致性聚类分析（开发中） | Bulk主页 |
| KM曲线 | `bulk_layer/bulk_km_layer/` | Kaplan-Meier生存曲线 | Bulk主页 |
| KM-R模式 | `bulk_layer/bulk_km_layer/bulk_km_r_layer/` | 基于R的KM分析 | KM曲线 |
| 相关性分析 | `bulk_layer/bulk_corre_layer/` | 基因表达相关性 | Bulk主页 |
| 相关性散点图 | `bulk_layer/bulk_corre_layer/bulk_corredot_layer/` | 散点图可视化 | 相关性分析 |
| 相关性气泡图 | `bulk_layer/bulk_corre_layer/bulk_correbubble_layer/` | 气泡图可视化（6种类型） | 相关性分析 |
| WGCNA | `bulk_layer/wgcna_layer/` | 加权共表达网络分析 | Bulk主页 |

### 通用工具

| 模块 | 路径 | 功能 |
|------|------|------|
| 韦恩图 | `commontools_layer/vennplot_layer/` | 多组数据交集可视化 |

---

## R语言集成

### R内核接口

项目通过 `rpy2` 模块实现Python与R的交互：

```python
# 在import_config.py中导入
import rpy2
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri
from rpy2.robjects.packages import importr
```

### R脚本路径

R脚本不打包，保持外置。程序通过 `get_r_script_path()` 函数动态查找：

```python
def get_r_script_path(caller_file, r_script_name):
    """动态获取R脚本路径，支持开发模式和打包模式"""
    # ...
```

### 支持的R包

| R包 | 用途 |
|-----|------|
| survival | KM生存分析 |
| survminer | KM曲线可视化 |
| ggplot2 | 高级绘图 |
| cowplot | 图形组合 |

---

## 添加新页面的步骤

1. **创建四层文件**：
   ```
   script/analyzer_layer/xxx_layer/
   ├── ui_layout_xxx.py      # 只用gui_styles模板创建控件
   ├── ui_bind_xxx.py        # 实现 bind_navigation()
   ├── ui_func_xxx.py        # 纯前端显示
   └── xxx_analysis.py       # 纯业务逻辑
   ```

2. **在 `page_intersect.py` 中注册**：
   ```python
   {
       'name': 'xxx_page',
       'ui_class': 'XxxPageUI',
       'ui_module': 'script.analyzer_layer.xxx_layer.ui_layout_xxx',
       'bind_class': 'XxxBind',
       'bind_module': 'script.analyzer_layer.xxx_layer.ui_bind_xxx',
       'attr_name': 'xxx_page',
       'parent_page': 'parent_page_name',      # 可选
       'data_source_page': 'source_page_name', # 可选
       'sync_method': 'sync_data_from_xxx'     # 可选
   }
   ```

3. **在主界面添加跳转按钮**（如果是一级页面）

4. **在bind层实现 `bind_navigation()` 方法**

5. **如需数据同步，实现 `sync_data_from_xxx()` 方法**

6. **在spec文件中添加hiddenimports**

---

## 模组开发指南

### 创建新模组

1. 在 `appdata/mods/` 下创建模组目录：
   ```
   appdata/mods/my_mod/
   ├── background/        # 背景图
   ├── GUI/               # GUI图标
   ├── music/             # 背景音乐
   ├── sound/             # 音效
   ├── start/             # 启动视频
   ├── emoji/             # 表情图片
   ├── pet/               # 宠物资源（可选）
   └── mod_script/
       ├── __init__.py
       └── mod_script.py  # 模组脚本
   ```

2. 继承 `BaseMod` 并实现5个核心函数：
   ```python
   class MyMod(BaseMod):
       def _get_main_layout(self):
           return {...}  # 位置配置
       
       def _get_main_colors(self):
           return {...}  # 主界面配色
       
       def _get_main_fonts(self):
           return {...}  # 主界面字体
       
       def _get_sub_colors(self):
           return {...}  # 子界面配色
       
       def _get_sub_fonts(self):
           return {...}  # 子界面字体
   ```

---

## 启动方式

```bash
python start.py
```

---

## 打包方式

```bash
pyinstaller koyuki_analyzer.spec --noconfirm
```

**详细打包说明请参考：** [打包注意事项.md](打包注意事项.md)

---

## 依赖环境

- Python 3.13.4
- PyQt5
- Scanpy 1.10.0+
- Pandas 2.2.0+
- NumPy 1.26.0+
- Matplotlib 3.8.0+
- Seaborn
- SciPy 1.14.0+
- Pygame (音效)
- rpy2 3.5.0+ (R模式)
- OpenCV
- h5py 3.10.0+
- anndata 0.10.0+

---

## 常见问题

### Q: 如何添加新的分析子界面？

参见上方「添加新页面的步骤」，注意：
- 所有控件必须用 `gui_styles.py` 中的模板创建
- 导航绑定统一放在bind层的 `bind_navigation()` 方法
- 页面跳转统一走 `page_intersect.go_to_page_with_bind()`
- 需要在spec文件中添加hiddenimports

### Q: 如何让子页面继承父页面的数据？

1. 在 `page_intersect.py` 的页面配置中设置 `data_source_page` 和 `sync_method`
2. 在子页面bind层实现同步方法，接受 `source_bind=None` 参数
3. 跳转时会自动调用同步方法并传入来源页面的bind对象

### Q: 如何切换模组？

通过主界面右上角的模组选择器，或调用：
```python
from script.mods_layer.mod_manager import global_mod_manager
global_mod_manager.set_current_mod("模组名称")
```

### Q: 打包后遇到问题怎么办？

请参考 [打包注意事项.md](打包注意事项.md)，里面记录了打包过程中遇到的所有问题及解决方案。
