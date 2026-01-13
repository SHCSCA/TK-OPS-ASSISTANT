"""
Unit tests for configuration
"""
import pytest
from config import (
    GROWTH_RATE_THRESHOLD,
    MAX_REVIEWS,
    PRICE_MIN,
    PRICE_MAX,
    VIDEO_SPEED_MULTIPLIER
)


class TestConfiguration:
    """Test configuration values"""
    
    def test_growth_rate_threshold(self):
        """Test growth rate threshold"""
        assert GROWTH_RATE_THRESHOLD == 500
        assert GROWTH_RATE_THRESHOLD > 0
    
    def test_review_limits(self):
        """Test review count limits"""
        assert MAX_REVIEWS == 50
        assert MAX_REVIEWS > 0
    
    def test_price_range(self):
        """Test price range configuration"""
        assert PRICE_MIN == 20
        assert PRICE_MAX == 80
        assert PRICE_MIN < PRICE_MAX
    
    def test_video_speed(self):
        """Test video speed multiplier"""
        assert VIDEO_SPEED_MULTIPLIER == 1.1
        assert 0.5 <= VIDEO_SPEED_MULTIPLIER <= 2.0
