from dataclasses import dataclass, field
import datetime
from typing import List, Set
from urllib.parse import urlparse
from ..value_objects.crawl_config import CrawlConfig
from ..value_objects.crawl_status import TaskStatus
from ..value_objects.crawl_result import CrawlResult
from ..domain_event.task_life_cycle_event import BaseLifeCycleEvent

@dataclass
class CrawlTask:
    """
    爬取任务实体类，作为聚合根
    """
    id: str
    config: CrawlConfig
    status: TaskStatus = TaskStatus.PENDING
    results: List[CrawlResult] = field(default_factory=list)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    url_queue: List[str] = field(default_factory=list)

    _visited_urls: Set[str] = field(default_factory=set)
    _life_cycle_events: List[BaseLifeCycleEvent] = field(default_factory=list)


    def __init__(self, id: str, config: CrawlConfig):
        self.id = id
        self.config = config
        self.status = TaskStatus.PENDING
        self.results = []
 
        self.created_at = datetime.datetime.now()
        self.updated_at = self.created_at
        self.url_queue = []
        self._visited_urls = set()
        self._life_cycle_events = []

#-------------------   状态转换方法   -------------------

    def start_crawl(self):
        """开始爬取任务"""
        # TODO 先进行状态检查，是否为PENDING
        self.status = TaskStatus.RUNNING


    def pause_crawl(self):
        """暂停爬取任务"""
        # TODO 先进行状态检查，是否为RUNNING
        self.status = TaskStatus.PAUSED

    def resume_crawl(self):
        """恢复爬取任务"""
        self.status = TaskStatus.RUNNING

    
    def stop_crawl(self):
        """停止爬取任务"""
        self.status = TaskStatus.STOPPED


    def complete_crawl(self):
        """完成爬取任务"""
        self.status = TaskStatus.COMPLETED

    def fail_crawl(self):
        """失败爬取任务"""
        self.status = TaskStatus.FAILED

#-------------------   URL管理方法   -------------------


    def add_url_to_queue(self, url: str):
        """将URL添加到队列，执行去重和robots.txt验证"""
        self.url_queue.append(url)

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




