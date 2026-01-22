"""局域网空投 UI 面板 (V2.0)

- 启动/停止本机 HTTP 服务
- 展示局域网访问地址与二维码
- 列出共享目录文件，支持为单个文件生成直达二维码

注意：Windows 可能弹出防火墙提示，需允许局域网访问。
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QMessageBox,
    QSpinBox,
)

import config
from utils.lan_server import get_lan_server
from utils.ui_log import append_log, install_log_context_menu
from PyQt5.QtWidgets import QTextEdit


class LanAirdropPanel(QWidget):
    """局域网空投"""

    def __init__(self):
        super().__init__()
        self.server = get_lan_server()
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("局域网空投")
        title.setObjectName("h1")
        layout.addWidget(title)

        frame = QFrame()
        frame.setProperty("class", "config-frame")
        form = QVBoxLayout(frame)

        # 共享目录
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("共享目录："))
        default_dir = str(getattr(config, "OUTPUT_DIR", Path("Output")).resolve())
        self.dir_input = QLineEdit(default_dir)
        dir_row.addWidget(self.dir_input, 1)
        pick_btn = QPushButton("选择目录")
        pick_btn.clicked.connect(self._pick_dir)
        dir_row.addWidget(pick_btn)
        form.addLayout(dir_row)

        # 端口
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("端口："))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1025, 65535)
        self.port_spin.setValue(int(getattr(self.server, "port", 8000) or 8000))
        port_row.addWidget(self.port_spin)
        port_row.addStretch(1)
        form.addLayout(port_row)

        # 控制按钮
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("启动服务")
        self.start_btn.setProperty("variant", "primary")
        self.start_btn.clicked.connect(self.start_server)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止服务")
        self.stop_btn.clicked.connect(self.stop_server)
        btn_row.addWidget(self.stop_btn)

        self.open_btn = QPushButton("在浏览器打开")
        self.open_btn.clicked.connect(self.open_in_browser)
        btn_row.addWidget(self.open_btn)

        btn_row.addStretch(1)
        form.addLayout(btn_row)

        # URL
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("访问地址："))
        self.url_label = QLabel("未启动")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        url_row.addWidget(self.url_label, 1)
        form.addLayout(url_row)

        # 二维码
        qr_row = QHBoxLayout()
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setAlignment(Qt.AlignCenter)
        # 使用全局主题样式，避免局部 setStyleSheet 破坏统一外观
        self.qr_label.setObjectName("QrPanel")
        qr_row.addWidget(self.qr_label)

        tips = QLabel(
            "使用方法：\n"
            "1) 点击【启动服务】\n"
            "2) 手机连同一 WiFi，扫码打开\n"
            "3) 可在右侧选择文件生成直达二维码\n\n"
            "提示：首次启动 Windows 可能弹出防火墙询问，请允许“专用网络”。"
        )
        tips.setProperty("variant", "muted")
        qr_row.addWidget(tips, 1)
        form.addLayout(qr_row)

        layout.addWidget(frame)

        # 文件列表 + 日志
        bottom = QHBoxLayout()

        file_box = QVBoxLayout()
        file_box.addWidget(QLabel("共享文件："))
        self.file_list = QListWidget()
        self.file_list.setObjectName("ContentList")
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        file_box.addWidget(self.file_list, 1)

        refresh_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self.refresh)
        refresh_row.addWidget(refresh_btn)
        refresh_row.addStretch(1)
        file_box.addLayout(refresh_row)

        bottom.addLayout(file_box, 1)

        log_box = QVBoxLayout()
        log_box.addWidget(QLabel("运行日志："))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogView")
        install_log_context_menu(self.log_view)
        log_box.addWidget(self.log_view, 1)

        bottom.addLayout(log_box, 1)

        layout.addLayout(bottom, 1)

        self.setLayout(layout)

    def _append(self, text: str, level: str = "INFO") -> None:
        append_log(self.log_view, text, level=level)

    def _pick_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择共享目录",
            self.dir_input.text().strip() or str(getattr(config, "OUTPUT_DIR", Path("Output"))),
        )
        if directory:
            self.dir_input.setText(directory)
            self.refresh()

    def refresh(self) -> None:
        # 更新按钮状态
        running = bool(getattr(self.server, "running", False))
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.open_btn.setEnabled(running)

        # 刷新 URL 与二维码
        url = self.server.get_url() if running else None
        self.url_label.setText(url or "未启动")

        pixmap = self.server.generate_qrcode() if running else None
        if pixmap:
            self.qr_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.qr_label.setText("(未启动)\n二维码")

        # 刷新文件列表
        self.file_list.clear()
        directory = self.dir_input.text().strip()
        if not directory or not os.path.isdir(directory):
            return

        try:
            p = Path(directory)
            files = [f for f in p.iterdir() if f.is_file()]
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            for f in files[:200]:
                item = QListWidgetItem(f.name)
                item.setData(Qt.UserRole, str(f))
                self.file_list.addItem(item)
        except Exception as e:
            self._append(f"读取目录失败：{e}", level="ERROR")

    def start_server(self) -> None:
        directory = self.dir_input.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(self, "目录不可用", "请选择存在的共享目录。")
            return

        self.server.directory = os.path.abspath(directory)
        self.server.port = int(self.port_spin.value())

        ok = self.server.start()
        if not ok:
            QMessageBox.warning(self, "启动失败", "局域网服务启动失败，请查看日志或尝试换一个端口。")
            self._append("局域网服务启动失败（可能端口被占用或权限不足）", level="ERROR")
            return

        self._append(f"服务已启动：{self.server.get_url()}")
        self.refresh()

    def stop_server(self) -> None:
        try:
            self.server.stop()
            self._append("服务已停止")
        except Exception as e:
            self._append(f"停止服务失败：{e}", level="ERROR")
        self.refresh()

    def open_in_browser(self) -> None:
        url = self.server.get_url()
        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))

    def _on_file_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if not current:
            return
        if not getattr(self.server, "running", False):
            return

        path = current.data(Qt.UserRole)
        if not path:
            return

        file_name = Path(path).name
        pixmap = self.server.generate_qrcode(file_name=file_name)
        if pixmap:
            self.qr_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._append(f"已生成文件直达二维码：{file_name}")

    def shutdown(self) -> None:
        # 窗口关闭时不强制停止：由 MainWindow.closeEvent 统一管理
        pass
