"""
剪贴板监听器：自动识别 URL → 入队下载 → 入库 → 可选自动处理
"""
import threading
import time
from typing import Callable, Optional
import re


class ClipboardMonitor:
    """后台监听剪贴板，检测到 URL 自动入队"""
    
    TIKTOK_URL_PATTERNS = [
        r'https?://(?:www\.)?tiktok\.com/@[\w\.\-]+/video/\d+',
        r'https?://(?:m\.)?tiktok\.com/@[\w\.\-]+/video/\d+',
        r'https?://(?:www\.)?tiktok\.com/video/\d+',
        r'https?://vt\.tiktok\.com/\w+',
    ]
    
    def __init__(self, on_url_detected: Callable[[str], None]):
        """
        Args:
            on_url_detected: 检测到 URL 时的回调函数，接受 url 字符串
        """
        self.on_url_detected = on_url_detected
        self.thread = None
        self.running = False
        self.last_clipboard = ""
        self.pause = False
    
    def _get_clipboard_text(self) -> str:
        """跨平台获取剪贴板文本"""
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception:
            try:
                # Windows 兜底方案
                import subprocess
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-Clipboard'],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                return result.stdout.strip()
            except Exception:
                return ""
    
    def _is_tiktok_url(self, text: str) -> bool:
        """检查是否为 TikTok URL"""
        for pattern in self.TIKTOK_URL_PATTERNS:
            if re.match(pattern, text):
                return True
        return False
    
    def start(self):
        """启动后台监听线程"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止监听"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
    
    def _monitor_loop(self):
        """后台监听循环"""
        while self.running:
            if not self.pause:
                try:
                    current_clipboard = self._get_clipboard_text()
                    
                    # 检测变化 & TikTok URL
                    if (current_clipboard != self.last_clipboard and 
                        current_clipboard.startswith('http') and
                        self._is_tiktok_url(current_clipboard)):
                        
                        self.last_clipboard = current_clipboard
                        if self.on_url_detected:
                            try:
                                self.on_url_detected(current_clipboard)
                            except Exception:
                                pass
                except Exception:
                    pass
            
            time.sleep(2)  # 每 2 秒检测一次


class ClipboardURLQueue:
    """剪贴板 URL 入队管理（支持去重、限制长度）"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.queue = []
        self.seen = set()
    
    def add(self, url: str) -> bool:
        """添加 URL（去重）"""
        if url not in self.seen:
            self.queue.append(url)
            self.seen.add(url)
            
            # 超出限制时删除最老的
            if len(self.queue) > self.max_size:
                removed = self.queue.pop(0)
                self.seen.discard(removed)
            
            return True
        return False
    
    def get_next(self) -> Optional[str]:
        """取出下一个 URL"""
        if self.queue:
            return self.queue.pop(0)
        return None
    
    def peek(self) -> Optional[str]:
        """查看但不取出"""
        return self.queue[0] if self.queue else None
    
    def size(self) -> int:
        """队列大小"""
        return len(self.queue)
