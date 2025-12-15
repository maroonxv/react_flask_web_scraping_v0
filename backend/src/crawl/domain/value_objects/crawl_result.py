from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

@dataclass
class CrawlResult:
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    abstract: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    publish_date: Optional[str] = None
    pdf_links: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    depth: int = 0
    crawled_at: datetime = field(default_factory=datetime.now)
