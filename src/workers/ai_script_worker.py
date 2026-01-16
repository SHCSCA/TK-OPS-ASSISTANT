"""AI 脚本生成 Worker（两步式二创 Step 1）

职责：
- 调用 AI 生成严格 JSON 脚本（hook/pain/solution/cta/full_script）
- 进行严格校验，不通过则自动重试
- 通过后将规范化结果通过 data_signal 发回 UI

说明：
- 耗时操作必须放在线程里，避免卡 UI
- 错误信息使用中文，便于运营同学理解
"""

from __future__ import annotations

import json
import logging
from typing import Any

import config
from workers.base_worker import BaseWorker
from utils.script_validation import validate_tiktok_script_payload

logger = logging.getLogger(__name__)


def _is_ark_base_url(base_url: str) -> bool:
    u = (base_url or "").strip().lower()
    return ("volces.com" in u) or ("volcengine.com" in u) or ("ark." in u)


def _build_ark_thinking_extra_body() -> dict[str, Any] | None:
    base_url_now = (getattr(config, "AI_BASE_URL", "") or "").strip()
    thinking_type = (getattr(config, "ARK_THINKING_TYPE", "") or "").strip()
    if not base_url_now or not thinking_type:
        return None
    if not _is_ark_base_url(base_url_now):
        return None
    return {"thinking": {"type": thinking_type}}


class AIScriptWorker(BaseWorker):
    """脚本生成：严格 JSON + 校验 + 重试"""

    def __init__(
        self,
        product_desc: str,
        role_prompt: str = "",
        model: str = "",
        max_attempts: int = 3,
        strict_validation: bool = True,
    ):
        super().__init__()
        self.product_desc = (product_desc or "").strip()
        self.role_prompt = (role_prompt or "").strip()
        self.model = (model or "").strip()
        self.max_attempts = max(1, int(max_attempts or 1))
        self.strict_validation = bool(strict_validation)

    def _run_impl(self) -> None:
        if not self.product_desc:
            self.emit_finished(False, "请先填写【商品/视频描述】。")
            return

        api_key = (getattr(config, "AI_API_KEY", "") or "").strip()
        if not api_key:
            self.emit_finished(False, "AI_API_KEY 未配置：请先在【系统设置】配置。")
            return

        base_url = ((getattr(config, "AI_BASE_URL", "") or "").strip() or "https://api.deepseek.com")
        use_model = self.model or (getattr(config, "AI_MODEL", "") or "deepseek-chat")

        extra_role = (
            self.role_prompt
            or (getattr(config, "AI_FACTORY_ROLE_PROMPT", "") or "").strip()
            or (getattr(config, "AI_SYSTEM_PROMPT", "") or "").strip()
        )

        # 角色提示词可观测
        try:
            if extra_role:
                preview = extra_role.replace("\n", " ")[:80]
                self.emit_log(f"🧩 脚本角色提示词：已启用（{len(extra_role)} 字）- {preview}...")
            else:
                self.emit_log("🧩 脚本角色提示词：未配置（仅使用内置默认角色）")
        except Exception:
            pass

        system = (
            "You are a TikTok short-form script writer. "
            "Return STRICT JSON only. Never add markdown. Never add extra keys. "
            "The script must be suitable for a 30-second voiceover. "
        )
        if extra_role:
            system += "\n[ROLE_PROMPT]\n" + extra_role

        user = (
            "Write a 30-second product pitch voiceover script for TikTok.\n"
            "Product description:\n"
            f"{self.product_desc}\n\n"
            "OUTPUT FORMAT (STRICT JSON object):\n"
            "{\n"
            "  \"hook_text\": \"...\",\n"
            "  \"pain_text\": \"...\",\n"
            "  \"solution_text\": \"...\",\n"
            "  \"cta_text\": \"...\",\n"
            "  \"full_script\": \"...\"\n"
            "}\n\n"
            "Constraints:\n"
            "- hook_text: ~3 seconds, punchy\n"
            "- pain_text: ~10 seconds\n"
            "- solution_text: ~15 seconds\n"
            "- cta_text: ~2 seconds, must include a clear action (click/buy/shop/link)\n"
            "- Keep total length under ~110 words (if English)\n"
            "- No emojis, no hashtags, no title list\n"
        )

        ark_extra = _build_ark_thinking_extra_body()

        last_reason = ""
        last_raw = ""

        for attempt in range(1, self.max_attempts + 1):
            if self.should_stop():
                self.emit_finished(False, "任务已取消。")
                return

            self.emit_progress(int(5 + (attempt - 1) * (70 / max(1, self.max_attempts))))
            self.emit_log(f"🤖 正在生成脚本（第 {attempt}/{self.max_attempts} 次）...")

            raw = self._call_ai_json(
                api_key=api_key,
                base_url=base_url,
                model=use_model,
                system=system,
                user=user,
                ark_extra=ark_extra,
            )

            last_raw = (raw or "").strip()
            if not last_raw:
                last_reason = "模型未返回有效内容。"
                self.emit_log(f"⚠️ 脚本为空：{last_reason}")
                continue

            payload = _try_parse_json(last_raw)
            if payload is None:
                last_reason = "模型输出不是合法 JSON。"
                self.emit_log(f"⚠️ {last_reason}（将自动重试）")
                continue

            result = validate_tiktok_script_payload(payload, strict=self.strict_validation)
            if result.ok and result.script_json:
                self.emit_progress(95)
                self.data_signal.emit(result.script_json)
                self.emit_finished(True, "脚本生成并校验通过。")
                return

            last_reason = (result.reason or "脚本校验失败。").strip()
            self.emit_log(f"⚠️ {last_reason}（将自动重试）")

        # 全部失败：回传最后一次原文，便于 UI 展示/诊断
        if last_raw:
            self.data_signal.emit({"raw": last_raw, "reason": last_reason})
        self.emit_progress(100)
        self.emit_finished(False, f"脚本生成失败：{last_reason or '请稍后重试或调整提示词。'}")

    def _call_ai_json(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        system: str,
        user: str,
        ark_extra: dict[str, Any] | None,
    ) -> str:
        try:
            import openai

            client = openai.OpenAI(api_key=api_key, base_url=base_url)

            # 优先：支持 JSON response_format 的 SDK/后端
            try:
                if ark_extra:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=0.4,
                        max_tokens=450,
                        response_format={"type": "json_object"},
                        extra_body=ark_extra,
                    )
                else:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=0.4,
                        max_tokens=450,
                        response_format={"type": "json_object"},
                    )
                return (resp.choices[0].message.content or "").strip()
            except TypeError:
                # openai SDK 版本不支持 response_format/extra_body
                pass

            # 兜底：普通 chat.completions
            try:
                if ark_extra:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=0.4,
                        max_tokens=450,
                        extra_body=ark_extra,
                    )
                else:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=0.4,
                        max_tokens=450,
                    )
            except TypeError:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.4,
                    max_tokens=450,
                )

            return (resp.choices[0].message.content or "").strip()

        except Exception as e:
            logger.error(f"脚本生成调用失败: {e}", exc_info=True)
            self.emit_log(f"❌ 脚本生成调用失败：{e}")
            return ""


def _try_parse_json(text: str) -> dict[str, Any] | None:
    s = (text or "").strip()
    if not s:
        return None

    # 常见“多包一层”兜底：提取首尾花括号
    if not s.startswith("{"):
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start : end + 1]

    try:
        obj = json.loads(s)
    except Exception:
        return None

    if not isinstance(obj, dict):
        return None
    return obj
