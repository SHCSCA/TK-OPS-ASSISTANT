"""
EchoTik API Client
Wrapper for EchoTik Open API (https://opendocs.echotik.live)
"""
import requests
import base64
import time
import datetime
from typing import Dict, List, Optional, Tuple
import config
from utils.logger import logger

class EchoTikApiClient:
    """Wrapper for EchoTik Open API"""
    
    BASE_URL = "https://open.echotik.live/api/v3"
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        """
        Initialize EchoTik client
        ARGS:
            api_key: EchoTik Username
            api_secret: EchoTik Password
        """
        self.api_key = api_key or config.ECHOTIK_API_KEY
        self.api_secret = api_secret or config.ECHOTIK_API_SECRET
        self._auth_header = self._generate_auth_header()
        
        # Log init (masked)
        key_masked = f"{self.api_key[:4]}..." if self.api_key else "None"
        logger.info(f"EchoTikApiClient Initialized. Key: {key_masked}")
    
    def _generate_auth_header(self) -> str:
        """Generate Basic Auth header"""
        if not self.api_key or not self.api_secret:
            return ""
        
        credentials = f"{self.api_key}:{self.api_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"
    
    def _request(self, method: str, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Make HTTP request to EchoTik
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": self._auth_header,
            "Content-Type": "application/json"
        }
        
        # Log request details
        logger.info(f"API Request: {method} {url}")
        logger.info(f"Params: {params}")
        
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=20
            )
            
            if response.status_code != 200:
                logger.error(f"API Status Code: {response.status_code}")
                logger.error(f"API Response Text: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"EchoTik API request failed: {str(e)}")
            return None

    def check_connection(self) -> Tuple[bool, str]:
        """
        Check API connectivity
        """
        if not self.api_key or not self.api_secret:
            return False, "请在设置中配置 EchoTik 账号和密码"
        
        endpoint = "/echotik/product/ranklist"
        
        # Using today's date for connectivity check
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Explicit params matching the successful test case
        api_params = {
            "region": "US",
            "rank_type": 1,            # 1 = Day
            "product_rank_field": 1,   # 1 = Sales
            "date": today,
            "page_num": 1,
            "page_size": 1             
        }
        
        try:
            result = self._request("GET", endpoint, api_params)
            
            if result and result.get("code") == 0:
                data = result.get("data", [])
                msg = f"API 连接成功！" 
                if data:
                    msg += f" (获取到 {len(data)} 条数据)"
                return True, msg
            elif result:
                return False, f"API 返回错误: {result.get('message')} ({result.get('code')})"
            else:
                return False, "无法连接到 EchoTik API (请检查网络或日志)"
        except Exception as e:
            return False, f"连接异常: {str(e)}"

    def fetch_trending_products(self, count: int = 100) -> List[Dict]:
        """
        Fetch trending products (Sales Rank List)
        Tries multiple date strategies if 403/Forbidden occurs (handling time skew).
        """
        endpoint = "/echotik/product/ranklist"
        
        current_date_obj = datetime.datetime.now()
        
        # Strategy: Try [Yesterday, Today, 1 Year Ago, 2 Years Ago]
        # This handles the case where System = 2026 but Real World = 2024
        dates_to_try = []
        
        # 1. Yesterday (Standard)
        dates_to_try.append((current_date_obj - datetime.timedelta(days=1)).strftime("%Y-%m-%d"))
        
        # 2. Today
        dates_to_try.append(current_date_obj.strftime("%Y-%m-%d"))
        
        # 3. Last Year (Same Day) - Handling Year Skew
        last_year = current_date_obj.replace(year=current_date_obj.year - 1)
        dates_to_try.append(last_year.strftime("%Y-%m-%d"))

        # 4. Two Years Ago
        two_years_ago = current_date_obj.replace(year=current_date_obj.year - 2)
        dates_to_try.append(two_years_ago.strftime("%Y-%m-%d"))
        
        last_error = None
        
        for date_str in dates_to_try:
            logger.info(f"Attempting fetch with date: {date_str}")
            
            params = {
                "region": "US",
                "rank_type": 1, # 1 = Day
                "product_rank_field": 1,
                "date": date_str,
                "page_num": 1,
                "page_size": 10 # Start with 10
            }
            
            result = self._request("GET", endpoint, params)
            
            if result and result.get("code") == 0:
                products = result.get("data", [])
                logger.info(f"Successfully fetched {len(products)} products using date {date_str}")
                return products
            
            if result:
                 logger.warning(f"Failed with date {date_str}: {result.get('message')}")
        
        logger.error("All date attempts failed.")
        return []
