from __future__ import annotations

from pathlib import Path

import config

from .edge_provider import synthesize_edge_tts
from .types import TtsError
from .volcengine_provider import synthesize_volcengine_token


def synthesize(
    text: str,
    out_path: Path,
    provider: str | None = None,
    emotion: str | None = None,
    speed_text: str | None = None,
) -> None:
    """统一入口：根据 provider 调用不同实现。"""
    p = (provider or getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip().lower()

    if p in ("edge", "edge-tts", "edgetts"):
        voice = (getattr(config, "TTS_VOICE", "en-US-AvaNeural") or "en-US-AvaNeural").strip()
        speed = (speed_text or str(getattr(config, "TTS_SPEED", "1.1") or "1.1")).strip()
        synthesize_edge_tts(text=text, out_path=out_path, voice=voice, speed_text=speed)
        return

    if p in ("volcengine", "doubao", "bytedance", "volc"):
        # Token 模式（OpenSpeech 风格）
        appid = getattr(config, "VOLC_TTS_APPID", "")
        token = config.get_volc_tts_token()
        cluster = getattr(config, "VOLC_TTS_CLUSTER", "volcano_tts")
        voice_type = getattr(config, "VOLC_TTS_VOICE_TYPE", "")
        encoding = getattr(config, "VOLC_TTS_ENCODING", "mp3")
        endpoint = getattr(config, "VOLC_TTS_ENDPOINT", "https://openspeech.bytedance.com/api/v1/tts")
        speed = (speed_text or str(getattr(config, "TTS_SPEED", "1.1") or "1.1")).strip()

        synthesize_volcengine_token(
            text=text,
            out_path=out_path,
            appid=str(appid),
            token=str(token),
            voice_type=str(voice_type),
            speed_text=speed,
            cluster=str(cluster),
            encoding=str(encoding),
            endpoint=str(endpoint),
            emotion=(emotion or "").strip(),
        )
        return

    raise TtsError(f"不支持的 TTS_PROVIDER：{p}")
