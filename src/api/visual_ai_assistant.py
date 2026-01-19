"""视觉 AI 助手（Doubao-Vision-Pro / OpenAI 兼容接口）

职责：
- 接收多张图片（base64）进行视觉分析
- 返回模型文本输出

注意：
- 所有异常都要抛出上层处理
- 不做 UI 日志输出
"""
from __future__ import annotations

from typing import Iterable

import config


class VisualAIAssistant:
    """多模态视觉分析助手（OpenAI 兼容协议）。"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = (api_key or getattr(config, "AI_API_KEY", "") or "").strip()
        self.base_url = (base_url or getattr(config, "AI_BASE_URL", "") or "").strip()
        self.model = (model or getattr(config, "AI_VISION_MODEL", "") or "").strip()

    def analyze_frames(self, frames_b64: Iterable[str], prompt: str) -> str:
        """分析连续视频帧并返回模型输出文本。"""
        if not self.api_key:
            raise ValueError("AI_API_KEY 未配置")
        if not self.base_url:
            raise ValueError("AI_BASE_URL 未配置")
        if not self.model:
            raise ValueError("AI_VISION_MODEL 未配置")

        images = [f"data:image/jpeg;base64,{b64}" for b64 in frames_b64 if b64]
        if not images:
            raise ValueError("未获取到有效视频帧")

        prompt_text = (prompt or "").strip() or (
            "分析这一组连续视频帧。请按时间顺序反推它的拍摄脚本，并指出它的黄金前三秒用了什么视觉钩子？"
        )

        import openai

        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        content = [{"type": "text", "text": prompt_text}]
        for url in images:
            content.append({"type": "image_url", "image_url": {"url": url}})

        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.4,
            max_tokens=1200,
        )

        return (resp.choices[0].message.content or "").strip()
