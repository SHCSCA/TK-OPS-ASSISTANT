from __future__ import annotations

import asyncio
from pathlib import Path

from .types import TtsError, TtsForbiddenError


def _speed_to_rate(speed_text: str) -> str:
    """把倍率（如 1.1）转换为 edge-tts rate（如 +10%）。"""
    try:
        s = float(speed_text)
    except Exception:
        s = 1.0
    delta = int(round((s - 1.0) * 100))
    if delta == 0:
        return "+0%"
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta}%"


def synthesize_edge_tts(text: str, out_path: Path, voice: str, speed_text: str) -> None:
    try:
        import edge_tts  # type: ignore
    except Exception as e:
        raise TtsError(f"edge-tts 不可用：{e}")

    async def _run():
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=_speed_to_rate(speed_text))
        await communicate.save(str(out_path))

    try:
        asyncio.run(_run())
    except Exception as e:
        msg = str(e)
        if "403" in msg or "Invalid response status" in msg:
            raise TtsForbiddenError(msg)
        raise TtsError(msg)
