import pytest
from unittest.mock import Mock, MagicMock
from src.crawl.infrastructure.crawl_domain_service_impl import CrawlDomainServiceImpl

class TestCrawlDomainServiceImpl:
    @pytest.fixture
    def mock_http_client(self):
        return Mock()

    @pytest.fixture
    def mock_html_parser(self):
        return Mock()

    @pytest.fixture
    def mock_robots_parser(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_http_client, mock_html_parser, mock_robots_parser):
        return CrawlDomainServiceImpl(
            http_client=mock_http_client,
            html_parser=mock_html_parser,
            robots_parser=mock_robots_parser
        )

    def test_get_domain_crawl_delay_returns_value(self, service, mock_robots_parser):
        """测试正常获取延迟"""
        url = "http://example.com/page1"
        expected_delay = 5.0
        
        # 模拟 robots parser 返回延迟
        mock_robots_parser.get_crawl_delay.return_value = expected_delay
        
        delay = service.get_domain_crawl_delay(url)
        
        assert delay == expected_delay
        # 验证调用参数：应该是域名部分
        mock_robots_parser.get_crawl_delay.assert_called_with("http://example.com", "WebCrawler/1.0")

    def test_get_domain_crawl_delay_returns_none(self, service, mock_robots_parser):
        """测试没有延迟限制时返回 None"""
        url = "http://example.com/page1"
        
        mock_robots_parser.get_crawl_delay.return_value = None
        
        delay = service.get_domain_crawl_delay(url)
        
        assert delay is None

    def test_get_domain_crawl_delay_handles_exception(self, service, mock_robots_parser):
        """测试发生异常时返回 None"""
        url = "http://example.com/page1"
        
        # 模拟抛出异常
        mock_robots_parser.get_crawl_delay.side_effect = Exception("Parsing Error")
        
        delay = service.get_domain_crawl_delay(url)
        
        assert delay is None

    def test_get_domain_crawl_delay_handles_invalid_url(self, service):
        """测试无效 URL 返回 None"""
        url = "not_a_valid_url"
        
        # 不需要 mock robots，因为 urlparse 可能会直接失败或者产生奇怪的结果
        # 如果 urlparse 不报错，get_crawl_delay 内部逻辑会继续
        # 这里主要测试代码健壮性
        
        delay = service.get_domain_crawl_delay(url)
        
        assert delay is None
