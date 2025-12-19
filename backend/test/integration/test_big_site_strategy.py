
import pytest
import time
from threading import Event
from unittest.mock import MagicMock
import sys
import os

# Add backend to path
current_file_path = os.path.abspath(__file__)
test_dir = os.path.dirname(os.path.dirname(current_file_path))
backend_dir = os.path.dirname(test_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from src.crawl.services.crawler_service import CrawlerService
from src.crawl.domain.value_objects.crawl_config import CrawlConfig
from src.crawl.domain.value_objects.crawl_strategy import CrawlStrategy
from src.crawl.domain.value_objects.crawl_status import TaskStatus
from src.shared.event_bus import EventBus
from src.crawl.domain.demand_interface.i_http_client import IHttpClient
from src.crawl.domain.value_objects.http_response import HttpResponse
from src.crawl.domain.domain_service.i_crawl_domain_service import ICrawlDomainService
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
        mock_meta.title = f"Title for {url}"
        mock_meta.author = None
        mock_meta.abstract = None
        mock_meta.keywords = []
        mock_meta.publish_date = None
        return mock_meta

    def discover_crawlable_links(self, content, url, task):
        # 如果是起始页，返回一组混合链接
        if url == "https://start.com":
            return [
                "https://github.com/repo1",       # 大站
                "https://small-site.com/page1",   # 普通
                "https://small-site.com/doc.pdf"  # PDF
            ]
        return []

    def identify_pdf_links(self, links):
        return [link for link in links if link.endswith('.pdf')]

def test_big_site_strategy():
    # Setup
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
    
    # Config
    config = CrawlConfig(
        start_url="https://start.com",
        strategy=CrawlStrategy.BIG_SITE_FIRST,
        max_depth=2,
        priority_domains=["github.com"],
        request_interval=0.01 # Speed up
    )
    
    # Create and Start Task
    task_id = service.create_crawl_task(config)
    service.start_crawl_task(task_id)
    
    # Wait for crawl to process
    time.sleep(1) # Should be enough for 4 requests

    
    # Stop
    service.stop_crawl_task(task_id)
    
    # Verify Results
    results = service.get_task_results(task_id)
    
    # Print results for debug
    for r in results:
        print(f"URL: {r.url}, Tags: {r.tags}, Depth: {r.depth}")
        
    # Assertions
    # 1. Start URL should be crawled
    assert any(r.url == "https://start.com" for r in results)
    
    # 2. Big Site should have tag
    github_result = next((r for r in results if "github.com" in r.url), None)
    assert github_result is not None
    assert "big_site" in github_result.tags
    
    # 3. Small Site should not have tag
    small_result = next((r for r in results if "small-site.com/page1" in r.url), None)
    assert small_result is not None
    assert "big_site" not in small_result.tags

if __name__ == "__main__":
    test_big_site_strategy()
