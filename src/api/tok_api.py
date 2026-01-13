"""
TikTok API client wrapper for RapidAPI TokApi
"""
import requests
import time
from typing import Dict, List, Optional
import config
from utils.logger import logger


class TokApiClient:
    """Wrapper for RapidAPI TokApi service"""
    
    def __init__(self, api_key: str | None = None, api_host: str | None = None):
        """
        Initialize TokApi client
        
        Args:
            api_key: RapidAPI key
            api_host: RapidAPI host endpoint
        """
        self.api_key = api_key if api_key is not None else getattr(config, "RAPIDAPI_KEY", "")
        self.api_host = api_host if api_host is not None else getattr(config, "RAPIDAPI_HOST", "")
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
            "Content-Type": "application/json"
        }
        self.base_url = f"https://{self.api_host}" if self.api_host else ""
    
    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int | None = None,
        **kwargs
    ) -> Optional[Dict]:
        """
        Make HTTP request with exponential backoff retry
        
        Args:
            method: HTTP method (GET, POST)
            url: Request URL
            max_retries: Maximum retry attempts
            **kwargs: Additional request parameters
            
        Returns:
            Response JSON dict or None if failed
        """
        retries = max_retries if max_retries is not None else getattr(config, "API_RETRY_COUNT", 3)
        for attempt in range(retries):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    timeout=10,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            
            except requests.Timeout:
                logger.warning(f"API 请求超时 (尝试 {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    delay = getattr(config, "API_RETRY_DELAY", 2) ** (attempt + 1)
                    time.sleep(delay)
            
            except requests.RequestException as e:
                logger.error(f"API 请求失败: {str(e)}")
                if attempt < retries - 1:
                    delay = getattr(config, "API_RETRY_DELAY", 2) ** (attempt + 1)
                    time.sleep(delay)
                else:
                    return None
        
        return None
    
    def fetch_trending(self, count: int = 100) -> Optional[List[Dict]]:
        """
        获取 TikTok Shop 热门商品

        Args:
            count: 获取数量
            
        Returns:
            商品列表或 None
        """
        url = f"{self.base_url}/api/v1/shop/trending"
        params = {"count": count}
        
        logger.info(f"正在从 TikTok API 获取 {count} 个热门商品...")
        result = self._request_with_retry("GET", url, params=params)
        
        if result:
            products = result.get('data', [])
            return products
        return None

    def check_connection(self) -> tuple[bool, str]:
        """
        Check API connectivity with a lightweight request
        
        Returns:
            (is_connected, message)
        """
        try:
            if not self.api_key or not self.api_host or not self.base_url:
                return False, "未配置 RapidAPI Key/Host，请先在系统设置中填写并保存。"

            # Using trending endpoint with count=1 as a connectivity check
            # Note: fetch_trending uses /api/v1/shop/trending. 
            # If the user says endpoints are deprecated, this test will confirm if this specific one works.
            url = f"{self.base_url}/api/v1/shop/trending"
            params = {"count": 1}
            
            logger.info("Performing API connectivity check...")
            # Do a single attempt, no retries for check
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                # RapidAPI TokApi usually returns 'data' or 'products'
                if isinstance(data, dict):
                    return True, "API 连接成功！"
                else:
                    return True, f"API 连接成功，但返回数据非 JSON: {str(data)[:50]}"
            elif response.status_code == 401:
                return False, "API Key 无效或未授权 (401)"
            elif response.status_code == 403:
                return False, "API 访问受限 (403) - 请检查订阅状态"
            else:
                return False, f"API 返回错误: {response.status_code} - {response.text[:100]}"
                
        except Exception as e:
            return False, f"连接发生异常: {str(e)}"
    
    def search_products(self, keyword: str, count: int = 50) -> Optional[List[Dict]]:
        """
        Search products by keyword on TikTok Shop
        
        Args:
            keyword: Search keyword
            count: Number of results
            
        Returns:
            List of product dictionaries or None if failed
        """
        url = f"{self.base_url}/api/v1/shop/search"
        params = {"keyword": keyword, "count": count}
        
        logger.info(f"Searching products with keyword: {keyword}")
        result = self._request_with_retry("GET", url, params=params)
        
        if result:
            products = result.get('data', [])
            logger.success(f"Found {len(products)} products matching '{keyword}'")
            return products
        else:
            logger.error(f"Search failed for keyword: {keyword}")
            return None
    
    def get_product_details(self, product_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific product
        
        Args:
            product_id: Product ID
            
        Returns:
            Product details dictionary or None if failed
        """
        url = f"{self.base_url}/api/v1/shop/product/{product_id}"
        
        logger.debug(f"Fetching details for product: {product_id}")
        result = self._request_with_retry("GET", url)
        
        return result.get('data') if result else None
