from dataclasses import dataclass, field
from typing import List
from .crawl_strategy import CrawlStrategy

@dataclass
class CrawlConfig:
    start_url: str
    strategy: CrawlStrategy = CrawlStrategy.BFS
    max_depth: int = 3
    max_pages: int = 100
    request_interval: float = 1.0
    allow_domains: List[str] = field(default_factory=list)
