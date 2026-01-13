"""AI 爆款文案/标签助手 UI 面板"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QComboBox,
    QFrame,
)

from workers.ai_worker import AICopyWorker
from utils.ui_log import append_log, install_log_context_menu


class AICopywriterPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.worker: AICopyWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("AI 爆款文案助手")
        title.setObjectName("h1")
        layout.addWidget(title)

        input_frame = QFrame()
        input_frame.setProperty("class", "config-frame")
        input_layout = QVBoxLayout(input_frame)

        input_layout.addWidget(QLabel("中文描述（越具体越好）："))
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("例：\n女生宿舍用的小型风扇，静音、续航长、夹子可夹在床边...\n")
        self.desc_input.setMaximumHeight(140)
        input_layout.addWidget(self.desc_input)

        row = QHBoxLayout()
        row.addWidget(QLabel("语气："))
        self.tone_combo = QComboBox()
        self.tone_combo.addItems([
            "幽默种草",
            "强促销",
            "悬疑反转",
            "专业测评",
            "情绪共鸣",
        ])
        row.addWidget(self.tone_combo)

        self.gen_btn = QPushButton("生成文案")
        self.gen_btn.clicked.connect(self.generate)
        row.addWidget(self.gen_btn)

        row.addStretch()
        input_layout.addLayout(row)

        layout.addWidget(input_frame)

        layout.addWidget(QLabel("输出："))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("LogView")
        install_log_context_menu(self.output)
        layout.addWidget(self.output)

        layout.addStretch()
        self.setLayout(layout)

    def _append(self, text: str):
        append_log(self.output, text, level="INFO")

    def generate(self):
        if self.worker:
            return

        desc = self.desc_input.toPlainText().strip()
        tone = self.tone_combo.currentText().strip()

        self.output.clear()
        self._append("正在生成，请稍候...")

        self.worker = AICopyWorker(desc_cn=desc, tone=tone)
        self.worker.log_signal.connect(self._append)
        self.worker.error_signal.connect(lambda m: self._append(f"✗ {m}"))
        # 统一结果信号：优先 data_signal，兼容旧 result_signal
        if hasattr(self.worker, "data_signal"):
            self.worker.data_signal.connect(self._on_result)
        else:
            self.worker.result_signal.connect(self._on_result)

        if hasattr(self.worker, "done_signal"):
            self.worker.done_signal.connect(self._on_done)
        self.worker.finished_signal.connect(self._on_finished)

        self.gen_btn.setEnabled(False)
        self.worker.start()

    def _on_result(self, data: dict):
        titles = data.get("titles") or []
        hashtags = data.get("hashtags") or []
        notes = data.get("notes") or []

        self._append("\n【标题（Titles）】")
        for i, t in enumerate(titles, 1):
            self._append(f"{i}. {t}")

        self._append("\n【标签（Hashtags）】")
        if hashtags:
            self._append(" ".join(hashtags))

        self._append("\n【拍摄/剪辑建议（Notes）】")
        for i, n in enumerate(notes, 1):
            self._append(f"{i}. {n}")

    def _on_finished(self):
        self.gen_btn.setEnabled(True)
        self.worker = None

    def _on_done(self, ok: bool, message: str):
        if ok:
            return
        append_log(self.output, f"任务失败：{message}", level="ERROR")

    def shutdown(self):
        """窗口关闭时的资源清理。"""
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass
