from playwright.sync_api import sync_playwright
import time
import logging

# 获取 logger
error_logger = logging.getLogger('infrastructure.error')
perf_logger = logging.getLogger('infrastructure.perf')

class PlaywrightClient:
    """
    Playwright 客户端封装
    
    注意：为了确保多线程安全性（Playwright Sync API 非线程安全），
    且避免复杂的线程池管理，这里采用 '每次请求启动独立实例' 的策略。
    虽然会有启动开销，但作为'降级兜底'方案，且在课程设计场景下，
    稳定性和代码简洁性优于极致性能。
    """

    def fetch_page(self, url: str, wait_for_selector: str = None) -> str:
        """
        使用浏览器渲染页面并获取 HTML
        
        参数:
            url: 目标 URL
            wait_for_selector: 可选，等待特定元素出现
            
        返回:
            渲染后的 HTML 内容
        """
        start_time = time.time()
        # 使用上下文管理器，确保每次都自动关闭资源
        with sync_playwright() as p:
            # 启动浏览器 (chromium)
            # headless=True 表示无头模式（不显示界面）
            browser = p.chromium.launch(headless=True)
            
            try:
                # 创建新上下文（相当于隐身窗口）
                # 可以设置 User-Agent, Viewport 等
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                page = context.new_page()
                
                # 访问页面
                # wait_until='networkidle' 表示等待网络空闲（通常意味着JS加载完成）
                # timeout 设置为 30s
                page.goto(url, wait_until="networkidle", timeout=30000)
                
                # 如果指定了等待元素
                if wait_for_selector:
                    try:
                        page.wait_for_selector(wait_for_selector, timeout=5000)
                    except Exception:
                        pass # 等不到也不报错，继续获取现有内容
                
                # 获取渲染后的 HTML
                content = page.content()
                
                # 记录性能日志
                elapsed_ms = (time.time() - start_time) * 1000
                perf_logger.info(f"Playwright Render {url} - {elapsed_ms:.2f}ms", extra={
                    'url': url,
                    'method': 'RENDER',
                    'elapsed_ms': elapsed_ms,
                    'component': 'PlaywrightClient'
                })
                
                return content
                
            except Exception as e:
                error_logger.error(f"Playwright Error: {url} - {str(e)}", exc_info=True, extra={'url': url, 'component': 'PlaywrightClient'})
                raise e
            finally:
                browser.close()
