"""云端图转视频（Image-to-Video）工具

设计目标：
- 通过可配置的 API 调用云端图生视频模型
- 保持接口松耦合，兼容不同供应商
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Tuple

import requests

import config


def _read_base64(path: str) -> str:
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("utf-8")


def _guess_mime(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in ("jpg", "jpeg"):
        return "image/jpeg"
    if suffix == "png":
        return "image/png"
    if suffix == "webp":
        return "image/webp"
    if suffix == "bmp":
        return "image/bmp"
    if suffix in ("tif", "tiff"):
        return "image/tiff"
    if suffix == "gif":
        return "image/gif"
    return "image/png"


def _build_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    api_key = (getattr(config, "VIDEO_CLOUD_API_KEY", "") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_video_url(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    
    # Candidates for video URL keys
    url_keys = ("video_url", "url", "download_url", "result_url", "video")

    # 1. Direct key in payload
    for key in url_keys:
        v = payload.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    
    # 2. Inside 'data' dict
    data = payload.get("data")
    if isinstance(data, dict):
        for key in url_keys:
            v = data.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v

    # 3. Inside 'result' (dict or list)
    result = payload.get("result")
    if isinstance(result, dict):
        for key in url_keys:
            v = result.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v
    elif isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                for key in url_keys:
                    v = item.get(key)
                    if isinstance(v, str) and v.startswith("http"):
                        return v

    # 4. Inside 'outputs' list
    outputs = payload.get("outputs")
    if isinstance(outputs, list):
        for item in outputs:
            if isinstance(item, dict):
                for key in url_keys:
                    v = item.get(key)
                    if isinstance(v, str) and v.startswith("http"):
                        return v
    
    return ""


def _extract_task_id(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("task_id", "id", "job_id"):
        v = payload.get(key)
        if isinstance(v, str) and v:
            return v
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("task_id", "id", "job_id"):
            v = data.get(key)
            if isinstance(v, str) and v:
                return v
    return ""


def _find_http_url_in_obj(obj) -> str:
    """递归查找对象中第一个以 http/https 开头的字符串并返回。"""
    try:
        if isinstance(obj, str):
            s = obj.strip()
            if s.startswith("http://") or s.startswith("https://"):
                return s
            return ""
        if isinstance(obj, dict):
            for k, v in obj.items():
                # skip small non-string primitives
                res = _find_http_url_in_obj(v)
                if res:
                    return res
        if isinstance(obj, list):
            for item in obj:
                res = _find_http_url_in_obj(item)
                if res:
                    return res
    except Exception:
        return ""
    return ""


def _find_base64_video_in_obj(obj) -> str:
    """递归查找对象中可能包含的 base64 视频字符串（data:video/...;base64, 或很长的 base64）并返回。"""
    try:
        if isinstance(obj, str):
            s = obj.strip()
            if s.startswith("data:video/") and ";base64," in s:
                return s
            # heuristic: long base64 without header (>= 100000 chars)
            if len(s) > 100000 and all(c.isalnum() or c in '+/=' for c in s[:200]):
                return s
            return ""
        if isinstance(obj, dict):
            for k, v in obj.items():
                res = _find_base64_video_in_obj(v)
                if res:
                    return res
        if isinstance(obj, list):
            for item in obj:
                res = _find_base64_video_in_obj(item)
                if res:
                    return res
    except Exception:
        return ""
    return ""


def _download_video(url: str, out_path: Path) -> Tuple[bool, str]:
    try:
        resp = requests.get(url, stream=True, timeout=60)
        if resp.status_code != 200:
            return False, f"下载失败 HTTP {resp.status_code}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True, str(out_path)
    except Exception as e:
        return False, f"下载异常：{e}"


def generate_video_from_image(
    image_path: str,
    prompt: str,
    out_path: Path,
    duration: float = 4.0,
    fps: int = 24,
    quality: str = "low",
    model: str = "",
) -> Tuple[bool, str]:
    """调用云端图转视频 API（火山方舟视频生成）。

    说明：
    - 提交任务：/contents/generations/tasks
    - 查询任务：/contents/generations/tasks/{task_id}
    """
    submit_url = (getattr(config, "VIDEO_CLOUD_SUBMIT_URL", "") or "").strip()
    status_url = (getattr(config, "VIDEO_CLOUD_STATUS_URL", "") or "").strip()
    
    # 优先使用传入的模型，否则读取配置
    use_model = (model or "").strip() or (getattr(config, "VIDEO_CLOUD_MODEL", "") or "").strip()
    
    if not submit_url:
        return False, "未配置 VIDEO_CLOUD_SUBMIT_URL"

    try:
        b64 = _read_base64(image_path)
    except Exception as e:
        return False, f"图片读取失败：{e}"

    mime = _guess_mime(image_path)
    image_data = f"data:{mime};base64,{b64}"

    # 映射质量 -> 分辨率
    q = (quality or "low").strip().lower()
    resolution = "720p"
    if q == "low":
        resolution = "480p"
    elif q == "medium":
        resolution = "720p"
    elif q == "high":
        resolution = "1080p"

    # 时长范围 [4,12]
    dur = int(max(4, min(12, int(duration or 4))))

    payload = {
        "model": use_model,
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": image_data},
                "role": "first_frame",
            },
        ],
        "ratio": "9:16",
        "duration": dur,
        "resolution": resolution,
        "watermark": False,
        "camera_fixed": False,
    }

    try:
        resp = requests.post(submit_url, json=payload, headers=_build_headers(), timeout=60)
        if resp.status_code != 200:
            return False, f"提交失败 HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json() if resp.text else {}
    except Exception as e:
        return False, f"提交异常：{e}"

    # 直接返回视频
    video_url = _extract_video_url(data)
    if video_url:
        return _download_video(video_url, out_path)

    # 轮询任务
    task_id = _extract_task_id(data)
    if not task_id or not status_url:
        return False, "未返回 video_url 或 task_id"

    # status_url 支持 {task_id} 占位
    def _build_status_url(tid: str) -> str:
        if "{task_id}" in status_url:
            return status_url.replace("{task_id}", tid)
        return status_url

    poll_sec = float(getattr(config, "VIDEO_CLOUD_POLL_SEC", 2.0) or 2.0)
    timeout_sec = float(getattr(config, "VIDEO_CLOUD_TIMEOUT", 120.0) or 120.0)
    start = time.time()

    while time.time() - start < timeout_sec:
        try:
            url = _build_status_url(task_id)
            params = None if "{task_id}" in status_url else {"task_id": task_id}
            r = requests.get(url, params=params, headers=_build_headers(), timeout=30)
            if r.status_code != 200:
                time.sleep(poll_sec)
                continue
            payload = r.json() if r.text else {}
        except Exception:
            time.sleep(poll_sec)
            continue

        status = str(payload.get("status") or payload.get("state") or payload.get("task_status") or "").lower()
        if status in ("success", "succeeded", "done", "finished"):
            video_url = _extract_video_url(payload)
            if video_url:
                return _download_video(video_url, out_path)

            # 若未返回 video_url，尝试递归查找可能的 URL
            alt_url = _find_http_url_in_obj(payload)
            if alt_url:
                return _download_video(alt_url, out_path)

            # 尝试在响应中查找 base64 视频内容并写入文件
            b64 = _find_base64_video_in_obj(payload)
            if b64:
                try:
                    # 支持 data:video/...;base64,header 或裸 base64
                    if b64.startswith("data:video/") and ";base64," in b64:
                        raw = b64.split(";base64,", 1)[1]
                    else:
                        raw = b64
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(base64.b64decode(raw))
                    return True, str(out_path)
                except Exception as e:
                    return False, f"提取 base64 视频失败：{e}"

            # 保存完整响应到调试文件，便于离线排查
            try:
                debug_path = out_path.with_suffix(out_path.suffix + ".response.json")
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                debug_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

            return False, "任务完成但未返回视频链接"
        if status in ("failed", "error"):
            return False, f"任务失败：{json.dumps(payload, ensure_ascii=False)[:200]}"

        time.sleep(poll_sec)

    return False, "任务超时"