from dataclasses import dataclass, field
from typing import List
from .crawl_strategy import CrawlStrategy

@dataclass
class CrawlConfig:
    start_url: str
    strategy: CrawlStrategy = CrawlStrategy.BFS
    max_depth: int = 3
    max_pages: int = 100
    request_interval: float = 1.0  # 这个参数控制请求间隔，实现爬取速率控制
    allow_domains: List[str] = field(default_factory=list)
    priority_domains: List[str] = field(default_factory=list)

    def __post_init__(self):
        """
        数据清洗与验证
        """
        if self.allow_domains:
            from urllib.parse import urlparse
            cleaned = []
            for domain in self.allow_domains:
                if not domain:
                    continue
                domain = domain.strip()
                
                # 如果包含协议，解析出域名
                if '://' in domain:
                    try:
                        parsed = urlparse(domain)
                        if parsed.netloc:
                            cleaned.append(parsed.netloc)
                        else:
                            cleaned.append(domain)
                    except:
                        cleaned.append(domain)
                # 如果不包含协议但包含路径分隔符，截取前面部分
                elif '/' in domain:
                    cleaned.append(domain.split('/')[0])
                else:
                    cleaned.append(domain)
            
            self.allow_domains = cleaned
