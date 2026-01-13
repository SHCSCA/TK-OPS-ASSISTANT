"""诊断中心 UI 面板

提供“一键诊断”能力：展示关键配置、目录可写、依赖/ffmpeg 状态。
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QProgressBar,
    QFrame,
    QApplication,
)

from workers.diagnostics_worker import DiagnosticsWorker
from utils.ui_log import append_log, install_log_context_menu


class DiagnosticsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.worker: DiagnosticsWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("诊断中心")
        title.setObjectName("h1")
        layout.addWidget(title)

        tip = QLabel("用于 EXE 场景快速定位：配置缺失 / 目录不可写 / ffmpeg 不可用 等问题。")
        tip.setProperty("variant", "muted")
        layout.addWidget(tip)

        frame = QFrame()
        frame.setProperty("class", "config-frame")
        frame_layout = QHBoxLayout(frame)

        self.start_button = QPushButton("开始诊断")
        self.start_button.clicked.connect(self.start_diagnostics)
        frame_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_diagnostics)
        self.stop_button.setEnabled(False)
        frame_layout.addWidget(self.stop_button)

        self.copy_button = QPushButton("复制结果")
        self.copy_button.clicked.connect(self.copy_results)
        self.copy_button.setEnabled(False)
        frame_layout.addWidget(self.copy_button)

        frame_layout.addStretch()
        layout.addWidget(frame)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["项目", "状态", "说明", "解决方案"])
        self.table.setRowCount(0)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(160)
        self.log_text.setObjectName("LogView")
        install_log_context_menu(self.log_text)
        layout.addWidget(QLabel("诊断日志:"), 0, Qt.AlignTop)
        layout.addWidget(self.log_text)

        layout.addStretch()
        self.setLayout(layout)

    def start_diagnostics(self):
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.table.setRowCount(0)
        self.log_text.clear()

        self.worker = DiagnosticsWorker()
        self.worker.log_signal.connect(self._on_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.error_signal.connect(self._on_error)
        if hasattr(self.worker, "done_signal"):
            self.worker.done_signal.connect(self._on_done)
        self.worker.finished_signal.connect(self._on_finished)
        if hasattr(self.worker, "data_signal"):
            self.worker.data_signal.connect(self._on_result)
        else:
            self.worker.result_signal.connect(self._on_result)
        self.worker.start()

    def stop_diagnostics(self):
        if self.worker:
            self.worker.stop()
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)

    def _on_log(self, message: str):
        append_log(self.log_text, message, level="INFO")

    def _on_progress(self, progress: int):
        self.progress_bar.setValue(progress)

    def _on_error(self, error_message: str):
        append_log(self.log_text, error_message, level="ERROR")

    def _on_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.copy_button.setEnabled(self.table.rowCount() > 0)

    def _on_done(self, ok: bool, message: str):
        if ok:
            return
        append_log(self.log_text, f"诊断失败：{message}", level="ERROR")

    def _on_result(self, items: list):
        self.table.setRowCount(len(items))
        for row, it in enumerate(items):
            name_item = QTableWidgetItem(str(it.get("name", "")))
            ok = bool(it.get("ok", False))
            status_item = QTableWidgetItem("通过" if ok else "失败")
            msg_item = QTableWidgetItem(str(it.get("message", "")))
            sol_item = QTableWidgetItem(str(it.get("solution", ""))) # 新增

            if ok:
                status_item.setForeground(QColor("#00e676"))
            else:
                status_item.setForeground(QColor("#ff5252"))

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, status_item)
            self.table.setItem(row, 2, msg_item)
            self.table.setItem(row, 3, sol_item) # 新增

        self.table.resizeColumnsToContents()
        self.copy_button.setEnabled(self.table.rowCount() > 0)

    def copy_results(self):
        try:
            lines = []
            for r in range(self.table.rowCount()):
                name = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
                status = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
                msg = self.table.item(r, 2).text() if self.table.item(r, 2) else ""
                lines.append(f"{name}\t{status}\t{msg}")
            text = "\n".join(lines)
            QApplication.clipboard().setText(text)
            append_log(self.log_text, "已复制诊断结果到剪贴板", level="INFO")
        except Exception as e:
            append_log(self.log_text, f"复制失败：{e}", level="WARNING")

    def shutdown(self):
        """窗口关闭时的资源清理。"""
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass
