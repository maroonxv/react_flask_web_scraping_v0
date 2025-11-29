import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional
from dataclasses import dataclass

from crawl.domain.demand_interface.i_http_client import IHttpClient


@dataclass
class HttpResponse:
    """HTTP响应值对象"""
    url: str
    status_code: int
    headers: dict
    content: str
    content_type: str
    is_success: bool
    error_message: Optional[str] = None


class HttpClientImpl(IHttpClient):
    """基于requests库的HTTP客户端实现"""
    
    def __init__(
        self,
        user_agent: str = "WebCrawler/1.0",
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff: float = 0.3
    ):
        """
        初始化HTTP客户端
        
        参数:
            user_agent: User-Agent标识
            timeout: 请求超时时间(秒)
            max_retries: 最大重试次数
            retry_backoff: 重试间隔倍数
        """
        self._timeout = timeout
        self._session = requests.Session()
        
        # 设置请求头
        self._session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码自动重试
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    
    def get(self, url: str) -> HttpResponse:
        """
        执行HTTP GET请求
        
        参数:
            url: 目标URL
            
        返回:
            HttpResponse对象，包含响应信息或错误信息
        """
        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
                allow_redirects=True  # 自动跟随重定向
            )
            
            # 检测编码
            encoding = response.encoding or 'utf-8'
            if response.apparent_encoding:
                encoding = response.apparent_encoding
            
            return HttpResponse(
                url=response.url,  # 重定向后的最终URL
                status_code=response.status_code,
                headers=dict(response.headers),
                content=response.content.decode(encoding, errors='ignore'),
                content_type=response.headers.get('Content-Type', ''),
                is_success=response.status_code == 200,
                error_message=None if response.ok else f"HTTP {response.status_code}"
            )
            
        except requests.exceptions.Timeout:
            return self._create_error_response(
                url, "请求超时", f"请求超过{self._timeout}秒未响应"
            )
        
        except requests.exceptions.ConnectionError as e:
            return self._create_error_response(
                url, "连接失败", f"无法连接到服务器: {str(e)}"
            )
        
        except requests.exceptions.TooManyRedirects:
            return self._create_error_response(
                url, "重定向过多", "重定向次数超过限制"
            )
        
        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                url, "请求异常", f"请求失败: {str(e)}"
            )
        
        except Exception as e:
            return self._create_error_response(
                url, "未知错误", f"未预期的错误: {type(e).__name__} - {str(e)}"
            )
    
    def head(self, url: str) -> HttpResponse:
        """
        执行HEAD请求(只获取响应头)
        
        参数:
            url: 目标URL
            
        返回:
            HttpResponse对象(content为空字符串)
        """
        try:
            response = self._session.head(
                url,
                timeout=10,  # HEAD请求用较短超时
                allow_redirects=True
            )
            
            return HttpResponse(
                url=response.url,
                status_code=response.status_code,
                headers=dict(response.headers),
                content='',  # HEAD请求没有body
                content_type=response.headers.get('Content-Type', ''),
                is_success=response.status_code == 200,
                error_message=None if response.ok else f"HTTP {response.status_code}"
            )
            
        except requests.exceptions.Timeout:
            return self._create_error_response(
                url, "HEAD请求超时", "HEAD请求超时"
            )
        
        except requests.exceptions.ConnectionError:
            return self._create_error_response(
                url, "连接失败", "无法连接到服务器"
            )
        
        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                url, "HEAD请求失败", f"HEAD请求异常: {str(e)}"
            )
        
        except Exception as e:
            return self._create_error_response(
                url, "未知错误", f"未预期的错误: {str(e)}"
            )
    
    def _create_error_response(
        self, 
        url: str, 
        error_type: str, 
        error_detail: str
    ) -> HttpResponse:
        """
        创建错误响应对象
        
        参数:
            url: 请求URL
            error_type: 错误类型
            error_detail: 错误详情
            
        返回:
            表示错误的HttpResponse对象
        """
        return HttpResponse(
            url=url,
            status_code=0,
            headers={},
            content='',
            content_type='',
            is_success=False,
            error_message=f"{error_type}: {error_detail}"
        )
    
    def close(self):
        """关闭会话，释放连接"""
        self._session.close()
    
    def __enter__(self):
        """支持上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时自动关闭会话"""
        self.close()
