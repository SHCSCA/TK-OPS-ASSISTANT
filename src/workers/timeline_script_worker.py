"""秒级情感口播脚本 Worker（Timeline Scripting）

输出 JSON 结构：
{
  "timeline": [
    {"start":0, "end":3, "text":"...", "emotion":"happy"}
  ]
}
"""
from __future__ import annotations

import json
import logging
from typing import Any

import config
from workers.base_worker import BaseWorker

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    s = (text or "").strip()
    if not s:
        return None
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


class TimelineScriptWorker(BaseWorker):
    """生成带时间轴与情感标签的口播脚本。"""

    def __init__(
        self,
        product_desc: str,
        total_duration: float,
        role_prompt: str = "",
        model: str = "",
        max_attempts: int = 3,
    ):
        super().__init__()
        self.product_desc = (product_desc or "").strip()
        self.total_duration = max(3.0, float(total_duration or 15.0))
        self.role_prompt = (role_prompt or "").strip()
        self.model = (model or "").strip()
        self.max_attempts = max(1, int(max_attempts or 1))

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

        system = (
            "You are a TikTok short-form script writer. "
            "Output STRICT JSON only. No markdown. No extra keys."
        )
        if self.role_prompt:
            system += "\n[ROLE_PROMPT]\n" + self.role_prompt

        user = (
            "Generate a timeline voiceover script with timestamps and emotions.\n"
            f"Total duration: {self.total_duration:.1f} seconds.\n"
            "Constraints:\n"
            "- English pacing ~2.5 words/second.\n"
            "- Each segment must have start<end.\n"
            "- Emotion must be one of: happy, sad, angry, surprise, neutral.\n"
            "- Output STRICT JSON object with key timeline only.\n\n"
            "JSON schema:\n"
            "{\n"
            "  \"timeline\": [\n"
            "    {\"start\":0, \"end\":3, \"text\":\"...\", \"emotion\":\"happy\"}\n"
            "  ]\n"
            "}\n\n"
            f"Product description:\n{self.product_desc}\n"
        )

        last_reason = ""
        last_raw = ""

        for attempt in range(1, self.max_attempts + 1):
            if self.should_stop():
                self.emit_finished(False, "任务已取消。")
                return

            self.emit_progress(int(10 + (attempt - 1) * (70 / max(1, self.max_attempts))))
            self.emit_log(f"🤖 正在生成时间轴脚本（第 {attempt}/{self.max_attempts} 次）...")

            raw = self._call_ai_json(
                api_key=api_key,
                base_url=base_url,
                model=use_model,
                system=system,
                user=user,
            )

            last_raw = (raw or "").strip()
            if not last_raw:
                last_reason = "模型未返回有效内容。"
                self.emit_log(f"⚠️ 脚本为空：{last_reason}")
                continue

            payload = _extract_json_object(last_raw)
            if not payload:
                last_reason = "模型输出不是合法 JSON。"
                self.emit_log(f"⚠️ {last_reason}（将自动重试）")
                continue

            timeline = payload.get("timeline")
            if not isinstance(timeline, list) or not timeline:
                last_reason = "timeline 为空或格式错误。"
                self.emit_log(f"⚠️ {last_reason}（将自动重试）")
                continue

            cleaned = self._normalize_timeline(timeline)
            if not cleaned:
                last_reason = "时间轴解析失败。"
                self.emit_log(f"⚠️ {last_reason}（将自动重试）")
                continue

            full_script = " ".join([x.get("text", "").strip() for x in cleaned if x.get("text")]).strip()

            self.data_signal.emit({"timeline": cleaned, "full_script": full_script})
            self.emit_progress(100)
            self.emit_finished(True, "时间轴脚本生成成功。")
            return

        if last_raw:
            self.data_signal.emit({"raw": last_raw, "reason": last_reason})
        self.emit_progress(100)
        self.emit_finished(False, f"时间轴脚本生成失败：{last_reason or '请稍后重试或调整提示词。'}")

    def _call_ai_json(self, *, api_key: str, base_url: str, model: str, system: str, user: str) -> str:
        try:
            import openai

            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 1200,
                "response_format": {"type": "json_object"},
            }

            resp = None
            try:
                resp = client.chat.completions.create(**kwargs)
            except TypeError:
                if "response_format" in kwargs:
                    del kwargs["response_format"]
                resp = client.chat.completions.create(**kwargs)

            # Token 统计
            try:
                if resp and resp.usage:
                    u = resp.usage
                    p = getattr(u, "prompt_tokens", 0)
                    c = getattr(u, "completion_tokens", 0)
                    t = getattr(u, "total_tokens", 0)
                    self.emit_log(f"💰 Token 消耗: Prompt={p}, Completion={c}, Total={t}")
            except Exception:
                pass

            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error(f"时间轴脚本生成调用失败: {e}", exc_info=True)
            self.emit_log(f"❌ 时间轴脚本生成调用失败：{e}")
            return ""

    def _normalize_timeline(self, timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for item in timeline:
            if not isinstance(item, dict):
                continue
            try:
                start = float(item.get("start", 0))
                end = float(item.get("end", 0))
            except Exception:
                continue
            text = (item.get("text", "") or "").strip()
            emotion = (item.get("emotion", "neutral") or "neutral").strip().lower()
            if not text:
                continue
            if end <= start:
                continue
            cleaned.append({"start": start, "end": end, "text": text, "emotion": emotion})

        if not cleaned:
            return []

        # 排序 + 裁剪到总时长
        cleaned.sort(key=lambda x: x["start"])
        out: list[dict[str, Any]] = []
        for seg in cleaned:
            if seg["start"] >= self.total_duration:
                continue
            seg["end"] = min(seg["end"], self.total_duration)
            if seg["end"] <= seg["start"]:
                continue
            out.append(seg)

        return out
