"""主窗口（主导航 + 内容区）

职责：
- 左侧导航（QListWidget）+ 右侧内容栈（QStackedWidget）
- 启动时执行数据库迁移
- 提供 IP 环境监测状态展示

约束：
- 样式由全局 QSS 控制，本文件避免局部 setStyleSheet 破坏主题一致性。
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QStatusBar,
    QStackedWidget, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import config
from api.ip_detector import check_ip_safety, get_ip_status_color
from ui.profit_analysis import ProfitAnalysisWidget  # V2.0 替代蓝海监测
from ui.material_factory import MaterialFactoryPanel
from ui.crm import CRMWidget  # V2.0 新增
from ui.downloader import DownloaderPanel
from ui.ai_content_factory import AIContentFactoryPanel, PhotoVideoPanel
from ui.visual_lab import VisualLabPanel
from ui.diagnostics import DiagnosticsPanel
from ui.settings import SettingsPanel
from ui.lan_airdrop import LanAirdropPanel
from utils.lan_server import get_lan_server  # V2.0 新增


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
        self.setWindowTitle("TikTok 运营助手 v2.0 Pro")
        
        # 允许自由拉伸，设定最小尺寸
        self.setMinimumSize(1200, 800)
        # 默认尺寸
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # 样式已由 Application 全局应用，此处不再设置
        
        # V2.0: 执行数据库迁移
        self._run_migrations()
        
        self._init_ui()
        self._check_ip_status()
        self.show()
    
    def _run_migrations(self):
        """V2.0 启动时执行数据库迁移"""
        try:
            from db.migrations import ensure_v2_database
            ensure_v2_database()
        except Exception as e:
            import logging
            logging.error(f"数据库迁移失败: {e}")
    
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("ContentStack")
        main_layout.addWidget(self.stacked_widget, 1)

        central_widget.setLayout(main_layout)

        self._init_content_stack()
        self._init_status_bar()

        # 默认选中第一个导航项
        self.nav_list.setCurrentRow(0)

    def _init_content_stack(self) -> None:
        """初始化右侧内容栈，顺序需与导航同步"""
        self.ip_panel = IPStatusPanel()
        self.profit_panel = ProfitAnalysisWidget()  # V2.0 替代蓝海监测
        self.material_factory_panel = MaterialFactoryPanel()
        self.crm_panel = CRMWidget()  # V2.0 新增
        self.downloader_panel = DownloaderPanel()
        self.ai_content_factory_panel = AIContentFactoryPanel(enable_photo=False)
        self.photo_video_panel = PhotoVideoPanel()
        self.visual_lab_panel = VisualLabPanel()
        self.lan_airdrop_panel = LanAirdropPanel()
        self.diagnostics_panel = DiagnosticsPanel()
        self.settings_panel = SettingsPanel()

        for panel in [
            self.ip_panel,
            self.profit_panel,
            self.material_factory_panel,
            self.crm_panel,
            self.downloader_panel,
            self.ai_content_factory_panel,
            self.photo_video_panel,
            self.visual_lab_panel,
            self.lan_airdrop_panel,
            self.diagnostics_panel,
            self.settings_panel,
        ]:
            self.stacked_widget.addWidget(panel)

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
        
        version = QLabel("v2.0 Pro")
        version.setAlignment(Qt.AlignCenter)
        version.setProperty("variant", "muted")
        title_layout.addWidget(version)
        
        layout.addWidget(title_box)
        
        # Navigation List
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")

        nav_items = [
            "🛡  IP 安全体检",
            "💰  选品清洗池",
            "🎬  素材工厂",
            "👥  账号矩阵",
            "⬇️  素材下载器",
            "🧠  AI 二创工厂",
            "🖼️  图文成片",
            "👁️  视觉实验室",
            "📡  局域网空投",
            "🧪  诊断中心",
            "⚙️  系统设置",
        ]

        for name in nav_items:
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

        # 局域网空投：每次进入刷新目录/二维码
        try:
            if getattr(self, "lan_airdrop_panel", None) and index == self.stacked_widget.indexOf(self.lan_airdrop_panel):
                self.lan_airdrop_panel.refresh()
        except Exception:
            pass

    def _check_ip_status(self):
        is_safe, msg = check_ip_safety()
        self.ip_status_label.setText(f"当前网络: {msg}")
        self._set_ip_status_variant(is_safe)
        
        # Also refresh panel
        self.ip_panel.refresh_status()

    def closeEvent(self, event):
        """Handle window close"""
        # V2.0: 停止局域网服务
        try:
            lan_server = get_lan_server()
            if lan_server.running:
                lan_server.stop()
        except:
            pass
        
        # 统一清理后台线程/定时器，避免 Windows 退出卡死
        for panel in [
            getattr(self, "profit_panel", None),
            getattr(self, "material_factory_panel", None),
            getattr(self, "crm_panel", None),
            getattr(self, "downloader_panel", None),
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
