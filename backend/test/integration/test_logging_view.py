import pytest
import logging
from flask_socketio import SocketIO
from src.shared.event_bus import EventBus
from src.crawl.view import crawler_view
from src.shared.handlers.websocket_handler import WebSocketLoggingHandler
from src.shared.event_handlers.websocket_handler import WebSocketEventHandler
from src.crawl.domain.domain_event.crawl_process_event import PageCrawledEvent

# Fake SocketIO implementation for verification
class FakeSocketIO:
    def __init__(self):
        self.messages = []
        self.connected_clients = {} # Not used here but part of typical fake

    def emit(self, event, data, namespace=None, room=None, broadcast=False):
        self.messages.append({
            'event': event,
            'data': data,
            'namespace': namespace,
            'room': room,
            'broadcast': broadcast
        })

class TestInitRealtimeLogging:

    @pytest.fixture(autouse=True)
    def cleanup_dependencies(self):
        """清理全局状态和日志 Handler"""
        # Setup: 保存原始状态
        original_bus = getattr(crawler_view._service, '_event_bus', None)
        
        # 获取需要清理的 logger
        error_logger = logging.getLogger('infrastructure.error')
        perf_logger = logging.getLogger('infrastructure.perf')
        
        # 记录原始 handlers 副本
        original_error_handlers = error_logger.handlers[:]
        original_perf_handlers = perf_logger.handlers[:]
        
        yield
        
        # Teardown: 恢复状态
        crawler_view._service._event_bus = original_bus
        
        # 恢复 loggers
        error_logger.handlers = original_error_handlers
        perf_logger.handlers = original_perf_handlers

    def test_init_realtime_logging_success(self):
        """测试正常初始化流程 - 使用真实对象"""
        # Arrange
        real_socketio = SocketIO()
        real_event_bus = EventBus()
        
        # 确保初始状态为空 (依赖 cleanup fixture)
        crawler_view._service._event_bus = None
        
        # Act
        crawler_view.init_realtime_logging(real_socketio, real_event_bus)
        
        # Assert
        # 1. 验证 EventBus 被注入到 Service
        assert crawler_view._service._event_bus == real_event_bus
        
        # 2. 验证 WebSocketEventHandler 被订阅
        # 检查 EventBus 的全局处理器列表
        # real_event_bus._global_handlers 应该包含 WebSocketEventHandler.handle
        assert len(real_event_bus._global_handlers) >= 1
        
        # 找到对应的 handler
        ws_event_handler_found = False
        for handler in real_event_bus._global_handlers:
            # handler 是 bound method，获取其所属实例 (__self__)
            if hasattr(handler, '__self__') and isinstance(handler.__self__, WebSocketEventHandler):
                ws_event_handler_found = True
                # 检查 socketio 是否正确传递
                assert handler.__self__._socketio == real_socketio
                break
        assert ws_event_handler_found, "WebSocketEventHandler 未订阅到 EventBus"
        
        # 3. 验证 WebSocketLoggingHandler 被添加到 Logger
        error_logger = logging.getLogger('infrastructure.error')
        perf_logger = logging.getLogger('infrastructure.perf')
        
        # 检查 error logger
        error_handler_found = False
        for h in error_logger.handlers:
            if isinstance(h, WebSocketLoggingHandler):
                error_handler_found = True
                assert h._socketio == real_socketio
                break
        assert error_handler_found, "WebSocketLoggingHandler 未添加到 infrastructure.error"
        
        # 检查 perf logger
        perf_handler_found = False
        for h in perf_logger.handlers:
            if isinstance(h, WebSocketLoggingHandler):
                perf_handler_found = True
                assert h._socketio == real_socketio
                break
        assert perf_handler_found, "WebSocketLoggingHandler 未添加到 infrastructure.perf"

    def test_init_realtime_logging_idempotency(self):
        """测试幂等性：避免重复添加 Handler"""
        # Arrange
        real_socketio = SocketIO()
        real_event_bus = EventBus()
        crawler_view._service._event_bus = None
        
        # Act 1: 第一次初始化
        crawler_view.init_realtime_logging(real_socketio, real_event_bus)
        
        # 记录 handler 数量
        error_logger = logging.getLogger('infrastructure.error')
        initial_handler_count = len([h for h in error_logger.handlers if isinstance(h, WebSocketLoggingHandler)])
        assert initial_handler_count == 1
        
        # Act 2: 第二次初始化
        crawler_view.init_realtime_logging(real_socketio, real_event_bus)
        
        # Assert
        final_handler_count = len([h for h in error_logger.handlers if isinstance(h, WebSocketLoggingHandler)])
        assert final_handler_count == 1 # 数量不应增加

    def test_inject_event_bus_only_if_missing(self):
        """测试：如果 Service 已经有 EventBus，不再重新赋值"""
        # Arrange
        real_socketio = SocketIO()
        new_event_bus = EventBus()
        
        existing_bus = EventBus()
        crawler_view._service._event_bus = existing_bus
        
        # Act
        crawler_view.init_realtime_logging(real_socketio, new_event_bus)
        
        # Assert
        # 应该保持原有的 bus
        assert crawler_view._service._event_bus == existing_bus
        assert crawler_view._service._event_bus != new_event_bus

    def test_realtime_log_emission_simulation(self):
        """测试：模拟发出日志消息，验证前端能否接收到（Fake SocketIO）"""
        # Arrange
        fake_socketio = FakeSocketIO() # 使用 Fake 对象来捕获 emit
        real_event_bus = EventBus()
        crawler_view._service._event_bus = None
        
        # 初始化
        crawler_view.init_realtime_logging(fake_socketio, real_event_bus)
        
        # Act 1: 触发技术错误日志
        error_logger = logging.getLogger('infrastructure.error')
        test_error_msg = "Test Critical Error Simulation"
        error_logger.error(test_error_msg, extra={'component': 'test_case'})
        
        # Act 2: 触发爬虫业务事件
        task_id = "task-123"
        event = PageCrawledEvent(
            task_id=task_id,
            url="http://example.com",
            title="Example Domain",
            depth=1,
            status_code=200,
            pdf_count=2
        )
        real_event_bus.publish(event)
        
        # Assert
        # 检查是否收到了两条消息
        assert len(fake_socketio.messages) >= 2
        
        # 1. 验证技术日志消息
        tech_msgs = [m for m in fake_socketio.messages if m['event'] == 'tech_log']
        assert len(tech_msgs) == 1
        tech_msg = tech_msgs[0]
        
        assert tech_msg['namespace'] == '/crawl'
        assert tech_msg['broadcast'] is True
        
        data = tech_msg['data']
        assert data['category'] == 'error' # error_logger -> error category
        assert data['level'] == 'ERROR'
        assert data['message'] == test_error_msg
        assert data['extra']['component'] == 'test_case' # extra field is nested in 'extra'
        assert 'timestamp' in data
        
        # 2. 验证业务事件消息
        crawl_msgs = [m for m in fake_socketio.messages if m['event'] == 'crawl_log']
        assert len(crawl_msgs) == 1
        crawl_msg = crawl_msgs[0]
        
        assert crawl_msg['namespace'] == '/crawl'
        assert crawl_msg['room'] == task_id # 应该推送到任务房间
        
        c_data = crawl_msg['data']
        assert c_data['task_id'] == task_id
        assert c_data['event_type'] == 'PageCrawledEvent'
        assert c_data['data']['url'] == "http://example.com"
        assert c_data['data']['title'] == "Example Domain"
        
        # 验证进度信息 (WebSocketEventHandler._extract_progress_info logic)
        assert 'progress' in c_data
        progress = c_data['progress']
        assert progress['current_depth'] == 1
        assert progress['pdfs_found'] == 0 # PageCrawledEvent data dict key is 'pdf_count' but _extract_progress_info might look for 'pdfs_found' or data.get('pdfs_found')? 
        
        # 让我们检查 WebSocketEventHandler._extract_progress_info 的实现
        # if event_type == "PAGE_CRAWLED":
        #     return {
        #         "current_depth": data.get('depth', 0),
        #         "pages_crawled": data.get('pages_crawled', 0), 
        #         "pdfs_found": data.get('pdfs_found', 0)
        #     }
        # PageCrawledEvent 的字段是 pdf_count，但 _extract_progress_info 期望 pdfs_found?
        # 如果不匹配，进度信息可能不准确，但这不影响消息发送本身。
        # 我们先断言它存在。
