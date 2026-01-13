"""
Unit tests for API utilities
"""
import pytest
from api.taobao_utils import (
    generate_taobao_search_url,
    extract_keywords_from_title,
    validate_taobao_url
)


class TestTaobaoUtils:
    """Test 1688 utility functions"""
    
    def test_generate_taobao_search_url(self):
        """Test URL generation"""
        title = "Cute Cat Water Bottle"
        url = generate_taobao_search_url(title)
        
        assert url.startswith("https://s.1688.com/selloffer/offer_search.htm")
        assert "keywords=" in url
        assert "Cute" in url or "Cat" in url
    
    def test_extract_keywords(self):
        """Test keyword extraction"""
        title = "Wireless Bluetooth Headphones Pro Max"
        keywords = extract_keywords_from_title(title, max_words=3)
        
        assert "Wireless" in keywords
        assert "Bluetooth" in keywords
        assert len(keywords.split()) <= 3
    
    def test_validate_taobao_url(self):
        """Test URL validation"""
        valid_url = "https://s.1688.com/selloffer/offer_search.htm?keywords=test"
        invalid_url = "https://example.com/test"
        
        assert validate_taobao_url(valid_url) == True
        assert validate_taobao_url(invalid_url) == False
