from abc import ABC, abstractmethod
from typing import List, Optional
from ..entity.crawl_task import CrawlTask
from ..value_objects.crawl_result import CrawlResult
from ..value_objects.pdf_crawl_result import PdfCrawlResult

class ICrawlRepository(ABC):
    """
    爬取任务仓储接口
    负责领域对象 CrawlTask 的持久化
    """

    @abstractmethod
    def save_task(self, task: CrawlTask) -> None:
        """保存或更新爬取任务"""
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[CrawlTask]:
        """根据ID获取爬取任务"""
        pass

    @abstractmethod
    def get_all_tasks(self) -> List[CrawlTask]:
        """获取所有爬取任务"""
        pass

    @abstractmethod
    def save_result(self, task_id: str, result: CrawlResult) -> None:
        """保存单条爬取结果"""
        pass

    @abstractmethod
    def get_results(self, task_id: str) -> List[CrawlResult]:
        """获取任务的所有爬取结果"""
        pass
    
    @abstractmethod
    def delete_results(self, task_id: str) -> None:
        """删除任务的所有结果 (用于重试/清理)"""
        pass

    @abstractmethod
    def save_pdf_result(self, task_id: str, result: PdfCrawlResult) -> None:
        """保存单条 PDF 爬取结果"""
        pass

    @abstractmethod
    def get_pdf_results(self, task_id: str) -> List[PdfCrawlResult]:
        """获取任务的所有 PDF 爬取结果"""
        pass
