from abc import ABC, abstractmethod
from ..value_objects.pdf_crawl_result import PdfCrawlResult


class IPdfDomainService(ABC):
    """
    PDF 领域服务接口
    
    封装 PDF 处理的领域逻辑，包括下载和内容提取。
    遵循开闭原则，作为独立接口不修改现有 ICrawlDomainService。
    """
    
    @abstractmethod
    def process_pdf_url(self, url: str, depth: int = 0) -> PdfCrawlResult:
        """
        处理 PDF URL：下载并提取内容
        
        领域逻辑:
        - 下载 PDF 二进制数据
        - 验证 Content-Type 为 application/pdf
        - 提取文本内容和元数据
        - 封装结果或错误信息
        
        参数:
            url: PDF 文件 URL
            depth: 爬取深度
            
        返回:
            PdfCrawlResult 值对象（包含成功结果或错误信息）
        """
        pass
