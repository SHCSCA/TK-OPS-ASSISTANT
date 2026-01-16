"""
IP 检测与环境验证
"""
import requests
from typing import Tuple
import config
from utils.logger import logger


def check_ip_safety() -> Tuple[bool, str]:
    """
    检查 IP 地理位置和数据中心状态
    
    返回:
        (是否安全: bool, 状态详细信息: str)
    """
    if not config.IP_CHECK_ENABLED:
        return True, "IP 检测已禁用"
    
    try:
        response = requests.get(config.IP_API_URL, timeout=config.IP_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        country = data.get('countryCode', 'XX')
        isp = data.get('isp', 'Unknown')
        ip_address = data.get('query', 'N/A')
        city = data.get('city', 'N/A')
        
        # Check country code
        if country not in config.SAFE_COUNTRY_CODES:
            return False, f"⚠️ 非美区IP: {country} (城市: {city})"
        
        # Check for datacenter/cloud provider IPs
        is_datacenter = any(keyword in isp for keyword in config.DANGEROUS_ISP_KEYWORDS)
        if is_datacenter:
            return False, f"⚠️ 检测到机房IP (易限流): {isp}"
        
        # Safe
        return True, f"✓ 环境安全 | IP: {ip_address} | ISP: {isp}"
    
    except requests.Timeout:
        logger.warning("IP detection timeout")
        return True, "⚠️ IP 检测超时 (使用默认安全)"
    except Exception as e:
        logger.error(f"IP detection failed: {str(e)}")
        return True, f"⚠️ IP检测失败: {str(e)}"


def get_ip_status_color(is_safe: bool) -> str:
    """根据 IP 安全状态返回 UI 颜色标识。"""
    return "green" if is_safe else "red"
