"""
浏览器自动化服务管理器 (V3.0 Core)
基于 Playwright 实现，负责管理浏览器生命周期、上下文、Cookie 持久化。
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, Error as PlaywrightError
import config

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
        self.context: Optional[BrowserContext] = None
        
        # 用户数据目录 (保存 Cookie/LocalStorage)
        self.user_data_dir = Path(getattr(config, "ASSET_LIBRARY_DIR", "AssetLibrary")) / "browser_data"
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.headless = getattr(config, "BROWSER_HEADLESS", True)
        self._initialized = True

    def start(self, headless: bool = None) -> bool:
        """启动浏览器进程"""
        if self.playwright and self.browser:
            return True

        # 优先使用传入参数，否则使用配置
        if headless is None:
            headless = self.headless

        try:
            logger.info(f"正在启动浏览器服务 (Headless={headless})...")
            self.playwright = sync_playwright().start()
            
            # 启动参数配置
            launch_args = [
                "--disable-blink-features=AutomationControlled", # 防检测核心
                "--no-first-run",
            ]
            
            # 启动浏览器 (Chromium)
            # 尝试使用系统已安装的 Edge，避免等待下载 Chromium
            try:
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    args=launch_args,
                    slow_mo=50, # 稍微减速，模拟人类
                    channel="msedge" 
                )
            except Exception as e:
                logger.warning(f"无法启动系统 Edge，尝试使用内置 Chromium: {e}")
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    args=launch_args,
                    slow_mo=50
                )
            
            # 创建上下文 (加载状态)
            self._create_context()
            
            logger.info("✅ 浏览器服务启动成功")
            return True
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败: {e}")
            self.stop()
            return False

    def _create_context(self):
        """创建浏览器上下文，注入防检测脚本"""
        if not self.browser:
            return

        # 模拟真实 User-Agent (Win10 Chrome)
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        self.context = self.browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 720},
            locale="zh-CN",
            timezone_id="Asia/Shanghai"
        )
        
        # 注入 Stealth 脚本 (绕过 `navigator.webdriver`)
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        # 尝试加载 Cookies
        self._load_cookies()

    def get_page(self) -> Optional[Page]:
        """获取一个新页面"""
        if not self.context:
            if not self.start():
                return None
        
        try:
            return self.context.new_page()
        except Exception as e:
            logger.error(f"创建页面失败: {e}")
            return None

    def stop(self):
        """停止服务并保存状态"""
        try:
            if self.context:
                self._save_cookies()
                self.context.close()
                self.context = None
            
            if self.browser:
                self.browser.close()
                self.browser = None
                
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
                
            logger.info("浏览器服务已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器服务异常: {e}")

    def _save_cookies(self):
        """保存 Cookies 到磁盘"""
        if not self.context:
            return
        
        try:
            cookies = self.context.cookies()
            cookie_file = self.user_data_dir / "cookies.json"
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            logger.debug(f"Cookies 已保存: {len(cookies)} 条")
        except Exception as e:
            logger.error(f"保存 Cookies 失败: {e}")

    def _load_cookies(self):
        """从磁盘加载 Cookies"""
        if not self.context:
            return
            
        cookie_file = self.user_data_dir / "cookies.json"
        if not cookie_file.exists():
            return
            
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            self.context.add_cookies(cookies)
            logger.debug(f"Cookies 已加载: {len(cookies)} 条")
        except Exception as e:
            logger.warning(f"加载 Cookies 失败 (可能是文件损坏): {e}")

# 全局单例访问入口
_global_browser_manager = None

def get_browser_manager() -> BrowserManager:
    global _global_browser_manager
    if _global_browser_manager is None:
        _global_browser_manager = BrowserManager()
    return _global_browser_manager
