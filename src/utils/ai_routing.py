"""AI 路由工具

目标：支持“任务级模型覆盖”，避免全局单模型绑定。

规则：
- 若任务级配置存在（API Key/Base URL/Model 任意一项），优先使用。
- 否则回退到全局 AI_* 配置。
"""
from __future__ import annotations

from typing import Dict, Tuple

import config


def _resolve_provider_profile(provider_name: str) -> Tuple[str, str]:
    name = (provider_name or "").strip().lower()
    if name in ("doubao", "volc", "volcengine", "ark"):
        return (
            (getattr(config, "AI_DOUBAO_API_KEY", "") or "").strip(),
            (getattr(config, "AI_DOUBAO_BASE_URL", "") or "").strip(),
        )
    if name in ("qwen", "qianwen", "aliyun", "dashscope"):
        return (
            (getattr(config, "AI_QWEN_API_KEY", "") or "").strip(),
            (getattr(config, "AI_QWEN_BASE_URL", "") or "").strip(),
        )
    if name in ("deepseek",):
        return (
            (getattr(config, "AI_DEEPSEEK_API_KEY", "") or "").strip(),
            (getattr(config, "AI_DEEPSEEK_BASE_URL", "") or "").strip(),
        )
    return ("", "")


def resolve_ai_profile(task: str, model_override: str = "", provider_override: str = "") -> Dict[str, str]:
    """解析指定任务的 AI 配置（API Key / Base URL / Model）。

    Args:
        task: 任务名（copywriter/factory/timeline/photo/vision/default）
        model_override: 运行时显式传入的模型（优先级最高）
        provider_override: 运行时显式传入的供应商（优先级高于配置）

    Returns:
        dict: {"api_key": str, "base_url": str, "model": str}
    """
    t = (task or "default").strip().lower()

    mapping = {
        "copywriter": ("AI_COPYWRITER_API_KEY", "AI_COPYWRITER_BASE_URL", "AI_COPYWRITER_MODEL", "AI_COPYWRITER_PROVIDER"),
        "factory": ("AI_FACTORY_API_KEY", "AI_FACTORY_BASE_URL", "AI_FACTORY_MODEL", "AI_FACTORY_PROVIDER"),
        "timeline": ("AI_TIMELINE_API_KEY", "AI_TIMELINE_BASE_URL", "AI_TIMELINE_MODEL", "AI_TIMELINE_PROVIDER"),
        "photo": ("AI_PHOTO_API_KEY", "AI_PHOTO_BASE_URL", "AI_PHOTO_MODEL", "AI_PHOTO_PROVIDER"),
        "vision": ("AI_VISION_API_KEY", "AI_VISION_BASE_URL", "AI_VISION_MODEL", "AI_VISION_PROVIDER"),
        "default": ("AI_API_KEY", "AI_BASE_URL", "AI_MODEL", "AI_PROVIDER"),
    }

    key_name, url_name, model_name, provider_name = mapping.get(t, mapping["default"])

    # 任务级覆盖（允许部分为空）
    task_api_key = (getattr(config, key_name, "") or "").strip()
    task_base_url = (getattr(config, url_name, "") or "").strip()
    task_model = (getattr(config, model_name, "") or "").strip()

    # 供应商预设
    provider_value = (provider_override or "").strip() or (getattr(config, provider_name, "") or "").strip()
    provider_key, provider_url = _resolve_provider_profile(provider_value)

    # 全局兜底
    global_api_key = (getattr(config, "AI_API_KEY", "") or "").strip()
    global_base_url = (getattr(config, "AI_BASE_URL", "") or "").strip()
    global_model = (getattr(config, "AI_MODEL", "") or "").strip()

    api_key = task_api_key or provider_key or global_api_key
    base_url = task_base_url or provider_url or global_base_url
    model = task_model or global_model

    # 运行时覆盖（最高优先级）
    if model_override:
        model = model_override.strip()

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }
