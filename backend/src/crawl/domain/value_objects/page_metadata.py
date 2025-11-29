from dataclasses import dataclass
from typing import Optional, List

@dataclass
class PageMetadata:
    title: str
    author: Optional[str]
    abstract: Optional[str]
    keywords: List[str]
    publish_date: Optional[str]
    url: str
