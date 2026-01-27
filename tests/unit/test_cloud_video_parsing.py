import base64
import json
from pathlib import Path

import pytest

from src.utils.cloud_video import (
    _extract_video_url,
    _find_http_url_in_obj,
    _find_base64_video_in_obj,
)


def test_extract_video_url_top_level():
    payload = {"video_url": "https://cdn.example.com/video.mp4"}
    assert _extract_video_url(payload) == "https://cdn.example.com/video.mp4"


def test_extract_video_url_nested_data():
    payload = {"data": {"video_url": "https://cdn.example.com/nested.mp4"}}
    assert _extract_video_url(payload) == "https://cdn.example.com/nested.mp4"


def test_extract_video_url_outputs_list():
    payload = {"outputs": [{"url": "https://cdn.example.com/out.mp4"}]}
    assert _extract_video_url(payload) == "https://cdn.example.com/out.mp4"


def test_find_http_url_in_obj_deep():
    payload = {"a": {"b": [{"c": "ignore"}, {"file": "http://host/file.mov"}]}}
    assert _find_http_url_in_obj(payload) == "http://host/file.mov"


def test_find_base64_video_with_data_header():
    sample = "data:video/mp4;base64," + base64.b64encode(b"fakevideo").decode()
    payload = {"result": {"content": sample}}
    found = _find_base64_video_in_obj(payload)
    assert found.startswith("data:video/")


def test_find_base64_heuristic_long_string():
    # craft a long base64-ish string
    raw = base64.b64encode(b"x" * 200000).decode()
    payload = {"blob": raw}
    found = _find_base64_video_in_obj(payload)
    assert found == raw
