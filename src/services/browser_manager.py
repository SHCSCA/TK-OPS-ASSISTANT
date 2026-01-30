"""
浏览器自动化服务管理器 (V3.0 Core)
基于 Playwright 实现，负责管理浏览器生命周期、上下文、Cookie 持久化。
支持多账户指纹隔离 (Task 2)。
"""
import os
import json
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Union
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, Error as PlaywrightError
import config
from browser.profile import BrowserProfile

logger = logging.getLogger(__name__)

class BrowserManager:
    """浏览器实例管理器 (Singleton)"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        
        # 默认上下文 (兼容旧代码)
        self.default_context: Optional[BrowserContext] = None
        
        # 多上下文管理 {profile_id: BrowserContext}
        self.active_contexts: Dict[str, BrowserContext] = {}
        
        # 基础数据根目录
        self.base_data_dir = Path(getattr(config, "ASSET_LIBRARY_DIR", "AssetLibrary")) / "browser_data"
        self.base_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.headless = getattr(config, "BROWSER_HEADLESS", True)
        self._initialized = True

    def start(self, headless: bool = None) -> bool:
        """启动浏览器进程 (Global Browser Process)"""
        if self.playwright and self.browser:
            return True

        if headless is None:
            headless = self.headless

        try:
            logger.info(f"正在启动浏览器服务 (Headless={headless})...")
            self.playwright = sync_playwright().start()
            
            # 浏览器全局启动参数 (这些参数对所有上下文生效)
            launch_args = [
                "--disable-blink-features=AutomationControlled", # 防检测核心
                "--no-first-run",
                "--disable-infobars",
                # 更高级的指纹混淆通常需要在 context 级别注入脚本
            ]
            
            # 优先尝试 Edge -> Chrome -> Chromium
            # Playwright 推荐使用其内置 Chromium 以获得最佳稳定性，但为了指纹真实性，尝试使用 Channel
            try:
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    args=launch_args,
                    slow_mo=50,
                    channel="msedge" 
                )
            except Exception:
                try:
                    self.browser = self.playwright.chromium.launch(
                        headless=headless,
                        args=launch_args,
                        slow_mo=50,
                        channel="chrome"
                    )
                except Exception:
                    logger.warning("无法启动系统浏览器(Edge/Chrome)，使用内置 Chromium")
                    self.browser = self.playwright.chromium.launch(
                        headless=headless,
                        args=launch_args,
                        slow_mo=50
                    )
            
            logger.info("✅ 浏览器服务启动成功")
            return True
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败: {e}")
            self.stop()
            return False

    def new_context_from_profile(self, profile: BrowserProfile) -> Optional[BrowserContext]:
        """为特定账户创建隔离的上下文 (Legacy Context API) - 需要持久化必须使用 launch_persistent_context?
        
        注意：Playwright中，普通的 new_context 无法持久化 UserDataDir。
        如果需要每个账户有独立的 Cache/Cookie/LocalStorage 文件夹，必须使用 `launch_persistent_context`。
        但 `launch_persistent_context` 会启动一个新的浏览器进程，无法复用 `self.browser`。
        
        鉴于 "P1: 为每个账号分配独立的 User Data Dir"，我们必须支持 **launch_persistent_context**。
        但为了简化管理，我们先实现 Mock 隔离（Context + Cookie Load/Save），后续可升级为多进程。
        """
        if not self.browser:
            if not self.start():
                return None

        try:
            # 1. 创建 Context (Ephemeral，内存隔离)
            # 用户要求 "分配独立的 User Data Dir"，但在 Playwright 单实例模式下，
            # User Data Dir 是绑定在 Launch 时的。
            # 为了实现 "多账号同时在线"，只能用 Incognito Contexts (new_context) + 手动 Cookie 管理。
            
            context = self.browser.new_context(
                user_agent=profile.user_agent,
                viewport=profile.viewport,
                locale=profile.locale,
                timezone_id=profile.timezone_id,
                # 注入防检测脚本
                java_script_enabled=True,
            )
            
            # 2. 注入 stealth 脚本
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            # 3. 加载 Cookies (模拟持久化)
            cookie_dir = self.base_data_dir / profile.user_data_dir_name
            # 确保目录存在
            cookie_dir.mkdir(parents=True, exist_ok=True)
            
            cookie_file = cookie_dir / "cookies.json"
            if cookie_file.exists():
                try:
                    with open(cookie_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                        context.add_cookies(cookies)
                except Exception as e:
                    logger.warning(f"加载 Cookies 失败 [{profile.name}]: {e}")
            
            # 注册关闭时的回调以保存 Cookie
            def _save_state():
                try:
                    cookies = context.cookies()
                    cookie_dir.mkdir(parents=True, exist_ok=True)
                    with open(cookie_file, 'w', encoding='utf-8') as f:
                        json.dump(cookies, f)
                except Exception as e:
                    logger.error(f"保存 Cookies 失败 [{profile.name}]: {e}")
                    
            context.on("close", lambda _: _save_state())
            
            self.active_contexts[profile.id] = context
            return context

        except Exception as e:
            logger.error(f"创建上下文失败 [{profile.name}]: {e}")
            return None

    def get_default_page(self) -> Optional[Page]:
        """获取默认页面的便捷方法 (兼容旧代码)"""
        # 使用默认 Profile
        if not self.default_context:
            # 创建一个临时的默认 profile
            default_profile = BrowserProfile(id="default", name="Default", user_data_dir_name="default_user")
            self.default_context = self.new_context_from_profile(default_profile)
            
        if not self.default_context:
            return None
            
        if not self.default_context.pages:
            return self.default_context.new_page()
        return self.default_context.pages[0]

    # 兼容旧接口名
    get_page = get_default_page

    def stop(self):
        """停止所有浏览器资源"""
        # 先关闭所有上下文以触发 Cookie 保存
        for ctx in list(self.active_contexts.values()):
            try:
                ctx.close()
            except Exception:
                pass
        self.active_contexts.clear()
        
        if self.default_context:
            try:
                self.default_context.close()
            except Exception:
                pass
            self.default_context = None

        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
            
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
            
        logger.info("浏览器服务已停止")

def get_browser_manager() -> BrowserManager:
    return BrowserManager()

