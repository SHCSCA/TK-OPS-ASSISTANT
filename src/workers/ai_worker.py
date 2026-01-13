"""AI 文案助手 Worker（QThread）"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal

from workers.base_worker import BaseWorker
from api.ai_assistant import generate_tiktok_copy


class AICopyWorker(BaseWorker):
    """生成标题/标签的后台线程"""

    result_signal = pyqtSignal(dict)

    def __init__(self, desc_cn: str, tone: str):
        super().__init__()
        self.desc_cn = desc_cn
        self.tone = tone

    def _run_impl(self):
        self.emit_log("开始生成 AI 文案...")
        self.emit_progress(10)

        result = generate_tiktok_copy(self.desc_cn, self.tone)

        self.emit_progress(90)
        try:
            self.result_signal.emit(result)
        except Exception:
            pass
        try:
            self.data_signal.emit(result)
        except Exception:
            pass
        self.emit_log("✓ AI 文案生成完成")
        self.emit_progress(100)
        self.emit_finished(True, "AI 文案生成完成")
