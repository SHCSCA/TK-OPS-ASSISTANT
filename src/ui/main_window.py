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
    QStackedWidget, QFrame, QMessageBox, QProgressDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTimer
import sys
import config
from api.ip_detector import check_ip_safety, get_ip_status_color
from utils.lan_server import get_lan_server
from utils.updater import UpdateChecker, AutoUpdater, UpdateDownloader
import importlib

class LazyLoader(QWidget):
    """
    延迟加载容器
    仅当被显示(ensure_loaded)时才实例化真正的业务 Panel，大幅提升启动速度。
    """
    def __init__(self, factory_func):
        super().__init__()
        self.factory = factory_func
        self.real_widget = None
        # 使用布局填充
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        
    def ensure_loaded(self):
        if self.real_widget:
            return self.real_widget
            
        # 实例化真正的业务组件
        try:
            self.real_widget = self.factory()
            self._layout.addWidget(self.real_widget)
        except Exception as e:
            # 容错显示
            err_label = QLabel(f"模块加载失败:\n{e}")
            err_label.setAlignment(Qt.AlignCenter)
            self._layout.addWidget(err_label)
            import logging
            logging.error(f"LazyLoader failed: {e}", exc_info=True)
            
        return self.real_widget

    def shutdown(self):
        """代理关闭事件"""
        if self.real_widget and hasattr(self.real_widget, "shutdown"):
            self.real_widget.shutdown()

    @property
    def worker(self):
        """代理 worker 属性（用于 closeEvent 清理）"""
        if self.real_widget and hasattr(self.real_widget, "worker"):
            return self.real_widget.worker
        return None

    def refresh(self):
        """代理 refresh 方法"""
        if self.real_widget and hasattr(self.real_widget, "refresh"):
            self.real_widget.refresh()


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
        
        # V2.2: 检查更新
        self._check_for_updates()
        
        self.show()

    def _check_for_updates(self):
        """Startup update check"""
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.check_finished.connect(self._on_update_check_finished)
        self._update_checker.start()

    def _on_update_available(self, version, url, notes):
        """Update found dialog"""
        msg = QMessageBox(self)
        msg.setWindowTitle("发现新版本")
        msg.setText(f"检测到新版本 v{version}！\n\n更新内容：\n{notes}")
        msg.setIcon(QMessageBox.Information)
        btn_update = msg.addButton("立即更新", QMessageBox.ActionRole)
        msg.addButton("稍后", QMessageBox.RejectRole)
        msg.exec_()
        
        if msg.clickedButton() == btn_update:
            if not getattr(sys, "frozen", False):
                ok = AutoUpdater.install_and_restart("")
                if not ok:
                    QMessageBox.warning(self, "失败", "源码更新失败，请检查 git 是否可用。")
                return
            if not url:
                QMessageBox.warning(self, "错误", "未找到下载链接")
                return
            self._start_update_download(url)

    def _on_update_check_finished(self, success: bool, message: str):
        try:
            if hasattr(self, "statusBar") and self.statusBar():
                self.statusBar().showMessage(f"更新检查：{message}", 5000)
        except Exception:
            pass

    def _start_update_download(self, url):
        """Start downloading the update"""
        self.progress_dlg = QProgressDialog("正在下载更新...", "取消", 0, 100, self)
        self.progress_dlg.setWindowModality(Qt.WindowModal)
        self.progress_dlg.setMinimumDuration(0)
        self.progress_dlg.setValue(0)

        self.downloader = UpdateDownloader(url)
        self.downloader.progress.connect(self._on_download_progress)
        self.downloader.finished.connect(self._on_download_finished)
        self.downloader.start()

        # Connect cancel button
        self.progress_dlg.canceled.connect(self.downloader.terminate)

    def _on_download_progress(self, pct):
        if hasattr(self, 'progress_dlg'):
            self.progress_dlg.setValue(pct)

    def _on_download_finished(self, success, path):
        if hasattr(self, 'progress_dlg'):
            self.progress_dlg.close()
            
        if success:
            reply = QMessageBox.question(
                self, "下载完成", 
                "更新包已就绪，是否立即重启应用进行安装覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if path:
                    AutoUpdater.install_and_restart(path)
                else:
                    QMessageBox.warning(self, "失败", "更新包路径为空")
        else:
            QMessageBox.warning(self, "下载失败", f"更新下载失败：{path}")
    
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

    def _create_lazy(self, module_path, class_name, **kwargs):
        """Helper to create a lazy loaded panel"""
        def factory():
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            return cls(**kwargs)
        return LazyLoader(factory)

    def _init_content_stack(self) -> None:
        """初始化右侧内容栈 (Lazy Loading Mode)"""
        # 定义各模块工厂
        self.dashboard_panel = self._create_lazy("ui.dashboard", "DashboardPanel", parent_nav_callback=self._switch_via_dashboard)
        self.profit_panel = self._create_lazy("ui.profit_analysis", "ProfitAnalysisWidget")
        self.material_factory_panel = self._create_lazy("ui.material_factory", "MaterialFactoryPanel")
        self.crm_panel = self._create_lazy("ui.crm", "CRMWidget")
        self.engagement_panel = self._create_lazy("ui.engagement", "EngagementPanel")
        self.downloader_panel = self._create_lazy("ui.downloader", "DownloaderPanel")
        self.ai_content_factory_panel = self._create_lazy("ui.ai_content_factory", "AIContentFactoryPanel", enable_photo=False, enable_cyborg=False)
        self.cyborg_panel = self._create_lazy("ui.ai_content_factory", "CyborgPanel")
        self.photo_video_panel = self._create_lazy("ui.ai_content_factory", "PhotoVideoPanel")
        self.visual_lab_panel = self._create_lazy("ui.visual_lab", "VisualLabPanel")
        self.lan_airdrop_panel = self._create_lazy("ui.lan_airdrop", "LanAirdropPanel")
        self.diagnostics_panel = self._create_lazy("ui.diagnostics", "DiagnosticsPanel")
        self.settings_panel = self._create_lazy("ui.settings", "SettingsPanel")

        # 顺序必须严格对应 Navigation Index [0..12]
        self.panels_ordered = [
            self.dashboard_panel,           # 0
            self.profit_panel,              # 1
            self.material_factory_panel,    # 2
            self.crm_panel,                 # 3
            self.engagement_panel,          # 4
            self.downloader_panel,          # 5
            self.ai_content_factory_panel,  # 6
            self.cyborg_panel,              # 7
            self.photo_video_panel,         # 8
            self.visual_lab_panel,          # 9
            self.lan_airdrop_panel,         # 10
            self.diagnostics_panel,         # 11
            self.settings_panel             # 12
        ]

        for panel in self.panels_ordered:
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
                ("🐴  半人马拼接", 7),
                ("🖼️  图转视频", 8),
                ("👁️  视觉实验室", 9),
            ]),
            ("💼 电商运营", [
                ("💰  选品清洗池", 1),
            ]),
            ("🛠️ 实用工具", [
                ("⬇️  素材下载器", 5),
                ("📡  局域网空投", 10),
            ]),
            ("🔧 系统管理", [
                ("🧪  诊断中心", 11),
                ("⚙️  系统设置", 12),
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
        
        # 触发延迟加载
        widget = self.stacked_widget.widget(index)
        if isinstance(widget, LazyLoader):
            widget.ensure_loaded()

        self.stacked_widget.setCurrentIndex(index)
        
        # Dashboard auto refresh happens on init, but we could trigger it again
        if index == 0 and hasattr(self.dashboard_panel, "_refresh_ip_status"):
             # self.dashboard_panel._refresh_ip_status() # Optional: auto refresh whenever creating
             pass

        # 局域网空投 (Index=9)：每次进入刷新目录/二维码
        try:
            if getattr(self, "lan_airdrop_panel", None) and index == 9:
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
