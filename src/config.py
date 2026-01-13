"""
TikTok 蓝海运营助手 - 全局配置
此文件包含项目的所有配置项、API 密钥、文件路径和业务阈值。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

# ===================================================
# 🏗️ 项目基础路径配置
# ===================================================

def _is_frozen() -> bool:
	return bool(getattr(sys, "frozen", False))


# 冻结态标记（供 UI/日志/诊断使用）
IS_FROZEN = _is_frozen()


def _clean_env_value(value: str | None) -> str:
	"""清洗环境变量值（去掉首尾空格与引号）。

	注意：用户可能在 .env 中写成 KEY='xxx' 或 KEY="xxx"。
	"""
	if value is None:
		return ""
	text = str(value).strip()
	if (text.startswith("\"") and text.endswith("\"")) or (text.startswith("'") and text.endswith("'")):
		text = text[1:-1].strip()
	return text


def _fallback_data_dir() -> Path:
	# Windows 优先用 %LOCALAPPDATA%，其次 %APPDATA%，否则回退到用户目录
	local_appdata = os.getenv("LOCALAPPDATA")
	if local_appdata:
		return Path(local_appdata) / "TK-Ops-Pro"
	appdata = os.getenv("APPDATA")
	if appdata:
		return Path(appdata) / "TK-Ops-Pro"
	return Path.home() / ".tk-ops-pro"


def _ensure_dir(path: Path) -> Path:
	try:
		path.mkdir(parents=True, exist_ok=True)
		return path
	except Exception:
		# 目录不可写时回退到可写目录（尽量保留末级目录名）
		fallback_root = _fallback_data_dir()
		try:
			fallback_root.mkdir(parents=True, exist_ok=True)
		except Exception:
			pass
		fallback = fallback_root / path.name
		try:
			fallback.mkdir(parents=True, exist_ok=True)
			return fallback
		except Exception:
			return fallback_root


# 运行目录：源码模式用项目根目录；打包(onefile)模式用 exe 所在目录
if IS_FROZEN:
	# 冻结态：代码目录在 exe 附近，但数据目录优先落到可写位置
	BASE_DIR = Path(sys.executable).resolve().parent
	DATA_DIR = _ensure_dir(_fallback_data_dir())
else:
	BASE_DIR = Path(__file__).resolve().parent.parent
	DATA_DIR = BASE_DIR

SRC_DIR = Path(__file__).resolve().parent  # 源代码目录 src/

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# 输出目录 (Excel 报告和处理后的视频)
OUTPUT_DIR = _ensure_dir(DATA_DIR / "Output")

# 素材库目录（下载/处理结果可归档到此处）
ASSET_LIBRARY_DIR = _ensure_dir(DATA_DIR / "AssetLibrary")

# 下载目录（素材采集器默认输出位置）
DOWNLOAD_DIR = Path(_clean_env_value(os.getenv("DOWNLOAD_DIR")) or str(OUTPUT_DIR / "Downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 日志目录
LOG_DIR = _ensure_dir(DATA_DIR / "Logs")

# 日志格式（全局统一）
LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATETIME_FORMAT = "%H:%M:%S"

# ===================================================
# 🔑 API 密钥与服务配置
# ===================================================
# EchoTik API 配置
ECHOTIK_API_KEY = _clean_env_value(os.getenv("ECHOTIK_API_KEY", ""))       # Username
ECHOTIK_API_SECRET = _clean_env_value(os.getenv("ECHOTIK_API_SECRET", "")) # Password

# 日志级别（默认 INFO）
LOG_LEVEL = (_clean_env_value(os.getenv("LOG_LEVEL", "INFO")) or "INFO").upper()

# 主题模式：dark / light
THEME_MODE = _clean_env_value(os.getenv("THEME_MODE", "dark")) or "dark"

# 应用版本（用于启动日志/诊断输出）
APP_VERSION = _clean_env_value(os.getenv("APP_VERSION", "1.0")) or "1.0"

# ===================================================
# 🤖 AI 文案助手配置
# ===================================================
# 支持 OpenAI / DeepSeek 等兼容 OpenAI Chat Completions 的服务
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")  # openai | deepseek | compatible
AI_API_KEY = _clean_env_value(os.getenv("AI_API_KEY", ""))
AI_BASE_URL = _clean_env_value(os.getenv("AI_BASE_URL", ""))  # 例如：https://api.deepseek.com
AI_MODEL = _clean_env_value(os.getenv("AI_MODEL", "gpt-4o-mini")) or "gpt-4o-mini"

# 生成结果语言
AI_OUTPUT_LANG = os.getenv("AI_OUTPUT_LANG", "en")


# ===================================================
# 📊 蓝海选品阈值配置
# ===================================================
def _env_int(name: str, default: int) -> int:
	try:
		return int(float(_clean_env_value(os.getenv(name, str(default))) or str(default)))
	except Exception:
		return default


def _env_float(name: str, default: float) -> float:
	try:
		return float(_clean_env_value(os.getenv(name, str(default))) or str(default))
	except Exception:
		return default


GROWTH_RATE_THRESHOLD = _env_int("GROWTH_RATE_THRESHOLD", 500)  # 近7日销量阈值
MAX_REVIEWS = _env_int("MAX_REVIEWS", 50)  # 最大评论数 (评价少代表竞争小)
PRICE_MIN = _env_float("PRICE_MIN", 20.0)  # 最低价格 (USD)
PRICE_MAX = _env_float("PRICE_MAX", 80.0)  # 最高价格 (USD)

# ===================================================
# 🎬 视频处理默认参数
# ===================================================
VIDEO_DEEP_REMIX_ENABLED = os.getenv("VIDEO_DEEP_REMIX_ENABLED", "0") == "1"
VIDEO_REMIX_MICRO_ZOOM = os.getenv("VIDEO_REMIX_MICRO_ZOOM", "1") == "1"
VIDEO_REMIX_ADD_NOISE = os.getenv("VIDEO_REMIX_ADD_NOISE", "0") == "1"
VIDEO_REMIX_STRIP_METADATA = os.getenv("VIDEO_REMIX_STRIP_METADATA", "1") == "1"

# ===================================================
# 💰 利润估算模型
# ===================================================
TAOBAO_PRICE_RATIO = 0.2    # 成本估算模型：假设 1688 进货价为 TikTok 售价的 20%
MIN_PROFIT_MARGIN = 15      # 能够被标记为"高利润"的最低毛利率 (%)

# 1688 搜索链接构造基准
TAOBAO_SEARCH_BASE = "https://s.1688.com/selloffer/offer_search.htm?keywords="

# ===================================================
# 🎬 视频处理配置 (素材工厂)
# ===================================================
VIDEO_SPEED_MULTIPLIER = 1.1      # 全局加速倍率 (V1.0 简单模式: 1.1x)
VIDEO_TRIM_HEAD = 0.5             # 掐头时长 (秒)
VIDEO_TRIM_TAIL = 0.5             # 去尾时长 (秒)
VIDEO_OUTPUT_SUFFIX = "_processed" # 处理后文件名的后缀

# ===================================================
# 🌍 IP 环境监测配置
# ===================================================
IP_CHECK_ENABLED = os.getenv("IP_CHECK_ENABLED", "true").lower() == "true"
IP_API_URL = "http://ip-api.com/json" # 免费 IP检测服务
IP_API_TIMEOUT = 5                    # 请求超时时间 (秒)


# Dangerous ISP/Datacenter keywords to flag
DANGEROUS_ISP_KEYWORDS = ["Google", "Amazon", "Microsoft", "Datacenter", "Cloud"]
SAFE_COUNTRY_CODES = ["US"]  # Only US is safe for TikTok Shop operations

# API Retry Configuration
API_RETRY_COUNT = 3
API_RETRY_DELAY = 2  # seconds, uses exponential backoff

# UI Configuration
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
LOG_WINDOW_HEIGHT = 150


def reload_config() -> None:
	"""重新加载 .env 并刷新模块内的全局配置。

	用途：
	- UI 保存设置后立即生效（避免 import-time 常量导致“保存不生效”）
	"""
	# 重新加载环境变量（覆盖当前 os.environ）
	load_dotenv(BASE_DIR / ".env", override=True)

	# 刷新关键项（仅刷新运行期会变动的配置；路径类保持稳定且尽量可写）
	global ECHOTIK_API_KEY, ECHOTIK_API_SECRET
	global AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL
	global IP_CHECK_ENABLED
	global DOWNLOAD_DIR
	global LOG_LEVEL, THEME_MODE
	global VIDEO_DEEP_REMIX_ENABLED, VIDEO_REMIX_MICRO_ZOOM, VIDEO_REMIX_ADD_NOISE, VIDEO_REMIX_STRIP_METADATA
	global GROWTH_RATE_THRESHOLD, MAX_REVIEWS, PRICE_MIN, PRICE_MAX

	ECHOTIK_API_KEY = _clean_env_value(os.getenv("ECHOTIK_API_KEY", ""))
	ECHOTIK_API_SECRET = _clean_env_value(os.getenv("ECHOTIK_API_SECRET", ""))

	AI_PROVIDER = _clean_env_value(os.getenv("AI_PROVIDER", "openai")) or "openai"
	AI_API_KEY = _clean_env_value(os.getenv("AI_API_KEY", ""))
	AI_BASE_URL = _clean_env_value(os.getenv("AI_BASE_URL", ""))
	AI_MODEL = _clean_env_value(os.getenv("AI_MODEL", "gpt-4o-mini")) or "gpt-4o-mini"

	LOG_LEVEL = (_clean_env_value(os.getenv("LOG_LEVEL", "INFO")) or "INFO").upper()
	THEME_MODE = _clean_env_value(os.getenv("THEME_MODE", "dark")) or "dark"

	IP_CHECK_ENABLED = (os.getenv("IP_CHECK_ENABLED", "true").lower() == "true")

	download_dir_text = _clean_env_value(os.getenv("DOWNLOAD_DIR"))
	DOWNLOAD_DIR = Path(download_dir_text) if download_dir_text else (OUTPUT_DIR / "Downloads")
	DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

	VIDEO_DEEP_REMIX_ENABLED = os.getenv("VIDEO_DEEP_REMIX_ENABLED", "0") == "1"
	VIDEO_REMIX_MICRO_ZOOM = os.getenv("VIDEO_REMIX_MICRO_ZOOM", "1") == "1"
	VIDEO_REMIX_ADD_NOISE = os.getenv("VIDEO_REMIX_ADD_NOISE", "0") == "1"
	VIDEO_REMIX_STRIP_METADATA = os.getenv("VIDEO_REMIX_STRIP_METADATA", "1") == "1"

	GROWTH_RATE_THRESHOLD = _env_int("GROWTH_RATE_THRESHOLD", 500)
	MAX_REVIEWS = _env_int("MAX_REVIEWS", 50)
	PRICE_MIN = _env_float("PRICE_MIN", 20.0)
	PRICE_MAX = _env_float("PRICE_MAX", 80.0)


def get_config(key: str, default=None):
	"""从内存配置读取配置项。"""
	return getattr(sys.modules[__name__], key, default)


def _ensure_env_file() -> Path:
	env_path = BASE_DIR / ".env"
	try:
		if not env_path.exists():
			env_path.write_text("", encoding="utf-8")
	except Exception:
		pass
	return env_path


def set_config(key: str, value, persist: bool = True, hot_reload: bool = True) -> None:
	"""统一写配置入口：UI 保存时调用。

	- persist=True：写入 .env
	- hot_reload=True：写入后 reload_config()，保证内存立即生效
	"""
	text = "" if value is None else str(value)
	if persist:
		env_path = _ensure_env_file()
		try:
			set_key(env_path, key, text)
		except Exception:
			# 兜底：即使写 .env 失败，也尽量更新内存值
			pass

	# 先更新环境变量，便于后续 reload_config 读取
	try:
		os.environ[key] = text
	except Exception:
		pass

	# 简单同步一次（避免 UI 立即读取旧值）
	try:
		setattr(sys.modules[__name__], key, value)
	except Exception:
		pass

	if hot_reload:
		try:
			reload_config()
		except Exception:
			pass


def validate_required_config() -> list[str]:
	"""检查必填配置，返回中文缺失项列表（用于启动提示/诊断中心）。"""
	missing: list[str] = []
	if not _clean_env_value(getattr(sys.modules[__name__], "ECHOTIK_API_KEY", "")):
		missing.append("EchoTik API Key（Username）")
	if not _clean_env_value(getattr(sys.modules[__name__], "ECHOTIK_API_SECRET", "")):
		missing.append("EchoTik API Secret（Password）")

	# 目录类：只检查可写性基础存在（深度检测交给诊断中心）
	for label, path in (
		("输出目录 OUTPUT_DIR", OUTPUT_DIR),
		("日志目录 LOG_DIR", LOG_DIR),
		("下载目录 DOWNLOAD_DIR", DOWNLOAD_DIR),
	):
		try:
			Path(path).mkdir(parents=True, exist_ok=True)
		except Exception:
			missing.append(f"{label}（不可创建/不可写）")
	return missing


def _mask_secret(value: str) -> str:
	text = _clean_env_value(value)
	if not text:
		return ""
	if len(text) <= 6:
		return "***"
	return f"{text[:2]}***{text[-2:]}"


def get_startup_info() -> dict:
	"""用于启动日志/诊断中心的信息（包含脱敏配置）。"""
	info: dict = {
		"app_version": APP_VERSION,
		"python_version": sys.version.split()[0],
		"is_frozen": bool(IS_FROZEN),
		"base_dir": str(BASE_DIR),
		"data_dir": str(DATA_DIR),
		"output_dir": str(OUTPUT_DIR),
		"log_dir": str(LOG_DIR),
		"download_dir": str(DOWNLOAD_DIR),
		"theme_mode": THEME_MODE,
		"echotik_api_key": _mask_secret(getattr(sys.modules[__name__], "ECHOTIK_API_KEY", "")),
		"echotik_api_secret": _mask_secret(getattr(sys.modules[__name__], "ECHOTIK_API_SECRET", "")),
	}
	return info
