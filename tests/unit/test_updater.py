import io
import os
from pathlib import Path

import pytest

from utils import updater


class _DummyResp:
    def __init__(self, content: bytes, status_code: int = 200, headers: dict | None = None):
        self._content = content
        self.status_code = status_code
        self.headers = headers or {"content-length": str(len(content))}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=8192):
        stream = io.BytesIO(self._content)
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_normalize_update_url_gitee():
    url = "https://api.github.com/repos/owner/repo/releases/latest"
    out = updater._normalize_update_url("gitee", url)
    assert out == "https://gitee.com/api/v5/repos/owner/repo/releases/latest"


def test_parse_release_accepts_zip_and_exe():
    data = {
        "tag_name": "V2.2.2",
        "assets": [
            {"name": "release.zip", "browser_download_url": "https://x/release.zip"},
            {"name": "app.exe", "browser_download_url": "https://x/app.exe"},
        ],
        "body": "notes",
    }
    ver, url, body = updater._parse_gitee_release(data)
    assert ver == "2.2.2"
    assert url.endswith(".zip")
    assert body == "notes"


def test_downloader_retries_when_zip_is_html(monkeypatch, tmp_path):
    calls = []

    def _fake_download(self, url: str, local_path: str, part_path: str) -> None:
        calls.append(url)
        # first call writes html, second writes a minimal zip header
        if len(calls) == 1:
            Path(local_path).write_bytes(b"<html>not zip</html>")
        else:
            Path(local_path).write_bytes(b"PK\x03\x04")

    monkeypatch.setattr(updater.UpdateDownloader, "_download_to", _fake_download)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))

    # zipfile.is_zipfile uses file signature; emulate by checking bytes
    def _fake_is_zipfile(p):
        data = Path(p).read_bytes()
        return data.startswith(b"PK")

    monkeypatch.setattr(updater.zipfile, "is_zipfile", _fake_is_zipfile)

    dl = updater.UpdateDownloader("https://gitee.com/x/archive/refs/tags/V2.2.2.zip")
    results = {}
    dl.finished.connect(lambda ok, path: results.update({"ok": ok, "path": path}))
    dl.run()

    assert calls[0].endswith("V2.2.2.zip")
    assert "download=1" in calls[1]
    assert results.get("ok") is True
    assert results.get("path", "").endswith("V2.2.2.zip")


def test_auto_updater_missing_installer(monkeypatch):
    monkeypatch.setattr(updater.os.path, "exists", lambda p: False)
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    assert updater.AutoUpdater.install_and_restart("C:/nope.zip") is False
