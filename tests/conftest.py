"""
Conftest - pytest configuration and fixtures
"""
import os
import sys
import pytest
from pathlib import Path


# 确保 tests 在任意工作目录下执行时，都能导入 src/ 下的模块
SRC_DIR = (Path(__file__).resolve().parent.parent / "src").resolve()
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# 让单元测试不受本地 .env 影响（config.py 在 import 时会 load_dotenv，但默认不覆盖已存在的环境变量）
os.environ["GROWTH_RATE_THRESHOLD"] = "500"
os.environ["MAX_REVIEWS"] = "50"
os.environ["PRICE_MIN"] = "20"
os.environ["PRICE_MAX"] = "80"


@pytest.fixture
def sample_product():
    """Provide a sample product dictionary"""
    return {
        'id': '12345',
        'title': 'Test Product',
        'price': 45.99,
        'growth_rate': 600,
        'review_count': 25,
        'main_image_url': 'https://example.com/image.jpg',
        'tk_url': 'https://tiktok.com/product/12345',
        'top_video_url': 'https://tiktok.com/video/67890'
    }


@pytest.fixture
def sample_video_file(tmp_path):
    """Provide a sample video file path"""
    video_file = tmp_path / "test_video.mp4"
    video_file.touch()
    return str(video_file)
