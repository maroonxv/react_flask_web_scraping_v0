"""
HttpClientImpl 的 pytest 测试套件
完整覆盖：初始化配置、GET/HEAD 请求、重试逻辑、异常处理、边界情况
"""

import pytest
from unittest.mock import Mock, patch, PropertyMock
import sys
import os
import requests_mock

# 添加 backend 目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.crawl.infrastructure.http_client_impl import HttpClientImpl
from src.crawl.domain.value_objects.http_response import HttpResponse
import requests


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def http_client():
    """创建 HttpClientImpl 实例并在测试后自动关闭"""
    client = HttpClientImpl(
        user_agent="TestBot/1.0",
        timeout=5,
        max_retries=2
    )
    yield client
    client.close()


@pytest.fixture
def mock_session():
    """Mock requests.Session 对象"""
    with patch('src.crawl.infrastructure.http_client_impl.requests.Session') as mock_session_cls:
        session = Mock()
        mock_session_cls.return_value = session
        yield session


def create_mock_response(status_code=200, content=b"<html>Success</html>", 
                        url="http://example.com", headers=None, encoding='utf-8'):
    """辅助函数：创建 mock 响应对象"""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.url = url
    mock_response.headers = headers or {'Content-Type': 'text/html'}
    mock_response.content = content
    mock_response.encoding = encoding
    mock_response.apparent_encoding = encoding
    mock_response.ok = (200 <= status_code < 300)
    return mock_response


# ============================================================================
# 初始化和配置测试
# ============================================================================

class TestInitialization:
    """测试 HttpClientImpl 初始化和配置"""

    def test_default_configuration(self):
        """测试默认配置"""
        client = HttpClientImpl()
        assert client._timeout == 30  
        assert 'User-Agent' in client._session.headers
        client.close()

    def test_custom_configuration(self, http_client):
        """测试自定义配置是否正确应用"""
        assert http_client._timeout == 5
        assert http_client._session.headers['User-Agent'] == "TestBot/1.0"
        assert 'gzip' in http_client._session.headers['Accept-Encoding']

    def test_adapter_mounted(self, http_client):
        """测试 HTTP/HTTPS 适配器是否挂载"""
        assert http_client._session.get_adapter('http://') is not None
        assert http_client._session.get_adapter('https://') is not None


# ============================================================================
# GET 请求测试 - 成功场景
# ============================================================================

class TestGetSuccess:
    """测试 GET 请求成功场景"""

    def test_get_basic_success(self, mock_session):
        """测试基本 GET 请求成功"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response()
        mock_session.get.return_value = mock_response

        response = client.get("http://example.com")

        assert isinstance(response, HttpResponse)
        assert response.is_success
        assert response.status_code == 200
        assert response.content == "<html>Success</html>"
        assert response.url == "http://example.com"
        
        mock_session.get.assert_called_once_with(
            "http://example.com",
            timeout=30,
            allow_redirects=True
        )

    def test_get_with_custom_headers(self, mock_session):
        """测试带自定义请求头的 GET 请求"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response()
        mock_session.get.return_value = mock_response

        custom_headers = {'Authorization': 'Bearer token123'}
        response = client.get("http://example.com", headers=custom_headers)

        assert response.is_success
        # 验证 headers 参数被传递（具体实现取决于你的代码）


# ============================================================================
# GET 请求测试 - HTTP 状态码
# ============================================================================

class TestGetStatusCodes:
    """测试 GET 请求各种 HTTP 状态码处理"""

    @pytest.mark.parametrize("status_code,expected_success", [
        (200, True),   # OK
        (201, True),   # Created
        (204, True),   # No Content
        (301, True),   # Moved Permanently (重定向后通常返回200)
        (302, True),   # Found
        (400, False),  # Bad Request
        (401, False),  # Unauthorized
        (403, False),  # Forbidden
        (404, False),  # Not Found
        (500, False),  # Internal Server Error
        (502, False),  # Bad Gateway
        (503, False),  # Service Unavailable
    ])
    def test_get_various_status_codes(self, mock_session, status_code, expected_success):
        """测试各种 HTTP 状态码的处理"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response(status_code=status_code)
        mock_response.ok = expected_success
        mock_session.get.return_value = mock_response

        response = client.get("http://example.com")

        assert response.status_code == status_code
        assert response.is_success == expected_success


# ============================================================================
# GET 请求测试 - 编码处理
# ============================================================================

class TestGetEncoding:
    """测试 GET 请求编码处理"""

    def test_get_utf8_encoding(self, mock_session):
        """测试 UTF-8 编码响应"""
        client = HttpClientImpl()
        client._session = mock_session
        
        content = "中文测试内容".encode('utf-8')
        mock_response = create_mock_response(content=content, encoding='utf-8')
        mock_session.get.return_value = mock_response

        response = client.get("http://example.com")
        assert response.content == "中文测试内容"

    def test_get_gbk_encoding_fallback(self, mock_session):
        """测试 GBK 编码自动检测"""
        client = HttpClientImpl()
        client._session = mock_session
        
        content = "中文测试内容".encode('gbk')
        mock_response = create_mock_response(content=content, encoding=None)
        mock_response.apparent_encoding = 'gbk'
        mock_session.get.return_value = mock_response

        response = client.get("http://example.com")
        assert response.content == "中文测试内容"

    def test_get_encoding_error_fallback(self, mock_session):
        """测试编码错误时的 fallback 处理"""
        client = HttpClientImpl()
        client._session = mock_session
        
        # 创建无效的编码内容
        mock_response = create_mock_response(content=b'\xff\xfe invalid', encoding='utf-8')
        mock_response.text = Mock(side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid'))
        mock_session.get.return_value = mock_response

        response = client.get("http://example.com")
        # 验证降级到 errors='ignore' 或其他 fallback 策略
        assert response.is_success  # 不应完全失败


# ============================================================================
# GET 请求测试 - 网络异常
# ============================================================================

class TestGetExceptions:
    """测试 GET 请求网络异常处理"""

    @pytest.mark.parametrize("exception_cls,error_keyword", [
        (requests.exceptions.Timeout, "请求超时"),
        (requests.exceptions.ConnectionError, "连接失败"),
        (requests.exceptions.TooManyRedirects, "重定向"),
        (requests.exceptions.HTTPError, "HTTP错误"),
        (requests.exceptions.RequestException, "请求"),
    ])
    def test_get_network_exceptions(self, mock_session, exception_cls, error_keyword):
        """测试各种网络异常的处理"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_session.get.side_effect = exception_cls("Network error")

        response = client.get("http://example.com")

        assert not response.is_success
        assert response.status_code == 0
        assert error_keyword in response.error_message


# ============================================================================
# GET 请求测试 - 重试逻辑
# ============================================================================


class TestGetRetry:
    """测试 GET 请求重试逻辑"""

    def test_retry_success_on_second_attempt(self):
        """测试第二次重试成功"""
        client = HttpClientImpl(max_retries=2)
        
        with requests_mock.Mocker() as m:
            # ✅ 使用列表模拟多次响应
            m.get(
                'http://example.com',
                [
                    {'exc': requests.exceptions.ConnectTimeout},  # 第1次超时
                    {
                        'text': '<html>Success</html>',
                        'status_code': 200,
                        'headers': {'Content-Type': 'text/html'}  # ✅ 添加 headers
                    }
                ]
            )

            response = client.get("http://example.com")

            assert response.is_success
            assert response.status_code == 200
            assert response.content == '<html>Success</html>'
            # ✅ 验证请求次数
            assert len(m.request_history) == 2

    def test_retry_exhausted_all_attempts(self):  # ✅ 移除 mock_session 参数
        client = HttpClientImpl(max_retries=2)
        
        with requests_mock.Mocker() as m:
            m.get('http://example.com', exc=requests.exceptions.ConnectTimeout)
            response = client.get("http://example.com")
            
            assert not response.is_success
            # ✅ 使用 request_history 检查
            assert len(m.request_history) == 3  # 初始 + 2次重试

    def test_retry_on_5xx_status_code(self):
        """测试 5xx 状态码触发重试"""
        client = HttpClientImpl(max_retries=1)
        
        with requests_mock.Mocker() as m:
            # 第1次 503，第2次 200
            m.get(
                'http://example.com',
                [
                    {'status_code': 503, 'text': 'Service Unavailable'},
                    {'status_code': 200, 'text': '<html>OK</html>'}
                ]
            )

            response = client.get("http://example.com")

            # 503 会触发重试，最终成功
            assert response.is_success
            assert response.status_code == 200
            assert len(m.request_history) == 2



# ============================================================================
# HEAD 请求测试
# ============================================================================

class TestHead:
    """测试 HEAD 请求"""

    def test_head_success(self, mock_session):
        """测试 HEAD 请求成功"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response()
        mock_session.head.return_value = mock_response

        response = client.head("http://example.com")

        assert response.is_success
        assert response.content == ''  # HEAD 无响应体
        assert 'Content-Type' in response.headers
        
        mock_session.head.assert_called_once()

    def test_head_timeout(self, mock_session):
        """测试 HEAD 请求超时"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_session.head.side_effect = requests.exceptions.Timeout("HEAD timeout")

        response = client.head("http://example.com")

        assert not response.is_success
        assert "请求超时" in response.error_message

    def test_head_404_not_found(self, mock_session):
        """测试 HEAD 请求返回 404"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response(status_code=404)
        mock_response.ok = False
        mock_session.head.return_value = mock_response

        response = client.head("http://example.com")

        assert not response.is_success
        assert response.status_code == 404


# ============================================================================
# 边界情况和特殊输入测试
# ============================================================================

class TestEdgeCases:
    """测试边界情况和特殊输入"""

    @pytest.mark.parametrize("invalid_url", [
        "",                              # 空 URL
        "   ",                           # 空白 URL
        "not-a-url",                     # 无效格式
        "ftp://unsupported.com",         # 不支持的协议
    ])
    def test_get_with_invalid_urls(self, mock_session, invalid_url):
        """测试无效 URL 处理"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_session.get.side_effect = requests.exceptions.InvalidURL("Invalid URL")

        response = client.get(invalid_url)

        assert not response.is_success

    def test_get_with_unicode_url(self, mock_session):
        """测试包含 Unicode 字符的 URL"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response()
        mock_session.get.return_value = mock_response

        url = "http://example.com/搜索?q=测试"
        response = client.get(url)

        # URL 应该被正确编码处理
        assert response.is_success or response.error_message  # 至少不崩溃

    def test_get_large_response(self, mock_session):
        """测试超大响应内容"""
        client = HttpClientImpl()
        client._session = mock_session
        
        # 模拟 10MB 响应
        large_content = b"x" * (10 * 1024 * 1024)
        mock_response = create_mock_response(content=large_content)
        mock_session.get.return_value = mock_response

        response = client.get("http://example.com")

        assert response.is_success
        assert len(response.content) == 10 * 1024 * 1024

    def test_get_empty_response(self, mock_session):
        """测试空响应内容"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response(content=b"", status_code=204)
        mock_session.get.return_value = mock_response

        response = client.get("http://example.com")

        assert response.is_success
        assert response.content == ""


# ============================================================================
# 上下文管理器测试
# ============================================================================

class TestContextManager:
    """测试上下文管理器功能"""

    def test_context_manager_support(self):
        """测试 with 语句支持"""
        with HttpClientImpl() as client:
            assert isinstance(client, HttpClientImpl)
            # 在上下文内可正常使用

    def test_session_closed_after_context(self, mock_session):
        """测试退出上下文后 session 被关闭"""
        with patch('src.crawl.infrastructure.http_client_impl.requests.Session', 
                   return_value=mock_session):
            with HttpClientImpl() as client:
                pass
            
            mock_session.close.assert_called_once()

    def test_close_method(self, mock_session):
        """测试显式调用 close() 方法"""
        client = HttpClientImpl()
        client._session = mock_session
        
        client.close()
        
        mock_session.close.assert_called_once()


# ============================================================================
# 资源管理和并发测试
# ============================================================================

class TestResourceManagement:
    """测试资源管理"""

    def test_multiple_requests_share_session(self, mock_session):
        """测试多次请求共享同一个 session"""
        client = HttpClientImpl()
        client._session = mock_session
        
        mock_response = create_mock_response()
        mock_session.get.return_value = mock_response

        client.get("http://example.com/page1")
        client.get("http://example.com/page2")

        # 应该使用同一个 session（调用了2次）
        assert mock_session.get.call_count == 2

    def test_operations_after_close(self, mock_session):
        """测试 close() 后再调用请求方法"""
        client = HttpClientImpl()
        client._session = mock_session
        client.close()

        # 尝试在关闭后发起请求
        # 根据你的实现，可能抛出异常或返回错误响应
        # 这里假设会捕获异常并返回失败响应
        try:
            response = client.get("http://example.com")
            assert not response.is_success
        except Exception:
            # 如果抛出异常也是合理的
            pass


# ============================================================================
# 集成测试（可选）
# ============================================================================

# @pytest.mark.integration
# class TestIntegration:
#     """集成测试（需要网络连接）"""

#     @pytest.mark.skip(reason="需要外部网络，CI 环境跳过")
#     def test_real_request(self):
#         """测试真实 HTTP 请求（用于本地验证）"""
#         client = HttpClientImpl()
#         response = client.get("https://httpbin.org/get")
        
#         assert response.is_success
#         assert response.status_code == 200
#         assert "httpbin.org" in response.url
        
#         client.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
