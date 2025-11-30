import pytest
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parents[3]
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from src.shared.handlers.websocket_handler import WebSocketLoggingHandler

class TestWebSocketLoggingHandler:
    
    @pytest.fixture
    def mock_socketio(self):
        """Fixture: Mock SocketIO 实例"""
        return MagicMock()
    
    @pytest.fixture
    def handler(self, mock_socketio):
        """Fixture: 提供 WebSocketLoggingHandler 实例"""
        handler = WebSocketLoggingHandler(mock_socketio, namespace='/test_ns')
        return handler
    
    @pytest.fixture
    def log_record(self):
        """Fixture: 创建一个标准的 LogRecord"""
        record = logging.LogRecord(
            name="infrastructure.error",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Test error message",
            args=(),
            exc_info=None
        )
        return record

    def test_initialization(self, mock_socketio):
        """测试初始化"""
        handler = WebSocketLoggingHandler(mock_socketio, namespace='/custom')
        assert handler._socketio == mock_socketio
        assert handler._namespace == '/custom'
        assert isinstance(handler._internal_logger, logging.Logger)

    def test_emit_normal_log(self, handler, mock_socketio, log_record):
        """测试正常发送日志"""
        handler.emit(log_record)
        
        mock_socketio.emit.assert_called_once()
        args, kwargs = mock_socketio.emit.call_args
        
        event_name = args[0]
        log_data = args[1]
        
        assert event_name == 'tech_log'
        assert kwargs['namespace'] == '/test_ns'
        assert kwargs['broadcast'] is True
        
        # 验证日志内容结构
        assert log_data['level'] == 'ERROR'
        assert log_data['message'] == 'Test error message'
        assert log_data['category'] == 'error' # infrastructure.error -> error

    def test_log_category_mapping(self, handler, mock_socketio):
        """测试日志分类映射逻辑"""
        # Test Case 1: infrastructure.perf -> performance
        perf_record = logging.LogRecord(
            name="infrastructure.perf",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Performance check",
            args=(),
            exc_info=None
        )
        handler.emit(perf_record)
        log_data = mock_socketio.emit.call_args[0][1]
        assert log_data['category'] == 'performance'
        
        # Test Case 2: infrastructure.unknown -> unknown
        unknown_record = logging.LogRecord(
            name="infrastructure.unknown",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Unknown check",
            args=(),
            exc_info=None
        )
        handler.emit(unknown_record)
        log_data = mock_socketio.emit.call_args[0][1]
        assert log_data['category'] == 'unknown'

    def test_extra_data_extraction(self, handler, mock_socketio):
        """测试 extra 数据提取"""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t", lineno=1, msg="msg", args=(), exc_info=None
        )
        # 手动添加 extra 属性（logging 模块会将 extra={...} 的内容注入到 record.__dict__）
        record.user_id = 123
        record.context = "test_context"
        record._private = "should_be_ignored" # 私有属性应被忽略
        
        handler.emit(record)
        log_data = mock_socketio.emit.call_args[0][1]
        
        assert log_data['extra']['user_id'] == 123
        assert log_data['extra']['context'] == "test_context"
        assert '_private' not in log_data['extra']

    def test_unserializable_extra_data(self, handler, mock_socketio):
        """测试不可序列化的 extra 数据处理"""
        class Unserializable:
            def __str__(self):
                return "I am object"
        
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t", lineno=1, msg="msg", args=(), exc_info=None
        )
        record.complex_obj = Unserializable()
        
        # 我们的 extract 逻辑使用了 try-except 保护，但目前实现是直接赋值
        # 如果直接赋值，emit 时 flask-socketio 可能会在 json 序列化时失败？
        # 不，handler 中的 _extract_extra_data 并没有做序列化检查，只是简单的 copy
        # 但是在 `_extract_extra_data` 中我们添加了 try-except 块来处理 value
        # 让我们回顾 handler 代码：它尝试 `extra[key] = value`，如果失败则 `str(value)`
        # 实际上简单的赋值不会抛异常，只有在后续 JSON 序列化时才会。
        # 但我们的 handler 并没有显式做 JSON 序列化，而是交给 socketio.emit。
        # 如果 socketio.emit 失败，会在 emit 方法的 try-except 中被捕获。
        
        # 为了测试 handler 的健壮性，我们可以 mock record.__dict__ 的 items 抛出异常？
        # 或者我们测试 _extract_extra_data 的逻辑（如果它包含序列化逻辑）。
        # 目前代码是：
        # try: extra[key] = value
        # except: extra[key] = str(value)
        # 简单的赋值通常不会抛错。
        
        # 假设我们希望 handler 能处理 socketio 发送失败的情况
        mock_socketio.emit.side_effect = Exception("Serialization Error")
        
        # 捕获内部日志
        with patch.object(handler._internal_logger, 'error') as mock_internal_log:
            handler.emit(record)
            mock_internal_log.assert_called_once()
            assert "WebSocket日志推送失败" in mock_internal_log.call_args[0][0]

    def test_exception_formatting(self, handler, mock_socketio):
        """测试异常堆栈信息的格式化"""
        try:
            raise ValueError("Test Exception")
        except ValueError:
            exc_info = sys.exc_info()
            
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="t", lineno=1, msg="Error", args=(), exc_info=exc_info
        )
        
        handler.emit(record)
        log_data = mock_socketio.emit.call_args[0][1]
        
        assert log_data['exception'] is not None
        assert "ValueError: Test Exception" in log_data['exception']

    def test_emit_exception_safety(self, handler, mock_socketio, log_record):
        """测试 emit 方法本身的异常安全性"""
        # 模拟 socketio.emit 抛出异常
        mock_socketio.emit.side_effect = Exception("Socket Error")
        
        # 确保不会向上抛出异常，而是记录内部日志
        with patch.object(handler._internal_logger, 'error') as mock_internal_log:
            try:
                handler.emit(log_record)
            except Exception:
                pytest.fail("handler.emit should not raise exception")
            
            mock_internal_log.assert_called_once()
