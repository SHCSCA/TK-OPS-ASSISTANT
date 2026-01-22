"""
Modern Toast Notification Component for PyQt5
现代轻量级气泡通知组件

Features:
- 非模态（Non-blocking）：不打断用户操作
- 动画效果：平滑的上浮淡入/淡出
- 自动排队：虽然简化版通常直接叠加，但保持单例管理
- 样式自适应：基于 variant 属性

Usage:
    from ui.toast import Toast
    Toast.show_success(parent_widget, "操作成功")
    Toast.show_error(parent_widget, "连接失败，请检查网络")
"""
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QFrame, QApplication, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PyQt5.QtGui import QColor, QFont

class Toast(QWidget):
    # 持续时间 (ms)
    DURATION = 3000
    ANIMATION_DURATION = 300

    def __init__(self, parent=None, text="", variant="info"):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # 确保在最上层，但作为子窗口
        
        self._setup_ui(text, variant)
        self._setup_animation()
        
    def _setup_ui(self, text, variant):
        # 主容器
        self.container = QFrame(self)
        self.container.setObjectName("ToastContainer")
        self.container.setProperty("variant", variant)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        # 图标 (简单用字符代替，后续可换 SVG)
        icon_map = {
            "success": "✓",
            "error": "✕",
            "warning": "!",
            "info": "ℹ"
        }
        self.lbl_icon = QLabel(icon_map.get(variant, "ℹ"))
        self.lbl_icon.setObjectName("ToastIcon")
        
        # 文本
        self.lbl_text = QLabel(text)
        self.lbl_text.setObjectName("ToastText")
        # 允许一定程度的换行，但通常 Toast 应该短小
        self.lbl_text.setWordWrap(True)
        
        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_text)
        
        # 自适应大小
        self.container.adjustSize()
        # 加上一点 padding 算作 Widget 大小
        self.setFixedSize(self.container.size())
        
        # 应用样式
        self._apply_local_style()

    def _apply_local_style(self):
        # 为了保证独立性，这里注入一段局部样式，
        # 但最终视觉由全局 styles.py 控制更好。
        # 这里作为 fallback 或者基础结构样式。
        pass

    def _setup_animation(self):
        # 透明度效果
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # 动画定义
        self.anim_opacity = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_opacity.setDuration(self.ANIMATION_DURATION)
        
        self.anim_pos = QPropertyAnimation(self, b"pos")
        self.anim_pos.setDuration(self.ANIMATION_DURATION)
        self.anim_pos.setEasingCurve(QEasingCurve.OutCubic)

        # 定时器：显示结束后淡出
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)

    def show_animation(self):
        if not self.parent():
            return

        # 定位：父窗口底部居中，向上浮动
        parent_geo = self.parent().rect()
        
        # 起始位置 (底部下沉)
        start_x = (parent_geo.width() - self.width()) // 2
        end_y = parent_geo.height() - self.height() - 60 # 距离底部 60px
        start_y = end_y + 20 # 向下偏移 20px
        
        self.move(start_x, start_y)
        self.show()

        # 执行并行动画
        self.anim_opacity.setStartValue(0.0)
        self.anim_opacity.setEndValue(1.0)
        
        self.anim_pos.setStartValue(QPoint(start_x, start_y))
        self.anim_pos.setEndValue(QPoint(start_x, end_y))
        
        self.anim_opacity.start()
        self.anim_pos.start()
        
        self.timer.start(self.DURATION)

    def fade_out(self):
        self.anim_opacity.setStartValue(1.0)
        self.anim_opacity.setEndValue(0.0)
        self.anim_opacity.finished.connect(self.close)
        self.anim_opacity.start()

    @staticmethod
    def show_message(parent, text, variant="info"):
        """静态工厂方法"""
        if not parent:
            return
        # 清理旧的 Toast (可选，防止堆叠过多)
        # for child in parent.findChildren(Toast):
        #     child.close()
            
        toast = Toast(parent, text, variant)
        toast.show_animation()

    @staticmethod
    def show_success(parent, text):
        Toast.show_message(parent, text, "success")

    @staticmethod
    def show_error(parent, text):
        Toast.show_message(parent, text, "error")

    @staticmethod
    def show_warning(parent, text):
        Toast.show_message(parent, text, "warning")
    
    @staticmethod
    def show_info(parent, text):
        Toast.show_message(parent, text, "info")
