# backend/test/integration/test_end_to_end_crawl.py
import pytest
import time
from threading import Event
from unittest.mock import MagicMock, ANY
import sys
import os

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, project_root)

from backend.src.crawl.services.crawler_service import CrawlerService
from backend.src.crawl.domain.value_objects.crawl_config import CrawlConfig
from backend.src.crawl.domain.value_objects.crawl_strategy import CrawlStrategy
from backend.src.crawl.domain.value_objects.crawl_status import TaskStatus
from backend.src.crawl.infrastructure.url_queue_impl import UrlQueueImpl
from backend.src.shared.event_bus import EventBus
from backend.src.crawl.domain.demand_interface.i_http_client import IHttpClient
from backend.src.crawl.domain.demand_interface.i_url_queue import IUrlQueue
from backend.src.crawl.domain.domain_service.i_crawl_domain_service import ICrawlDomainService

# Mock实现，用于隔离网络和复杂依赖
class MockHttpClient(IHttpClient):
    def __init__(self):
        self.get_count = 0
        
    def get(self, url: str, **kwargs):
        self.get_count += 1
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.content = b"<html><body><a href='https://news.ycombinator.com/item?id=123'>Link</a></body></html>"
        return mock_response

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
            return ["https://news.ycombinator.com/item?id=123", "https://news.ycombinator.com/item?id=456"]
        return []

    def identify_pdf_links(self, links):
        return []

@pytest.fixture
def crawler_service():
    http_client = MockHttpClient()
    domain_service = MockCrawlDomainService()
    event_bus = EventBus()
    
    service = CrawlerService(
        crawl_domain_service=domain_service,
        http_client=http_client,
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
        start_urls=["https://news.ycombinator.com/"],
        strategy=CrawlStrategy.BFS,
        max_depth=2,
        max_pages=10,
        request_interval=0.1, # 快速测试
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
