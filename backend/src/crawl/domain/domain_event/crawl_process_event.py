from dataclasses import dataclass, field
from typing import List
from src.shared.domain.events import DomainEvent

@dataclass
class PageCrawledEvent(DomainEvent):
    """页面爬取成功事件"""
    url: str
    title: str
    depth: int
    status_code: int
    pdf_count: int = 0

@dataclass
class PdfFoundEvent(DomainEvent):
    """发现PDF事件"""
    pdf_urls: List[str]
    source_page_url: str
    count: int

@dataclass
class CrawlErrorEvent(DomainEvent):
    """爬取过程中发生的非致命错误（如单个页面失败）"""
    url: str
    error_type: str
    error_message: str

@dataclass
class LinkFilteredEvent(DomainEvent):
    """链接被过滤事件（可选，用于调试或详细日志）"""
    url: str
    reason: str  # e.g., "visited", "domain_not_allowed", "robots_txt"
