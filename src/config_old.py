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

# Version
# APP_VERSION is now dynamic (see below)

# Telemetry
SENTRY_DSN = os.getenv("SENTRY_DSN", "") # 空字符串表示禁用

# Auto Update (初始化依赖 _clean_env_value，定义在函数之后)

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


# Auto Update
UPDATE_PROVIDER = _clean_env_value(os.getenv("UPDATE_PROVIDER", "github")) or "github"
UPDATE_CHECK_URL = _clean_env_value(os.getenv("UPDATE_CHECK_URL", "https://api.github.com/repos/SHCSCA/TK-OPS-ASSISTANT/releases/latest"))


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
	# 冻结态：代码目录在 exe 附近
	BASE_DIR = Path(sys.executable).resolve().parent

	# 【架构优化】智能便携模式 (Smart Portable Mode)
	# 1. 优先尝试在 EXE 同级目录存储数据（Logs/Output/AssetLibrary），实现“即插即用”。
	# 2. 如果所在目录不可写（例如安装在 C:\Program Files），自动降级到系统 AppData 目录，防止权限报错。
	try:
		# 写入测试
		test_write_path = BASE_DIR / ".perm_check"
		test_write_path.write_text("ok", encoding="utf-8")
		test_write_path.unlink() # 清理测试文件
		
		# 测试通过：使用便携模式
		# 【UI美学优化】为避免在桌面生成过多杂乱文件夹，将 Logs/Output/AssetLibrary 统一收纳到 'tk_data' 目录
		DATA_DIR = BASE_DIR / "tk_data"
		try:
			DATA_DIR.mkdir(exist_ok=True)
		except Exception:
			# 极少情况无法创建子目录，回退到根目录
			DATA_DIR = BASE_DIR
	except Exception:
		# 测试失败（无权限）：使用 AppData 模式
		DATA_DIR = _ensure_dir(_fallback_data_dir())
else:
	BASE_DIR = Path(__file__).resolve().parent.parent
	DATA_DIR = BASE_DIR

SRC_DIR = Path(__file__).resolve().parent  # 源代码目录 src/

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# ===================================================
# 版本号管理 (Dynamic Versioning)
# ===================================================
def _get_app_version() -> str:
    """获取应用版本号。
    优先读取运行目录下的 APP_VERSION.txt (由更新程序生成)，
    如果不存在，则使用默认的硬编码版本。
    """
    try:
        ver_file = BASE_DIR / "APP_VERSION.txt"
        if ver_file.exists():
            v = ver_file.read_text(encoding="utf-8").strip()
            if v:
                return v
    except Exception:
        pass
    return "2.2.3" # Default Fallback

APP_VERSION = _get_app_version()


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

# 主题模式：dark / light（默认浅色）
THEME_MODE = _clean_env_value(os.getenv("THEME_MODE", "light")) or "light"

# 是否显示 EchoTik 配置（默认隐藏）
SHOW_ECHOTIK_SETTINGS = _clean_env_value(os.getenv("SHOW_ECHOTIK_SETTINGS", "false")).lower() == "true"

# 应用版本（用于启动日志/诊断输出）
def _load_app_version() -> str:
	"""优先读取本地版本文件，其次读取环境变量。"""
	try:
		ver_file = BASE_DIR / "APP_VERSION.txt"
		if ver_file.exists():
			text = (ver_file.read_text(encoding="utf-8") or "").strip()
			if text:
				return text
	except Exception:
		pass
	return _clean_env_value(os.getenv("APP_VERSION", APP_VERSION)) or APP_VERSION

APP_VERSION = _load_app_version()

# ===================================================
# AI 文案助手配置
# ===================================================
# 支持 OpenAI / DeepSeek 等兼容 OpenAI Chat Completions 的服务
AI_PROVIDER = _clean_env_value(os.getenv("AI_PROVIDER", "openai")) or "openai"  # openai | deepseek | compatible
AI_API_KEY = _clean_env_value(os.getenv("AI_API_KEY", "")) or _clean_env_value(os.getenv("DEEPSEEK_API_KEY", ""))
AI_BASE_URL = _clean_env_value(os.getenv("AI_BASE_URL", ""))  # 例如：https://api.deepseek.com
AI_MODEL = _clean_env_value(os.getenv("AI_MODEL", "gpt-4o-mini")) or "gpt-4o-mini"
AI_VISION_MODEL = _clean_env_value(os.getenv("AI_VISION_MODEL", "")) or ""
if not AI_VISION_MODEL:
	AI_VISION_MODEL = AI_MODEL
AI_SYSTEM_PROMPT = _clean_env_value(os.getenv("AI_SYSTEM_PROMPT", ""))

# 多供应商配置（可选）
AI_DOUBAO_API_KEY = _clean_env_value(os.getenv("AI_DOUBAO_API_KEY", ""))
AI_DOUBAO_BASE_URL = _clean_env_value(os.getenv("AI_DOUBAO_BASE_URL", ""))
AI_QWEN_API_KEY = _clean_env_value(os.getenv("AI_QWEN_API_KEY", ""))
AI_QWEN_BASE_URL = _clean_env_value(os.getenv("AI_QWEN_BASE_URL", ""))
AI_DEEPSEEK_API_KEY = _clean_env_value(os.getenv("AI_DEEPSEEK_API_KEY", ""))
AI_DEEPSEEK_BASE_URL = _clean_env_value(os.getenv("AI_DEEPSEEK_BASE_URL", ""))
AI_DEEPSEEK_MODEL = _clean_env_value(os.getenv("AI_DEEPSEEK_MODEL", ""))

# 任务级选择供应商（可选）
AI_COPYWRITER_PROVIDER = _clean_env_value(os.getenv("AI_COPYWRITER_PROVIDER", ""))
AI_FACTORY_PROVIDER = _clean_env_value(os.getenv("AI_FACTORY_PROVIDER", ""))
AI_TIMELINE_PROVIDER = _clean_env_value(os.getenv("AI_TIMELINE_PROVIDER", ""))
AI_PHOTO_PROVIDER = _clean_env_value(os.getenv("AI_PHOTO_PROVIDER", ""))
AI_VISION_PROVIDER = _clean_env_value(os.getenv("AI_VISION_PROVIDER", ""))

# 任务级覆盖（可选）：用于按功能选择不同模型/服务
AI_COPYWRITER_API_KEY = _clean_env_value(os.getenv("AI_COPYWRITER_API_KEY", ""))
AI_COPYWRITER_BASE_URL = _clean_env_value(os.getenv("AI_COPYWRITER_BASE_URL", ""))
AI_COPYWRITER_MODEL = _clean_env_value(os.getenv("AI_COPYWRITER_MODEL", ""))

AI_FACTORY_API_KEY = _clean_env_value(os.getenv("AI_FACTORY_API_KEY", ""))
AI_FACTORY_BASE_URL = _clean_env_value(os.getenv("AI_FACTORY_BASE_URL", ""))
AI_FACTORY_MODEL = _clean_env_value(os.getenv("AI_FACTORY_MODEL", ""))

AI_TIMELINE_API_KEY = _clean_env_value(os.getenv("AI_TIMELINE_API_KEY", ""))
AI_TIMELINE_BASE_URL = _clean_env_value(os.getenv("AI_TIMELINE_BASE_URL", ""))
AI_TIMELINE_MODEL = _clean_env_value(os.getenv("AI_TIMELINE_MODEL", ""))

AI_PHOTO_API_KEY = _clean_env_value(os.getenv("AI_PHOTO_API_KEY", ""))
AI_PHOTO_BASE_URL = _clean_env_value(os.getenv("AI_PHOTO_BASE_URL", ""))
AI_PHOTO_MODEL = _clean_env_value(os.getenv("AI_PHOTO_MODEL", ""))

AI_VISION_API_KEY = _clean_env_value(os.getenv("AI_VISION_API_KEY", ""))
AI_VISION_BASE_URL = _clean_env_value(os.getenv("AI_VISION_BASE_URL", ""))

# 火山方舟（Ark）可选参数：深度思考模式。
# 注意：仅部分模型支持该字段；且文档说明“默认开启深度思考模式，可手动关闭”。
# 这里保持默认不发送，由用户按需配置：enabled / disabled（以官方文档为准）。
ARK_THINKING_TYPE = _clean_env_value(os.getenv("ARK_THINKING_TYPE", ""))

# 面板级“自定义角色提示词”（用于：各 AI 功能面板的配置按钮）
AI_COPYWRITER_ROLE_PROMPT = _clean_env_value(os.getenv("AI_COPYWRITER_ROLE_PROMPT", ""))
AI_FACTORY_ROLE_PROMPT = _clean_env_value(os.getenv("AI_FACTORY_ROLE_PROMPT", ""))
AI_PHOTO_ROLE_PROMPT = _clean_env_value(os.getenv("AI_PHOTO_ROLE_PROMPT", ""))
AI_VISION_ROLE_PROMPT = _clean_env_value(os.getenv("AI_VISION_ROLE_PROMPT", ""))
AI_PROFIT_ROLE_PROMPT = _clean_env_value(os.getenv("AI_PROFIT_ROLE_PROMPT", ""))

# 生成结果语言
AI_OUTPUT_LANG = _clean_env_value(os.getenv("AI_OUTPUT_LANG", "en")) or "en"



# ===================================================
# TTS 配音配置（AI 二创工厂）
# ===================================================
TTS_PROVIDER = _clean_env_value(os.getenv("TTS_PROVIDER", "edge-tts")) or "edge-tts"  # edge-tts | volcengine
TTS_FALLBACK_PROVIDER = _clean_env_value(os.getenv("TTS_FALLBACK_PROVIDER", ""))
TTS_VOICE = _clean_env_value(os.getenv("TTS_VOICE", "en-US-AvaNeural")) or "en-US-AvaNeural"
TTS_SPEED = _clean_env_value(os.getenv("TTS_SPEED", "1.1")) or "1.1"
TTS_EMOTION_PRESET = _clean_env_value(os.getenv("TTS_EMOTION_PRESET", ""))
TTS_EMOTION_CUSTOM = _clean_env_value(os.getenv("TTS_EMOTION_CUSTOM", ""))
TTS_EMOTION_INTENSITY = _clean_env_value(os.getenv("TTS_EMOTION_INTENSITY", "中")) or "中"
TTS_SCENE_MODE = _clean_env_value(os.getenv("TTS_SCENE_MODE", ""))

# ===================================================
# 云端图转视频（I2V）配置
# ===================================================
VIDEO_CLOUD_ENABLED = _clean_env_value(os.getenv("VIDEO_CLOUD_ENABLED", "false")).lower() == "true"
VIDEO_CLOUD_API_KEY = _clean_env_value(os.getenv("VIDEO_CLOUD_API_KEY", ""))
VIDEO_CLOUD_SUBMIT_URL = _clean_env_value(os.getenv("VIDEO_CLOUD_SUBMIT_URL", ""))
VIDEO_CLOUD_STATUS_URL = _clean_env_value(os.getenv("VIDEO_CLOUD_STATUS_URL", ""))
VIDEO_CLOUD_MODEL = _clean_env_value(os.getenv("VIDEO_CLOUD_MODEL", ""))
VIDEO_CLOUD_QUALITY = _clean_env_value(os.getenv("VIDEO_CLOUD_QUALITY", "low")) or "low"
try:
	VIDEO_CLOUD_TIMEOUT = float(_clean_env_value(os.getenv("VIDEO_CLOUD_TIMEOUT", "120")) or 120.0)
except Exception:
	VIDEO_CLOUD_TIMEOUT = 120.0
try:
	VIDEO_CLOUD_POLL_SEC = float(_clean_env_value(os.getenv("VIDEO_CLOUD_POLL_SEC", "2")) or 2.0)
except Exception:
	VIDEO_CLOUD_POLL_SEC = 2.0

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


def _env_csv(name: str, default: list[str], upper: bool = False, lower: bool = False) -> list[str]:
	"""读取逗号分隔配置并返回列表。

	Args:
		name: 环境变量名
		default: 默认列表
		upper: 是否统一转大写
		lower: 是否统一转小写
	"""
	try:
		text = _clean_env_value(os.getenv(name, ""))
		if not text:
			return default
		items = [x.strip() for x in text.split(",") if x.strip()]
		if upper:
			items = [x.upper() for x in items]
		if lower:
			items = [x.lower() for x in items]
		return items or default
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
# 图转视频（V2.0）默认参数
# ===================================================
PHOTO_VIDEO_FPS = _env_int("PHOTO_VIDEO_FPS", 24)
PHOTO_PREVIEW_VOLUME = _env_int("PHOTO_PREVIEW_VOLUME", 80)
TIKTOK_VIDEO_BITRATE = _clean_env_value(os.getenv("TIKTOK_VIDEO_BITRATE", "3500k")) or "3500k"
TIKTOK_MAXRATE = _clean_env_value(os.getenv("TIKTOK_MAXRATE", "3500k")) or "3500k"
TIKTOK_BUFSIZE = _clean_env_value(os.getenv("TIKTOK_BUFSIZE", "7000k")) or "7000k"
TIKTOK_AUDIO_BITRATE = _clean_env_value(os.getenv("TIKTOK_AUDIO_BITRATE", "128k")) or "128k"

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
IP_CHECK_INTERVAL_SEC = _env_int("IP_CHECK_INTERVAL_SEC", 300)
IP_SCAMALYTICS_MAX_SCORE = _env_int("IP_SCAMALYTICS_MAX_SCORE", 30)
IPINFO_URL = _clean_env_value(os.getenv("IPINFO_URL", "https://ipinfo.io/json")) or "https://ipinfo.io/json"
IPINFO_TOKEN = _clean_env_value(os.getenv("IPINFO_TOKEN", ""))
IPINFO_ALLOWED_TYPES = _clean_env_value(os.getenv("IPINFO_ALLOWED_TYPES", "ISP,Residential"))
IPINFO_BLOCKED_TYPES = _clean_env_value(os.getenv("IPINFO_BLOCKED_TYPES", "Hosting,Business"))


# 需标记为风险的 ISP/机房关键词（用于诊断中心提醒）
DANGEROUS_ISP_KEYWORDS = _env_csv(
	"DANGEROUS_ISP_KEYWORDS",
	["Google", "Amazon", "Microsoft", "Datacenter", "Cloud"],
)

# 允许的国家/地区代码（TikTok Shop 运营环境约束，默认仅 US）
SAFE_COUNTRY_CODES = _env_csv("SAFE_COUNTRY_CODES", ["US"], upper=True)

# 当检测到高风险 IP 时，是否强制禁用左侧导航（默认 false，推荐保留为 false）
IP_BLOCK_NAV_ON_RISK = os.getenv("IP_BLOCK_NAV_ON_RISK", "false").lower() == "true"

# API 重试配置
API_RETRY_COUNT = 3
API_RETRY_DELAY = 2  # 秒；内部使用指数退避

# ===================================================
# V2.2 智能内容工厂配置
# ===================================================
PERSONA_LIBRARY = {
	"bestie": "The Bestie (闺蜜)：OMG 你必须看这个...",
	"skeptic": "The Skeptic (怀疑论者)：我以为是智商税，结果...",
	"expert": "The Expert (专家)：商家不想让你知道的 3 个秘密...",
}
HEARTBEAT_SPEED_MIN = _env_float("HEARTBEAT_SPEED_MIN", 0.9)
HEARTBEAT_SPEED_MAX = _env_float("HEARTBEAT_SPEED_MAX", 1.1)
HEARTBEAT_PERIOD_SEC = _env_float("HEARTBEAT_PERIOD_SEC", 4.0)
CYBORG_INTRO_SEC = _env_float("CYBORG_INTRO_SEC", 2.0)
CYBORG_OUTRO_SEC = _env_float("CYBORG_OUTRO_SEC", 2.0)

# ===================================================
# 评论监控配置
# ===================================================
COMMENT_WATCH_KEYWORDS = _clean_env_value(os.getenv("COMMENT_WATCH_KEYWORDS", "want,need"))
COMMENT_BLOCKLIST = _clean_env_value(os.getenv("COMMENT_BLOCKLIST", "fake,scam"))
COMMENT_DM_ENABLED = (os.getenv("COMMENT_DM_ENABLED", "true").lower() == "true")
COMMENT_DM_TEMPLATE = _clean_env_value(os.getenv("COMMENT_DM_TEMPLATE", "Thanks! I sent you the link in DM."))

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
	global AI_VISION_MODEL, AI_VISION_API_KEY, AI_VISION_BASE_URL
	global AI_COPYWRITER_API_KEY, AI_COPYWRITER_BASE_URL, AI_COPYWRITER_MODEL
	global AI_FACTORY_API_KEY, AI_FACTORY_BASE_URL, AI_FACTORY_MODEL
	global AI_TIMELINE_API_KEY, AI_TIMELINE_BASE_URL, AI_TIMELINE_MODEL
	global AI_PHOTO_API_KEY, AI_PHOTO_BASE_URL, AI_PHOTO_MODEL
	global AI_DOUBAO_API_KEY, AI_DOUBAO_BASE_URL
	global AI_QWEN_API_KEY, AI_QWEN_BASE_URL
	global AI_DEEPSEEK_API_KEY, AI_DEEPSEEK_BASE_URL, AI_DEEPSEEK_MODEL
	global AI_COPYWRITER_PROVIDER, AI_FACTORY_PROVIDER, AI_TIMELINE_PROVIDER, AI_PHOTO_PROVIDER, AI_VISION_PROVIDER
	global AI_SYSTEM_PROMPT, AI_COPYWRITER_ROLE_PROMPT, AI_FACTORY_ROLE_PROMPT
	global AI_PHOTO_ROLE_PROMPT, AI_VISION_ROLE_PROMPT, AI_PROFIT_ROLE_PROMPT
	global AI_OUTPUT_LANG
	global ARK_THINKING_TYPE
	global TTS_PROVIDER, TTS_FALLBACK_PROVIDER, TTS_VOICE, TTS_SPEED
	global TTS_EMOTION_PRESET, TTS_EMOTION_CUSTOM, TTS_EMOTION_INTENSITY, TTS_SCENE_MODE
	global VIDEO_CLOUD_ENABLED, VIDEO_CLOUD_API_KEY, VIDEO_CLOUD_SUBMIT_URL, VIDEO_CLOUD_STATUS_URL, VIDEO_CLOUD_MODEL
	global VIDEO_CLOUD_QUALITY, VIDEO_CLOUD_TIMEOUT, VIDEO_CLOUD_POLL_SEC
	global VOLC_TTS_ENDPOINT, VOLC_TTS_APPID, VOLC_TTS_ACCESS_TOKEN, VOLC_TTS_SECRET_KEY, VOLC_TTS_TOKEN, VOLC_TTS_CLUSTER, VOLC_TTS_VOICE_TYPE, VOLC_TTS_ENCODING
	global IP_CHECK_ENABLED, IP_API_URL, IP_API_TIMEOUT
	global IP_CHECK_INTERVAL_SEC, IP_SCAMALYTICS_MAX_SCORE
	global IPINFO_URL, IPINFO_TOKEN, IPINFO_ALLOWED_TYPES, IPINFO_BLOCKED_TYPES
	global DANGEROUS_ISP_KEYWORDS, SAFE_COUNTRY_CODES
	global DOWNLOAD_DIR
	global LOG_LEVEL, THEME_MODE
	global VIDEO_DEEP_REMIX_ENABLED, VIDEO_REMIX_MICRO_ZOOM, VIDEO_REMIX_ADD_NOISE, VIDEO_REMIX_STRIP_METADATA
	global PHOTO_VIDEO_FPS, PHOTO_PREVIEW_VOLUME
	global TIKTOK_VIDEO_BITRATE, TIKTOK_MAXRATE, TIKTOK_BUFSIZE, TIKTOK_AUDIO_BITRATE
	global GROWTH_RATE_THRESHOLD, MAX_REVIEWS, PRICE_MIN, PRICE_MAX
	global SUBTITLE_BURN_ENABLED, SUBTITLE_FONT_NAME
	global SUBTITLE_FONT_AUTO, SUBTITLE_FONT_SIZE
	global SUBTITLE_FONT_SIZE_RATIO, SUBTITLE_FONT_SIZE_MIN, SUBTITLE_FONT_SIZE_MAX
	global SUBTITLE_OUTLINE_AUTO, SUBTITLE_OUTLINE
	global SUBTITLE_OUTLINE_MIN, SUBTITLE_OUTLINE_MAX
	global SUBTITLE_SHADOW, SUBTITLE_MARGIN_V_RATIO, SUBTITLE_MARGIN_V_MIN, SUBTITLE_MARGIN_LR
	global PERSONA_LIBRARY, HEARTBEAT_SPEED_MIN, HEARTBEAT_SPEED_MAX, HEARTBEAT_PERIOD_SEC
	global CYBORG_INTRO_SEC, CYBORG_OUTRO_SEC
	global COMMENT_WATCH_KEYWORDS, COMMENT_BLOCKLIST
	global COMMENT_DM_ENABLED, COMMENT_DM_TEMPLATE
	global UPDATE_PROVIDER, UPDATE_CHECK_URL

	ECHOTIK_API_KEY = _clean_env_value(os.getenv("ECHOTIK_API_KEY", ""))
	ECHOTIK_API_SECRET = _clean_env_value(os.getenv("ECHOTIK_API_SECRET", ""))
	RAPIDAPI_KEY = _clean_env_value(os.getenv("RAPIDAPI_KEY", ""))
	RAPIDAPI_HOST = _clean_env_value(os.getenv("RAPIDAPI_HOST", ""))

	AI_PROVIDER = _clean_env_value(os.getenv("AI_PROVIDER", "openai")) or "openai"
	AI_API_KEY = _clean_env_value(os.getenv("AI_API_KEY", "")) or _clean_env_value(os.getenv("DEEPSEEK_API_KEY", ""))
	AI_BASE_URL = _clean_env_value(os.getenv("AI_BASE_URL", ""))
	AI_MODEL = _clean_env_value(os.getenv("AI_MODEL", "gpt-4o-mini")) or "gpt-4o-mini"
	AI_VISION_MODEL = _clean_env_value(os.getenv("AI_VISION_MODEL", "")) or ""
	if not AI_VISION_MODEL:
		AI_VISION_MODEL = AI_MODEL
	AI_SYSTEM_PROMPT = _clean_env_value(os.getenv("AI_SYSTEM_PROMPT", ""))

	AI_DOUBAO_API_KEY = _clean_env_value(os.getenv("AI_DOUBAO_API_KEY", ""))
	AI_DOUBAO_BASE_URL = _clean_env_value(os.getenv("AI_DOUBAO_BASE_URL", ""))
	AI_QWEN_API_KEY = _clean_env_value(os.getenv("AI_QWEN_API_KEY", ""))
	AI_QWEN_BASE_URL = _clean_env_value(os.getenv("AI_QWEN_BASE_URL", ""))
	AI_DEEPSEEK_API_KEY = _clean_env_value(os.getenv("AI_DEEPSEEK_API_KEY", ""))
	AI_DEEPSEEK_BASE_URL = _clean_env_value(os.getenv("AI_DEEPSEEK_BASE_URL", ""))
	AI_DEEPSEEK_MODEL = _clean_env_value(os.getenv("AI_DEEPSEEK_MODEL", ""))

	AI_COPYWRITER_PROVIDER = _clean_env_value(os.getenv("AI_COPYWRITER_PROVIDER", ""))
	AI_FACTORY_PROVIDER = _clean_env_value(os.getenv("AI_FACTORY_PROVIDER", ""))
	AI_TIMELINE_PROVIDER = _clean_env_value(os.getenv("AI_TIMELINE_PROVIDER", ""))
	AI_PHOTO_PROVIDER = _clean_env_value(os.getenv("AI_PHOTO_PROVIDER", ""))
	AI_VISION_PROVIDER = _clean_env_value(os.getenv("AI_VISION_PROVIDER", ""))
	AI_COPYWRITER_API_KEY = _clean_env_value(os.getenv("AI_COPYWRITER_API_KEY", ""))
	AI_COPYWRITER_BASE_URL = _clean_env_value(os.getenv("AI_COPYWRITER_BASE_URL", ""))
	AI_COPYWRITER_MODEL = _clean_env_value(os.getenv("AI_COPYWRITER_MODEL", ""))
	AI_FACTORY_API_KEY = _clean_env_value(os.getenv("AI_FACTORY_API_KEY", ""))
	AI_FACTORY_BASE_URL = _clean_env_value(os.getenv("AI_FACTORY_BASE_URL", ""))
	AI_FACTORY_MODEL = _clean_env_value(os.getenv("AI_FACTORY_MODEL", ""))
	AI_TIMELINE_API_KEY = _clean_env_value(os.getenv("AI_TIMELINE_API_KEY", ""))
	AI_TIMELINE_BASE_URL = _clean_env_value(os.getenv("AI_TIMELINE_BASE_URL", ""))
	AI_TIMELINE_MODEL = _clean_env_value(os.getenv("AI_TIMELINE_MODEL", ""))
	AI_PHOTO_API_KEY = _clean_env_value(os.getenv("AI_PHOTO_API_KEY", ""))
	AI_PHOTO_BASE_URL = _clean_env_value(os.getenv("AI_PHOTO_BASE_URL", ""))
	AI_PHOTO_MODEL = _clean_env_value(os.getenv("AI_PHOTO_MODEL", ""))
	AI_VISION_API_KEY = _clean_env_value(os.getenv("AI_VISION_API_KEY", ""))
	AI_VISION_BASE_URL = _clean_env_value(os.getenv("AI_VISION_BASE_URL", ""))
	AI_OUTPUT_LANG = _clean_env_value(os.getenv("AI_OUTPUT_LANG", "en")) or "en"
	ARK_THINKING_TYPE = _clean_env_value(os.getenv("ARK_THINKING_TYPE", ""))
	AI_COPYWRITER_ROLE_PROMPT = _clean_env_value(os.getenv("AI_COPYWRITER_ROLE_PROMPT", ""))
	AI_FACTORY_ROLE_PROMPT = _clean_env_value(os.getenv("AI_FACTORY_ROLE_PROMPT", ""))
	AI_PHOTO_ROLE_PROMPT = _clean_env_value(os.getenv("AI_PHOTO_ROLE_PROMPT", ""))
	AI_VISION_ROLE_PROMPT = _clean_env_value(os.getenv("AI_VISION_ROLE_PROMPT", ""))
	AI_PROFIT_ROLE_PROMPT = _clean_env_value(os.getenv("AI_PROFIT_ROLE_PROMPT", ""))

	TTS_PROVIDER = _clean_env_value(os.getenv("TTS_PROVIDER", "edge-tts")) or "edge-tts"
	TTS_FALLBACK_PROVIDER = _clean_env_value(os.getenv("TTS_FALLBACK_PROVIDER", ""))
	TTS_VOICE = _clean_env_value(os.getenv("TTS_VOICE", "en-US-AvaNeural")) or "en-US-AvaNeural"
	TTS_SPEED = _clean_env_value(os.getenv("TTS_SPEED", "1.1")) or "1.1"
	TTS_EMOTION_PRESET = _clean_env_value(os.getenv("TTS_EMOTION_PRESET", ""))
	TTS_EMOTION_CUSTOM = _clean_env_value(os.getenv("TTS_EMOTION_CUSTOM", ""))
	TTS_EMOTION_INTENSITY = _clean_env_value(os.getenv("TTS_EMOTION_INTENSITY", "中")) or "中"
	TTS_SCENE_MODE = _clean_env_value(os.getenv("TTS_SCENE_MODE", ""))

	VIDEO_CLOUD_ENABLED = _clean_env_value(os.getenv("VIDEO_CLOUD_ENABLED", "false")).lower() == "true"
	VIDEO_CLOUD_API_KEY = _clean_env_value(os.getenv("VIDEO_CLOUD_API_KEY", ""))
	VIDEO_CLOUD_SUBMIT_URL = _clean_env_value(os.getenv("VIDEO_CLOUD_SUBMIT_URL", ""))
	VIDEO_CLOUD_STATUS_URL = _clean_env_value(os.getenv("VIDEO_CLOUD_STATUS_URL", ""))
	VIDEO_CLOUD_MODEL = _clean_env_value(os.getenv("VIDEO_CLOUD_MODEL", ""))
	VIDEO_CLOUD_QUALITY = _clean_env_value(os.getenv("VIDEO_CLOUD_QUALITY", "low")) or "low"
	VIDEO_CLOUD_TIMEOUT = _env_float("VIDEO_CLOUD_TIMEOUT", 120.0)
	VIDEO_CLOUD_POLL_SEC = _env_float("VIDEO_CLOUD_POLL_SEC", 2.0)

	VOLC_TTS_ENDPOINT = _clean_env_value(os.getenv("VOLC_TTS_ENDPOINT", "https://openspeech.bytedance.com/api/v1/tts"))
	VOLC_TTS_APPID = _clean_env_value(os.getenv("VOLC_TTS_APPID", ""))
	VOLC_TTS_ACCESS_TOKEN = _clean_env_value(os.getenv("VOLC_TTS_ACCESS_TOKEN", "")) or _clean_env_value(os.getenv("VOLC_TTS_TOKEN", ""))
	VOLC_TTS_SECRET_KEY = _clean_env_value(os.getenv("VOLC_TTS_SECRET_KEY", ""))
	VOLC_TTS_TOKEN = _clean_env_value(os.getenv("VOLC_TTS_TOKEN", ""))
	VOLC_TTS_CLUSTER = _clean_env_value(os.getenv("VOLC_TTS_CLUSTER", "volcano_tts")) or "volcano_tts"
	VOLC_TTS_VOICE_TYPE = _clean_env_value(os.getenv("VOLC_TTS_VOICE_TYPE", ""))
	VOLC_TTS_ENCODING = _clean_env_value(os.getenv("VOLC_TTS_ENCODING", "mp3")) or "mp3"

	LOG_LEVEL = (_clean_env_value(os.getenv("LOG_LEVEL", "INFO")) or "INFO").upper()
	THEME_MODE = _clean_env_value(os.getenv("THEME_MODE", "light")) or "light"

	IP_CHECK_ENABLED = (os.getenv("IP_CHECK_ENABLED", "true").lower() == "true")
	IP_API_URL = _clean_env_value(os.getenv("IP_API_URL", "http://ip-api.com/json")) or "http://ip-api.com/json"
	IP_API_TIMEOUT = _env_int("IP_API_TIMEOUT", 5)
	IP_CHECK_INTERVAL_SEC = _env_int("IP_CHECK_INTERVAL_SEC", 300)
	IP_SCAMALYTICS_MAX_SCORE = _env_int("IP_SCAMALYTICS_MAX_SCORE", 30)
	IPINFO_URL = _clean_env_value(os.getenv("IPINFO_URL", "https://ipinfo.io/json")) or "https://ipinfo.io/json"
	IPINFO_TOKEN = _clean_env_value(os.getenv("IPINFO_TOKEN", ""))
	IPINFO_ALLOWED_TYPES = _clean_env_value(os.getenv("IPINFO_ALLOWED_TYPES", "ISP,Residential"))
	IPINFO_BLOCKED_TYPES = _clean_env_value(os.getenv("IPINFO_BLOCKED_TYPES", "Hosting,Business"))
	DANGEROUS_ISP_KEYWORDS = _env_csv(
		"DANGEROUS_ISP_KEYWORDS",
		["Google", "Amazon", "Microsoft", "Datacenter", "Cloud"],
	)
	SAFE_COUNTRY_CODES = _env_csv("SAFE_COUNTRY_CODES", ["US"], upper=True)

	download_dir_text = _clean_env_value(os.getenv("DOWNLOAD_DIR"))
	# 默认下载目录：素材库下 Downloads（更贴合“素材统一归档”工作流）
	DOWNLOAD_DIR = Path(download_dir_text) if download_dir_text else (ASSET_LIBRARY_DIR / "Downloads")
	DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

	VIDEO_DEEP_REMIX_ENABLED = os.getenv("VIDEO_DEEP_REMIX_ENABLED", "0") == "1"
	VIDEO_REMIX_MICRO_ZOOM = os.getenv("VIDEO_REMIX_MICRO_ZOOM", "1") == "1"
	VIDEO_REMIX_ADD_NOISE = os.getenv("VIDEO_REMIX_ADD_NOISE", "0") == "1"
	VIDEO_REMIX_STRIP_METADATA = os.getenv("VIDEO_REMIX_STRIP_METADATA", "1") == "1"

	PHOTO_VIDEO_FPS = _env_int("PHOTO_VIDEO_FPS", 24)
	PHOTO_PREVIEW_VOLUME = _env_int("PHOTO_PREVIEW_VOLUME", 80)
	TIKTOK_VIDEO_BITRATE = _clean_env_value(os.getenv("TIKTOK_VIDEO_BITRATE", "3500k")) or "3500k"
	TIKTOK_MAXRATE = _clean_env_value(os.getenv("TIKTOK_MAXRATE", "3500k")) or "3500k"
	TIKTOK_BUFSIZE = _clean_env_value(os.getenv("TIKTOK_BUFSIZE", "7000k")) or "7000k"
	TIKTOK_AUDIO_BITRATE = _clean_env_value(os.getenv("TIKTOK_AUDIO_BITRATE", "128k")) or "128k"

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

	PERSONA_LIBRARY = {
		"bestie": "The Bestie (闺蜜)：OMG 你必须看这个...",
		"skeptic": "The Skeptic (怀疑论者)：我以为是智商税，结果...",
		"expert": "The Expert (专家)：商家不想让你知道的 3 个秘密...",
	}
	HEARTBEAT_SPEED_MIN = _env_float("HEARTBEAT_SPEED_MIN", 0.9)
	HEARTBEAT_SPEED_MAX = _env_float("HEARTBEAT_SPEED_MAX", 1.1)
	HEARTBEAT_PERIOD_SEC = _env_float("HEARTBEAT_PERIOD_SEC", 4.0)
	CYBORG_INTRO_SEC = _env_float("CYBORG_INTRO_SEC", 2.0)
	CYBORG_OUTRO_SEC = _env_float("CYBORG_OUTRO_SEC", 2.0)
	COMMENT_WATCH_KEYWORDS = _clean_env_value(os.getenv("COMMENT_WATCH_KEYWORDS", "want,need"))
	COMMENT_BLOCKLIST = _clean_env_value(os.getenv("COMMENT_BLOCKLIST", "fake,scam"))
	COMMENT_DM_ENABLED = (os.getenv("COMMENT_DM_ENABLED", "true").lower() == "true")
	COMMENT_DM_TEMPLATE = _clean_env_value(os.getenv("COMMENT_DM_TEMPLATE", "Thanks! I sent you the link in DM."))

	UPDATE_PROVIDER = _clean_env_value(os.getenv("UPDATE_PROVIDER", "github")) or "github"
	UPDATE_CHECK_URL = _clean_env_value(os.getenv("UPDATE_CHECK_URL", "https://api.github.com/repos/SHCSCA/TK-OPS-ASSISTANT/releases/latest"))


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
		"THEME_MODE": "light",
		"LOG_LEVEL": "INFO",
		"UPDATE_PROVIDER": "github",
		"UPDATE_CHECK_URL": "https://api.github.com/repos/SHCSCA/TK-OPS-ASSISTANT/releases/latest",
		"RAPIDAPI_KEY": "",
		"RAPIDAPI_HOST": "",
		"AI_PROVIDER": "openai",
		"AI_BASE_URL": "",
		"AI_API_KEY": "",
		"AI_MODEL": "gpt-4o-mini",
		"AI_VISION_MODEL": "",
		"AI_VISION_API_KEY": "",
		"AI_VISION_BASE_URL": "",
		"AI_DOUBAO_API_KEY": "",
		"AI_DOUBAO_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
		"AI_QWEN_API_KEY": "",
		"AI_QWEN_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
		"AI_DEEPSEEK_API_KEY": "",
		"AI_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
		"AI_DEEPSEEK_MODEL": "deepseek-chat",
		"AI_COPYWRITER_PROVIDER": "",
		"AI_FACTORY_PROVIDER": "",
		"AI_TIMELINE_PROVIDER": "",
		"AI_PHOTO_PROVIDER": "",
		"AI_VISION_PROVIDER": "",
		"AI_SYSTEM_PROMPT": "",
		"ARK_THINKING_TYPE": "",
		"AI_COPYWRITER_API_KEY": "",
		"AI_COPYWRITER_BASE_URL": "",
		"AI_COPYWRITER_MODEL": "",
		"AI_FACTORY_API_KEY": "",
		"AI_FACTORY_BASE_URL": "",
		"AI_FACTORY_MODEL": "",
		"AI_TIMELINE_API_KEY": "",
		"AI_TIMELINE_BASE_URL": "",
		"AI_TIMELINE_MODEL": "",
		"AI_PHOTO_API_KEY": "",
		"AI_PHOTO_BASE_URL": "",
		"AI_PHOTO_MODEL": "",
		"AI_COPYWRITER_ROLE_PROMPT": "",
		"AI_FACTORY_ROLE_PROMPT": "",
		"AI_PHOTO_ROLE_PROMPT": "",
		"AI_VISION_ROLE_PROMPT": "",
		"AI_PROFIT_ROLE_PROMPT": "",
		"AI_OUTPUT_LANG": "en",
		"TTS_PROVIDER": "edge-tts",
		"TTS_FALLBACK_PROVIDER": "",
		"TTS_VOICE": "en-US-AvaNeural",
		"TTS_SPEED": "1.1",
		"TTS_EMOTION_PRESET": "",
		"TTS_EMOTION_CUSTOM": "",
		"TTS_EMOTION_INTENSITY": "中",
		"TTS_SCENE_MODE": "",
		"VIDEO_CLOUD_ENABLED": "false",
		"VIDEO_CLOUD_API_KEY": "",
		"VIDEO_CLOUD_SUBMIT_URL": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
		"VIDEO_CLOUD_STATUS_URL": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}",
		"VIDEO_CLOUD_MODEL": "",
		"VIDEO_CLOUD_QUALITY": "low",
		"VIDEO_CLOUD_TIMEOUT": "120",
		"VIDEO_CLOUD_POLL_SEC": "2",
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
		"IP_API_URL": "http://ip-api.com/json",
		"IP_API_TIMEOUT": "5",
		"IP_CHECK_INTERVAL_SEC": "300",
		"IP_SCAMALYTICS_MAX_SCORE": "30",
		"IPINFO_URL": "https://ipinfo.io/json",
		"IPINFO_TOKEN": "",
		"IPINFO_ALLOWED_TYPES": "ISP,Residential",
		"IPINFO_BLOCKED_TYPES": "Hosting,Business",
		"DANGEROUS_ISP_KEYWORDS": "Google,Amazon,Microsoft,Datacenter,Cloud",
		"SAFE_COUNTRY_CODES": "US",
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
		# 图转视频（V2.0）
		"PHOTO_VIDEO_FPS": "24",
		"PHOTO_PREVIEW_VOLUME": "80",
		"TIKTOK_VIDEO_BITRATE": "3500k",
		"TIKTOK_MAXRATE": "3500k",
		"TIKTOK_BUFSIZE": "7000k",
		"TIKTOK_AUDIO_BITRATE": "128k",
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
		# V2.2: 人设/情绪曲线/评论监控
		"HEARTBEAT_SPEED_MIN": "0.9",
		"HEARTBEAT_SPEED_MAX": "1.1",
		"HEARTBEAT_PERIOD_SEC": "4.0",
		"CYBORG_INTRO_SEC": "2.0",
		"CYBORG_OUTRO_SEC": "2.0",
		"COMMENT_WATCH_KEYWORDS": "want,need",
		"COMMENT_BLOCKLIST": "fake,scam",
		"COMMENT_DM_ENABLED": "true",
		"COMMENT_DM_TEMPLATE": "Thanks! I sent you the link in DM.",
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
