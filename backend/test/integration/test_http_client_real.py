"""
HttpClientImpl 的真实网络集成测试
测试策略：
1. 使用 httpbin.org 作为测试目标，验证真实的 HTTP 请求/响应行为
2. 覆盖 GET、HEAD、状态码处理、重定向、超时、编码处理等真实场景
3. 依赖外部网络，因此标记为 slow 或 integration
"""

import pytest
import sys
import os

# 添加 backend 目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.crawl.infrastructure.http_client_impl import HttpClientImpl
from src.crawl.domain.value_objects.http_response import HttpResponse

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def http_client():
    """
    创建一个共享的 HttpClientImpl 实例
    scope="module" 表示在整个模块测试期间只创建一次，提高效率
    """
    client = HttpClientImpl(
        user_agent="TraeTestBot/1.0",
        timeout=10,  # 真实网络请求需要更长的超时时间
        max_retries=3
    )
    yield client
    client.close()

# ============================================================================
# 基础 GET 请求测试
# ============================================================================

class TestRealGetRequests:
    """测试真实的 GET 请求"""

    def test_get_httpbin_ip(self, http_client):
        """测试简单的 GET 请求 (httpbin.org/ip)"""
        url = "http://httpbin.org/ip"
        response = http_client.get(url)

        assert response.is_success
        assert response.status_code == 200
        assert "origin" in response.content
        assert response.url == url

    def test_get_https_support(self, http_client):
        """测试 HTTPS 支持"""
        url = "https://httpbin.org/get"
        response = http_client.get(url)

        assert response.is_success
        assert response.status_code == 200

    def test_user_agent_header(self, http_client):
        """验证 User-Agent 是否正确发送"""
        url = "http://httpbin.org/user-agent"
        response = http_client.get(url)

        assert response.is_success
        assert "TraeTestBot/1.0" in response.content

    def test_custom_headers(self, http_client):
        """测试自定义 Header 发送"""
        url = "http://httpbin.org/headers"
        custom_headers = {"X-Custom-Header": "TraeIntegrationTest"}
        response = http_client.get(url, headers=custom_headers)

        assert response.is_success
        assert "TraeIntegrationTest" in response.content

    def test_get_hacker_news(self, http_client):
        """测试访问 Hacker News"""
        url = "https://news.ycombinator.com/"
        response = http_client.get(url)

        assert response.is_success
        assert response.status_code == 200
        assert "Hacker News" in response.content

# ============================================================================
# 状态码与错误处理测试
# ============================================================================

class TestRealStatusCodes:
    """测试各种 HTTP 状态码的真实处理"""

    def test_404_not_found(self, http_client):
        """测试 404 页面"""
        url = "http://httpbin.org/status/404"
        response = http_client.get(url)

        assert not response.is_success
        assert response.status_code == 404

    def test_500_server_error(self, http_client):
        """测试 500 服务器错误"""
        url = "http://httpbin.org/status/500"
        response = http_client.get(url)

        assert not response.is_success
        assert response.status_code == 500

    def test_redirects(self, http_client):
        """测试重定向 (默认为自动跟随)"""
        # httpbin 会重定向到 /get
        url = "http://httpbin.org/redirect-to?url=/get"
        response = http_client.get(url)

        assert response.is_success
        assert response.status_code == 200
        # 最终 URL 应该是重定向后的
        assert response.url.endswith("/get")

# ============================================================================
# HEAD 请求测试
# ============================================================================

class TestRealHeadRequests:
    """测试真实的 HEAD 请求"""

    def test_head_request(self, http_client):
        """测试 HEAD 请求"""
        url = "http://httpbin.org/get"
        response = http_client.head(url)

        assert response.is_success
        assert response.status_code == 200
        assert response.content == ""  # HEAD 请求不应有内容
        assert "Content-Type" in response.headers

# ============================================================================
# 编码与内容测试
# ============================================================================

class TestRealEncoding:
    """测试真实内容的编码处理"""

    def test_utf8_content(self, http_client):
        """测试 UTF-8 编码内容"""
        url = "http://httpbin.org/encoding/utf8"
        response = http_client.get(url)

        assert response.is_success
        # 验证能正确解析其中的特殊字符
        assert "∮" in response.content  # 包含在示例内容中的字符

# ============================================================================
# 异常与超时测试
# ============================================================================

class TestRealExceptions:
    """测试真实网络异常 (需要谨慎选择目标)"""

    def test_connection_timeout(self):
        """
        测试连接超时
        使用一个不可达的 IP (10.255.255.1 是保留地址，通常不可达)
        并设置极短的超时时间
        """
        # 创建一个专门用于测试超时的客户端
        client = HttpClientImpl(timeout=1, max_retries=0)
        
        # 尝试连接一个通常会丢包或无响应的地址
        # 注意：这取决于网络环境，有时会立即返回 "网络不可达"
        try:
            response = client.get("http://10.255.255.1")
            assert not response.is_success
            assert "超时" in response.error_message or "连接" in response.error_message
        finally:
            client.close()

    def test_invalid_domain(self, http_client):
        """测试无效域名"""
        url = "http://this-domain-definitely-does-not-exist.com"
        response = http_client.get(url)

        assert not response.is_success
        # 通常是 ConnectionError (0)，但在某些网络环境下（如代理）可能返回 502/503/504
        assert response.status_code in [0, 502, 503, 504]
        assert response.error_message

# ============================================================================
# 性能与大数据测试
# ============================================================================

class TestRealPerformance:
    """测试稍大数据的传输"""
    
    def test_download_image(self, http_client):
        """测试下载二进制数据 (图片)"""
        url = "http://httpbin.org/image/png"
        response = http_client.get(url)

        assert response.is_success
        assert response.status_code == 200
        assert len(response.content) > 0
        # 验证 Content-Type
        assert "image/png" in response.headers.get("Content-Type", "")
