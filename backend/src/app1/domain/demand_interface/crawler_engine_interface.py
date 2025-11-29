from abc import ABC, abstractmethod

class CrawlerEngineInterface(ABC):
    @abstractmethod
    def fetch_url(self, url: str) -> HttpResponse:
        """执行HTTP请求"""
        pass
    
    @abstractmethod
    def extract_pdf_info(self, pdf_content: bytes) -> PDFMetadata:
        """提取PDF关键信息(标题、作者、摘要、关键词、发表时间)"""
        pass
