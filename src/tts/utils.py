"""
TTS Utilities - Shared logic for emotion and instruction building.
"""
from typing import Dict
import config

def build_emotion_instruction(base_emotion: str) -> str:
    """
    Constructs an emotion instruction string for TTS engines (e.g. Doubao/Volcengine).
    Based on config settings (SCENE_MODE, PRESET, CUSTOM, INTENSITY).
    """
    preset = (getattr(config, "TTS_EMOTION_PRESET", "") or "").strip()
    custom = (getattr(config, "TTS_EMOTION_CUSTOM", "") or "").strip()
    intensity = (getattr(config, "TTS_EMOTION_INTENSITY", "中") or "中").strip()
    scene_mode = (getattr(config, "TTS_SCENE_MODE", "") or "").strip().lower()

    scene_templates = {
        "commerce": "用强转化、强节奏、强调卖点的带货语气说",
        "review": "用客观、冷静、对比分析的测评语气说",
        "unboxing": "用真实、兴奋、细节描述的开箱语气说",
        "story": "用剧情对白的语气说，带有情绪起伏",
        "talk": "用清晰、稳定、讲解导向的口播语气说",
    }

    emotion = (base_emotion or "").strip().lower()
    emotion_map = {
        "happy": "开心", "sad": "悲伤", "angry": "生气",
        "surprise": "惊讶", "neutral": "平静", "excited": "兴奋",
        "calm": "沉稳", "serious": "严肃", "curious": "好奇",
        "persuasive": "劝导", "suspense": "悬念", "warm": "温柔",
        "firm": "坚定", "energetic": "有活力", "confident": "自信"
    }

    parts = []
    scene_hint = scene_templates.get(scene_mode, "")
    if scene_hint: parts.append(scene_hint)
    if preset: parts.append(preset)
    if custom: parts.append(custom)

    if emotion and emotion != "neutral":
        emotion_cn = emotion_map.get(emotion, emotion)
        parts.append(f"情绪偏{emotion_cn}，强度{intensity}")
    elif parts:
        parts.append(f"情绪强度{intensity}")
    else:
        return ""

    return "，".join([p for p in parts if p])
