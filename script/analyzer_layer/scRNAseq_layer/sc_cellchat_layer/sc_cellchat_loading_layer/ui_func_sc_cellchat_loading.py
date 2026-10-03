# -*- coding: utf-8 -*-
"""
CellChat数据加载类前端功能层
"""

import os
import glob
import threading
from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong
from script.analyzer_layer.scRNAseq_layer.sc_cellchat_layer.sc_cellchat_loading_layer.sc_cellchat_loading_analysis import ScCellChatLoadingAnalysis
from PyQt5.QtCore import QObject, pyqtSignal


class VisualizeSignals(QObject):
    """用于线程间通信的信号类"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)


class ScCellChatLoadingFunc:
    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget if parent_widget else ui_instance.sc_cellchat_loading_page
        self._scan_path = None
        self._rds_files = []
        self.analysis = ScCellChatLoadingAnalysis(ui_instance)
        
        # 创建信号对象
        self._signals = VisualizeSignals()
        self._signals.finished.connect(self._on_visualize_complete)
        self._signals.error.connect(self._on_visualize_error)
    
    def log(self, message):
        """记录日志"""
        if hasattr(self.ui, 'data_info_text'):
            current_text = self.ui.data_info_text.toPlainText()
            new_text = current_text + "\n" + message if current_text else message
            self.ui.data_info_text.setPlainText(new_text)
            self.ui.data_info_text.verticalScrollBar().setValue(
                self.ui.data_info_text.verticalScrollBar().maximum()
            )
    
    def scan_rds_files(self):
        """扫描RDS文件"""
        # 获取扫描路径
        scan_path = getattr(self.ui, 'input_scan_path', None)
        if scan_path:
            path_text = scan_path.text()
        else:
            path_text = r"appdata\analyze_data\cellchat_rds_data"
        
        # 转换为完整路径
        if not os.path.isabs(path_text):
            # 尝试在多个位置查找
            possible_paths = [
                os.path.join(os.getcwd(), path_text),
                os.path.join(os.path.expanduser("~"), path_text),
                path_text
            ]
            
            full_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    full_path = p
                    break
            
            if full_path is None:
                full_path = path_text
        else:
            full_path = path_text
        
        self._scan_path = full_path
        
        if not os.path.exists(full_path):
            self.log(f"扫描路径不存在: {full_path}")
            self.alert_error(f"扫描路径不存在: {full_path}")
            return []
        
        # 扫描RDS文件
        self._rds_files = glob.glob(os.path.join(full_path, "*.rds"))
        self._rds_files = [f for f in self._rds_files if "cellchat" in os.path.basename(f).lower()]
        
        # 显示到列表
        if hasattr(self.ui, 'list_rds_files'):
            self.ui.list_rds_files.clear()
            for f in self._rds_files:
                item = QListWidgetItem(os.path.basename(f))
                item.setData(Qt.UserRole, f)
                self.ui.list_rds_files.addItem(item)
        
        self.log(f"找到 {len(self._rds_files)} 个CellChat RDS文件")
        return self._rds_files
    
    def load_rds_file(self, rds_path):
        """加载RDS文件并重新出图"""
        self.log(f"加载RDS文件: {os.path.basename(rds_path)}")
        self.log("正在运行R脚本重新出图，请稍候...")
        
        # 禁用加载按钮防止重复点击
        if hasattr(self.ui, 'btn_load'):
            self.ui.btn_load.setEnabled(False)
            self.ui.btn_load.setText("正在出图...")
        
        # 使用线程运行R脚本
        thread = threading.Thread(target=self._run_visualize, args=(rds_path,))
        thread.daemon = True
        thread.start()
        
        return True
    
    def _run_visualize(self, rds_path):
        """运行R脚本重新出图（在线程中执行）"""
        try:
            # 获取输出目录（使用RDS文件所在目录）
            output_dir = os.path.dirname(rds_path)
            
            # 调用Analysis层运行R脚本
            result = self.analysis.visualize_from_rds(rds_path, output_dir)
            
            # 通过信号在主线程中更新UI
            self._signals.finished.emit(result)
            
        except Exception as e:
            self.log(f"出图失败: {e}")
            import traceback
            traceback.print_exc()
            self._signals.error.emit(str(e))
    
    def _on_visualize_complete(self, result):
        """出图完成回调（在主线程中执行）"""
        # 恢复加载按钮
        if hasattr(self.ui, 'btn_load'):
            self.ui.btn_load.setEnabled(True)
            self.ui.btn_load.setText("加载选中RDS")
        
        if result.get('success'):
            self.log("出图完成！")
            self._display_generated_files(result)
            self.alert_success("CellChat重新出图完成")
        else:
            error_msg = result.get('error', '未知错误')
            self.log(f"出图失败: {error_msg}")
            self.alert_failure(f"出图失败: {error_msg}")
    
    def _on_visualize_error(self, error_msg):
        """出图错误回调"""
        if hasattr(self.ui, 'btn_load'):
            self.ui.btn_load.setEnabled(True)
            self.ui.btn_load.setText("加载选中RDS")
        
        self.log(f"出图失败: {error_msg}")
        self.alert_failure(f"出图失败: {error_msg}")
    
    def _display_generated_files(self, result):
        """显示生成的图片和表格"""
        files = result.get('files', {})
        
        # 显示通讯数量图
        count_img = files.get('count')
        if count_img and os.path.exists(count_img) and hasattr(self.ui, 'loading_count_image_label'):
            pixmap = QPixmap(count_img)
            if not pixmap.isNull():
                # 使用ZoomableImageLabel的set_pixmap方法
                self.ui.loading_count_image_label.set_pixmap(pixmap)
                self.log(f"通讯数量图: {count_img}")
        
        # 显示通讯强度图
        weight_img = files.get('weight')
        if weight_img and os.path.exists(weight_img) and hasattr(self.ui, 'loading_weight_image_label'):
            pixmap = QPixmap(weight_img)
            if not pixmap.isNull():
                # 使用ZoomableImageLabel的set_pixmap方法
                self.ui.loading_weight_image_label.set_pixmap(pixmap)
                self.log(f"通讯强度图: {weight_img}")
        
        # 显示通路信息表
        info_csv = files.get('info')
        if info_csv and os.path.exists(info_csv) and hasattr(self.ui, 'table_loading_info'):
            try:
                import pandas as pd
                info_data = pd.read_csv(info_csv)
                self.display_pathway_info_table(info_data)
                self.log(f"通路信息表: {info_csv} ({len(info_data)} 条记录)")
            except Exception as e:
                self.log(f"读取通路信息表失败: {e}")
    
    def display_pathway_info_table(self, info_data):
        """显示通路信息表格"""
        if hasattr(self.ui, 'table_loading_info'):
            table = self.ui.table_loading_info
            if info_data is not None and len(info_data) > 0:
                table.setRowCount(0)
                table.setColumnCount(len(info_data.columns))
                table.setHorizontalHeaderLabels(info_data.columns.tolist())
                
                for row_idx in range(len(info_data)):
                    table.insertRow(row_idx)
                    for col_idx in range(len(info_data.columns)):
                        value = str(info_data.iloc[row_idx, col_idx])
                        item = QTableWidgetItem(value)
                        item.setTextAlignment(Qt.AlignCenter)
                        table.setItem(row_idx, col_idx, item)
                
                table.resizeColumnsToContents()
            else:
                table.setRowCount(0)
                table.setColumnCount(1)
                table.setHorizontalHeaderLabels(["提示"])
                table.insertRow(0)
                table.setItem(0, 0, QTableWidgetItem("暂无通路信息"))
    
    def get_save_file_path(self, title, default_name, filter_text):
        """弹出保存文件对话框"""
        if self.parent_widget:
            save_path, _ = QFileDialog.getSaveFileName(
                self.parent_widget, title, default_name, filter_text)
            return save_path
        return ""
    
    def alert_success(self, message):
        if self.parent_widget:
            happy(self.parent_widget, str(message))
    
    def alert_failure(self, message):
        if self.parent_widget:
            wrong(self.parent_widget, str(message))
    
    def alert_error(self, message):
        if self.parent_widget:
            attention(self.parent_widget, str(message))
