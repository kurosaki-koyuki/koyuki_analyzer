# -*- coding: utf-8 -*-
"""
通用算法工具脚本 - 存放各种通用函数
这些函数与生信分析无关，主要用于通用功能（如文件操作、图片处理等）
"""

from .import_config import *

# ========================================
# 文件操作工具类
# ========================================
class FileUtils:
    """文件操作工具类"""
    
    @staticmethod
    def ensure_directory(directory):
        """确保目录存在"""
        try:
            os.makedirs(directory, exist_ok=True)
            return True
        except Exception as e:
            print(f"创建目录失败: {e}")
            return False
    
    @staticmethod
    def file_exists(file_path):
        """检查文件是否存在"""
        return os.path.exists(file_path)
    
    @staticmethod
    def get_file_size(file_path):
        """获取文件大小"""
        try:
            if os.path.exists(file_path):
                return os.path.getsize(file_path)
            return 0
        except Exception as e:
            print(f"获取文件大小失败: {e}")
            return 0
    
    @staticmethod
    def get_file_extension(file_path):
        """获取文件扩展名"""
        try:
            return os.path.splitext(file_path)[1].lower()
        except Exception as e:
            print(f"获取文件扩展名失败: {e}")
            return ""
    
    @staticmethod
    def is_valid_image_file(file_path):
        """检查是否为有效的图片文件"""
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp']
        extension = FileUtils.get_file_extension(file_path)
        return extension in valid_extensions
    
    @staticmethod
    def is_valid_audio_file(file_path):
        """检查是否为有效的音频文件"""
        valid_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.aac']
        extension = FileUtils.get_file_extension(file_path)
        return extension in valid_extensions
    
    @staticmethod
    def is_valid_video_file(file_path):
        """检查是否为有效的视频文件"""
        valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
        extension = FileUtils.get_file_extension(file_path)
        return extension in valid_extensions

# ========================================
# 图片处理工具类
# ========================================
class ImageUtils:
    """图片处理工具类"""
    
    @staticmethod
    def load_image(image_path):
        """加载图片"""
        try:
            if os.path.exists(image_path):
                return QPixmap(image_path)
            return None
        except Exception as e:
            print(f"加载图片失败: {e}")
            return None
    
    @staticmethod
    def scale_image(pixmap, width, height, keep_aspect=True):
        """缩放图片"""
        try:
            if pixmap:
                if keep_aspect:
                    return pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                else:
                    return pixmap.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            return None
        except Exception as e:
            print(f"缩放图片失败: {e}")
            return None
    
    @staticmethod
    def create_icon(icon_path):
        """创建图标"""
        try:
            if os.path.exists(icon_path):
                return QIcon(icon_path)
            return None
        except Exception as e:
            print(f"创建图标失败: {e}")
            return None

# ========================================
# 字符串处理工具类
# ========================================
class StringUtils:
    """字符串处理工具类"""
    
    @staticmethod
    def is_empty(text):
        """检查字符串是否为空"""
        return text is None or len(str(text).strip()) == 0
    
    @staticmethod
    def truncate(text, max_length, suffix="..."):
        """截断字符串"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def clean_filename(filename):
        """清理文件名，移除非法字符"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()

# ========================================
# 时间处理工具类
# ========================================
class TimeUtils:
    """时间处理工具类"""
    
    @staticmethod
    def get_current_timestamp():
        """获取当前时间戳"""
        import time
        return time.time()
    
    @staticmethod
    def get_current_datetime(format_str="%Y-%m-%d %H:%M:%S"):
        """获取当前日期时间字符串"""
        from datetime import datetime
        return datetime.now().strftime(format_str)
    
    @staticmethod
    def format_duration(seconds):
        """格式化时长"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

# ========================================
# 日志工具类
# ========================================
class LogUtils:
    """日志工具类"""
    
    @staticmethod
    def log_info(message):
        """记录信息日志"""
        print(f"[INFO] {TimeUtils.get_current_datetime()} - {message}")
    
    @staticmethod
    def log_warning(message):
        """记录警告日志"""
        print(f"[WARNING] {TimeUtils.get_current_datetime()} - {message}")
    
    @staticmethod
    def log_error(message):
        """记录错误日志"""
        print(f"[ERROR] {TimeUtils.get_current_datetime()} - {message}")
    
    @staticmethod
    def log_debug(message):
        """记录调试日志"""
        print(f"[DEBUG] {TimeUtils.get_current_datetime()} - {message}")

# ========================================
# 配置工具类
# ========================================
class ConfigUtils:
    """配置工具类"""
    
    @staticmethod
    def get_base_dir():
        """获取基础目录"""
        return BASE_DIR
    
    @staticmethod
    def get_output_dir():
        """获取输出目录"""
        FileUtils.ensure_directory(OUT_BASE)
        return OUT_BASE
    
    @staticmethod
    def get_data_path():
        """获取数据路径"""
        return DATA_PATH

# ========================================
# PyQt5 通用控件类
# ========================================
class ScalableLabel(QLabel):
    """可缩放标签类 - 支持鼠标滚轮缩放和拖拽"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scale_factor = 1.0
        self.min_scale = 0.3
        self.max_scale = 3.0
        self.setMinimumSize(400, 300)
        self.current_pixmap = None
        self.setScaledContents(False)
        self.dragging = False
        self.last_pos = None
        
    def setPixmap(self, pixmap):
        self.current_pixmap = pixmap
        if pixmap is not None:
            label_size = self.size()
            pixmap_size = pixmap.size()
            scale_w = label_size.width() / pixmap_size.width()
            scale_h = label_size.height() / pixmap_size.height()
            self.scale_factor = min(scale_w, scale_h, 1.0)
            self.update_scaled_pixmap()
        else:
            super().setPixmap(pixmap)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_pixmap is not None and self.scale_factor > 0:
            label_size = self.size()
            pixmap_size = self.current_pixmap.size()
            scale_w = label_size.width() / pixmap_size.width()
            scale_h = label_size.height() / pixmap_size.height()
            fit_scale = min(scale_w, scale_h, 1.0)
            if self.scale_factor == 1.0:
                self.scale_factor = fit_scale
                self.update_scaled_pixmap()
    
    def update_scaled_pixmap(self):
        if self.current_pixmap is None:
            return
        scaled_pixmap = self.current_pixmap.scaled(
            self.current_pixmap.size() * self.scale_factor,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        super().setPixmap(scaled_pixmap)
    
    def wheelEvent(self, event):
        if self.current_pixmap is None:
            super().wheelEvent(event)
            return
        
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale_factor = min(self.scale_factor * 1.1, self.max_scale)
        else:
            self.scale_factor = max(self.scale_factor / 1.1, self.min_scale)
        
        self.update_scaled_pixmap()
        event.accept()
    
    def mousePressEvent(self, event):
        if self.current_pixmap is not None:
            self.dragging = True
            self.last_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.dragging and self.current_pixmap is not None:
            parent = self.parent()
            if parent and hasattr(parent, 'horizontalScrollBar') and hasattr(parent, 'verticalScrollBar'):
                dx = event.pos().x() - self.last_pos.x()
                dy = event.pos().y() - self.last_pos.y()
                h_bar = parent.horizontalScrollBar()
                v_bar = parent.verticalScrollBar()
                h_bar.setValue(h_bar.value() - dx)
                v_bar.setValue(v_bar.value() - dy)
                self.last_pos = event.pos()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.dragging = False
        super().mouseReleaseEvent(event)