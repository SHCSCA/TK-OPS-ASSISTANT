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

from utils.ai_routing import resolve_ai_profile


class VisualAIAssistant:
    """多模态视觉分析助手（OpenAI 兼容协议）。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        role_prompt: str | None = None,
    ):
        profile = resolve_ai_profile(
            "vision",
            model_override=(model or "").strip(),
            provider_override=(provider or "").strip(),
        )
        self.api_key = (api_key or profile.get("api_key", "") or "").strip()
        self.base_url = (base_url or profile.get("base_url", "") or "").strip()
        self.model = (model or profile.get("model", "") or "").strip()
        self.role_prompt = (role_prompt or "").strip()

    def analyze_frames(self, frames_b64: Iterable[str], prompt: str) -> str:
        """分析连续视频帧并返回模型输出文本。"""
        if not self.api_key:
            raise ValueError("AI_API_KEY 未配置")
        if not self.base_url:
            raise ValueError("AI_BASE_URL 未配置")
        if not self.model:
            raise ValueError("AI_VISION_MODEL 未配置")

        if "deepseek.com" in self.base_url:
             raise ValueError("DeepSeek 官方 API 暂不支持视觉分析（图片输入）。请切换到 Aliyun (Qwen-VL) 或 Volcengine (Doubao-Vision)。")

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

        # 角色提示词（优先使用本次传入，其次使用视觉实验室已保存配置）
        extra_role = (
            (self.role_prompt or "").strip()
            or (getattr(__import__("config"), "AI_VISION_ROLE_PROMPT", "") or "").strip()
            or (getattr(__import__("config"), "AI_SYSTEM_PROMPT", "") or "").strip()
        )
        messages = []
        if extra_role:
            messages.append({"role": "system", "content": extra_role})
        messages.append({"role": "user", "content": content})

        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=4096,
            )
            
            try:
                if resp.choices[0].finish_reason == "length":
                     logger.warning("VisualAI: Response truncated due to max_tokens limit.")
            except:
                pass
                
            return (resp.choices[0].message.content or "").strip()
            
        except openai.BadRequestError as e:
            # Handle non-vision model errors specifically
            msg = str(e).lower()
            if "image_url" in msg or "expected text" in msg or "invalid_request_error" in msg:
                raise ValueError(
                    f"当前模型 ({self.model}) 不支持视觉分析（不支持 image_url 参数）。"
                    "请在设置中切换为支持 Vision 的模型（如 GPT-4o, Claude-3.5-Sonnet, Gemini-1.5-Pro 等）。"
                ) from e
            raise
        except openai.NotFoundError as e:
            raise ValueError(f"模型 ({self.model}) 不存在或 API 地址错误 (404)。请检查 AI 设置。") from e
