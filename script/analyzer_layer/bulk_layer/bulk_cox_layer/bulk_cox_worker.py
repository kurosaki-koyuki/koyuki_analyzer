# -*- coding: utf-8 -*-
"""
COX分析异步执行器 - 使用QTimer延迟执行
避免立即阻塞UI，同时保持rpy2在同一线程中运行
"""

from script.utils_layer.import_config import *


class BulkCoxWorker(QObject):
    finished = pyqtSignal(bool, object)
    progress = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._running = False
    
    def stop(self):
        self._running = False
    
    def _on_progress(self, message):
        """内部进度回调"""
        self.progress.emit(message)
    
    def run_cox_analysis(self, analysis, gene_names, total_gene_count, clinical_covariates, adjusted,
                         filter1_col, filter1_groups, filter2_col, filter2_groups):
        self._running = True
        
        self.progress.emit(f"开始COX分析，共 {total_gene_count} 个基因")
        
        print(f"[BulkCoxWorker] === COX分析开始 ===")
        print(f"[BulkCoxWorker] 基因数: {total_gene_count}")
        print(f"[BulkCoxWorker] 校正模式: {'多因素' if adjusted else '单因素'}")
        print(f"[BulkCoxWorker] 协变量: {clinical_covariates}")
        print(f"[BulkCoxWorker] R可用: {analysis.robjects is not None}")
        
        try:
            result_df = analysis.run_cox_analysis(
                gene_names=gene_names,
                clinical_covariates=clinical_covariates,
                adjusted=adjusted,
                filter1_col=filter1_col,
                filter1_groups=filter1_groups,
                filter2_col=filter2_col,
                filter2_groups=filter2_groups,
                progress_callback=self._on_progress
            )
            
            QApplication.processEvents()
            print("[BulkCoxWorker] COX分析执行完成")
            
            if result_df is not None and len(result_df) > 0:
                self.progress.emit(f"分析完成! 总基因: {len(result_df)}")
                self.finished.emit(True, result_df)
            else:
                self.progress.emit("分析完成，但无结果")
                self.finished.emit(True, None)
                
            print(f"[BulkCoxWorker] === COX分析完成 ===")
            
        except Exception as e:
            import traceback
            error_msg = f"COX分析失败: {str(e)}\n{traceback.format_exc()}"
            print(f"[BulkCoxWorker] === COX分析失败 ===\n{error_msg}")
            self.progress.emit(error_msg)
            self.finished.emit(False, None)
        finally:
            self._running = False