"""视觉实验室（视频拆解与脚本反推）"""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFileDialog,
    QDoubleSpinBox,
    QFrame,
)

from workers.visual_analysis_worker import VisualAnalysisWorker
from utils.ui_log import append_log, install_log_context_menu


class VisualLabPanel(QWidget):
    """视觉实验室 UI 面板"""

    def __init__(self) -> None:
        super().__init__()
        self.worker: VisualAnalysisWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("视觉实验室")
        title.setObjectName("h1")
        layout.addWidget(title)

        desc = QLabel("用途：上传竞品视频，自动抽帧并反推拍摄脚本，识别前三秒视觉钩子。")
        desc.setProperty("variant", "muted")
        layout.addWidget(desc)

        config_frame = QFrame()
        config_frame.setProperty("class", "config-frame")
        form = QVBoxLayout(config_frame)

        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("视频文件："))
        self.video_path_input = QLineEdit()
        self.video_path_input.setPlaceholderText("请选择 .mp4/.mov/... 文件")
        row_video.addWidget(self.video_path_input, 1)
        pick_btn = QPushButton("选择视频")
        pick_btn.clicked.connect(self._pick_video)
        row_video.addWidget(pick_btn)
        form.addLayout(row_video)

        row_interval = QHBoxLayout()
        row_interval.addWidget(QLabel("抽帧间隔(秒)："))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 10.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setValue(2.0)
        row_interval.addWidget(self.interval_spin)
        row_interval.addStretch(1)
        form.addLayout(row_interval)

        row_btn = QHBoxLayout()
        self.start_btn = QPushButton("开始拆解")
        self.start_btn.setProperty("variant", "primary")
        self.start_btn.clicked.connect(self._start_analysis)
        row_btn.addWidget(self.start_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._stop_analysis)
        self.stop_btn.setEnabled(False)
        row_btn.addWidget(self.stop_btn)
        row_btn.addStretch(1)
        form.addLayout(row_btn)

        layout.addWidget(config_frame)

        result_frame = QFrame()
        result_frame.setProperty("class", "config-frame")
        result_layout = QVBoxLayout(result_frame)
        result_layout.addWidget(QLabel("分析结果："))
        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setMinimumHeight(240)
        result_layout.addWidget(self.result_view)
        layout.addWidget(result_frame)

        log_frame = QFrame()
        log_frame.setProperty("class", "config-frame")
        log_layout = QVBoxLayout(log_frame)
        log_layout.addWidget(QLabel("运行日志："))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogView")
        self.log_view.setMinimumHeight(180)
        install_log_context_menu(self.log_view)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_frame)

        layout.addStretch(1)
        self.setLayout(layout)

    def _pick_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)",
        )
        if file_path:
            self.video_path_input.setText(file_path)

    def _start_analysis(self) -> None:
        video_path = (self.video_path_input.text() or "").strip()
        if not video_path:
            append_log(self.log_view, "请先选择视频文件", level="WARNING")
            return
        if not Path(video_path).exists():
            append_log(self.log_view, "视频文件不存在", level="ERROR")
            return

        self.result_view.clear()
        self.log_view.clear()
        append_log(self.log_view, "开始视觉分析...")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.worker = VisualAnalysisWorker(
            video_path=video_path,
            interval_sec=float(self.interval_spin.value()),
        )
        self.worker.log_signal.connect(lambda m: append_log(self.log_view, m))
        self.worker.data_signal.connect(self._on_result)
        self.worker.done_signal.connect(self._on_done)
        self.worker.start()

    def _stop_analysis(self) -> None:
        if self.worker:
            try:
                self.worker.stop()
            except Exception:
                pass
        append_log(self.log_view, "已发送停止信号", level="WARNING")

    def _on_result(self, text: object) -> None:
        try:
            self.result_view.setPlainText(str(text or ""))
        except Exception:
            pass

    def _on_done(self, ok: bool, message: str) -> None:
        if message:
            append_log(self.log_view, message, level="INFO" if ok else "ERROR")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker = None
