"""配置中心相关测试（环境变量解析）。"""
from __future__ import annotations

import config


def test_env_csv_parsing(monkeypatch):
    """确保逗号分隔配置能正确解析并归一化。"""
    monkeypatch.setenv("SAFE_COUNTRY_CODES", "us, ca,  JP")
    monkeypatch.setenv("DANGEROUS_ISP_KEYWORDS", "Google, Amazon,Cloud")

    # 触发热加载
    config.reload_config()

    assert config.SAFE_COUNTRY_CODES == ["US", "CA", "JP"]
    assert config.DANGEROUS_ISP_KEYWORDS == ["Google", "Amazon", "Cloud"]
