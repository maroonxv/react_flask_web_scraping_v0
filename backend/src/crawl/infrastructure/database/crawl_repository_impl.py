from typing import List, Optional
import json
from ...domain.demand_interface.i_crawl_repository import ICrawlRepository
from ...domain.entity.crawl_task import CrawlTask
from ...domain.value_objects.crawl_result import CrawlResult
from ...domain.value_objects.pdf_crawl_result import PdfCrawlResult
from ...domain.value_objects.pdf_content import PdfContent
from ...domain.value_objects.pdf_metadata import PdfMetadata
from ...domain.value_objects.crawl_config import CrawlConfig
from ...domain.value_objects.crawl_status import TaskStatus
from ...domain.value_objects.crawl_strategy import CrawlStrategy
from .i_crawl_dao import ICrawlDao
from .models import CrawlTaskModel, CrawlResultModel, PdfResultModel

class CrawlRepositoryImpl(ICrawlRepository):
    """
    爬取任务仓储实现
    """
    
    def __init__(self, dao: ICrawlDao):
        self._dao = dao

    def save_task(self, task: CrawlTask) -> None:
        """
        保存或更新任务
        注意：这里只保存任务本身的属性，不级联保存 results (results由save_result单独处理)
        但是需要保存 visited_urls
        """
        model = self._to_task_model(task)
        # 检查是否存在
        existing = self._dao.get_task_by_id(task.id)
        if existing:
            self._dao.update_task(model)
        else:
            self._dao.create_task(model)

    def get_task(self, task_id: str) -> Optional[CrawlTask]:
        model = self._dao.get_task_by_id(task_id)
        if not model:
            return None
        return self._to_task_entity(model)

    def get_all_tasks(self) -> List[CrawlTask]:
        models = self._dao.get_all_tasks()
        return [self._to_task_entity(m) for m in models]

    def save_result(self, task_id: str, result: CrawlResult) -> None:
        model = self._to_result_model(task_id, result)
        self._dao.add_result(model)

    def get_results(self, task_id: str) -> List[CrawlResult]:
        models = self._dao.get_results_by_task_id(task_id)
        return [self._to_result_entity(m) for m in models]

    def delete_results(self, task_id: str) -> None:
        self._dao.delete_results_by_task_id(task_id)

    def save_pdf_result(self, task_id: str, result: PdfCrawlResult) -> None:
        model = self._to_pdf_result_model(task_id, result)
        self._dao.add_pdf_result(model)

    def get_pdf_results(self, task_id: str) -> List[PdfCrawlResult]:
        models = self._dao.get_pdf_results_by_task_id(task_id)
        return [self._to_pdf_result_entity(m) for m in models]

    # ------------------ 映射方法 ------------------

    def _to_task_model(self, task: CrawlTask) -> CrawlTaskModel:
        return CrawlTaskModel(
            id=task.id,
            name=task.name,
            status=task.status.value,
            start_url=task.config.start_url,
            strategy=task.config.strategy.value,
            max_depth=task.config.max_depth,
            max_pages=task.config.max_pages,
            request_interval=task.config.request_interval,
            allow_domains=task.config.allow_domains,
            priority_domains=task.config.priority_domains,
            visited_urls=list(task.visited_urls), # Set -> List for JSON
            created_at=task.created_at,
            updated_at=task.updated_at
        )

    def _to_task_entity(self, model: CrawlTaskModel) -> CrawlTask:
        config = CrawlConfig(
            start_url=model.start_url,
            strategy=CrawlStrategy(model.strategy),
            max_depth=model.max_depth,
            max_pages=model.max_pages,
            request_interval=model.request_interval,
            allow_domains=model.allow_domains if model.allow_domains else [],
            priority_domains=model.priority_domains if model.priority_domains else []
        )
        
        task = CrawlTask(id=model.id, config=config, name=model.name)
        task.status = TaskStatus(model.status)
        task.created_at = model.created_at
        task.updated_at = model.updated_at
        
        if model.visited_urls:
            # 这里的 _visited_urls 是 protected，但在 entity 中有 property
            # 我们需要一种方式设置它，或者直接操作 _visited_urls
            # 由于是 Python，直接访问 _visited_urls 是可行的，虽然不优雅
            task._visited_urls = set(model.visited_urls)
            
        # 注意：这里没有加载 results，如果需要，调用者应该单独调用 get_results
        # 或者我们在 entity 中加一个 load_results 方法
        return task

    def _to_result_model(self, task_id: str, result: CrawlResult) -> CrawlResultModel:
        return CrawlResultModel(
            task_id=task_id,
            url=result.url,
            title=result.title,
            author=result.author,
            abstract=result.abstract,
            keywords=result.keywords,
            publish_date=result.publish_date,
            pdf_links=result.pdf_links,
            tags=result.tags,
            depth=result.depth,
            crawled_at=result.crawled_at
        )

    def _to_result_entity(self, model: CrawlResultModel) -> CrawlResult:
        return CrawlResult(
            url=model.url,
            title=model.title,
            author=model.author,
            abstract=model.abstract,
            keywords=model.keywords if model.keywords else [],
            publish_date=model.publish_date,
            pdf_links=model.pdf_links if model.pdf_links else [],
            tags=model.tags if model.tags else [],
            depth=model.depth,
            crawled_at=model.crawled_at
        )

    def _to_pdf_result_model(self, task_id: str, result: PdfCrawlResult) -> PdfResultModel:
        model = PdfResultModel(
            task_id=task_id,
            url=result.url,
            is_success=1 if result.is_success else 0,
            error_message=result.error_message,
            depth=result.depth,
            crawled_at=result.crawled_at
        )
        
        if result.pdf_content:
            model.content_text = result.pdf_content.text_content
            if result.pdf_content.metadata:
                model.meta_title = result.pdf_content.metadata.title
                model.meta_author = result.pdf_content.metadata.author
                model.page_count = result.pdf_content.metadata.page_count
                model.creation_date = result.pdf_content.metadata.creation_date
                
        return model

    def _to_pdf_result_entity(self, model: PdfResultModel) -> PdfCrawlResult:
        content = None
        if model.is_success:
            metadata = PdfMetadata(
                title=model.meta_title,
                author=model.meta_author,
                page_count=model.page_count,
                creation_date=model.creation_date,
                modification_date=None, # DB model simplified, can add if needed
                creator=None
            )
            content = PdfContent(
                source_url=model.url,
                text_content=model.content_text,
                page_texts=(), # Large data, maybe skip loading for summary list
                metadata=metadata
            )
            
        return PdfCrawlResult(
            url=model.url,
            pdf_content=content,
            crawled_at=model.crawled_at,
            depth=model.depth,
            error_message=model.error_message
        )
