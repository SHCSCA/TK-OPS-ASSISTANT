from __future__ import annotations


class TtsError(RuntimeError):
    """TTS 合成失败的统一异常。"""


class TtsForbiddenError(TtsError):
    """服务端拒绝（常见 401/403/风控）。"""
