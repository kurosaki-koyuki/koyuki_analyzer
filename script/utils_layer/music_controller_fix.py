"""
全局音乐控件修复脚本
用于统一管理音乐控件相关的修复逻辑，避免在子界面中重复修改
"""

from script.utils_layer.import_config import QPushButton, QSlider, QIcon, QSize, os


def fix_music_controller_bindings(ui_bind_instance, music_controller):
    """
    修复音乐控制器的绑定问题
    
    问题：音乐按钮的clicked信号在MusicController.create_music_controls中已经绑定
    如果在子界面的ui_bind中再次绑定，会导致信号被绑定两次，产生冲突
    
    解决方案：
    1. 解绑原有的音乐按钮信号
    2. 重新绑定音乐按钮信号到主窗口的toggle_music方法（实现全局同步）
    3. 绑定音量滑块的信号
    
    Args:
        ui_bind_instance: ui_bind实例（如ViolinBind或InitialAnalysisBind）
        music_controller: 音乐控制器实例
    """
    if music_controller:
        # 获取音乐按钮
        music_button = music_controller.get_music_button()
        if music_button:
            # 解绑原有的信号连接（MusicController中的toggle_music）
            try:
                music_button.clicked.disconnect()
            except TypeError:
                pass  # 如果没有连接，会抛出TypeError
            
            # 重新绑定到主窗口的toggle_music方法（实现全局同步）
            main_window = ui_bind_instance.parent
            if hasattr(main_window, 'toggle_music'):
                music_button.clicked.connect(main_window.toggle_music)
        
        # 只绑定音量滑块的信号
        volume_slider = music_controller.get_volume_slider()
        if volume_slider:
            volume_slider.valueChanged.connect(ui_bind_instance.set_volume)


def sync_volume_sliders(source_value, all_sliders):
    """
    同步所有音量滑块的值
    
    Args:
        source_value: 源滑块的值
        all_sliders: 所有需要同步的滑块列表
    """
    for slider in all_sliders:
        if slider and slider.value() != source_value:
            slider.blockSignals(True)
            slider.setValue(source_value)
            slider.blockSignals(False)


def get_music_button_icon(is_playing, paths):
    """
    获取音乐按钮图标
    
    Args:
        is_playing: 是否正在播放
        paths: 模组路径字典
        
    Returns:
        QIcon对象或None
    """
    icon_path = paths.get('MUSIC_STOP_ICON') if is_playing else paths.get('MUSIC_PLAY_ICON')
    if icon_path and os.path.exists(icon_path):
        return QIcon(icon_path)
    return None


def update_music_button_icon(music_button, is_playing, paths):
    """
    更新音乐按钮图标
    
    Args:
        music_button: 音乐按钮控件
        is_playing: 是否正在播放
        paths: 模组路径字典
    """
    icon = get_music_button_icon(is_playing, paths)
    if icon and music_button:
        music_button.setIcon(icon)
        music_button.setIconSize(QSize(32, 32))


def get_all_music_buttons(main_window):
    """
    获取主窗口中的所有音乐按钮（包括主界面直接创建的和子界面music_controller中的）

    Args:
        main_window: 主窗口实例

    Returns:
        list: 所有音乐按钮的列表
    """
    buttons = []

    # 主界面直接创建的music_btn
    if hasattr(main_window, 'music_btn') and main_window.music_btn:
        buttons.append(main_window.music_btn)

    # 小提琴图界面的音乐按钮 - music_controller在violin_ui中
    if hasattr(main_window, 'violin_ui'):
        violin_ui = main_window.violin_ui
        if hasattr(violin_ui, 'music_controller') and violin_ui.music_controller:
            button = violin_ui.music_controller.get_music_button()
            if button:
                buttons.append(button)

    # 初步分析界面的音乐按钮 - music_controller在analysis_ui中
    if hasattr(main_window, 'analysis_ui'):
        analysis_ui = main_window.analysis_ui
        if hasattr(analysis_ui, 'music_controller') and analysis_ui.music_controller:
            button = analysis_ui.music_controller.get_music_button()
            if button:
                buttons.append(button)

    # 差异分析界面的音乐按钮 - music_controller在diff_ui中
    if hasattr(main_window, 'diff_ui'):
        diff_ui = main_window.diff_ui
        if hasattr(diff_ui, 'music_controller') and diff_ui.music_controller:
            button = diff_ui.music_controller.get_music_button()
            if button:
                buttons.append(button)

    # bulk表达量分析界面的音乐按钮 - music_controller在bulk_ui中
    if hasattr(main_window, 'bulk_ui'):
        bulk_ui = main_window.bulk_ui
        if hasattr(bulk_ui, 'music_controller') and bulk_ui.music_controller:
            button = bulk_ui.music_controller.get_music_button()
            if button:
                buttons.append(button)

    return buttons


def sync_all_music_buttons(main_window, is_playing, paths):
    """
    同步主窗口中所有音乐按钮的图标状态
    
    Args:
        main_window: 主窗口实例
        is_playing: 是否正在播放
        paths: 模组路径字典
    """
    buttons = get_all_music_buttons(main_window)
    icon = get_music_button_icon(is_playing, paths)
    
    if icon:
        for button in buttons:
            if button:
                button.setIcon(icon)
                button.setIconSize(QSize(32, 32))


def ensure_music_controller_initialization(ui_instance, mod_manager):
    """
    确保音乐控制器正确初始化
    
    Args:
        ui_instance: ui实例（如ViolinUI或InitialAnalysisUI）
        mod_manager: 模组管理器实例
    """
    try:
        mod_instance = mod_manager.get_current_mod()
        if hasattr(mod_instance, 'get_music_controller_class'):
            MusicControllerClass = mod_instance.get_music_controller_class()
            if hasattr(ui_instance, 'music_controller') and ui_instance.music_controller is None:
                ui_instance.music_controller = MusicControllerClass(ui_instance.parent, mod_instance)
    except Exception as e:
        print(f"[DEBUG] Music controller initialization error: {e}")


def validate_music_controller_state(music_controller):
    """
    验证音乐控制器状态
    
    Args:
        music_controller: 音乐控制器实例
        
    Returns:
        bool: 音乐控制器是否正常工作
    """
    if music_controller is None:
        return False
    
    music_button = music_controller.get_music_button()
    volume_slider = music_controller.get_volume_slider()
    
    return music_button is not None and volume_slider is not None


def get_all_volume_sliders(main_window):
    """
    获取主窗口中的所有音量滑块（包括主界面直接创建的和子界面music_controller中的）
    
    Args:
        main_window: 主窗口实例
        
    Returns:
        list: 所有音量滑块的列表
    """
    sliders = []
    
    # 主界面直接创建的volume_slider（不通过music_controller）
    if hasattr(main_window, 'volume_slider') and main_window.volume_slider:
        sliders.append(main_window.volume_slider)
    
    # 小提琴图界面的音量滑块 - music_controller在violin_ui中
    if hasattr(main_window, 'violin_ui'):
        violin_ui = main_window.violin_ui
        if hasattr(violin_ui, 'music_controller') and violin_ui.music_controller:
            slider = violin_ui.music_controller.get_volume_slider()
            if slider:
                sliders.append(slider)
        # 也检查直接的volume_slider（备用）
        elif hasattr(violin_ui, 'volume_slider') and violin_ui.volume_slider:
            sliders.append(violin_ui.volume_slider)
    
    # 初步分析界面的音量滑块 - music_controller在analysis_ui中
    if hasattr(main_window, 'analysis_ui'):
        analysis_ui = main_window.analysis_ui
        if hasattr(analysis_ui, 'music_controller') and analysis_ui.music_controller:
            slider = analysis_ui.music_controller.get_volume_slider()
            if slider:
                sliders.append(slider)
        # 也检查直接的volume_slider（备用）
        elif hasattr(analysis_ui, 'volume_slider') and analysis_ui.volume_slider:
            sliders.append(analysis_ui.volume_slider)

    # 差异分析界面的音量滑块 - music_controller在diff_ui中
    if hasattr(main_window, 'diff_ui'):
        diff_ui = main_window.diff_ui
        if hasattr(diff_ui, 'music_controller') and diff_ui.music_controller:
            slider = diff_ui.music_controller.get_volume_slider()
            if slider:
                sliders.append(slider)
        # 也检查直接的volume_slider（备用）
        elif hasattr(diff_ui, 'volume_slider') and diff_ui.volume_slider:
            sliders.append(diff_ui.volume_slider)

    # bulk表达量分析界面的音量滑块 - music_controller在bulk_ui中
    if hasattr(main_window, 'bulk_ui'):
        bulk_ui = main_window.bulk_ui
        if hasattr(bulk_ui, 'music_controller') and bulk_ui.music_controller:
            slider = bulk_ui.music_controller.get_volume_slider()
            if slider:
                sliders.append(slider)
        # 也检查直接的volume_slider（备用）
        elif hasattr(bulk_ui, 'volume_slider') and bulk_ui.volume_slider:
            sliders.append(bulk_ui.volume_slider)

    return sliders


def get_all_music_controllers(main_window):
    """
    获取主窗口中的所有音乐控制器
    
    Args:
        main_window: 主窗口实例
        
    Returns:
        list: 所有音乐控制器的列表
    """
    controllers = []
    
    # 检查主界面的音乐控制器
    if hasattr(main_window, 'music_controller') and main_window.music_controller:
        controllers.append(main_window.music_controller)
    
    # 检查小提琴图界面的音乐控制器
    if hasattr(main_window, 'violin_bind') and hasattr(main_window.violin_bind, 'violin_ui'):
        if hasattr(main_window.violin_bind.violin_ui, 'music_controller') and main_window.violin_bind.violin_ui.music_controller:
            controllers.append(main_window.violin_bind.violin_ui.music_controller)
    
    # 检查初步分析界面的音乐控制器
    if hasattr(main_window, 'analysis_bind') and hasattr(main_window.analysis_bind, 'analysis_ui'):
        if hasattr(main_window.analysis_bind.analysis_ui, 'music_controller') and main_window.analysis_bind.analysis_ui.music_controller:
            controllers.append(main_window.analysis_bind.analysis_ui.music_controller)

    # 检查差异分析界面的音乐控制器
    if hasattr(main_window, 'diff_bind') and hasattr(main_window.diff_bind, 'diff_ui'):
        if hasattr(main_window.diff_bind.diff_ui, 'music_controller') and main_window.diff_bind.diff_ui.music_controller:
            controllers.append(main_window.diff_bind.diff_ui.music_controller)

    return controllers


def sync_all_volume_sliders(main_window, source_value):
    """
    同步主窗口中所有音量滑块（包括主界面和子界面）
    
    Args:
        main_window: 主窗口实例
        source_value: 源滑块的值
    """
    sliders = get_all_volume_sliders(main_window)
    sync_volume_sliders(source_value, sliders)