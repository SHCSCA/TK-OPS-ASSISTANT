from __future__ import annotations

import base64
import uuid
from pathlib import Path

import requests

from .types import TtsError, TtsForbiddenError


def _clamp_speed(speed_text: str) -> float:
    """将倍率（1.0 正常）映射到火山 speed_ratio。"""
    try:
        v = float(speed_text)
    except Exception:
        v = 1.0
    # 常见允许范围大约 0.5 ~ 2.0，这里做保守夹紧
    if v < 0.5:
        v = 0.5
    if v > 2.0:
        v = 2.0
    return v


def _looks_like_base64(s: str) -> bool:
    if not s:
        return False
    t = s.strip()
    # base64 通常较长，且只包含 A-Z a-z 0-9 + / =
    # 这里不要设太高阈值：测试/短文本合成可能返回很短的 base64
    if len(t) < 4:
        return False
    for ch in t:
        if not (
            "A" <= ch <= "Z"
            or "a" <= ch <= "z"
            or "0" <= ch <= "9"
            or ch in "+/="
        ):
            return False
    return True


def _extract_audio_base64(payload) -> str:
    """从火山返回 JSON 中提取 base64 音频。

    兼容：
    - data 为字符串：{"data": "<b64>"}
    - data 为对象：{"data": {"audio": "<b64>"}} 或其它嵌套
    """

    if payload is None:
        return ""

    # 常见一层
    if isinstance(payload, dict):
        for key in ("data", "audio", "audio_data", "speech", "result"):
            if key in payload:
                v = payload.get(key)
                if isinstance(v, str) and _looks_like_base64(v):
                    return v
                # 继续向下找
                nested = _extract_audio_base64(v)
                if nested:
                    return nested
        # 遍历所有值兜底
        for v in payload.values():
            nested = _extract_audio_base64(v)
            if nested:
                return nested
        return ""

    if isinstance(payload, list):
        for it in payload:
            nested = _extract_audio_base64(it)
            if nested:
                return nested
        return ""

    if isinstance(payload, str) and _looks_like_base64(payload):
        return payload

    return ""


def _emotion_to_instruction(emotion: str) -> str:
    """将情绪标签映射为豆包 TTS 2.0 语音指令。

    说明：豆包 TTS 2.0 支持通过文本内嵌 [#指令] 控制语气/情绪。
    - 输入可为英文情绪标签（happy/sad/angry/surprise/neutral）
    - 也可直接传入自定义中文指令（不含包裹符号时自动加 [#...]）
    """
    emo = (emotion or "").strip()
    if not emo:
        return ""

    # 如果调用方已经传入完整指令片段，直接透传
    if emo.startswith("[#") and emo.endswith("]"):
        return emo

    mapping = {
        "happy": "用开心、轻快、热情的语气说",
        "sad": "用低落、缓慢、带点哽咽的语气说",
        "angry": "用生气、强调、有压迫感的语气说",
        "surprise": "用惊讶、语调上扬的语气说",
        "neutral": "用平静、自然的语气说",
    }

    mapped = mapping.get(emo.lower())
    if mapped:
        return f"[# {mapped}]"

    # 自定义情绪：自动加指令包装
    return f"[# {emo}]"


def synthesize_volcengine_token(
    text: str,
    out_path: Path,
    appid: str,
    token: str,
    voice_type: str,
    speed_text: str,
    cluster: str = "volcano_tts",
    encoding: str = "mp3",
    endpoint: str = "https://openspeech.bytedance.com/api/v1/tts",
    uid: str = "tk-ops-pro",
    emotion: str = "",
) -> None:
    """豆包/火山 TTS（Token 模式）。

    说明：该模式使用 OpenSpeech 风格接口：appid + token。
    成功返回 data(base64) 音频。
    """

    appid = (appid or "").strip()
    token = (token or "").strip()
    voice_type = (voice_type or "").strip()

    if not appid or not token:
        raise TtsError("缺少 VOLC_TTS_APPID / VOLC_TTS_ACCESS_TOKEN（或旧键 VOLC_TTS_TOKEN）")
    if not voice_type:
        raise TtsError("缺少 VOLC_TTS_VOICE_TYPE（火山音色）")

    payload = {
        "app": {"appid": appid, "token": token, "cluster": (cluster or "volcano_tts")},
        "user": {"uid": uid},
        "audio": {
            "voice_type": voice_type,
            "encoding": encoding,
            "speed_ratio": _clamp_speed(speed_text),
            "volume_ratio": 1.0,
            "pitch_ratio": 1.0,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }

    # 豆包 TTS 2.0 情绪控制：优先使用“语音指令”
    instruction = _emotion_to_instruction(emotion)
    if instruction:
        payload["request"]["text"] = f"{instruction}{text}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer;{token}",
        # 兼容部分火山网关/新文档要求的 Header（不影响旧接口）
        "X-Api-App-Key": appid,
        "X-Api-Access-Key": token,
    }

    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
    except Exception as e:
        raise TtsError(f"火山 TTS 请求失败：{e}")

    if resp.status_code in (401, 403):
        raise TtsForbiddenError(f"{resp.status_code}：{resp.text[:200]}")

    if resp.status_code != 200:
        raise TtsError(f"火山 TTS HTTP {resp.status_code}：{resp.text[:200]}")

    try:
        data = resp.json()
    except Exception as e:
        raise TtsError(f"火山 TTS 返回非 JSON：{e}; body={resp.text[:200]}")

    # 常见返回：{"code":0,"message":"success","data":"<base64>"}
    code = data.get("code")
    # 兼容部分返回以 3000 表示成功（message=Success）
    if code not in (0, "0", None, 200, "200", 3000, "3000"):
        raise TtsError(f"火山 TTS 失败：code={code}, message={data.get('message')}")

    b64 = _extract_audio_base64(data)
    if not b64:
        raise TtsError(f"火山 TTS 未返回可解析的音频数据：code={code}, message={data.get('message')}")

    try:
        audio_bytes = base64.b64decode(b64)
    except Exception as e:
        raise TtsError(f"火山 TTS 音频解码失败：{e}")

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio_bytes)
    except Exception as e:
        raise TtsError(f"音频写入失败：{e}")
