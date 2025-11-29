# infrastructure/queue/url_queue_impl.py
from collections import deque
import heapq
from typing import Optional, List
from ..domain.demand_interface.i_url_queue import IUrlQueue
from ..domain.value_objects.queued_url import QueuedUrl


class UrlQueueImpl(IUrlQueue):
    """URL队列实现 - 支持BFS/DFS/优先级三种策略"""
    
    def __init__(self):
        self._strategy: str = "BFS"
        self._max_depth: int = 3
        self._current_depth: int = 0
        
        # 不同策略使用不同数据结构
        self._bfs_queue: deque = deque()  # BFS: 双端队列(FIFO)
        self._dfs_stack: List[QueuedUrl] = []  # DFS: 栈(LIFO)
        self._priority_heap: List[tuple] = []  # PRIORITY: 最小堆(需要取负数实现最大堆)
        self._heap_counter: int = 0  # 用于优先级相同时保持插入顺序
    
    def initialize(self, start_url: str, strategy: str, max_depth: int = 3) -> None:
        """初始化队列"""
        if strategy not in ["BFS", "DFS", "PRIORITY"]:
            raise ValueError(f"不支持的策略: {strategy}，仅支持 BFS/DFS/PRIORITY")
        
        self._strategy = strategy
        self._max_depth = max_depth
        self._current_depth = 0
        
        # 清空所有队列
        self.clear()
        
        # 添加起始URL(深度为0)
        self.enqueue(start_url, depth=0, priority=100)
    
    def enqueue(self, url: str, depth: int, priority: int = 0) -> None:
        """添加URL到队列"""
        # 深度限制检查
        if depth > self._max_depth:
            return
        
        queued_url = QueuedUrl(url=url, depth=depth, priority=priority)
        
        if self._strategy == "BFS":
            self._bfs_queue.append(queued_url)
        
        elif self._strategy == "DFS":
            self._dfs_stack.append(queued_url)
        
        elif self._strategy == "PRIORITY":
            # 使用负优先级实现最大堆(Python的heapq是最小堆)
            # 同时使用counter保证相同优先级时按插入顺序
            heapq.heappush(
                self._priority_heap,
                (-priority, self._heap_counter, queued_url)
            )
            self._heap_counter += 1
    
    def dequeue(self) -> Optional[QueuedUrl]:
        """从队列取出下一个URL"""
        queued_url = None
        
        try:
            if self._strategy == "BFS":
                if self._bfs_queue:
                    queued_url = self._bfs_queue.popleft()
            
            elif self._strategy == "DFS":
                if self._dfs_stack:
                    queued_url = self._dfs_stack.pop()
            
            elif self._strategy == "PRIORITY":
                if self._priority_heap:
                    _, _, queued_url = heapq.heappop(self._priority_heap)
            
            if queued_url:
                self._current_depth = queued_url.depth
            
            return queued_url
        
        except (IndexError, KeyError):
            return None
    
    def is_empty(self) -> bool:
        """判断队列是否为空"""
        if self._strategy == "BFS":
            return len(self._bfs_queue) == 0
        elif self._strategy == "DFS":
            return len(self._dfs_stack) == 0
        elif self._strategy == "PRIORITY":
            return len(self._priority_heap) == 0
        return True
    
    def size(self) -> int:
        """返回队列大小"""
        if self._strategy == "BFS":
            return len(self._bfs_queue)
        elif self._strategy == "DFS":
            return len(self._dfs_stack)
        elif self._strategy == "PRIORITY":
            return len(self._priority_heap)
        return 0
    
    def clear(self) -> None:
        """清空所有队列"""
        self._bfs_queue.clear()
        self._dfs_stack.clear()
        self._priority_heap.clear()
        self._heap_counter = 0
        self._current_depth = 0
    
    def get_current_depth(self) -> int:
        """获取当前处理的URL深度"""
        return self._current_depth
