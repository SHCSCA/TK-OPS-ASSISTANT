"""
Dashboard Panel (Home Page)
工作台 / 仪表盘

Features:
- Global Status Overview (IP, System)
- Quick Access to core modules
- Recent activity summary (Optional)
"""
import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QGridLayout, QPushButton, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont

import config
from api.ip_detector import check_ip_safety
from ui.toast import Toast

class StatCard(QFrame):
    """Simple Statistic Card"""
    def __init__(self, title, value, icon=None, variant="default"):
        super().__init__()
        self.setProperty("class", "card")
        self.setFixedWidth(240)
        self.setFixedHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel(title)
        lbl_title.setProperty("variant", "muted")
        layout.addWidget(lbl_title)
        
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("font-size: 24px; font-weight: bold; color: #00e676;") 
        # Note: color hardcoded for now or use objectName "h1" if mapped
        layout.addWidget(self.lbl_value)
        
        layout.addStretch()

class DashboardPanel(QWidget):
    def __init__(self, parent_nav_callback=None):
        super().__init__()
        self.parent_nav_callback = parent_nav_callback # Func to switch tabs
        self._init_ui()
        
        # Auto refresh IP on load (delayed)
        QTimer.singleShot(500, self._refresh_ip_status)

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 1. Header
        header_layout = QHBoxLayout()
        
        title_box = QVBoxLayout()
        h1 = QLabel("工作台")
        h1.setObjectName("h1")
        title_box.addWidget(h1)
        
        date_str = datetime.datetime.now().strftime("%Y年%m月%d日 %A")
        sub = QLabel(f"欢迎回来，今日是 {date_str}")
        sub.setProperty("variant", "muted")
        title_box.addWidget(sub)
        
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        # 2. Key Metrics Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(20)
        
        # IP Card (Dynamic)
        self.card_ip = StatCard("当前网络环境", "检测中...")
        metrics_layout.addWidget(self.card_ip)
        
        # Output Dir Info
        out_count = self._count_output_files()
        self.card_files = StatCard("今日产出素材", f"{out_count} 个")
        metrics_layout.addWidget(self.card_files)
        
        # System status
        self.card_sys = StatCard("系统状态", "运行正常")
        metrics_layout.addWidget(self.card_sys)
        
        metrics_layout.addStretch()
        layout.addLayout(metrics_layout)

        # 3. Quick Access
        layout.addWidget(QLabel("快速开始"))
        
        quick_grid = QGridLayout()
        quick_grid.setSpacing(15)
        
        # Buttons definition: (Title, Icon emoji, Target Index)
        # Indexes based on main_window.py _on_nav_changed 
        # (Check main_window.py for mapping)
        actions = [
            ("素材工厂", "🎬", 2, "primary"),
            ("素材下载", "⬇️", 5, "default"),
            ("选品清洗", "💰", 1, "default"),
            ("AI 二创", "🧠", 6, "default"),
        ]
        
        for i, (text, icon, idx, variant) in enumerate(actions):
            btn = QPushButton(f"  {icon}  {text}")
            btn.setFixedSize(160, 60)
            btn.setProperty("variant", variant if variant != "default" else "")
            btn.clicked.connect(lambda checked, ix=idx: self._nav_to(ix))
            quick_grid.addWidget(btn, 0, i)
            
        # Add a refresh button for IP
        btn_refresh = QPushButton("🔄 刷新网络状态")
        btn_refresh.setFixedSize(160, 60)
        btn_refresh.clicked.connect(self._refresh_ip_status)
        quick_grid.addWidget(btn_refresh, 0, 4)
        
        layout.addLayout(quick_grid)
        layout.addStretch()
        
        self.setLayout(layout)

    def _nav_to(self, index):
        if self.parent_nav_callback:
            self.parent_nav_callback(index)

    def _refresh_ip_status(self):
        self.card_ip.lbl_value.setText("检测中...")
        self.card_ip.lbl_value.setStyleSheet("font-size: 24px; font-weight: bold; color: #bdc3c7;")
        QApplication.processEvents()
        
        is_safe, msg = check_ip_safety()
        
        # Shorten message for card
        display_text = "安全 (US)" if is_safe else "风险"
        if "CN_IP" in msg: display_text = "风险 (CN)"
        
        color = "#00e676" if is_safe else "#ff5252"
        self.card_ip.lbl_value.setText(display_text)
        self.card_ip.lbl_value.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        
        # Update main window status bar too via callback if needed, but not implemented here.
        # Just show toast
        if is_safe:
             Toast.show_success(self.window(), f"网络环境安全: {msg}")
        else:
             Toast.show_warning(self.window(), f"网络环境风险: {msg}")

    def _count_output_files(self):
        # Quick check of output dir
        try:
            p = Path(config.OUTPUT_DIR)
            if not p.exists(): return 0
            # Count files modified today
            # minimal implementation
            today = datetime.datetime.now().date()
            count = 0
            # Only checking top level or one level deep to avoid perf hit
            for f in p.glob("*/*"):
                if f.is_file():
                    mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).date()
                    if mtime == today:
                        count += 1
            return count
        except Exception:
            return 0
