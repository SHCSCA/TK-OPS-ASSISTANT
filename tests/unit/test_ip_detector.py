"""IP 检测模块单元测试。

覆盖点：
- 国家白名单拦截
- Scamalytics 分数拦截
- 关闭检测时直接放行
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保障测试在任意工作目录下都能解析 src/ 模块
SRC_DIR = (Path(__file__).resolve().parents[2] / "src").resolve()
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import config  # type: ignore[import-not-found]
import api.ip_detector as ip_detector  # type: ignore[import-not-found]


def _patch_config(monkeypatch) -> None:
    """统一打补丁，避免不同测试重复配置。"""
    monkeypatch.setattr(config, "IP_CHECK_ENABLED", True)
    monkeypatch.setattr(config, "SAFE_COUNTRY_CODES", ["US"])
    monkeypatch.setattr(config, "DANGEROUS_ISP_KEYWORDS", ["datacenter", "cloud"])
    monkeypatch.setattr(config, "IPINFO_ALLOWED_TYPES", "ISP,Residential")
    monkeypatch.setattr(config, "IPINFO_BLOCKED_TYPES", "Hosting,Business")
    monkeypatch.setattr(config, "IP_SCAMALYTICS_MAX_SCORE", 30)


def test_ip_check_disabled(monkeypatch):
    """IP 检测关闭时应直接放行。"""
    monkeypatch.setattr(config, "IP_CHECK_ENABLED", False)
    ok, msg = ip_detector.check_ip_safety()
    assert ok is True
    assert "禁用" in msg


def test_ip_country_block(monkeypatch):
    """非白名单国家应被拦截。"""
    _patch_config(monkeypatch)
    monkeypatch.setattr(ip_detector, "_fetch_ipinfo", lambda: {
        "countryCode": "CN",
        "isp": "China Telecom",
        "query": "1.1.1.1",
        "city": "Beijing",
    })
    monkeypatch.setattr(ip_detector, "_fetch_scamalytics_score", lambda _: 0)

    ok, msg = ip_detector.check_ip_safety()
    assert ok is False
    assert "非美区" in msg


def test_ip_scamalytics_block(monkeypatch):
    """Scamalytics 分数过高应被拦截。"""
    _patch_config(monkeypatch)
    monkeypatch.setattr(ip_detector, "_fetch_ipinfo", lambda: {
        "countryCode": "US",
        "isp": "Comcast Cable",
        "query": "8.8.8.8",
        "city": "LA",
        "privacy": {"service": "ISP"},
    })
    monkeypatch.setattr(ip_detector, "_fetch_scamalytics_score", lambda _: 80)

    ok, msg = ip_detector.check_ip_safety()
    assert ok is False
    assert "Scamalytics" in msg
