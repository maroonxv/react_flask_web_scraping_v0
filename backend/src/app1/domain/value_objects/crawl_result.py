from dataclasses import dataclass
import datetime
from typing import Optional, List

class CrawlResult:
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    abstract: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    publish_time: Optional[str] = None
    crawled_at: datetime.datetime = field(default_factory=datetime.datetime.now)