"""配置中心相关测试（环境变量解析）。"""
from __future__ import annotations

import os
import config


def test_env_csv_parsing():
    """测试 _env_csv 函数的解析和归一化功能（单元测试，不依赖实际环境）。"""
    # 直接测试内部函数
    from config import _env_csv
    
    # 测试空值返回默认值
    result = _env_csv("NONEXISTENT_VAR", ["DEFAULT"])
    assert result == ["DEFAULT"], f"空值应返回默认，得到 {result}"
    
    # 测试正常解析（不依赖 os.getenv，而是直接调用）
    # 这种方式避免了 monkeypatch 与 load_dotenv 的冲突问题
    os.environ["TEST_CSV_VAR"] = "us, ca,  JP"
    result = _env_csv("TEST_CSV_VAR", ["DEFAULT"], upper=True)
    assert result == ["US", "CA", "JP"], f"期望 ['US', 'CA', 'JP']，实际 {result}"
    
    # 清理测试环境变量
    del os.environ["TEST_CSV_VAR"]


