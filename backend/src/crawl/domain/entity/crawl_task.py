from dataclasses import dataclass, field
import datetime
from typing import List, Set, Optional
from urllib.parse import urlparse
from ..value_objects.crawl_config import CrawlConfig
from ..value_objects.crawl_status import TaskStatus
from ..value_objects.crawl_result import CrawlResult
from src.shared.domain.events import DomainEvent
from ..domain_event.task_life_cycle_event import (
    TaskCreatedEvent, TaskStartedEvent, TaskPausedEvent, 
    TaskResumedEvent, TaskStoppedEvent, TaskCompletedEvent, TaskFailedEvent
)
from ..domain_event.crawl_process_event import PageCrawledEvent, CrawlErrorEvent

from ..value_objects.crawl_strategy import CrawlStrategy

@dataclass
class CrawlTask:
    """
    爬取任务实体类，作为聚合根
    """
    id: str
    name: str  # Added name field
    config: CrawlConfig
    status: TaskStatus = TaskStatus.PENDING
    results: List[CrawlResult] = field(default_factory=list)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    url_queue_obj: Optional[object] = None # 实际的UrlQueue对象，非持久化字段

    _visited_urls: Set[str] = field(default_factory=set)
    _life_cycle_events: List[DomainEvent] = field(default_factory=list)


    def __init__(self, id: str, config: CrawlConfig, name: str = None):
        self.id = id
        self.name = name or id  # Default to id if name not provided
        self.config = config
        self.status = TaskStatus.PENDING
        self.results = []
 
        self.created_at = datetime.datetime.now()
        self.updated_at = self.created_at
        self.url_queue_obj = None
        self._visited_urls = set()
        self._life_cycle_events = []
        
        # 记录任务创建事件
        self._record_event(TaskCreatedEvent(
            task_id=self.id,
            start_url=self.config.start_url,
            strategy=self.config.strategy.value,
            max_depth=self.config.max_depth,
            max_pages=self.config.max_pages,
            request_interval=self.config.request_interval,
            allow_domains=self.config.allow_domains
        ))

    def _record_event(self, event: DomainEvent):
        """内部方法：记录领域事件"""
        self._life_cycle_events.append(event)
        self.updated_at = datetime.datetime.now()

    def get_uncommitted_events(self) -> List[DomainEvent]:
        """获取未提交的领域事件（用于后续发布）"""
        # 注意：这里通常应该返回并清空，或者由外部管理。
        # 为了简单起见，我们这里只返回副本，清空逻辑由应用服务处理
        # 或者我们遵循：事件是实体的历史记录，不应被清空？
        # 在Event Sourcing中是历史，在普通DDD中通常在事务提交后清空。
        # 这里我们假设应用服务会读取并发布，然后如果需要可以调用 clear_events
        return list(self._life_cycle_events)

    def clear_events(self):
        """清空已处理的事件"""
        self._life_cycle_events.clear()

#-------------------   状态转换方法   -------------------

    def start_crawl(self):
        """开始爬取任务"""
        if self.status != TaskStatus.PENDING:
            # 只有PENDING状态可以开始
            # 如果已经是RUNNING，忽略；如果是其他状态，可能抛异常
            return

        self.status = TaskStatus.RUNNING
        self._record_event(TaskStartedEvent(task_id=self.id))


    def pause_crawl(self):
        """暂停爬取任务"""
        if self.status != TaskStatus.RUNNING:
            return

        self.status = TaskStatus.PAUSED
        self._record_event(TaskPausedEvent(task_id=self.id))

    def resume_crawl(self):
        """恢复爬取任务"""
        if self.status != TaskStatus.PAUSED:
            return 

        self.status = TaskStatus.RUNNING
        self._record_event(TaskResumedEvent(task_id=self.id))

    
    def stop_crawl(self, reason: str = "用户手动停止"):
        """停止爬取任务"""
        if self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
            return

        self.status = TaskStatus.STOPPED
        self._record_event(TaskStoppedEvent(task_id=self.id, reason=reason))


    def complete_crawl(self, total_pdfs: int = 0):
        """完成爬取任务"""
        if self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
            return

        self.status = TaskStatus.COMPLETED
        
        # 计算耗时
        elapsed = (datetime.datetime.now() - self.created_at).total_seconds()
        
        self._record_event(TaskCompletedEvent(
            task_id=self.id,
            total_pages=len(self._visited_urls),
            total_pdfs=total_pdfs, # 这个数据可能需要外部传入，或者在实体内维护计数
            elapsed_time=elapsed
        ))

    def fail_crawl(self, error_message: str, stack_trace: str = ""):
        """失败爬取任务"""
        # 失败可以从任何状态发生
        self.status = TaskStatus.FAILED
        self._record_event(TaskFailedEvent(
            task_id=self.id,
            error_message=error_message,
            stack_trace=stack_trace
        ))

#-------------------   URL管理方法   -------------------


    def add_url_to_queue(self, url: str):
        """将URL添加到队列，执行去重和robots.txt验证"""
        # 注意：这里只做简单的队列管理，不触发核心生命周期事件
        # 需要由Service层调用UrlQueueImpl进行入队，这里仅做实体层校验
        if url not in self._visited_urls:
             # 实际入队逻辑由外部服务操作 self.url_queue_obj
             pass

    def set_config(self, interval: float = None, max_pages: int = None, max_depth: int = None, strategy: CrawlStrategy = None):
        """设置爬取配置"""
        if interval is not None:
            self.config.request_interval = interval
        if max_pages is not None:
            self.config.max_pages = max_pages
        if max_depth is not None:
            self.config.max_depth = max_depth
        if strategy is not None:
            self.config.strategy = strategy
        self.updated_at = datetime.datetime.now()
        # 这里可以记录配置变更事件，如果需要的话

#-------------------   业务规则验证   -------------------

    def is_url_allowed(self, url: str) -> bool:
        """验证URL是否符合允许的域名规则"""
        if not self.config.allow_domains:
            return True
        parsed_url = urlparse(url)
        return any(domain in parsed_url.netloc for domain in self.config.allow_domains)

    def mark_url_visited(self, url: str):
        self._visited_urls.add(url)

    def is_url_visited(self, url: str) -> bool:
        """验证URL是否已被访问"""
        return url in self._visited_urls

    @property
    def visited_urls(self) -> Set[str]:
        """获取已访问URL集合"""
        return self._visited_urls

    def add_crawl_result(self, result: CrawlResult, depth: int = 0):
        """添加爬取结果并记录事件"""
        self.results.append(result)
        self.updated_at = datetime.datetime.now()
        
        # 记录页面爬取成功事件
        self._record_event(PageCrawledEvent(
            task_id=self.id,
            url=result.url,
            title=result.title,
            depth=depth,
            status_code=200, # 假设成功
            pdf_count=len(result.pdf_links),
            author=result.author,
            abstract=result.abstract,
            keywords=result.keywords,
            publish_date=result.publish_date
        ))

    def record_crawl_error(self, url: str, error_message: str, error_type: str = "GeneralError"):
        """记录爬取错误"""
        self._record_event(CrawlErrorEvent(
            task_id=self.id,
            url=url,
            error_type=error_type,
            error_message=error_message
        ))
