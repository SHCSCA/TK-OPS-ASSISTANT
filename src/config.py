# config.py - Refactored with Pydantic
"""
TikTok 蓝海运营助手 - 全局配置 (New Pydantic-based System)
此文件使用 Pydantic 重构配置系统，实现强类型验证、默认值管理和自动加载。
"""
import os
import sys
from pathlib import Path
from typing import Literal, Optional, List, Dict, Any
from pydantic import Field, SecretStr, HttpUrl, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing_extensions import Annotated

# --- Validators ---
def parse_csv_list(v: Any) ->List[str]:
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return v

# ===================================================
# 核心路径解析逻辑 (保持原逻辑不变)
# ===================================================
def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))

IS_FROZEN = _is_frozen()

if IS_FROZEN:
    # 冻结态：代码目录在 exe 附近
    BASE_DIR = Path(sys.executable).resolve().parent
    try:
        # 写入测试确定是否可写（Portable Mode 判定）
        test_write_path = BASE_DIR / ".perm_check"
        test_write_path.write_text("ok", encoding="utf-8")
        test_write_path.unlink() 
        DATA_DIR = BASE_DIR / "tk_data" # 优先使用便携目录
        try:
             DATA_DIR.mkdir(exist_ok=True)
        except Exception:
             DATA_DIR = BASE_DIR
    except Exception:
        # 无权限回退到 AppData
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
             DATA_DIR = Path(local_appdata) / "TK-Ops-Pro"
        else:
             DATA_DIR = Path.home() / ".tk-ops-pro"
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
else:
    # 源码模式
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR

# ===================================================
# 辅助函数：版本加载
# ===================================================
def _load_app_version() -> str:
    """优先读取本地版本文件，用于更新后动态版本显示"""
    try:
        ver_file = BASE_DIR / "APP_VERSION.txt"
        if ver_file.exists():
            text = ver_file.read_text(encoding="utf-8").strip()
            if text:
                return text
    except Exception:
        pass
    return "0.0.0" # 在 Pydantic 模型中设置默认值

# ===================================================
# 配置模型定义
# ===================================================
class AppSettings(BaseSettings):
    """
    应用程序全局配置模型
    所有字段都有类型验证，并自动从环境变量或 .env 文件加载。
    """
    
    # --- 基础元信息 ---
    APP_VERSION: str = Field(default_factory=_load_app_version, description="应用版本号")
    THEME_MODE: Literal["dark", "light"] = Field("light", description="主题模式 (dark/light)")
    WINDOW_WIDTH: int = Field(1280, description="窗口默认宽度")
    WINDOW_HEIGHT: int = Field(800, description="窗口默认高度")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", description="日志等级")
    SENTRY_DSN: Optional[str] = Field("", description="Sentry 错误监控 DSN (空字符串禁用)")
    
    # --- 日志格式 (兼容 logger.py) ---
    LOG_FORMAT: str = Field(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", 
        description="日志格式"
    )
    LOG_DATETIME_FORMAT: str = Field(
        "%Y-%m-%d %H:%M:%S", 
        description="日志时间格式"
    )

    # --- 目录路径 (类型自动转 Path) ---
    BASE_DIR: Path = Field(default=BASE_DIR, description="程序根目录")
    DATA_DIR: Path = Field(default=DATA_DIR, description="数据存储目录")
    
    # 注意：Path 类型字段如果不给默认值，Pydantic 会尝试从环境变量读取字符串并转换
    # 下面这些目录在 model_post_init 中会进一步处理默认值逻辑
    OUTPUT_DIR: Optional[Path] = Field(None, description="结果输出目录")
    LOG_DIR: Optional[Path] = Field(None, description="日志目录")
    ASSET_LIBRARY_DIR: Optional[Path] = Field(None, description="素材库根目录")
    DOWNLOAD_DIR: Optional[Path] = Field(None, description="素材下载目录")
    PROCESSED_VIDEOS_DIR: Optional[Path] = Field(None, description="处理后视频存放目录")

    # --- 蓝海选品 (EchoTik) ---
    ECHOTIK_API_KEY: str = Field("", description="EchoTik 用户名/Key")
    ECHOTIK_API_SECRET: SecretStr = Field("", description="EchoTik 密码/Secret")
    SHOW_ECHOTIK_SETTINGS: bool = Field(False, description="是否显示 API Key 设置")
    
    # --- 选品阈值 ---
    GROWTH_RATE_THRESHOLD: int = Field(500, description="7日销量增长率阈值")
    MAX_REVIEWS: int = Field(50, description="最大评论数过滤")
    PRICE_MIN: float = Field(20.0, description="最低价格 (USD)")
    PRICE_MAX: float = Field(80.0, description="最高价格 (USD)")

    # --- AI 服务配置 (兼容 OpenAI) ---
    AI_PROVIDER: str = Field("openai", description="AI 服务商 (openai/deepseek/compatible)")
    AI_BASE_URL: str = Field("", description="AI API 基础地址")
    AI_API_KEY: SecretStr = Field("", description="AI API Key")
    AI_MODEL: str = Field("gpt-4o-mini", description="默认 AI 模型")
    AI_VISION_MODEL: str = Field("", description="视觉模型 (留空同 AI_MODEL)")
    AI_SYSTEM_PROMPT: str = Field("", description="全局系统提示词")
    ARK_THINKING_TYPE: str = Field("", description="火山深度思考开关 (enabled/disabled)")
    AI_OUTPUT_LANG: str = Field("en", description="AI 输出语言")

    # --- AI Token 计费 ---
    AI_TOKEN_PRICE_PER_1K_PROMPT: float = Field(0.0, description="Prompt 价格/1k token")
    AI_TOKEN_PRICE_PER_1K_COMPLETION: float = Field(0.0, description="Completion 价格/1k token")
    AI_TOKEN_CURRENCY: str = Field("USD", description="计费币种")

    # --- 独立 AI 通道配置 (可选) ---
    AI_COPYWRITER_PROVIDER: str = Field("", description="文案助手专用 Provider")
    AI_FACTORY_PROVIDER: str = Field("", description="二创工厂专用 Provider")
    AI_TIMELINE_PROVIDER: str = Field("", description="时间轴专用 Provider")
    AI_PHOTO_PROVIDER: str = Field("", description="图转视频专用 Provider")
    AI_VISION_PROVIDER: str = Field("", description="视觉识别专用 Provider")
    
    # --- Prompt 角色配置 ---
    AI_COPYWRITER_ROLE_PROMPT: str = Field("", description="文案助手角色提示词")
    AI_FACTORY_ROLE_PROMPT: str = Field("", description="二创工厂角色提示词")
    AI_PHOTO_ROLE_PROMPT: str = Field("", description="图生视频角色提示词")
    AI_VISION_ROLE_PROMPT: str = Field("", description="视觉识别角色提示词")
    AI_PROFIT_ROLE_PROMPT: str = Field("", description="利润核算角色提示词")

    # --- TTS 语音合成 ---
    TTS_PROVIDER: Literal["edge-tts", "volcengine"] = Field("edge-tts", description="TTS 服务商")
    TTS_VOICE: str = Field("en-US-AvaNeural", description="TTS 发音人")
    TTS_SPEED: str = Field("1.1", description="语速 (字符串形式，如 +10%)")
    TTS_FALLBACK_PROVIDER: str = Field("", description="备用 TTS 服务商")
    
    # 火山 TTS 配置
    VOLC_TTS_ENDPOINT: str = Field("https://openspeech.bytedance.com/api/v1/tts", description="火山 TTS 接口")
    VOLC_TTS_APPID: str = Field("", description="火山 TTS AppID")
    VOLC_TTS_ACCESS_TOKEN: SecretStr = Field("", description="火山 TTS Access Token")
    VOLC_TTS_CLUSTER: str = Field("volcano_tts", description="火山 TTS 业务集群")
    VOLC_TTS_VOICE_TYPE: str = Field("", description="火山 TTS 音色 ID")
    VOLC_TTS_ENCODING: str = Field("mp3", description="火山 TTS 编码格式")

    # --- 视频处理参数 ---
    VIDEO_DEEP_REMIX_ENABLED: bool = Field(False, description="启用深度去重")
    VIDEO_REMIX_MICRO_ZOOM: bool = Field(True, description="启用微缩放混淆")
    VIDEO_REMIX_ADD_NOISE: bool = Field(False, description="启用噪点添加")
    VIDEO_REMIX_STRIP_METADATA: bool = Field(True, description="启用去除元数据")
    
    # 视频参数详情
    PHOTO_VIDEO_FPS: int = Field(24, description="图片转视频帧率")
    TIKTOK_VIDEO_BITRATE: str = Field("3500k", description="视频码率")
    TIKTOK_AUDIO_BITRATE: str = Field("128k", description="音频码率")

    # --- 字幕设置 ---
    SUBTITLE_BURN_ENABLED: bool = Field(True, description="是否烧录字幕")
    SUBTITLE_FONT_NAME: str = Field("Microsoft YaHei UI", description="字幕字体")
    SUBTITLE_FONT_SIZE: int = Field(56, description="字幕字号 (px)")
    SUBTITLE_FONT_AUTO: bool = Field(True, description="自动字号")
    SUBTITLE_OUTLINE: int = Field(4, description="描边宽度 (px)")
    SUBTITLE_OUTLINE_AUTO: bool = Field(True, description="自动描边")

    # --- IP 环境检测 ---
    IP_CHECK_ENABLED: bool = Field(True, description="启用 IP 环境检测")
    IP_API_URL: str = Field("http://ip-api.com/json", description="IP 检测 API")
    IP_CHECK_INTERVAL_SEC: int = Field(300, description="IP 检测间隔 (秒)")
    
    # 复杂类型解析在 pydantic-settings 中往往比较棘手，改回最稳妥的 str并在 post_init 处理
    # 避免反复在不同环境上的解析 bug
    SAFE_COUNTRY_CODES: str = Field("US", description="安全国家代码列表 (逗号分隔)")
    DANGEROUS_ISP_KEYWORDS: str = Field(
        "Google,Amazon,Microsoft,Datacenter,Cloud", 
        description="危险 ISP 关键词列表"
    )
    
    # 实际使用的是解析后的列表，这里作为 Property 或者是 cached_property 提供
    # 但为了兼容旧代码直接访问 config.SAFE_COUNTRY_CODES 得到 list，我们需要在 _export_to_module 中做转换

    # --- 自动更新 ---
    UPDATE_PROVIDER: str = Field("github", description="更新源 (github/gitee)")
    UPDATE_CHECK_URL: str = Field(
        "https://api.github.com/repos/SHCSCA/TK-OPS-ASSISTANT/releases/latest",
        description="更新检查地址"
    )

    # --- 局域网服务 ---
    LAN_ENABLED: bool = Field(False, description="启用局域网传输服务")
    LAN_PORT: int = Field(8000, description="局域网端口")

    # --- Pydantic 配置: 允许从 .env 读取，忽略多余字段 ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        # 允许逗号分隔列表自动解析
        env_parse_enums=True
    )

    def model_post_init(self, __context):
        """后处理：初始化默认路径"""
        # 1. 初始化各类目录（如果环境变量未设置）
        if not self.OUTPUT_DIR:
            self.OUTPUT_DIR = self.DATA_DIR / "Output"
        if not self.LOG_DIR:
            self.LOG_DIR = self.DATA_DIR / "Logs"
        if not self.ASSET_LIBRARY_DIR:
            self.ASSET_LIBRARY_DIR = self.DATA_DIR / "AssetLibrary"
        if not self.PROCESSED_VIDEOS_DIR:
            self.PROCESSED_VIDEOS_DIR = self.OUTPUT_DIR / "Processed_Videos"
        if not self.DOWNLOAD_DIR:
            self.DOWNLOAD_DIR = self.ASSET_LIBRARY_DIR / "Downloads"
        
        # 2. 确保必要的目录存在
        for path in [self.OUTPUT_DIR, self.LOG_DIR, self.ASSET_LIBRARY_DIR, self.DOWNLOAD_DIR, self.PROCESSED_VIDEOS_DIR]:
             try:
                 path.mkdir(parents=True, exist_ok=True)
             except Exception:
                 pass # 可能是权限问题，诊断时会报错
        
        # 3. 版本号兜底
        if not self.APP_VERSION or self.APP_VERSION == "0.0.0":
            self.APP_VERSION = "2.2.3" # Fallback hardcoded
        
        # 4. 视觉模型默认值
        if not self.AI_VISION_MODEL and self.AI_MODEL:
            self.AI_VISION_MODEL = self.AI_MODEL

# ===================================================
# 全局单例与兼容层
# ===================================================

# 1. 实例化配置对象 (加载 .env)
# 为了避免 import 时的磁盘 I/O 阻塞太久，也可以在此处使用 lazy loading，
# 但 Pydantic 本身很快，直接实例化即可。
try:
    settings = AppSettings()
except Exception as e:
    # 极端情况：.env 格式错误导致无法启动
    # 这里做一个简单的 fallback 打印，避免静默崩溃
    print(f"CRITICAL CONFIG ERROR: {e}")
    # 尝试无 .env 启动
    settings = AppSettings(_env_file=None)

# 2. 兼容性导出 (为了不破坏现有的 import config 引用)
# 将 settings 的属性映射到模块全局变量
# 这是重构过渡期的关键：让旧代码 `config.AI_API_KEY` 依然能工作
def _export_to_module():
    current_module = sys.modules[__name__]
    for key, value in settings.model_dump().items():
        # SecretStr 需要显式转为字符串供旧代码使用
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        
        # 针对列表字段的手动转换 (Compatibility Hook)
        if key == "SAFE_COUNTRY_CODES":
            value = [x.strip().upper() for x in str(value).split(",") if x.strip()]
        elif key == "DANGEROUS_ISP_KEYWORDS":
            value = [x.strip() for x in str(value).split(",") if x.strip()]
            
        # 将配置项注入到当前模块的全局命名空间
        setattr(current_module, key, value)

    # 补充旧版特有的辅助变量/常量
    setattr(current_module, "IS_FROZEN", IS_FROZEN)
    # 兼容 aliases (旧 config 中的逻辑)
    if not hasattr(current_module, "VOLC_TTS_TOKEN"):
        setattr(current_module, "VOLC_TTS_TOKEN", settings.VOLC_TTS_ACCESS_TOKEN.get_secret_value())

_export_to_module()


# 3. 提供更新方法 (供 UI 设置保存使用) - 引入 Debounce (Task 6)
import threading
import time

_config_save_lock = threading.Lock()
_pending_config_updates: Dict[str, Any] = {}
_config_debounce_timer: Optional[threading.Timer] = None

def _flush_config_updates():
    """执行实际的配置保存 (Worker)"""
    global _pending_config_updates, _config_debounce_timer
    
    with _config_save_lock:
         to_update = _pending_config_updates.copy()
         _pending_config_updates.clear()
         _config_debounce_timer = None
    
    if not to_update:
        return

    # 批量写入 .env 以减少 IO
    env_path = BASE_DIR / ".env"
    from dotenv import dotenv_values, set_key 
    
    # 1. 尝试一次性读取现有
    # 由于 set_key 每次只写一行，多次调用依然会有 IO 开销
    # 优化：如果 key 很多，可以重写整个文件，但为了安全起见暂时维持 loop set_key
    # 仅在非关键路径使用 debounce
    
    for k, v in to_update.items():
        try:
             # 如果文件不存在先创建
            if not env_path.exists():
                env_path.write_text("", encoding="utf-8")
            set_key(env_path, k, str(v))
        except Exception:
            pass

    # 处理 hot_reload (仅需 reload 一次)
    # 注意：这里我们假设 set_config 的调用者通常期望 hot_reload=True
    # 我们将在 flush 结束时统一 reload
    try:
        # 更新 os.environ
        for k, v in to_update.items():
             os.environ[k] = str(v)
             
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env", override=True)
        
        global settings
        settings = AppSettings()
        _export_to_module()
    except Exception as e:
        print(f"Reload config failed: {e}")

def set_config(key: str, value, persist: bool = True, hot_reload: bool = True) -> None:
    """
    更新配置并持久化到 .env
    (Task 6: 实现防抖机制，避免 UI 连续调整时频繁 I/O)
    """
    global settings, _config_debounce_timer
    
    # 立即更新内存中的 module level 变量，保证 UI 响应性 (Optimistic UI)
    current_module = sys.modules[__name__]
    setattr(current_module, key, value)
    
    # 同时更新 Pydantic 实例的一份拷贝(如果可能)，防止不一致
    # 但由于 settings 是不可变的(默认)，或者我们不想太复杂，暂时跳过 deeply sync settings object
    
    if not persist:
        # 仅内存更新
        if hot_reload:
             # 简单更新 environ 模拟
             os.environ[key] = str(value)
        return

    # 防抖处理
    with _config_save_lock:
        _pending_config_updates[key] = value
        
        # 取消上一次的 timer
        if _config_debounce_timer:
            _config_debounce_timer.cancel()
        
        # 启动新 timer (0.5s)
        _config_debounce_timer = threading.Timer(0.5, _flush_config_updates)
        _config_debounce_timer.start()


# 4. 提供重新加载方法
def reload_config():
    # 实际上 set_config(hot_reload=True) 已经做了，这里保留接口兼容
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
    global settings
    settings = AppSettings()
    _export_to_module()

# 5. 保留原有辅助函数接口 (兼容旧 UI 调用)
def get_startup_info() -> dict:
    return {
        "app_version": settings.APP_VERSION,
        "python_version": sys.version.split()[0],
        "is_frozen": IS_FROZEN,
        "data_dir": str(settings.DATA_DIR),
        "theme_mode": settings.THEME_MODE,
    }

def validate_required_config() -> list[str]:
    missing = []
    if not settings.ECHOTIK_API_KEY:
        missing.append("EchoTik API Key")
    # Pydantic 已经保证了字段存在，这里主要检查逻辑上的必填
    return missing

def get_volc_tts_token() -> str:
    """获取火山 TTS Token (兼容旧接口)"""
    return settings.VOLC_TTS_ACCESS_TOKEN.get_secret_value() if settings.VOLC_TTS_ACCESS_TOKEN else ""

