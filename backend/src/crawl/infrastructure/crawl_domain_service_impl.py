"""
模块职责（领域服务实现）
- 提供纯领域逻辑的实现：页面元信息提取、可爬取链接发现、PDF链接识别、日期解析；
- 将技术细节（HTML/HTTP/robots）通过需求接口抽象注入，确保领域逻辑独立可测试。

设计要点
- 优先级规则：标题按 OpenGraph > Twitter Card > 常规 meta > title 回退；
- 链接发现：委托解析器抽取所有链接后，应用域名白名单、去重、robots 过滤；
- PDF识别：扩展名快速判断 + HEAD 请求 Content-Type 二次确认；
- 日期解析：兼容常见格式，统一返回 "YYYY-MM-DD" 字符串，解析失败返回 None。
"""

from typing import List, Optional
from datetime import datetime
from urllib.parse import urlparse
from ..domain.domain_service.i_crawl_domain_service import ICrawlDomainService
from ..domain.demand_interface.i_http_client import IHttpClient
from ..domain.demand_interface.i_html_parser import IHtmlParser
from ..domain.demand_interface.i_robots_txt_parser import IRobotsTxtParser
from ..domain.value_objects.page_metadata import PageMetadata
from ..domain.entity.crawl_task import CrawlTask

class CrawlDomainServiceImpl(ICrawlDomainService):
    def __init__(
        self,
        http_client: IHttpClient,
        html_parser: IHtmlParser,
        robots_parser: IRobotsTxtParser
    ):
        # 依赖注入：技术接口由基础设施层实现，领域层仅使用抽象
        self._http = http_client
        self._parser = html_parser
        self._robots = robots_parser
    
    def extract_page_metadata(self, html: str, url: str) -> PageMetadata:
        # 1. 调用 IHtmlParser 获取原始 meta 标签
        meta_tags = self._parser.extract_meta_tags(html)
        
        # 2. 应用领域逻辑 - 优先级规则：按常见标准从强到弱选择标题
        title = (
            meta_tags.get('og:title') or  # Open Graph优先
            meta_tags.get('twitter:title') or 
            meta_tags.get('title') or
            '未知标题'  # 默认值
        )
        
        # 作者信息：常见字段回退
        author = meta_tags.get('author') or meta_tags.get('og:article:author')
        
        # 3. 日期解析 - 领域逻辑：统一格式并容错
        publish_date_str = meta_tags.get('article:published_time')
        publish_date = self._parse_date(publish_date_str) if publish_date_str else None
        
        return PageMetadata(
            title=title,
            author=author,
            abstract=meta_tags.get('description'),
            keywords=meta_tags.get('keywords', '').split(','),
            publish_date=publish_date,
            url=url
        )
    
    def discover_crawlable_links(self, html: str, base_url: str, task: CrawlTask) -> List[str]:
        # 1. 技术解析 - 委托给 IHtmlParser 抽取所有链接（已做绝对化处理）
        all_links = self._parser.extract_links(html, base_url)
        
        # 2. 应用领域规则过滤：白名单/去重/robots
        crawlable_links = []
        for link in all_links:
            # 业务规则1: 域名白名单
            if not task.is_url_allowed(link):
                continue
            
            # 业务规则2: 去重
            if task.is_url_visited(link):
                continue
            
            # 业务规则3: robots.txt
            if not self._robots.is_allowed(link, "WebCrawler/1.0"):
                continue
            
            crawlable_links.append(link)
        
        return crawlable_links
    
    def identify_pdf_links(self, links: List[str]) -> List[str]:
        pdf_links = []
        for link in links:
            # 领域规则1: 扩展名判断（快速路径）
            if link.lower().endswith('.pdf'):
                pdf_links.append(link)
                continue
            
            # 领域规则2: Content-Type 验证（准确路径）
            # 性能优化：暂时禁用对所有链接的 HEAD 请求，因为这会导致严重的性能问题（100+链接需要数分钟）
            # response = self._http.head(link)
            # if response.content_type and 'application/pdf' in response.content_type:
            #    pdf_links.append(link)
        
        return pdf_links
    
    def get_domain_crawl_delay(self, url: str) -> Optional[float]:
        """获取域名对应的 Crawl-delay"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return None

            # 构造基础 url (scheme + netloc)
            domain_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # 使用 robots parser 获取延迟
            # 这里我们假设 user_agent 是通用的，或者可以配置
            # 目前 CrawlDomainService 没有传入 User-Agent 的上下文，暂时硬编码或使用默认
            # 理想情况下应该从 Task 配置中获取，但接口定义限制了参数
            # 我们可以约定一个默认 User-Agent
            user_agent = "WebCrawler/1.0" 
            
            return self._robots.get_crawl_delay(domain_url, user_agent)
        except Exception as e:
            # 解析失败或其他错误，默认无延迟
            print(f"Error in get_domain_crawl_delay: {e}")
            return None

    def _parse_date(self, s: str) -> Optional[str]:
        """
        尝试按多种常见格式解析日期字符串，统一输出为 "YYYY-MM-DD"。
        解析失败返回 None。
        """
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        return None
