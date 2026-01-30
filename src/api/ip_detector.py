"""
IP 检测与环境验证
"""
from typing import Tuple, Dict, Any
import re
import config
from utils.logger import logger
from utils.network import request_with_retry

def _fetch_ipinfo() -> Dict[str, Any]:
    """获取 IP 基础信息（ip-api + ipinfo），并做容错合并。"""
    result: Dict[str, Any] = {}
    try:
        response = request_with_retry("GET", config.IP_API_URL, timeout=getattr(config, "IP_API_TIMEOUT", 10))
        response.raise_for_status()
        result.update(response.json() or {})
    except Exception:
        pass

    try:
        params = {}
        if getattr(config, "IPINFO_TOKEN", ""):
            params["token"] = config.IPINFO_TOKEN
        resp = request_with_retry("GET", config.IPINFO_URL, params=params, timeout=getattr(config, "IP_API_TIMEOUT", 10))
        resp.raise_for_status()
        result.update(resp.json() or {})
    except Exception:
        pass
    return result

def _fetch_scamalytics_score(ip_address: str) -> int | None:
    """从 Scamalytics 页面提取 Fraud Score（容错，失败返回 None）。"""
    if not ip_address:
        return None
    try:
        url = f"https://scamalytics.com/ip/{ip_address}"
        resp = request_with_retry("GET", url, timeout=getattr(config, "IP_API_TIMEOUT", 10))
        if resp.status_code != 200:
            return None
        text = resp.text
        # 简单正则提取分数
        m = re.search(r"Fraud\s*Score\s*[:>\s]*([0-9]{1,3})", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    except Exception:
        return None
    return None


def check_ip_safety() -> Tuple[bool, str]:
    """
    检查 IP 地理位置 + Scamalytics 分数 + ISP 类型

    返回:
        (是否安全: bool, 状态详细信息: str)
    """
    if not config.IP_CHECK_ENABLED:
        return True, "IP 检测已禁用"

    try:
        data = _fetch_ipinfo()
        country = data.get("countryCode") or data.get("country", "XX")
        isp = data.get("isp") or data.get("org") or "Unknown"
        ip_address = data.get("query") or data.get("ip") or "N/A"
        city = data.get("city", "N/A")

        # Check country code
        safe_countries = [str(x).upper() for x in (config.SAFE_COUNTRY_CODES or []) if str(x).strip()]
        if safe_countries and str(country).upper() not in safe_countries:
            return False, f"⚠️ 非美区IP: {country} (城市: {city})"

        # Check ISP keyword
        keywords = config.DANGEROUS_ISP_KEYWORDS or []
        is_datacenter = any(str(keyword).lower() in str(isp).lower() for keyword in keywords)
        if is_datacenter:
            return False, f"⚠️ 检测到机房IP (易限流): {isp}"

        # Check ISP type from ipinfo (Hosting/Business)
        allowed_types = [x.strip().lower() for x in (config.IPINFO_ALLOWED_TYPES or "").split(",") if x.strip()]
        blocked_types = [x.strip().lower() for x in (config.IPINFO_BLOCKED_TYPES or "").split(",") if x.strip()]
        isp_type = str(data.get("privacy", {}).get("service", "") or data.get("type", "")).lower()
        if isp_type and blocked_types and any(x in isp_type for x in blocked_types):
            return False, f"⚠️ ISP 类型风险: {isp_type}"
        if isp_type and allowed_types and not any(x in isp_type for x in allowed_types):
            return False, f"⚠️ ISP 类型不合规: {isp_type}"

        # Scamalytics score
        score = _fetch_scamalytics_score(str(ip_address))
        if score is not None and score >= int(getattr(config, "IP_SCAMALYTICS_MAX_SCORE", 30)):
            return False, f"⚠️ Scamalytics 分数过高: {score}"

        return True, f"✓ 环境安全 | IP: {ip_address} | ISP: {isp} | Score: {score if score is not None else 'N/A'}"

    except requests.Timeout:
        logger.warning("IP detection timeout")
        return True, "⚠️ IP 检测超时 (使用默认安全)"
    except Exception as e:
        logger.error(f"IP detection failed: {str(e)}")
        return True, f"⚠️ IP检测失败: {str(e)}"


def get_ip_status_color(is_safe: bool) -> str:
    """根据 IP 安全状态返回 UI 颜色标识。"""
    return "green" if is_safe else "red"
