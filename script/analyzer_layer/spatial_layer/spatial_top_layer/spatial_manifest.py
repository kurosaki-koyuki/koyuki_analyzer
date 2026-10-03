# -*- coding: utf-8 -*-
"""
空转数据集清单（manifest）读写脚本 - 负责 manifest.json 的读、校验、写与扫描
M1 的「数据集身份」由 manifest 文件决定，**不是** .rds 文件名（台账 K1/K2/K5 教训）
本模块只依赖标准库（json / os），不 import UI，不 import 任何重库，import 期不读盘
"""

import json
import os
import re

# 契约 §1：数据集身份 = manifest 文件；同 stem 的 .rds 必须存在
MANIFEST_SUFFIX = '.manifest.json'

# 契约 §3：只 os.listdir 一层 + 白名单后缀；必须挡住的已知脏东西（防御性黑名单，仅用于诊断提示）
KNOWN_BAD_NAME_HINTS = ('1.RDataTmp', '暂存可搬出', '结果果', '_raw_scaled', 'MES_adata')

# 契约 §2 的必需字段结构：'obj' 表示子对象，'list' 表示列表
_REQUIRED_TOP = {
    'schema': 'int',
    'dataset_id': 'str',
    'display_name': 'str',
    'created_at': 'str',
    'artifact': 'obj',
    'source': 'obj',
    'summary': 'obj',
    'samples': 'list',
    'figure_types': 'list',
    'pipeline': 'list',
    'rebuild': 'obj',
}
_REQUIRED_ARTIFACT = {'path': 'str', 'bytes': 'int', 'mtime': 'str', 'kind': 'str'}
_REQUIRED_SOURCE = {'engine': 'str', 'engine_version': 'str', 'raw_root': 'str',
                    'raw_files_total': 'int', 'raw_bytes_total': 'int'}
_REQUIRED_SUMMARY = {'n_samples': 'int', 'n_spots': 'int', 'n_genes': 'int',
                     'n_spots_pass_qc': 'int', 'n_clusters': 'int'}
_REQUIRED_REBUILD = {'requires_raw_root': 'bool', 'expected_samples': 'int'}
# samples[] 逐样本字段：UI 列样本只用它
_REQUIRED_SAMPLE = ('id', 'label', 'spots', 'spots_pass_qc', 'n_genes',
                    'median_nFeature', 'median_nCount', 'median_percent_mito',
                    'review_state')
_NUMERIC_SAMPLE_FIELDS = ('spots', 'spots_pass_qc', 'n_genes',
                          'median_nFeature', 'median_nCount', 'median_percent_mito')

# 原始样本编号判据（见 validate_manifest 里 samples[].id 的 2026-09-25 修订说明）。
#   字母开头的标识符：字母/数字/下划线/点/连字符。
#   · GSM7596587   通过（GEO，行为与修订前逐字一致）
#   · UKF241_C_ST  通过（Dryad/UKF 队列的原始样本目录名）
#   · '1' / 'S1'（序号）、'mgh258 / SOX2'（显示名）仍被挡
_SAMPLE_ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_.\-]*$')


class ManifestError(Exception):
    """manifest 不可用（文件缺失 / 不是合法 JSON / 顶层不是对象）—— 调用方只需捕获这一个类型"""
    pass


# =============================================================================
# 内部工具
# =============================================================================
def _typename(v):
    """把 Python 值映射成契约里的类型名，bool 必须先于 int 判断（bool 是 int 的子类）"""
    if isinstance(v, bool):
        return 'bool'
    if isinstance(v, int):
        return 'int'
    if isinstance(v, float):
        return 'float'
    if isinstance(v, str):
        return 'str'
    if isinstance(v, dict):
        return 'obj'
    if isinstance(v, list):
        return 'list'
    if v is None:
        return 'null'
    return type(v).__name__


def _check_fields(container, spec, prefix, issues):
    """逐字段检查存在性与类型；**只记录问题，不抛异常**（字段缺失一律容错）"""
    if not isinstance(container, dict):
        issues.append('%s: 期望对象，实际是 %s' % (prefix, _typename(container)))
        return
    for key, want in spec.items():
        full = '%s.%s' % (prefix, key)
        if key not in container:
            issues.append('%s: 字段缺失' % full)
            continue
        got = _typename(container[key])
        if got != want:
            # int/float 互通（JSON 里 3 与 3.0 都可能出现），其余严格
            if want == 'int' and got == 'float':
                continue
            issues.append('%s: 类型应为 %s，实际是 %s' % (full, want, got))


# =============================================================================
# 冻结接口（W2 依赖，不许改名）
# =============================================================================
def read_manifest(path) -> dict:
    """
    读取并校验 manifest.json。

    **失败语义（刻意分成两档）**：
      - 硬失败 → 抛 ManifestError：文件不存在 / 读不出 / 不是合法 JSON / 顶层不是对象。
        这几种情况下**没有任何可信内容**可返回，所以必须抛。
      - 软问题（字段缺失、类型不对、列表项不全）→ **绝不抛**，
        返回**已解析的部分**，并把问题清单挂在返回 dict 的保留键 `_issues` 上（list[str]）。
        这样 UI 侧只 catch 一个 ManifestError 就够，且判据永远拿得到。

    返回的 dict 就是 manifest 内容原样（可能不完整）；`_issues` 是唯一被本模块注入的键，
    write_manifest() 会自动丢弃所有 `_` 开头的键，因此回写不会污染文件。
    """
    if not path:
        raise ManifestError('manifest 路径为空')
    if not os.path.isfile(path):
        raise ManifestError('manifest 文件不存在: %s' % path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except UnicodeDecodeError as e:
        raise ManifestError('manifest 不是 UTF-8 编码: %s (%s)' % (path, e))
    except json.JSONDecodeError as e:
        raise ManifestError('manifest 不是合法 JSON: %s (%s)' % (path, e))
    except OSError as e:
        raise ManifestError('manifest 读取失败: %s (%s)' % (path, e))

    if not isinstance(data, dict):
        raise ManifestError('manifest 顶层必须是对象，实际是 %s' % _typename(data))

    data['_issues'] = validate_manifest(data)
    return data


def validate_manifest(d) -> list[str]:
    """
    校验 manifest 结构，返回**问题清单**（空列表 = 通过）。**永不抛异常**。

    只做**内存内结构校验**，不碰磁盘（因此不依赖 BASE_DIR、也不受 CWD 影响）。
    与磁盘相关的校验见 check_artifact()。

    注意：输入里若带 `_issues`（read_manifest 注入的），会被忽略，不会重复报告。
    """
    issues = []
    if not isinstance(d, dict):
        return ['顶层: 期望对象，实际是 %s' % _typename(d)]

    # 顶层字段
    _check_fields(d, _REQUIRED_TOP, 'manifest', issues)

    # schema 值（M1 只认 1）
    if isinstance(d.get('schema'), int) and not isinstance(d.get('schema'), bool):
        if d['schema'] != 1:
            issues.append('manifest.schema: M1 只支持 1，实际是 %s' % d['schema'])

    # dataset_id 非空
    if 'dataset_id' in d and isinstance(d['dataset_id'], str) and not d['dataset_id'].strip():
        issues.append('manifest.dataset_id: 不能为空字符串')

    # 子对象
    _check_fields(d.get('artifact'), _REQUIRED_ARTIFACT, 'artifact', issues)
    _check_fields(d.get('source'), _REQUIRED_SOURCE, 'source', issues)
    _check_fields(d.get('summary'), _REQUIRED_SUMMARY, 'summary', issues)
    _check_fields(d.get('rebuild'), _REQUIRED_REBUILD, 'rebuild', issues)

    # artifact.kind 取值
    art = d.get('artifact')
    if isinstance(art, dict) and isinstance(art.get('kind'), str) and art['kind'] != 'seurat_rds':
        issues.append('artifact.kind: M1 期望 seurat_rds，实际是 %s' % art['kind'])
    # artifact.path 必须是相对路径（契约 §2：相对 BASE_DIR）
    if isinstance(art, dict) and isinstance(art.get('path'), str):
        if os.path.isabs(art['path']):
            issues.append('artifact.path: 必须是相对 BASE_DIR 的路径，实际是绝对路径')

    # source.engine（M1 离线构建用 rscript）
    src = d.get('source')
    if isinstance(src, dict) and isinstance(src.get('engine'), str) and src['engine'] != 'rscript':
        issues.append('source.engine: M1 离线构建期望 rscript，实际是 %s' % src['engine'])
    if isinstance(src, dict) and isinstance(src.get('raw_root'), str):
        if os.path.isabs(src['raw_root']):
            issues.append('source.raw_root: 必须是相对 BASE_DIR 的路径，实际是绝对路径')

    # samples[] 明细
    samples = d.get('samples')
    if isinstance(samples, list):
        if len(samples) == 0:
            issues.append('samples: 为空列表（数据集至少要有 1 个样本）')
        ids_seen = {}
        for i, s in enumerate(samples):
            p = 'samples[%d]' % i
            if not isinstance(s, dict):
                issues.append('%s: 期望对象，实际是 %s' % (p, _typename(s)))
                continue
            for key in _REQUIRED_SAMPLE:
                if key not in s:
                    issues.append('%s.%s: 字段缺失' % (p, key))
            sid = s.get('id')
            if isinstance(sid, str):
                # 契约 §2 取值纪律：samples[].id 必须是**原始样本编号**（不是序号、不是显示名）。
                # ★ 2026-09-25 修订（实装 Dryad/UKF 胶质瘤数据集时实测到的真阻塞）：
                #   原判据写死 `sid.startswith('GSM')`，会把**非 GEO 数据集**整体判成
                #   【致命问题】——`spatial_data_analysis._FATAL_ISSUE_PREFIXES` 含 `samples[`，
                #   于是 `load_data()` 直接拒绝加载（实测 ok=False，msg 全是 samples[i].id）。
                #   但 GEO 之外根本没有 GSM 编号：Dryad 队列的"原始编号"就是原始样本目录名
                #   （如 UKF241_C_ST）。⇒ 现改为"字母开头的标识符"这一**同一个意图**的判据：
                #     · GSM7596587 通过（GEO 行为逐字不变）
                #     · UKF241_C_ST 通过（Dryad/UKF）
                #     · '1'/'S1'（序号）、含空格或斜杠的显示名 仍被挡住
                if not _SAMPLE_ID_RE.match(sid):
                    issues.append(
                        '%s.id: 必须是原始样本编号（字母开头的标识符：字母/数字/下划线/点/连字符），'
                        '实际是 %s' % (p, sid))
                if sid in ids_seen:
                    issues.append('%s.id: 与 samples[%d] 重复 (%s)' % (p, ids_seen[sid], sid))
                else:
                    ids_seen[sid] = i
            else:
                issues.append('%s.id: 缺失或不是字符串' % p)
            for key in _NUMERIC_SAMPLE_FIELDS:
                if key in s and not isinstance(s[key], (int, float)):
                    issues.append('%s.%s: 期望数值，实际是 %s' % (p, key, _typename(s[key])))
            # 逐样本一致性：pass_qc 不应超过 spots
            sp, spq = s.get('spots'), s.get('spots_pass_qc')
            if isinstance(sp, (int, float)) and isinstance(spq, (int, float)) and spq > sp:
                issues.append('%s: spots_pass_qc(%s) 大于 spots(%s)' % (p, spq, sp))

        # summary 与 samples 的交叉一致性（不通过也不算致命，只报问题）
        summ = d.get('summary')
        if isinstance(summ, dict) and isinstance(summ.get('n_samples'), int):
            if summ['n_samples'] != len(samples):
                issues.append('summary.n_samples(%s) 与 samples 条数(%s) 不一致'
                              % (summ['n_samples'], len(samples)))

    # rebuild 与 samples 的交叉一致性
    # 方向性判定：expected_samples 指「重建该数据集应当能产出多少样本」（= 原始目录里的 GSM 目录数），
    # 因此 **samples 少于 expected_samples 是合法的**（用 --samples 做的子集冒烟构建），
    # 只有 samples 多于 expected_samples 才是真矛盾。
    rb = d.get('rebuild')
    if isinstance(rb, dict) and isinstance(rb.get('expected_samples'), int) and isinstance(samples, list):
        if len(samples) > rb['expected_samples']:
            issues.append('rebuild.expected_samples(%s) 小于 samples 条数(%s)：不可能重建出这么多样本'
                          % (rb['expected_samples'], len(samples)))

    # pipeline[] 明细
    pipe = d.get('pipeline')
    if isinstance(pipe, list):
        for i, st in enumerate(pipe):
            if not isinstance(st, dict):
                issues.append('pipeline[%d]: 期望对象，实际是 %s' % (i, _typename(st)))
            elif 'step' not in st:
                issues.append('pipeline[%d].step: 字段缺失' % i)

    # 脏名提示（契约 §3 要求挡住的已知脏东西）
    did = d.get('dataset_id')
    if isinstance(did, str):
        for bad in KNOWN_BAD_NAME_HINTS:
            if bad in did:
                issues.append('dataset_id: 命中已知脏名片段 %r' % bad)

    return issues


def write_manifest(d, path) -> None:
    """
    写出 manifest.json（UTF-8 / 缩进 2 / 保留中文不转义）。

    - 所有 `_` 开头的内部键（如 read_manifest 注入的 `_issues`）会被丢弃，保证回写不污染文件；
    - 会先调用 validate_manifest()，**有问题照写但在返回值里无法回传**（签名冻结为 -> None），
      因此需要判据时请调用方自行先 validate_manifest()；
    - 目录不存在会自动创建；写失败抛 ManifestError。
    """
    if not isinstance(d, dict):
        raise ManifestError('write_manifest 需要 dict，实际是 %s' % _typename(d))
    payload = {k: v for k, v in d.items() if not (isinstance(k, str) and k.startswith('_'))}
    parent = os.path.dirname(os.path.abspath(path))
    try:
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except OSError as e:
        raise ManifestError('manifest 写出失败: %s (%s)' % (path, e))


# =============================================================================
# 附加工具（不是冻结接口，供 W1/W2 与构建驱动使用；纯 stdlib）
# =============================================================================
def manifest_stem(path) -> str:
    """从 manifest 文件名取数据集 stem：'GSE237183.manifest.json' -> 'GSE237183'"""
    name = os.path.basename(path)
    if name.endswith(MANIFEST_SUFFIX):
        return name[:-len(MANIFEST_SUFFIX)]
    return os.path.splitext(name)[0]


def resolve_artifact_path(manifest, base_dir) -> str:
    """把 manifest.artifact.path（相对 BASE_DIR）解析成绝对路径；缺失返回 ''"""
    art = manifest.get('artifact') if isinstance(manifest, dict) else None
    rel = art.get('path') if isinstance(art, dict) else None
    if not isinstance(rel, str) or not rel:
        return ''
    if os.path.isabs(rel):
        return os.path.normpath(rel)
    return os.path.normpath(os.path.join(base_dir, rel))


def resolve_raw_root(manifest, base_dir) -> str:
    """把 manifest.source.raw_root（相对 BASE_DIR）解析成绝对路径；缺失返回 ''"""
    src = manifest.get('source') if isinstance(manifest, dict) else None
    rel = src.get('raw_root') if isinstance(src, dict) else None
    if not isinstance(rel, str) or not rel:
        return ''
    if os.path.isabs(rel):
        return os.path.normpath(rel)
    return os.path.normpath(os.path.join(base_dir, rel))


def check_artifact(manifest, base_dir) -> list[str]:
    """
    磁盘侧校验：主对象是否存在 / 体积是否与 manifest 记的一致。返回问题清单（空 = 通过）。**永不抛异常**。

    与 validate_manifest() 分开，是因为结构校验不该依赖磁盘与 BASE_DIR
    （契约 §3 要求 load_data 把「存在性/体积/mtime」校验一遍，W2 可调本函数）。
    """
    issues = []
    path = resolve_artifact_path(manifest, base_dir)
    if not path:
        return ['artifact.path: 缺失，无法定位主对象']
    if not os.path.isfile(path):
        return ['artifact: 主对象不存在: %s' % path]
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return ['artifact: 无法读取体积: %s (%s)' % (path, e)]
    art = manifest.get('artifact') or {}
    want = art.get('bytes')
    if isinstance(want, int) and want > 0 and size != want:
        issues.append('artifact.bytes: manifest 记 %s，磁盘实际 %s（差 %s）'
                      % (want, size, size - want))
    want_m = art.get('mtime')
    if isinstance(want_m, str) and want_m:
        try:
            import datetime
            actual = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%dT%H:%M:%S')
            # 只比到秒；mtime 在同一秒内写入属正常，不做严格相等判定
            if len(want_m) >= 19 and actual[:19] != want_m[:19]:
                issues.append('artifact.mtime: manifest 记 %s，磁盘实际 %s' % (want_m, actual))
        except (OSError, ValueError, OverflowError):
            pass
    return issues


def scan_manifest_files(scan_dir) -> list:
    """
    契约 §3 的扫描：**只 os.listdir 一层** + 白名单 `*.manifest.json` + 同 stem 的 `.rds` 存在性检查。
    返回 [(dataset_id, manifest_path, artifact_path), ...]，按 dataset_id 排序。**永不抛异常**。

    不做：不递归、不打开 .rds、不算哈希、不按体积去重。
    """
    out = []
    if not scan_dir or not os.path.isdir(scan_dir):
        return out
    try:
        entries = os.listdir(scan_dir)
    except OSError:
        return out
    for name in entries:
        if not name.endswith(MANIFEST_SUFFIX):
            continue
        mpath = os.path.join(scan_dir, name)
        if not os.path.isfile(mpath):
            continue
        stem = manifest_stem(mpath)
        rds = os.path.join(scan_dir, stem + '.rds')
        if os.path.isfile(rds):
            out.append((stem, mpath, rds))
    out.sort(key=lambda t: t[0])
    return out
