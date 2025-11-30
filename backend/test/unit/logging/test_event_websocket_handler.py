import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from datetime import datetime

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parents[3]
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from src.shared.event_handlers.websocket_handler import WebSocketEventHandler
from src.shared.domain.events import DomainEvent

# Mock Events
@dataclass
class MockPageCrawledEvent(DomainEvent):
    url: str = "http://example.com"
    depth: int = 1
    pages_crawled: int = 5
    pdfs_found: int = 2

@dataclass
class MockTaskCompletedEvent(DomainEvent):
    total_pages: int = 100
    total_pdfs: int = 20
    elapsed_time: float = 50.5

@dataclass
class MockCrawlErrorEvent(DomainEvent):
    error_count: int = 1
    error_message: str = "Connection failed"

@dataclass
class MockGenericEvent(DomainEvent):
    pass

class TestWebSocketEventHandler:
    
    @pytest.fixture
    def mock_socketio(self):
        return MagicMock()
    
    @pytest.fixture
    def handler(self, mock_socketio):
        # 确保日志记录器不会实际输出到控制台干扰测试结果
        handler = WebSocketEventHandler(mock_socketio, namespace='/test')
        return handler

    def test_initialization(self, mock_socketio):
        handler = WebSocketEventHandler(mock_socketio, namespace='/custom')
        assert handler._socketio == mock_socketio
        assert handler._namespace == '/custom'

    def test_handle_page_crawled_event(self, handler, mock_socketio):
        """测试处理页面爬取事件，验证进度提取"""
        task_id = "task_page"
        event = MockPageCrawledEvent(task_id=task_id)
        
        # Mock event_type property since our mock class name is MockPageCrawledEvent
        # But the handler logic checks for "PAGE_CRAWLED" string literal in _extract_progress_info
        # Wait, DomainEvent.event_type returns class name by default.
        # The handler checks: if event_type == "PAGE_CRAWLED"
        # So we need to either rename our mock class or mock the event_type property.
        # Let's mock the property for this test to match the handler's expectation.
        with patch.object(MockPageCrawledEvent, 'event_type', 'PAGE_CRAWLED'):
            handler.handle(event)
        
        mock_socketio.emit.assert_called_once()
        args, kwargs = mock_socketio.emit.call_args
        
        assert args[0] == 'crawl_log'
        payload = args[1]
        assert kwargs['namespace'] == '/test'
        assert kwargs['room'] == task_id
        
        # Verify payload content
        assert payload['task_id'] == task_id
        assert payload['event_type'] == 'PAGE_CRAWLED'
        assert payload['progress']['current_depth'] == 1
        assert payload['progress']['pages_crawled'] == 5
        assert payload['progress']['pdfs_found'] == 2

    def test_handle_task_completed_event(self, handler, mock_socketio):
        """测试任务完成事件"""
        task_id = "task_done"
        event = MockTaskCompletedEvent(task_id=task_id)
        
        with patch.object(MockTaskCompletedEvent, 'event_type', 'CRAWL_COMPLETED'):
            handler.handle(event)
        
        payload = mock_socketio.emit.call_args[0][1]
        assert payload['progress']['status'] == 'completed'
        assert payload['progress']['total_pages'] == 100
        assert payload['progress']['elapsed_time'] == 50.5

    def test_handle_crawl_error_event(self, handler, mock_socketio):
        """测试爬取错误事件"""
        task_id = "task_err"
        event = MockCrawlErrorEvent(task_id=task_id)
        
        with patch.object(MockCrawlErrorEvent, 'event_type', 'CRAWL_ERROR'):
            handler.handle(event)
            
        payload = mock_socketio.emit.call_args[0][1]
        assert payload['progress']['status'] == 'error'
        assert payload['progress']['error_count'] == 1

    def test_handle_generic_event(self, handler, mock_socketio):
        """测试普通事件（无特定进度信息）"""
        task_id = "task_gen"
        event = MockGenericEvent(task_id=task_id)
        
        handler.handle(event)
        
        payload = mock_socketio.emit.call_args[0][1]
        assert payload['progress'] is None
        assert payload['event_type'] == 'MockGenericEvent'

    def test_handle_socket_exception(self, handler, mock_socketio):
        """测试 Socket 发送异常时的处理"""
        mock_socketio.emit.side_effect = Exception("Connection lost")
        event = MockGenericEvent(task_id="task_fail")
        
        # Should not raise exception
        with patch.object(handler._logger, 'error') as mock_log:
            handler.handle(event)
            mock_log.assert_called_once()
            assert "WebSocket推送失败" in mock_log.call_args[0][0]

    def test_broadcast_to_all(self, handler, mock_socketio):
        """测试广播功能"""
        msg = {"info": "system update"}
        handler.broadcast_to_all(msg)
        
        mock_socketio.emit.assert_called_with(
            'broadcast',
            msg,
            namespace='/test'
        )

    def test_broadcast_exception(self, handler, mock_socketio):
        """测试广播异常处理"""
        mock_socketio.emit.side_effect = Exception("Broadcast fail")
        
        with patch.object(handler._logger, 'error') as mock_log:
            handler.broadcast_to_all({})
            mock_log.assert_called_once()
            assert "广播失败" in mock_log.call_args[0][0]

    def test_send_to_task(self, handler, mock_socketio):
        """测试发送给指定任务"""
        task_id = "task_123"
        msg = {"cmd": "stop"}
        handler.send_to_task(task_id, msg)
        
        mock_socketio.emit.assert_called_with(
            'task_message',
            msg,
            namespace='/test',
            room=task_id
        )

    def test_send_to_task_exception(self, handler, mock_socketio):
        """测试发送给任务时的异常处理"""
        mock_socketio.emit.side_effect = Exception("Send fail")
        
        with patch.object(handler._logger, 'error') as mock_log:
            handler.send_to_task("task_1", {})
            mock_log.assert_called_once()
            assert "发送消息到任务 task_1 失败" in mock_log.call_args[0][0]
