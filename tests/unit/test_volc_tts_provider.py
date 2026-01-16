import base64
from pathlib import Path

import pytest

from tts.volcengine_provider import synthesize_volcengine_token
from tts.types import TtsError


class _FakeResp:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_synthesize_volcengine_token_writes_file_and_headers(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout

        audio = base64.b64encode(b"abc").decode("ascii")
        return _FakeResp(200, {"code": 0, "message": "success", "data": audio})

    import tts.volcengine_provider as provider

    monkeypatch.setattr(provider.requests, "post", fake_post)

    out = tmp_path / "out.mp3"
    synthesize_volcengine_token(
        text="OK",
        out_path=out,
        appid="6049891965",
        token="ACCESS_TOKEN_X",
        voice_type="saturn_zh_male_shuanglangshaonian_tob",
        speed_text="1.0",
        cluster="volcano_tts",
        encoding="mp3",
        endpoint="https://openspeech.bytedance.com/api/v1/tts",
    )

    assert out.exists()
    assert out.read_bytes() == b"abc"

    # 关键：我们在 provider 里同时带 Authorization 和 X-Api-* 头
    headers = captured["headers"]
    assert headers["X-Api-App-Key"] == "6049891965"
    assert headers["X-Api-Access-Key"] == "ACCESS_TOKEN_X"
    assert "Authorization" in headers


def test_synthesize_volcengine_token_missing_voice_type(tmp_path: Path):
    out = tmp_path / "out.mp3"
    with pytest.raises(TtsError):
        synthesize_volcengine_token(
            text="OK",
            out_path=out,
            appid="6049891965",
            token="ACCESS_TOKEN_X",
            voice_type="",
            speed_text="1.0",
        )
