# shared/event_handlers/logging_handler.py
from collections import deque
from typing import Dict, List, Optional
from .base_handler import BaseEventHandler

class LoggingEventHandler(BaseEventHandler):
    """
    日志事件处理器
    职责：
    1. 捕获领域事件并转换为日志格式
    2. 按任务ID分组存储日志到内存队列
    3. 提供日志查询接口供API调用
    """
    
    def __init__(self, max_logs_per_task: int = 1000):
        """
        初始化日志处理器
        
        参数:
            max_logs_per_task: 每个任务最多保留的日志条数（超出则丢弃最旧的）
        """
        # 每个任务的日志队列: {task_id: deque}
        self._task_logs: Dict[str, deque] = {}
        self._max_logs_per_task = max_logs_per_task
    
    def handle(self, event) -> None:
        """
        处理事件：转换为日志格式并存储
        
        参数:
            event: DomainEvent 实例
        """
        task_id = event.task_id
        
        # 确保任务有日志队列
        if task_id not in self._task_logs:
            self._task_logs[task_id] = deque(maxlen=self._max_logs_per_task)
        
        # 转换事件为日志格式（使用基类方法）
        log_entry = self._format_event_to_log(event)
        
        # 存储日志
        self._task_logs[task_id].append(log_entry)
    
    def get_logs(self, task_id: str, last_n: Optional[int] = None) -> List[dict]:
        """
        获取任务日志
        
        参数:
            task_id: 任务ID
            last_n: 获取最近N条，None表示全部
            
        返回:
            日志字典列表
        """
        logs = self._task_logs.get(task_id, deque())
        
        if last_n:
            return list(logs)[-last_n:]
        return list(logs)
    
    def get_all_task_ids(self) -> List[str]:
        """获取所有有日志的任务ID列表"""
        return list(self._task_logs.keys())
    
    def clear_logs(self, task_id: str) -> None:
        """
        清空指定任务的日志
        
        参数:
            task_id: 任务ID
        """
        if task_id in self._task_logs:
            self._task_logs[task_id].clear()
    
    def get_log_count(self, task_id: str) -> int:
        """
        获取任务日志条数
        
        参数:
            task_id: 任务ID
            
        返回:
            日志条数
        """
        return len(self._task_logs.get(task_id, deque()))
    
    def get_logs_by_level(self, task_id: str, level: str) -> List[dict]:
        """
        获取指定级别的日志
        
        参数:
            task_id: 任务ID
            level: 日志级别 (INFO/ERROR/SUCCESS/WARNING)
            
        返回:
            过滤后的日志列表
        """
        logs = self._task_logs.get(task_id, deque())
        return [log for log in logs if log['level'] == level]
    
    def get_error_logs(self, task_id: str) -> List[dict]:
        """
        快捷方法：获取所有错误日志
        
        参数:
            task_id: 任务ID
            
        返回:
            错误日志列表
        """
        return self.get_logs_by_level(task_id, 'ERROR')
    
    def has_errors(self, task_id: str) -> bool:
        """
        检查任务是否有错误日志
        
        参数:
            task_id: 任务ID
            
        返回:
            True表示有错误
        """
        return len(self.get_error_logs(task_id)) > 0
