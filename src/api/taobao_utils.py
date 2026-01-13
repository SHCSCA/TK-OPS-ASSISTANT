"""
1688 Taobao utilities for generating search links
"""
import urllib.parse
from typing import List


def generate_taobao_search_url(product_title: str) -> str:
    """
    Generate 1688 keyword search URL from product title
    
    Args:
        product_title: TikTok product title
        
    Returns:
        URL string for 1688 keyword search
    """
    keywords = urllib.parse.quote(product_title)
    return f"https://s.1688.com/selloffer/offer_search.htm?keywords={keywords}"


def extract_keywords_from_title(title: str, max_words: int = 5) -> str:
    """
    Extract core keywords from product title for better search
    
    Args:
        title: Product title
        max_words: Maximum number of words to extract
        
    Returns:
        Extracted keywords string
    """
    # Simple strategy: take first N words (can be improved with NLP)
    words = title.split()[:max_words]
    return " ".join(words)


def validate_taobao_url(url: str) -> bool:
    """
    Validate that URL is a valid 1688 search link
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid
    """
    return url.startswith("https://s.1688.com/selloffer/offer_search.htm")
