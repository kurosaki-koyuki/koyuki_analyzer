# -*- coding: utf-8 -*-
"""
scRNAseq hdWGCNA分析异步执行器 - 使用QTimer延迟执行
避免立即阻塞UI，同时保持rpy2在同一线程中运行
"""

from script.utils_layer.import_config import *


class HdWgcnaWorker(QObject):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._running = False
    
    def stop(self):
        self._running = False
    
    def run_stage3(self, analysis, network_type, manual_power):
        self._running = True
        self.progress.emit("开始运行阶段三：软阈值选择")
        
        print("[HdWgcnaWorker] === 阶段三开始 ===")
        print(f"[HdWgcnaWorker] network_type={network_type}, manual_power={manual_power}")
        print(f"[HdWgcnaWorker] R可用: {analysis.robjects is not None}")
        print(f"[HdWgcnaWorker] stage2_completed: {analysis._stage2_completed}")
        
        try:
            from rpy2.robjects import StrVector, IntVector
            
            output_dir = analysis.dataset_output_dir if analysis.dataset_output_dir else analysis._temp_dir
            print(f"[HdWgcnaWorker] output_dir={output_dir}")
            
            analysis.robjects.globalenv['output_dir'] = StrVector([output_dir])
            analysis.robjects.globalenv['network_type'] = StrVector([network_type])
            analysis.robjects.globalenv['plot_width'] = IntVector([1200])
            analysis.robjects.globalenv['plot_height'] = IntVector([800])
            
            if manual_power is not None:
                analysis.robjects.globalenv['manual_power'] = IntVector([manual_power])
                print(f"[HdWgcnaWorker] 设置手动软阈值: {manual_power}")
            
            r_code = analysis._read_stage_code("STAGE3")
            print(f"[HdWgcnaWorker] R代码长度: {len(r_code)}")
            
            print("[HdWgcnaWorker] 执行R代码...")
            QApplication.processEvents()
            
            result = analysis.robjects.r(r_code)
            
            QApplication.processEvents()
            print("[HdWgcnaWorker] R代码执行完成")
            
            analysis._stage3_completed = True
            
            power_estimate = None
            try:
                power_estimate = int(analysis.robjects.r('sc_hdwgcna_power_estimate')[0])
                print(f"[HdWgcnaWorker] 推荐软阈值: {power_estimate}")
            except Exception as e:
                print(f"[HdWgcnaWorker] 获取推荐软阈值失败: {e}")
            
            QApplication.processEvents()
            
            self.progress.emit(f"阶段三完成，推荐软阈值: {power_estimate}")
            self.finished.emit(True, 'stage3')
            print("[HdWgcnaWorker] === 阶段三完成 ===")
            
        except Exception as e:
            import traceback
            error_msg = f"阶段三失败: {str(e)}\n{traceback.format_exc()}"
            print(f"[HdWgcnaWorker] === 阶段三失败 ===\n{error_msg}")
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg)
        finally:
            self._running = False
    
    def run_stage4(self, analysis, power, min_module_size, merge_threshold):
        self._running = True
        self.progress.emit("开始运行阶段四：网络构建")
        
        print("[HdWgcnaWorker] === 阶段四开始 ===")
        print(f"[HdWgcnaWorker] power={power}, min_module_size={min_module_size}, merge_threshold={merge_threshold}")
        print(f"[HdWgcnaWorker] R可用: {analysis.robjects is not None}")
        print(f"[HdWgcnaWorker] stage3_completed: {analysis._stage3_completed}")
        
        try:
            from rpy2.robjects import StrVector, IntVector
            
            output_dir = analysis.dataset_output_dir if analysis.dataset_output_dir else analysis._temp_dir
            print(f"[HdWgcnaWorker] output_dir={output_dir}")
            
            analysis.robjects.globalenv['output_dir'] = StrVector([output_dir])
            analysis.robjects.globalenv['plot_width'] = IntVector([1200])
            analysis.robjects.globalenv['plot_height'] = IntVector([800])
            
            if power is not None:
                analysis.robjects.globalenv['soft_power'] = IntVector([power])
                print(f"[HdWgcnaWorker] 设置软阈值: {power}")
            
            analysis.robjects.globalenv['min_module_size'] = IntVector([min_module_size])
            analysis.robjects.globalenv['merge_threshold'] = analysis.robjects.r.c(merge_threshold)
            print(f"[HdWgcnaWorker] 设置min_module_size={min_module_size}, merge_threshold={merge_threshold}")
            
            r_code = analysis._read_stage_code("STAGE4")
            print(f"[HdWgcnaWorker] R代码长度: {len(r_code)}")
            
            print("[HdWgcnaWorker] 执行R代码...")
            QApplication.processEvents()
            
            result = analysis.robjects.r(r_code)
            
            QApplication.processEvents()
            print("[HdWgcnaWorker] R代码执行完成")
            
            analysis._stage4_completed = True
            
            QApplication.processEvents()
            
            self.progress.emit("阶段四完成：网络构建成功")
            self.finished.emit(True, 'stage4')
            print("[HdWgcnaWorker] === 阶段四完成 ===")
            
        except Exception as e:
            import traceback
            error_msg = f"阶段四失败: {str(e)}\n{traceback.format_exc()}"
            print(f"[HdWgcnaWorker] === 阶段四失败 ===\n{error_msg}")
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg)
        finally:
            self._running = False