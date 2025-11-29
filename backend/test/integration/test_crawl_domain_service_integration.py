"""
CrawlDomainServiceImpl 的集成测试
测试策略：
1. HtmlParserImpl 使用真实实例（无副作用，纯逻辑）
2. HttpClientImpl 使用 Mock（避免网络请求）
3. RobotsTxtParserImpl 使用 Mock（避免网络请求）
4. 验证各个组件在 CrawlDomainService 中的协作逻辑
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
import os
from datetime import datetime

# 添加 backend 目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.crawl.infrastructure.crawl_domain_service_impl import CrawlDomainServiceImpl
from src.crawl.infrastructure.html_parser_impl import HtmlParserImpl
from src.crawl.domain.entity.crawl_task import CrawlTask
from src.crawl.domain.value_objects.crawl_config import CrawlConfig
from src.crawl.domain.value_objects.page_metadata import PageMetadata

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_http_client():
    return Mock()

@pytest.fixture
def real_html_parser():
    return HtmlParserImpl()

@pytest.fixture
def mock_robots_parser():
    return Mock()

@pytest.fixture
def domain_service(mock_http_client, real_html_parser, mock_robots_parser):
    return CrawlDomainServiceImpl(
        http_client=mock_http_client,
        html_parser=real_html_parser,
        robots_parser=mock_robots_parser
    )

@pytest.fixture
def crawl_task():
    config = CrawlConfig(
        start_url="http://example.com",
        allow_domains=["example.com"],
        max_depth=3
    )
    task = CrawlTask(id="test_task_1", config=config)
    return task

# ============================================================================
# 测试 extract_page_metadata
# ============================================================================

class TestExtractPageMetadata:
    """测试元数据提取逻辑 Integration"""

    def test_metadata_priority_logic(self, domain_service):
        """测试标题提取的优先级：OG > Twitter > Title"""
        html = """
        <html>
            <head>
                <title>普通标题</title>
                <meta property="og:title" content="OG标题">
                <meta name="twitter:title" content="Twitter标题">
                <meta name="description" content="页面描述">
                <meta name="keywords" content="python,testing,crawl">
            </head>
            <body></body>
        </html>
        """
        metadata = domain_service.extract_page_metadata(html, "http://example.com")
        
        assert isinstance(metadata, PageMetadata)
        # 验证 OG 优先级最高
        assert metadata.title == "OG标题"
        assert metadata.abstract == "页面描述"
        assert metadata.keywords == ["python", "testing", "crawl"]

    def test_metadata_fallback_logic(self, domain_service):
        """测试标题提取的回退逻辑：没有 OG/Twitter 时使用 Title"""
        html = """
        <html>
            <head>
                <title>普通标题</title>
            </head>
            <body></body>
        </html>
        """
        metadata = domain_service.extract_page_metadata(html, "http://example.com")
        assert metadata.title == "普通标题"

    def test_date_parsing(self, domain_service):
        """测试日期解析逻辑"""
        html = """
        <html>
            <head>
                <meta property="article:published_time" content="2023-10-01T12:00:00+08:00">
            </head>
        </html>
        """
        metadata = domain_service.extract_page_metadata(html, "http://example.com")
        # 服务层应将其标准化为 YYYY-MM-DD
        assert metadata.publish_date == "2023-10-01"

    def test_date_parsing_failure(self, domain_service):
        """测试无效日期格式"""
        html = """
        <html>
            <head>
                <meta property="article:published_time" content="invalid-date">
            </head>
        </html>
        """
        metadata = domain_service.extract_page_metadata(html, "http://example.com")
        assert metadata.publish_date is None

# ============================================================================
# 测试 discover_crawlable_links
# ============================================================================

class TestDiscoverCrawlableLinks:
    """测试链接发现逻辑 Integration"""

    def test_filter_logic_integration(self, domain_service, mock_robots_parser, crawl_task):
        """
        集成测试链接发现的所有过滤规则：
        1. 解析 HTML 获取链接 (HtmlParserImpl)
        2. 域名白名单 (CrawlTask)
        3. 已访问去重 (CrawlTask)
        4. Robots.txt 规则 (RobotsTxtParser)
        """
        html = """
        <html>
            <body>
                <a href="/allowed/page1">允许页面1</a>
                <a href="http://example.com/allowed/page2">允许页面2</a>
                <a href="http://other-domain.com/page">外部域名(应过滤)</a>
                <a href="/visited/page">已访问页面(应过滤)</a>
                <a href="/robots/disallowed">Robots禁止(应过滤)</a>
            </body>
        </html>
        """
        base_url = "http://example.com"
        
        # 1. 设置任务状态
        # 标记一个页面为已访问
        crawl_task.mark_url_visited("http://example.com/visited/page")
        
        # 2. 设置 Robots 规则
        # 模拟 /robots/disallowed 禁止访问，其他允许
        def robots_check(url, user_agent):
            return "robots/disallowed" not in url
        mock_robots_parser.is_allowed.side_effect = robots_check

        # 执行发现
        links = domain_service.discover_crawlable_links(html, base_url, crawl_task)

        # 验证结果
        expected_links = [
            "http://example.com/allowed/page1",
            "http://example.com/allowed/page2"
        ]
        
        assert len(links) == 2
        for link in expected_links:
            assert link in links

        # 验证被过滤的链接不在结果中
        assert "http://other-domain.com/page" not in links # 域名过滤
        assert "http://example.com/visited/page" not in links # 访问记录过滤
        assert "http://example.com/robots/disallowed" not in links # Robots过滤

# ============================================================================
# 测试 identify_pdf_links
# ============================================================================

class TestIdentifyPdfLinks:
    """测试 PDF 识别逻辑 Integration"""

    def test_identify_by_extension(self, domain_service, mock_http_client):
        """测试通过扩展名识别 PDF (无需网络请求)"""
        links = [
            "http://example.com/doc.pdf",
            "http://example.com/doc.PDF",
            "http://example.com/image.png"
        ]
        
        # 配置 mock 返回非 PDF 类型，用于 image.png 的检查
        mock_response = Mock()
        mock_response.content_type = "image/png"
        mock_http_client.head.return_value = mock_response

        pdfs = domain_service.identify_pdf_links(links)
        
        assert "http://example.com/doc.pdf" in pdfs
        assert "http://example.com/doc.PDF" in pdfs
        assert "http://example.com/image.png" not in pdfs
        
        # 验证仅对非 pdf 后缀的链接发起了 HEAD 请求
        # 前两个链接因为后缀名匹配，直接被识别为 PDF，跳过了 HEAD 请求
        # 只有 image.png 走到了 HEAD 请求逻辑
        mock_http_client.head.assert_called_once_with("http://example.com/image.png")

    def test_identify_by_content_type(self, domain_service, mock_http_client):
        """测试通过 Content-Type 识别 PDF (需要 Mock HTTP)"""
        links = [
            "http://example.com/download?id=123",  # 可能是 PDF
            "http://example.com/page"              # 普通页面
        ]
        
        # 模拟 HTTP HEAD 响应
        def head_side_effect(url):
            response = Mock()
            if "id=123" in url:
                response.content_type = "application/pdf"
            else:
                response.content_type = "text/html"
            return response
            
        mock_http_client.head.side_effect = head_side_effect
        
        pdfs = domain_service.identify_pdf_links(links)
        
        assert "http://example.com/download?id=123" in pdfs
        assert "http://example.com/page" not in pdfs
        
        # 验证发起了 HEAD 请求
        assert mock_http_client.head.call_count == 2
