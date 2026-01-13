"""
Main application window (Refactored)
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QStatusBar,
    QStackedWidget, QFrame
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont, QColor
import config
from api.ip_detector import check_ip_safety, get_ip_status_color
from ui.blue_ocean import BlueOceanPanel
from ui.material_factory import MaterialFactoryPanel
from ui.downloader import DownloaderPanel
from ui.ai_copywriter import AICopywriterPanel
from ui.diagnostics import DiagnosticsPanel
from ui.settings import SettingsPanel


class IPStatusPanel(QWidget):
    """独立的 IP 状态展示面板"""
    def __init__(self):
        super().__init__()
        self._init_ui()

    def _set_status_variant(self, is_safe: bool) -> None:
        """用动态属性驱动样式，避免局部 setStyleSheet 破坏全局主题。"""
        self.status_label.setProperty("status", "safe" if is_safe else "unsafe")
        # 触发 QSS 重新应用
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Title
        title = QLabel("IP 环境监测")
        title.setObjectName("h1")
        layout.addWidget(title)

        # Status info container
        self.status_container = QFrame()
        self.status_container.setProperty("class", "config-frame")
        container_layout = QVBoxLayout(self.status_container)
        container_layout.setContentsMargins(30, 30, 30, 30)

        self.status_label = QLabel("正在检测...")
        self.status_label.setObjectName("h2")
        self.status_label.setWordWrap(True)
        container_layout.addWidget(self.status_label)

        layout.addWidget(self.status_container)

        # Info text
        info_text = QLabel(
            "提示：\n1. 此工具建议在美国本地网络环境下运行。\n"
            "2. 如检测到非美区或机房IP (Datacenter)，可能会影响 TikTok 流量。\n"
            "3. 绿色状态表示环境相对安全。"
        )
        info_text.setProperty("variant", "muted")
        layout.addWidget(info_text)

        layout.addStretch()
        self.setLayout(layout)

    def refresh_status(self):
        """刷新状态显示"""
        is_safe, status_message = check_ip_safety()
        icon = "✅" if is_safe else "⚠️"
        
        self.status_label.setText(f"{icon} {status_message}")
        self._set_status_variant(is_safe)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok 蓝海运营助手 v1.0")
        
        # 允许自由拉伸，设定最小尺寸
        self.setMinimumSize(1200, 800)
        # 默认尺寸
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # 样式已由 Application 全局应用，此处不再设置
        
        self._init_ui()
        self._check_ip_status()
        self.show()
    
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Left Navigation Panel
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel)
        
        # 2. Right Content Area (QStackedWidget)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("ContentStack")
        
        # Initialize Panels
        self.ip_panel = IPStatusPanel()
        self.blue_ocean_panel = BlueOceanPanel()
        self.material_factory_panel = MaterialFactoryPanel()
        self.downloader_panel = DownloaderPanel()
        self.ai_copywriter_panel = AICopywriterPanel()
        self.diagnostics_panel = DiagnosticsPanel()
        self.settings_panel = SettingsPanel()
        
        # Add to stack (Order must match nav list)
        self.stacked_widget.addWidget(self.ip_panel)            # Index 0
        self.stacked_widget.addWidget(self.blue_ocean_panel)    # Index 1
        self.stacked_widget.addWidget(self.material_factory_panel) # Index 2
        self.stacked_widget.addWidget(self.downloader_panel)    # Index 3
        self.stacked_widget.addWidget(self.ai_copywriter_panel) # Index 4
        self.stacked_widget.addWidget(self.diagnostics_panel)   # Index 5
        self.stacked_widget.addWidget(self.settings_panel)      # Index 6
        
        main_layout.addWidget(self.stacked_widget)
        central_widget.setLayout(main_layout)
        
        self._init_status_bar()
        
        # Select first item by default
        self.nav_list.setCurrentRow(0)

    def _create_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(220)
        panel.setObjectName("LeftPanel")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # App Title Area
        title_box = QFrame()
        title_box.setFixedHeight(80)
        title_box.setObjectName("TitleBox")
        title_layout = QVBoxLayout(title_box)
        
        title = QLabel("TK 运营助手")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("h2")
        title_layout.addWidget(title)
        
        version = QLabel("v1.0 Pro")
        version.setAlignment(Qt.AlignCenter)
        version.setProperty("variant", "muted")
        title_layout.addWidget(version)
        
        layout.addWidget(title_box)
        
        # Navigation List
        self.nav_list = QListWidget()
        
        nav_items = [
            ("📊  IP 环境监测", 0),
            ("🌊  蓝海监测器", 1),
            ("🎬  素材工厂", 2),
            ("⬇️  素材下载器", 3),
            ("🤖  AI 文案助手", 4),
            ("🧪  诊断中心", 5),
            ("⚙️  系统设置", 6)
        ]
        
        for name, _ in nav_items:
            item = QListWidgetItem(name)
            item.setFont(QFont("Microsoft YaHei UI", 10))
            self.nav_list.addItem(item)
            
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list)
        
        panel.setLayout(layout)
        return panel

    def _init_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.setSizeGripEnabled(False)
        
        self.ip_status_label = QLabel("正在初始化...")
        self.ip_status_label.setProperty("variant", "muted")
        self.statusBar.addWidget(self.ip_status_label)

    def _set_ip_status_variant(self, is_safe: bool) -> None:
        self.ip_status_label.setProperty("status", "safe" if is_safe else "unsafe")
        self.ip_status_label.style().unpolish(self.ip_status_label)
        self.ip_status_label.style().polish(self.ip_status_label)

    def _on_nav_changed(self, index):
        """Switch stacked widget page"""
        self.stacked_widget.setCurrentIndex(index)
        
        # Special refresh for IP panel
        if index == 0:
            self.ip_panel.refresh_status()

    def _check_ip_status(self):
        is_safe, msg = check_ip_safety()
        self.ip_status_label.setText(f"当前网络: {msg}")
        self._set_ip_status_variant(is_safe)
        
        # Also refresh panel
        self.ip_panel.refresh_status()

    def closeEvent(self, event):
        """Handle window close"""
        # 统一清理后台线程/定时器，避免 Windows 退出卡死
        for panel in [
            getattr(self, "blue_ocean_panel", None),
            getattr(self, "material_factory_panel", None),
            getattr(self, "downloader_panel", None),
            getattr(self, "ai_copywriter_panel", None),
            getattr(self, "diagnostics_panel", None),
        ]:
            if not panel:
                continue
            try:
                if hasattr(panel, "shutdown"):
                    panel.shutdown()
                    continue
                worker = getattr(panel, "worker", None)
                if worker:
                    worker.stop()
            except Exception:
                pass

        event.accept()
