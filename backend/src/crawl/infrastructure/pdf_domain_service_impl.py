"""
PDF 领域服务实现模块

模块职责:
- 协调 IBinaryHttpClient 和 IPdfContentExtractor 完成 PDF 处理
- 验证 Content-Type 确保下载的是 PDF 文件
- 封装成功结果或错误信息到 PdfCrawlResult

设计要点:
- 遵循开闭原则，作为独立实现不修改现有代码
- 依赖注入：通过构造函数注入 IBinaryHttpClient 和 IPdfContentExtractor
- 错误处理：下载失败或提取失败都返回带 error_message 的 PdfCrawlResult
"""

import logging
from ..domain.domain_service.i_pdf_domain_service import IPdfDomainService
from ..domain.demand_interface.i_binary_http_client import IBinaryHttpClient
from ..domain.demand_interface.i_pdf_content_extractor import IPdfContentExtractor
from ..domain.value_objects.pdf_crawl_result import PdfCrawlResult

logger = logging.getLogger('domain.pdf')


class PdfDomainServiceImpl(IPdfDomainService):
    """
    PDF 领域服务实现
    
    协调二进制 HTTP 客户端和 PDF 内容提取器，完成 PDF URL 的处理流程：
    1. 下载 PDF 二进制数据
    2. 验证 Content-Type 为 application/pdf
    3. 提取文本内容和元数据
    4. 封装结果或错误信息
    """
    
    def __init__(
        self,
        binary_http_client: IBinaryHttpClient,
        pdf_extractor: IPdfContentExtractor
    ):
        """
        初始化 PDF 领域服务
        
        参数:
            binary_http_client: 二进制 HTTP 客户端，用于下载 PDF 文件
            pdf_extractor: PDF 内容提取器，用于解析 PDF 内容
        """
        self._http_client = binary_http_client
        self._pdf_extractor = pdf_extractor
    
    def process_pdf_url(self, url: str, depth: int = 0) -> PdfCrawlResult:
        """
        处理 PDF URL：下载并提取内容
        
        处理流程:
        1. 使用 IBinaryHttpClient 下载 PDF 二进制数据
        2. 验证响应的 Content-Type 包含 application/pdf
        3. 使用 IPdfContentExtractor 提取文本和元数据
        4. 返回 PdfCrawlResult（成功或失败）
        
        参数:
            url: PDF 文件 URL
            depth: 爬取深度
            
        返回:
            PdfCrawlResult 值对象（包含成功结果或错误信息）
        """
        # 1. 下载 PDF
        response = self._http_client.get_binary(url)
        
        if not response.is_success:
            logger.warning(f"Failed to download PDF: {url} - {response.error_message}")
            return PdfCrawlResult(
                url=url,
                depth=depth,
                error_message=f"Download failed: {response.error_message}"
            )
        
        # 2. 验证 Content-Type
        content_type = response.content_type.lower() if response.content_type else ""
        if "application/pdf" not in content_type:
            logger.warning(f"Not a PDF file: {url} - Content-Type: {response.content_type}")
            return PdfCrawlResult(
                url=url,
                depth=depth,
                error_message=f"Not a PDF: {response.content_type}"
            )
        
        # 3. 提取内容
        try:
            pdf_content = self._pdf_extractor.extract_content(response.content, url)
            page_count = pdf_content.metadata.page_count if pdf_content.metadata else 0
            logger.info(f"Successfully extracted PDF: {url} ({page_count} pages)")
            return PdfCrawlResult(
                url=url,
                pdf_content=pdf_content,
                depth=depth
            )
            
        except Exception as e:
            logger.error(f"Failed to extract PDF content: {url} - {str(e)}")
            return PdfCrawlResult(
                url=url,
                depth=depth,
                error_message=str(e)
            )
