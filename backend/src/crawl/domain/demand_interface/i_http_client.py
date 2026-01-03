from abc import ABC, abstractmethod
from ..value_objects.http_response import HttpResponse

class IHttpClient(ABC):
    @abstractmethod
    def get(self, url: str, render_js: bool = False) -> HttpResponse:
        """
        执行HTTP GET请求
        参数:
            url: 目标URL
            render_js: 是否使用浏览器动态渲染页面 (默认为 False)
        返回: HttpResponse(status_code, headers, content, content_type)
        处理: 网络异常、超时、重试
        """
        pass
    
    @abstractmethod
    def head(self, url: str) -> HttpResponse:
        """
        执行HEAD请求(只获取响应头,不下载body)
        用途: 快速检查URL的Content-Type判断是否为PDF
        """
        pass
