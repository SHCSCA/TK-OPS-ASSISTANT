"""
互动/获客中心 (Engagement Center)
专注处理评论监控、关键词截流、私信任务
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, 
    QFrame, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QSize
import config
from utils.ui_log import append_log
import services.browser_manager
from workers.comment_monitor_worker import CommentMonitorWorker

class EngagementPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.worker: CommentMonitorWorker | None = None
        self._init_ui()
        self._init_timers()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        title = QLabel("互动/获客中心")
        title.setObjectName("h1")
        layout.addWidget(title)
        
        tip = QLabel("监控评论区关键词，发掘潜在客户；管理自动私信与互动任务。")
        tip.setProperty("variant", "muted")
        layout.addWidget(tip)

        # 1. 评论监控区域
        self._init_comment_section(layout)

        # 2. 私信/任务队列区域
        self._init_dm_section(layout)

        layout.addStretch()

    def _init_comment_section(self, parent_layout):
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title Row
        head_row = QHBoxLayout()
        ico = QLabel("💬")
        ico.setStyleSheet("font-size: 18px;")
        head_row.addWidget(ico)
        
        h2 = QLabel("评论区关键词监控 (V3.0 实战版)")
        h2.setObjectName("h2")
        head_row.addWidget(h2)
        head_row.addStretch()
        layout.addLayout(head_row)

        desc = QLabel(
            "说明：基于 Playwright 浏览器自动化技术，无需 API Key。\n"
            "输入目标视频链接，系统将自动访问并实时抓取命中关键词的评论。"
        )
        desc.setProperty("variant", "muted")
        layout.addWidget(desc)
        
        # Controls
        # Row 1: Target URL
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("监控视频链接:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.tiktok.com/@user/video/123456... (必须是公开视频)")
        url_row.addWidget(self.url_input, 1)
        layout.addLayout(url_row)
        
        # Row 2: Keywords & Button
        kw_row = QHBoxLayout()
        kw_row.addWidget(QLabel("监控关键词 (逗号分隔):"))
        self.kw_input = QLineEdit()
        self.kw_input.setPlaceholderText("例如: price, want, link, 多少钱, 哪里买")
        try:
            self.kw_input.setText(getattr(config, "COMMENT_WATCH_KEYWORDS", "want,need,price"))
        except:
            pass
        kw_row.addWidget(self.kw_input, 1)
        
        self.btn_monitor = QPushButton("启动监控")
        self.btn_monitor.setProperty("variant", "primary")
        self.btn_monitor.setCheckable(True)
        self.btn_monitor.toggled.connect(self._toggle_monitor)
        kw_row.addWidget(self.btn_monitor)
        
        layout.addLayout(kw_row)
        
        # Results List
        self.comment_list = QListWidget()
        self.comment_list.setObjectName("ContentList")
        self.comment_list.setMinimumHeight(200)
        layout.addWidget(self.comment_list)
        
        parent_layout.addWidget(frame)

    def _init_dm_section(self, parent_layout):
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title Row
        head_row = QHBoxLayout()
        ico = QLabel("📩")
        ico.setStyleSheet("font-size: 18px;")
        head_row.addWidget(ico)
        
        h2 = QLabel("私信/跟进任务")
        h2.setObjectName("h2")
        head_row.addWidget(h2)
        head_row.addStretch()
        layout.addLayout(head_row)
        
        # Tools
        tool_row = QHBoxLayout()
        btn_refresh = QPushButton("刷新队列")
        btn_refresh.clicked.connect(self._refresh_dm_tasks)
        tool_row.addWidget(btn_refresh)
        
        btn_mark = QPushButton("标记为已处理")
        btn_mark.clicked.connect(self._mark_done)
        tool_row.addWidget(btn_mark)
        tool_row.addStretch()
        layout.addLayout(tool_row)
        
        # List
        self.dm_list = QListWidget()
        self.dm_list.setObjectName("ContentList")
        self.dm_list.setMinimumHeight(150)
        layout.addWidget(self.dm_list)
        
        parent_layout.addWidget(frame)

    def _init_timers(self):
        # V3.0: 移除轮询 Timer，改用 Worker 信号驱动
        pass

    def _toggle_monitor(self, active):
        if active:
            url = self.url_input.text().strip()
            keywords = [k.strip() for k in self.kw_input.text().split(",") if k.strip()]
            
            if not url:
                QMessageBox.warning(self, "参数缺失", "请先输入要监控的视频链接(URL)")
                # Reset button state without triggering toggled if possible, or just return
                self.btn_monitor.setChecked(False) # This will re-trigger toggle(False)
                return
            
            if not keywords:
                QMessageBox.warning(self, "参数缺失", "请至少输入一个监控关键词")
                self.btn_monitor.setChecked(False)
                return

            self.btn_monitor.setText("监控运行中 (点击停止)")
            self.btn_monitor.setProperty("variant", "danger") 
            
            # Start Worker
            self._start_worker(url, keywords)

        else:
            self.btn_monitor.setText("启动监控")
            self.btn_monitor.setProperty("variant", "primary")
            self._stop_worker()
        
        # Refresh style
        self.btn_monitor.style().unpolish(self.btn_monitor)
        self.btn_monitor.style().polish(self.btn_monitor)

    def _start_worker(self, url, keywords):
        self.worker = CommentMonitorWorker(url, keywords)
        self.worker.log_signal.connect(self._add_log_item)
        self.worker.new_comment_signal.connect(self._on_new_comment)
        # finished_signal 在 BaseWorker 中定义为无参数 pyqtSignal()
        # done_signal 是 (bool, str)，包含结果信息
        self.worker.done_signal.connect(self._on_monitor_done)
        self.worker.start()
        
        from ui.toast import Toast
        Toast.show_success(self, "监控服务已启动: 浏览器内核初始化中...")

    def _stop_worker(self):
        if self.worker:
            self.worker.stop()
            self._add_log_item("🛑 [系统] 正在停止监控服务...")
            # Worker will emit finished signal which calls _on_monitor_finished

    def _on_monitor_done(self, ok, msg):
        self._add_log_item(f"🏁 {msg}")
        if self.btn_monitor.isChecked():
             self.btn_monitor.setChecked(False) # Reset UI
        self.worker = None

    def _on_new_comment(self, user, text, timestamp):
        # 1. Log visually
        log_msg = f"🔥 [{timestamp}] @{user}: {text}"
        self._add_log_item(log_msg)
        
        # 2. Add to Task List
        task_text = f"@{user}: {text[:50]}... [来自: 关键词命中]"
        self.dm_list.addItem(task_text)
        
        # 3. Toast
        # from ui.toast import Toast
        # Toast.show_info(self, f"发现新线索: @{user}")

    def _poll_logic(self):
        # Deprecated in V3.0
        pass

    def _add_log_item(self, text):
        item = QListWidgetItem(text)
        self.comment_list.insertItem(0, item)
        # 保持列表不过长
        if self.comment_list.count() > 200:
            self.comment_list.takeItem(200)
        
    def _refresh_dm_tasks(self):
        # Mock reload from DB
        self.dm_list.clear()
        # Item: "User @abc asked about price [Pending]" 
        pass

    def _mark_done(self):
        item = self.dm_list.currentItem()
        if item:
            row = self.dm_list.row(item)
            self.dm_list.takeItem(row)
