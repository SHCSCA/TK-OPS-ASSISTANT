import sys
import os
import time

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from services.browser_manager import BrowserManager

TARGET_URL = "https://www.tiktok.com/@dxgzu/video/7591957647121845535?is_from_webapp=1&sender_device=pc"

def verify_scraping():
    print(">>> 启动浏览器自动化测试...")
    bm = BrowserManager()
    
    # 强制有头模式，方便观察，且规避 headless 检测
    success = bm.start(headless=False)
    if not success:
        print("❌ 浏览器启动失败")
        return

    page = bm.get_page()
    if not page:
        print("❌ 页面创建失败")
        return
        
    page.on("requestfailed", lambda request: print(f"REQ FAILED: {request.url} : {request.failure}"))
    page.on("console", lambda msg: print(f"BROWSER LOG: {msg.text}"))

    try:
        print(f">>> 正在访问 URL: {TARGET_URL}")
        page.goto(TARGET_URL, timeout=60000)
        
        print(">>> 等待页面加载 (10s)...")
        page.wait_for_timeout(10000)
        
        # 尝试关闭弹窗
        try:
            page.locator("#login-modal-content button[data-e2e='modal-close-inner-button']").click(timeout=1000)
            page.keyboard.press("Escape")
        except:
            pass

        # 尝试切换到评论 Tab
        try:
            print(">>> 检查评论 Tab...")
            tabs = page.locator("#comments")
            if tabs.count() > 0:
                print("点击 #comments tab...")
                tabs.first.click()
                page.wait_for_timeout(2000)
        except: 
            pass

        print(f"page.title(): {page.title()}")
        
        # DEBUG: 打印页面上存在的某些关键 data-e2e，看看是否加载成功
        try:
            print(">>> DEBUG: 正在扫描页面 data-e2e 标记...")
            # 查找任意 data-e2e 元素
            all_e2es = page.locator("[data-e2e]").evaluate_all("list => list.map(e => e.getAttribute('data-e2e'))")
            unique_e2es = list(set(all_e2es))
            print(f"找到 {len(unique_e2es)} 个唯一的 data-e2e 标记.")
            comment_e2es = [e for e in unique_e2es if 'comment' in e]
            print(f"包含 'comment' 的标记: {comment_e2es}")

            # 进一步调试：查找所有 class 包含 comment 的元素
            print(">>> DEBUG: 查找 class 包含 'comment' 的元素...")
            comment_classes = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('*'))
                    .map(e => e.className)
                    .filter(c => c && typeof c === 'string' && c.toLowerCase().includes('comment'))
            }""")
            # 去重
            unique_classes = list(set(comment_classes))
            print(f"找到 {len(unique_classes)} 个 class 包含 comment 的样本. 前 5 个: {unique_classes[:5]}")
            
            if not comment_e2es and not unique_classes:
                 print("❌ 页面完全没有 comment 相关元素，可能评论被禁用或未加载。")
            
            # 保存页面 HTML 供离线分析
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print(">>> 已保存页面源码到 debug_page.html")

        except Exception as e:
            print(f"DEBUG Error: {e}")

        print(">>> 模拟滚动加载评论...")
        
        # Explicitly wait for real content (p tags inside comment items) to avoid Skeletons
        try:
            print(">>> Waiting for real comment text to load (Non-Skeleton)...")
            # Try to verify at least one item is NOT a skeleton
            # Focusing the list might trigger lazy load
            list_container = page.locator("div[class*='CommentListContainer']").first
            if list_container.count() > 0:
                list_container.click() # Focus
                page.keyboard.press("PageDown")
                page.wait_for_timeout(1000)
                page.keyboard.press("PageDown")
            
            page.wait_for_selector("div[class*='CommentItem']:not(:has(.TUXSkeletonRectangle))", timeout=20000)
            print(">>> Real content detected!")
        except Exception as e:
            print(f"WARNING: Real content wait timed out: {e}")
            print("Proceeding anyway, but expecting only skeletons.")

        # 多滚几次，确保评论加载出来
        for _ in range(3):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(2000)
            
        print(">>> 开始提取评论元素...")
        
        # 使用 Worker 中的最新选择器策略
        # 策略 A
        comment_elements = page.locator("div[data-e2e='comment-item-container']").all()
        print(f"策略 A (data-e2e) 找到: {len(comment_elements)} 个元素")
        
        # 策略 B
        if not comment_elements:
            print("切换策略 B (Class模糊匹配)...")
            comment_elements = page.locator("div[class*='CommentItem'], div[class*='comment-item']").all()
            print(f"策略 B 找到: {len(comment_elements)} 个元素")

        if not comment_elements:
            print("❌ 未找到任何评论容器，可能是反爬虫机制生效或者选择器失效。")
            with open("status.log", "w", encoding="utf-8") as f:
                f.write("FAIL: No elements found")
            return
            
        with open("status.log", "w", encoding="utf-8") as f:
            f.write(f"SUCCESS: Found {len(comment_elements)} elements")

        found_contents = []
        keywords = ["want", "need", "think"]
        
        for i, el in enumerate(comment_elements):
            try:
                # DEBUG: Print structure of first element
                if i == 0:
                    try:
                        # Scan all descendants
                        descendants = el.locator("*").all()
                        scan_log = []
                        scan_log.append(f"TOTAL DESCENDANTS: {len(descendants)}")
                        for d in descendants:
                            try:
                                tag = d.evaluate("el => el.tagName")
                                # Use text_content, potentially hidden
                                txt = d.text_content() 
                                html_frag = d.inner_html()
                                scan_log.append(f"TAG: {tag}")
                                scan_log.append(f"  TEXT_CONTENT: {txt[:50]}")
                                scan_log.append(f"  HTML_FRAG: {html_frag[:50]}...")
                                classes = d.get_attribute("class")
                                scan_log.append(f"  CLASSES: {classes}")
                                data_e2e = d.get_attribute("data-e2e")
                                if(data_e2e):
                                    scan_log.append(f"  DATA-E2E: {data_e2e}")
                                scan_log.append("-" * 20)
                            except Exception as inner_e:
                                scan_log.append(f"  ERROR: {inner_e}")
                        
                        with open("scan_result.txt", "w", encoding="utf-8") as f:
                            f.write("\n".join(scan_log))
                        print(">>> Saved scan result to scan_result.txt")
                    except Exception as e:
                        with open("scan_error.log", "w") as f:
                            f.write(str(e))

                # 尝试抓取文本
                text_el = el.locator("p[data-e2e='comment-level-1']")
                if text_el.count() == 0:
                    text_el = el.locator("p")
                
                user_el = el.locator("span[data-e2e='comment-username']")
                if user_el.count() == 0:
                    user_el = el.locator("a[href*='@']")
                
                if text_el.count() > 0:
                    text = text_el.first.inner_text().strip()
                    user = user_el.first.inner_text().strip() if user_el.count() > 0 else "Unknown"
                    
                    found_contents.append(f"@{user}: {text}")
                    
                    # 检查关键词
                    for kw in keywords:
                        if kw in text.lower():
                            print(f"✅ [HIT] 命中关键词 '{kw}': @{user} 说: {text}")
            except Exception as e:
                print(f"⚠️ 解析单个评论出错: {e}")

        print(f"\n>>> 扫描完成，共提取 {len(found_contents)} 条评论。")
        if len(found_contents) > 0:
            print("前 5 条样本:")
            for c in found_contents[:5]:
                print(f" - {c}")
        else:
            print("❌ 未提取到任何文本内容。")

    except Exception as e:
        print(f"❌ 测试过程发生异常: {e}")
    finally:
        print(">>> 测试结束，清理资源...")
        # page.close()
        # bm.stop() 
        # 为了让用户看到结果，这里甚至可以先不关，或者等待一下
        page.close()
        bm.stop()

if __name__ == "__main__":
    try:
        with open("boot.log", "w") as f:
            f.write("Started")
        verify_scraping()
    except Exception as e:
        with open("crash.log", "w") as f:
            f.write(str(e))
