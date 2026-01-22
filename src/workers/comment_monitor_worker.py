"""
实时评论监控 Worker (基于 V3.0 Playwright)
负责启动浏览器，访问指定视频/页面，抓取评论并匹配关键词。
"""
import time
import random
from PyQt5.QtCore import pyqtSignal
from workers.base_worker import BaseWorker
from services.browser_manager import get_browser_manager

class CommentMonitorWorker(BaseWorker):
    # (user, content, timestamp)
    new_comment_signal = pyqtSignal(str, str, str)
    
    def __init__(self, target_url: str, keywords: list[str]):
        super().__init__()
        self.target_url = target_url
        self.keywords = [k.lower() for k in keywords if k.strip()]
        self.browser_manager = get_browser_manager()
        self.is_running = True

    def _run_impl(self):
        if not self.target_url:
            self.emit_finished(False, "未提供目标视频链接")
            return

        self.emit_log(f"🚀 正在启动浏览器内核...")
        # TikTok 反爬严重，强制使用有头模式 (Headless=False) 以绕过检测
        # 允许用户看到浏览器窗口，方便排查是否弹出了验证码
        if not self.browser_manager.start(headless=False):
            self.emit_finished(False, "浏览器启动失败，请检查 Playwright 是否安装")
            return

        page = self.browser_manager.get_page()
        if not page:
            self.emit_finished(False, "无法创建浏览器页面")
            return

        try:
            self.emit_log(f"🔗 正在访问: {self.target_url}")
            page.goto(self.target_url, timeout=60000)
            
            # 等待评论区加载 (TikTok 的评论区通常在视频下方或侧边)
            # 简单的反爬处理：随机等待，模拟鼠标移动
            self.emit_log("⏳ 等待页面加载...")
            page.wait_for_timeout(5000)
            
            # 尝试点击 "Login" 弹窗关闭 (如果有)
            try:
                # 尝试关闭常见的登录弹窗/体验弹窗
                page.locator("#login-modal-content button[data-e2e='modal-close-inner-button']").click(timeout=1000)
                page.keyboard.press("Escape") 
            except:
                pass

            # [新增] 检查评论是否需要点击 Tab 才能显示
            try:
                # 只有当找不到评论元素时才尝试点击
                if page.locator("div[class*='CommentItem']").count() == 0:
                    tab = page.locator("#comments").first
                    if tab.count() > 0:
                        self.emit_log("💡 检测到评论 Tab，尝试点击展开评论区...")
                        tab.click()
                        page.wait_for_timeout(3000)
            except Exception as e:
                self.emit_log(f"⚠️ 尝试展开评论区出错: {e}")

            self.emit_log(f"🔍 开始扫描评论流 (当前关键词: {self.keywords})...")
            
            # 循环监控
            seen_comments = set()
            no_new_count = 0
            
            while self.is_running:
                # 滚动以加载更多评论
                page.mouse.wheel(0, 2000) # 加大滚动幅度
                page.wait_for_timeout(2000)
                
                # 抓取评论元素的多重策略
                # 策略 A: 标准 data-e2e
                comment_elements = page.locator("div[data-e2e='comment-item-container']").all()
                
                # 策略 B: 尝试通过 Class 特征抓取 (如果 A 失败)
                if not comment_elements:
                    # 查找包含 CommentText 的 div
                    # 这是一个较松散的定位，但能应对 DOM 变化
                    comment_elements = page.locator("div[class*='CommentItem'], div[class*='comment-item']").all()

                found_new_this_round = False
                scan_count_this_round = 0
                
                for el in comment_elements:
                    try:
                        scan_count_this_round += 1
                        # 提取文本 - 增强兼容性
                        text_el = el.locator("p[data-e2e='comment-level-1']")
                        # 如果找不到 data-e2e，尝试找任何 P 标签 (可能是评论内容)
                        if text_el.count() == 0:
                             text_el = el.locator("p")

                        user_el = el.locator("span[data-e2e='comment-username']")
                        # 如果找不到用户名，尝试找 href 包含 @ 的链接
                        if user_el.count() == 0:
                            user_el = el.locator("a[href*='@']")
                        
                        if text_el.count() == 0: continue
                        
                        text = text_el.first.inner_text().strip()
                        # 用户名兜底
                        user = "Anonymous"
                        if user_el.count() > 0:
                            user = user_el.first.inner_text().strip()
                        
                        # 唯一标识
                        sig = f"{user}:{text}"
                        if sig in seen_comments:
                            continue
                            
                        seen_comments.add(sig)
                        found_new_this_round = True
                        
                        # 关键词匹配 (转小写)
                        text_lower = text.lower()
                        if any(kw in text_lower for kw in self.keywords):
                            timestamp = time.strftime("%H:%M:%S")
                            self.new_comment_signal.emit(user, text, timestamp)
                            self.emit_log(f"🔥 命中关键词: @{user}: {text}...")
                        
                        # Debug: 可以在日志输出扫描到的非目标评论，方便调试 (可选，为了不刷屏先注释)
                        # else:
                        #     self.emit_log(f"扫描: {text[:10]}...") 
                            
                    except Exception as e:
                        continue
                
                # 反馈扫描状态
                if found_new_this_round:
                    no_new_count = 0
                else:
                    no_new_count += 1
                
                # 每 5 轮只要没找到新评论，就提示一下正在运行
                if no_new_count % 5 == 0 and no_new_count > 0:
                    self.emit_log(f"⏳ 正在扫描... 已累计监听 {len(seen_comments)} 条评论")
                
                # 检查停止信号
                if self.should_stop():
                    break
                    page.wait_for_timeout(5000)
                    no_new_count = 0 # 重置以免频繁 log
                
                # 检查停止信号
                if self.should_stop():
                    break
                    
            self.emit_finished(True, "监控结束")
            
        except Exception as e:
            self.emit_finished(False, f"监控中断: {e}")
        finally:
            # 任务结束不关闭 BrowserManager (它是全局单例)，只关闭 Page
            try:
                page.close()
            except:
                pass
            self.is_running = False

    def stop(self):
        self.is_running = False
        super().stop()
