# backend/test/integration/test_end_to_end_crawl.py
import pytest
import time
from threading import Event
from unittest.mock import MagicMock, ANY
import sys
import os

# Add backend to path
# 获取当前文件的绝对路径
current_file_path = os.path.abspath(__file__)
# 获取 test 目录
test_dir = os.path.dirname(os.path.dirname(current_file_path))
# 获取 backend 目录
backend_dir = os.path.dirname(test_dir)
# 获取项目根目录 (scraping_app_v0)
project_root = os.path.dirname(backend_dir)

# 将 backend 目录添加到 sys.path，以便可以直接导入 src
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from src.crawl.services.crawler_service import CrawlerService
from src.crawl.domain.value_objects.crawl_config import CrawlConfig
from src.crawl.domain.value_objects.crawl_strategy import CrawlStrategy
from src.crawl.domain.value_objects.crawl_status import TaskStatus
from src.crawl.infrastructure.url_queue_impl import UrlQueueImpl
from src.shared.event_bus import EventBus
from src.crawl.domain.demand_interface.i_http_client import IHttpClient
from src.crawl.domain.value_objects.http_response import HttpResponse
from src.crawl.domain.demand_interface.i_url_queue import IUrlQueue
from src.crawl.domain.domain_service.i_crawl_domain_service import ICrawlDomainService
from src.crawl.infrastructure.http_client_impl import HttpClientImpl
from src.crawl.domain.demand_interface.i_crawl_repository import ICrawlRepository
from src.crawl.domain.entity.crawl_task import CrawlTask
from src.crawl.domain.value_objects.crawl_result import CrawlResult

class InMemoryCrawlRepository(ICrawlRepository):
    def __init__(self):
        self._tasks: dict[str, CrawlTask] = {}
        self._results: dict[str, list[CrawlResult]] = {}

    def save_task(self, task: CrawlTask) -> None:
        self._tasks[task.id] = task

    def get_task(self, task_id: str):
        return self._tasks.get(task_id)

    def get_all_tasks(self):
        return list(self._tasks.values())

    def save_result(self, task_id: str, result: CrawlResult) -> None:
        self._results.setdefault(task_id, []).append(result)

    def get_results(self, task_id: str):
        return list(self._results.get(task_id, []))

    def delete_results(self, task_id: str) -> None:
        self._results[task_id] = []

# Mock实现，用于隔离网络和复杂依赖
class MockHttpClient(IHttpClient):
    def get(self, url: str, headers=None) -> HttpResponse:
        return HttpResponse(
            url=url,
            status_code=200,
            headers={"Content-Type": "text/html"},
            content="<html><body>Mock Content</body></html>",
            content_type="text/html",
            is_success=True,
            error_message=None
        )
        
    def head(self, url: str) -> HttpResponse:
        return HttpResponse(
            url=url,
            status_code=200,
            headers={"Content-Type": "text/html"},
            content="",
            content_type="text/html",
            is_success=True,
            error_message=None
        )
    
    def close(self):
        pass

class MockCrawlDomainService(ICrawlDomainService):
    def extract_page_metadata(self, content, url):
        mock_meta = MagicMock()
        mock_meta.title = "Hacker News"
        mock_meta.author = None
        mock_meta.abstract = None
        mock_meta.keywords = []
        mock_meta.publish_date = None
        return mock_meta

    def discover_crawlable_links(self, content, url, task):
        # 模拟发现链接
        if "ycombinator.com" in url:
            # Generate dynamic links to ensure we have enough content to crawl
            import hashlib
            base_hash = int(hashlib.md5(url.encode()).hexdigest(), 16)
            return [
                f"https://news.ycombinator.com/item?id={base_hash % 100000}",
                f"https://news.ycombinator.com/item?id={(base_hash + 1) % 100000}"
            ]
        return []

    def identify_pdf_links(self, links):
        return []

@pytest.fixture
def crawler_service():
    # 使用 Mock HttpClientImpl
    http_client = MockHttpClient()
    domain_service = MockCrawlDomainService()
    event_bus = EventBus()
    repository = InMemoryCrawlRepository()
    
    service = CrawlerService(
        crawl_domain_service=domain_service,
        http_client=http_client,
        repository=repository,
        event_bus=event_bus
    )
    return service

def test_end_to_end_crawl_lifecycle(crawler_service):
    """
    端到端测试爬取任务生命周期：
    创建 -> 启动 -> 运行 -> 暂停 -> 修改配置 -> 恢复 -> 停止 -> 查看结果
    """
    # 1. 初始化爬取任务
    config = CrawlConfig(
        start_url="https://news.ycombinator.com/",
        strategy=CrawlStrategy.BFS,
        max_depth=10,
        max_pages=50,
        request_interval=0.2, # 慢一点，避免测试过快结束
        allow_domains=["ycombinator.com"]
    )
    
    task_id = crawler_service.create_crawl_task(config)
    assert task_id is not None
    
    # 验证任务已创建且状态为PENDING
    status = crawler_service.get_task_status(task_id)
    assert status["status"] == TaskStatus.PENDING.value
    assert status["queue_size"] == 0 # 此时队列尚未初始化

    # 2. 启动爬取任务
    crawler_service.start_crawl_task(task_id)
    
    # 等待一小段时间让线程启动并爬取一些页面
    time.sleep(1)
    
    # 验证状态为RUNNING
    status = crawler_service.get_task_status(task_id)
    assert status["status"] == TaskStatus.RUNNING.value
    # 应该已经有结果了
    assert status["visited_count"] > 0
    assert status["result_count"] > 0
    
    # 3. 暂停爬取任务
    crawler_service.pause_crawl_task(task_id)
    
    # 验证状态为PAUSED
    status = crawler_service.get_task_status(task_id)
    assert status["status"] == TaskStatus.PAUSED.value
    
    # 记录当前的爬取数量，用于后续验证是否真的暂停（数量不再增加）
    count_after_pause = status["visited_count"]
    time.sleep(0.5)
    status = crawler_service.get_task_status(task_id)
    assert status["visited_count"] == count_after_pause
    
    # 4. 修改爬取任务的配置
    # 修改间隔为0.5s，最大深度为5
    crawler_service.set_crawl_config(task_id, interval=0.5, max_depth=5)
    
    # 验证配置已更新
    task = crawler_service._tasks[task_id]
    assert task.config.request_interval == 0.5
    assert task.config.max_depth == 5
    
    # 5. 恢复爬取任务
    crawler_service.resume_crawl_task(task_id)
    
    # 验证状态恢复为RUNNING
    status = crawler_service.get_task_status(task_id)
    assert status["status"] == TaskStatus.RUNNING.value
    
    # 等待爬取继续进行
    time.sleep(1)
    status = crawler_service.get_task_status(task_id)
    assert status["visited_count"] > count_after_pause
    
    # 6. 停止爬取任务
    crawler_service.stop_crawl_task(task_id)
    
    # 验证状态为STOPPED
    status = crawler_service.get_task_status(task_id)
    # 注意：stop是异步信号，可能需要一点时间或者立即生效（取决于循环检查点）
    # 在当前实现中，stop_crawl_task直接修改了状态，所以应该立即生效
    assert status["status"] == TaskStatus.STOPPED.value
    
    # 验证队列已清空
    assert status["queue_size"] == 0
    
    # 7. 获取爬取结果
    results = crawler_service.get_task_results(task_id)
    assert len(results) > 0
    assert results[0].url == "https://news.ycombinator.com/"
    assert results[0].title == "Hacker News"

    print(f"\n测试通过！共爬取 {len(results)} 个页面。")

if __name__ == "__main__":
    # 允许直接运行此脚本进行测试
    pytest.main([__file__, "-v", "-s"])
