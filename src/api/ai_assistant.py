"""AI 文案助手 API 封装

目标：给运营同学一键生成 TikTok 风格的标题/卖点/Hashtags。
- 所有调用应在 Worker 线程中进行
- 这里仅提供“纯函数式”接口，便于测试与替换供应商
"""

from __future__ import annotations

import json
from typing import Dict, List

import config


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


def generate_tiktok_copy(desc_cn: str, tone: str) -> Dict[str, List[str]]:
    """生成 TikTok 标题与标签。

    Args:
        desc_cn: 中文产品/视频描述
        tone: 语气（中文）

    Returns:
        {"titles": [...], "hashtags": [...], "notes": [...]}
    """
    if not desc_cn or not desc_cn.strip():
        raise ValueError("请先输入素材/产品的描述。")

    if not config.AI_API_KEY:
        raise ValueError("未配置 AI_API_KEY。请到【系统设置】里填写后再使用。")

    base_url = (config.AI_BASE_URL or "").strip() or None

    # 延迟导入：避免无 AI 依赖时影响主程序启动
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError(f"openai 库不可用：{e}")

    client = OpenAI(api_key=config.AI_API_KEY, base_url=base_url)

    system = (
        "你是一名非常懂 TikTok 带货的视频文案专家。"
        "你输出必须是 JSON，不要输出多余解释文字。"
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
""".strip()

    resp = client.chat.completions.create(
        model=config.AI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.8,
    )

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
