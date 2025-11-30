"""
RobotsTxtParserImpl 的 pytest 测试套件
覆盖：初始化、is_allowed、crawl_delay、缓存管理、异常处理、边界情况
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from urllib.robotparser import RobotFileParser
import sys
import os

# 添加 backend 目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.crawl.infrastructure.robots_txt_parser_impl import RobotsTxtParserImpl


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def parser():
    """创建 RobotsTxtParserImpl 实例"""
    return RobotsTxtParserImpl(cache_timeout=3600)


@pytest.fixture
def mock_robot_parser():
    """创建 mock RobotFileParser"""
    mock = Mock(spec=RobotFileParser)
    mock.can_fetch = Mock(return_value=True)
    mock.crawl_delay = Mock(return_value=None)
    return mock


def create_robots_txt_content(rules: list) -> list:
    """
    辅助函数：创建 robots.txt 内容
    
    参数:
        rules: 规则列表，例如 ['User-agent: *', 'Disallow: /admin/']
    返回:
        适用于 RobotFileParser.parse() 的列表
    """
    return rules


# ============================================================================
# 初始化测试
# ============================================================================

class TestInitialization:
    """测试初始化"""

    def test_default_cache_timeout(self):
        """测试默认缓存超时"""
        parser = RobotsTxtParserImpl()
        # 默认值应该是某个合理的数值（根据你的实现可能需要调整）
        assert hasattr(parser, '_cache_timeout')

    def test_custom_cache_timeout(self):
        """测试自定义缓存超时"""
        parser = RobotsTxtParserImpl(cache_timeout=7200)
        assert parser._cache_timeout == 7200

    def test_cache_initialized_empty(self, parser):
        """测试缓存初始为空"""
        assert len(parser._cache) == 0


# ============================================================================
# is_allowed 测试 - 基本功能
# ============================================================================

class TestIsAllowedBasic:
    """测试 is_allowed 基本功能"""

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_allowed_url(self, mock_parser_cls, parser):
        """测试允许访问的 URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser.crawl_delay.return_value = None
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/page', 'TestBot')

        assert result is True
        mock_parser.can_fetch.assert_called_once_with('TestBot', 'http://example.com/page')

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_disallowed_url(self, mock_parser_cls, parser):
        """测试禁止访问的 URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = False
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/admin', 'TestBot')

        assert result is False

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_https_url(self, mock_parser_cls, parser):
        """测试 HTTPS URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('https://secure.example.com/page', 'TestBot')

        assert result is True
        # 验证使用了正确的域名
        mock_parser.set_url.assert_called()

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_url_with_port(self, mock_parser_cls, parser):
        """测试带端口的 URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com:8080/page', 'TestBot')

        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_url_with_query_params(self, mock_parser_cls, parser):
        """测试带查询参数的 URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/search?q=test', 'TestBot')

        assert result is True


# ============================================================================
# is_allowed 测试 - User-Agent 处理
# ============================================================================

class TestIsAllowedUserAgent:
    """测试不同 User-Agent 的处理"""

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_specific_user_agent(self, mock_parser_cls, parser):
        """测试特定 User-Agent"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/', 'Googlebot')

        assert result is True
        mock_parser.can_fetch.assert_called_with('Googlebot', 'http://example.com/')

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_wildcard_user_agent(self, mock_parser_cls, parser):
        """测试通配符 User-Agent"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/', '*')

        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_different_user_agents_different_rules(self, mock_parser_cls, parser):
        """测试不同 User-Agent 可能有不同规则"""
        mock_parser = Mock()
        # 模拟不同 user-agent 返回不同结果
        mock_parser.can_fetch.side_effect = lambda ua, url: ua != 'BadBot'
        mock_parser_cls.return_value = mock_parser

        assert parser.is_allowed('http://example.com/admin', 'GoodBot') is True
        assert parser.is_allowed('http://example.com/admin', 'BadBot') is False


# ============================================================================
# is_allowed 测试 - 异常处理
# ============================================================================

class TestIsAllowedExceptions:
    """测试 is_allowed 异常处理"""

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_robots_txt_fetch_failure_defaults_allow(self, mock_parser_cls, parser):
        """测试 robots.txt 获取失败时默认允许"""
        mock_parser = Mock()
        mock_parser.read.side_effect = Exception("Network error")
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        # 应该降级到默认允许
        result = parser.is_allowed('http://example.com/page', 'TestBot')

        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_invalid_url_defaults_allow(self, mock_parser_cls, parser):
        """测试无效 URL 时默认允许"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('not-a-valid-url', 'TestBot')

        # 解析失败应该默认允许
        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_empty_url_defaults_allow(self, mock_parser_cls, parser):
        """测试空 URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('', 'TestBot')

        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_can_fetch_raises_exception(self, mock_parser_cls, parser):
        """测试 can_fetch 抛出异常时的处理"""
        mock_parser = Mock()
        mock_parser.can_fetch.side_effect = Exception("Parser error")
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/page', 'TestBot')

        # 异常应该被捕获，默认允许
        assert result is True


# ============================================================================
# get_crawl_delay 测试
# ============================================================================

class TestGetCrawlDelay:
    """测试 get_crawl_delay 功能"""

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_crawl_delay_specified(self, mock_parser_cls, parser):
        """测试有 Crawl-delay 指令"""
        mock_parser = Mock()
        mock_parser.crawl_delay.return_value = 5
        mock_parser_cls.return_value = mock_parser

        delay = parser.get_crawl_delay('http://example.com', 'TestBot')

        assert delay == 5.0
        mock_parser.crawl_delay.assert_called_once_with('TestBot')

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_crawl_delay_not_specified(self, mock_parser_cls, parser):
        """测试无 Crawl-delay 指令"""
        mock_parser = Mock()
        mock_parser.crawl_delay.return_value = None
        mock_parser_cls.return_value = mock_parser

        delay = parser.get_crawl_delay('http://example.com', 'TestBot')

        assert delay is None

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_crawl_delay_float_value(self, mock_parser_cls, parser):
        """测试浮点数延迟"""
        mock_parser = Mock()
        mock_parser.crawl_delay.return_value = 1.5
        mock_parser_cls.return_value = mock_parser

        delay = parser.get_crawl_delay('http://example.com', 'TestBot')

        assert delay == 1.5

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_crawl_delay_exception_returns_none(self, mock_parser_cls, parser):
        """测试获取延迟失败时返回 None"""
        mock_parser = Mock()
        mock_parser.crawl_delay.side_effect = Exception("Error")
        mock_parser_cls.return_value = mock_parser

        delay = parser.get_crawl_delay('http://example.com', 'TestBot')

        assert delay is None

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_crawl_delay_different_user_agents(self, mock_parser_cls, parser):
        """测试不同 User-Agent 可能有不同延迟"""
        mock_parser = Mock()
        # 模拟不同 user-agent 返回不同延迟
        mock_parser.crawl_delay.side_effect = lambda ua: 10 if ua == 'SlowBot' else 1
        mock_parser_cls.return_value = mock_parser

        delay1 = parser.get_crawl_delay('http://example.com', 'FastBot')
        delay2 = parser.get_crawl_delay('http://example.com', 'SlowBot')

        assert delay1 == 1.0
        assert delay2 == 10.0


# ============================================================================
# 缓存管理测试
# ============================================================================

class TestCacheManagement:
    """测试缓存机制"""

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_cache_stores_parser(self, mock_parser_cls, parser):
        """测试解析器被缓存"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        # 第一次访问
        parser.is_allowed('http://example.com/page1', 'TestBot')
        
        # 验证缓存中有该域名
        assert 'http://example.com' in parser._cache

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_cache_reused_for_same_domain(self, mock_parser_cls, parser):
        """测试同域名重用缓存"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        # 多次访问同一域名
        parser.is_allowed('http://example.com/page1', 'TestBot')
        parser.is_allowed('http://example.com/page2', 'TestBot')

        # RobotFileParser 应该只创建一次
        assert mock_parser_cls.call_count == 1
        # can_fetch 应该调用两次
        assert mock_parser.can_fetch.call_count == 2

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_different_domains_separate_cache(self, mock_parser_cls, parser):
        """测试不同域名使用不同缓存"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        parser.is_allowed('http://example1.com/page', 'TestBot')
        parser.is_allowed('http://example2.com/page', 'TestBot')

        # 应该为两个域名创建两个解析器
        assert mock_parser_cls.call_count == 2
        assert len(parser._cache) == 2

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_refresh_cache_removes_entry(self, mock_parser_cls, parser):
        """测试刷新缓存删除条目"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        # 先访问一次，建立缓存
        parser.is_allowed('http://example.com/page', 'TestBot')
        assert 'http://example.com' in parser._cache

        # 刷新缓存
        parser.refresh_cache('http://example.com')
        assert 'http://example.com' not in parser._cache

    def test_refresh_cache_nonexistent_domain(self, parser):
        """测试刷新不存在的缓存不报错"""
        # 不应该抛出异常
        parser.refresh_cache('http://nonexistent.com')

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_cache_refreshed_domain_refetches(self, mock_parser_cls, parser):
        """测试刷新后再次访问会重新获取"""
        mock_parser1 = Mock()
        mock_parser1.can_fetch.return_value = True
        
        mock_parser2 = Mock()
        mock_parser2.can_fetch.return_value = False
        
        mock_parser_cls.side_effect = [mock_parser1, mock_parser2]

        # 第一次访问
        result1 = parser.is_allowed('http://example.com/page', 'TestBot')
        assert result1 is True

        # 刷新缓存
        parser.refresh_cache('http://example.com')

        # 再次访问应该重新创建解析器
        result2 = parser.is_allowed('http://example.com/page', 'TestBot')
        
        # 验证创建了两次解析器
        assert mock_parser_cls.call_count == 2


# ============================================================================
# _get_parser 间接测试
# ============================================================================

class TestGetParser:
    """测试 _get_parser 方法（通过公共方法间接测试）"""

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_parser_sets_correct_robots_url(self, mock_parser_cls, parser):
        """测试解析器设置正确的 robots.txt URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        parser.is_allowed('http://example.com/page', 'TestBot')

        # 验证设置了正确的 robots.txt URL
        mock_parser.set_url.assert_called_once_with('http://example.com/robots.txt')

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_parser_reads_robots_txt(self, mock_parser_cls, parser):
        """测试解析器读取 robots.txt"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        parser.is_allowed('http://example.com/page', 'TestBot')

        # 验证调用了 read() 下载并解析
        mock_parser.read.assert_called_once()

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_parser_read_failure_creates_permissive_parser(self, mock_parser_cls, parser):
        """测试读取失败时创建允许所有访问的解析器"""
        mock_parser = Mock()
        mock_parser.read.side_effect = Exception("Network error")
        mock_parser_cls.return_value = mock_parser

        parser.is_allowed('http://example.com/page', 'TestBot')

        # 应该调用 parse([]) 创建空规则解析器
        mock_parser.parse.assert_called_once_with([])


# ============================================================================
# 边界情况和特殊场景
# ============================================================================

class TestEdgeCases:
    """测试边界情况"""

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_url_with_fragment(self, mock_parser_cls, parser):
        """测试带 fragment 的 URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/page#section', 'TestBot')

        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_url_with_unicode_characters(self, mock_parser_cls, parser):
        """测试包含 Unicode 字符的 URL"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('http://example.com/搜索', 'TestBot')

        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_relative_url_path(self, mock_parser_cls, parser):
        """测试相对路径（应该失败并默认允许）"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        result = parser.is_allowed('/relative/path', 'TestBot')

        # 相对路径无法解析域名，应该默认允许
        assert result is True

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_multiple_sequential_calls(self, mock_parser_cls, parser):
        """测试连续多次调用"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser.crawl_delay.return_value = 2
        mock_parser_cls.return_value = mock_parser

        # 混合调用不同方法
        assert parser.is_allowed('http://example.com/page1', 'TestBot') is True
        assert parser.get_crawl_delay('http://example.com', 'TestBot') == 2.0
        assert parser.is_allowed('http://example.com/page2', 'TestBot') is True

        # 应该只创建一次解析器
        assert mock_parser_cls.call_count == 1

    @patch('src.crawl.infrastructure.robots_txt_parser_impl.RobotFileParser')
    def test_concurrent_domain_access(self, mock_parser_cls, parser):
        """测试同时访问不同域名"""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_parser_cls.return_value = mock_parser

        domains = [
            'http://site1.com/page',
            'http://site2.com/page',
            'http://site3.com/page'
        ]

        for url in domains:
            parser.is_allowed(url, 'TestBot')

        # 应该为3个域名创建3个解析器
        assert mock_parser_cls.call_count == 3
        assert len(parser._cache) == 3


# ============================================================================
# 集成测试（可选）
# ============================================================================

# @pytest.mark.integration
# class TestIntegration:
#     """集成测试（需要网络连接）"""

#     @pytest.mark.skip(reason="需要外部网络，仅本地手动测试")
#     def test_real_robots_txt_google(self):
#         """测试真实的 Google robots.txt"""
#         parser = RobotsTxtParserImpl()
#         
#         # Google 的 robots.txt 通常禁止爬取某些路径
#         result = parser.is_allowed('https://www.google.com/search', 'TestBot')
#         
#         # 实际结果取决于 Google 的 robots.txt 规则
#         assert isinstance(result, bool)

#     @pytest.mark.skip(reason="需要外部网络，仅本地手动测试")
