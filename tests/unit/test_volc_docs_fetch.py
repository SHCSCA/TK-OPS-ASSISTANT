from tts.volc_docs import fetch_voice_types_from_docs


class _Resp:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


def test_fetch_voice_types_from_docs_parses(monkeypatch):
    html = "<div>saturn_zh_male_shuanglangshaonian_tob</div>"

    import tts.volc_docs as vd

    def fake_get(url, timeout=0, headers=None):
        return _Resp(200, html)

    monkeypatch.setattr(vd.requests, "get", fake_get)

    items = fetch_voice_types_from_docs(timeout=1)
    assert "saturn_zh_male_shuanglangshaonian_tob" in items
