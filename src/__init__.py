"""
TK-Ops-Assistant Package
"""
from __future__ import annotations

import sys
from pathlib import Path

# 兼容两种启动方式：
# 1) `python src/main.py`（sys.path 已含 src 目录）
# 2) `python -m src.main`（sys.path 默认含项目根目录，但不含 src 目录）
#
# 当前项目大量使用扁平导入（例如 `from ui.xxx import ...`），因此需要确保
# `src/` 在 sys.path 中，才能在两种启动方式下都能解析到 ui/workers/utils/api 等模块。
_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
	sys.path.insert(0, _SRC_DIR)

__version__ = "1.0.0"
__author__ = "TK Operations Team"
__description__ = "TikTok Shop Blue Ocean Detection & Video Processing Tool"
