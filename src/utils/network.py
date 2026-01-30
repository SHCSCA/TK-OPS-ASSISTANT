"""
网络请求工具模块 (Task 5)
提供统一的、带重试机制和超时的网络请求会话，
并支持 User-Agent 轮询（简单的指纹基础）。
"""
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import random
import logging

logger = logging.getLogger(__name__)

# 默认浏览器 User-Agents
DEFAULT_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
]

def get_session(
    retries: int = 3, 
    backoff_factor: float = 0.5, 
    timeout: int = 15,
    random_ua: bool = True
) -> requests.Session:
    """
    创建一个预配置的 Requests Session
    
    Features:
    - 自动重试 (Retries)
    - 超时设置 (Timeout - 需在 request 调用时显式传递，或通过 wrapper 封装)
    - 随机 User-Agent
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    if random_ua:
        session.headers.update({
            "User-Agent": random.choice(DEFAULT_AGENTS)
        })
        
    return session

def request_with_retry(method: str, url: str, **kwargs):
    """
    简易的带重试请求封装 (Utility wrap)
    """
    timeout = kwargs.pop('timeout', 15) # 默认超时 15秒
    with get_session() as s:
        try:
            return s.request(method, url, timeout=timeout, **kwargs)
        except Exception as e:
            logger.error(f"Network Request Failed [{method} {url}]: {e}")
            raise
