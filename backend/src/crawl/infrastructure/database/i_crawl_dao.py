from abc import ABC, abstractmethod
from typing import List, Optional
from .models import CrawlTaskModel, CrawlResultModel, PdfResultModel

class ICrawlDao(ABC):
    """
    Interface for Crawl Data Access Object
    """
    
    @abstractmethod
    def create_task(self, task: CrawlTaskModel) -> None:
        """Create a new crawl task"""
        pass

    @abstractmethod
    def get_task_by_id(self, task_id: str) -> Optional[CrawlTaskModel]:
        """Get a crawl task by ID"""
        pass

    @abstractmethod
    def update_task(self, task: CrawlTaskModel) -> None:
        """Update an existing crawl task"""
        pass

    @abstractmethod
    def get_all_tasks(self) -> List[CrawlTaskModel]:
        """Get all crawl tasks"""
        pass

    @abstractmethod
    def add_result(self, result: CrawlResultModel) -> None:
        """Add a crawl result"""
        pass

    @abstractmethod
    def get_results_by_task_id(self, task_id: str) -> List[CrawlResultModel]:
        """Get all results for a specific task"""
        pass
    
    @abstractmethod
    def delete_results_by_task_id(self, task_id: str) -> None:
        """Delete all results for a specific task (e.g. on restart)"""
        pass

    @abstractmethod
    def add_pdf_result(self, result: PdfResultModel) -> None:
        """Add a PDF crawl result"""
        pass

    @abstractmethod
    def get_pdf_results_by_task_id(self, task_id: str) -> List[PdfResultModel]:
        """Get all PDF results for a specific task"""
        pass
