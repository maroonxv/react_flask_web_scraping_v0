from abc import ABC, abstractmethod
from ..value_objects.pdf_content import PdfContent
from ..value_objects.pdf_metadata import PdfMetadata


class IPdfContentExtractor(ABC):
    """PDF 内容提取器接口"""

    @abstractmethod
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
        pass

    @abstractmethod
    def extract_metadata(self, pdf_data: bytes) -> PdfMetadata:
        """
        从 PDF 二进制数据提取元数据

        参数:
            pdf_data: PDF 文件的二进制数据

        返回:
            PdfMetadata 值对象
        """
        pass
