import pytest
import os
import sys
from pathlib import Path

# 添加 backend 目录到 path 以便导入模块
backend_dir = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(backend_dir))

from src.crawl.infrastructure.http_client_impl import HttpClientImpl
from src.crawl.infrastructure.binary_http_client_impl import BinaryHttpClientImpl
from src.crawl.domain.value_objects.http_response import HttpResponse
from src.crawl.domain.value_objects.binary_response import BinaryResponse

# 目标 URL，已知存在 SSL 问题
TARGET_URL = "https://panel.fii-foxconn.com//static/upload/2025/08/11/202508112171.pdf"

class TestSslVerification:
    """
    集成测试：验证 HTTP 客户端在处理 SSL 证书问题网站时的行为
    不使用 Mock，直接请求真实网络
    """
    
    def setup_method(self):
        self.http_client = HttpClientImpl(timeout=10, max_retries=1)
        self.binary_client = BinaryHttpClientImpl(max_retries=1)

    def teardown_method(self):
        if hasattr(self, 'http_client'):
            self.http_client.close()
        if hasattr(self, 'binary_client'):
            self.binary_client.close()

    def test_http_client_get_ssl_site(self):
        """测试 HttpClientImpl.get() 请求 SSL 问题网站"""
        # Act
        response = self.http_client.get(TARGET_URL)
        
        # Assert
        # 验证请求没有因为 SSL 错误抛出异常，且返回了内容
        # 注意：虽然是 PDF，但 HttpClientImpl 也可以请求，只是内容是二进制乱码
        print(f"HttpClient Status: {response.status_code}")
        print(f"HttpClient Error: {response.error_message}")
        
        assert response.is_success is True, f"请求失败: {response.error_message}"
        assert response.status_code == 200
        assert len(response.content) > 0

    def test_binary_client_get_ssl_site(self):
        """测试 BinaryHttpClientImpl.get_binary() 请求 SSL 问题网站"""
        # Act
        response = self.binary_client.get_binary(TARGET_URL)
        
        # Assert
        print(f"BinaryClient Status: {response.status_code}")
        print(f"BinaryClient Error: {response.error_message}")
        
        assert response.is_success is True, f"二进制下载失败: {response.error_message}"
        assert response.status_code == 200
        assert len(response.content) > 0
        assert b"%PDF" in response.content[:1024], "响应内容看起来不是 PDF"

if __name__ == "__main__":
    # 允许直接运行此脚本
    pytest.main(["-v", __file__])
