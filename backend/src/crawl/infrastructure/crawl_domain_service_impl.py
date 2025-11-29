from typing import List, Optional
from datetime import datetime
from crawl.domain.domain_service.i_crawl_domain_service import ICrawlDomainService
from crawl.domain.demand_interface.i_http_client import IHttpClient
from crawl.domain.demand_interface.i_html_parser import IHtmlParser
from crawl.domain.demand_interface.i_robots_txt_parser import IRobotsTxtParser
from crawl.domain.value_objects.page_metadata import PageMetadata
from crawl.domain.entity.crawl_task import CrawlTask

class CrawlDomainServiceImpl(ICrawlDomainService):
    def __init__(
        self,
        http_client: IHttpClient,
        html_parser: IHtmlParser,
        robots_parser: IRobotsTxtParser
    ):
        self._http = http_client
        self._parser = html_parser
        self._robots = robots_parser
    
    def extract_page_metadata(self, html: str, url: str) -> PageMetadata:
        # 1. 调用IHtmlParser获取原始meta标签
        meta_tags = self._parser.extract_meta_tags(html)
        
        # 2. 应用领域逻辑 - 优先级规则
        title = (
            meta_tags.get('og:title') or  # Open Graph优先
            meta_tags.get('twitter:title') or 
            meta_tags.get('title') or
            '未知标题'  # 默认值
        )
        
        author = meta_tags.get('author') or meta_tags.get('og:article:author')
        
        # 3. 日期解析 - 领域逻辑
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
        # 1. 技术解析 - 委托给IHtmlParser
        all_links = self._parser.extract_links(html, base_url)
        
        # 2. 应用领域规则过滤
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
            # 领域规则1: 扩展名判断
            if link.lower().endswith('.pdf'):
                pdf_links.append(link)
                continue
            
            # 领域规则2: Content-Type验证
            response = self._http.head(link)
            if response.content_type and 'application/pdf' in response.content_type:
                pdf_links.append(link)
        
        return pdf_links

    def _parse_date(self, s: str) -> Optional[str]:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        return None
