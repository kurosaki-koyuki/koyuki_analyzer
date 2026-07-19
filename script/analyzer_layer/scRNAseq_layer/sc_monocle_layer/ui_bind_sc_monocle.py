# -*- coding: utf-8 -*-
"""
scRNAseq Monocle分析界面功能绑定脚本 - 负责粘合内外，绑定信号，编排analysis与func的协作
"""

import os
from PyQt5.QtCore import QTimer, QUrl
from script.utils_layer.page_intersect import page_intersect
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.sc_monocle_analysis import ScMonocleAnalysis
from script.analyzer_layer.scRNAseq_layer.sc_monocle_layer.ui_func_sc_monocle import ScMonocleFunc


class ScMonocleBind:
    def __init__(self, main_window, sc_monocle_ui):
        self.parent = main_window
        self.sc_monocle_ui = sc_monocle_ui
        self.analysis = ScMonocleAnalysis()
        self.func = ScMonocleFunc(sc_monocle_ui, main_window)
        self.func._analysis = self.analysis
        self._metadata_values = {}
        self.bind_signals()

    def bind_signals(self):
        self.bind_navigation()
        self.bind_analysis_functions()

    def bind_navigation(self):
        if hasattr(self.sc_monocle_ui, 'btn_back_sc_monocle'):
            self.sc_monocle_ui.btn_back_sc_monocle.clicked.connect(self.handle_back)

    def bind_analysis_functions(self):
        if hasattr(self.sc_monocle_ui, 'btn_stage1'):
            self.sc_monocle_ui.btn_stage1.clicked.connect(self.run_stage1)
        
        if hasattr(self.sc_monocle_ui, 'btn_stage2'):
            self.sc_monocle_ui.btn_stage2.clicked.connect(self.run_stage2)
            
            if hasattr(self.sc_monocle_ui, 'btn_stage3'):
                self.sc_monocle_ui.btn_stage3.clicked.connect(self.run_stage3)
        
        if hasattr(self.sc_monocle_ui, 'btn_stage4'):
            self.sc_monocle_ui.btn_stage4.clicked.connect(self.run_stage4)
        
        if hasattr(self.sc_monocle_ui, 'btn_export_png'):
            self.sc_monocle_ui.btn_export_png.clicked.connect(self.export_png)
        
        if hasattr(self.sc_monocle_ui, 'btn_export_pdf'):
            self.sc_monocle_ui.btn_export_pdf.clicked.connect(self.export_pdf)
        
        if hasattr(self.sc_monocle_ui, 'combo_main_annot'):
            self.sc_monocle_ui.combo_main_annot.currentIndexChanged.connect(self.on_main_annot_changed)
        
        if hasattr(self.sc_monocle_ui, 'combo_filter1'):
            self.sc_monocle_ui.combo_filter1.currentIndexChanged.connect(self.on_filter1_changed)
        
        if hasattr(self.sc_monocle_ui, 'combo_filter2'):
            self.sc_monocle_ui.combo_filter2.currentIndexChanged.connect(self.on_filter2_changed)
        
        if hasattr(self.sc_monocle_ui, 'list_main_groups'):
            self.sc_monocle_ui.list_main_groups.itemSelectionChanged.connect(self.on_main_groups_changed)

    def handle_back(self):
        page_intersect.go_to_page_with_bind('scRNAseq_top_page')

    def sync_data_from_single_cell_main(self, single_cell_bind=None):
        try:
            if single_cell_bind is None:
                single_cell_bind = getattr(self.parent, 'scRNAseq_top_bind', None)

            if single_cell_bind is None:
                return

            if hasattr(single_cell_bind, 'analysis'):
                self.analysis.set_seurat_path(single_cell_bind.analysis.seurat_path)
                self.analysis.set_dataset_name(single_cell_bind.analysis.dataset_name)
                self.analysis.set_dataset_output_dir(single_cell_bind.analysis.dataset_output_dir)

                if single_cell_bind.analysis.seurat_path is not None:
                    self.func.log(f"已从scRNAseq主页同步Seurat对象: {single_cell_bind.analysis.dataset_name}")
                    
                    self.load_metadata_columns_from_main(single_cell_bind.analysis)

        except Exception as e:
            print(f"Monocle同步数据时出错: {str(e)}")

    def load_metadata_columns_from_main(self, main_analysis):
        try:
            metadata_cols = []
            if hasattr(main_analysis, 'seurat_metadata_columns') and main_analysis.seurat_metadata_columns:
                metadata_cols = main_analysis.seurat_metadata_columns
            
            if hasattr(self.sc_monocle_ui, 'combo_annotation'):
                self.sc_monocle_ui.combo_annotation.clear()
                self.sc_monocle_ui.combo_annotation.addItem("选择注释列")
                for col in metadata_cols:
                    self.sc_monocle_ui.combo_annotation.addItem(col)
            
            if hasattr(self.sc_monocle_ui, 'combo_main_annot'):
                self.sc_monocle_ui.combo_main_annot.clear()
                self.sc_monocle_ui.combo_main_annot.addItem("选择注释列")
                for col in metadata_cols:
                    self.sc_monocle_ui.combo_main_annot.addItem(col)
            
            if hasattr(self.sc_monocle_ui, 'combo_filter1'):
                self.sc_monocle_ui.combo_filter1.clear()
                self.sc_monocle_ui.combo_filter1.addItem("不筛选")
                for col in metadata_cols:
                    self.sc_monocle_ui.combo_filter1.addItem(col)
            
            if hasattr(self.sc_monocle_ui, 'combo_filter2'):
                self.sc_monocle_ui.combo_filter2.clear()
                self.sc_monocle_ui.combo_filter2.addItem("不筛选")
                for col in metadata_cols:
                    self.sc_monocle_ui.combo_filter2.addItem(col)
            
            if hasattr(self.sc_monocle_ui, 'combo_plot_annot'):
                self.sc_monocle_ui.combo_plot_annot.clear()
                self.sc_monocle_ui.combo_plot_annot.addItem("选择注释列")
                for col in metadata_cols:
                    self.sc_monocle_ui.combo_plot_annot.addItem(col)
            
            if hasattr(self.sc_monocle_ui, 'combo_alignment'):
                self.sc_monocle_ui.combo_alignment.clear()
                self.sc_monocle_ui.combo_alignment.addItem("不校正")
                for col in metadata_cols:
                    self.sc_monocle_ui.combo_alignment.addItem(col)
            
            if hasattr(self.sc_monocle_ui, 'combo_traj_annot'):
                self.sc_monocle_ui.combo_traj_annot.clear()
                self.sc_monocle_ui.combo_traj_annot.addItem("选择注释列")
                for col in metadata_cols:
                    self.sc_monocle_ui.combo_traj_annot.addItem(col)
            
            self._metadata_values = {}
            if hasattr(main_analysis, 'seurat_metadata_values') and main_analysis.seurat_metadata_values:
                self._metadata_values = main_analysis.seurat_metadata_values
            
            self.func.log(f"已加载 {len(metadata_cols)} 个注释列")
        except Exception as e:
            print(f"加载注释列失败: {str(e)}")

    def run_stage1(self):
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return
        
        annotation_col = ""
        if hasattr(self.sc_monocle_ui, 'combo_annotation'):
            annotation_col = self.sc_monocle_ui.combo_annotation.currentText()
        
        if annotation_col == "选择注释列" or not annotation_col:
            self.func.alert_error("请先选择一个注释列")
            return

        self.func.log(f"正在按注释出图: {annotation_col}...")
        
        success, result = self.analysis.generate_annotation_plot(annotation_col)

        if not success:
            self.func.alert_failure(f"出图失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"出图完成: {result}")

        if os.path.exists(result):
            self.func.display_stage1_images([result])
            self.func.log(f"已显示注释图")
        else:
            self.func.log("未找到生成的图片")

        if self.sc_monocle_ui.monocle_plot_tabs.currentIndex() != 0:
            self.sc_monocle_ui.monocle_plot_tabs.setCurrentIndex(0)

        self.func.alert_success(f"注释图 {annotation_col} 绘制完成")

    def export_png(self):
        stage1_output = self.analysis._get_monocle_output_dir()
        self.func.export_stage1_png(stage1_output)

    def export_pdf(self):
        stage1_output = self.analysis._get_monocle_output_dir()
        self.func.export_stage1_pdf(stage1_output)

    def on_main_annot_changed(self):
        if not hasattr(self.sc_monocle_ui, 'list_main_groups'):
            return
        
        main_annot = self.sc_monocle_ui.combo_main_annot.currentText()
        self.sc_monocle_ui.list_main_groups.clear()
        
        if main_annot != "选择注释列" and main_annot in self._metadata_values:
            for value in self._metadata_values[main_annot]:
                self.sc_monocle_ui.list_main_groups.addItem(value)
        
        if hasattr(self.sc_monocle_ui, 'combo_plot_annot'):
            self.sc_monocle_ui.combo_plot_annot.setCurrentText(main_annot)

    def on_filter1_changed(self):
        if not hasattr(self.sc_monocle_ui, 'list_filter1'):
            return
        
        filter_col = self.sc_monocle_ui.combo_filter1.currentText()
        self.sc_monocle_ui.list_filter1.clear()
        
        if filter_col != "不筛选" and filter_col in self._metadata_values:
            for value in self._metadata_values[filter_col]:
                self.sc_monocle_ui.list_filter1.addItem(value)

    def on_filter2_changed(self):
        if not hasattr(self.sc_monocle_ui, 'list_filter2'):
            return
        
        filter_col = self.sc_monocle_ui.combo_filter2.currentText()
        self.sc_monocle_ui.list_filter2.clear()
        
        if filter_col != "不筛选" and filter_col in self._metadata_values:
            for value in self._metadata_values[filter_col]:
                self.sc_monocle_ui.list_filter2.addItem(value)

    def on_main_groups_changed(self):
        if not hasattr(self.sc_monocle_ui, 'list_main_groups') or not hasattr(self.sc_monocle_ui, 'check_re_reduce'):
            return
        
        selected_items = self.sc_monocle_ui.list_main_groups.selectedItems()
        selected_count = len(selected_items)
        
        main_annot = self.sc_monocle_ui.combo_main_annot.currentText()
        total_count = 0
        if main_annot in self._metadata_values:
            total_count = len(self._metadata_values[main_annot])
        
        if selected_count > 0 and selected_count < total_count:
            self.sc_monocle_ui.check_re_reduce.setChecked(True)
        elif selected_count == total_count or selected_count == 0:
            self.sc_monocle_ui.check_re_reduce.setChecked(False)

    def run_stage2(self):
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return
        
        main_annot = self.sc_monocle_ui.combo_main_annot.currentText()
        if main_annot == "选择注释列":
            self.func.alert_error("请选择主注释列")
            return
        
        main_groups = []
        if hasattr(self.sc_monocle_ui, 'list_main_groups'):
            for item in self.sc_monocle_ui.list_main_groups.selectedItems():
                main_groups.append(item.text())
        
        filter1_col = self.sc_monocle_ui.combo_filter1.currentText()
        filter1_groups = []
        if filter1_col != "不筛选" and hasattr(self.sc_monocle_ui, 'list_filter1'):
            for item in self.sc_monocle_ui.list_filter1.selectedItems():
                filter1_groups.append(item.text())
        
        filter2_col = self.sc_monocle_ui.combo_filter2.currentText()
        filter2_groups = []
        if filter2_col != "不筛选" and hasattr(self.sc_monocle_ui, 'list_filter2'):
            for item in self.sc_monocle_ui.list_filter2.selectedItems():
                filter2_groups.append(item.text())
        
        re_reduce = False
        if hasattr(self.sc_monocle_ui, 'check_re_reduce'):
            re_reduce = self.sc_monocle_ui.check_re_reduce.isChecked()
        
        dim_val = 2
        if hasattr(self.sc_monocle_ui, 'input_dim_val'):
            try:
                dim_val = int(self.sc_monocle_ui.input_dim_val.text())
            except:
                dim_val = 2
        
        plot_annot = self.sc_monocle_ui.combo_plot_annot.currentText()
        if plot_annot == "选择注释列":
            plot_annot = main_annot
        
        self.func.log(f"正在执行细胞筛选...")
        self.func.log(f"主注释: {main_annot}, 分组: {', '.join(main_groups) if main_groups else '全选'}")
        if filter1_groups:
            self.func.log(f"筛选条件1: {filter1_col}={', '.join(filter1_groups)}")
        if filter2_groups:
            self.func.log(f"筛选条件2: {filter2_col}={', '.join(filter2_groups)}")
        self.func.log(f"重新降维: {re_reduce}, dim: {dim_val}")
        
        success, result = self.analysis.run_stage2_filter(
            main_annot, main_groups,
            filter1_col if filter1_col != "不筛选" else "", filter1_groups,
            filter2_col if filter2_col != "不筛选" else "", filter2_groups,
            re_reduce, dim_val, plot_annot
        )
        
        if not success:
            self.func.alert_failure(f"筛选失败: {result}")
            self.func.log(f"❌ {result}")
            return
        
        self.func.log(f"筛选完成")
        
        lines = result.strip().split('\n')
        png_path = lines[-1].strip() if lines else ""
        
        if os.path.exists(png_path):
            self.func.display_stage2_images([png_path])
            self.func.log(f"已显示筛选UMAP图")
        else:
            self.func.log(f"未找到生成的图片: {png_path}")
        
        if self.sc_monocle_ui.monocle_plot_tabs.currentIndex() != 1:
            self.sc_monocle_ui.monocle_plot_tabs.setCurrentIndex(1)
        
        self.func.alert_success("阶段二分析完成")

    def run_stage3(self):
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return
        
        num_dim = 50
        if hasattr(self.sc_monocle_ui, 'input_num_dim'):
            try:
                num_dim = int(self.sc_monocle_ui.input_num_dim.text())
            except:
                num_dim = 50
        
        alignment_col = ""
        if hasattr(self.sc_monocle_ui, 'combo_alignment'):
            alignment_col = self.sc_monocle_ui.combo_alignment.currentText()
            if alignment_col == "不校正":
                alignment_col = ""
        
        plot_annot = ""
        if hasattr(self.sc_monocle_ui, 'combo_traj_annot'):
            plot_annot = self.sc_monocle_ui.combo_traj_annot.currentText()
            if plot_annot == "选择注释列":
                plot_annot = ""
        
        coord_mode = "UMAP"
        if hasattr(self.sc_monocle_ui, 'combo_coord_mode'):
            coord_mode = self.sc_monocle_ui.combo_coord_mode.currentText()
        
        self.func.log(f"正在创建CDS对象...")
        self.func.log(f"num_dim: {num_dim}, 批次校正: {alignment_col if alignment_col else '不校正'}")
        self.func.log(f"轨迹图注释: {plot_annot if plot_annot else '自动选择'}, 坐标模式: {coord_mode}")
        
        success, result = self.analysis.run_stage3_cds(num_dim, alignment_col, plot_annot, coord_mode)
        
        if not success:
            self.func.alert_failure(f"CDS创建失败: {result}")
            self.func.log(f"❌ {result}")
            return
        
        self.func.log(f"CDS创建完成")
        
        lines = result.strip().split('\n')
        traj_path = ""
        partition_path = ""
        
        for line in lines:
            if '_trajectory.png' in line:
                traj_path = line.strip()
            elif '_partition.png' in line:
                partition_path = line.strip()
        
        if traj_path and os.path.exists(traj_path):
            self.func.display_stage3_traj_image(traj_path)
            self.func.log(f"已显示轨迹图")
        else:
            self.func.log(f"未找到轨迹图")
        
        if partition_path and os.path.exists(partition_path):
            self.func.display_stage3_partition_image(partition_path)
            self.func.log(f"已显示分区图")
        else:
            self.func.log(f"未找到分区图")
        
        self.sc_monocle_ui.monocle_plot_tabs.setCurrentIndex(2)
        
        self.func.alert_success("阶段三分析完成")

    def run_stage4(self):
        if not self.analysis.seurat_path:
            self.func.alert_error("请先从主页加载RDS文件")
            return

        node_mode = "auto"
        if hasattr(self.sc_monocle_ui, 'combo_node_mode'):
            node_mode = self.sc_monocle_ui.combo_node_mode.currentText()

        self.func.log(f"正在计算伪时间...")
        self.func.log(f"节点选择模式: {node_mode}")

        if node_mode == "manual":
            self._run_stage4_manual()
        else:
            self._run_stage4_auto()

    def _run_stage4_auto(self):
        """自动模式：阻塞执行，完成后显示伪时间图"""
        success, result = self.analysis.run_stage4_pseudotime("auto", "")

        if not success:
            self.func.alert_failure(f"伪时间计算失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"伪时间计算完成")
        self._display_pseudotime_result(result)

    def _run_stage4_manual(self):
        """手动模式：启动R脚本进程，QTimer轮询获取Shiny URL和完成状态"""
        web_view = getattr(self.sc_monocle_ui, 'stage4_web_view', None)
        if web_view is None:
            self.func.alert_error("网页标签页未就绪（QtWebEngineWidgets未安装），无法使用手动模式")
            return

        # 切换到网页标签页（索引4）
        self.sc_monocle_ui.monocle_plot_tabs.setCurrentIndex(4)
        self.func.log(f"已切换到「节点选择(Shiny)」标签页")

        # 阶段四伊始：系统自检8787端口占用，自动清理残留进程
        self.func.log(f"正在系统自检8787端口占用情况...")
        killed_pids, clean_msg = self.analysis.kill_port_8787_occupants()
        self.func.log(clean_msg)

        # 启动R脚本进程（非阻塞）
        success, result = self.analysis.run_stage4_pseudotime("manual", "")
        if not success:
            self.func.alert_failure(f"Shiny启动失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"正在启动Shiny服务器...")

        import time
        self._stage4_shiny_loaded = False
        self._stage4_start_time = time.time()
        # 启动QTimer轮询Shiny URL和完成状态
        self._stage4_poll_timer = QTimer(self.sc_monocle_ui.sc_monocle_page)
        self._stage4_poll_timer.timeout.connect(self._poll_stage4_manual)
        self._stage4_poll_timer.start(500)  # 每500ms检查一次

    def _poll_stage4_manual(self):
        """轮询manual模式的Shiny URL和完成状态（UI线程）"""
        # 如果还没加载Shiny URL，检查是否有URL
        if not getattr(self, '_stage4_shiny_loaded', False):
            # 超时检查（120秒）
            import time
            elapsed = time.time() - getattr(self, '_stage4_start_time', time.time())
            if elapsed > 120:
                self._stage4_poll_timer.stop()
                self.func.alert_failure("Shiny启动超时（120秒），请检查R环境是否正常")
                self.func.log(f"❌ Shiny启动超时")
                return

            # 检查进程是否已经退出
            proc = getattr(self.analysis, '_stage4_process', None)
            if proc is not None and proc.poll() is not None:
                # 进程已退出，读取剩余输出
                self._stage4_poll_timer.stop()
                finished, result = self.analysis.poll_stage4()
                self.func.alert_failure(f"R脚本已退出: {result}")
                self.func.log(f"❌ R脚本已退出: {result}")
                return

            status, data = self.analysis.get_stage4_shiny_url()

            if status == "waiting":
                if data is not None:
                    self.func.log(f"[R] {data}")
                return

            if status == "eof":
                self._stage4_poll_timer.stop()
                self.func.alert_failure("R脚本意外退出，未获取到Shiny URL")
                self.func.log(f"❌ R脚本意外退出")
                return

            if status == "error":
                self._stage4_poll_timer.stop()
                self.func.alert_failure(f"Shiny启动失败: {data}")
                self.func.log(f"❌ {data}")
                return

            # status == "url"
            self._stage4_shiny_loaded = True
            self._stage4_shiny_url = data
            self.func.log(f"Shiny已启动: {data}")
            self.func.log(f"正在标签页中加载Shiny网页...")

            # 在QWebEngineView中加载Shiny URL
            try:
                # 先显示加载中提示
                loading_html = f"""
                <html>
                <head><meta charset="utf-8"><style>
                    body {{
                        background: rgba(26, 26, 46, 1);
                        color: #87CEEB;
                        font-family: Arial, 'Microsoft YaHei', sans-serif;
                        margin: 0;
                        padding: 40px;
                        text-align: center;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 30px;
                        background: rgba(255,255,255,0.05);
                        border: 1px solid #E91E63;
                        border-radius: 8px;
                    }}
                    h2 {{ color: #E91E63; margin-bottom: 20px; }}
                    p {{ line-height: 1.8; font-size: 14px; text-align: left; }}
                    .url {{
                        margin-top: 15px;
                        padding: 10px;
                        background: rgba(255,255,255,0.08);
                        border-left: 3px solid #E91E63;
                        font-family: monospace;
                        word-break: break-all;
                        text-align: left;
                    }}
                </style></head>
                <body>
                    <div class="container">
                        <h2>正在加载Shiny网页...</h2>
                        <p>系统正在加载Shiny网页到标签页中，请稍候。</p>
                        <p>如果网页显示异常（如点图区域空白），请手动复制下方URL到系统浏览器中打开：</p>
                        <div class="url">{data}</div>
                        <p><b>操作步骤：</b></p>
                        <p>1. 查看UMAP轨迹图</p>
                        <p>2. 框选或点击要作为根节点的点（红色为已选中）</p>
                        <p>3. 点击网页中的「Done」按钮完成选择</p>
                        <p>4. 选择完成后，系统会自动继续计算伪时间</p>
                    </div>
                </body>
                </html>
                """
                self.sc_monocle_ui.stage4_web_view.setHtml(loading_html)

                # 延迟2秒后加载Shiny URL，确保服务器完全就绪
                from PyQt5.QtCore import QTimer as _QTimer
                _QTimer.singleShot(2000, lambda: self._load_shiny_in_webview(data))
            except Exception as e:
                self.func.alert_failure(f"加载Shiny网页失败: {e}，请手动访问: {data}")
                self.func.log(f"❌ 加载Shiny网页失败: {e}")
            return

        # Shiny已加载，检查R脚本是否完成
        finished, result = self.analysis.poll_stage4()
        if not finished:
            return

        # 停止轮询
        self._stage4_poll_timer.stop()

        if result.startswith("ERROR"):
            self.func.alert_failure(f"伪时间计算失败: {result}")
            self.func.log(f"❌ {result}")
            return

        self.func.log(f"伪时间计算完成")
        self._display_pseudotime_result(result)

    def _load_shiny_in_webview(self, url):
        """在QWebEngineView中加载Shiny URL"""
        try:
            from PyQt5.QtCore import QUrl
            self.sc_monocle_ui.stage4_web_view.load(QUrl(url))
            self.func.log(f"Shiny网页已加载到标签页")
            self.func.log(f"请在网页中选择根节点后点击「Done」按钮")
        except Exception as e:
            self.func.alert_failure(f"加载Shiny网页失败: {e}，请手动访问: {url}")
            self.func.log(f"❌ 加载Shiny网页失败: {e}")

    def _display_pseudotime_result(self, result):
        """显示伪时间图结果（UI线程）"""
        lines = result.strip().split('\n')
        pseudotime_path = ""

        for line in lines:
            if '_pseudotime.png' in line:
                pseudotime_path = line.strip()

        # 如果找到的行包含"已保存"等描述文字，尝试提取实际路径
        if pseudotime_path and not os.path.exists(pseudotime_path):
            # 尝试从行中提取路径（可能是"Pseudotime图已保存: <path>"格式）
            import re
            path_match = re.search(r'([A-Za-z]:\\[^\s]+_pseudotime\.png|/[^\s]+/_pseudotime\.png|[A-Za-z]:/[^\s]+_pseudotime\.png)', pseudotime_path)
            if path_match:
                pseudotime_path = path_match.group(1)

        if pseudotime_path and os.path.exists(pseudotime_path):
            self.func.display_stage4_pseudotime_image(pseudotime_path)
            self.func.log(f"已显示伪时间图")
        else:
            self.func.log(f"未找到伪时间图")

        # 伪时间图标签页索引为5（网页标签页插在4）
        self.sc_monocle_ui.monocle_plot_tabs.setCurrentIndex(5)

        self.func.alert_success("阶段四分析完成")
