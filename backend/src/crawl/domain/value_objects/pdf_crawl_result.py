from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from .pdf_content import PdfContent


@dataclass
class PdfCrawlResult:
    """PDF 爬取结果值对象"""
    url: str
    pdf_content: Optional[PdfContent] = None
    crawled_at: datetime = field(default_factory=datetime.now)
    depth: int = 0
    error_message: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.pdf_content is not None and self.error_message is None
