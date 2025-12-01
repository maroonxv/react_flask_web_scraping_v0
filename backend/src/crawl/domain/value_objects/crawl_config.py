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
