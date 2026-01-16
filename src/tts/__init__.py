"""TTS Provider Layer

说明：
- 提供可扩展的 TTS 适配层，避免业务 Worker 直接耦合某个第三方。
- 当前支持：edge-tts、volcengine（豆包/火山：Token 模式）
"""

from .types import TtsError, TtsForbiddenError
from .router import synthesize

__all__ = [
    "TtsError",
    "TtsForbiddenError",
    "synthesize",
]
