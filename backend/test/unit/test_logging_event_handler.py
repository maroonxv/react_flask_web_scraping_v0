import pytest
import logging
import shutil
import sys
from pathlib import Path
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock, patch

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from src.shared.event_handlers.logging_handler import LoggingEventHandler
from src.shared.domain.events import DomainEvent

# Mock events
@dataclass
class TaskStartedEvent(DomainEvent):
    pass

@dataclass
class TaskFailedEvent(DomainEvent):
    error_message: str = "Mock error"
    stack_trace: str = ""

class TestLoggingEventHandler:
    
    @pytest.fixture
    def handler(self, tmp_path):
        """创建一个使用临时目录的handler"""
        # 清理全局 logger 的 handlers，防止之前测试的残留干扰
        logger = logging.getLogger("src.shared.event_handlers.logging_handler")
        old_handlers = logger.handlers[:]
        logger.handlers = []

        # Patch Path inside the module to redirect log creation to tmp_path
        with patch('src.shared.event_handlers.logging_handler.logging.handlers.TimedRotatingFileHandler') as MockHandler:
            # 配置 Mock 实例的 level 属性，防止 logging 模块比较时出错 (int >= Mock)
            mock_instance = MockHandler.return_value
            mock_instance.level = logging.NOTSET
            
            handler = LoggingEventHandler(max_logs_per_task=10)
            # Manually override the task logs for a fresh start
            handler._task_logs = {}
            yield handler
            
            # Cleanup
            logger.handlers = old_handlers

    def test_initialization(self):
        # 清理 logger
        logger = logging.getLogger("src.shared.event_handlers.logging_handler")
        logger.handlers = []
        
        with patch('src.shared.event_handlers.logging_handler.logging.handlers.TimedRotatingFileHandler') as MockHandler:
            # 同样需要设置 level，防止如果测试中触发了日志记录导致崩溃
            mock_instance = MockHandler.return_value
            mock_instance.level = logging.NOTSET
            
            handler = LoggingEventHandler()
            assert handler._max_logs_per_task == 1000
            assert isinstance(handler._task_logs, dict)
            MockHandler.assert_called_once()
        
        # Cleanup
        logger.handlers = []

    def test_handle_dataclass_event(self, handler):
        """测试处理 Dataclass 类型的事件"""
        task_id = "task_123"
        event = TaskStartedEvent(task_id=task_id)
        
        handler.handle(event)
        
        logs = handler.get_logs(task_id)
        assert len(logs) == 1
        log = logs[0]
        assert log['task_id'] == task_id
        # event_type should match class name
        assert log['event_type'] == "TaskStartedEvent"
        assert log['level'] == "INFO"
        # 默认回退消息包含事件类型名称
        assert "任务开始" in log['message']

    def test_log_storage_limit(self, handler):
        """测试日志数量限制"""
        with patch('src.shared.event_handlers.logging_handler.logging.handlers.TimedRotatingFileHandler') as MockHandler:
            mock_instance = MockHandler.return_value
            mock_instance.level = logging.NOTSET
            
            small_handler = LoggingEventHandler(max_logs_per_task=3)
            task_id = "task_limit"
            
            for i in range(5):
                event = TaskStartedEvent(task_id=task_id)
                small_handler.handle(event)
            
            logs = small_handler.get_logs(task_id)
            assert len(logs) == 3

    def test_query_methods(self, handler):
        """测试各种查询方法"""
        task_id = "task_query"
        
        # Add INFO log
        handler.handle(TaskStartedEvent(task_id=task_id))
        
        # Add ERROR log
        handler.handle(TaskFailedEvent(task_id=task_id))
        
        # Test get_logs
        assert len(handler.get_logs(task_id)) == 2
        assert len(handler.get_logs(task_id, last_n=1)) == 1
        
        # Test get_logs_by_level
        infos = handler.get_logs_by_level(task_id, "INFO")
        errors = handler.get_logs_by_level(task_id, "ERROR")
        assert len(infos) >= 1 # Depending on default mapping
        assert len(errors) == 1
        
        # Test get_error_logs
        assert len(handler.get_error_logs(task_id)) == 1
        
        # Test has_errors
        assert handler.has_errors(task_id) is True
        assert handler.has_errors("non_existent") is False

    def test_custom_namer(self, handler):
        """测试日志文件命名逻辑"""
        # Test case 1: Standard format
        default_name = "/path/to/logs/crawler_log.log.2025-11-30"
        
        # Fix path separator for windows/linux consistency in test assertion
        # We compare parts or normalized paths
        result = handler._custom_namer(default_name)
        assert Path(result).name == "2025-11-30_crawler_log.log"
        
        # Test case 2: No date suffix
        name_no_date = "/path/to/crawler.log"
        assert handler._custom_namer(name_no_date) == name_no_date

    def test_clear_logs(self, handler):
        task_id = "task_clear"
        handler.handle(TaskStartedEvent(task_id=task_id))
        assert len(handler.get_logs(task_id)) == 1
        
        handler.clear_logs(task_id)
        assert len(handler.get_logs(task_id)) == 0

    def test_handle_exception_safety(self, handler):
        """测试 handle 方法发生异常时不会崩溃"""
        with patch.object(handler, '_format_event_to_log', side_effect=Exception("Boom")):
            event = TaskStartedEvent(task_id="task_err")
            # Should not raise
            handler.handle(event)
            # Log should be empty for this task
            assert len(handler.get_logs("task_err")) == 0
