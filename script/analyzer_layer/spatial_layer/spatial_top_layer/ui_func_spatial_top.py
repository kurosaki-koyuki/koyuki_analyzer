# -*- coding: utf-8 -*-
"""
空转分析顶层导航界面前端功能脚本 - 只负责前端显示、控件内容更新、图片渲染等
不绑定信号，不写业务算法，不处理导出逻辑
"""

from script.utils_layer.import_config import *
from script.mods_layer.emoji_function_for_mods import happy, attention, wrong


class SpatialTopFunc:
    """空转分析顶层导航界面前端功能类 - 纯前端显示操作"""

    def __init__(self, ui_instance, parent_widget=None):
        self.ui = ui_instance
        self.parent_widget = parent_widget

    def update_styles(self):
        """更新界面样式"""
        if hasattr(self.ui, 'update_styles'):
            self.ui.update_styles()

    def update_background(self):
        """更新背景图"""
        if hasattr(self.ui, 'update_background'):
            self.ui.update_background()

    # ------------------------------------------------------------------
    # M1 新增（契约 §6）
    # ------------------------------------------------------------------
    def log(self, message):
        """在状态文本框中记录日志（控件不存在时静默返回）

        照 ui_func_bulk_top.py:28-31：用 append，保持已有内容不丢。
        """
        try:
            if not hasattr(self.ui, 'spatial_status_text') or not self.ui.spatial_status_text:
                return
            self.ui.spatial_status_text.append(str(message))
        except Exception:
            # 纯显示，绝不因为日志失败而影响主流程
            traceback.print_exc()

    def clear_log(self):
        """清空状态文本框（控件不存在时静默返回）"""
        try:
            if hasattr(self.ui, 'spatial_status_text') and self.ui.spatial_status_text:
                self.ui.spatial_status_text.setPlainText("")
        except Exception:
            traceback.print_exc()

    def set_combo_items(self, combo_widget, items, keep_selection=True):
        """安全地设置下拉框内容，可选保持当前选中项

        照 ui_func_bulk_top.py:33-41 的既有写法。
        """
        try:
            if combo_widget is None:
                return
            if not hasattr(combo_widget, 'clear') or not hasattr(combo_widget, 'addItems'):
                return
            items = list(items) if items else []
            saved_text = combo_widget.currentText() if keep_selection else ""
            combo_widget.clear()
            if items:
                combo_widget.addItems([str(i) for i in items])
            if keep_selection and saved_text and saved_text in items:
                combo_widget.setCurrentText(saved_text)
        except Exception:
            traceback.print_exc()

    # 样本清单表头（与 update_sample_list 的取值一一对应）
    SAMPLE_COLUMNS = ("样本编号", "显示名", "spots", "过QC spots", "基因数",
                      "中位 nFeature", "中位 nCount", "中位 线粒体%", "审查状态")

    def update_sample_list(self, samples, dataset_name=""):
        """把逐样本清单渲染到只读样本清单控件（M1 只展示，不可多选）

        ⚠ 实测 W1 的 `spatial_sample_list` 是 `create_styled_table` 出来的
           **QTableWidget（NonEditableTable，gui_styles.py:951/1067）**，不是列表控件 →
           必须用 setRowCount/setColumnCount/setItem，**没有 addItem/addItems**。
           本方法同时兼容「列表控件」写法（若 W1 后续换成 create_styled_list_widget）。

        Args:
            samples: manifest['samples'] —— [{id, label, spots, spots_pass_qc, ...}, ...]
            dataset_name: 数据集名（当前仅保留签名，未参与渲染）
        """
        try:
            widget = getattr(self.ui, 'spatial_sample_list', None)
            if widget is None:
                return

            rows = [s for s in (samples or []) if isinstance(s, dict)]

            # —— 分支 A：QTableWidget ——
            if hasattr(widget, 'setRowCount') and hasattr(widget, 'setItem'):
                self._fill_sample_table(widget, rows)
                return

            # —— 分支 B：列表控件 ——
            if hasattr(widget, 'clear') and hasattr(widget, 'addItem'):
                widget.clear()
                if not rows:
                    widget.addItem("（无样本数据）")
                    return
                for item in rows:
                    widget.addItem(self._sample_row_text(item))
                return
        except Exception:
            traceback.print_exc()

    def _fill_sample_table(self, widget, rows):
        """把样本行写进 QTableWidget（只读：项目不可编辑）"""
        try:
            columns = list(self.SAMPLE_COLUMNS)
            widget.setColumnCount(len(columns))
            widget.setHorizontalHeaderLabels(columns)
            widget.setRowCount(len(rows))

            for r, item in enumerate(rows):
                cells = (
                    item.get('id'),
                    item.get('label'),
                    item.get('spots'),
                    item.get('spots_pass_qc'),
                    item.get('n_genes'),
                    item.get('median_nFeature'),
                    item.get('median_nCount'),
                    item.get('median_percent_mito'),
                    item.get('review_state'),
                )
                for c, value in enumerate(cells):
                    text = "" if value is None else str(value)
                    cell = QTableWidgetItem(text)
                    # 只读展示：禁止编辑
                    cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    widget.setItem(r, c, cell)

            if not rows:
                widget.setRowCount(1)
                cell = QTableWidgetItem("（无样本数据）")
                cell.setFlags(Qt.ItemIsEnabled)
                widget.setItem(0, 0, cell)
        except Exception:
            traceback.print_exc()

    def _sample_row_text(self, item):
        """列表控件分支用的单行文本"""
        try:
            sid = item.get('id') or '?'
            label = item.get('label') or sid
            spots = item.get('spots')
            text = f"{sid}  |  spots={spots if spots is not None else '?'}"
            if label and label != sid:
                text += f"  |  {label}"
            return text
        except Exception:
            return "?"

    def clear_sample_list(self):
        """清空样本清单控件（控件不存在时静默返回）"""
        try:
            widget = getattr(self.ui, 'spatial_sample_list', None)
            if widget is None:
                return
            if hasattr(widget, 'setRowCount'):
                widget.setRowCount(0)
            elif hasattr(widget, 'clear'):
                widget.clear()
        except Exception:
            traceback.print_exc()

    def update_data_info(self, info_dict):
        """把数据集摘要写进日志（照 ui_func_bulk_top.py:43-51 形状，字段按空转调整）"""
        try:
            if not isinstance(info_dict, dict) or not info_dict:
                return
            dataset = info_dict.get('dataset') or info_dict.get('dataset_id') or ''
            n_samples = info_dict.get('n_samples')
            if n_samples is None:
                n_samples = info_dict.get('samples')
            n_spots = info_dict.get('n_spots')
            n_genes = info_dict.get('n_genes')
            if n_genes is None:
                n_genes = info_dict.get('genes')

            if dataset:
                self.log(f"数据集: {dataset}")
            if n_samples is not None:
                self.log(f"样本数: {n_samples}")
            if n_spots is not None:
                self.log(f"spot 数: {n_spots}")
            if n_genes is not None:
                self.log(f"基因数: {n_genes}")
        except Exception:
            traceback.print_exc()

    # ------------------------------------------------------------------
    # M1 v2：读进内存的过程反馈（约 5 秒，必须让用户看得见）
    # ------------------------------------------------------------------
    def refresh(self):
        """立刻把已排队的界面更新画出来（供"耗时操作前/后"调用）

        ⚠ 这是纯显示层动作：只泵一次事件队列，不做任何业务。
           调用方必须自己配重入守卫，否则用户连点会重入耗时操作。
        """
        try:
            QApplication.processEvents()
        except Exception:
            traceback.print_exc()

    def set_load_buttons_enabled(self, enabled, busy_reason=""):
        """统一启用/禁用与数据加载相关的按钮（照 bulk 的 _set_buttons_enabled 形状）

        Args:
            enabled: True 恢复，False 禁用
            busy_reason: 仅用于日志，不参与逻辑
        """
        try:
            for attr in ('btn_spatial_select_path', 'btn_spatial_load'):
                btn = getattr(self.ui, attr, None)
                if btn is not None and hasattr(btn, 'setEnabled'):
                    btn.setEnabled(bool(enabled))
        except Exception:
            traceback.print_exc()

    def log_memory_state(self, memory_text, data_in_memory):
        """把「是否已进内存」如实写进日志（**绝不含糊其辞**）

        Args:
            memory_text: analysis.get_memory_text() 的返回值（未进内存时为空串）
            data_in_memory: analysis.data_in_memory
        """
        try:
            if data_in_memory:
                self.log(memory_text if memory_text else "已读入内存")
            else:
                # 关键：明确告诉用户"数据没进内存"，不要让 UI 看起来像成功了
                self.log("注意：数据未进内存（仅清单已加载，样本清单可用）")
        except Exception:
            traceback.print_exc()


__all__ = ['SpatialTopFunc']
