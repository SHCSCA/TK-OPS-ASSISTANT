from __future__ import annotations

import re
from typing import Iterable

import requests


DEFAULT_VOICE_LIST_DOC_URL = "https://www.volcengine.com/docs/6561/1257544"


def extract_voice_types_from_text(text: str) -> list[str]:
    """从文档 HTML/文本中提取可能的 voice_type。

    说明：音色列表文档页面结构可能调整，因此这里采用“正则容错提取”。
    目标是让运营同学可以一键导入常见 voice_type，最终以控制台/官方文档为准。
    """

    if not text:
        return []

    patterns: Iterable[str] = (
        r"\bsaturn_[a-z0-9_]+_tob\b",
        r"\b(?:zh|en|ja|es|id|pt)_[a-z0-9_]+_bigtts\b",
        r"\bBV\d+_streaming\b",
        r"\bcustom_mix_bigtts\b",
    )

    voices: set[str] = set()
    for pat in patterns:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            v = str(m).strip()
            if v:
                voices.add(v)

    return sorted(voices)


def fetch_voice_types_from_docs(url: str = DEFAULT_VOICE_LIST_DOC_URL, timeout: int = 20) -> list[str]:
    """从火山公开音色列表文档抓取并解析音色 ID。

    注意：文档页面可能按地区/登录态/反爬策略返回不同内容，因此这里会尝试多个 URL 变体。
    """

    urls = [
        url,
        # 常见语言参数变体
        f"{url}?lang=zh",
        f"{url}?lang=zh-cn",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    last_err: Exception | None = None
    for u in urls:
        try:
            resp = requests.get(u, timeout=timeout, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:120]}")
            items = extract_voice_types_from_text(resp.text or "")
            if items:
                return items
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise RuntimeError(f"抓取音色文档失败：{last_err}")
    return []
