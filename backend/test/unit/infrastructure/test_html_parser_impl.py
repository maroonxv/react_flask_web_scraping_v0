import pytest
import sys
import os
from unittest.mock import Mock, patch

# 将 backend 目录添加到系统路径，以便导入 src 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.crawl.infrastructure.html_parser_impl import HtmlParserImpl

class TestHtmlParserImpl:
    """
    HtmlParserImpl 的单元测试类
    
    测试目标：
    - 验证 HTML 链接提取功能的正确性（包括绝对路径转换、去重、无效链接过滤）。
    - 验证 Meta 标签提取功能（包括标准 Meta、OpenGraph、Title、Charset）。
    - 验证文本内容提取功能（包括脚本/样式去除、空白标准化）。
    - 验证 URL 标准化逻辑。
    - 验证异常处理机制。
    """

    @pytest.fixture
    def parser(self):
        """pytest fixture: 创建 HtmlParserImpl 实例供测试使用"""
        return HtmlParserImpl()

    def test_extract_links_valid(self, parser):
        """
        测试提取有效链接
        - 验证相对路径是否正确转换为绝对路径
        - 验证 http/https 协议是否被保留
        """
        html = """
        <html>
            <body>
                <a href="/page1">Page 1</a>
                <a href="http://example.com/page2">Page 2</a>
                <a href="page3">Page 3</a>
            </body>
        </html>
        """
        base_url = "http://example.com"
        links = parser.extract_links(html, base_url)
        
        expected = {
            "http://example.com/page1",
            "http://example.com/page2",
            "http://example.com/page3"
        }
        # 使用 set 比较，忽略顺序
        assert set(links) == expected

    def test_extract_links_deduplication(self, parser):
        """
        测试链接去重功能
        - 验证相同的链接是否只返回一次
        """
        html = """
        <html>
            <body>
                <a href="/page1">Link 1</a>
                <a href="/page1">Link 1 Again</a>
            </body>
        </html>
        """
        base_url = "http://example.com"
        links = parser.extract_links(html, base_url)
        assert len(links) == 1
        assert links[0] == "http://example.com/page1"

    def test_extract_links_ignore_invalid_schemes(self, parser):
        """
        测试忽略无效协议
        - 验证 mailto, tel, javascript, 空链接, 锚点链接 是否被过滤
        """
        html = """
        <html>
            <body>
                <a href="mailto:user@example.com">Email</a>
                <a href="tel:123456">Phone</a>
                <a href="javascript:void(0)">JS</a>
                <a href="#">Anchor</a>
                <a href="">Empty</a>
            </body>
        </html>
        """
        base_url = "http://example.com"
        links = parser.extract_links(html, base_url)
        assert len(links) == 0

    def test_extract_links_empty_input(self, parser):
        """
        测试空输入处理
        - 验证 HTML 为空或 Base URL 为空时返回空列表
        """
        assert parser.extract_links("", "http://example.com") == []
        assert parser.extract_links("<html></html>", "") == []
        assert parser.extract_links(None, "http://example.com") == []

    def test_extract_links_exception(self, parser):
        """
        测试异常处理
        - 模拟 BeautifulSoup 解析抛出异常，验证方法是否安全返回空列表而不崩溃
        """
        with patch('src.crawl.infrastructure.html_parser_impl.BeautifulSoup') as mock_bs:
            mock_bs.side_effect = Exception("Parsing error")
            links = parser.extract_links("<html></html>", "http://example.com")
            assert links == []

    def test_extract_meta_tags(self, parser):
        """
        测试 Meta 标签提取
        - 验证 title, charset, standard meta, og meta 是否正确提取
        """
        html = """
        <html>
            <head>
                <title>Test Page</title>
                <meta charset="utf-8">
                <meta name="description" content="A test page">
                <meta name="keywords" content="test, parser">
                <meta property="og:title" content="Open Graph Title">
                <meta property="og:image" content="http://example.com/image.jpg">
                <meta name="empty" content="">
                <meta name="" content="no name">
            </head>
        </html>
        """
        meta = parser.extract_meta_tags(html)
        
        assert meta['title'] == "Test Page"
        assert meta['charset'] == "utf-8"
        assert meta['description'] == "A test page"
        assert meta['keywords'] == "test, parser"
        assert meta['og:title'] == "Open Graph Title"
        assert meta['og:image'] == "http://example.com/image.jpg"
        # 验证空 name 或空 content 的标签被忽略
        assert 'empty' not in meta
        assert 'no name' not in meta

    def test_extract_meta_tags_empty(self, parser):
        """测试 Meta 提取的空输入处理"""
        assert parser.extract_meta_tags("") == {}
        assert parser.extract_meta_tags(None) == {}

    def test_extract_meta_tags_exception(self, parser):
        """测试 Meta 提取的异常处理"""
        with patch('src.crawl.infrastructure.html_parser_impl.BeautifulSoup') as mock_bs:
            mock_bs.side_effect = Exception("Parsing error")
            assert parser.extract_meta_tags("<html></html>") == {}

    def test_extract_text_content(self, parser):
        """
        测试纯文本内容提取
        - 验证 script/style 标签内容是否被移除
        - 验证多余空白字符是否被标准化为一个空格
        """
        html = """
        <html>
            <head>
                <style>body { color: red; }</style>
                <script>console.log('test');</script>
            </head>
            <body>
                <h1>Hello World</h1>
                <p>This is a   test.</p>
                <div>
                    <span>Nested content</span>
                </div>
            </body>
        </html>
        """
        text = parser.extract_text_content(html)
        
        # 验证 script 和 style 内容已被移除
        assert "body { color: red; }" not in text
        assert "console.log" not in text
        # 验证文本内容及空白处理
        assert "Hello World This is a test. Nested content" == text

    def test_extract_text_content_empty(self, parser):
        """测试文本提取的空输入处理"""
        assert parser.extract_text_content("") == ""
        assert parser.extract_text_content(None) == ""

    def test_extract_text_content_exception(self, parser):
        """测试文本提取的异常处理"""
        with patch('src.crawl.infrastructure.html_parser_impl.BeautifulSoup') as mock_bs:
            mock_bs.side_effect = Exception("Parsing error")
            assert parser.extract_text_content("<html></html>") == ""

    def test_normalize_url(self, parser):
        """
        测试 URL 标准化私有方法
        - 验证端口去除、协议小写、Fragment 去除
        """
        # 注意：直接测试私有方法在 Python 中是允许的，有助于验证核心逻辑
        assert parser._normalize_url("http://example.com:80/path") == "http://example.com/path"
        # URL 路径和查询参数通常是大小写敏感的，因此不应强制转换为小写
        assert parser._normalize_url("HTTPS://EXAMPLE.COM/PATH?Q=1#fragment") == "https://example.com/PATH?Q=1"
        # 验证不支持的协议返回空字符串
        assert parser._normalize_url("ftp://example.com") == ""

    def test_extract_links_with_text(self, parser):
        """
        测试带锚文本的链接提取
        - 验证返回结构包含 url 和 text
        - 验证锚文本去除了空白
        """
        html = """
        <html>
            <body>
                <a href="/page1">Link 1</a>
                <a href="http://example.com/page2">   Link 2   </a>
            </body>
        </html>
        """
        base_url = "http://example.com"
        results = parser.extract_links_with_text(html, base_url)
        
        assert len(results) == 2
        
        # find_all 通常按文档顺序返回
        assert results[0]['url'] == "http://example.com/page1"
        assert results[0]['text'] == "Link 1"
        
        assert results[1]['url'] == "http://example.com/page2"
        assert results[1]['text'] == "Link 2"

    def test_extract_links_with_text_exception(self, parser):
        """测试带锚文本链接提取的异常处理"""
        with patch('src.crawl.infrastructure.html_parser_impl.BeautifulSoup') as mock_bs:
            mock_bs.side_effect = Exception("Parsing error")
            assert parser.extract_links_with_text("<html></html>", "http://a.com") == []

if __name__ == '__main__':
    pytest.main()
