from typing import Optional
from ..domain.demand_interface.i_http_client import IHttpClient
from ..domain.value_objects.http_response import HttpResponse
from .http_client_impl import HttpClientImpl
from .playwright_client import PlaywrightClient

class HybridHttpClient(IHttpClient):
    """
    混合模式 HTTP 客户端
    组合了 HttpClientImpl (静态) 和 PlaywrightClient (动态)
    根据 render_js 参数智能切换
    """
    
    def __init__(self, static_client: HttpClientImpl, playwright_client: PlaywrightClient):
        self._static_client = static_client
        self._dynamic_client = playwright_client
    
    def get(self, url: str, headers: Optional[dict] = None, render_js: bool = False) -> HttpResponse:
        """
        执行GET请求，支持动静切换
        """
        # 1. 如果不需要渲染 JS，直接使用静态客户端
        if not render_js:
            return self._static_client.get(url, headers=headers)
        
        # 2. 如果需要渲染 JS，使用 Playwright
        try:
            # 这里的 fetch_page 会启动浏览器并渲染
            content = self._dynamic_client.fetch_page(url)
            
            # 构造成功的响应对象
            # 注意：Playwright 获取的状态码稍微麻烦一点，这里简化处理，假设成功就是 200
            # 真实的 status code 需要在 page.on("response") 中捕获，比较复杂，暂略
            return HttpResponse(
                url=url,
                status_code=200, 
                headers={"Content-Type": "text/html; charset=utf-8"}, # 模拟 header
                content=content,
                content_type="text/html",
                is_success=True,
                error_message=None
            )
            
        except Exception as e:
            # 动态渲染失败
            return HttpResponse(
                url=url,
                status_code=0,
                headers={},
                content="",
                content_type="",
                is_success=False,
                error_message=f"Dynamic Rendering Failed: {str(e)}"
            )

    def head(self, url: str) -> HttpResponse:
        """
        HEAD 请求总是使用静态客户端 (Playwright 没有简单的 HEAD 方法)
        """
        return self._static_client.head(url)

    def close(self):
        if hasattr(self._static_client, 'close'):
            self._static_client.close()
