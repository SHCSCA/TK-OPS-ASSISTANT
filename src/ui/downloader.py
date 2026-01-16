"""万能素材采集器（下载器）UI 面板

- 输入多条链接（每行 1 条）
- 后台线程下载（yt-dlp）
- 展示任务状态、进度、保存路径与日志
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QFrame,
    QTextEdit,
    QLineEdit,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QSizePolicy,
)

import config
from utils.ui_log import append_log, install_log_context_menu
from workers.download_worker import DownloadWorker


class DownloaderPanel(QWidget):
    """素材采集器面板"""

    def __init__(self):
        super().__init__()
        self.worker: DownloadWorker | None = None
        self._clipboard_timer: QTimer | None = None
        self._last_clipboard_text: str = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("万能素材采集器")
        title.setObjectName("h1")
        layout.addWidget(title)

        tip = QLabel(
            "用途：输入链接批量下载视频素材（支持剪贴板监听）。\n"
            "默认下载到【素材库】目录；可在【系统设置 → 下载目录】修改。"
        )
        tip.setProperty("variant", "muted")
        layout.addWidget(tip)

        config_frame = QFrame()
        config_frame.setProperty("class", "config-frame")
        config_layout = QHBoxLayout(config_frame)

        # 左侧：目录信息 + 按钮
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.addWidget(QLabel("下载目录："))

        self.output_dir = str(config.DOWNLOAD_DIR)
        self.output_dir_label = QLabel(self.output_dir)
        self.output_dir_label.setProperty("variant", "muted")
        self.output_dir_label.setWordWrap(True)
        self.output_dir_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.output_dir_label.setToolTip(self.output_dir)
        left_col.addWidget(self.output_dir_label)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("选择...")
        browse_btn.clicked.connect(self._choose_dir)
        btn_row.addWidget(browse_btn)

        open_btn = QPushButton("打开目录")
        open_btn.clicked.connect(self._open_dir)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        left_col.addLayout(btn_row)

        config_layout.addLayout(left_col, 2)

        # 右侧：选项
        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        self.no_watermark_checkbox = QCheckBox("去水印（尽力获取无水印源）")
        self.no_watermark_checkbox.setChecked(False)
        right_col.addWidget(self.no_watermark_checkbox)

        self.clipboard_checkbox = QCheckBox("监听剪贴板（自动识别链接）")
        self.clipboard_checkbox.setChecked(False)
        self.clipboard_checkbox.toggled.connect(self._toggle_clipboard_listener)
        right_col.addWidget(self.clipboard_checkbox)

        self.archive_checkbox = QCheckBox("自动归档到素材库")
        self.archive_checkbox.setChecked(True)
        right_col.addWidget(self.archive_checkbox)

        right_col.addStretch()
        config_layout.addLayout(right_col, 1)

        layout.addWidget(config_frame)

        layout.addWidget(QLabel("粘贴视频链接（每行 1 条）："))
        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText("示例：\nhttps://www.tiktok.com/...\nhttps://youtu.be/...\n")
        self.urls_input.setMaximumHeight(120)
        layout.addWidget(self.urls_input)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始下载")
        self.start_btn.clicked.connect(self.start_download)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_download)
        btn_row.addWidget(self.stop_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["序号", "链接", "状态", "进度", "文件"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        layout.addWidget(QLabel("运行日志："))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(160)
        self.log_text.setObjectName("LogView")
        install_log_context_menu(self.log_text)
        layout.addWidget(self.log_text)

        layout.addStretch()
        self.setLayout(layout)

    def _choose_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择下载目录", self.output_dir or str(config.DOWNLOAD_DIR))
        if directory:
            self.output_dir = directory
            self.output_dir_label.setText(directory)
            self.output_dir_label.setToolTip(directory)

    def _open_dir(self):
        path = (self.output_dir or "").strip() or str(config.DOWNLOAD_DIR)
        if not path:
            return
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except Exception as e:
            self._log(f"✗ 打开目录失败：{e}")

    def _parse_urls(self) -> List[str]:
        text = self.urls_input.toPlainText().strip()
        if not text:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _log(self, message: str):
        append_log(self.log_text, message, level="INFO")

    def start_download(self):
        urls = self._parse_urls()
        output_dir = (self.output_dir or "").strip() or str(config.DOWNLOAD_DIR)
        prefer_no_watermark = self.no_watermark_checkbox.isChecked()
        archive_enabled = self.archive_checkbox.isChecked()

        self.table.setRowCount(len(urls))
        for i, url in enumerate(urls):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(url))
            self.table.setItem(i, 2, QTableWidgetItem("等待"))
            self.table.setItem(i, 3, QTableWidgetItem("0%"))
            self.table.setItem(i, 4, QTableWidgetItem(""))

        self.log_text.clear()
        self.progress_bar.setValue(0)
        self._log(f"下载目录：{output_dir}")

        self.worker = DownloadWorker(
            urls=urls,
            output_dir=output_dir,
            prefer_no_watermark=prefer_no_watermark,
            archive_enabled=archive_enabled,
            archive_root=str(getattr(config, "ASSET_LIBRARY_DIR", "")) or None,
        )
        self.worker.log_signal.connect(lambda m: append_log(self.log_text, m, level="INFO"))
        self.worker.error_signal.connect(lambda m: append_log(self.log_text, m, level="ERROR"))
        self.worker.progress_signal.connect(self.progress_bar.setValue)

        self.worker.item_status_signal.connect(self._on_item_status)
        self.worker.item_progress_signal.connect(self._on_item_progress)
        self.worker.item_file_signal.connect(self._on_item_file)
        if hasattr(self.worker, "done_signal"):
            self.worker.done_signal.connect(self._on_done)
        self.worker.finished_signal.connect(self._on_finished)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.worker.start()

    def stop_download(self):
        if self.worker:
            self.worker.stop()
        self.stop_btn.setEnabled(False)

    def _on_item_status(self, row: int, status: str):
        item = QTableWidgetItem(status)
        self.table.setItem(row, 2, item)

    def _on_item_progress(self, row: int, progress: int):
        self.table.setItem(row, 3, QTableWidgetItem(f"{progress}%"))

    def _on_item_file(self, row: int, filename: str):
        self.table.setItem(row, 4, QTableWidgetItem(filename))

    def _on_finished(self):
        self._log("✓ 下载任务已结束")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker = None

    def _on_done(self, ok: bool, message: str):
        if ok:
            return
        append_log(self.log_text, f"任务失败：{message}", level="ERROR")

    def _toggle_clipboard_listener(self, enabled: bool):
        if enabled:
            if not self._clipboard_timer:
                self._clipboard_timer = QTimer(self)
                self._clipboard_timer.setInterval(800)
                self._clipboard_timer.timeout.connect(self._poll_clipboard)
            self._last_clipboard_text = ""
            self._clipboard_timer.start()
            append_log(self.log_text, "已开启剪贴板监听", level="INFO")
        else:
            if self._clipboard_timer:
                self._clipboard_timer.stop()
            append_log(self.log_text, "已关闭剪贴板监听", level="INFO")

    def _poll_clipboard(self):
        try:
            clip = QApplication.clipboard()
            text = (clip.text() or "").strip()
        except Exception:
            return

        if not text or text == self._last_clipboard_text:
            return

        self._last_clipboard_text = text
        # 简单提取：包含 http(s) 的行按行加入
        candidates = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("http")]
        if not candidates:
            return

        existing = set(self._parse_urls())
        new_urls = [u for u in candidates if u not in existing]
        if not new_urls:
            return

        current = self.urls_input.toPlainText().strip()
        append_text = "\n".join(new_urls)
        if current:
            self.urls_input.setPlainText(current + "\n" + append_text + "\n")
        else:
            self.urls_input.setPlainText(append_text + "\n")
        self._log(f"[INFO] 从剪贴板新增 {len(new_urls)} 条链接")

    def shutdown(self):
        """窗口关闭时的资源清理：停止剪贴板监听与后台线程。"""
        try:
            if self._clipboard_timer:
                self._clipboard_timer.stop()
        except Exception:
            pass
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass
