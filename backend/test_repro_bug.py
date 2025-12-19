
import time
import pytest
from unittest.mock import MagicMock

from src.crawl.services.crawler_service import CrawlerService
from src.crawl.domain.value_objects.crawl_config import CrawlConfig
from src.crawl.domain.value_objects.crawl_strategy import CrawlStrategy
from src.crawl.domain.value_objects.crawl_status import TaskStatus
from src.crawl.domain.demand_interface.i_http_client import IHttpClient
from src.crawl.domain.domain_service.i_crawl_domain_service import ICrawlDomainService
from src.crawl.domain.value_objects.http_response import HttpResponse
from src.crawl.domain.demand_interface.i_crawl_repository import ICrawlRepository
from src.crawl.domain.value_objects.crawl_result import CrawlResult


class InMemoryCrawlRepository(ICrawlRepository):
    def __init__(self):
        self._tasks = {}
        self._results = {}

    def save_task(self, task):
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
            content="<html><body>Mock</body></html>",
            content_type="text/html",
            is_success=True,
            error_message=None,
        )

    def head(self, url: str) -> HttpResponse:
        return HttpResponse(
            url=url,
            status_code=200,
            headers={"Content-Type": "text/html"},
            content="",
            content_type="text/html",
            is_success=True,
            error_message=None,
        )

    def close(self):
        pass


class MockCrawlDomainService(ICrawlDomainService):
    def extract_page_metadata(self, html: str, url: str):
        meta = MagicMock()
        meta.title = f"Title {url}"
        meta.author = None
        meta.abstract = None
        meta.keywords = []
        meta.publish_date = None
        return meta

    def discover_crawlable_links(self, html: str, base_url: str, task):
        idx = len(task.visited_urls)
        return [f"http://example.com/page/{idx + 1}"]

    def identify_pdf_links(self, links):
        return []


def test_pause_resume():
    http = MockHttpClient()
    domain_service = MockCrawlDomainService()
    repository = InMemoryCrawlRepository()

    service = CrawlerService(domain_service, http, repository=repository, event_bus=None)

    config = CrawlConfig(
        start_url="http://example.com/page/0",
        strategy=CrawlStrategy.BFS,
        max_depth=100000,
        max_pages=200,
        request_interval=0.01,
    )

    task_id = service.create_crawl_task(config)
    service.start_crawl_task(task_id)

    time.sleep(0.05)
    status = service.get_task_status(task_id)
    assert status["status"] == TaskStatus.RUNNING.value
    assert status["visited_count"] > 0

    service.pause_crawl_task(task_id)
    time.sleep(0.2)
    status = service.get_task_status(task_id)
    assert status["status"] == TaskStatus.PAUSED.value
    visited_before = status["visited_count"]
    time.sleep(1.1)
    visited_after = service.get_task_status(task_id)["visited_count"]
    assert visited_after == visited_before

    service.resume_crawl_task(task_id)
    time.sleep(0.2)
    status = service.get_task_status(task_id)
    assert status["status"] == TaskStatus.RUNNING.value

    time.sleep(0.6)
    assert service.get_task_status(task_id)["visited_count"] > visited_before
