# -*- coding: utf-8 -*-
"""
单细胞StaVIA分析异步执行器 - 使用QTimer延迟执行
避免立即阻塞UI，运行过程中定期处理事件保持响应
"""

from script.utils_layer.import_config import *


class StaviaWorker(QObject):
    finished = pyqtSignal(bool, str, object)
    progress = pyqtSignal(str)
    plots_ready = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._running = False

    def stop(self):
        self._running = False

    @property
    def is_running(self):
        return self._running

    def run_analysis(self, analysis, params):
        self._running = True
        self.progress.emit("开始StaVIA轨迹分析...")

        try:
            QApplication.processEvents()

            self.progress.emit("正在准备数据并运行VIA分析...")
            QApplication.processEvents()

            results = analysis.run_via_analysis(
                ncomps=params['ncomps'],
                knn=params['knn'],
                resolution_parameter=params['resolution'],
                memory=params['memory'],
                use_rep=params['use_rep'],
                clusters=params['clusters'],
                basis=params['basis'],
                re_dim=params['re_dim'],
                filter_params=params['filter_params']
            )

            QApplication.processEvents()
            self.progress.emit(f"VIA分析完成！检测到 {results['num_clusters']} 个簇")
            self.progress.emit(f"终末簇数量: {results['num_terminal_clusters']}")
            QApplication.processEvents()

            self.progress.emit("正在生成可视化图片...")
            plots = analysis.generate_plots(
                clusters=params['clusters'],
                basis=params['basis']
            )

            QApplication.processEvents()

            for key, fig in plots.items():
                if fig is not None:
                    self.progress.emit(f"✓ {key} 图片已生成")
                else:
                    self.progress.emit(f"✗ {key} 图片生成失败")
                QApplication.processEvents()

            self.plots_ready.emit(plots)
            self.finished.emit(True, "分析完成", results)
            self._running = False

        except Exception as e:
            import traceback
            error_msg = f"分析失败: {str(e)}\n{traceback.format_exc()}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, None)
            self._running = False
