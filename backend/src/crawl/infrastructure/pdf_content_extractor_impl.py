"""
PDF 内容提取器实现模块

使用 PyMuPDF (fitz) 库实现 PDF 内容和元数据提取。
"""
import logging
from datetime import datetime
from typing import Optional

import fitz  # PyMuPDF

from ..domain.demand_interface.i_pdf_content_extractor import IPdfContentExtractor
from ..domain.value_objects.pdf_content import PdfContent
from ..domain.value_objects.pdf_metadata import PdfMetadata
from ..domain.exceptions.pdf_exceptions import PdfExtractionError, PdfPasswordProtectedError


logger = logging.getLogger('infrastructure.pdf')


class PdfContentExtractorImpl(IPdfContentExtractor):
    """PDF 内容提取器实现（使用 PyMuPDF）"""

    def extract_content(self, pdf_data: bytes, source_url: str) -> PdfContent:
        """
        从 PDF 二进制数据提取完整内容

        参数:
            pdf_data: PDF 文件的二进制数据
            source_url: PDF 来源 URL

        返回:
            PdfContent 值对象

        异常:
            PdfExtractionError: PDF 解析失败
            PdfPasswordProtectedError: PDF 受密码保护
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")

            if doc.is_encrypted:
                doc.close()
                raise PdfPasswordProtectedError(f"PDF is password protected: {source_url}")

            page_texts = []
            for page in doc:
                try:
                    page_texts.append(page.get_text())
                except Exception as e:
                    logger.warning(f"Failed to extract text from page: {str(e)}")
                    page_texts.append("")

            text_content = "\n".join(page_texts)
            metadata = self._extract_metadata_from_doc(doc)

            doc.close()

            return PdfContent(
                source_url=source_url,
                text_content=text_content,
                page_texts=tuple(page_texts),
                metadata=metadata
            )

        except PdfPasswordProtectedError:
            raise
        except fitz.FileDataError as e:
            raise PdfExtractionError(f"Invalid or corrupted PDF file: {str(e)}")
        except Exception as e:
            raise PdfExtractionError(f"Failed to extract PDF content: {str(e)}")

    def extract_metadata(self, pdf_data: bytes) -> PdfMetadata:
        """
        从 PDF 二进制数据提取元数据

        参数:
            pdf_data: PDF 文件的二进制数据

        返回:
            PdfMetadata 值对象

        异常:
            PdfExtractionError: PDF 解析失败
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            metadata = self._extract_metadata_from_doc(doc)
            doc.close()
            return metadata
        except fitz.FileDataError as e:
            raise PdfExtractionError(f"Invalid or corrupted PDF file: {str(e)}")
        except Exception as e:
            raise PdfExtractionError(f"Failed to extract PDF metadata: {str(e)}")

    def _extract_metadata_from_doc(self, doc: fitz.Document) -> PdfMetadata:
        """
        从 PyMuPDF 文档对象提取元数据

        参数:
            doc: PyMuPDF 文档对象

        返回:
            PdfMetadata 值对象
        """
        meta = doc.metadata or {}
        return PdfMetadata(
            title=meta.get("title") or None,
            author=meta.get("author") or None,
            creator=meta.get("creator") or None,
            creation_date=self._parse_pdf_date(meta.get("creationDate")),
            modification_date=self._parse_pdf_date(meta.get("modDate")),
            page_count=doc.page_count
        )

    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        解析 PDF 日期格式

        PDF 日期格式: D:YYYYMMDDHHmmSS+HH'mm' 或 D:YYYYMMDDHHmmSS

        参数:
            date_str: PDF 日期字符串

        返回:
            datetime 对象，解析失败返回 None
        """
        if not date_str:
            return None

        try:
            # 移除 "D:" 前缀
            if date_str.startswith("D:"):
                date_str = date_str[2:]

            # 移除时区信息（如果存在）
            # 格式可能是: YYYYMMDDHHmmSS+HH'mm' 或 YYYYMMDDHHmmSS-HH'mm'
            for sep in ['+', '-', 'Z']:
                if sep in date_str:
                    date_str = date_str.split(sep)[0]
                    break

            # 尝试解析不同长度的日期字符串
            if len(date_str) >= 14:
                return datetime.strptime(date_str[:14], "%Y%m%d%H%M%S")
            elif len(date_str) >= 8:
                return datetime.strptime(date_str[:8], "%Y%m%d")
            elif len(date_str) >= 4:
                return datetime.strptime(date_str[:4], "%Y")

            return None
        except Exception as e:
            logger.debug(f"Failed to parse PDF date '{date_str}': {str(e)}")
            return None
