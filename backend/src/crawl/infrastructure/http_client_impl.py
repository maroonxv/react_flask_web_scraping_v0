import requests
import time
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional
from ..domain.demand_interface.i_http_client import IHttpClient
from ..domain.value_objects.http_response import HttpResponse

# 获取 logger
error_logger = logging.getLogger('infrastructure.error')
perf_logger = logging.getLogger('infrastructure.perf')

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
        self._max_retries = max_retries

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
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            raise_on_status=False,
            # 启用连接相关异常的重试
            connect=max_retries,  # 连接失败重试次数
            read=max_retries,     # 读取超时重试次数
            redirect=5,           # 重定向次数
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    
    def get(self, url: str, headers: Optional[dict] = None, render_js: bool = False) -> HttpResponse:
        """
        执行HTTP GET请求
        
        参数:
            url: 目标URL
            headers: 自定义请求头(可选)
            render_js: 是否使用动态渲染 (HttpClientImpl不支持此功能，若为True将忽略或仅执行静态请求)
            
        返回:
            HttpResponse对象，包含响应信息或错误信息
        """
        start_time = time.time()
        try:
            # 合并会话头和自定义头
            request_headers = None
            if headers:
                request_headers = headers
            
            response = self._session.get(
                url,
                headers=request_headers,
                timeout=self._timeout,
                allow_redirects=True  # 自动跟随重定向
            )
            
            # 计算耗时 (ms)
            elapsed_ms = (time.time() - start_time) * 1000
            
            # 记录性能日志
            perf_logger.info(f"HTTP GET {url} - {response.status_code} - {elapsed_ms:.2f}ms", extra={
                'url': url,
                'method': 'GET',
                'status_code': response.status_code,
                'elapsed_ms': elapsed_ms,
                'component': 'HttpClientImpl'
            })

            # =========== 针对各种编码情况做的处理 ===========
            
            # 1. 使用 apparent_encoding 自动检测编码
            if response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding
            
            # 2. 如果 apparent_encoding 也没检测出来（罕见），兜底用 utf-8
            if not response.encoding:
                response.encoding = 'utf-8'
                
            # 3. 获取内容
            # response.text 会自动使用上面设置好的 response.encoding 进行解码
            # 只要 encoding 设置对，这里就不会乱码
            content = response.text
            
            return HttpResponse(
                url=response.url,
                status_code=response.status_code,
                headers=dict(response.headers),
                content=content,
                content_type=response.headers.get('Content-Type', ''),
                is_success=response.ok,
                error_message=None if response.ok else f"HTTP {response.status_code}"
            )
            
        except requests.exceptions.Timeout:
            error_msg = f"请求超过{self._timeout}秒未响应"
            error_logger.error(f"HTTP Timeout: {url} - {error_msg}", extra={'url': url, 'error_type': 'Timeout'})
            return self._create_error_response(url, "请求超时", error_msg)
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"无法连接到服务器: {str(e)}"
            error_logger.error(f"HTTP ConnectionError: {url} - {error_msg}", extra={'url': url, 'error_type': 'ConnectionError'})
            return self._create_error_response(url, "连接失败", error_msg)
        
        except requests.exceptions.TooManyRedirects:
            error_msg = "重定向次数超过限制"
            error_logger.error(f"HTTP TooManyRedirects: {url}", extra={'url': url, 'error_type': 'TooManyRedirects'})
            return self._create_error_response(url, "重定向过多", error_msg)
        
        except requests.exceptions.HTTPError as e:  # ✅ 添加 HTTPError 专门处理
            error_msg = f"HTTP错误: {str(e)}"
            error_logger.error(f"HTTP HTTPError: {url} - {error_msg}", extra={'url': url, 'error_type': 'HTTPError'})
            return self._create_error_response(url, "HTTP错误", error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {str(e)}"
            error_logger.error(f"HTTP RequestException: {url} - {error_msg}", extra={'url': url, 'error_type': 'RequestException'})
            return self._create_error_response(url, "请求异常", error_msg)
        
        except Exception as e:
            error_msg = f"未预期的错误: {type(e).__name__} - {str(e)}"
            error_logger.error(f"HTTP Unhandled Exception: {url} - {error_msg}", exc_info=True, extra={'url': url, 'error_type': 'Unhandled'})
            return self._create_error_response(url, "未知错误", error_msg)
    
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
                timeout=self._timeout,
                allow_redirects=True
            )
            
            return HttpResponse(
                url=response.url,
                status_code=response.status_code,
                headers=dict(response.headers),
                content='',  # HEAD请求没有body
                content_type=response.headers.get('Content-Type', ''),
                is_success=response.ok,  # 包含所有200-299的状态码情况
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
