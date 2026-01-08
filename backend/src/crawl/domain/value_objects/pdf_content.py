from dataclasses import dataclass
from typing import Optional, Tuple
from .pdf_metadata import PdfMetadata


@dataclass(frozen=True)
class PdfContent:
    """PDF 内容值对象（不可变）"""
    source_url: str
    text_content: str  # 全文本内容
    page_texts: Tuple[str, ...]  # 每页文本（使用 tuple 保持不可变）
    metadata: Optional[PdfMetadata] = None
