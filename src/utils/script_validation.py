"""脚本校验工具

目标：为“二创工厂两步式”提供严格、可解释的脚本校验。

约定的脚本 JSON schema（严格模式）：
- hook_text: str
- pain_text: str
- solution_text: str
- cta_text: str
- full_script: str（可选；若缺失则由四段拼接生成）

校验重点：
- 四段必须非空
- 长度必须可控（30 秒口播建议 80-110 words 左右）
- CTA 必须包含明确行动指令

注意：
- 返回面向 UI 的中文原因
- 变量/函数名用英文
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScriptValidationResult:
    ok: bool
    reason: str
    normalized_script_text: str
    script_json: dict[str, str] | None = None


_CTA_KEYWORDS = (
    # 英文常见 CTA
    "shop",
    "buy",
    "order",
    "tap",
    "click",
    "link",
    "checkout",
    "add to cart",
    "grab",
    "get yours",
    "today",
    "now",
    # 中文常见 CTA（兼容用户偏好）
    "下单",
    "购买",
    "点击",
    "链接",
    "橱窗",
    "立刻",
    "马上",
    "现在",
)


def _is_probably_cjk(text: str) -> bool:
    if not text:
        return False
    cjk_count = 0
    for ch in text:
        code = ord(ch)
        # CJK Unified Ideographs + 常用标点大致覆盖
        if (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF):
            cjk_count += 1
    return (cjk_count / max(1, len(text))) >= 0.15


def _word_count(text: str) -> int:
    # 粗略英文词统计；中文将落到字符统计分支
    parts = [p for p in (text or "").replace("\n", " ").split(" ") if p.strip()]
    return len(parts)


def _char_count_no_spaces(text: str) -> int:
    return len("".join((text or "").split()))


def validate_tiktok_script_payload(payload: Any, *, strict: bool = True) -> ScriptValidationResult:
    """校验 AI 返回的脚本结构。

    - payload 可以是 dict 或者 JSON-like
    - strict=True 启用更严格的长度/CTA 约束
    """

    if not isinstance(payload, dict):
        return ScriptValidationResult(False, "脚本结构不正确：应为 JSON 对象。", "")

    def _get(key: str) -> str:
        value = payload.get(key, "")
        if value is None:
            return ""
        if not isinstance(value, str):
            return ""
        return value.strip()

    hook_text = _get("hook_text")
    pain_text = _get("pain_text")
    solution_text = _get("solution_text")
    cta_text = _get("cta_text")
    full_script = _get("full_script")

    missing = [k for k, v in (
        ("hook_text", hook_text),
        ("pain_text", pain_text),
        ("solution_text", solution_text),
        ("cta_text", cta_text),
    ) if not v]
    if missing:
        return ScriptValidationResult(False, f"脚本不完整：缺少字段 {', '.join(missing)}。", "")

    if not full_script:
        full_script = "\n".join([hook_text, pain_text, solution_text, cta_text]).strip()

    # CTA 强约束：必须包含明确行动指令（英文/中文任一）
    if strict:
        lowered = (cta_text or "").lower()
        if not any(k in lowered or k in cta_text for k in _CTA_KEYWORDS):
            return ScriptValidationResult(
                False,
                "CTA 不够明确：请包含‘点击/下单/链接/橱窗’或英文 click/buy/shop/link 等行动指令。",
                "",
            )

    # 长度约束（30 秒口播）：英文按 words，中文按非空格字符
    is_cjk = _is_probably_cjk(full_script)

    if is_cjk:
        # 中文 30 秒：建议 <= 220 字符（不含空格）
        char_count = _char_count_no_spaces(full_script)
        if strict and (char_count > 220):
            return ScriptValidationResult(False, f"脚本过长：约 {char_count} 字，建议控制在 220 字以内（30 秒）。", "")
        # 分段长度（中文）
        if strict and _char_count_no_spaces(hook_text) > 45:
            return ScriptValidationResult(False, "Hook 过长：建议 45 字以内（约 3 秒）。", "")
        if strict and _char_count_no_spaces(cta_text) > 45:
            return ScriptValidationResult(False, "CTA 过长：建议 45 字以内（约 2-3 秒）。", "")
    else:
        words = _word_count(full_script)
        if strict and (words > 110):
            return ScriptValidationResult(False, f"脚本过长：约 {words} words，建议控制在 110 words 以内（30 秒）。", "")
        if strict and _word_count(hook_text) > 18:
            return ScriptValidationResult(False, "Hook 过长：建议 18 words 以内（约 3 秒）。", "")
        if strict and _word_count(cta_text) > 18:
            return ScriptValidationResult(False, "CTA 过长：建议 18 words 以内（约 2-3 秒）。", "")

    normalized = {
        "hook_text": hook_text,
        "pain_text": pain_text,
        "solution_text": solution_text,
        "cta_text": cta_text,
        "full_script": full_script,
    }

    return ScriptValidationResult(True, "脚本校验通过。", full_script, script_json=normalized)
