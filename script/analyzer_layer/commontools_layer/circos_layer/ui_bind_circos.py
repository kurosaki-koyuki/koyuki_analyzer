# -*- coding: utf-8 -*-
"""
Circos 圈图界面功能绑定脚本 - 全权负责粘合内外
绑信号 + 组装参数 + 调内核 CircosAnalysis + 预览/表格/导出/跳转
（风格照抄 commontools_layer/vennplot_layer/ui_bind_vennplot.py）
"""

from script.utils_layer.import_config import *
from script.mods_layer.mod_manager import global_mod_manager
from script.utils_layer.music_controller_fix import fix_music_controller_bindings
from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.commontools_layer.circos_layer.ui_func_circos import CircosFunc

try:
    from script.analyzer_layer.commontools_layer.circos_layer.circos_analysis import CircosAnalysis
except Exception as _import_err:      # 内核文件尚未就绪时不炸掉整个页面注册
    CircosAnalysis = None
    _CIRCOS_IMPORT_ERROR = _import_err
else:
    _CIRCOS_IMPORT_ERROR = None


TIER_TO_MB = {"1 Mb": 1, "2 Mb": 2, "5 Mb": 5, "10 Mb": 10, "20 Mb": 20}


class CircosBind:
    """Circos 圈图功能绑定类 - 全权负责粘合内外"""

    def __init__(self, parent_window, circos_ui):
        self.parent = parent_window
        self.circos_ui = circos_ui
        self.func = CircosFunc(circos_ui, parent_window)
        self._bindings_done = False

        self.analysis = None
        if CircosAnalysis is not None:
            try:
                self.analysis = CircosAnalysis(log_callback=self.func.log)
            except Exception as e:            # 兜底：不带回调再试一次
                try:
                    self.analysis = CircosAnalysis()
                except Exception as e2:
                    self.func.log(f"[ERROR] CircosAnalysis 初始化失败: {e2}")
                    self.analysis = None
            if self.analysis is None:
                self.func.log(f"[ERROR] CircosAnalysis 初始化失败: {e}")

        self.last_out_dir = None              # 最近一次输出目录
        self._last_plot_path = None           # 最近一次预览图路径
        self.last_missing = []                # 最近一次未匹配基因
        self._genelists_loaded = False

        self.init_bindings()

        if self.analysis is None:
            self.func.log("[ERROR] Circos 内核（CircosAnalysis）不可用: %s" % _CIRCOS_IMPORT_ERROR)
            self.func.log("[INFO] 页面控件仍可正常显示，运行前请确认内核文件已就绪")
        else:
            self.refresh_genelists(log=True)

    # ------------------------------------------------------------ 绑定入口
    def init_bindings(self):
        """初始化所有绑定"""
        if self._bindings_done:
            return

        self.bind_music_controls()
        self.bind_gene_input()
        self.bind_parameter_controls()
        self.bind_circos_buttons()
        self.bind_navigation()

        # 构造时先执行一次互斥（与 bulk_expr 的做法一致）
        self._on_input_mode_changed()
        self._on_genes_text_changed()

        self._bindings_done = True

    def bind_music_controls(self):
        """绑定音乐控制"""
        if hasattr(self.circos_ui, 'music_controller'):
            fix_music_controller_bindings(self, self.circos_ui.music_controller)

    def bind_navigation(self):
        """绑定页面导航按钮 → 小工具主页"""
        if hasattr(self.circos_ui, 'btn_back_circos'):
            self.circos_ui.btn_back_circos.clicked.connect(
                lambda: page_intersect.go_to_page_with_bind('commontools_top_page'))

    def bind_gene_input(self):
        """绑定基因输入相关控件"""
        if hasattr(self.circos_ui, 'circos_input_mode_combo'):
            self.circos_ui.circos_input_mode_combo.currentIndexChanged.connect(
                self._on_input_mode_changed)
        if hasattr(self.circos_ui, 'circos_genes_text'):
            self.circos_ui.circos_genes_text.textChanged.connect(self._on_genes_text_changed)
        if hasattr(self.circos_ui, 'circos_genelist_combo'):
            self.circos_ui.circos_genelist_combo.currentIndexChanged.connect(
                self._on_genes_text_changed)
        if hasattr(self.circos_ui, 'btn_refresh_genelists'):
            self.circos_ui.btn_refresh_genelists.clicked.connect(self._on_refresh_genelists)

    def bind_parameter_controls(self):
        """绑定标题开关等参数控件（标题显示与否联动输入框可用性）"""
        if hasattr(self.circos_ui, 'circos_show_title_check'):
            self.circos_ui.circos_show_title_check.stateChanged.connect(
                self._on_show_title_changed)
        self._on_show_title_changed()

    def bind_circos_buttons(self):
        """绑定功能按钮"""
        if hasattr(self.circos_ui, 'btn_run_circos'):
            self.circos_ui.btn_run_circos.clicked.connect(self.run_circos_analysis)
        if hasattr(self.circos_ui, 'btn_clear_circos'):
            self.circos_ui.btn_clear_circos.clicked.connect(self.clear_circos)
        if hasattr(self.circos_ui, 'btn_export_circos'):
            self.circos_ui.btn_export_circos.clicked.connect(self.export_circos_image)
        if hasattr(self.circos_ui, 'btn_open_out_dir'):
            self.circos_ui.btn_open_out_dir.clicked.connect(self.open_output_dir)

    # ------------------------------------------------------------ 页面前置
    def on_page_entered(self):
        """路由每次跳转进来时回调：刷新基因列表下拉与计数

        动机见 page_intersect.py:683-698 —— bind 是启动时一次性建好的，
        首次跳转不会重建，不在这里刷新页面就会是空的。
        """
        try:
            self.refresh_genelists(log=False)
        except Exception as e:
            self.func.log(f"[ERROR] on_page_entered 刷新基因列表失败: {e}")
        try:
            self._on_input_mode_changed()
            self._on_genes_text_changed()
        except Exception as e:
            self.func.log(f"[ERROR] on_page_entered 刷新计数失败: {e}")

    # ------------------------------------------------------------ 互斥与计数
    def _current_mode(self):
        combo = getattr(self.circos_ui, 'circos_input_mode_combo', None)
        if combo is None:
            return "手动输入"
        return combo.currentText()

    def _on_input_mode_changed(self, *args):
        """输入模式互斥：手动输入 ↔ 外部列表（照抄 bulk_expr 的做法）"""
        ui = self.circos_ui
        manual_mode = self._current_mode() == "手动输入"

        if hasattr(ui, 'circos_genes_text'):
            ui.circos_genes_text.setEnabled(manual_mode)
        if hasattr(ui, 'circos_genelist_combo'):
            ui.circos_genelist_combo.setEnabled(not manual_mode)
        if hasattr(ui, 'btn_refresh_genelists'):
            ui.btn_refresh_genelists.setEnabled(not manual_mode)

        self.func.log(f"[INFO] 输入模式：{self._current_mode()}")

    def _on_show_title_changed(self, *args):
        """不显示标题时，标题输入框置灰"""
        if hasattr(self.circos_ui, 'circos_show_title_check') and \
                hasattr(self.circos_ui, 'circos_title_input'):
            show = self.circos_ui.circos_show_title_check.isChecked()
            self.circos_ui.circos_title_input.setEnabled(show)

    def _on_refresh_genelists(self):
        self.refresh_genelists(log=True)

    def _on_genes_text_changed(self, *args):
        """输入即计数：文本/下拉变化时刷新「解析到 N 个基因」"""
        try:
            genes = self._resolve_input_genes(quiet=True)
            self.func.update_gene_count(len(genes))
        except Exception:
            self.func.clear_gene_count()

    # --------------------------------------------------------- 基因列表刷新
    def refresh_genelists(self, log=False):
        """用内核 scan_gene_lists() 填充基因列表下拉、list_assemblies() 填充参考基因组下拉"""
        if self.analysis is None:
            self.func.update_genelist_hint(0)
            self.func.update_gene_count(0)
            if log:
                self.func.log("[ERROR] 内核不可用，无法扫描基因列表")
            return 0

        # 参考基因组下拉（至少保留 hg38，内核给了就用内核的）
        try:
            assemblies = list(self.analysis.list_assemblies() or [])
        except Exception as e:
            self.func.log(f"[ERROR] 扫描参考基因组失败: {e}")
            assemblies = []
        if not assemblies:
            assemblies = ["hg38"]
        if hasattr(self.circos_ui, 'circos_assembly_combo'):
            self.func.set_combo_items(self.circos_ui.circos_assembly_combo, assemblies)
            if self.circos_ui.circos_assembly_combo.currentText() not in assemblies:
                self.circos_ui.circos_assembly_combo.setCurrentText("hg38")

        # 基因列表下拉
        try:
            paths = self.analysis.scan_gene_lists()
        except Exception as e:
            self.func.log(f"[ERROR] 扫描基因列表失败: {e}")
            paths = []

        count = self.func.update_genelist_combo(paths)
        self._genelists_loaded = True
        if log:
            self.func.log(f"[INFO] 参考基因组：{assemblies}")
            self.func.log(f"[INFO] 基因列表目录扫描完成，共 {count} 个文件")
            for p in paths:
                self.func.log(f"[INFO]   - {os.path.basename(str(p))}")

        # 下拉内容变了，计数也跟着刷新
        self._on_genes_text_changed()
        return count

    # --------------------------------------------------------- 基因来源解析
    def _selected_genelist_path(self):
        combo = getattr(self.circos_ui, 'circos_genelist_combo', None)
        if combo is None or combo.count() == 0:
            return ""
        data = combo.currentData()
        if data:
            return str(data)
        return str(combo.currentText() or "")

    def _resolve_input_genes(self, quiet=False):
        """按当前输入模式取基因列表（手动 → parse_gene_text；外部 → read_gene_list_file）"""
        if self.analysis is None:
            return []

        if self._current_mode() == "手动输入":
            if not hasattr(self.circos_ui, 'circos_genes_text'):
                return []
            text = self.circos_ui.circos_genes_text.toPlainText()
            if not str(text).strip():
                return []
            return list(self.analysis.parse_gene_text(text) or [])

        path = self._selected_genelist_path()
        if not path:
            if not quiet:
                self.func.log("[ERROR] 未选择外部基因列表文件")
            return []
        if not os.path.exists(path):
            if not quiet:
                self.func.log(f"[ERROR] 基因列表文件不存在: {path}")
            return []
        return list(self.analysis.read_gene_list_file(path) or [])

    # ------------------------------------------------------------ 参数组装
    def _collect_render_params(self):
        """从界面控件组装 render(...) 的参数（键名与内核签名逐字一致）"""
        ui = self.circos_ui

        def _checked(name, default=True):
            w = getattr(ui, name, None)
            return bool(w.isChecked()) if w is not None else bool(default)

        def _num(name, default):
            w = getattr(ui, name, None)
            if w is None:
                return default
            try:
                return w.value()
            except Exception:
                return default

        def _text(name, default=""):
            w = getattr(ui, name, None)
            if w is None:
                return default
            try:
                return w.text()
            except Exception:
                return default

        tier = TIER_TO_MB.get(_text('circos_tier_combo'), 5)
        assembly = _text('circos_assembly_combo') or "hg38"

        formats = []
        if _checked('circos_fmt_png_check'):
            formats.append("png")
        if _checked('circos_fmt_svg_check'):
            formats.append("svg")
        if _checked('circos_fmt_pdf_check'):
            formats.append("pdf")
        # 预览必须有位图：用户只勾 SVG/PDF 时临时也出 PNG（见日志说明）
        preview_png = "png" not in formats
        if preview_png:
            formats.append("png")

        title_text = _text('circos_title_input') or "Chromosomal Distribution of Genes"
        if not _checked('circos_show_title_check'):
            title_text = ""

        dpi = _num('circos_dpi_input', 300)
        figsize = _num('circos_size_input', 10)
        max_labels = _num('circos_max_labels_input', 40)

        # ---- 基因名标签三个旋钮（契约 §14.2/§14.3）----
        label_fontsize = _num('circos_label_fontsize_input', 9)
        label_layers = _num('circos_label_layers_input', 2)
        label_min_sep = _num('circos_label_minsep_input', 10)

        try:
            dpi = int(float(dpi))
        except (TypeError, ValueError):
            dpi = 300
        try:
            figsize = float(figsize)
        except (TypeError, ValueError):
            figsize = 10.0
        try:
            max_labels = int(float(max_labels))
        except (TypeError, ValueError):
            max_labels = 40
        try:
            label_fontsize = int(float(label_fontsize))
        except (TypeError, ValueError):
            label_fontsize = 9
        try:
            label_layers = int(float(label_layers))
        except (TypeError, ValueError):
            label_layers = 2
        try:
            label_min_sep = float(label_min_sep)
        except (TypeError, ValueError):
            label_min_sep = 10.0

        return {
            "assembly": assembly,
            "tier": tier,
            "show_ideogram": _checked('circos_show_ideogram_check'),
            "show_gc": _checked('circos_show_gc_check'),
            "show_density_heatmap": _checked('circos_show_density_heatmap_check'),
            "show_density_bars": _checked('circos_show_density_bars_check'),
            "show_loci": _checked('circos_show_loci_check'),
            "show_gene_labels": _checked('circos_show_gene_labels_check'),
            "show_legend": _checked('circos_show_legend_check'),
            "show_title": _checked('circos_show_title_check'),
            "title_text": title_text,
            "species": "Homo sapiens",
            "max_labels": max_labels,
            "label_fontsize": label_fontsize,
            "label_layers": label_layers,
            "label_min_sep": label_min_sep,
            "dpi": dpi,
            "figsize": figsize,
            "formats": tuple(formats),
            "_preview_png": preview_png,
        }

    # ------------------------------------------------------------------ 运行
    def run_circos_analysis(self):
        """运行 Circos 圈图"""
        ui = self.circos_ui
        self.func.log("=" * 60)
        self.func.log("[INFO] 开始运行 Circos 圈图分析")

        if self.analysis is None:
            self.func.log("[ERROR] Circos 内核（CircosAnalysis）不可用，无法运行")
            self.func.alert_error("Circos 内核尚未就绪（circos_analysis.py 不可用）")
            return

        try:
            # 1) 取基因
            mode = self._current_mode()
            self.func.log(f"[INFO] 输入模式：{mode}")
            if mode == "外部列表":
                self.func.log(f"[INFO] 基因列表文件：{self._selected_genelist_path() or '（未选择）'}")

            symbols = self._resolve_input_genes(quiet=False)
            self.func.update_gene_count(len(symbols))
            self.func.log(f"[INFO] 解析数：{len(symbols)} 个基因（已去重）")

            if not symbols:
                self.func.log("[ERROR] 没有解析到任何基因，请检查输入")
                self.func.alert_error("没有解析到任何基因，请先输入基因名或选择基因列表文件")
                return

            # 2) 可选 PPI 连线（联网失败一律跳过，不抛异常）
            params = self._collect_render_params()
            if hasattr(ui, 'circos_links_check') and ui.circos_links_check.isChecked():
                try:
                    min_score = float(ui.circos_links_score_input.value())
                except Exception:
                    min_score = 0.7
                self.func.log(f"[INFO] 正在通过 STRING 获取 PPI 连线（最低置信度 {min_score}）...")
                QApplication.processEvents()
                links = self.analysis.fetch_string_links(symbols, min_score=min_score)
                params["links"] = links
                if links:
                    self.func.log(f"[INFO] 取得 {len(links)} 条连线")
                else:
                    self.func.log("[WARN] 未取得连线（离线或查询失败），已跳过连线")
            else:
                params["links"] = None

            # 3) 基因定位查询
            self.func.log(f"[INFO] 正在查询基因坐标（assembly={params['assembly']}）...")
            QApplication.processEvents()
            result = self.analysis.lookup_genes(symbols, assembly=params["assembly"])
            result = result if isinstance(result, dict) else {}

            found = list(result.get('found') or [])
            missing = list(result.get('missing') or [])
            duplicated = result.get('duplicated') or {}

            self.func.log(f"[INFO] 命中：{len(found)} 个基因；未匹配：{len(missing)} 个（已跳过，不报错）")

            if not found:
                self.func.log("[ERROR] 没有任何基因匹配到坐标，无法绘图")
                self.func.alert_error("没有任何基因匹配到坐标，无法绘图。请检查基因名或参考基因组")
                self.func.fill_missing_table(self._missing_rows(missing, duplicated))
                return

            # 4) 绘图
            self.func.log(f"[INFO] 绘图参数：tier={params['tier']} Mb | "
                          f"ideogram={params['show_ideogram']} gc={params['show_gc']} "
                          f"heatmap={params['show_density_heatmap']} bars={params['show_density_bars']} "
                          f"loci={params['show_loci']} labels={params['show_gene_labels']} "
                          f"legend={params['show_legend']} title={params['show_title']} | "
                          f"max_labels={params['max_labels']} "
                          f"label_fontsize={params['label_fontsize']} "
                          f"label_layers={params['label_layers']} "
                          f"label_min_sep={params['label_min_sep']} | "
                          f"dpi={params['dpi']} figsize={params['figsize']} | "
                          f"formats={','.join(params['formats'])}")
            if params.get('_preview_png'):
                self.func.log("[INFO] 界面预览需要位图，本次额外生成一张 PNG 供预览（不计入导出格式）")

            self.func.log("[INFO] 正在绘图...")
            QApplication.processEvents()

            call_params = {k: v for k, v in params.items() if not k.startswith('_')}
            render_result = self.analysis.render(found, **call_params)
            render_result = render_result if isinstance(render_result, dict) else {}

            self.last_out_dir = render_result.get('out_dir') or None
            files = list(render_result.get('files') or [])
            self.func.log(f"[INFO] 输出目录：{self.last_out_dir}")
            for f in files:
                self.func.log(f"[INFO] 已生成：{f}")

            # 5) 预览 + 表格
            plot_path = render_result.get('plot_path')
            if plot_path and self.func.display_plot(plot_path):
                self._last_plot_path = plot_path
                self.func.log("[INFO] 圈图已显示在「圈图」页签")
            else:
                self.func.log("[WARN] 未能显示预览图")

            genes = list(render_result.get('genes') or [])
            if not genes:
                self.func.log("[WARN] 内核未返回逐基因定位表，改读 genes.tsv（若存在）")
                genes = self._read_genes_tsv(self.last_out_dir)
            self.func.fill_genes_table(genes)
            self.func.log(f"[INFO] 基因定位表：{len(genes)} 行")

            # 6) 未匹配基因（必须可见）
            missing_rows = self._missing_rows(missing, duplicated)
            self.func.fill_missing_table(missing_rows)
            if missing:
                self.func.log(f"[WARN] 跳过 {len(missing)} 个未匹配基因：{', '.join([str(m) for m in missing])}")
            if duplicated:
                for sym, chroms in duplicated.items():
                    self.func.log(f"[WARN] {sym} 落在多条染色体 {chroms}，按第一条为准")
            if not missing and not duplicated:
                self.func.log("[INFO] 未匹配基因：无")

            stats = render_result.get('stats') or {}
            if stats:
                self.func.log(f"[INFO] 统计：{stats}")

            self.func.alert_success("Circos 圈图生成完成")

        except Exception as e:
            self.func.log(f"[ERROR] 运行失败: {e}")
            import traceback
            self.func.log(f"[ERROR] 详细错误: {traceback.format_exc()}")
            self.func.alert_failure(f"运行失败: {e}")

    def _missing_rows(self, missing, duplicated=None):
        """把 missing/duplicated 整理成「未匹配基因」表要的行"""
        rows = []
        for m in missing or []:
            rows.append({'symbol': str(m), 'reason': '未匹配（不在基因坐标表中）'})
        for sym, chroms in (duplicated or {}).items():
            try:
                chrom_list = list(chroms)
            except TypeError:
                chrom_list = [chroms]
            if not chrom_list:
                continue
            rows.append({'symbol': str(sym),
                         'reason': f"多条染色体 {chrom_list}，取 {chrom_list[0]}（已绘图）"})
        return rows

    def _read_genes_tsv(self, out_dir):
        """内核没返回 genes 列表时，从输出目录的 genes.tsv 兜底读取（只做显示用）"""
        if not out_dir:
            return []
        path = os.path.join(out_dir, "genes.tsv")
        if not os.path.exists(path):
            return []
        rows = []
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                header = None
                for line in f:
                    parts = line.rstrip('\n').rstrip('\r').split('\t')
                    if header is None:
                        header = parts
                        continue
                    if not parts or not parts[0]:
                        continue
                    rec = dict(zip(header, parts))
                    rows.append({
                        'symbol': rec.get('symbol', parts[0]),
                        'chrom': rec.get('chrom', ''),
                        'start': rec.get('start', ''),
                        'end': rec.get('end', ''),
                        'length': rec.get('length_bp', rec.get('length', '')),
                        'cytoband': rec.get('cytoband', ''),
                        'gene_density': rec.get('gene_density', ''),
                        'gc': rec.get('gc_percent', rec.get('gc', '')),
                        'status': 'OK',
                    })
        except Exception:
            return []
        return rows

    # ------------------------------------------------------------------ 导出
    def export_circos_image(self):
        """导出图片：按目标扩展名重新出图（矢量格式必须是真矢量）"""
        if self.analysis is None:
            self.func.alert_error("Circos 内核尚未就绪，无法导出")
            return

        try:
            default_dir = self.last_out_dir or OUT_BASE
            default_name = os.path.join(default_dir, "circos_genes.png")
            save_path = self.func.get_save_file_path(
                "导出 Circos 圈图", default_name,
                "PNG 图片 (*.png);;SVG 矢量图 (*.svg);;PDF 文档 (*.pdf)")
            if not save_path:
                return

            ext = os.path.splitext(save_path)[1].lower().lstrip('.')
            if ext not in ('png', 'svg', 'pdf'):
                save_path = save_path + ".png"
                ext = "png"

            self.func.log(f"[INFO] 正在按 {ext.upper()} 重新出图 → {save_path}")
            QApplication.processEvents()

            produced = self.analysis.export_current(save_path)
            if produced and os.path.exists(produced):
                self.func.log(f"[INFO] 已导出：{produced}（{ext.upper()} 重新出图，非改后缀）")
                self.func.alert_success(f"导出成功：{produced}")
            else:
                self.func.log("[ERROR] 导出失败：没有可复用的绘图参数，请先点「▶ 运行」")
                self.func.alert_error("导出失败：请先运行一次生成圈图")
        except Exception as e:
            self.func.log(f"[ERROR] 导出失败: {e}")
            import traceback
            self.func.log(f"[ERROR] 详细错误: {traceback.format_exc()}")
            self.func.alert_failure(f"导出失败: {e}")

    # ------------------------------------------------------------ 其它按钮
    def open_output_dir(self):
        """打开最近一次输出目录"""
        out_dir = self.last_out_dir
        if not out_dir or not os.path.isdir(out_dir):
            self.func.log("[ERROR] 还没有输出目录，请先运行一次")
            self.func.alert_error("还没有输出目录，请先运行一次")
            return

        try:
            ok = False
            if hasattr(self.analysis, 'open_output_dir') and self.analysis is not None:
                ok = bool(self.analysis.open_output_dir(out_dir))
            if not ok:
                if hasattr(os, 'startfile'):
                    os.startfile(out_dir)         # noqa: S606 (Windows)
                    ok = True
                else:
                    self.func.log("[WARN] 当前系统不支持自动打开目录")
            if ok:
                self.func.log(f"[INFO] 已打开输出目录：{out_dir}")
        except Exception as e:
            self.func.log(f"[ERROR] 打开输出目录失败: {e}")
            self.func.alert_failure(f"打开输出目录失败: {e}")

    def clear_circos(self):
        """清空输入与结果（不清空输出目录记录）"""
        ui = self.circos_ui
        if hasattr(ui, 'circos_genes_text'):
            ui.circos_genes_text.blockSignals(True)
            ui.circos_genes_text.clear()
            ui.circos_genes_text.blockSignals(False)
        self.func.clear_gene_count()
        self.func.clear_tables()
        self.func.clear_plot()
        self._last_plot_path = None
        self.last_missing = []
        self.func.log("[INFO] 已清空输入与结果")

    # ------------------------------------------------------------------ 兜底
    def set_volume(self, value):
        """设置音量（与韦恩图页一致）"""
        mod_instance = global_mod_manager.get_current_mod()
        if hasattr(mod_instance, 'global_music_player'):
            mod_instance.global_music_player.set_volume(value / 100.0)

        if hasattr(self.parent, '_sync_all_volume_sliders_from_subinterface'):
            self.parent._sync_all_volume_sliders_from_subinterface(value)
