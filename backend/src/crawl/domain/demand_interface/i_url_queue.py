from abc import ABC, abstractmethod
from typing import Optional
from ..value_objects.queued_url import QueuedUrl


class IUrlQueue(ABC):
    """
    URL队列接口 - 管理待爬取URL的存取策略
    职责: 根据不同策略(BFS/DFS/优先级)管理URL队列
    """
    
    @abstractmethod
    def initialize(self, start_url: str, strategy: str, max_depth: int = 3) -> None:
        """
        初始化队列
        
        参数:
            start_url: 起始URL
            strategy: 爬取策略 "BFS" | "DFS" | "PRIORITY"
            max_depth: 最大爬取深度
        """
        pass
    
    @abstractmethod
    def enqueue(self, url: str, depth: int, priority: int = 0) -> None:
        """
        添加URL到队列
        
        参数:
            url: 待爬取的URL
            depth: 当前深度(从起始URL开始计数)
            priority: 优先级(仅在PRIORITY策略下有效)
        """
        pass
    
    @abstractmethod
    def dequeue(self) -> Optional[QueuedUrl]:
        """
        从队列取出下一个URL
        
        返回:
            QueuedUrl对象，队列为空时返回None
        
        策略:
            - BFS: 先进先出(FIFO)
            - DFS: 后进先出(LIFO)
            - PRIORITY: 按优先级排序
        """
        pass
    
    @abstractmethod
    def is_empty(self) -> bool:
        """判断队列是否为空"""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """返回队列中URL数量"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """清空队列"""
        pass
    
    @abstractmethod
    def get_current_depth(self) -> int:
        """获取当前正在处理的URL深度"""
        pass
