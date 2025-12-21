import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 确保 backend 目录在 path 中
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from src.crawl.services.crawler_service import CrawlerService
from src.crawl.domain.entity.crawl_task import CrawlTask
from src.crawl.domain.value_objects.crawl_config import CrawlConfig
from src.crawl.domain.value_objects.crawl_status import TaskStatus
from src.crawl.domain.value_objects.crawl_result import CrawlResult

class TestCrawlerServiceDelay:
    
    @pytest.fixture
    def mock_components(self):
        return {
            "domain_service": Mock(),
            "http_client": Mock(),
            "repository": Mock(),
            "event_bus": Mock()
        }

    @pytest.fixture
    def service(self, mock_components):
        return CrawlerService(
            crawl_domain_service=mock_components["domain_service"],
            http_client=mock_components["http_client"],
            repository=mock_components["repository"],
            event_bus=mock_components["event_bus"]
        )

    @patch('src.crawl.services.crawler_service.time')
    def test_crawl_loop_respects_robots_delay(self, mock_time, service, mock_components):
        """测试爬取循环遵守 robots.txt 的延迟"""
        # Setup
        task_id = "test_task"
        config = CrawlConfig(
            start_url="http://example.com",
            request_interval=1.0  # 用户配置 1秒
        )
        
        # Mock Task
        task = MagicMock()
        task.id = task_id
        task.config = config
        task.status = TaskStatus.RUNNING
        task.is_url_visited.return_value = False
        task.is_url_allowed.return_value = True
        task.visited_urls = []
        
        # Mock Queue
        queue_mock = MagicMock()
        url_obj = MagicMock()
        url_obj.url = "http://example.com/page1"
        url_obj.depth = 0
        
        # 第一次 dequeue 返回 url，第二次返回 None 结束循环
        queue_mock.is_empty.side_effect = [False, False, True]
        queue_mock.dequeue.side_effect = [url_obj, None]
        task.url_queue_obj = queue_mock
        
        # Mock HTTP Response
        response = Mock()
        response.is_success = True
        response.content = "<html></html>"
        mock_components["http_client"].get.return_value = response
        
        # Mock Domain Service Metadata & Links
        metadata = Mock()
        metadata.title = "Test Title"
        metadata.author = None
        metadata.abstract = None
        metadata.keywords = []
        metadata.publish_date = None
        mock_components["domain_service"].extract_page_metadata.return_value = metadata
        mock_components["domain_service"].discover_crawlable_links.return_value = []
        mock_components["domain_service"].identify_pdf_links.return_value = []
        
        # Key: 设置 Robots Delay 为 5.0 秒 (大于用户配置的 1.0)
        mock_components["domain_service"].get_domain_crawl_delay.return_value = 5.0
        
        # Mock time.time()
        # 1. loop start: 100.0
        # 2. elapsed check: 100.1
        mock_time.time.side_effect = [100.0, 100.1, 105.0, 105.0, 105.0] 
        
        # Mock CrawlResult creation implicitly handled by task.add_crawl_result
        
        # 执行
        service._execute_crawl_loop(task)
        
        # 验证
        # 应该调用了 get_domain_crawl_delay
        mock_components["domain_service"].get_domain_crawl_delay.assert_called_with("http://example.com/page1")
        
        # 验证 sleep 时间
        # Target interval = max(1.0, 5.0) = 5.0
        # Elapsed = 100.1 - 100.0 = 0.1
        # Sleep = 5.0 - 0.1 = 4.9
        
        # 检查 time.sleep 是否被调用且参数接近 4.9
        found = False
        for call in mock_time.sleep.call_args_list:
            args, _ = call
            if args and abs(args[0] - 4.9) < 0.001:
                found = True
                break
        
        assert found, f"Expected sleep(4.9) not found. Calls: {mock_time.sleep.call_args_list}"

    @patch('src.crawl.services.crawler_service.time')
    def test_crawl_loop_respects_user_interval_when_larger(self, mock_time, service, mock_components):
        """测试当用户配置间隔更大时，遵守用户配置"""
        # Setup
        task_id = "test_task"
        config = CrawlConfig(
            start_url="http://example.com",
            request_interval=10.0  # 用户配置 10秒
        )
        
        # Mock Task
        task = MagicMock()
        task.id = task_id
        task.config = config
        task.status = TaskStatus.RUNNING
        task.is_url_visited.return_value = False
        task.is_url_allowed.return_value = True
        task.visited_urls = []
        
        queue_mock = MagicMock()
        url_obj = MagicMock()
        url_obj.url = "http://example.com/page1"
        url_obj.depth = 0
        
        queue_mock.is_empty.side_effect = [False, False, True]
        queue_mock.dequeue.side_effect = [url_obj, None]
        task.url_queue_obj = queue_mock
        
        response = Mock()
        response.is_success = True
        response.content = "<html></html>"
        mock_components["http_client"].get.return_value = response
        
        metadata = Mock()
        metadata.title = "Test"
        mock_components["domain_service"].extract_page_metadata.return_value = metadata
        mock_components["domain_service"].discover_crawlable_links.return_value = []
        mock_components["domain_service"].identify_pdf_links.return_value = []
        
        # Key: 设置 Robots Delay 为 5.0 秒 (小于用户配置的 10.0)
        mock_components["domain_service"].get_domain_crawl_delay.return_value = 5.0
        
        mock_time.time.side_effect = [100.0, 100.1, 110.0, 110.0]
        
        # 执行
        service._execute_crawl_loop(task)
        
        # 验证 sleep 时间
        # Target interval = max(10.0, 5.0) = 10.0
        # Elapsed = 0.1
        # Sleep = 9.9
        
        found = False
        for call in mock_time.sleep.call_args_list:
            args, _ = call
            if args and abs(args[0] - 9.9) < 0.001:
                found = True
                break
        
        assert found, f"Expected sleep(9.9) not found. Calls: {mock_time.sleep.call_args_list}"
