from typing import Dict, List, Callable
import logging


class EventBus:
    """
    事件总线 - 共享基础设施
    不定义接口，直接实现（因为只有一个版本）
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._logger = logging.getLogger(__name__)
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
        self._logger.debug(f"订阅事件: {event_type}")
    
    def publish(self, event) -> None:
        """发布事件"""
        handlers = self._handlers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                # 这里的handler是一个具体的事件处理函数，如LoggingEventHandler.handle
                handler(event)
            except Exception as e:
                self._logger.error(f"事件处理失败: {event.event_type} - {str(e)}")
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)