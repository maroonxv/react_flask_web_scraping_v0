from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass(frozen=True)
class PdfMetadata:
    """PDF 元数据值对象（不可变）"""
    title: Optional[str] = None
    author: Optional[str] = None
    creator: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
