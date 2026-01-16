"""
TikTok 蓝海运营助手 - 全局配置
此文件包含项目的所有配置项、API 密钥、文件路径和业务阈值。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

# ===================================================
# 项目基础路径配置
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

# 素材工厂处理视频目录（默认）
PROCESSED_VIDEOS_DIR = _ensure_dir(OUTPUT_DIR / "Processed_Videos")

# 素材库目录（下载/处理结果可归档到此处）
ASSET_LIBRARY_DIR = _ensure_dir(DATA_DIR / "AssetLibrary")

# 下载目录（素材采集器默认输出位置）
DOWNLOAD_DIR = Path(_clean_env_value(os.getenv("DOWNLOAD_DIR")) or str(ASSET_LIBRARY_DIR / "Downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 日志目录
LOG_DIR = _ensure_dir(DATA_DIR / "Logs")

# 日志格式（全局统一）
LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATETIME_FORMAT = "%H:%M:%S"

# ===================================================
# API 密钥与服务配置
# ===================================================
# EchoTik API 配置
ECHOTIK_API_KEY = _clean_env_value(os.getenv("ECHOTIK_API_KEY", ""))       # Username
ECHOTIK_API_SECRET = _clean_env_value(os.getenv("ECHOTIK_API_SECRET", "")) # Password

# RapidAPI（TokApi）配置（可选）
RAPIDAPI_KEY = _clean_env_value(os.getenv("RAPIDAPI_KEY", ""))
RAPIDAPI_HOST = _clean_env_value(os.getenv("RAPIDAPI_HOST", ""))

# 日志级别（默认 INFO）
LOG_LEVEL = (_clean_env_value(os.getenv("LOG_LEVEL", "INFO")) or "INFO").upper()

# 主题模式：dark / light
THEME_MODE = _clean_env_value(os.getenv("THEME_MODE", "dark")) or "dark"

# 应用版本（用于启动日志/诊断输出）
APP_VERSION = _clean_env_value(os.getenv("APP_VERSION", "1.0")) or "1.0"

# ===================================================
# AI 文案助手配置
# ===================================================
# 支持 OpenAI / DeepSeek 等兼容 OpenAI Chat Completions 的服务
AI_PROVIDER = _clean_env_value(os.getenv("AI_PROVIDER", "openai")) or "openai"  # openai | deepseek | compatible
AI_API_KEY = _clean_env_value(os.getenv("AI_API_KEY", "")) or _clean_env_value(os.getenv("DEEPSEEK_API_KEY", ""))
AI_BASE_URL = _clean_env_value(os.getenv("AI_BASE_URL", ""))  # 例如：https://api.deepseek.com
AI_MODEL = _clean_env_value(os.getenv("AI_MODEL", "gpt-4o-mini")) or "gpt-4o-mini"
AI_SYSTEM_PROMPT = _clean_env_value(os.getenv("AI_SYSTEM_PROMPT", ""))

# 火山方舟（Ark）可选参数：深度思考模式。
# 注意：仅部分模型支持该字段；且文档说明“默认开启深度思考模式，可手动关闭”。
# 这里保持默认不发送，由用户按需配置：enabled / disabled（以官方文档为准）。
ARK_THINKING_TYPE = _clean_env_value(os.getenv("ARK_THINKING_TYPE", ""))

# 面板级“自定义角色提示词”（用于：AI 文案助手/AI 二创工厂的输入框，自动持久化）
AI_COPYWRITER_ROLE_PROMPT = _clean_env_value(os.getenv("AI_COPYWRITER_ROLE_PROMPT", ""))
AI_FACTORY_ROLE_PROMPT = _clean_env_value(os.getenv("AI_FACTORY_ROLE_PROMPT", ""))

# 生成结果语言
AI_OUTPUT_LANG = _clean_env_value(os.getenv("AI_OUTPUT_LANG", "en")) or "en"



# ===================================================
# TTS 配音配置（AI 二创工厂）
# ===================================================
TTS_PROVIDER = _clean_env_value(os.getenv("TTS_PROVIDER", "edge-tts")) or "edge-tts"  # edge-tts | volcengine
TTS_FALLBACK_PROVIDER = _clean_env_value(os.getenv("TTS_FALLBACK_PROVIDER", ""))
TTS_VOICE = _clean_env_value(os.getenv("TTS_VOICE", "en-US-AvaNeural")) or "en-US-AvaNeural"
TTS_SPEED = _clean_env_value(os.getenv("TTS_SPEED", "1.1")) or "1.1"

# 火山/豆包 TTS（Token 模式）
VOLC_TTS_ENDPOINT = _clean_env_value(os.getenv("VOLC_TTS_ENDPOINT", "https://openspeech.bytedance.com/api/v1/tts"))
VOLC_TTS_APPID = _clean_env_value(os.getenv("VOLC_TTS_APPID", ""))
# 兼容：旧键 VOLC_TTS_TOKEN -> 新键 VOLC_TTS_ACCESS_TOKEN
VOLC_TTS_ACCESS_TOKEN = _clean_env_value(os.getenv("VOLC_TTS_ACCESS_TOKEN", "")) or _clean_env_value(os.getenv("VOLC_TTS_TOKEN", ""))
VOLC_TTS_SECRET_KEY = _clean_env_value(os.getenv("VOLC_TTS_SECRET_KEY", ""))
VOLC_TTS_TOKEN = _clean_env_value(os.getenv("VOLC_TTS_TOKEN", ""))  # 旧键保留，避免老版本/用户脚本报错
VOLC_TTS_CLUSTER = _clean_env_value(os.getenv("VOLC_TTS_CLUSTER", "volcano_tts")) or "volcano_tts"
VOLC_TTS_VOICE_TYPE = _clean_env_value(os.getenv("VOLC_TTS_VOICE_TYPE", ""))
VOLC_TTS_ENCODING = _clean_env_value(os.getenv("VOLC_TTS_ENCODING", "mp3")) or "mp3"


# ===================================================
# 蓝海选品阈值配置
# ===================================================
def _env_int(name: str, default: int) -> int:
	try:
		raw = os.getenv(name, None)
		text = _clean_env_value(raw)
		if text == "":
			return default
		return int(text)
	except Exception:
		return default


def _env_float(name: str, default: float) -> float:
	try:
		raw = os.getenv(name, None)
		text = _clean_env_value(raw)
		if text == "":
			return default
		return float(text)
	except Exception:
		return default


# ===================================================
# AI Token 成本估算配置
# ===================================================
# 说明：按 1K Token 计价，Prompt 与 Completion 可分别设置
AI_TOKEN_PRICE_PER_1K_PROMPT = _env_float("AI_TOKEN_PRICE_PER_1K_PROMPT", 0.0)
AI_TOKEN_PRICE_PER_1K_COMPLETION = _env_float("AI_TOKEN_PRICE_PER_1K_COMPLETION", 0.0)
AI_TOKEN_CURRENCY = _clean_env_value(os.getenv("AI_TOKEN_CURRENCY", "USD")) or "USD"


GROWTH_RATE_THRESHOLD = _env_int("GROWTH_RATE_THRESHOLD", 500)  # 近7日销量阈值
MAX_REVIEWS = _env_int("MAX_REVIEWS", 50)  # 最大评论数 (评价少代表竞争小)
PRICE_MIN = _env_float("PRICE_MIN", 20.0)  # 最低价格 (USD)
PRICE_MAX = _env_float("PRICE_MAX", 80.0)  # 最高价格 (USD)


# ===================================================
# 字幕样式配置（AI 二创工厂）
# ===================================================
# 说明：这些配置用于 ffmpeg/libass 烧录字幕时的 force_style

SUBTITLE_BURN_ENABLED = (os.getenv("SUBTITLE_BURN_ENABLED", "true").lower() == "true")
SUBTITLE_FONT_NAME = _clean_env_value(os.getenv("SUBTITLE_FONT_NAME", "Microsoft YaHei UI")) or "Microsoft YaHei UI"

# 字号：优先使用像素字号（更直观）；也支持自动按分辨率自适应
SUBTITLE_FONT_AUTO = (os.getenv("SUBTITLE_FONT_AUTO", "true").lower() == "true")
SUBTITLE_FONT_SIZE = _env_int("SUBTITLE_FONT_SIZE", 56)  # px，自动关闭时生效

# 字号：按视频高度比例自适应（例如 1920 高：0.034 -> 65 左右）
SUBTITLE_FONT_SIZE_RATIO = _env_float("SUBTITLE_FONT_SIZE_RATIO", 0.034)
SUBTITLE_FONT_SIZE_MIN = _env_int("SUBTITLE_FONT_SIZE_MIN", 34)
SUBTITLE_FONT_SIZE_MAX = _env_int("SUBTITLE_FONT_SIZE_MAX", 72)

# 描边：支持"自动（按字号自适应）"与"手动像素值（无上限）"两种模式
SUBTITLE_OUTLINE_AUTO = (os.getenv("SUBTITLE_OUTLINE_AUTO", "true").lower() == "true")
SUBTITLE_OUTLINE = _env_int("SUBTITLE_OUTLINE", 4)  # px；手动模式时生效，无上限
SUBTITLE_OUTLINE_MIN = _env_int("SUBTITLE_OUTLINE_MIN", 2)  # 自动模式下限
SUBTITLE_OUTLINE_MAX = _env_int("SUBTITLE_OUTLINE_MAX", 10)  # 自动模式上限

SUBTITLE_SHADOW = _env_int("SUBTITLE_SHADOW", 2)

# 底部边距：按视频高度比例自适应
SUBTITLE_MARGIN_V_RATIO = _env_float("SUBTITLE_MARGIN_V_RATIO", 0.095)
SUBTITLE_MARGIN_V_MIN = _env_int("SUBTITLE_MARGIN_V_MIN", 60)
SUBTITLE_MARGIN_LR = _env_int("SUBTITLE_MARGIN_LR", 40)

# ===================================================
# 视频处理默认参数
# ===================================================
VIDEO_DEEP_REMIX_ENABLED = os.getenv("VIDEO_DEEP_REMIX_ENABLED", "0") == "1"
VIDEO_REMIX_MICRO_ZOOM = os.getenv("VIDEO_REMIX_MICRO_ZOOM", "1") == "1"
VIDEO_REMIX_ADD_NOISE = os.getenv("VIDEO_REMIX_ADD_NOISE", "0") == "1"
VIDEO_REMIX_STRIP_METADATA = os.getenv("VIDEO_REMIX_STRIP_METADATA", "1") == "1"

# ===================================================
# 利润估算模型
# ===================================================
TAOBAO_PRICE_RATIO = 0.2    # 成本估算模型：假设 1688 进货价为 TikTok 售价的 20%
MIN_PROFIT_MARGIN = 15      # 能够被标记为"高利润"的最低毛利率 (%)

# 1688 搜索链接构造基准
TAOBAO_SEARCH_BASE = "https://s.1688.com/selloffer/offer_search.htm?keywords="

# ===================================================
# 视频处理配置（素材工厂）
# ===================================================
VIDEO_SPEED_MULTIPLIER = 1.1      # 全局加速倍率 (V1.0 简单模式: 1.1x)
VIDEO_TRIM_HEAD = 0.5             # 掐头时长 (秒)
VIDEO_TRIM_TAIL = 0.5             # 去尾时长 (秒)
VIDEO_OUTPUT_SUFFIX = "_processed" # 处理后文件名的后缀

# ===================================================
# IP 环境监测配置
# ===================================================
IP_CHECK_ENABLED = os.getenv("IP_CHECK_ENABLED", "true").lower() == "true"
IP_API_URL = "http://ip-api.com/json"  # 免费 IP 检测服务
IP_API_TIMEOUT = 5  # 请求超时时间（秒）


# 需标记为风险的 ISP/机房关键词（用于诊断中心提醒）
DANGEROUS_ISP_KEYWORDS = ["Google", "Amazon", "Microsoft", "Datacenter", "Cloud"]

# 允许的国家/地区代码（TikTok Shop 运营环境约束，默认仅 US）
SAFE_COUNTRY_CODES = ["US"]

# API 重试配置
API_RETRY_COUNT = 3
API_RETRY_DELAY = 2  # 秒；内部使用指数退避

# UI 默认尺寸
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
LOG_WINDOW_HEIGHT = 150


def get_volc_tts_token() -> str:
	"""统一获取火山 TTS Token（新旧键兼容）。

	返回值优先级：
	- VOLC_TTS_ACCESS_TOKEN
	- VOLC_TTS_TOKEN（旧键，兼容保留）
	"""
	access_token = _clean_env_value(getattr(sys.modules[__name__], "VOLC_TTS_ACCESS_TOKEN", ""))
	if access_token:
		return access_token
	legacy_token = _clean_env_value(getattr(sys.modules[__name__], "VOLC_TTS_TOKEN", ""))
	return legacy_token


def reload_config() -> None:
	"""重新加载 .env 并刷新模块内的全局配置。

	用途：
	- UI 保存设置后立即生效（避免 import-time 常量导致“保存不生效”）
	"""
	# 重新加载环境变量（覆盖当前 os.environ）
	load_dotenv(BASE_DIR / ".env", override=True)

	# 刷新关键项（仅刷新运行期会变动的配置；路径类保持稳定且尽量可写）
	global ECHOTIK_API_KEY, ECHOTIK_API_SECRET
	global RAPIDAPI_KEY, RAPIDAPI_HOST
	global AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL
	global AI_SYSTEM_PROMPT, AI_COPYWRITER_ROLE_PROMPT, AI_FACTORY_ROLE_PROMPT
	global AI_OUTPUT_LANG
	global ARK_THINKING_TYPE
	global TTS_PROVIDER, TTS_FALLBACK_PROVIDER, TTS_VOICE, TTS_SPEED
	global VOLC_TTS_ENDPOINT, VOLC_TTS_APPID, VOLC_TTS_ACCESS_TOKEN, VOLC_TTS_SECRET_KEY, VOLC_TTS_TOKEN, VOLC_TTS_CLUSTER, VOLC_TTS_VOICE_TYPE, VOLC_TTS_ENCODING
	global IP_CHECK_ENABLED
	global DOWNLOAD_DIR
	global LOG_LEVEL, THEME_MODE
	global VIDEO_DEEP_REMIX_ENABLED, VIDEO_REMIX_MICRO_ZOOM, VIDEO_REMIX_ADD_NOISE, VIDEO_REMIX_STRIP_METADATA
	global GROWTH_RATE_THRESHOLD, MAX_REVIEWS, PRICE_MIN, PRICE_MAX
	global SUBTITLE_BURN_ENABLED, SUBTITLE_FONT_NAME
	global SUBTITLE_FONT_AUTO, SUBTITLE_FONT_SIZE
	global SUBTITLE_FONT_SIZE_RATIO, SUBTITLE_FONT_SIZE_MIN, SUBTITLE_FONT_SIZE_MAX
	global SUBTITLE_OUTLINE_AUTO, SUBTITLE_OUTLINE
	global SUBTITLE_OUTLINE_MIN, SUBTITLE_OUTLINE_MAX
	global SUBTITLE_SHADOW, SUBTITLE_MARGIN_V_RATIO, SUBTITLE_MARGIN_V_MIN, SUBTITLE_MARGIN_LR

	ECHOTIK_API_KEY = _clean_env_value(os.getenv("ECHOTIK_API_KEY", ""))
	ECHOTIK_API_SECRET = _clean_env_value(os.getenv("ECHOTIK_API_SECRET", ""))
	RAPIDAPI_KEY = _clean_env_value(os.getenv("RAPIDAPI_KEY", ""))
	RAPIDAPI_HOST = _clean_env_value(os.getenv("RAPIDAPI_HOST", ""))

	AI_PROVIDER = _clean_env_value(os.getenv("AI_PROVIDER", "openai")) or "openai"
	AI_API_KEY = _clean_env_value(os.getenv("AI_API_KEY", "")) or _clean_env_value(os.getenv("DEEPSEEK_API_KEY", ""))
	AI_BASE_URL = _clean_env_value(os.getenv("AI_BASE_URL", ""))
	AI_MODEL = _clean_env_value(os.getenv("AI_MODEL", "gpt-4o-mini")) or "gpt-4o-mini"
	AI_SYSTEM_PROMPT = _clean_env_value(os.getenv("AI_SYSTEM_PROMPT", ""))
	AI_OUTPUT_LANG = _clean_env_value(os.getenv("AI_OUTPUT_LANG", "en")) or "en"
	ARK_THINKING_TYPE = _clean_env_value(os.getenv("ARK_THINKING_TYPE", ""))
	AI_COPYWRITER_ROLE_PROMPT = _clean_env_value(os.getenv("AI_COPYWRITER_ROLE_PROMPT", ""))
	AI_FACTORY_ROLE_PROMPT = _clean_env_value(os.getenv("AI_FACTORY_ROLE_PROMPT", ""))

	TTS_PROVIDER = _clean_env_value(os.getenv("TTS_PROVIDER", "edge-tts")) or "edge-tts"
	TTS_FALLBACK_PROVIDER = _clean_env_value(os.getenv("TTS_FALLBACK_PROVIDER", ""))
	TTS_VOICE = _clean_env_value(os.getenv("TTS_VOICE", "en-US-AvaNeural")) or "en-US-AvaNeural"
	TTS_SPEED = _clean_env_value(os.getenv("TTS_SPEED", "1.1")) or "1.1"

	VOLC_TTS_ENDPOINT = _clean_env_value(os.getenv("VOLC_TTS_ENDPOINT", "https://openspeech.bytedance.com/api/v1/tts"))
	VOLC_TTS_APPID = _clean_env_value(os.getenv("VOLC_TTS_APPID", ""))
	VOLC_TTS_ACCESS_TOKEN = _clean_env_value(os.getenv("VOLC_TTS_ACCESS_TOKEN", "")) or _clean_env_value(os.getenv("VOLC_TTS_TOKEN", ""))
	VOLC_TTS_SECRET_KEY = _clean_env_value(os.getenv("VOLC_TTS_SECRET_KEY", ""))
	VOLC_TTS_TOKEN = _clean_env_value(os.getenv("VOLC_TTS_TOKEN", ""))
	VOLC_TTS_CLUSTER = _clean_env_value(os.getenv("VOLC_TTS_CLUSTER", "volcano_tts")) or "volcano_tts"
	VOLC_TTS_VOICE_TYPE = _clean_env_value(os.getenv("VOLC_TTS_VOICE_TYPE", ""))
	VOLC_TTS_ENCODING = _clean_env_value(os.getenv("VOLC_TTS_ENCODING", "mp3")) or "mp3"

	LOG_LEVEL = (_clean_env_value(os.getenv("LOG_LEVEL", "INFO")) or "INFO").upper()
	THEME_MODE = _clean_env_value(os.getenv("THEME_MODE", "dark")) or "dark"

	IP_CHECK_ENABLED = (os.getenv("IP_CHECK_ENABLED", "true").lower() == "true")

	download_dir_text = _clean_env_value(os.getenv("DOWNLOAD_DIR"))
	# 默认下载目录：素材库下 Downloads（更贴合“素材统一归档”工作流）
	DOWNLOAD_DIR = Path(download_dir_text) if download_dir_text else (ASSET_LIBRARY_DIR / "Downloads")
	DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

	VIDEO_DEEP_REMIX_ENABLED = os.getenv("VIDEO_DEEP_REMIX_ENABLED", "0") == "1"
	VIDEO_REMIX_MICRO_ZOOM = os.getenv("VIDEO_REMIX_MICRO_ZOOM", "1") == "1"
	VIDEO_REMIX_ADD_NOISE = os.getenv("VIDEO_REMIX_ADD_NOISE", "0") == "1"
	VIDEO_REMIX_STRIP_METADATA = os.getenv("VIDEO_REMIX_STRIP_METADATA", "1") == "1"

	GROWTH_RATE_THRESHOLD = _env_int("GROWTH_RATE_THRESHOLD", 500)
	MAX_REVIEWS = _env_int("MAX_REVIEWS", 50)
	PRICE_MIN = _env_float("PRICE_MIN", 20.0)
	PRICE_MAX = _env_float("PRICE_MAX", 80.0)

	SUBTITLE_BURN_ENABLED = (os.getenv("SUBTITLE_BURN_ENABLED", "true").lower() == "true")
	SUBTITLE_FONT_NAME = _clean_env_value(os.getenv("SUBTITLE_FONT_NAME", "Microsoft YaHei UI")) or "Microsoft YaHei UI"
	SUBTITLE_FONT_AUTO = (os.getenv("SUBTITLE_FONT_AUTO", "true").lower() == "true")
	SUBTITLE_FONT_SIZE = _env_int("SUBTITLE_FONT_SIZE", 56)
	SUBTITLE_FONT_SIZE_RATIO = _env_float("SUBTITLE_FONT_SIZE_RATIO", 0.034)
	SUBTITLE_FONT_SIZE_MIN = _env_int("SUBTITLE_FONT_SIZE_MIN", 34)
	SUBTITLE_FONT_SIZE_MAX = _env_int("SUBTITLE_FONT_SIZE_MAX", 72)
	SUBTITLE_OUTLINE_AUTO = (os.getenv("SUBTITLE_OUTLINE_AUTO", "true").lower() == "true")
	SUBTITLE_OUTLINE = _env_int("SUBTITLE_OUTLINE", 4)
	SUBTITLE_OUTLINE_MIN = _env_int("SUBTITLE_OUTLINE_MIN", 2)
	SUBTITLE_OUTLINE_MAX = _env_int("SUBTITLE_OUTLINE_MAX", 10)
	SUBTITLE_SHADOW = _env_int("SUBTITLE_SHADOW", 2)
	SUBTITLE_MARGIN_V_RATIO = _env_float("SUBTITLE_MARGIN_V_RATIO", 0.095)
	SUBTITLE_MARGIN_V_MIN = _env_int("SUBTITLE_MARGIN_V_MIN", 60)
	SUBTITLE_MARGIN_LR = _env_int("SUBTITLE_MARGIN_LR", 40)


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


def sync_env_file() -> None:
	"""同步 .env 文件中的关键配置项（只做“补齐/迁移”，不主动清空用户已有值）。

	用途：
	- README/.env.example 与实际运行配置保持一致
	- 兼容历史配置：DEEPSEEK_API_KEY -> AI_API_KEY
	"""
	env_path = _ensure_env_file()

	# 迁移：如果用户旧版只配置了 DEEPSEEK_API_KEY，则自动补齐 AI_API_KEY
	try:
		ai_key = _clean_env_value(os.getenv("AI_API_KEY"))
		legacy_key = _clean_env_value(os.getenv("DEEPSEEK_API_KEY"))
		if not ai_key and legacy_key:
			try:
				set_key(env_path, "AI_API_KEY", legacy_key)
			except Exception:
				pass
			try:
				os.environ["AI_API_KEY"] = legacy_key
			except Exception:
				pass
	except Exception:
		pass

	# 迁移：VOLC_TTS_TOKEN -> VOLC_TTS_ACCESS_TOKEN
	try:
		access_token = _clean_env_value(os.getenv("VOLC_TTS_ACCESS_TOKEN"))
		legacy_token = _clean_env_value(os.getenv("VOLC_TTS_TOKEN"))
		if not access_token and legacy_token:
			try:
				set_key(env_path, "VOLC_TTS_ACCESS_TOKEN", legacy_token)
			except Exception:
				pass
			try:
				os.environ["VOLC_TTS_ACCESS_TOKEN"] = legacy_token
			except Exception:
				pass
	except Exception:
		pass

	# 仅补齐缺失 key：不覆盖用户已有值
	defaults: dict[str, str] = {
		"THEME_MODE": "dark",
		"LOG_LEVEL": "INFO",
		"RAPIDAPI_KEY": "",
		"RAPIDAPI_HOST": "",
		"AI_PROVIDER": "openai",
		"AI_BASE_URL": "",
		"AI_API_KEY": "",
		"AI_MODEL": "gpt-4o-mini",
		"AI_SYSTEM_PROMPT": "",
		"ARK_THINKING_TYPE": "",
		"AI_COPYWRITER_ROLE_PROMPT": "",
		"AI_FACTORY_ROLE_PROMPT": "",
		"AI_OUTPUT_LANG": "en",
		"TTS_PROVIDER": "edge-tts",
		"TTS_FALLBACK_PROVIDER": "",
		"TTS_VOICE": "en-US-AvaNeural",
		"TTS_SPEED": "1.1",
		"VOLC_TTS_ENDPOINT": "https://openspeech.bytedance.com/api/v1/tts",
		"VOLC_TTS_APPID": "",
		"VOLC_TTS_ACCESS_TOKEN": "",
		"VOLC_TTS_SECRET_KEY": "",
		"VOLC_TTS_TOKEN": "",
		"VOLC_TTS_CLUSTER": "volcano_tts",
		"VOLC_TTS_VOICE_TYPE": "",
		"VOLC_TTS_ENCODING": "mp3",
		"LAN_PORT": "8000",
		"LAN_ENABLED": "false",
		"IP_CHECK_ENABLED": "true",
		# 选品阈值（给出默认值，便于用户在 .env 中直接调整）
		"GROWTH_RATE_THRESHOLD": "500",
		"MAX_REVIEWS": "50",
		"PRICE_MIN": "20",
		"PRICE_MAX": "80",
		# 视频处理开关（与代码一致：0/1）
		"VIDEO_DEEP_REMIX_ENABLED": "0",
		"VIDEO_REMIX_MICRO_ZOOM": "1",
		"VIDEO_REMIX_ADD_NOISE": "0",
		"VIDEO_REMIX_STRIP_METADATA": "1",
		# 字幕样式（ffmpeg/libass）
		"SUBTITLE_BURN_ENABLED": "true",
		"SUBTITLE_FONT_NAME": "Microsoft YaHei UI",
		"SUBTITLE_FONT_AUTO": "true",
		"SUBTITLE_FONT_SIZE": "56",
		"SUBTITLE_FONT_SIZE_RATIO": "0.034",
		"SUBTITLE_FONT_SIZE_MIN": "34",
		"SUBTITLE_FONT_SIZE_MAX": "72",
		"SUBTITLE_OUTLINE_AUTO": "true",
		"SUBTITLE_OUTLINE": "4",
		"SUBTITLE_OUTLINE_MIN": "2",
		"SUBTITLE_OUTLINE_MAX": "10",
		"SUBTITLE_SHADOW": "2",
		"SUBTITLE_MARGIN_V_RATIO": "0.095",
		"SUBTITLE_MARGIN_V_MIN": "60",
		"SUBTITLE_MARGIN_LR": "40",
	}

	for key, default_value in defaults.items():
		try:
			current = os.getenv(key)
			if current is None:
				try:
					set_key(env_path, key, default_value)
				except Exception:
					pass
				try:
					os.environ[key] = default_value
				except Exception:
					pass
		except Exception:
			continue


def set_config(key: str, value, persist: bool = True, hot_reload: bool = True) -> None:
	"""统一写配置入口：UI 保存时调用。

	- persist=True：写入 .env
	- hot_reload=True：写入后 reload_config()，保证内存立即生效
	"""
	text = "" if value is None else str(value)

	# 兼容旧键：保持新旧键同步，避免老版本/脚本仍读取旧键。
	aliases: dict[str, list[str]] = {
		"VOLC_TTS_ACCESS_TOKEN": ["VOLC_TTS_TOKEN"],
	}
	if persist:
		env_path = _ensure_env_file()
		try:
			set_key(env_path, key, text)
		except Exception:
			# 兜底：即使写 .env 失败，也尽量更新内存值
			pass

		for alias_key in aliases.get(key, []):
			try:
				set_key(env_path, alias_key, text)
			except Exception:
				pass

	# 先更新环境变量，便于后续 reload_config 读取
	try:
		os.environ[key] = text
	except Exception:
		pass
	for alias_key in aliases.get(key, []):
		try:
			os.environ[alias_key] = text
		except Exception:
			pass

	# 简单同步一次（避免 UI 立即读取旧值）
	try:
		setattr(sys.modules[__name__], key, value)
	except Exception:
		pass
	for alias_key in aliases.get(key, []):
		try:
			setattr(sys.modules[__name__], alias_key, value)
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
