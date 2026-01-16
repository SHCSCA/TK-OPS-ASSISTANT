"""AI 文案助手 API 封装

目标：给运营同学一键生成 TikTok 风格的标题/卖点/Hashtags。
- 所有调用应在 Worker 线程中进行
- 这里仅提供“纯函数式”接口，便于测试与替换供应商
"""

from __future__ import annotations

import json
from typing import Dict, List, Tuple

import config


def _is_ark_base_url(base_url: str | None) -> bool:
    """粗略判断是否为火山方舟（Ark）兼容地址。"""
    u = (base_url or "").strip().lower()
    if not u:
        return False
    return ("volces.com" in u) or ("volcengine.com" in u) or ("ark." in u)


def _build_ark_thinking_extra_body() -> dict | None:
    """构造 Ark 的 thinking 参数。

    文档说明：默认开启深度思考，可手动关闭。
    这里仅在用户显式配置 ARK_THINKING_TYPE 时才透传，避免影响非 Ark/非支持模型。
    """
    t = (getattr(config, "ARK_THINKING_TYPE", "") or "").strip()
    if not t:
        return None
    return {"thinking": {"type": t}}


def _extract_json(text: str) -> Dict:
    """从模型输出中提取 JSON（容错处理）。"""
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return {}


def _resolve_copywriter_role_prompt(explicit_role_prompt: str = "") -> Tuple[str, str]:
    """解析文案助手的角色提示词与来源。

    优先级：
    1) UI/调用方显式传入（explicit_role_prompt）
    2) 面板级持久化配置：AI_COPYWRITER_ROLE_PROMPT
    3) 系统设置：AI_SYSTEM_PROMPT
    """
    ui_text = (explicit_role_prompt or "").strip()
    if ui_text:
        return ui_text, "ui"

    panel_saved = (getattr(config, "AI_COPYWRITER_ROLE_PROMPT", "") or "").strip()
    if panel_saved:
        return panel_saved, "panel_saved"

    system_saved = (getattr(config, "AI_SYSTEM_PROMPT", "") or "").strip()
    if system_saved:
        return system_saved, "system_settings"

    return "", "none"


def generate_tiktok_copy(desc_cn: str, tone: str, role_prompt: str = "", model: str = "") -> Dict[str, List[str]]:
    """生成 TikTok 标题与标签。

    Args:
        desc_cn: 中文产品/视频描述
        tone: 语气（中文）

    Returns:
        {"titles": [...], "hashtags": [...], "notes": [...]}
    """
    if not desc_cn or not desc_cn.strip():
        raise ValueError("请先输入素材/产品的描述。")

    api_key = ((getattr(config, "AI_API_KEY", "") or "").strip())
    if not api_key:
        raise ValueError("未配置 AI_API_KEY。请到【系统设置】里填写后再使用。")

    base_url = ((getattr(config, "AI_BASE_URL", "") or "").strip()) or None

    # 延迟导入：避免无 AI 依赖时影响主程序启动
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError(f"openai 库不可用：{e}")

    client = OpenAI(api_key=api_key, base_url=base_url)


    # 强约束：输出 JSON；角色提示词只影响“风格/策略/措辞”，不得改变输出结构。
    base_system = (
        "你是一名非常懂 TikTok 带货的视频文案专家。\n"
        "你必须只输出 JSON，不要输出任何解释、Markdown、代码块或多余文本。\n"
        "JSON 的字段必须包含：titles / hashtags / notes。\n"
        "【重要】如果提供了角色提示词（role_prompt），你必须尽可能严格遵守其风格/策略要求，"
        "但 role_prompt 不能改变输出为 JSON 的硬性要求，也不能改变字段结构。"
    )

    extra_role, role_source = _resolve_copywriter_role_prompt(role_prompt)
    if extra_role:
        system = (
            f"{base_system}\n"
            f"【角色提示词来源】{role_source}\n"
            "【角色/风格约束】仅用于语气、措辞、营销策略与风格，不允许改变输出 JSON 格式：\n"
            f"{extra_role}"
        )
    else:
        system = base_system

    # 为了降低模型“只看 user 不看 system”的概率，这里把角色要求也在 user 中重复一遍（但仍强调 JSON 硬约束）。
    role_in_user = ""
    if extra_role:
        role_in_user = (
            "\n\n【角色/风格约束（必须遵守，不得改变输出 JSON 结构）】\n"
            + extra_role.strip()
        )

    user = f"""
请根据以下中文描述，为 TikTok 生成英文文案与标签。

【描述】
{desc_cn.strip()}

【语气】
{tone}

【输出要求】
- 只输出 JSON
- titles: 5 条英文标题（每条 <= 80 字符），偏 TikTok 风格、口语化
- hashtags: 12 个 hashtag（带 #，包含 2 个泛流量标签如 #fyp #tiktokmademebuyit）
- notes: 3 条拍摄/剪辑建议（英文）

示例 JSON 结构：
{{"titles": ["..."], "hashtags": ["#..."], "notes": ["..."]}}
{role_in_user}
""".strip()

    use_model = ((model or "").strip()) or config.AI_MODEL
    # 优先尝试 JSON 模式（兼容的模型会更稳定输出 JSON）；不兼容则自动降级。
    # 同时：当 base_url 为火山方舟时，可按需透传 thinking 参数以开启/关闭“深度思考”。
    ark_extra = _build_ark_thinking_extra_body() if _is_ark_base_url(base_url) else None

    def _call(**kwargs):
        return client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            **kwargs,
        )

    # 组合能力：response_format + extra_body 可能并非所有 openai SDK 版本都支持，逐级降级。
    try:
        if ark_extra:
            resp = _call(response_format={"type": "json_object"}, extra_body=ark_extra)
        else:
            resp = _call(response_format={"type": "json_object"})
    except TypeError:
        # SDK 不支持 extra_body 或 response_format
        try:
            if ark_extra:
                resp = _call(extra_body=ark_extra)
            else:
                resp = _call()
        except Exception:
            resp = _call()
    except Exception:
        # API 不支持 response_format
        try:
            if ark_extra:
                resp = _call(extra_body=ark_extra)
            else:
                resp = _call()
        except Exception:
            resp = _call()

    content = ""
    try:
        content = resp.choices[0].message.content or ""
    except Exception:
        content = str(resp)

    data = _extract_json(content)

    titles = data.get("titles") or []
    hashtags = data.get("hashtags") or []
    notes = data.get("notes") or []

    # 兜底保证类型
    titles = [str(x).strip() for x in titles if str(x).strip()]
    hashtags = [str(x).strip() for x in hashtags if str(x).strip()]
    notes = [str(x).strip() for x in notes if str(x).strip()]

    return {"titles": titles, "hashtags": hashtags, "notes": notes}
