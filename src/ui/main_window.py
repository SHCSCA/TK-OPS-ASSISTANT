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
    QStackedWidget, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTimer
import config
from api.ip_detector import check_ip_safety, get_ip_status_color
from ui.dashboard import DashboardPanel
from ui.profit_analysis import ProfitAnalysisWidget  # V2.0 替代蓝海监测
from ui.material_factory import MaterialFactoryPanel
from ui.crm import CRMWidget  # V2.0 新增
from ui.engagement import EngagementPanel  # V2.0 新增
from ui.downloader import DownloaderPanel
from ui.ai_content_factory import AIContentFactoryPanel, PhotoVideoPanel
from ui.visual_lab import VisualLabPanel
from ui.diagnostics import DiagnosticsPanel
from ui.settings import SettingsPanel
from ui.lan_airdrop import LanAirdropPanel
from utils.lan_server import get_lan_server  # V2.0 新增


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok 运营助手 v2.0 Pro")
        self._ip_blocked = False
        
        # 允许自由拉伸，设定最小尺寸
        self.setMinimumSize(1200, 800)
        # 默认尺寸
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # 样式已由 Application 全局应用，此处不再设置
        
        # V2.0: 执行数据库迁移
        self._run_migrations()
        
        self._init_ui()
        self._check_ip_status()
        self._init_ip_timer()
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

        # 默认选中第一个可操作的导航项 (跳过标题)
        default_row = getattr(self, "first_selectable_row", 1)
        self.nav_list.setCurrentRow(default_row)

    def _init_content_stack(self) -> None:
        """初始化右侧内容栈，顺序需与导航同步"""
        self.dashboard_panel = DashboardPanel(parent_nav_callback=self._switch_via_dashboard)
        self.profit_panel = ProfitAnalysisWidget()  # V2.0 替代蓝海监测
        self.material_factory_panel = MaterialFactoryPanel()
        self.crm_panel = CRMWidget()  # V2.0 新增
        self.engagement_panel = EngagementPanel() # V2.0 新增
        self.downloader_panel = DownloaderPanel()
        self.ai_content_factory_panel = AIContentFactoryPanel(enable_photo=False)
        self.photo_video_panel = PhotoVideoPanel()
        self.visual_lab_panel = VisualLabPanel()
        self.lan_airdrop_panel = LanAirdropPanel()
        self.diagnostics_panel = DiagnosticsPanel()
        self.settings_panel = SettingsPanel()

        for panel in [
            self.dashboard_panel,
            self.profit_panel,
            self.material_factory_panel,
            self.crm_panel,
            self.engagement_panel,  # Integrated EngagementPanel
            self.downloader_panel,
            self.ai_content_factory_panel,
            self.photo_video_panel,
            self.visual_lab_panel,
            self.lan_airdrop_panel,
            self.diagnostics_panel,
            self.settings_panel,
        ]:
            self.stacked_widget.addWidget(panel)
            
    def _switch_via_dashboard(self, index: int):
        """Callback for dashboard quick actions"""
        # Find item with this UserRole and select it
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            if item.data(Qt.UserRole) == index:
                self.nav_list.setCurrentRow(i)
                break

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

        # Structure: (Header, [(Title, StackIndex), ...])
        nav_structure = [
            ("🚀 核心功能", [
                ("�  工作台", 0),
                ("👥  账号矩阵", 3),
                ("💬  互动中心", 4),
            ]),
            ("🎨 内容创作", [
                ("🎬  素材工厂", 2),
                ("🧠  AI 二创工厂", 6),
                ("🖼️  图文成片", 7),
                ("👁️  视觉实验室", 8),
            ]),
            ("💼 电商运营", [
                ("💰  选品清洗池", 1),
            ]),
            ("🛠️ 实用工具", [
                ("⬇️  素材下载器", 5),
                ("📡  局域网空投", 9),
            ]),
            ("🔧 系统管理", [
                ("🧪  诊断中心", 10),
                ("⚙️  系统设置", 11),
            ])
        ]

        self.first_selectable_row = 0
        current_row = 0
        first_found = False

        for group_title, items in nav_structure:
            # Add Header
            header = QListWidgetItem(group_title)
            # 标题不可选中
            header.setFlags(Qt.NoItemFlags)
            header.setData(Qt.UserRole, -1)
            
            font = QFont()
            font.setBold(True)
            font.setPointSize(9)
            header.setFont(font)
            # 简单的视觉区分，更复杂的样式建议在 QSS 中针对 UserRole=-1 或 disabled 状态设置
            header.setForeground(Qt.gray)
            
            self.nav_list.addItem(header)
            current_row += 1

            for title, page_idx in items:
                item = QListWidgetItem(title)
                item.setFont(QFont("Microsoft YaHei UI", 10))
                item.setData(Qt.UserRole, page_idx)
                self.nav_list.addItem(item)
                
                if not first_found:
                    self.first_selectable_row = current_row
                    first_found = True
                
                current_row += 1
            
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

    def _on_nav_changed(self, row):
        """Switch stacked widget page based on item data"""
        item = self.nav_list.item(row)
        if not item:
            return

        page_idx = item.data(Qt.UserRole)
        # 标题项 UserRole 为 -1，忽略
        if page_idx is None or int(page_idx) == -1:
            return
            
        index = int(page_idx)
        self.stacked_widget.setCurrentIndex(index)
        
        # Dashboard auto refresh happens on init, but we could trigger it again
        if index == 0 and hasattr(self.dashboard_panel, "_refresh_ip_status"):
             # self.dashboard_panel._refresh_ip_status() # Optional: auto refresh whenever creating
             pass

        # 局域网空投：每次进入刷新目录/二维码
        try:
            if getattr(self, "lan_airdrop_panel", None) and index == 8:
                self.lan_airdrop_panel.refresh()
        except Exception:
            pass

    def _check_ip_status(self):
        is_safe, msg = check_ip_safety()
        try:
            self.ip_status_label.setText(f"当前网络: {msg}")
            self._set_ip_status_variant(is_safe)
        except Exception:
            pass

        try:
            if not is_safe:
                self._block_on_ip_risk(msg)
            else:
                self._recover_from_ip_risk()
        except Exception:
            pass
        
        # If dashboard exists, maybe refresh it too
        if hasattr(self, "dashboard_panel") and hasattr(self.dashboard_panel, "_refresh_ip_status"):
             # Optional: sync dashboard card
             pass

    def _init_ip_timer(self) -> None:
        """每 5 分钟自动检测一次 IP 环境。"""
        try:
            interval_sec = int(getattr(config, "IP_CHECK_INTERVAL_SEC", 300) or 300)
        except Exception:
            interval_sec = 300
        self._ip_timer = QTimer(self)
        self._ip_timer.setInterval(max(60, interval_sec) * 1000)
        self._ip_timer.timeout.connect(self._check_ip_status)
        self._ip_timer.start()

    def _block_on_ip_risk(self, msg: str) -> None:
        """当 IP 风险触发时，软熔断并提示用户切断网络。"""
        if self._ip_blocked:
            return
        self._ip_blocked = True
        try:
            # 仅在配置允许时才强制禁用导航（默认不禁用，避免阻塞用户）
            if getattr(config, "IP_BLOCK_NAV_ON_RISK", False):
                self.nav_list.setEnabled(False)
        except Exception:
            pass
        QMessageBox.critical(self, "IP 风险", f"检测到高风险网络环境：\n{msg}\n\n请立刻切换/断开网络后重试。")

    def _recover_from_ip_risk(self) -> None:
        """IP 恢复后解除软熔断。"""
        if not self._ip_blocked:
            return
        self._ip_blocked = False
        try:
            self.nav_list.setEnabled(True)
        except Exception:
            pass

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
