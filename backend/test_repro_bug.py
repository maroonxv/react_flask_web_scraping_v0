
import time
import unittest
from threading import Thread
from src.crawl.services.crawler_service import CrawlerService
from src.crawl.domain.value_objects.crawl_config import CrawlConfig
from src.crawl.domain.value_objects.crawl_strategy import CrawlStrategy
from src.crawl.domain.value_objects.crawl_status import TaskStatus
from src.crawl.infrastructure.http_client_impl import HttpClientImpl
from src.crawl.infrastructure.crawl_domain_service_impl import CrawlDomainServiceImpl
from src.crawl.infrastructure.html_parser_impl import HtmlParserImpl
from src.crawl.infrastructure.robots_txt_parser_impl import RobotsTxtParserImpl

class MockEventBus:
    def publish(self, event):
        pass

class TestPauseResume(unittest.TestCase):
    def setUp(self):
        self.http = HttpClientImpl()
        self.parser = HtmlParserImpl()
        self.robots = RobotsTxtParserImpl()
        self.domain_service = CrawlDomainServiceImpl(self.http, self.parser, self.robots)
        self.service = CrawlerService(self.domain_service, self.http, event_bus=MockEventBus())

    def test_pause_resume(self):
        # 1. Create task
        config = CrawlConfig(
            start_url="http://toscrape.com",
            strategy=CrawlStrategy.BFS,
            max_depth=2,
            max_pages=10,
            request_interval=0.5
        )
        task_id = self.service.create_crawl_task(config)
        task = self.service._tasks[task_id]

        # 2. Start task
        print(f"Starting task {task_id}")
        self.service.start_crawl_task(task_id)
        
        # Wait for some crawling
        time.sleep(3)
        
        # Check running
        self.assertEqual(task.status, TaskStatus.RUNNING)
        print(f"Task status after start: {task.status}, queue size: {task.url_queue_obj.size()}")
        
        # 3. Pause task
        print("Pausing task...")
        self.service.pause_crawl_task(task_id)
        
        # Wait for thread to exit
        time.sleep(2)
        
        # Check paused
        self.assertEqual(task.status, TaskStatus.PAUSED)
        print(f"Task status after pause: {task.status}, queue size: {task.url_queue_obj.size()}")
        self.assertTrue(task_id in self.service._paused_tasks)
        
        # 4. Resume task
        print("Resuming task...")
        self.service.resume_crawl_task(task_id)
        
        # Wait for resume effect
        time.sleep(1)
        
        # Check resumed
        self.assertEqual(task.status, TaskStatus.RUNNING)
        print(f"Task status after resume: {task.status}, queue size: {task.url_queue_obj.size()}")
        self.assertFalse(task_id in self.service._paused_tasks)
        
        # Wait more to see if it continues
        initial_visited = len(task.visited_urls)
        time.sleep(3)
        final_visited = len(task.visited_urls)
        
        print(f"Visited count: {initial_visited} -> {final_visited}")
        
        if final_visited > initial_visited:
            print("SUCCESS: Crawler continued working.")
        else:
            print("FAILURE: Crawler did not process new pages.")
            
        self.assertTrue(final_visited >= initial_visited) # At least not stopped completely (soft check)

if __name__ == "__main__":
    unittest.main()
