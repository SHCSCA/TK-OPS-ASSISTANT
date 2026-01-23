"""AI 模型缓存（供应商维度）

用途：
- 记录供应商连通性与可用模型列表
- 供 UI 下拉框二级联动快速读取
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import config


def _norm_provider(provider: str) -> str:
    return (provider or "").strip().lower()


def _cache_path() -> Path:
    base = Path(getattr(config, "DATA_DIR", Path.cwd()))
    cache_dir = base / "Cache"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return cache_dir / "ai_models.json"


def _load() -> dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {"providers": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"providers": {}}


def _save(data: dict[str, Any]) -> None:
    path = _cache_path()
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _get_provider_entry(data: dict[str, Any], provider: str) -> dict[str, Any]:
    p = _norm_provider(provider)
    providers = data.setdefault("providers", {})
    return providers.setdefault(
        p,
        {
            "models": [],
            "ok": False,
            "message": "",
            "updated_at": 0,
        },
    )


def set_provider_models(provider: str, models: list[str], ok: bool = True, message: str = "") -> None:
    data = _load()
    entry = _get_provider_entry(data, provider)
    entry["models"] = list(dict.fromkeys([m for m in (models or []) if m]))
    entry["ok"] = bool(ok)
    entry["message"] = message or ""
    entry["updated_at"] = int(time.time())
    _save(data)


def set_provider_status(provider: str, ok: bool, message: str = "") -> None:
    data = _load()
    entry = _get_provider_entry(data, provider)
    entry["ok"] = bool(ok)
    entry["message"] = message or ""
    entry["updated_at"] = int(time.time())
    _save(data)


def get_provider_models(provider: str) -> list[str]:
    data = _load()
    entry = _get_provider_entry(data, provider)
    return list(entry.get("models") or [])


def get_provider_status(provider: str) -> dict[str, Any]:
    data = _load()
    entry = _get_provider_entry(data, provider)
    return {
        "ok": bool(entry.get("ok")),
        "message": entry.get("message", "") or "",
        "updated_at": int(entry.get("updated_at") or 0),
    }


def list_ok_providers() -> list[str]:
    data = _load()
    providers = data.get("providers", {}) or {}
    ok_list = []
    for k, v in providers.items():
        if bool((v or {}).get("ok")):
            ok_list.append(k)
    return ok_list
