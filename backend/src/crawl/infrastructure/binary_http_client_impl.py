"""
二进制 HTTP 客户端实现

使用 requests 库实现二进制内容下载，专门用于下载 PDF 等二进制文件。
"""

import requests
import logging
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ..domain.demand_interface.i_binary_http_client import IBinaryHttpClient
from ..domain.value_objects.binary_response import BinaryResponse

# 获取 logger
error_logger = logging.getLogger('infrastructure.error')
perf_logger = logging.getLogger('infrastructure.perf')


class BinaryHttpClientImpl(IBinaryHttpClient):
    """二进制 HTTP 客户端实现（使用 requests 库）"""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        max_retries: int = 3,
        retry_backoff: float = 0.3
    ):
        """
        初始化二进制 HTTP 客户端

        参数:
            user_agent: User-Agent 标识
            max_retries: 最大重试次数
            retry_backoff: 重试间隔倍数
        """
        self._user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        self._session = requests.Session()

        # 设置请求头
        self._session.headers.update({
            'User-Agent': self._user_agent,
            'Accept': 'application/pdf,application/octet-stream,*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })

        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
            connect=max_retries,
            read=max_retries,
            redirect=5,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def get_binary(self, url: str, timeout: int = 30) -> BinaryResponse:
        """
        下载二进制内容

        参数:
            url: 目标 URL
            timeout: 超时时间（秒）

        返回:
            BinaryResponse 值对象
        """
        try:
            response = self._session.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                stream=True,  # 使用流式下载以处理大文件
                verify=False  # 忽略 SSL 验证
            )

            # 读取全部内容
            content = response.content

            # 记录性能日志
            perf_logger.info(
                f"Binary GET {url} - {response.status_code} - {len(content)} bytes",
                extra={
                    'url': url,
                    'method': 'GET',
                    'status_code': response.status_code,
                    'content_length': len(content),
                    'component': 'BinaryHttpClientImpl'
                }
            )

            return BinaryResponse(
                url=url,
                status_code=response.status_code,
                headers=dict(response.headers),
                content=content,
                content_type=response.headers.get('Content-Type', ''),
                is_success=response.status_code == 200,
                error_message=None if response.status_code == 200 else f"HTTP {response.status_code}"
            )

        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            error_logger.error(
                f"Binary HTTP Timeout: {url}",
                extra={'url': url, 'error_type': 'Timeout'}
            )
            return self._create_error_response(url, error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            error_logger.error(
                f"Binary HTTP ConnectionError: {url} - {error_msg}",
                extra={'url': url, 'error_type': 'ConnectionError'}
            )
            return self._create_error_response(url, error_msg)

        except requests.exceptions.TooManyRedirects:
            error_msg = "Too many redirects"
            error_logger.error(
                f"Binary HTTP TooManyRedirects: {url}",
                extra={'url': url, 'error_type': 'TooManyRedirects'}
            )
            return self._create_error_response(url, error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            error_logger.error(
                f"Binary HTTP RequestException: {url} - {error_msg}",
                extra={'url': url, 'error_type': 'RequestException'}
            )
            return self._create_error_response(url, error_msg)

        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__} - {str(e)}"
            error_logger.error(
                f"Binary HTTP Unhandled Exception: {url} - {error_msg}",
                exc_info=True,
                extra={'url': url, 'error_type': 'Unhandled'}
            )
            return self._create_error_response(url, error_msg)

    def _create_error_response(self, url: str, error_message: str) -> BinaryResponse:
        """
        创建错误响应对象

        参数:
            url: 请求 URL
            error_message: 错误信息

        返回:
            表示错误的 BinaryResponse 对象
        """
        return BinaryResponse(
            url=url,
            status_code=0,
            headers={},
            content=b"",
            content_type="",
            is_success=False,
            error_message=error_message
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
